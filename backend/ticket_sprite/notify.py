"""Notification: Adaptive Cards posted to a Teams channel via a Workflows webhook."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from .config import Settings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Mention:
    email: str
    name: str

    @property
    def tag(self) -> str:
        return f"<at>{self.name}</at>"


def build_card(title: str, lines: list[str], link: tuple[str, str] | None, mentions: list[Mention]) -> dict:
    body: list[dict] = [{"type": "TextBlock", "text": title, "weight": "Bolder", "size": "Medium", "wrap": True}]
    body += [{"type": "TextBlock", "text": line, "wrap": True} for line in lines]
    content: dict = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": body,
        "msteams": {
            "width": "Full",
            "entities": [
                {"type": "mention", "text": m.tag, "mentioned": {"id": m.email, "name": m.name}} for m in mentions
            ],
        },
    }
    if link:
        content["actions"] = [{"type": "Action.OpenUrl", "title": link[0], "url": link[1]}]
    return {
        "type": "message",
        "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": content}],
    }


class Notifier:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self._url = settings.teams_webhook_url
        self._transport = transport
        self.sent: list[dict] = []  # kept for tests / debugging

    @property
    def enabled(self) -> bool:
        return bool(self._url)

    async def post(
        self, title: str, lines: list[str], link: tuple[str, str] | None = None, mentions: list[Mention] | None = None
    ) -> bool:
        payload = build_card(title, lines, link, mentions or [])
        self.sent.append(payload)
        if not self._url:
            log.info("Teams webhook not configured; skipped: %s", title)
            return False
        try:
            async with httpx.AsyncClient(timeout=15, transport=self._transport) as c:
                resp = await c.post(self._url, json=payload)
            if resp.status_code >= 400:
                log.warning("Teams webhook returned %s: %s", resp.status_code, resp.text[:300])
                return False
            return True
        except httpx.RequestError:
            log.exception("Teams webhook failed")
            return False


def mention_for(email: str, display_name: str | None = None) -> Mention:
    return Mention(email=email, name=display_name or email.split("@")[0])
