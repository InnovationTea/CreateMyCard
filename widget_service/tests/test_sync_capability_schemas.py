# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import importlib.util
import json
from pathlib import Path
from typing import Any

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "sync_capability_schemas.py"
)
SCRIPT_SPEC = importlib.util.spec_from_file_location(
    "sync_capability_schemas",
    SCRIPT_PATH,
)
if SCRIPT_SPEC is None or SCRIPT_SPEC.loader is None:
    raise RuntimeError("cannot load sync_capability_schemas.py")
SCRIPT_MODULE = importlib.util.module_from_spec(SCRIPT_SPEC)
SCRIPT_SPEC.loader.exec_module(SCRIPT_MODULE)
synchronize = SCRIPT_MODULE.synchronize


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_synchronize_updates_validator_without_touching_online_skill(tmp_path):
    capabilities_root = (
        tmp_path / "widget_service" / "cloud" / "data" / "capabilities"
    )
    validator_path = (
        tmp_path
        / "widget_service"
        / "cloud"
        / "data"
        / "validator_rules"
        / "schemas"
        / "capability.weather.schema.json"
    )
    skill_path = (
        tmp_path
        / "skills"
        / "harmony-card-generation-online"
        / "scripts"
        / "rules"
        / "schemas"
        / "capability.weather.schema.json"
    )
    _write_json(
        capabilities_root / "registry_ranges.json",
        {"ranges": [{"registryVersion": "registry-v1"}]},
    )
    _write_json(
        capabilities_root / "registry-v1" / "data_capabilities.json",
        [
            {
                "id": "ViewWeather",
                "defaultWriteResultTo": "/data/weather",
                "inputSchema": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
                "outputSchema": {
                    "type": "object",
                    "properties": {"temperature": {"type": "number"}},
                },
            }
        ],
    )
    _write_json(
        validator_path,
        {
            "capabilityId": "ViewWeather",
            "preferredWriteResultTo": "/data/old",
            "inputSchema": {"type": "object", "additionalProperties": False},
            "outputSchema": {"type": "object", "additionalProperties": False},
        },
    )
    skill_payload = {"sentinel": "must-not-change"}
    _write_json(skill_path, skill_payload)

    changes = synchronize(tmp_path, check_only=False)

    validator = json.loads(validator_path.read_text(encoding="utf-8"))
    expected_path = (
        Path("widget_service")
        / "cloud"
        / "data"
        / "validator_rules"
        / "schemas"
        / "capability.weather.schema.json"
    )
    assert [Path(change) for change in changes] == [expected_path]
    assert validator["preferredWriteResultTo"] == "/data/weather"
    assert validator["inputSchema"]["required"] == ["city"]
    assert validator["inputSchema"]["additionalProperties"] is False
    assert json.loads(skill_path.read_text(encoding="utf-8")) == skill_payload
