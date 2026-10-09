"""融球专项结构校验。

融球在转换层已经展开为标准 A2UI 组件树。本校验器集中解析这棵受控树的
层次、引用和参考几何，不模拟端侧渲染，也不生成渲染复核诊断。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from ..base import BaseValidator
from .color_math import RgbaColor, _rgba

FUSION_REFERENCE_SIZE = 160


@dataclass(frozen=True)
class FusionBallGeometry:
    slot_id: str
    ball_id: str
    width: int
    height: int
    diameter: int
    alignment: str


LARGE_BALL = FusionBallGeometry("fusionBallLargeSlot", "fusionBallLarge", 180, 44, 210, "center")
MEDIUM_BALL = FusionBallGeometry("fusionBallMediumSlot", "fusionBallMedium", 80, 220, 160, "bottom")
SMALL_BALL = FusionBallGeometry(
    "fusionBallSmallSlot", "fusionBallSmall", 195, 190, 100, "bottomEnd"
)
FUSION_BALL_GEOMETRIES = (LARGE_BALL, MEDIUM_BALL, SMALL_BALL)


BACKGROUND_ID = "fusionBallBackground"
GLASS_ID = "fusionBallGlassLayer"


@dataclass
class FusionStructure:
    foreground: dict[str, Any] | None = None
    colors: list[RgbaColor] = field(default_factory=list)
    glass: RgbaColor | None = None
    errors: list[dict[str, Any]] = field(default_factory=list)


def styles_of(component: dict[str, Any]) -> dict[str, Any]:
    styles = component.get("styles")
    return styles if isinstance(styles, dict) else {}


def finite_number(value: Any) -> float | None:
    number: float | None = None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            candidate = float(value)
        except OverflowError:
            return number
        if math.isfinite(candidate):
            number = candidate
    return number


def dimension(value: Any, parent: float) -> float | None:
    result = finite_number(value)
    if value == "matchParent":
        result = parent
    elif isinstance(value, str) and value.endswith("%"):
        try:
            result = finite_number(float(value.removesuffix("%")) * parent / 100.0)
        except ValueError:
            result = None
    return result


def color_of(value: Any) -> RgbaColor | None:
    result: RgbaColor | None = None
    if isinstance(value, str):
        try:
            result = _rgba(value)
        except ValueError:
            # 调用方将无法解析的颜色转成明确诊断，不按默认颜色继续。
            result = None
    return result


def child_ids(component: dict[str, Any]) -> list[str]:
    children = component.get("children")
    result: list[str] = []
    if isinstance(children, list):
        for child in children:
            if isinstance(child, str):
                result.append(child)
    elif isinstance(children, dict):
        template_id = children.get("componentId")
        if isinstance(template_id, str):
            result.append(template_id)
    return result


def visible(component: dict[str, Any]) -> bool:
    visibility = styles_of(component).get("visibility")
    return visibility not in ("hidden", "none")


def reachable_fusion(root: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> bool:
    pending = [root]
    visited: set[str] = set()
    while pending:
        component = pending.pop()
        component_id = component.get("id")
        if not isinstance(component_id, str) or component_id in visited:
            continue
        visited.add(component_id)
        if not visible(component):
            continue
        children = child_ids(component)
        if component_id == BACKGROUND_ID or BACKGROUND_ID in children:
            return True
        for child_id in children:
            child = by_id.get(child_id)
            if isinstance(child, dict):
                pending.append(child)
    return False


def _error(
    result: FusionStructure, component_id: str, key: str, actual: Any, expected: Any
) -> None:
    result.errors.append(
        {"component": component_id, "field": key, "actual": actual, "expected": expected}
    )


def _node(
    result: FusionStructure,
    by_id: dict[str, dict[str, Any]],
    component_id: str,
    kind: str,
    children: list[str],
) -> dict[str, Any] | None:
    component = by_id.get(component_id)
    if not isinstance(component, dict):
        _error(result, component_id, "component", None, kind)
        return None
    if component.get("component") != kind:
        _error(result, component_id, "component", component.get("component"), kind)
    actual_children = component.get("children", [])
    if actual_children != children:
        _error(result, component_id, "children", actual_children, children)
    styles = styles_of(component)
    for key in ("margin", "padding"):
        value = styles.get(key, 0)
        values = list(value.values()) if isinstance(value, dict) else [value]
        if any(finite_number(item) != 0.0 for item in values):
            _error(result, component_id, key, value, 0)
    # 受控背景不接受额外的布局/绘制效果；不能悄悄忽略它们后声明几何有效。
    allowed = {
        "width",
        "height",
        "borderRadius",
        "alignContent",
        "clip",
        "margin",
        "padding",
        "backgroundColor",
        "backdropBlur",
        "strokeWidth",
        "color",
        "vertical",
    }
    extras = sorted(set(styles) - allowed)
    if extras:
        _error(result, component_id, "styles", extras, "受控融球背景样式")
    return styles


def _size(
    result: FusionStructure,
    component_id: str,
    styles: dict[str, Any],
    parent_width: float,
    parent_height: float,
    width: float,
    height: float,
) -> None:
    for key, parent, expected in (
        ("width", parent_width, width),
        ("height", parent_height, height),
    ):
        actual = dimension(styles.get(key), parent)
        if actual is None or not math.isclose(actual, expected, abs_tol=0.0001, rel_tol=0.0):
            _error(
                result,
                component_id,
                key,
                {"declared": styles.get(key), "resolved": actual},
                expected,
            )


def _value(
    result: FusionStructure,
    component_id: str,
    styles: dict[str, Any],
    key: str,
    expected: Any,
    default: Any = None,
) -> None:
    actual = styles.get(key, default)
    if actual != expected or isinstance(actual, bool) != isinstance(expected, bool):
        _error(result, component_id, key, actual, expected)


def inspect_fusion(root: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> FusionStructure:
    result = FusionStructure()
    children = child_ids(root)
    valid_order = root.get("children") == children and len(children) == 2
    if valid_order:
        valid_order = children[0] == BACKGROUND_ID
    if root.get("component") != "Stack" or not valid_order:
        _error(result, "root", "children", children, "Stack 内背景在前，唯一前景在后")
        return result
    foreground = by_id.get(children[1])
    reserved_ids = {BACKGROUND_ID, GLASS_ID, root.get("id")}
    for geometry in FUSION_BALL_GEOMETRIES:
        reserved_ids.add(geometry.slot_id)
        reserved_ids.add(geometry.ball_id)
    if not isinstance(foreground, dict) or children[1] in reserved_ids:
        _error(result, children[1], "component", foreground, "独立前景组件")
    else:
        result.foreground = foreground
    root_styles = styles_of(root)
    _value(result, "root", root_styles, "alignContent", "topStart")
    _value(result, "root", root_styles, "clip", True)
    _value(result, "root", root_styles, "padding", 0, 0)
    slots = [geometry.slot_id for geometry in FUSION_BALL_GEOMETRIES]
    background = _node(result, by_id, BACKGROUND_ID, "Stack", slots + [GLASS_ID])
    if background is None:
        return result
    reference = float(FUSION_REFERENCE_SIZE)
    _size(result, BACKGROUND_ID, background, reference, reference, reference, reference)
    _value(result, BACKGROUND_ID, background, "alignContent", "topStart")
    _value(result, BACKGROUND_ID, background, "clip", True)
    for geometry in FUSION_BALL_GEOMETRIES:
        slot = _node(result, by_id, geometry.slot_id, "Stack", [geometry.ball_id])
        if slot is None:
            continue
        _size(
            result,
            geometry.slot_id,
            slot,
            reference,
            reference,
            float(geometry.width),
            float(geometry.height),
        )
        _value(result, geometry.slot_id, slot, "alignContent", geometry.alignment)
        _value(result, geometry.slot_id, slot, "clip", False, False)
        ball = _node(result, by_id, geometry.ball_id, "Divider", [])
        if ball is None:
            continue
        actual_width = dimension(slot.get("width"), reference)
        actual_height = dimension(slot.get("height"), reference)
        if actual_width is not None and actual_height is not None:
            _size(
                result,
                geometry.ball_id,
                ball,
                actual_width,
                actual_height,
                float(geometry.diameter),
                float(geometry.diameter),
            )
        _value(result, geometry.ball_id, ball, "borderRadius", geometry.diameter / 2)
        _value(result, geometry.ball_id, ball, "clip", True)
        _value(result, geometry.ball_id, ball, "strokeWidth", 0)
        color = color_of(ball.get("backgroundColor"))
        if color is None or color[3] != 1.0:
            _error(
                result,
                geometry.ball_id,
                "backgroundColor",
                ball.get("backgroundColor"),
                "不透明静态颜色",
            )
        else:
            result.colors.append(color)
    glass = _node(result, by_id, GLASS_ID, "Divider", [])
    if glass is None:
        return result
    _size(result, GLASS_ID, glass, reference, reference, reference, reference)
    _value(result, GLASS_ID, glass, "strokeWidth", 0)
    result.glass = color_of(glass.get("backgroundColor"))
    if result.glass is None:
        _error(result, GLASS_ID, "backgroundColor", glass.get("backgroundColor"), "静态 ARGB 颜色")
    blur = glass.get("backdropBlur")
    radius = finite_number(blur.get("radius")) if isinstance(blur, dict) else None
    if radius is None or radius < 0.0:
        _error(result, GLASS_ID, "backdropBlur", blur, "有限非负 radius")
    return result


def _report(
    reporter: Any, code: str, severity: str, pointer: str, message: str, actual: Any, hint: str
) -> None:
    reporter.add(
        severity,
        code,
        "quality",
        "genui",
        line=2,
        json_pointer=pointer,
        actual=actual,
        message=message,
        fix_hint=hint,
        source="fusion-readability",
    )


class FusionReadabilityValidator(BaseValidator):
    """校验展开后的融球结构和参考几何。"""

    stage = "quality"
    name = "fusion_readability"

    def validate(self, context: Any, rules: Any, reporter: Any) -> None:
        del rules
        root = context.components_by_id.get(context.root_id)
        if not isinstance(root, dict) or not reachable_fusion(root, context.components_by_id):
            return

        size = context.cardspec.get("suggestSize")
        styles = styles_of(root)
        reference = float(FUSION_REFERENCE_SIZE)
        reference_dimensions = (
            dimension(styles.get("width", "matchParent"), reference),
            dimension(styles.get("height", "matchParent"), reference),
        )

        # 160×160 是当前受控融球结构的唯一参考几何。其它尺寸不套用这套
        # 几何，也不发出端侧渲染复核提示；待对应尺寸有正式结构后再增加规则。
        if size not in (None, "2x2"):
            return
        if reference_dimensions != (reference, reference):
            _report(
                reporter,
                "FUSION.STRUCTURE_INVALID",
                "error",
                "/updateComponents/root",
                "2x2 融球根尺寸不符合 160×160 参考结构。",
                {
                    "violations": [
                        {
                            "component": "root",
                            "field": "width/height",
                            "actual": reference_dimensions,
                            "expected": (reference, reference),
                        }
                    ]
                },
                "将 2x2 根宽高调整为参考 160×160，或使用 matchParent。",
            )
            return

        structure = inspect_fusion(root, context.components_by_id)
        if structure.errors:
            _report(
                reporter,
                "FUSION.STRUCTURE_INVALID",
                "error",
                "/updateComponents/components",
                "融球背景不符合受控几何或层次结构。",
                {"violations": structure.errors},
                "按受控融球结构修复背景；百分比相对直接父级解析。"
                "中球槽应为参考 80×220、中球为 160×160；不要移动或压扁球体。",
            )
