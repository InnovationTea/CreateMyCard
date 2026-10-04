"""本地画廊配置兼容与模型响应错误处理。"""

from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from config.config import get_settings
from services.template_generation.test_support import gallery_model_runtime as runtime


def test_legacy_environment_is_typed_and_keeps_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings().model_copy(deep=True)
    monkeypatch.setattr(runtime, "get_settings", lambda: settings)
    path = tmp_path / "local.env"
    path.write_text(
        'WIDGET_SERVICE_OPENAI_MASTER_CLIENT=deepseek_http\n'
        'WIDGET_SERVICE_DEEPSEEK_API_URL=https://example.invalid\n'
        'WIDGET_SERVICE_DEEPSEEK_API_KEY=test-only-secret\n'
        'WIDGET_SERVICE_DEEPSEEK_MODEL=test-model\n'
        'WIDGET_SERVICE_IDS_INSTALLATION_FILTER_PACKAGE_NAMES=["test.package"]\n'
        'WIDGET_SERVICE_MODEL_MAX_CONCURRENCY=3\n'
        'WIDGET_SERVICE_ENABLE_A2UI_MODEL_MOCK=true\n'
        'WIDGET_SERVICE_ENABLE_ARTIFACT_VALIDATION=false\n', encoding="utf-8",
    )
    config = runtime.configure_gallery_environment(path)
    assert config is not None
    assert "test-only-secret" not in repr(config)
    assert settings.openai_master_client == "llmclient"
    assert settings.model_max_concurrency == 3
    assert settings.ids_installation_filter_package_names == ("test.package",)
    assert settings.enable_artifact_validation is True
    assert settings.enable_a2ui_model_mock is False


@pytest.mark.parametrize("content", ["", "WIDGET_SERVICE_OPENAI_MASTER_CLIENT=deepseek_http\n"])
def test_local_configuration_without_http_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, content: str,
) -> None:
    settings = get_settings().model_copy(deep=True)
    settings.openai_master_client = "deepseek_platform"
    monkeypatch.setattr(runtime, "get_settings", lambda: settings)
    path = tmp_path / "local.env"
    path.write_text(content, encoding="utf-8")
    if content:
        with pytest.raises(ValueError, match="不完整"):
            runtime.configure_gallery_environment(path)
    else:
        assert runtime.configure_gallery_environment(path) is None


@pytest.mark.parametrize(
    ("status", "payload", "error"),
    [
        (200, {"choices": [{"message": {"content": "result"}}]}, ""),
        (401, {"secret": "must-not-log"}, "HTTP 请求失败"),
        (200, {"choices": []}, "choices"),
        (200, {"choices": [{"message": {"content": None}}]}, "文本内容"),
    ],
)
def test_http_transport_validates_model_response(
    monkeypatch: pytest.MonkeyPatch, status: int, payload: dict, error: str,
) -> None:
    client = MagicMock()
    client.__enter__.return_value = client
    client.post.return_value = httpx.Response(status, json=payload)
    monkeypatch.setattr(runtime.httpx, "Client", lambda **_kwargs: client)
    config = runtime.GalleryHttpConfig("https://example.invalid", "test", "secret")
    transport = runtime.GalleryHttpTransport(config)
    if error:
        with pytest.raises((ValueError, RuntimeError), match=error):
            transport.generate([])
    else:
        assert transport.generate([]) == "result"
