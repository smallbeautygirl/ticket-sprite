"""Knowledge Source: a dedicated, read-only `main` clone (ADR-0002).

Tools exposed to the model are confined to the Product root. In `docs` depth
(the PM role) only glossary / ADR / spec documents are visible.
"""

from __future__ import annotations

import asyncio
import fnmatch
import logging
import os
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .config import Settings

log = logging.getLogger(__name__)

MAX_READ_LINES = 400
MAX_GREP_HITS = 60
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "logs", ".pytest_cache", ".mypy_cache"}
DOC_GLOBS = ["CONTEXT.md", "CONTEXT-MAP.md", "README*.md", "docs/**", "*.md"]


class Depth(StrEnum):
    DOCS = "docs"
    CODE = "code"


class KnowledgeError(Exception):
    pass


@dataclass
class KnowledgeSource:
    root: Path
    depth: Depth

    def _resolve(self, rel: str) -> Path:
        rel = (rel or ".").lstrip("/")
        path = (self.root / rel).resolve()
        root = self.root.resolve()
        if path != root and root not in path.parents:
            raise KnowledgeError(f"path outside knowledge source: {rel}")
        if path.is_file() and not self._visible(path):
            raise KnowledgeError(f"not visible at depth={self.depth}: {rel}")
        return path

    def _visible(self, path: Path) -> bool:
        rel = path.resolve().relative_to(self.root.resolve()).as_posix()
        if any(part in SKIP_DIRS for part in rel.split("/")):
            return False
        if self.depth is Depth.CODE:
            return True
        return any(fnmatch.fnmatch(rel, g) or rel.startswith("docs/") for g in DOC_GLOBS)

    def _iter_files(self, base: Path):
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            for name in sorted(filenames):
                p = Path(dirpath) / name
                if self._visible(p):
                    yield p

    # ---- tools ----

    def list_files(self, path: str = ".", pattern: str = "*") -> str:
        base = self._resolve(path)
        if not base.is_dir():
            raise KnowledgeError(f"not a directory: {path}")
        root = self.root.resolve()
        hits = [
            p.resolve().relative_to(root).as_posix()
            for p in self._iter_files(base)
            if fnmatch.fnmatch(p.name, pattern)
        ]
        if not hits:
            return "(no files)"
        more = f"\n… {len(hits) - 300} more" if len(hits) > 300 else ""
        return "\n".join(hits[:300]) + more

    def grep(self, pattern: str, path: str = ".", glob: str = "*") -> str:
        try:
            rx = re.compile(pattern, re.IGNORECASE)
        except re.error as exc:
            raise KnowledgeError(f"bad regex: {exc}") from exc
        base = self._resolve(path)
        files = [base] if base.is_file() else self._iter_files(base)
        root = self.root.resolve()
        out: list[str] = []
        for f in files:
            if not fnmatch.fnmatch(f.name, glob):
                continue
            try:
                with f.open(encoding="utf-8", errors="ignore") as fh:
                    for i, line in enumerate(fh, 1):
                        if rx.search(line):
                            out.append(f"{f.resolve().relative_to(root).as_posix()}:{i}: {line.rstrip()[:240]}")
                            if len(out) >= MAX_GREP_HITS:
                                return "\n".join(out) + "\n… (truncated; narrow the pattern or path)"
            except OSError:
                continue
        return "\n".join(out) or "(no matches)"

    def read_file(self, path: str, start_line: int = 1, max_lines: int = 200) -> str:
        f = self._resolve(path)
        if not f.is_file():
            raise KnowledgeError(f"not a file: {path}")
        max_lines = max(1, min(max_lines, MAX_READ_LINES))
        start_line = max(1, start_line)
        lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
        chunk = lines[start_line - 1 : start_line - 1 + max_lines]
        numbered = "\n".join(f"{start_line + i}\t{line}" for i, line in enumerate(chunk))
        tail = ""
        if start_line - 1 + max_lines < len(lines):
            tail = f"\n… file has {len(lines)} lines; continue with start_line={start_line + max_lines}"
        return numbered + tail

    def call(self, name: str, args: dict) -> str:
        if name == "list_files":
            return self.list_files(args.get("path", "."), args.get("pattern", "*"))
        if name == "grep":
            return self.grep(args["pattern"], args.get("path", "."), args.get("glob", "*"))
        if name == "read_file":
            return self.read_file(args["path"], int(args.get("start_line", 1)), int(args.get("max_lines", 200)))
        raise KnowledgeError(f"unknown tool: {name}")


TOOL_DEFS: list[dict] = [
    {
        "name": "list_files",
        "description": "List files under a directory of the product's Knowledge Source (paths relative to the product root).",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory relative to the product root. Default '.'"},
                "pattern": {"type": "string", "description": "fnmatch pattern on the file name, e.g. '*.md'"},
            },
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "grep",
        "description": "Case-insensitive regex search across the Knowledge Source. Returns path:line: text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "path": {"type": "string", "description": "File or directory to search. Default '.'"},
                "glob": {"type": "string", "description": "fnmatch on file names, e.g. '*.py'"},
            },
            "required": ["pattern"],
            "additionalProperties": False,
        },
    },
    {
        "name": "read_file",
        "description": "Read a file (with line numbers) from the Knowledge Source.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "start_line": {"type": "integer"},
                "max_lines": {"type": "integer", "description": "At most 400"},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    },
]


# ---- keeping the clone fresh ----


async def _git(*args: str, cwd: Path | None = None) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        "git", *args, cwd=cwd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
    )
    out, _ = await proc.communicate()
    return proc.returncode or 0, out.decode(errors="ignore")


async def sync_knowledge(settings: Settings) -> None:
    repo = settings.knowledge_root / settings.knowledge_repo_dir
    if not (repo / ".git").exists():
        settings.knowledge_root.mkdir(parents=True, exist_ok=True)
        code, out = await _git(
            "clone", "--branch", settings.knowledge_branch, "--single-branch",
            settings.knowledge_repo_source, str(repo),
        )
        log.info("knowledge clone exit=%s %s", code, out[-300:])
        return
    code, out = await _git("pull", "--ff-only", "origin", settings.knowledge_branch, cwd=repo)
    if code:
        log.warning("knowledge pull failed: %s", out[-300:])


async def knowledge_sync_loop(settings: Settings) -> None:
    while True:
        try:
            await sync_knowledge(settings)
        except Exception:  # keep the loop alive
            log.exception("knowledge sync failed")
        await asyncio.sleep(settings.knowledge_pull_interval_seconds)
