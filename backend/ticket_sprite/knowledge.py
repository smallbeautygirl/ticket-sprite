"""Knowledge Source: a dedicated, read-only clone per Product, tracking its branch (ADR-0002, ADR-0004).

Tools exposed to the model are confined to the Product root. In `docs` depth
(PM and FAE) only glossary / ADR / spec documents and the Product's screens are visible.
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
from .products import MIDDLEWARE, Product, products

log = logging.getLogger(__name__)

MAX_READ_LINES = 400
MAX_GREP_HITS = 60
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "logs", ".pytest_cache", ".mypy_cache"}
DOC_GLOBS = ["CONTEXT.md", "CONTEXT-MAP.md", "README*.md", "docs/**", "*.md"]
# Plus each Product's screens (Product.screen_globs): PM and FAE describe what they saw on screen,
# and need those words mapped to the glossary


class Depth(StrEnum):
    DOCS = "docs"
    CODE = "code"


class KnowledgeError(Exception):
    pass


@dataclass
class KnowledgeSource:
    root: Path
    depth: Depth
    product: Product = MIDDLEWARE

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
        if any(fnmatch.fnmatch(rel, g) for g in self.product.hidden_globs):
            return False
        if self.depth is Depth.CODE:
            return True
        globs = [*DOC_GLOBS, *self.product.screen_globs]
        return any(fnmatch.fnmatch(rel, g) or rel.startswith("docs/") for g in globs)

    def visible_files(self):
        """Every file visible at this depth, relative to the product root."""
        root = self.root.resolve()
        for p in self._iter_files(self.root):
            yield p.resolve().relative_to(root)

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


async def sync_product(settings: Settings, p: Product) -> None:
    """Bring a Product's clone to the tip of its branch.

    Fetch-and-reset rather than pull: a feature branch may be rebased or force-pushed, and a
    read-only clone has nothing of its own to keep. A local-path source may only know the branch
    as a remote-tracking ref (fetched there but never checked out), so that ref is tried too.
    """
    repo = settings.knowledge_root / p.clone_dir
    if not (repo / ".git").exists():
        repo.mkdir(parents=True, exist_ok=True)
        await _git("init", "-q", cwd=repo)
        await _git("remote", "add", "origin", settings.knowledge_repo_source, cwd=repo)
    tracking = f"refs/remotes/origin/{p.branch}"
    for ref in (f"refs/heads/{p.branch}", tracking):
        code, out = await _git("fetch", "-q", "origin", f"+{ref}:{tracking}", cwd=repo)
        if code == 0:
            break
    else:
        log.warning("knowledge fetch failed for %s (%s): %s", p.id, p.branch, out[-300:])
        return
    code, out = await _git("checkout", "-q", "-f", "-B", p.branch, tracking, cwd=repo)
    if code:
        log.warning("knowledge checkout failed for %s: %s", p.id, out[-300:])


async def sync_knowledge(settings: Settings) -> None:
    for p in products(settings).values():
        try:
            await sync_product(settings, p)
        except Exception:  # one Product's trouble must not keep the others stale
            log.exception("knowledge sync failed for %s", p.id)


async def knowledge_sync_loop(settings: Settings) -> None:
    while True:
        try:
            await sync_knowledge(settings)
        except Exception:  # keep the loop alive
            log.exception("knowledge sync failed")
        await asyncio.sleep(settings.knowledge_pull_interval_seconds)
