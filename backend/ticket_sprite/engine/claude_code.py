"""Interviewer backed by the owner's own Claude Code CLI (`claude -p`).

Single-user mode only: the CLI runs on the owner's Claude login, so the web app
must serve nobody else (see `Settings.single_user`). Reads are confined by the
CLI's working directory: tools may read inside it and the attachment folder,
and every read elsewhere is denied by `--permission-mode dontAsk`.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import shutil
import signal
import tempfile
from pathlib import Path

from ..config import Settings
from ..knowledge import Depth, KnowledgeSource
from .llm import EngineError, InterviewContext, round_prompt, spec_prompt, system_prompt
from .progress import EngineProgress, display_path
from .schema import ROUND_SCHEMA, SPEC_SCHEMA, RoundResult, SpecResult

TOOL_NOTE = (
    "\nYour tools are Read, Grep and Glob over the current working directory (the product's "
    "Knowledge Source). Attachments are files you can Read at the paths given in the request."
)


# One stream-json line can carry a whole file Read; asyncio's default line limit is 64 KiB
STREAM_LINE_LIMIT = 64 * 1024 * 1024


def _track(event: dict, progress: EngineProgress, cwd: Path) -> None:
    for block in event.get("message", {}).get("content", []):
        if block.get("type") != "tool_use":
            continue
        name, args = block.get("name"), block.get("input") or {}
        if name == "Read":
            progress.read(display_path(str(args.get("file_path", "")), cwd))
        elif name in ("Grep", "Glob"):
            progress.search()


async def _result_event(stdout: asyncio.StreamReader, progress: EngineProgress | None, cwd: Path) -> dict | None:
    result = None
    async for line in stdout:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "assistant" and progress is not None:
            _track(event, progress, cwd)
        elif event.get("type") == "result":
            result = event
    return result


def _copy_visible(knowledge: KnowledgeSource, dest: Path) -> None:
    """Materialise the view this depth may see (docs for PM and FAE; code minus the Product's hidden files)."""
    for rel in knowledge.visible_files():
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(knowledge.root / rel, dest / rel)


class ClaudeCodeInterviewer:
    def __init__(self, settings: Settings):
        self._s = settings

    async def next_round(
        self, ctx: InterviewContext, knowledge: KnowledgeSource, progress: EngineProgress | None = None
    ) -> RoundResult:
        return RoundResult.from_json(await self._run(ctx, knowledge, round_prompt(ctx), ROUND_SCHEMA, progress))

    async def write_spec(
        self, ctx: InterviewContext, knowledge: KnowledgeSource, progress: EngineProgress | None = None
    ) -> SpecResult:
        return SpecResult.from_json(await self._run(ctx, knowledge, spec_prompt(ctx), SPEC_SCHEMA, progress))

    def _command(self, prompt: str, schema: dict, knowledge: KnowledgeSource, attachment_dirs: list[Path]) -> list[str]:
        cmd = [
            self._s.claude_code_bin, "-p", prompt,
            "--output-format", "stream-json", "--verbose",
            "--json-schema", json.dumps(schema),
            "--tools", "Read", "Grep", "Glob",
            "--permission-mode", "dontAsk",
            "--no-session-persistence",
            "--setting-sources", "",
            "--strict-mcp-config",
            "--system-prompt", system_prompt(knowledge) + TOOL_NOTE,
            "--effort", self._s.anthropic_effort,
        ]
        if self._s.claude_code_model:
            cmd += ["--model", self._s.claude_code_model]
        for d in attachment_dirs:
            cmd += ["--add-dir", str(d)]
        return cmd

    async def _run(
        self,
        ctx: InterviewContext,
        knowledge: KnowledgeSource,
        prompt: str,
        schema: dict,
        progress: EngineProgress | None = None,
    ) -> dict:
        if not knowledge.root.is_dir():
            raise EngineError("Knowledge Source 尚未就緒（clone 還沒完成）")
        attachment_dirs = sorted({a.path.parent.resolve() for a in ctx.attachments})
        if ctx.attachments:
            listing = "\n".join(f"- {a.filename} ({a.content_type}): {a.path.resolve()}" for a in ctx.attachments)
            prompt = f"Attachments (Read them before the first round):\n{listing}\n\n{prompt}"

        with tempfile.TemporaryDirectory(prefix="sprite-docs-") as tmp:
            # RD reads the product root in place, unless the Product hides files there (the CLI can't be told to skip them)
            if knowledge.depth is Depth.DOCS or knowledge.product.hidden_globs:
                _copy_visible(knowledge, Path(tmp))
                cwd = Path(tmp)
            else:
                cwd = knowledge.root
            cmd = self._command(prompt, schema, knowledge, attachment_dirs)
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd, cwd=cwd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                    stdin=asyncio.subprocess.DEVNULL, limit=STREAM_LINE_LIMIT,
                    start_new_session=True,  # its own process group, so stopping it also stops its tools
                )
            except FileNotFoundError as exc:
                raise EngineError(f"找不到 Claude Code CLI：{self._s.claude_code_bin}") from exc
            assert proc.stdout is not None and proc.stderr is not None
            stderr = asyncio.create_task(proc.stderr.read())
            try:
                data = await asyncio.wait_for(
                    _result_event(proc.stdout, progress, cwd), self._s.claude_code_timeout_seconds
                )
                await proc.wait()
            except BaseException as exc:
                # timed out, or the Requester stopped the sprite (task cancelled)
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(proc.pid, signal.SIGKILL)
                await proc.wait()
                if isinstance(exc, TimeoutError):
                    raise EngineError("Claude Code 逾時") from exc
                raise
            finally:
                err = await stderr

        if data is None:
            detail = err.decode(errors="ignore").strip()[-300:]
            raise EngineError(f"Claude Code 執行失敗：{detail or proc.returncode}")
        if data.get("is_error") or data.get("subtype") != "success":
            raise EngineError(f"Claude Code 錯誤：{str(data.get('result') or data.get('subtype'))[:300]}")
        result = data.get("structured_output")
        if not isinstance(result, dict):
            raise EngineError("Claude Code 沒有回傳結構化結果")
        return result
