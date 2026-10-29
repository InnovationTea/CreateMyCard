"""静态分组错误不能遮住同源可确认的展开容量，原阻断及非静态路径保持。"""

import json
import socket

import pytest

from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.card_validation.compact_validation import api
from services.card_validation.compact_validation.semantic.static_content import static_group_errors
from services.compact_dsl_a2ui_converter import CompactDslConversionError
from services.compact_layout_runtime import CompactLayoutRuntimeError
from services.compact_repair_strategy import CompactRepairStrategyTracker
from services.generation_content_policy import (
    EXISTING_CONTENT_POLICY,
    STATIC_CONTENT_POLICY,
    content_policy_scope,
)
from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext
from services.protocol_registry import A2UIProtocolRegistry


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def reject(*_args, **_kwargs):
        raise AssertionError("联合诊断测试不得访问网络")

    monkeypatch.setattr(socket.socket, "connect", reject)
    monkeypatch.setattr(socket.socket, "connect_ex", reject)


def make_case(*, long_values=True, missing_shared=True):
    seasons = ("春季", "夏季", "秋季", "冬季")
    values = (
        "每4至5天一次", "每2至3天一次，早晚喷雾", "每5至7天一次", "每10至14天一次，水温接近室温",
    )
    facts = []
    groups = []
    items = []
    for index, season in enumerate(seasons):
        facts.append({"text": season, "priority": "must", "componentHints": ["SingleLineList"]})
        groups.append({"id": f"season{index}", "kind": "object", "identity": season,
                       "factIndexes": [index]})
        items.append({"text": season, "assist": values[index] if long_values else "适量"})
    if missing_shared:
        facts.append({"text": "盆土表面下2厘米干透再浇，忌积水", "priority": "must"})
        groups.append({"id": "shared_topic", "kind": "shared", "factIndexes": [4]})
    rows = [
        ["root", "Layout", {"layout": "S-static-content"}, ["header", "body"]],
        ["header", "SingleLineTitle", {"title": "绿萝浇水频率"}],
        ["body", "SingleLineList", {"items": items}],
    ]
    source = "\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows)
    plan = {"info_required": facts, "contentGroups": groups}
    return source, plan


def make_valid_case(policy):
    if policy.is_static:
        return make_case(long_values=False, missing_shared=False)
    rows = [
        ["root", "Column", {"width": "matchParent", "height": "matchParent"}, ["body"]],
        ["body", "EmphasisText", {"mainText": "提醒"}],
    ]
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows), None


def validate(source, plan, **kwargs):
    return validate_compact_dsl(
        source,
        task_spec={"size": "2x2", "dataModelSchema": {"data": {}},
                   "eventCandidates": [], "assetCandidates": []},
        card_spec={"suggestSize": "2x2"}, compact_plan=plan, **kwargs,
    )


def test_real_missing_shared_and_single_line_capacity_are_both_reported():
    source, plan = make_case()
    with content_policy_scope(STATIC_CONTENT_POLICY):
        group_errors = static_group_errors(source, plan)
        with pytest.raises(CompactDslValidationError) as raised:
            validate(source, plan)
    error = raised.value
    assert list(error.errors[:len(group_errors)]) == group_errors
    assert any("shared_topic" in message for message in error.errors)
    assert "body.item1_assist 完整文字需要 2 行，92.8vp 区域仅允许 1 行" in error.errors[-1]
    assert [item.code for item in error.diagnostics].count("COMPACT_STATIC_TEXT_CAPACITY") == 1
    assert isinstance(error.__cause__, CompactDslConversionError)


def test_static_group_failure_still_blocks_when_expansion_succeeds(monkeypatch):
    source, plan = make_case(long_values=False)
    calls = []
    original_expand = api.expand_high_level_component_rows

    def expand(*args, **kwargs):
        calls.append(True)
        return original_expand(*args, **kwargs)

    monkeypatch.setattr(api, "expand_high_level_component_rows", expand)
    with content_policy_scope(STATIC_CONTENT_POLICY):
        group_errors = static_group_errors(source, plan)
        with pytest.raises(CompactDslValidationError) as raised:
            validate(source, plan)
    assert calls == [True]
    assert list(raised.value.errors) == group_errors


def test_static_group_and_unknown_conversion_error_preserve_both_and_cause(monkeypatch):
    source, plan = make_case()
    original_error = CompactDslConversionError("原始组件合同失败，不属于容量")

    def fail(*_args, **_kwargs):
        raise original_error

    monkeypatch.setattr(api, "expand_high_level_component_rows", fail)
    with content_policy_scope(STATIC_CONTENT_POLICY):
        group_errors = static_group_errors(source, plan)
        with pytest.raises(CompactDslValidationError) as raised:
            validate(source, plan)
    assert list(raised.value.errors) == [*group_errors, str(original_error)]
    assert raised.value.__cause__ is original_error
    assert all(item.code != "COMPACT_STATIC_TEXT_CAPACITY" for item in raised.value.diagnostics)


def test_layout_error_is_appended_once_after_original_group_and_capacity(monkeypatch):
    source, plan = make_case()

    def fail_layout(*_args, **_kwargs):
        raise CompactLayoutRuntimeError("原布局失败")

    monkeypatch.setattr(api, "match_compact_layout", fail_layout)
    with content_policy_scope(STATIC_CONTENT_POLICY):
        with pytest.raises(CompactDslValidationError) as raised:
            validate(source, plan, layout_scope="S-static-content")
    assert raised.value.errors[-1] == "原布局失败"
    assert raised.value.errors.count("原布局失败") == 1
    assert "COMPACT_STATIC_TEXT_CAPACITY" in raised.value.errors[-2]


@pytest.mark.parametrize("policy", [STATIC_CONTENT_POLICY, EXISTING_CONTENT_POLICY])
def test_other_original_error_does_not_start_expansion(monkeypatch, policy):
    source, plan = make_valid_case(policy)

    def original_error(_components, errors):
        errors.append("既有动作文字错误")

    def forbidden_expand(*_args, **_kwargs):
        raise AssertionError("无静态分组错误的原阻断路径不得进入展开")

    monkeypatch.setattr(api, "_collect_action_label_length_errors", original_error)
    monkeypatch.setattr(api, "expand_high_level_component_rows", forbidden_expand)
    with content_policy_scope(policy):
        with pytest.raises(CompactDslValidationError) as raised:
            validate(source, plan)
    assert raised.value.errors == ("既有动作文字错误",)


@pytest.mark.parametrize("message,structured", [
    ("COMPACT_STATIC_TEXT_CAPACITY: 原容量错误", True),
    ("原普通转换错误", False),
])
@pytest.mark.parametrize("policy", [STATIC_CONTENT_POLICY, EXISTING_CONTENT_POLICY])
def test_no_original_error_keeps_conversion_error_behavior(
    monkeypatch, policy, message, structured,
):
    source, plan = make_valid_case(policy)
    original_error = CompactDslConversionError(message)

    def fail(*_args, **_kwargs):
        raise original_error

    monkeypatch.setattr(api, "expand_high_level_component_rows", fail)
    with content_policy_scope(policy):
        with pytest.raises(CompactDslValidationError) as raised:
            validate(source, plan)
    assert raised.value.errors == (message,)
    assert bool(raised.value.diagnostics) is structured
    assert raised.value.__cause__ is original_error


@pytest.mark.parametrize("policy", [STATIC_CONTENT_POLICY, EXISTING_CONTENT_POLICY])
def test_no_original_error_only_expands_once(monkeypatch, policy):
    source, plan = make_valid_case(policy)
    original_expand = api.expand_high_level_component_rows
    calls = []

    def expand(*args, **kwargs):
        calls.append(True)
        return original_expand(*args, **kwargs)

    monkeypatch.setattr(api, "expand_high_level_component_rows", expand)
    with content_policy_scope(policy):
        validate(source, plan)
    assert calls == [True]


@pytest.mark.parametrize("source", [
    "not a valid compact source",
    '["root", "Text", {"content": "静态源禁止基础文字"}]',
])
def test_invalid_static_source_does_not_reach_expansion(monkeypatch, source):
    def forbidden_expand(*_args, **_kwargs):
        raise AssertionError("无效源不得进入展开")

    monkeypatch.setattr(api, "expand_high_level_component_rows", forbidden_expand)
    with content_policy_scope(STATIC_CONTENT_POLICY):
        with pytest.raises(CompactDslValidationError):
            validate(source, None)


def add_value_facts(source, plan):
    rows = [json.loads(line) for line in source.splitlines()]
    body = rows[2][2]
    facts = [{"text": "绿萝浇水频率", "priority": "must", "displayRole": "title"}]
    groups = [{"id": "shared_title", "kind": "shared", "factIndexes": [0]}]
    items = body.get("items")
    assert isinstance(items, list)
    for index, item in enumerate(items):
        label = item.get("text")
        value = item.get("assist")
        assert isinstance(label, str)
        assert isinstance(value, str)
        start = len(facts)
        facts.extend([
            {"text": label, "priority": "must", "componentHints": ["SingleLineList"]},
            {"text": value, "priority": "must", "componentHints": ["SingleLineList"]},
        ])
        groups.append({"id": f"season{index}", "kind": "object", "identity": label,
                       "factIndexes": [start, start + 1]})
    groups.append({"id": "shared_topic", "kind": "shared", "factIndexes": [len(facts)]})
    original_facts = plan.get("info_required")
    assert isinstance(original_facts, list)
    facts.append(original_facts[-1])
    return {"info_required": facts, "contentGroups": groups}


@pytest.mark.parametrize("has_value_facts", [False, True])
def test_processor_joint_errors_reach_existing_capacity_and_guarded_drop(has_value_facts):
    source, plan = make_case()
    if has_value_facts:
        plan = add_value_facts(source, plan)
    task = {"size": "2x2", "dataModelSchema": {"data": {}},
            "eventCandidates": [], "assetCandidates": []}
    profile = A2UIProtocolRegistry("a2ui-form-rom6.0-v1").get_profile()
    context = DslProcessingContext(
        size="2x2", task_spec=task, card_spec={"suggestSize": "2x2"},
        protocol_profile=profile, design_profile_id="design-compact-dsl",
        compact_plan=plan, content_policy=STATIC_CONTENT_POLICY,
        layout_scope="S-static-content-guided", colorless_layout=True,
    )
    result = DesignCompactProcessor().process(source, context)
    assert result.source_dsl == source
    assert not result.standard_dsl
    issues = [item.to_diagnostic_payload() for item in result.errors]
    assert any("COMPACT_STATIC_CORE_MISSING" in item.get("message", "") for item in issues)
    assert any("body.item1_assist" in item.get("message", "") for item in issues)
    with content_policy_scope(STATIC_CONTENT_POLICY):
        tracker = CompactRepairStrategyTracker(static_content=True, max_repair_attempts=5)
        first = tracker.next_directive(source, issues, compact_plan=plan, task_spec=task)
        assert first.category == "layout_capacity"
        assert first.repair_strategy == "rebudget"
        assert first.optional_drop is None
        assert first.approved_omitted_fact_indexes == ()
        second = tracker.next_directive(source, issues, compact_plan=plan, task_spec=task)
    assert second.category == "layout_capacity"
    assert len(second.capacity_fits) == 1
    expected_facts = [{"factIndex": 4}] if has_value_facts else []
    assert second.capacity_fits[0].get("doesNotFit") == [
        {"itemIndex": 1, "property": "assist", "planFacts": expected_facts},
    ]
    if has_value_facts:
        assert second.optional_drop is not None
        assert second.optional_drop.fact_indexes == (4,)
        assert second.approved_omitted_fact_indexes == (4,)
    else:
        assert second.optional_drop is None
        assert second.approved_omitted_fact_indexes == ()
