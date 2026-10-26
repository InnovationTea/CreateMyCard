# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import re
from pathlib import Path

import pytest
from cloud.config.config import Settings
from cloud.config.config_helper import ConfigHelper

from services import widget_generation_service as service_module
from services.compact_prompt_loader import read_prompt


def _force_default_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    missing_spec = tmp_path / "missing-spec.yaml"
    monkeypatch.setattr(ConfigHelper, "_get_spec_config_file", lambda _self: missing_spec)


def test_default_model_failure_retry_is_enabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _force_default_config(monkeypatch, tmp_path)
    helper = ConfigHelper("local")
    assert helper.get("enable_model_failure_retry") == "true"
    assert helper.get("model_failure_max_retry_attempts") == 1
    assert helper.get("fallback_model_failure_max_retry_attempts") == 1


def test_missing_spec_uses_default_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _force_default_config(monkeypatch, tmp_path)

    helper = ConfigHelper("local")

    assert helper.config_file.name == "default_config.yaml"
    assert helper.get("obs.expire.time") == 3600
    assert helper.get("enable_a2ui_model_mock") == "true"
    assert helper.get("daily_usage_slb") == ""
    assert helper.get("daily_usage_limit_exceeded_message") == (
        "今日 AI 卡片生成次数已达上限，请明天再尝试。"
    )
    assert helper.get("daily_usage_limit_unavailable_message") == "本次卡片生成失败，请稍后重试。"
    assert helper.get("fusion_ball_min_prd_version") == "11.7.5.206"
    assert helper.get("enable_compact_dsl_argument_repair_fallback") == "false"
    assert helper.get("compact_dsl_argument_repair_reminder_count") == 1
    assert helper.get("compact_dsl_argument_repair_max_attempts") == 2
    assert helper.get("enable_compact_dsl_interface_retry") == "true"
    assert helper.get("compact_dsl_interface_retry_count") == 1
    assert helper.get("enable_single_step_generation_fallback") == "false"
    assert helper.get("enable_single_step_widget_edit") == "true"
    assert helper.get("enable_widget_edit") == "true"
    assert "enable_post_layout_theme" not in helper
    assert "enable_post_layout_theme" not in Settings.model_fields
    assert helper.get("enable_photo_background_theme") == "true"
    assert helper.get("enable_subjectless_wide_theme") == "false"
    assert helper.get("enable_square_photo_expansion") == "false"


@pytest.mark.parametrize(
    ("config_key", "prompt_name"),
    [
        ("system.prompt", "create"),
        ("edit.system.prompt", "edit"),
        ("repair.system.prompt", "repair"),
    ],
)
def test_default_prompt_references_load_complete_source(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    config_key: str,
    prompt_name: str,
) -> None:
    _force_default_config(monkeypatch, tmp_path)
    helper = ConfigHelper("local")
    source_root = (
        Path(__file__).resolve().parents[1]
        / "cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source"
    )
    expected = read_prompt(source_root, prompt_name)
    assert expected.strip()
    assert helper.get(config_key) == expected


def test_existing_spec_is_used_without_default_merge(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    spec_file = tmp_path / "spec_records.yaml"
    spec_file.write_text("ENVIRONMENT: cn_dev_default\nonly_spec: true\n", encoding="utf-8")
    monkeypatch.setattr(ConfigHelper, "_get_spec_config_file", lambda _self: spec_file)

    helper = ConfigHelper("local")

    assert helper.config_file == spec_file.resolve()
    assert helper.get("only_spec") == "true"
    assert "obs.expire.time" not in helper
    assert helper.get("enable_compact_dsl_interface_retry", "false") == "false"
    assert helper.get("compact_dsl_interface_retry_count", 1) == 1


def test_default_interface_retry_policy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _force_default_config(monkeypatch, tmp_path)
    helper = ConfigHelper("local")

    assert helper.get("enable_compact_dsl_interface_retry") == "true"
    assert helper.get("compact_dsl_interface_retry_count") == 1


def test_cloud_properties_file_keeps_json_compatibility(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    spec_file = tmp_path / "user-config.properties"
    spec_file.write_text('{"ENVIRONMENT": "cloud", "feature": true}', encoding="utf-8")
    monkeypatch.setattr(ConfigHelper, "_get_spec_config_file", lambda _self: spec_file)

    helper = ConfigHelper("cloud")

    assert helper.get("ENVIRONMENT") == "cloud"
    assert helper.get("feature") == "true"


def test_default_config_covers_all_runtime_config_keys(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _force_default_config(monkeypatch, tmp_path)
    helper = ConfigHelper("local")
    cloud_root = Path(__file__).resolve().parents[1] / "cloud"
    required_keys: set[str] = set()
    for source_file in cloud_root.rglob("*.py"):
        source = source_file.read_text(encoding="utf-8")
        required_keys.update(re.findall(r'CONFIG\.get\("([^"]+)"\)', source))

    missing_keys: list[str] = []
    for key in required_keys:
        if key not in helper:
            missing_keys.append(key)

    assert not missing_keys


def test_settings_prefixed_environment_wins_over_bare_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("OPENAI_MASTER_CLIENT", "llmclient")
    monkeypatch.setenv(
        "WIDGET_SERVICE_OPENAI_MASTER_CLIENT",
        "deepseek_official_http",
    )

    settings = Settings(_env_file=tmp_path / "missing.env")

    assert settings.openai_master_client == "deepseek_official_http"


@pytest.mark.parametrize(
    "option", ["daily_usage_limit_exceeded_message", "daily_usage_limit_unavailable_message"]
)
def test_daily_usage_messages_support_environment_override(monkeypatch, tmp_path, option):
    monkeypatch.setenv(f"WIDGET_SERVICE_{option.upper()}", "自定义卡片提示。")
    settings = Settings(_env_file=tmp_path / "missing.env")
    assert getattr(settings, option) == "自定义卡片提示。"


@pytest.mark.parametrize("enabled", [False, True])
def test_settings_reads_card_template_switch_from_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    enabled: bool,
) -> None:
    monkeypatch.setenv("WIDGET_SERVICE_ENABLE_CARD_TEMPLATE", str(enabled).lower())

    settings = Settings(_env_file=tmp_path / "missing.env")
    monkeypatch.setattr(service_module, "get_settings", lambda: settings)

    assert settings.enable_card_template is enabled
    assert service_module.WidgetGenerationService()._enable_card_template() is enabled


def test_removed_theme_switch_cannot_restore_front_loaded_theme(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("WIDGET_SERVICE_ENABLE_POST_LAYOUT_THEME", "false")

    settings = Settings(_env_file=tmp_path / "missing.env")

    assert not hasattr(settings, "enable_post_layout_theme")


@pytest.mark.parametrize("key", [
    "ENABLE_PHOTO_BACKGROUND_THEME", "WIDGET_SERVICE_ENABLE_PHOTO_BACKGROUND_THEME",
])
@pytest.mark.parametrize("enabled", [False, True])
def test_photo_switch_can_override_enabled_default(monkeypatch, tmp_path, key, enabled):
    monkeypatch.delenv("ENABLE_PHOTO_BACKGROUND_THEME", raising=False)
    monkeypatch.delenv("WIDGET_SERVICE_ENABLE_PHOTO_BACKGROUND_THEME", raising=False)
    monkeypatch.setenv(key, str(enabled).lower())
    settings = Settings(_env_file=tmp_path / "missing.env")
    assert settings.enable_photo_background_theme is enabled


def test_settings_reads_prompt_file_alias_from_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("prompt from env file", encoding="utf-8")
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"WIDGET_SERVICE_SYSTEM_PROMPT_FILE={prompt_file}\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("WIDGET_SERVICE_SYSTEM_PROMPT_FILE", raising=False)

    settings = Settings(_env_file=env_file)

    assert settings.system_prompt == "prompt from env file"
