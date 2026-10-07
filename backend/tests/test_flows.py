from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import httpx

from ticket_sprite.engine.llm import round_prompt, spec_prompt
from ticket_sprite.engine.schema import DraftQuestion, RoundResult
from ticket_sprite.models import Handoff
from ticket_sprite.services import send_due_reminders, working_days_between

from .conftest import client_for, login


async def _detail(c, iid):
    r = await c.get(f"/api/interviews/{iid}")
    assert r.status_code == 200, r.text
    return r.json()


def _pending(detail, who=None):
    return [q for q in detail["questions"] if q["status"] == "pending" and (who is None or q["respondent"] == who)]


async def test_requires_login(app):
    async with client_for(app) as c:
        assert (await c.get("/api/me")).status_code == 401


async def test_pm_feature_flow_to_ticket(app, deps, vivian, fake_ado, notifier, llm):
    r = await vivian.post(
        "/api/interviews",
        data={"role": "pm", "request_type": "feature", "text": "客戶想要開放標注給標注員"},
        files=[("files", ("notes.txt", b"customer said: we need labels", "text/plain"))],
    )
    assert r.status_code == 200, r.text
    iid = r.json()["id"]
    await deps.drain()

    d = await _detail(vivian, iid)
    assert d["template"] == "grill_product"
    assert d["round"] == 1 and len(d["questions"]) == 2
    q1, q2 = d["questions"]
    assert q1["recommendation"] == "標注員" and q1["can_skip"]
    # The PM template only sees documents
    ctx = llm.calls[0][1]
    assert ctx.attachments[0].filename == "notes.txt"

    assert (await vivian.post(f"/api/questions/{q1['id']}/respond", json={"action": "answer", "text": "標注員"})).status_code == 200
    assert (await vivian.post(f"/api/questions/{q2['id']}/respond", json={"action": "skip"})).status_code == 200
    await deps.drain()

    d = await _detail(vivian, iid)
    assert d["round"] == 2
    round2 = _pending(d)
    assert len(round2) == 2
    for q in round2:
        await vivian.post(f"/api/questions/{q['id']}/respond", json={"action": "unknown"})
    await deps.drain()
    d = await _detail(vivian, iid)
    assert d["engine_done"] and not _pending(d)
    skipped = next(q for q in d["questions"] if q["id"] == q2["id"])
    assert skipped["status"] == "skipped" and skipped["answer_text"] == "能在列表上看到標注"

    assert (await vivian.post(f"/api/interviews/{iid}/finish")).status_code == 200
    await deps.drain()
    d = await _detail(vivian, iid)
    assert d["status"] == "spec_draft" and d["spec_markdown"]

    r = await vivian.put(f"/api/interviews/{iid}/spec", json={"title": "開放標注", "markdown": "## 背景\n改過"})
    assert r.status_code == 200

    # No ADO Credential yet
    r = await vivian.post(f"/api/interviews/{iid}/ticket", json={"title": "開放標注", "parent_id": 41152})
    assert r.status_code == 409

    r = await vivian.put("/api/me/ado", json={"pat": "bad-pat-0000000000"})
    assert r.status_code == 400
    r = await vivian.put("/api/me/ado", json={"pat": "good-pat-1234567890", "expires_on": "2027-10-01"})
    assert r.status_code == 200 and r.json()["display_name"] == "Vivian Fan"

    r = await vivian.post(
        f"/api/interviews/{iid}/ticket",
        json={"title": "開放標注", "parent_id": 41152, "priority": 2, "assignee": " Kevin@LinkerVision.com ",
              "work_item_type": "User Story"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["ticket_url"].endswith("/_workitems/edit/50001")

    created = fake_ado.created[0]
    assert created["type"] == "User Story"
    fields = {op["path"]: op["value"] for op in created["ops"]}
    assert fields["/fields/System.Title"] == "開放標注"
    assert "改過" in fields["/fields/System.Description"]
    assert f"/interviews/{iid}" in fields["/fields/System.Description"]
    assert fields["/fields/System.Tags"] == "ticket-sprite; role:pm; to:rd"
    assert fields["/fields/System.AssignedTo"] == "kevin@linkervision.com"
    relations = [op["value"] for op in created["ops"] if op["path"] == "/relations/-"]
    assert {"rel": "System.LinkTypes.Hierarchy-Reverse",
            "url": "https://dev.azure.com/linkerengineer/_apis/wit/workItems/41152"} in relations
    assert any(r["rel"] == "AttachedFile" for r in relations)
    assert fake_ado.uploads == ["notes.txt"]
    assert notifier.sent and "#50001" in notifier.sent[-1]["attachments"][0]["content"]["body"][0]["text"]

    d = await _detail(vivian, iid)
    assert d["status"] == "ticketed"
    # Frozen
    assert (await vivian.put(f"/api/interviews/{iid}/spec", json={"title": "x", "markdown": "y"})).status_code == 400


async def test_rd_clarify_handoff_to_pm(app, deps, vivian, kevin, notifier):
    r = await vivian.post(
        "/api/interviews",
        data={"role": "rd", "request_type": "task", "text": "我理解標注存在 middleware…想請教需求來源"},
    )
    iid = r.json()["id"]
    await deps.drain()
    d = await _detail(vivian, iid)
    assert d["template"] == "clarify"
    premise, question = d["questions"]
    assert premise["kind"] == "premise" and premise["ai_note"] and premise["recommendation"] is None

    # RD edits the question, then hands both off to Kevin
    r = await vivian.patch(f"/api/questions/{question['id']}", json={"body": "這個功能當初是誰提的？"})
    assert r.status_code == 200
    r = await vivian.post(
        f"/api/interviews/{iid}/handoffs",
        json={"question_ids": [premise["id"], question["id"]], "to_email": "Kevin@linkervision.com"},
    )
    assert r.status_code == 200, r.text
    card = notifier.sent[-1]["attachments"][0]["content"]
    assert card["msteams"]["entities"][0]["mentioned"]["id"] == "kevin@linkervision.com"

    mine = (await kevin.get("/api/interviews", params={"scope": "for-me"})).json()
    assert [i["id"] for i in mine] == [iid]

    kd = await _detail(kevin, iid)
    kq = {q["id"]: q for q in kd["questions"]}
    assert kq[question["id"]]["body"] == "這個功能當初是誰提的？"
    assert kq[question["id"]]["can_respond"] and not kq[question["id"]]["can_skip"]

    # Vivian can no longer answer handed-off questions; Kevin cannot skip
    r = await vivian.post(f"/api/questions/{question['id']}/respond", json={"action": "answer", "text": "x"})
    assert r.status_code == 403
    r = await kevin.post(f"/api/questions/{question['id']}/respond", json={"action": "skip"})
    assert r.status_code == 400

    await kevin.post(f"/api/questions/{premise['id']}/respond", json={"action": "correct", "text": "還有存在 Observ"})
    await kevin.post(f"/api/questions/{question['id']}/respond", json={"action": "answer", "text": "客戶要求"})
    assert "已回答完" in notifier.sent[-1]["attachments"][0]["content"]["body"][1]["text"]
    await deps.drain()

    # Follow-up of Kevin's answer goes straight back to Kevin, without a recommendation
    kd = await _detail(kevin, iid)
    followup = next(q for q in _pending(kd) if q["respondent"] == "kevin@linkervision.com")
    assert followup["recommendation"] is None
    assert kd["handoffs"][0]["status"] == "open"
    # The Requester still sees the recommendation
    vd = await _detail(vivian, iid)
    assert next(q for q in vd["questions"] if q["id"] == followup["id"])["recommendation"] == "標注員"

    # Requester decides it's enough → Decision Record, no ticket
    assert (await vivian.post(f"/api/interviews/{iid}/finish")).status_code == 200
    await deps.drain()
    r = await vivian.post(f"/api/interviews/{iid}/decision-record", json={"title": "標注定位"})
    assert r.status_code == 200
    vd = await _detail(vivian, iid)
    assert vd["status"] == "decision_record"
    corrected = next(q for q in vd["questions"] if q["id"] == premise["id"])
    assert corrected["status"] == "corrected" and corrected["answered_by"] == "kevin@linkervision.com"


async def test_recall_handoff(app, deps, vivian, kevin):
    iid = (await vivian.post("/api/interviews", data={"role": "pm", "request_type": "feature", "text": "x"})).json()["id"]
    await deps.drain()
    q = (await _detail(vivian, iid))["questions"][0]
    hid = (await vivian.post(f"/api/interviews/{iid}/handoffs",
                             json={"question_ids": [q["id"]], "to_email": "kevin@linkervision.com",
                                   "notify": False})).json()["id"]
    assert (await kevin.post(f"/api/handoffs/{hid}/recall")).status_code == 403
    assert (await vivian.post(f"/api/handoffs/{hid}/recall")).status_code == 200
    d = await _detail(vivian, iid)
    back = next(x for x in d["questions"] if x["id"] == q["id"])
    assert back["respondent"] == "vivian@linkervision.com" and back["can_skip"]
    assert d["handoffs"][0]["status"] == "recalled"


async def test_withdraw_last_pending_advances(app, deps, vivian):
    iid = (await vivian.post("/api/interviews", data={"role": "pm", "request_type": "feature", "text": "x"})).json()["id"]
    await deps.drain()
    q1, q2 = (await _detail(vivian, iid))["questions"]
    await vivian.post(f"/api/questions/{q1['id']}/respond", json={"action": "answer", "text": "a"})
    assert (await vivian.post(f"/api/questions/{q2['id']}/withdraw")).status_code == 200
    await deps.drain()
    assert (await _detail(vivian, iid))["round"] == 2


def test_working_days():
    fri = datetime(2026, 10, 9, 10, tzinfo=timezone.utc)
    assert working_days_between(fri, fri + timedelta(days=3)) == 1  # Sat, Sun, Mon
    assert working_days_between(fri, fri + timedelta(days=4)) == 2


async def test_reminders_then_alert_requester(app, deps, vivian, notifier):
    iid = (await vivian.post("/api/interviews", data={"role": "pm", "request_type": "feature", "text": "x"})).json()["id"]
    await deps.drain()
    q = (await _detail(vivian, iid))["questions"][0]
    await vivian.post(f"/api/interviews/{iid}/handoffs",
                      json={"question_ids": [q["id"]], "to_email": "kevin@linkervision.com", "notify": False})
    now = datetime.now(timezone.utc)
    assert await send_due_reminders(deps, now) == 0
    t = now
    for _ in range(2):
        t = t + timedelta(days=4)
        assert await send_due_reminders(deps, t) == 1
        assert "提醒回答" in notifier.sent[-1]["attachments"][0]["content"]["body"][0]["text"]
    t = t + timedelta(days=4)
    assert await send_due_reminders(deps, t) == 1
    assert "仍未回答" in notifier.sent[-1]["attachments"][0]["content"]["body"][0]["text"]
    assert await send_due_reminders(deps, t + timedelta(days=10)) == 0
    async with deps.sessionmaker() as s:
        h = (await s.scalars(__import__("sqlalchemy").select(Handoff))).one()
        assert h.reminders_sent == 2 and h.requester_alerted


async def test_bug_ticket_uses_bug_type_and_severity(app, deps, vivian, fake_ado):
    iid = (await vivian.post("/api/interviews", data={"role": "fae", "request_type": "bug", "text": "gate 掛了"})).json()["id"]
    await deps.drain()
    d = await _detail(vivian, iid)
    assert d["template"] == "quick_bug_technical"
    await vivian.post(f"/api/interviews/{iid}/finish")
    await deps.drain()
    d = await _detail(vivian, iid)
    assert d["suggested_severity"] == "3 - Medium"
    await vivian.put("/api/me/ado", json={"pat": "good-pat-1234567890"})
    r = await vivian.post(f"/api/interviews/{iid}/ticket",
                          json={"title": "gate 掛了", "severity": "2 - High", "priority": 1, "notify": False})
    assert r.status_code == 200, r.text
    created = fake_ado.created[-1]
    fields = {op["path"]: op["value"] for op in created["ops"]}
    assert created["type"] == "Bug"
    assert fields["/fields/Microsoft.VSTS.Common.Severity"] == "2 - High"
    assert "/fields/Microsoft.VSTS.TCM.ReproSteps" in fields


async def test_work_item_search(app, vivian):
    assert (await vivian.get("/api/ado/work-items", params={"q": "middleware"})).status_code == 409
    await vivian.put("/api/me/ado", json={"pat": "good-pat-1234567890"})
    r = await vivian.get("/api/ado/work-items", params={"q": "middleware"})
    assert r.json() == [{"id": 41152, "title": "Middleware", "work_item_type": "Feature", "state": "Active"}]
    r = await vivian.get("/api/ado/work-items", params={"q": "#41152"})
    assert r.json()[0]["id"] == 41152


async def test_observ_login(settings, llm, notifier):
    from ticket_sprite.main import create_app

    settings.auth_mode = "observ"

    def observ(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/apiserver/users/token"):
            body = __import__("json").loads(request.content)
            if body["password"] == "right":
                return httpx.Response(200, json={"access_token": "tok"})
            return httpx.Response(401, json={"detail": "bad"})
        if request.url.path.endswith("/auth/users/me"):
            assert request.headers["authorization"] == "Bearer tok"
            assert request.headers["x-request-service-id"] == settings.observ_service_id
            return httpx.Response(200, json={"id": 7, "email": "Kevin@LinkerVision.com", "name": "Kevin"})
        return httpx.Response(404)

    application = create_app(settings, llm=llm, notifier=notifier, background_jobs=False)
    application.state.observ_transport = httpx.MockTransport(observ)
    async with application.router.lifespan_context(application):
        async with client_for(application) as c:
            r = await c.post("/api/auth/login", json={"email": "kevin@linkervision.com", "password": "wrong"})
            assert r.status_code == 401
            r = await c.post("/api/auth/login", json={"email": "kevin@linkervision.com", "password": "right"})
            assert r.status_code == 200
            me = (await c.get("/api/me")).json()
            assert me["email"] == "kevin@linkervision.com" and me["display_name"] == "Kevin"
            assert me["default_role"] == "pm"


async def test_trial_allowlist(settings, llm, notifier):
    from ticket_sprite.main import create_app

    settings.allowed_emails = "Vivian@linkervision.com, kevin@linkervision.com"
    application = create_app(settings, llm=llm, notifier=notifier, background_jobs=False)
    async with application.router.lifespan_context(application):
        async with client_for(application) as outsider:
            r = await outsider.post("/api/auth/login", json={"email": "amy@linkervision.com"})
            assert r.status_code == 403 and "試用名單" in r.json()["detail"]
        vivian = await login(application, "vivian@linkervision.com")
        iid = (await vivian.post("/api/interviews",
                                 data={"role": "pm", "request_type": "feature", "text": "x"})).json()["id"]
        await application.state.deps.drain()
        q = (await _detail(vivian, iid))["questions"][0]
        r = await vivian.post(f"/api/interviews/{iid}/handoffs",
                              json={"question_ids": [q["id"]], "to_email": "amy@linkervision.com"})
        assert r.status_code == 400 and "試用名單" in r.json()["detail"]
        r = await vivian.post(f"/api/interviews/{iid}/handoffs",
                              json={"question_ids": [q["id"]], "to_email": "kevin@linkervision.com",
                                    "notify": False})
        assert r.status_code == 200

        # Removing someone from the allowlist ends their existing session
        settings.allowed_emails = "kevin@linkervision.com"
        assert (await vivian.get("/api/me")).status_code == 401
        await vivian.aclose()


async def test_user_roles_set_the_default_role_on_login(settings, llm, notifier):
    from ticket_sprite.main import create_app

    settings.user_roles = "Danny@linkervision.com=fae, froggy@linkervision.com=rd"
    application = create_app(settings, llm=llm, notifier=notifier, background_jobs=False)
    async with application.router.lifespan_context(application):
        async def role_after_login(email: str) -> str:
            c = await login(application, email)
            role = (await c.get("/api/me")).json()["default_role"]
            await c.aclose()
            return role

        assert await role_after_login("danny@linkervision.com") == "fae"
        assert await role_after_login("amy@linkervision.com") == "pm"
        assert await role_after_login("froggy@linkervision.com") == "rd"

        # A Role someone picks in Settings outlives the mapping on later logins
        froggy = await login(application, "froggy@linkervision.com")
        assert (await froggy.put("/api/me", json={"default_role": "pm"})).status_code == 200
        await froggy.aclose()
        assert await role_after_login("froggy@linkervision.com") == "pm"


async def test_engine_progress_is_shown_while_the_round_runs(app, deps, vivian, llm):
    gate = asyncio.Event()
    next_round = llm.next_round

    async def slow_round(ctx, knowledge, progress=None):
        progress.read("docs/adr/0001.md")
        progress.search()
        await gate.wait()
        return await next_round(ctx, knowledge, progress)

    llm.next_round = slow_round
    iid = (await vivian.post("/api/interviews", data={"role": "pm", "request_type": "feature", "text": "x"})).json()["id"]
    for _ in range(50):
        d = await _detail(vivian, iid)
        if d["engine_progress"]:
            break
        await asyncio.sleep(0.01)

    assert d["engine_busy"]
    assert d["engine_progress"]["reads"] == ["docs/adr/0001.md"]
    assert d["engine_progress"]["searches"] == 1 and d["engine_progress"]["started_at"]

    gate.set()
    await deps.drain()
    d = await _detail(vivian, iid)
    assert not d["engine_busy"] and d["engine_progress"] is None
    assert not deps.progress


async def test_question_budget_caps_the_interview(app, deps, vivian, llm):
    """精簡 = 5 questions: a round that overshoots keeps premises and core questions, then the interview ends."""
    contexts = []

    async def wide_round(ctx, knowledge, progress=None):
        contexts.append(ctx)
        return RoundResult(
            done=False,
            summary="s",
            questions=[
                DraftQuestion(kind="question", title=f"r{ctx.round + 1} 次要", body="b"),
                DraftQuestion(kind="question", title=f"r{ctx.round + 1} 核心", body="b", core=True),
                DraftQuestion(kind="premise", title=f"r{ctx.round + 1} 前提", body="b"),
                DraftQuestion(kind="question", title=f"r{ctx.round + 1} 次要二", body="b"),
            ],
            new_terms=[],
        )

    llm.next_round = wide_round
    r = await vivian.post("/api/interviews", data={"role": "pm", "request_type": "feature", "text": "x",
                                                   "question_budget": "brief"})
    iid = r.json()["id"]
    await deps.drain()
    d = await _detail(vivian, iid)
    assert d["question_budget"] == 5 and d["questions_asked"] == 4
    for q in _pending(d):
        await vivian.post(f"/api/questions/{q['id']}/respond", json={"action": "unknown"})
    await deps.drain()

    d = await _detail(vivian, iid)
    round2 = [q["title"] for q in d["questions"] if q["round"] == 2]
    assert round2 == ["r2 核心"]  # one left: premises and core questions outrank the rest, in the AI's order
    assert contexts[1].question_budget == 5 and "at most 1 more" in round_prompt(contexts[1])
    await vivian.post(f"/api/questions/{_pending(d)[0]['id']}/respond", json={"action": "confirm"})
    await deps.drain()

    d = await _detail(vivian, iid)
    assert d["engine_done"] and d["questions_asked"] == 5
    assert len(contexts) == 2  # budget spent: no third call


async def test_unknown_question_budget_is_rejected(vivian):
    r = await vivian.post("/api/interviews", data={"role": "pm", "request_type": "feature", "text": "x",
                                                   "question_budget": "huge"})
    assert r.status_code == 400


async def test_requester_deletes_interview_with_its_files(app, deps, vivian, kevin):
    r = await vivian.post(
        "/api/interviews",
        data={"role": "pm", "request_type": "feature", "text": "x"},
        files=[("files", ("notes.txt", b"notes", "text/plain"))],
    )
    iid = r.json()["id"]
    await deps.drain()
    d = await _detail(vivian, iid)
    q = _pending(d)[0]
    await vivian.post(f"/api/interviews/{iid}/handoffs", json={"question_ids": [q["id"]], "to_email": "kevin@linkervision.com"})
    assert (deps.settings.upload_dir / iid).is_dir()

    assert (await kevin.delete(f"/api/interviews/{iid}")).status_code == 403
    assert (await vivian.delete(f"/api/interviews/{iid}")).status_code == 200

    assert (await vivian.get(f"/api/interviews/{iid}")).status_code == 404
    assert iid not in [i["id"] for i in (await vivian.get("/api/interviews?scope=mine")).json()]
    assert not (deps.settings.upload_dir / iid).exists()


async def test_cannot_delete_while_the_engine_works(app, deps, vivian, llm):
    gate = asyncio.Event()
    next_round = llm.next_round

    async def slow_round(ctx, knowledge, progress=None):
        await gate.wait()
        return await next_round(ctx, knowledge, progress)

    llm.next_round = slow_round
    iid = (await vivian.post("/api/interviews", data={"role": "pm", "request_type": "feature", "text": "x"})).json()["id"]
    r = await vivian.delete(f"/api/interviews/{iid}")
    assert r.status_code == 409
    gate.set()
    await deps.drain()
    assert (await vivian.delete(f"/api/interviews/{iid}")).status_code == 200


async def test_audience_defaults_by_role_and_reaches_the_prompt(app, deps, vivian, llm):
    iid = (await vivian.post("/api/interviews", data={"role": "rd", "request_type": "task", "text": "x"})).json()["id"]
    await deps.drain()
    d = await _detail(vivian, iid)
    assert d["audience"] == "pm" and d["assignee"] is None  # RD clarifies with PM

    iid = (await vivian.post("/api/interviews", data={
        "role": "pm", "request_type": "feature", "text": "x", "audience": "fae", "assignee": "Kevin@LinkerVision.com",
    })).json()["id"]
    await deps.drain()
    d = await _detail(vivian, iid)
    assert d["audience"] == "fae" and d["assignee"] == "kevin@linkervision.com"
    ctx = llm.calls[-1][1]
    assert "Audience: the Spec is for an FAE" in round_prompt(ctx)

    r = await vivian.post("/api/interviews", data={"role": "pm", "request_type": "feature", "text": "x",
                                                   "assignee": "not-an-email"})
    assert r.status_code == 400


async def test_no_questions_goes_straight_to_a_spec(app, deps, vivian, llm):
    r = await vivian.post("/api/interviews", data={
        "role": "pm", "request_type": "feature", "text": "歷史事件要能用路口、路段、地點關鍵字篩選",
        "question_budget": "none",
    })
    iid = r.json()["id"]
    await deps.drain()

    d = await _detail(vivian, iid)
    assert d["status"] == "spec_draft" and d["spec_markdown"] and not d["questions"]
    assert [kind for kind, _ in llm.calls] == ["spec"]  # no round was asked
    assert "skip the interview" in spec_prompt(llm.calls[0][1])


async def test_assignee_suggestions_come_from_recent_ado_assignees(app, vivian, fake_ado):
    assert (await vivian.get("/api/ado/people")).status_code == 409  # not connected to ADO yet
    await vivian.put("/api/me/ado", json={"pat": "good-pat-1234567890", "expires_on": "2027-10-01"})

    people = (await vivian.get("/api/ado/people")).json()
    assert [(p["email"], p["assigned"]) for p in people] == [
        ("kevin@linkervision.com", 2), ("froggy@linkervision.com", 1),
    ]  # same person under two spellings is merged; service accounts without an email are dropped
    assert people[0]["display_name"] == "Kevin Lin"

    calls = fake_ado.wiql_calls
    await vivian.get("/api/ado/people")
    assert fake_ado.wiql_calls == calls  # cached


async def _spec_ready(vivian, deps, request_type):
    iid = (await vivian.post("/api/interviews", data={"role": "pm", "request_type": request_type, "text": "x",
                                                      "question_budget": "none"})).json()["id"]
    await deps.drain()
    await vivian.put("/api/me/ado", json={"pat": "good-pat-1234567890", "expires_on": "2027-10-01"})
    return iid


async def test_feature_opens_as_task_by_default(app, deps, vivian, fake_ado):
    iid = await _spec_ready(vivian, deps, "feature")
    r = await vivian.post(f"/api/interviews/{iid}/ticket", json={"title": "t", "severity": "2 - High"})
    assert r.status_code == 200, r.text
    created = fake_ado.created[-1]
    fields = {op["path"]: op["value"] for op in created["ops"]}
    assert created["type"] == "Task"
    assert "/fields/Microsoft.VSTS.Common.Severity" not in fields  # severity only on a Bug
    assert (await _detail(vivian, iid))["ticket_type"] == "Task"


async def test_unknown_work_item_type_is_rejected(app, deps, vivian, fake_ado):
    iid = await _spec_ready(vivian, deps, "feature")
    r = await vivian.post(f"/api/interviews/{iid}/ticket", json={"title": "t", "work_item_type": "Epic"})
    assert r.status_code == 400 and not fake_ado.created


async def test_ticket_keeps_only_existing_tags_without_tag_permission(app, deps, vivian, fake_ado):
    fake_ado.can_create_tags = False
    iid = await _spec_ready(vivian, deps, "feature")
    r = await vivian.post(f"/api/interviews/{iid}/ticket", json={"title": "t"})
    assert r.status_code == 200, r.text
    fields = {op["path"]: op["value"] for op in fake_ado.created[-1]["ops"]}
    assert fields["/fields/System.Tags"] == "ticket-sprite; role:pm"  # to:rd is new, dropped


async def test_parent_choices_are_the_current_iteration_user_stories(app, vivian, fake_ado):
    await vivian.put("/api/me/ado", json={"pat": "good-pat-1234567890", "expires_on": "2027-10-01"})
    r = await vivian.get("/api/ado/parents")
    assert r.status_code == 200, r.text
    assert [w["id"] for w in r.json()] == [41152, 41155]  # board order kept


async def test_pm_and_fae_specs_are_requests_not_designs(app, deps, vivian, llm):
    for role in ("fae", "rd"):
        await vivian.post("/api/interviews", data={"role": role, "request_type": "feature", "text": "x",
                                                   "question_budget": "none"})
    await deps.drain()
    fae_ctx, rd_ctx = (ctx for kind, ctx in llm.calls if kind == "spec")
    assert "not a design document" in spec_prompt(fae_ctx) and fae_ctx.template.id == "grill_product"
    assert "Do use the terms defined in CONTEXT.md" in spec_prompt(fae_ctx)
    assert "not a design document" not in spec_prompt(rd_ctx)


async def test_regenerating_a_draft_spec_replaces_it(app, deps, vivian, llm):
    iid = (await vivian.post("/api/interviews", data={"role": "pm", "request_type": "feature", "text": "x",
                                                      "question_budget": "none"})).json()["id"]
    await deps.drain()
    await vivian.put(f"/api/interviews/{iid}/spec", json={"title": "t", "markdown": "edited by hand"})

    assert (await vivian.post(f"/api/interviews/{iid}/spec/regenerate")).status_code == 200
    await deps.drain()
    d = await _detail(vivian, iid)
    assert d["spec_markdown"] != "edited by hand" and d["spec_revision"] is None
    assert [k for k, _ in llm.calls] == ["spec", "spec"]


async def test_regenerated_spec_updates_the_ticket_description(app, deps, vivian, kevin, fake_ado):
    iid = await _spec_ready(vivian, deps, "feature")
    await vivian.post(f"/api/interviews/{iid}/ticket", json={"title": "t"})
    ticket_id = (await _detail(vivian, iid))["ticket_id"]

    assert (await kevin.post(f"/api/interviews/{iid}/spec/regenerate")).status_code == 403
    assert (await vivian.post(f"/api/interviews/{iid}/spec/regenerate")).status_code == 200
    await deps.drain()
    d = await _detail(vivian, iid)
    revision = d["spec_revision"]
    assert revision and not fake_ado.patched  # nothing reaches ADO until applied

    fake_ado.description_editors = ["Kevin Lin"]
    r = await vivian.post(f"/api/interviews/{iid}/spec/revision/apply", json={})
    assert r.status_code == 409 and "Kevin Lin" in r.json()["detail"] and "Someone Else" not in r.json()["detail"]
    assert not fake_ado.patched

    r = await vivian.post(f"/api/interviews/{iid}/spec/revision/apply", json={"force": True})
    assert r.status_code == 200, r.text
    patch = fake_ado.patched[-1]
    fields = {op["path"]: op["value"] for op in patch["ops"]}
    assert patch["id"] == ticket_id and "/fields/Microsoft.VSTS.TCM.ReproSteps" not in fields
    assert f"/interviews/{iid}" in fields["/fields/System.Description"]
    d = await _detail(vivian, iid)
    assert d["spec_markdown"] == revision and d["spec_revision"] is None


async def test_spec_revision_can_be_discarded(app, deps, vivian, fake_ado):
    iid = await _spec_ready(vivian, deps, "feature")
    await vivian.post(f"/api/interviews/{iid}/ticket", json={"title": "t"})
    await vivian.post(f"/api/interviews/{iid}/spec/regenerate")
    await deps.drain()
    assert (await vivian.delete(f"/api/interviews/{iid}/spec/revision")).status_code == 200
    assert (await _detail(vivian, iid))["spec_revision"] is None
    assert (await vivian.post(f"/api/interviews/{iid}/spec/revision/apply", json={})).status_code == 400


async def test_decision_record_spec_can_be_regenerated(app, deps, vivian, fake_ado):
    iid = (await vivian.post("/api/interviews", data={"role": "pm", "request_type": "feature", "text": "x",
                                                      "question_budget": "none"})).json()["id"]
    await deps.drain()
    await vivian.put(f"/api/interviews/{iid}/spec", json={"title": "t", "markdown": "old record"})
    assert (await vivian.post(f"/api/interviews/{iid}/decision-record", json={"title": "t"})).status_code == 200

    assert (await vivian.post(f"/api/interviews/{iid}/spec/regenerate")).status_code == 200
    await deps.drain()
    d = await _detail(vivian, iid)
    assert d["spec_markdown"] == "old record" and d["spec_revision"]  # kept aside for review

    assert (await vivian.post(f"/api/interviews/{iid}/spec/revision/apply", json={})).status_code == 200
    d = await _detail(vivian, iid)
    assert d["spec_markdown"] != "old record" and d["spec_revision"] is None
    assert not fake_ado.patched  # a Decision Record never touches ADO
