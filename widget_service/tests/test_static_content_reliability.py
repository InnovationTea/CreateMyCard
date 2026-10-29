"""静态创建的阶段边界、结构反馈与通用标题候选回归。"""

import copy
import json
from types import SimpleNamespace

import pytest

from services.card_validation import validate_compact_dsl
from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    parse_compact_dsl_rows,
)
from services.compact_plan import CompactPlanValidationError, parse_compact_plan_call
from services.generation_content_policy import (
    EXISTING_CONTENT_POLICY,
    STATIC_CONTENT_POLICY,
    content_policy_scope,
)
from services.prompt_builder import PromptBuilder
from services.static_content_presentation import (
    static_presentation_candidates,
    trial_static_presentation,
)


def _fact(text, **extras):
    return {
        "requirement": "展示本项内容", "priority": "must", "text": text,
        "sourceTexts": [text], **extras,
    }


def _plan(facts):
    groups = []
    for index in range(len(facts)):
        groups.append({
            "id": f"object{index}", "kind": "object", "identity": None, "factIndexes": [index],
        })
    return {"info_required": facts, "contentGroups": groups, "omittedContents": []}


def _submit(plan, query, size="2x4"):
    return parse_compact_plan_call(
        json.dumps({"name": "submit_card_plan", "arguments": plan}, ensure_ascii=False),
        {"userQuery": query, "size": size},
        require_static_identity=True, require_static_omission_refs=True,
    )


@pytest.mark.parametrize("fence", [None, "genui", "json"])
def test_phase_object_cannot_be_reinterpreted_as_nested_component_rows(fence):
    value = {
        "name": "submit_card_plan",
        "arguments": {"rows": [["root", "Column", {}, []], ["/state/ready", True]]},
    }
    raw = json.dumps(value)
    if fence:
        raw = f"```{fence}\n{raw}\n```"
    with pytest.raises(CompactDslConversionError, match="JSON array rows"):
        parse_compact_dsl_rows(raw)


@pytest.mark.parametrize("identifier", [None, [], {}, 3, True])
def test_invalid_component_id_is_rejected_before_legacy_repair(identifier):
    raw = json.dumps([identifier, "Column", {"space": 4}, []])
    with pytest.raises(CompactDslConversionError, match="component id"):
        parse_compact_dsl_rows(raw)


@pytest.mark.parametrize("kind", [None, [], {}, 3, True, ""])
def test_invalid_component_type_is_rejected_before_legacy_repair(kind):
    raw = json.dumps(["root", kind, {"space": 4}, []])
    with pytest.raises(CompactDslConversionError, match="component type"):
        parse_compact_dsl_rows(raw)


@pytest.mark.parametrize("props", [None, [], 3, True])
def test_invalid_component_props_keep_conversion_exception(props):
    with pytest.raises(CompactDslConversionError, match="props must be an object"):
        parse_compact_dsl_rows(json.dumps(["root", "Column", props, []]))


@pytest.mark.parametrize("property_name", ["width", "height", "alignItems"])
@pytest.mark.parametrize("value", [[], {}])
def test_non_string_alias_values_are_left_for_contract_validation(property_name, value):
    from services.compact_dsl_a2ui_converter import _repair_legacy_component_props

    props = {property_name: value}
    baseline = copy.deepcopy(props)
    kind, repaired = _repair_legacy_component_props("root", "Column", props)
    assert kind == "Column"
    assert repaired == baseline
    assert props == baseline


def test_plan_reports_index_and_source_problems_together_without_mutating_submission():
    facts = [_fact("甲乙丙丁", sourceTexts=["甲", "乙", "丙", "丁"]), _fact("戊")]
    plan = _plan(facts)
    groups = plan.get("contentGroups")
    assert isinstance(groups, list)
    groups[0]["factIndexes"] = [0, 2, True]
    groups[1]["factIndexes"] = [0]
    baseline = copy.deepcopy(plan)
    with content_policy_scope(STATIC_CONTENT_POLICY):
        with pytest.raises(CompactPlanValidationError) as caught:
            _submit(plan, "甲乙丙丁戊")
    message = str(caught.value)
    assert "contentGroups[0].factIndexes[1]" in message
    assert "实际值=2" in message and "有效整数索引为0–1" in message
    assert "contentGroups[0].factIndexes[2]" in message
    assert "contentGroups[1].factIndexes[0]" in message
    assert "info_required[0].sourceTexts" in message and "实际4段" in message
    assert "info_required[1]" in message
    assert plan == baseline


@pytest.mark.parametrize("bad_index", [True, [], {}, "0", -1, 1])
def test_invalid_fact_index_never_gets_guessed_or_coerced(bad_index):
    plan = _plan([_fact("原文")])
    groups = plan.get("contentGroups")
    assert isinstance(groups, list)
    groups[0]["factIndexes"] = [bad_index]
    with content_policy_scope(STATIC_CONTENT_POLICY):
        with pytest.raises(CompactPlanValidationError, match="factIndexes"):
            _submit(plan, "原文")


def test_plan_json_feedback_preserves_error_location_and_does_not_repair_internal_structure():
    raw = '{"name":"submit_card_plan",\n"arguments":{"selectionNotes":["甲"],["乙"]}}'
    with pytest.raises(CompactPlanValidationError) as caught:
        parse_compact_plan_call(raw, {"size": "2x4"})
    message = str(caught.value)
    assert "Plan output must be valid JSON." in message
    assert "line=2" in message and "column=" in message and "offset=" in message
    assert isinstance(caught.value.__cause__, json.JSONDecodeError)


def test_static_plan_repair_keeps_summary_permission_and_dynamic_contract_is_unchanged():
    messages = [
        {"role": "system", "content": "合同"},
        {"role": "user", "content": "请求"},
        {"role": "assistant", "content": "错误计划"},
    ]
    baseline = copy.deepcopy(messages)
    with content_policy_scope(STATIC_CONTENT_POLICY):
        repaired = PromptBuilder.build_compact_plan_repair(messages, "错误计划", ("索引错误",))
    content = repaired[-1].get("content")
    assert isinstance(content, str)
    assert "忠于sourceTexts的摘要" in content
    assert "不得用自由摘要" not in content
    assert "本次提交的info_required" in content
    assert "全部展示" in content and "冲突来源" in content
    with content_policy_scope(EXISTING_CONTENT_POLICY):
        existing = PromptBuilder.build_compact_plan_repair(messages, "错误计划", ("索引错误",))
    existing_content = existing[-1].get("content")
    assert isinstance(existing_content, str)
    assert "text 必须保留原文" in existing_content
    assert messages == baseline


def _dense_plan():
    facts = [
        _fact("本月采样完整记录", displayRole="title"),
        _fact("整体变化约0.72%", displayRole="body"),
        _fact("最高：采样甲 7.1268", displayRole="body"),
        _fact("最低：采样戊 7.0754", displayRole="body"),
    ]
    for name, reading in (
        ("采样甲", "7.1268"), ("采样乙", "7.1045"), ("采样丙", "7.0921"),
        ("采样丁", "7.0832"), ("采样戊", "7.0754"),
    ):
        facts.append(_fact(f"{name} {reading}", displayRole="title"))
    groups = [{"id": "shared", "kind": "shared", "identity": None, "factIndexes": [0, 1, 2, 3]}]
    for index in range(4, len(facts)):
        groups.append({
            "id": f"sample{index}", "kind": "object", "identity": None, "factIndexes": [index],
        })
    return {"info_required": facts, "contentGroups": groups, "omittedContents": []}


def test_shared_header_search_finds_complete_layout_without_changing_facts_or_limits():
    plan = _dense_plan()
    baseline = copy.deepcopy(plan)
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    query = "；".join(fact.get("text", "") for fact in facts)
    with content_policy_scope(STATIC_CONTENT_POLICY):
        trial = trial_static_presentation(plan, query, "2x4")
        assert trial.source is not None
        rows = [json.loads(line) for line in trial.source.splitlines()]
        assert any(row[0] == "header" and row[1] == "SingleLineTitle" for row in rows)
        validate_compact_dsl(
            trial.source,
            task_spec={
                "userQuery": query, "size": "2x4", "dataModelSchema": {"data": {}},
                "eventCandidates": [], "assetCandidates": [],
            },
            card_spec={"suggestSize": "2x4"}, compact_plan=plan,
            layout_scope="W-static-content-guided",
        )
    assert not trial.errors
    assert plan == baseline


def test_candidates_remain_unique_and_all_complete_font_steps_precede_optional_omission():
    plan = _dense_plan()
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    facts[1]["priority"] = "should"
    with content_policy_scope(STATIC_CONTENT_POLICY):
        sources = static_presentation_candidates(plan, "2x4")
    assert len(sources) == len(set(sources))
    complete_fonts = []
    omission_seen = False
    for source in sources:
        rows = [json.loads(line) for line in source.splitlines()]
        body = next(row for row in rows if row[0] == "body")
        if "整体变化约0.72%" not in source:
            omission_seen = True
            continue
        assert not omission_seen
        complete_fonts.append(body[2].get("fontSize", 12))
    assert complete_fonts == sorted(complete_fonts, reverse=True)
    assert set(complete_fonts) == {12, 11, 10}


def test_unenumerated_structure_remains_feedback_not_permission_to_drop_core():
    facts = []
    for index in range(8):
        facts.append(_fact(f"对象{index}完整内容"))
    plan = _plan(facts)
    baseline = copy.deepcopy(plan)
    with content_policy_scope(STATIC_CONTENT_POLICY):
        trial = trial_static_presentation(plan, "完整内容", "2x4")
    assert trial.source is None
    assert trial.attempted == 0
    assert any("不代表所有合法排版均不可行" in error for error in trial.errors)
    assert plan == baseline


@pytest.mark.asyncio
async def test_wrong_stage_output_recovers_via_existing_candidates_without_extra_model_calls(
    monkeypatch, isolated_theme_stage,
):
    from api.schemas import GenerateWidgetCardRequest
    from config.config import get_settings
    from core.errors import GenerationStatus
    from custom.a2ui_model_client import A2UIModelClient
    from services.artifact_store import ArtifactStore
    from services.widget_generation_service import WidgetGenerationService

    plan = _plan([_fact("甲：完整说明"), _fact("乙：完整说明")])
    raw = json.dumps({"name": "submit_card_plan", "arguments": plan}, ensure_ascii=False)
    calls = []
    saved = []

    async def generate(_client, _prompt, profile=None, **_kwargs):
        calls.append((profile or {}).get("format"))
        return raw

    def save(_store, artifact):
        saved.append(artifact)
        return SimpleNamespace(
            artifactUrl="https://artifact.test/reliability", artifactDigest="test",
        )

    settings = get_settings()
    monkeypatch.setattr(settings, "enable_static_content_generation_policy", True)
    monkeypatch.setattr(settings, "enable_a2ui_model_mock", False)
    monkeypatch.setattr(settings, "enable_artifact_validation", True)
    monkeypatch.setattr(A2UIModelClient, "generate", generate)
    monkeypatch.setattr(ArtifactStore, "save", save)
    request = GenerateWidgetCardRequest(
        uid="reliability-test", prdVer="11.7.7.331", device={"romVersion": "7.0"},
        userQuery="制作静态卡片：甲：完整说明；乙：完整说明", size="2x4",
        title="完整说明", description="阶段边界回归",
    )
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(request)
    assert response.status == GenerationStatus.SUCCESS
    assert len(saved) == 1
    assert calls == ["raw-json", "compact-dsl"]
