"""验证统一入口选择规则，以及模板仍被通用约束拦截。"""

import json
from dataclasses import replace

import pytest

from services.card_validation import CompactDslValidationError, validate_card, validate_compact_dsl
from services.card_validation import validation_policy as policies
from services.card_validation.validation_policy import CompactRule


def _input(template: bool, size: str = "2x2") -> tuple[list[list], dict]:
    rows = [
        ["root", "Stack", {}, ["template_root" if template else "content"]],
        ["template_root" if template else "content", "Column", {"height": 136}, ["value", "other"]],
        ["value", "Text", {"content": "{{ ${/data/weather/level} }}", "fontSize": 14}],
        ["other", "Text", {"content": "{{ ${/data/battery/level} }}", "fontSize": 14}],
        ["/data/weather/level", "弱"],
        ["/data/battery/level", "正常"],
    ]
    spec = {
        "size": size,
        "assetCandidates": [],
        "eventCandidates": [],
        "dataModelSchema": {"data": {
            "weather": {"level": {
                "type": "string", "description": "紫外线等级", "sampleValue": "弱",
            }},
            "battery": {"level": {
                "type": "string", "description": "电池状态", "sampleValue": "正常",
            }},
        }},
    }
    return rows, spec


def _validate(rows: list[list], spec: dict) -> None:
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    validate_compact_dsl(source, task_spec=spec, card_spec={"suggestSize": spec.get("size")})


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_template_uses_its_design_rules_while_standard_keeps_layout_and_label_checks(size):
    rows, spec = _input(True, size)
    _validate(rows, spec)
    ordinary, spec = _input(False, size)
    with pytest.raises(CompactDslValidationError) as caught:
        _validate(ordinary, spec)
    assert any("ambiguous meaning" in error for error in caught.value.errors)
    assert any("must use" in error for error in caught.value.errors)


def test_template_can_select_one_design_rule_without_enabling_other_design_rules(monkeypatch):
    selected = replace(
        policies.TEMPLATE_VALIDATION_POLICY,
        compact_rules=(
            policies.TEMPLATE_VALIDATION_POLICY.compact_rules | {CompactRule.METRIC_LABEL}
        ),
    )
    monkeypatch.setattr(policies, "TEMPLATE_VALIDATION_POLICY", selected)
    rows, spec = _input(True)
    with pytest.raises(CompactDslValidationError) as caught:
        _validate(rows, spec)
    assert any("ambiguous meaning" in error for error in caught.value.errors)
    assert not any("must use S4" in error for error in caught.value.errors)


@pytest.mark.parametrize(("change", "message"), [
    ("asset", "original src"),
    ("event", "onClick"),
    ("binding", "not declared"),
    ("missing-data", "no matching"),
    ("height", "vertical layout"),
    ("empty", "non-empty"),
])
def test_template_keeps_common_checks(change: str, message: str):
    rows, spec = _input(True)
    if change == "asset":
        rows[2] = ["value", "Image", {"src": "resources/not-approved.svg"}]
    elif change == "event":
        rows[2][2]["onClick"] = [{"call": "clickToIntent", "args": {"intentName": "Bad"}}]
    elif change == "binding":
        rows[2][2]["content"] = "{{ ${/data/unknown/value} }}"
    elif change == "missing-data":
        rows.pop(4)
    elif change == "height":
        rows[2][2]["height"] = 200
    else:
        rows[1][3] = []
    with pytest.raises(CompactDslValidationError, match=message):
        _validate(rows, spec)


@pytest.mark.parametrize("marker", ["missing", "orphan", "nested", "prefix"])
def test_invalid_marker_never_selects_template_rules(marker):
    rows, spec = _input(True)
    if marker == "missing":
        rows[1][0] = "content"
    elif marker == "orphan":
        rows[0][3] = ["other"]
    elif marker == "nested":
        rows[0][3] = ["wrapper"]
        rows.append(["wrapper", "Column", {}, ["template_root"]])
    else:
        rows[0][3] = ["template_root_0"]
        rows[1][0] = "template_root_0"
    with pytest.raises(CompactDslValidationError):
        _validate(rows, spec)


def test_repair_reselects_rules_after_template_marker_removed():
    rows, spec = _input(True)
    _validate(rows, spec)
    rows[0][3] = ["content"]
    rows[1][0] = "content"
    with pytest.raises(CompactDslValidationError, match="must use S4"):
        _validate(rows, spec)


def test_duplicate_parsed_component_ids_never_select_template_rules():
    policy = policies.resolve_validation_policy(
        root_id="root", root_children=("template_root",),
        component_ids=("root", "template_root", "value", "value"),
    )
    assert policy == policies.STANDARD_VALIDATION_POLICY


def test_a2ui_entry_can_select_contrast_for_templates(monkeypatch):
    messages = [
        {"version": "v0.9", "createSurface": {"surfaceId": "card"}},
        {"version": "v0.9", "updateComponents": {
            "surfaceId": "card", "root": "root", "components": [
                {"id": "root", "component": "Column", "children": ["template_root"],
                 "styles": {"backgroundColor": "#FFFFFFFF"}},
                {"id": "template_root", "component": "Text", "content": "白底白字",
                 "styles": {"fontColor": "#FFFFFFFF", "fontSize": 14}},
            ],
        }},
        {"version": "v0.9", "updateDataModel": {
            "surfaceId": "card", "path": "/", "value": {},
        }},
    ]
    source = "\n".join(json.dumps(message) for message in messages)
    assert not validate_card(dsl_text=source).has_code("VISUAL.CONTRAST")
    selected = replace(
        policies.TEMPLATE_VALIDATION_POLICY,
        a2ui_validators=policies.TEMPLATE_VALIDATION_POLICY.a2ui_validators | {"contrast"},
    )
    monkeypatch.setattr(policies, "TEMPLATE_VALIDATION_POLICY", selected)
    assert validate_card(dsl_text=source).has_code("VISUAL.CONTRAST")
