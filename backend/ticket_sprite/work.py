"""Current Work: what is open or just closed under a Product's Parent, with the PRs that name it.

PMs read it to see what RD is already doing; the interviewer reads it to spot a Request that
overlaps a ticket. Tickets come from ADO; a PR belongs to a ticket when its title or body says AB#<id>.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import httpx

from .ado import AdoClient, ChildWorkItem
from .products import Product

log = logging.getLogger(__name__)

RECENTLY_CLOSED_DAYS = 14
CLOSED_STATES = {"Closed", "Done"}
DROPPED_STATES = {"Removed"}
# Furthest along first among open tickets; anything unknown sits beside Testing
STATE_ORDER = {"Active": 0, "Testing": 1, "Resolved": 2, "New": 3}
AB_REF = re.compile(r"AB#(\d+)")


@dataclass(frozen=True)
class PullRequest:
    repo: str  # owner/name
    number: int
    title: str
    state: str  # open, merged or closed (closed without merging)
    url: str
    work_item_ids: frozenset[int]


@dataclass(frozen=True)
class WorkEntry:
    item: ChildWorkItem
    prs: list[PullRequest] = field(default_factory=list)


@dataclass(frozen=True)
class CurrentWork:
    parent_id: int
    entries: list[WorkEntry]
    github: bool  # whether PR state was looked up at all


class GitHub:
    def __init__(self, token: str, transport: httpx.AsyncBaseTransport | None = None):
        self._headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        self._transport = transport

    async def recent_pulls(self, repo: str) -> list[PullRequest]:
        """The repo's 100 most recently updated PRs, open or not."""
        async with httpx.AsyncClient(headers=self._headers, timeout=20, transport=self._transport) as c:
            resp = await c.get(
                f"https://api.github.com/repos/{repo}/pulls",
                params={"state": "all", "sort": "updated", "direction": "desc", "per_page": 100},
            )
        resp.raise_for_status()
        return [
            PullRequest(
                repo=repo,
                number=p["number"],
                title=p.get("title") or "",
                state="merged" if p.get("merged_at") else p.get("state", "open"),
                url=p.get("html_url", ""),
                work_item_ids=frozenset(int(i) for i in AB_REF.findall(f"{p.get('title') or ''} {p.get('body') or ''}")),
            )
            for p in resp.json()
        ]


async def _pulls(github: GitHub, repos: tuple[str, ...]) -> list[PullRequest]:
    out: list[PullRequest] = []
    for repo in repos:
        try:
            out += await github.recent_pulls(repo)
        except httpx.HTTPError as exc:
            # PR state is a nicety: the tickets still show without it
            log.warning("could not list pull requests of %s: %s", repo, exc)
    return out


def _relevant(item: ChildWorkItem, now: datetime) -> bool:
    if item.state in DROPPED_STATES:
        return False
    if item.state in CLOSED_STATES:
        return item.closed is not None and now - item.closed <= timedelta(days=RECENTLY_CLOSED_DAYS)
    return True


def _order(item: ChildWorkItem) -> tuple:
    if item.state in CLOSED_STATES:
        return (9, -(item.closed or datetime.min.replace(tzinfo=timezone.utc)).timestamp())
    return (STATE_ORDER.get(item.state, 1), -item.id)


async def current_work(
    ado: AdoClient, github: GitHub | None, product: Product, now: datetime | None = None
) -> CurrentWork:
    now = now or datetime.now(timezone.utc)
    items = sorted((i for i in await ado.children(product.default_parent_id) if _relevant(i, now)), key=_order)
    pulls = await _pulls(github, product.github_repos) if github else []
    entries = [
        WorkEntry(item=i, prs=sorted((p for p in pulls if i.id in p.work_item_ids), key=lambda p: (p.repo, -p.number)))
        for i in items
    ]
    return CurrentWork(parent_id=product.default_parent_id, entries=entries, github=github is not None)


def as_json(work: CurrentWork) -> list[dict]:
    return [
        {
            "id": e.item.id,
            "title": e.item.title,
            "type": e.item.work_item_type,
            "state": e.item.state,
            "assignee": e.item.assignee,
            "iteration": e.item.iteration,
            "closed_on": e.item.closed.date().isoformat() if e.item.closed else None,
            "url": e.item.url,
            "prs": [
                {"repo": p.repo.rsplit("/", 1)[-1], "number": p.number, "title": p.title, "state": p.state, "url": p.url}
                for p in e.prs
            ],
        }
        for e in work.entries
    ]


def for_interviewer(work: CurrentWork) -> str:
    """One line per ticket, e.g. `#45669 [Testing · Froggy Hong] 模型用量頁 — PR #212 merged`."""
    lines = []
    for e in work.entries:
        who = f" · {e.item.assignee}" if e.item.assignee else ""
        when = f" {e.item.closed.date().isoformat()}" if e.item.closed else ""
        prs = ", ".join(f"PR #{p.number} {p.state}" for p in e.prs)
        lines.append(f"#{e.item.id} [{e.item.state}{when}{who}] {e.item.title}" + (f" — {prs}" if prs else ""))
    return "\n".join(lines)
