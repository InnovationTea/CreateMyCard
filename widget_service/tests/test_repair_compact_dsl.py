# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import json
from pathlib import Path

import pytest

import repair_compact_dsl as repair_module

_VALID_COMPACT_DSL = "\n".join(
    [
        '["root","Column",{"width":160,"height":160,"padding":8,'
        '"borderRadius":18,"clip":true},["title"]]',
        '["title","Text",{"content":"Repair Demo","fontSize":20,'
        '"fontColor":"#E5000000"}]',
        '["/ui/state","ready"]',
    ]
)
_INVALID_COMPACT_DSL = "\n".join(
    [
        '["root","Column",{"width":160,"height":160},["temperature"]]',
        '["temperature","Text",'
        '{"content":"{{ \'/data/weather/current/temperatureText\' }}"}]',
        '["/data/weather/current/temperatureText","26℃"]',
    ]
)

_TASK_SPEC = {
    "userQuery": "生成一张修复测试卡片",
    "size": "2x2",
    "eventCandidates": [],
    "dataModelSchema": {},
    "assetCandidates": [],
}


def _write_artifact(
    path: Path,
    compact_dsl: str = _VALID_COMPACT_DSL,
) -> None:
    blocks = {
        "cardspec": {
            "title": "修复测试",
            "description": "修复测试卡片",
            "suggestSize": "2x2",
        },
        "genui": _VALID_COMPACT_DSL,
        "schema": {"schemaVersion": "widget-artifact-v2"},
        "taskspec": _TASK_SPEC,
        "effectivecapabilities": {"data": [], "event": [], "asset": []},
        "removedcapabilities": [],
        "generationplan": {},
        "meta": {
            "protocolProfileId": "a2ui-form-rom6.0-v1",
            "capabilityRegistryVersion": "app-test_rom-6.0",
            "createdAt": 1,
        },
    }
    block_order = (
        "cardspec",
        "genui",
        "schema",
        "taskspec",
        "effectivecapabilities",
        "removedcapabilities",
        "generationplan",
        "meta",
    )
    parts = []
    for name in block_order:
        body = json.dumps(blocks[name], ensure_ascii=False)
        if name == "genui":
            body = blocks[name]
        parts.append(f"```{name}\n{body}\n```")
    parts.append(f"```designcompactdsl\n{compact_dsl}\n```")
    path.write_text("\n".join(parts), encoding="utf-8")


@pytest.mark.asyncio
async def test_repair_compact_dsl_repairs_validation_failure(monkeypatch, tmp_path):
    validation_calls = 0
    repair_prompts: list[list[dict[str, str]]] = []
    client_closed = False

    class FakeArtifactValidator:
        def validate(self, _artifact, _protocol_profile):
            nonlocal validation_calls
            validation_calls += 1
            if validation_calls == 1:
                return ["TEST_VALIDATION_FAILED: test validation failure [genui]"]
            return []

    class FakeModelClient:
        def __init__(self, **_kwargs):
            pass

        async def generate_repair(self, prompt, _profile):
            repair_prompts.append(prompt)
            return _VALID_COMPACT_DSL

        async def aclose(self):
            nonlocal client_closed
            client_closed = True

    monkeypatch.setattr(repair_module, "ArtifactValidator", FakeArtifactValidator)
    monkeypatch.setattr(repair_module, "A2UIModelClient", FakeModelClient)
    artifact_path = tmp_path / "artifact.txt"
    _write_artifact(artifact_path)

    result = await repair_module.repair_compact_dsl(artifact_path)

    assert result.repair_count == 1
    assert validation_calls == 2
    assert client_closed is True
    assert len(result.dsl.splitlines()) == 3
    repair_payload = json.loads(repair_prompts[0][1]["content"])
    assert repair_payload["invalidSourceDsl"] == _VALID_COMPACT_DSL
    assert repair_payload["qualityErrors"][0]["stage"] == "validation"
    original_user_content = json.loads(repair_payload["originalUserContent"])
    assert original_user_content == _TASK_SPEC


@pytest.mark.asyncio
async def test_repair_compact_dsl_repairs_compact_validation_failure(
    monkeypatch,
    tmp_path,
):
    repair_prompts: list[list[dict[str, str]]] = []

    class FakeArtifactValidator:
        def validate(self, _artifact, _protocol_profile):
            return []

    class FakeModelClient:
        def __init__(self, **_kwargs):
            pass

        async def generate_repair(self, prompt, _profile):
            repair_prompts.append(prompt)
            return _VALID_COMPACT_DSL

        async def aclose(self):
            pass

    monkeypatch.setattr(repair_module, "ArtifactValidator", FakeArtifactValidator)
    monkeypatch.setattr(repair_module, "A2UIModelClient", FakeModelClient)
    artifact_path = tmp_path / "invalid-artifact.txt"
    _write_artifact(artifact_path, _INVALID_COMPACT_DSL)

    result = await repair_module.repair_compact_dsl(artifact_path)

    assert result.repair_count == 1
    repair_payload = json.loads(repair_prompts[0][1]["content"])
    quality_errors = repair_payload["qualityErrors"]
    assert len(quality_errors) == 2
    assert all(item["stage"] == "validation" for item in quality_errors)
    assert all(
        item["code"] == "COMPACT_DSL_VALIDATION_FAILED"
        for item in quality_errors
    )
