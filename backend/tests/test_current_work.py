"""Current Work: the Parent's open and lately closed tickets, with the PRs that name them."""

from __future__ import annotations

PAT = {"pat": "good-pat-1234567890", "expires_on": "2027-10-01"}


async def test_current_work_lists_open_and_lately_closed_tickets_with_their_prs(app, vivian):
    await vivian.put("/api/me/ado", json=PAT)
    r = await vivian.get("/api/work?product=middleware")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["parent_id"] == 41152 and body["github"] is True
    # Active, then Testing, then New, then what closed in the last two weeks; long closed and removed left out
    assert [i["id"] for i in body["items"]] == [45772, 45669, 45736, 45615]
    by_id = {i["id"]: i for i in body["items"]}
    assert by_id[45772]["assignee"] == "Vivian Fan" and by_id[45772]["iteration"] == "SPRINT 1"
    assert by_id[45736]["assignee"] is None
    assert by_id[45615]["closed_on"] is not None and by_id[45772]["closed_on"] is None
    assert [(p["repo"], p["number"], p["state"]) for p in by_id[45669]["prs"]] == [("lighthouse-saas-api", 212, "merged")]
    assert [(p["repo"], p["number"], p["state"]) for p in by_id[45772]["prs"]] == [("deliver-heimdall", 1, "open")]
    assert by_id[45736]["prs"] == []


async def test_current_work_without_a_github_token_shows_tickets_only(app, deps, vivian):
    deps.settings.github_token = ""
    await vivian.put("/api/me/ado", json=PAT)
    body = (await vivian.get("/api/work?product=middleware")).json()
    assert body["github"] is False
    assert len(body["items"]) == 4 and all(i["prs"] == [] for i in body["items"])


async def test_current_work_needs_an_ado_credential(app, vivian):
    r = await vivian.get("/api/work?product=middleware")
    assert r.status_code == 409


async def test_current_work_is_cached_across_people(app, deps, vivian, kevin, fake_ado):
    await vivian.put("/api/me/ado", json=PAT)
    await vivian.get("/api/work?product=middleware")
    fake_ado.children.clear()
    # Kevin has no PAT, but the list Vivian fetched a moment ago is still fresh
    r = await kevin.get("/api/work?product=middleware")
    assert r.status_code == 200 and len(r.json()["items"]) == 4


async def test_the_interviewer_sees_current_work(app, deps, vivian, llm):
    from ticket_sprite.engine.llm import round_prompt, spec_prompt

    await vivian.put("/api/me/ado", json=PAT)
    await vivian.post("/api/interviews", data={"role": "pm", "request_type": "feature", "text": "x"})
    await deps.drain()
    ctx = next(c for kind, c in llm.calls if kind == "round")
    assert "#45772" in ctx.current_work and "PR #1 open" in ctx.current_work
    assert "#41154" not in ctx.current_work
    assert "<current_work>" in round_prompt(ctx) and "<current_work>" in spec_prompt(ctx)


async def test_an_interview_runs_without_current_work_when_ado_is_not_connected(app, deps, vivian, llm):
    from ticket_sprite.engine.llm import round_prompt

    await vivian.post("/api/interviews", data={"role": "pm", "request_type": "feature", "text": "x"})
    await deps.drain()
    ctx = next(c for kind, c in llm.calls if kind == "round")
    assert ctx.current_work is None and "<current_work>" not in round_prompt(ctx)
