"""小卡双动作槽的固定角色、容量与事实保护。"""

import copy
import json

import pytest

from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    ComponentRow,
    convert_compact_dsl_to_a2ui,
    parse_compact_dsl_rows,
)


def _case(pure: bool) -> tuple[dict, dict, list]:
    task = {"size": "2x2", "userQuery": "打开两个入口", "assetCandidates": [],
            "eventCandidates": [], "dataModelSchema": {"data": {}}}
    facts = []
    children = ["first", "second"] if pure else ["value", "first", "second"]
    props = {"layout": "S-content-dual-action"}
    if pure:
        props["variant"] = "actions-only"
    rows = [["root", "Layout", props, children]]
    if not pure:
        task["dataModelSchema"]["data"] = {"sample": {
            "percent": {"type": "number", "sampleValue": 32},
        }}
        facts.append({"dataId": "/data/sample/percent", "priority": "must", "requirement": "比例"})
        rows.append(["value", "EmphasizedData", {
            "value": {"path": "/data/sample/percent"}, "unit": "%", "fontSize": 30,
        }])
        rows.append(["/data/sample/percent", 32])
    for name in ("first", "second"):
        handler = {"call": "open", "args": {"target": name}}
        task["eventCandidates"].append({"id": name, **handler})
        facts.append({"actionId": name, "priority": "must", "requirement": "操作"})
        component = "CardButton" if pure else "PillButton"
        rows.append([name, component, {"label": "打开", "onClick": [handler]}])
    plan = {"info_required": facts, "layoutHints": ["S-content-dual-action"]}
    return task, plan, rows


def _source(rows: list) -> str:
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


@pytest.mark.parametrize("pure,expected_height", [(False, 36), (True, 57)])
def test_dual_action_buttons_validate_and_keep_slot_geometry(
    pure: bool, expected_height: int,
) -> None:
    task, plan, rows = _case(pure)
    source = _source(rows)
    result = validate_compact_dsl(
        source, task_spec=task, compact_plan=plan, card_spec={"suggestSize": "2x2"},
        enforce_model_component_types=True,
    )
    assert not result.warnings
    parsed = parse_compact_dsl_rows(source, size="2x2")
    if pure:
        buttons = [
            row for row in parsed
            if isinstance(row, ComponentRow) and row.component_type == "CardButton"
        ]
        assert len(buttons) == 2
        assert all(row.props.get("height") == expected_height for row in buttons)
    else:
        action_slots = [
            row
            for row in parsed
            if isinstance(row, ComponentRow)
            and row.component_type == "Column"
            and row.props.get("height") == expected_height
            and len(row.children) == 1
        ]
        assert len(action_slots) == 2
    output = convert_compact_dsl_to_a2ui(source, size="2x2")
    messages = [json.loads(line) for line in output.splitlines()]
    components = messages[1].get("updateComponents", {}).get("components", [])
    assert len([row for row in components if row.get("onClick")]) == 2
    assert not any(row.get("component") == "PillButton" for row in components)


@pytest.mark.parametrize(
    ("pure", "kind", "expected"),
    [
        (False, "CardButton", "PillButton"),
        (False, "CircleButton", "PillButton"),
        (True, "PillButton", "CardButton"),
        (True, "CircleButton", "CardButton"),
        (True, "InfoBlock", "CardButton"),
    ],
)
def test_dual_action_roles_reject_other_components(
    pure: bool, kind: str, expected: str,
) -> None:
    _, _, rows = _case(pure)
    rows[-1][1] = kind
    with pytest.raises(CompactDslConversionError, match=expected):
        convert_compact_dsl_to_a2ui(_source(rows), size="2x2")


@pytest.mark.parametrize("prop,value", [("height", 30), ("width", 100), ("padding", 0)])
def test_model_cannot_resize_the_new_buttons(prop: str, value: int) -> None:
    _, _, rows = _case(False)
    rows[-1][2][prop] = value
    with pytest.raises(CompactDslConversionError, match="几何"):
        convert_compact_dsl_to_a2ui(_source(rows), size="2x2")


def test_standard_slot_cannot_use_two_line_label() -> None:
    _, _, rows = _case(False)
    rows[-1][2]["labelLines"] = 2
    with pytest.raises(CompactDslConversionError, match="单行"):
        convert_compact_dsl_to_a2ui(_source(rows), size="2x2")


def test_pure_action_slot_keeps_card_button_two_line_contract() -> None:
    _, _, rows = _case(True)
    rows[-1][2]["labelLines"] = 2
    converted = convert_compact_dsl_to_a2ui(_source(rows), size="2x2")
    assert '"maxLines":2' in converted


@pytest.mark.parametrize(
    ("size", "label", "icon", "keep_icon"),
    [
        ("2x2", "屏幕时长管控", "switch.svg", False),
        ("2x4", "打车去公司", "car.svg", False),
        ("2x2", "ABCDEF", "switch.svg", True),
        ("2x4", "打车", None, True),
        ("2x2", "屏幕时长管控", None, False),
    ],
)
def test_card_button_icon_yields_to_label_width(size, label, icon, keep_icon) -> None:
    handler = {"call": "open", "args": {"target": "first"}}
    props = {"label": label, "onClick": [handler]}
    if icon is not None:
        props["icon"] = "resources/base/media/" + icon
    if size == "2x2":
        _, _, rows = _case(True)
        rows[1][2] = props
        button_id = "first"
    else:
        button_id = "lower"
        rows = [
            ["root", "Layout", {"layout": "W-content-side-slots"}, ["body", "upper", "lower"]],
            ["body", "Region", {"variant": "title-content"}, ["title", "main"]],
            ["title", "SingleLineTitle", {"title": "天气"}],
            ["main", "EmphasisText", {"mainText": "小雨"}],
            ["upper", "InfoBlock", {"variant": "slot", "primaryText": "75%",
                                   "secondaryText": "降水概率", "backgroundColor": "#33000000"}],
            [button_id, "CardButton", props],
        ]
    output = convert_compact_dsl_to_a2ui(_source(rows), size=size)
    by_id = _nodes_by_id(output)
    button = by_id.get(button_id)
    text = by_id.get(button_id + "_label")
    assert button is not None and text is not None
    assert button.get("onClick") == [handler]
    assert text.get("content") == label
    assert text.get("styles", {}).get("maxLines") == 1
    assert (button_id + "_visual" in by_id) is keep_icon
    assert button.get("itemMargin") == (8 if keep_icon else 0)


def _nodes_by_id(output: str) -> dict:
    update = json.loads(output.splitlines()[1]).get("updateComponents")
    assert update is not None
    nodes = update.get("components")
    assert isinstance(nodes, list)
    return {node.get("id"): node for node in nodes}


@pytest.mark.parametrize(("height", "expected_lines"), [(57, 2), (36, 1)])
def test_icon_free_label_wraps_only_in_a_tall_enough_slot(height, expected_lines) -> None:
    rows = [
        ["root", "Column", {"width": "matchParent", "height": "matchParent"}, ["slot"]],
        ["slot", "Column", {"width": 78, "height": height}, ["action"]],
        ["action", "CardButton", {
            "label": "屏幕时长管控", "width": "matchParent", "height": "matchParent",
            "onClick": [{"call": "open", "args": {}}],
        }],
    ]
    output = convert_compact_dsl_to_a2ui(_source(rows), size="2x4")
    by_id = _nodes_by_id(output)
    button = by_id.get("action")
    text = by_id.get("action_label")
    assert button is not None and text is not None
    assert button.get("children") == ["action_label"]
    assert text.get("styles", {}).get("maxLines") == expected_lines
    assert text.get("styles", {}).get("fontSize") == 14


def test_card_button_is_not_a_single_action_substitute() -> None:
    rows = [["root", "Layout", {"layout": "S-title-content-action"}, ["title", "body", "action"]],
            ["title", "SingleLineTitle", {"title": "测试", "fontSize": 12}],
            ["body", "EmphasisText", {"mainText": "状态", "fontSize": 18}],
            ["action", "CardButton", {"label": "打开", "onClick": [{"call": "open", "args": {}}]}]]
    with pytest.raises(CompactDslConversionError, match="PillButton"):
        convert_compact_dsl_to_a2ui(_source(rows), size="2x2")


def test_dynamic_body_cannot_be_moved_into_button_label() -> None:
    task, plan, rows = _case(False)
    rows[-1][2]["label"] = {"path": "/data/sample/percent"}
    with pytest.raises(CompactDslValidationError, match="static"):
        validate_compact_dsl(_source(rows), task_spec=task, compact_plan=plan,
                             card_spec={"suggestSize": "2x2"})


def test_actions_only_still_requires_all_display_facts() -> None:
    task, plan, rows = _case(True)
    plan = copy.deepcopy(plan)
    plan["info_required"].append({"text": "必须显示", "priority": "must", "requirement": "正文"})
    with pytest.raises(CompactDslValidationError, match="no body or data display facts"):
        validate_compact_dsl(_source(rows), task_spec=task, compact_plan=plan,
                             card_spec={"suggestSize": "2x2"})
