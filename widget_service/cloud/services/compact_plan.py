# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact DSL 两阶段生成使用的信息计划合同。"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any

from services.compact_component_semantics import CORE_INFORMATION_COMPONENT_TYPES
from services.compact_composition_context import (
    composition_group_minimum_height,
    composition_implementation_conflicts,
    composition_region_capacity,
)
from services.compact_composition_planner import compound_duration_bindings
from services.compact_dsl_a2ui_converter import (
    MODEL_COMPACT_INPUT_COMPONENT_TYPES,
    ComponentRow,
    parse_compact_dsl_rows,
)
from services.compact_layout_runtime import (
    CompactLayoutRuntimeError,
    load_layout_contract,
    match_compact_layout,
)

SUBMIT_CARD_PLAN = "submit_card_plan"

_JSON_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL | re.IGNORECASE)
_BINDING_PATH = re.compile(r"\$\{(?P<path>/[^}\s]+)\}")
_PERCENTAGE_VALUE = re.compile(r"^\s*[+-]?(?:\d+(?:\.\d*)?|\.\d+)\s*[%％]\s*$")
_FACT_KEYS = frozenset(
    {"requirement", "priority", "dataId", "actionId", "text", "componentHints"}
)
_TARGET_KEYS = ("dataId", "actionId", "text")
_FACT_PRIORITIES = frozenset({"must", "should"})
_SHARED_FACT_COMPONENTS = (
    "SingleLineTitle",
    "DoubleLineTitle",
    "Badge",
    "EmphasizedData",
    "EmphasisText",
    "SecondaryBody",
    "InfoBlock",
    "H_BarChart",
    "NumericRatioStack",
    "ProgressCircleSingle",
    "ProgressCircle",
    "TableText",
    "EventCard",
    "PillButton",
)
_PROGRESS_FACT_COMPONENTS = frozenset(
    {"ProgressCircle", "ProgressLine2", "ProgressCircleSingle"}
)
_ACTION_FACT_COMPONENTS = frozenset({"PillButton", "CircleButton", "CardButton"})
_VISIBLE_PROP_NAMES = frozenset(
    {
        "content",
        "displayValue",
        "items",
        "label",
        "location",
        "mainText",
        "primaryText",
        "secondaryInfo",
        "secondaryLabel",
        "secondaryText",
        "supportingText",
        "time",
        "title",
        "total",
        "unit",
        "value",
        "externalText",
    }
)
_COMPONENT_HINTS = {
    "2x2": (
        *_SHARED_FACT_COMPONENTS,
        "DataDisplay",
        "CircleButton",
    ),
    "2x4": (
        *_SHARED_FACT_COMPONENTS,
        "ProgressLine2",
        "TextBlock",
        "CardButton",
        "TopTextBottomValue",
        "SummaryList",
    ),
}
_LAYOUT_HINTS = {
    "2x2": (
        "S-center",
        "S-title-content",
        "S-title-content-action",
        "S-title-anchor",
        "S-content-dual-action",
        "S-dual-info",
        "S-title-dual-content",
        "S-title-dual-column-action",
        "S-title-primary-secondary-action",
        "S-quad-content",
    ),
    "2x4": (
        "W-top-bottom",
        "W-split-panels",
        "W-content-side-slots",
        "W-four-slots",
    ),
}


class CompactPlanValidationError(ValueError):
    """模型提交的 Compact Info Plan 不满足合同。"""

    def __init__(self, errors: list[str] | tuple[str, ...]) -> None:
        self.errors = tuple(dict.fromkeys(errors))
        super().__init__("; ".join(self.errors))


@dataclass(frozen=True)
class CompactPlanValidationResult:
    """标准化后的计划及不阻断生成的清理提示。"""

    plan: dict[str, Any]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompactOptionalDropCandidate:
    """描述一个可在最终兜底中删除的非 Action 组件。"""

    component_id: str
    component_type: str
    fact_indexes: tuple[int, ...]
    requirements: tuple[str, ...]
    contains_must_facts: bool


def build_compact_plan_tool(
    task_spec: dict[str, Any],
    *,
    include_composition: bool = False,
) -> dict[str, Any]:
    """根据本次 TaskSpec 构造 submit_card_plan 的动态工具合同。"""
    size = task_spec.get("size")
    data_paths = list(compact_plan_data_paths(task_spec))
    action_ids = list(compact_plan_action_ids(task_spec))
    asset_ids = list(compact_plan_asset_ids(task_spec))
    target_variants: list[dict[str, Any]] = []
    if data_paths:
        target_variants.append({"required": ["dataId"]})
    if action_ids:
        target_variants.append({"required": ["actionId"]})
    target_variants.append({"required": ["text"]})
    properties: dict[str, Any] = {
        "requirement": {
            "type": "string",
            "minLength": 1,
            "description": "一个需要规划可见落点的原子信息或操作。",
        },
        "priority": {
            "type": "string",
            "enum": ["must", "should"],
            "description": (
                "must 是不可省略的核心信息；should 是省略后仍不改变"
                "卡片主要用途的补充信息。所有 actionId 必须为 must。"
            ),
        },
        "text": {
            "type": "string",
            "minLength": 1,
            "description": (
                "逐字引用 userQuery 明确要求在卡面展示的静态正文；"
                "仅用于拨号、入会、导航等操作的参数不单独列为展示事实。"
            ),
        },
        "componentHints": {
            "type": "array",
            "items": {"type": "string", "enum": list(_component_hints(size))},
            "minItems": 1,
            "maxItems": 3,
            "uniqueItems": True,
            "description": (
                "按优先级排列的组件候选；第一项是合同条件成立时应落实的首选，"
                "其余为不适配时的备选，不冻结实例数量。先按对象和信息关系合组，"
                "再给组内事实推荐可共同承载它们的组件，不默认逐字段拆成单文字组件。"
                "真实占比或进度可以绑定"
                "number/integer dataId，或样例为完整数值百分比的 string dataId；"
                "普通字符串、布尔值、静态正文和操作不推荐进度组件。"
                "SingleLineTitle 承担单行标题；DoubleLineTitle 承担标题加紧密相关的次信息。"
                "标题事实不得同时推荐正文或其它标题替代组件。"
            ),
        },
    }
    if data_paths:
        properties["dataId"] = {
            "type": "string",
            "enum": data_paths,
            "description": "必须在卡面展示的动态信息的真实 JSON Pointer；仅用于事件传参时不选。",
        }
    if action_ids:
        properties["actionId"] = {
            "type": "string",
            "enum": action_ids,
            "description": "用户明确要求的真实事件候选 ID；该候选原有参数继续完整携带。",
        }
    plan_properties: dict[str, Any] = {
        "info_required": {
            "type": "array",
            "minItems": 1,
            "maxItems": 24,
            "items": {
                "type": "object",
                "properties": properties,
                "required": ["requirement", "priority"],
                "oneOf": target_variants,
                "additionalProperties": False,
            },
        },
        "layoutHints": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": list(_layout_hints(size)),
            },
            "maxItems": 2,
            "uniqueItems": True,
            "description": "至多两个父布局软候选，不冻结最终骨架。",
        },
    }
    required = ["info_required"]
    description = "提交卡片信息与操作的优先级；组件和布局只提供软候选。"
    if asset_ids:
        assignment_properties = {
            "assetId": {
                "type": ["string", "null"],
                "enum": [*asset_ids, None],
                "description": "选择候选素材 ID；没有语义匹配素材时为 null。",
            },
            "reason": {
                "type": "string",
                "minLength": 1,
                "description": "assetId 为 null 时说明没有选择图标的具体原因。",
            },
        }
        plan_properties["assetAssignments"] = {
            "type": "object",
            "properties": {
                "actions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "actionId": {
                                "type": "string",
                                "enum": action_ids,
                            },
                            **assignment_properties,
                        },
                        "required": ["actionId", "assetId"],
                        "additionalProperties": False,
                    },
                    "maxItems": len(action_ids),
                    "description": "按 info_required 中的动作顺序逐项决定按钮图标。",
                },
                "title": {
                    "type": "object",
                    "properties": assignment_properties,
                    "required": ["assetId"],
                    "additionalProperties": False,
                    "description": (
                        "先完成动作图标分配，再为一个语义匹配的 SingleLineTitle 选择"
                        "未使用素材；不指定标题行顺序。无标题布局填 null 并说明原因。"
                    ),
                },
            },
            "required": ["actions", "title"],
            "additionalProperties": False,
        }
        required.append("assetAssignments")
        description += "存在素材候选时，同时提交按钮优先、标题随后且不复用的素材分配。"
    if include_composition:
        plan_properties["composition"] = _composition_tool_schema(size)
        required.append("composition")
        description += "同时提交可完整承载这些事实的分区、组件合组和容量计划。"
    return {
        "type": "function",
        "function": {
            "name": SUBMIT_CARD_PLAN,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": plan_properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


def _composition_tool_schema(size: Any) -> dict[str, Any]:
    """实例级实现计划；事实仍由 info_required 独立确定。"""
    integer = {"type": "integer", "minimum": 0, "maximum": 23}
    extent = {"type": "number", "minimum": 0}
    group = {
        "type": "object",
        "properties": {
            "component": {"type": "string", "enum": list(_component_hints(size))},
            "factIndexes": {"type": "array", "items": integer, "minItems": 0,
                            "maxItems": 24,
                            "description": (
                                "只有装饰 SingleLineTitle 可以为空；同事实多属性重复索引。"
                            )},
            "placements": {"type": "array", "items": {"type": "string"},
                           "minItems": 0, "maxItems": 24,
                           "description": "逐条对应 factIndexes 的可见 Prop，如 items[0].value。"},
            "referenceHeight": {**extent, "description": "完整组件按实际条数/行数合计占高。"},
            "variant": {"type": "string"},
            "density": {"type": "string", "enum": ["compact"]},
            "columns": {"type": "integer", "enum": [1, 2]},
            "lines": {"type": "array", "items": {"type": "integer", "enum": [1, 2]},
                      "description": "依每个实际文本 item 顺序记录行数，不一律设两行。"},
            "labelLines": {"type": "integer", "enum": [1, 2]},
        },
        "required": ["component", "factIndexes", "placements", "referenceHeight"],
        "additionalProperties": False,
    }
    region = {
        "type": "object",
        "properties": {
            "id": {"type": "string", "minLength": 1},
            "path": {"type": "array", "items": integer,
                     "description": "选定布局内从 root 开始的子序号；全卡为[]。"},
            "referenceWidth": {**extent, "description": "已扣此区域内边距的可用宽度。"},
            "referenceHeight": {**extent, "description": "已扣此区域内边距的可用高度。"},
            "gap": {**extent, "description": "合同允许的组间距，不改组件内部间距。"},
            "groups": {"type": "array", "items": group, "minItems": 1, "maxItems": 24},
        },
        "required": ["id", "path", "referenceWidth", "referenceHeight", "gap", "groups"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "layout": {"type": "string", "enum": list(_layout_hints(size))},
            "variant": {"type": "integer", "minimum": 1},
            "regions": {"type": "array", "items": region, "minItems": 1, "maxItems": 8},
        },
        "required": ["layout", "variant", "regions"],
        "additionalProperties": False,
        "description": (
            "实例级分区合组计划：覆盖全部必要事实与动作，核算横向文字与纵向占高，"
            "参考尺寸来自当前合同，不写成固定输出宽高；不能缩字或删信息。"
        ),
    }


def _finite_extent(value: Any) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= 0)


def _normalize_composition(
    value: Any, raw_facts: Any, facts: list[dict[str, Any]], size: Any,
) -> tuple[dict[str, Any] | None, list[str]]:
    """标准化实现方案；调用方根据运行模式决定是否阻断。"""
    if value is None:
        return None, []
    warning = "composition ignored: regroup all facts with valid layout, placements and budgets."
    schema = _composition_tool_schema(size)
    if not isinstance(value, dict) or set(value) != {"layout", "variant", "regions"}:
        return None, [warning]
    variant = value.get("variant")
    valid_variant = isinstance(variant, int) and not isinstance(variant, bool) and variant > 0
    if value.get("layout") not in _layout_hints(size) or not valid_variant:
        return None, [warning]
    layout = load_layout_contract().get("layouts", {}).get(value.get("layout"), {})
    if variant > len(layout.get("patterns", [])):
        return None, [warning]
    action_count = sum(1 for fact in facts if "actionId" in fact)
    action_range = layout.get("actionCount", {})
    if not action_range.get("min", 0) <= action_count <= action_range.get("max", action_count):
        return None, ["composition layout cannot carry all required actions; "
                      "choose a compatible layout without removing any action."]
    regions = value.get("regions")
    if not isinstance(regions, list) or not 1 <= len(regions) <= 8:
        return None, [warning]
    identities: list[tuple[str, str]] = []
    for fact in facts:
        for key in _TARGET_KEYS:
            if key in fact:
                identities.append((key, fact.get(key)))
                break
    index_map: dict[int, int] = {}
    for index, fact in enumerate(raw_facts):
        for key in _TARGET_KEYS:
            target = fact.get(key)
            if isinstance(target, str) and (key, target.strip()) in identities:
                index_map[index] = identities.index((key, target.strip()))
    region_schema = schema.get("properties", {}).get("regions", {}).get("items", {})
    group_schema = region_schema.get("properties", {}).get("groups", {}).get("items", {})
    covered: set[int] = set()
    normalized: list[dict[str, Any]] = []
    notes: list[str] = []
    for region in regions:
        if not _composition_region_shape(region, region_schema):
            return None, [warning]
        if size == "2x2":
            region, slot_note = _small_content_region(region, layout, variant)
            if slot_note is not None:
                notes.append(slot_note)
        capacity = composition_region_capacity(
            size, value.get("layout"), variant, region.get("path"),
        )
        region = dict(region)
        if capacity is not None:
            region.update(referenceWidth=capacity.get("width"),
                          referenceHeight=capacity.get("height"))
            if capacity.get("fixedGap") is not None:
                region["gap"] = capacity.get("fixedGap")
            region["capacitySource"] = "layout_contract"
        else:
            region["capacitySource"] = "model_estimate"
            notes.append(f"region {region.get('id')} capacity must be checked against "
                         "the complete layout contract before generating.")
        groups: list[dict[str, Any]] = []
        for group in region.get("groups"):
            normalized_group = _composition_group(group, group_schema, index_map, facts, size)
            if normalized_group is None:
                return None, [warning]
            covered.update(normalized_group.get("factIndexes"))
            notes.extend(normalized_group.get("placementNotes", []))
            groups.append(normalized_group)
        height = sum(group.get("referenceHeight") for group in groups)
        height += region.get("gap") * (len(groups) - 1)
        remaining = region.get("referenceHeight") - height
        height_tolerance = 2.0 if size == "2x2" else 0.0
        if remaining < -height_tolerance:
            notes.append(f"region {region.get('id')} overflows by {-remaining:g}vp; "
                         "replace this complete grouping, do not shrink or omit facts.")
        normalized.append({**region, "groups": groups, "requiredHeight": height,
                           "remainingHeight": remaining})
    if covered != set(range(len(facts))):
        return None, ["composition incomplete: retain every info_required fact and action; "
                      "rebuild complete region assignments before generating."]
    return {"layout": value.get("layout"), "variant": variant, "regions": normalized}, notes


def _anchor_plan_errors(
    facts: list[dict[str, Any]],
    layout_hints: list[str],
    composition: dict[str, Any] | None,
) -> list[str]:
    """阻止没有独立左下支撑事实的 Anchor 进入生成阶段。"""
    composition_is_anchor = (
        isinstance(composition, dict) and composition.get("layout") == "S-title-anchor"
    )
    if not composition_is_anchor and "S-title-anchor" not in layout_hints:
        return []
    if not composition_is_anchor:
        body_facts = [
            fact
            for fact in facts
            if "actionId" not in fact
            and fact.get("componentHints") != ["SingleLineTitle"]
        ]
        if len(body_facts) >= 2:
            return []
        return [
            "S-title-anchor requires one primary body fact and at least one independent "
            "support fact; title-only context and actions do not count. Remove the Anchor "
            "hint and choose a text-action layout when support is empty."
        ]

    support_indexes: set[int] = set()
    other_visible_indexes: set[int] = set()
    for region in composition.get("regions", []):
        path = tuple(region.get("path", []))
        indexes: set[int] = set()
        for group in region.get("groups", []):
            for index in group.get("factIndexes", []):
                if not isinstance(index, int) or not 0 <= index < len(facts):
                    continue
                if "actionId" not in facts[index]:
                    indexes.add(index)
        if path[:3] == (1, 1, 0):
            support_indexes.update(indexes)
        elif path[:1] == (0,) or path[:2] == (1, 0):
            other_visible_indexes.update(indexes)
    independent_support = support_indexes - other_visible_indexes
    if independent_support:
        return []
    return [
        "S-title-anchor composition must assign at least one independent non-action fact "
        "to support path [1, 1, 0]; a title fact, duplicated primary fact, empty group or "
        "invented label cannot fill the left support region. Choose a text-action layout."
    ]


def _secondary_body_composition_errors(
    composition: dict[str, Any] | None,
) -> list[str]:
    """Require every planned SecondaryBody group to support a core group in its region."""
    if not isinstance(composition, dict):
        return []
    errors: list[str] = []
    for region in composition.get("regions", []):
        if not isinstance(region, dict):
            continue
        groups = region.get("groups", [])
        if not isinstance(groups, list):
            continue
        components: set[str] = set()
        for group in groups:
            if not isinstance(group, dict):
                continue
            component = group.get("component")
            if isinstance(component, str):
                components.add(component)
        if "SecondaryBody" not in components:
            continue
        if components & CORE_INFORMATION_COMPONENT_TYPES:
            continue
        errors.append(
            f"composition region {region.get('id')} uses SecondaryBody without a core "
            "information component in the same region; titles, buttons, layout containers "
            "and other SecondaryBody groups do not count."
        )
    return errors


def _small_content_region(
    region: dict[str, Any], layout: dict[str, Any], variant: int,
) -> tuple[dict[str, Any], str | None]:
    """正文误分到带嵌套动作的父区时，交接真实纯正文槽，不重复分配动作高度。"""
    groups = region.get("groups", [])
    if not groups or any(not isinstance(group, dict) for group in groups):
        return region, None
    if any(group.get("component") in
                         {"SingleLineTitle", "DoubleLineTitle", *_ACTION_FACT_COMPONENTS}
                         for group in groups):
        return region, None
    path = tuple(region.get("path", []))
    rules = layout.get("patterns", [])[variant - 1].get("rules", [])
    action_paths = [tuple(rule.get("path", [])) for rule in rules
                    if rule.get("eventPolicy") == "require"]
    if not any(len(action) > len(path) and action[:len(path)] == path for action in action_paths):
        return region, None
    slots = []
    for rule in rules:
        slot = rule.get("path", [])
        if len(slot) != len(path) + 1 or tuple(slot)[:len(path)] != path:
            continue
        if rule.get("types") != ["Column"]:
            continue
        if any(action[:len(slot)] == tuple(slot) for action in action_paths):
            continue
        slots.append(slot)
    if len(slots) != 1:
        return region, None
    return {**region, "path": slots[0]}, (
        f"content assignment moved from parent {list(path)} to pure content slot {slots[0]}; "
        "its capacity excludes the separate action reservation. Keep all facts and original "
        "fonts; regroup short same-object auxiliary facts if the complete content overflows."
    )


def _composition_region_shape(value: Any, schema: dict[str, Any]) -> bool:
    if not isinstance(value, dict) or set(value) != set(schema.get("required")):
        return False
    if not isinstance(value.get("id"), str) or not value.get("id").strip():
        return False
    path = value.get("path")
    if not isinstance(path, list):
        return False
    for index in path:
        if not isinstance(index, int) or isinstance(index, bool) or index < 0:
            return False
    for key in ("referenceWidth", "referenceHeight", "gap"):
        if not _finite_extent(value.get(key)):
            return False
    groups = value.get("groups")
    return isinstance(groups, list) and 1 <= len(groups) <= 24


def _composition_group(
    value: Any, schema: dict[str, Any], index_map: dict[int, int],
    facts: list[dict[str, Any]], size: Any,
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    if set(value) - set(schema.get("properties")) or not set(schema.get("required")) <= set(value):
        return None
    component = value.get("component")
    if component not in _component_hints(size) or not _finite_extent(value.get("referenceHeight")):
        return None
    indexes, placements = value.get("factIndexes"), value.get("placements")
    if not isinstance(indexes, list) or not isinstance(placements, list):
        return None
    value = dict(value)
    placement_notes: list[str] = []
    if not indexes:
        if component != "SingleLineTitle" or placements not in ([], ["title"]):
            return None
        placements = []
    elif len(indexes) == 1 and placements == ["value", "displayValue"]:
        if component not in {"ProgressCircleSingle", "ProgressLine2"}:
            return None
        indexes = indexes * 2
    elif len(indexes) == 1 and placements == ["value", "unit"]:
        if component != "EmphasizedData":
            return None
        placements = ["value"]
        placement_notes.append(
            "EmphasizedData.unit is not another copy of its numeric fact: resolve the real "
            "unit from the field contract, never bind the numeric value to unit."
        )
    if len(indexes) != len(placements) or len(indexes) > 24:
        return None
    value["placements"] = placements
    remapped: list[int] = []
    for index, placement in zip(indexes, placements, strict=True):
        if not isinstance(index, int) or isinstance(index, bool) or index not in index_map:
            return None
        if not isinstance(placement, str) or not placement.strip():
            return None
        remapped.append(index_map[index])
    actions = [index for index in remapped if "actionId" in facts[index]]
    if actions and (len(remapped) != 1 or component not in _ACTION_FACT_COMPONENTS):
        return None
    if not actions and component in _ACTION_FACT_COMPONENTS:
        return None
    for key in ("columns", "labelLines"):
        number = value.get(key)
        if key in value and (type(number) is not int or number not in (1, 2)):
            return None
    lines = value.get("lines")
    if lines is not None:
        if not isinstance(lines, list) or not lines:
            return None
        for line in lines:
            if type(line) is not int or line not in (1, 2):
                return None
    for key in ("variant", "density"):
        if key in value and not isinstance(value.get(key), str):
            return None
        allowed = schema.get("properties", {}).get(key, {}).get("enum")
        if key in value and allowed is not None and value.get(key) not in allowed:
            return None
    height = composition_group_minimum_height(size, value)
    planned_height = value.get("referenceHeight")
    if height is not None:
        exact_small_readout = size == "2x2" and component in {"EmphasizedData", "EmphasisText"}
        planned_height = height if exact_small_readout else max(height, planned_height)
    group = {**value, "factIndexes": remapped, "referenceHeight": planned_height}
    if size == "2x2" and component == "TableText":
        item_indexes = set()
        for placement in placements:
            match = re.fullmatch(r"items\[(\d+)\]\.(?:label|value)", placement)
            if match is not None:
                item_indexes.add(int(match.group(1)))
        if item_indexes and (len(item_indexes) not in (2, 3)
                             or item_indexes != set(range(len(item_indexes)))):
            group["implementationConflict"] = (
                "TableText only supports two or three contiguous items, not "
                f"{len(item_indexes)}. Keep every fact; regroup ordinary information in "
                "SecondaryBody at its legal single-row/multiline font, combining short same-object "
                "attributes into full-width labelled lines when they fit. Do not copy "
                "the invalid table or shrink text to create a smaller table."
            )
    if placement_notes:
        group["placementNotes"] = placement_notes
    return group


def parse_compact_plan_call(
    raw_output: str,
    task_spec: dict[str, Any],
    *,
    static_text_source: str | None = None,
    require_composition: bool = False,
) -> CompactPlanValidationResult:
    """解析命名工具调用包，并按当前 TaskSpec 标准化 Plan。"""
    syntax_warnings: list[str] = []
    payload = _parse_json_object(raw_output, syntax_warnings)
    if set(payload) != {"name", "arguments"}:
        raise CompactPlanValidationError(
            ["Plan output must contain only name and arguments."]
        )
    if payload.get("name") != SUBMIT_CARD_PLAN:
        raise CompactPlanValidationError(
            [f"Plan output must call {SUBMIT_CARD_PLAN}."]
        )
    arguments = payload.get("arguments")
    if isinstance(arguments, str):
        arguments = _parse_json_object(arguments, syntax_warnings)
    if not isinstance(arguments, dict):
        raise CompactPlanValidationError(["submit_card_plan.arguments must be an object."])
    asset_ids = compact_plan_asset_ids(task_spec)
    allowed_arguments = {"info_required", "layoutHints"}
    if asset_ids:
        allowed_arguments.add("assetAssignments")
    if require_composition:
        allowed_arguments.add("composition")
    unknown_arguments = set(arguments) - allowed_arguments
    if unknown_arguments:
        names = ", ".join(sorted(unknown_arguments))
        raise CompactPlanValidationError([f"Unsupported Plan arguments: {names}."])
    facts, warnings = _validate_facts(
        arguments.get("info_required"),
        task_spec,
        static_text_source=static_text_source,
    )
    warnings[:0] = syntax_warnings
    plan: dict[str, Any] = {"info_required": facts}
    if asset_ids:
        if "assetAssignments" not in arguments:
            raise CompactPlanValidationError(
                ["assetAssignments is required when TaskSpec provides asset candidates."]
            )
        plan["assetAssignments"] = _normalize_asset_assignments(
            arguments.get("assetAssignments"),
            facts,
            task_spec,
        )
    layout_hints, layout_warnings = _normalize_layout_hints(
        arguments.get("layoutHints"),
        task_spec.get("size"),
    )
    warnings.extend(layout_warnings)
    if layout_hints:
        plan["layoutHints"] = layout_hints
    composition = None
    composition_warnings: list[str] = []
    if require_composition:
        if "composition" not in arguments:
            raise CompactPlanValidationError(
                ["composition is required when runtime prompt context is enabled."]
            )
        composition, composition_warnings = _normalize_composition(
            arguments.get("composition"), arguments.get("info_required"), facts,
            task_spec.get("size"),
        )
        if composition is None:
            errors = composition_warnings or ["composition is invalid or incomplete."]
            raise CompactPlanValidationError(errors)
        overflow_errors = []
        for region in composition.get("regions", []):
            remaining = region.get("remainingHeight")
            if isinstance(remaining, (int, float)) and remaining < 0:
                overflow_errors.append(
                    f"composition region {region.get('id')} has negative remainingHeight "
                    f"{remaining:g}vp; rebuild the complete grouping without omitting facts."
                )
        if overflow_errors:
            raise CompactPlanValidationError(overflow_errors)
    anchor_errors = _anchor_plan_errors(facts, layout_hints, composition)
    if anchor_errors:
        raise CompactPlanValidationError(anchor_errors)
    secondary_body_errors = _secondary_body_composition_errors(composition)
    if secondary_body_errors:
        raise CompactPlanValidationError(secondary_body_errors)
    warnings.extend(composition_warnings)
    duration_paths = set(compound_duration_bindings(plan, task_spec))
    for fact in facts:
        if fact.get("dataId") not in duration_paths:
            continue
        hints = fact.get("componentHints", [])
        if "EmphasizedData" not in hints:
            continue
        corrected: list[str] = []
        for hint in hints:
            candidate = "EmphasisText" if hint == "EmphasizedData" else hint
            if candidate not in corrected:
                corrected.append(candidate)
        fact["componentHints"] = corrected
        warnings.append("Compound duration text uses EmphasisText, not a numeric hero; "
                        "retain the complete binding and all units.")
    if composition is not None:
        incompatible = False
        for region in composition.get("regions", []):
            for group in region.get("groups", []):
                if group.get("component") != "EmphasizedData":
                    continue
                for index in group.get("factIndexes", []):
                    if not isinstance(index, int) or not 0 <= index < len(facts):
                        continue
                    if facts[index].get("dataId") in duration_paths:
                        incompatible = True
        if incompatible:
            note = ("composition uses a numeric hero for compound duration text; regroup "
                    "with EmphasisText and retain every fact, binding and unit.")
            if require_composition:
                raise CompactPlanValidationError([note])
            composition = None
            warnings.append(note)
    if composition is not None:
        plan["composition"] = composition
    if composition_warnings:
        plan["compositionNotes"] = composition_warnings
    return CompactPlanValidationResult(plan=plan, warnings=tuple(warnings))


def compact_plan_context(
    plan: dict[str, Any], *, implementation_conflicts: list[str] | None = None,
    execution_selected: bool = False,
) -> str:
    """构造第二阶段使用的硬事实与软候选说明。"""
    conflicts = (
        composition_implementation_conflicts(plan)
        if implementation_conflicts is None else implementation_conflicts
    )
    context_plan = dict(plan)
    if conflicts:
        context_plan.pop("composition", None)
        context_plan["compositionNotes"] = conflicts
    asset_instruction = ""
    if "assetAssignments" in context_plan:
        asset_instruction = (
            "assetAssignments 冻结素材消费顺序与结果：先按 actionId 将分配落实到对应"
            "动作组件。有 SingleLineTitle 时，将 title 中的非空素材落实到其中一个"
            "语义匹配的标题且恰好使用一次，不按组件行顺序或左右位置确定标题。"
            "其余标题不得增加未分配图标；title.assetId 为 null 时所有标题保持无图标。"
            "无标题布局不消费标题装饰素材，不得为此新增标题；必需标题事实仍须满足。"
            "按钮分配始终落实，不得复用、互换或跳过，也不得用未分配素材覆盖空分配。"
        )
    small_conflict = False
    if conflicts:
        for layout_hint in plan.get("layoutHints", []):
            if isinstance(layout_hint, str) and layout_hint.startswith("S-"):
                small_conflict = True
                break
    preference_instruction = (
        "componentHints 第一项是首选：语义、类型、素材、事件和容量成立时应落实；"
        "具体条件不成立才改选合法备选或组件组合。"
    )
    intent_context = _component_intent_context(plan)
    if small_conflict:
        preference_instruction = (
            "当前小卡compositionNotes已证明原合组或容量有冲突，原候选首项不再是实例清单。"
            "先重算完整信息组与动作的合法承载，再选匹配组件；不要按旧候选逐事实实例化，"
            "普通辅助状态不新增强调焦点。候选与全部硬事实保留，不靠降字或删事实过关。"
        )
        intent_context = ""
    payload = json.dumps(context_plan, ensure_ascii=False, separators=(",", ":"))
    if execution_selected:
        conflict_instruction = ""
        if small_conflict:
            conflict_instruction = (
                "本轮小卡旧分区已有明确合组或容量冲突，不能继续保留失效的body包装或"
                "按候选首项逐事实新增实例。按当前完整布局变体重新核算全部事实和动作，"
                "普通辅助状态不叠加强调焦点；只交接诊断与文字指导，不提供恢复蓝图。"
            )
        return (
            "# 已接受的 Compact Info Plan\n\n"
            "info_required 冻结全部 must/should 事实与真实动作；未明确进入"
            "drop_optional_component 阶段时，两种优先级都必须可见。组件候选不是新增实例清单；"
            "compositionRecovery 提供完整参考时实现其中已选方案，不再按 componentHints 第一项"
            "重做选型，也不照抄已经诊断为冲突的旧 composition。"
            "没有恢复参考时，合法composition保持原分区和合组；没有完整composition时"
            "按对象信息关系和当前尺寸完整案例组织，不能把候选第一项当作逐事实实例清单。"
            f"{conflict_instruction}"
            "普通时间、数量说明和状态不因候选排序新增强调焦点；标题与主值职责保持不变。"
            "局部修复保持待修树的合法结构，只处理明确错误。"
            f"{asset_instruction}"
            "按参考蓝图的父子关系和事实索引落实真实绑定、完整文案与所属动作；"
            "索引从0开始，不能把索引或压力样值写入最终 DSL。标题绑定保留指定标题职责。"
            "核对必要的对象标签、完整单位与全部动作，原字号不变，不能裁切或删信息。"
            "参考预算不代替标签与单位的核算；明确发现参考方案仍不成立时才整体重组。\n\n"
            f"```json\n{payload}\n```"
        )
    return (
        "# 已接受的 Compact Info Plan\n\n"
        "以下 Plan 冻结 must/should 信息、静态正文和操作；正常生成与修复都必须完整展示两种优先级，"
        "只有微服务明确进入 drop_optional_component 最终兜底时，"
        "才允许省略程序指定的非 Action 事实。"
        "除标题组件职责外，"
        "componentHints 与 layoutHints 不冻结组件实例或最终骨架，但不能无理由忽略。"
        "当 composition 已选中且合同、容量均成立时，它是本轮的执行选择；尤其"
        "S-title-anchor 不能仅因存在 PillButton 就被降级替换为底部文字动作布局。"
        f"{preference_instruction}先按对象和信息关系合组，再映射可见 Prop。"
        "不能因为完整案例使用了其它组件就将匹配的信息组拆成逐字段的单文字组件。"
        "每项事实必须在最终 Compact DSL 中有完整可读的落点；"
        "同组图形与对应读数允许共用绑定，禁止跨组无意义重复。"
        "不得为了布局或修复删除 Plan 事实；动作必须使用 "
        "TaskSpec 中对应 actionId 的完整事件候选。最终组件与布局仍按完整合同和容量选择。\n"
        f"{asset_instruction}\n"
        "若有 composition，按它的 layout/variant、region.path 与顺序 groups 实现，"
        "factIndexes 引用下面去重后的 info_required，placements 指明每条事实的可见 Prop。"
        "空映射 SingleLineTitle 只是装饰标题的容量预留，不是遗漏事实；"
        "重复索引表示同一实例共用同一事实，不能据此增加实例或重复正文。"
        "placementNotes 中的单位必须按原字段合同解决，不能把数值当单位再次绑定。"
        "不要重新逐字段实例化组件，或把单列合组改回窄双列；动作保持完整目标名称。"
        "每区 sum(referenceHeight)+gap 必须小于可用高度，横排每列还须容纳完整文字。"
        "这些数字仅用于容量核算，区域输出仍为 matchParent/layoutWeight；"
        "正文必须承接扣除标题、动作、padding和间距后的剩余空间，不能向整父区撑高。"
        "compositionNotes 是需要纠正的组合诊断，不允许通过裁切、缩字或删事实处理。"
        "确有合同/容量冲突时整体重选可承载的分区合组并重新核算，不能盲从错误计划。\n"
        "一个语义分区可使用一个 SingleLineTitle；2x4 左右独立分区"
        "可分别使用 SingleLineTitle。被 Plan 指定给 SingleLineTitle 的标题事实必须出现在某个"
        "SingleLineTitle.title 中，不能改由正文组件承载。需要标题加次信息时使用 DoubleLineTitle。\n"
        "逐项核对 dataId → 可见组件 Prop：标题、地区、更新时间也必须真实绑定；"
        "不能用用户原话或 sampleValue 写死，即使首帧文字相同。只写数据行、只在事件参数"
        "引用都不算可见。actionId → 所属对象的点击组件或用户明确要求的独立动作槽，"
        "两者都须有准确可见的动作名称；独立操作不要求同名数据根。入会不能挂在"
        "耳机等无关信息块，不能因槽位已满省略动作。数值图形不支持的格式化文本保留文字，"
        "不得从 sampleValue 提取数字写成静态进度。\n"
        "有路径引用不等于读数能看全。逐项检查标签、值、单位在扣除 padding 和图标后"
        "的实际文字区：使用当前路径所属对象的短名称加完整动态读数，不复制示例的对象标签。"
        "耳机数据不能标为手机，左右读数必须区分；长说明不能挤掉数值。"
        "平均、最高、最低各有独立统计含义，不能拼成无标签区间；动作短名保留必要目标限定。"
        "第二行只放另一项必要事实，不重复主行标签；取消可选图标仍放不下时改用基础组合。"
        "先按信息关系形成完整组件组合，再比较能容纳组合与全部动作的合法布局和内容槽；"
        "不先锁定辅助槽再压入事实，不把宽卡默认堆成单列。横排先核对完整文本所需宽度，"
        "纵排累加真实行数、固定行高和间距，使用当前组件合同而非照抄示例容量。"
        "动作先留足高度，环、状态、标题的总高度不能超出剩余正文；layoutWeight 不会让"
        "文字或环缩小。时间段、日期时间和带长单位的指标使用普通字号或分行，不套用大数字。\n\n"
        f"```json\n{payload}\n```"
        f"{intent_context}"
    )


def _component_intent_context(plan: dict[str, Any]) -> str:
    """把已接受的首选映射成核对表，不新增硬使用率门禁或模型调用。"""
    allowed = set(_COMPONENT_HINTS["2x2"]) | set(_COMPONENT_HINTS["2x4"])
    groups: dict[str, list[int]] = {}
    for index, fact in enumerate(plan.get("info_required", []), start=1):
        if not isinstance(fact, dict):
            continue
        hints = fact.get("componentHints")
        if not isinstance(hints, list) or not hints:
            continue
        preferred = hints[0]
        if isinstance(preferred, str) and preferred in allowed:
            groups.setdefault(preferred, []).append(index)
    if not groups:
        return ""
    payload = json.dumps(groups, ensure_ascii=False, separators=(",", ":"))
    return (
        "\n\n# 本轮首选组件落点核对\n\n"
        "编号是 info_required 中从 1 开始的事实序号，不是组件数量。"
        "此表按候选组件类型汇总，不是信息分组结果；"
        "先按对象与信息关系确定实例，再逐事实核对覆盖。"
        "同对象、同事件或同级信息组才合并实例，不混合不同对象。"
        "生成和修复前核对首选是否落实，不适配时按具体语义、绑定、容量原因改选。"
        "此核对不输出解释、不添加协议字段、不删事实凑组件。"
        "保留正式骨架的父容器与层级，组件放在内容槽内；"
        "逐 Prop 核对自身绑定合同，不借用其它组件属性。\n\n"
        f"```json\n{payload}\n```"
    )


@dataclass(frozen=True)
class _CompactVisibleState:
    paths: frozenset[str]
    literals: tuple[str, ...]
    title_paths: frozenset[str]
    title_literals: tuple[str, ...]
    handlers: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class CompactPlanCoverageResult:
    """区分阻断生成的 Plan 覆盖错误与仅供观察的静态文案告警。"""

    errors: tuple[str, ...]
    warnings: tuple[str, ...]


def _compact_visible_state(components: list[ComponentRow]) -> _CompactVisibleState:
    visible_paths: set[str] = set()
    visible_literals: list[str] = []
    single_line_title_paths: set[str] = set()
    single_line_title_literals: list[str] = []
    handlers: list[dict[str, Any]] = []
    for component in components:
        visible_props = {
            key: value
            for key, value in component.props.items()
            if key in _VISIBLE_PROP_NAMES
        }
        _collect_paths_and_literals(visible_props, visible_paths, visible_literals)
        if component.component_type == "SingleLineTitle":
            _collect_paths_and_literals(
                {"title": component.props.get("title")},
                single_line_title_paths,
                single_line_title_literals,
            )
        on_click = component.props.get("onClick")
        if isinstance(on_click, list):
            handlers.extend(item for item in on_click if isinstance(item, dict))
    return _CompactVisibleState(
        paths=frozenset(visible_paths),
        literals=tuple(_normalize_text(value) for value in visible_literals),
        title_paths=frozenset(single_line_title_paths),
        title_literals=tuple(_normalize_text(value) for value in single_line_title_literals),
        handlers=tuple(handlers),
    )


def _compact_fact_coverage_result(
    fact: dict[str, Any],
    state: _CompactVisibleState,
    event_handlers: dict[str, dict[str, Any]],
) -> CompactPlanCoverageResult:
    requirement = fact.get("requirement")
    label = requirement if isinstance(requirement, str) else "unknown requirement"
    hints = fact.get("componentHints")
    requires_single_line_title = isinstance(hints, list) and "SingleLineTitle" in hints
    data_id = fact.get("dataId")
    if isinstance(data_id, str) and data_id not in state.paths:
        return CompactPlanCoverageResult(
            errors=(f"Plan fact is missing from visible DSL: {label} ({data_id}).",),
            warnings=(),
        )
    if (
        isinstance(data_id, str)
        and requires_single_line_title
        and data_id not in state.title_paths
    ):
        return CompactPlanCoverageResult(
            errors=(
                "Plan title fact must be visible in a SingleLineTitle.title: "
                f"{label} ({data_id}).",
            ),
            warnings=(),
        )
    action_id = fact.get("actionId")
    if isinstance(action_id, str):
        expected = event_handlers.get(action_id)
        if expected is None or expected not in state.handlers:
            return CompactPlanCoverageResult(
                errors=(
                    f"Plan action is missing from visible DSL: {label} ({action_id}).",
                ),
                warnings=(),
            )
        return CompactPlanCoverageResult(errors=(), warnings=())
    text = fact.get("text")
    if isinstance(text, str):
        expected_text = _normalize_text(text)
        if requires_single_line_title and not any(
            expected_text in actual for actual in state.title_literals
        ):
            return CompactPlanCoverageResult(
                errors=(
                    "Plan title fact must be visible in a SingleLineTitle.title: "
                    f"{label}.",
                ),
                warnings=(),
            )
        if not expected_text or not any(expected_text in actual for actual in state.literals):
            return CompactPlanCoverageResult(
                errors=(),
                warnings=(f"Plan static text is not fully visible in DSL: {label}.",),
            )
    return CompactPlanCoverageResult(errors=(), warnings=())


def evaluate_compact_plan_coverage(
    compact_dsl: str,
    plan: dict[str, Any] | None,
    task_spec: dict[str, Any],
    *,
    allowed_omitted_fact_indexes: tuple[int, ...] = (),
) -> CompactPlanCoverageResult:
    """检查 Plan 覆盖，并将普通静态文案的非完整命中降级为告警。"""
    if not plan:
        return CompactPlanCoverageResult(errors=(), warnings=())
    rows = parse_compact_dsl_rows(compact_dsl)
    components = [row for row in rows if isinstance(row, ComponentRow)]
    state = _compact_visible_state(components)
    event_handlers = _event_handlers_by_id(task_spec)
    allowed = set(allowed_omitted_fact_indexes)
    errors: list[str] = []
    warnings: list[str] = []
    facts = plan.get("info_required")
    if not isinstance(facts, list):
        return CompactPlanCoverageResult(
            errors=("Accepted Compact Plan has no info_required facts.",),
            warnings=(),
        )
    for index, fact in enumerate(facts):
        if not isinstance(fact, dict):
            continue
        result = _compact_fact_coverage_result(fact, state, event_handlers)
        if index in allowed and "actionId" not in fact:
            continue
        errors.extend(result.errors)
        warnings.extend(result.warnings)
    required_layout = _required_anchor_layout(plan, task_spec)
    if required_layout is not None:
        try:
            match_compact_layout(
                components,
                size="2x2",
                layout_scope=required_layout,
            )
        except CompactLayoutRuntimeError:
            errors.append(
                "Accepted Compact Plan selected S-title-anchor as its executable "
                "composition; keep the CircleButton anchor layout instead of replacing it "
                "with a text-action layout that compresses the required content."
            )
    return CompactPlanCoverageResult(errors=tuple(errors), warnings=tuple(warnings))


def compact_plan_coverage_errors(
    compact_dsl: str,
    plan: dict[str, Any] | None,
    task_spec: dict[str, Any],
    *,
    allowed_omitted_fact_indexes: tuple[int, ...] = (),
) -> tuple[str, ...]:
    """返回会阻断 Compact DSL 发布的 Plan 覆盖错误。"""
    return evaluate_compact_plan_coverage(
        compact_dsl,
        plan,
        task_spec,
        allowed_omitted_fact_indexes=allowed_omitted_fact_indexes,
    ).errors


def compact_plan_coverage_warnings(
    compact_dsl: str,
    plan: dict[str, Any] | None,
    task_spec: dict[str, Any],
    *,
    allowed_omitted_fact_indexes: tuple[int, ...] = (),
) -> tuple[str, ...]:
    """返回不阻断发布的普通静态文案覆盖告警。"""
    return evaluate_compact_plan_coverage(
        compact_dsl,
        plan,
        task_spec,
        allowed_omitted_fact_indexes=allowed_omitted_fact_indexes,
    ).warnings


def compact_plan_omitted_facts(
    compact_dsl: str,
    plan: dict[str, Any] | None,
    task_spec: dict[str, Any],
    allowed_omitted_fact_indexes: tuple[int, ...],
) -> tuple[dict[str, Any], ...]:
    """返回最终兜底后确实不再可见的非 Action 事实。"""
    if not plan or not allowed_omitted_fact_indexes:
        return ()
    facts = plan.get("info_required")
    if not isinstance(facts, list):
        return ()
    rows = parse_compact_dsl_rows(compact_dsl)
    components = [row for row in rows if isinstance(row, ComponentRow)]
    state = _compact_visible_state(components)
    event_handlers = _event_handlers_by_id(task_spec)
    omitted: list[dict[str, Any]] = []
    for index in allowed_omitted_fact_indexes:
        if not 0 <= index < len(facts):
            continue
        fact = facts[index]
        if not isinstance(fact, dict) or "actionId" in fact:
            continue
        result = _compact_fact_coverage_result(fact, state, event_handlers)
        if result.errors or result.warnings:
            omitted.append(fact)
    return tuple(omitted)


def compact_plan_optional_drop_candidate(
    compact_dsl: str,
    plan: dict[str, Any] | None,
    task_spec: dict[str, Any],
) -> CompactOptionalDropCandidate | None:
    """优先选 should-only 组件，并在同类候选中最小化事实损失。"""
    if not plan:
        return None
    facts = plan.get("info_required")
    if not isinstance(facts, list):
        return None
    try:
        rows = parse_compact_dsl_rows(compact_dsl)
    except (TypeError, ValueError):
        return None
    event_handlers = _event_handlers_by_id(task_spec)
    should_only_candidates: list[CompactOptionalDropCandidate] = []
    fallback_candidates: list[CompactOptionalDropCandidate] = []
    for row in rows:
        if not isinstance(row, ComponentRow):
            continue
        if row.component_type in {"Row", "Column", "Stack"}:
            continue
        if row.component_type in _ACTION_FACT_COMPONENTS:
            continue
        if row.props.get("onClick"):
            continue
        state = _compact_visible_state([row])
        matched: list[int] = []
        priorities: list[str] = []
        has_action_fact = False
        for index, fact in enumerate(facts):
            if not isinstance(fact, dict):
                continue
            result = _compact_fact_coverage_result(fact, state, event_handlers)
            if result.errors or result.warnings:
                continue
            if "actionId" in fact:
                has_action_fact = True
                break
            matched.append(index)
            priorities.append(str(fact.get("priority") or "must"))
        if has_action_fact or not matched:
            continue
        requirements = tuple(str(facts[index].get("requirement") or "") for index in matched)
        candidate = CompactOptionalDropCandidate(
            component_id=row.component_id,
            component_type=row.component_type,
            fact_indexes=tuple(matched),
            requirements=requirements,
            contains_must_facts=any(priority != "should" for priority in priorities),
        )
        if candidate.contains_must_facts:
            fallback_candidates.append(candidate)
        else:
            should_only_candidates.append(candidate)
    candidates = should_only_candidates or fallback_candidates
    if not candidates:
        return None
    return min(candidates, key=lambda item: len(item.fact_indexes))


def _required_anchor_layout(
    plan: dict[str, Any],
    task_spec: dict[str, Any],
) -> str | None:
    """已闭合的 anchor 方案是执行选择，不允许 DSL 阶段无理由降级为文字按钮。"""
    if task_spec.get("size") != "2x2":
        return None
    composition = plan.get("composition")
    if not isinstance(composition, dict) or composition.get("layout") != "S-title-anchor":
        return None
    if composition_implementation_conflicts(plan):
        return None
    for fact in plan.get("info_required", []):
        if not isinstance(fact, dict) or "actionId" not in fact:
            continue
        hints = fact.get("componentHints")
        if isinstance(hints, list) and hints and hints[0] == "CircleButton":
            return "S-title-anchor"
    return None
def compact_plan_data_paths(task_spec: dict[str, Any]) -> tuple[str, ...]:
    """按 TaskSpec 顺序列出可作为事实目标的叶子 JSON Pointer。"""
    schema = task_spec.get("dataModelSchema")
    if not isinstance(schema, dict):
        return ()
    paths: list[str] = []
    _collect_schema_paths(schema, (), paths)
    return tuple(dict.fromkeys(paths))


def compact_plan_action_ids(task_spec: dict[str, Any]) -> tuple[str, ...]:
    """列出本轮具有稳定 ID 的事件候选。"""
    candidates = task_spec.get("eventCandidates")
    if not isinstance(candidates, list):
        return ()
    identifiers: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        identifier = candidate.get("id")
        if isinstance(identifier, str) and identifier.strip():
            identifiers.append(identifier.strip())
    return tuple(dict.fromkeys(identifiers))


def compact_plan_asset_ids(task_spec: dict[str, Any]) -> tuple[str, ...]:
    """按 TaskSpec 顺序列出具有稳定 ID 和静态路径的素材候选。"""
    candidates = task_spec.get("assetCandidates")
    if not isinstance(candidates, list):
        return ()
    identifiers: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        identifier = candidate.get("id")
        source = candidate.get("src")
        if not isinstance(identifier, str) or not identifier.strip():
            continue
        if not isinstance(source, str) or not source.strip():
            continue
        identifiers.append(identifier.strip())
    return tuple(dict.fromkeys(identifiers))


def _normalize_asset_assignments(
    value: Any,
    facts: list[dict[str, Any]],
    task_spec: dict[str, Any],
) -> dict[str, Any]:
    """校验按钮优先、标题随后且不复用素材的显式分配。"""
    if not isinstance(value, dict) or set(value) != {"actions", "title"}:
        raise CompactPlanValidationError(
            ["assetAssignments must contain only actions and title."]
        )
    asset_ids = set(compact_plan_asset_ids(task_spec))
    selected_action_ids = [
        fact.get("actionId")
        for fact in facts
        if isinstance(fact.get("actionId"), str)
    ]
    actions = value.get("actions")
    if not isinstance(actions, list):
        raise CompactPlanValidationError(["assetAssignments.actions must be an array."])
    normalized_actions: dict[str, dict[str, Any]] = {}
    used_assets: set[str] = set()
    errors: list[str] = []
    for index, assignment in enumerate(actions):
        location = f"assetAssignments.actions[{index}]"
        if not isinstance(assignment, dict):
            errors.append(f"{location} must be an object.")
            continue
        unknown_keys = set(assignment) - {"actionId", "assetId", "reason"}
        if unknown_keys:
            names = ", ".join(sorted(unknown_keys))
            errors.append(f"{location} contains unsupported fields: {names}.")
            continue
        action_id = assignment.get("actionId")
        if action_id not in selected_action_ids:
            errors.append(f"{location}.actionId is not selected by info_required.")
            continue
        if action_id in normalized_actions:
            errors.append(f"{location}.actionId is duplicated: {action_id}.")
            continue
        normalized = _normalize_single_asset_assignment(
            assignment,
            asset_ids,
            location=location,
            used_assets=used_assets,
            errors=errors,
        )
        normalized["actionId"] = action_id
        normalized_actions[action_id] = normalized
    missing_actions = [
        action_id for action_id in selected_action_ids if action_id not in normalized_actions
    ]
    if missing_actions:
        errors.append(
            "assetAssignments.actions must decide every selected action: "
            + ", ".join(missing_actions)
            + "."
        )
    title = value.get("title")
    if not isinstance(title, dict):
        errors.append("assetAssignments.title must be an object.")
        normalized_title: dict[str, Any] = {"assetId": None, "reason": "invalid"}
    else:
        unknown_keys = set(title) - {"assetId", "reason"}
        if unknown_keys:
            names = ", ".join(sorted(unknown_keys))
            errors.append(f"assetAssignments.title contains unsupported fields: {names}.")
        normalized_title = _normalize_single_asset_assignment(
            title,
            asset_ids,
            location="assetAssignments.title",
            used_assets=used_assets,
            errors=errors,
        )
    if errors:
        raise CompactPlanValidationError(errors)
    ordered_actions = [normalized_actions[action_id] for action_id in selected_action_ids]
    return {"actions": ordered_actions, "title": normalized_title}


def _normalize_single_asset_assignment(
    value: dict[str, Any],
    asset_ids: set[str],
    *,
    location: str,
    used_assets: set[str],
    errors: list[str],
) -> dict[str, Any]:
    """标准化单个按钮或标题的素材决定。"""
    asset_id = value.get("assetId")
    reason = value.get("reason")
    if asset_id is None:
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"{location}.reason is required when assetId is null.")
            return {"assetId": None, "reason": "invalid"}
        return {"assetId": None, "reason": reason.strip()}
    if not isinstance(asset_id, str) or asset_id not in asset_ids:
        errors.append(f"{location}.assetId is not present in TaskSpec asset candidates.")
        return {"assetId": None, "reason": "invalid"}
    if asset_id in used_assets:
        errors.append(f"{location}.assetId reuses an already assigned asset: {asset_id}.")
    used_assets.add(asset_id)
    return {"assetId": asset_id}


def _validate_facts(
    value: Any,
    task_spec: dict[str, Any],
    *,
    static_text_source: str | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(value, list) or not value:
        raise CompactPlanValidationError(
            ["info_required must be a non-empty array of atomic facts."]
        )
    if len(value) > 24:
        raise CompactPlanValidationError(["info_required must contain at most 24 facts."])
    data_paths = set(compact_plan_data_paths(task_spec))
    progress_paths: list[str] = []
    _collect_progress_schema_paths(
        task_spec.get("dataModelSchema"),
        (),
        progress_paths,
    )
    progress_data_paths = set(progress_paths)
    action_ids = set(compact_plan_action_ids(task_spec))
    allowed_hints = set(_component_hints(task_spec.get("size")))
    user_query = task_spec.get("userQuery")
    query_text = user_query if isinstance(user_query, str) else ""
    if static_text_source:
        query_text = f"{query_text}\n{static_text_source}"
    normalized: list[dict[str, Any]] = []
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    warnings: list[str] = []
    errors: list[str] = []
    for index, raw_fact in enumerate(value):
        location = f"info_required[{index}]"
        if not isinstance(raw_fact, dict):
            errors.append(f"{location} must be an object.")
            continue
        unknown_keys = set(raw_fact) - _FACT_KEYS
        if unknown_keys:
            names = ", ".join(sorted(unknown_keys))
            errors.append(f"{location} contains unsupported fields: {names}.")
            continue
        requirement = raw_fact.get("requirement")
        if not isinstance(requirement, str) or not requirement.strip():
            errors.append(f"{location}.requirement must be non-empty text.")
            continue
        targets = [name for name in _TARGET_KEYS if _non_empty(raw_fact.get(name))]
        if len(targets) != 1:
            errors.append(
                f"{location} must choose exactly one of dataId, actionId, or text."
            )
            continue
        target = targets[0]
        target_value = raw_fact[target].strip()
        if target == "dataId" and target_value not in data_paths:
            errors.append(f"{location}.dataId is not present in TaskSpec: {target_value}.")
            continue
        if target == "dataId" and _internal_action_parameter_fact(
            target_value, requirement, task_spec, query_text,
        ):
            errors.append(
                f"{location}: {target_value} is an internal identifier used only by an action, "
                "not a requested visible fact. Keep its original path in the complete event "
                "candidate and retain that action; rebuild this Plan with every real display "
                "requirement, without adding an identifier text row. Do not remove user facts."
            )
            continue
        if target == "actionId" and target_value not in action_ids:
            errors.append(
                f"{location}.actionId is not present in TaskSpec: {target_value}."
            )
            continue
        if target == "text" and _normalize_text(target_value) not in _normalize_text(
            query_text
        ):
            errors.append(f"{location}.text must be copied from userQuery.")
            continue
        priority = raw_fact.get("priority", "must")
        if priority not in _FACT_PRIORITIES:
            errors.append(f"{location}.priority must be must or should.")
            continue
        if target == "actionId" and priority != "must":
            priority = "must"
            warnings.append(f"{location}.priority was forced to must for an action.")
        fact: dict[str, Any] = {
            "requirement": requirement.strip(),
            "priority": priority,
            target: target_value,
        }
        hints = raw_fact.get("componentHints")
        if hints is not None:
            if not isinstance(hints, list):
                warnings.append(
                    f"{location}.componentHints was ignored because it is not an array."
                )
            else:
                accepted_hints: list[str] = []
                removed_type_mismatch = False
                removed_target_mismatch = False
                for hint in hints:
                    if not isinstance(hint, str) or hint not in allowed_hints:
                        continue
                    is_action_hint = hint in _ACTION_FACT_COMPONENTS
                    if (target == "actionId") != is_action_hint:
                        removed_target_mismatch = True
                        continue
                    if hint in _PROGRESS_FACT_COMPONENTS:
                        if target != "dataId" or target_value not in progress_data_paths:
                            removed_type_mismatch = True
                            continue
                    if hint not in accepted_hints:
                        accepted_hints.append(hint)
                removed_single_line_title_alternatives = False
                removed_single_line_title_backup = False
                if task_spec.get("size") == "2x2" and accepted_hints:
                    title_is_backup = accepted_hints[0] != "SingleLineTitle"
                    if title_is_backup and "SingleLineTitle" in accepted_hints:
                        accepted_hints.remove("SingleLineTitle")
                        removed_single_line_title_backup = True
                if "SingleLineTitle" in accepted_hints and accepted_hints != ["SingleLineTitle"]:
                    accepted_hints = ["SingleLineTitle"]
                    removed_single_line_title_alternatives = True
                if accepted_hints:
                    fact["componentHints"] = accepted_hints[:3]
                if accepted_hints != hints:
                    reason = "unsupported or duplicate values."
                    if removed_single_line_title_backup:
                        reason = (
                            "a fallback SingleLineTitle cannot override the preferred "
                            "body component or create a new mandatory title role."
                        )
                    elif removed_single_line_title_alternatives:
                        reason = (
                            "alternatives because SingleLineTitle is the exclusive "
                            "title component."
                        )
                    elif removed_target_mismatch:
                        reason = "unsupported, target-incompatible or duplicate values."
                    elif removed_type_mismatch:
                        reason = "unsupported, type-incompatible or duplicate values."
                    warnings.append(f"{location}.componentHints removed {reason}")
        identity = (target, target_value)
        previous = seen.get(identity)
        if previous is None:
            seen[identity] = fact
            normalized.append(fact)
            continue
        if fact["requirement"] not in previous["requirement"]:
            previous["requirement"] += "; " + fact["requirement"]
        if fact["priority"] == "must":
            previous["priority"] = "must"
        merged_hints = list(
            dict.fromkeys(
                [*previous.get("componentHints", []), *fact.get("componentHints", [])]
            )
        )
        if merged_hints:
            previous["componentHints"] = merged_hints[:3]
        warnings.append(f"{location} duplicated an existing target and was merged.")
    if errors:
        raise CompactPlanValidationError(errors)
    return normalized, warnings


def _internal_action_parameter_fact(
    path: str, requirement: str, task: dict[str, Any], query: str,
) -> bool:
    """仅反馈计划自己承认的内部传参标识错误；不推断普通字段不可见。"""
    if not re.search(r"仅供|仅用于|用于(?:打开|定位|识别|传参)", requirement):
        return False
    if re.search(r"(?:显示|展示|查看).{0,16}(?:编号|标识|(?<![a-z])ID(?![a-z])|entityId)",
                 query, re.I):
        return False
    from services.compact_composition_planner import _schema_value

    description = _schema_value(task, path).get("description", "")
    if not re.search(r"(?:唯一|内部).{0,12}(?:标识|(?<![a-z])ID(?![a-z]))", description, re.I):
        return False
    for candidate in task.get("eventCandidates", []):
        if not isinstance(candidate, dict):
            continue
        paths: set[str] = set()
        literals: list[str] = []
        _collect_paths_and_literals(candidate.get("args"), paths, literals)
        if path in paths:
            return True
    return False


def _normalize_layout_hints(
    value: Any,
    size: Any,
) -> tuple[list[str], list[str]]:
    if value is None:
        return [], []
    if not isinstance(value, list):
        return [], ["layoutHints was ignored because it is not an array."]
    allowed = set(_layout_hints(size))
    accepted: list[str] = []
    for item in value:
        if isinstance(item, str) and item in allowed and item not in accepted:
            accepted.append(item)
    accepted = accepted[:2]
    warnings = []
    if accepted != value:
        warnings.append("layoutHints removed unsupported, duplicate, or excess values.")
    return accepted, warnings


def _parse_json_object(
    raw_output: str, warnings: list[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(raw_output, str) or not raw_output.strip():
        raise CompactPlanValidationError(["Plan output must be non-empty JSON."])
    text = raw_output.strip()
    match = _JSON_FENCE.fullmatch(text)
    if match is not None:
        text = match.group(1).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        repaired = _recover_plan_closers(text)
        if repaired is None:
            raise CompactPlanValidationError(["Plan output must be valid JSON."]) from exc
        payload = repaired
        if warnings is not None:
            warnings.append("Plan JSON terminal closing delimiters recovered; facts unchanged.")
    if not isinstance(payload, dict):
        raise CompactPlanValidationError(["Plan output root must be an object."])
    return payload


def _recover_plan_closers(text: str) -> dict[str, Any] | None:
    """只恢复终端纯闭合串，不补值、不改字符串、不修内部结构。"""
    suffix = re.search(r"[\]}\s]+$", text)
    if suffix is None:
        return None
    prefix = text[:suffix.start()]
    stack: list[str] = []
    in_string = False
    escaped = False
    for char in prefix:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "[{":
            stack.append("]" if char == "[" else "}")
        elif char in "]}":
            if not stack or stack.pop() != char:
                return None
    if in_string or not stack:
        return None
    actual = re.sub(r"\s", "", suffix.group())
    expected = "".join(reversed(stack))
    if not 1 <= abs(len(actual) - len(expected)) <= 2:
        return None
    shorter, longer = sorted((actual, expected), key=len)
    cursor = iter(longer)
    for char in shorter:
        if char not in cursor:
            return None
    try:
        payload = json.loads(prefix + expected)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _collect_schema_paths(
    value: Any,
    path: tuple[str | int, ...],
    output: list[str],
    *,
    numeric_only: bool = False,
) -> None:
    if isinstance(value, list):
        for index, item in enumerate(value):
            _collect_schema_paths(item, (*path, index), output, numeric_only=numeric_only)
        return
    if not isinstance(value, dict):
        if path and not numeric_only:
            output.append(_json_pointer(path))
        return
    if _is_schema_leaf(value):
        if path and (not numeric_only or value.get("type") in {"number", "integer"}):
            output.append(_json_pointer(path))
        return
    if value.get("type") == "array" and "items" in value:
        _collect_schema_paths(value["items"], (*path, 0), output, numeric_only=numeric_only)
        return
    if value.get("type") == "object" and isinstance(value.get("properties"), dict):
        for key, child in value["properties"].items():
            _collect_schema_paths(child, (*path, key), output, numeric_only=numeric_only)
        return
    for key, child in value.items():
        _collect_schema_paths(child, (*path, key), output, numeric_only=numeric_only)


def _collect_progress_schema_paths(
    value: Any,
    path: tuple[str | int, ...],
    output: list[str],
) -> None:
    if isinstance(value, list):
        for index, item in enumerate(value):
            _collect_progress_schema_paths(item, (*path, index), output)
        return
    if not isinstance(value, dict):
        return
    if _is_schema_leaf(value):
        field_type = value.get("type")
        sample_value = value.get("sampleValue")
        numeric_field = field_type in {"number", "integer"}
        percentage_text = (
            field_type == "string"
            and isinstance(sample_value, str)
            and _PERCENTAGE_VALUE.fullmatch(sample_value) is not None
        )
        if path and (numeric_field or percentage_text):
            output.append(_json_pointer(path))
        return
    if value.get("type") == "array" and "items" in value:
        _collect_progress_schema_paths(value["items"], (*path, 0), output)
        return
    if value.get("type") == "object" and isinstance(value.get("properties"), dict):
        for key, child in value["properties"].items():
            _collect_progress_schema_paths(child, (*path, key), output)
        return
    for key, child in value.items():
        _collect_progress_schema_paths(child, (*path, key), output)


def _is_schema_leaf(value: dict[str, Any]) -> bool:
    field_type = value.get("type")
    if isinstance(field_type, str) and field_type not in {"array", "object"}:
        return True
    return "sampleValue" in value and not isinstance(value.get("sampleValue"), dict)


def _json_pointer(path: tuple[str | int, ...]) -> str:
    tokens = [str(item).replace("~", "~0").replace("/", "~1") for item in path]
    return "/" + "/".join(tokens)


def _collect_paths_and_literals(
    value: Any,
    paths: set[str],
    literals: list[str],
) -> None:
    if isinstance(value, str):
        matches = list(_BINDING_PATH.finditer(value))
        if matches:
            paths.update(match.group("path") for match in matches)
        else:
            literals.append(value)
        return
    if isinstance(value, dict):
        if set(value) == {"path"} and isinstance(value.get("path"), str):
            paths.add(value["path"])
            return
        for child in value.values():
            _collect_paths_and_literals(child, paths, literals)
        return
    if isinstance(value, list):
        for child in value:
            _collect_paths_and_literals(child, paths, literals)


def _event_handlers_by_id(task_spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    handlers: dict[str, dict[str, Any]] = {}
    candidates = task_spec.get("eventCandidates")
    if not isinstance(candidates, list):
        return handlers
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        identifier = candidate.get("id")
        call = candidate.get("call")
        args = candidate.get("args")
        if (
            isinstance(identifier, str)
            and isinstance(call, str)
            and isinstance(args, dict)
        ):
            handlers[identifier] = {"call": call, "args": args}
    return handlers


def _component_hints(size: Any) -> tuple[str, ...]:
    candidates = _COMPONENT_HINTS.get(size, _SHARED_FACT_COMPONENTS)
    return tuple(
        component
        for component in candidates
        if component in MODEL_COMPACT_INPUT_COMPONENT_TYPES
    )


def _layout_hints(size: Any) -> tuple[str, ...]:
    return _LAYOUT_HINTS.get(size, ())


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", "", value).casefold() if isinstance(value, str) else ""


def _non_empty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())
