"""HTTP API. Thin: validate input, call services, shape output."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import services
from ..ado import SEVERITIES, AdoClient, AdoCredentialMissing, AdoCredentialProvider, AdoError, PatCipher, pat_auth_header
from ..auth import SESSION_COOKIE, LoginFailed, ObservAuthClient, ObservIdentity, current_email, issue_session
from ..config import Settings, get_settings
from ..db import get_session
from ..engine.templates import DEFAULT_TEMPLATE, TEMPLATES
from ..models import Attachment, Interview, Question, QuestionStatus, RequestType, Role, User
from ..services import Deps, FlowError

router = APIRouter(prefix="/api")

PAT_EXPIRY_WARNING_DAYS = 14


def get_deps(request: Request) -> Deps:
    return request.app.state.deps


def _flow(exc: FlowError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=str(exc))


# ---------------------------------------------------------------- auth


class LoginIn(BaseModel):
    email: str
    password: str = ""


@router.post("/auth/login")
async def login(
    body: LoginIn,
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
):
    email = body.email.strip().lower()
    if not settings.may_log_in(email):
        detail = "目前是單人試用模式，只開放給擁有者登入" if settings.single_user else "目前是試用階段，你不在試用名單中"
        raise HTTPException(status_code=403, detail=detail)
    if settings.auth_mode == "dev":
        identity = ObservIdentity(observ_id=None, email=email, display_name=email.split("@")[0])
    else:
        client = ObservAuthClient(settings, getattr(request.app.state, "observ_transport", None))
        try:
            identity = await client.login(email, body.password)
        except LoginFailed as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    user = await session.get(User, identity.email)
    if user is None:
        user = User(email=identity.email)
        session.add(user)
    user.observ_id = identity.observ_id or user.observ_id
    user.display_name = identity.display_name or user.display_name
    await session.commit()

    response.set_cookie(
        SESSION_COOKIE,
        issue_session(settings, identity.email),
        max_age=settings.session_max_age_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.public_base_url.startswith("https"),
    )
    return {"email": identity.email}


@router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


async def _user(session: AsyncSession, email: str) -> User:
    user = await session.get(User, email)
    if user is None:  # session cookie from before the DB was reset
        user = User(email=email)
        session.add(user)
        await session.commit()
    return user


def _ado_status(user: User, settings: Settings) -> dict:
    connected = bool(user.ado_pat_encrypted)
    expires = user.ado_pat_expires_on
    return {
        "connected": connected,
        "dev_fallback": not connected and bool(settings.ado_dev_pat),
        "display_name": user.ado_display_name,
        "expires_on": expires.isoformat() if expires else None,
        "expiring_soon": bool(expires and expires - date.today() <= timedelta(days=PAT_EXPIRY_WARNING_DAYS)),
        "expired": bool(expires and expires < date.today()),
        "token_page": f"https://dev.azure.com/{settings.ado_org}/_usersSettings/tokens",
    }


@router.get("/me")
async def me(
    email: str = Depends(current_email),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    user = await _user(session, email)
    return {
        "email": user.email,
        "display_name": user.display_name,
        "default_role": user.default_role,
        "ado": _ado_status(user, settings),
    }


class MeIn(BaseModel):
    default_role: Role


@router.put("/me")
async def update_me(body: MeIn, email: str = Depends(current_email), session: AsyncSession = Depends(get_session)):
    user = await _user(session, email)
    user.default_role = body.default_role
    await session.commit()
    return {"ok": True}


class AdoPatIn(BaseModel):
    pat: str = Field(min_length=10)
    expires_on: date | None = None


@router.put("/me/ado")
async def connect_ado(
    body: AdoPatIn,
    request: Request,
    email: str = Depends(current_email),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    pat = body.pat.strip()
    client = AdoClient(settings, pat_auth_header(pat), getattr(request.app.state.deps, "ado_transport", None))
    try:
        identity = await client.whoami()
        # Prove the Work Items scope, not just a valid token
        await client.get_work_items([settings.ado_default_parent_id])
    except AdoCredentialMissing as exc:
        raise HTTPException(status_code=400, detail="PAT 無效，請確認有勾選 Work Items (Read & Write)") from exc
    except AdoError as exc:
        raise HTTPException(status_code=400, detail=f"PAT 驗證失敗：{exc}") from exc
    user = await _user(session, email)
    user.ado_pat_encrypted = PatCipher(settings.fernet_key).encrypt(pat)
    user.ado_display_name = identity.display_name
    user.ado_pat_expires_on = body.expires_on
    await session.commit()
    return _ado_status(user, settings)


@router.delete("/me/ado")
async def disconnect_ado(
    email: str = Depends(current_email),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    user = await _user(session, email)
    user.ado_pat_encrypted = None
    user.ado_display_name = None
    user.ado_pat_expires_on = None
    await session.commit()
    return _ado_status(user, settings)


async def _ado_for(request: Request, session: AsyncSession, email: str, settings: Settings) -> AdoClient:
    user = await _user(session, email)
    try:
        header = AdoCredentialProvider(settings).auth_header(user)
    except AdoCredentialMissing as exc:
        raise HTTPException(status_code=409, detail="尚未連結 Azure DevOps") from exc
    return AdoClient(settings, header, request.app.state.deps.ado_transport)


@router.get("/ado/work-items")
async def search_work_items(
    q: str,
    request: Request,
    email: str = Depends(current_email),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    if not q.strip():
        return []
    ado = await _ado_for(request, session, email, settings)
    try:
        items = await ado.search_work_items(q)
    except AdoCredentialMissing as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AdoError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return [i.__dict__ for i in items]


# ---------------------------------------------------------------- meta


@router.get("/meta")
async def meta(settings: Settings = Depends(get_settings)):
    return {
        "roles": [r.value for r in Role],
        "request_types": [t.value for t in RequestType],
        "templates": [{"id": t.id, "label": t.label} for t in TEMPLATES.values()],
        "default_template": {f"{r.value}:{t.value}": v for (r, t), v in DEFAULT_TEMPLATE.items()},
        "default_parent_id": settings.ado_default_parent_id,
        "severities": SEVERITIES,
        "auth_mode": settings.auth_mode,
        "single_user": settings.single_user,
    }


# ---------------------------------------------------------------- interviews


def _question_out(q: Question, interview: Interview, viewer: str) -> dict:
    # A Handoff Respondent sees options only, never the recommendation (Q28)
    show_rec = not (q.handoff_id and viewer != interview.requester_email)
    return {
        "id": q.id,
        "ref": services.question_ref(q),
        "round": q.round,
        "kind": q.kind,
        "title": q.title,
        "body": q.body,
        "options": q.options or [],
        "recommendation": q.recommendation if show_rec else None,
        "rationale": q.rationale if show_rec else None,
        "ai_note": q.ai_note,
        "core": q.core,
        "respondent": q.respondent_email,
        "handoff_id": q.handoff_id,
        "status": q.status,
        "answer_text": q.answer_text,
        "answered_by": q.answered_by,
        "answered_at": q.answered_at.isoformat() if q.answered_at else None,
        "can_respond": q.status == QuestionStatus.PENDING and q.respondent_email == viewer,
        "can_skip": q.status == QuestionStatus.PENDING and q.respondent_email == viewer
        and not q.handoff_id and bool(q.recommendation),
    }


def _summary_out(i: Interview) -> dict:
    return {
        "id": i.id,
        "requester": i.requester_email,
        "role": i.role,
        "request_type": i.request_type,
        "status": i.status,
        "title": i.title or i.request_text[:60],
        "ticket_id": i.ticket_id,
        "ticket_url": i.ticket_url,
        "created_at": i.created_at.isoformat(),
        "updated_at": i.updated_at.isoformat() if i.updated_at else None,
    }


def _detail_out(i: Interview, viewer: str, settings: Settings, deps: Deps) -> dict:
    progress = deps.progress.get(i.id)
    return {
        **_summary_out(i),
        "product": i.product,
        "template": i.template,
        "template_label": TEMPLATES[i.template].label if i.template in TEMPLATES else i.template,
        "request_text": i.request_text,
        "round": i.round,
        "engine_busy": i.engine_busy,
        "engine_done": i.engine_done,
        "engine_error": i.engine_error,
        "engine_progress": progress.to_json() if progress and i.engine_busy else None,
        "summary": i.engine_summary,
        "new_terms": i.new_terms or [],
        "spec_markdown": i.spec_markdown,
        "suggested_priority": i.suggested_priority,
        "suggested_severity": i.suggested_severity,
        "parent_id": i.parent_id,
        "default_parent_id": settings.ado_default_parent_id,
        "is_requester": viewer == i.requester_email,
        "unknown_core_count": services.unknown_core_count(i),
        "unknown_warning": services.unknown_core_count(i) > services.UNKNOWN_WARNING_THRESHOLD,
        "questions": [_question_out(q, i, viewer) for q in i.questions],
        "attachments": [
            {"id": a.id, "filename": a.filename, "content_type": a.content_type, "size": a.size}
            for a in i.attachments
        ],
        "handoffs": [
            {
                "id": h.id,
                "to": h.to_email,
                "status": h.status,
                "reminders_sent": h.reminders_sent,
                "created_at": h.created_at.isoformat(),
                "pending": sum(1 for q in i.questions if q.handoff_id == h.id and q.status == QuestionStatus.PENDING),
            }
            for h in i.handoffs
        ],
    }


@router.get("/interviews")
async def list_interviews(
    scope: str = "all",
    email: str = Depends(current_email),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Interview).order_by(Interview.updated_at.desc()).limit(200)
    if scope == "mine":
        stmt = stmt.where(Interview.requester_email == email)
    elif scope == "for-me":
        pending = select(Question.interview_id).where(
            Question.respondent_email == email,
            Question.status == QuestionStatus.PENDING,
            Question.handoff_id.is_not(None),
        )
        stmt = stmt.where(Interview.id.in_(pending))
    rows = (await session.scalars(stmt)).all()
    return [_summary_out(i) for i in rows]


@router.post("/interviews")
async def create_interview(
    role: Role = Form(...),
    request_type: RequestType = Form(...),
    text: str = Form(""),
    template: str | None = Form(None),
    files: list[UploadFile] = File(default_factory=list),
    email: str = Depends(current_email),
    session: AsyncSession = Depends(get_session),
    deps: Deps = Depends(get_deps),
):
    try:
        interview = await services.create_interview(
            deps,
            session,
            requester=email,
            role=role,
            request_type=request_type,
            template=template or DEFAULT_TEMPLATE[(role, request_type)],
            text=text,
            files=files,
        )
    except FlowError as exc:
        raise _flow(exc) from exc
    return {"id": interview.id}


@router.get("/interviews/{interview_id}")
async def get_interview(
    interview_id: str,
    email: str = Depends(current_email),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    deps: Deps = Depends(get_deps),
):
    try:
        interview = await services.load_interview(session, interview_id)
    except FlowError as exc:
        raise _flow(exc) from exc
    return _detail_out(interview, email, settings, deps)


@router.post("/interviews/{interview_id}/attachments")
async def add_attachments(
    interview_id: str,
    files: list[UploadFile] = File(...),
    email: str = Depends(current_email),
    session: AsyncSession = Depends(get_session),
    deps: Deps = Depends(get_deps),
):
    try:
        interview = await services.load_interview(session, interview_id)
        if interview.requester_email != email or interview.frozen_at:
            raise FlowError("無法新增附件", 403)
        await services.save_uploads(deps, session, interview, files, email)
        await session.commit()
    except FlowError as exc:
        raise _flow(exc) from exc
    return {"ok": True}


@router.get("/interviews/{interview_id}/attachments/{attachment_id}")
async def download_attachment(
    interview_id: str,
    attachment_id: str,
    email: str = Depends(current_email),
    session: AsyncSession = Depends(get_session),
):
    att = await session.get(Attachment, attachment_id)
    if att is None or att.interview_id != interview_id or not Path(att.storage_path).is_file():
        raise HTTPException(status_code=404, detail="找不到附件")
    return FileResponse(att.storage_path, media_type=att.content_type, filename=att.filename)


class RespondIn(BaseModel):
    action: str
    text: str | None = None


@router.post("/questions/{question_id}/respond")
async def respond(
    question_id: str,
    body: RespondIn,
    email: str = Depends(current_email),
    session: AsyncSession = Depends(get_session),
    deps: Deps = Depends(get_deps),
):
    try:
        await services.respond(deps, session, question_id, email, body.action, body.text)
    except FlowError as exc:
        raise _flow(exc) from exc
    return {"ok": True}


class EditQuestionIn(BaseModel):
    title: str | None = None
    body: str | None = None
    options: list[str] | None = None


@router.patch("/questions/{question_id}")
async def edit_question(
    question_id: str,
    body: EditQuestionIn,
    email: str = Depends(current_email),
    session: AsyncSession = Depends(get_session),
):
    try:
        await services.edit_question(session, question_id, email, body.title, body.body, body.options)
    except FlowError as exc:
        raise _flow(exc) from exc
    return {"ok": True}


@router.post("/questions/{question_id}/withdraw")
async def withdraw_question(
    question_id: str,
    email: str = Depends(current_email),
    session: AsyncSession = Depends(get_session),
    deps: Deps = Depends(get_deps),
):
    try:
        await services.withdraw_question(deps, session, question_id, email)
    except FlowError as exc:
        raise _flow(exc) from exc
    return {"ok": True}


@router.post("/interviews/{interview_id}/retry")
async def retry(
    interview_id: str,
    email: str = Depends(current_email),
    session: AsyncSession = Depends(get_session),
    deps: Deps = Depends(get_deps),
):
    try:
        await services.retry_engine(deps, session, interview_id, email)
    except FlowError as exc:
        raise _flow(exc) from exc
    return {"ok": True}


class HandoffIn(BaseModel):
    question_ids: list[str]
    to_email: str
    notify: bool = True


@router.post("/interviews/{interview_id}/handoffs")
async def create_handoff(
    interview_id: str,
    body: HandoffIn,
    email: str = Depends(current_email),
    session: AsyncSession = Depends(get_session),
    deps: Deps = Depends(get_deps),
):
    try:
        handoff = await services.create_handoff(
            deps, session, interview_id, email, body.question_ids, body.to_email, body.notify
        )
    except FlowError as exc:
        raise _flow(exc) from exc
    return {"id": handoff.id, "link": services.interview_link(deps.settings, interview_id)}


@router.post("/handoffs/{handoff_id}/recall")
async def recall_handoff(
    handoff_id: str,
    email: str = Depends(current_email),
    session: AsyncSession = Depends(get_session),
    deps: Deps = Depends(get_deps),
):
    try:
        await services.recall_handoff(deps, session, handoff_id, email)
    except FlowError as exc:
        raise _flow(exc) from exc
    return {"ok": True}


@router.post("/interviews/{interview_id}/finish")
async def finish(
    interview_id: str,
    email: str = Depends(current_email),
    session: AsyncSession = Depends(get_session),
    deps: Deps = Depends(get_deps),
):
    try:
        await services.finish(deps, session, interview_id, email)
    except FlowError as exc:
        raise _flow(exc) from exc
    return {"ok": True}


class SpecIn(BaseModel):
    title: str
    markdown: str


@router.put("/interviews/{interview_id}/spec")
async def update_spec(
    interview_id: str,
    body: SpecIn,
    email: str = Depends(current_email),
    session: AsyncSession = Depends(get_session),
):
    try:
        await services.update_spec(session, interview_id, email, body.title, body.markdown)
    except FlowError as exc:
        raise _flow(exc) from exc
    return {"ok": True}


class TicketIn(BaseModel):
    title: str
    parent_id: int | None = None
    priority: int | None = None
    severity: str | None = None
    notify: bool = True


@router.post("/interviews/{interview_id}/ticket")
async def create_ticket(
    interview_id: str,
    body: TicketIn,
    email: str = Depends(current_email),
    session: AsyncSession = Depends(get_session),
    deps: Deps = Depends(get_deps),
):
    try:
        interview = await services.create_ticket(
            deps,
            session,
            interview_id,
            email,
            services.TicketRequest(
                title=body.title, parent_id=body.parent_id, priority=body.priority,
                severity=body.severity, notify=body.notify,
            ),
        )
    except FlowError as exc:
        raise _flow(exc) from exc
    except AdoCredentialMissing as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AdoError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"ticket_id": interview.ticket_id, "ticket_url": interview.ticket_url}


class DecisionRecordIn(BaseModel):
    title: str = ""


@router.post("/interviews/{interview_id}/decision-record")
async def decision_record(
    interview_id: str,
    body: DecisionRecordIn,
    email: str = Depends(current_email),
    session: AsyncSession = Depends(get_session),
    deps: Deps = Depends(get_deps),
):
    try:
        await services.save_decision_record(session, interview_id, email, body.title)
    except FlowError as exc:
        raise _flow(exc) from exc
    return {"link": services.interview_link(deps.settings, interview_id)}
