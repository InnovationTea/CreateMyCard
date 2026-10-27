"""按已有静态 error 执行确定性修复；无 error 不生成候选，不调用渲染器或模型。"""

import json
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass, replace
from typing import Any

from services.card_validation.compact_validation.semantic.layout.geometry import (
    _single_line_title_height,
)
from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    ComponentRow,
    parse_compact_dsl_rows,
)
from services.compact_outer_recomposition import _serialize, _unique_id
from services.compact_region_layout import _inset, _number, reference_region_boxes
from services.generation_pipeline import DslProcessingContext, DslProcessingResult
from services.generation_trace_recorder import trace_attempt, trace_record, trace_span
from services.protocol_registry import A2UIProtocolRegistry


@dataclass
class ScriptRepairBudget:
    """一次生成内跨模型质量重试共享候选次数。"""

    max_candidates: int
    candidates_used: int = 0


_RULE_NAMES = {
    "semantic-layout": "语义布局重排",
    "duplicate-click": "完全重复点击动作去重",
    "height-closure": "明确父区的高度继承补齐",
    "button-slot": "按钮容器空间",
    "sibling-space": "同级空间分配",
    "parent-budget": "父容器预算",
}
_BUDGET_ERRORS = {
    "COMPACT_LAYOUT_HEIGHT_OVERFLOW": "height",
    "COMPACT_LAYOUT_WIDTH_OVERFLOW": "width",
}
_UNSAFE_SPACE = {"position", "translate", "rotate", "scale", "constraintSize", "aspectRatio"}


def _reference_boxes(
    nodes: dict[str, ComponentRow],
    context: DslProcessingContext,
) -> dict:
    model = []
    for row in nodes.values():
        styles = row.props
        if row.component_type == "SingleLineTitle":
            styles = {**styles, "height": _single_line_title_height(row, size=context.size)}
        model.append(
            {
                "id": row.component_id,
                "component": row.component_type,
                "styles": styles,
                "children": list(row.children),
            }
        )
    profile = A2UIProtocolRegistry.read_design_protocol_profile(
        context.design_profile_id or "design-compact-dsl",
    )
    return reference_region_boxes(model, size=context.size, profile=profile)


def _height_is_known(
    parent: ComponentRow,
    nodes: dict[str, ComponentRow],
    context: DslProcessingContext | None,
) -> bool:
    if context is None or _UNSAFE_SPACE.intersection(parent.props):
        return False
    boxes = _reference_boxes(nodes, context)
    box = boxes.get(parent.component_id)
    return box is not None and box.height is not None and box.height > 0


def _growth_fits_parent(
    row: ComponentRow,
    axis: str,
    value: float,
    nodes: dict[str, ComponentRow],
    parents: dict[str, str],
    context: DslProcessingContext | None,
) -> bool:
    parent = nodes.get(parents.get(row.component_id))
    if parent is None or _UNSAFE_SPACE.intersection(parent.props):
        return False
    available = _number(parent.props.get(axis))
    if context is not None:
        box = _reference_boxes(nodes, context).get(parent.component_id)
        measured = box.axis(axis) if box is not None else None
        if measured is not None:
            available = measured if available is None else min(available, measured)
    padding = _inset({"styles": parent.props}, "padding", axis)
    margin = _inset({"styles": row.props}, "margin", axis)
    if available is None or padding is None or margin is None:
        return False
    return value + margin <= available - padding + 1e-6


def _structural_candidates(
    row: ComponentRow,
    code: str,
    nodes: dict[str, ComponentRow],
    parents: dict[str, str],
    settings: Any,
    context: DslProcessingContext | None,
) -> Iterator[tuple[str, ComponentRow]]:
    if code == "COMPACT_CLICK_HANDLER_COUNT" and settings.enable_compact_duplicate_click_repair:
        handlers = row.props.get("onClick")
        if not isinstance(handlers, list) or len(handlers) < 2:
            return
        identities = set()
        for handler in handlers:
            if not isinstance(handler, dict) or set(handler) != {"call", "args"}:
                return
            call = handler.get("call")
            if (
                not isinstance(call, str)
                or not call.strip()
                or not isinstance(handler.get("args"), dict)
            ):
                return
            identities.add(json.dumps(handler, sort_keys=True, ensure_ascii=False))
        if len(identities) == 1:
            yield "duplicate-click", replace(row, props={**row.props, "onClick": [handlers[0]]})
    if code == "COMPACT_LAYOUT_HEIGHT_UNRESOLVED" and settings.enable_compact_height_closure_repair:
        if row.component_type != "Column" or "height" in row.props:
            return
        if _UNSAFE_SPACE.intersection(row.props):
            return
        parent = nodes.get(parents.get(row.component_id))
        if parent is not None and parent.component_type == "Row":
            if _height_is_known(parent, nodes, context):
                yield "height-closure", replace(row, props={**row.props, "height": "matchParent"})


def _changed_source(rows: list, changed: ComponentRow) -> str:
    candidate_rows = []
    for row in rows:
        if isinstance(row, ComponentRow) and row.component_id == changed.component_id:
            row = changed
        candidate_rows.append(row)
    return _serialize(candidate_rows)


def _subtree(identifier: str, nodes: dict[str, ComponentRow]) -> Iterator[ComponentRow]:
    pending = [identifier]
    visited = set()
    while pending:
        current = pending.pop()
        row = nodes.get(current)
        if row is None or current in visited:
            continue
        visited.add(current)
        yield row
        pending.extend(reversed(row.children))


def _readonly(identifier: str, nodes: dict[str, ComponentRow]) -> bool:
    for row in _subtree(identifier, nodes):
        if row.props.get("onClick") or row.component_type in {
            "InfoBlock",
            "PillButton",
            "CircleButton",
            "CardButton",
        }:
            return False
    return True


def _semantic_candidates(
    rows: list,
    nodes: dict[str, ComponentRow],
    parents: dict[str, str],
    target: ComponentRow,
    axis: str,
    size: str,
) -> Iterator[tuple[int, str]]:
    # 只遍历报错子树及祖先；不调整旁支区域。布局合法性仍由原处理链判断。
    affected = list(_subtree(target.component_id, nodes))
    visited = {row.component_id for row in affected}
    parent = nodes.get(parents.get(target.component_id))
    while parent is not None and parent.component_id not in visited:
        visited.add(parent.component_id)
        affected.append(parent)
        parent = nodes.get(parents.get(parent.component_id))
    for row in affected:
        layout = row.props.get("layout")
        variant = row.props.get("variant", "standard")
        variants = ()
        if row.component_type == "Layout":
            if size == "2x2" and layout == "S-title-content-action":
                variants = ("direct", "direct-dense", "direct-tight", "direct-flush")
            elif size == "2x2" and layout == "S-title-primary-secondary-action":
                variants = ("dense",)
            elif size == "2x4" and layout == "W-top-bottom":
                variants = ("equal", "bottom-details", "continuous")
        elif row.component_type == "Group" and len(row.children) == 2:
            if _readonly(row.component_id, nodes):
                if axis == "height" and variant in {"hero-support", "label-value"}:
                    variants = ("peer-pair",)
                elif axis == "width" and variant == "peer-pair":
                    variants = ("hero-support",)
        elif row.component_type == "SecondaryBody":
            columns = 2 if axis == "height" else 1
            if row.props.get("columns", 2) != columns:
                yield (
                    2,
                    _changed_source(
                        rows,
                        replace(row, props={**row.props, "columns": columns}),
                    ),
                )
        for value in variants:
            if value != variant:
                # 1 保持横竖方向；2 改变横竖方向，只在低改动候选无解后尝试。
                priority = 2 if row.component_type == "Group" else 1
                yield (
                    priority,
                    _changed_source(
                        rows,
                        replace(row, props={**row.props, "variant": value}),
                    ),
                )

        # 把原主内容、辅助内容放入只读 Group；标题和底部动作保持原位置与内容。
        replacement = None
        if row.component_type == "Layout" and size == "2x2":
            replacement = {
                "S-title-dual-content": ("S-title-content", 3),
                "S-title-primary-secondary-action": ("S-title-content-action", 4),
            }.get(layout)
            if variant not in {"standard", "dense"}:
                replacement = None
        elif row.component_type == "Region" and size == "2x4":
            replacement = {
                "title-hero-support": ("title-content", 3),
                "title-hero-support-action": ("title-content-action", 4),
            }.get(variant)
        if replacement is None or len(row.children) != replacement[1]:
            continue
        primary, support = row.children[1:3]
        if not _readonly(primary, nodes) or not _readonly(support, nodes):
            continue
        identifier = _unique_id(f"{row.component_id}_content_group", set(nodes))
        children = (row.children[0], identifier, *row.children[3:])
        props = {**row.props}
        if row.component_type == "Layout":
            props["layout"] = replacement[0]
            props["variant"] = "direct" if len(children) == 3 else "standard"
        else:
            props["variant"] = replacement[0]
        changed = replace(row, props=props, children=children)
        for group_variant in ("hero-support", "peer-pair"):
            group = ComponentRow(
                identifier,
                "Group",
                {"variant": group_variant},
                (primary, support),
            )
            priority = 1 if group_variant == "hero-support" else 2
            if row.component_type == "Layout" and len(children) == 3:
                for action_variant in ("direct", "direct-dense", "direct-tight", "direct-flush"):
                    candidate = replace(changed, props={**props, "variant": action_variant})
                    yield priority, _changed_source([*rows, group], candidate)
            else:
                yield priority, _changed_source([*rows, group], changed)


def _diagnostics(result: DslProcessingResult) -> Iterator[dict]:
    for issue in result.errors:
        for diagnostic in issue.prompt_context.get("compactDiagnostics", []):
            if isinstance(diagnostic, dict):
                yield diagnostic


def _split_region_candidate(
    rows: list,
    nodes: dict[str, ComponentRow],
    *,
    capacity_error: bool,
) -> str | None:
    root = nodes.get("root")
    if root is None or root.component_type != "Layout":
        return None
    if root.props.get("layout") != "W-top-bottom" or len(root.children) not in {2, 3}:
        return None
    details = nodes.get(root.children[-1])
    if details is None:
        return None
    if details.component_type != "EventCard":
        supported = details.component_type in {"SummaryList", "TopTextBottomValue"}
        if not capacity_error or not supported:
            return None
        if len(root.children) != 3:
            return None
    if not all(_readonly(child, nodes) for child in root.children):
        return None
    used = set(nodes)
    primary_id = _unique_id("repair_primary_region", used)
    details_id = _unique_id("repair_details_region", used)
    primary_children = root.children[:-1]
    variant = "title-content" if len(primary_children) == 2 else "center"
    primary = ComponentRow(primary_id, "Region", {"variant": variant}, primary_children)
    secondary = ComponentRow(details_id, "Region", {"variant": "center"}, (details.component_id,))
    props = {**root.props, "layout": "W-split-panels"}
    props.pop("variant", None)
    changed = replace(root, props=props, children=(primary_id, details_id))
    return _changed_source([*rows, primary, secondary], changed)


def _top_bottom_candidate(rows: list, nodes: dict[str, ComponentRow]) -> str | None:
    root = nodes.get("root")
    if root is None or root.component_type != "Layout":
        return None
    if root.props.get("layout") != "W-split-panels" or len(root.children) != 2:
        return None
    primary, secondary = (nodes.get(child) for child in root.children)
    if primary is None or secondary is None:
        return None
    if primary.component_type != "Region" or primary.props != {"variant": "title-content"}:
        return None
    if secondary.component_type != "Region" or secondary.props != {"variant": "center"}:
        return None
    if len(primary.children) != 2 or len(secondary.children) != 1:
        return None
    details = nodes.get(secondary.children[0])
    if details is None or details.component_type not in {"SummaryList", "TopTextBottomValue"}:
        return None
    if not all(_readonly(child, nodes) for child in root.children):
        return None
    props = {**root.props, "layout": "W-top-bottom", "variant": "continuous"}
    changed = replace(root, props=props, children=(*primary.children, *secondary.children))
    kept = []
    for row in rows:
        if isinstance(row, ComponentRow) and row.component_id in root.children:
            continue
        kept.append(row)
    return _changed_source(kept, changed)


def _error_facts(result: DslProcessingResult) -> dict[tuple, float | None]:
    facts: dict[tuple, float | None] = {}
    for issue in result.errors:
        diagnostics = issue.prompt_context.get("compactDiagnostics", [])
        if not diagnostics:
            facts[(issue.code, issue.message)] = None
        for diagnostic in diagnostics:
            key = (
                diagnostic.get("code"),
                diagnostic.get("evidenceComponentId") or diagnostic.get("componentId"),
                diagnostic.get("evidencePropertyPath") or diagnostic.get("propertyPath"),
            )
            actual = diagnostic.get("actual")
            overflow = _number(actual.get("overflow")) if isinstance(actual, dict) else None
            if key not in facts:
                facts[key] = overflow
            else:
                previous = facts.get(key)
                if previous is None or overflow is None:
                    facts[key] = None
                else:
                    facts[key] = max(previous, overflow)
    return facts


def _improved(before: DslProcessingResult, after: DslProcessingResult) -> bool:
    old, new = _error_facts(before), _error_facts(after)
    if not new.keys() <= old.keys():
        return False
    improved = new.keys() < old.keys()
    for key, overflow in new.items():
        previous = old.get(key)
        if previous is not None:
            if overflow is None or overflow > previous:
                return False
            if overflow < previous - 1e-6:
                improved = True
    previous_warnings = set()
    for issue in before.issues:
        if issue.severity == "warning":
            previous_warnings.add((issue.code, issue.message))
    for issue in after.issues:
        if issue.severity == "warning" and (issue.code, issue.message) not in previous_warnings:
            return False
    return improved


def static_candidates(
    result: DslProcessingResult,
    settings: Any,
    *,
    context: DslProcessingContext | None = None,
) -> Iterator[tuple[str, str]]:
    if not result.errors:
        return
    rows = parse_compact_dsl_rows(result.source_dsl, expand_layouts=False)
    nodes: dict[str, ComponentRow] = {}
    parents: dict[str, str] = {}
    for row in rows:
        if isinstance(row, ComponentRow):
            nodes[row.component_id] = row
            for child in row.children:
                parents[child] = row.component_id
    seen = set()
    same_direction = []
    reflows = []
    if context is not None and settings.enable_compact_semantic_layout_repair:
        if context.size == "2x4":
            capacity_error = any(d.get("code") in _BUDGET_ERRORS for d in _diagnostics(result))
            candidates = [_split_region_candidate(rows, nodes, capacity_error=capacity_error)]
            if capacity_error:
                candidates.append(_top_bottom_candidate(rows, nodes))
            for candidate in candidates:
                if candidate is None:
                    continue
                seen.add(("semantic-layout", candidate))
                reflows.append(("semantic-layout", candidate))
    for diagnostic in _diagnostics(result):
        source = nodes.get(diagnostic.get("componentId"))
        if source is not None:
            for rule, changed in _structural_candidates(
                source,
                diagnostic.get("code"),
                nodes,
                parents,
                settings,
                context,
            ):
                candidate = _changed_source(rows, changed)
                identity = (rule, candidate)
                if identity not in seen:
                    seen.add(identity)
                    yield rule, candidate
        axis = _BUDGET_ERRORS.get(diagnostic.get("code"))
        actual = diagnostic.get("actual")
        if axis is None or not isinstance(actual, dict):
            continue
        overflow = _number(actual.get("overflow"))
        component_id = diagnostic.get("componentId")
        current = nodes.get(component_id)
        if overflow is None or overflow <= 0 or current is None:
            continue
        if context is not None and settings.enable_compact_semantic_layout_repair:
            for priority, candidate in _semantic_candidates(
                rows,
                nodes,
                parents,
                current,
                axis,
                context.size,
            ):
                identity = ("semantic-layout", candidate)
                if identity not in seen:
                    seen.add(identity)
                    if priority == 1:
                        same_direction.append(identity)
                    else:
                        reflows.append(identity)
        visited = set()
        while current is not None and current.component_id not in visited:
            visited.add(current.component_id)
            if current.component_type not in {"Row", "Column"}:
                break
            if _UNSAFE_SPACE.intersection(current.props):
                break
            edits = []
            has_button = any(
                node.component_type in {"PillButton", "CircleButton", "CardButton"}
                for node in _subtree(current.component_id, nodes)
            )
            rule = "button-slot" if has_button else "parent-budget"
            switch = (
                settings.enable_compact_button_slot_repair
                if rule == "button-slot"
                else settings.enable_compact_parent_budget_repair
            )
            explicit = _number(current.props.get(axis))
            if switch and explicit is not None and current.component_id != "root":
                grown = explicit + overflow
                if _growth_fits_parent(current, axis, grown, nodes, parents, context):
                    edits.append((rule, axis, grown))
            gap = _number(current.props.get("itemMargin"))
            if settings.enable_compact_parent_budget_repair and gap is not None and gap > 0:
                # 先试既有的零间距候选，避免连续减半的微小进展耗尽整个候选预算。
                edits.extend(("parent-budget", "itemMargin", value) for value in (0, gap / 2))
            weight = _number(current.props.get("layoutWeight"))
            if axis == "width" and settings.enable_compact_sibling_space_repair and weight:
                parent = nodes.get(parents.get(current.component_id))
                if parent is not None and parent.component_type == "Row":
                    for factor in (2, 3, 4, 6):
                        edits.append(("sibling-space", "layoutWeight", weight * factor))
            for rule, key, value in edits:
                identity = (current.component_id, key, value)
                if identity in seen:
                    continue
                seen.add(identity)
                changed = replace(current, props={**current.props, key: value})
                yield rule, _changed_source(rows, changed)
            current = nodes.get(parents.get(current.component_id))
    yield from same_direction
    yield from reflows


async def repair_static_errors(
    result: DslProcessingResult,
    *,
    settings: Any,
    evaluate: Callable[[str], Awaitable[DslProcessingResult]],
    budget: ScriptRepairBudget,
    context: DslProcessingContext | None = None,
) -> DslProcessingResult:
    if not result.errors or not settings.enable_compact_script_repair:
        return result
    original = result
    attempted = 0
    while result.errors and budget.candidates_used < budget.max_candidates:
        accepted = False
        try:
            for rule, source in static_candidates(result, settings, context=context):
                if budget.candidates_used >= budget.max_candidates:
                    break
                budget.candidates_used += 1
                attempted += 1
                with (
                    trace_attempt(scriptCandidate=budget.candidates_used),
                    trace_span(
                        "compact.script.candidate",
                        stage="repair.script",
                        details={
                            "rule": rule,
                            "ruleName": _RULE_NAMES.get(rule),
                            "candidate": budget.candidates_used,
                        },
                    ) as span,
                ):
                    candidate = await evaluate(source)
                    accepted = _improved(result, candidate)
                    span.text_artifacts.update(
                        {
                            "compact_script_before": result.source_dsl,
                            "compact_script_candidate": source,
                        }
                    )
                    span.json_artifacts["compact_script_issues"] = [
                        issue.to_diagnostic_payload() for issue in candidate.issues
                    ]
                    span.artifact_roles.update(
                        {
                            "compact_script_before": "input",
                            "compact_script_candidate": "output",
                            "compact_script_issues": "diagnostic",
                        }
                    )
                    span.outcome(
                        "success" if accepted else "rejected",
                        accepted=accepted,
                        beforeErrorCount=len(result.errors),
                        afterErrorCount=len(candidate.errors),
                        reasonCode="ERROR_FACTS_IMPROVED" if accepted else "NO_SAFE_PROGRESS",
                    )
                if accepted:
                    result = candidate
                    break
        except CompactDslConversionError as exc:
            trace_record(
                "compact.script.parse_failed",
                stage="repair.script",
                status="skipped",
                details={"exceptionType": type(exc).__name__, "reasonCode": "SOURCE_PARSE_FAILED"},
            )
            break
        if not accepted:
            break
    trace_record(
        "compact.script.decision",
        stage="repair.script",
        status="success",
        details={
            "candidateCount": attempted,
            "changed": result.source_dsl != original.source_dsl,
            "remainingErrorCount": len(result.errors),
            "next": "quality_controller" if result.errors else "validation",
        },
    )
    return result
