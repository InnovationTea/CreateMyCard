# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import re
from pathlib import Path

import pytest
from cloud.config.config_helper import ConfigHelper


def _force_default_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    missing_spec = tmp_path / "missing-spec.yaml"
    monkeypatch.setattr(ConfigHelper, "_get_spec_config_file", lambda _self: missing_spec)


def test_missing_spec_uses_default_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _force_default_config(monkeypatch, tmp_path)

    helper = ConfigHelper("local")

    assert helper.config_file.name == "default_config.yaml"
    assert helper.get("obs.expire.time") == 3600
    assert helper.get("enable_a2ui_model_mock") == "true"
    assert "# 一、任务目标与优先级" in helper.get("system.prompt")
    assert "编辑模式附加规则" in helper.get("edit.system.prompt")
    assert "DSL 转换或校验错误修复" in helper.get("repair.system.prompt")
    assert helper.get("fusion_ball_min_prd_version") == "11.7.5.206"
    assert helper.get("enable_compact_dsl_argument_repair_fallback") == "false"
    assert helper.get("compact_dsl_argument_repair_reminder_count") == 1


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
