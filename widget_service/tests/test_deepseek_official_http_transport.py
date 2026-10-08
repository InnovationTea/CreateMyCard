# -*- coding: utf-8 -*-
import json

import httpx
import pytest
from debug_tools.end_to_end_debug.backend.debug_agent.agent import DebugAgentSession

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
async def test_official_http_builds_non_streaming_request_without_legacy_fields():
    captured: dict[str, object] = {}

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
        _settings(),
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


@pytest.mark.asyncio
async def test_official_http_supports_text_parts_and_thinking_mode():
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
        _settings(deepseek_official_http_enable_thinking=True),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    result = await transport.generate([])

    assert result == "onetwo"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "code"),
    [
        (httpx.Response(503), "MODEL_HTTP_STATUS"),
        (httpx.Response(200, json={"choices": []}), "MODEL_EMPTY_OUTPUT"),
        (httpx.Response(200, content=b"not-json"), "MODEL_RESPONSE_INVALID"),
    ],
)
async def test_official_http_maps_remote_failures(response: httpx.Response, code: str):
    def handler(_request: httpx.Request) -> httpx.Response:
        return response

    transport = DeepSeekOfficialHttpTransport(
        _settings(),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(ModelTransportError) as error_info:
        await transport.generate([])

    assert error_info.value.code == code


@pytest.mark.asyncio
async def test_official_http_maps_timeout_without_leaking_request_details():
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("secret prompt should not be logged")

    transport = DeepSeekOfficialHttpTransport(
        _settings(),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(ModelTransportError) as error_info:
        await transport.generate([{"role": "user", "content": "secret prompt"}])

    assert error_info.value.code == "MODEL_HTTP_TIMEOUT"


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


def test_debug_agent_prefers_official_http_when_api_key_is_configured():
    debug_settings = type("DebugSettingsStub", (), {"request_timeout_seconds": 1.0})()
    session = object.__new__(DebugAgentSession)
    session.debug_settings = debug_settings
    settings = _settings(
        openai_master_client="llmclient",
        deepseek_official_http_enable_thinking=True,
    )

    client = session._default_model_client(None, settings)

    assert isinstance(client, PlatformChatClient)
    assert client.thinking_mode == "high"
