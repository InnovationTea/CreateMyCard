"""单位检查必须在主题选择前使用既有质量修复预算。"""

import json
from types import SimpleNamespace

import pytest

from api.schemas import GenerateWidgetCardRequest
from config.config import get_settings
from core.errors import GenerationStatus
from custom.a2ui_model_client import A2UIModelClient
from services.artifact_store import ArtifactStore
from services.validator import ArtifactValidator
from services.widget_generation_service import WidgetGenerationService

pytestmark = pytest.mark.usefixtures("existing_generation_policy")


def _unit_source(path: str, unit: str, supporting_text: str, with_unit: bool) -> str:
    value = {"path": path}
    props: dict[str, object] = {
        "label": "读数", "value": value, "supportingText": supporting_text
    }
    if with_unit:
        props["value"] = "{{ ${" + path + "} + '" + unit + "' }}"
    rows = [
        ["root", "Layout", {"layout": "S-center"}, ["content"]],
        ["content", "DataDisplay", props],
        [path, 30],
    ]
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


@pytest.mark.asyncio
@pytest.mark.parametrize("full_validation", [False, True])
@pytest.mark.parametrize("recovers", [False, True])
@pytest.mark.parametrize("unit", ["天", "%"])
async def test_missing_unit_uses_quality_budget_before_theme(
    monkeypatch, full_validation: bool, recovers: bool, unit: str
) -> None:
    if unit == "天":
        capability_id = "GetCountdownDays"
        arguments = {"targetDate": "2026-10-17"}
        data_root = "/data/countdown"
        data_path = data_root + "/countdownDays"
        supporting_text = "10月17日出发"
        query = "显示出发倒计时，保留10月17日出发"
    else:
        capability_id = "GetEarphoneInfo"
        arguments = {}
        data_root = "/data/earphone"
        data_path = data_root + "/batteryLevel"
        supporting_text = "耳机盒电量"
        query = "显示耳机盒电量百分比"
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_a2ui_model_mock", False)
    monkeypatch.setattr(settings, "enable_artifact_validation", full_validation)
    monkeypatch.setattr(settings, "enable_validation_failure_retry", True)
    monkeypatch.setattr(settings, "validation_failure_max_repair_attempts", 2)
    monkeypatch.setattr(settings, "enable_design_compact_runtime_prompt_context", False)
    monkeypatch.setattr(
        WidgetGenerationService, "_enable_card_template", staticmethod(lambda: False)
    )
    monkeypatch.setattr(
        WidgetGenerationService, "_enable_jsx_generation", staticmethod(lambda: False)
    )
    calls = []
    repair_prompts = []

    async def generate(_client, prompt, profile=None, **_kwargs):
        model_format = (profile or {}).get("format")
        if model_format == "raw-json":
            calls.append("plan")
            return json.dumps({
                "name": "submit_card_plan",
                "arguments": {
                    "info_required": [
                        {
                            "requirement": query, "priority": "must",
                            "dataId": data_path,
                            "componentHints": ["DataDisplay"],
                        },
                        {
                            "requirement": supporting_text, "priority": "must",
                            "text": supporting_text, "componentHints": ["DataDisplay"],
                        },
                    ],
                    "layoutHints": ["S-center"],
                },
            }, ensure_ascii=False)
        if "initial" not in calls:
            calls.append("initial")
            return _unit_source(data_path, unit, supporting_text, False)
        calls.append("repair")
        repair_prompts.append(json.dumps(prompt, ensure_ascii=False))
        return _unit_source(data_path, unit, supporting_text, recovers)

    async def theme(artifact, _task, _client, validator, profile, **_kwargs):
        calls.append("theme")
        assert supporting_text in artifact.genui
        assert data_path in artifact.genui
        assert not validator.validate_layout(artifact, profile)
        return artifact

    def save(_store, _artifact):
        calls.append("save")
        return SimpleNamespace(
            artifactUrl="https://artifact.test/unit", artifactDigest="sha256:unit"
        )

    original_units = ArtifactValidator.validate_display_units

    def units(validator, artifact, capabilities):
        assert not full_validation, "完整校验开启时不额外执行单位专项"
        return original_units(validator, artifact, capabilities)

    monkeypatch.setattr(A2UIModelClient, "generate", generate)
    monkeypatch.setattr("services.post_layout_theme.theme_artifact", theme)
    monkeypatch.setattr(ArtifactStore, "save", save)
    monkeypatch.setattr(ArtifactValidator, "validate_display_units", units)
    request = GenerateWidgetCardRequest(
        uid="test-user", prdVer="11.7.7.331", device={"romVersion": "7.0"},
        userQuery=query, size="2x2", title="动态读数",
        description="查看动态读数",
        candidateDataBindings=[{
            "capabilityId": capability_id, "arguments": arguments,
            "writeResultTo": data_root,
        }],
    )
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(request)
    for prompt in repair_prompts:
        assert "DISPLAY_UNIT_MISSING" in prompt
        assert "displayUnits" in prompt
        assert "content_value/content" in prompt
    if recovers:
        assert response.status == GenerationStatus.SUCCESS
        assert calls == ["plan", "initial", "repair", "theme", "save"]
    else:
        assert response.status == GenerationStatus.FAILED
        assert calls == ["plan", "initial", "repair", "repair"]
