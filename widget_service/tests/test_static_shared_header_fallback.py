"""共享说明使用独立承载，不能在试排时变成某一对象的专属条件。"""

import copy
import json

import pytest

from config.config import get_settings
from models.artifact import ArtifactMeta, WidgetArtifact
from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.card_validation.compact_validation.semantic.static_content import static_fact_coverage
from services.compact_high_level_components import CompactDslConversionError
from services.generation_content_policy import STATIC_CONTENT_POLICY, content_policy_scope
from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext
from services.protocol_registry import A2UIProtocolRegistry
from services.static_content_components import complete_static_text_trial
from services.static_content_presentation import (
    static_presentation_candidates,
    trial_static_presentation,
)
from services.validator import ArtifactValidator


def _fact(text, role="body", **extra):
    return {
        "requirement": text, "text": text, "sourceTexts": [text], "priority": "must",
        "displayRole": role, **extra,
    }


def _plan():
    facts = [
        _fact("猫咪分龄每日喂食量", "title"),
        _fact("每天50至70克干粮，分4餐"),
        _fact("每天60至90克干粮，分3餐"),
        _fact("每天40至60克干粮，分2餐"),
        _fact("每天35至50克，选易消化配方"),
        _fact("各阶段均保证自由饮水"),
    ]
    groups = [{"id": "title", "kind": "shared", "identity": None, "factIndexes": [0]}]
    names = ("2至4月龄幼猫", "4至12月龄", "1至7岁成年猫", "7岁以上老年猫")
    for index, name in enumerate(names, 1):
        groups.append({
            "id": f"object{index}", "kind": "object", "identity": name,
            "factIndexes": [index],
        })
    groups.append({"id": "note", "kind": "shared", "identity": None, "factIndexes": [5]})
    return {
        "info_required": facts, "contentGroups": groups, "presentationStyle": "comparison",
        "layoutHints": ["W-static-content"], "omittedContents": [],
    }


def _tariff_plan(*, compact_times=False):
    facts = [
        _fact("谷段 23:00–次日7:00，0.42元/度", "value"),
        _fact("平段 7:00–10:00、15:00–18:00，0.78元/度", "value"),
        _fact("峰段 11:00–14:00、18:00–21:00，1.16元/度", "value"),
        _fact("另收服务费0.55元/度"),
    ]
    if compact_times:
        facts[1] = _fact("平段 7:00–10:00，0.78元/度", "value")
        facts[2] = _fact("峰段 11:00–14:00，1.16元/度", "value")
    groups = []
    for index, name in enumerate(("谷段", "平段", "峰段")):
        groups.append({
            "id": f"object{index}", "kind": "object", "identity": name,
            "factIndexes": [index],
        })
    groups.append({"id": "note", "kind": "shared", "identity": None, "factIndexes": [3]})
    return {
        "info_required": facts, "contentGroups": groups, "presentationStyle": "records",
        "layoutHints": ["W-static-content"], "omittedContents": [],
    }


def _task(plan):
    query = "；".join(fact.get("text", "") for fact in plan.get("info_required", []))
    return {
        "userQuery": query, "size": "2x4", "dataModelSchema": {"data": {}},
        "eventCandidates": [], "assetCandidates": [],
        "appVersion": "17.0.4.300", "romVersion": "7.0.0",
    }


def _header(source):
    rows = [json.loads(line) for line in source.splitlines()]
    row = next((row for row in rows if row[0] == "header"), None)
    return row[2].get("title") if row else None


def _validate(source, plan):
    with complete_static_text_trial():
        return validate_compact_dsl(
            source, task_spec=_task(plan), card_spec={"suggestSize": "2x4"},
            compact_plan=plan, layout_scope="W-static-content-guided",
        )


@pytest.fixture(autouse=True)
def _static_scope(monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_design_compact_deterministic_repair", True)
    with content_policy_scope(STATIC_CONTENT_POLICY):
        yield


def test_shared_notes_are_not_inserted_into_individual_object_candidates():
    plan = _plan()
    assert static_presentation_candidates(plan, "2x4") == ()
    sources = static_presentation_candidates(plan, "2x4", include_fallback=True)
    assert len(sources) == 1
    assert len(set(sources)) == len(sources)
    rows = [json.loads(line) for line in sources[0].splitlines()]
    body = next(row for row in rows if row[0] == "body")
    assert "各阶段均保证自由饮水" not in json.dumps(body, ensure_ascii=False)
    assert _header(sources[-1]) == "猫咪分龄每日喂食量；各阶段均保证自由饮水"
    _validate(sources[-1], plan)


def test_three_records_with_shared_fee_choose_legal_independent_header_layout():
    plan = _tariff_plan(compact_times=True)
    before = copy.deepcopy(plan)
    trial = trial_static_presentation(plan, _task(plan).get("userQuery"), "2x4")
    assert trial.source is not None
    assert trial.errors == ()
    assert _header(trial.source) == "另收服务费0.55元/度"
    rows = [json.loads(line) for line in trial.source.splitlines()]
    body = next(row for row in rows if row[0] == "body")
    assert body[1] == "SingleLineList"
    assert body[2].get("items") == [
        {"text": "谷段", "assist": "23:00–次日7:00，0.42元/度"},
        {"text": "平段", "assist": "7:00–10:00，0.78元/度"},
        {"text": "峰段", "assist": "11:00–14:00，1.16元/度"},
    ]
    coverage = static_fact_coverage(trial.source, plan)
    assert len(coverage) == 4
    assert all(item.visible for item in coverage)
    _validate(trial.source, plan)
    assert plan == before


def test_long_three_row_values_do_not_bypass_new_panel_capacity():
    plan = _tariff_plan()
    before = copy.deepcopy(plan)
    trial = trial_static_presentation(plan, _task(plan).get("userQuery"), "2x4")
    assert trial.source is None
    assert trial.errors
    assert any("COMPACT_STATIC_TEXT_CAPACITY" in error for error in trial.errors)
    assert plan == before


@pytest.mark.parametrize("plan_factory", [_plan, _tariff_plan])
def test_complete_trial_and_processor_restore_without_omission_or_font_change(plan_factory):
    plan = plan_factory(compact_times=True) if plan_factory is _tariff_plan else plan_factory()
    before = copy.deepcopy(plan)
    task = _task(plan)
    trial = trial_static_presentation(plan, task.get("userQuery"), "2x4")
    assert trial.source is not None
    assert trial.errors == ()
    coverage = static_fact_coverage(trial.source, plan)
    assert len(coverage) == len(plan.get("info_required", []))
    assert all(item.visible for item in coverage)
    profile = A2UIProtocolRegistry().get_profile()
    card = {"suggestSize": "2x4", "title": "分龄喂食", "description": "完整展示喂食量和共同说明"}
    context = DslProcessingContext(
        size="2x4", task_spec=task, card_spec=card, protocol_profile=profile,
        compact_plan=plan, content_policy=STATIC_CONTENT_POLICY,
        layout_scope="W-static-content-guided", colorless_layout=True,
    )
    # 原源失败后，真实处理入口必须完成后备转换，不能只测试候选生成。
    broken = '\n'.join([
        '["root","Layout",{"layout":"W-static-content"},["missing"]]',
        '["/state/ready",true]',
    ])
    result = DesignCompactProcessor().process(broken, context)
    assert result.errors == ()
    assert [json.loads(line) for line in result.source_dsl.splitlines()] == [
        json.loads(line) for line in trial.source.splitlines()
    ]
    artifact = WidgetArtifact(
        genui=result.standard_dsl, taskSpec=task, cardSpec=card,
        effectiveCapabilities={"data": [], "event": [], "asset": []},
        meta=ArtifactMeta(protocolProfileId=profile.get("id"), createdAt=0,
                          capabilityRegistryVersion="offline-test"),
    )
    assert ArtifactValidator({}).validate_layout(artifact, profile) == []
    fonts = set()
    for line in result.standard_dsl.splitlines():
        message = json.loads(line)
        for component in message.get("updateComponents", {}).get("components", []):
            font_size = component.get("styles", {}).get("fontSize")
            if font_size is not None:
                fonts.add(font_size)
    assert fonts == {12}
    assert plan == before
    # 原已成功源不重排，不因为新候选出现而覆盖既有布局。
    same = DesignCompactProcessor().process(result.source_dsl, context)
    assert same == result


def test_overlong_shared_header_is_rejected_instead_of_clipped():
    plan = _plan()
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    facts[5] = _fact("各阶段均保证自由饮水并且定时清洗食盆水盆保持环境干净卫生" * 3)
    sources = static_presentation_candidates(plan, "2x4", include_fallback=True)
    assert _header(sources[-1]).endswith(facts[5].get("text"))
    with pytest.raises((CompactDslValidationError, CompactDslConversionError), match="完整文字"):
        _validate(sources[-1], plan)
    assert trial_static_presentation(plan, _task(plan).get("userQuery"), "2x4").source is None


@pytest.mark.parametrize("role", ["value", "label", "leading", "trailing", "detail"])
def test_other_shared_roles_are_not_moved_to_an_object_or_reclassified_into_header(role):
    plan = _plan()
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    facts[5]["displayRole"] = role
    sources = static_presentation_candidates(plan, "2x4", include_fallback=True)
    assert sources == ()


def test_shared_note_without_existing_title_uses_its_original_text_as_header():
    plan = _plan()
    sources = static_presentation_candidates(plan, "2x4", (0,), include_fallback=True)
    assert sources
    assert all(_header(source) == "各阶段均保证自由饮水" for source in sources)


def test_title_without_shared_notes_keeps_only_existing_candidate():
    sources = static_presentation_candidates(_plan(), "2x4", (5,), include_fallback=True)
    assert len(sources) == 1
    assert _header(sources[0]) == "猫咪分龄每日喂食量"


def test_single_object_emphasis_keeps_shared_note_in_existing_secondary_field():
    plan = {
        "info_required": [_fact("当前19度", "value"), _fact("体感舒适")],
        "contentGroups": [
            {"id": "reading", "kind": "object", "identity": None, "factIndexes": [0]},
            {"id": "note", "kind": "shared", "identity": None, "factIndexes": [1]},
        ],
        "presentationStyle": "content", "layoutHints": ["W-static-content"],
    }
    sources = static_presentation_candidates(plan, "2x4")
    assert len(sources) == 1
    rows = [json.loads(line) for line in sources[0].splitlines()]
    assert rows == [
        ["root", "Layout", {"layout": "W-static-content"}, ["body"]],
        ["body", "EmphasisText", {"mainText": "当前19度", "bottomText": "体感舒适"}],
        ["/state/ready", True],
    ]


def test_shared_header_preserves_declared_group_order():
    plan = _plan()
    groups = plan.get("contentGroups")
    assert isinstance(groups, list)
    groups[0], groups[-1] = groups[-1], groups[0]
    sources = static_presentation_candidates(plan, "2x4", include_fallback=True)
    assert _header(sources[-1]) == "各阶段均保证自由饮水；猫咪分龄每日喂食量"
    _validate(sources[-1], plan)


def test_protected_shared_note_remains_exact_and_plan_is_unchanged():
    plan = _plan()
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    facts[5]["preserveVerbatim"] = True
    facts[5]["protectedTexts"] = ["各阶段均保证自由饮水"]
    before = copy.deepcopy(plan)
    trial = trial_static_presentation(plan, _task(plan).get("userQuery"), "2x4")
    assert trial.source is not None
    assert _header(trial.source) == "猫咪分龄每日喂食量；各阶段均保证自由饮水"
    assert plan == before


def test_optional_omission_candidates_keep_existing_precedence():
    plan = _plan()
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    facts[5]["priority"] = "should"
    trial = trial_static_presentation(plan, _task(plan).get("userQuery"), "2x4")
    assert trial.source is not None
    assert "各阶段均保证自由饮水" not in trial.source
    assert trial.errors and "省略" in trial.errors[0]


def test_action_plan_is_not_rebuilt_by_shared_header_fallback():
    plan = _plan()
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    facts.append({"actionId": "event.open", "priority": "must"})
    assert static_presentation_candidates(plan, "2x4", include_fallback=True) == ()
    assert trial_static_presentation(plan, "保留动作", "2x4").source is None
