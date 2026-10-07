"""What the engine returns. Mirrors the JSON schemas sent as structured output."""

from __future__ import annotations

from dataclasses import dataclass, field

_NULLABLE_STR = {"anyOf": [{"type": "string"}, {"type": "null"}]}

_TERM = {
    "type": "object",
    "properties": {
        "term": {"type": "string"},
        "meaning": {"type": "string", "description": "What the Requester means by it"},
        "conflict": {**_NULLABLE_STR, "description": "Which glossary term it collides with, if any"},
    },
    "required": ["term", "meaning", "conflict"],
    "additionalProperties": False,
}

ROUND_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "done": {"type": "boolean", "description": "True when every branch of the design tree is settled"},
        "summary": {"type": "string", "description": "Current shared understanding, 繁體中文, a few sentences"},
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["question", "premise"]},
                    "title": {"type": "string", "description": "Short title, 繁體中文"},
                    "body": {"type": "string", "description": "The question or premise statement, 繁體中文"},
                    "options": {"type": "array", "items": {"type": "string"}},
                    "recommendation": {**_NULLABLE_STR, "description": "Recommended answer; null for premises"},
                    "rationale": _NULLABLE_STR,
                    "ai_note": {
                        **_NULLABLE_STR,
                        "description": "Evidence from the Knowledge Source, e.g. premise verification with file:line",
                    },
                    "core": {"type": "boolean", "description": "Essential to the Spec"},
                    "followup_of": {
                        **_NULLABLE_STR,
                        "description": "Ref (e.g. 'R2.1') of the earlier question this one extends, else null",
                    },
                },
                "required": [
                    "kind", "title", "body", "options", "recommendation",
                    "rationale", "ai_note", "core", "followup_of",
                ],
                "additionalProperties": False,
            },
        },
        "new_terms": {"type": "array", "items": _TERM},
    },
    "required": ["done", "summary", "questions", "new_terms"],
    "additionalProperties": False,
}

SPEC_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Ticket title, 繁體中文, under 80 characters"},
        "markdown": {"type": "string", "description": "The Spec in Markdown, following the outline"},
        "priority": {"type": "integer", "enum": [1, 2, 3, 4]},
        "severity": {
            "type": "string",
            "enum": ["1 - Critical", "2 - High", "3 - Medium", "4 - Low", "none"],
            "description": "Bug severity; 'none' for non-bugs",
        },
        "new_terms": {"type": "array", "items": _TERM},
    },
    "required": ["title", "markdown", "priority", "severity", "new_terms"],
    "additionalProperties": False,
}


@dataclass
class DraftQuestion:
    kind: str
    title: str
    body: str
    options: list[str] = field(default_factory=list)
    recommendation: str | None = None
    rationale: str | None = None
    ai_note: str | None = None
    core: bool = False
    followup_of: str | None = None


@dataclass
class RoundResult:
    done: bool
    summary: str
    questions: list[DraftQuestion]
    new_terms: list[dict]

    @classmethod
    def from_json(cls, data: dict) -> RoundResult:
        return cls(
            done=bool(data["done"]),
            summary=data.get("summary", ""),
            questions=[DraftQuestion(**q) for q in data.get("questions", [])],
            new_terms=list(data.get("new_terms", [])),
        )


@dataclass
class SpecResult:
    title: str
    markdown: str
    priority: int | None
    severity: str | None
    new_terms: list[dict]

    @classmethod
    def from_json(cls, data: dict) -> SpecResult:
        return cls(
            title=data["title"],
            markdown=data["markdown"],
            priority=data.get("priority"),
            severity=None if data.get("severity") in (None, "none") else data["severity"],
            new_terms=list(data.get("new_terms", [])),
        )
