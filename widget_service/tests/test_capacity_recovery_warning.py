"""省略warning必须参与接口恢复证据，不能覆盖Action或重复事实硬错误。"""

import json

import pytest

from api.schemas import GenerateWidgetCardRequest
from config.config import get_settings
from core.errors import ErrorCode, GenerationStatus
from custom.a2ui_model_client import A2UIModelClient
from services.compact_repair_strategy import compact_capacity_recovery_failure_category
from services.generation_pipeline import (
    DslProcessingResult,
    DslProcessorKind,
    QualityIssue,
    get_dsl_processor,
)
from services.widget_generation_service import WidgetGenerationService


def omitted_issue():
    return QualityIssue(stage="validation", code="COMPACT_PLAN_FACT_OMITTED",
                        message="Plan fact was omitted by the bounded fallback: 睡眠综合得分.",
                        severity="warning")


def final_error(kind):
    code = "COMPACT_DSL_VALIDATION_FAILED"
    message = "content: TableText.items requires 2 to 3 entries."
    if kind == "action":
        code = "COMPACT_PLAN_COVERAGE_FAILED"
        message = "Plan action is missing from visible DSL: 打开设置 (event.settings)."
    elif kind == "duplicate":
        code = "COMPACT_PLAN_COVERAGE_FAILED"
        message = "Plan fact is displayed more than once in visible DSL: 睡眠综合得分."
    return QualityIssue(stage="validation", code=code, message=message)


@pytest.mark.parametrize("kind", ["props", "action", "duplicate"])
@pytest.mark.parametrize("prior_layout", [False, True])
def test_omission_warning_only_recovers_prior_capacity_without_protected_errors(kind, prior_layout):
    issues = [omitted_issue().to_diagnostic_payload(), final_error(kind).to_diagnostic_payload()]
    category = compact_capacity_recovery_failure_category(issues, layout_failure_seen=prior_layout)
    assert category == ("layout_capacity" if prior_layout and kind == "props" else None)


def test_warning_alone_or_warning_layout_does_not_authorize_recovery():
    warning = omitted_issue().to_diagnostic_payload()
    assert compact_capacity_recovery_failure_category([warning], layout_failure_seen=True) is None
    layout = {"code": "COMPACT_DSL_VALIDATION_FAILED", "severity": "warning",
              "message": "component root: vertical layout requires at least 160vp within 126vp"}
    error = final_error("props").to_diagnostic_payload()
    assert compact_capacity_recovery_failure_category(
        [layout, error], layout_failure_seen=False,
    ) is None


@pytest.mark.parametrize("kind", ["action", "duplicate"])
def test_actual_layout_error_cannot_override_action_or_duplicate_failure(kind):
    layout = {"code": "COMPACT_DSL_VALIDATION_FAILED",
              "message": "component root: vertical layout requires at least 160vp within 126vp"}
    assert compact_capacity_recovery_failure_category(
        [layout, final_error(kind).to_diagnostic_payload()], layout_failure_seen=True,
    ) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,prior_layout,expected", [
    ("props", True, True), ("props", False, False),
    ("action", True, False), ("duplicate", True, False),
])
async def test_service_passes_warning_evidence_to_interface_retry_context(
    monkeypatch, kind, prior_layout, expected,
):
    settings = get_settings()
    for name, value in {
        "enable_a2ui_model_mock": False, "enable_artifact_validation": False,
        "enable_validation_failure_retry": True, "validation_failure_max_repair_attempts": 1,
        "enable_design_compact_runtime_prompt_context": False,
        "enable_drop_plan_fact_validation": False, "enable_single_step_generation_fallback": False,
        "enable_ids_mock": True,
    }.items():
        monkeypatch.setattr(settings, name, value)
    for name in ("_enable_card_template", "_enable_jsx_generation"):
        monkeypatch.setattr(WidgetGenerationService, name, staticmethod(lambda: False))
    formats = []
    source = '\n'.join([
        '["root","Layout",{"layout":"S-title-content"},["title","content"]]',
        '["title","SingleLineTitle",{"title":"测试"}]',
        '["content","EmphasisText",{"mainText":"测试"}]',
        '["/state/ready",true]',
    ])

    async def generate(_client, _prompt, profile=None, **_kwargs):
        model_format = (profile or {}).get("format")
        formats.append(model_format)
        if model_format == "raw-json":
            return json.dumps({"name": "submit_card_plan", "arguments": {
                "info_required": [{"requirement": "测试", "priority": "must", "text": "测试",
                                   "componentHints": ["EmphasisText"]}],
                "layoutHints": ["S-title-content"],
            }}, ensure_ascii=False)
        return source

    process_calls = []

    def process(source_dsl, _context):
        process_calls.append(source_dsl)
        if len(process_calls) == 1:
            message = "content: unsupported prop invalidProp"
            if prior_layout:
                message = "component root: vertical layout requires at least 160vp within 126vp"
            issues = (QualityIssue(stage="validation", code="COMPACT_DSL_VALIDATION_FAILED",
                                   message=message),)
        else:
            issues = (omitted_issue(), final_error(kind))
        return DslProcessingResult(source_dsl=source_dsl, issues=issues)

    monkeypatch.setattr(A2UIModelClient, "generate", generate)
    processor = get_dsl_processor(DslProcessorKind.DESIGN_COMPACT)
    monkeypatch.setattr(processor, "process", process)
    request = GenerateWidgetCardRequest(
        uid="offline-regression", prdVer="11.7.8.320", device={"romVersion": "6.0"},
        userQuery="生成测试卡片", title="测试", description="离线接口恢复回归", size="2x2",
    )
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(request)
    assert response.status == GenerationStatus.FAILED
    assert response.errorCode == ErrorCode.VALIDATION_FAILED
    retry = response._compact_dsl_retry_context
    assert (retry is not None) is expected
    if retry is not None:
        assert retry.capacity_recovery is True
    assert len(process_calls) == 2
    assert formats == ["raw-json", "compact-dsl", "compact-dsl"]
