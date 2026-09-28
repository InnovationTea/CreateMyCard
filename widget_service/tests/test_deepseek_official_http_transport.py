"""官方 HTTP 空正文/截断诊断不泄露内容，也不将思考内容作为 DSL。"""

from types import SimpleNamespace

import httpx
import pytest

from custom.deepseek_official_http_transport import DeepSeekOfficialHttpTransport
from custom.model_transport import ModelTransportError


@pytest.mark.parametrize("content,reason,expected_code", [
    ("", "length", "MODEL_OUTPUT_TRUNCATED"),
    ("```genui\n[partial", "length", "MODEL_OUTPUT_TRUNCATED"),
    (None, "stop", "MODEL_EMPTY_OUTPUT"),
    (" \n", "stop", "MODEL_EMPTY_OUTPUT"),
])
@pytest.mark.asyncio
async def test_invalid_output_reports_safe_metadata(
    content, reason: str, expected_code: str, monkeypatch,
) -> None:
    records = []
    monkeypatch.setattr("custom.deepseek_official_http_transport.logger.warning", records.append)
    monkeypatch.setattr(
        "custom.deepseek_official_http_transport.report_ops_metrics", lambda **kw: None,
    )
    body = {
        "choices": [{"finish_reason": reason,
                     "message": {"content": content, "reasoning_content": "SECRET_REASONING"}}],
        "usage": {"prompt_tokens": 30, "completion_tokens": 100, "total_tokens": 130,
                  "completion_tokens_details": {"reasoning_tokens": 100}},
    }
    settings = SimpleNamespace(
        deepseek_official_http_url="https://model.test/chat/completions",
        deepseek_official_http_api_key="SECRET_API_KEY",
        deepseek_official_http_model="test-model",
        deepseek_official_http_temperature=0.7,
        deepseek_official_http_top_p=0.9,
        deepseek_official_http_max_tokens=100,
        deepseek_official_http_enable_thinking=True,
    )
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        transport = DeepSeekOfficialHttpTransport(settings, client)
        with pytest.raises(ModelTransportError) as caught:
            await transport.generate([{"role": "user", "content": "SECRET_PROMPT"}])
    assert caught.value.code == expected_code
    assert len(requests) == 1  # 不隐式重试或改变配置。
    output = "\n".join(records)
    assert expected_code in output
    assert "finish_reason" in output and reason in output
    assert "reasoning_tokens" in output and "reasoning_content_chars" in output
    for secret in ("SECRET_REASONING", "SECRET_API_KEY", "SECRET_PROMPT", "partial"):
        assert secret not in output


@pytest.mark.parametrize("content,expected", [
    ("dsl", "dsl"),
    ([{"type": "text", "text": "one"}, {"type": "image", "text": "ignore"},
      {"type": "text", "text": "two"}], "onetwo"),
])
def test_complete_response_preserves_content(content, expected: str) -> None:
    assert DeepSeekOfficialHttpTransport._extract_content({
        "choices": [{"finish_reason": "stop", "message": {"content": content}}],
    }) == expected


@pytest.mark.parametrize("body", [None, [], {}, {"choices": []}, {"choices": [None]}])
def test_malformed_response_summary_is_safe(body) -> None:
    assert isinstance(DeepSeekOfficialHttpTransport._response_summary(body), dict)
    with pytest.raises(ModelTransportError):
        DeepSeekOfficialHttpTransport._extract_content(body)


def test_metadata_whitelist_rejects_untrusted_text() -> None:
    result = DeepSeekOfficialHttpTransport._response_summary({
        "choices": [{"finish_reason": "SECRET_IN_REASON", "message": {}}],
        "usage": {"prompt_tokens": True, "completion_tokens": -1, "total_tokens": "SECRET",
                  "completion_tokens_details": {"reasoning_tokens": False}},
    })
    assert result.get("finish_reason") == "unknown"
    assert result.get("usage") == {}
    assert "SECRET" not in str(result)
