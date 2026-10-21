"""生成前的有限组合搜索；只产生实现建议，不改写产物或放宽发布校验。"""

from __future__ import annotations

import copy
import itertools
import json
import math
import re
from dataclasses import dataclass, field
from typing import Any

from services.compact_component_runtime import (
    component_visual_recipe,
    secondary_body_variant,
    text_block_width_contract,
)
from services.compact_layout_runtime import load_layout_contract
from services.compact_reference_canvas import reference_dimension
from services.compact_slot_compatibility import auxiliary_groups_have_core, check_component_slot

_CONTAINERS = {"Column", "Row", "Stack"}
_SEARCH_LIMIT = 4096
_RESULT_LIMIT = 3
_DURATION_PART = r"\d+(?:\.\d+)?\s*(?:小时|分钟|毫秒|天|时|分|秒)"
_COMPOUND_DURATION = re.compile(rf"\s*(?:{_DURATION_PART}\s*){{2,}}")


@dataclass
class Region:
    path: tuple[int, ...]
    kind: str
    props: dict[str, Any]
    rule: dict[str, Any]
    children: list[Region] = field(default_factory=list)
    width: float = 0.0
    height: float = 0.0


def feasible_composition_candidates(
    size: str,
    plan: dict[str, Any],
    task: dict[str, Any],
    *, display_samples: dict[str, str] | None = None,
    display_roles: dict[str, dict[str, Any]] | None = None,
    action_labels: dict[str, str] | None = None,
) -> dict[str, Any]:
    """列出完整参考解；搜索未命中不是新失败，也不能视为合同无解。"""
    facts = plan.get("info_required", [])
    unresolved: list[str] = []
    choices = _group_choices(
        size, facts, plan, task, unresolved, display_samples=display_samples,
        display_roles=display_roles,
    )
    if unresolved:
        return {"status": "unresolved", "unresolved": unresolved, "candidates": []}
    actions = _action_groups(
        size,
        facts,
        task,
        plan,
        unresolved,
        action_labels=action_labels,
    )
    if unresolved:
        return {"status": "unresolved", "unresolved": unresolved, "candidates": []}
    layouts = load_layout_contract().get("layouts", {})
    preferred = plan.get("layoutHints", [])
    ordered = sorted(
        layouts,
        key=lambda name: preferred.index(name) if name in preferred else len(preferred),
    )
    candidates: list[dict[str, Any]] = []
    examined = 0
    diagnostics: list[dict[str, Any]] = []
    pattern_count = sum(
        len(value.get("patterns", [])) for value in layouts.values() if value.get("size") == size
    )
    pattern_budget = max(1, _SEARCH_LIMIT // max(1, pattern_count))
    limited = False
    for name in ordered:
        layout = layouts.get(name, {})
        if layout.get("size") != size:
            continue
        # 当前求解器只构造独立按钮，不支持该布局的只读列表整体点击。
        if name == "W-top-bottom" and actions:
            continue
        count = layout.get("actionCount", {})
        if not count.get("min", 0) <= len(actions) <= count.get("max", 0):
            continue
        for variant, pattern in enumerate(layout.get("patterns", []), start=1):
            previous_count = len(candidates)
            pattern_stop = examined + pattern_budget
            tree = _region_tree(size, pattern.get("rules", []))
            if tree is None:
                continue
            zones = _leaves(tree)
            for combination in itertools.product(*choices):
                examined += 1
                if examined >= pattern_stop:
                    limited = True
                    break
                groups: list[dict[str, Any]] = []
                for bundle in combination:
                    groups.extend(copy.deepcopy(bundle))
                if not auxiliary_groups_have_core(groups):
                    continue
                for allocation in _allocations(zones, groups, actions, size, layout_id=name):
                    examined += 1
                    if examined >= pattern_stop:
                        limited = True
                        break
                    if allocation is None:
                        continue
                    regions = _close_regions(zones, allocation, size)
                    if regions is None:
                        continue
                    candidate = {"layout": name, "variant": variant, "regions": regions}
                    if _all_facts_covered(candidate, len(facts)):
                        candidates.append(candidate)
                        break
                if len(candidates) > previous_count:
                    break
                if examined >= pattern_stop:
                    break
            if len(candidates) == previous_count:
                diagnostics.append(
                    {
                        "layout": name,
                        "variant": variant,
                        "reason": "no complete allocation in supported search",
                    }
                )
            if len(candidates) >= _RESULT_LIMIT or examined >= _SEARCH_LIMIT:
                break
        if len(candidates) >= _RESULT_LIMIT or examined >= _SEARCH_LIMIT:
            break
    return {
        "status": "reference_candidates" if candidates else "no_candidate_found",
        "candidates": candidates,
        "examinedAllocations": examined,
        "searchLimited": limited,
        "diagnostics": diagnostics,
        "applicationPolicy": "Preserve a valid, closed existing composition; use a complete "
        "alternative only when its actual implementation conflicts.",
        "widthEvidence": "Recipe fonts plus complete pressure samples; not device measurement. "
        "Labels/units must remain within the recorded allowance. "
        "Unknown dynamic lengths still require generation-time review.",
    }


def _part(size: str, name: str, part: str, variant: str | None = None) -> dict[str, Any]:
    recipe = component_visual_recipe(name, size=size, variant=variant)
    return recipe.get("parts", {}).get(part, {}).get("styles", {})


def _extent(value: Any, axis: str) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) * 2
    if isinstance(value, dict):
        sides = ("left", "right") if axis == "width" else ("top", "bottom")
        return sum(float(value.get(side, 0)) for side in sides)
    return 0.0


def _schema_value(task: dict[str, Any], path: str) -> dict[str, Any]:
    node = task.get("dataModelSchema", {})
    for token in path.removeprefix("/").split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(node, list) and token.isdigit():
            index = int(token)
            node = node[index] if index < len(node) else None
        elif isinstance(node, dict):
            node = node.get("items") if token.isdigit() and "items" in node else node.get(token)
        else:
            return {}
    return node if isinstance(node, dict) else {}


def is_compound_duration_text(value: Any) -> bool:
    """只识别完整多段时长样值，不推测字段名、不拆单位或执行表达式。"""
    return isinstance(value, str) and _COMPOUND_DURATION.fullmatch(value) is not None


def compound_duration_bindings(plan: dict[str, Any], task: dict[str, Any]) -> list[str]:
    """列出事实中具有明确完整多段时长样值的字符串绑定。"""
    paths: list[str] = []
    for fact in plan.get("info_required", []):
        path = fact.get("dataId")
        if not isinstance(path, str):
            continue
        schema_field = _schema_value(task, path)
        if schema_field.get("type") != "string":
            continue
        if is_compound_duration_text(schema_field.get("sampleValue")) and path not in paths:
            paths.append(path)
    return paths


def _pressure(
    fact: dict[str, Any], task: dict[str, Any], display_samples: dict[str, str] | None = None,
) -> str | None:
    path = fact.get("dataId")
    value = _schema_value(task, path).get("sampleValue") if path else fact.get("text")
    if isinstance(value, bool):
        # 只能使用失败源中已存在的完整两分支文字；未知映射不能用 True 的宽度证明。
        return display_samples.get(path) if display_samples is not None else None
    if isinstance(value, (str, int, float)):
        displayed = display_samples.get(path) if display_samples is not None else None
        if isinstance(displayed, str) and _text_width(displayed, 1) > _text_width(str(value), 1):
            return displayed
        return str(value)
    return None


def _text_width(value: str, font_size: float) -> float:
    # 保守压力估算，换行按实际字符累计，不把总宽直接除以行数冒充可换行。
    widths = []
    for line in value.splitlines():
        widths.append(sum(font_size * (0.6 if ch.isascii() else 1) for ch in line))
    return math.ceil(max(widths, default=0))


def _declared_unit(item: dict[str, Any]) -> str | None:
    contract = item.get("fieldContract", {})
    if contract.get("type") not in {"number", "integer"}:
        return None
    description = contract.get("description", "")
    suffix = re.search(r"必须在数值后追加[“\"]([^”\"]+)[”\"]", description)
    return suffix.group(1) if suffix is not None else None


def quantitative_main_bindings(plan: dict[str, Any], task: dict[str, Any]) -> list[str]:
    """列出已计划为量化主值的真实数值绑定，不按业务名称推测。"""
    paths = []
    for fact in plan.get("info_required", []):
        path = fact.get("dataId")
        hints = fact.get("componentHints", [])
        if not isinstance(path, str) or not hints:
            continue
        primary = hints[0] == "EmphasizedData"
        ratio = hints[0] == "InfoBlock" and "ProgressCircleSingle" in hints
        if not primary and not ratio:
            continue
        if _schema_value(task, path).get("type") in {"number", "integer"}:
            paths.append(path)
    return paths


def _group_choices(
    size: str,
    facts: list[dict[str, Any]],
    plan: dict[str, Any],
    task: dict[str, Any],
    unresolved: list[str],
    *, display_samples: dict[str, str] | None = None,
    display_roles: dict[str, dict[str, Any]] | None = None,
) -> list[list[list[dict[str, Any]]]]:
    declared: dict[int, dict[str, Any]] = {}
    event_groups: list[dict[str, Any]] = []
    event_indexes: set[int] = set()
    quantitative_paths = set(quantitative_main_bindings(plan, task))
    for region in plan.get("composition", {}).get("regions", []):
        for group in region.get("groups", []):
            for index in group.get("factIndexes", []):
                declared.setdefault(index, group)
            event = _declared_event_group(size, group, facts, task)
            if event is None:
                event = _declared_table_group(size, group, facts, task, display_samples)
            if event is not None:
                indexes = set(event.get("factIndexes", []))
                if not indexes.intersection(event_indexes):
                    event_groups.append(event)
                    event_indexes.update(indexes)
    objects: dict[str, list[dict[str, Any]]] = {}
    for index, fact in enumerate(facts):
        if fact.get("actionId"):
            continue
        if index in event_indexes:
            continue
        sample = _pressure(fact, task, display_samples)
        if sample is None:
            unresolved.append(f"fact {index}: no trustworthy display pressure sample")
            continue
        hints = fact.get("componentHints", [])
        first = hints[0] if hints else "SecondaryBody"
        if "SingleLineTitle" in hints:
            first = "SingleLineTitle"
        declared_group = declared.get(index, {})
        declared_name = declared_group.get("component")
        scalar_names = {"EmphasizedData", "EmphasisText", "SecondaryBody", "ProgressLine2"}
        if declared_name in scalar_names and "SingleLineTitle" not in hints:
            first = declared_name
        source_role = (display_roles or {}).get(fact.get("dataId"), {})
        if source_role and "SingleLineTitle" not in hints:
            first = source_role.get("component", first)
            declared_group = {**declared_group, **source_role}
            from services.compact_composition_context import literal_display_parts

            declared_group["displayParts"] = literal_display_parts(
                source_role.get("displayExpression"), task,
            )
        if fact.get("dataId") in quantitative_paths:
            first = "EmphasizedData"
            label = source_role.get("displayLabel")
            if isinstance(label, str) and label.strip():
                value = _schema_value(task, fact.get("dataId")).get("sampleValue")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    sample = str(value)
        supported = {
            "SingleLineTitle",
            "EmphasizedData",
            "EmphasisText",
            "SecondaryBody",
            "TextBlock",
            "ProgressLine2",
            "EventCard",
            "TableText",
        }
        if first not in supported:
            if "EmphasizedData" in hints:
                first = "EmphasizedData"
            elif first == "InfoBlock" and "ProgressCircleSingle" in hints:
                schema_field = _schema_value(task, fact.get("dataId", ""))
                if schema_field.get("type") not in {"number", "integer"}:
                    unresolved.append(f"fact {index}: quantitative main needs numeric contract")
                    continue
                # 数字比例主值不与状态合成小字辅文；完整数值与真实单位沿用主值规格。
                first = "EmphasizedData"
            elif first == "InfoBlock" and "EmphasisText" in hints:
                first = "EmphasisText"
            elif first == "InfoBlock" and "SecondaryBody" in hints:
                # 普通 InfoBlock 主文14fp，正文回退沿用14fp；数值+单位16fp不可降级。
                placements = declared_group.get("placements", [])
                field_type = _schema_value(task, fact.get("dataId", "")).get("type")
                if "unit" in placements or field_type not in {"string", "boolean"}:
                    unresolved.append(f"fact {index}: numeric InfoBlock needs exact unit recipe")
                    continue
                first = "SecondaryBody"
                declared_group = {}
            else:
                unresolved.append(f"fact {index}: unsupported exact recipe occupancy {first}")
                continue
        if first in {"EventCard", "TableText"}:
            # 未提供真正事件标题时不可伪造 EventCard。普通属性使用原候选中的正文回退。
            if "SecondaryBody" not in hints:
                unresolved.append(f"fact {index}: structured props cannot be reconstructed")
                continue
            first = "SecondaryBody"
        schema_field = _schema_value(task, fact.get("dataId")) if fact.get("dataId") else {}
        value = schema_field.get("sampleValue") if schema_field else fact.get("text")
        if first == "EmphasizedData" and is_compound_duration_text(value):
            # 修正错误数值选型，不把普通数值缩小，也不将完整文本拆成样例数字。
            first = "EmphasisText"
            declared_group = {}
        path = fact.get("dataId", "")
        identity = path.rsplit("/", 1)[0] if path else f"static:{index}"
        item = {
            "index": index,
            "component": first,
            "sample": sample,
            "declared": declared_group,
            "source": path or fact.get("text"),
            "object": identity,
            "meaning": fact.get("requirement"),
            "fieldContract": _schema_value(task, path) if path else {},
        }
        objects.setdefault(identity, []).append(item)
    output: list[list[list[dict[str, Any]]]] = []
    for items in objects.values():
        has_object_title = any(item.get("component") == "SingleLineTitle" for item in items)
        for item in items:
            item["hasObjectTitle"] = has_object_title
        singles = [_single_group(size, item) for item in items]
        alternatives = [singles]
        if len(singles) >= 2:
            gap = _part(size, "SecondaryBody", "root").get("itemMargin", 0)
            alternatives.append([_nested_group("Column", singles, gap)])
            wrapped = [_two_line_group(group) for group in singles]
            if wrapped != singles:
                alternatives.append([_nested_group("Column", wrapped, gap)])
        ordinary = [item for item in items if item.get("component") == "SecondaryBody"]
        if len(ordinary) >= 2:
            # 两项同行保留14fp；两项分行按12fp/12vp核算。
            for pair in itertools.combinations(ordinary, 2):
                for columns in (1, 2):
                    packed = _ordinary_pair(size, pair, columns)
                    rest = []
                    pair_indexes = {item.get("index") for item in pair}
                    for item in items:
                        if item.get("index") not in pair_indexes:
                            rest.append(_single_group(size, item))
                    alternatives.append([packed, *rest])
                packed = _ordinary_pair(size, pair, 2)
                packed.update({
                    "lines": [2, 2], "requiredHeight": packed.get("requiredHeight") * 2,
                    "minimumWidth": packed.get("minimumWidth") / 2,
                    "fullTextRequiresTwoLineReview": True,
                })
                alternatives.append([packed, *rest])
        readouts = [group for group in singles if group.get("component") == "EmphasizedData"]
        if len(readouts) == 1 and len(singles) == 3:
            texts = [group for group in singles if group is not readouts[0]]
            if all(group.get("component") != "TextBlock" for group in texts):
                gap = _part(size, "SecondaryBody", "root").get("itemMargin", 0)
                text_column = _nested_group("Column", texts, gap)
                alternatives.append([_nested_group("Row", [text_column, readouts[0]], gap)])
        blocks = [item for item in items if item.get("component") == "TextBlock"]
        if 2 <= len(blocks) <= 4:
            rest = [_single_group(size, item) for item in items if item not in blocks]
            alternatives.insert(0, [_text_block(size, blocks), *rest])
        output.append(alternatives)
    for event in event_groups:
        output.append([[event]])
    return output


def _nested_group(
    direction: str, groups: list[dict[str, Any]], gap: float,
) -> dict[str, Any]:
    widths = [group.get("minimumWidth") for group in groups]
    heights = [group.get("requiredHeight") for group in groups]
    indexes = []
    for group in groups:
        indexes.extend(group.get("factIndexes", []))
    horizontal = direction == "Row"
    return {
        "component": direction, "nestedGroups": copy.deepcopy(groups), "gap": gap,
        "factIndexes": indexes, "placements": ["nestedGroups"] * len(indexes),
        "minimumWidth": sum(widths) + gap * (len(groups) - 1) if horizontal else max(widths),
        "requiredHeight": max(heights) if horizontal else sum(heights) + gap * (len(groups) - 1),
        "object": groups[0].get("object"),
    }


def _two_line_group(group: dict[str, Any]) -> dict[str, Any]:
    """原字号正文的两行列宽，逐字符验证而非总宽直接折半。"""
    result = copy.deepcopy(group)
    if group.get("component") != "SecondaryBody" or group.get("columns") != 1:
        return result
    sample = group.get("pressureOnly")
    font = group.get("fontSize")
    if not isinstance(sample, str) or not isinstance(font, (int, float)):
        return result
    minimum = group.get("minimumWidth")
    if not isinstance(minimum, (int, float)) or minimum <= 0:
        return result
    recipe = component_visual_recipe("SecondaryBody", variant="multiline")
    styles = recipe.get("parts", {}).get("text", {}).get("styles", {})
    font = styles.get("fontSize")
    for width in range(max(1, math.ceil(minimum / 2)), math.ceil(minimum) + 1):
        if _wrapped_lines(sample, font, width) <= 2:
            result.update({
                "minimumWidth": width, "lines": [2],
                "requiredHeight": styles.get("height") * 2,
                "fontSize": font,
            })
            break
    return result


def _group_text_fits(group: dict[str, Any], width: float) -> bool:
    """复核实际分配后的嵌套正文行数，不以合组高度闭合冒充文字完整。"""
    nested = group.get("nestedGroups")
    if nested:
        widths = _nested_widths(group, width)
        for child, available in zip(nested, widths, strict=True):
            if not _group_text_fits(child, available):
                return False
        return True
    if group.get("component") != "SecondaryBody":
        return group.get("minimumWidth", 0) <= width
    samples = group.get("pressureOnly")
    samples = [samples] if isinstance(samples, str) else samples
    if not isinstance(samples, list):
        # 未携带文字压力时仅沿用已有最小宽度，不声称逐字验证或新增失败门禁。
        return group.get("minimumWidth", 0) <= width
    columns = group.get("columns", 1)
    font = group.get("fontSize")
    separator = _text_width(" | ", font) if columns == 2 else 0
    available = (width - separator) / columns
    lines = group.get("lines", [])
    for sample, limit in zip(samples, lines, strict=True):
        if _wrapped_lines(sample, font, available) > limit:
            return False
    return True


def _nested_widths(group: dict[str, Any], width: float) -> list[float]:
    nested = group.get("nestedGroups", [])
    if group.get("component") != "Row":
        return [width] * len(nested)
    minimums = [child.get("minimumWidth", 0) for child in nested]
    total = sum(minimums)
    available = width - group.get("gap", 0) * max(0, len(nested) - 1)
    if total <= 0:
        return [available / len(nested)] * len(nested)
    return [available * minimum / total for minimum in minimums]


def _declared_event_group(
    size: str, group: dict[str, Any], facts: list[dict[str, Any]], task: dict[str, Any],
) -> dict[str, Any] | None:
    """仅重建完整已声明事件；不从字段名猜角色，也不创造标题或删掉备注。"""
    if group.get("component") != "EventCard":
        return None
    indexes = group.get("factIndexes", [])
    placements = group.get("placements", [])
    if not indexes or len(indexes) != len(placements) or len(set(indexes)) != len(indexes):
        return None
    items: dict[int, dict[str, list[str]]] = {}
    sources = []
    for index, placement in zip(indexes, placements, strict=True):
        if not isinstance(index, int) or not 0 <= index < len(facts):
            return None
        match = (
            re.fullmatch(r"items\[(\d+)\]\.(title|time|location)", placement)
            if isinstance(placement, str) else None
        )
        fact = facts[index]
        candidate = "EventCard" in fact.get("componentHints", [])
        if match is None or fact.get("actionId") or not candidate:
            return None
        sample = _pressure(fact, task)
        if sample is None:
            return None
        values = items.setdefault(int(match.group(1)), {})
        values.setdefault(match.group(2), []).append(sample)
        path = fact.get("dataId")
        if isinstance(path, str):
            sources.append(path)
    if sorted(items) != list(range(len(items))) or len(items) > 2:
        return None
    density = group.get("density", "normal")
    if density not in {"normal", "compact"}:
        return None
    height = 0.0
    widths = []
    fonts = {}
    for item in items.values():
        titles = item.get("title", [])
        times = item.get("time", [])
        locations = item.get("location", [])
        if len(titles) != 1 or not 1 <= len(times) <= 2 or len(locations) > 1:
            return None
        variant = "compact" if density == "compact" else (
            "withLocation" if locations else "withoutLocation"
        )
        recipe = component_visual_recipe("EventCard", size=size, variant=variant)
        parts = recipe.get("parts", {})
        title = parts.get("title", {}).get("styles", {})
        meta = parts.get("meta", {}).get("styles", {})
        fonts = {"title": title.get("fontSize"), "meta": meta.get("fontSize")}
        line_widths = [_text_width(titles[0], fonts.get("title"))]
        time_width = _text_width(" - ".join(times), fonts.get("meta"))
        if locations and density == "compact":
            location_width = _text_width(locations[0], fonts.get("meta"))
            time_width += location_width + parts.get("metaRow", {}).get("styles", {}).get(
                "itemMargin", 0
            )
        elif locations:
            line_widths.append(_text_width(locations[0], fonts.get("meta")))
        line_widths.append(time_width)
        rail_width = parts.get("rail", {}).get("styles", {}).get("width", 0)
        root_gap = parts.get("root", {}).get("styles", {}).get("itemMargin", 0)
        widths.append(max(line_widths) + rail_width + root_gap)
        height += recipe.get("metrics", {}).get("height", 0)
    if density == "compact":
        gap_recipe = component_visual_recipe("EventCard", size=size, variant="compact")
        item_margin = gap_recipe.get("metrics", {}).get("itemMargin", 0)
    else:
        item_margin = _part(size, "EventCard", "multiRoot").get("itemMargin", 0)
    height += item_margin * (len(items) - 1)
    if height <= 0:
        return None
    identity = "/".join(sources[0].split("/")[:-1]) if sources else None
    while identity and any(not path.startswith(identity + "/") for path in sources):
        identity = identity.rsplit("/", 1)[0]
    return {
        "component": "EventCard", "density": density,
        "factIndexes": list(indexes), "placements": list(placements),
        "requiredHeight": height, "minimumWidth": max(widths),
        "partFonts": fonts, "object": identity,
        "displayInstruction": "Keep every declared title/time/location binding and density; "
        "join paired start/end times without dropping either endpoint. No invented title.",
    }


def _declared_table_group(
    size: str, group: dict[str, Any], facts: list[dict[str, Any]], task: dict[str, Any],
    display_samples: dict[str, str] | None,
) -> dict[str, Any] | None:
    """保留真实已声明的明细表，不把三行表误拆成三条更高的正文。"""
    if group.get("component") != "TableText":
        return None
    indexes = group.get("factIndexes", [])
    placements = group.get("placements", [])
    if len(indexes) not in {2, 3} or len(placements) != len(indexes):
        return None
    samples = []
    sources = []
    for position, index in enumerate(indexes):
        if not isinstance(index, int) or not 0 <= index < len(facts):
            return None
        if placements[position] != f"items[{position}].value":
            return None
        fact = facts[index]
        sample = _pressure(fact, task, display_samples)
        if sample is None or "TableText" not in fact.get("componentHints", []):
            return None
        samples.append(sample)
        sources.append(fact.get("dataId", "").rsplit("/", 1)[0])
    if len(set(sources)) != 1:
        return None
    variant = "compact" if len(indexes) == 3 else None
    recipe = component_visual_recipe("TableText", size=size, variant=variant)
    styles = _part(size, "TableText", "value", variant)
    gap_key = "threeRowGap" if len(indexes) == 3 else "twoRowGap"
    gap = recipe.get("metrics", {}).get(gap_key, 0)
    return {
        "component": "TableText", "factIndexes": list(indexes),
        "placements": list(placements), "object": sources[0],
        "requiredHeight": styles.get("height") * len(indexes) + gap * (len(indexes) - 1),
        "minimumWidth": max(_text_width(sample, styles.get("fontSize")) for sample in samples),
        "fontSize": styles.get("fontSize"), "labelsRequireWidthReview": True,
        "pressureOnly": samples,
    }


def _sample_with_unit(item: dict[str, Any]) -> str:
    sample = item.get("sample")
    unit = _declared_unit(item)
    if unit is not None and not sample.rstrip().endswith(unit):
        sample += unit
    return sample


def _single_group(size: str, item: dict[str, Any]) -> dict[str, Any]:
    name = item.get("component")
    if name == "TextBlock":
        name = "SecondaryBody"  # 单项 TextBlock 不满足条数合同，原字号不能低报。
    part = {
        "SingleLineTitle": "title",
        "EmphasizedData": "value",
        "EmphasisText": "main",
        "SecondaryBody": "text",
        "ProgressLine2": "value",
    }.get(name)
    styles = _part(size, name, part)
    unit = _declared_unit(item)
    sample = item.get("sample")
    if unit is not None and name not in {"EmphasizedData", "ProgressLine2"}:
        sample = _sample_with_unit(item)
    elif unit is not None and sample.rstrip().endswith(unit):
        sample = sample.rstrip().removesuffix(unit).rstrip()
    width = _text_width(sample, styles.get("fontSize"))
    placement = {
        "SingleLineTitle": "title",
        "EmphasizedData": "value",
        "EmphasisText": "mainText",
        "SecondaryBody": "items[0].value",
        "ProgressLine2": "displayValue",
    }.get(name)
    root = _part(size, name, "root")
    height = root.get("height")
    if not isinstance(height, (int, float)):
        height = styles.get("height")
    output = {
        "component": name,
        "factIndexes": [item.get("index")],
        "placements": [placement],
        "requiredHeight": height,
        "minimumWidth": width,
        "fontSize": styles.get("fontSize"),
        "pressureOnly": sample,
        "object": item.get("object"),
        "meaning": item.get("meaning"),
    }
    if name == "SecondaryBody":
        output.update({"columns": 1, "lines": [1], "labelAllowance": 0})
    if name in {"EmphasisText", "EmphasizedData"}:
        output["splitDisplayParts"] = item.get("declared", {}).get("displayParts", [])
    if unit is not None:
        output["unitFromFieldContract"] = unit
        if name in {"EmphasizedData", "ProgressLine2"}:
            unit_width = _text_width(unit, _part(size, name, "unit").get("fontSize"))
            part = "readout" if name == "ProgressLine2" else "root"
            output["minimumWidth"] += unit_width + _part(size, name, part).get("itemMargin", 0)
        else:
            output["bindingInstruction"] = (
                "Keep the original binding and append the declared "
                "unit as a legal display expression, never a sample."
            )
    elif item.get("fieldContract", {}).get("type") in {"number", "integer"}:
        output["labelOrUnitRequiresReview"] = True
    if name == "ProgressLine2":
        output["variant"] = item.get("declared", {}).get("variant")
        output["ratioContractMustBeRetained"] = True
    needs_caption = not item.get("hasObjectTitle", False)
    if name == "EmphasizedData" and unit in {"%", "％"} and needs_caption:
        if re.fullmatch(r"\s*[+-]?(?:\d+(?:\.\d*)?|\.\d+)\s*", sample):
            title_style = _part(size, "SingleLineTitle", "title")
            caption = {
                "component": "SingleLineTitle", "factIndexes": [], "placements": [],
                "requiredHeight": _part(size, "SingleLineTitle", "root").get("height"),
                "minimumWidth": 0,
                "fontSize": title_style.get("fontSize"), "meaning": item.get("meaning"),
                "object": item.get("object"), "requiresObjectCaption": True,
            }
            gap = _part(size, "SecondaryBody", "root").get("itemMargin", 0)
            return _nested_group("Column", [caption, output], gap)
    return output


def _ordinary_pair(size: str, pair: tuple[dict[str, Any], ...], columns: int) -> dict[str, Any]:
    variant = secondary_body_variant([{"maxLines": 1}] * len(pair), columns)
    styles = _part(size, "SecondaryBody", "text", variant)
    height = styles.get("height")
    gap = _part(size, "SecondaryBody", "root").get("itemMargin", 0)
    samples = []
    for item in pair:
        samples.append(_sample_with_unit(item))
    widths = [_text_width(sample, styles.get("fontSize")) for sample in samples]
    separator = _text_width(" | ", styles.get("fontSize")) if columns == 2 else 0
    return {
        "component": "SecondaryBody",
        "columns": columns,
        "factIndexes": [item.get("index") for item in pair],
        "placements": ["items[0].value", "items[1].value"],
        "lines": [1, 1],
        "requiredHeight": height if columns == 2 else height * 2 + gap,
        "minimumWidth": max(widths) * columns + separator,
        "fontSize": styles.get("fontSize"),
        "labelAllowance": 0,
        "pressureOnly": samples,
        "unitSuffixesFromFieldContract": [_declared_unit(item) for item in pair],
        "object": pair[0].get("object"),
    }


def _text_block(size: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    contract = text_block_width_contract(size)
    root = _part(size, "TextBlock", "root")
    item_styles = _part(size, "TextBlock", "item")
    value = _part(size, "TextBlock", "value")
    item_widths = []
    for item in items:
        sample = _sample_with_unit(item)
        item_widths.append(
            max(
                contract.item_minimum_width,
                _text_width(sample, value.get("fontSize"))
                + _extent(item_styles.get("padding"), "width"),
            )
        )
    width = max(item_widths) * len(items)
    width += contract.gap * (len(items) - 1)
    return {
        "component": "TextBlock",
        "factIndexes": [item.get("index") for item in items],
        "placements": [f"items[{i}].value" for i in range(len(items))],
        "requiredHeight": root.get("constraintSize", {}).get("minHeight"),
        "minimumWidth": width,
        "labelsRequireWidthReview": True,
        "object": items[0].get("object"),
        "unitSuffixesFromFieldContract": [_declared_unit(item) for item in items],
    }


def _action_groups(
    size: str,
    facts: list[dict[str, Any]],
    task: dict[str, Any],
    plan: dict[str, Any],
    unresolved: list[str],
    *, action_labels: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    candidates = {item.get("id"): item for item in task.get("eventCandidates", [])}
    assigned_assets: dict[str, Any] = {}
    assignments = plan.get("assetAssignments")
    if isinstance(assignments, dict):
        actions = assignments.get("actions")
        if isinstance(actions, list):
            for action in actions:
                if not isinstance(action, dict):
                    continue
                action_id = action.get("actionId")
                if isinstance(action_id, str):
                    assigned_assets[action_id] = action.get("assetId")
    output: list[dict[str, Any]] = []
    for index, fact in enumerate(facts):
        identifier = fact.get("actionId")
        if not identifier:
            continue
        event = candidates.get(identifier)
        if event is None:
            unresolved.append(f"action fact {index}: missing complete event candidate")
            continue
        output.append(
            {
                "factIndexes": [index],
                "placements": ["onClick"],
                "actionId": identifier,
                "eventCandidate": copy.deepcopy(event),
                "labelMeaning": fact.get("requirement"),
                "labelRequiresWidthReview": True,
                "ownerRoots": _action_owners(event),
                "pressureLabelOnly": (action_labels or {}).get(identifier),
                "componentCandidates": list(fact.get("componentHints", [])),
                "hasAssignedIcon": isinstance(assigned_assets.get(identifier), str),
            }
        )
    return output


def _action_owners(event: dict[str, Any]) -> list[str]:
    roots: list[str] = []
    encoded = json.dumps(event.get("args", {}), ensure_ascii=False)
    for match in re.finditer(r"/data/([^/\s}'\"]+)", encoded):
        root = f"/data/{match.group(1)}/"
        if root not in roots:
            roots.append(root)
    return roots


def _region_tree(size: str, rules: list[dict[str, Any]]) -> Region | None:
    nodes: dict[tuple[int, ...], Region] = {}
    for rule in rules:
        path = tuple(rule.get("path", []))
        for depth in range(len(path) + 1):
            prefix = path[:depth]
            if prefix not in nodes:
                nodes[prefix] = Region(prefix, "Column", {}, {})
        region = nodes.get(path)
        if region is None:
            return None
        types = rule.get("types", ["Column"])
        containers = [name for name in types if name in _CONTAINERS]
        region.kind = containers[0] if containers else types[0]
        region.props = {**rule.get("props", {}), **rule.get("slotSize", {})}
        region.rule = rule
    _add_implicit_allocation_slots(nodes)
    for path in sorted(nodes):
        if path:
            parent = nodes.get(path[:-1])
            if parent is None:
                return None
            parent.children.append(nodes.get(path))
    root = nodes.get(())
    if root is None:
        return None
    if not _assign_boxes(
        root, reference_dimension(size, "width"), reference_dimension(size, "height"), size
    ):
        return None
    return root


def _add_implicit_allocation_slots(nodes: dict[tuple[int, ...], Region]) -> None:
    """为合同只约束结构、未约束组件类型的子槽补组合搜索落点。"""
    for path, region in list(nodes.items()):
        count = region.rule.get("childCount")
        if not isinstance(count, int):
            count = region.rule.get("childCountMin")
        if not isinstance(count, int) or count <= 0:
            continue
        for index in range(count):
            child_path = (*path, index)
            if child_path not in nodes:
                nodes[child_path] = Region(child_path, "Column", {}, {})


def _assign_boxes(region: Region, width: float, height: float, size: str) -> bool:
    region.width = width - _extent(region.props.get("padding"), "width")
    region.height = height - _extent(region.props.get("padding"), "height")
    if region.width <= 0 or region.height <= 0:
        return False
    axis = "width" if region.kind == "Row" else "height"
    available = region.width if axis == "width" else region.height
    gap = region.props.get("itemMargin", 0)
    fixed = 0.0
    flexible = 0
    extents: list[float | None] = []
    for child in region.children:
        extent = child.props.get(axis)
        if axis == "height" and child.kind not in _CONTAINERS:
            extent = _part(size, child.kind, "root").get("height")
        if not isinstance(extent, (int, float)):
            extent = None
            flexible += 1
        else:
            fixed += extent
        extents.append(extent)
    remaining = available - fixed - gap * max(0, len(extents) - 1)
    if region.kind != "Stack" and remaining < 0:
        return False
    for child, extent in zip(region.children, extents, strict=True):
        child_width = child.props.get("width")
        child_height = child.props.get("height")
        if not isinstance(child_width, (int, float)):
            child_width = region.width
        if not isinstance(child_height, (int, float)):
            child_height = region.height
        if region.kind != "Stack":
            allocated = extent if extent is not None else remaining / flexible
            if axis == "width":
                child_width = allocated
            else:
                child_height = allocated
        if child_width > region.width or child_height > region.height:
            return False
        if not _assign_boxes(child, child_width, child_height, size):
            return False
    return True


def _leaves(region: Region) -> list[Region]:
    if not region.children:
        return [region]
    output: list[Region] = []
    for child in region.children:
        output.extend(_leaves(child))
    return output


def _allocations(
    zones: list[Region],
    groups: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    size: str,
    *,
    layout_id: str | None = None,
):
    allocation: list[list[dict[str, Any]]] = [[] for _ in zones]
    remaining = list(groups)
    unused_actions = copy.deepcopy(actions)
    body_zones: list[int] = []
    for i, zone in enumerate(zones):
        policy = zone.rule.get("eventPolicy")
        if policy == "require":
            if not unused_actions:
                return
            action = unused_actions.pop(0)
            name = _action_component_for_zone(zone, action)
            if name is None:
                return
            action.update(
                {
                    "component": name,
                    "requiredHeight": _part(size, name, "root").get("height"),
                    "minimumWidth": 0,
                }
            )
            allocation[i].append(action)
        elif zone.kind == "SingleLineTitle":
            title = next(
                (group for group in remaining if group.get("component") == "SingleLineTitle"), None
            )
            if title is not None:
                remaining.remove(title)
                allocation[i].append(title)
            else:
                allocation[i].append(
                    {
                        "component": "SingleLineTitle",
                        "factIndexes": [],
                        "placements": [],
                        "minimumWidth": 0,
                        "requiredHeight": _part(size, "SingleLineTitle", "root").get("height"),
                        "optionalDecoration": True,
                    }
                )
        elif zone.kind in _CONTAINERS:
            body_zones.append(i)
        else:
            return
    if not body_zones and not remaining and not unused_actions:
        yield allocation
        return
    if not body_zones:
        return
    # 动作进入独立槽，或所在分区底部；禁止在 forbid-subtree 的信息槽塞按钮。
    pools = []
    for group in remaining:
        compatible_zones: list[int] = []
        for index in body_zones:
            zone = zones[index]
            assessment = check_component_slot(
                group, size=size, layout_id=layout_id, slot_rule=zone.rule,
                width=zone.width, height=zone.height,
            )
            if assessment.status != "incompatible":
                compatible_zones.append(index)
        pools.append(compatible_zones)
    for _action in unused_actions:
        pools.append(
            [i for i in body_zones if zones[i].rule.get("eventPolicy") != "forbid-subtree"]
        )
    if any(not pool for pool in pools):
        return
    action_start = len(remaining)
    destinations_to_try = itertools.islice(itertools.product(*pools), _SEARCH_LIMIT)
    if len(unused_actions) > 1 and len(body_zones) > 1:
        # 等价完整分配优先均衡独立动作，避免最先把多个按钮堆进一个窄内容区。
        destinations_to_try = sorted(
            destinations_to_try,
            key=lambda targets: _action_distribution_cost(targets[action_start:], allocation),
        )
    for destinations in destinations_to_try:
        belonging: dict[str, int] = {}
        split = False
        for group, destination in zip(remaining, destinations, strict=False):
            identity = group.get("object")
            if identity is None:
                continue
            previous = belonging.setdefault(identity, destination)
            if previous != destination:
                split = True
                break
        if split:
            yield None
            continue
        action_destinations = destinations[action_start:]
        for action, destination in zip(unused_actions, action_destinations, strict=True):
            owners = action.get("ownerRoots", [])
            matching_destinations = set()
            for identity, body_destination in belonging.items():
                if any(f"{identity}/".startswith(owner) for owner in owners):
                    matching_destinations.add(body_destination)
            if matching_destinations and destination not in matching_destinations:
                split = True
                break
        if split:
            yield None
            continue
        value = copy.deepcopy(allocation)
        for group, destination in zip(remaining + unused_actions, destinations, strict=True):
            value[destination].append(copy.deepcopy(group))
        yield value


def _action_distribution_cost(
    destinations: tuple[int, ...], allocation: list[list[dict[str, Any]]],
) -> int:
    """只排序已有合法分配，不猜事件归属、不删除或新增动作。"""
    counts = []
    for groups in allocation:
        count = 0
        for group in groups:
            if group.get("actionId"):
                count += 1
        counts.append(count)
    for destination in destinations:
        counts[destination] += 1
    return sum(count * count for count in counts)


def _close_regions(
    zones: list[Region],
    allocation: list[list[dict[str, Any]]],
    size: str,
) -> list[dict[str, Any]] | None:
    result = []
    for zone, groups in zip(zones, allocation, strict=True):
        if not groups:
            return None
        only_actions = all(group.get("actionId") for group in groups)
        if only_actions and zone.rule.get("eventPolicy") != "require":
            if len(zones) > 1:
                return None
        if zone.kind in {"Row", "Stack"}:
            return None  # 当前搜索只在合法 Column 内容槽里构造内部横排，避免改写固定父方向。
        for group in groups:
            if group.get("fullTextRequiresTwoLineReview"):
                separator = _text_width(" ｜ ", group.get("fontSize"))
                item_width = (zone.width - separator) / 2
                samples = group.get("pressureOnly", [])
                if any(_wrapped_lines(sample, group.get("fontSize"), item_width) > 2
                       for sample in samples):
                    return None
            if group.get("actionId") and not group.get("component"):
                group["component"] = "PillButton"
                group["requiredHeight"] = _part(size, "PillButton", "root").get("height")
                group["minimumWidth"] = 0
            if group.get("actionId"):
                name = group.get("component")
                root = _part(size, name, "root")
                if name == "CircleButton":
                    group["accessibilityLabel"] = group.get("labelMeaning")
                    group["requiresAccurateIcon"] = True
                    continue
                label_width = zone.width - _extent(root.get("padding"), "width")
                if name == "CardButton":
                    if group.get("hasAssignedIcon"):
                        label_width -= _part(size, name, "icon").get("width", 0)
                        label_width -= root.get("itemMargin", 0)
                else:
                    label_width = min(label_width, _part(size, name, "label").get("maxWidth"))
                group["labelWidthBudget"] = label_width
                group["labelFontSize"] = _part(size, name, "label").get("fontSize")
                if label_width <= 0:
                    return None
                label = group.get("pressureLabelOnly")
                if isinstance(label, str):
                    font = group.get("labelFontSize")
                    if _text_width(label, font) > label_width:
                        if name != "CardButton" or _wrapped_lines(label, font, label_width) != 2:
                            return None
                        label_part = _part(size, name, "label", "multilineLabel")
                        if label_part.get("height", 0) + _extent(
                            root.get("padding"), "height",
                        ) > group.get("requiredHeight", 0):
                            return None
                        group["labelLines"] = 2
        gap = zone.props.get(
            "itemMargin", _part(size, "SecondaryBody", "root").get("itemMargin", 0)
        )
        packed = _pack(groups, zone.width, gap, height_budget=zone.height)
        if packed is None:
            return None
        rows, height = packed
        if height > zone.height:
            return None
        direct_children = _direct_children(zone, groups, rows)
        if direct_children is None:
            # 单列优先不能覆盖布局直属子数合同；需横排时再比较紧凑组合。
            packed = _pack(groups, zone.width, gap)
            if packed is None:
                return None
            rows, height = packed
            if height > zone.height:
                return None
            direct_children = _direct_children(zone, groups, rows)
            if direct_children is None:
                return None
        for row in rows:
            widths = row.get("referenceChildWidths", [zone.width])
            for index, available in zip(row.get("groupIndexes", []), widths, strict=True):
                if not _group_text_fits(groups[index], available):
                    return None
        _record_text_allowances(groups, rows, zone.width, size)
        result.append(
            {
                "path": list(zone.path),
                "referenceWidth": zone.width,
                "referenceHeight": zone.height,
                "gap": gap,
                "rows": rows,
                "requiredHeight": height,
                "remainingHeight": zone.height - height,
                "wrapper": "Column" if zone.kind in _CONTAINERS else None,
                "directChildContract": {
                    key: zone.rule.get(key)
                    for key in ("childCount", "childCountMin", "childCountMax")
                    if key in zone.rule
                },
                "groups": groups,
            }
        )
        result[-1]["directChildren"] = direct_children
    return result


def _action_component_for_zone(
    zone: Region,
    action: dict[str, Any],
) -> str | None:
    """按 Plan 候选和槽位合同选择动作组件；纯图标槽必须有显式语义选择。"""
    zone_types = zone.rule.get("types", [])
    candidates = action.get("componentCandidates", [])
    for name in candidates:
        if name in zone_types and name in {"PillButton", "CircleButton", "CardButton"}:
            return name
    if "CircleButton" in zone_types:
        return None
    for name in ("CardButton", "PillButton"):
        if name in zone_types:
            return name
    return None


def _record_text_allowances(
    groups: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    width: float,
    size: str,
) -> None:
    for row in rows:
        indexes = row.get("groupIndexes", [])
        widths = row.get("referenceChildWidths", [width])
        for index, available in zip(indexes, widths, strict=True):
            _record_group_allowance(groups[index], available, size)


def _record_group_allowance(group: dict[str, Any], available: float, size: str) -> None:
    group["referenceWidthBudget"] = available
    group["additionalTextWidthBudget"] = max(0, available - group.get("minimumWidth", 0))
    nested = group.get("nestedGroups")
    if nested:
        for child, width in zip(nested, _nested_widths(group, available), strict=True):
            _record_group_allowance(child, width, size)
    if group.get("component") == "TextBlock":
        count = len(group.get("factIndexes", []))
        gap = _part(size, "TextBlock", "root").get("itemMargin", 0)
        padding = _extent(_part(size, "TextBlock", "item").get("padding"), "width")
        group["perItemLabelWidthBudget"] = (available - gap * (count - 1)) / count - padding


def _pack(
    groups: list[dict[str, Any]], width: float, gap: float, *, height_budget: float | None = None,
):
    """保持组顺序，比较单列与相邻组横排；操作始终留在底部独立行。"""
    if height_budget is not None:
        columns = []
        total = gap * max(0, len(groups) - 1)
        for index, group in enumerate(groups):
            minimum = group.get("minimumWidth")
            height = group.get("requiredHeight")
            if not isinstance(minimum, (int, float)) or not isinstance(height, (int, float)):
                break
            if minimum > width:
                break
            total += height
            columns.append({"direction": "column", "groupIndexes": [index],
                            "height": height, "availableWidth": width})
        if len(columns) == len(groups) and total <= height_budget:
            return columns, total
    best: dict[int, tuple[list[dict[str, Any]], float]] = {len(groups): ([], 0.0)}
    for i in range(len(groups) - 1, -1, -1):
        group = groups[i]
        minimum = group.get("minimumWidth")
        height = group.get("requiredHeight")
        if not isinstance(minimum, (int, float)) or not isinstance(height, (int, float)):
            continue
        if minimum > width:
            parts = group.get("splitDisplayParts", [])
            if group.get("component") in {"EmphasisText", "EmphasizedData"} and len(parts) == 2:
                font = group.get("fontSize")
                if all(_text_width(part.get("sample"), font) <= width for part in parts):
                    children = []
                    for position, part in enumerate(parts):
                        children.append({
                            "component": group.get("component"), "fontSize": font,
                            "requiredHeight": height,
                            "minimumWidth": _text_width(part.get("sample"), font),
                            "factIndexes": group.get("factIndexes") if position else [],
                            "placements": group.get("placements") if position else [],
                            "object": group.get("object"),
                        })
                        key = "originalValue" if group.get("component") == "EmphasizedData" \
                            else "originalMainText"
                        children[-1][key] = part.get("text")
                    group.update(_nested_group("Column", children, gap))
                    height = group.get("requiredHeight")
                    minimum = group.get("minimumWidth")
        if minimum > width:
            if group.get("component") != "SecondaryBody" or group.get("columns") != 1:
                continue
            sample = group.get("pressureOnly")
            if not isinstance(sample, str):
                continue
            if _wrapped_lines(sample, group.get("fontSize"), width) != 2:
                continue
            height *= 2
            group["requiredHeight"] = height
            group["lines"] = [2]
            minimum = width
            group["minimumWidth"] = minimum
        suffix = best.get(i + 1)
        if suffix is not None:
            rows, tail = suffix
            best[i] = (
                [
                    {
                        "direction": "column",
                        "groupIndexes": [i],
                        "height": height,
                        "availableWidth": width,
                    },
                    *rows,
                ],
                height + tail + (gap if rows else 0),
            )
        if i + 1 >= len(groups):
            continue
        other = groups[i + 1]
        if group.get("actionId") or other.get("actionId"):
            continue
        other_width = other.get("minimumWidth")
        other_height = other.get("requiredHeight")
        if not isinstance(other_width, (int, float)):
            continue
        if not isinstance(other_height, (int, float)) or minimum + other_width + gap > width:
            continue
        suffix = best.get(i + 2)
        if suffix is None:
            continue
        rows, tail = suffix
        row_height = max(height, other_height)
        occupied = row_height + tail + (gap if rows else 0)
        previous = best.get(i)
        if previous is None or occupied < previous[1]:
            spare = (width - gap - minimum - other_width) / 2
            best[i] = (
                [
                    {
                        "direction": "row",
                        "groupIndexes": [i, i + 1],
                        "height": row_height,
                        "referenceChildWidths": [minimum + spare, other_width + spare],
                    },
                    *rows,
                ],
                occupied,
            )
    return best.get(0)


def _wrapped_lines(text: str, font_size: float, width: float) -> int:
    lines = 1
    used = 0.0
    for character in text:
        if character == "\n":
            lines += 1
            used = 0.0
            continue
        advance = font_size * (0.6 if character.isascii() else 1)
        if advance > width:
            return 3
        if used + advance > width:
            lines += 1
            used = 0.0
        used += advance
    return lines


def _direct_children(
    zone: Region,
    groups: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]] | None:
    """明确包装层和直属动作，满足原变体子数，不能把多组直接塞进单子槽。"""
    if zone.kind not in _CONTAINERS:
        return [{"groupIndexes": [0]}] if len(groups) == 1 else None
    actions = [i for i, group in enumerate(groups) if group.get("actionId")]
    body = [i for i, group in enumerate(groups) if not group.get("actionId")]
    children: list[dict[str, Any]] = []
    if body:
        children.append(
            {
                "component": "Column",
                "groupIndexes": body,
                "placement": "remaining_body",
                "rows": rows[: len(rows) - len(actions)],
            }
        )
    for index in actions:
        children.append(
            {
                "component": groups[index].get("component"),
                "groupIndexes": [index],
                "placement": "bottom_action",
            }
        )
    exact = zone.rule.get("childCount")
    lower = exact if exact is not None else zone.rule.get("childCountMin", 1)
    upper = exact if exact is not None else zone.rule.get("childCountMax", len(children))
    if lower <= len(children) <= upper:
        return children
    if exact == 1:
        return [
            {"component": "Column", "children": children, "placement": "single_foreground_wrapper"}
        ]
    if not actions and lower <= len(rows) <= upper:
        return [
            {
                "component": "Row" if row.get("direction") == "row" else "Column",
                "groupIndexes": row.get("groupIndexes"),
            }
            for row in rows
        ]
    return None


def _all_facts_covered(candidate: dict[str, Any], count: int) -> bool:
    seen: list[int] = []
    for region in candidate.get("regions", []):
        for group in region.get("groups", []):
            seen.extend(group.get("factIndexes", []))
    return sorted(seen) == list(range(count))


def composition_text_width_conflicts(
    size: str, plan: dict[str, Any], task: dict[str, Any],
) -> list[str]:
    """只核对能够确定的等宽组压力值；不猜未知标签或改发布校验。"""
    conflicts = []
    facts = plan.get("info_required", [])
    composition = plan.get("composition", {})
    if not isinstance(composition, dict) or not isinstance(facts, list):
        return conflicts
    for region in composition.get("regions", []):
        available = region.get("referenceWidth")
        if not isinstance(available, (int, float)):
            continue
        for group in region.get("groups", []):
            if group.get("component") != "TextBlock":
                continue
            indexes = group.get("factIndexes", [])
            count = len(indexes)
            if count < 2:
                continue
            root = _part(size, "TextBlock", "root")
            item_padding = _extent(_part(size, "TextBlock", "item").get("padding"), "width")
            inner_width = available - _extent(root.get("padding"), "width")
            item_width = (inner_width - root.get("itemMargin", 0) * (count - 1)) / count
            item_width -= item_padding
            value_style = _part(size, "TextBlock", "value")
            font = value_style.get("fontSize")
            if not isinstance(font, (int, float)):
                continue
            for index in indexes:
                if not isinstance(index, int) or not 0 <= index < len(facts):
                    continue
                sample = _pressure(facts[index], task)
                if sample is None:
                    continue
                required = _text_width(sample, font)
                if required > item_width:
                    conflicts.append(
                        f"TextBlock fact {index} complete pressure value requires {required:g}vp "
                        f"within an equal item of {item_width:g}vp; regroup without truncation"
                    )
    return conflicts


def composition_structure_blueprint(size: str, candidate: dict[str, Any]) -> list[dict[str, Any]]:
    """展开参考结构的节点关系，不生成最终DSL或组件视觉属性。"""
    layout = load_layout_contract().get("layouts", {}).get(candidate.get("layout"), {})
    patterns = layout.get("patterns", [])
    variant = candidate.get("variant")
    if not isinstance(variant, int) or not 1 <= variant <= len(patterns):
        return []
    tree = _region_tree(size, patterns[variant - 1].get("rules", []))
    if tree is None:
        return []
    zones = {}
    for region in candidate.get("regions", []):
        zones[tuple(region.get("path", []))] = region
    output: list[dict[str, Any]] = []

    def add_group(
        identifier: str, group: dict[str, Any], *, weight: float | None = None,
    ) -> str:
        nested = group.get("nestedGroups")
        if nested:
            children = []
            for index, child in enumerate(nested):
                child_weight = None
                if group.get("component") == "Row":
                    child_weight = child.get("minimumWidth")
                children.append(add_group(f"{identifier}_{index}", child, weight=child_weight))
            layout_props = {"width": "matchParent"}
            if weight is not None:
                layout_props["layoutWeight"] = weight
            output.append({
                "id": identifier, "component": group.get("component"), "children": children,
                "fixedLayoutProps": {"itemMargin": group.get("gap", 0), "padding": 0},
                "suggestedLayoutProps": layout_props,
            })
            return identifier
        props = {}
        if "originalMainText" in group:
            props["mainText"] = group.get("originalMainText")
        if "originalValue" in group:
            props["value"] = group.get("originalValue")
        for key in (
            "columns", "lines", "variant", "density", "labelLines",
            "unitFromFieldContract", "accessibilityLabel", "requiresAccurateIcon",
        ):
            if key in group:
                props[key] = group.get(key)
        # PillButton 的宽度由动作槽和 Recipe 决定，公开合同不接受 width。
        layout_props: dict[str, Any] = {}
        if group.get("component") != "PillButton":
            layout_props["width"] = "matchParent"
        if weight is not None:
            layout_props["layoutWeight"] = weight
        output.append({
            "id": identifier, "component": group.get("component"), "children": [],
            "factIndexes": group.get("factIndexes"), "placements": group.get("placements"),
            "groupParameters": props, "suggestedLayoutProps": layout_props,
            "displayBudget": {
                "referenceWidth": group.get("referenceWidthBudget"),
                "valueMinimumWidth": group.get("minimumWidth"),
                "additionalTextWidth": group.get("additionalTextWidthBudget"),
                "fontSize": group.get("fontSize"),
                "meaning": group.get("meaning"),
                "requiresObjectCaption": group.get("requiresObjectCaption", False),
            },
        })
        return identifier

    def add_piece(
        identifier: str, piece: dict[str, Any], groups: list[dict[str, Any]], gap: float,
    ) -> str:
        indexes = piece.get("groupIndexes", [])
        component = piece.get("component")
        if len(indexes) == 1 and piece.get("placement") != "remaining_body":
            group = groups[indexes[0]]
            if component is None or component == group.get("component"):
                return add_group(identifier, group)
        children = []
        if "children" in piece:
            for index, child in enumerate(piece.get("children")):
                children.append(add_piece(f"{identifier}_{index}", child, groups, gap))
        elif "rows" in piece:
            for index, row in enumerate(piece.get("rows")):
                child = {"component": "Row" if row.get("direction") == "row" else None,
                         "groupIndexes": row.get("groupIndexes", []),
                         "referenceChildWidths": row.get("referenceChildWidths")}
                children.append(add_piece(f"{identifier}_{index}", child, groups, gap))
        else:
            widths = piece.get("referenceChildWidths")
            total = sum(widths) if isinstance(widths, list) and widths else None
            for position, index in enumerate(indexes):
                weight = widths[position] if total is not None and total > 0 else None
                children.append(add_group(f"{identifier}_{position}", groups[index], weight=weight))
        node = {"id": identifier, "component": component or "Column",
                "children": children, "fixedLayoutProps": {"itemMargin": gap, "padding": 0}}
        if piece.get("placement") == "remaining_body":
            node["suggestedLayoutProps"] = {"width": "matchParent", "layoutWeight": 1}
            node["fixedLayoutProps"].update({"alignItems": "start", "justifyContent": "start"})
        elif piece.get("placement") == "single_foreground_wrapper":
            node["suggestedLayoutProps"] = {"width": "matchParent", "height": "matchParent"}
        widths = piece.get("referenceChildWidths")
        if widths is not None:
            node["referenceChildWeights"] = widths
        output.append(node)
        return identifier

    def visit(region: Region) -> str:
        identifier = "root" if not region.path else "region_" + "_".join(map(str, region.path))
        zone = zones.get(region.path)
        groups = zone.get("groups", []) if zone is not None else []
        if zone is not None and region.kind not in _CONTAINERS:
            if not groups:
                raise ValueError("Reference leaf has no complete fact group")
            return add_group(identifier, groups[0])
        children = []
        if zone is not None:
            for index, piece in enumerate(zone.get("directChildren", [])):
                children.append(add_piece(
                    f"{identifier}_child{index}", piece, groups, zone.get("gap", 0),
                ))
        else:
            for child in region.children:
                children.append(visit(child))
        fixed = {"padding": 0}
        for key in ("padding", "itemMargin", "alignItems", "justifyContent"):
            if key in region.props:
                fixed[key] = region.props.get(key)
        if zone is not None:
            fixed["itemMargin"] = zone.get("gap", 0)
        node = {"id": identifier, "component": region.kind, "children": children,
                "fixedLayoutProps": fixed}
        if not region.path:
            node["suggestedLayoutProps"] = {"width": "matchParent", "height": "matchParent"}
        output.append(node)
        return identifier

    visit(tree)
    return list(reversed(output))
