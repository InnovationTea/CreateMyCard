# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""模板进度环经过公共转换后保留尺寸，普通卡片沿用尺寸规则。"""

from __future__ import annotations

import json
from typing import Any

import pytest

from services.compact_dsl_a2ui_converter import (
    ComponentRow,
    _normalize_ring_stack_children,
    convert_compact_dsl_to_a2ui,
)
from services.generation_pipeline import DslProcessorKind
from services.template_generation.engine.cardplan.compiler import (
    _compile_ux_layout_shell,
    _instantiate_blueprint,
    _serialize_node,
    _strip_advanced_component_markers,
)
from services.template_generation.engine.cardplan.fusion_ball_background import (
    FusionBallPalette,
    apply_content_safe_inset,
    apply_fusion_ball_background,
)
from services.template_generation.engine.cardplan.models import HybridBodyContract
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.tersel_converter import convert_tersel_to_a2ui
from services.template_generation.source_adapter import prepare_template_source_dsl


def _ring_rows() -> list[ComponentRow]:
    return [
        ComponentRow("root", "Stack", {}, ("template_root", "outside")),
        ComponentRow("template_root", "Column", {}, ("row",)),
        ComponentRow("row", "Row", {"height": 36}, ("ring_stack",)),
        ComponentRow("ring_stack", "Stack", {"width": 36, "height": 36}, ("ring", "icon")),
        ComponentRow("ring", "Progress", {
            "type": "ring", "value": {"path": "/data/batterySOC"}, "total": 100,
            "width": 36, "height": 36, "strokeWidth": 4,
        }),
        ComponentRow("icon", "Image", {
            "src": "resources/base/media/battery_leaf_fill.svg", "width": 12, "height": 12,
        }),
        ComponentRow("outside", "Progress", {
            "type": "ring", "value": 68, "total": 100,
            "width": 36, "height": 36, "strokeWidth": 4,
        }),
    ]


def _convert(rows: list[ComponentRow], size: str = "2x2") -> list[dict[str, Any]]:
    values: list[list[Any]] = []
    for row in rows:
        value: list[Any] = [row.component_id, row.component_type, row.props]
        if row.children:
            value.append(list(row.children))
        values.append(value)
    values.append(["/data/batterySOC", 68])
    compact = "\n".join(json.dumps(value) for value in values)
    return _components(convert_compact_dsl_to_a2ui(compact, size=size))


def _components(a2ui: str) -> list[dict[str, Any]]:
    messages = [json.loads(line) for line in a2ui.splitlines()]
    update = messages[1].get("updateComponents")
    assert isinstance(update, dict)
    components = update.get("components")
    assert isinstance(components, list)
    return components


def _component(components: list[dict[str, Any]], component_id: str) -> dict[str, Any]:
    return next(component for component in components if component.get("id") == component_id)


def _styles(component: dict[str, Any]) -> dict[str, Any]:
    styles = component.get("styles")
    assert isinstance(styles, dict)
    return styles


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize(("width", "height", "stroke"), [(36, 36, 4), (40, 40, 5), (64, 60, 8)])
def test_template_ring_retains_explicit_geometry_and_layer_order(
    size: str, width: int, height: int, stroke: int,
) -> None:
    rows = _ring_rows()
    rows[3].props.update({"width": width, "height": height})
    rows[4].props.update({"width": width, "height": height, "strokeWidth": stroke})
    components = _convert(rows, size)
    ring = _component(components, "ring")
    ring_styles = _styles(ring)
    assert ring_styles.get("width") == width
    assert ring_styles.get("height") == height
    assert ring_styles.get("strokeWidth") == stroke
    assert ring.get("value") == "{{ ${/data/batterySOC} }}"
    stack = _component(components, "ring_stack")
    assert _styles(stack).get("width") == width
    assert _styles(stack).get("height") == height
    assert stack.get("children") == ["icon", "ring"]
    assert _styles(_component(components, "row")).get("height") == 36
    assert _styles(_component(components, "icon")).get("width") == 12
    outside_styles = _styles(_component(components, "outside"))
    assert outside_styles.get("width") == (48 if size == "2x2" else 36)
    assert outside_styles.get("strokeWidth") == (6 if size == "2x2" else 4)


def test_template_ring_does_not_gain_undeclared_geometry() -> None:
    rows = _ring_rows()
    for row in rows[3:5]:
        for key in ("width", "height", "strokeWidth"):
            row.props.pop(key, None)
    components = _convert(rows)
    for component_id in ("ring_stack", "ring"):
        styles = _component(components, component_id).get("styles", {})
        assert not {"width", "height", "strokeWidth"}.intersection(styles)


@pytest.mark.parametrize("marker_state", [
    "missing", "dangling", "unreferenced", "nested", "duplicate", "no-root",
])
def test_invalid_template_marker_keeps_ring_size_policy(marker_state: str) -> None:
    rows = _ring_rows()
    if marker_state == "missing":
        rows[0] = ComponentRow("root", "Stack", {}, ("row", "outside"))
        rows.pop(1)
    elif marker_state == "dangling":
        rows[0] = ComponentRow("root", "Stack", {}, ("template_root", "row", "outside"))
        rows.pop(1)
    elif marker_state == "unreferenced":
        rows[0] = ComponentRow("root", "Stack", {}, ("row", "outside"))
    elif marker_state == "nested":
        rows[0] = ComponentRow("root", "Stack", {}, ("wrapper", "outside"))
        rows.append(ComponentRow("wrapper", "Column", {}, ("template_root",)))
    elif marker_state == "duplicate":
        rows.append(rows[1])
    else:
        rows.pop(0)
    # 在归一化入口验证无效标记；公共解析器另有既有去重/修复策略。
    normalized = _normalize_ring_stack_children(rows, size="2x2")
    for row in normalized:
        if row.component_id in {"ring_stack", "ring"}:
            assert row.props.get("width") == row.props.get("height") == 48
        if row.component_id == "ring":
            assert row.props.get("strokeWidth") == 6


def test_unmarked_dual_zone_ring_keeps_44vp_policy() -> None:
    rows = _ring_rows()
    rows[0] = ComponentRow(
        "root", "Column", {"padding": 8, "itemMargin": 8}, ("zone", "other_zone"),
    )
    rows[1] = ComponentRow("zone", "Column", {"width": 134, "height": 63}, ("row",))
    rows.append(ComponentRow("other_zone", "Column", {"width": 134, "height": 63}, ("outside",)))
    components = _convert(rows)
    for component_id in ("ring_stack", "ring", "outside"):
        styles = _styles(_component(components, component_id))
        assert styles.get("width") == styles.get("height") == 44
    assert _styles(_component(components, "ring")).get("strokeWidth") == 6


def test_linear_progress_and_events_remain_unchanged() -> None:
    rows = _ring_rows()
    rows[4].props.update({"type": "linear", "width": 80, "height": 8, "strokeWidth": 3})
    events = [{"call": "clickToDeeplink", "args": {"uri": "battery"}}]
    rows[3].props["onClick"] = events
    components = _convert(rows)
    styles = _styles(_component(components, "ring"))
    assert styles.get("width") == 80
    assert styles.get("height") == 8
    assert styles.get("strokeWidth") == 3
    assert _component(components, "ring_stack").get("onClick") == events


@pytest.mark.parametrize("fusion", [False, True])
def test_battery_compact_ring_stays_36vp_after_template_round_trip(fusion: bool) -> None:
    registry = get_cardplan_registry()
    definition = registry.require_template("BatteryOverviewCompact@1")
    content = _instantiate_blueprint(
        definition.variants[0].root,
        {"batteryIcon": "resources/base/media/battery_leaf_fill.svg"},
        {"percent": "${data.phoneBattery.batterySOC}",
         "charging": "${data.phoneBattery.chargingStatusDesc}"},
        registry.theme_reference_values("battery-device-green"),
    )
    contract = HybridBodyContract.model_construct(theme_profile_id="battery-device-green")
    card = _compile_ux_layout_shell(content, contract, registry)
    if fusion:
        card = apply_fusion_ball_background(
            card, size="2x2",
            palette=FusionBallPalette(large="#FF17734C", medium="#FF26BFA6", small="#FF60BF98"),
        )
    else:
        card = apply_content_safe_inset(card, size="2x2")
    task = {"dataModelSchema": {"data": {"phoneBattery": {
        "batterySOC": {"type": "number", "sampleValue": 68},
        "chargingStatusDesc": {"type": "string", "sampleValue": "正在充电"},
    }}}}
    profile = {"version": "v0.9", "catalogId": "ohos.a2ui.extended.catalog.form"}
    original = convert_tersel_to_a2ui(
        _serialize_node(_strip_advanced_component_markers(card)),
        size="2x2", protocol_profile=profile, task_spec=task,
    )
    compact = prepare_template_source_dsl(
        original, processor_kind=DslProcessorKind.DESIGN_COMPACT,
        size="2x2", protocol_profile=profile,
    )
    converted = convert_compact_dsl_to_a2ui(compact, size="2x2", protocol_profile=profile)
    for output in (original, converted):
        components = _components(output)
        ring = next(item for item in components if item.get("component") == "Progress")
        assert _styles(ring).get("width") == _styles(ring).get("height") == 36
        assert _styles(ring).get("strokeWidth") == 6
        ring_id = ring.get("id")
        stack = next(item for item in components if ring_id in item.get("children", []))
        assert _styles(stack).get("width") == _styles(stack).get("height") == 36
        assert ('"fusionBallBackground"' in output) is fusion
