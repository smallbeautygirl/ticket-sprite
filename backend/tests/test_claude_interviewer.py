"""ClaudeInterviewer against a mocked Messages API: tool loop, request shape, parsing."""

from __future__ import annotations

import json

import anthropic
import httpx2
import pytest

from ticket_sprite.engine.llm import ClaudeInterviewer, EngineError, InterviewContext
from ticket_sprite.engine.templates import TEMPLATES
from ticket_sprite.knowledge import Depth, KnowledgeSource


def _message(content, stop_reason, **extra):
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5-5",
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 10},
        **extra,
    }


ROUND_JSON = {
    "done": False,
    "summary": "理解中",
    "questions": [
        {
            "kind": "question", "title": "過濾", "body": "你說的過濾是 Exclusion Area 嗎？",
            "options": ["Exclusion Area", "Intake Drop"], "recommendation": "Exclusion Area",
            "rationale": "CONTEXT.md", "ai_note": "CONTEXT.md:2", "core": True, "followup_of": None,
        }
    ],
    "new_terms": [{"term": "過濾", "meaning": "排除區域", "conflict": "Exclusion Area"}],
}


def _client(responses: list[dict], seen: list[dict]) -> anthropic.AsyncAnthropic:
    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(json.loads(request.content))
        return httpx2.Response(200, json=responses[len(seen) - 1])

    return anthropic.AsyncAnthropic(
        api_key="test",
        max_retries=0,
        http_client=anthropic.DefaultAsyncHttpxClient(transport=httpx2.MockTransport(handler)),
    )


def _ctx() -> InterviewContext:
    return InterviewContext(
        template=TEMPLATES["grill_product"], role="pm", request_type="feature",
        requester="v@x.com", request_text="想要過濾某些區域的事件",
    )


async def test_tool_loop_and_request_shape(settings):
    seen: list[dict] = []
    responses = [
        _message([{"type": "tool_use", "id": "tu_1", "name": "grep", "input": {"pattern": "Exclusion"}}], "tool_use"),
        _message([{"type": "text", "text": json.dumps(ROUND_JSON, ensure_ascii=False)}], "end_turn"),
    ]
    interviewer = ClaudeInterviewer(settings, _client(responses, seen))
    ks = KnowledgeSource(root=settings.product_root, depth=Depth.DOCS)

    result = await interviewer.next_round(_ctx(), ks)

    assert result.questions[0].recommendation == "Exclusion Area"
    assert result.new_terms[0]["conflict"] == "Exclusion Area"
    first, second = seen
    assert first["model"] == "claude-opus-5-5"
    assert first["thinking"] == {"type": "adaptive"}
    assert first["fallbacks"] == "default"
    assert first["output_config"]["format"]["type"] == "json_schema"
    assert {t["name"] for t in first["tools"]} == {"list_files", "grep", "read_file"}
    assert "the console's screens (app/ui_static); other code is not visible" in first["system"]
    # Append-only: the second request replays the first assistant turn and adds the tool result
    assert second["messages"][1]["role"] == "assistant"
    tool_result = second["messages"][2]["content"][0]
    assert tool_result["type"] == "tool_result" and "CONTEXT.md:2:" in tool_result["content"]


async def test_refusal_becomes_engine_error(settings):
    seen: list[dict] = []
    responses = [
        _message([], "refusal", stop_details={"type": "refusal", "category": "cyber", "explanation": None}),
    ]
    interviewer = ClaudeInterviewer(settings, _client(responses, seen))
    with pytest.raises(EngineError, match="拒絕"):
        await interviewer.next_round(_ctx(), KnowledgeSource(root=settings.product_root, depth=Depth.DOCS))
