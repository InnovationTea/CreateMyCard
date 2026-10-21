# -*- coding: utf-8 -*-
import json

import httpx
import pytest
from openai import AsyncOpenAI
from openai.resources.chat.completions import AsyncCompletions

from config.config import Settings
from custom.deepseek_official_http_transport import DeepSeekOfficialHttpTransport
from custom.model_transport import ModelTransportError
from custom.official_http_client import OfficialHttpCompletion, OfficialHttpToolCall
from models.generation import ModelRequestContext
from services.multi_step_generation.core import model_adapter
from services.multi_step_generation.core.model_adapter import PlatformChatClient


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "deepseek_official_http_url": "https://api.deepseek.com/chat/completions",
        "deepseek_official_http_api_key": "test-key",
        "deepseek_official_http_model": "deepseek-flash",
        "deepseek_official_http_temperature": 0.7,
        "deepseek_official_http_top_p": 0.9,
        "deepseek_official_http_max_tokens": 8192,
        "deepseek_official_http_enable_thinking": False,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.asyncio
@pytest.mark.parametrize("use_sdk", [True, False])
async def test_official_http_builds_non_streaming_request_without_legacy_fields(
    use_sdk, monkeypatch
):
    captured: dict[str, object] = {}
    original_create = AsyncCompletions.create

    async def capture_create(client, **kwargs):
        captured["sdk_parameters"] = kwargs
        return await original_create(client, **kwargs)

    monkeypatch.setattr(AsyncCompletions, "create", capture_create)

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "createSurface(...)"}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 4},
            },
        )

    transport = DeepSeekOfficialHttpTransport(
        _settings(deepseek_official_http_use_sdk=use_sdk),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    messages = [{"role": "user", "content": "make a card"}]

    result = await transport.generate(messages)

    body = captured["body"]
    assert result == "createSurface(...)"
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["headers"]["authorization"] == "Bearer test-key"
    assert body["messages"] == messages
    assert body["stream"] is False
    assert body["thinking"] == {"type": "disabled"}
    assert "top_k" not in body
    assert "requestId" not in body
    assert "stream_options" not in body
    if use_sdk:
        assert isinstance(transport._sdk_client, AsyncOpenAI)
        assert transport._sdk_client.max_retries == 0
        assert str(transport._sdk_client.base_url) == "https://api.deepseek.com/"
        parameters = captured.get("sdk_parameters")
        assert isinstance(parameters, dict)
        assert parameters.get("extra_body") == {"thinking": {"type": "disabled"}}
        assert "thinking" not in parameters
        assert parameters.get("messages") == messages
    else:
        assert transport._sdk_client is None
        assert "sdk_parameters" not in captured


@pytest.mark.asyncio
@pytest.mark.parametrize("use_sdk", [True, False])
async def test_official_http_supports_text_parts_and_thinking_mode(use_sdk):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"type": "text", "text": "one"},
                                {"type": "reasoning", "text": "private"},
                                {"type": "text", "text": "two"},
                            ],
                            "reasoning_content": "private reasoning",
                        }
                    }
                ]
            },
        )

    transport = DeepSeekOfficialHttpTransport(
        _settings(
            deepseek_official_http_enable_thinking=True,
            deepseek_official_http_use_sdk=use_sdk,
        ),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    result = await transport.generate([])

    assert result == "onetwo"


@pytest.mark.asyncio
@pytest.mark.parametrize("use_sdk", [True, False])
@pytest.mark.parametrize(
    ("response", "code"),
    [
        (httpx.Response(503), "MODEL_HTTP_STATUS"),
        (httpx.Response(200, json={"choices": []}), "MODEL_EMPTY_OUTPUT"),
        (httpx.Response(200, content=b"not-json"), "MODEL_RESPONSE_INVALID"),
    ],
)
async def test_official_http_maps_remote_failures(response: httpx.Response, code: str, use_sdk):
    request_count = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return response

    transport = DeepSeekOfficialHttpTransport(
        _settings(deepseek_official_http_use_sdk=use_sdk),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(ModelTransportError) as error_info:
        await transport.generate([])

    assert error_info.value.code == code
    assert request_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("use_sdk", [True, False])
@pytest.mark.parametrize("failure", [httpx.ReadTimeout, httpx.ConnectError])
async def test_official_http_maps_timeout_without_leaking_request_details(use_sdk, failure):
    def handler(_request: httpx.Request) -> httpx.Response:
        raise failure("secret prompt should not be logged")

    transport = DeepSeekOfficialHttpTransport(
        _settings(deepseek_official_http_use_sdk=use_sdk),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(ModelTransportError) as error_info:
        await transport.generate([{"role": "user", "content": "secret prompt"}])

    expected = "MODEL_HTTP_TIMEOUT" if failure is httpx.ReadTimeout else "MODEL_HTTP_REQUEST_ERROR"
    assert error_info.value.code == expected
    assert "secret prompt" not in str(error_info.value)


def test_official_http_sdk_defaults_on_and_supports_environment_override(monkeypatch):
    monkeypatch.delenv("WIDGET_SERVICE_DEEPSEEK_OFFICIAL_HTTP_USE_SDK", raising=False)
    assert _settings().deepseek_official_http_use_sdk is True
    monkeypatch.setenv("WIDGET_SERVICE_DEEPSEEK_OFFICIAL_HTTP_USE_SDK", "false")
    assert _settings().deepseek_official_http_use_sdk is False


@pytest.mark.asyncio
@pytest.mark.parametrize("owns_client", [True, False])
@pytest.mark.parametrize("use_sdk", [True, False])
async def test_official_http_sdk_keeps_exact_endpoint_metrics_and_client_lifecycle(
    owns_client,
    use_sdk,
    monkeypatch,
):
    endpoint = "https://model.test/proxy/v1/chat/completions?api-version=test"
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == endpoint
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "result"}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
            },
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    trace_events: list[dict[str, object]] = []
    monkeypatch.setattr(
        "custom.deepseek_official_http_transport.trace_record",
        lambda _name, **kwargs: trace_events.append(kwargs),
    )
    settings = _settings(
        deepseek_official_http_url=endpoint,
        deepseek_official_http_use_sdk=use_sdk,
    )
    transport = DeepSeekOfficialHttpTransport(
        settings,
        http_client=None if owns_client else http_client,
    )
    if owns_client:
        await transport.http_client.aclose()
        transport.http_client = http_client
    assert await transport.generate([]) == "result"
    sdk_client = transport._sdk_client
    assert await transport.generate([]) == "result"
    assert transport._sdk_client is sdk_client
    assert captured.get("payload") == transport._build_payload([])
    assert trace_events[0].get("metrics") == {
        "inputTokens": 3,
        "completionTokens": 4,
        "totalTokens": 7,
        "outputChars": 6,
    }
    await transport.aclose()
    assert http_client.is_closed is owns_client
    await http_client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("use_sdk", [True, False])
async def test_nonstandard_endpoint_requires_legacy_http_mode(use_sdk):
    endpoint = "https://model.test/custom/completion"
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        assert str(request.url) == endpoint
        return httpx.Response(200, json={"choices": [{"message": {"content": "result"}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        transport = DeepSeekOfficialHttpTransport(
            _settings(deepseek_official_http_url=endpoint, deepseek_official_http_use_sdk=use_sdk),
            http_client=client,
        )
        if use_sdk:
            with pytest.raises(
                ModelTransportError, match="must end with /chat/completions"
            ) as error:
                await transport.generate([])
            assert error.value.code == "MODEL_CONFIG_INVALID"
            assert request_count == 0
        else:
            assert await transport.generate([]) == "result"
            assert request_count == 1


@pytest.mark.asyncio
async def test_platform_chat_client_reuses_official_http_api_key_for_tool_calls(monkeypatch):
    settings = _settings(
        openai_master_client="deepseek_official_http",
        model_queue_timeout_seconds=1.0,
        model_request_timeout_seconds=1.0,
    )
    captured: dict[str, object] = {}

    async def fake_request_official_http(**kwargs):
        captured.update(kwargs)
        return OfficialHttpCompletion(
            tool_calls=(
                OfficialHttpToolCall(
                    id="call-1",
                    name="load_skill",
                    arguments='{"resourceId":"instructions"}',
                ),
            ),
            finish_reason="tool_calls",
        )

    monkeypatch.setattr(model_adapter, "request_official_http", fake_request_official_http)
    client = PlatformChatClient(
        settings,
        ModelRequestContext(
            session_id="s1",
            interaction_id="i1",
            device_id="d1",
            country_code="CN",
            app_version="1.0",
            app_name="debug",
        ),
        thinking_mode="disable",
        request_timeout=1.0,
    )

    completion = await client.complete(
        [{"role": "user", "content": "create a card"}],
        tools=[{"type": "function", "function": {"name": "load_skill"}}],
        tool_choice="auto",
        max_tokens=128,
        enable_thinking=False,
    )

    assert completion.tool_calls[0].name == "load_skill"
    assert captured["api_key"] == "test-key"
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["thinking_enabled"] is False
