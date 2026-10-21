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
_SECONDARY_BODY_DYNAMIC_LABEL_MARKERS = (
    "secondarybody.items[].label only accepts a static value",
)
_SECONDARY_BODY_FONT_SIZE_MARKERS = (
    "secondarybody.fontsize must be the fixed recipe value",
)
_CAPACITY_REGROUP_CONTRACT_MARKERS = (
    "is auxiliary and cannot be the only information component",
)
_DUPLICATE_PLAN_FACT_PREFIX = (
    "plan fact is displayed more than once in visible dsl:"
)
COMPACT_COMPONENT_FALLBACK_MAX_ATTEMPTS = 2
DROP_OPTIONAL_COMPONENT_MIN_REPAIR_ATTEMPT = 4
PLAN_COVERAGE_EARLY_DROP_MIN_REPAIR_ATTEMPTS = 2

_CAPACITY_TEXT_COMPACTION_INSTRUCTION = (
    " 容量修复的受控选型例外：仅当2x4强调读数组合已确认放不下、整卡其它位置已有"
    "TextBlock等核心信息组件，且用户未明确要求大号强调、进度或事件形式时，"
    "可将该读数和同对象短补充合并为一个SecondaryBody.items。短字段名称放静态label，"
    "动态值和单位放value，完整保留全部标签、数值、单位、绑定和Action。"
    "这是更换显示组件，不是缩小EmphasizedData的固定字号；新组件整组单行14fp/19vp，"
    "多行或任一项maxLines:2时12fp/16vp，行间距2vp。更新父级引用并移除被替换的旧子树；"
    "不得补造核心组件、拆成多个单项SecondaryBody或删除事实来满足条件。"
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
        if self.approved_omitted_fact_indexes:
            payload["approvedOmittedFactIndexes"] = list(
                self.approved_omitted_fact_indexes
            )
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


def _has_duplicate_plan_facts(quality_errors: list[dict[str, Any]]) -> bool:
    for issue in quality_errors:
        duplicate_facts = issue.get("duplicateFacts")
        if isinstance(duplicate_facts, list) and duplicate_facts:
            return True
        message = str(issue.get("message") or "").strip().lower()
        if message.startswith(_DUPLICATE_PLAN_FACT_PREFIX):
            return True
    return False


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
    messages = "\n".join(
        str(issue.get("message") or "").lower() for issue in quality_errors
    )
    return _contains_marker(messages, _CAPACITY_REGROUP_CONTRACT_MARKERS)


def _capacity_overflow_limit(capacity_fits: list[dict[str, Any]]) -> int | None:
    """返回本轮已证明的最小溢出事实数，用于限制提前 Drop 的损失。"""
    counts: list[int] = []
    for capacity_fit in capacity_fits:
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


def _duplicate_fact_instruction(*, scope: str) -> str:
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
    if scope == "parent_layout":
        instruction += (
            "上一轮局部去重未闭合；重新组织受影响信息组及其直接父布局，不再提交相同组件组合。"
        )
    elif scope == "full_dsl":
        instruction += (
            "重复问题已持续存在；从已接受 Plan 重建完整 DSL，为每个 dataId 只分配一个可见位置。"
        )
    return instruction


def _fixed_side_slot_text_overflow(
    invalid_source_dsl: str,
    quality_errors: list[dict[str, Any]],
) -> bool:
    """识别侧双槽固定信息槽无法容纳完整单行内容的容量错误。"""
    messages = "\n".join(
        str(issue.get("message") or "") for issue in quality_errors
    )
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
        fixed_slots = [
            child for child in children[1:] if isinstance(child, str)
        ]
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
    messages = "\n".join(
        str(issue.get("message") or "").lower() for issue in quality_errors
    )
    base_instruction = (
        "只修复错误组件中被定位的 Props、绑定或格式，并复查直接父容器；"
        "保留该组件其它合法属性、动态事实、事件和视觉能力，"
        "不得通过删除未报错属性、移除视觉变体或更换为弱语义组件来绕过校验。"
    )
    secondary_body_count = re.search(
        r"secondarybody\.items requires 1 to 6 entries \(got (\d+)\)", messages,
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
            "整组只有一行且各项 maxLines 都为 1（默认 1）时，固定为 14fp/19vp；"
            "超过一行或任一项 maxLines 为 2 时，整组固定为 12fp/16vp，行间距为 2vp。"
            "两项同行用 14；两项 columns:1 分行用 12，不能只按项目数判断。"
            "若其它错误授权调整 items、columns 或 maxLines，合组完成后按最终行布局重新核算"
            "字号与高度；不得仅为缩小字号拆散信息组或删除事实。"
        )
    return base_instruction


def _issue_category(quality_errors: list[dict[str, Any]]) -> str:
    codes = {str(issue.get("code") or "") for issue in quality_errors}
    messages = "\n".join(
        str(issue.get("message") or "").lower() for issue in quality_errors
    )
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
        strategy = (
            "parent_layout_recompose" if scope == "parent_layout" else "rebudget"
        )
        instruction = (
            "修复违反合同的父布局结构，重新分配完整信息组和动作槽。"
            if scope == "parent_layout"
            else "重算受影响信息组的完整高度与间距，改用能闭合的合法子布局组合。"
        )
    elif category_attempt == 2:
        scope = "parent_layout"
        strategy = "parent_layout_recompose"
        instruction = (
            "前一轮布局修复没有闭合；停止修改局部几何，重新选择父布局变体并分配全部事实。"
        )
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
) -> CompactRepairDirective:
    repeated_root_cause = consecutive_failures >= 2 or no_progress
    duplicate_plan_facts = (
        category == "plan_coverage" and _has_duplicate_plan_facts(quality_errors)
    )
    if duplicate_plan_facts and category_attempt == 1 and not no_progress:
        scope = "information_group"
        strategy = "deduplicate_visible_facts"
        retry_target = "dsl_local_repair"
        instruction = _duplicate_fact_instruction(scope=scope)
    elif duplicate_plan_facts and category_attempt == 2:
        scope = "parent_layout"
        strategy = "parent_layout_recompose"
        retry_target = "dsl_recompose"
        instruction = _duplicate_fact_instruction(scope=scope)
    elif duplicate_plan_facts:
        scope = "full_dsl"
        strategy = "plan_guided_recompose"
        retry_target = "dsl_recompose"
        instruction = _duplicate_fact_instruction(scope=scope)
    elif force_targeted:
        scope = "information_group" if category == "plan_coverage" else "component"
        strategy = (
            "coverage_restore"
            if category == "plan_coverage"
            else "component_contract_repair"
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
            "coverage_restore"
            if category == "plan_coverage"
            else "component_contract_repair"
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
            "本次请求已经达到全局最大修复次数；停止调用模型，"
            "保留当前诊断并按校验失败处理。"
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
    try:
        rows = parse_compact_dsl_rows(compact_dsl)
    except (CompactDslConversionError, TypeError, ValueError):
        return False
    components = [row for row in rows if isinstance(row, ComponentRow)]
    if any(row.component_id == candidate.component_id for row in components):
        return False
    return not any(candidate.component_id in row.children for row in components)


class CompactRepairStrategyTracker:
    """在单次生成请求内跟踪失败指纹并选择下一轮修复范围。"""

    def __init__(
        self,
        *,
        max_repair_attempts: int = 10,
        capacity_recovery: bool = False,
    ) -> None:
        if max_repair_attempts < 1:
            raise ValueError("max_repair_attempts must be at least 1")
        self._max_repair_attempts = max_repair_attempts
        self._capacity_recovery = capacity_recovery
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

    def validation_omitted_fact_indexes(
        self,
        compact_plan: dict[str, Any] | None,
        *,
        validate_drop_plan_facts: bool,
    ) -> tuple[int, ...]:
        """仅在已进入Drop且开关关闭时放宽展示事实，保留Action检查。"""
        explicitly_allowed = self.allowed_omitted_fact_indexes
        if validate_drop_plan_facts or not explicitly_allowed:
            return explicitly_allowed
        facts = compact_plan.get("info_required") if compact_plan is not None else None
        if not isinstance(facts, list):
            return explicitly_allowed
        allowed: list[int] = []
        for index, fact in enumerate(facts):
            if isinstance(fact, dict) and "actionId" not in fact:
                allowed.append(index)
        return tuple(allowed)

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
    ) -> CompactOptionalDropCandidate | None:
        """从当前仍可见内容中选择下一轮唯一候选并累计省略授权。"""
        candidate = compact_plan_optional_drop_candidate(
            compact_dsl,
            compact_plan,
            task_spec,
            allow_must_fallback=allow_must_fallback,
            max_fact_count=max_fact_count,
            allowed_fact_indexes=allowed_fact_indexes,
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
        capacity_fits = _capacity_fits_from_issues(quality_errors)
        if not capacity_fits:
            capacity_fits = bounded_component_capacity_contexts(
                invalid_source_dsl,
                quality_errors,
                compact_plan,
            )
        if capacity_fits:
            category = "layout_capacity"
            self._latest_capacity_fits = copy.deepcopy(capacity_fits)
            overflow_limit = _capacity_overflow_limit(capacity_fits)
            if overflow_limit is not None:
                self._capacity_overflow_limit = overflow_limit
            self._capacity_overflow_fact_indexes = _capacity_overflow_fact_indexes(
                capacity_fits
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
            self._previous_source is not None
            and normalized_source == self._previous_source
        )
        category_attempt = self._category_attempts.get(category, 0) + 1
        self._category_attempts[category] = category_attempt
        self._previous_fingerprint = fingerprint
        self._previous_source = normalized_source
        changed_constraint = previous_category is not None and category != previous_category
        persistent_capacity = category == "layout_capacity" and category_attempt >= 2
        joint_progress_failed = changed_constraint or revisited_topology or persistent_capacity
        joint_inputs_available = compact_plan is not None and task_spec is not None
        joint_recompose = (
            joint_inputs_available and previous_layout_failure and relevant
        )
        joint_recompose = joint_recompose and joint_progress_failed
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
            if self._allowed_omitted_fact_indexes:
                directive = replace(
                    directive,
                    approved_omitted_fact_indexes=tuple(
                        sorted(self._allowed_omitted_fact_indexes)
                    ),
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
        bounded_capacity_followup = (
            self._capacity_pressure_repair_submitted
            and self._repair_submission_count > 0
            and (
                is_layout_failure
                or _capacity_regroup_contract_failure(quality_errors)
            )
        )
        early_drop_due = persistent_plan_coverage_followup or bounded_capacity_followup
        allow_text_compaction = _capacity_text_compaction_relevant(
            invalid_source_dsl,
        )
        recovery_drop_due = self._capacity_recovery and self._repair_submission_count == 0
        drop_entry_due = early_drop_due or recovery_drop_due or (
            self._repair_submission_count >= DROP_OPTIONAL_COMPONENT_MIN_REPAIR_ATTEMPT - 1
            and self._active_fallback != "drop_optional_component"
        )
        drop_relevant_failure = (
            is_layout_failure
            or persistent_plan_coverage_followup
            or bounded_capacity_followup
        )
        if drop_entry_due and drop_relevant_failure and task_spec is not None:
            max_fact_count = self._capacity_overflow_limit if early_drop_due else None
            allowed_fact_indexes = None
            if bounded_capacity_followup:
                allowed_fact_indexes = self._capacity_overflow_fact_indexes
            candidate = self._select_drop_candidate(
                invalid_source_dsl,
                compact_plan,
                task_spec,
                allow_must_fallback=not self._capacity_recovery,
                max_fact_count=max_fact_count,
                allowed_fact_indexes=allowed_fact_indexes,
            )
            if candidate is not None:
                self._active_fallback = "drop_optional_component"
                self._fallback_submission_count = 0
                self._fallback_submission_limit = (
                    self._max_repair_attempts - self._repair_submission_count
                )
        if self._active_fallback == "drop_optional_component":
            if self._optional_drop_candidate is None:
                raise RuntimeError("optional drop fallback has no selected candidate")
            candidate_was_removed = _drop_candidate_is_fully_removed(
                invalid_source_dsl,
                self._optional_drop_candidate,
            )
            if candidate_was_removed and not is_layout_failure:
                directive = _non_layout_directive(
                    category=category,
                    quality_errors=quality_errors,
                    fingerprint=fingerprint,
                    consecutive_failures=self._consecutive_failures,
                    category_attempt=category_attempt,
                    no_progress=no_progress,
                    force_targeted=True,
                )
            elif candidate_was_removed:
                candidate = None
                if task_spec is not None:
                    candidate = self._select_drop_candidate(
                        invalid_source_dsl,
                        compact_plan,
                        task_spec,
                        allow_must_fallback=not self._capacity_recovery,
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
        elif (
            is_semantic_layout_contract_failure
            and self._consecutive_failures <= 2
        ):
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
                )
            elif self._fallback_submission_count >= COMPACT_COMPONENT_FALLBACK_MAX_ATTEMPTS:
                candidate = None
                if is_layout_failure and task_spec is not None:
                    candidate = self._select_drop_candidate(
                        invalid_source_dsl,
                        compact_plan,
                        task_spec,
                        allow_must_fallback=not self._capacity_recovery,
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
            )
        if early_drop_due and directive.repair_strategy == "drop_optional_component":
            if persistent_plan_coverage_followup:
                early_drop_instruction = (
                    "Plan 事实缺失经过两次无损修复后仍未恢复；"
                )
            else:
                early_drop_instruction = (
                    "固定容量组件的超限内容在一次无损重组后"
                    "仍未获得合法落点；"
                )
            directive = replace(
                directive,
                instruction=(
                    f"{early_drop_instruction}"
                    "不再等待固定第四轮，提前进入程序授权的最小 Drop。"
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
                instruction=(
                    f"{directive.instruction}\n\n{semantic_layout_guidance}"
                ),
            )
        if directive.retryable:
            self._repair_submission_count += 1
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
                approved_omitted_fact_indexes=tuple(
                    sorted(self._allowed_omitted_fact_indexes)
                ),
            )
        self._previous_strategy = directive.repair_strategy
        return directive
