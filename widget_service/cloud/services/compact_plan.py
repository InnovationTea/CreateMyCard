# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact DSL 两阶段生成使用的信息计划合同。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from services.compact_dsl_a2ui_converter import (
    COMPACT_INPUT_COMPONENT_TYPES,
    ComponentRow,
    parse_compact_dsl_rows,
)

SUBMIT_CARD_PLAN = "submit_card_plan"

_JSON_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL | re.IGNORECASE)
_BINDING_PATH = re.compile(r"\$\{(?P<path>/[^}\s]+)\}")
_FACT_KEYS = frozenset(
    {"requirement", "dataId", "actionId", "text", "componentHints"}
)
_TARGET_KEYS = ("dataId", "actionId", "text")
_SHARED_FACT_COMPONENTS = (
    "CardHeader",
    "EmphasizedData",
    "InfoBlock",
    "ProgressCircleSingle",
    "ProgressCircle",
    "TableText",
    "EventCard",
    "Text",
    "Image",
    "PillButton",
)
_NUMERIC_FACT_COMPONENTS = frozenset(
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
        "primaryText",
        "secondaryLabel",
        "secondaryText",
        "src",
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


def build_compact_plan_tool(task_spec: dict[str, Any]) -> dict[str, Any]:
    """根据本次 TaskSpec 构造 submit_card_plan 的动态工具合同。"""
    size = task_spec.get("size")
    data_paths = list(compact_plan_data_paths(task_spec))
    action_ids = list(compact_plan_action_ids(task_spec))
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
            "description": "一个必须可见的原子信息或操作。",
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
                "按优先级排列的组件软候选，不冻结最终组件。进度组件只推荐给本事实"
                "直接绑定的 number/integer dataId；字符串、布尔值、静态正文和操作不推荐进度组件。"
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
    return {
        "type": "function",
        "function": {
            "name": SUBMIT_CARD_PLAN,
            "description": (
                "提交最终卡片必须可见的信息与操作；组件和布局只提供软候选。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "info_required": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 24,
                        "items": {
                            "type": "object",
                            "properties": properties,
                            "required": ["requirement"],
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
                },
                "required": ["info_required"],
                "additionalProperties": False,
            },
        },
    }


def parse_compact_plan_call(
    raw_output: str,
    task_spec: dict[str, Any],
    *,
    static_text_source: str | None = None,
) -> CompactPlanValidationResult:
    """解析命名工具调用包，并按当前 TaskSpec 标准化 Plan。"""
    payload = _parse_json_object(raw_output)
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
        arguments = _parse_json_object(arguments)
    if not isinstance(arguments, dict):
        raise CompactPlanValidationError(["submit_card_plan.arguments must be an object."])
    unknown_arguments = set(arguments) - {"info_required", "layoutHints"}
    if unknown_arguments:
        names = ", ".join(sorted(unknown_arguments))
        raise CompactPlanValidationError([f"Unsupported Plan arguments: {names}."])
    facts, warnings = _validate_facts(
        arguments.get("info_required"),
        task_spec,
        static_text_source=static_text_source,
    )
    plan: dict[str, Any] = {"info_required": facts}
    layout_hints, layout_warnings = _normalize_layout_hints(
        arguments.get("layoutHints"),
        task_spec.get("size"),
    )
    warnings.extend(layout_warnings)
    if layout_hints:
        plan["layoutHints"] = layout_hints
    return CompactPlanValidationResult(plan=plan, warnings=tuple(warnings))


def compact_plan_context(plan: dict[str, Any]) -> str:
    """构造第二阶段使用的硬事实与软候选说明。"""
    payload = json.dumps(plan, ensure_ascii=False, separators=(",", ":"))
    return (
        "# 已接受的 Compact Info Plan\n\n"
        "以下 Plan 只冻结必须可见的信息、静态正文和操作；componentHints 与 "
        "layoutHints 都是软候选，不冻结组件实例或最终骨架。每项事实必须由最终 Compact "
        "DSL 中恰好一个可见 Prop 承载。不得为了布局或修复删除 Plan 事实；动作必须使用 "
        "TaskSpec 中对应 actionId 的完整事件候选。最终组件与布局仍按完整合同和容量选择。\n"
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
        "动作先留足高度，环、状态、标题的总高度不能超出剩余正文；layoutWeight 不会让"
        "文字或环缩小。时间段、日期时间和带长单位的指标使用普通字号或分行，不套用大数字。\n\n"
        f"```json\n{payload}\n```"
    )


def compact_plan_coverage_errors(
    compact_dsl: str,
    plan: dict[str, Any] | None,
    task_spec: dict[str, Any],
) -> tuple[str, ...]:
    """检查最终 Compact DSL 是否覆盖已冻结的信息与操作。"""
    if not plan:
        return ()
    rows = parse_compact_dsl_rows(compact_dsl)
    components = [row for row in rows if isinstance(row, ComponentRow)]
    visible_paths: set[str] = set()
    visible_literals: list[str] = []
    handlers: list[dict[str, Any]] = []
    for component in components:
        visible_props = {
            key: value
            for key, value in component.props.items()
            if key in _VISIBLE_PROP_NAMES
        }
        _collect_paths_and_literals(visible_props, visible_paths, visible_literals)
        on_click = component.props.get("onClick")
        if isinstance(on_click, list):
            handlers.extend(item for item in on_click if isinstance(item, dict))
    event_handlers = _event_handlers_by_id(task_spec)
    normalized_literals = [_normalize_text(value) for value in visible_literals]
    errors: list[str] = []
    facts = plan.get("info_required")
    if not isinstance(facts, list):
        return ("Accepted Compact Plan has no info_required facts.",)
    for fact in facts:
        if not isinstance(fact, dict):
            continue
        requirement = fact.get("requirement")
        label = requirement if isinstance(requirement, str) else "unknown requirement"
        if "dataId" in fact and fact["dataId"] not in visible_paths:
            errors.append(f"Plan fact is missing from visible DSL: {label} ({fact['dataId']}).")
            continue
        if "actionId" in fact:
            expected = event_handlers.get(fact["actionId"])
            if expected is None or expected not in handlers:
                errors.append(
                    f"Plan action is missing from visible DSL: {label} ({fact['actionId']})."
                )
            continue
        if "text" in fact:
            expected_text = _normalize_text(fact["text"])
            if not expected_text or not any(
                expected_text in actual for actual in normalized_literals
            ):
                errors.append(f"Plan static text is missing from visible DSL: {label}.")
    return tuple(errors)


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
    numeric_paths: list[str] = []
    _collect_schema_paths(task_spec.get("dataModelSchema"), (), numeric_paths, numeric_only=True)
    numeric_data_paths = set(numeric_paths)
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
        fact: dict[str, Any] = {
            "requirement": requirement.strip(),
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
                    if hint in _NUMERIC_FACT_COMPONENTS:
                        if target != "dataId" or target_value not in numeric_data_paths:
                            removed_type_mismatch = True
                            continue
                    if hint not in accepted_hints:
                        accepted_hints.append(hint)
                if accepted_hints:
                    fact["componentHints"] = accepted_hints[:3]
                if accepted_hints != hints:
                    reason = "unsupported or duplicate values."
                    if removed_target_mismatch:
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


def _parse_json_object(raw_output: str) -> dict[str, Any]:
    if not isinstance(raw_output, str) or not raw_output.strip():
        raise CompactPlanValidationError(["Plan output must be non-empty JSON."])
    text = raw_output.strip()
    match = _JSON_FENCE.fullmatch(text)
    if match is not None:
        text = match.group(1).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CompactPlanValidationError(["Plan output must be valid JSON."]) from exc
    if not isinstance(payload, dict):
        raise CompactPlanValidationError(["Plan output root must be an object."])
    return payload


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
        if component in COMPACT_INPUT_COMPONENT_TYPES
    )


def _layout_hints(size: Any) -> tuple[str, ...]:
    return _LAYOUT_HINTS.get(size, ())


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", "", value).casefold() if isinstance(value, str) else ""


def _non_empty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())
