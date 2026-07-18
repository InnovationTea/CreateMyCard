#!/usr/bin/env python3
"""DSL-only deterministic aesthetic risk checks for HarmonyOS A2UI Form cards.

Scope: contrast, palette, typography, static layout and interaction-affordance risks.
Precondition: the DSL has already passed the existing hard/protocol validator.
No renderer, screenshot, OCR, network call, model, or third-party dependency is used.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeAlias


RGBA: TypeAlias = tuple[float, float, float, float]
MAX_BACKGROUND_CANDIDATES = 4096


@dataclass(frozen=True)
class Thresholds:
    normal_text_min: float = 4.5
    large_text_min: float = 3.0
    critical_min: float = 3.0
    large_font_size: float = 18.0
    large_bold_font_size: float = 14.0
    large_bold_font_weight: float = 700.0
    max_chromatic_families: int = 2
    max_gradient_surfaces: int = 1
    max_gradient_stops: int = 3
    max_translucent_surface_layers: int = 2
    max_font_size_levels: int = 3
    max_radius_values: int = 3
    max_shadowed_components: int = 2
    max_border_width_values: int = 2
    max_nested_surfaces: int = 2

    def __post_init__(self) -> None:
        values = {
            "normal_text_min": self.normal_text_min,
            "large_text_min": self.large_text_min,
            "critical_min": self.critical_min,
            "large_font_size": self.large_font_size,
            "large_bold_font_size": self.large_bold_font_size,
            "large_bold_font_weight": self.large_bold_font_weight,
            "max_chromatic_families": self.max_chromatic_families,
            "max_gradient_surfaces": self.max_gradient_surfaces,
            "max_gradient_stops": self.max_gradient_stops,
            "max_translucent_surface_layers": self.max_translucent_surface_layers,
            "max_font_size_levels": self.max_font_size_levels,
            "max_radius_values": self.max_radius_values,
            "max_shadowed_components": self.max_shadowed_components,
            "max_border_width_values": self.max_border_width_values,
            "max_nested_surfaces": self.max_nested_surfaces,
        }
        for name, value in values.items():
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
            ):
                raise ValueError(f"{name} 必须是有限数值")

        if not (
            1.0
            <= self.critical_min
            <= self.large_text_min
            <= self.normal_text_min
            <= 21.0
        ):
            raise ValueError(
                "对比度阈值必须满足 "
                "1 <= critical_min <= large_text_min <= normal_text_min <= 21"
            )
        if not (
            0.0 < self.large_bold_font_size <= self.large_font_size
        ):
            raise ValueError(
                "字号阈值必须满足 0 < large_bold_font_size <= large_font_size"
            )
        if not 100.0 <= self.large_bold_font_weight <= 900.0:
            raise ValueError("large_bold_font_weight 必须位于 100 到 900")
        if not 1 <= self.max_chromatic_families <= 8:
            raise ValueError("max_chromatic_families 必须位于 1 到 8")
        if not 1 <= self.max_gradient_surfaces <= 4:
            raise ValueError("max_gradient_surfaces 必须位于 1 到 4")
        if not 2 <= self.max_gradient_stops <= 8:
            raise ValueError("max_gradient_stops 必须位于 2 到 8")
        if not 1 <= self.max_translucent_surface_layers <= 6:
            raise ValueError("max_translucent_surface_layers 必须位于 1 到 6")
        if not 2 <= self.max_font_size_levels <= 8:
            raise ValueError("max_font_size_levels 必须位于 2 到 8")
        if not 1 <= self.max_radius_values <= 6:
            raise ValueError("max_radius_values 必须位于 1 到 6")
        if not 0 <= self.max_shadowed_components <= 6:
            raise ValueError("max_shadowed_components 必须位于 0 到 6")
        if not 1 <= self.max_border_width_values <= 4:
            raise ValueError("max_border_width_values 必须位于 1 到 4")
        if not 1 <= self.max_nested_surfaces <= 5:
            raise ValueError("max_nested_surfaces 必须位于 1 到 5")


@dataclass(frozen=True)
class AestheticContext:
    components: list[dict[str, Any]]
    components_by_id: dict[str, dict[str, Any]]
    source_index_by_id: dict[str, int]
    parent_by_child: dict[str, str]


def read_text(path: str) -> str:
    if path == "-":
        return sys.stdin.read().lstrip("\ufeff")
    return Path(path).read_text(encoding="utf-8-sig")


def extract_genui(raw: str) -> str:
    match = re.search(r"```genui\s*([\s\S]*?)```", raw, re.I)
    return match.group(1).strip() if match else raw.strip()


def reject_nonfinite_json_constant(constant: str) -> Any:
    raise ValueError(f"不允许非有限数值 {constant}")


def prepare_context(raw: str) -> tuple[AestheticContext | None, list[dict[str, Any]]]:
    """Build the graph needed by the aesthetic algorithm.

    This is a defensive precondition assertion, not a replacement for validate_card.py.
    It only blocks graph ambiguity that would make a contrast result untrustworthy.
    """

    reasons: list[str] = []
    messages: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        [line.strip() for line in extract_genui(raw).splitlines() if line.strip()], 1
    ):
        try:
            value = json.loads(line, parse_constant=reject_nonfinite_json_constant)
        except (json.JSONDecodeError, ValueError) as exc:
            detail = exc.msg if isinstance(exc, json.JSONDecodeError) else str(exc)
            reasons.append(f"第 {line_number} 行 JSON 无法解析：{detail}")
            continue
        if not isinstance(value, dict):
            reasons.append(f"第 {line_number} 行不是 JSON object")
            continue
        messages.append(value)

    updates = [
        message["updateComponents"]
        for message in messages
        if isinstance(message.get("updateComponents"), dict)
    ]
    if len(updates) != 1:
        reasons.append(f"需要 1 个 updateComponents，实际为 {len(updates)} 个")
        return None, [precondition_diagnostic(reasons)]

    update = updates[0]
    raw_components = update.get("components")
    if not isinstance(raw_components, list) or not raw_components:
        reasons.append("updateComponents.components 必须是非空数组")
        return None, [precondition_diagnostic(reasons)]
    if any(not isinstance(item, dict) for item in raw_components):
        reasons.append("components 数组包含非 object 项")
        return None, [precondition_diagnostic(reasons)]
    components = list(raw_components)

    components_by_id: dict[str, dict[str, Any]] = {}
    source_index_by_id: dict[str, int] = {}
    duplicate_ids: set[str] = set()
    for index, component in enumerate(components):
        component_id = component.get("id")
        if not isinstance(component_id, str) or not component_id:
            reasons.append(f"components[{index}].id 不是非空字符串")
            continue
        if component_id in components_by_id:
            duplicate_ids.add(component_id)
            continue
        components_by_id[component_id] = component
        source_index_by_id[component_id] = index
        if (
            component.get("component") in {"Text", "Button"}
            and has_visible_text(component)
            and not isinstance(component.get("styles"), dict)
        ):
            reasons.append(f"可见文字组件 {component_id} 缺少 object styles")
    if duplicate_ids:
        reasons.append("组件 id 重复：" + ", ".join(sorted(duplicate_ids)))

    root_id = update.get("root")
    if not isinstance(root_id, str) or root_id not in components_by_id:
        reasons.append("updateComponents.root 未指向已声明组件")

    parents_by_child: dict[str, set[str]] = {}
    children_by_parent: dict[str, list[str]] = {}
    for component in components:
        parent_id = component.get("id")
        if not isinstance(parent_id, str) or parent_id not in components_by_id:
            continue
        children = component.get("children")
        if children is None:
            children_by_parent[parent_id] = []
            continue
        if isinstance(children, list):
            child_ids = [item for item in children if isinstance(item, str)]
            if len(child_ids) != len(children):
                reasons.append(f"{parent_id}.children 含非字符串引用")
        elif isinstance(children, dict) and isinstance(children.get("componentId"), str):
            child_ids = [children["componentId"]]
        else:
            reasons.append(f"{parent_id}.children 无法解析")
            child_ids = []
        if len(child_ids) != len(set(child_ids)):
            reasons.append(f"{parent_id}.children 重复引用同一组件")
        children_by_parent[parent_id] = child_ids
        for child_id in child_ids:
            if child_id not in components_by_id:
                reasons.append(f"{parent_id}.children 引用了不存在的 {child_id}")
                continue
            parents_by_child.setdefault(child_id, set()).add(parent_id)

    ambiguous_children = {
        child_id: sorted(parent_ids)
        for child_id, parent_ids in parents_by_child.items()
        if len(parent_ids) > 1
    }
    if ambiguous_children:
        reasons.append(
            "组件存在多个父节点："
            + "; ".join(
                f"{child_id}<-{','.join(parent_ids)}"
                for child_id, parent_ids in sorted(ambiguous_children.items())
            )
        )
    parent_by_child = {
        child_id: next(iter(parent_ids))
        for child_id, parent_ids in parents_by_child.items()
        if len(parent_ids) == 1
    }
    if has_parent_cycle(parent_by_child, set(components_by_id)):
        reasons.append("组件父子关系存在循环")

    if isinstance(root_id, str) and root_id in components_by_id:
        reachable: set[str] = set()
        pending = [root_id]
        while pending:
            current_id = pending.pop()
            if current_id in reachable:
                continue
            reachable.add(current_id)
            pending.extend(children_by_parent.get(current_id, []))
        unreachable = sorted(set(components_by_id) - reachable)
        if unreachable:
            reasons.append("存在 root 不可达组件：" + ", ".join(unreachable))

    if reasons:
        return None, [precondition_diagnostic(reasons)]
    return (
        AestheticContext(
            components=components,
            components_by_id=components_by_id,
            source_index_by_id=source_index_by_id,
            parent_by_child=parent_by_child,
        ),
        [],
    )


def precondition_diagnostic(reasons: list[str]) -> dict[str, Any]:
    return diagnostic(
        "error",
        "AESTHETIC_PRECONDITION_FAILED",
        "输入不满足美学算法的前置条件；请先通过现有 hard/协议校验器。",
        json_pointer="/updateComponents",
        actual={"reasons": reasons[:20]},
        expected="validate_card.py hard stage passed",
        fix_hint="先修复或合并 DSL 结构错误，再运行美学算法；本脚本不替代协议校验器。",
    )


def has_parent_cycle(parent_by_child: dict[str, str], component_ids: set[str]) -> bool:
    for start_id in component_ids:
        visited: set[str] = set()
        current_id: str | None = start_id
        while current_id is not None:
            if current_id in visited:
                return True
            visited.add(current_id)
            current_id = parent_by_child.get(current_id)
    return False


def analyze(raw: str, thresholds: Thresholds | None = None) -> dict[str, Any]:
    thresholds = thresholds or Thresholds()
    context, diagnostics = prepare_context(raw)
    if context is None:
        return build_report([], 0, 0, diagnostics, thresholds)

    text_like_count = 0
    checked_count = 0
    for component in context.components:
        component_type = component.get("component")
        if component_type not in {"Text", "Button"} or not has_visible_text(component):
            continue
        component_id = component.get("id")
        styles = component.get("styles")
        if not isinstance(component_id, str) or not isinstance(styles, dict):
            continue
        if not is_effectively_visible(
            component_id, context.components_by_id, context.parent_by_child
        ):
            continue
        text_like_count += 1
        source_index = context.source_index_by_id[component_id]
        pointer = f"/updateComponents/components/{source_index}/styles/fontColor"
        logical_path = (
            f"/updateComponents/componentsById/{component_id}/styles/fontColor"
        )
        foreground_value = styles.get("fontColor")
        foreground = parse_hex_color(foreground_value)
        if foreground is None:
            diagnostics.append(
                diagnostic(
                    "warning",
                    "AESTHETIC_COLOR_CONTRAST_UNDETERMINED",
                    "文字颜色不是可静态解析的 hex，无法确定对比度。",
                    json_pointer=pointer,
                    logical_path=logical_path,
                    actual={"componentId": component_id, "fontColor": foreground_value},
                    expected="#RRGGBB 或 #AARRGGBB",
                    fix_hint="提供静态 fontColor，或在真实渲染后由 UCD 复核。",
                )
            )
            continue

        backgrounds, background_layers, uncertainty = resolve_background_candidates(
            component_id,
            context.components_by_id,
            context.parent_by_child,
        )
        ratios = [
            ratio
            for background in backgrounds
            if (ratio := contrast_ratio(foreground, background)) is not None
        ]
        if not ratios:
            diagnostics.append(
                diagnostic(
                    "warning",
                    "AESTHETIC_COLOR_CONTRAST_UNDETERMINED",
                    "背景包含图片、动态颜色或无法闭合的透明叠层，无法从 DSL 确定对比度。",
                    json_pointer=pointer,
                    logical_path=logical_path,
                    actual={
                        "componentId": component_id,
                        "fontColor": foreground_value,
                        "backgroundLayers": background_layers,
                        "uncertainty": uncertainty,
                    },
                    fix_hint="该组件不能被自动判定为通过；请在真实渲染后由 UCD 复核。",
                )
            )
            continue

        raw_font_size = styles.get("fontSize")
        font_size = numeric(raw_font_size)
        if font_size is None and "fontSize" in styles:
            diagnostics.append(
                diagnostic(
                    "warning",
                    "AESTHETIC_COLOR_CONTRAST_UNDETERMINED",
                    "字号是动态或不可静态解析的值，无法选择文字对比度阈值。",
                    json_pointer=f"/updateComponents/components/{source_index}/styles/fontSize",
                    logical_path=f"/updateComponents/componentsById/{component_id}/styles/fontSize",
                    actual={"componentId": component_id, "fontSize": raw_font_size},
                    expected="静态 fontSize，或真实渲染后的可读性复核。",
                    fix_hint="提供静态字号，或将此组件纳入真实渲染与 UCD 可读性复核。",
                )
            )
            continue
        if font_size is None:
            font_size = 16.0
        checked_count += 1
        ratio = min(ratios)
        classification_font_size, adaptive_font_size_uncertain = (
            smallest_possible_font_size(styles, font_size)
        )
        raw_font_weight = styles.get("fontWeight")
        font_weight = normalize_font_weight(raw_font_weight, component_type)
        is_large = classification_font_size >= thresholds.large_font_size or (
            classification_font_size >= thresholds.large_bold_font_size
            and font_weight >= thresholds.large_bold_font_weight
        )
        required = thresholds.large_text_min if is_large else thresholds.normal_text_min
        if ratio >= required:
            continue
        severity = "error" if ratio < thresholds.critical_min else "warning"
        diagnostics.append(
            diagnostic(
                severity,
                "AESTHETIC_COLOR_CONTRAST_LOW",
                "文字与背景的对比度不足，可能看不清楚。",
                json_pointer=pointer,
                logical_path=logical_path,
                actual={
                    "componentId": component_id,
                    "componentType": component_type,
                    "fontColor": foreground_value,
                    "backgroundLayers": background_layers,
                    "contrastRatio": round(ratio, 2),
                    "fontSize": raw_font_size,
                    "normalizedFontSize": font_size,
                    "classificationFontSize": classification_font_size,
                    "minFontSize": styles.get("minFontSize"),
                    "maxFontSize": styles.get("maxFontSize"),
                    "adaptiveFontSizeUncertain": adaptive_font_size_uncertain,
                    "fontWeight": raw_font_weight,
                    "normalizedFontWeight": font_weight,
                    "largeText": is_large,
                },
                expected={"contrastRatio": f">= {required}:1"},
                fix_hint="提高文字与背景的明暗差，或改用高对比的文字/背景色。",
            )
        )

    diagnostics.extend(evaluate_palette_complexity(context, thresholds))
    diagnostics.extend(evaluate_color_role_consistency(context))
    diagnostics.extend(evaluate_gradient_complexity(context, thresholds))
    diagnostics.extend(evaluate_alpha_stack_complexity(context, thresholds))
    diagnostics.extend(evaluate_typography_system(context, thresholds))
    diagnostics.extend(evaluate_style_consistency(context, thresholds))
    diagnostics.extend(evaluate_surface_nesting(context, thresholds))
    diagnostics.extend(evaluate_spacing_tokens(context))
    diagnostics.extend(evaluate_fixed_layout_overflow(context))
    diagnostics.extend(evaluate_static_text_clip_risk(context))
    diagnostics.extend(evaluate_action_target_size(context))
    diagnostics.extend(evaluate_false_affordance(context))
    diagnostics.extend(evaluate_information_hierarchy(context))
    diagnostics.extend(evaluate_small_card_density(context))

    return build_report(
        context.components,
        text_like_count,
        checked_count,
        diagnostics,
        thresholds,
    )


COLOR_STYLE_FIELDS = (
    "backgroundColor",
    "fontColor",
    "borderColor",
    "color",
    "selectedColor",
    "unSelectedColor",
)


def evaluate_palette_complexity(
    context: AestheticContext, thresholds: Thresholds
) -> list[dict[str, Any]]:
    """Detect competing chromatic families from DSL-defined, visible colors only.

    Image pixels and dynamic expressions are intentionally excluded: they cannot be
    analysed without a renderer or multimodal model.
    """

    families: dict[int, set[str]] = {}
    for component in context.components:
        component_id = component.get("id")
        if not isinstance(component_id, str) or not is_effectively_visible(
            component_id, context.components_by_id, context.parent_by_child
        ):
            continue
        styles = component.get("styles")
        if not isinstance(styles, dict):
            continue
        for color in iter_static_style_colors(styles):
            family = chromatic_hue_family(color)
            if family is not None:
                families.setdefault(family, set()).add(component_id)

    if len(families) <= thresholds.max_chromatic_families:
        return []
    return [
        diagnostic(
            "warning",
            "AESTHETIC_COLOR_PALETTE_TOO_COMPLEX",
            "同一卡片出现过多无关高饱和色族，视觉焦点可能相互竞争。",
            json_pointer="/updateComponents/components",
            actual={
                "chromaticFamilyCount": len(families),
                "hueFamilies": sorted(families),
                "componentIds": sorted(
                    {component_id for values in families.values() for component_id in values}
                ),
            },
            expected={"maxChromaticFamilies": thresholds.max_chromatic_families},
            fix_hint="保留一个场景主色与一个状态/动作色，其余颜色改为中性或同色族辅助色。",
        )
    ]


def evaluate_gradient_complexity(
    context: AestheticContext, thresholds: Thresholds
) -> list[dict[str, Any]]:
    gradients: list[tuple[str, int]] = []
    for component in context.components:
        component_id = component.get("id")
        if not isinstance(component_id, str) or not is_effectively_visible(
            component_id, context.components_by_id, context.parent_by_child
        ):
            continue
        styles = component.get("styles")
        gradient = styles.get("linearGradient") if isinstance(styles, dict) else None
        colors = gradient.get("colors") if isinstance(gradient, dict) else None
        if isinstance(colors, list):
            gradients.append((component_id, len(colors)))

    largest_stop_count = max((stop_count for _, stop_count in gradients), default=0)
    if (
        len(gradients) <= thresholds.max_gradient_surfaces
        and largest_stop_count <= thresholds.max_gradient_stops
    ):
        return []
    return [
        diagnostic(
            "warning",
            "AESTHETIC_COLOR_GRADIENT_OVERCOMPLEX",
            "渐变面或渐变 stop 过多，卡片容易显得杂乱并削弱信息层级。",
            json_pointer="/updateComponents/components",
            actual={
                "gradientSurfaces": [component_id for component_id, _ in gradients],
                "stopCounts": {component_id: count for component_id, count in gradients},
            },
            expected={
                "maxGradientSurfaces": thresholds.max_gradient_surfaces,
                "maxGradientStops": thresholds.max_gradient_stops,
            },
            fix_hint="2×2 卡片优先保留一个渐变面，且使用 2–3 个有明确场景角色的 stop。",
        )
    ]


def evaluate_color_role_consistency(context: AestheticContext) -> list[dict[str, Any]]:
    """Check two low-cost color-role risks without treating UCD tokens as closed.

    Brand/scenario colors can legitimately extend the token system, therefore this
    algorithm does not reject unknown hex values. It only reports clearly competing
    accent surfaces and mutually inconsistent CTA colors inside the same card.
    """

    accent_surfaces: list[tuple[str, int]] = []
    action_families: dict[int, list[str]] = {}
    for component in context.components:
        component_id = component.get("id")
        styles = component.get("styles")
        if (
            not isinstance(component_id, str)
            or not isinstance(styles, dict)
            or not is_effectively_visible(
                component_id, context.components_by_id, context.parent_by_child
            )
        ):
            continue
        background = parse_hex_color(styles.get("backgroundColor"))
        family = chromatic_hue_family(background) if background is not None else None
        if family is not None and component_id in context.parent_by_child:
            accent_surfaces.append((component_id, family))
        if is_action_container(component) and family is not None:
            action_families.setdefault(family, []).append(component_id)

    diagnostics: list[dict[str, Any]] = []
    if len(accent_surfaces) > 3:
        diagnostics.append(
            diagnostic(
                "warning",
                "AESTHETIC_COLOR_ACCENT_OVERUSED",
                "同一卡片使用过多高饱和强调面，容易让每个元素都在争夺注意力。",
                json_pointer="/updateComponents/components",
                actual={"accentSurfaces": [{"componentId": item_id, "hueFamily": family} for item_id, family in accent_surfaces]},
                expected="紧凑卡片通常保留 1 个场景强调面，必要时再增加 1 个状态/动作强调面。",
                fix_hint="将次要面改为中性色或主色低饱和变体，避免每个标签都使用强色底。",
            )
        )
    if sum(len(component_ids) for component_ids in action_families.values()) >= 3 and len(action_families) >= 3:
        diagnostics.append(
            diagnostic(
                "warning",
                "AESTHETIC_COLOR_ROLE_INCONSISTENT",
                "同一卡片的多个 CTA 使用互不相关的强调色，动作角色缺少一致性。",
                json_pointer="/updateComponents/components",
                actual={"actionHueFamilies": {str(family): component_ids for family, component_ids in sorted(action_families.items())}},
                expected="同类 CTA 应复用同一动作色；不同颜色只用于明确的成功/警告/危险语义。",
                fix_hint="统一 CTA 色角色，保留语义状态色仅用于对应状态，而非随机区分按钮。",
            )
        )
    return diagnostics


def evaluate_alpha_stack_complexity(
    context: AestheticContext, thresholds: Thresholds
) -> list[dict[str, Any]]:
    deepest: tuple[str, list[str]] | None = None
    for component in context.components:
        component_id = component.get("id")
        if not isinstance(component_id, str) or not is_effectively_visible(
            component_id, context.components_by_id, context.parent_by_child
        ):
            continue
        translucent_ids: list[str] = []
        current_id: str | None = component_id
        while current_id is not None:
            current = context.components_by_id.get(current_id, {})
            styles = current.get("styles") if isinstance(current, dict) else None
            if isinstance(styles, dict) and has_translucent_surface(styles):
                translucent_ids.append(current_id)
            current_id = context.parent_by_child.get(current_id)
        if deepest is None or len(translucent_ids) > len(deepest[1]):
            deepest = (component_id, translucent_ids)

    if deepest is None or len(deepest[1]) <= thresholds.max_translucent_surface_layers:
        return []
    component_id, layer_ids = deepest
    return [
        diagnostic(
            "warning",
            "AESTHETIC_COLOR_ALPHA_STACK_COMPLEX",
            "同一视觉路径叠加过多半透明表面，颜色可能发灰或浑浊。",
            json_pointer=f"/updateComponents/components/{context.source_index_by_id[component_id]}",
            actual={"componentId": component_id, "translucentSurfaceIds": layer_ids},
            expected={"maxTranslucentSurfaceLayers": thresholds.max_translucent_surface_layers},
            fix_hint="合并相邻半透明背板，优先保留一层主表面和一层必要的弱分隔。",
        )
    ]


def has_translucent_surface(styles: dict[str, Any]) -> bool:
    background = parse_hex_color(styles.get("backgroundColor"))
    if background is not None and 0 < background[3] < 0.999:
        return True
    gradient = styles.get("linearGradient")
    if isinstance(gradient, dict) and isinstance(gradient.get("colors"), list):
        return any(
            (parsed := parse_hex_color(stop[0])) is not None and 0 < parsed[3] < 0.999
            for stop in gradient["colors"]
            if isinstance(stop, list) and stop
        )
    return False


def evaluate_typography_system(
    context: AestheticContext, thresholds: Thresholds
) -> list[dict[str, Any]]:
    font_sizes: dict[float, list[str]] = {}
    text_weights: list[tuple[str, float]] = []
    for component in context.components:
        component_id = component.get("id")
        component_type = component.get("component")
        styles = component.get("styles")
        if (
            component_type not in {"Text", "Button"}
            or not isinstance(component_id, str)
            or not isinstance(styles, dict)
            or not has_visible_text(component)
            or not is_effectively_visible(
                component_id, context.components_by_id, context.parent_by_child
            )
        ):
            continue
        raw_font_size = styles.get("fontSize")
        font_size = numeric(raw_font_size)
        if font_size is None and "fontSize" not in styles:
            font_size = 16.0
        if font_size is not None:
            font_sizes.setdefault(font_size, []).append(component_id)
        text_weights.append(
            (component_id, normalize_font_weight(styles.get("fontWeight"), component_type))
        )

    diagnostics: list[dict[str, Any]] = []
    if len(font_sizes) > thresholds.max_font_size_levels:
        diagnostics.append(
            diagnostic(
            "warning",
            "AESTHETIC_TYPO_TOO_MANY_LEVELS",
            "同一卡片使用过多字号层级，信息结构容易显得零散。",
            json_pointer="/updateComponents/components",
            actual={
                "fontSizeLevels": sorted(font_sizes),
                "componentIdsBySize": {
                    str(size): component_ids for size, component_ids in sorted(font_sizes.items())
                },
            },
            expected={"maxFontSizeLevels": thresholds.max_font_size_levels},
            fix_hint="2×2 卡片优先收敛为主信息、标题/状态、支撑信息三档字号。",
            )
        )
    if len(text_weights) >= 3 and all(weight >= 700 for _, weight in text_weights):
        diagnostics.append(
            diagnostic(
                "warning",
                "AESTHETIC_TYPO_BOLD_OVERUSED",
                "可见文字几乎全部使用粗体，主次关系会被压平。",
                json_pointer="/updateComponents/components",
                actual={"componentIds": [component_id for component_id, _ in text_weights]},
                expected="保留一个主信息或 CTA 使用粗体，其余文字使用 Regular/Medium。",
                fix_hint="降低标题、支撑信息或辅助标签的字重，只保留一个最强视觉焦点。",
            )
        )
    return diagnostics


def evaluate_style_consistency(
    context: AestheticContext, thresholds: Thresholds
) -> list[dict[str, Any]]:
    radii: dict[float, list[str]] = {}
    shadowed_component_ids: list[str] = []
    border_widths: dict[float, list[str]] = {}
    for component in context.components:
        component_id = component.get("id")
        if not isinstance(component_id, str) or not is_effectively_visible(
            component_id, context.components_by_id, context.parent_by_child
        ):
            continue
        styles = component.get("styles")
        if not isinstance(styles, dict):
            continue
        radius = numeric(styles.get("borderRadius"))
        if radius is not None and radius > 0:
            radii.setdefault(radius, []).append(component_id)

        shadow = styles.get("shadow")
        if shadow not in (None, "", False):
            shadowed_component_ids.append(component_id)

        border_width = numeric(styles.get("borderWidth"))
        if border_width is not None and border_width > 0:
            border_widths.setdefault(border_width, []).append(component_id)

    diagnostics: list[dict[str, Any]] = []
    if len(radii) > thresholds.max_radius_values:
        diagnostics.append(
            diagnostic(
            "warning",
            "AESTHETIC_STYLE_RADIUS_INCONSISTENT",
            "同一卡片使用过多圆角规格，组件体系缺少一致性。",
            json_pointer="/updateComponents/components",
            actual={
                "radiusValues": sorted(radii),
                "componentIdsByRadius": {
                    str(radius): component_ids for radius, component_ids in sorted(radii.items())
                },
            },
            expected={"maxRadiusValues": thresholds.max_radius_values},
            fix_hint="收敛为面板、小图标块和 pill 三类圆角角色，重复组件复用同一规格。",
            )
        )
    if len(shadowed_component_ids) > thresholds.max_shadowed_components:
        diagnostics.append(
            diagnostic(
                "warning",
                "AESTHETIC_STYLE_SHADOW_OVERUSED",
                "多个组件同时使用阴影，紧凑卡片容易产生视觉噪声。",
                json_pointer="/updateComponents/components",
                actual={"shadowedComponentIds": shadowed_component_ids},
                expected={"maxShadowedComponents": thresholds.max_shadowed_components},
                fix_hint="优先保留 root 或一个关键背板的低强度阴影，其余层用边框或色阶区分。",
            )
        )
    if len(border_widths) > thresholds.max_border_width_values:
        diagnostics.append(
            diagnostic(
                "warning",
                "AESTHETIC_STYLE_STROKE_INCONSISTENT",
                "同一卡片混用过多描边粗细，组件边界显得不统一。",
                json_pointer="/updateComponents/components",
                actual={
                    "borderWidthValues": sorted(border_widths),
                    "componentIdsByBorderWidth": {
                        str(width): component_ids
                        for width, component_ids in sorted(border_widths.items())
                    },
                },
                expected={"maxBorderWidthValues": thresholds.max_border_width_values},
                fix_hint="优先统一为一个主描边规格；只有进度、分隔线等独立角色才使用第二规格。",
            )
        )
    return diagnostics


def evaluate_surface_nesting(
    context: AestheticContext, thresholds: Thresholds
) -> list[dict[str, Any]]:
    deepest: tuple[str, list[str]] | None = None
    for component in context.components:
        component_id = component.get("id")
        if not isinstance(component_id, str) or not is_effectively_visible(
            component_id, context.components_by_id, context.parent_by_child
        ):
            continue
        surface_ids: list[str] = []
        current_id: str | None = component_id
        while current_id is not None:
            current = context.components_by_id.get(current_id, {})
            styles = current.get("styles") if isinstance(current, dict) else None
            is_non_root = current_id in context.parent_by_child
            if is_non_root and isinstance(styles, dict) and any(
                field in styles for field in ("backgroundColor", "linearGradient")
            ):
                surface_ids.append(current_id)
            current_id = context.parent_by_child.get(current_id)
        if deepest is None or len(surface_ids) > len(deepest[1]):
            deepest = (component_id, surface_ids)

    if deepest is None or len(deepest[1]) <= thresholds.max_nested_surfaces:
        return []
    component_id, surface_ids = deepest
    return [
        diagnostic(
            "warning",
            "AESTHETIC_STYLE_SURFACE_NESTING_EXCESSIVE",
            "内容背板层级过深，卡片出现明显的卡片套卡片风险。",
            json_pointer=f"/updateComponents/components/{context.source_index_by_id[component_id]}",
            actual={"componentId": component_id, "nestedSurfaceIds": surface_ids},
            expected={"maxNestedSurfaces": thresholds.max_nested_surfaces},
            fix_hint="合并相邻背板，将层级收敛为 root 加一个内容面，必要时再保留一个弱分组面。",
        )
    ]


SPACING_TOKENS = frozenset({0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0})


def evaluate_spacing_tokens(context: AestheticContext) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    for component in context.components:
        component_id = component.get("id")
        if not isinstance(component_id, str) or not is_effectively_visible(
            component_id, context.components_by_id, context.parent_by_child
        ):
            continue
        for field in ("itemMargin", "space"):
            value = numeric(component.get(field))
            if value is not None and value not in SPACING_TOKENS:
                violations.append(
                    {"componentId": component_id, "field": field, "value": value}
                )
        styles = component.get("styles")
        if not isinstance(styles, dict):
            continue
        for field in ("margin", "padding"):
            for path, value in iter_spacing_numbers(styles.get(field), field):
                if value not in SPACING_TOKENS:
                    violations.append(
                        {"componentId": component_id, "field": path, "value": value}
                    )

    if not violations:
        return []
    return [
        diagnostic(
            "warning",
            "AESTHETIC_LAYOUT_SPACING_NON_TOKEN",
            "间距未落在卡片 spacing token 阶梯内，容易破坏节奏一致性。",
            json_pointer="/updateComponents/components",
            actual={"violations": violations},
            expected={"allowedSpacingTokens": sorted(SPACING_TOKENS)},
            fix_hint="优先使用 4/8/12/16vp；仅在严密预算时使用 2/6/10/14vp。",
        )
    ]


def iter_spacing_numbers(value: object, path: str) -> list[tuple[str, float]]:
    number = numeric(value)
    if number is not None:
        return [(path, number)]
    if isinstance(value, dict):
        results: list[tuple[str, float]] = []
        for key, child in value.items():
            results.extend(iter_spacing_numbers(child, f"{path}.{key}"))
        return results
    return []


def evaluate_fixed_layout_overflow(context: AestheticContext) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for container in context.components:
        container_id = container.get("id")
        container_type = container.get("component")
        styles = container.get("styles")
        if (
            container_type not in {"Row", "Column"}
            or not isinstance(container_id, str)
            or not isinstance(styles, dict)
            or not is_effectively_visible(
                container_id, context.components_by_id, context.parent_by_child
            )
        ):
            continue
        axis = "width" if container_type == "Row" else "height"
        available = numeric(styles.get(axis))
        if available is None:
            continue
        padding = spacing_axis_total(styles.get("padding"), axis)
        if padding is None:
            continue
        available -= padding
        child_sizes: list[float] = []
        unresolved = False
        for child_id in child_component_ids(container):
            child = context.components_by_id.get(child_id, {})
            child_styles = child.get("styles") if isinstance(child, dict) else None
            if not isinstance(child_styles, dict) or any(
                field in child_styles for field in ("layoutWeight", "flexShrink", "flexGrow")
            ):
                unresolved = True
                break
            child_size = numeric(child_styles.get(axis))
            margin = spacing_axis_total(child_styles.get("margin"), axis)
            if child_size is None or margin is None:
                unresolved = True
                break
            child_sizes.append(child_size + margin)
        if unresolved or not child_sizes:
            continue
        gap = numeric(container.get("itemMargin"))
        if gap is None:
            if "itemMargin" in container:
                continue
            gap = 0.0
        required = sum(child_sizes) + gap * (len(child_sizes) - 1)
        if required > available + 1e-9:
            diagnostics.append(
                diagnostic(
                    "warning",
                    "AESTHETIC_LAYOUT_BOUNDS_OVERFLOW",
                    "固定尺寸子项超过容器可用空间，存在溢出或挤压风险。",
                    json_pointer=f"/updateComponents/components/{context.source_index_by_id[container_id]}",
                    actual={
                        "containerId": container_id,
                        "axis": axis,
                        "available": available,
                        "required": required,
                        "childSizes": child_sizes,
                        "itemMargin": gap,
                    },
                    expected={"required": f"<= {available}"},
                    fix_hint="缩短固定尺寸、减少间距，或改用已验证的弹性布局并在真实渲染中复核。",
                )
            )
    return diagnostics


def spacing_axis_total(value: object, axis: str) -> float | None:
    if value is None:
        return 0.0
    number = numeric(value)
    if number is not None:
        return number * 2
    if not isinstance(value, dict):
        return None
    first = "left" if axis == "width" else "top"
    second = "right" if axis == "width" else "bottom"
    first_value = numeric(value.get(first, 0))
    second_value = numeric(value.get(second, 0))
    if first_value is None or second_value is None:
        return None
    return first_value + second_value


def evaluate_static_text_clip_risk(context: AestheticContext) -> list[dict[str, Any]]:
    """Warn when a literal text string cannot fit a fully static text box.

    This is deliberately a conservative estimate, not a font-shaping engine: it
    only emits when content, width, line count, font size and horizontal padding
    are all static. Dynamic text, adaptive size and unconstrained width are left
    to the real renderer/UCD review instead of being guessed.
    """

    diagnostics: list[dict[str, Any]] = []
    for component in context.components:
        component_id = component.get("id")
        component_type = component.get("component")
        styles = component.get("styles")
        if (
            component_type not in {"Text", "Button"}
            or not isinstance(component_id, str)
            or not isinstance(styles, dict)
            or not is_effectively_visible(
                component_id, context.components_by_id, context.parent_by_child
            )
        ):
            continue
        content = visible_text_value(component)
        width = numeric(styles.get("width"))
        font_size = numeric(styles.get("fontSize"))
        if font_size is None and "fontSize" in styles:
            continue
        if font_size is None:
            font_size = 16.0
        max_lines = numeric(styles.get("maxLines")) or 1.0
        padding = spacing_axis_total(styles.get("padding"), "width")
        if (
            content is None
            or is_dynamic_dsl_value(content)
            or width is None
            or padding is None
            or max_lines <= 0
            or any(field in styles for field in ("minFontSize", "maxFontSize"))
        ):
            continue
        available = width - padding
        estimated = estimate_text_width(content, font_size)
        capacity = max(available, 0.0) * max_lines
        if estimated <= capacity + 1e-9:
            continue
        diagnostics.append(
            diagnostic(
                "warning",
                "AESTHETIC_TEXT_CLIP_RISK",
                "静态文本长度超过可证明的文本框容量，存在截断、换行失控或省略号风险。",
                json_pointer=f"/updateComponents/components/{context.source_index_by_id[component_id]}/styles",
                actual={
                    "componentId": component_id,
                    "estimatedTextWidth": round(estimated, 2),
                    "estimatedCapacity": round(capacity, 2),
                    "width": width,
                    "horizontalPadding": padding,
                    "maxLines": max_lines,
                    "fontSize": font_size,
                },
                expected="estimatedTextWidth <= availableWidth * maxLines",
                fix_hint="缩短文案、增加可用宽度/行数，或在真实渲染中确认可接受的省略策略。",
            )
        )
    return diagnostics


def visible_text_value(component: dict[str, Any]) -> str | None:
    field = "label" if component.get("component") == "Button" else "content"
    value = component.get(field)
    return value if isinstance(value, str) and value.strip() else None


def is_dynamic_dsl_value(value: object) -> bool:
    return isinstance(value, str) and "{{" in value and "}}" in value


def estimate_text_width(text: str, font_size: float) -> float:
    """Fast, deterministic CJK/Latin width proxy for clear overflow cases."""

    units = 0.0
    for character in text:
        if character.isspace():
            units += 0.35
        elif ord(character) >= 0x2E80:
            units += 1.0
        elif character.isalnum():
            units += 0.6
        else:
            units += 0.45
    return units * font_size


def evaluate_action_target_size(context: AestheticContext) -> list[dict[str, Any]]:
    """Check only statically sized Button controls; unknown targets are not guessed."""

    diagnostics: list[dict[str, Any]] = []
    for component in context.components:
        component_id = component.get("id")
        styles = component.get("styles")
        if (
            not is_action_container(component)
            or not isinstance(component_id, str)
            or not isinstance(styles, dict)
            or not is_effectively_visible(
                component_id, context.components_by_id, context.parent_by_child
            )
        ):
            continue
        width, height = numeric(styles.get("width")), numeric(styles.get("height"))
        if width is None or height is None or (width >= 24 and height >= 24):
            continue
        diagnostics.append(
            diagnostic(
                "warning",
                "AESTHETIC_ACTION_TOO_SMALL",
                "静态按钮热区小于 24×24vp，容易误触且不利于可用性。",
                json_pointer=f"/updateComponents/components/{context.source_index_by_id[component_id]}/styles",
                actual={"componentId": component_id, "width": width, "height": height},
                expected={"minWidth": 24, "minHeight": 24},
                fix_hint="将可点击区域扩展到至少 24×24vp；视觉图标可小，但热区不应随之缩小。",
            )
        )
    return diagnostics


def evaluate_false_affordance(context: AestheticContext) -> list[dict[str, Any]]:
    """Find static Text pills that visually resemble a button but expose no action.

    It intentionally reports a risk rather than a hard error: tags can be valid
    static content, while the result gives UCD a precise review target.
    """

    risks: list[str] = []
    for component in context.components:
        component_id = component.get("id")
        styles = component.get("styles")
        if (
            component.get("component") != "Text"
            or not isinstance(component_id, str)
            or not isinstance(styles, dict)
            or visible_text_value(component) is None
            or not is_effectively_visible(
                component_id, context.components_by_id, context.parent_by_child
            )
        ):
            continue
        has_surface = "backgroundColor" in styles or "linearGradient" in styles
        has_pill_shape = (numeric(styles.get("borderRadius")) or 0) > 0
        has_box = numeric(styles.get("width")) is not None and numeric(styles.get("height")) is not None
        if has_surface and has_pill_shape and has_box and not has_effective_action(
            component_id, context
        ):
            risks.append(component_id)
    if not risks:
        return []
    return [
        diagnostic(
            "warning",
            "AESTHETIC_AFFORDANCE_FALSE_POSITIVE",
            "静态文字呈现为可点击 pill/按钮样式，但 DSL 未声明动作，存在假按钮风险。",
            json_pointer="/updateComponents/components",
            actual={"componentIds": risks},
            expected="视觉上像按钮的元素应声明可用动作，或改成明显的非交互标签样式。",
            fix_hint="补充真实可用动作，或去除按钮式背景、固定热区和过强圆角暗示。",
        )
    ]


def evaluate_information_hierarchy(context: AestheticContext) -> list[dict[str, Any]]:
    text_items: list[tuple[str, str, float]] = []
    for component in context.components:
        component_id, component_type, styles = (
            component.get("id"),
            component.get("component"),
            component.get("styles"),
        )
        if (
            component_type not in {"Text", "Button"}
            or not isinstance(component_id, str)
            or not isinstance(styles, dict)
            or visible_text_value(component) is None
            or not is_effectively_visible(
                component_id, context.components_by_id, context.parent_by_child
            )
        ):
            continue
        size = numeric(styles.get("fontSize"))
        if size is None and "fontSize" not in styles:
            size = 16.0
        if size is None:
            continue
        weight = normalize_font_weight(styles.get("fontWeight"), component_type)
        # A bounded, explainable proxy for visual dominance; not a visual score.
        prominence = size * (1.0 + max(weight - 400.0, 0.0) / 1000.0)
        text_items.append(
            (
                component_id,
                "action" if has_effective_action(component_id, context) else str(component_type),
                prominence,
            )
        )

    if len(text_items) < 2:
        return []
    diagnostics: list[dict[str, Any]] = []
    scores = sorted(score for _, _, score in text_items)
    maximum, median = scores[-1], scores[len(scores) // 2]
    if len(text_items) >= 3 and median > 0 and maximum / median < 1.25:
        diagnostics.append(
            diagnostic(
                "warning",
                "AESTHETIC_HIERARCHY_NO_PRIMARY",
                "多个可见文本的静态字号/字重相近，缺少可计算的主信息焦点。",
                json_pointer="/updateComponents/components",
                actual={"prominence": {component_id: round(score, 2) for component_id, _, score in text_items}},
                expected="主信息应在字号或字重上与支撑信息形成明确差异。",
                fix_hint="强化一个主信息，降低辅助文字的字号或字重，避免所有内容同等抢眼。",
            )
        )
    primary_items = [item for item in text_items if item[2] >= maximum * 0.9]
    if len(primary_items) >= 3:
        diagnostics.append(
            diagnostic(
                "warning",
                "AESTHETIC_HIERARCHY_TOO_MANY_PRIMARY",
                "同一卡片存在多个同等强度的主信息，阅读顺序可能失焦。",
                json_pointer="/updateComponents/components",
                actual={"primaryComponentIds": [item[0] for item in primary_items], "maxProminence": round(maximum, 2)},
                expected="通常仅保留一个主信息；并列主信息需要明确分组或降低其中一项。",
                fix_hint="选定唯一主信息，其余改为标题、状态或支撑层级。",
            )
        )
    action_scores = [score for _, kind, score in text_items if kind == "action"]
    content_scores = [score for _, kind, score in text_items if kind != "action"]
    if action_scores and content_scores and max(action_scores) > max(content_scores) * 1.2:
        diagnostics.append(
            diagnostic(
                "warning",
                "AESTHETIC_HIERARCHY_ACTION_OVER_PRIMARY",
                "CTA 的静态文字强度明显超过内容主信息，操作可能压过卡片主题。",
                json_pointer="/updateComponents/components",
                actual={"maxActionProminence": round(max(action_scores), 2), "maxContentProminence": round(max(content_scores), 2)},
                expected="CTA 应支撑主信息，而不是在字号/字重上压过主题。",
                fix_hint="降低 CTA 字号/字重，或增强内容主信息；保留颜色作为动作识别即可。",
            )
        )
    return diagnostics


def evaluate_small_card_density(context: AestheticContext) -> list[dict[str, Any]]:
    root_id = next(
        (component_id for component_id in context.components_by_id if component_id not in context.parent_by_child),
        None,
    )
    root = context.components_by_id.get(root_id, {}) if root_id else {}
    styles = root.get("styles") if isinstance(root, dict) else None
    if not isinstance(styles, dict):
        return []
    width, height = numeric(styles.get("width")), numeric(styles.get("height"))
    if width is None or height is None or width > 180 or height > 180:
        return []
    visible_non_root = [
        component.get("id")
        for component in context.components
        if component.get("id") != root_id
        and isinstance(component.get("id"), str)
        and is_effectively_visible(
            component["id"], context.components_by_id, context.parent_by_child
        )
    ]
    if len(visible_non_root) <= 10:
        return []
    return [
        diagnostic(
            "warning",
            "AESTHETIC_LAYOUT_DENSITY_HIGH",
            "小尺寸卡片的可见组件数过多，存在信息拥挤与点击误导风险。",
            json_pointer="/updateComponents/components",
            actual={"cardSize": {"width": width, "height": height}, "visibleNonRootComponentCount": len(visible_non_root)},
            expected="2×2 静态卡片优先收敛到 10 个以内可见非 root 组件；复杂内容需真实渲染复核。",
            fix_hint="合并重复标签、隐藏次要装饰，或将详情引导至点击后的下一层。",
        )
    ]


def iter_static_style_colors(styles: dict[str, Any]) -> list[RGBA]:
    colors: list[RGBA] = []
    for field in COLOR_STYLE_FIELDS:
        parsed = parse_hex_color(styles.get(field))
        if parsed is not None:
            colors.append(parsed)
    gradient = styles.get("linearGradient")
    if isinstance(gradient, dict) and isinstance(gradient.get("colors"), list):
        for stop in gradient["colors"]:
            if isinstance(stop, list) and stop:
                parsed = parse_hex_color(stop[0])
                if parsed is not None:
                    colors.append(parsed)
    return colors


def chromatic_hue_family(color: RGBA) -> int | None:
    red, green, blue, alpha = color
    maximum = max(red, green, blue)
    minimum = min(red, green, blue)
    chroma = maximum - minimum
    if alpha < 0.6 or maximum < 0.2 or chroma < 0.2:
        return None
    if maximum == red:
        hue = ((green - blue) / chroma) % 6
    elif maximum == green:
        hue = (blue - red) / chroma + 2
    else:
        hue = (red - green) / chroma + 4
    return int((hue * 60) // 30) % 12


def build_report(
    components: list[dict[str, Any]],
    text_like_count: int,
    checked_count: int,
    diagnostics: list[dict[str, Any]],
    thresholds: Thresholds,
) -> dict[str, Any]:
    error_count = sum(item["severity"] == "error" for item in diagnostics)
    warning_count = sum(item["severity"] == "warning" for item in diagnostics)
    needs_review_count = sum(
        item["code"] == "AESTHETIC_COLOR_CONTRAST_UNDETERMINED"
        for item in diagnostics
    )
    status = (
        "fail"
        if error_count
        else "needs_review"
        if needs_review_count
        else "pass_with_warnings"
        if warning_count
        else "pass"
    )
    return {
        "schemaVersion": "0.2",
        "status": status,
        "summary": {
            "componentCount": len(components),
            "textLikeCount": text_like_count,
            "checkedCount": checked_count,
            "errorCount": error_count,
            "warningCount": warning_count,
            "needsReviewCount": needs_review_count,
        },
        "thresholds": {
            "normalTextMin": thresholds.normal_text_min,
            "largeTextMin": thresholds.large_text_min,
            "criticalMin": thresholds.critical_min,
            "largeFontSize": thresholds.large_font_size,
            "largeBoldFontSize": thresholds.large_bold_font_size,
            "largeBoldFontWeight": thresholds.large_bold_font_weight,
            "maxChromaticFamilies": thresholds.max_chromatic_families,
            "maxGradientSurfaces": thresholds.max_gradient_surfaces,
            "maxGradientStops": thresholds.max_gradient_stops,
            "maxTranslucentSurfaceLayers": thresholds.max_translucent_surface_layers,
            "maxFontSizeLevels": thresholds.max_font_size_levels,
            "maxRadiusValues": thresholds.max_radius_values,
            "maxShadowedComponents": thresholds.max_shadowed_components,
            "maxBorderWidthValues": thresholds.max_border_width_values,
            "maxNestedSurfaces": thresholds.max_nested_surfaces,
        },
        "diagnostics": diagnostics,
    }


def has_visible_text(component: dict[str, Any]) -> bool:
    field = "label" if component.get("component") == "Button" else "content"
    value = component.get(field)
    if isinstance(value, str):
        return bool(value.strip())
    return value is not None


def component_is_statically_hidden(component: dict[str, Any]) -> bool:
    styles = component.get("styles")
    return isinstance(styles, dict) and styles.get("visibility") in {"hidden", "none"}


def is_effectively_visible(
    component_id: str,
    components_by_id: dict[str, dict[str, Any]],
    parent_by_child: dict[str, str],
) -> bool:
    current_id: str | None = component_id
    while current_id is not None:
        component = components_by_id.get(current_id, {})
        if component_is_statically_hidden(component):
            return False
        current_id = parent_by_child.get(current_id)
    return True


def resolve_background_candidates(
    component_id: str,
    components_by_id: dict[str, dict[str, Any]],
    parent_by_child: dict[str, str],
) -> tuple[list[RGBA], list[str], list[str]]:
    ancestry: list[str] = []
    current_id: str | None = component_id
    while current_id:
        ancestry.append(current_id)
        current_id = parent_by_child.get(current_id)

    candidates: list[RGBA] = []
    base_known = False
    descriptions: list[str] = []
    uncertainty: list[str] = []
    requires_solid_cover = False
    path = list(reversed(ancestry))
    for path_index, ancestor_id in enumerate(path):
        component = components_by_id.get(ancestor_id, {})
        styles = component.get("styles", {}) if isinstance(component, dict) else {}
        if not isinstance(styles, dict):
            continue

        if "backgroundImage" in styles:
            candidates = []
            base_known = False
            descriptions.append(f"{ancestor_id}:backgroundImage")
            uncertainty.append(f"{ancestor_id} 使用 backgroundImage")
            requires_solid_cover = True
        else:
            layer_kind = (
                "gradient"
                if "linearGradient" in styles
                else "solid"
                if "backgroundColor" in styles
                else ""
            )
            layer_values, layer_description, layer_uncertainty = background_layer(styles)
            if layer_uncertainty:
                candidates = []
                base_known = False
                uncertainty.append(f"{ancestor_id} {layer_uncertainty}")
                requires_solid_cover = True
            elif layer_values:
                descriptions.append(f"{ancestor_id}:{layer_description}")
                rounded_exposes_parent = (
                    path_index > 0
                    and base_known
                    and bool(candidates)
                    and not shape_value_is_zero(styles.get("borderRadius"))
                )
                if all(layer[3] >= 0.999 for layer in layer_values):
                    if requires_solid_cover and (
                        layer_kind != "solid"
                        or not solid_layer_can_clear_image_taint(styles)
                    ):
                        candidates = []
                        base_known = False
                        uncertainty.append(
                            f"{ancestor_id} 的背景无法证明完整遮住图片像素"
                        )
                    else:
                        candidate_count = len(layer_values) + (
                            len(candidates) if rounded_exposes_parent else 0
                        )
                        if candidate_count > MAX_BACKGROUND_CANDIDATES:
                            candidates = []
                            base_known = False
                            requires_solid_cover = True
                            uncertainty.append(
                                f"{ancestor_id} 的背景候选数量超过安全上限"
                            )
                        else:
                            candidates = (
                                [*candidates, *layer_values]
                                if rounded_exposes_parent
                                else list(layer_values)
                            )
                            base_known = True
                            requires_solid_cover = False
                            if rounded_exposes_parent:
                                descriptions.append(
                                    f"{ancestor_id}:roundedExposesParent"
                                )
                elif base_known and candidates:
                    parent_candidates = list(candidates)
                    combination_count = len(layer_values) * len(parent_candidates)
                    candidate_count = combination_count + (
                        len(parent_candidates) if rounded_exposes_parent else 0
                    )
                    if candidate_count > MAX_BACKGROUND_CANDIDATES:
                        candidates = []
                        base_known = False
                        requires_solid_cover = True
                        uncertainty.append(
                            f"{ancestor_id} 的透明背景组合数 {combination_count} "
                            f"超过安全上限 {MAX_BACKGROUND_CANDIDATES}"
                        )
                    else:
                        candidates = [
                            composite(layer, background)
                            for layer in layer_values
                            for background in parent_candidates
                        ]
                        if rounded_exposes_parent:
                            candidates = [*parent_candidates, *candidates]
                            descriptions.append(
                                f"{ancestor_id}:roundedExposesParent"
                            )
                else:
                    candidates = []
                    base_known = False
                    uncertainty.append(f"{ancestor_id} 的半透明背景缺少可确定底色")
                    requires_solid_cover = True

        branch_id = path[path_index + 1] if path_index + 1 < len(path) else None
        sibling_tainted, sibling_cover, visual_siblings = stack_sibling_effect(
            component, branch_id, components_by_id
        )
        if sibling_tainted:
            candidates = []
            base_known = False
            requires_solid_cover = True
            descriptions.append(
                f"{ancestor_id}:stackSiblings({','.join(visual_siblings)})"
            )
            uncertainty.append(
                f"{ancestor_id} 的 Stack 分支后方存在视觉兄弟层："
                + ", ".join(visual_siblings)
            )
        elif sibling_cover is not None:
            candidates = [sibling_cover]
            base_known = True
            requires_solid_cover = False
            descriptions.append(f"{ancestor_id}:opaqueSolidStackCover")
    return candidates if base_known else [], descriptions, uncertainty


def solid_layer_can_clear_image_taint(styles: dict[str, Any]) -> bool:
    if styles.get("visibility") not in (None, "visible"):
        return False
    return shape_value_is_zero(styles.get("borderRadius"))


def shape_value_is_zero(value: object) -> bool:
    if value is None:
        return True
    number = numeric(value)
    if number is not None:
        return abs(number) < 1e-9
    if isinstance(value, dict):
        return all(shape_value_is_zero(item) for item in value.values())
    return False


def stack_sibling_effect(
    component: dict[str, Any],
    branch_id: str | None,
    components_by_id: dict[str, dict[str, Any]],
) -> tuple[bool, RGBA | None, list[str]]:
    if component.get("component") != "Stack" or not isinstance(branch_id, str):
        return False, None, []
    children = component.get("children")
    if not isinstance(children, list) or branch_id not in children:
        return False, None, []
    tainted = False
    cover: RGBA | None = None
    visual_siblings: list[str] = []
    for sibling_id in children[: children.index(branch_id)]:
        if not isinstance(sibling_id, str):
            continue
        if not subtree_has_visual_layer(sibling_id, components_by_id, set()):
            continue
        visual_siblings.append(sibling_id)
        sibling = components_by_id.get(sibling_id, {})
        proven_cover = proven_full_opaque_solid_cover(sibling, component)
        if proven_cover is not None:
            tainted = False
            cover = proven_cover
        else:
            tainted = True
            cover = None
    return tainted, cover, visual_siblings


def proven_full_opaque_solid_cover(
    sibling: dict[str, Any], stack: dict[str, Any]
) -> RGBA | None:
    if sibling.get("component") != "Text" or child_component_ids(sibling):
        return None
    content = sibling.get("content")
    if not isinstance(content, str) or content.strip():
        return None
    sibling_styles = sibling.get("styles")
    stack_styles = stack.get("styles")
    if not isinstance(sibling_styles, dict) or not isinstance(stack_styles, dict):
        return None
    safe_style_fields = {
        "width",
        "height",
        "backgroundColor",
        "visibility",
        "maxLines",
    }
    if set(sibling_styles) - safe_style_fields:
        return None
    if sibling_styles.get("visibility") not in (None, "visible"):
        return None
    color = parse_hex_color(sibling_styles.get("backgroundColor"))
    if color is None or color[3] < 0.999:
        return None
    stack_size_can_differ = any(
        field in stack_styles
        for field in ("constraintSize", "layoutWeight", "flexGrow", "flexShrink")
    )
    if not dimension_covers(
        sibling_styles.get("width"),
        stack_styles.get("width"),
        stack_size_can_differ=stack_size_can_differ,
    ) or not dimension_covers(
        sibling_styles.get("height"),
        stack_styles.get("height"),
        stack_size_can_differ=stack_size_can_differ,
    ):
        return None
    return color


def dimension_covers(
    layer_value: object,
    stack_value: object,
    *,
    stack_size_can_differ: bool = False,
) -> bool:
    if isinstance(layer_value, str) and layer_value in {"matchParent", "100%"}:
        return True
    if stack_size_can_differ:
        return False
    layer_size = numeric(layer_value)
    stack_size = numeric(stack_value)
    return (
        layer_size is not None
        and stack_size is not None
        and layer_size >= stack_size
    )


def subtree_has_visual_layer(
    component_id: str,
    components_by_id: dict[str, dict[str, Any]],
    visited: set[str],
) -> bool:
    if component_id in visited:
        return False
    visited.add(component_id)
    component = components_by_id.get(component_id, {})
    if component_is_statically_hidden(component):
        return False
    styles = component.get("styles", {}) if isinstance(component, dict) else {}
    if component.get("component") == "Image" or (
        isinstance(styles, dict)
        and any(
            field in styles
            for field in ("backgroundColor", "backgroundImage", "linearGradient")
        )
    ):
        return True
    return any(
        subtree_has_visual_layer(child_id, components_by_id, visited)
        for child_id in child_component_ids(component)
    )


def child_component_ids(component: dict[str, Any]) -> list[str]:
    children = component.get("children")
    if isinstance(children, list):
        return [child_id for child_id in children if isinstance(child_id, str)]
    if isinstance(children, dict) and isinstance(children.get("componentId"), str):
        return [children["componentId"]]
    return []


def has_declared_action(component: dict[str, Any]) -> bool:
    """Match the protocol's component-level onClick carrier conservatively."""

    handlers = component.get("onClick")
    return isinstance(handlers, list) and bool(handlers)


def is_action_container(component: dict[str, Any]) -> bool:
    """Buttons are action-shaped; other components need a declared onClick."""

    return component.get("component") == "Button" or has_declared_action(component)


def has_effective_action(component_id: str, context: AestheticContext) -> bool:
    """A child inherits the click affordance of any visible ancestor container."""

    current_id: str | None = component_id
    while current_id is not None:
        component = context.components_by_id.get(current_id, {})
        if is_action_container(component):
            return True
        current_id = context.parent_by_child.get(current_id)
    return False


def background_layer(styles: dict[str, Any]) -> tuple[list[RGBA], str, str]:
    if "linearGradient" in styles:
        gradient = styles.get("linearGradient")
        if not isinstance(gradient, dict) or not isinstance(gradient.get("colors"), list):
            return [], "", "linearGradient 无法静态解析"
        colors: list[RGBA] = []
        labels: list[str] = []
        for stop in gradient["colors"]:
            if not (isinstance(stop, list) and len(stop) == 2):
                return [], "", "linearGradient stop 无法静态解析"
            parsed = parse_hex_color(stop[0])
            if parsed is None:
                return [], "", "linearGradient 颜色无法静态解析"
            colors.append(parsed)
            labels.append(str(stop[0]))
        return colors, "linearGradient(" + ",".join(labels) + ")", ""

    if "backgroundColor" in styles:
        value = styles.get("backgroundColor")
        parsed = parse_hex_color(value)
        if parsed is None:
            return [], "", "backgroundColor 无法静态解析"
        return [parsed], f"backgroundColor({value})", ""
    return [], "", ""


def parse_hex_color(value: object) -> RGBA | None:
    if not isinstance(value, str) or not value.startswith("#"):
        return None
    raw = value[1:]
    try:
        if len(raw) == 6:
            alpha = 255
            red, green, blue = int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
        elif len(raw) == 8:
            alpha = int(raw[0:2], 16)
            red, green, blue = int(raw[2:4], 16), int(raw[4:6], 16), int(raw[6:8], 16)
        else:
            return None
    except ValueError:
        return None
    return red / 255, green / 255, blue / 255, alpha / 255


def composite(foreground: RGBA, background: RGBA) -> RGBA:
    fg_red, fg_green, fg_blue, fg_alpha = foreground
    bg_red, bg_green, bg_blue, bg_alpha = background
    out_alpha = fg_alpha + bg_alpha * (1 - fg_alpha)
    if out_alpha == 0:
        return 0, 0, 0, 0
    return (
        (fg_red * fg_alpha + bg_red * bg_alpha * (1 - fg_alpha)) / out_alpha,
        (fg_green * fg_alpha + bg_green * bg_alpha * (1 - fg_alpha)) / out_alpha,
        (fg_blue * fg_alpha + bg_blue * bg_alpha * (1 - fg_alpha)) / out_alpha,
        out_alpha,
    )


def contrast_ratio(foreground: RGBA, background: RGBA) -> float | None:
    if background[3] < 0.999:
        return None
    visible_foreground = composite(foreground, background)
    foreground_luminance = relative_luminance(visible_foreground)
    background_luminance = relative_luminance(background)
    lighter = max(foreground_luminance, background_luminance)
    darker = min(foreground_luminance, background_luminance)
    return (lighter + 0.05) / (darker + 0.05)


def relative_luminance(color: RGBA) -> float:
    red, green, blue, _ = color
    return 0.2126 * linearize(red) + 0.7152 * linearize(green) + 0.0722 * linearize(blue)


def linearize(channel: float) -> float:
    if channel <= 0.04045:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, str):
        match = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)(?:vp|fp|px)?\s*", value)
        if match:
            number = float(match.group(1))
            return number if math.isfinite(number) else None
    return None


def normalize_font_weight(value: object, component_type: object) -> float:
    number = numeric(value)
    if number is not None:
        return number
    if isinstance(value, str):
        named_weights = {
            "lighter": 100.0,
            "normal": 400.0,
            "regular": 400.0,
            "medium": 500.0,
            "bold": 700.0,
            "bolder": 900.0,
        }
        if value in named_weights:
            return named_weights[value]
    return 500.0 if component_type == "Button" else 400.0


def smallest_possible_font_size(
    styles: dict[str, Any], declared_size: float
) -> tuple[float, bool]:
    smallest = declared_size
    uncertain = False
    for field in ("minFontSize", "maxFontSize"):
        if field not in styles:
            continue
        value = numeric(styles.get(field))
        if value is None:
            smallest = 0.0
            uncertain = True
        else:
            smallest = min(smallest, value)
    return smallest, uncertain


def diagnostic(
    severity: str,
    code: str,
    message: str,
    *,
    line: int | None = None,
    json_pointer: str = "",
    logical_path: str = "",
    actual: Any = None,
    expected: Any = None,
    fix_hint: str = "",
) -> dict[str, Any]:
    result = {
        "severity": severity,
        "code": code,
        "message": message,
        "line": line,
        "jsonPointer": json_pointer,
        "logicalPath": logical_path,
        "actual": actual,
        "expected": expected,
        "fixHint": fix_hint,
    }
    return {key: value for key, value in result.items() if value not in (None, "")}


def render_text(report: dict[str, Any]) -> str:
    lines = [
        f"status: {report['status']}",
        f"checked: {report['summary']['checkedCount']}/{report['summary']['textLikeCount']}",
    ]
    for item in report["diagnostics"]:
        location = item.get("jsonPointer", "genui")
        lines.append(f"{item['severity'].upper()} {item['code']} {location}")
        lines.append(f"问题: {item['message']}")
        if item.get("actual") is not None:
            lines.append(
                "当前: "
                + json.dumps(item["actual"], ensure_ascii=False, allow_nan=False)
            )
        if item.get("expected") is not None:
            lines.append(
                "期望: "
                + json.dumps(item["expected"], ensure_ascii=False, allow_nan=False)
            )
        if item.get("fixHint"):
            lines.append(f"建议: {item['fixHint']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Standalone DSL-only aesthetic risk validator")
    parser.add_argument(
        "path", nargs="?", default="-", help="genui JSONL file, fenced draft, or '-' for stdin"
    )
    parser.add_argument("--format", choices=["json", "text"], default="text")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failed exit code")
    parser.add_argument(
        "--allow-undetermined",
        action="store_true",
        help="Allow IMAGE/dynamic contrast cases to exit 0; default requires review.",
    )
    parser.add_argument("--normal-min", type=float, default=4.5)
    parser.add_argument("--large-min", type=float, default=3.0)
    parser.add_argument("--critical-min", type=float, default=3.0)
    args = parser.parse_args()

    try:
        thresholds = Thresholds(
            normal_text_min=args.normal_min,
            large_text_min=args.large_min,
            critical_min=args.critical_min,
        )
    except ValueError as exc:
        parser.error(str(exc))

    report = analyze(read_text(args.path), thresholds)
    print(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
        if args.format == "json"
        else render_text(report)
    )
    if report["summary"]["errorCount"]:
        return 1
    if report["summary"]["needsReviewCount"] and not args.allow_undetermined:
        return 1
    if args.strict and report["summary"]["warningCount"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
