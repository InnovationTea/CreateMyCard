"""默认开启的2x4紧凑搜索：联合分区、开关、额度及语义防回退。"""

import json
from dataclasses import replace

import pytest

from config.config import get_settings
from services import compact_wide_recomposition as search
from services.card_validation import CompactDslValidationError
from services.compact_dsl_a2ui_converter import ComponentRow, DataRow, parse_compact_dsl_rows
from services.compact_repair_simplification import (
    _merge_supporting,
    _secondary_options,
    binding_paths,
    serialize_rows,
)
from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext


def _case() -> tuple[str, DslProcessingContext]:
    rows = [["root", "Layout", {"layout": "W-split-panels"}, ["first", "second"]]]
    schema = {}
    facts = []
    for city in ("first", "second"):
        rows.extend([
            [city, "Region", {"variant": "title-hero-support"},
             [city + "_title", city + "_main", city + "_detail"]],
            [city + "_title", "SingleLineTitle", {"title": city, "fontSize": 12}],
            [city + "_main", "EmphasisText", {
                "mainText": {"path": f"/data/{city}/temperatureText"}, "fontSize": 18,
                "secondaryText": {"path": f"/data/{city}/condition"},
            }],
        ])
        values = {"date": "2026-10-19", "weekday": "星期一", "condition": "阴",
                  "temperatureRangeText": "17℃ / 27℃"}
        items = []
        daily_schema = {}
        fields = (("date", "今日 "), ("weekday", "星期 "),
                  ("condition", "天气 "), ("temperatureRangeText", "温度范围 "))
        for key, label in fields:
            path = f"/data/{city}/daily/0/{key}"
            sample = values.get(key)
            assert isinstance(sample, str)
            items.append({"label": label, "value": {"path": path}})
            rows.append([path, sample])
            daily_schema[key] = {"type": "string", "sampleValue": sample}
            facts.append({"dataId": path, "priority": "must", "requirement": path})
        rows.append([city + "_detail", "SecondaryBody", {
            "items": items, "columns": 1, "fontSize": 12,
        }])
        rows.extend([[f"/data/{city}/temperatureText", "22℃"],
                     [f"/data/{city}/condition", "多云"]])
        schema[city] = {"daily": [daily_schema],
                        "temperatureText": {"type": "string", "sampleValue": "22℃"},
                        "condition": {"type": "string", "sampleValue": "多云"}}
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    context = DslProcessingContext(
        size="2x4", task_spec={"size": "2x4", "appVersion": "99.0",
                               "dataModelSchema": {"data": schema}},
        card_spec={"suggestSize": "2x4"}, protocol_profile={},
        compact_plan={"info_required": facts}, layout_scope="W-plan-guided",
        colorless_layout=True,
    )
    return source, context


def test_search_is_enabled_by_default_and_repairs_both_regions(monkeypatch) -> None:
    assert get_settings().enable_design_compact_deterministic_repair
    source, context = _case()
    monkeypatch.setattr(get_settings(), "enable_design_compact_deterministic_repair", False)
    original = DesignCompactProcessor().process(source, context)
    assert original.errors
    monkeypatch.setattr(get_settings(), "enable_design_compact_deterministic_repair", True)
    result = DesignCompactProcessor().process(source, context)
    assert not result.errors
    rows = parse_compact_dsl_rows(result.source_dsl, expand_layouts=False)
    details = []
    for row in rows:
        if isinstance(row, ComponentRow) and row.component_type == "SecondaryBody":
            details.append(row)
    assert len(details) == 2
    for row in details:
        assert len(row.props.get("items", [])) == 2


def test_disabled_success_and_template_paths_never_search(monkeypatch) -> None:
    def unexpected(*args, **kwargs):
        pytest.fail("deterministic search must not run")

    source, context = _case()
    monkeypatch.setattr(get_settings(), "enable_design_compact_deterministic_repair", True)
    accepted = DesignCompactProcessor().process(source, context)
    assert not accepted.errors
    monkeypatch.setattr("services.generation_pipeline.recompose_wide_card", unexpected)
    unchanged = DesignCompactProcessor().process(accepted.source_dsl, context)
    assert unchanged.source_dsl == accepted.source_dsl
    DesignCompactProcessor().process(source, replace(context, size="2x2"))
    monkeypatch.setattr(get_settings(), "enable_design_compact_deterministic_repair", False)
    assert DesignCompactProcessor().process(source, context).errors
    monkeypatch.setattr(get_settings(), "enable_design_compact_deterministic_repair", True)
    DesignCompactProcessor().process(source, replace(context, skip_compact_dsl_validation=True))


def test_existing_planned_countdown_can_restore_core_without_losing_support(monkeypatch) -> None:
    rows = [
        ["root", "Layout", {"layout": "W-split-panels"}, ["left", "right"]],
        ["left", "Region", {"variant": "title-content"}, ["title", "body"]],
        ["title", "SingleLineTitle", {"title": "出行安排", "fontSize": 12}],
        ["body", "SecondaryBody", {"items": [
            {"value": "早上出发"}, {"value": "下午返程"},
            {"value": "{{ '距出发 ' + ${/data/countdown/days} + ' 天' }}"},
        ], "columns": 1, "fontSize": 12}],
        ["right", "Region", {"variant": "title-content"}, ["note_title", "note"]],
        ["note_title", "SingleLineTitle", {"title": "携带物品", "fontSize": 12}],
        ["note", "SecondaryBody", {"items": [{"value": "雨伞"}, {"value": "外套"}],
                                   "columns": 1, "fontSize": 12}],
        ["/data/countdown/days", 3],
    ]
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    context = DslProcessingContext(
        size="2x4", card_spec={"suggestSize": "2x4"}, protocol_profile={},
        task_spec={"size": "2x4", "appVersion": "99.0", "dataModelSchema": {"data": {
            "countdown": {"days": {"type": "integer", "sampleValue": 3}},
        }}},
        compact_plan={"info_required": [{
            "dataId": "/data/countdown/days", "priority": "must",
            "requirement": "出行倒计时", "componentHints": ["EmphasisText"],
        }]}, layout_scope="W-plan-guided", colorless_layout=True,
    )
    monkeypatch.setattr(get_settings(), "enable_design_compact_deterministic_repair", False)
    baseline = DesignCompactProcessor().process(source, context)
    assert any("SecondaryBody is auxiliary" in issue.message for issue in baseline.errors)
    monkeypatch.setattr(get_settings(), "enable_design_compact_deterministic_repair", True)
    result = DesignCompactProcessor().process(source, context)
    assert not result.errors
    candidate_rows = parse_compact_dsl_rows(result.source_dsl, expand_layouts=False)
    original_rows = parse_compact_dsl_rows(source, expand_layouts=False)
    assert search._preserves(search._snapshot(candidate_rows), search._snapshot(original_rows))
    assert any(
        isinstance(row, ComponentRow) and row.component_type == "EmphasisText"
        for row in candidate_rows
    )


@pytest.mark.parametrize("change", ["action", "button_type", "binding", "data", "static", "region"])
def test_candidate_protection_keeps_facts_actions_and_ownership(change: str) -> None:
    rows = (
        ComponentRow("root", "Layout", {"layout": "W-split-panels"}, ("left", "right")),
        ComponentRow("left", "Region", {"variant": "center"}, ("value",)),
        ComponentRow("right", "Region", {"variant": "center"}, ("other",)),
        ComponentRow("value", "EmphasisText", {"mainText": {"path": "/data/value"}}),
        ComponentRow("other", "PillButton", {"label": "打开", "onClick": [{"call": "open"}]}),
        DataRow("/data/value", "完整原值"),
    )
    candidate = list(rows)
    if change == "action":
        candidate[4] = replace(rows[4], props={"label": "打开", "onClick": [{"call": "wrong"}]})
    elif change == "button_type":
        candidate[4] = replace(rows[4], component_type="CardButton")
    elif change == "binding":
        candidate[3] = replace(rows[3], props={"mainText": "样例"})
    elif change == "data":
        candidate[5] = DataRow("/data/value", "改写值")
    elif change == "static":
        candidate[4] = replace(rows[4], props={"label": "删除", "onClick": [{"call": "open"}]})
    else:
        candidate[1] = replace(rows[1], children=("other",))
        candidate[2] = replace(rows[2], children=("value",))
    assert not search._preserves(search._snapshot(tuple(candidate)), search._snapshot(rows))


@pytest.mark.parametrize("limit,expected", [(3, 3), (100, 64)])
def test_search_budget_and_invalid_candidates_preserve_original(
    monkeypatch, limit, expected,
) -> None:
    source, context = _case()
    source_rows = parse_compact_dsl_rows(source, expand_layouts=False)

    def variants(*args, **kwargs):
        for index in range(100):
            rows = list(source_rows)
            root = rows[0]
            assert isinstance(root, ComponentRow)
            rows[0] = replace(root, props={"layout": "W-split-panels", "unknown": index})
            yield "invalid_contract", tuple(rows)

    def reject(*args, **kwargs):
        raise CompactDslValidationError(["invalid candidate"])

    monkeypatch.setattr(search, "_variants", variants)
    monkeypatch.setattr(search, "validate_compact_dsl", reject)
    result = search.recompose_wide_card(
        source, task_spec=context.task_spec, card_spec=context.card_spec, protocol_profile={},
        layout_scope=context.layout_scope, compact_plan=context.compact_plan,
        messages=("vertical layout overflow",), candidate_limit=limit,
    )
    assert not result.applied
    assert result.candidate_count == expected
    assert result.source_dsl == source
    assert serialize_rows(source_rows)


@pytest.mark.parametrize("second_owner,merged", [("weather", True), ("battery", False)])
def test_support_merge_never_combines_different_objects(second_owner, merged) -> None:
    rows = (
        ComponentRow("group", "Group", {"variant": "peer-pair"}, ("a", "b")),
        ComponentRow("a", "SecondaryBody", {"items": [
            {"label": "天气", "value": {"path": "/data/weather/condition"}},
        ]}),
        ComponentRow("b", "SecondaryBody", {"items": [
            {"label": "详情", "value": {"path": f"/data/{second_owner}/detail"}},
        ]}),
    )
    candidate = _merge_supporting(rows)
    assert (candidate != rows) == merged
    original_paths = binding_paths([row.props for row in rows])
    assert binding_paths([row.props for row in candidate]) == original_paths
    if merged:
        assert len(candidate) == 1
        assert len(candidate[0].props.get("items", [])) == 2


def test_dedup_keeps_static_items_and_does_not_repair_invalid_columns() -> None:
    items = [{"value": {"path": "/data/value"}}] * 2 + [{"value": "提示"}] * 2
    row = ComponentRow("body", "SecondaryBody", {"items": items, "columns": 1})
    options = _secondary_options(row, {}, False)
    compact = next(candidate for candidate in options if len(candidate.props.get("items", [])) == 3)
    assert compact.props.get("items", []).count({"value": "提示"}) == 2
    invalid = replace(row, props={**row.props, "columns": "invalid"})
    assert _secondary_options(invalid, {}, False) == [invalid]
