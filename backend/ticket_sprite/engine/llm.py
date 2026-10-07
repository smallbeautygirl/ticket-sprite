"""The interviewer: Claude with read-only Knowledge Source tools and structured output.

Each call is a fresh, append-only conversation built from the Interview's saved
state, so nothing is ever edited in a history that carries thinking blocks.
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import anthropic

from ..config import Settings
from ..knowledge import TOOL_DEFS, KnowledgeError, KnowledgeSource
from .progress import EngineProgress
from .schema import ROUND_SCHEMA, SPEC_SCHEMA, DraftQuestion, RoundResult, SpecResult
from ..models import Role
from .templates import AUDIENCE_NOTE, InterviewTemplate

log = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 30
TEXT_ATTACHMENT_LIMIT = 100_000
IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
TEXT_SUFFIXES = {".txt", ".log", ".md", ".csv", ".json", ".yaml", ".yml", ".xml", ".py", ".sql"}


class EngineError(Exception):
    pass


@dataclass
class AttachmentInput:
    filename: str
    content_type: str
    path: Path


@dataclass
class QAItem:
    ref: str  # e.g. "R2.1"
    kind: str
    title: str
    body: str
    options: list[str]
    status: str
    answer_text: str | None
    respondent: str
    recommendation: str | None


@dataclass
class InterviewContext:
    template: InterviewTemplate
    role: str
    request_type: str
    requester: str
    request_text: str
    attachments: list[AttachmentInput] = field(default_factory=list)
    history: list[QAItem] = field(default_factory=list)
    round: int = 0
    summary: str | None = None
    question_budget: int | None = None
    audience: str = "rd"

    @property
    def asked(self) -> int:
        return sum(1 for q in self.history if q.status != "withdrawn")


class InterviewLLM(Protocol):
    async def next_round(
        self, ctx: InterviewContext, knowledge: KnowledgeSource, progress: EngineProgress | None = None
    ) -> RoundResult: ...

    async def write_spec(
        self, ctx: InterviewContext, knowledge: KnowledgeSource, progress: EngineProgress | None = None
    ) -> SpecResult: ...


# ---------------------------------------------------------------- prompts

SYSTEM_PROMPT = """\
You are 開票小精靈 (Ticket Sprite), an interviewer that turns a raw Request from a PM, FAE or RD \
into a Spec that RD can build from. You grill the Respondent relentlessly but efficiently until \
there is a shared understanding, the way the grill-with-docs method does:

- Map the Request as a design tree: every decision branches into the decisions that hang off it.
- Work in rounds. Each round asks the whole *frontier*: every open decision whose prerequisites are \
already settled. Never ask a question whose answer depends on another question still open in the \
same round; it belongs to a later round. Number of questions per round: usually 2-6.
- Give every question a recommended answer and a short rationale, unless the question will be \
answered by someone other than the Requester (then recommendation is null) or it is a premise.
- Finding facts is your job, never the Respondent's. Before asking, look things up in the \
Knowledge Source with the tools (glossary CONTEXT.md, docs/adr, specs, and code when allowed). \
Do not ask what you can look up; instead state what you found and ask for the decision.
- Challenge language against the glossary: when the Requester uses a term that conflicts with \
CONTEXT.md, or a vague term, propose the precise canonical term. Record such terms in new_terms.
- Stress-test with concrete edge-case scenarios.
- Answers marked 不知道 become Open Questions; do not re-ask them, but you may ask a narrower \
question if it unblocks other branches. Answers marked 跳過 mean the recommended answer was \
adopted as an Assumption.
- Set done=true (and ask no questions) when every branch has been visited.

Write everything the humans read in 繁體中文; keep product terms and identifiers in English.

Knowledge Source access for this interview: {depth_note}
"""

DEPTH_NOTE = {
    "docs": "documents only (CONTEXT.md, README, docs/**). Code files are not visible.",
    "code": "full repository of the product, including code.",
}

STATUS_LABEL = {
    "pending": "（尚未回答）",
    "answered": "回答",
    "unknown": "不知道 → Open Question",
    "skipped": "跳過 → 採用推薦答案為 Assumption",
    "confirmed": "Premise 正確",
    "corrected": "Premise 不正確，更正為",
    "withdrawn": "（已撤回，忽略）",
}


def render_history(ctx: InterviewContext) -> str:
    if not ctx.history:
        return "(no questions asked yet)"
    lines = []
    for q in ctx.history:
        if q.status == "withdrawn":
            continue
        kind = "Premise" if q.kind == "premise" else "Q"
        lines.append(f"[{q.ref}] {kind} — {q.title}\n{q.body}")
        if q.options:
            lines.append("Options: " + " | ".join(q.options))
        if q.recommendation:
            lines.append(f"Recommended: {q.recommendation}")
        label = STATUS_LABEL.get(q.status, q.status)
        answer = f"{label}：{q.answer_text}" if q.answer_text else label
        lines.append(f"Respondent {q.respondent} → {answer}\n")
    return "\n".join(lines)


def _attachment_blocks(attachments: list[AttachmentInput]) -> list[dict]:
    blocks: list[dict] = []
    for a in attachments:
        try:
            data = a.path.read_bytes()
        except OSError:
            continue
        if a.content_type in IMAGE_TYPES:
            blocks.append({"type": "text", "text": f"Attachment: {a.filename}"})
            blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": a.content_type,
                        "data": base64.standard_b64encode(data).decode(),
                    },
                }
            )
        elif a.content_type == "application/pdf":
            blocks.append(
                {
                    "type": "document",
                    "title": a.filename,
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": base64.standard_b64encode(data).decode(),
                    },
                }
            )
        elif a.content_type.startswith("text/") or Path(a.filename).suffix.lower() in TEXT_SUFFIXES:
            text = data.decode("utf-8", errors="ignore")
            if len(text) > TEXT_ATTACHMENT_LIMIT:
                text = text[:TEXT_ATTACHMENT_LIMIT] + "\n…(truncated)"
            blocks.append({"type": "text", "text": f"<attachment name=\"{a.filename}\">\n{text}\n</attachment>"})
        else:
            blocks.append({"type": "text", "text": f"Attachment {a.filename} ({a.content_type}) cannot be read."})
    return blocks


def _context_text(ctx: InterviewContext) -> str:
    return (
        f"Interview Template: {ctx.template.id} — {ctx.template.focus}\n\n"
        f"Role: {ctx.role}  Request Type: {ctx.request_type}  Requester: {ctx.requester}\n"
        f"Audience: the Spec is for {AUDIENCE_NOTE[Role(ctx.audience)]} Ask what that reader needs "
        "and write the Spec for them.\n\n"
        f"<request>\n{ctx.request_text}\n</request>\n\n"
        f"Current understanding: {ctx.summary or '(none yet)'}\n\n"
        f"<interview_so_far>\n{render_history(ctx)}\n</interview_so_far>"
    )


def round_prompt(ctx: InterviewContext) -> str:
    if ctx.template.clarify and ctx.round == 0:
        task = (
            "This is the first round of a clarify interview. Parse the Requester's text into premises "
            "(kind=premise, recommendation=null) and questions, verify every premise against the "
            "Knowledge Source (evidence in ai_note), add missing questions, and rewrite them so the "
            "intended Respondent can answer. Order premises first."
        )
    else:
        task = (
            f"Produce round {ctx.round + 1}: the current frontier of open decisions, or done=true if "
            "nothing is left. Do not repeat questions already asked. When a question extends an earlier "
            "answer, set followup_of to that question's ref."
        )
    if ctx.question_budget is not None:
        left = max(0, ctx.question_budget - ctx.asked)
        task += (
            f"\n\nQuestion budget: the Requester chose at most {ctx.question_budget} questions for the whole "
            f"interview; {ctx.asked} asked so far, so at most {left} more (premises count). Spend them on the "
            "decisions RD cannot build without, core first; leave lesser branches unasked and do not merge "
            "several decisions into one question to save budget. If none are left, set done=true."
        )
    return f"{_context_text(ctx)}\n\n{task}\nRespond with the JSON object only."


# PM and FAE hand RD a request, not a design: RD reads the code and decides how
BRIEF_SPEC_RULE = (
    "This Spec is the Requester's request to RD, not a design document. Keep it to about one page (roughly "
    "600 字). Write in product language: no file paths, line numbers, endpoints, SQL, tables, functions or "
    "config names; RD will work those out. Do use the terms defined in CONTEXT.md and the ADRs (e.g. "
    "Location, Exclusion Area, Ensemble Gate): they are the language PM, FAE and RD share, so name things "
    "by them rather than paraphrasing. Skip the 相關模組／懷疑的模組 section. At most 5 acceptance "
    "criteria, each a behaviour a user can see; at most 5 Assumptions and only the Open Questions that need "
    "a decision. Leave out sections that would be empty. "
)


def _budget_rule(budget: int | None) -> str:
    if budget is None:
        return ""
    if budget == 0:
        return (
            "The Requester chose to skip the interview, so nothing was asked. Look the Request up in the "
            "Knowledge Source with the tools and fill in what the documents settle. Every decision you had to "
            "make yourself goes under Assumptions with a one-line reason (marked 未經確認); anything without a "
            "safe default goes under Open Questions. Keep the Spec as short as the Request warrants. "
        )
    return (
        "The Requester capped the number of questions, so some decisions were never asked: list each "
        "important one under Assumptions with your recommended answer (marked 未經確認), or under Open "
        "Questions when there is no safe default. "
    )


def spec_prompt(ctx: InterviewContext) -> str:
    return (
        f"{_context_text(ctx)}\n\n"
        "The interview is finished. Write the Spec in 繁體中文 following this outline exactly:\n"
        f"{ctx.template.spec_outline}\n\n"
        "Rules: Answers go into the body. 不知道 items go under Open Questions. 跳過 items go under "
        "Assumptions, marked 未經確認. Pending (unanswered) questions also go under Open Questions. "
        "When someone other than the Requester answered, note it, e.g.「（由 kevin@… 回答）」. "
        "Related modules stay at module or file level and you may check them with the tools. "
        + _budget_rule(ctx.question_budget)
        + (BRIEF_SPEC_RULE if ctx.role in ("pm", "fae") else "")
        + "Suggest priority by urgency: 1 = must be done now (blocks a release, customer already hurt, contractual "
        "date); 2 = this or next sprint; 3 = normal backlog; 4 = nice to have. For bugs also suggest severity by "
        "impact: 1 - Critical (outage, data loss, no workaround), 2 - High (major feature broken, painful "
        "workaround), 3 - Medium (partial, workaround exists), 4 - Low (cosmetic); otherwise severity 'none'."
        "\nRespond with the JSON object only."
    )


# ---------------------------------------------------------------- Claude


class ClaudeInterviewer:
    def __init__(self, settings: Settings, client: anthropic.AsyncAnthropic | None = None):
        self._s = settings
        self._client = client or anthropic.AsyncAnthropic()

    async def next_round(
        self, ctx: InterviewContext, knowledge: KnowledgeSource, progress: EngineProgress | None = None
    ) -> RoundResult:
        data = await self._run(ctx, knowledge, round_prompt(ctx), ROUND_SCHEMA, progress)
        return RoundResult.from_json(data)

    async def write_spec(
        self, ctx: InterviewContext, knowledge: KnowledgeSource, progress: EngineProgress | None = None
    ) -> SpecResult:
        data = await self._run(ctx, knowledge, spec_prompt(ctx), SPEC_SCHEMA, progress)
        return SpecResult.from_json(data)

    async def _run(
        self,
        ctx: InterviewContext,
        knowledge: KnowledgeSource,
        prompt: str,
        schema: dict,
        progress: EngineProgress | None,
    ) -> dict:
        system = SYSTEM_PROMPT.format(depth_note=DEPTH_NOTE[knowledge.depth.value])
        messages: list[dict] = [
            {"role": "user", "content": [*_attachment_blocks(ctx.attachments), {"type": "text", "text": prompt}]}
        ]
        for _ in range(MAX_TOOL_ITERATIONS):
            try:
                response = await self._client.beta.messages.create(
                    model=self._s.anthropic_model,
                    max_tokens=16000,
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks="default",
                    thinking={"type": "adaptive"},
                    output_config={
                        "effort": self._s.anthropic_effort,
                        "format": {"type": "json_schema", "schema": schema},
                    },
                    cache_control={"type": "ephemeral"},
                    system=system,
                    tools=TOOL_DEFS,
                    messages=messages,
                )
            except anthropic.RateLimitError as exc:
                raise EngineError("Claude API 流量限制，請稍後再試") from exc
            except anthropic.APIStatusError as exc:
                raise EngineError(f"Claude API 錯誤 {exc.status_code}: {exc.message}") from exc
            except anthropic.APIConnectionError as exc:
                raise EngineError("無法連線到 Claude API") from exc

            if response.stop_reason == "refusal":
                category = response.stop_details.category if response.stop_details else None
                raise EngineError(f"Claude 拒絕回應（{category}）")
            if response.stop_reason == "max_tokens":
                raise EngineError("Claude 回應過長被截斷")

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "pause_turn":
                continue
            if response.stop_reason == "tool_use":
                messages.append({"role": "user", "content": self._run_tools(response.content, knowledge, progress)})
                continue

            text = "".join(b.text for b in response.content if b.type == "text")
            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:
                raise EngineError("Claude 回傳的 JSON 無法解析") from exc
        raise EngineError("查閱 Knowledge Source 次數過多，未能完成")

    @staticmethod
    def _run_tools(content, knowledge: KnowledgeSource, progress: EngineProgress | None) -> list[dict]:
        results = []
        for block in content:
            if block.type != "tool_use":
                continue
            if progress is not None:
                if block.name == "read_file":
                    progress.read(str(block.input.get("path", "")))
                else:
                    progress.search()
            try:
                out = knowledge.call(block.name, dict(block.input))
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": out})
            except (KnowledgeError, KeyError, ValueError, TypeError) as exc:
                results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": f"Error: {exc}", "is_error": True}
                )
        return results


# ---------------------------------------------------------------- fake (tests / offline demo)


class FakeInterviewer:
    """Deterministic interviewer: two rounds, then done. Clarify round 1 echoes premises."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, InterviewContext]] = []

    async def next_round(
        self, ctx: InterviewContext, knowledge: KnowledgeSource, progress: EngineProgress | None = None
    ) -> RoundResult:
        self.calls.append(("round", ctx))
        if progress is not None:
            progress.read("CONTEXT.md")
        if ctx.template.clarify and ctx.round == 0:
            return RoundResult(
                done=False,
                summary="RD 想釐清功能定位",
                questions=[
                    DraftQuestion(
                        kind="premise", title="標注儲存位置", body="標注存在 middleware 自己的資料表",
                        ai_note="已在程式碼中確認", core=True,
                    ),
                    DraftQuestion(
                        kind="question", title="需求來源", body="當初是誰提的、想解決什麼問題？",
                        options=["客戶要求", "內部 QA", "對齊 EvHistory"], core=True,
                    ),
                ],
                new_terms=[],
            )
        if ctx.round >= 2:
            return RoundResult(done=True, summary="已問完", questions=[], new_terms=[])
        followup = next((q.ref for q in ctx.history if q.status == "answered"), None)
        return RoundResult(
            done=False,
            summary=f"第 {ctx.round + 1} 輪",
            questions=[
                DraftQuestion(
                    kind="question", title=f"問題 {ctx.round + 1}-1", body="這個需求的使用者是誰？",
                    options=["PM", "標注員"], recommendation="標注員", rationale="依 Request 推測", core=True,
                    followup_of=followup if ctx.round >= 1 else None,
                ),
                DraftQuestion(
                    kind="question", title=f"問題 {ctx.round + 1}-2", body="驗收條件是什麼？",
                    recommendation="能在列表上看到標注", rationale="最小可驗收",
                ),
            ],
            new_terms=[{"term": "標注", "meaning": "人工判定 VLM 答案", "conflict": None}],
        )

    async def write_spec(
        self, ctx: InterviewContext, knowledge: KnowledgeSource, progress: EngineProgress | None = None
    ) -> SpecResult:
        self.calls.append(("spec", ctx))
        body = render_history(ctx)
        return SpecResult(
            title="測試 Spec",
            markdown=f"## 背景\n{ctx.request_text}\n\n## 問答\n{body}",
            priority=2,
            severity="3 - Medium" if ctx.request_type == "bug" else None,
            new_terms=[],
        )
