# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
# ruff: noqa: E402
import asyncio
import base64
import hashlib
import hmac
import json
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLOUD_ROOT = PROJECT_ROOT / "cloud"
APP_VERSION = ".".join(("11", "7", "5", "205"))
CLIENT_VERSION = ".".join(("12", "0", "0", "1"))
if str(CLOUD_ROOT) not in sys.path:
    sys.path.insert(0, str(CLOUD_ROOT))

from api.routes import _model_request_context_from_payload
from api.schemas import GenerateWidgetCardRequest
from config.config import Settings
from custom.deepseek_http_client import DeepSeekHttpClient
from custom.deepseek_platform_client import DeepSeekPlatformClient
from custom.model_runtime import ModelExecutionRuntime
from custom.model_transport import ModelTransportError
from custom.unified_model_client import UnifiedModelClient
from models.generation import ModelRequestContext


def _request_context() -> ModelRequestContext:
    return ModelRequestContext(
        session_id="session-001",
        interaction_id="interaction-001",
        device_id="device-001",
        country_code="CN",
        app_version=APP_VERSION,
        app_name="com.huawei.hmos.vassistant",
    )


@pytest.mark.asyncio
async def test_deepseek_http_uses_dedicated_model_settings():
    captured: dict[str, object] = {}

    async def handle_request(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["Authorization"]
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "http-result"}}]},
        )

    settings = Settings(
        _env_file=None,
        deepseek_api_key="test-key",
        deepseek_api_url="https://model.test/v1/",
        deepseek_http_model="http-model",
        deepseek_http_max_tokens=4096,
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handle_request)
    ) as http_client:
        client = DeepSeekHttpClient(settings, http_client)
        result = await client.generate([{"role": "user", "content": "hello"}])
        await client.aclose()

    assert result == "http-result"
    assert captured["url"] == "https://model.test/v1/chat/completions"
    assert captured["authorization"] == "Bearer test-key"
    assert captured["payload"] == {
        "model": "http-model",
        "messages": [{"role": "user", "content": "hello"}],
        "stream": False,
        "thinking": {"type": "disabled"},
        "temperature": 0.7,
        "top_p": 0.9,
        "max_tokens": 4096,
    }


class _FakeWebSocket:
    def __init__(self, events: list[str]) -> None:
        self.events = iter(events)
        self.sent_payload = ""
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, _exc_type, _exc, _traceback):
        self.closed = True
        return False

    async def send(self, payload: str) -> None:
        self.sent_payload = payload

    def __aiter__(self):
        return self

    async def __anext__(self) -> str:
        try:
            return next(self.events)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


@pytest.mark.asyncio
async def test_deepseek_platform_builds_signed_dynamic_request_and_closes_socket(
    monkeypatch,
):
    settings = Settings(
        _env_file=None,
        deepseek_platform_access_key="access-key",
        deepseek_platform_ws_url="ws://model.test/deepseek",
        deepseek_platform_model_name="model-test",
        deepseek_platform_api_key="business-key",
        deepseek_platform_sender="sender-test",
        deepseek_platform_receiver="receiver-test",
        deepseek_platform_message_name="message-test",
    )
    encoded_secret = base64.b64encode(b"secret-key")
    websocket = _FakeWebSocket(
        [
            json.dumps({"result": {"type": "partialText", "text": "part"}}),
            json.dumps({"result": {"type": "finalText", "text": "complete"}}),
        ]
    )
    connect_arguments: dict[str, object] = {}

    def fake_connect(url, **kwargs):
        connect_arguments["url"] = url
        connect_arguments.update(kwargs)
        return websocket

    monkeypatch.setattr(
        "custom.deepseek_platform_client.websockets.connect",
        fake_connect,
    )
    messages = [{"role": "system", "content": "system prompt"}]
    original_messages = [dict(item) for item in messages]
    client = DeepSeekPlatformClient(
        settings,
        secret_loader=lambda key: (
            encoded_secret
            if key == "genui.deepseek.platform.secret.key"
            else b""
        ),
        timestamp_provider=lambda: 1_700_000_000_123,
    )

    result = await client.generate(messages, _request_context())

    digest = hmac.new(
        b"secret-key",
        b"access-key1700000000123",
        hashlib.sha256,
    ).digest()
    expected_signature = base64.b64encode(digest).decode("utf-8")
    headers = connect_arguments["additional_headers"]
    body = json.loads(websocket.sent_payload)
    assert result == "complete"
    assert websocket.closed is True
    assert messages == original_messages
    assert connect_arguments["url"] == "ws://model.test/deepseek"
    assert headers["token"] == f"access-key;1700000000123;{expected_signature};"
    assert headers["sessionId"] == "session-001"
    assert headers["interactionId"] == "interaction-001"
    assert headers["deviceId"] == "device-001"
    assert headers["locate"] == "CN"
    assert headers["appVersion"] == APP_VERSION
    assert headers["appName"] == "com.huawei.hmos.vassistant"
    assert headers["messageName"] == "message-test"
    assert headers["sender"] == "sender-test"
    assert headers["receiver"] == "receiver-test"
    assert body["session"]["sessionId"] == "session-001"
    assert body["body"]["messages"] == messages
    assert body["body"]["modelName"] == "model-test"
    assert body["body"]["apiKey"] == "business-key"


@pytest.mark.asyncio
async def test_deepseek_platform_reports_explicit_error_and_empty_completion(monkeypatch):
    settings = Settings(
        _env_file=None,
        deepseek_platform_access_key="access-key",
        deepseek_platform_ws_url="ws://model.test/deepseek",
    )
    sockets = iter(
        [
            _FakeWebSocket(
                [json.dumps({"errorCode": "429", "errorMessage": "rate limited"})]
            ),
            _FakeWebSocket(["not-json"]),
            _FakeWebSocket(
                [json.dumps({"result": {"type": "finalText", "text": ""}})]
            ),
        ]
    )
    monkeypatch.setattr(
        "custom.deepseek_platform_client.websockets.connect",
        lambda *_args, **_kwargs: next(sockets),
    )
    client = DeepSeekPlatformClient(
        settings,
        secret_loader=lambda _key: base64.b64encode(b"secret-key"),
    )

    with pytest.raises(ModelTransportError) as explicit_error:
        await client.generate([], _request_context())
    with pytest.raises(ModelTransportError) as incomplete_error:
        await client.generate([], _request_context())
    with pytest.raises(ModelTransportError) as empty_error:
        await client.generate([], _request_context())

    assert explicit_error.value.code == "429"
    assert "rate limited" in str(explicit_error.value)
    assert incomplete_error.value.code == "MODEL_STREAM_INCOMPLETE"
    assert empty_error.value.code == "MODEL_EMPTY_OUTPUT"


@pytest.mark.asyncio
async def test_deepseek_platform_maps_connection_failure(monkeypatch):
    settings = Settings(
        _env_file=None,
        deepseek_platform_access_key="access-key",
        deepseek_platform_ws_url="ws://model.test/deepseek",
    )

    def fail_connect(*_args, **_kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(
        "custom.deepseek_platform_client.websockets.connect",
        fail_connect,
    )
    client = DeepSeekPlatformClient(
        settings,
        secret_loader=lambda _key: base64.b64encode(b"secret-key"),
    )

    with pytest.raises(ModelTransportError, match="request failed") as error_info:
        await client.generate([], _request_context())

    assert isinstance(error_info.value.__cause__, OSError)


def test_deepseek_platform_rejects_missing_or_empty_sts_secret():
    settings = Settings(
        _env_file=None,
        deepseek_platform_access_key="access-key",
        deepseek_platform_ws_url="ws://model.test/deepseek",
    )
    missing_client = DeepSeekPlatformClient(
        settings,
        secret_loader=lambda key: (_ for _ in ()).throw(KeyError(key)),
    )
    empty_client = DeepSeekPlatformClient(
        settings,
        secret_loader=lambda _key: base64.b64encode(b""),
    )

    with pytest.raises(ModelTransportError):
        missing_client._build_token()
    with pytest.raises(ModelTransportError):
        empty_client._build_token()


class _SequenceRuntime:
    def __init__(self, outcomes: dict[str, list[object]]) -> None:
        self.outcomes = outcomes
        self.calls: list[tuple[str, ModelRequestContext | None]] = []

    async def generate_once(self, provider, _messages, request_context):
        self.calls.append((provider, request_context))
        outcome = self.outcomes[provider].pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.mark.asyncio
async def test_unified_model_client_master_success_does_not_call_fallback():
    settings = Settings(_env_file=None, enable_model_failure_retry=True)
    runtime = _SequenceRuntime({"deepseek_platform": ["master-result"]})
    client = UnifiedModelClient(settings, runtime, operation_name="compact")

    result = await client.generate(
        "openai",
        [],
        _request_context(),
        phase="initial",
    )

    assert result == "master-result"
    assert runtime.calls == [("deepseek_platform", _request_context())]
    assert client.retry_count == 0


@pytest.mark.asyncio
async def test_unified_model_client_does_not_treat_quality_candidate_as_fallback_error():
    settings = Settings(_env_file=None, enable_model_failure_retry=True)
    runtime = _SequenceRuntime({"deepseek_platform": ["invalid-design-token"]})
    client = UnifiedModelClient(settings, runtime, operation_name="compact")

    result = await client.generate(
        "openai",
        [],
        _request_context(),
        phase="initial",
    )

    assert result == "invalid-design-token"
    assert [provider for provider, _context in runtime.calls] == [
        "deepseek_platform"
    ]


@pytest.mark.asyncio
async def test_unified_model_client_retry_disabled_never_calls_fallback():
    settings = Settings(_env_file=None, enable_model_failure_retry=False)
    error = ModelTransportError("master unavailable", code="MODEL_UNAVAILABLE")
    runtime = _SequenceRuntime({"deepseek_platform": [error]})
    client = UnifiedModelClient(settings, runtime, operation_name="compact")

    with pytest.raises(ModelTransportError, match="master unavailable"):
        await client.generate(
            "openai",
            [],
            _request_context(),
            phase="initial",
        )

    assert [provider for provider, _context in runtime.calls] == ["deepseek_platform"]
    assert client.retry_count == 0


@pytest.mark.asyncio
async def test_unified_model_client_fallback_disabled_retries_only_master():
    settings = Settings(
        _env_file=None,
        enable_model_failure_retry=True,
        enable_openai_fallback=False,
        model_failure_max_retry_attempts=1,
        model_failure_retry_jitter_ratio=0.0,
    )
    failure = ModelTransportError("master unavailable", code="MODEL_UNAVAILABLE")
    runtime = _SequenceRuntime({"deepseek_platform": [failure, failure]})
    delays: list[float] = []

    async def record_sleep(delay: float) -> None:
        delays.append(delay)

    client = UnifiedModelClient(
        settings,
        runtime,
        operation_name="compact",
        sleep=record_sleep,
    )

    with pytest.raises(ModelTransportError, match="master unavailable"):
        await client.generate("openai", [], _request_context(), phase="initial")

    assert [provider for provider, _context in runtime.calls] == [
        "deepseek_platform",
        "deepseek_platform",
    ]
    assert delays == [1.0]
    assert client.retry_count == 1


@pytest.mark.asyncio
async def test_unified_model_client_exhausts_master_then_uses_fallback_retries():
    settings = Settings(
        _env_file=None,
        enable_model_failure_retry=True,
        model_failure_max_retry_attempts=2,
        fallback_model_failure_max_retry_attempts=1,
        model_failure_retry_jitter_ratio=0.0,
    )
    failure = ModelTransportError("temporarily unavailable")
    runtime = _SequenceRuntime(
        {
            "deepseek_platform": [failure, failure, failure],
            "llmclient": [failure, "fallback-result"],
        }
    )
    delays: list[float] = []

    async def record_sleep(delay: float) -> None:
        delays.append(delay)

    client = UnifiedModelClient(
        settings,
        runtime,
        operation_name="compact",
        sleep=record_sleep,
    )

    result = await client.generate(
        "openai",
        [],
        _request_context(),
        phase="repair",
    )

    assert result == "fallback-result"
    assert [provider for provider, _context in runtime.calls] == [
        "deepseek_platform",
        "deepseek_platform",
        "deepseek_platform",
        "llmclient",
        "llmclient",
    ]
    assert delays == [1.0, 2.0, 1.0]
    assert client.retry_count == 4


@pytest.mark.asyncio
async def test_unified_model_client_can_swap_master_and_fallback_and_restart_master():
    settings = Settings(
        _env_file=None,
        enable_model_failure_retry=True,
        openai_master_client="llmclient",
        openai_fallback_client="deepseek_platform",
    )
    runtime = _SequenceRuntime({"llmclient": ["invalid-token", "repaired-token"]})
    client = UnifiedModelClient(settings, runtime, operation_name="compact")

    first = await client.generate("openai", [], _request_context(), phase="initial")
    repaired = await client.generate("openai", [], _request_context(), phase="repair")

    assert first == "invalid-token"
    assert repaired == "repaired-token"
    assert [provider for provider, _context in runtime.calls] == [
        "llmclient",
        "llmclient",
    ]


def test_model_route_configuration_rejects_legacy_value_and_same_clients():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, a2ui_form_model_backend="llmclient")
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            openai_master_client="llmclient",
            openai_fallback_client="llmclient",
        )


def test_model_request_context_uses_request_fields_without_cross_request_reuse():
    request = GenerateWidgetCardRequest(
        uid="user-001",
        device={"deviceId": "request-device", "romVersion": "6.0"},
        prdVer=APP_VERSION,
        userQuery="天气卡片",
        title="天气",
        description="天气卡片",
    )
    first_payload = {
        "session": {
            "sessionId": "session-one",
            "interactionId": "interaction-one",
            "deviceId": "session-device",
            "clientVersion": CLIENT_VERSION,
            "packageName": "com.example.first",
        },
        "deviceInfo": {"countryCode": "DE", "deviceId": "device-info"},
    }

    first = _model_request_context_from_payload(first_payload, request)
    second = _model_request_context_from_payload({}, request)

    assert first == ModelRequestContext(
        session_id="session-one",
        interaction_id="interaction-one",
        device_id="session-device",
        country_code="DE",
        app_version=CLIENT_VERSION,
        app_name="com.example.first",
    )
    assert second.device_id == "request-device"
    assert second.session_id != first.session_id
    assert second.interaction_id != first.interaction_id


@pytest.mark.asyncio
async def test_all_physical_model_clients_share_one_concurrency_limit():
    settings = Settings(
        _env_file=None,
        model_max_concurrency=1,
        model_queue_timeout_seconds=1.0,
        model_request_timeout_seconds=1.0,
    )
    state_lock = threading.Lock()
    active_calls = 0
    max_active_calls = 0

    def enter_call() -> None:
        nonlocal active_calls, max_active_calls
        with state_lock:
            active_calls += 1
            max_active_calls = max(max_active_calls, active_calls)

    def leave_call() -> None:
        nonlocal active_calls
        with state_lock:
            active_calls -= 1

    class FakeMepTransport:
        @staticmethod
        async def generate(_messages):
            enter_call()
            try:
                await asyncio.sleep(0.01)
                return "mep"
            finally:
                leave_call()

        @staticmethod
        async def aclose():
            return None

    class FakeDeepSeekPlatformTransport:
        @staticmethod
        async def generate(_messages, _request_context):
            enter_call()
            try:
                await asyncio.sleep(0.01)
                return "deepseek-platform"
            finally:
                leave_call()

    class FakeDeepSeekHttpTransport:
        @staticmethod
        async def generate(_messages, _request_context):
            enter_call()
            try:
                await asyncio.sleep(0.01)
                return "deepseek-http"
            finally:
                leave_call()

        @staticmethod
        async def aclose():
            return None

    class FakeLlmClientTransport:
        @staticmethod
        def generate(_messages):
            enter_call()
            try:
                time.sleep(0.01)
                return "llmclient"
            finally:
                leave_call()

    runtime = ModelExecutionRuntime(
        settings,
        mep_transport=FakeMepTransport(),
        deepseek_http_transport=FakeDeepSeekHttpTransport(),
        deepseek_platform_transport=FakeDeepSeekPlatformTransport(),
        llmclient_transport=FakeLlmClientTransport(),
    )
    try:
        results = await asyncio.gather(
            runtime.generate_once("mep", [], _request_context()),
            runtime.generate_once("deepseek_http", [], _request_context()),
            runtime.generate_once("deepseek_platform", [], _request_context()),
            runtime.generate_once("llmclient", [], _request_context()),
        )
    finally:
        await runtime.aclose()

    assert results == ["mep", "deepseek-http", "deepseek-platform", "llmclient"]
    assert max_active_calls == 1
