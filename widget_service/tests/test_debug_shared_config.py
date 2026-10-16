"""端到端与受管微服务的配置解析保持一致。"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from debug_tools.batch_testing.managed_config import read_configuration, runtime_values
from debug_tools.end_to_end_debug.backend.debug_agent.config import load_main_agent_model_settings
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SharedSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)
    openai_master_client: str = Field(
        default="llmclient",
        validation_alias=AliasChoices(
            "WIDGET_SERVICE_OPENAI_MASTER_CLIENT", "openai_master_client"
        ),
    )
    deepseek_official_http_api_key: str = ""
    model_max_concurrency: int = 1
    enable_model_failure_retry: bool = False
    system_prompt: str = ""


@pytest.mark.parametrize("local_exists", [True, False])
def test_agent_uses_shared_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, local_exists: bool
) -> None:
    project = tmp_path / "widget_service"
    default_dir = project / "cloud/config"
    default_dir.mkdir(parents=True)
    (default_dir / "default_config.yaml").write_text(
        "openai_master_client: llmclient\nmodel_max_concurrency: 3\n", encoding="utf-8"
    )
    (project / ".env").write_text(
        "WIDGET_SERVICE_MODEL_MAX_CONCURRENCY=7\n", encoding="utf-8"
    )
    debug_path = tmp_path / "debug_tool.yaml"
    if local_exists:
        debug_path.write_text(
            "main_agent:\n  model:\n    openai_master_client: invalid-legacy\n"
            "widget_backend:\n  exposed:\n    openai_master_client: deepseek_official_http\n"
            "  defaults:\n    deepseek_official_http_api_key: test-only-key\n"
            "    model_max_concurrency: 11\n    enable_model_failure_retry: true\n"
            "    system_prompt: '@file:prompt.txt'\n",
            encoding="utf-8",
        )
        (tmp_path / "prompt.txt").write_text("共享提示词", encoding="utf-8")
    monkeypatch.setenv("WIDGET_SERVICE_OPENAI_MASTER_CLIENT", "deepseek_platform")
    configuration = read_configuration(project, debug_path=debug_path)
    expected = runtime_values(configuration)

    settings = load_main_agent_model_settings(
        SimpleNamespace(config_path=debug_path), SharedSettings, project_root=project
    )

    for name, value in settings.model_dump().items():
        if name in expected:
            assert value == expected.get(name)
    assert settings.model_max_concurrency == (11 if local_exists else 7)
    assert settings.openai_master_client == (
        "deepseek_official_http" if local_exists else "llmclient"
    )
    if local_exists:
        assert settings.deepseek_official_http_api_key == "test-only-key"
        assert settings.system_prompt == "共享提示词"
