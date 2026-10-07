"""Interview flow: rounds, responses, Handoff, Spec, Ticket, reminders.

Routers stay thin; everything that changes an Interview goes through here.
"""

from __future__ import annotations

import asyncio
import logging
import mimetypes
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import markdown as md
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from .ado import (
    DEFAULT_WORK_ITEM_TYPE,
    SEVERITIES,
    WORK_ITEM_TYPES,
    AdoClient,
    AdoCredentialProvider,
)
from .config import Settings
from .engine.llm import (
    AttachmentInput,
    EngineError,
    InterviewContext,
    InterviewLLM,
    QAItem,
)
from .engine.progress import EngineProgress
from .engine.schema import DraftQuestion
from .engine.templates import DEFAULT_AUDIENCE, QUESTION_BUDGETS, TEMPLATES, depth_for
from .knowledge import KnowledgeSource
from .models import (
    Attachment,
    Handoff,
    HandoffStatus,
    Interview,
    InterviewStatus,
    Question,
    QuestionKind,
    QuestionStatus,
    RequestType,
    Role,
    User,
    utcnow,
)
from .notify import Notifier, mention_for

log = logging.getLogger(__name__)

UNKNOWN_WARNING_THRESHOLD = 3


class FlowError(Exception):
    """A request that is not allowed in the Interview's current state."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


@dataclass
class Deps:
    settings: Settings
    sessionmaker: async_sessionmaker[AsyncSession]
    llm: InterviewLLM
    notifier: Notifier
    ado_transport: httpx.AsyncBaseTransport | None = None
    tasks: set[asyncio.Task] = field(default_factory=set)
    # interview id → what the engine is doing; present only while it runs
    progress: dict[str, EngineProgress] = field(default_factory=dict)
    # interview id → its engine task, so the Requester can stop it
    running: dict[str, asyncio.Task] = field(default_factory=dict)
    # recent ADO assignees for the Assignee picker: (fetched at, people)
    people_cache: tuple[float, list] | None = None

    def spawn(self, interview_id: str, coro) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        self.running[interview_id] = task

        def done(t: asyncio.Task) -> None:
            self.tasks.discard(t)
            if self.running.get(interview_id) is t:
                del self.running[interview_id]

        task.add_done_callback(done)
        return task

    async def stop(self, interview_id: str) -> None:
        """Cancel the Interview's engine task (which kills its Claude Code run) and wait for it to end."""
        task = self.running.get(interview_id)
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def drain(self) -> None:
        """Wait for background engine work (tests)."""
        while self.tasks:
            await asyncio.gather(*list(self.tasks), return_exceptions=True)


# ---------------------------------------------------------------- loading


async def load_interview(session: AsyncSession, interview_id: str) -> Interview:
    interview = await session.scalar(
        select(Interview)
        .where(Interview.id == interview_id)
        .options(
            selectinload(Interview.questions),
            selectinload(Interview.attachments),
            selectinload(Interview.handoffs),
        )
        .execution_options(populate_existing=True)
    )
    if interview is None:
        raise FlowError("找不到這個 Interview", 404)
    return interview


def question_ref(q: Question) -> str:
    return f"R{q.round}.{q.seq}"


def interview_link(settings: Settings, interview_id: str) -> str:
    return f"{settings.public_base_url.rstrip('/')}/interviews/{interview_id}"


async def display_name(session: AsyncSession, email: str) -> str | None:
    user = await session.get(User, email)
    return user.display_name if user else None


# ---------------------------------------------------------------- create


def _safe_filename(name: str) -> str:
    name = Path(name or "file").name
    return re.sub(r"[^\w.\-()一-鿿 ]", "_", name)[:200] or "file"


async def save_uploads(
    deps: Deps, session: AsyncSession, interview: Interview, files: list[UploadFile], uploader: str
) -> None:
    folder = deps.settings.upload_dir / interview.id
    folder.mkdir(parents=True, exist_ok=True)
    for f in files:
        data = await f.read()
        if not data:
            continue
        if len(data) > deps.settings.max_upload_bytes:
            raise FlowError(f"{f.filename} 超過 {deps.settings.max_upload_bytes // (1024 * 1024)}MB")
        att = Attachment(
            interview_id=interview.id,
            filename=_safe_filename(f.filename or "file"),
            content_type=f.content_type or mimetypes.guess_type(f.filename or "")[0] or "application/octet-stream",
            size=len(data),
            storage_path="",
            uploaded_by=uploader,
        )
        session.add(att)
        await session.flush()
        path = folder / f"{att.id}_{att.filename}"
        path.write_bytes(data)
        att.storage_path = str(path)


async def create_interview(
    deps: Deps,
    session: AsyncSession,
    *,
    requester: str,
    role: Role,
    request_type: RequestType,
    template: str,
    text: str,
    files: list[UploadFile],
    question_budget: str,
    audience: Role | None = None,
    assignee: str = "",
) -> Interview:
    if template not in TEMPLATES:
        raise FlowError(f"未知的 Interview Template: {template}")
    budget = next((b for b in QUESTION_BUDGETS if b.id == question_budget), None)
    if budget is None:
        raise FlowError(f"未知的題數選項: {question_budget}")
    if not text.strip() and not files:
        raise FlowError("請輸入需求內容或附件")
    interview = Interview(
        requester_email=requester,
        role=role,
        request_type=request_type,
        template=template,
        request_text=text.strip(),
        question_budget=budget.limit,
        audience=audience or DEFAULT_AUDIENCE[role],
        assignee_email=_assignee(assignee),
        engine_busy=True,
    )
    if budget.limit == 0:
        interview.status = InterviewStatus.SPEC_DRAFT
        interview.engine_done = True
    session.add(interview)
    await session.flush()
    await save_uploads(deps, session, interview, files, requester)
    await session.commit()
    deps.spawn(interview.id, generate_spec(deps, interview.id) if budget.limit == 0 else advance(deps, interview.id))
    return interview


# ---------------------------------------------------------------- engine rounds


def knowledge_for(deps: Deps, interview: Interview) -> KnowledgeSource:
    return KnowledgeSource(root=deps.settings.product_root, depth=depth_for(Role(interview.role)))


def build_context(interview: Interview) -> InterviewContext:
    return InterviewContext(
        template=TEMPLATES[interview.template],
        role=interview.role,
        request_type=interview.request_type,
        requester=interview.requester_email,
        request_text=interview.request_text,
        attachments=[
            AttachmentInput(a.filename, a.content_type, Path(a.storage_path)) for a in interview.attachments
        ],
        history=[
            QAItem(
                ref=question_ref(q),
                kind=q.kind,
                title=q.title,
                body=q.body,
                options=list(q.options or []),
                status=q.status,
                answer_text=q.answer_text,
                respondent=q.respondent_email,
                recommendation=q.recommendation,
            )
            for q in interview.questions
        ],
        round=interview.round,
        summary=interview.engine_summary,
        question_budget=interview.question_budget,
        audience=audience_of(interview),
    )


def _merge_terms(existing: list, new: list) -> list:
    seen = {t.get("term") for t in existing}
    return [*existing, *(t for t in new if t.get("term") not in seen)]


def audience_of(interview: Interview) -> str:
    return interview.audience or DEFAULT_AUDIENCE[Role(interview.role)]


def _assignee(email: str | None) -> str | None:
    email = (email or "").strip().lower()
    if not email:
        return None
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise FlowError(f"指派對象的 email 格式不正確：{email}")
    return email


def _has_pending(interview: Interview) -> bool:
    return any(q.status == QuestionStatus.PENDING for q in interview.questions)


def budget_left(interview: Interview) -> int | None:
    if interview.question_budget is None:
        return None
    asked = sum(1 for q in interview.questions if q.status != QuestionStatus.WITHDRAWN)
    return max(0, interview.question_budget - asked)


def _within_budget(drafts: list[DraftQuestion], left: int | None) -> list[DraftQuestion]:
    """Backstop for a round that overshoots the Question Budget: keep Premises and core questions first."""
    if left is None or len(drafts) <= left:
        return drafts
    ranked = sorted(range(len(drafts)), key=lambda i: (drafts[i].kind != "premise" and not drafts[i].core, i))
    keep = set(ranked[:left])
    return [d for i, d in enumerate(drafts) if i in keep]


async def advance(deps: Deps, interview_id: str) -> None:
    """Ask the next round if the current one is fully resolved."""
    async with deps.sessionmaker() as session:
        interview = await load_interview(session, interview_id)
        if interview.status != InterviewStatus.INTERVIEWING or interview.engine_done or _has_pending(interview):
            interview.engine_busy = False
            await session.commit()
            return
        if budget_left(interview) == 0:
            interview.engine_done = True
            interview.engine_busy = False
            await session.commit()
            return
        interview.engine_busy = True
        interview.engine_error = None
        await session.commit()

        progress = deps.progress[interview.id] = EngineProgress()
        try:
            result = await deps.llm.next_round(build_context(interview), knowledge_for(deps, interview), progress)
        except EngineError as exc:
            interview.engine_busy = False
            interview.engine_error = str(exc)
            await session.commit()
            return
        except Exception:
            log.exception("engine round failed")
            interview.engine_busy = False
            interview.engine_error = "拷問引擎發生未預期的錯誤"
            await session.commit()
            return
        finally:
            deps.progress.pop(interview.id, None)

        by_ref = {question_ref(q): q for q in interview.questions}
        next_round = interview.round + 1
        followups_to: dict[str, Handoff] = {}
        drafts = _within_budget(result.questions, budget_left(interview))
        for seq, draft in enumerate(drafts, 1):
            parent = by_ref.get(draft.followup_of or "")
            respondent = interview.requester_email
            handoff_id = None
            if parent is not None and parent.respondent_email != interview.requester_email and parent.handoff_id:
                respondent = parent.respondent_email
                handoff_id = parent.handoff_id
            kind = QuestionKind.PREMISE if draft.kind == "premise" else QuestionKind.QUESTION
            q = Question(
                interview_id=interview.id,
                round=next_round,
                seq=seq,
                kind=kind,
                title=draft.title[:255],
                body=draft.body,
                options=draft.options,
                recommendation=None if kind is QuestionKind.PREMISE else draft.recommendation,
                rationale=draft.rationale,
                ai_note=draft.ai_note,
                core=draft.core,
                respondent_email=respondent,
                handoff_id=handoff_id,
            )
            interview.questions.append(q)
            if handoff_id:
                handoff = next(h for h in interview.handoffs if h.id == handoff_id)
                handoff.status = HandoffStatus.OPEN
                handoff.last_notified_at = utcnow()
                followups_to[handoff.id] = handoff

        interview.round = next_round
        interview.engine_summary = result.summary
        interview.new_terms = _merge_terms(list(interview.new_terms or []), result.new_terms)
        interview.engine_done = (result.done and not drafts) or budget_left(interview) == 0
        interview.engine_busy = False
        await session.commit()

        for handoff in followups_to.values():
            await deps.notifier.post(
                "開票小精靈：有新的追問",
                [f"{mention_for(handoff.to_email, await display_name(session, handoff.to_email)).tag} "
                 f"你先前回答的題目有追問，請再幫忙回答。"],
                link=("前往回答", interview_link(deps.settings, interview.id)),
                mentions=[mention_for(handoff.to_email, await display_name(session, handoff.to_email))],
            )


# ---------------------------------------------------------------- responses


RESPOND_ACTIONS = {
    QuestionKind.QUESTION: {"answer", "unknown", "skip"},
    QuestionKind.PREMISE: {"confirm", "correct", "unknown"},
}


async def respond(deps: Deps, session: AsyncSession, question_id: str, user: str, action: str, text: str | None) -> None:
    q = await session.get(Question, question_id)
    if q is None:
        raise FlowError("找不到這一題", 404)
    interview = await load_interview(session, q.interview_id)
    q = next(x for x in interview.questions if x.id == question_id)
    if interview.status != InterviewStatus.INTERVIEWING:
        raise FlowError("這個 Interview 已經不能再回答")
    if user != q.respondent_email:
        raise FlowError("這一題不是由你回答", 403)
    if action not in RESPOND_ACTIONS[QuestionKind(q.kind)]:
        raise FlowError(f"不支援的回應：{action}")
    text = (text or "").strip() or None
    if action in ("answer", "correct") and not text:
        raise FlowError("請輸入內容")
    if action == "skip":
        if q.handoff_id or not q.recommendation:
            raise FlowError("這一題沒有推薦答案，不能跳過")
        text = q.recommendation

    q.status = {
        "answer": QuestionStatus.ANSWERED,
        "unknown": QuestionStatus.UNKNOWN,
        "skip": QuestionStatus.SKIPPED,
        "confirm": QuestionStatus.CONFIRMED,
        "correct": QuestionStatus.CORRECTED,
    }[action]
    q.answer_text = text
    q.answered_by = user
    q.answered_at = utcnow()

    completed: Handoff | None = None
    if q.handoff_id:
        handoff = next(h for h in interview.handoffs if h.id == q.handoff_id)
        if handoff.status == HandoffStatus.OPEN and not any(
            x.status == QuestionStatus.PENDING for x in interview.questions if x.handoff_id == handoff.id
        ):
            handoff.status = HandoffStatus.COMPLETED
            completed = handoff

    run_engine = not _has_pending(interview) and not interview.engine_done
    if run_engine:
        interview.engine_busy = True
    await session.commit()

    if completed is not None:
        requester = mention_for(interview.requester_email, await display_name(session, interview.requester_email))
        await deps.notifier.post(
            "開票小精靈：轉交的題目已回答",
            [f"{requester.tag} {completed.to_email} 已回答完轉交的題目。"],
            link=("查看", interview_link(deps.settings, interview.id)),
            mentions=[requester],
        )
    if run_engine:
        deps.spawn(interview.id, advance(deps, interview.id))


async def edit_question(session: AsyncSession, question_id: str, user: str, title: str | None, body: str | None,
                        options: list[str] | None) -> None:
    q = await session.get(Question, question_id)
    if q is None:
        raise FlowError("找不到這一題", 404)
    interview = await load_interview(session, q.interview_id)
    if interview.requester_email != user:
        raise FlowError("只有 Requester 可以修改題目", 403)
    if q.status != QuestionStatus.PENDING:
        raise FlowError("已回答的題目不能修改")
    if title is not None:
        q.title = title[:255]
    if body is not None:
        q.body = body
    if options is not None:
        q.options = [o for o in options if o.strip()]
    await session.commit()


async def delete_interview(deps: Deps, session: AsyncSession, interview_id: str, user: str) -> None:
    """Remove an Interview with its questions, Handoffs and attachment files. An ADO Ticket stays in ADO."""
    interview = await load_interview(session, interview_id)
    if interview.requester_email != user:
        raise FlowError("只有 Requester 可以刪除", 403)
    if interview.engine_busy:
        await deps.stop(interview_id)
    await session.delete(interview)
    await session.commit()
    shutil.rmtree(deps.settings.upload_dir / interview_id, ignore_errors=True)


async def withdraw_question(deps: Deps, session: AsyncSession, question_id: str, user: str) -> None:
    q = await session.get(Question, question_id)
    if q is None:
        raise FlowError("找不到這一題", 404)
    interview = await load_interview(session, q.interview_id)
    q = next(x for x in interview.questions if x.id == question_id)
    if interview.requester_email != user:
        raise FlowError("只有 Requester 可以撤回題目", 403)
    if q.status != QuestionStatus.PENDING:
        raise FlowError("已回答的題目不能撤回")
    q.status = QuestionStatus.WITHDRAWN
    q.answered_by = user
    q.answered_at = utcnow()
    run_engine = not _has_pending(interview) and not interview.engine_done
    if run_engine:
        interview.engine_busy = True
    await session.commit()
    if run_engine:
        deps.spawn(interview.id, advance(deps, interview.id))


async def stop_engine(deps: Deps, session: AsyncSession, interview_id: str, user: str) -> None:
    """The Requester changed their mind while the sprite works: stop it; 重試 starts the step over."""
    interview = await load_interview(session, interview_id)
    if interview.requester_email != user:
        raise FlowError("只有 Requester 可以停止小精靈", 403)
    if not interview.engine_busy:
        return
    await deps.stop(interview_id)
    await session.refresh(interview)
    interview.engine_busy = False
    interview.engine_error = "已停止小精靈。可以修改需求後按「重試」重新開始，或直接刪除。"
    await session.commit()


async def retry_engine(deps: Deps, session: AsyncSession, interview_id: str, user: str) -> None:
    interview = await load_interview(session, interview_id)
    if interview.requester_email != user:
        raise FlowError("只有 Requester 可以重試", 403)
    if interview.engine_busy:
        return
    interview.engine_busy = True
    await session.commit()
    if interview.spec_markdown is None and interview.status == InterviewStatus.SPEC_DRAFT:
        deps.spawn(interview.id, generate_spec(deps, interview.id))
    else:
        deps.spawn(interview.id, advance(deps, interview.id))


def unknown_core_count(interview: Interview) -> int:
    return sum(1 for q in interview.questions if q.core and q.status == QuestionStatus.UNKNOWN)


# ---------------------------------------------------------------- Handoff


async def create_handoff(
    deps: Deps, session: AsyncSession, interview_id: str, user: str, question_ids: list[str], to_email: str,
    notify: bool,
) -> Handoff:
    if deps.settings.single_user:
        raise FlowError("單人試用模式不能轉交：請把題目複製給對方，再代為填入對方的回答")
    interview = await load_interview(session, interview_id)
    if interview.requester_email != user:
        raise FlowError("只有 Requester 可以轉交題目", 403)
    if interview.status != InterviewStatus.INTERVIEWING:
        raise FlowError("這個 Interview 已經不能轉交")
    to_email = to_email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+", to_email):
        raise FlowError("請輸入正確的 email")
    if to_email == user:
        raise FlowError("不能轉交給自己")
    if not deps.settings.may_log_in(to_email):
        raise FlowError(f"{to_email} 不在試用名單中，對方無法登入回答")
    chosen = [q for q in interview.questions if q.id in set(question_ids)]
    if not chosen:
        raise FlowError("請選擇要轉交的題目")
    if any(q.status != QuestionStatus.PENDING or q.respondent_email != user for q in chosen):
        raise FlowError("只能轉交自己尚未回答的題目")

    handoff = Handoff(interview_id=interview.id, from_email=user, to_email=to_email)
    interview.handoffs.append(handoff)
    await session.flush()
    for q in chosen:
        q.respondent_email = to_email
        q.handoff_id = handoff.id
    await session.commit()

    if notify:
        target = mention_for(to_email, await display_name(session, to_email))
        await deps.notifier.post(
            "開票小精靈：有題目轉交給你",
            [
                f"{target.tag} {user} 有 {len(chosen)} 題想請你回答。",
                f"Request：{interview.request_text[:120]}",
            ],
            link=("前往回答", interview_link(deps.settings, interview.id)),
            mentions=[target],
        )
    return handoff


async def recall_handoff(deps: Deps, session: AsyncSession, handoff_id: str, user: str) -> None:
    handoff = await session.get(Handoff, handoff_id)
    if handoff is None:
        raise FlowError("找不到這個轉交", 404)
    interview = await load_interview(session, handoff.interview_id)
    handoff = next(h for h in interview.handoffs if h.id == handoff_id)
    if interview.requester_email != user:
        raise FlowError("只有 Requester 可以收回", 403)
    for q in interview.questions:
        if q.handoff_id == handoff.id and q.status == QuestionStatus.PENDING:
            q.respondent_email = interview.requester_email
            q.handoff_id = None
    handoff.status = HandoffStatus.RECALLED
    await session.commit()


def working_days_between(start: datetime, end: datetime) -> int:
    """Whole Mon-Fri days elapsed after `start` up to `end`."""
    days = 0
    cursor = start
    while True:
        cursor = cursor + timedelta(days=1)
        if cursor > end:
            return days
        if cursor.weekday() < 5:
            days += 1


async def send_due_reminders(deps: Deps, now: datetime | None = None) -> int:
    """Remind silent Respondents after N working days, at most M times, then tell the Requester."""
    now = now or utcnow()
    s = deps.settings
    sent = 0
    async with deps.sessionmaker() as session:
        handoffs = (
            await session.scalars(
                select(Handoff).where(Handoff.status == HandoffStatus.OPEN).options(selectinload(Handoff.interview))
            )
        ).all()
        for h in handoffs:
            if h.interview.status != InterviewStatus.INTERVIEWING:
                continue
            last = h.last_notified_at if h.last_notified_at.tzinfo else h.last_notified_at.replace(tzinfo=timezone.utc)
            if working_days_between(last, now) < s.handoff_reminder_working_days:
                continue
            link = ("前往回答", interview_link(s, h.interview_id))
            if h.reminders_sent < s.handoff_max_reminders:
                target = mention_for(h.to_email, await display_name(session, h.to_email))
                await deps.notifier.post(
                    "開票小精靈：提醒回答",
                    [f"{target.tag} {h.from_email} 轉交的題目還在等你回答（第 {h.reminders_sent + 1} 次提醒）。"],
                    link=link,
                    mentions=[target],
                )
                h.reminders_sent += 1
                h.last_notified_at = now
                sent += 1
            elif not h.requester_alerted:
                requester = mention_for(h.from_email, await display_name(session, h.from_email))
                await deps.notifier.post(
                    "開票小精靈：轉交的題目仍未回答",
                    [f"{requester.tag} {h.to_email} 已提醒 {h.reminders_sent} 次仍未回答，請直接聯繫或收回題目。"],
                    link=("查看", interview_link(s, h.interview_id)),
                    mentions=[requester],
                )
                h.requester_alerted = True
                sent += 1
        await session.commit()
    return sent


async def reminder_loop(deps: Deps) -> None:
    while True:
        try:
            await send_due_reminders(deps)
        except Exception:
            log.exception("reminder run failed")
        await asyncio.sleep(deps.settings.reminder_check_interval_seconds)


# ---------------------------------------------------------------- Spec


async def finish(deps: Deps, session: AsyncSession, interview_id: str, user: str) -> None:
    interview = await load_interview(session, interview_id)
    if interview.requester_email != user:
        raise FlowError("只有 Requester 可以產出 Spec", 403)
    if interview.status != InterviewStatus.INTERVIEWING:
        raise FlowError("Spec 已經產出")
    if interview.engine_busy:
        raise FlowError("拷問引擎還在出題，請稍候")
    interview.status = InterviewStatus.SPEC_DRAFT
    interview.engine_busy = True
    interview.engine_error = None
    for h in interview.handoffs:
        if h.status == HandoffStatus.OPEN:
            h.status = HandoffStatus.COMPLETED
    await session.commit()
    deps.spawn(interview.id, generate_spec(deps, interview.id))


async def generate_spec(deps: Deps, interview_id: str, as_revision: bool = False) -> None:
    """Write the Spec; for a ticketed Interview (as_revision) keep it aside until the Requester applies it."""
    async with deps.sessionmaker() as session:
        interview = await load_interview(session, interview_id)
        progress = deps.progress[interview.id] = EngineProgress()
        try:
            result = await deps.llm.write_spec(build_context(interview), knowledge_for(deps, interview), progress)
        except EngineError as exc:
            interview.engine_error = str(exc)
        except Exception:
            log.exception("spec generation failed")
            interview.engine_error = "產出 Spec 時發生未預期的錯誤"
        else:
            if as_revision:
                interview.spec_revision = result.markdown
                deps.progress.pop(interview.id, None)
                interview.engine_busy = False
                await session.commit()
                return
            interview.title = result.title[:255]
            interview.spec_markdown = result.markdown
            interview.suggested_priority = result.priority
            interview.suggested_severity = result.severity if result.severity in SEVERITIES else None
            interview.new_terms = _merge_terms(list(interview.new_terms or []), result.new_terms)
        deps.progress.pop(interview.id, None)
        interview.engine_busy = False
        await session.commit()


async def regenerate_spec(deps: Deps, session: AsyncSession, interview_id: str, user: str) -> None:
    """Rewrite the Spec with the current rules: in place while a draft, as a revision to review once it
    has been ticketed or saved as a Decision Record."""
    interview = await load_interview(session, interview_id)
    if interview.requester_email != user:
        raise FlowError("只有 Requester 可以重新產出 Spec", 403)
    if interview.status not in (InterviewStatus.SPEC_DRAFT, InterviewStatus.TICKETED, InterviewStatus.DECISION_RECORD):
        raise FlowError("拷問結束後才能重新產出 Spec")
    if interview.engine_busy:
        raise FlowError("小精靈還在處理，請稍候", 409)
    interview.engine_busy = True
    interview.engine_error = None
    await session.commit()
    deps.spawn(interview.id, generate_spec(deps, interview.id, as_revision=interview.status != InterviewStatus.SPEC_DRAFT))


async def apply_spec_revision(deps: Deps, session: AsyncSession, interview_id: str, user: str, force: bool) -> None:
    """Adopt the regenerated Spec. For a Ticket it also replaces the ADO description, unless someone edited
    it there and force is off; a Decision Record lives only here."""
    interview = await load_interview(session, interview_id)
    if interview.requester_email != user:
        raise FlowError("只有 Requester 可以採用新版 Spec", 403)
    if not interview.spec_revision:
        raise FlowError("沒有待更新的新版 Spec")
    if interview.status == InterviewStatus.DECISION_RECORD:
        interview.spec_markdown = interview.spec_revision
        interview.spec_revision = None
        await session.commit()
        return
    if interview.status != InterviewStatus.TICKETED or not interview.ticket_id:
        raise FlowError("沒有待更新的新版 Spec")
    requester = await session.get(User, user)
    ado = AdoClient(deps.settings, AdoCredentialProvider(deps.settings).auth_header(requester), deps.ado_transport)
    if not force:
        editors = await ado.description_edits(interview.ticket_id)
        if editors:
            raise FlowError(
                f"ADO #{interview.ticket_id} 的描述在開票後被 {'、'.join(editors)} 改過，更新會覆蓋這些修改"
                "（ADO 的 History 仍可還原）。",
                409,
            )
    await ado.set_description(
        interview.ticket_id,
        spec_html(deps.settings, interview, interview.spec_revision),
        is_bug=interview.ticket_type == "Bug",
    )
    interview.spec_markdown = interview.spec_revision
    interview.spec_revision = None
    await session.commit()


async def discard_spec_revision(session: AsyncSession, interview_id: str, user: str) -> None:
    interview = await load_interview(session, interview_id)
    if interview.requester_email != user:
        raise FlowError("只有 Requester 可以操作", 403)
    interview.spec_revision = None
    await session.commit()


async def update_spec(session: AsyncSession, interview_id: str, user: str, title: str, markdown_text: str) -> None:
    interview = await load_interview(session, interview_id)
    if interview.requester_email != user:
        raise FlowError("只有 Requester 可以編輯 Spec", 403)
    if interview.status != InterviewStatus.SPEC_DRAFT or interview.frozen_at:
        raise FlowError("Spec 已凍結")
    interview.title = title.strip()[:255]
    interview.spec_markdown = markdown_text
    await session.commit()


def spec_html(settings: Settings, interview: Interview, markdown_text: str | None = None) -> str:
    text = interview.spec_markdown if markdown_text is None else markdown_text
    body = md.markdown(text or "", extensions=["tables", "fenced_code", "sane_lists"])
    link = interview_link(settings, interview.id)
    return f'{body}<hr/><p>由開票小精靈產生 · <a href="{link}">完整拷問記錄</a></p>'


async def _require_draft(session: AsyncSession, interview_id: str, user: str) -> Interview:
    interview = await load_interview(session, interview_id)
    if interview.requester_email != user:
        raise FlowError("只有 Requester 可以操作", 403)
    if interview.status != InterviewStatus.SPEC_DRAFT or not interview.spec_markdown:
        raise FlowError("Spec 尚未就緒或已凍結")
    return interview


@dataclass
class TicketRequest:
    title: str
    parent_id: int | None
    priority: int | None
    severity: str | None
    notify: bool
    assignee: str | None = None
    work_item_type: str | None = None  # None = DEFAULT_WORK_ITEM_TYPE for the Request Type


async def create_ticket(deps: Deps, session: AsyncSession, interview_id: str, user: str, req: TicketRequest) -> Interview:
    interview = await _require_draft(session, interview_id, user)
    title = req.title.strip() or interview.title or "未命名需求"
    if req.severity and req.severity not in SEVERITIES:
        raise FlowError("Severity 不正確")
    if req.priority is not None and req.priority not in (1, 2, 3, 4):
        raise FlowError("Priority 必須是 1-4")
    assignee = _assignee(req.assignee)
    wi_type = req.work_item_type or DEFAULT_WORK_ITEM_TYPE[RequestType(interview.request_type)]
    if wi_type not in WORK_ITEM_TYPES:
        raise FlowError(f"不支援的票種：{wi_type}")

    requester = await session.get(User, user)
    ado = AdoClient(deps.settings, AdoCredentialProvider(deps.settings).auth_header(requester), deps.ado_transport)
    attachment_urls = []
    for a in interview.attachments:
        try:
            data = Path(a.storage_path).read_bytes()
        except OSError:
            continue
        attachment_urls.append(await ado.upload_attachment(a.filename, data))
    created = await ado.create_work_item(
        work_item_type=wi_type,
        title=title,
        description_html=spec_html(deps.settings, interview),
        parent_id=req.parent_id,
        tags=["ticket-sprite", f"role:{interview.role}", f"to:{audience_of(interview)}"],
        priority=req.priority,
        severity=req.severity if wi_type == "Bug" else None,
        attachment_urls=attachment_urls,
        assigned_to=assignee,
    )
    interview.title = title
    interview.assignee_email = assignee
    interview.ticket_id = created.id
    interview.ticket_url = created.url
    interview.ticket_type = wi_type
    interview.parent_id = req.parent_id
    interview.status = InterviewStatus.TICKETED
    interview.frozen_at = utcnow()
    await session.commit()

    if req.notify:
        await deps.notifier.post(
            f"開票小精靈：#{created.id} {title}",
            [f"{user} 開了一張 {wi_type}（role: {interview.role}）"
             + (f"，指派給 {assignee}" if assignee else "")
             + (f"，Parent #{req.parent_id}" if req.parent_id else "")],
            link=("在 Azure DevOps 開啟", created.url),
        )
    return interview


async def save_decision_record(session: AsyncSession, interview_id: str, user: str, title: str) -> Interview:
    interview = await _require_draft(session, interview_id, user)
    interview.title = title.strip()[:255] or interview.title
    interview.status = InterviewStatus.DECISION_RECORD
    interview.frozen_at = utcnow()
    await session.commit()
    return interview
