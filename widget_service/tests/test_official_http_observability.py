"""真实 HTTP 适配链的 thinking 透传、结束原因和用量可观测性。"""

import json
from types import SimpleNamespace

import httpx
import pytest

from custom import model_runtime, official_http_client
from custom.model_transport import ModelTransportError


@pytest.mark.parametrize("thinking", [False, True])
@pytest.mark.parametrize(
    ("content", "reason", "status"),
    [
        ("answer", "stop", "completed"),
        ("", "stop", "empty"),
        ("partial", "length", "truncated"),
        ("", "length", "truncated"),
    ],
)
def test_runtime_http_payload_and_completion_metadata(
    monkeypatch, thinking, content, reason, status
):
    payloads = []
    events = []
    logs = []

    def respond(request):
        payloads.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"content": content, "reasoning_content": "private-thought"},
                        "finish_reason": reason,
                    }
                ],
                "usage": {
                    "prompt_tokens": 30,
                    "completion_tokens": 12,
                    "total_tokens": 42,
                    "completion_tokens_details": {"reasoning_tokens": 7},
                },
            },
        )

    async_client = httpx.AsyncClient
    monkeypatch.setattr(
        official_http_client.httpx,
        "AsyncClient",
        lambda **kwargs: async_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    monkeypatch.setattr(
        model_runtime,
        "get_settings",
        lambda: SimpleNamespace(deepseek_http_url="https://model.test/chat/completions"),
    )
    monkeypatch.setattr(
        model_runtime,
        "LLMClientOptions",
        lambda: SimpleNamespace(
            api_key="secret-key",
            model="test",
            user="",
            temperature=0.7,
            top_p=0.9,
            max_tokens=10000,
            stop=None,
            enable_thinking=thinking,
            recv_timeout=10,
        ),
    )
    monkeypatch.setattr(
        official_http_client, "trace_record", lambda *args, **kwargs: events.append(kwargs)
    )
    monkeypatch.setattr(official_http_client.logger, "info", logs.append)
    if reason == "length":
        with pytest.raises(ModelTransportError) as error:
            model_runtime._generate_with_llmclient([])
        assert error.value.code == "MODEL_OUTPUT_TRUNCATED"
    else:
        assert model_runtime._generate_with_llmclient([]) == content
    assert len(payloads) == 1
    assert payloads[0].get("thinking") == {"type": "enabled" if thinking else "disabled"}
    assert payloads[0].get("max_tokens") == 8192
    assert len(events) == 1
    event = events[0]
    assert event.get("status") == status
    assert event.get("details") == {
        "finishReason": reason,
        "thinkingEnabled": thinking,
        "maxOutputTokens": 8192,
    }
    assert event.get("metrics") == {
        "inputTokens": 30,
        "completionTokens": 12,
        "totalTokens": 42,
        "reasoningTokens": 7,
        "promptCacheHitTokens": None,
        "promptCacheMissTokens": None,
        "outputChars": len(content),
        "reasoningChars": 15,
    }
    log_text = "\n".join(logs)
    assert "finishReason" in log_text
    assert "completionTokens" in log_text
    assert "private-thought" not in log_text
    assert "secret-key" not in log_text


@pytest.mark.parametrize("usage", [None, {}, {"prompt_tokens": True, "completion_tokens": "12"}])
def test_missing_or_invalid_usage_remains_unknown(monkeypatch, usage):
    events = []
    monkeypatch.setattr(
        official_http_client, "trace_record", lambda *args, **kwargs: events.append(kwargs)
    )
    official_http_client._record_completion(
        official_http_client.OfficialHttpCompletion(content="ok", usage=usage),
        thinking_enabled=None,
        max_tokens=8192,
    )
    metrics = events[0].get("metrics")
    assert metrics is not None
    for key in ("inputTokens", "completionTokens", "reasoningTokens", "totalTokens"):
        assert metrics.get(key) is None


def test_tool_call_without_text_is_not_classified_as_empty(monkeypatch):
    events = []
    monkeypatch.setattr(
        official_http_client, "trace_record", lambda *args, **kwargs: events.append(kwargs)
    )
    completion = official_http_client.OfficialHttpCompletion(
        tool_calls=(official_http_client.OfficialHttpToolCall("1", "test", "{}"),),
        finish_reason="tool_calls",
    )
    official_http_client._record_completion(completion, thinking_enabled=None, max_tokens=8192)
    assert events[0].get("status") == "completed"
