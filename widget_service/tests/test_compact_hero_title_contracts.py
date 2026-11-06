"""主槽角色与标题容量走公开校验，普通标题和既有布局保持兼容。"""

import json

import pytest

from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.theme_style_roles import layout_phase


def source(hero, title="概览"):
    rows = [
        ["root", "Layout", {"layout": "W-content-side-slots"}, ["area", "upper", "lower"]],
        ["area", "Region", {"variant": "title-hero-support"}, ["heading", "main", "support"]],
        ["heading", "SingleLineTitle", {"title": title, "fontSize": 12}],
        ["main", *hero],
        ["support", "SecondaryBody", {"items": [{"value": "辅助信息"}], "fontSize": 14}],
        ["upper", "InfoBlock", {"variant": "slot", "primaryText": "甲", "secondaryText": "第一项"}],
        ["lower", "InfoBlock", {"variant": "slot", "primaryText": "乙", "secondaryText": "第二项"}],
        ["/data/value", 30],
    ]
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def validate(dsl, *, sample=True):
    field = {"type": "integer"}
    if sample:
        field["sampleValue"] = 30
    task = {"size": "2x4", "dataModelSchema": {"data": {"value": field}}}
    with layout_phase():
        return validate_compact_dsl(
            dsl, task_spec=task, card_spec={}, enforce_model_component_types=True,
        )


@pytest.mark.parametrize("hero", [
    ["SingleLineTitle", {"title": "一行标题", "fontSize": 12}],
    ["SecondaryBody", {"items": [{"value": "辅助说明"}], "fontSize": 14}],
])
def test_other_regions_core_cannot_substitute_for_a_hero(hero):
    with pytest.raises(CompactDslValidationError, match="hero slot requires a core"):
        validate(source(hero))


def test_core_group_in_hero_is_allowed():
    dsl = source(["Group", {"variant": "hero-support"}, ["value", "note"]])
    dsl += '\n["value","EmphasisText",{"mainText":"主内容","fontSize":18}]'
    dsl += '\n["note","SecondaryBody",{"items":[{"value":"说明"}],"fontSize":14}]'
    validate(dsl)


def test_group_of_titles_and_auxiliary_text_is_not_a_core():
    dsl = source(["Group", {"variant": "hero-support"}, ["value", "note"]])
    dsl += '\n["value","SingleLineTitle",{"title":"小标题","fontSize":12}]'
    dsl += '\n["note","SecondaryBody",{"items":[{"value":"说明"}],"fontSize":14}]'
    with pytest.raises(CompactDslValidationError, match="hero slot requires a core"):
        validate(dsl)


def test_long_title_cannot_hide_the_only_numeric_reading():
    title = "{{ '较长的任务背景和必要对象说明还有 ' + ${/data/value} + ' 项' }}"
    with pytest.raises(CompactDslValidationError, match="text width overflow") as captured:
        validate(source(["EmphasisText", {"mainText": "主内容", "fontSize": 18}], title))
    assert "SingleLineTitle is the only display" in str(captured.value)


def test_decorative_long_title_keeps_non_blocking_warning():
    hero = ["EmphasisText", {"mainText": "主内容", "fontSize": 18}]
    result = validate(source(hero, "装饰标题" * 8))
    assert any("SingleLineTitle overflow" in item for item in result.warnings)


def test_title_with_separate_core_reading_is_not_blocked():
    title = "{{ '较长的任务背景和必要对象说明还有 ' + ${/data/value} + ' 项' }}"
    hero = ["EmphasizedData", {"value": {"path": "/data/value"}, "unit": "项", "fontSize": 30}]
    result = validate(source(hero, title))
    assert any("SingleLineTitle overflow" in item for item in result.warnings)


def test_unknown_title_sample_is_not_guessed():
    title = "{{ '较长的任务背景和必要对象说明还有 ' + ${/data/value} + ' 项' }}"
    hero = ["EmphasisText", {"mainText": "主内容", "fontSize": 18}]
    result = validate(source(hero, title), sample=False)
    assert not any("SingleLineTitle overflow" in item for item in result.warnings)


def test_hero_error_uses_existing_recomposition_budget():
    from services.compact_repair_strategy import CompactRepairStrategyTracker

    dsl = source(["SingleLineTitle", {"title": "一行标题", "fontSize": 12}])
    with pytest.raises(CompactDslValidationError) as captured:
        validate(dsl)
    issues = [
        {"stage": "validation", "code": "COMPACT_DSL_VALIDATION_FAILED", "message": message}
        for message in captured.value.errors
    ]
    tracker = CompactRepairStrategyTracker(max_repair_attempts=1)
    directive = tracker.next_directive(dsl, issues)
    assert directive.category == "layout_structure"
    assert directive.retry_target == "dsl_recompose"
    assert directive.retryable is True
    assert tracker.next_directive(dsl, issues).retryable is False
