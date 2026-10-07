"""Interview Templates: how an Interview asks. Defaults come from Role × Request Type."""

from __future__ import annotations

from dataclasses import dataclass

from ..knowledge import Depth
from ..models import RequestType, Role


@dataclass(frozen=True)
class InterviewTemplate:
    id: str
    label: str
    focus: str  # appended to the system prompt
    spec_outline: str
    clarify: bool = False  # first round parses the Requester's Premises and questions


_FEATURE_OUTLINE = """\
## 背景
## Customer 原話（逐字引用附件或 Request 中客戶說的話；沒有就寫「無」）
## 問題陳述
## 使用情境
## 範圍
### 要做
### 不做
## 驗收條件（每條用 Given / When / Then）
## 相關模組（只到模組或檔案層級，不寫實作方式）
## Assumptions（未經確認，逐條標示）
## Open Questions
## New Terms"""

_BUG_OUTLINE = """\
## 摘要
## 環境（Deployment Environment、版本、相關 camera / task / vendor 等）
## 重現步驟
## 預期結果
## 實際結果
## 影響範圍與嚴重度
## 懷疑的模組（只到模組或檔案層級）
## Assumptions（未經確認，逐條標示）
## Open Questions
## New Terms"""

_CLARIFY_OUTLINE = """\
## 背景
## 已確認的 Premise（逐條：原陳述 → 確認 / 糾正後的內容，標註由誰確認）
## 問答結論
## 決定事項
## 後續行動
## Assumptions（未經確認，逐條標示）
## Open Questions
## New Terms"""

TEMPLATES: dict[str, InterviewTemplate] = {
    t.id: t
    for t in [
        InterviewTemplate(
            id="grill_product",
            label="grill-with-docs（產品面）",
            focus=(
                "The Requester is a PM. Grill from the product side: who the user is, the concrete "
                "scenario, the value, what is in and out of scope, and testable acceptance criteria. "
                "Use the Knowledge Source's glossary (CONTEXT.md), ADRs and specs to catch fuzzy or "
                "conflicting terms (\"you said 'filter' — is that Intake Drop or Exclusion Area?\") and "
                "contradictions with documented decisions. Do not ask implementation questions."
            ),
            spec_outline=_FEATURE_OUTLINE,
        ),
        InterviewTemplate(
            id="grill_technical",
            label="grill-with-docs（技術面）",
            focus=(
                "The Requester is an FAE who knows the repo and Observ architecture. Grill like "
                "grill_product, but also go into the code: which flow, gate, router or job is affected, "
                "what the current behaviour actually is, and edge cases visible in the code. Verify the "
                "Requester's claims about current behaviour against the code before relying on them."
            ),
            spec_outline=_FEATURE_OUTLINE,
        ),
        InterviewTemplate(
            id="quick_bug",
            label="快速 bug 回報",
            focus=(
                "This is a bug report. Be quick: collect a one-line summary, environment, reproduction "
                "steps, expected vs actual result, and impact (who / how many / how often). Ask at most "
                "two rounds unless something essential is missing."
            ),
            spec_outline=_BUG_OUTLINE,
        ),
        InterviewTemplate(
            id="quick_bug_technical",
            label="快速 bug 回報（技術版）",
            focus=(
                "This is a bug report from someone technical. Collect summary, environment (deployment "
                "environment, version, camera/task/vendor ids), reproduction steps, expected vs actual, "
                "logs, impact, and the suspected module. Look in the code to sharpen the questions (e.g. "
                "\"does it fail before or after the Ensemble Gate?\")."
            ),
            spec_outline=_BUG_OUTLINE,
        ),
        InterviewTemplate(
            id="clarify",
            label="釐清（Premise + 問題，轉交 PM）",
            focus=(
                "The Requester (usually RD) already wrote their current understanding and the questions "
                "they want someone else (usually a PM) to answer. In the first round: split the input "
                "into Premises (statements about how things are now, to be confirmed or corrected) and "
                "questions. Verify EVERY Premise against the code and put the evidence (file:line) or the "
                "contradiction in ai_note. Add questions the Requester missed, and rewrite questions so a "
                "PM can answer them, offering options where natural. These questions will be handed off, "
                "so set recommendation to null. Later rounds: ask follow-ups only as extensions of earlier "
                "answers, and set followup_of to the question they extend."
            ),
            spec_outline=_CLARIFY_OUTLINE,
            clarify=True,
        ),
    ]
}

DEFAULT_TEMPLATE: dict[tuple[Role, RequestType], str] = {
    (Role.PM, RequestType.FEATURE): "grill_product",
    (Role.PM, RequestType.BUG): "quick_bug",
    (Role.PM, RequestType.TASK): "clarify",
    (Role.FAE, RequestType.FEATURE): "grill_technical",
    (Role.FAE, RequestType.BUG): "quick_bug_technical",
    (Role.FAE, RequestType.TASK): "clarify",
    (Role.RD, RequestType.FEATURE): "clarify",
    (Role.RD, RequestType.BUG): "quick_bug_technical",
    (Role.RD, RequestType.TASK): "clarify",
}


def default_template(role: Role, request_type: RequestType) -> str:
    return DEFAULT_TEMPLATE[(role, request_type)]


# PM and FAE hand work to RD; RD clarifies with PM
DEFAULT_AUDIENCE: dict[Role, Role] = {Role.PM: Role.RD, Role.FAE: Role.RD, Role.RD: Role.PM}

AUDIENCE_NOTE: dict[Role, str] = {
    Role.RD: "RD, who will build it: precise acceptance criteria, edge cases and the related modules; "
    "no product pitch.",
    Role.PM: "a PM, who decides product scope: product language, user impact and the decisions needed; "
    "name modules only when it matters, no code-level detail.",
    Role.FAE: "an FAE, who works with customer sites: site and deployment impact, how to verify on site, "
    "workarounds and what to tell the Customer.",
}


def depth_for(role: Role) -> Depth:
    """PM reads documents only; FAE and RD can read code (Q19)."""
    return Depth.DOCS if role is Role.PM else Depth.CODE


@dataclass(frozen=True)
class QuestionBudget:
    id: str
    label: str
    limit: int | None  # None = ask until every branch is visited


QUESTION_BUDGETS = [
    QuestionBudget("brief", "精簡", 5),
    QuestionBudget("standard", "標準", 12),
    QuestionBudget("thorough", "深入", None),
]
DEFAULT_QUESTION_BUDGET = "standard"
