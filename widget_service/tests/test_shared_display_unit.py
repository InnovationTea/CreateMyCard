"""双指标共享单位的分区边界与心率别名回归。"""

import json

import pytest

from services.card_validation.context import ValidationContext
from services.card_validation.diagnostics import Reporter
from services.card_validation.display_unit_rules import (
    DisplayUnitRule,
    matching_unit_literal_count,
    static_text_exactly_matches_rule,
)
from services.card_validation.display_unit_validator import DisplayUnitValidator
from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui


def _context(title="心率 · 次/分", other_root="health", other_unit="次/分钟"):
    components = [
        {"id": "root", "component": "Column", "children": ["header", "metrics"]},
        {"id": "header", "component": "Row", "children": ["icon", "title"]},
        {"id": "icon", "component": "Image", "src": "heart.svg"},
        {"id": "title", "component": "Text", "content": title},
        {"id": "metrics", "component": "Row", "children": ["left", "right"]},
        {"id": "left", "component": "Column", "children": ["maximum", "max_label"]},
        {"id": "right", "component": "Column", "children": ["minimum", "min_label"]},
        {"id": "maximum", "component": "Text", "content": "{{ ${/data/health/max} }}"},
        {"id": "minimum", "component": "Text",
         "content": "{{ ${/data/" + other_root + "/min} }}"},
        {"id": "max_label", "component": "Text", "content": "最高"},
        {"id": "min_label", "component": "Text", "content": "最低"},
    ]
    bindings = []
    capabilities = {}
    for root in dict.fromkeys(["health", other_root]):
        bindings.append({"capabilityId": root, "writeResultTo": "/data/" + root})
        capabilities[root] = {
            "id": root,
            "outputSchema": {"type": "object", "properties": {
                "max": {"type": "integer", "displayUnits": ["次/分钟"], "unitIncluded": False},
                "min": {"type": "integer", "displayUnits": [other_unit], "unitIncluded": False},
            }},
        }
    return ValidationContext(
        components=components,
        components_by_id={item.get("id"): item for item in components},
        cardspec={"dataBindings": bindings},
        effective_data_capabilities=capabilities,
    )


def _validate(context):
    reporter = Reporter()
    DisplayUnitValidator().validate(context, None, reporter)
    return reporter


@pytest.mark.parametrize("title", ["心率 · 次/分", "心率（次/分钟）", "心率: 次/分钟"])
def test_shared_title_covers_pair(title):
    assert not _validate(_context(title)).has_error()


@pytest.mark.parametrize("title", ["心率", "心率 · 次/分数", "次数/分钟统计"])
def test_title_requires_explicit_complete_unit(title):
    assert _validate(_context(title)).error_count == 2


def test_different_business_cannot_share_unit():
    assert _validate(_context(other_root="weather")).error_count == 2


def test_different_units_cannot_share_title():
    assert _validate(_context(other_unit="℃")).error_count == 2


def test_title_in_sibling_panel_cannot_supply_unit():
    context = _context()
    header = context.components_by_id.get("header")
    assert header is not None
    header["component"] = "Column"
    assert _validate(context).error_count == 2


def test_title_outside_nearest_panel_cannot_supply_unit():
    context = _context()
    root = context.components_by_id.get("root")
    assert root is not None
    root["children"] = ["header", "panel"]
    panel = {"id": "panel", "component": "Column", "children": ["metrics"]}
    context.components.append(panel)
    context.components_by_id["panel"] = panel
    assert _validate(context).error_count == 2


def test_inline_duplicate_still_rejected_with_shared_title():
    context = _context()
    maximum = context.components_by_id.get("maximum")
    assert maximum is not None
    maximum["content"] = "{{ ${/data/health/max} + '次/分' + '次/分钟' }}"
    assert _validate(context).has_code("DISPLAY_UNIT_DUPLICATED")


def test_third_dynamic_field_prevents_shared_title_exemption():
    context = _context()
    label = context.components_by_id.get("max_label")
    assert label is not None
    label["content"] = "{{ ${/data/weather/temperature} }}"
    assert _validate(context).error_count == 2


def test_single_metric_does_not_gain_shared_title_exemption():
    context = _context()
    minimum = context.components_by_id.get("minimum")
    assert minimum is not None
    minimum["content"] = "96"
    assert _validate(context).error_count == 1


def test_different_objects_under_same_binding_cannot_share_title():
    context = _context()
    minimum = context.components_by_id.get("minimum")
    assert minimum is not None
    minimum["content"] = "{{ ${/data/health/other/min} }}"
    capability = context.effective_data_capabilities.get("health")
    assert capability is not None
    schema = capability.get("outputSchema")
    assert isinstance(schema, dict)
    properties = schema.get("properties")
    assert isinstance(properties, dict)
    minimum_schema = properties.get("min")
    assert isinstance(minimum_schema, dict)
    properties["other"] = {"type": "object", "properties": {"min": minimum_schema}}
    assert _validate(context).error_count == 2


def test_shared_title_inside_business_panel_is_accepted():
    context = _context()
    panel = context.components_by_id.get("root")
    assert panel is not None
    panel["id"] = "health_panel"
    context.components_by_id.pop("root")
    context.components_by_id["health_panel"] = panel
    root = {"id": "root", "component": "Row", "children": ["health_panel", "weather"]}
    weather = {"id": "weather", "component": "Text",
               "content": "{{ ${/data/weather/temperature} }}"}
    context.components.extend([root, weather])
    context.components_by_id.update({"root": root, "weather": weather})
    assert not _validate(context).has_error()


def test_logged_compact_structure_after_conversion():
    context = _context()
    rows = [
        ["root", "Column", {"padding": 12, "justifyContent": "start"},
         ["header", "metrics"]],
        ["header", "CardHeader", {"title": "心率 · 次/分", "fontColor": "#FFFFFFFF"}],
    ]
    for component in context.components:
        if component.get("id") in {"root", "header", "icon", "title"}:
            continue
        props = {}
        if component.get("component") == "Text":
            props["content"] = component.get("content")
        row = [component.get("id"), component.get("component"), props]
        if "children" in component:
            row.append(component.get("children"))
        rows.append(row)
    rows.append(["/data/health", {"max": 168, "min": 96}])
    compact = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    standard = convert_compact_dsl_to_a2ui(compact, size="2x2")
    update = json.loads(standard.splitlines()[1]).get("updateComponents")
    assert isinstance(update, dict)
    components = update.get("components")
    assert isinstance(components, list)
    context.components = components
    context.components_by_id = {item.get("id"): item for item in components}
    assert not _validate(context).has_error()


@pytest.mark.parametrize("declared", ["次/分", "次/分钟"])
@pytest.mark.parametrize("shown", ["次/分", "次/分钟"])
def test_heart_rate_aliases_are_bidirectional(declared, shown):
    rule = DisplayUnitRule((declared,), False)
    assert static_text_exactly_matches_rule(shown, rule)
    assert matching_unit_literal_count("{{ ${/data/health/max} + '" + shown + "' }}", rule) == 1
