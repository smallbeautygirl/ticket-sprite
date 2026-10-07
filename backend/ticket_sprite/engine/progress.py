"""What the interviewer is doing right now, for the waiting screen.

Kept in memory only: it matters while a round or Spec is being written and is
meaningless after a restart, when the engine run it describes is gone too.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from ..models import utcnow

SHOWN_READS = 12


@dataclass
class EngineProgress:
    started_at: datetime = field(default_factory=utcnow)
    reads: list[str] = field(default_factory=list)
    searches: int = 0

    def read(self, path: str) -> None:
        if path and path not in self.reads:
            self.reads.append(path)

    def search(self) -> None:
        self.searches += 1

    def to_json(self) -> dict:
        return {
            "started_at": self.started_at.isoformat(),
            "reads": self.reads[-SHOWN_READS:],
            "read_count": len(self.reads),
            "searches": self.searches,
        }


def display_path(path: str, root: Path) -> str:
    """Show a Knowledge Source file relative to its root; anything else (attachments) by name."""
    p = Path(path)
    if not p.is_absolute():
        return p.as_posix()
    try:
        return p.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return p.name
