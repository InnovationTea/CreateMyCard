"""百炼是独立可选通道，不改变原默认配置或共用官方DeepSeek密钥。"""

import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest

from config.config import Settings
from config.config_helper import ConfigHelper
from custom.aliyun_bailian_transport import AliyunBailianHttpTransport
from custom.model_runtime import ModelExecutionRuntime
from custom.model_transport import ModelTransportError
from custom.unified_model_client import UnifiedModelClient


def _settings(**overrides: object) -> Settings:
    values = {
        "_env_file": None,
        "openai_master_client": "aliyun_bailian",
        "aliyun_bailian_base_url": "https://deployment.example/compatible-mode/v1",
        "aliyun_bailian_api_key": "bailian-test-secret",
        "aliyun_bailian_model": "deepseek-v4.1-flash",
        "deepseek_official_http_api_key": "different-official-secret",
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.asyncio
@pytest.mark.parametrize("suffix", ["", "/", "/chat/completions"])
async def test_independent_settings_and_compatible_payload(suffix: str) -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(url=str(request.url), authorization=request.headers.get("authorization"))
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    settings = _settings(
        aliyun_bailian_base_url=f"https://deployment.example/compatible-mode/v1{suffix}",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        transport = AliyunBailianHttpTransport(settings, http_client=client)
        assert await transport.generate([{"role": "user", "content": "demo"}]) == "OK"
        await transport.aclose()
        assert not client.is_closed
    assert captured.get("url") == "https://deployment.example/compatible-mode/v1/chat/completions"
    assert captured.get("authorization") == "Bearer bailian-test-secret"
    body = captured.get("body")
    assert isinstance(body, dict)
    assert body.get("model") == "deepseek-v4.1-flash"
    assert body.get("thinking") == {"type": "disabled"}
    assert body.get("stream") is False
    assert body.get("max_tokens") == 8192
    assert settings.deepseek_official_http_api_key == "different-official-secret"
    assert "bailian-test-secret" not in repr(transport.options)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response,code",
    [
        (httpx.Response(401), "MODEL_HTTP_STATUS"),
        (httpx.Response(503), "MODEL_HTTP_STATUS"),
        (httpx.Response(200, content=b"bad json"), "MODEL_RESPONSE_INVALID"),
        (httpx.Response(200, json={"choices": []}), "MODEL_EMPTY_OUTPUT"),
    ],
)
async def test_remote_errors_preserve_common_error_codes(
    response: httpx.Response,
    code: str,
) -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: response)) as client:
        transport = AliyunBailianHttpTransport(_settings(), http_client=client)
        with pytest.raises(ModelTransportError) as error:
            await transport.generate([])
    assert error.value.code == code
    assert "bailian-test-secret" not in str(error.value)
    assert "DeepSeek official" not in str(error.value)


@pytest.mark.asyncio
async def test_missing_key_does_not_borrow_official_key_or_call_network() -> None:
    def unexpected_request(_: httpx.Request) -> httpx.Response:
        pytest.fail("百炼未配置密钥时不应请求网络")

    async with httpx.AsyncClient(transport=httpx.MockTransport(unexpected_request)) as client:
        transport = AliyunBailianHttpTransport(_settings(aliyun_bailian_api_key=""), client)
        with pytest.raises(ModelTransportError) as error:
            await transport.generate([])
    assert error.value.code == "MODEL_CONFIG_INVALID"


@pytest.mark.asyncio
async def test_bailian_uses_runtime_routing_and_closes_owned_client() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        settings = _settings(enable_model_failure_retry=False)
        transport = AliyunBailianHttpTransport(settings, http_client=client)
        runtime = ModelExecutionRuntime(settings, aliyun_bailian_transport=transport)
        try:
            router = UnifiedModelClient(settings, runtime, operation_name="compact")
            assert await router.generate("openai", [], None, phase="initial") == "OK"
        finally:
            await runtime.aclose()
    owned = AliyunBailianHttpTransport(_settings())
    await owned.aclose()
    assert owned.http_client.is_closed


def test_settings_accept_bailian_as_master_and_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WIDGET_SERVICE_ALIYUN_BAILIAN_MODEL", "deployment-model")
    settings = Settings(_env_file=None, openai_fallback_client="aliyun_bailian")
    assert settings.openai_fallback_client == "aliyun_bailian"
    assert settings.aliyun_bailian_model == "deployment-model"
    assert settings.openai_master_client != "aliyun_bailian"


def test_old_deployment_config_can_omit_all_new_bailian_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_get = ConfigHelper.get

    def old_config_get(self, key, default=None):
        if key.startswith("aliyun_bailian_"):
            return default
        return original_get(self, key, default)

    monkeypatch.setattr(ConfigHelper, "get", old_config_get)
    path = Path(__file__).resolve().parents[1] / "cloud/config/config.py"
    spec = importlib.util.spec_from_file_location("isolated_bailian_config", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    settings = module.Settings(_env_file=None)
    assert settings.aliyun_bailian_api_key == ""
    assert settings.aliyun_bailian_max_tokens == 8192
    assert settings.openai_master_client != "aliyun_bailian"


@pytest.mark.asyncio
async def test_timeout_does_not_expose_secret_or_request_text() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("bailian-test-secret and private prompt")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        transport = AliyunBailianHttpTransport(_settings(), http_client=client)
        with pytest.raises(ModelTransportError) as error:
            await transport.generate([{"role": "user", "content": "private prompt"}])
    assert error.value.code == "MODEL_HTTP_TIMEOUT"
    assert "private prompt" not in str(error.value)
    assert "bailian-test-secret" not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"aliyun_bailian_base_url": "not-an-http-url"},
        {"aliyun_bailian_base_url": "https://name:private@deployment.example/v1"},
        {"aliyun_bailian_model": ""},
        {"aliyun_bailian_max_tokens": 0},
        {"aliyun_bailian_temperature": -1},
        {"aliyun_bailian_top_p": 0},
    ],
)
async def test_invalid_configuration_stops_before_network(overrides: dict) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        pytest.fail("非法配置不应发起HTTP请求")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        transport = AliyunBailianHttpTransport(_settings(**overrides), http_client=client)
        with pytest.raises(ModelTransportError) as error:
            await transport.generate([])
    assert error.value.code == "MODEL_CONFIG_INVALID"


@pytest.mark.asyncio
async def test_bailian_can_be_explicit_fallback_without_changing_retry_contract() -> None:
    calls = []

    class FailedOfficial:
        async def generate(self, messages, request_context=None):
            calls.append("official")
            raise ModelTransportError("official unavailable", code="MODEL_HTTP_STATUS")

        async def aclose(self):
            return None

    def handler(_: httpx.Request) -> httpx.Response:
        calls.append("bailian")
        return httpx.Response(200, json={"choices": [{"message": {"content": "recovered"}}]})

    settings = _settings(
        openai_master_client="deepseek_official_http",
        openai_fallback_client="aliyun_bailian",
        enable_model_failure_retry=True,
        enable_openai_fallback=True,
        model_failure_max_retry_attempts=0,
        fallback_model_failure_max_retry_attempts=0,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        runtime = ModelExecutionRuntime(
            settings,
            deepseek_official_http_transport=FailedOfficial(),
            aliyun_bailian_transport=AliyunBailianHttpTransport(settings, http_client=client),
        )
        try:
            router = UnifiedModelClient(settings, runtime, operation_name="compact")
            assert await router.generate("openai", [], None, phase="initial") == "recovered"
            assert router.retry_count == 1
        finally:
            await runtime.aclose()
    assert calls == ["official", "bailian"]
