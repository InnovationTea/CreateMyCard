# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""为 Design Compact 质量修复选择逐级升级的执行范围。"""

import copy
import hashlib
import json
import re
from dataclasses import dataclass, replace
from typing import Any

from services.compact_dsl_a2ui_converter import ComponentRow, parse_compact_dsl_rows
from services.compact_high_level_components import CompactDslConversionError
from services.compact_plan import (
    CompactOptionalDropCandidate,
    compact_plan_optional_drop_candidate,
)
from services.compact_repair_context import (
    JOINT_RECOMPOSITION_INSTRUCTION,
    bounded_component_capacity_contexts,
    repair_topology_fingerprint,
    semantic_layout_repair_guidance,
)

_CAPACITY_MARKERS = (
    "compact_static_text_capacity",
    "vertical layout requires at least",
    "overflows by",
    "occupancy:",
    "within available height",
    "text width overflow",
)
_STRUCTURE_MARKERS = (
    "compact layout does not match scope",
    "layout does not match",
    "语义布局不符合合同",
    "slot root",
    "must have",
    "must use row",
    "must use column",
)
_ROOT_STRUCTURE_MARKERS = (
    "compact layout does not match scope",
    "layout does not match",
    "语义布局不符合合同",
    "component rows must form one tree rooted at root",
    "unreachable component(s):",
    "cyclic component reference",
    "missing component reference",
    "component has multiple parents",
    " has multiple parents:",
    "the root component is missing",
)
_TREE_STRUCTURE_CODES = frozenset(
    {
        "COMPACT_COMPONENT_DUPLICATE_CHILD",
        "COMPACT_COMPONENT_MULTIPLE_PARENTS",
        "COMPACT_COMPONENT_EMPTY_CONTAINER",
    }
)
_LAYOUT_CAPACITY_CODES = frozenset(
    {
        "COMPACT_LAYOUT_HEIGHT_OVERFLOW",
        "COMPACT_LAYOUT_HEIGHT_UNRESOLVED",
        "COMPACT_LAYOUT_WIDTH_OVERFLOW",
    }
)

_TREE_RECOMPOSE_INSTRUCTION = (
    " 先检查以 root 为根的完整组件树：所有引用存在、每个节点只有一个父引用、"
    "没有环或孤立节点，并核对父区允许的角色和有序 children。"
    "不得只把孤立节点挂到不接受该角色的 Region；必要时重组受控 Group 或更换合法父布局。"
    "保留全部事实、绑定、标签、单位和动作，不通过删除孤立业务节点规避错误；"
    "结构闭合后重新核算各区容量，不修改展开后的内部几何。"
)
_INFO_BLOCK_PROGRESS_VALUE_MARKERS = (
    "infoblock.primarytext must be a finite number or complete numeric percentage",
    "infoblock.primarytext must resolve between 0 and total",
)
_SECONDARY_BODY_DYNAMIC_LABEL_MARKERS = ("secondarybody.items[].label only accepts a static value",)
_SECONDARY_BODY_FONT_SIZE_MARKERS = ("secondarybody.fontsize must be the fixed recipe value",)
_CAPACITY_REGROUP_CONTRACT_MARKERS = ("is auxiliary and cannot be the only information component",)
_TABLE_TEXT_ITEM_RANGE_MARKER = "tabletext.items requires 2 to 3 entries"
_DUPLICATE_PLAN_FACT_PREFIX = "plan fact is displayed more than once in visible dsl:"
_DUPLICATE_PLAN_ACTION_PREFIX = "plan action is displayed more than once in visible dsl:"
COMPACT_COMPONENT_FALLBACK_MAX_ATTEMPTS = 2
DROP_OPTIONAL_COMPONENT_MIN_REPAIR_ATTEMPT = 4
PLAN_COVERAGE_EARLY_DROP_MIN_REPAIR_ATTEMPTS = 2

_CAPACITY_TEXT_COMPACTION_INSTRUCTION = (
    " 容量修复的受控选型例外：仅当2x4强调读数组合已确认放不下、整卡其它位置已有"
    "TextBlock等核心信息组件，且用户未明确要求大号强调、进度或事件形式时，"
    "可将该读数和同对象短补充合并为一个SecondaryBody.items。短字段名称放静态label，"
    "动态值和单位放value，完整保留全部标签、数值、单位、绑定和Action。"
    "这是更换显示组件，不是缩小EmphasizedData的固定字号；新组件整组单行14fp/14vp，"
    "多行或任一项maxLines:2时12fp/12vp，行间距2vp。更新父级引用并移除被替换的旧子树；"
    "不得补造核心组件、拆成多个单项SecondaryBody或删除事实来满足条件。"
)

_TEXT_ONLY_TABLE_REPAIR_INSTRUCTION = (
    " 当前可见业务正文只有SecondaryBody等普通标签—值文本，没有可承担核心信息的组件。"
    "若同一对象内有2–3项同级、等权、无事件／比例／强调语义的短标签—值，"
    "优先按TableText合同重组该组，由TableText承担核心信息角色；"
    "两项使用fontSize 12并预留38vp，三项使用fontSize 10并预留52vp。"
    "逐项保留label、value、完整动态绑定与对象归属；不能只把组件改名，"
    "不能将事件、比例或应强调的主值表格化。超出TableText容量的事实继续放入其它合法内容角色，"
    "只有optionalDrop或approvedOmissions明确授权的事实才能省略。"
)

_PILL_ACTION_ANCHOR_MIGRATION_INSTRUCTION = (
    " 当前是2×2文字动作布局，且全宽PillButton参与了容量压力。"
    "可把S-title-anchor作为同级合法布局候选，但不能只把PillButton改名为CircleButton。"
    "仅当已接受Plan只有一个显式动作、存在与动作语义准确匹配的SVG、用户没有要求卡面显示"
    "按钮文案，并且正文能够拆成上方主信息和左下独立支撑信息时，才整体迁移："
    "将root.layout改为S-title-anchor，按[title, primary, support, action]重排直属children，"
    "将原动作改为CircleButton，完整保留原onClick和icon，并把原按钮文案写入"
    "accessibility.label；保留全部事实、绑定和动作。若任一条件不满足，则保留PillButton，"
    "改选其它能够闭合容量的合法组件组合或父布局。"
)

_ANCHOR_MIGRATION_SOURCE_LAYOUTS = frozenset(
    {
        "S-title-content-action",
        "S-title-primary-secondary-action",
    }
)


@dataclass(frozen=True)
class CompactRepairDirective:
    """一次 Design Compact 修复应采用的范围与策略。"""

    category: str
    scope: str
    repair_strategy: str
    retry_target: str
    fingerprint: str
    consecutive_failures: int
    category_attempt: int
    no_progress: bool
    retryable: bool
    instruction: str
    fallback_stage: str | None = None
    fallback_attempt: int | None = None
    fallback_attempt_limit: int | None = None
    fallback_remaining_attempts: int | None = None
    optional_drop: CompactOptionalDropCandidate | None = None
    approved_omitted_fact_indexes: tuple[int, ...] = ()
    stop_reason: str | None = None
    joint_context: dict[str, Any] | None = None
    capacity_fits: tuple[dict[str, Any], ...] = ()

    def to_prompt_payload(self) -> dict[str, Any]:
        """转换成可进入修复提示词和 Trace 的稳定字段。"""
        payload: dict[str, Any] = {
            "category": self.category,
            "scope": self.scope,
            "repairStrategy": self.repair_strategy,
            "retryTarget": self.retry_target,
            "fingerprint": self.fingerprint,
            "consecutiveFailures": self.consecutive_failures,
            "categoryAttempt": self.category_attempt,
            "noProgress": self.no_progress,
            "retryable": self.retryable,
            "instruction": self.instruction,
        }
        if self.fallback_stage is not None:
            payload.update(
                {
                    "fallbackStage": self.fallback_stage,
                    "fallbackAttempt": self.fallback_attempt,
                    "fallbackAttemptLimit": self.fallback_attempt_limit,
                    "fallbackRemainingAttempts": self.fallback_remaining_attempts,
                }
            )
        if self.optional_drop is not None:
            payload["optionalDrop"] = {
                "componentId": self.optional_drop.component_id,
                "componentType": self.optional_drop.component_type,
                "allowedOmittedFactIndexes": list(self.optional_drop.fact_indexes),
                "requirements": list(self.optional_drop.requirements),
                "containsMustFacts": self.optional_drop.contains_must_facts,
            }
            if self.optional_drop.partial:
                payload["optionalDrop"]["partial"] = True
                payload["optionalDrop"]["displayTexts"] = list(self.optional_drop.display_texts)
                if self.optional_drop.item_indexes:
                    payload["optionalDrop"]["allowedItemIndexes"] = list(
                        self.optional_drop.item_indexes
                    )
            if self.optional_drop.requires_core_reattach:
                payload["optionalDrop"]["requiresCoreReattach"] = True
                payload["optionalDrop"]["protectedCoreComponentIds"] = list(
                    self.optional_drop.protected_core_component_ids
                )
        if self.approved_omitted_fact_indexes:
            payload["approvedOmittedFactIndexes"] = list(self.approved_omitted_fact_indexes)
        if self.stop_reason is not None:
            payload["stopReason"] = self.stop_reason
        if self.joint_context is not None:
            payload["jointRecomposition"] = copy.deepcopy(self.joint_context)
        if self.capacity_fits:
            payload["capacityFits"] = copy.deepcopy(list(self.capacity_fits))
        return payload


def _normalized_issue_message(message: str) -> str:
    """忽略每轮可变的 vp 数值，保留被违反的容器与约束。"""
    normalized = message.strip().lower()
    return re.sub(r"\b\d+(?:\.\d+)?vp\b", "<vp>", normalized)


def _issue_fingerprint(quality_errors: list[dict[str, Any]]) -> str:
    entries: list[tuple[str, str, str]] = []
    for issue in quality_errors:
        entries.append(
            (
                str(issue.get("stage") or ""),
                str(issue.get("code") or ""),
                _normalized_issue_message(str(issue.get("message") or "")),
            )
        )
    encoded = json.dumps(sorted(entries), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _contains_marker(messages: str, markers: tuple[str, ...]) -> bool:
    return any(marker in messages for marker in markers)


def _duplicate_entries(issue: dict[str, Any]) -> list[dict[str, Any]]:
    entries = []
    for name in ("duplicateFacts", "duplicateActions"):
        values = issue.get(name)
        if isinstance(values, list):
            entries.extend(value for value in values if isinstance(value, dict))
    return entries


def _has_duplicate_actions(quality_errors: list[dict[str, Any]]) -> bool:
    for issue in quality_errors:
        actions = issue.get("duplicateActions")
        if isinstance(actions, list) and actions:
            return True
    return False


def _has_duplicate_plan_facts(quality_errors: list[dict[str, Any]]) -> bool:
    for issue in quality_errors:
        if _duplicate_entries(issue):
            return True
        message = str(issue.get("message") or "").strip().lower()
        if message.startswith((_DUPLICATE_PLAN_FACT_PREFIX, _DUPLICATE_PLAN_ACTION_PREFIX)):
            return True
    return False


def _duplicate_plan_fact_excess_count(quality_errors: list[dict[str, Any]]) -> int | None:
    """返回重复事实超出其允许展示次数的总数。"""
    structured_count = 0
    has_structured_facts = False
    message_count = 0
    for issue in quality_errors:
        duplicate_facts = _duplicate_entries(issue)
        if duplicate_facts:
            has_structured_facts = True
            for fact in duplicate_facts:
                if not isinstance(fact, dict):
                    continue
                actual_count = fact.get("actualVisibleCount")
                expected_count = fact.get("expectedVisibleCount")
                if isinstance(actual_count, int) and isinstance(expected_count, int):
                    structured_count += max(0, actual_count - expected_count)
            continue
        message = str(issue.get("message") or "").strip().lower()
        if message.startswith((_DUPLICATE_PLAN_FACT_PREFIX, _DUPLICATE_PLAN_ACTION_PREFIX)):
            message_count += 1
    if has_structured_facts:
        return structured_count
    return message_count if message_count else None


def _display_position_key(position: Any) -> tuple[str, str] | None:
    key = None
    if isinstance(position, dict):
        component_id = position.get("componentId")
        property_name = position.get("property")
        if isinstance(component_id, str) and isinstance(property_name, str):
            if component_id.strip() and property_name.strip():
                key = (component_id, property_name)
    return key


def _has_required_slot_conflict(fact: Any) -> bool:
    if not isinstance(fact, dict):
        return False
    data_id = fact.get("dataId")
    if not isinstance(data_id, str) or not data_id.startswith("/data/"):
        return False
    actual_count = fact.get("actualVisibleCount")
    if type(actual_count) is not int or actual_count < 2:
        return False
    expected_count = fact.get("expectedVisibleCount")
    if type(expected_count) is not int or expected_count != 1:
        return False
    positions = fact.get("requiredDisplayPositions")
    occurrences = fact.get("occurrences")
    if not isinstance(positions, list) or not isinstance(occurrences, list):
        return False
    occurrence_keys = set()
    for occurrence in occurrences:
        key = _display_position_key(occurrence)
        if key is not None:
            occurrence_keys.add(key)
    required_keys = set()
    for position in positions:
        key = _display_position_key(position)
        if key is not None and key in occurrence_keys:
            required_keys.add(key)
    return len(required_keys) >= 2


def _has_duplicate_required_slot_conflict(quality_errors: list[dict[str, Any]]) -> bool:
    """只接受同一已报重复事实中至少两个独立必填展示位置的诊断。"""
    for issue in quality_errors:
        if _has_duplicate_action_slot_conflict(issue):
            return True
        duplicate_facts = issue.get("duplicateFacts")
        if not isinstance(duplicate_facts, list):
            continue
        for fact in duplicate_facts:
            if _has_required_slot_conflict(fact):
                return True
    return False


def _has_duplicate_action_slot_conflict(issue: dict[str, Any]) -> bool:
    actions = issue.get("duplicateActions")
    if not isinstance(actions, list):
        return False
    for action in actions:
        if not isinstance(action, dict) or not isinstance(action.get("actionId"), str):
            continue
        actual_count = action.get("actualVisibleCount")
        expected_count = action.get("expectedVisibleCount")
        if type(actual_count) is not int or actual_count < 2:
            continue
        if type(expected_count) is not int or expected_count != 1:
            continue
        occurrences = action.get("occurrences")
        if not isinstance(occurrences, list):
            continue
        positions = set()
        fixed_slot = False
        for occurrence in occurrences:
            key = _display_position_key(occurrence)
            if key is None or key[1] != "onClick":
                continue
            positions.add(key)
            if occurrence.get("fixedRequiredSlot") is True:
                fixed_slot = True
        if len(positions) >= 2 and fixed_slot:
            return True
    return False


def _duplicate_action_instruction(*, duplicate_count_not_reduced: bool) -> str:
    instruction = (
        "逐项修复 duplicateActions 中同一完整 onClick 的重复入口，核对 occurrences、父角色和"
        "fixedRequiredSlot；最终保留一个完整入口以及原事件数组、参数、动态绑定、标签和图标。"
        "不同参数、开关值或绑定的动作不得合并；不得删除任何独立 Action。"
        "可选动作移除后同步合法父变体；固定槽不能直接删 children、清空事件或放入占位内容，"
        "按 repairStrategy.scope 调整必要父布局和已有独立信息的落位，不复制信息或虚构动作填槽。"
        "保留字号、独立事实和数据行，冲突父区外不变；完整复查动作、信息、组件、结构及容量。"
        "不新增重试额度。"
    )
    if duplicate_count_not_reduced:
        instruction += (
            "上一轮重复超额数量没有减少；本轮须减少重复入口，不能只改 ID 或按钮名，"
            "不得新增、复制或换位置保留同一完整动作的重复入口。"
        )
    return instruction


def _has_missing_plan_fact_error(quality_errors: list[dict[str, Any]]) -> bool:
    """只识别非 Action 事实缺失；重复事实与动作缺失不能授权 Drop。"""
    for issue in quality_errors:
        if issue.get("code") != "COMPACT_PLAN_COVERAGE_FAILED":
            continue
        message = str(issue.get("message") or "").strip().lower()
        if message.startswith("plan fact is missing from visible dsl:"):
            return True
    return False


def _capacity_fits_from_issues(
    quality_errors: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """读取校验阶段已生成的固定组件容量证据。"""
    contexts: list[dict[str, Any]] = []
    for issue in quality_errors:
        capacity_fits = issue.get("capacityFits")
        if not isinstance(capacity_fits, list):
            continue
        for capacity_fit in capacity_fits:
            if isinstance(capacity_fit, dict):
                contexts.append(copy.deepcopy(capacity_fit))
    return contexts


def _capacity_regroup_contract_failure(
    quality_errors: list[dict[str, Any]],
) -> bool:
    """识别容量重组后常见的核心／辅助组件语义未闭合。"""
    messages = "\n".join(str(issue.get("message") or "").lower() for issue in quality_errors)
    return _contains_marker(messages, _CAPACITY_REGROUP_CONTRACT_MARKERS)


def _table_text_item_overflow_failure(
    compact_dsl: str,
    quality_errors: list[dict[str, Any]],
) -> bool:
    """只把已确认超过三项的 TableText 合同错误视为直接 Drop 信号。"""
    messages = "\n".join(str(issue.get("message") or "").lower() for issue in quality_errors)
    if _TABLE_TEXT_ITEM_RANGE_MARKER not in messages:
        return False
    try:
        rows = parse_compact_dsl_rows(
            compact_dsl,
            expand_layouts=False,
            skip_compact_dsl_validation=True,
            preserve_unreachable=True,
        )
    except (CompactDslConversionError, TypeError, ValueError):
        return False
    for row in rows:
        if not isinstance(row, ComponentRow) or row.component_type != "TableText":
            continue
        items = row.props.get("items")
        if isinstance(items, list) and len(items) > 3:
            return True
    return False


def _capacity_overflow_limit(capacity_fits: list[dict[str, Any]]) -> int | None:
    """返回本轮已证明的最小溢出事实数，用于限制提前 Drop 的损失。"""
    counts: list[int] = []
    for capacity_fit in capacity_fits:
        value = capacity_fit.get("overflowFactCount")
        if value is None:
            value = capacity_fit.get("overflowItemCount")
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            continue
        counts.append(value)
    return min(counts) if counts else None


def _capacity_overflow_fact_indexes(capacity_fits: list[dict[str, Any]]) -> set[int]:
    """只返回可由 doesNotFit 证明确认的 Plan 事实索引。"""
    indexes: set[int] = set()
    for capacity_fit in capacity_fits:
        overflow_items = capacity_fit.get("doesNotFit")
        if not isinstance(overflow_items, list):
            continue
        for overflow_item in overflow_items:
            if not isinstance(overflow_item, dict):
                continue
            plan_facts = overflow_item.get("planFacts")
            if not isinstance(plan_facts, list):
                continue
            for plan_fact in plan_facts:
                if not isinstance(plan_fact, dict):
                    continue
                fact_index = plan_fact.get("factIndex")
                if isinstance(fact_index, int) and not isinstance(fact_index, bool):
                    indexes.add(fact_index)
    return indexes


def _duplicate_fact_instruction(*, duplicate_count_not_reduced: bool) -> str:
    instruction = (
        "修复 duplicateFacts 列出的重复展示事实。逐项核对 occurrences，确保每个报错 "
        "dataId 最终只在一个可见属性中出现。优先保留同时具有明确对象、标签、完整值和单位的"
        "语义表达，不因字号更大就保留含义不清的裸值或生硬拼接。只删除其它重复绑定："
        "重复位于 SecondaryBody 单个 item 时只删除该 item；表达式同时包含多个 dataId 时只"
        "移除报错的重复引用，不连带删除未报错事实。组件仍有其它有效内容时保留组件；组件"
        "变空时删除组件行并同步删除直接父级 children 引用。不得修改 accepted Plan、删除"
        "唯一剩余展示、删除数据行、静态化动态值，或改变未报错的事实、Action、图标和区域。"
        "完成后逐项复查报错 dataId 的可见次数恰好为1，并确认没有空组件、孤立组件或失效引用。"
        "去重后 SecondaryBody 仍只能承担辅助信息；若核心组件或当前信息组语义不再成立，"
        "在本轮允许范围内重组选型，但不得重新引入重复绑定。"
    )
    if duplicate_count_not_reduced:
        instruction += (
            "上一轮重复超额数量没有减少；本轮必须删除至少一个 occurrences 中的重复引用，"
            "不得迁移、复制或新增该 dataId 的可见绑定。"
        )
    return instruction


def _duplicate_required_slot_instruction() -> str:
    return (
        "duplicateFacts.requiredDisplayPositions 已确认同一事实占据至少两个必填展示位置。"
        "本轮只调整这些冲突槽所在的必要父布局及信息组，为每个报错 dataId 保留唯一完整展示；"
        "允许重新分配已有独立事实或采用合同允许的组合，不无条件重建整卡。"
        "不能清空必填属性、仅删除固定槽、放置占位文字或虚构事实填槽；"
        "不得删除独有事实、标签、单位、数据行或 Action，不修改 accepted Plan、字号及组件内部UX。"
        "冲突父布局外的正确内容与结构保持不变。重复引用应减少，但不能用局部硬删破坏必填合同；"
        "修改后完整复检覆盖、动作、组件、结构和容量，未闭合继续返回真实错误。"
    )


def _fixed_side_slot_text_overflow(
    invalid_source_dsl: str,
    quality_errors: list[dict[str, Any]],
) -> bool:
    """识别侧双槽固定信息槽无法容纳完整单行内容的容量错误。"""
    messages = "\n".join(str(issue.get("message") or "") for issue in quality_errors)
    if "text width overflow" not in messages.lower():
        return False
    fixed_slots: list[str] = []
    for line in invalid_source_dsl.splitlines():
        try:
            payload = json.loads(line)
        except (TypeError, ValueError):
            continue
        if not isinstance(payload, list) or len(payload) != 4:
            continue
        if payload[0:2] != ["root", "Layout"]:
            continue
        props = payload[2]
        children = payload[3]
        if not isinstance(props, dict) or props.get("layout") != "W-content-side-slots":
            continue
        if not isinstance(children, list) or len(children) != 3:
            continue
        fixed_slots = [child for child in children[1:] if isinstance(child, str)]
        break
    if len(fixed_slots) != 2:
        return False
    for match in re.finditer(r"component\s+([^:\s]+):\s+text width overflow", messages, re.I):
        component_id = match.group(1)
        for slot_id in fixed_slots:
            if component_id == slot_id or component_id.startswith(f"{slot_id}_"):
                return True
    return False


def _capacity_text_compaction_relevant(invalid_source_dsl: str) -> bool:
    """只有当前 DSL 同时具备强调值与等权详情时才发送该受控例外。"""
    return '"EmphasizedData"' in invalid_source_dsl and '"TextBlock"' in invalid_source_dsl


def _pill_action_anchor_migration_relevant(
    invalid_source_dsl: str,
    task_spec: dict[str, Any] | None,
) -> bool:
    """识别2×2文字动作布局发生容量错误时可考虑的锚点布局迁移。"""
    if task_spec is None or task_spec.get("size") != "2x2":
        return False
    try:
        rows = parse_compact_dsl_rows(
            invalid_source_dsl,
            expand_layouts=False,
            skip_compact_dsl_validation=True,
        )
    except (CompactDslConversionError, TypeError, ValueError):
        return False
    components: dict[str, ComponentRow] = {}
    for row in rows:
        if isinstance(row, ComponentRow):
            components[row.component_id] = row
    root = components.get("root")
    if root is None or root.component_type != "Layout" or not root.children:
        return False
    if root.props.get("layout") not in _ANCHOR_MIGRATION_SOURCE_LAYOUTS:
        return False
    action = components.get(root.children[-1])
    return action is not None and action.component_type == "PillButton"


def _height_overflow_regions(quality_errors: list[dict[str, Any]]) -> set[str]:
    regions: set[str] = set()
    for issue in quality_errors:
        diagnostics = issue.get("compactDiagnostics")
        if not isinstance(diagnostics, list):
            continue
        for diagnostic in diagnostics:
            if not isinstance(diagnostic, dict):
                continue
            if diagnostic.get("code") != "COMPACT_LAYOUT_HEIGHT_OVERFLOW":
                continue
            component_id = diagnostic.get("componentId")
            if isinstance(component_id, str) and component_id:
                regions.add(component_id)
    return regions


def _has_quality_error_code(
    quality_errors: list[dict[str, Any]], expected_code: str
) -> bool:
    for issue in quality_errors:
        if issue.get("code") == expected_code:
            return True
        diagnostics = issue.get("compactDiagnostics")
        if not isinstance(diagnostics, list):
            continue
        for diagnostic in diagnostics:
            if isinstance(diagnostic, dict) and diagnostic.get("code") == expected_code:
                return True
    return False


def _requires_parent_layout_recompose(
    quality_errors: list[dict[str, Any]],
) -> bool:
    """多个分区同时超限，或容量与事实缺失并存时跳过局部重预算。"""
    has_plan_coverage_error = False
    for issue in quality_errors:
        if issue.get("code") == "COMPACT_PLAN_COVERAGE_FAILED":
            has_plan_coverage_error = True
            break
    regions = _height_overflow_regions(quality_errors)
    return len(regions) >= 2 or (bool(regions) and has_plan_coverage_error)


def _component_contract_instruction(quality_errors: list[dict[str, Any]]) -> str:
    """为可确定修法的组件属性错误提供不降级的精确指令。"""
    messages = "\n".join(str(issue.get("message") or "").lower() for issue in quality_errors)
    base_instruction = (
        "只修复错误组件中被定位的 Props、绑定或格式，并复查直接父容器；"
        "保留该组件其它合法属性、动态事实、事件和视觉能力，"
        "不得通过删除未报错属性、移除视觉变体或更换为弱语义组件来绕过校验。"
    )
    if _has_quality_error_code(
        quality_errors, "COMPACT_DISPLAY_ACTION_LABEL_TOO_LONG"
    ):
        return (
            f"{base_instruction} 只把报错按钮的可见label缩短到最多5个字符，"
            "使用简洁的“动作+必要目标”文案，例如将“一键导航去公司”改为“导航去公司”；"
            "完整保留onClick的call、args、动作目标、图标、组件、父布局和唯一Action，"
            "不得复制、删除、改目标或虚构第二个Action。"
        )
    secondary_body_count = re.search(
        r"secondarybody\.items requires 1 to 6 entries \(got (\d+)\)",
        messages,
    )
    if secondary_body_count is not None and int(secondary_body_count.group(1)) > 6:
        return (
            f"{base_instruction} SecondaryBody.items 超过6项，优先删除重复、与需求无关或"
            "已接受Plan未要求的可选补充项，整理为1–6项；保留剩余项的标签、完整值、单位和绑定。"
            "不得按数组顺序直接截掉末尾项，也不得仅为满足项数删除Plan要求的must/should事实；"
            "删除这些事实仍需现有Drop授权，否则保留事实并重选合法组件组合。"
            "整理后按实际行数重新核算固定字号、行高和父区容量，不为6项放宽布局预算。"
        )
    if _contains_marker(messages, _INFO_BLOCK_PROGRESS_VALUE_MARKERS):
        return (
            f"{base_instruction} InfoBlock 的 progressCircle 数值错误时，保留 visual、icon、"
            "fillColor 及其它合法属性；primaryText 只绑定同一 0–100 number/integer 字段的"
            '原始 PathBinding 或合法数值，百分号单独写为 unit:"%"。不得把业务标签或百分号'
            "拼入 primaryText，也不得删除 visual 来消除错误。"
        )
    if _contains_marker(messages, _SECONDARY_BODY_DYNAMIC_LABEL_MARKERS):
        return (
            f"{base_instruction} SecondaryBody.items[].label 只能保留原本就是静态文字的标签；"
            "动态 label 必须与同项现有 value 按原显示顺序合并为一个完整的 items[].value "
            "Expression，并保留全部原始绑定。不得把动态内容静态化、删除或改写为样例值。"
        )
    if _contains_marker(messages, _SECONDARY_BODY_FONT_SIZE_MARKERS):
        return (
            f"{base_instruction} SecondaryBody.fontSize 不是自由字号：保持当前合法的 items、"
            "columns、maxLines、绑定和事实不变，只把 fontSize 改为错误信息给出的固定 Recipe 值。"
            "整组只有一行且各项 maxLines 都为 1（默认 1）时，固定为 14fp/14vp；"
            "超过一行或任一项 maxLines 为 2 时，整组固定为 12fp/12vp，行间距为 2vp。"
            "两项同行用 14；两项 columns:1 分行用 12，不能只按项目数判断。"
            "若其它错误授权调整 items、columns 或 maxLines，合组完成后按最终行布局重新核算"
            "字号与高度；不得仅为缩小字号拆散信息组或删除事实。"
        )
    return base_instruction


def _issue_category(quality_errors: list[dict[str, Any]]) -> str:
    if _has_duplicate_actions(quality_errors):
        return "plan_coverage"
    codes = {str(issue.get("code") or "") for issue in quality_errors}
    messages = "\n".join(str(issue.get("message") or "").lower() for issue in quality_errors)
    for issue in quality_errors:
        diagnostics = issue.get("compactDiagnostics", [])
        if not isinstance(diagnostics, list):
            continue
        for diagnostic in diagnostics:
            if isinstance(diagnostic, dict):
                code = diagnostic.get("code")
                if isinstance(code, str):
                    codes.add(code)
    # 根布局尚未匹配正式骨架时，容量超限通常只是非法拓扑的派生结果。
    # 先重建父布局，避免把整卡结构问题误路由为局部高度微调。
    if codes & _TREE_STRUCTURE_CODES or _contains_marker(messages, _ROOT_STRUCTURE_MARKERS):
        return "layout_structure"
    if re.search(r"component [^\n]*\.children references [^\n]* more than once", messages):
        return "layout_structure"
    if codes & _LAYOUT_CAPACITY_CODES:
        return "layout_capacity"
    if _contains_marker(messages, _CAPACITY_MARKERS):
        return "layout_capacity"
    if _contains_marker(messages, _STRUCTURE_MARKERS):
        return "layout_structure"
    if "COMPACT_PLAN_COVERAGE_FAILED" in codes:
        return "plan_coverage"
    if "ARTIFACT_VALIDATION_FAILED" in codes:
        return "artifact_validation"
    return "component_contract"


def _is_semantic_layout_contract_failure(
    quality_errors: list[dict[str, Any]],
) -> bool:
    """识别已经给出精确父节点合同的语义布局错误。"""
    messages = [str(issue.get("message") or "") for issue in quality_errors]
    has_missing_reference = any("引用了不存在的组件" in message for message in messages)
    return not has_missing_reference and any(
        "语义布局不符合合同" in message for message in messages
    )


def _semantic_layout_contract_directive(
    *,
    fingerprint: str,
    consecutive_failures: int,
    category_attempt: int,
    no_progress: bool,
) -> CompactRepairDirective:
    """先按错误消息修正直属角色，避免过早重写整卡。"""
    instruction = (
        "只修复错误消息定位的 Layout、Region 或 Group 节点：严格按消息给出的合同调整该节点"
        "直属 children 的数量、顺序和角色，并补齐或替换错误角色。Group 整体只占一个直属角色；"
        "title-count 只占标题角色；title-content-action 的动作角色必须使用 PillButton；"
        "W-content-side-slots 的固定动作槽使用 CardButton。保持其它区域、事实、绑定、Action 及"
        "已经合法的 layout/variant 不变，不修改语义展开后的 Row/Column 几何。"
    )
    if consecutive_failures >= 2 or no_progress:
        instruction += (
            " 上一轮没有执行这项合同修复；本轮必须实际改变报错节点的直属 children 或 variant，"
            "逐项对照错误消息闭合角色，不得原样返回上一轮 DSL，也不得改写无关区域。"
        )
    return CompactRepairDirective(
        category="layout_structure",
        scope="parent_layout",
        repair_strategy="semantic_layout_contract_repair",
        retry_target="dsl_local_repair",
        fingerprint=fingerprint,
        consecutive_failures=consecutive_failures,
        category_attempt=category_attempt,
        no_progress=no_progress,
        retryable=True,
        instruction=instruction,
    )


def _semantic_layout_parent_directive(
    *,
    fingerprint: str,
    consecutive_failures: int,
    category_attempt: int,
    no_progress: bool,
) -> CompactRepairDirective:
    """两次精确合同修复仍失败时，仅重组共同父布局。"""
    return CompactRepairDirective(
        category="layout_structure",
        scope="parent_layout",
        repair_strategy="parent_layout_recompose",
        retry_target="dsl_recompose",
        fingerprint=fingerprint,
        consecutive_failures=consecutive_failures,
        category_attempt=category_attempt,
        no_progress=no_progress,
        retryable=True,
        instruction=(
            "同一语义布局合同已经两次未闭合；停止重复局部改名或原样返回，重组报错节点及其共同"
            "父布局，重新选择一个完整合法的 Layout/Region/Group 变体并一次补齐全部直属角色。"
            "保留父区外正确内容、全部事实、绑定和 Action；本轮仍不重写整份 DSL。"
        ),
    )


def compact_repair_issue_category(quality_errors: list[dict[str, Any]]) -> str:
    """返回稳定的修复问题分类，供接口级恢复判定复用。"""
    return _issue_category(quality_errors)


def compact_capacity_recovery_failure_category(
    quality_errors: list[dict[str, Any]],
    *,
    layout_failure_seen: bool,
) -> str | None:
    """判断接口重试是否应按前序布局失败进入容量恢复。"""
    errors = [issue for issue in quality_errors if issue.get("severity") != "warning"]
    category = _issue_category(errors)
    protected_failure = _has_duplicate_plan_facts(errors)
    for issue in errors:
        message = str(issue.get("message") or "").strip().lower()
        if message.startswith("plan action is missing from visible dsl:"):
            protected_failure = True
            break
    result: str | None = None
    if errors and not protected_failure:
        if category in {"layout_capacity", "layout_structure"}:
            result = category
        elif layout_failure_seen:
            for issue in quality_errors:
                code = str(issue.get("code") or "")
                message = str(issue.get("message") or "").strip().lower()
                if code == "COMPACT_PLAN_FACT_OMITTED":
                    result = "layout_capacity"
                    break
                if category == "plan_coverage" and message.startswith(
                    "plan fact is missing from visible dsl:",
                ):
                    result = "layout_capacity"
                    break
    return result


def _joint_repair_relevant(category: str, quality_errors: list[dict[str, Any]]) -> bool:
    if category in {"layout_capacity", "layout_structure", "plan_coverage"}:
        return True
    for issue in quality_errors:
        message = str(issue.get("message") or "").lower()
        if _contains_marker(message, ("plan-assigned", "assetassignments action")):
            return True
    return False


def _layout_directive(
    *,
    category: str,
    fingerprint: str,
    consecutive_failures: int,
    category_attempt: int,
    no_progress: bool,
    prefer_split_panels: bool = False,
    force_parent_layout: bool = False,
    allow_text_compaction: bool = False,
    offer_anchor_action_migration: bool = False,
) -> CompactRepairDirective:
    split_panels_instruction = ""
    if prefer_split_panels:
        split_panels_instruction = (
            " 当前 W-content-side-slots 固定侧槽无法容纳该完整信息组；"
            "不要继续把多个字段拼入 InfoBlock 单行。若内容可分成两个完整信息组，"
            "优先比较并改用 W-split-panels，在两个 Region 内使用合法多行组件承载；"
            "若左右分区容量仍不成立，再选择其它合法父布局。保留全部事实和 Action。"
        )
    repeated_root_cause = consecutive_failures >= 2 or no_progress
    if repeated_root_cause:
        scope = "full_dsl"
        strategy = "plan_guided_recompose"
        instruction = (
            "同一布局根因已经重复或上一轮 DSL 没有变化；放弃上一轮 Compact DSL 的旧拓扑，"
            "从已接受 Plan 的全部硬事实和动作重新构造完整 DSL。"
            f"{split_panels_instruction}"
        )
    elif force_parent_layout:
        scope = "parent_layout"
        strategy = "parent_layout_recompose"
        instruction = (
            "多个语义分区同时容量超限，或当前仍缺失事实、补回后容量还会增加；"
            "跳过局部高度微调，先恢复缺失事实，再按全部信息组和 Action 重新选择父布局。"
            "保留固定字号与设计尺寸，不裁切、缩字、隐藏或删除事实。"
        )
    elif prefer_split_panels:
        scope = "parent_layout"
        strategy = "parent_layout_recompose"
        instruction = (
            "固定侧槽宽度无法通过局部换行或修改 Props 闭合；重新分配完整信息组和动作槽。"
            f"{split_panels_instruction}"
        )
    elif category_attempt == 1:
        scope = "parent_layout" if category == "layout_structure" else "sublayout"
        strategy = "parent_layout_recompose" if scope == "parent_layout" else "rebudget"
        instruction = (
            "修复违反合同的父布局结构，重新分配完整信息组和动作槽。"
            if scope == "parent_layout"
            else "重算受影响信息组的完整高度与间距，改用能闭合的合法子布局组合。"
        )
    elif category_attempt == 2:
        scope = "parent_layout"
        strategy = "parent_layout_recompose"
        instruction = "前一轮布局修复没有闭合；停止修改局部几何，重新选择父布局变体并分配全部事实。"
    else:
        scope = "full_dsl"
        strategy = "plan_guided_recompose"
        instruction = (
            "局部与父布局修复均未解决根因；放弃上一轮 Compact DSL 的旧拓扑，"
            "从已接受 Plan 的全部硬事实和动作重新构造完整 DSL。"
        )
    if category == "layout_structure":
        instruction += _TREE_RECOMPOSE_INSTRUCTION
    if category == "layout_capacity" and allow_text_compaction:
        instruction += _CAPACITY_TEXT_COMPACTION_INSTRUCTION
    if category == "layout_capacity" and offer_anchor_action_migration:
        instruction += _PILL_ACTION_ANCHOR_MIGRATION_INSTRUCTION
    return CompactRepairDirective(
        category=category,
        scope=scope,
        repair_strategy=strategy,
        retry_target="dsl_recompose",
        fingerprint=fingerprint,
        consecutive_failures=consecutive_failures,
        category_attempt=category_attempt,
        no_progress=no_progress,
        retryable=True,
        instruction=instruction,
    )


def _non_layout_directive(
    *,
    category: str,
    quality_errors: list[dict[str, Any]],
    fingerprint: str,
    consecutive_failures: int,
    category_attempt: int,
    no_progress: bool,
    force_targeted: bool = False,
    duplicate_count_not_reduced: bool = False,
) -> CompactRepairDirective:
    repeated_root_cause = consecutive_failures >= 2 or no_progress
    duplicate_plan_facts = category == "plan_coverage" and _has_duplicate_plan_facts(quality_errors)
    duplicate_actions = _has_duplicate_actions(quality_errors)
    if duplicate_plan_facts and duplicate_actions:
        fixed_slots = _has_duplicate_required_slot_conflict(quality_errors)
        scope = "parent_layout" if fixed_slots else "information_group"
        strategy = "parent_layout_recompose" if fixed_slots else "deduplicate_visible_actions"
        retry_target = "dsl_recompose" if fixed_slots else "dsl_local_repair"
        instruction = _duplicate_action_instruction(
            duplicate_count_not_reduced=duplicate_count_not_reduced,
        )
        if any(issue.get("duplicateFacts") for issue in quality_errors):
            instruction += _duplicate_fact_instruction(
                duplicate_count_not_reduced=duplicate_count_not_reduced,
            )
    elif duplicate_plan_facts and _has_duplicate_required_slot_conflict(quality_errors):
        scope = "parent_layout"
        strategy = "parent_layout_recompose"
        retry_target = "dsl_recompose"
        instruction = _duplicate_required_slot_instruction()
    elif duplicate_plan_facts:
        scope = "information_group"
        strategy = "deduplicate_visible_facts"
        retry_target = "dsl_local_repair"
        instruction = _duplicate_fact_instruction(
            duplicate_count_not_reduced=duplicate_count_not_reduced,
        )
    elif force_targeted:
        scope = "information_group" if category == "plan_coverage" else "component"
        strategy = (
            "coverage_restore" if category == "plan_coverage" else "component_contract_repair"
        )
        retry_target = "dsl_local_repair"
        instruction = (
            "恢复缺失的 Plan 必须事实并复查其所属信息组，不删除其它已正确事实。"
            if category == "plan_coverage"
            else _component_contract_instruction(quality_errors)
        )
    elif repeated_root_cause:
        scope = "full_dsl"
        strategy = "plan_guided_recompose"
        retry_target = "dsl_recompose"
        instruction = (
            "同一局部错误已经重复或上一轮 DSL 没有变化；从已接受 Plan "
            "的全部硬事实和动作重建完整 DSL，不再修补原组件结构。"
        )
    elif category_attempt > 1:
        scope = "parent_layout"
        strategy = "parent_layout_recompose"
        retry_target = "dsl_recompose"
        instruction = (
            "局部修复没有消除错误；保留全部事实与动作，重新组织受影响组件及其父布局，"
            "不要再次提交相同组件结构。"
        )
    else:
        scope = "information_group" if category == "plan_coverage" else "component"
        strategy = (
            "coverage_restore" if category == "plan_coverage" else "component_contract_repair"
        )
        retry_target = "dsl_local_repair"
        instruction = (
            "恢复缺失的 Plan 必须事实并复查其所属信息组，不删除其它已正确事实。"
            if category == "plan_coverage"
            else _component_contract_instruction(quality_errors)
        )
    return CompactRepairDirective(
        category=category,
        scope=scope,
        repair_strategy=strategy,
        retry_target=retry_target,
        fingerprint=fingerprint,
        consecutive_failures=consecutive_failures,
        category_attempt=category_attempt,
        no_progress=no_progress,
        retryable=True,
        instruction=instruction,
    )


def _exhausted_directive(
    *,
    category: str,
    fingerprint: str,
    consecutive_failures: int,
    category_attempt: int,
    no_progress: bool,
    fallback_stage: str | None = None,
    fallback_attempt: int | None = None,
    fallback_attempt_limit: int | None = None,
) -> CompactRepairDirective:
    return CompactRepairDirective(
        category=category,
        scope="full_dsl",
        repair_strategy="exhausted",
        retry_target="stop",
        fingerprint=fingerprint,
        consecutive_failures=consecutive_failures,
        category_attempt=category_attempt,
        no_progress=no_progress,
        retryable=False,
        instruction=(
            "本次请求已经达到全局最大修复次数；停止调用模型，保留当前诊断并按校验失败处理。"
        ),
        fallback_stage=fallback_stage,
        fallback_attempt=fallback_attempt,
        fallback_attempt_limit=fallback_attempt_limit,
        fallback_remaining_attempts=(0 if fallback_stage is not None else None),
        stop_reason="global_attempt_limit",
    )


def _full_dsl_transition_directive(
    *,
    category: str,
    fingerprint: str,
    consecutive_failures: int,
    category_attempt: int,
    no_progress: bool,
    instruction: str,
    fallback_stage: str | None = None,
    fallback_attempt: int | None = None,
    fallback_attempt_limit: int | None = None,
) -> CompactRepairDirective:
    """局部阶段达到迁移阈值后回到完整 DSL 重组，而不是提前停止。"""
    remaining_attempts = None
    if fallback_attempt is not None and fallback_attempt_limit is not None:
        remaining_attempts = max(0, fallback_attempt_limit - fallback_attempt)
    return CompactRepairDirective(
        category=category,
        scope="full_dsl",
        repair_strategy="plan_guided_recompose",
        retry_target="dsl_recompose",
        fingerprint=fingerprint,
        consecutive_failures=consecutive_failures,
        category_attempt=category_attempt,
        no_progress=no_progress,
        retryable=True,
        instruction=instruction,
        fallback_stage=fallback_stage,
        fallback_attempt=fallback_attempt,
        fallback_attempt_limit=fallback_attempt_limit,
        fallback_remaining_attempts=remaining_attempts,
    )


def _compact_component_fallback_directive(
    *,
    category: str,
    fingerprint: str,
    consecutive_failures: int,
    category_attempt: int,
    no_progress: bool,
    fallback_attempt: int,
    allow_text_compaction: bool,
) -> CompactRepairDirective:
    """进入 claw-widget 同义的无损紧凑组件兜底阶段。"""
    remaining_attempts = COMPACT_COMPONENT_FALLBACK_MAX_ATTEMPTS - fallback_attempt
    instruction = (
        "正常布局修复与完整 DSL 重组仍未闭合；进入 compact_component "
        "无损紧凑组件替换阶段。按修复合同改用语义兼容且占位更小的已登记组件、"
        "合并同对象辅助信息，并在当前尺寸合法布局内重新分配；必须保留全部事实、"
        "动态绑定和 Action，不得删除、静态化、缩字、裁切或隐藏内容。"
    )
    if allow_text_compaction:
        instruction += _CAPACITY_TEXT_COMPACTION_INSTRUCTION
    return CompactRepairDirective(
        category=category,
        scope="full_dsl",
        repair_strategy="compact_component",
        retry_target="dsl_recompose",
        fingerprint=fingerprint,
        consecutive_failures=consecutive_failures,
        category_attempt=category_attempt,
        no_progress=no_progress,
        retryable=True,
        instruction=instruction,
        fallback_stage="compact_component",
        fallback_attempt=fallback_attempt,
        fallback_attempt_limit=COMPACT_COMPONENT_FALLBACK_MAX_ATTEMPTS,
        fallback_remaining_attempts=remaining_attempts,
    )


def _drop_optional_component_fallback_directive(
    *,
    category: str,
    fingerprint: str,
    consecutive_failures: int,
    category_attempt: int,
    no_progress: bool,
    fallback_attempt: int,
    fallback_attempt_limit: int,
    candidate: CompactOptionalDropCandidate,
) -> CompactRepairDirective:
    """删除一个由程序确定的非 Action 组件，不授权第二次删减。"""
    remaining_attempts = fallback_attempt_limit - fallback_attempt
    requirements = "、".join(candidate.requirements)
    if no_progress and fallback_attempt > 0:
        instruction = (
            "上一轮没有执行 Drop：输出 DSL 与上一轮完全相同。本轮必须删除 "
            f"optionalDrop.componentId 指定的 {candidate.component_id} "
            f"({candidate.component_type}) 组件行，并从直接父组件 children 中移除该 ID；"
            "如果该组件已经删除，则保持删除状态，使用剩余组件重新闭合当前布局。"
            "不得删除其他组件、未授权的 must/should 事实或任何 Action；"
            "必须输出完整 Compact DSL，禁止原样返回上一轮 Compact DSL。"
        )
    else:
        instruction = (
            "已进入有界删除兜底。只允许删除程序指定的一个非 Action 业务展示组件："
            f"{candidate.component_id} ({candidate.component_type})，对应信息：{requirements}。"
            "必须同时从直接父组件 children 中移除该组件 ID，并重排其余全部 must/should "
            "事实与 Action；本轮不得删除任何其他组件、"
            "改变动态绑定、缩字、裁切或隐藏内容。"
        )
    if candidate.partial:
        if candidate.component_type == "SecondaryBody":
            instruction = (
                "已进入条目级最小删减兜底。仅允许从 optionalDrop.componentId 指定的 "
                f"SecondaryBody.items 删除 allowedItemIndexes={candidate.item_indexes!r} "
                "对应且仍承载 allowedOmittedFactIndexes 的 doesNotFit 条目；保留该组件的"
                "其余 items、顺序、绑定、字号和父级引用。仅当删除后 items 为空时才删除"
                "组件行及其直接父级引用。不得删除其它组件、未授权事实或任何 Action；"
                "整卡必须继续保留至少一个核心信息组件。"
            )
        elif candidate.component_type == "TableText":
            instruction = (
                "已进入 TableText 条目级最小删减兜底。当前表格超过三项合同上限，或三行表格"
                "在目标布局中容量失败；"
                "仅允许从 optionalDrop.componentId 指定的 TableText.items 删除 "
                f"allowedItemIndexes={candidate.item_indexes!r} 对应且仍承载 "
                "allowedOmittedFactIndexes 的一行。若删除后仍超过三项，等待程序下一轮继续"
                "授权；保留其余行的顺序、绑定、字号和父级引用，不得删除整个 TableText、"
                "其它组件、未授权事实或任何 Action。"
            )
        else:
            priority = "must" if candidate.contains_must_facts else "should"
            instruction = (
                "已进入静态最小删减兜底。仅允许省略 allowedOmittedFactIndexes "
                f"对应且由程序批准的{priority}文字：{candidate.display_texts!r}。"
                "只修改其所在条目或字段；不得删除保护原文或任何未授权事实的整组件、"
                "整条目、整组。"
                "仅当条目或组已无剩余事实时才移除空条目或组，并重排余下内容。"
                "保留全部Action、至少一个正文对象、对象归属和未授权事实；"
                "不改写Plan、缩字、截断或隐藏。"
            )
    if candidate.requires_core_reattach:
        instruction += (
            " 当前 DSL 的核心信息组件只是暂时未挂到 root，并非不存在。"
            "本轮必须把 protectedCoreComponentIds 中至少一个组件重新挂到 root 可达的"
            "合法 Region/Group 内容角色；保留这些核心组件承载的事实，不得把它们作为"
            "Drop 对象或用标题、按钮、SecondaryBody替代。"
        )
    return CompactRepairDirective(
        category=category,
        scope="full_dsl",
        repair_strategy="drop_optional_component",
        retry_target="dsl_recompose",
        fingerprint=fingerprint,
        consecutive_failures=consecutive_failures,
        category_attempt=category_attempt,
        no_progress=no_progress,
        retryable=True,
        instruction=instruction,
        fallback_stage="drop_optional_component",
        fallback_attempt=fallback_attempt,
        fallback_attempt_limit=fallback_attempt_limit,
        fallback_remaining_attempts=remaining_attempts,
        optional_drop=candidate,
    )


def _drop_candidate_is_fully_removed(
    compact_dsl: str,
    candidate: CompactOptionalDropCandidate,
) -> bool:
    """候选行及全部父级引用均消失后，才允许选择下一个候选。"""
    if candidate.partial:
        if candidate.component_type in {"SecondaryBody", "TableText"}:
            try:
                rows = parse_compact_dsl_rows(
                    compact_dsl,
                    expand_layouts=False,
                    skip_compact_dsl_validation=candidate.component_type == "TableText",
                )
            except (CompactDslConversionError, TypeError, ValueError):
                return False
            for row in rows:
                if not isinstance(row, ComponentRow):
                    continue
                if row.component_id != candidate.component_id:
                    continue
                items = row.props.get("items")
                if not isinstance(items, list):
                    return False
                signatures = {
                    json.dumps(
                        item,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    for item in items
                }
                return not any(
                    signature in signatures for signature in candidate.item_signatures
                )
            return True
        from services.card_validation.compact_validation.semantic.static_content import (
            display_text,
            static_display_groups,
        )

        try:
            objects, shared = static_display_groups(compact_dsl)
        except (TypeError, ValueError):
            return False
        for group in objects + shared:
            if group.component_id != candidate.component_id:
                continue
            visible = display_text("".join(group.parts))
            if any(display_text(text) in visible for text in candidate.display_texts):
                return False
        return True
    try:
        rows = parse_compact_dsl_rows(compact_dsl)
    except (CompactDslConversionError, TypeError, ValueError):
        return False
    components = [row for row in rows if isinstance(row, ComponentRow)]
    if any(row.component_id == candidate.component_id for row in components):
        return False
    return not any(candidate.component_id in row.children for row in components)


def _protected_core_is_reattached(
    compact_dsl: str,
    candidate: CompactOptionalDropCandidate,
) -> bool:
    """核心暂时不可达时，Drop 只有在至少恢复一个保护节点后才算执行完成。"""
    if not candidate.requires_core_reattach:
        return True
    try:
        rows = parse_compact_dsl_rows(
            compact_dsl,
            expand_layouts=False,
            preserve_unreachable=True,
        )
    except (CompactDslConversionError, TypeError, ValueError):
        return False
    components = {
        row.component_id: row for row in rows if isinstance(row, ComponentRow)
    }
    pending = ["root"]
    reachable: set[str] = set()
    while pending:
        component_id = pending.pop()
        if component_id in reachable:
            continue
        component = components.get(component_id)
        if component is None:
            continue
        reachable.add(component_id)
        pending.extend(component.children)
    return any(
        component_id in reachable
        for component_id in candidate.protected_core_component_ids
    )


class CompactRepairStrategyTracker:
    """在单次生成请求内跟踪失败指纹并选择下一轮修复范围。"""

    def __init__(
        self,
        *,
        max_repair_attempts: int = 10,
        capacity_recovery: bool = False,
        static_content: bool = False,
    ) -> None:
        if max_repair_attempts < 1:
            raise ValueError("max_repair_attempts must be at least 1")
        self._max_repair_attempts = max_repair_attempts
        self._capacity_recovery = capacity_recovery
        self._static_content = static_content
        self._repair_submission_count = 0
        self._previous_fingerprint: str | None = None
        self._previous_source: str | None = None
        self._consecutive_failures = 0
        self._category_attempts: dict[str, int] = {}
        self._previous_strategy: str | None = None
        self._active_fallback: str | None = None
        self._fallback_submission_count = 0
        self._fallback_submission_limit = 0
        self._optional_drop_candidate: CompactOptionalDropCandidate | None = None
        self._allowed_omitted_fact_indexes: list[int] = []
        self._joint_categories: list[str] = []
        self._failed_topologies: set[str] = set()
        self._layout_failure_seen = False
        self._plan_coverage_repair_submission_count = 0
        self._joint_full_recompose_seen = False
        self._capacity_pressure_repair_submitted = False
        self._latest_capacity_fits: list[dict[str, Any]] = []
        self._capacity_overflow_limit: int | None = None
        self._capacity_overflow_fact_indexes: set[int] = set()
        self._previous_duplicate_excess_count: int | None = None

    @property
    def allowed_omitted_fact_indexes(self) -> tuple[int, ...]:
        """暴露各轮由程序明确批准删除的非 Action 事实。"""
        if self._active_fallback != "drop_optional_component":
            return ()
        return tuple(sorted(self._allowed_omitted_fact_indexes))

    @property
    def layout_failure_seen(self) -> bool:
        """当前完整生成内是否已出现布局容量或结构失败。"""
        return self._layout_failure_seen

    @property
    def drop_active(self) -> bool:
        """当前是否已进入程序授权的 Drop 阶段。"""
        return self._active_fallback == "drop_optional_component"

    def validation_omitted_fact_indexes(
        self,
        compact_plan: dict[str, Any] | None,
        *,
        validate_drop_plan_facts: bool,
    ) -> tuple[int, ...]:
        """Drop 只豁免程序明确批准的非 Action 事实。"""
        explicitly_allowed = self.allowed_omitted_fact_indexes
        return explicitly_allowed

    @property
    def optional_drop_candidate(self) -> CompactOptionalDropCandidate | None:
        """返回当前 Drop 轮次唯一允许删除的组件。"""
        return self._optional_drop_candidate

    def _select_drop_candidate(
        self,
        compact_dsl: str,
        compact_plan: dict[str, Any] | None,
        task_spec: dict[str, Any],
        *,
        allow_must_fallback: bool = True,
        max_fact_count: int | None = None,
        allowed_fact_indexes: set[int] | None = None,
        allow_invalid_table_text: bool = False,
    ) -> CompactOptionalDropCandidate | None:
        """从当前仍可见内容中选择下一轮唯一候选并累计省略授权。"""
        candidate = compact_plan_optional_drop_candidate(
            compact_dsl,
            compact_plan,
            task_spec,
            allow_must_fallback=allow_must_fallback,
            max_fact_count=max_fact_count,
            allowed_fact_indexes=allowed_fact_indexes,
            allow_invalid_table_text=allow_invalid_table_text,
        )
        if candidate is None:
            return None
        self._optional_drop_candidate = candidate
        for fact_index in candidate.fact_indexes:
            if fact_index not in self._allowed_omitted_fact_indexes:
                self._allowed_omitted_fact_indexes.append(fact_index)
        return candidate

    def next_directive(
        self,
        invalid_source_dsl: str,
        quality_errors: list[dict[str, Any]],
        *,
        compact_plan: dict[str, Any] | None = None,
        task_spec: dict[str, Any] | None = None,
    ) -> CompactRepairDirective:
        """根据当前失败和请求内历史选择局部修复或结构重组。"""
        category = _issue_category(quality_errors)
        duplicate_excess_count = _duplicate_plan_fact_excess_count(quality_errors)
        duplicate_count_not_reduced = False
        if duplicate_excess_count is not None:
            previous_count = self._previous_duplicate_excess_count
            duplicate_count_not_reduced = (
                previous_count is not None and duplicate_excess_count >= previous_count
            )
        self._previous_duplicate_excess_count = duplicate_excess_count
        capacity_fits = _capacity_fits_from_issues(quality_errors)
        if not capacity_fits:
            capacity_fits = bounded_component_capacity_contexts(
                invalid_source_dsl,
                quality_errors,
                compact_plan,
            )
        if capacity_fits and not _has_duplicate_actions(quality_errors):
            category = "layout_capacity"
            self._latest_capacity_fits = copy.deepcopy(capacity_fits)
            overflow_limit = _capacity_overflow_limit(capacity_fits)
            if overflow_limit is not None:
                self._capacity_overflow_limit = overflow_limit
            self._capacity_overflow_fact_indexes = _capacity_overflow_fact_indexes(capacity_fits)
        duplicate_plan_coverage = (
            category == "plan_coverage" and _has_duplicate_plan_facts(quality_errors)
        )
        duplicate_required_slot_conflict = (
            duplicate_plan_coverage and _has_duplicate_required_slot_conflict(quality_errors)
        )
        previous_category = self._joint_categories[-1] if self._joint_categories else None
        previous_layout_failure = self._layout_failure_seen
        has_plan_coverage_error = _has_missing_plan_fact_error(quality_errors)
        if not has_plan_coverage_error:
            self._plan_coverage_repair_submission_count = 0
        relevant = _joint_repair_relevant(category, quality_errors)
        topology = repair_topology_fingerprint(invalid_source_dsl) if relevant else None
        revisited_topology = topology is not None and topology in self._failed_topologies
        if relevant:
            self._joint_categories.append(category)
            if topology is not None:
                self._failed_topologies.add(topology)
        if category in {"layout_capacity", "layout_structure"}:
            self._layout_failure_seen = True
        fingerprint = _issue_fingerprint(quality_errors)
        if fingerprint == self._previous_fingerprint:
            self._consecutive_failures += 1
        else:
            self._consecutive_failures = 1
        normalized_source = invalid_source_dsl.strip()
        no_progress = (
            self._previous_source is not None and normalized_source == self._previous_source
        )
        category_attempt = self._category_attempts.get(category, 0) + 1
        self._category_attempts[category] = category_attempt
        self._previous_fingerprint = fingerprint
        self._previous_source = normalized_source
        changed_constraint = previous_category is not None and category != previous_category
        persistent_capacity = category == "layout_capacity" and category_attempt >= 2
        joint_progress_failed = changed_constraint or revisited_topology or persistent_capacity
        joint_inputs_available = compact_plan is not None and task_spec is not None
        joint_recompose = joint_inputs_available and previous_layout_failure and relevant
        joint_recompose = joint_recompose and joint_progress_failed
        joint_recompose = joint_recompose and not duplicate_plan_coverage
        joint_recompose = joint_recompose and not self._joint_full_recompose_seen
        full_recompose_seen = self._previous_strategy == "plan_guided_recompose"
        full_recompose_seen = full_recompose_seen or (
            joint_inputs_available and self._joint_full_recompose_seen
        )

        if self._repair_submission_count >= self._max_repair_attempts:
            directive = _exhausted_directive(
                category=category,
                fingerprint=fingerprint,
                consecutive_failures=self._consecutive_failures,
                category_attempt=category_attempt,
                no_progress=no_progress,
                fallback_stage=self._active_fallback,
                fallback_attempt=self._fallback_submission_count,
                fallback_attempt_limit=(
                    self._fallback_submission_limit
                    if self._active_fallback == "drop_optional_component"
                    else COMPACT_COMPONENT_FALLBACK_MAX_ATTEMPTS
                    if self._active_fallback == "compact_component"
                    else None
                ),
            )
            if duplicate_required_slot_conflict:
                directive = replace(directive, scope="parent_layout")
            elif _has_duplicate_actions(quality_errors):
                directive = replace(directive, scope="information_group")
            if self._allowed_omitted_fact_indexes:
                directive = replace(
                    directive,
                    approved_omitted_fact_indexes=tuple(sorted(self._allowed_omitted_fact_indexes)),
                )
            self._previous_strategy = directive.repair_strategy
            return directive

        repeated_root_cause = self._consecutive_failures >= 2 or no_progress
        is_layout_failure = category in {"layout_capacity", "layout_structure"}
        is_semantic_layout_contract_failure = _is_semantic_layout_contract_failure(
            quality_errors,
        )
        semantic_layout_guidance = semantic_layout_repair_guidance(
            invalid_source_dsl,
            quality_errors,
            compact_plan,
        )
        persistent_plan_coverage_followup = (
            has_plan_coverage_error
            and self._plan_coverage_repair_submission_count
            >= PLAN_COVERAGE_EARLY_DROP_MIN_REPAIR_ATTEMPTS
        )
        capacity_regroup_contract_failure = _capacity_regroup_contract_failure(
            quality_errors,
        )
        table_text_item_overflow = _table_text_item_overflow_failure(
            invalid_source_dsl,
            quality_errors,
        )
        bounded_capacity_followup = (
            self._capacity_pressure_repair_submitted
            and self._repair_submission_count > 0
            and (is_layout_failure or capacity_regroup_contract_failure)
        )
        early_drop_due = persistent_plan_coverage_followup or bounded_capacity_followup
        allow_text_compaction = _capacity_text_compaction_relevant(
            invalid_source_dsl,
        )
        recovery_drop_due = self._capacity_recovery and self._repair_submission_count == 0
        drop_entry_due = (
            table_text_item_overflow
            or early_drop_due
            or recovery_drop_due
            or (
                self._repair_submission_count >= DROP_OPTIONAL_COMPONENT_MIN_REPAIR_ATTEMPT - 1
                and self._active_fallback != "drop_optional_component"
            )
        )
        drop_relevant_failure = (
            table_text_item_overflow
            or is_layout_failure
            or persistent_plan_coverage_followup
            or bounded_capacity_followup
        )
        drop_entry_due = drop_entry_due and not _has_duplicate_actions(quality_errors)
        if drop_entry_due and drop_relevant_failure and task_spec is not None:
            max_fact_count = self._capacity_overflow_limit if early_drop_due else None
            allowed_fact_indexes = None
            recovery_item_drop = recovery_drop_due and bool(
                self._capacity_overflow_fact_indexes
            )
            if bounded_capacity_followup or recovery_item_drop:
                allowed_fact_indexes = self._capacity_overflow_fact_indexes
            candidate = self._select_drop_candidate(
                invalid_source_dsl,
                compact_plan,
                task_spec,
                max_fact_count=max_fact_count,
                allowed_fact_indexes=allowed_fact_indexes,
                allow_invalid_table_text=table_text_item_overflow,
            )
            if candidate is not None:
                self._active_fallback = "drop_optional_component"
                self._fallback_submission_count = 0
                self._fallback_submission_limit = (
                    self._max_repair_attempts - self._repair_submission_count
                )
        if duplicate_required_slot_conflict or _has_duplicate_actions(quality_errors):
            directive = _non_layout_directive(
                category=category,
                quality_errors=quality_errors,
                fingerprint=fingerprint,
                consecutive_failures=self._consecutive_failures,
                category_attempt=category_attempt,
                no_progress=no_progress,
                duplicate_count_not_reduced=duplicate_count_not_reduced,
            )
        elif self._active_fallback == "drop_optional_component":
            if self._optional_drop_candidate is None:
                raise RuntimeError("optional drop fallback has no selected candidate")
            candidate_was_removed = _drop_candidate_is_fully_removed(
                invalid_source_dsl,
                self._optional_drop_candidate,
            )
            candidate_was_removed = (
                candidate_was_removed
                and _protected_core_is_reattached(
                    invalid_source_dsl,
                    self._optional_drop_candidate,
                )
            )
            if candidate_was_removed and not drop_relevant_failure:
                directive = _non_layout_directive(
                    category=category,
                    quality_errors=quality_errors,
                    fingerprint=fingerprint,
                    consecutive_failures=self._consecutive_failures,
                    category_attempt=category_attempt,
                    no_progress=no_progress,
                    force_targeted=True,
                    duplicate_count_not_reduced=duplicate_count_not_reduced,
                )
            elif candidate_was_removed:
                candidate = None
                if task_spec is not None:
                    candidate = self._select_drop_candidate(
                        invalid_source_dsl,
                        compact_plan,
                        task_spec,
                        max_fact_count=self._capacity_overflow_limit,
                        allowed_fact_indexes=(
                            self._capacity_overflow_fact_indexes or None
                        ),
                        allow_invalid_table_text=table_text_item_overflow,
                    )
                if candidate is None:
                    directive = _full_dsl_transition_directive(
                        category=category,
                        fingerprint=fingerprint,
                        consecutive_failures=self._consecutive_failures,
                        category_attempt=category_attempt,
                        no_progress=no_progress,
                        fallback_stage=self._active_fallback,
                        fallback_attempt=self._fallback_submission_count,
                        fallback_attempt_limit=self._fallback_submission_limit,
                        instruction=(
                            "当前 Drop 候选已经移除且没有新的合法非 Action 候选；"
                            "保留程序累计批准的省略结果，从已接受 Plan、剩余事实和动作"
                            "重新构造完整 DSL。"
                            "不得恢复已批准删除的组件，不得删除新的未授权事实或任何 Action。"
                        ),
                    )
                else:
                    directive = _drop_optional_component_fallback_directive(
                        category=category,
                        fingerprint=fingerprint,
                        consecutive_failures=self._consecutive_failures,
                        category_attempt=category_attempt,
                        no_progress=no_progress,
                        fallback_attempt=self._fallback_submission_count,
                        fallback_attempt_limit=self._fallback_submission_limit,
                        candidate=candidate,
                    )
                    self._fallback_submission_count += 1
            else:
                directive = _drop_optional_component_fallback_directive(
                    category=category,
                    fingerprint=fingerprint,
                    consecutive_failures=self._consecutive_failures,
                    category_attempt=category_attempt,
                    no_progress=no_progress,
                    fallback_attempt=self._fallback_submission_count,
                    fallback_attempt_limit=self._fallback_submission_limit,
                    candidate=self._optional_drop_candidate,
                )
                self._fallback_submission_count += 1
        elif is_semantic_layout_contract_failure and self._consecutive_failures <= 2:
            directive = _semantic_layout_contract_directive(
                fingerprint=fingerprint,
                consecutive_failures=self._consecutive_failures,
                category_attempt=category_attempt,
                no_progress=no_progress,
            )
        elif (
            is_semantic_layout_contract_failure
            and self._previous_strategy == "semantic_layout_contract_repair"
        ):
            directive = _semantic_layout_parent_directive(
                fingerprint=fingerprint,
                consecutive_failures=self._consecutive_failures,
                category_attempt=category_attempt,
                no_progress=no_progress,
            )
        elif self._active_fallback == "compact_component":
            if not is_layout_failure:
                # 紧凑布局消除布局错误后，持续按新错误类别迁移到定向修复；
                # 后续若重新出现布局错误，再继续 Drop 或完整 DSL 重组。
                directive = _non_layout_directive(
                    category=category,
                    quality_errors=quality_errors,
                    fingerprint=fingerprint,
                    consecutive_failures=self._consecutive_failures,
                    category_attempt=category_attempt,
                    no_progress=no_progress,
                    force_targeted=True,
                    duplicate_count_not_reduced=duplicate_count_not_reduced,
                )
            elif self._fallback_submission_count >= COMPACT_COMPONENT_FALLBACK_MAX_ATTEMPTS:
                candidate = None
                if is_layout_failure and task_spec is not None:
                    candidate = self._select_drop_candidate(
                        invalid_source_dsl,
                        compact_plan,
                        task_spec,
                    )
                if candidate is None:
                    self._active_fallback = None
                    self._fallback_submission_count = 0
                    directive = _full_dsl_transition_directive(
                        category=category,
                        fingerprint=fingerprint,
                        consecutive_failures=self._consecutive_failures,
                        category_attempt=category_attempt,
                        no_progress=no_progress,
                        fallback_stage="compact_component",
                        fallback_attempt=COMPACT_COMPONENT_FALLBACK_MAX_ATTEMPTS,
                        fallback_attempt_limit=COMPACT_COMPONENT_FALLBACK_MAX_ATTEMPTS,
                        instruction=(
                            "无损紧凑组件阶段已达到迁移阈值，但当前没有合法 Drop 候选；"
                            "不要停止修复，改为根据已接受 Plan、完整失败历史和当前合同"
                            "重新构造完整 DSL，"
                            "重新选择合法布局与信息合组，并保留全部事实、绑定和 Action。"
                        ),
                    )
                else:
                    self._active_fallback = "drop_optional_component"
                    self._fallback_submission_count = 0
                    self._fallback_submission_limit = max(
                        0,
                        self._max_repair_attempts - self._repair_submission_count,
                    )
                    directive = _drop_optional_component_fallback_directive(
                        category=category,
                        fingerprint=fingerprint,
                        consecutive_failures=self._consecutive_failures,
                        category_attempt=category_attempt,
                        no_progress=no_progress,
                        fallback_attempt=self._fallback_submission_count,
                        fallback_attempt_limit=self._fallback_submission_limit,
                        candidate=candidate,
                    )
                    self._fallback_submission_count += 1
            else:
                directive = _compact_component_fallback_directive(
                    category=category,
                    fingerprint=fingerprint,
                    consecutive_failures=self._consecutive_failures,
                    category_attempt=category_attempt,
                    no_progress=no_progress,
                    fallback_attempt=self._fallback_submission_count,
                    allow_text_compaction=allow_text_compaction,
                )
                self._fallback_submission_count += 1
        elif is_layout_failure and full_recompose_seen:
            self._active_fallback = "compact_component"
            directive = _compact_component_fallback_directive(
                category=category,
                fingerprint=fingerprint,
                consecutive_failures=self._consecutive_failures,
                category_attempt=category_attempt,
                no_progress=no_progress,
                fallback_attempt=self._fallback_submission_count,
                allow_text_compaction=allow_text_compaction,
            )
            self._fallback_submission_count += 1
        elif repeated_root_cause and self._previous_strategy == "plan_guided_recompose":
            directive = _non_layout_directive(
                category=category,
                quality_errors=quality_errors,
                fingerprint=fingerprint,
                consecutive_failures=self._consecutive_failures,
                category_attempt=category_attempt,
                no_progress=no_progress,
                force_targeted=True,
                duplicate_count_not_reduced=duplicate_count_not_reduced,
            )
        elif joint_recompose:
            directive = _full_dsl_transition_directive(
                category=category,
                fingerprint=fingerprint,
                consecutive_failures=self._consecutive_failures,
                category_attempt=category_attempt,
                no_progress=no_progress,
                instruction=JOINT_RECOMPOSITION_INSTRUCTION,
            )
        elif is_layout_failure:
            prefer_split_panels = _fixed_side_slot_text_overflow(
                invalid_source_dsl,
                quality_errors,
            )
            force_parent_layout = _requires_parent_layout_recompose(quality_errors)
            offer_anchor_action_migration = _pill_action_anchor_migration_relevant(
                invalid_source_dsl,
                task_spec,
            )
            directive = _layout_directive(
                category=category,
                fingerprint=fingerprint,
                consecutive_failures=self._consecutive_failures,
                category_attempt=category_attempt,
                no_progress=no_progress,
                prefer_split_panels=prefer_split_panels,
                force_parent_layout=force_parent_layout,
                allow_text_compaction=allow_text_compaction,
                offer_anchor_action_migration=offer_anchor_action_migration,
            )
        else:
            directive = _non_layout_directive(
                category=category,
                quality_errors=quality_errors,
                fingerprint=fingerprint,
                consecutive_failures=self._consecutive_failures,
                category_attempt=category_attempt,
                no_progress=no_progress,
                duplicate_count_not_reduced=duplicate_count_not_reduced,
            )
        if early_drop_due and directive.repair_strategy == "drop_optional_component":
            if persistent_plan_coverage_followup:
                early_drop_instruction = "Plan 事实缺失经过两次无损修复后仍未恢复；"
            else:
                early_drop_instruction = "固定容量组件的超限内容在一次无损重组后仍未获得合法落点；"
            directive = replace(
                directive,
                instruction=(
                    f"{early_drop_instruction}"
                    "不再等待固定第四轮，提前进入程序授权的最小 Drop。"
                    f"{directive.instruction}"
                ),
            )
        if table_text_item_overflow and directive.repair_strategy == "drop_optional_component":
            directive = replace(
                directive,
                instruction=(
                    "TableText.items 已超过组件合同允许的三项；"
                    "不再执行普通组件属性修复，直接进入程序授权的最小 Drop。"
                    f"{directive.instruction}"
                ),
            )
        semantic_guidance_strategies = {
            "semantic_layout_contract_repair",
            "parent_layout_recompose",
            "plan_guided_recompose",
        }
        if (
            semantic_layout_guidance is not None
            and directive.repair_strategy in semantic_guidance_strategies
        ):
            directive = replace(
                directive,
                instruction=(f"{directive.instruction}\n\n{semantic_layout_guidance}"),
            )
        if (
            capacity_regroup_contract_failure
            and directive.repair_strategy != "drop_optional_component"
        ):
            directive = replace(
                directive,
                instruction=(
                    f"{directive.instruction}{_TEXT_ONLY_TABLE_REPAIR_INSTRUCTION}"
                ),
            )
        if directive.retryable:
            self._repair_submission_count += 1
            # 去重轮消耗总修复预算，但不能冒充容量／缺失事实修复来提前授权 Drop。
            if not _has_duplicate_actions(quality_errors):
                if (
                    has_plan_coverage_error
                    and directive.repair_strategy != "drop_optional_component"
                ):
                    self._plan_coverage_repair_submission_count += 1
                if capacity_fits and directive.repair_strategy != "drop_optional_component":
                    self._capacity_pressure_repair_submitted = True
            if joint_inputs_available and directive.repair_strategy == "plan_guided_recompose":
                self._joint_full_recompose_seen = True
        if joint_inputs_available and relevant:
            directive = replace(
                directive,
                joint_context={
                    "observedCategories": list(self._joint_categories),
                    "layoutPreviouslyFailed": previous_layout_failure,
                    "revisitedTopology": revisited_topology,
                    "topologyFingerprint": topology,
                },
            )
        if self._latest_capacity_fits and (capacity_fits or early_drop_due):
            directive = replace(
                directive,
                capacity_fits=tuple(copy.deepcopy(self._latest_capacity_fits)),
            )
        if self._allowed_omitted_fact_indexes:
            directive = replace(
                directive,
                approved_omitted_fact_indexes=tuple(sorted(self._allowed_omitted_fact_indexes)),
            )
        if self._static_content and directive.repair_strategy != "drop_optional_component":
            repeated = directive.consecutive_failures >= 2
            directive = replace(
                directive,
                instruction=(
                    "按当前静态合同修复完整源，正文仅用ContentBlock、RecordList、ComparisonGroup；"
                    "保留must核心、保护片段、原文要求和动作；无保护should可省略并反馈取舍。"
                    "不得删除仍承载must的组件；混合组件只删除可选补充片段。"
                    "先修属性与布局，再去装饰标题、短键值改属性表，按实际行盒重组。"
                    "对比对象名与主值分开，关键数值、日期时间、单位保持完整片段；"
                    "超宽时改全宽正文或列表；省略号只采用Plan已有展示版本，"
                    "完整落实已接受核心文字；不再次摘要、缩字、隐式裁切或将核心移入note。"
                    + (
                        "同一问题重复出现：必须切换组件形态，优先完整复制计划的staticPresentation；"
                        "若没有已验证候选，按试排容量重新分配主副字段，不能再次返回相同结构。"
                        if repeated
                        else ""
                    )
                ),
                retryable=directive.retryable and directive.consecutive_failures < 3,
                stop_reason=(
                    "static_repeated_failure"
                    if directive.consecutive_failures >= 3
                    else directive.stop_reason
                ),
            )
        self._previous_strategy = directive.repair_strategy
        return directive
