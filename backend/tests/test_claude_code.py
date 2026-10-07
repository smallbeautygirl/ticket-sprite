"""Single-user mode: the owner's own `claude -p` drives the interview."""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

from ticket_sprite.engine.claude_code import ClaudeCodeInterviewer
from ticket_sprite.engine.llm import AttachmentInput, EngineError, InterviewContext
from ticket_sprite.engine.progress import EngineProgress
from ticket_sprite.engine.templates import TEMPLATES
from ticket_sprite.knowledge import Depth, KnowledgeSource
from ticket_sprite.main import create_app

from .conftest import client_for

ROUND = {"done": True, "summary": "ok", "questions": [], "new_terms": []}


def _fake_claude(tmp_path: Path, payload: dict) -> Path:
    """A stand-in CLI that records argv + cwd and prints a `claude -p --output-format json` result."""
    log = tmp_path / "claude-call.json"
    script = tmp_path / "fake-claude"
    script.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        f"json.dump({{'argv': sys.argv[1:], 'cwd': os.getcwd(), 'files': sorted(os.listdir('.'))}}, open({str(log)!r}, 'w'))\n"
        f"print(json.dumps({payload!r}))\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


def _ctx(attachments=None) -> InterviewContext:
    return InterviewContext(
        template=TEMPLATES["grill_product"], role="pm", request_type="feature",
        requester="v@x.com", request_text="想要過濾事件", attachments=attachments or [],
    )


async def test_docs_depth_runs_in_docs_only_copy(settings, tmp_path):
    settings.claude_code_bin = str(_fake_claude(tmp_path, {
        "type": "result", "subtype": "success", "is_error": False, "structured_output": ROUND,
    }))
    att = tmp_path / "uploads" / "i1" / "a_notes.txt"
    att.parent.mkdir(parents=True)
    att.write_text("customer notes")

    result = await ClaudeCodeInterviewer(settings).next_round(
        _ctx([AttachmentInput("notes.txt", "text/plain", att)]),
        KnowledgeSource(root=settings.product_root, depth=Depth.DOCS),
    )

    assert result.done
    call = json.loads((tmp_path / "claude-call.json").read_text())
    argv = call["argv"]
    # PM sees documents only: the CLI runs in a copy without app/ code
    assert call["files"] == ["CONTEXT.md", "docs"]
    assert Path(call["cwd"]) != settings.product_root
    assert argv[argv.index("--permission-mode") + 1] == "dontAsk"
    assert argv[argv.index("--tools") + 1 : argv.index("--tools") + 4] == ["Read", "Grep", "Glob"]
    assert json.loads(argv[argv.index("--json-schema") + 1])["required"] == ["done", "summary", "questions", "new_terms"]
    assert argv[argv.index("--add-dir") + 1] == str(att.parent.resolve())
    assert str(att.resolve()) in argv[argv.index("-p") + 1]


async def test_code_depth_runs_in_product_root(settings, tmp_path):
    settings.claude_code_bin = str(_fake_claude(tmp_path, {
        "type": "result", "subtype": "success", "is_error": False, "structured_output": ROUND,
    }))
    await ClaudeCodeInterviewer(settings).next_round(
        _ctx(), KnowledgeSource(root=settings.product_root, depth=Depth.CODE)
    )
    call = json.loads((tmp_path / "claude-call.json").read_text())
    assert Path(call["cwd"]).resolve() == settings.product_root.resolve()
    assert "--add-dir" not in call["argv"]


async def test_cli_error_becomes_engine_error(settings, tmp_path):
    settings.claude_code_bin = str(_fake_claude(tmp_path, {
        "type": "result", "subtype": "error_max_turns", "is_error": True, "result": "limit",
    }))
    with pytest.raises(EngineError, match="Claude Code"):
        await ClaudeCodeInterviewer(settings).next_round(
            _ctx(), KnowledgeSource(root=settings.product_root, depth=Depth.DOCS)
        )


async def test_missing_cli(settings):
    settings.claude_code_bin = "/nonexistent/claude"
    with pytest.raises(EngineError, match="找不到"):
        await ClaudeCodeInterviewer(settings).next_round(
            _ctx(), KnowledgeSource(root=settings.product_root, depth=Depth.DOCS)
        )


async def test_single_user_mode_only_owner_and_no_handoff(settings, llm, notifier):
    settings.llm_mode = "claude_code"
    settings.owner_email = "Vivian@linkervision.com"
    app = create_app(settings, llm=llm, notifier=notifier, background_jobs=False)
    async with app.router.lifespan_context(app):
        async with client_for(app) as other:
            r = await other.post("/api/auth/login", json={"email": "kevin@linkervision.com"})
            assert r.status_code == 403
        async with client_for(app) as owner:
            assert (await owner.post("/api/auth/login", json={"email": "vivian@linkervision.com"})).status_code == 200
            assert (await owner.get("/api/meta")).json()["single_user"] is True
            iid = (await owner.post("/api/interviews", data={"role": "pm", "request_type": "feature",
                                                             "text": "x"})).json()["id"]
            await app.state.deps.drain()
            q = (await owner.get(f"/api/interviews/{iid}")).json()["questions"][0]
            r = await owner.post(f"/api/interviews/{iid}/handoffs",
                                 json={"question_ids": [q["id"]], "to_email": "kevin@linkervision.com"})
            assert r.status_code == 400 and "單人" in r.json()["detail"]


async def test_single_user_mode_requires_owner(settings, llm, notifier):
    settings.llm_mode = "claude_code"
    settings.owner_email = ""
    app = create_app(settings, llm=llm, notifier=notifier, background_jobs=False)
    with pytest.raises(RuntimeError, match="OWNER_EMAIL"):
        async with app.router.lifespan_context(app):
            pass


def test_fake_cli_is_executable(tmp_path):
    assert os.access(_fake_claude(tmp_path, {}), os.X_OK)


async def test_stream_reports_reads_and_searches(settings, tmp_path):
    """Tool calls in the stream-json feed become progress; the final result line is the answer."""
    script = tmp_path / "fake-claude-stream"
    script.write_text(
        f"#!{sys.executable}\n"
        "import json, os\n"
        "def tool(name, **args):\n"
        "    return {'type': 'tool_use', 'name': name, 'input': args}\n"
        "print(json.dumps({'type': 'system', 'subtype': 'init'}))\n"
        "print('not json')\n"
        "print(json.dumps({'type': 'assistant', 'message': {'content': [\n"
        "    tool('Read', file_path=os.path.join(os.getcwd(), 'docs', 'adr', '0001.md')),\n"
        "    tool('Grep', pattern='Event'),\n"
        "    tool('Read', file_path='/elsewhere/uploads/a_notes.txt'),\n"
        "    tool('Read', file_path=os.path.join(os.getcwd(), 'docs', 'adr', '0001.md')),\n"
        "]}}))\n"
        f"print(json.dumps({{'type': 'result', 'subtype': 'success', 'is_error': False, 'structured_output': {ROUND!r}}}))\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    settings.claude_code_bin = str(script)
    progress = EngineProgress()

    result = await ClaudeCodeInterviewer(settings).next_round(
        _ctx(), KnowledgeSource(root=settings.product_root, depth=Depth.DOCS), progress
    )

    assert result.done
    assert progress.reads == ["docs/adr/0001.md", "a_notes.txt"]
    assert progress.searches == 1
