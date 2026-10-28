"""静态新合同：语义参数、固定贴底、原文覆盖与动态隔离。"""

import json
import re
import subprocess
from pathlib import Path

import pytest

from services.card_validation import validate_compact_dsl
from services.card_validation.compact_validation.semantic.static_content import (
    static_display_groups,
    static_group_errors,
)
from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.compact_plan import CompactPlanValidationError, parse_compact_plan_call
from services.compact_repair_strategy import CompactRepairStrategyTracker
from services.generation_content_policy import (
    EXISTING_CONTENT_POLICY,
    STATIC_CONTENT_POLICY,
    content_policy_scope,
    resolve_content_policy,
    static_layout_ids,
    static_model_components,
)
from services.static_content_context import standard_components
from services.static_content_presentation import static_presentation_candidates

REPO = Path(__file__).resolve().parents[2]
SOURCE = (
    REPO / "widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source"
)


def encode(kind, props, *, size="2x2", header=False, note=False, root_props=None):
    children = ["header"] if header else []
    children.append("body")
    rows = [["body", kind, props]]
    if header:
        rows.insert(0, ["header", "SingleLineTitle", {"title": "共同主题"}])
    if note:
        children.append("note")
        rows.append(["note", "SecondaryBody", {"items": [{"value": "共同说明"}]}])
    layout = "S-static-content" if size == "2x2" else "W-static-content"
    root = ["root", "Layout", {"layout": layout, **(root_props or {})}, children]
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in [root, *rows])


def plan_for(source, query):
    objects, shared = static_display_groups(source)
    facts = []
    groups = []
    for kind, displays in (("object", objects), ("shared", shared)):
        for display in displays:
            indexes = []
            for part in display.parts:
                indexes.append(len(facts))
                facts.append({
                    "text": part, "priority": "must", "requirement": part, "sourceTexts": [query],
                })
            groups.append({
                "id": str(len(groups)), "kind": kind, "identity": None, "factIndexes": indexes,
            })
    return {"info_required": facts, "contentGroups": groups}


def check(source, size="2x2", query="测试原文"):
    task = {
        "size": size, "userQuery": query, "dataModelSchema": {"data": {}},
        "eventCandidates": [], "assetCandidates": [],
    }
    with content_policy_scope(STATIC_CONTENT_POLICY):
        plan = plan_for(source, query)
        validate_compact_dsl(
            source, task_spec=task, card_spec={"suggestSize": size}, compact_plan=plan,
            layout_scope=f"{'S' if size == '2x2' else 'W'}-static-content-guided",
        )
        return standard_components(convert_compact_dsl_to_a2ui(source, size=size))


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("header,note", [(False, False), (True, False)])
def test_fixed_frame_keeps_header_top_and_all_content_bottom(size, header, note):
    nodes = check(encode("EmphasisText", {"mainText": "核心结论"},
                         size=size, header=header, note=note), size)
    root = nodes.get("root")
    assert root
    assert root.get("styles", {}).get("padding") == 12
    wrappers = []
    for node in nodes.values():
        styles = node.get("styles", {})
        if styles.get("layoutWeight") == 1 and styles.get("justifyContent") == "end":
            wrappers.append(node)
    assert len(wrappers) == 1
    wrapper = wrappers[0]
    assert wrapper.get("children") == (["body", "note"] if note else ["body"])
    expected = ["header", wrapper.get("id")] if header else [wrapper.get("id")]
    assert root.get("children") == expected


@pytest.mark.parametrize("count", [2, 3])
def test_text_list_derives_separator_spacing_and_typography(count):
    items = [{"primaryText": f"记录{index}", "secondaryText": "说明", "value": 20}
             for index in range(count)]
    nodes = check(encode("TextList", {"items": items}))
    dividers = [node for node in nodes.values() if node.get("component") == "Divider"]
    assert len(dividers) == count - 1
    body = nodes.get("body")
    assert body
    assert body.get("itemMargin") == (12 if count == 2 else 6)
    sizes = set()
    for node in nodes.values():
        if node.get("component") == "Text":
            styles = node.get("styles", {})
            sizes.add((styles.get("fontSize"), styles.get("fontWeight")))
    assert (12, 500) in sizes
    assert (10, 400) in sizes


def test_three_item_list_with_header_is_rejected_without_changing_spec():
    items = [{"primaryText": str(index), "secondaryText": "说明"} for index in range(3)]
    with pytest.raises(ValueError, match="含标题区时最多两项"):
        check(encode("TextList", {"items": items}, header=True))


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_single_line_list_preserves_units_and_uses_fixed_spacing(size):
    source = encode("SingleLineList", {"items": [
        {"text": "温度", "assist": "28℃"}, {"text": "湿度", "assist": "60%"},
    ]}, size=size)
    nodes = check(source, size)
    assert nodes.get("body", {}).get("itemMargin") == 4
    texts = [node.get("content") for node in nodes.values() if node.get("component") == "Text"]
    assert "28℃" in texts
    assert "60%" in texts
    assert not any(node.get("component") == "Divider" for node in nodes.values())


@pytest.mark.parametrize("kind,props", [
    ("ContentBlock", {"body": "内容"}), ("RecordList", {"items": [{"title": "内容"}]}),
    ("TableText", {"items": [{"label": "标签", "value": "值"}]}),
    ("PillButton", {"label": "操作"}), ("CardButton", {"label": "操作"}),
    ("SecondaryBody", {"items": [{"value": "辅助"}]}),
])
def test_removed_types_cannot_enter_static_route(kind, props):
    with pytest.raises(ValueError):
        check(encode(kind, props))


@pytest.mark.parametrize("field,value", [
    ("fontSize", 12), ("fontColor", "#FF000000"), ("height", 80),
    ("gap", 2), ("onClick", []), ("maxLines", 9),
])
def test_model_cannot_reintroduce_runtime_style_or_action_fields(field, value):
    with pytest.raises(ValueError):
        check(encode("EmphasisText", {"mainText": "结论", field: value}))


@pytest.mark.parametrize("variant", ["flow", "compact", "bottom-content"])
def test_fixed_frame_has_no_model_variant(variant):
    with pytest.raises(ValueError):
        check(encode("EmphasisText", {"mainText": "结论"}, root_props={"variant": variant}))


def test_capacity_and_object_coverage_are_not_relaxed():
    source = encode("SingleLineList", {"items": [
        {"text": "对象甲", "assist": "128元/月"}, {"text": "对象乙", "assist": "159元/月"},
    ]})
    with content_policy_scope(STATIC_CONTENT_POLICY):
        plan = plan_for(source, "原文")
        assert not static_group_errors(source, plan)
        assert static_group_errors(source.replace("159元/月", "128元/月"), plan)
    with pytest.raises(ValueError):
        check(encode("SingleLineList", {"items": [{"text": "说明", "assist": "很长内容" * 30}]}))


def test_action_requests_keep_existing_route_and_static_plan_rejects_action():
    selected = resolve_content_policy(
        operation="generateWidgetCardCompactDsl", enabled=True, is_edit=False,
        requested_data=False, effective_data=False, requested_events=True, effective_events=True,
    )
    assert selected == EXISTING_CONTENT_POLICY
    plan = {"info_required": [{"actionId": "action.x", "priority": "must", "requirement": "动作"}],
            "contentGroups": []}
    with content_policy_scope(STATIC_CONTENT_POLICY):
        with pytest.raises(CompactPlanValidationError):
            parse_compact_plan_call(json.dumps({"name": "submit_card_plan", "arguments": plan}),
                                    {"size": "2x2", "userQuery": "操作"})
        for size in ("2x2", "2x4"):
            assert len(static_layout_ids(size)) == 1
            assert not {"TableText", "CardButton", "PillButton"} & static_model_components(size)


def test_candidates_keep_fixed_styles_and_do_not_modify_accepted_facts():
    source = encode("SingleLineList", {"items": [
        {"text": "对象甲", "assist": "128元/月"}, {"text": "对象乙", "assist": "159元/月"},
    ]})
    with content_policy_scope(STATIC_CONTENT_POLICY):
        plan = plan_for(source, "原文")
        plan.get("info_required", [])[0]["displayRole"] = "label"
        plan.get("info_required", [])[1]["displayRole"] = "value"
        plan.get("info_required", [])[2]["displayRole"] = "label"
        plan.get("info_required", [])[3]["displayRole"] = "value"
        before = json.dumps(plan, ensure_ascii=False)
        candidates = static_presentation_candidates(plan, "2x2")
        assert candidates
        assert before == json.dumps(plan, ensure_ascii=False)
        for candidate in candidates:
            assert "fontSize" not in candidate
            assert '"variant"' not in candidate
            assert "ContentBlock" not in candidate


def test_static_capacity_drop_follows_one_unsuccessful_space_repair_and_is_bounded():
    source = encode("EmphasisText", {"mainText": "核心结论", "secondaryText": "可选补充"})
    error = [{"code": "COMPACT_DSL_VALIDATION_FAILED", "stage": "validation",
              "message": "component root: vertical layout requires at least 147vp within 126vp"}]
    with content_policy_scope(STATIC_CONTENT_POLICY):
        plan = plan_for(source, "测试原文")
        facts = plan.get("info_required", [])
        assert facts
        facts[-1]["priority"] = "should"
        tracker = CompactRepairStrategyTracker(max_repair_attempts=5, static_content=True)
        first = tracker.next_directive(source, error, compact_plan=plan, task_spec={"size": "2x2"})
        assert first.repair_strategy != "drop_optional_component"
        second = tracker.next_directive(source, error, compact_plan=plan, task_spec={"size": "2x2"})
        assert second.repair_strategy == "drop_optional_component"
        candidate = tracker.optional_drop_candidate
        assert candidate
        assert candidate.fact_indexes == (len(facts) - 1,)
        assert not candidate.contains_must_facts
        assert second.approved_omitted_fact_indexes == (len(facts) - 1,)


def test_static_syntax_errors_cannot_authorize_drop():
    source = encode("EmphasisText", {"mainText": "核心", "secondaryText": "补充"})
    error = [{"code": "COMPACT_DSL_SYNTAX_ERROR", "stage": "validation",
              "message": "Compact DSL must contain JSON array rows"}]
    with content_policy_scope(STATIC_CONTENT_POLICY):
        plan = plan_for(source, "测试原文")
        tracker = CompactRepairStrategyTracker(max_repair_attempts=5, static_content=True)
        for _index in range(3):
            directive = tracker.next_directive(
                source, error, compact_plan=plan, task_spec={"size": "2x2"},
            )
            assert directive.repair_strategy != "drop_optional_component"
            assert not directive.approved_omitted_fact_indexes


def test_static_missing_reference_does_not_enter_early_capacity_drop():
    source = encode("EmphasisText", {"mainText": "核心", "secondaryText": "补充"})
    errors = [{
        "code": "COMPACT_DSL_VALIDATION_FAILED", "stage": "validation",
        "message": "语义布局不符合合同：节点 body：引用了不存在的组件。",
    }]
    with content_policy_scope(STATIC_CONTENT_POLICY):
        plan = plan_for(source, "测试原文")
        tracker = CompactRepairStrategyTracker(max_repair_attempts=5, static_content=True)
        for _index in range(2):
            directive = tracker.next_directive(
                source, errors, compact_plan=plan, task_spec={"size": "2x2"},
            )
            assert directive.repair_strategy != "drop_optional_component"
            assert not directive.approved_omitted_fact_indexes


def test_single_subject_name_can_move_to_header_without_forcing_it_into_emphasis():
    source = encode("EmphasisText", {"mainText": "周六开放"}, header=True)
    source = source.replace("共同主题", "示例馆")
    plan = {
        "info_required": [
            {"text": "示例馆", "priority": "must", "displayRole": "title"},
            {"text": "周六开放", "priority": "must", "displayRole": "body"},
        ],
        "contentGroups": [{"id": "venue", "kind": "object", "identity": "示例馆",
                           "factIndexes": [0, 1]}],
    }
    with content_policy_scope(STATIC_CONTENT_POLICY):
        assert not static_group_errors(source, plan)
        candidates = static_presentation_candidates(plan, "2x2")
        assert candidates
        emphasis = []
        for line in candidates[0].splitlines():
            row = json.loads(line)
            if len(row) > 2 and row[1] == "EmphasisText":
                emphasis.append(row)
        assert emphasis and emphasis[0][2].get("mainText") == "周六开放"
        assert '"SecondaryBody"' not in candidates[0]


def examples():
    result = []
    for size in ("2x2", "2x4"):
        text = (SOURCE / f"static_content/fewshots/{size}.md").read_text(encoding="utf-8")
        for raw, source in re.findall(r"```json\s*(.*?)```\s*```genui\s*(.*?)```", text, re.S):
            result.append((size, json.loads(raw), source))
    return result


@pytest.mark.parametrize("size,task,source", examples())
def test_all_migrated_examples_pass_same_geometry_and_coverage_checks(size, task, source):
    check(source, size, task.get("userQuery", ""))


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_migration_adds_no_input_facts_or_domains(size):
    path = f"widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/" \
           f"prompt_source/static_content/fewshots/{size}.md"
    original = subprocess.check_output(["git", "show", f"e4497adb:{path}"], cwd=REPO).decode()
    old_inputs = []
    for raw in re.findall(r"```json\s*(.*?)```", original, re.S):
        task = json.loads(raw)
        if not task.get("eventCandidates"):
            old_inputs.append(task)
    new_inputs = [task for item_size, task, _source in examples() if item_size == size]
    assert new_inputs == old_inputs
