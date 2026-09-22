from __future__ import annotations

import json
import math
import re
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from decimal import Decimal, InvalidOperation
from typing import Any

if "." in (__package__ or ""):
    from ..jsx_to_a2ui.catalog.bindings import (
        BINDABLE_PROPS,
        CompileContext,
        data_binding_ids,
        indexed_value_template_tokens,
        materialize_binding_literals,
        status_binding_evidence,
    )
    from ..jsx_to_a2ui.catalog.contracts import collect_jsx_component_errors
    from ..jsx_to_a2ui.catalog.metric_semantics import metric_requires_label
    from ..jsx_to_a2ui.compiler import compile_source
    from ..jsx_to_a2ui.exceptions import (
        A2UIProtocolOutputError,
        ConversionError,
        ParseError,
        ValidationError,
    )
    from ..jsx_to_a2ui.ir.a2ui_nodes import collect_binding_validation_errors
    from ..jsx_to_a2ui.parser.jsx_ast import JSXElement
    from ..jsx_to_a2ui.parser.jsx_parser import extract_card_functions
    from ..jsx_to_a2ui.semantic_layouts import lower_semantic_card
    from ..jsx_to_a2ui.validation.jsx_preflight import collect_conversion_preflight_errors
else:  # Support top-level package imports.
    from jsx_to_a2ui.catalog.bindings import (
        BINDABLE_PROPS,
        CompileContext,
        data_binding_ids,
        indexed_value_template_tokens,
        materialize_binding_literals,
        status_binding_evidence,
    )
    from jsx_to_a2ui.catalog.contracts import collect_jsx_component_errors
    from jsx_to_a2ui.catalog.metric_semantics import metric_requires_label
    from jsx_to_a2ui.compiler import compile_source
    from jsx_to_a2ui.exceptions import (
        A2UIProtocolOutputError,
        ConversionError,
        ParseError,
        ValidationError,
    )
    from jsx_to_a2ui.ir.a2ui_nodes import collect_binding_validation_errors
    from jsx_to_a2ui.parser.jsx_ast import JSXElement
    from jsx_to_a2ui.parser.jsx_parser import extract_card_functions
    from jsx_to_a2ui.semantic_layouts import lower_semantic_card
    from jsx_to_a2ui.validation.jsx_preflight import collect_conversion_preflight_errors

from .card_sizes import CARD_SIZE_DIMENSIONS, card_dimensions, task_card_size
from .config import RESOURCE_STAGES
from .layout_rules import (
    LAYOUT_PATTERN_2X2_CODES,
    LAYOUT_PATTERN_2X2_NAMES,
    LAYOUT_PATTERN_2X4_CODES,
    LAYOUT_PATTERN_2X4_NAMES,
    SUB_PATTERN_2X4_GROUPS,
    SUB_PATTERN_2X4_NAMES,
    TOP_LEVEL_2X2_TYPES,
    TOP_LEVEL_2X4_TYPES,
    declared_2x2_layout_errors,
    declared_layout_errors,
    fixed_grid_errors,
    fixed_slot_dimension_errors,
    fixed_slot_kind,
    preferred_axis_size,
)
from .required_facts import (
    context_with_initial_values,
    enforceable_facts,
    missing_required_facts,
    required_facts_schema,
    validate_required_facts,
    validate_data_inventory,
    unavailable_data_ids,
    input_availability_warnings,
)
from .resources import (
    GenerationResources,
    generation_components_for_size,
    generatable_contracts,
    iter_asset_values,
)


_BUDGET_CARD_SIZE: ContextVar[str | None] = ContextVar("layout_budget_card_size", default=None)


@dataclass(slots=True)
class CompiledSubmission:
    source: str
    jsx: str
    messages: list[dict[str, Any]]
    decision: dict[str, Any]
    compile_context: dict[str, Any] = field(default_factory=dict)
    coverage: list[dict[str, Any]] = field(default_factory=list)
    unmet_requirements: list[str] = field(default_factory=list)
    semantic_status: str = "completed"
    warnings: list[dict[str, str]] = field(default_factory=list)
    semantic_source: str | None = None


def submission_reference_ids(
    submission: CompiledSubmission,
) -> tuple[set[str], set[str]]:
    """Return data/action references from the compiled JSX itself.

    Coverage metadata is advisory and may be absent or normalized, so browser
    repair regression checks must derive references from the JSX tree instead.
    """

    cards = extract_card_functions(submission.source)
    return _effective_binding_ids(cards[next(iter(cards))])


def browser_repair_preservation_findings(
    baseline: CompiledSubmission,
    candidate: CompiledSubmission,
    compile_context: dict[str, Any] | None,
    *,
    require_all_data_ids: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Detect deterministic semantic regressions introduced by layout repair.

    Removing an action is a definite regression. Text/number similarity alone
    does not prove staticization. Completely omitting a data binding is
    advisory during ordinary repair, forbidden during compact fallback, and
    allowed during drop fallback. Action removal is always forbidden.
    """

    baseline_data, baseline_actions = submission_reference_ids(baseline)
    candidate_data, candidate_actions = submission_reference_ids(candidate)
    removed_data = sorted(baseline_data - candidate_data)
    removed_actions = sorted(baseline_actions - candidate_actions)
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, str]] = []


    if removed_actions:
        errors.append(
            {
                "severity": "error",
                "code": "browser-repair-dropped-action",
                "message": (
                    "浏览器布局修复删除了此前有效的 actionId："
                    + ", ".join(repr(value) for value in removed_actions)
                    + "。布局修复不得通过删除交互需求通过校验。"
                ),
                "details": {"removedActionIds": removed_actions},
            }
        )

    if not removed_data:
        return errors, warnings

    try:
        effective_context = baseline.compile_context or compile_context
        context = CompileContext.from_payload(effective_context)
        cards = extract_card_functions(candidate.source)
        root = cards[next(iter(cards))]
    except ConversionError:
        context = None
        root = None

    staticized: dict[str, list[str]] = {}
    if context is not None and root is not None:
        visible_literals = [
            (f"{node.tag}.{location}", literal)
            for node in _walk(root)
            for location, literal in _unbound_display_values(node)
        ]
        for binding_id in removed_data:
            try:
                sample = context.data_binding(binding_id).value
            except ValidationError:
                continue
            matches: list[str] = []
            for location, literal in visible_literals:
                if isinstance(sample, bool) or sample is None:
                    continue
                if type(literal) is type(sample) and literal == sample:
                    matches.append(location)
                    continue
                if isinstance(literal, str) and isinstance(sample, str):
                    normalized_sample = sample.strip()
                    if normalized_sample and normalized_sample in literal:
                        matches.append(location)
                        continue
                if isinstance(literal, str) and isinstance(sample, (int, float)):
                    if _number_tokens(sample) & _number_tokens(literal):
                        matches.append(location)
            if matches:
                staticized[binding_id] = sorted(set(matches))

    if staticized:
        strict_preservation = require_all_data_ids
        (errors if strict_preservation else warnings).append(
            {
                "severity": "error" if strict_preservation else "warning",
                "code": "browser-repair-staticized-binding",
                "message": (
                    "浏览器布局修复删除了动态绑定，静态文本与其样例值相似，需核对是否为同一事实："
                    + "; ".join(
                        f"{binding_id!r} -> {', '.join(locations)}" for binding_id, locations in staticized.items()
                    )
                    + "。仅凭文字或数值相似不能确认静态化；必需 ID 的遗漏另行校验。"
                ),
                "details": {"staticizedDataIds": staticized},
            }
        )

    omitted = [value for value in removed_data if value not in staticized]
    if omitted:
        omitted_text = ", ".join(repr(value) for value in omitted)
        if require_all_data_ids:
            errors.append(
                {
                    "severity": "error",
                    "code": "browser-fallback-compact-dropped-binding",
                    "message": (
                        "紧凑组件替换阶段不得删除信息，但本次提交省略了数据绑定："
                        + omitted_text
                        + "。请通过更换组件或重组布局保留这些 dataIds。"
                    ),
                    "details": {"removedDataIds": omitted},
                }
            )
        else:
            warnings.append(
                {
                    "severity": "warning",
                    "code": "browser-repair-dropped-binding",
                    "message": (
                        "浏览器布局修复省略了此前展示的数据绑定："
                        + omitted_text
                        + "。仅当这些信息确实可舍弃时才应接受该结果。"
                    ),
                }
            )
    return errors, warnings




class LayoutBudgetError(ValidationError):
    """The statically known vertical content cannot fit its allocated region."""


class LayoutStructureError(ValidationError):
    """A declared layout violates an explicit structural contract."""


class RequiredInformationError(ValidationError):
    """A submission omitted a frozen, query-grounded display requirement."""


def _validate_structure(validate) -> None:
    try:
        validate()
    except ValidationError as exc:
        raise LayoutStructureError(str(exc)) from exc


_ARIA_LABEL_COMPONENTS = frozenset({"CircleButton", "ProgressCircleSingle", "ProgressCircle"})

_STRUCTURAL_PERCENT_TOTALS = frozenset({"ProgressLine1", "ProgressLine2"})
_TWO_COLUMN_GRID = re.compile(r"\s*(?P<fixed>\d+(?:\.\d+)?)px\s+minmax\(0,\s*(?P<weight>\d+(?:\.\d+)?)fr\)\s*")


def normalize_jsx_expression(source: str) -> str:
    value = source.strip()
    fence = re.fullmatch(r"```(?:jsx|javascript|js)?\s*(.*?)\s*```", value, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        value = fence.group(1).strip()
    if value.endswith(";"):
        value = value[:-1].rstrip()
    if not value.startswith("<"):
        raise ParseError("submit_card_jsx.jsx must be one JSX expression beginning with <Card>")
    return value


def wrap_card_source(component_name: str, jsx: str) -> str:
    return f"function {component_name}() {{\n  return (\n{jsx}\n  );\n}}\n"


def _jsx_literal(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _serialize_jsx(node: JSXElement, depth: int = 0) -> str:
    indent = "  " * depth
    props: list[str] = []
    for name, value in node.props.items():
        if isinstance(value, str):
            props.append(f"{name}={_jsx_literal(value)}")
        else:
            props.append(f"{name}={{{_jsx_literal(value)}}}")
    opening = f"{indent}<{node.tag}" + (" " + " ".join(props) if props else "")
    if not node.children:
        return opening + " />"
    lines = [opening + ">"]
    for child in node.children:
        if isinstance(child, JSXElement):
            lines.append(_serialize_jsx(child, depth + 1))
        else:
            lines.append("  " * (depth + 1) + str(child))
    lines.append(f"{indent}</{node.tag}>")
    return "\n".join(lines)


def _remove_empty_scalar_data_ids(root: JSXElement) -> list[dict[str, str]]:
    """Treat an explicitly empty scalar binding as an absent optional binding."""
    warnings: list[dict[str, str]] = []
    for node in _walk(root):
        owners: list[tuple[dict[str, Any], str]] = [(node.props, "")]
        items = node.props.get("items")
        if isinstance(items, list):
            owners.extend(
                (item, f"items[{index}].")
                for index, item in enumerate(items)
                if isinstance(item, dict)
            )
        for owner, prefix in owners:
            data_ids = owner.get("dataIds")
            if not isinstance(data_ids, dict):
                continue
            empty_props = [
                prop for prop, binding_id in data_ids.items()
                if isinstance(binding_id, str) and not binding_id.strip()
            ]
            if not empty_props:
                continue
            value_maps = owner.get("dataValueMaps")
            for prop in empty_props:
                data_ids.pop(prop, None)
                if isinstance(value_maps, dict):
                    value_maps.pop(prop, None)
                location = f"{prefix}dataIds.{prop}"
                warnings.append({
                    "severity": "warning",
                    "code": "empty-data-id-removed",
                    "message": (
                        f"<{node.tag}> {location} was empty and was removed; "
                        "the corresponding display value remains static"
                    ),
                })
            if not data_ids:
                owner.pop("dataIds", None)
            if isinstance(value_maps, dict) and not value_maps:
                owner.pop("dataValueMaps", None)
    return warnings


def _walk(node: JSXElement):
    yield node
    for child in node.child_elements():
        yield from _walk(child)


def _restore_remote_asset_sources(root: JSXElement, context: CompileContext | None) -> bool:
    """Replace model-facing asset aliases with their original remote URLs."""
    if context is None or not context.assets:
        return False
    sources = {alias: asset.src for alias, asset in context.assets.items()}
    changed = False

    def restore(value: Any, *, key: str | None = None) -> Any:
        nonlocal changed
        if isinstance(value, dict):
            return {
                nested_key: restore(nested, key=str(nested_key))
                for nested_key, nested in value.items()
            }
        if isinstance(value, list):
            return [restore(item, key=key) for item in value]
        if key in {"icon", "src", "checkIcon"} and isinstance(value, str) and value in sources:
            changed = True
            return sources[value]
        return value

    for node in _walk(root):
        node.props = restore(node.props)
    return changed


def _validate_generation_subset(root: JSXElement, expected_size: str | None = None) -> None:
    actual_size = root.props.get("size")
    resolved_size = expected_size or (actual_size if actual_size in CARD_SIZE_DIMENSIONS else None)
    contracts = generatable_contracts(resolved_size)
    if expected_size is None and resolved_size is None:
        card_contract = contracts["Card"]
        card_enums = dict(card_contract.enums or {})
        card_enums["size"] = card_enums.get("size", frozenset()) | {150}
        contracts = {
            **contracts,
            "Card": replace(card_contract, enums=card_enums),
        }
    all_component_names = set(generatable_contracts())
    errors: list[str] = []
    for node in _walk(root):
        if node.tag not in contracts:
            if resolved_size is not None and node.tag in all_component_names:
                errors.append(f"<{node.tag}> is not available for Card size={resolved_size!r}")
            else:
                errors.append(f"<{node.tag}> is not available to the JSX generation workflow")
        else:
            errors.extend(collect_jsx_component_errors(node, contracts))
    if root.tag != "Card":
        errors.append("generated card JSX must use <Card> as its root component")
    if expected_size is not None:
        if actual_size != expected_size:
            width, height = CARD_SIZE_DIMENSIONS[expected_size]
            errors.append(
                f"input task size={expected_size!r} requires <Card size={expected_size!r}> "
                f"({width}x{height}vp), found {actual_size!r}"
            )
    elif actual_size not in CARD_SIZE_DIMENSIONS and actual_size != 150:
        allowed = ", ".join(repr(item) for item in CARD_SIZE_DIMENSIONS)
        errors.append(
            f"generated Card.size must be one of {allowed}; numeric size={{150}} "
            f"is accepted only when no task size is available, found {actual_size!r}"
        )
    if resolved_size == "2x2":
        info_count = sum(1 for node in _walk(root) if node.tag == "InfoBlock")
        if info_count not in {0, 2}:
            errors.append("a 2x2 Card using InfoBlock must contain exactly two InfoBlock components")
    event_card_count = sum(1 for node in _walk(root) if node.tag == "EventCard")
    if event_card_count > 1:
        errors.append(
            "a Card may contain at most one EventCard; put one or two schedules "
            "in that component's items prop"
        )
    for ratio_stack in (node for node in _walk(root) if node.tag == "NumericRatioStack"):
        items = ratio_stack.props.get("items")
        if isinstance(items, list) and len(items) != 3:
            errors.append("NumericRatioStack.items must contain exactly three items")
    for node in _walk(root):
        if node.tag in _ARIA_LABEL_COMPONENTS and "ariaLabel" in node.props:
            aria_label = node.props.get("ariaLabel")
            if not isinstance(aria_label, str) or not aria_label.strip():
                errors.append(f"<{node.tag}> must declare a non-empty ariaLabel")
    if errors:
        raise ValidationError("; ".join(dict.fromkeys(errors)))


def _validate_conversion_preflight(root: JSXElement) -> None:
    errors = collect_conversion_preflight_errors(root)
    if errors:
        raise ValidationError("; ".join(errors))


def _canonical_layout_pattern(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = re.sub(r"[\s·:：]+", "", value).casefold()
    for name, code in (*LAYOUT_PATTERN_2X2_CODES.items(), *LAYOUT_PATTERN_2X4_CODES.items()):
        if re.sub(r"[\s·:：]+", "", name).casefold() == normalized:
            return code
    lowered = value.lower()
    match = re.search(r"type\s*[-_ ]?\s*(\d+)(?:\s*[-_ ]\s*([abcr])\b)?", lowered)
    if not match:
        return None
    number, suffix = match.groups()
    variant = re.search(r"variant\s*[-_ ]?\s*([abc])", lowered)
    suffix = suffix or (variant.group(1) if variant else None)
    return f"{int(number)}-{suffix.upper()}" if suffix else str(int(number))


def _canonical_sub_pattern(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = re.sub(r"[\s·:：]+", "", value).casefold()
    for name in SUB_PATTERN_2X4_NAMES:
        if re.sub(r"[\s·:：]+", "", name).casefold() == normalized:
            return name
    return None


def _layout_decision_fields(decision: dict[str, Any]) -> dict[str, Any]:
    """Keep only fields that describe the submitted layout decision."""

    return {
        key: decision[key]
        for key in ("layoutPattern", "subPattern")
        if key in decision
    }


def _validate_sub_pattern_decision(
    decision: dict[str, Any],
    size: object,
    pattern: str | None,
) -> list[str]:
    if size == "2x2":
        if "subPattern" in decision:
            return ["2x2 decision must not include subPattern"]
        return []
    if size != "2x4":
        return []
    if "subPattern" not in decision:
        raw_layout = decision.get("layoutPattern")
        normalized_layout = (
            re.sub(r"[\s·:：]+", "", raw_layout).casefold()
            if isinstance(raw_layout, str)
            else ""
        )
        public_layout_names = {
            re.sub(r"[\s·:：]+", "", name).casefold()
            for name in LAYOUT_PATTERN_2X4_NAMES
        }
        # Historical Type labels remain accepted by direct Python callers so
        # old saved traces and integrations can still be replayed. The live
        # 2x4 tool schema only exposes public names and requires subPattern.
        if normalized_layout not in public_layout_names:
            return []
        return ["2x4 decision.subPattern is required"]
    sub_pattern = decision.get("subPattern")
    if not isinstance(sub_pattern, dict):
        return ["2x4 decision.subPattern must be an object keyed by layout region"]

    if pattern == "13":
        expected_regions = {"left", "right"}
        required_group = "118"
    elif pattern in {"15", "15-R"}:
        expected_regions = {"content"}
        required_group = "140"
    elif pattern in {"12", "14"}:
        expected_regions = set()
        required_group = None
    else:
        return []

    actual_regions = set(sub_pattern)
    if actual_regions != expected_regions:
        rendered = ", ".join(sorted(expected_regions)) or "no region keys"
        return [
            f'2x4 layoutPattern requires subPattern with exactly {rendered}; '
            f"received {sorted(actual_regions)}"
        ]

    errors: list[str] = []
    canonical_by_region: dict[str, str] = {}
    for region, raw_name in sub_pattern.items():
        name = _canonical_sub_pattern(raw_name)
        if name is None:
            errors.append(f'decision.subPattern.{region} must name a documented Sub layout')
            continue
        canonical_by_region[region] = name
        if required_group is not None and SUB_PATTERN_2X4_GROUPS[name] != required_group:
            errors.append(
                f'decision.subPattern.{region} must use a Sub-{required_group} layout for '
                "the selected top-level layoutPattern"
            )
    return errors


def _validate_layout_decision(
    root: JSXElement,
    decision: dict[str, Any] | None,
    expected_size: str | None,
) -> None:
    if decision is None:
        return
    errors: list[str] = []
    pattern = _canonical_layout_pattern(decision.get("layoutPattern"))
    if pattern is None:
        errors.append("decision.layoutPattern must name a documented layout")
    size = expected_size or root.props.get("size")
    if size == "2x2":
        if pattern is not None and pattern not in TOP_LEVEL_2X2_TYPES:
            errors.append("2x2 decision.layoutPattern must use a documented 2x2 layout name")
        errors.extend(declared_2x2_layout_errors(root, pattern))
        if _number(root.props.get("padding", 12)) == 8 and pattern != "3":
            errors.append('only 2x2 layout "双信息块" may use Card.padding=8vp')
    if size == "2x4":
        if pattern is not None and pattern not in TOP_LEVEL_2X4_TYPES:
            errors.append("2x4 decision.layoutPattern must use a documented 2x4 top-level layout name")
        sub_pattern_errors = _validate_sub_pattern_decision(decision, size, pattern)
        errors.extend(sub_pattern_errors)
        errors.extend(declared_layout_errors(root, pattern))
    else:
        errors.extend(_validate_sub_pattern_decision(decision, size, pattern))
    appearance = root.props.get("appearance")
    if appearance == "type0-gradient" and pattern != "0":
        errors.append("Card appearance='type0-gradient' may only be used with layout \"核心居中\"")
    if errors:
        raise ValidationError("; ".join(dict.fromkeys(errors)))


def _validate_assets(root: JSXElement, prompt_task: dict[str, Any] | None) -> None:
    candidates = prompt_task.get("assetCandidates", []) if prompt_task is not None else None
    allowed_sources = (
        None
        if candidates is None
        else {
            item["src"].replace("\\", "/")
            for item in candidates
            if isinstance(item, dict) and isinstance(item.get("src"), str)
        }
        if isinstance(candidates, list)
        else set()
    )
    errors: list[str] = []
    for node in _walk(root):
        for source in iter_asset_values(node.props):
            normalized = source.replace("\\", "/")
            if allowed_sources is not None and normalized not in allowed_sources:
                errors.append(
                    f"<{node.tag}> resource {source!r} is not an exact model-facing src "
                    "from input assetCandidates"
                )
    if errors:
        raise ValidationError("; ".join(dict.fromkeys(errors)))


_NONNEGATIVE_LAYOUT_PROPS = frozenset(
    {
        "gap",
        "rowGap",
        "columnGap",
        "basis",
        "width",
        "minWidth",
        "height",
        "minHeight",
        "mt",
        "mb",
        "ml",
        "mr",
        "top",
        "right",
        "bottom",
        "left",
    }
)


def _validate_layout_values(root: JSXElement) -> None:
    issues: list[str] = []

    def visit(node: JSXElement, parent: JSXElement | None) -> None:
        for prop in _NONNEGATIVE_LAYOUT_PROPS:
            if prop not in node.props:
                continue
            value = node.props[prop]
            if isinstance(value, bool):
                issues.append(f"<{node.tag}>.{prop} must not be boolean")
            elif (numeric := _number(value)) is not None and numeric < 0:
                issues.append(f"<{node.tag}>.{prop} must be non-negative, found {value!r}")
        flex = node.props.get("flex")
        if flex is not None and (isinstance(flex, bool) or flex not in {0, 1}):
            issues.append(f"<{node.tag}>.flex must be 0 or 1, found {flex!r}")
        padding = node.props.get("padding")
        padding_values = padding.values() if isinstance(padding, dict) else (padding,)
        for value in padding_values:
            if isinstance(value, bool) or ((numeric := _number(value)) is not None and numeric < 0):
                issues.append(f"<{node.tag}>.padding must contain non-negative numbers")
                break
        if (
            node.tag == "Card"
            and _number(node.props.get("padding", 12)) != 12
            and not (node.props.get("size") == "2x2" and _number(node.props.get("padding")) == 8)
        ):
            issues.append(
                '<Card>.padding must be 12vp, except 2x2 layout "双信息块" which uses 8vp'
            )
        if parent is not None and parent.tag == "Grid" and node.props.get("basis") is not None:
            issues.append(
                f"<{node.tag}>.basis has no main-axis meaning as a direct Grid child; "
                "set Grid rows/columns or the child's explicit width/height instead"
            )
        children = node.child_elements()
        for index, child in enumerate(children):
            if child.tag == "CardButton":
                width, height = _card_button_slot_dimensions(node, index, parent)
                if width is not None and height is not None and width < height:
                    issues.append(
                        "<CardButton> parent slot must be at least as wide as it is tall; "
                        f"found {_vp(width)}×{_vp(height)}vp"
                    )
                if height is not None and not 48 <= height <= 64:
                    issues.append(
                        "<CardButton> parent slot height must be between 48vp and 64vp; "
                        f"found {_vp(height)}vp"
                    )
            visit(child, node)

    visit(root, None)
    if issues:
        raise ValidationError("; ".join(dict.fromkeys(issues)))


_INTRINSIC_HEIGHTS = {
    "Badge": 16,
    # 2x4 uses a 64vp value line and two 4vp gaps so Type13 Type0 closes at 110vp.
    "DataDisplay": 110,
    "EmphasizedData": 32,
    "ProgressLine1": 25,
    "NumericRatio": 16,
    "ChecklistItem": 48,
    "PillButton": 36,
    "CircleButton": 36,
    "TopTextBottomValue": 68,
    "TextBlock": 48,
}

# Keep tiny sub-pixel/rounding differences advisory. This matches the browser
# validator's visible-overflow tolerance while still rejecting a flex slot that
# is provably too small for a component's static lower bound.
_LAYOUT_VISUAL_TOLERANCE = 1.5

_PROGRESS_CIRCLE_SINGLE_RING_WIDTH = 52
_PROGRESS_CIRCLE_SINGLE_COMPACT_RING_WIDTH = 44
_PROGRESS_CIRCLE_SINGLE_CONTENT_GAP = 8
_PROGRESS_CIRCLE_SINGLE_MIN_TEXT_SLOT = 14
_PROGRESS_CIRCLE_SINGLE_MIN_WIDTH = (
    _PROGRESS_CIRCLE_SINGLE_RING_WIDTH
    + _PROGRESS_CIRCLE_SINGLE_CONTENT_GAP
    + _PROGRESS_CIRCLE_SINGLE_MIN_TEXT_SLOT
)


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)px\s*", value)
        if match:
            return float(match.group(1))
    return None


def _validate_action_slot_compatibility(
    root: JSXElement,
    decision: dict[str, Any] | None = None,
    expected_size: str | None = None,
    *,
    advisory_issues: list[tuple[str, str]] | None = None,
) -> None:
    """Reject action components placed in a slot for another button family."""
    issues: list[str] = []
    pattern = _canonical_layout_pattern((decision or {}).get("layoutPattern"))
    size = expected_size or root.props.get("size")
    is_type_zero = pattern == "0" or root.props.get("appearance") == "type0-gradient"
    if size == "2x2" and is_type_zero:
        business_components = [
            node.tag
            for node in _walk(root)
            if node.tag not in {"Card", "Stack", "Grid"}
        ]
        if len(business_components) != 1:
            rendered = ", ".join(business_components) or "none"
            issues.append(
                '2x2 layout "核心居中" must contain exactly one business component '
                "and cannot add a title, button, or parallel module; found: "
                + rendered
            )
    info_blocks = [node for node in _walk(root) if node.tag == "InfoBlock"]
    if size == "2x2" and info_blocks and pattern is not None and pattern != "3":
        issues.append('InfoBlock is only allowed in 2x2 layout "双信息块"')
    if size == "2x4" and info_blocks and pattern is not None and pattern not in {"14", "15", "15-R"}:
        issues.append(
            'InfoBlock is only allowed in 2x4 layouts "四槽宫格", '
            '"左内容右侧双槽", or "左侧双槽右内容" fixed slots'
        )
    if size == "2x2" and info_blocks:
        extra_business_components = [
            node.tag for node in _walk(root) if node.tag not in {"Card", "Stack", "Grid", "InfoBlock"}
        ]
        if extra_business_components:
            issues.append(
                "a 2x2 InfoBlock card may only contain its two InfoBlock business "
                "components; remove: " + ", ".join(dict.fromkeys(extra_business_components))
            )
    if info_blocks and advisory_issues is not None:
        appearance = root.props.get("appearance")
        if isinstance(appearance, str) and appearance.endswith("-soft"):
            # The theme name alone does not prove a rendering error. Keep
            # the color risk visible without rejecting an otherwise valid card.
            advisory_issues.append((
                "info-block-appearance-risk",
                f"InfoBlock on '{appearance}' may have low-contrast translucent backplates "
                "depending on the selected theme and content; "
                "appearance compatibility is advisory only, not a submission error.",
            ))

    def is_card_button_slot(node: JSXElement) -> bool:
        if node.tag == "CardButton":
            return True
        children = node.child_elements()
        return node.tag == "Stack" and len(children) == 1 and children[0].tag == "CardButton"

    if size == "2x4":
        for container in _walk(root):
            issues.extend(fixed_slot_dimension_errors(container))
            children = container.child_elements()
            direct_card_buttons = [child for child in children if child.tag == "CardButton"]
            if container.tag == "Card" and direct_card_buttons:
                issues.append(
                    "CardButton must be placed in a half-card Stack slot or a documented Grid cell"
                )
            if container.tag == "Stack" and direct_card_buttons and not (
                len(children) == 1 and len(direct_card_buttons) == 1
            ):
                issues.append(
                    "each CardButton in a Stack must be the only child of its own "
                    "explicit or flex-allocated slot; Grid cells are already slots"
                )
            if container.tag == "Grid" and (_grid_column_count(container) or 1) > 1:
                if any(fixed_slot_kind(child) is not None for child in children):
                    issues.extend(fixed_grid_errors(children, _grid_column_count(container)))
                    for axis in ("rowGap", "columnGap"):
                        gap = _number(container.props.get(axis, container.props.get("gap", 0)))
                        if gap is not None and gap != 12:
                            issues.append(f'2x4 layout "四槽宫格" {axis} must be 12vp; found {_vp(gap)}vp')
            elif (
                sum(is_card_button_slot(child) for child in children) >= 2
                and container.tag in {"Card", "Stack"}
                and container.props.get("direction", "column") == "row"
            ):
                issues.append(
                    'outside the documented "四槽宫格" Grid, 2x4 CardButton actions must '
                    "be stacked vertically; a single horizontal row is not allowed"
                )
    for node in _walk(root):
        width = _number(node.props.get("width"))
        height = _number(node.props.get("height"))
        if node.tag != "Stack" or width != height or width not in {36, 40}:
            continue
        if any(descendant.tag == "PillButton" for descendant in _walk(node) if descendant is not node):
            issues.append(
                f"a Stack with width={{{int(width)}}} height={{{int(height)}}} is a "
                "compact CircleButton action slot and "
                "cannot contain the fixed-width PillButton; use CircleButton or select a "
                "full-width PillButton layout"
            )
    if issues:
        raise ValidationError("; ".join(dict.fromkeys(issues)))


def _validate_progress_line_theme(root: JSXElement) -> None:
    """Keep generated progress components aligned with the Card background."""
    appearance = root.props.get("appearance")
    dark_surface = root.props.get("size") != "2x4" and isinstance(appearance, str) and (
        appearance.startswith("orb-") or appearance.endswith("-gradient")
    )
    issues: list[str] = []
    for node in _walk(root):
        if node.tag not in {"ProgressLine2", "H_BarChart"}:
            continue
        mode = node.props.get("mode")
        expected_mode = "dark" if dark_surface else "light"
        if mode != expected_mode:
            issues.append(
                f"{node.tag} on a {'dark' if dark_surface else 'light'} Card must use mode='{expected_mode}'"
            )
    if issues:
        raise ValidationError("; ".join(dict.fromkeys(issues)))


def _explicit_height(node: JSXElement) -> float | None:
    return _number(node.props.get("height"))


def _numeric_basis(node: JSXElement) -> float | None:
    return _number(node.props.get("basis"))


def _effective_min_height(node: JSXElement) -> float | None:
    explicit = _number(node.props.get("minHeight"))
    if explicit is not None:
        return explicit
    if _number(node.props.get("flex")) == 1:
        return 0
    if node.tag == "Stack" and any(
        child.tag == "TextBlock" for child in node.child_elements()
    ):
        return 0
    return None


def _height_lower_bound(node: JSXElement, value: float) -> float:
    return max(value, _effective_min_height(node) or 0)


def _vertical_padding(node: JSXElement) -> float:
    if node.tag == "Stack" and node.props.get("surface") == "backplate":
        return 16 if _BUDGET_CARD_SIZE.get() == "2x4" else 12
    if node.tag != "Card":
        return 0
    padding = node.props.get("padding", 12)
    value = _number(padding)
    if value is not None:
        return value * 2
    if isinstance(padding, dict):
        top = _number(padding.get("top", 0))
        bottom = _number(padding.get("bottom", 0))
        if top is not None and bottom is not None:
            return top + bottom
    return 0


def _margin_extent(node: JSXElement, start: str, end: str) -> float:
    return (_number(node.props.get(start)) or 0) + (_number(node.props.get(end)) or 0)


def _gap(node: JSXElement) -> float:
    return _number(node.props.get("gap", 0)) or 0


def _flex_weight(node: JSXElement) -> float:
    value = _number(node.props.get("flex"))
    return value if value is not None and value > 0 else 0


def _grid_column_count(node: JSXElement) -> int | None:
    columns = node.props.get("columns", 2)
    if isinstance(columns, int) and not isinstance(columns, bool) and columns > 0:
        return columns
    if isinstance(columns, str) and _TWO_COLUMN_GRID.fullmatch(columns):
        return 2
    return None


def _card_button_slot_dimensions(
    parent: JSXElement,
    child_index: int,
    ancestor: JSXElement | None = None,
) -> tuple[float | None, float | None]:
    """Return only statically provable CardButton parent-slot dimensions."""
    if parent.tag == "Stack":
        if ancestor:
            width = _number(preferred_axis_size(parent, ancestor, "width"))
        else:
            width = _number(parent.props.get("width"))
        height = _number(preferred_axis_size(parent, ancestor, "height")) if ancestor else _explicit_height(parent)
        return width, height
    if parent.tag != "Grid":
        return None, None

    columns = _grid_column_count(parent)
    if columns is None:
        return None, None
    width = _number(parent.props.get("width"))
    column_gap = _number(parent.props.get("columnGap", parent.props.get("gap", 0))) or 0
    if width is not None:
        template = parent.props.get("columns")
        if isinstance(template, str) and (match := _TWO_COLUMN_GRID.fullmatch(template)):
            fixed = float(match.group("fixed"))
            available = max(0, width - column_gap)
            column_widths = [fixed, max(0, available - fixed)]
            width = column_widths[child_index % columns]
        else:
            width = max(0, width - column_gap * max(0, columns - 1)) / columns

    height: float | None = None
    rows = parent.props.get("rows")
    row_count = (len(parent.child_elements()) + columns - 1) // columns
    if isinstance(rows, str):
        tokens = rows.split()
        if len(tokens) == row_count and all(re.fullmatch(r"\d+(?:\.\d+)?px", token) for token in tokens):
            height = float(tokens[child_index // columns][:-2])
    return width, height


def _minimum_height(node: JSXElement) -> float:
    """Return a safe, statically known lower bound for the node's height."""
    explicit = _explicit_height(node)
    if explicit is not None:
        return _height_lower_bound(node, explicit)
    if node.tag == "Icon":
        return _height_lower_bound(node, _number(node.props.get("size")) or 0)
    if node.tag == "SingleLineTitle":
        return _height_lower_bound(node, 16)
    if node.tag == "DoubleLineTitle":
        return _height_lower_bound(node, 40)
    if node.tag == "SecondaryBody":
        items = node.props.get("items")
        count = len(items) if isinstance(items, list) else 1
        rows = math.ceil(count / 2)
        return _height_lower_bound(node, 16 * rows + 2 * (rows - 1) if count > 2 else 19)
    if node.tag == "EmphasisText":
        return _height_lower_bound(
            node,
            24 + (2 if node.props.get("secondaryText") == "" else 18
                  if node.props.get("secondaryText") is not None else 0),
        )
    if node.tag == "ProgressLine2":
        return _height_lower_bound(node, 56)
    if node.tag == "TableText":
        items = node.props.get("items")
        count = len(items) if isinstance(items, list) else 0
        return _height_lower_bound(node, count * 16 + max(0, count - 1) * 2)
    if node.tag == "TopTextBottomValue":
        return _height_lower_bound(node, 68)
    if node.tag == "CardButton":
        return _height_lower_bound(node, 48)
    if node.tag == "H_BarChart":
        items = node.props.get("items")
        count = len(items) if isinstance(items, list) else 0
        item_height = 28 if count == 3 else 30
        return _height_lower_bound(node, count * item_height + max(0, count - 1) * 11)
    if node.tag == "InfoBlock":
        return _height_lower_bound(node, 57 if _BUDGET_CARD_SIZE.get() == "2x4" else 63)
    if node.tag == "ProgressCircle":
        diameter = 96 if node.props.get("size", "sm") == "md" else 44
        return _height_lower_bound(node, diameter + 2 + 14)
    if node.tag == "ProgressCircleSingle":
        if node.props.get("size") == "compact":
            return _height_lower_bound(
                node,
                46 if node.props.get("secondaryLabel") is not None else 44,
            )
        return _height_lower_bound(node, 52)
    if node.tag == "NumericRatioStack":
        return _height_lower_bound(
            node,
            16 if node.props.get("direction", "column") == "row" else 56,
        )
    if node.tag == "EventCard":
        items = node.props.get("items")
        if isinstance(items, list):
            item_gap = 4 if len(items) > 1 else 0
            return _height_lower_bound(
                node,
                sum(
                    32 if node.props.get("density") == "compact"
                    else 50 if isinstance(item, dict) and item.get("location") is not None
                    else 34
                    for item in items
                ) + item_gap,
            )
        if node.props.get("density") == "compact":
            return _height_lower_bound(node, 32)
        return _height_lower_bound(
            node,
            18 + 16 + (16 if node.props.get("location") is not None else 0),
        )
    intrinsic = _INTRINSIC_HEIGHTS.get(node.tag)
    if intrinsic is not None:
        return _height_lower_bound(node, float(intrinsic))
    if node.tag == "Grid":
        row_gap = _number(node.props.get("rowGap", node.props.get("gap", 0))) or 0
        explicit_rows = node.props.get("rows")
        if isinstance(explicit_rows, str):
            values = re.fullmatch(r"\s*(\d+(?:\.\d+)?px)(?:\s+(\d+(?:\.\d+)?px))*\s*", explicit_rows)
            if values:
                heights = [float(value[:-2]) for value in re.findall(r"\d+(?:\.\d+)?px", explicit_rows)]
                return _height_lower_bound(
                    node,
                    sum(heights) + row_gap * max(0, len(heights) - 1),
                )
        children = node.child_elements()
        columns = _grid_column_count(node)
        if columns is None:
            return _height_lower_bound(node, 0)
        row_heights = [
            max(
                (
                    _minimum_height(child) + _margin_extent(child, "mt", "mb")
                    for child in children[index:index + columns]
                ),
                default=0,
            )
            for index in range(0, len(children), columns)
        ]
        return _height_lower_bound(
            node,
            sum(row_heights) + row_gap * max(0, len(row_heights) - 1),
        )
    relative_overlay = node.props.get("position") == "relative" and any(
        child.props.get("position") == "absolute" for child in node.child_elements()
    )
    if node.tag != "Stack" or relative_overlay:
        return _height_lower_bound(node, 0)
    children = node.child_elements()
    if not children:
        return _height_lower_bound(node, 0)
    heights = [_minimum_height(child) + _margin_extent(child, "mt", "mb") for child in children]
    if node.props.get("direction", "column") == "row":
        return _height_lower_bound(
            node,
            max(heights, default=0) + _vertical_padding(node),
        )
    return _height_lower_bound(
        node,
        sum(heights) + _gap(node) * max(0, len(children) - 1) + _vertical_padding(node),
    )


def _non_shrinking_auto_height(node: JSXElement) -> float:
    """Return the deterministic auto-size reservation of a flex: 0 child."""
    explicit = _explicit_height(node)
    if explicit is not None:
        return _height_lower_bound(node, explicit)
    if node.tag == "TextBlock":
        # The runtime declares flex-basis: 64px, min-height: 48px. A direct
        # flex: 0 wrapper uses the 64px auto size and cannot shrink to 48px.
        return _height_lower_bound(node, 64)
    if node.tag != "Stack":
        return _minimum_height(node)
    children = [
        child
        for child in node.child_elements()
        if child.props.get("position") != "absolute"
    ]
    if not children:
        return _minimum_height(node)
    heights = [
        _non_shrinking_auto_height(child) + _margin_extent(child, "mt", "mb")
        for child in children
    ]
    if node.props.get("direction", "column") == "row":
        content_height = max(heights, default=0)
    else:
        content_height = sum(heights) + _gap(node) * max(0, len(heights) - 1)
    return _height_lower_bound(
        node,
        content_height + _vertical_padding(node),
    )


def _vp(value: float) -> str:
    numeric = float(value)
    return str(int(numeric)) if numeric.is_integer() else f"{numeric:g}"


def _vertical_overflow_message(path: str, required: float, available: float) -> str:
    return (
        f"{path} requires at least {_vp(required)}vp vertically but only "
        f"{_vp(available)}vp is available; reduce or regroup content instead "
        "of relying on overflow, flex shrink, or adjacent gaps"
    )


def _flex_vertical_risk_message(path: str, required: float, available: float) -> str:
    return (
        f"{path} needs at least {_vp(required)}vp vertically while its computed flex "
        f"share is {_vp(available)}vp; the parent has enough total vertical budget, "
        "but this local allocation may not fit without shrinking or overlap"
    )


def _relative_flow_layer(node: JSXElement) -> JSXElement | None:
    children = [child for child in node.child_elements() if child.props.get("position") != "absolute"]
    if not children:
        return None
    props = {name: node.props[name] for name in ("direction", "gap", "align", "justify", "wrap") if name in node.props}
    return JSXElement(tag="Stack", props=props, children=children, offset=node.offset)


def _contains_component(node: JSXElement, tag: str) -> bool:
    return any(descendant.tag == tag for descendant in _walk(node))


def _absolute_axis_interval(
    node: JSXElement,
    available: float,
    *,
    start_prop: str,
    end_prop: str,
    size_prop: str,
    fallback_size: float | None = None,
) -> tuple[float, float] | None:
    start = _number(node.props.get(start_prop))
    end = _number(node.props.get(end_prop))
    size = _number(node.props.get(size_prop))
    if size is None and start is not None and end is not None:
        size = max(0, available - start - end)
    elif size is None and (start is not None or end is not None):
        size = fallback_size
    result: tuple[float, float] | None = None
    if size is not None:
        if start is not None:
            origin = start
        elif end is not None:
            origin = available - end - size
        else:
            origin = None
        if origin is not None:
            result = (origin, origin + size)
    return result


def _axis_overlap(first: tuple[float, float], second: tuple[float, float]) -> float:
    return min(first[1], second[1]) - max(first[0], second[0])


def _collect_absolute_rectangles(
    children: list[JSXElement],
    available_width: float,
    available_height: float,
) -> tuple[
    list[tuple[int, JSXElement, tuple[float, float], tuple[float, float]]],
    list[tuple[int, tuple[float, float], tuple[float, float]]],
]:
    rectangles: list[tuple[int, JSXElement, tuple[float, float], tuple[float, float]]] = []
    estimated: list[tuple[int, tuple[float, float], tuple[float, float]]] = []
    for index, child in enumerate(children, start=1):
        horizontal = _absolute_axis_interval(
            child,
            available_width,
            start_prop="left",
            end_prop="right",
            size_prop="width",
        )
        if horizontal is None:
            continue
        vertical = _absolute_axis_interval(
            child,
            available_height,
            start_prop="top",
            end_prop="bottom",
            size_prop="height",
            fallback_size=_minimum_height(child),
        )
        if vertical is not None:
            rectangles.append((index, child, horizontal, vertical))
        estimated_height = _estimated_auto_height(
            child,
            horizontal[1] - horizontal[0],
        )
        estimated_vertical = _absolute_axis_interval(
            child,
            available_height,
            start_prop="top",
            end_prop="bottom",
            size_prop="height",
            fallback_size=estimated_height,
        )
        if estimated_vertical is not None:
            estimated.append((index, horizontal, estimated_vertical))
    return rectangles, estimated


def _validate_proven_absolute_overlaps(
    node: JSXElement,
    path: str,
    rectangles: list[tuple[int, JSXElement, tuple[float, float], tuple[float, float]]],
    issues: list[str],
) -> set[tuple[int, int]]:
    overlaps: set[tuple[int, int]] = set()
    for left_index, (first_index, first, first_x, first_y) in enumerate(rectangles):
        for second_number, second, second_x, second_y in rectangles[left_index + 1:]:
            if _axis_overlap(first_x, second_x) <= 1e-9:
                continue
            vertical_overlap = _axis_overlap(first_y, second_y)
            if vertical_overlap > 1e-9:
                overlaps.add((first_index, second_number))
                issues.append(
                    f"{path}/<Stack>[{first_index}] overlaps "
                    f"{path}/<Stack>[{second_number}] by {_vp(vertical_overlap)}vp vertically"
                )
                continue
            first_is_button = _contains_component(first, "PillButton")
            second_is_button = _contains_component(second, "PillButton")
            backplate_button_gap = (
                node.props.get("surface") == "backplate"
                and first_is_button != second_is_button
            )
            opposing_edge_gap = _uses_opposing_vertical_edges(first, second)
            if not backplate_button_gap and not opposing_edge_gap:
                continue
            gap = max(second_y[0] - first_y[1], first_y[0] - second_y[1])
            if gap < 8 - 1e-9:
                if backplate_button_gap:
                    issues.append(
                        f"{path} upper content and backplate PillButton require an 8vp gap; "
                        f"found {_vp(gap)}vp"
                    )
                else:
                    issues.append(
                        f"{path} opposing absolute content regions require an 8vp gap; "
                        f"found {_vp(gap)}vp"
                    )
    return overlaps


def _uses_opposing_vertical_edges(first: JSXElement, second: JSXElement) -> bool:
    first_uses_top = first.props.get("top") is not None
    first_uses_bottom = first.props.get("bottom") is not None
    second_uses_top = second.props.get("top") is not None
    second_uses_bottom = second.props.get("bottom") is not None
    first_from_top = first_uses_top and not first_uses_bottom
    first_from_bottom = first_uses_bottom and not first_uses_top
    second_from_top = second_uses_top and not second_uses_bottom
    second_from_bottom = second_uses_bottom and not second_uses_top
    return (first_from_top and second_from_bottom) or (
        first_from_bottom and second_from_top
    )


def _estimated_flow_height_risk_message(
    path: str,
    required: float,
    available: float,
) -> str:
    return (
        f"{path} may need about {_vp(required)}vp vertically after text wrapping "
        f"while only {_vp(available)}vp is available; text height is font-dependent, "
        "and the estimated content does not fit"
    )


def _validate_estimated_absolute_overlaps(
    path: str,
    rectangles: list[tuple[int, tuple[float, float], tuple[float, float]]],
    proven_overlaps: set[tuple[int, int]],
    advisory_issues: list[str] | None,
) -> None:
    if advisory_issues is None:
        return
    for left_index, first_entry in enumerate(rectangles):
        first_index, first_x, first_y = first_entry
        for second_entry in rectangles[left_index + 1:]:
            second_number, second_x, second_y = second_entry
            if (first_index, second_number) in proven_overlaps:
                continue
            if _axis_overlap(first_x, second_x) <= 1e-9:
                continue
            vertical_overlap = _axis_overlap(first_y, second_y)
            if vertical_overlap <= 1e-9:
                continue
            message = (
                f"{path}/<Stack>[{first_index}] and {path}/<Stack>[{second_number}] "
                f"have about {_vp(vertical_overlap)}vp vertical overlap after likely "
                "text wrapping"
            )
            advisory_issues.append(
                message
                + "; text height is font-dependent, but the estimated regions overlap"
            )


def _validate_absolute_sibling_geometry(
    node: JSXElement,
    available_width: float | None,
    available_height: float,
    path: str,
    issues: list[str],
    advisory_issues: list[str] | None,
) -> None:
    absolute_children = [
        child for child in node.child_elements() if child.props.get("position") == "absolute"
    ]
    if node.props.get("surface") == "backplate" and any(
        _contains_component(child, "PillButton") for child in absolute_children
    ):
        if any(child.props.get("position") != "absolute" for child in node.child_elements()):
            issues.append(
                f"{path} with an absolute backplate PillButton must place upper content "
                "in a separate absolute region so the required 8vp gap is deterministic"
            )
    if available_width is None:
        return
    proven, estimated = _collect_absolute_rectangles(
        absolute_children,
        available_width,
        available_height,
    )
    proven_overlaps = _validate_proven_absolute_overlaps(
        node,
        path,
        proven,
        issues,
    )
    _validate_estimated_absolute_overlaps(
        path,
        estimated,
        proven_overlaps,
        advisory_issues,
    )


def _validate_relative_stack(
    node: JSXElement,
    available: float,
    flow_available: float,
    available_width: float | None,
    path: str,
    issues: list[str],
    advisory_issues: list[str] | None,
) -> None:
    flow = _relative_flow_layer(node)
    if flow is not None:
        flow_width = (
            max(0, available_width - _horizontal_padding(node))
            if available_width is not None
            else None
        )
        _validate_vertical_container(
            flow,
            flow_available,
            f"{path}/<flow>",
            issues,
            available_width=flow_width,
            advisory_issues=advisory_issues,
        )
    absolute_children = [
        child
        for child in node.child_elements()
        if child.props.get("position") == "absolute"
    ]
    for index, child in enumerate(absolute_children, start=1):
        child_path = f"{path}/<Stack>[{index}]"
        top = _number(child.props.get("top")) or 0
        bottom = _number(child.props.get("bottom")) or 0
        has_top = child.props.get("top") is not None
        has_bottom = child.props.get("bottom") is not None
        margins = _margin_extent(child, "mt", "mb")
        height = _explicit_height(child)
        if height is None:
            if has_top and has_bottom:
                height = max(0, available - top - bottom - margins)
            else:
                height = _minimum_height(child)
            required = top + height + bottom + margins
        elif has_top:
            # CSS resolves top + height first and ignores an over-constraining
            # bottom value for a non-replaced absolutely positioned box.
            required = top + height + margins
        else:
            required = height + bottom + margins
        if required > available + 1e-9:
            issues.append(_vertical_overflow_message(child_path, required, available))
        child_width = _number(child.props.get("width"))
        if child_width is None and available_width is not None:
            left = _number(child.props.get("left"))
            right = _number(child.props.get("right"))
            if left is not None and right is not None:
                child_width = max(0, available_width - left - right)
        _validate_vertical_container(
            child,
            height,
            child_path,
            issues,
            available_width=child_width,
            advisory_issues=advisory_issues,
        )
    _validate_absolute_sibling_geometry(
        node,
        available_width,
        available,
        path,
        issues,
        advisory_issues,
    )


def _validate_vertical_container(
    node: JSXElement,
    available: float,
    path: str,
    issues: list[str],
    *,
    available_width: float | None = None,
    advisory_issues: list[str] | None = None,
) -> None:
    explicit = _explicit_height(node)
    minimum = _effective_min_height(node)
    declared = max(explicit or 0, minimum or 0) if explicit is not None or minimum is not None else None
    if declared is not None and declared > available + 1e-9:
        issues.append(_vertical_overflow_message(path, declared, available))
        available = declared
    inner = max(0, available - _vertical_padding(node))
    explicit_width = _number(node.props.get("width"))
    node_width = explicit_width if explicit_width is not None else available_width
    inner_width = (
        max(0, node_width - _horizontal_padding(node))
        if node_width is not None
        else None
    )
    if node.tag == "Stack" and any(child.tag == "CardButton" for child in node.child_elements()):
        if not 48 <= inner <= 64:
            issues.append(
                f"{path} CardButton parent slot height must be between 48vp and 64vp; "
                f"found {_vp(inner)}vp"
            )
        if inner_width is not None and inner_width > 132 + 1e-9:
            issues.append(
                f"{path} CardButton parent slot width must be at most 132vp; "
                f"found {_vp(inner_width)}vp"
            )
        if inner_width is not None and inner_width < inner - 1e-9:
            issues.append(
                f"{path} CardButton parent slot must be at least as wide as it is tall; "
                f"found {_vp(inner_width)}×{_vp(inner)}vp"
            )
    has_absolute_children = any(
        child.props.get("position") == "absolute" for child in node.child_elements()
    )
    is_overlay_container = (
        node.tag == "Card"
        or (node.tag == "Stack" and node.props.get("position") == "relative")
    ) and has_absolute_children
    if is_overlay_container:
        _validate_relative_stack(
            node,
            available,
            inner,
            node_width,
            path,
            issues,
            advisory_issues,
        )
        return
    if node.tag == "Grid":
        required = _minimum_height(node)
        if required > available + 1e-9:
            issues.append(_vertical_overflow_message(path, required, available))
        columns = _grid_column_count(node)
        if columns is None:
            return
        children = node.child_elements()
        row_count = (len(children) + columns - 1) // columns
        row_gap = _number(node.props.get("rowGap", node.props.get("gap", 0))) or 0
        rows = node.props.get("rows")
        row_heights: list[float] = []
        if isinstance(rows, str):
            tokens = rows.split()
            if len(tokens) == row_count and all(re.fullmatch(r"\d+(?:\.\d+)?px", token) for token in tokens):
                row_heights = [float(token[:-2]) for token in tokens]
        if not row_heights:
            available_rows = max(0, inner - row_gap * max(0, row_count - 1))
            row_heights = [available_rows / row_count] * row_count if row_count else []
        total = sum(row_heights) + row_gap * max(0, len(row_heights) - 1)
        if total > available + 1e-9:
            issues.append(_vertical_overflow_message(path, total, available))
        for index, child in enumerate(children, start=1):
            row_height = row_heights[(index - 1) // columns]
            column_width = None
            if inner_width is not None:
                column_gap = _number(
                    node.props.get("columnGap", node.props.get("gap", 0))
                ) or 0
                available_columns = max(
                    0,
                    inner_width - column_gap * max(0, columns - 1),
                )
                template = node.props.get("columns")
                if isinstance(template, str) and (
                    match := _TWO_COLUMN_GRID.fullmatch(template)
                ):
                    fixed = float(match.group("fixed"))
                    column_widths = [fixed, max(0, available_columns - fixed)]
                    column_width = column_widths[(index - 1) % columns]
                else:
                    column_width = available_columns / columns
            margins = _margin_extent(child, "mt", "mb")
            required_child = _minimum_height(child) + margins
            child_path = f"{path}/<{child.tag}>[{index}]"
            if required_child > row_height + 1e-9:
                issues.append(_vertical_overflow_message(child_path, required_child, row_height))
            if child.tag == "CardButton" and not 48 <= row_height <= 64:
                issues.append(
                    f"{child_path} CardButton Grid row height must be between 48vp and 64vp; "
                    f"found {_vp(row_height)}vp"
                )
            if child.tag == "CardButton" and column_width is not None:
                if column_width > 132 + 1e-9:
                    issues.append(
                        f"{child_path} CardButton Grid column width must be at most 132vp; "
                        f"found {_vp(column_width)}vp"
                    )
                if column_width < row_height - 1e-9:
                    issues.append(
                        f"{child_path} CardButton Grid cell must be at least as "
                        "wide as it is tall; "
                        f"found {_vp(column_width)}×{_vp(row_height)}vp"
                    )
            if child.tag in {"Stack", "Grid"}:
                _validate_vertical_container(
                    child,
                    max(0, row_height - margins),
                    child_path,
                    issues,
                    available_width=column_width,
                    advisory_issues=advisory_issues,
                )
        return

    children = node.child_elements()
    if not children:
        return
    if node.props.get("direction", "column") == "row":
        for index, child in enumerate(children, start=1):
            margins = _margin_extent(child, "mt", "mb")
            child_path = f"{path}/<{child.tag}>[{index}]"
            required_child = _minimum_height(child) + margins
            if required_child > inner + 1e-9:
                issues.append(_vertical_overflow_message(child_path, required_child, inner))
            child_height = _explicit_height(child) or max(0, inner - margins)
            if child_height + margins > inner + 1e-9:
                issues.append(
                    _vertical_overflow_message(
                        child_path,
                        child_height + margins,
                        inner,
                    )
                )
            if child.tag in {"Stack", "Grid"}:
                child_width = _number(child.props.get("width"))
                if child_width is None:
                    child_width = _numeric_basis(child)
                _validate_vertical_container(
                    child,
                    child_height,
                    child_path,
                    issues,
                    available_width=child_width,
                    advisory_issues=advisory_issues,
                )
        return

    gap_total = _gap(node) * max(0, len(children) - 1)
    fixed_total = gap_total
    flex_children: list[tuple[int, JSXElement, float]] = []
    reservations: dict[int, float] = {}
    for index, child in enumerate(children, start=1):
        margins = _margin_extent(child, "mt", "mb")
        basis = _numeric_basis(child)
        weight = 0 if basis is not None else _flex_weight(child)
        if weight:
            flex_children.append((index, child, weight))
            fixed_total += margins
            continue
        if child.props.get("height") == "full":
            reservation = inner
        elif basis is not None:
            reservation = max(basis, _effective_min_height(child) or 0)
        elif _number(child.props.get("flex")) == 0:
            reservation = _non_shrinking_auto_height(child)
        else:
            reservation = _minimum_height(child)
        reservations[index] = reservation
        fixed_total += reservation + margins

    minimum_total = fixed_total + sum(
        _minimum_height(child) for _, child, _ in flex_children
    )
    parent_can_close = minimum_total <= inner + 1e-9
    if not parent_can_close:
        issues.append(_vertical_overflow_message(path, minimum_total, inner))

    can_estimate_flow = (
        parent_can_close
        and node.tag == "Stack"
        and len(children) >= 2
    )
    if can_estimate_flow and inner_width is not None and advisory_issues is not None:
        estimated_total = gap_total + sum(
            _estimated_auto_height(
                child,
                _number(child.props.get("width")) or inner_width,
            )
            + _margin_extent(child, "mt", "mb")
            for child in children
        )
        if estimated_total > inner + _LAYOUT_VISUAL_TOLERANCE:
            advisory_issues.append(
                _estimated_flow_height_risk_message(
                    path,
                    estimated_total,
                    inner,
                )
            )

    remaining = max(0, inner - fixed_total)
    total_weight = sum(weight for _, _, weight in flex_children)
    deterministic_flex_allocation = (
        bool(flex_children)
        and (node.tag == "Card" or _explicit_height(node) is not None)
        and all(
            _effective_min_height(child) == 0
            and child.props.get("height") is None
            for _, child, _ in flex_children
        )
    )
    for index, child in enumerate(children, start=1):
        if child.tag not in {"Stack", "Grid"}:
            continue
        flex_entry = next((entry for entry in flex_children if entry[0] == index), None)
        if flex_entry is not None:
            child_available = remaining * flex_entry[2] / total_weight
            child_minimum = _minimum_height(child)
            child_path = f"{path}/<{child.tag}>[{index}]"
            if parent_can_close and child_minimum > child_available + 1e-9:
                shortfall = child_minimum - child_available
                if (
                    deterministic_flex_allocation
                    and shortfall > _LAYOUT_VISUAL_TOLERANCE
                ):
                    issues.append(
                        _vertical_overflow_message(
                            child_path,
                            child_minimum,
                            child_available,
                        )
                    )
                elif advisory_issues is not None:
                    advisory_issues.append(
                        _flex_vertical_risk_message(
                            child_path,
                            child_minimum,
                            child_available,
                        )
                    )
            if parent_can_close:
                child_available = max(child_available, child_minimum)
        else:
            child_available = reservations[index]
        child_width = _number(child.props.get("width"))
        if child_width is None:
            child_width = inner_width
        _validate_vertical_container(
            child,
            child_available,
            f"{path}/<{child.tag}>[{index}]",
            issues,
            available_width=child_width,
            advisory_issues=advisory_issues,
        )


def _budget_tree_with_resolved_basis(root: JSXElement) -> JSXElement:
    """Use a private tree so budgets never read a size overridden by basis."""
    def visit(node: JSXElement, parent: JSXElement | None) -> JSXElement:
        props = node.props
        in_flex_parent = parent is not None and parent.tag in {"Card", "Stack"}
        if in_flex_parent and node.props.get("position") != "absolute":
            has_basis = _numeric_basis(node) is not None
        else:
            has_basis = False
        if has_basis:
            axis = "width" if parent.props.get("direction", "column") == "row" else "height"
            if axis in props:
                props = {**props, axis: preferred_axis_size(node, parent, axis)}
        return replace(node, props=props, children=[
            visit(child, node) if isinstance(child, JSXElement) else child
            for child in node.children
        ])

    return visit(root, None)


def _validate_layout_budget(
    root: JSXElement,
    advisory_issues: list[str] | None = None,
) -> None:
    root = _budget_tree_with_resolved_basis(root)
    dimensions = card_dimensions(root.props.get("size"))
    if dimensions is None:
        return
    height = _number(dimensions[1])
    width = _number(dimensions[0])
    if height is not None:
        issues: list[str] = []
        token = _BUDGET_CARD_SIZE.set(root.props.get("size"))
        try:
            _validate_vertical_container(
                root,
                height,
                "<Card>",
                issues,
                available_width=width,
                advisory_issues=advisory_issues,
            )
        finally:
            _BUDGET_CARD_SIZE.reset(token)
        if issues:
            raise LayoutBudgetError("; ".join(dict.fromkeys(issues)))


def _raise_estimated_layout_risks(estimated_issues: list[str]) -> None:
    """Promote estimated vertical closure/overlap risks to blocking errors."""
    unique = list(dict.fromkeys(estimated_issues))
    estimated_issues.clear()
    if unique:
        raise LayoutBudgetError("; ".join(unique))


def _horizontal_padding(node: JSXElement) -> float:
    if node.tag == "Stack" and node.props.get("surface") == "backplate":
        return 16 if _BUDGET_CARD_SIZE.get() == "2x4" else 12
    if node.tag != "Card":
        return 0
    padding = node.props.get("padding", 12)
    value = _number(padding)
    if value is not None:
        return value * 2
    if isinstance(padding, dict):
        left = _number(padding.get("left", 0))
        right = _number(padding.get("right", 0))
        if left is not None and right is not None:
            return left + right
    return 0


def _declared_width(
    node: JSXElement,
    available: float,
    *,
    inside_backplate: bool = False,
) -> float | None:
    width = node.props.get("width")
    if width == "full":
        declared = available
    else:
        declared = _number(width)
    if declared is None:
        return None
    return declared


def _minimum_width(
    node: JSXElement,
    *,
    inside_backplate: bool = False,
) -> float:
    declared = max(
        _number(node.props.get("minWidth")) or 0,
        _number(node.props.get("width")) or 0,
    )
    intrinsic = {
        "CircleButton": 36,
        "PillButton": (
            (116 if _BUDGET_CARD_SIZE.get() == "2x4" else 126)
            if inside_backplate
            else (132 if _BUDGET_CARD_SIZE.get() == "2x4" else 126)
        ),
        "NumericRatio": 20,
        "NumericRatioStack": 76 if node.props.get("direction", "column") == "row" else 20,
        "InfoBlock": 132 if _BUDGET_CARD_SIZE.get() == "2x4" else 134,
        "TopTextBottomValue": 276,
    }.get(node.tag, 0)
    if node.tag == "TextBlock":
        items = node.props.get("items")
        count = len(items) if isinstance(items, list) else 0
        intrinsic = count * 64 + max(0, count - 1) * 8
    if node.tag == "ProgressCircleSingle":
        # The required label needs one contract-defined 14vp text slot in
        # addition to the fixed ring and gap. Longer text remains advisory.
        ring_width = (
            _PROGRESS_CIRCLE_SINGLE_COMPACT_RING_WIDTH
            if node.props.get("size") == "compact"
            else _PROGRESS_CIRCLE_SINGLE_RING_WIDTH
        )
        intrinsic = (
            ring_width
            + _PROGRESS_CIRCLE_SINGLE_CONTENT_GAP
            + _PROGRESS_CIRCLE_SINGLE_MIN_TEXT_SLOT
        )
    if node.tag == "ProgressCircle":
        intrinsic = 96 if node.props.get("size", "sm") == "md" else 44
    own_minimum = max(declared, intrinsic)
    is_overlay = node.props.get("position") == "relative" and any(
        child.props.get("position") == "absolute" for child in node.child_elements()
    )
    if node.tag == "Stack" and not is_overlay:
        children = [
            child
            for child in node.child_elements()
            if child.props.get("position") != "absolute"
        ]
        if children:
            children_inside_backplate = inside_backplate or node.props.get("surface") == "backplate"
            child_widths = [
                _minimum_width(child, inside_backplate=children_inside_backplate)
                + _margin_extent(child, "ml", "mr")
                for child in children
            ]
            if node.props.get("direction", "column") == "row":
                content_minimum = sum(child_widths) + _gap(node) * max(0, len(children) - 1)
            else:
                content_minimum = max(child_widths, default=0)
            own_minimum = max(own_minimum, content_minimum + _horizontal_padding(node))
    elif node.tag == "Grid":
        children = node.child_elements()
        columns = _grid_column_count(node)
        if children and columns:
            column_minimums = [0.0] * columns
            for index, child in enumerate(children):
                column = index % columns
                column_minimums[column] = max(
                    column_minimums[column],
                    _minimum_width(child, inside_backplate=inside_backplate)
                    + _margin_extent(child, "ml", "mr"),
                )
            gap = _number(node.props.get("columnGap", node.props.get("gap", 0))) or 0
            own_minimum = max(
                own_minimum,
                sum(column_minimums) + gap * max(0, columns - 1),
            )
    return own_minimum


def _horizontal_overflow_message(path: str, required: float, available: float) -> str:
    return f"{path} requires at least {_vp(required)}vp horizontally but only {_vp(available)}vp is available"


def _estimated_text_width(value: Any, font_size: float) -> float:
    if value is None or isinstance(value, bool):
        return 0
    text_value = str(value)
    units = 0.0
    for char in text_value:
        if char.isspace():
            units += 0.45
        elif ord(char) > 127:
            units += 1.0
        elif char.isupper() or char.isdigit():
            units += 0.65
        else:
            units += 0.55
    return units * font_size


def _segmented_text(node: JSXElement, content_prop: str) -> str:
    items = node.props.get("items")
    if not isinstance(items, list):
        value = node.props.get(content_prop)
        return str(value) if value is not None else ""
    separator = node.props.get("separator", " ｜ ")
    separator_text = separator if isinstance(separator, str) else " ｜ "
    parts: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        label = item.get("label")
        value = item.get("value")
        parts.append(
            (str(label) if label is not None else "")
            + (str(value) if value is not None else "")
        )
    return separator_text.join(parts)


def _estimated_wrapped_lines(value: Any, font_size: float, width: float) -> int:
    if width <= 0 or value is None:
        return 1
    estimated_width = _estimated_text_width(value, font_size)
    return max(1, math.ceil(estimated_width / width))


def _estimated_text_component_height(
    node: JSXElement,
    available_width: float,
) -> float | None:
    if node.tag == "EmphasizedData":
        required_width = _emphasized_data_width(node)
        lines = (
            max(1, math.ceil(required_width / available_width))
            if available_width > 0
            else 1
        )
        return _height_lower_bound(node, lines * 38)
    if node.tag == "EventCard":
        items = node.props.get("items")
        if isinstance(items, list):
            heights = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                if node.props.get("density") == "compact":
                    heights.append(32)
                    continue
                content_width = max(1, available_width - 15)
                lines = min(2, _estimated_wrapped_lines(item.get("title"), 14, content_width))
                heights.append(lines * 18 + 16 + (16 if item.get("location") is not None else 0))
            item_gap = 4 if len(heights) > 1 else 0
            return _height_lower_bound(node, sum(heights) + item_gap)
        if node.props.get("density") == "compact":
            return _height_lower_bound(node, 32)
        content_width = max(1, available_width - 15)
        lines = _estimated_wrapped_lines(
            node.props.get("title"),
            14,
            content_width,
        )
        lines = min(2, lines)
        height = lines * 18 + 16
        if node.props.get("location") is not None:
            height += 16
        return _height_lower_bound(node, height)
    if node.tag == "SecondaryBody":
        items = node.props.get("items")
        if not isinstance(items, list):
            return _height_lower_bound(node, 19)
        # JSX chooses whole-field groups using 14px measurements, then uses
        # 12px typography if multiple groups or an overlong field are present.
        # Keep this font-dependent estimate advisory, not an A2UI layout plan.
        fields = [_segmented_text(
            JSXElement(node.tag, {"items": [item]}, []), "body",
        ) for item in items]
        separator = node.props.get("separator", " ｜ ")
        separator = separator if isinstance(separator, str) else " ｜ "
        widths = [_estimated_text_width(field, 14) for field in fields]
        rows: list[str] = []
        index = 0
        while index < len(fields):
            pair_fits = (
                index + 1 < len(fields)
                and widths[index] + _estimated_text_width(separator, 14) + widths[index + 1]
                <= available_width + 0.5
            )
            rows.append(separator.join(fields[index:index + 2]) if pair_fits else fields[index])
            index += 2 if pair_fits else 1
        multiline = len(items) > 2 or len(rows) > 1 or any(width > available_width + 0.5 for width in widths)
        font_size, line_height = (12, 16) if multiline else (14, 19)
        total = sum(_estimated_wrapped_lines(row, font_size, available_width) * line_height for row in rows)
        return _height_lower_bound(node, total + 2 * max(0, len(rows) - 1))
    return None


def _estimated_auto_height(node: JSXElement, available_width: float) -> float:
    """Estimate font-dependent auto height for conservative layout rejection."""
    explicit = _explicit_height(node)
    if explicit is not None:
        return _height_lower_bound(node, explicit)
    minimum = _minimum_height(node)
    text_component_height = _estimated_text_component_height(node, available_width)
    if text_component_height is not None:
        return text_component_height
    if node.tag != "Stack":
        return minimum
    children = [
        child
        for child in node.child_elements()
        if child.props.get("position") != "absolute"
    ]
    if not children:
        return minimum
    inner_width = max(0, available_width - _horizontal_padding(node))
    heights: list[float] = []
    for child in children:
        child_width = _number(child.props.get("width"))
        if child_width is None:
            child_width = inner_width
        child_height = _estimated_auto_height(child, child_width)
        heights.append(child_height + _margin_extent(child, "mt", "mb"))
    if node.props.get("direction", "column") == "row":
        content_height = max(heights, default=0)
    else:
        content_height = sum(heights) + _gap(node) * max(0, len(heights) - 1)
    estimated = content_height + _vertical_padding(node)
    return _height_lower_bound(node, max(minimum, estimated))


def _progress_circle_single_width_estimate(node: JSXElement) -> float:
    """Estimate the non-shrinkable ring + text width used by the runtime."""
    three_lines = node.props.get("secondaryLabel") is not None
    display_value = node.props.get("displayValue")
    if display_value is None:
        value = node.props.get("value")
        if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
            display_value = f"{int(max(0, min(100, float(value))))}%"
        else:
            display_value = value
    text_width = max(
        _estimated_text_width(node.props.get("label"), 14),
        _estimated_text_width(display_value, 10 if three_lines else 12),
        _estimated_text_width(node.props.get("secondaryLabel"), 10),
    )
    return 52 + 8 + text_width


def _emphasized_data_width(node: JSXElement) -> float:
    items = node.props.get("items")
    if not isinstance(items, list):
        items = [{"value": node.props.get("value"), "unit": node.props.get("unit")}]
    required = 0.0
    visible_items = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        if visible_items:
            required += 2
        required += _estimated_text_width(item.get("value"), 38)
        if item.get("unit") is not None:
            required += 2 + _estimated_text_width(item.get("unit"), 12)
        visible_items += 1
    return required


def _horizontal_text_risk_message(path: str, required: float, available: float) -> str:
    return (
        f"{path} EmphasizedData main value may need about {_vp(required)}vp while "
        f"the slot provides {_vp(available)}vp; this is a font-dependent estimate, "
        "so verify the rendered result instead of treating it as proven overflow"
    )


def _progress_circle_single_width_risk_message(
    path: str,
    required: float,
    available: float,
) -> str:
    return (
        f"{path} ProgressCircleSingle may need about {_vp(required)}vp while "
        f"the slot provides {_vp(available)}vp; the text group does not shrink, "
        "but this width is font-dependent, so verify it in the browser instead of "
        "treating it as proven overflow"
    )


def _wrapping_text_candidates(node: JSXElement) -> list[tuple[str, object, float]]:
    if node.tag == "DoubleLineTitle":
        return [("secondaryInfo", node.props.get("secondaryInfo"), 12)]
    if node.tag == "SecondaryBody":
        items = node.props.get("items")
        if not isinstance(items, list):
            return []
        font_size = 12 if len(items) > 2 else 14
        return [
            (f"items[{index}:{index + 2}]", _segmented_text(
                JSXElement(node.tag, {**node.props, "items": items[index:index + 2]}, []),
                "body",
            ), font_size)
            for index in range(0, len(items), 2)
        ]
    if node.tag == "EventCard":
        items = node.props.get("items")
        if isinstance(items, list):
            return [
                (f"items[{index}].title", item.get("title"), 14)
                for index, item in enumerate(items)
                if isinstance(item, dict)
            ]
        return [("title", node.props.get("title"), 14)]
    if node.tag == "EmphasisText":
        return [
            ("mainText", node.props.get("mainText"), 18),
            ("secondaryText", node.props.get("secondaryText"), 12),
        ]
    return []


def _estimated_row_text_width(node: JSXElement) -> float | None:
    if node.tag == "EmphasisText":
        return max(
            _estimated_text_width(node.props.get("mainText"), 18),
            _estimated_text_width(node.props.get("secondaryText"), 12),
        )
    if node.tag == "EmphasizedData":
        return _emphasized_data_width(node)
    if node.tag == "SecondaryBody":
        return max(
            (_estimated_text_width(value, font_size)
             for _, value, font_size in _wrapping_text_candidates(node)),
            default=0,
        )
    if node.tag != "Stack":
        return None
    children = [
        child
        for child in node.child_elements()
        if child.props.get("position") != "absolute"
    ]
    estimates = [_estimated_row_text_width(child) for child in children]
    known = [estimate for estimate in estimates if estimate is not None]
    if not known:
        return None
    if node.props.get("direction", "column") == "row":
        content_width = sum(known) + _gap(node) * max(0, len(known) - 1)
    else:
        content_width = max(known)
    return content_width + _horizontal_padding(node)


def _auto_row_width_risk_message(path: str, required: float, available: float) -> str:
    return (
        f"{path} auto-sized text children may need about {_vp(required)}vp horizontally "
        f"while the row provides {_vp(available)}vp; font metrics and flex shrink may "
        "force wrapping, so this estimate is advisory only"
    )


def _wrapping_text_risk_message(
    path: str,
    prop: str,
    required: float,
    available: float,
) -> str:
    return (
        f"{path}.{prop} may wrap beyond the component's one-line layout lower bound: "
        f"the static text may need about {_vp(required)}vp while the slot provides "
        f"{_vp(available)}vp; this is a font-dependent estimate and is advisory only"
    )


def _validate_horizontal_container(
    node: JSXElement,
    available: float,
    path: str,
    issues: list[str],
    advisory_issues: list[str],
    *,
    inside_backplate: bool = False,
) -> None:
    declared = _declared_width(
        node,
        available,
        inside_backplate=inside_backplate,
    )
    minimum = _minimum_width(node, inside_backplate=inside_backplate)
    if minimum > available + 1e-9:
        issues.append(_horizontal_overflow_message(path, minimum, available))
    if declared is not None and declared > available + 1e-9:
        issues.append(_horizontal_overflow_message(path, declared, available))
    width = min(available, declared) if declared is not None else available
    inner = max(0, width - _horizontal_padding(node))
    direct_actions = [
        child for child in node.child_elements() if child.tag in {"CardButton", "PillButton"}
    ]
    if node.tag in {"Card", "Stack"} and direct_actions and inner > 132 + 1e-9:
        names = ", ".join(dict.fromkeys(child.tag for child in direct_actions))
        issues.append(
            f"{path} is a {_vp(inner)}vp-wide parent slot for {names}; action slots "
            "must stay within one half-card region of at most 132vp"
        )
    if node.tag == "EmphasizedData":
        required_text = _emphasized_data_width(node)
        if required_text > inner * 1.08 + 1e-9:
            advisory_issues.append(_horizontal_text_risk_message(path, required_text, inner))
    elif node.tag == "ProgressCircleSingle":
        required_text = _progress_circle_single_width_estimate(node)
        if required_text > inner * 1.08 + 1e-9:
            advisory_issues.append(
                _progress_circle_single_width_risk_message(
                    path,
                    required_text,
                    inner,
                )
            )
    for prop, value, font_size in _wrapping_text_candidates(node):
        if value is None or isinstance(value, bool) or str(value) == "":
            continue
        required_text = _estimated_text_width(value, font_size)
        if required_text > inner * 1.08 + 1e-9:
            advisory_issues.append(
                _wrapping_text_risk_message(path, prop, required_text, inner)
            )
    children = node.child_elements()
    if not children:
        return
    children_inside_backplate = inside_backplate or (
        node.tag == "Stack" and node.props.get("surface") == "backplate"
    )

    has_absolute_children = any(
        child.props.get("position") == "absolute" for child in children
    )
    is_overlay_container = (
        node.tag == "Card"
        or (node.tag == "Stack" and node.props.get("position") == "relative")
    ) and has_absolute_children
    if is_overlay_container:
        flow = _relative_flow_layer(node)
        if flow is not None:
            _validate_horizontal_container(
                flow,
                inner,
                f"{path}/<flow>",
                issues,
                advisory_issues,
                inside_backplate=children_inside_backplate,
            )
        absolute_children = [
            child for child in children if child.props.get("position") == "absolute"
        ]
        for index, child in enumerate(absolute_children, start=1):
            child_path = f"{path}/<Stack>[{index}]"
            child_width = _declared_width(
                child,
                width,
                inside_backplate=children_inside_backplate,
            )
            left = _number(child.props.get("left")) or 0
            right = _number(child.props.get("right")) or 0
            has_left = child.props.get("left") is not None
            margins = _margin_extent(child, "ml", "mr")
            if child_width is None:
                child_width = max(0, width - left - right - margins)
                child_width = max(
                    child_width,
                    _minimum_width(
                        child,
                        inside_backplate=children_inside_backplate,
                    ),
                )
                required = left + child_width + right + margins
            elif has_left:
                # CSS resolves left + width first in LTR layout and ignores an
                # over-constraining right value.
                required = left + child_width + margins
            else:
                required = child_width + right + margins
            if required > width + 1e-9:
                issues.append(_horizontal_overflow_message(child_path, required, width))
            _validate_horizontal_container(
                child,
                child_width,
                child_path,
                issues,
                advisory_issues,
                inside_backplate=children_inside_backplate,
            )
        return

    if node.tag == "Grid":
        columns = _grid_column_count(node)
        if columns is None:
            return
        gap = _number(node.props.get("columnGap", node.props.get("gap", 0))) or 0
        required_gaps = gap * max(0, columns - 1)
        if required_gaps > inner + 1e-9:
            issues.append(_horizontal_overflow_message(path, required_gaps, inner))
        available_columns = max(0, inner - required_gaps)
        column_widths = [available_columns / columns] * columns
        template = node.props.get("columns")
        if isinstance(template, str):
            match = _TWO_COLUMN_GRID.fullmatch(template)
            if match:
                fixed = float(match.group("fixed"))
                column_widths = [fixed, max(0, available_columns - fixed)]
                if fixed > available_columns + 1e-9:
                    issues.append(_horizontal_overflow_message(path, fixed, available_columns))
        for index, child in enumerate(children, start=1):
            column_width = column_widths[(index - 1) % columns]
            margins = _margin_extent(child, "ml", "mr")
            child_width = max(0, column_width - margins)
            declared_child = _declared_width(
                child,
                child_width,
                inside_backplate=children_inside_backplate,
            )
            minimum_child = _minimum_width(
                child,
                inside_backplate=children_inside_backplate,
            )
            if minimum_child + margins > column_width + 1e-9:
                issues.append(
                    _horizontal_overflow_message(
                        f"{path}/<{child.tag}>[{index}]",
                        minimum_child + margins,
                        column_width,
                    )
                )
            if declared_child is not None and declared_child + margins > column_width + 1e-9:
                issues.append(
                    _horizontal_overflow_message(
                        f"{path}/<{child.tag}>[{index}]",
                        declared_child + margins,
                        column_width,
                    )
                )
            _validate_horizontal_container(
                child,
                declared_child if declared_child is not None else child_width,
                f"{path}/<{child.tag}>[{index}]",
                issues,
                advisory_issues,
                inside_backplate=children_inside_backplate,
            )
        return

    if node.tag in {"Card", "Stack"} and node.props.get("direction", "column") == "row":
        gap = _gap(node)
        gap_total = gap * max(0, len(children) - 1)
        declared_widths = [
            max(
                basis,
                _number(child.props.get("minWidth")) or 0,
            )
            if (basis := _numeric_basis(child)) is not None
            else _declared_width(
                child,
                inner,
                inside_backplate=children_inside_backplate,
            )
            for child in children
        ]
        minimum_widths = [
            _minimum_width(
                child,
                inside_backplate=children_inside_backplate,
            )
            for child in children
        ]
        margins = [_margin_extent(child, "ml", "mr") for child in children]
        fixed_total = sum(value for value in declared_widths if value is not None) + sum(margins)
        flexible_indices = [index for index, value in enumerate(declared_widths) if value is None]
        flexible_minimum = sum(minimum_widths[index] for index in flexible_indices)
        required = fixed_total + flexible_minimum + gap_total
        if required > inner + 1e-9:
            issues.append(_horizontal_overflow_message(path, required, inner))
        distributable = max(0, inner - required)
        all_flexible_are_weighted = all(_flex_weight(children[index]) > 0 for index in flexible_indices)
        weights = {index: _flex_weight(children[index]) for index in flexible_indices}
        total_weight = sum(weights.values()) if all_flexible_are_weighted else 0
        fixed_width_total = sum(value for value in declared_widths if value is not None)
        estimated_flexible_widths = {
            index: _estimated_row_text_width(children[index])
            for index in flexible_indices
        }
        known_estimates = [
            estimate
            for estimate in estimated_flexible_widths.values()
            if estimate is not None
        ]
        if not total_weight and len(known_estimates) >= 2:
            estimated_required = fixed_total + gap_total + sum(
                max(
                    minimum_widths[index],
                    estimated_flexible_widths[index]
                    if estimated_flexible_widths[index] is not None
                    else minimum_widths[index],
                )
                for index in flexible_indices
            )
            if estimated_required > inner * 1.08 + 1e-9:
                advisory_issues.append(
                    _auto_row_width_risk_message(
                        path,
                        estimated_required,
                        inner,
                    )
                )
        for index, (child, child_width) in enumerate(
            zip(children, declared_widths),
            start=1,
        ):
            if child_width is None:
                zero_index = index - 1
                if total_weight:
                    child_width = minimum_widths[zero_index]
                    child_width += distributable * weights[zero_index] / total_weight
                else:
                    # Auto-sized flex items depend on rendered content. Give the
                    # child the largest width it could provably receive after
                    # other fixed/minimum reservations instead of inventing an
                    # equal-share allocation that can cause false rejections.
                    other_minimums = sum(minimum_widths[other] for other in flexible_indices if other != zero_index)
                    child_width = max(
                        minimum_widths[zero_index],
                        inner - gap_total - sum(margins) - fixed_width_total - other_minimums,
                    )
            _validate_horizontal_container(
                child,
                child_width,
                f"{path}/<{child.tag}>[{index}]",
                issues,
                advisory_issues,
                inside_backplate=children_inside_backplate,
            )
        return

    for index, child in enumerate(children, start=1):
        margins = _margin_extent(child, "ml", "mr")
        child_available = max(0, inner - margins)
        declared_child = _declared_width(
            child,
            child_available,
            inside_backplate=children_inside_backplate,
        )
        minimum_child = _minimum_width(
            child,
            inside_backplate=children_inside_backplate,
        )
        if minimum_child + margins > inner + 1e-9:
            issues.append(
                _horizontal_overflow_message(
                    f"{path}/<{child.tag}>[{index}]",
                    minimum_child + margins,
                    inner,
                )
            )
        if declared_child is not None and declared_child + margins > inner + 1e-9:
            issues.append(
                _horizontal_overflow_message(
                    f"{path}/<{child.tag}>[{index}]",
                    declared_child + margins,
                    inner,
                )
            )
        _validate_horizontal_container(
            child,
            declared_child if declared_child is not None else child_available,
            f"{path}/<{child.tag}>[{index}]",
            issues,
            advisory_issues,
            inside_backplate=children_inside_backplate,
        )


def _validate_horizontal_budget(
    root: JSXElement,
    advisory_issues: list[str] | None = None,
) -> None:
    root = _budget_tree_with_resolved_basis(root)
    dimensions = card_dimensions(root.props.get("size"))
    if dimensions is None:
        return
    width = _number(dimensions[0])
    if width is not None:
        issues: list[str] = []
        warnings: list[str] = []
        token = _BUDGET_CARD_SIZE.set(root.props.get("size"))
        try:
            _validate_horizontal_container(root, width, "<Card>", issues, warnings)
        finally:
            _BUDGET_CARD_SIZE.reset(token)
        if advisory_issues is not None:
            advisory_issues.extend(dict.fromkeys(warnings))
        if issues:
            raise LayoutBudgetError("; ".join(dict.fromkeys(issues)))


def _validate_text_region_usage(
    root: JSXElement, decision: dict[str, Any] | None,
    advisory_issues: list[tuple[str, str]],
    user_query: str = "",
) -> None:
    if root.props.get("size") not in CARD_SIZE_DIMENSIONS:
        return  # Legacy numeric-size fixtures are outside the generation API.
    # Only use documented parent regions. A generic nested Stack is not proof
    # of a separate semantic region and must not reset the core count.
    pattern = _canonical_layout_pattern((decision or {}).get("layoutPattern"))
    regions = [root]
    if root.props.get("size") == "2x4" and pattern in {"13", "15", "15-R"}:
        regions = root.child_elements()
    ignored = {"Card", "Stack", "Grid", "SingleLineTitle", "DoubleLineTitle", "Badge",
               "Icon", "AppIcon", "WeatherIcon", "PillButton", "CircleButton", "CardButton"}
    explicit_peer_table_intent = bool(re.search(
        r"列表|清单|一览|表格|逐项|分别|各项|同等|等权|并列|对比|比较|汇总|"
        r"\b(?:list|table|overview|compare|comparison|each)\b",
        user_query,
        re.I,
    ))
    all_business = [node for node in _walk(root) if node.tag not in ignored]
    if (
        pattern is not None
        and all_business
        and all(node.tag == "TableText" for node in all_business)
        and not explicit_peer_table_intent
    ):
        raise ValidationError(
            "the card cannot use TableText as its only business information for an ordinary "
            "multi-field request. Select the most relevant dynamic fact as one core EmphasisText, "
            "EmphasizedData, progress, InfoBlock or other semantic core, and put the remaining "
            "supplementary facts into one SecondaryBody or one labeled TableText according to "
            "which is clearer. A static category title does not count "
            "as the core. Sole TableText is reserved for an explicit list, table, comparison or "
            "equal-priority overview request"
        )
    for index, region in enumerate(regions):
        business = [node for node in _walk(region) if node.tag not in ignored]
        if business and all(node.tag == "SecondaryBody" for node in business):
            raise ValidationError(
                f"region[{index}] cannot use SecondaryBody as its only business information; "
                "choose a core component without inventing or deleting facts"
            )
        emphasized = [node for node in business if node.tag in {"EmphasisText", "EmphasizedData"}]
        for node in business:
            if node.tag != "EmphasisText":
                continue
            bindings = node.props.get("dataIds")
            secondary_ids = bindings.get("secondaryText") if isinstance(bindings, dict) else None
            if isinstance(secondary_ids, list) and len(secondary_ids) >= 3:
                raise ValidationError(
                    "EmphasisText.secondaryText cannot combine three or more distinct dataIds into "
                    "one unlabeled value string. Keep one core component and render those "
                    "supplementary facts with one SecondaryBody when values are self-describing, "
                    "or one TableText when per-item labels are required for clarity"
                )
        # Semantic 2x4 submissions derive a documented decision from
        # Card.layout/Region.variant, which establishes the region boundary.
        # Keep legacy/internal decision-less geometry probes outside this hard
        # gate because arbitrary wrapper Stacks do not identify a region.
        if len(emphasized) > 1 and pattern is not None:
            component_names = ", ".join(node.tag for node in emphasized)
            raise ValidationError(
                f"region[{index}] contains {len(emphasized)} emphasized core components "
                f"({component_names}); one semantic region allows at most one EmphasisText or "
                "EmphasizedData in total. Wrapper Stacks do not establish independent semantic regions"
            )


def _validate_metric_semantics(
    root: JSXElement,
    advisory_issues: list[tuple[str, str]],
) -> None:
    semantic_issues: list[str] = []
    for node in _walk(root):
        if node.tag != "SecondaryBody":
            continue
        items = node.props.get("items")
        if not isinstance(items, list) or not items:
            semantic_issues.append(f"{node.tag}.items must be a non-empty array")
            continue
        ambiguous_items: list[str] = []
        for index, item in enumerate(items):
            where = f"{node.tag}.items[{index}]"
            if not isinstance(item, dict):
                semantic_issues.append(f"{where} must be an object")
                continue
            label = item.get("label")
            if label is not None and (not isinstance(label, str) or not label.strip()):
                semantic_issues.append(f"{where}.label must be omitted or a non-empty string")
            if "value" not in item:
                semantic_issues.append(f"{where}.value is required")
                continue
            if isinstance(item["value"], (dict, list, bool)) or item["value"] is None:
                semantic_issues.append(f"{where}.value must be a string or number")
                continue
            if label is None and metric_requires_label(item["value"]):
                ambiguous_items.append(f"{where}.value={item['value']!r}")
        if ambiguous_items:
            advisory_issues.append(
                (
                    "metric-context-risk",
                    ", ".join(ambiguous_items) + " may be ambiguous without static semantic labels",
                )
            )
    if semantic_issues:
        raise ValidationError("; ".join(dict.fromkeys(semantic_issues)))


def _inactive_scalar_props(node: JSXElement) -> set[str]:
    if not isinstance(node.props.get("items"), list):
        return set()
    if node.tag == "EventCard":
        return {"title", "time", "location"}
    if node.tag in {"EmphasizedData", "ProgressLine2", "ProgressLine2WithData"}:
        return {"value", "unit"}
    return set()


def _unbound_display_values(node: JSXElement):
    allowed = BINDABLE_PROPS.get(node.tag, frozenset())
    data_ids = node.props.get("dataIds")
    bound = set(data_ids) if isinstance(data_ids, dict) else set()
    for prop in sorted(name for name in allowed if not name.startswith("items[].")):
        if prop in node.props and prop not in bound and prop not in _inactive_scalar_props(node):
            if node.tag in _STRUCTURAL_PERCENT_TOTALS and prop == "totalValue" and node.props[prop] == 100:
                continue
            yield prop, node.props[prop]
    item_props = {name.removeprefix("items[].") for name in allowed if name.startswith("items[].")}
    items = node.props.get("items")
    if not isinstance(items, list):
        return
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        item_ids = item.get("dataIds")
        item_bound = set(item_ids) if isinstance(item_ids, dict) else set()
        for prop in sorted(item_props):
            if prop in item and prop not in item_bound:
                yield f"items[{index}].{prop}", item[prop]


_REQUIRED_FACT_STATIC_PROPS = {
    "DataDisplay": ("label", "supportingText"),
    "Gauge": ("label",),
    "PillButton": ("label",),
    "CardButton": ("text",),
    "TextBlock": ("items[].label",),
    "TopTextBottomValue": ("items[].label", "items[].unit"),
    "H_BarChart": ("items[].label",),
    "SecondaryBody": ("items[].label",),
}


def _required_fact_display_values(node: JSXElement, *, include_bound: bool = False):
    """Include rendered static labels, not arbitrary string-valued props.

    These fields are displayed by their respective converters but deliberately
    have no binding slot. Keep them separate from _unbound_display_values so
    labels do not become candidates for dynamic-value/staticization warnings.
    """
    display_node = node
    if include_bound:
        # After materialization these are the actual initial display literals.
        # Checking literal text here must not reject it just because it is bound.
        props = {key: value for key, value in node.props.items() if key != "dataIds"}
        if isinstance(props.get("items"), list):
            props["items"] = [
                {key: value for key, value in item.items() if key != "dataIds"}
                if isinstance(item, dict) else item for item in props["items"]
            ]
        display_node = JSXElement(tag=node.tag, props=props, children=node.children)
    yield from _unbound_display_values(display_node)
    for prop in _REQUIRED_FACT_STATIC_PROPS.get(node.tag, ()):
        if not prop.startswith("items[]."):
            if prop in node.props:
                yield prop, node.props[prop]
            continue
        items = node.props.get("items")
        if not isinstance(items, list):
            continue
        item_prop = prop.removeprefix("items[].")
        for index, item in enumerate(items):
            if isinstance(item, dict) and item_prop in item:
                yield f"items[{index}].{item_prop}", item[item_prop]


def _required_text_binding_conflicts(
    root: JSXElement,
    facts: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], set[str]]:
    """Reject a static text fact whose visible owner is dynamically bound.

    This must run before binding materialization. Otherwise the authoritative
    data value replaces the model's literal and the downstream coverage check
    can only report the misleading symptom that the text disappeared.
    """

    bound_owners: list[dict[str, Any]] = []
    for node in _walk(root):
        allowed = BINDABLE_PROPS.get(node.tag, frozenset())
        owners: list[tuple[dict[str, Any], str]] = [(node.props, "")]
        items = node.props.get("items")
        if isinstance(items, list):
            owners.extend(
                (item, f"items[{index}].")
                for index, item in enumerate(items)
                if isinstance(item, dict)
            )
        for owner, prefix in owners:
            data_ids = owner.get("dataIds")
            if not isinstance(data_ids, dict):
                continue
            for prop, binding_ids in data_ids.items():
                location = prefix + prop
                contract_location = f"items[].{prop}" if prefix else prop
                if contract_location not in allowed or prop not in owner:
                    continue
                if not prefix and prop in _inactive_scalar_props(node):
                    continue
                ids = (
                    [binding_ids]
                    if isinstance(binding_ids, str) and binding_ids
                    else [value for value in binding_ids if isinstance(value, str) and value]
                    if isinstance(binding_ids, list)
                    else []
                )
                if not ids:
                    continue
                bound_owners.append({
                    "component": node.tag,
                    "prop": location,
                    "value": owner[prop],
                    "dataIds": ids,
                    "template": owner.get(f"{prop}Template"),
                })

    findings: list[dict[str, Any]] = []
    conflicted_texts: set[str] = set()
    for fact in facts:
        text = fact.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        normalized_text = re.sub(r"\s+", "", text)
        pattern = (r"(?<![\d.])" if normalized_text[0].isdigit() else "") + re.escape(normalized_text)
        if normalized_text[-1].isdigit():
            pattern += r"(?![\d.])"
        for owner in bound_owners:
            value = owner["value"]
            if not isinstance(value, (str, int, float)) or isinstance(value, bool):
                continue
            normalized_value = re.sub(r"\s+", "", str(value))
            if re.search(pattern, normalized_value) is None:
                continue
            template = owner.get("template")
            if (
                isinstance(template, str)
                and "{value}" in template
                and re.search(pattern, re.sub(r"\s+", "", template)) is not None
            ):
                # The template preserves the static text while replacing only
                # its dynamic placeholder, so this is a legitimate mixed owner.
                continue
            other_owners = [
                f"<{candidate['component']}> {candidate['prop']}"
                for candidate in bound_owners
                if candidate is not owner
                and set(candidate["dataIds"]) & set(owner["dataIds"])
            ]
            requirement = str(fact.get("requirement") or text)
            ids = owner["dataIds"]
            message = (
                f"Info Plan declares {text!r} as a static text fact, but "
                f"<{owner['component']}> {owner['prop']} binds it to dataIds={ids!r}. "
                "A text fact must remain an unbound visible literal; remove the binding "
                "from this prop instead of assigning an unrelated dataId."
            )
            if other_owners:
                message += " The same dataId is already visibly owned by " + ", ".join(other_owners) + "."
            findings.append({
                "severity": "error",
                "code": "static-text-binding-conflict",
                "phase": "required_information",
                "message": message,
                "details": {
                    "requirement": requirement,
                    "text": text,
                    "component": owner["component"],
                    "prop": owner["prop"],
                    "dataIds": ids,
                    "otherOwners": other_owners,
                },
            })
            conflicted_texts.add(text)
            break
    return findings, conflicted_texts


def _literal_is_grounded_in_query(literal: object, prompt_task: dict[str, Any] | None) -> bool:
    if prompt_task is None:
        return False
    query = str(prompt_task.get("userQuery") or "")
    if isinstance(literal, bool):
        return False
    if isinstance(literal, (int, float)):
        token = re.escape(format(literal, ".15g"))
        return re.search(rf"(?<![\d.]){token}(?![\d.])", query) is not None
    value = str(literal).strip()
    return bool(value) and value in query


def _unplanned_query_values(root, context, prompt_task, resolved_ids):
    """Surface conflicting raw JSX claims without treating a substring as proof."""
    warnings = []
    for node in _walk(root):
        owners = [(node.props, '')]
        if isinstance(node.props.get('items'), list):
            owners.extend((item, 'items[].') for item in node.props['items'] if isinstance(item, dict))
        for owner, prefix in owners:
            ids = owner.get('dataIds')
            if not isinstance(ids, dict):
                continue
            for prop, key in ids.items():
                if prefix + prop not in BINDABLE_PROPS.get(node.tag, ()):
                    continue
                if not isinstance(key, str) or key not in context.data:
                    continue
                if key in resolved_ids or prop not in owner:
                    continue
                binding = context.data[key]
                if (owner[prop] != binding.value_for_prop(node.tag, prefix + prop)
                        and _literal_is_grounded_in_query(owner[prop], prompt_task)):
                    item = {'severity': 'warning', 'code': 'unplanned-query-value', 'dataId': key,
                            'message': (
                                f'JSX proposes {owner[prop]!r} for {key!r}, '
                                'but no per-ID initialValue was established. '
                                f'Retaining input {binding.value!r}; '
                                'verify field identity in the plan, not just presence in userQuery.'
                            )}
                    if item not in warnings:
                        warnings.append(item)
    return warnings


def _canonical_number_token(value: str) -> str:
    try:
        number = Decimal(value)
    except InvalidOperation:
        return value
    if number == number.to_integral():
        return str(number.quantize(Decimal(1)))
    return format(number.normalize(), "f")


def _number_tokens(value: Any) -> set[str]:
    """Collect business-number tokens without treating booleans as numbers."""
    if isinstance(value, bool) or value is None:
        return set()
    if isinstance(value, dict):
        tokens: set[str] = set()
        for child in value.values():
            tokens.update(_number_tokens(child))
        return tokens
    if isinstance(value, list):
        tokens: set[str] = set()
        for child in value:
            tokens.update(_number_tokens(child))
        return tokens
    if isinstance(value, (str, int, float)):
        return {_canonical_number_token(token) for token in re.findall(r"\d+(?:\.\d+)?", str(value))}
    return set()


def _prompt_sample_numbers(
    prompt_task: dict[str, Any],
    compile_context: dict[str, Any] | None = None,
) -> set[str]:
    numbers: set[str] = set()
    data = prompt_task.get("data", [])
    if not isinstance(data, list):
        return numbers
    for item in data:
        if isinstance(item, dict) and "value" in item:
            numbers.update(_number_tokens(item["value"]))
    if compile_context is not None:
        try:
            context = CompileContext.from_payload(compile_context)
        except ValidationError:
            context = None
        if context is not None:
            for binding in context.data.values():
                numbers.update(_number_tokens(binding.value))
    return numbers


def _query_number_tokens(query: str) -> set[str]:
    # Card-size notation is layout metadata, not a business value the model may
    # copy into visible content.
    without_card_sizes = re.sub(
        r"(?<!\d)\d+\s*(?:[xX×*])\s*\d+(?!\d)",
        "",
        query,
    )
    return _number_tokens(without_card_sizes)


_COMPLETE_NUMERIC_METRIC = re.compile(
    r"^\s*(?:\d{1,2}:\d{2}|[+-]?\d+(?:\.\d+)?\s*"
    r"(?:[%％℃℉°‰]|[A-Za-z]{1,8}|摄氏度|华氏度|公里|千米|分钟|小时|千卡|"
    r"毫秒|秒|天|步|米|克|升|元))\s*$",
    flags=re.IGNORECASE,
)

_COMPOSITE_METRIC_SEPARATOR = re.compile(r"\s*(?:/|／|\||｜|–|—|~|～|至)\s*")


def _is_complete_numeric_metric(value: Any) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (int, float)):
        return True
    return isinstance(value, str) and _COMPLETE_NUMERIC_METRIC.fullmatch(value) is not None


def _is_composite_emphasized_metric(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parts = _COMPOSITE_METRIC_SEPARATOR.split(value.strip())
    return len(parts) > 1 and all(_is_complete_numeric_metric(part) for part in parts)


def _validate_emphasized_data_semantics(root: JSXElement, advisory_issues: list[tuple[str, str]] | None = None) -> None:
    issues: list[str] = []
    for node in _walk(root):
        if node.tag != "EmphasizedData":
            continue
        raw_items = node.props.get("items")
        owners = raw_items if isinstance(raw_items, list) else [node.props]
        for index, owner in enumerate(owners):
            if not isinstance(owner, dict) or not _is_composite_emphasized_metric(
                owner.get("value")
            ):
                continue
            location = f"items[{index}].value" if isinstance(raw_items, list) else "value"
            issues.append(
                f"EmphasizedData.{location}={owner['value']!r} contains multiple complete "
                "metrics separated as one emphasized value; use a component or layout "
                "with separate value slots"
            )
    if issues and advisory_issues is not None:
        advisory_issues.extend(("composite-metric-risk", message) for message in dict.fromkeys(issues))


def _validate_status_unit_semantics(
    root: JSXElement,
    compile_context: CompileContext,
    advisory_issues: list[tuple[str, str]],
) -> None:
    def validate_owner(node: JSXElement, owner: dict[str, Any], where: str) -> None:
        data_ids = owner.get("dataIds")
        binding_id = data_ids.get("unit") if isinstance(data_ids, dict) else None
        if not isinstance(binding_id, str):
            return
        try:
            binding = compile_context.data_binding(binding_id)
        except ValidationError:
            return
        identifier_match, description_match = status_binding_evidence(binding)
        if identifier_match and description_match:
            advisory_issues.append(
                (
                    "status-unit-risk",
                    f"<{node.tag}> {where}unit binds {binding.id!r}; both its identifier and "
                    "description suggest status text rather than a measurement unit. Confirm "
                    "whether SecondaryBody or TableText would express it more clearly.",
                )
            )
        elif identifier_match or description_match:
            advisory_issues.append(
                (
                    "status-unit-risk",
                    f"<{node.tag}> {where}unit binds {binding.id!r}, which may describe a status "
                    "rather than a measurement unit",
                )
            )

    for node in _walk(root):
        if node.tag not in {"EmphasizedData", "ProgressLine2", "ProgressLine2WithData"}:
            continue
        items = node.props.get("items")
        if isinstance(items, list):
            for index, item in enumerate(items):
                if isinstance(item, dict):
                    validate_owner(node, item, f"items[{index}].")
        else:
            validate_owner(node, node.props, "")


def _validate_info_block_status_labels(
    root: JSXElement,
    compile_context: CompileContext,
) -> None:
    """Require object labels when InfoBlock combines ambiguous charging states."""

    def is_charging_status(binding: Any) -> bool:
        identifier = binding.id.casefold()
        description = binding.description.casefold()
        return "charging" in identifier or ("充电" in description and "状态" in description)

    issues: list[str] = []
    for node in _walk(root):
        if node.tag != "InfoBlock":
            continue
        data_ids = node.props.get("dataIds")
        if not isinstance(data_ids, dict):
            continue

        primary_id = data_ids.get("primaryText")
        if isinstance(primary_id, str) and primary_id:
            try:
                primary_binding = compile_context.data_binding(primary_id)
            except ValidationError:
                primary_binding = None
            template = node.props.get("primaryTextTemplate")
            if (
                primary_binding is not None
                and is_charging_status(primary_binding)
                and (not isinstance(template, str) or template.count("{value}") != 1)
            ):
                issues.append(
                    "<InfoBlock> primaryText binds a charging status that is not self-describing; "
                    "add primaryTextTemplate with the object label, for example "
                    "primaryTextTemplate=\"对象名 {value}\""
                )

        secondary_ids = data_binding_ids(
            "InfoBlock", "secondaryText", data_ids.get("secondaryText")
        )
        if secondary_ids is None or len(secondary_ids) < 2:
            continue
        charging_count = 0
        for binding_id in secondary_ids:
            try:
                binding = compile_context.data_binding(binding_id)
            except ValidationError:
                continue
            charging_count += int(is_charging_status(binding))
        if charging_count < 2:
            continue
        template = node.props.get("secondaryTextTemplate")
        if indexed_value_template_tokens(template, len(secondary_ids)) is None:
            example = " ｜ ".join(
                f"对象{index + 1} {{{index}}}" for index in range(len(secondary_ids))
            )
            issues.append(
                "<InfoBlock> secondaryText binds multiple charging statuses that are not "
                "self-describing; add an indexed secondaryTextTemplate that labels each object, "
                f"for example secondaryTextTemplate=\"{example}\""
            )
    if issues:
        raise ValidationError("; ".join(dict.fromkeys(issues)))


def _validate_emphasis_text_secondary_labels(
    root: JSXElement,
    compile_context: CompileContext,
) -> None:
    """Keep EmphasisText secondary values understandable after live updates."""

    issues: list[str] = []
    for node in _walk(root):
        if node.tag != "EmphasisText":
            continue
        data_ids = node.props.get("dataIds")
        if not isinstance(data_ids, dict):
            continue
        secondary_ids = data_binding_ids(
            "EmphasisText", "secondaryText", data_ids.get("secondaryText")
        )
        if secondary_ids is None:
            continue
        template = node.props.get("secondaryTextTemplate")
        if len(secondary_ids) > 1:
            if indexed_value_template_tokens(template, len(secondary_ids)) is None:
                issues.append(
                    "<EmphasisText> secondaryText combines multiple dataIds; add an indexed "
                    "secondaryTextTemplate with meaningful static labels for every value, using "
                    "{0}, {1}, ... once each in dataIds order"
                )
            continue
        value_maps = node.props.get("dataValueMaps")
        if isinstance(value_maps, dict) and "secondaryText" in value_maps:
            continue
        try:
            binding = compile_context.data_binding(secondary_ids[0])
        except ValidationError:
            continue
        if (
            metric_requires_label(binding.value_for_prop("EmphasisText", "secondaryText"))
            and (not isinstance(template, str) or template.count("{value}") != 1)
        ):
            issues.append(
                "<EmphasisText> secondaryText binds a value that is not self-describing; add "
                "secondaryTextTemplate with a meaningful static label and one {value} placeholder"
            )
    if issues:
        raise ValidationError("; ".join(dict.fromkeys(issues)))


def _collect_static_dynamic_value_warnings(
    root: JSXElement,
    compile_context: dict[str, Any],
    prompt_task: dict[str, Any] | None,
    advisory_issues: list[tuple[str, str]],
) -> None:
    context = CompileContext.from_payload(compile_context)
    if not context.data:
        return
    for node in _walk(root):
        for location, literal in _unbound_display_values(node):
            if literal == "":
                continue
            matches = [
                binding.id
                for binding in context.data.values()
                if type(literal) is type(binding.value) and literal == binding.value
            ]
            if len(matches) != 1 or _literal_is_grounded_in_query(literal, prompt_task):
                continue
            advisory_issues.append(
                (
                    "possible-static-dynamic-value",
                    f"{node.tag}.{location}={literal!r} 与动态字段 {matches[0]!r} 的样例完整相同，"
                    "但没有 dataIds；当前规则无法确定它是固定文案还是被静态化的动态值，请检查。",
                )
            )


def _validate_static_title_dynamic_fact_ownership(root: JSXElement) -> None:
    """Reject a static title that repeats a separately bound visible text fact."""
    static_titles: list[tuple[str, str, str]] = []
    for node in _walk(root):
        if node.tag not in {"SingleLineTitle", "DoubleLineTitle"}:
            continue
        data_ids = node.props.get("dataIds")
        bound = set(data_ids) if isinstance(data_ids, dict) else set()
        for prop in ("title", "secondaryInfo"):
            value = node.props.get(prop)
            if prop in bound or not isinstance(value, str) or not value.strip():
                continue
            static_titles.append((node.tag, prop, value.strip().casefold()))

    if not static_titles:
        return

    conflicts: list[str] = []
    for node in _walk(root):
        if node.tag in {"SingleLineTitle", "DoubleLineTitle"}:
            continue
        owners: list[tuple[dict[str, Any], str]] = [(node.props, "")]
        items = node.props.get("items")
        if isinstance(items, list):
            owners.extend(
                (item, f"items[{index}].")
                for index, item in enumerate(items)
                if isinstance(item, dict)
            )
        allowed = BINDABLE_PROPS.get(node.tag, frozenset())
        for owner, prefix in owners:
            data_ids = owner.get("dataIds")
            if not isinstance(data_ids, dict):
                continue
            for prop, binding_id in data_ids.items():
                if prefix + prop not in allowed or prop not in owner:
                    continue
                value = owner[prop]
                if not isinstance(value, str):
                    continue
                token = value.strip().casefold()
                if len(token) < 2:
                    continue
                for title_tag, title_prop, title in static_titles:
                    if token not in title:
                        continue
                    ids = binding_id if isinstance(binding_id, list) else [binding_id]
                    rendered_ids = [item for item in ids if isinstance(item, str) and item]
                    conflicts.append(
                        f"{title_tag}.{title_prop} contains bound {node.tag}.{prefix}{prop}={value!r} "
                        f"({', '.join(rendered_ids) or 'dynamic binding'}); the same visible fact has two owners. "
                        "Use a generic static title that omits the value, or bind the title with *Template "
                        "and remove the duplicate body display"
                    )
    if conflicts:
        raise ValidationError("; ".join(dict.fromkeys(conflicts)))


def _data_ids(value: Any) -> set[str]:
    if not isinstance(value, dict):
        return set()
    result: set[str] = set()
    for item in value.values():
        if isinstance(item, str) and item:
            result.add(item)
        elif isinstance(item, list):
            result.update(child for child in item if isinstance(child, str) and child)
    return result


def _validate_interactions_and_invented_numbers(
    root: JSXElement,
    prompt_task: dict[str, Any] | None,
    compile_context: dict[str, Any] | None = None,
    advisory_issues: list[tuple[str, str]] | None = None,
    *,
    validate_dynamic_values: bool = True,
) -> None:
    if prompt_task is None:
        return
    seen_actions: set[str] = set()
    issues: list[str] = []
    for node in _walk(root):
        if node.tag in {"PillButton", "CircleButton", "CardButton"}:
            action_id = node.props.get("actionId")
            if node.props.get("disabled") is not True and not action_id:
                issues.append(f"{node.tag} 是启用状态，但没有 actionId。")
            if isinstance(action_id, str) and action_id:
                if action_id in seen_actions:
                    issues.append(f"actionId {action_id!r} 在同一张卡片中只能使用一次")
                seen_actions.add(action_id)

    query = str(prompt_task.get("userQuery") or "")
    query_numbers = _query_number_tokens(query)
    sample_numbers = _prompt_sample_numbers(prompt_task, compile_context)
    exact_samples: list[Any] = []
    if compile_context is not None:
        try:
            exact_samples = [binding.value for binding in CompileContext.from_payload(compile_context).data.values()]
        except ValidationError:
            pass
    for node in _walk(root):
        for location, literal in _unbound_display_values(node):
            if isinstance(literal, bool) or not isinstance(literal, (str, int, float)):
                continue
            # Exact sample literals are already reported by
            # _collect_static_dynamic_value_warnings; avoid emitting a second,
            # differently worded warning for the same risk.
            if any(type(literal) is type(sample) and literal == sample for sample in exact_samples):
                continue
            numbers = _number_tokens(literal)
            ungrounded = numbers - query_numbers
            staticized = ungrounded & sample_numbers
            invented = ungrounded - sample_numbers
            if validate_dynamic_values and staticized and advisory_issues is not None:
                advisory_issues.append(
                    (
                        "possible-static-dynamic-number",
                        f"{node.tag}.{location}={literal!r} 中的数值 {sorted(staticized)!r} "
                        "也出现在输入动态样例中，但当前规则无法确定字段来源；请检查是否需要 "
                        "dataIds 或由已绑定值动态派生。",
                    )
                )
            if invented and advisory_issues is not None:
                qualifier = "完整数值指标" if _is_complete_numeric_metric(literal) else "混合文案"
                advisory_issues.append(
                    (
                        "ungrounded-number-risk",
                        f"{node.tag}.{location}={literal!r} 作为{qualifier}包含输入未提供的数值 "
                        f"{sorted(invented)!r}；无法确定它是合法固定值还是无依据的业务值，请检查。",
                    )
                )
    if issues:
        raise ValidationError("; ".join(dict.fromkeys(issues)))


def _prompt_action_ids(prompt_task: dict[str, Any] | None) -> set[str]:
    if not isinstance(prompt_task, dict):
        return set()
    actions = prompt_task.get("actions")
    if not isinstance(actions, list):
        return set()
    action_ids = set()
    for action in actions:
        if not isinstance(action, dict):
            continue
        action_id = action.get("id")
        if isinstance(action_id, str) and action_id:
            action_ids.add(action_id)
    return action_ids


def _normalize_info_plan_component_hints(
    facts: list[dict[str, Any]],
    card_size: str | None,
    warnings: list[dict[str, Any]],
) -> None:
    """Keep component hints soft, size-scoped and safe to ignore."""

    allowed = generation_components_for_size(card_size) - {"Card", "Grid", "Stack"}
    for index, fact in enumerate(facts):
        hints = fact.get("componentHints")
        if not isinstance(hints, list):
            continue
        accepted = [hint for hint in hints if hint in allowed]
        dropped = [hint for hint in hints if hint not in allowed]
        if accepted:
            fact["componentHints"] = accepted
        else:
            fact.pop("componentHints", None)
        if dropped:
            warnings.append({
                "severity": "warning",
                "phase": "plan_contract",
                "code": "plan-component-hint-dropped",
                "message": (
                    f"info_required[{index}].componentHints removed unsupported "
                    f"components {dropped!r}"
                ),
            })


def _validate_required_action_coverage(
    root: JSXElement,
    prompt_task: dict[str, Any] | None,
    decision: dict[str, Any] | None,
    expected_size: str | None,
) -> None:
    """Require every model-visible task Action and a matching declared layout."""
    required_actions = _prompt_action_ids(prompt_task)
    issues: list[str] = []
    pattern = _canonical_layout_pattern((decision or {}).get("layoutPattern"))

    # This is deliberately narrow: Sub-118-B is the title + one-content
    # skeleton and has no Action slot.  When the JSX region itself contains a
    # PillButton, the decision and the rendered structure disagree even if the
    # browser happens to find enough pixels and reports no overflow.
    sub_pattern = (decision or {}).get("subPattern")
    regions = root.child_elements()
    has_side_subpatterns = (
        expected_size == "2x4"
        and pattern == "13"
        and isinstance(sub_pattern, dict)
    )
    if has_side_subpatterns and len(regions) == 2:
        for region_name, region_node in zip(("left", "right"), regions):
            declared_sub_pattern = _canonical_sub_pattern(sub_pattern.get(region_name))
            if declared_sub_pattern != "Sub-118-B 标题单内容":
                continue
            if any(node.tag == "PillButton" for node in _walk(region_node)):
                issues.append(
                    f'decision.subPattern.{region_name} declares "Sub-118-B 标题单内容", '
                    "which has no Action slot, but the corresponding JSX region contains "
                    'PillButton; use "Sub-118-D 标题内容单按钮" and keep the button in its '
                    "separate bottom slot"
                )

    if expected_size == "2x4" and pattern == "12":
        if required_actions:
            issues.append(
                '2x4 layout "上下双区" does not support Action, but the task requires '
                f"actionIds {sorted(required_actions)!r}; choose an Action-capable layout"
            )

    used_actions = set()
    for node in _walk(root):
        if node.tag not in {"PillButton", "CircleButton", "CardButton"}:
            continue
        action_id = node.props.get("actionId")
        if isinstance(action_id, str) and action_id:
            used_actions.add(action_id)
    missing_actions = sorted(required_actions - used_actions)
    if missing_actions:
        issues.append(
            "required input actionIds are missing from the generated card: "
            + ", ".join(repr(value) for value in missing_actions)
            + "; assign each Action to one legal button slot instead of listing it in unmetRequirements"
        )
    if issues:
        raise ValidationError("; ".join(issues))


def _referenced_binding_ids(root: JSXElement) -> tuple[set[str], set[str]]:
    data_ids: set[str] = set()
    action_ids: set[str] = set()
    for node in _walk(root):
        data_ids.update(_data_ids(node.props.get("dataIds")))
        items = node.props.get("items")
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    data_ids.update(_data_ids(item.get("dataIds")))
        action_id = node.props.get("actionId")
        if isinstance(action_id, str) and action_id:
            action_ids.add(action_id)
    return data_ids, action_ids


def _effective_binding_ids(root: JSXElement) -> tuple[set[str], set[str]]:
    """Count consumed binding slots, not ignored scalar/metadata declarations."""
    data_ids: set[str] = set()
    action_ids: set[str] = set()
    for node in _walk(root):
        allowed = BINDABLE_PROPS.get(node.tag, frozenset())
        bindings = node.props.get("dataIds")
        if isinstance(bindings, dict):
            active_bindings = {}
            for key, value in bindings.items():
                if key not in allowed or key.startswith("items[]."):
                    continue
                if key not in _inactive_scalar_props(node):
                    active_bindings[key] = value
            data_ids.update(_data_ids(active_bindings))
        items = node.props.get("items")
        if isinstance(items, list):
            for item in items:
                bindings = item.get("dataIds") if isinstance(item, dict) else None
                if isinstance(bindings, dict):
                    data_ids.update(_data_ids({key: value for key, value in bindings.items()
                                              if f"items[].{key}" in allowed}))
        action_id = node.props.get("actionId")
        if node.tag in {"PillButton", "CircleButton", "CardButton"} and isinstance(action_id, str) and action_id:
            action_ids.add(action_id)
    return data_ids, action_ids


_INDEXED_DATA_ID = re.compile(r"^(?P<collection>.+)\.(?P<index>\d+)\.[^.]+$")


def _event_card_capacity_omissions(
    root: JSXElement,
    missing: list[dict[str, Any]],
    used_data: set[str],
) -> list[dict[str, Any]]:
    """Allow one full EventCard to omit wholly unrendered extra schedules.

    EventCard intentionally supports at most two items. When its two item
    slots are both occupied by distinct objects from one indexed collection,
    extra objects from that collection may be omitted without turning the
    otherwise valid two-item card into an endless required-information repair.
    Partially rendered objects and non-EventCard facts remain protected.
    """

    event_cards = [node for node in _walk(root) if node.tag == "EventCard"]
    if len(event_cards) != 1:
        return []
    items = event_cards[0].props.get("items")
    if not isinstance(items, list) or len(items) != 2:
        return []

    represented_groups: set[tuple[str, int]] = set()
    for item in items:
        if not isinstance(item, dict):
            return []
        item_groups = set()
        for data_id in _data_ids(item.get("dataIds")):
            match = _INDEXED_DATA_ID.fullmatch(data_id)
            if match is not None:
                item_groups.add((match.group("collection"), int(match.group("index"))))
        if len(item_groups) != 1:
            return []
        represented_groups.update(item_groups)
    if len(represented_groups) != 2:
        return []

    represented_collections = {collection for collection, _ in represented_groups}
    used_groups = {
        (match.group("collection"), int(match.group("index")))
        for data_id in used_data
        if (match := _INDEXED_DATA_ID.fullmatch(data_id)) is not None
    }
    omitted: list[dict[str, Any]] = []
    for fact in missing:
        data_id = fact.get("dataId")
        hints = fact.get("componentHints")
        if not isinstance(data_id, str) or not isinstance(hints, list) or "EventCard" not in hints:
            continue
        match = _INDEXED_DATA_ID.fullmatch(data_id)
        if match is None:
            continue
        group = (match.group("collection"), int(match.group("index")))
        if group[0] in represented_collections and group not in used_groups:
            omitted.append(fact)
    return omitted


_NO_UNMET_REQUIREMENTS = frozenset(
    {
        "无",
        "没有",
        "暂无",
        "无未满足需求",
        "全部满足",
        "none",
        "n/a",
    }
)


def _coverage_warning(message: str) -> dict[str, str]:
    return {
        "code": "coverage-metadata-normalized",
        "severity": "warning",
        "message": message,
    }


def _layout_warning(message: str) -> dict[str, str]:
    return {
        "code": "layout-risk",
        "severity": "warning",
        "phase": "layout_budget",
        "message": message,
    }


_LAYOUT_BUDGET_REPAIR_HINT = (
    "若当前布局空间不足且存在符合文档、按钮数量和图标资源约束的图标按钮布局，"
    "请优先重新评估 CircleButton Layout Pattern；这只是布局重选建议，不能直接把 "
    "PillButton 机械替换成 CircleButton，也不能删除必需信息、dataIds 或 actionId。"
)


def _semantic_warning(code: str, message: str) -> dict[str, str]:
    return {
        "code": code,
        "severity": "warning",
        "phase": "business_semantics",
        "message": message,
    }


def _normalize_coverage_metadata(
    root: JSXElement,
    coverage: Any,
    unmet_requirements: Any,
    *,
    required: bool,
) -> tuple[list[dict[str, Any]], list[str], str, list[dict[str, str]]]:
    if not required and coverage is None and unmet_requirements is None:
        return [], [], "completed", []

    warnings: list[dict[str, str]] = []
    if coverage is None:
        coverage_items: list[Any] = []
    elif isinstance(coverage, list):
        coverage_items = coverage
    elif isinstance(coverage, (str, dict)):
        coverage_items = [coverage]
        warnings.append(_coverage_warning("coverage 不是数组，已在本地转换为数组。"))
    else:
        coverage_items = []
        warnings.append(_coverage_warning("coverage 格式无法识别，已忽略该辅助元数据。"))

    if unmet_requirements is None:
        unmet_items: list[Any] = []
    elif isinstance(unmet_requirements, list):
        unmet_items = unmet_requirements
    elif isinstance(unmet_requirements, (str, dict)):
        unmet_items = [unmet_requirements]
        warnings.append(_coverage_warning("unmetRequirements 不是数组，已在本地转换为数组。"))
    else:
        unmet_items = []
        warnings.append(_coverage_warning("unmetRequirements 格式无法识别，已忽略该辅助元数据。"))

    used_data, used_actions = _referenced_binding_ids(root)
    covered_data: set[str] = set()
    covered_actions: set[str] = set()
    normalized_by_requirement: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(coverage_items):
        if isinstance(item, str):
            requirement = item.strip()
            item = {"requirement": requirement}
            warnings.append(_coverage_warning(f"coverage[{index}] 是字符串，已转换为 requirement 对象。"))
        elif isinstance(item, dict) and isinstance(item.get("requirement"), str):
            requirement = item["requirement"].strip()
        else:
            warnings.append(_coverage_warning(f"coverage[{index}] 无法识别，已忽略。"))
            continue
        if not requirement:
            warnings.append(_coverage_warning(f"coverage[{index}] 为空，已忽略。"))
            continue
        data = item.get("dataIds", [])
        actions = item.get("actionIds", [])
        if not isinstance(data, list) or not all(isinstance(value, str) and value for value in data):
            data = []
            warnings.append(_coverage_warning(f"coverage[{index}].dataIds 格式错误，已由最终 JSX 重新推导。"))
        if not isinstance(actions, list) or not all(isinstance(value, str) and value for value in actions):
            actions = []
            warnings.append(_coverage_warning(f"coverage[{index}].actionIds 格式错误，已由最终 JSX 重新推导。"))
        entry = normalized_by_requirement.setdefault(
            requirement,
            {
                "requirement": requirement,
                "dataIds": [],
                "actionIds": [],
            },
        )
        # JSX is the source of truth. Preserve the model's requirement-to-id
        # hints only when they reference ids actually used by the final tree;
        # discard stale, unknown and duplicate metadata locally.
        for value in data:
            if value in used_data and value not in covered_data:
                entry["dataIds"].append(value)
                covered_data.add(value)
        for value in actions:
            if value in used_actions and value not in covered_actions:
                entry["actionIds"].append(value)
                covered_actions.add(value)

    normalized = list(normalized_by_requirement.values())
    unmet: list[str] = []
    for index, item in enumerate(unmet_items):
        if isinstance(item, str):
            value = item.strip()
        elif isinstance(item, dict) and isinstance(item.get("requirement"), str):
            value = item["requirement"].strip()
            warnings.append(_coverage_warning(f"unmetRequirements[{index}] 是对象，已提取 requirement 字符串。"))
        else:
            warnings.append(_coverage_warning(f"unmetRequirements[{index}] 无法识别，已忽略。"))
            continue
        if not value or value.lower() in _NO_UNMET_REQUIREMENTS:
            if value:
                warnings.append(_coverage_warning(f"unmetRequirements[{index}] 表示没有未满足需求，已规范化为空。"))
            continue
        if value not in unmet:
            unmet.append(value)

    missing_data = sorted(used_data - covered_data)
    missing_actions = sorted(used_actions - covered_actions)
    if normalized and (missing_data or missing_actions):
        normalized[0]["dataIds"].extend(missing_data)
        normalized[0]["actionIds"].extend(missing_actions)
    if unmet and normalized:
        status = "partial"
    elif unmet:
        # unmetRequirements is model-authored advisory metadata.  Without a
        # locally verifiable coverage record it cannot prove that the input is
        # insufficient, so keep the explanation but leave status unverified.
        status = "unverified"
    elif normalized:
        # Model-authored coverage cannot establish semantic completeness.
        status = "unverified"
    else:
        status = "unverified" if required else "completed"
        if required:
            warnings.append(
                _coverage_warning(
                    "coverage 与 unmetRequirements 均未提供有效内容；卡片继续生成，但需求覆盖状态未验证。"
                )
            )
    return normalized, unmet, status, warnings


def _error_phase(exc: ConversionError) -> str:
    if isinstance(exc, A2UIProtocolOutputError):
        return "a2ui_protocol_output"
    if isinstance(exc, ParseError):
        return "jsx_parse"
    if isinstance(exc, LayoutBudgetError):
        return "layout_budget"
    if isinstance(exc, LayoutStructureError):
        return "layout_structure"
    if isinstance(exc, RequiredInformationError):
        return "required_information"
    if isinstance(exc, ValidationError):
        return "contract_or_protocol"
    return "conversion"


def _error_retryable(exc: ConversionError) -> bool:
    return not isinstance(exc, A2UIProtocolOutputError)


def _validation_finding(exc: ConversionError) -> dict[str, str]:
    phase = _error_phase(exc)
    if phase == "contract_or_protocol":
        layout_markers = (
            "items must contain one or two schedules", "a Card may contain at most one EventCard",
            "cannot use SecondaryBody as its only business information",
            "one semantic region allows at most one EmphasisText or EmphasizedData",
            "required input actionIds are missing",
        )
        for marker in layout_markers:
            if marker in str(exc):
                # Component-organization constraints require restructuring.
                phase = "layout_structure"
                break
    return {
        "severity": "error",
        "code": phase.replace("_", "-"),
        "phase": phase,
        "message": str(exc),
    }


class OrderedWorkflowState:
    def __init__(
        self,
        component_name: str,
        resources: GenerationResources | None = None,
        *,
        compile_context: dict[str, Any] | None = None,
        prompt_task: dict[str, Any] | None = None,
        defer_browser_validation: bool = False,
        validate_layout_budget: bool = True,
        validation_enabled: bool = True,
        validate_dynamic_values: bool = True,
        enable_dynamic_data_binding: bool = True,
        require_semantic_layout: bool = False,
    ) -> None:
        if not re.fullmatch(r"Card[A-Za-z0-9_$]+", component_name):
            raise ValueError("component_name must match Card[A-Za-z0-9_$]+")
        self.component_name = component_name
        self.resources = resources or GenerationResources()
        self.next_stage_index = 0
        self.loaded_resources: list[str] = []
        self.resource_reads: list[dict[str, Any]] = []
        self.submission: CompiledSubmission | None = None
        self.pending_submission: CompiledSubmission | None = None
        self.compile_context = compile_context or {}
        self.prompt_task = prompt_task
        try:
            self.expected_card_size = task_card_size(prompt_task)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        self.validation_enabled = validation_enabled
        self.defer_browser_validation = defer_browser_validation and validation_enabled
        self.validate_layout_budget = validate_layout_budget and validation_enabled
        self.validate_dynamic_values = validate_dynamic_values
        self.enable_dynamic_data_binding = enable_dynamic_data_binding
        self.require_semantic_layout = require_semantic_layout and self.expected_card_size == "2x4"
        self.active_layout_fallback: str | None = None
        self.required_facts: list[dict[str, Any]] | None = None
        self.plan_warnings: list[dict[str, Any]] = []

    def install_plan(self, plan: dict[str, Any], *, warnings: list[dict[str, Any]] | None = None) -> None:
        warnings = list(warnings or [])
        facts = validate_required_facts(
            plan.get("info_required"), str((self.prompt_task or {}).get("userQuery") or ""),
            CompileContext.from_payload(self.compile_context),
            warnings=warnings,
        )
        _normalize_info_plan_component_hints(facts, self.expected_card_size, warnings)
        planned_actions = {fact["actionId"] for fact in facts if "actionId" in fact}
        for action_id in sorted(_prompt_action_ids(self.prompt_task) - planned_actions):
            facts.append({
                "requirement": f"Preserve requested action {action_id}",
                "actionId": action_id,
            })
            warnings.append({
                "severity": "warning",
                "phase": "plan_contract",
                "code": "plan-action-restored",
                "message": f"Required input action {action_id!r} was added to the Info Plan",
            })
        context = context_with_initial_values(facts, self.compile_context)
        for warning in input_availability_warnings(CompileContext.from_payload(context)):
            if warning not in warnings:
                warnings.append(warning)
        self.required_facts = facts
        self.compile_context = context
        self.plan_warnings = []
        for warning in warnings:
            if warning not in self.plan_warnings:
                self.plan_warnings.append(warning)

    @property
    def expected_stage(self):
        if self.next_stage_index >= len(RESOURCE_STAGES):
            return None
        return RESOURCE_STAGES[self.next_stage_index]

    def read_generation_resource(self, key: str) -> dict[str, Any]:
        expected = self.expected_stage
        if expected is None:
            return {"ok": False, "error": "all resources are loaded; call submit_card_jsx"}
        if key != expected.key:
            return {"ok": False, "error": f"expected resource {expected.key!r}, received {key!r}"}
        source_files = [
            str(path.resolve()) for path in self.resources.source_files(key, card_size=self.expected_card_size)
        ]
        content = self.resources.read(key, card_size=self.expected_card_size)
        self.loaded_resources.append(key)
        self.resource_reads.append(
            {
                "resource": key,
                "source_files": source_files,
            }
        )
        self.next_stage_index += 1
        following = self.expected_stage
        if self.next_stage_index == 2 and self.required_facts is None:
            next_target = "submit_card_plan"
        elif following is not None:
            next_target = following.key
        else:
            next_target = "submit_card_jsx"
        return {
            "ok": True,
            "resource": key,
            "content": content,
            "next": next_target,
        }

    def mark_resources_loaded(self) -> None:
        """Mark the reference bundle as loaded when it was injected in the prompt."""
        self.loaded_resources = [stage.key for stage in RESOURCE_STAGES]
        self.resource_reads = []
        for stage in RESOURCE_STAGES:
            source_files = []
            for path in self.resources.source_files(stage.key, card_size=self.expected_card_size):
                source_files.append(str(path.resolve()))
            self.resource_reads.append(
                {
                    "resource": stage.key,
                    "source_files": source_files,
                }
            )
        self.next_stage_index = len(RESOURCE_STAGES)


    def submit_card_jsx(
        self,
        jsx: str,
        decision: dict[str, Any] | None = None,
        coverage: list[dict[str, Any]] | None = None,
        unmet_requirements: list[str] | None = None,
    ) -> dict[str, Any]:
        if self.expected_stage is not None:
            return {"ok": False, "error": f"read {self.expected_stage.key!r} before submitting JSX"}
        try:
            expression = normalize_jsx_expression(jsx)
            source = wrap_card_source(self.component_name, expression)
            cards = extract_card_functions(source)
            root = cards[self.component_name]
            semantic_source = None
            if self.require_semantic_layout and "layout" not in root.props:
                raise LayoutStructureError(
                    "2x4 generation requires Card.layout and Region slots; raw Stack/Grid is not "
                    "allowed in semantic JSX"
                )
            if "layout" in root.props:
                semantic_source = source
                try:
                    root, derived_decision = lower_semantic_card(root)
                except ValidationError as exc:
                    raise LayoutStructureError(str(exc)) from exc
                submitted_decision = (
                    _layout_decision_fields(decision)
                    if decision is not None
                    else None
                )
                if submitted_decision is not None and submitted_decision != derived_decision:
                    raise LayoutStructureError(
                        f"decision must match Card.layout/Region.variant: {derived_decision!r}"
                    )
                decision = derived_decision
                expression = _serialize_jsx(root)
                source = wrap_card_source(self.component_name, expression)
        except ConversionError as exc:
            return {
                "ok": False,
                "phase": _error_phase(exc),
                "retryable": _error_retryable(exc),
                "error": str(exc),
                "findings": [_validation_finding(exc)],
                "instruction": "fix the JSX and call submit_card_jsx again",
            }

        parsed_compile_context: CompileContext | None = None
        compile_context_error: ConversionError | None = None
        initial_value_warnings: list[dict[str, Any]] = []
        binding_normalization_warnings: list[dict[str, str]] = []
        required_fact_binding_findings: list[dict[str, Any]] = []
        conflicted_required_texts: set[str] = set()
        user_query = str((self.prompt_task or {}).get("userQuery") or "")
        # Planned generation resolves overrides by ID in the plan, not by
        # treating any JSX literal found in the query as that field's value.
        locked_initial_ids = frozenset()
        try:
            parsed_compile_context = CompileContext.from_payload(self.compile_context)
            # A new candidate must be measured anew. Saved snapshots are only
            # for recompiling their exact source, never for model repairs.
            parsed_compile_context.rendered_layout = None
            binding_normalization_warnings = _remove_empty_scalar_data_ids(root)
            if self.required_facts is not None:
                required_fact_binding_findings, conflicted_required_texts = (
                    _required_text_binding_conflicts(
                        root,
                        enforceable_facts(self.required_facts, user_query),
                    )
                )
                initial_value_warnings = _unplanned_query_values(
                    root, parsed_compile_context, self.prompt_task,
                    {fact['dataId'] for fact in self.required_facts if 'initialValue' in fact},
                )
                locked_initial_ids = frozenset(parsed_compile_context.data)
            if self.enable_dynamic_data_binding:
                materialize_binding_literals(
                    root,
                    parsed_compile_context,
                    user_query=user_query,
                    locked_initial_ids=locked_initial_ids,
                )
            if self.enable_dynamic_data_binding or binding_normalization_warnings:
                expression = _serialize_jsx(root)
                source = wrap_card_source(self.component_name, expression)
        except ConversionError as exc:
            compile_context_error = exc

        findings: list[dict[str, Any]] = []
        finding_messages: set[str] = set()
        layout_warning_messages: list[str] = []
        semantic_warning_messages: list[tuple[str, str]] = []

        def add_finding(exc: ConversionError) -> None:
            message = str(exc)
            if message in finding_messages:
                return
            finding_messages.add(message)
            findings.append(_validation_finding(exc))

        for finding in required_fact_binding_findings:
            message = finding["message"]
            if message not in finding_messages:
                finding_messages.add(message)
                findings.append(finding)

        if self.validation_enabled:
            validators = [
                lambda: _validate_generation_subset(root, self.expected_card_size),
                lambda: _validate_structure(lambda: _validate_layout_values(root)),
                lambda: _validate_emphasized_data_semantics(root, semantic_warning_messages),
                lambda: _validate_action_slot_compatibility(
                    root,
                    decision,
                    self.expected_card_size,
                    advisory_issues=semantic_warning_messages,
                ),
                lambda: _validate_required_action_coverage(
                    root,
                    self.prompt_task,
                    decision,
                    self.expected_card_size,
                ),
                lambda: _validate_progress_line_theme(root),
                lambda: _validate_structure(
                    lambda: _validate_layout_decision(root, decision, self.expected_card_size)
                ),
                lambda: _validate_assets(root, self.prompt_task),
                lambda: _validate_conversion_preflight(root),
            ]
            if self.validate_layout_budget:
                validators.extend(
                    (
                        lambda: _validate_layout_budget(
                            root,
                            layout_warning_messages,
                        ),
                        lambda: _raise_estimated_layout_risks(layout_warning_messages),
                        lambda: _validate_horizontal_budget(
                            root,
                            layout_warning_messages,
                        ),
                    )
                )
            validators.append(lambda: _validate_metric_semantics(root, semantic_warning_messages))
            validators.append(lambda: _validate_text_region_usage(
                root,
                decision,
                semantic_warning_messages,
                str((self.prompt_task or {}).get("userQuery") or ""),
            ))
            validators.append(lambda: _validate_static_title_dynamic_fact_ownership(root))
            if self.validate_dynamic_values:
                validators.append(
                    lambda: _collect_static_dynamic_value_warnings(
                        root,
                        self.compile_context,
                        self.prompt_task,
                        semantic_warning_messages,
                    )
                )
            validators.append(
                lambda: _validate_interactions_and_invented_numbers(
                    root,
                    self.prompt_task,
                    self.compile_context,
                    semantic_warning_messages,
                    validate_dynamic_values=self.validate_dynamic_values,
                ),
            )
            for validate in validators:
                try:
                    validate()
                except ConversionError as exc:
                    add_finding(exc)

            if parsed_compile_context is not None:
                try:
                    _validate_info_block_status_labels(root, parsed_compile_context)
                    _validate_emphasis_text_secondary_labels(root, parsed_compile_context)
                    _validate_status_unit_semantics(
                        root,
                        parsed_compile_context,
                        semantic_warning_messages,
                    )
                except ConversionError as exc:
                    add_finding(exc)
            for node in _walk(root):
                if parsed_compile_context is not None:
                    for message in collect_binding_validation_errors(
                        node,
                        parsed_compile_context,
                    ):
                        add_finding(ValidationError(message))

        if compile_context_error is not None:
            add_finding(compile_context_error)

        dropped_required_facts: list[dict[str, Any]] = []
        if self.required_facts is not None:
            used_data, used_actions = _effective_binding_ids(root)
            literals = []
            for node in _walk(root):
                for _, value in _required_fact_display_values(node, include_bound=True):
                    literals.append(value)
            # Input actions are checked independently (including their slots).
            # Do not report the same missing action again as a fact failure.
            unavailable = unavailable_data_ids(parsed_compile_context) if parsed_compile_context is not None else set()
            # An empty initial value does not remove a planned display binding:
            # the value may arrive later. Availability is advisory, not coverage.
            selected = [fact for fact in enforceable_facts(self.required_facts, user_query)
                        if fact.get("actionId") not in _prompt_action_ids(self.prompt_task)]
            missing = missing_required_facts(selected, used_data, used_actions, literals)
            # A static text that was present in the submitted JSX but attached
            # to a dynamic binding already has a more precise root-cause error.
            # Do not additionally misreport the same fact as simply missing.
            missing = [
                fact for fact in missing
                if fact.get("text") not in conflicted_required_texts
            ]
            capacity_omissions = _event_card_capacity_omissions(root, missing, used_data)
            if capacity_omissions:
                dropped_required_facts.extend(capacity_omissions)
                missing = [fact for fact in missing if fact not in capacity_omissions]
                semantic_warning_messages.append((
                    "event-card-capacity-omission",
                    "EventCard 已使用两个日程槽；未展示的额外完整日程已按组件容量限制省略。",
                ))
            if missing and self.active_layout_fallback == "drop_optional_component":
                dropped_required_facts.extend(
                    fact for fact in missing
                    if fact.get("actionId") is None
                )
                missing = [fact for fact in missing if fact not in dropped_required_facts]
            if missing:
                add_finding(RequiredInformationError(
                    "missing required facts: " + json.dumps(missing, ensure_ascii=False)
                    + "; restore these facts and bindings in every repair/fallback stage"
                ))
                findings[-1]["details"] = {"missingFacts": missing}

        (
            normalized_coverage,
            normalized_unmet,
            semantic_status,
            metadata_warnings,
        ) = _normalize_coverage_metadata(
            root,
            coverage,
            unmet_requirements,
            required=self.prompt_task is not None,
        )
        if dropped_required_facts:
            semantic_status = "partial"
        layout_warnings = [_layout_warning(message) for message in dict.fromkeys(layout_warning_messages)]
        semantic_warnings = [
            _semantic_warning(code, message) for code, message in dict.fromkeys(semantic_warning_messages)
        ]
        warnings = [*self.plan_warnings, *initial_value_warnings, *binding_normalization_warnings,
                    *(self.prompt_task or {}).get("inputWarnings", []),
                    *layout_warnings, *semantic_warnings, *metadata_warnings]

        if findings:
            first = findings[0]
            instruction = (
                "fix the JSX by resolving every ERROR and call submit_card_jsx again; "
                "WARNING entries are advisory only and must not be resolved by deleting "
                "required information or changing business semantics"
            )
            if first["phase"] == "layout_budget":
                instruction += "; " + _LAYOUT_BUDGET_REPAIR_HINT
            result = {
                "ok": False,
                "phase": first["phase"],
                "retryable": True,
                "error": first["message"],
                "findings": findings,
                "instruction": instruction,
            }
            if compile_context_error is not None and parsed_compile_context is None:
                result.update(phase="input_context", retryable=False,
                              instruction="编译输入数据或动作上下文无效；先修正输入，不重生成 JSX。")
            if warnings:
                result["warnings"] = warnings
            return result

        if _restore_remote_asset_sources(root, parsed_compile_context):
            expression = _serialize_jsx(root)
            source = wrap_card_source(self.component_name, expression)

        try:
            messages = compile_source(
                source,
                card=self.component_name,
                compile_contexts={self.component_name: parsed_compile_context},
                # The normalized source/context already resolved initial values.
                user_query=None,
                enable_dynamic_data_binding=self.enable_dynamic_data_binding,
            )[self.component_name]
        except ConversionError as exc:
            retryable = _error_retryable(exc)
            result = {
                "ok": False,
                "phase": _error_phase(exc),
                "retryable": retryable,
                "error": str(exc),
                "findings": [_validation_finding(exc)],
                "instruction": (
                    "fix the JSX by resolving every ERROR and call submit_card_jsx again; "
                    "WARNING entries are advisory only and must not be resolved by deleting "
                    "required information or changing business semantics"
                    if retryable
                    else "report this as an A2UI compiler/protocol output error; do not regenerate JSX"
                ),
            }
            if warnings:
                result["warnings"] = warnings
            return result
        prepared = CompiledSubmission(
            source=source,
            jsx=expression,
            messages=messages,
            decision=decision or {},
            compile_context=parsed_compile_context.payload(),
            coverage=normalized_coverage,
            unmet_requirements=normalized_unmet,
            semantic_status=semantic_status,
            warnings=warnings,
            semantic_source=semantic_source,
        )
        if self.defer_browser_validation:
            self.pending_submission = prepared
        else:
            self.submission = prepared
        result = {
            "ok": True,
            "pendingBrowserValidation": self.defer_browser_validation,
        }
        if self.required_facts is not None:
            enforceable = enforceable_facts(self.required_facts, user_query)
            result["requiredFactsUnavailable"] = sum(fact.get('dataId') in unavailable for fact in enforceable)
            result["requiredFactsChecked"] = len(enforceable)
            result["requiredFactsAdvisory"] = len(self.required_facts) - len(enforceable)
        if warnings:
            result["warnings"] = warnings
        return result

    def apply_rendered_layout(self, snapshot: dict | None) -> None:
        """Use the accepted candidate's existing browser pass; never re-render."""
        if snapshot is None:
            return
        pending = self.pending_submission
        if pending is None:
            raise RuntimeError("no pending JSX submission to apply layout")
        if not snapshot.get("secondaryBodies") and not re.search(r"<SecondaryBody(?:\s|/?>)", pending.source):
            return
        context = {**pending.compile_context, "renderedLayout": snapshot}
        messages = compile_source(
            pending.source, card=self.component_name,
            compile_contexts={self.component_name: context},
            enable_dynamic_data_binding=self.enable_dynamic_data_binding,
        )[self.component_name]
        pending.messages = messages
        pending.compile_context = context

    def accept_pending_submission(self) -> None:
        if self.pending_submission is None:
            raise RuntimeError("no pending JSX submission to accept")
        self.submission = self.pending_submission
        self.pending_submission = None

    def reject_pending_submission(self) -> None:
        self.pending_submission = None


def _decision_schema(card_size: str | None = None) -> dict[str, Any]:
    if card_size == "2x2":
        layout_names = list(LAYOUT_PATTERN_2X2_NAMES)
    elif card_size == "2x4":
        layout_names = list(LAYOUT_PATTERN_2X4_NAMES)
    else:
        layout_names = [*LAYOUT_PATTERN_2X2_NAMES, *LAYOUT_PATTERN_2X4_NAMES]

    properties: dict[str, Any] = {
        "layoutPattern": {
            "type": "string",
            "enum": layout_names,
            "description": "从当前尺寸的 layout_patterns 资源中选择一个顶层布局名称。",
        },
    }
    required = ["layoutPattern"]
    if card_size != "2x2":
        sub_118_value = {
            "type": "string",
            "enum": [
                name for name in SUB_PATTERN_2X4_NAMES
                if SUB_PATTERN_2X4_GROUPS[name] == "118"
            ],
        }
        sub_140_value = {
            "type": "string",
            "enum": [
                name for name in SUB_PATTERN_2X4_NAMES
                if SUB_PATTERN_2X4_GROUPS[name] == "140"
            ],
        }
        type13_region_value = {
            "type": "string",
            "enum": list(sub_118_value["enum"]),
            "description": (
                "Type13 左右父区均使用四边 8vp 安全边距内的 116×110vp 子布局。"
            ),
        }
        properties["subPattern"] = {
            "type": "object",
            "description": (
                "2x4 父内容区的子布局定位。左右双区填写 left 和 right；"
                "Type15 左内容右侧双槽与 Type15-R 左侧双槽右内容均填写 content；"
                "上下双区和四槽宫格填写空对象。"
            ),
            "properties": {
                "left": type13_region_value,
                "right": type13_region_value,
                "content": sub_140_value,
            },
            "additionalProperties": False,
        }
        if card_size == "2x4":
            required.append("subPattern")
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def build_plan_tool(card_size: str | None = None, compile_context: dict[str, Any] | None = None) -> dict[str, Any]:
    component_names = sorted(
        generation_components_for_size(card_size) - {"Card", "Grid", "Stack"}
    )
    return {
        "type": "function",
        "function": {
            "name": "submit_card_plan",
            "description": (
                "提交必须展示的信息及每项信息可优先尝试的组件软候选。"
                "本阶段不选择布局；最终布局由 submit_card_jsx 的 JSX 携带。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "info_required": required_facts_schema(
                        CompileContext.from_payload(compile_context),
                        component_names=component_names,
                    ),
                },
                "required": ["info_required"],
                "additionalProperties": False,
            },
        },
    }


def _validate_plan_arguments(
    arguments: dict[str, Any], card_size: str | None,
    prompt_task: dict[str, Any] | None = None,
    compile_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    plan_warnings: list[dict[str, str]] = []
    required_actions = _prompt_action_ids(prompt_task)
    facts = []
    try:
        facts = validate_required_facts(
            arguments.get("info_required"), str((prompt_task or {}).get("userQuery") or ""),
            CompileContext.from_payload(compile_context), warnings=plan_warnings,
        )
        _normalize_info_plan_component_hints(facts, card_size, plan_warnings)
        planned_actions = {fact["actionId"] for fact in facts if "actionId" in fact}
        # The input already specifies these actions. Restore their metadata
        # deterministically; the actual button/slot checks still run on JSX.
        for action_id in sorted(required_actions - planned_actions):
            facts.append({"requirement": f"Preserve requested action {action_id}", "actionId": action_id})
            plan_warnings.append({"severity": "warning", "code": "plan-action-restored",
                                  "message": f"Required input action {action_id!r} was added to the plan"})
    except ConversionError as exc:
        errors.append(str(exc))
    else:
        # Keep the advisory inventory warning, but the Info Plan no longer
        # accepts or persists model-authored data_exclusions.
        try:
            validate_data_inventory(
                facts,
                None,
                CompileContext.from_payload(
                    context_with_initial_values(facts, compile_context)
                ),
                prompt_task,
                plan_warnings,
            )
        except ConversionError as exc:
            errors.append(str(exc))
    if errors:
        return {"ok": False, "error": "; ".join(dict.fromkeys(errors)),
                "findings": [{"severity": "error", "phase": "plan_contract", "code": "plan-contract", "message": error}
                             for error in dict.fromkeys(errors)], "warnings": plan_warnings}
    # The normalized Plan deliberately contains no layout choice. For 2x4,
    # the runner derives it from each semantic JSX candidate.
    result = {"ok": True, "next": "jsx_contract", "plan": {"info_required": facts}}
    if plan_warnings:
        result["warnings"] = plan_warnings
    return result


def validate_plan_arguments(
    arguments: dict[str, Any], card_size: str | None,
    prompt_task: dict[str, Any] | None = None,
    compile_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = _validate_plan_arguments(arguments, card_size, prompt_task, compile_context)
    if not result.get("ok"):
        result.update({
            "phase": "plan_contract", "retryable": True, "retryTarget": "submit_card_plan",
            "instruction": (
                "只修正计划，不生成 JSX。动态信息填写真实 dataId，动作填写 actionId；"
                "text 只用于用户原文中的静态正文，不能填写样例值、字段说明或设计说明。"
                "未覆盖样例时省略 initialValue/valueSourceQuote，未选中的目标字段直接省略。"
                "字段未清点 warning 不要求重试，不要为消除它而展示内部标识或无关信息。"
                "保留原始用户需求，不得靠删除需求通过检查。"
            ),
        })
    return result


def build_agent_tools(
    card_size: str | None = None,
    compile_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    submit_properties: dict[str, Any] = {
        "jsx": {"type": "string"},
        "coverage": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "requirement": {"type": "string"},
                },
                "required": ["requirement"],
                "additionalProperties": False,
            },
        },
        "unmetRequirements": {"type": "array", "items": {"type": "string"}},
    }
    submit_required = ["jsx"]
    # 2x4 semantic JSX already carries the complete layout choice in
    # Card.layout and Region.variant. Derive the public decision from those
    # fields so the model cannot submit a second, divergent copy.
    if card_size != "2x4":
        submit_properties = {"decision": _decision_schema(card_size), **submit_properties}
        submit_required.insert(0, "decision")
    return [
        {
            "type": "function",
            "function": {
                "name": "read_generation_resource",
                "description": "Read the next required card-generation resource in the enforced order.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "enum": [stage.key for stage in RESOURCE_STAGES],
                        }
                    },
                    "required": ["name"],
                    "additionalProperties": False,
                },
            },
        },
        build_plan_tool(card_size, compile_context),
        {
            "type": "function",
            "function": {
                "name": "submit_card_jsx",
                "description": (
                    "Submit one declarative <Card> JSX expression. It must pass syntax, component, "
                    "resource, interaction-reference, and layout validation."
                ),
                "parameters": {
                    "type": "object",
                    "properties": submit_properties,
                    "required": submit_required,
                    "additionalProperties": False,
                },
            },
        },
    ]


# Backward-compatible export for callers that inspect the generic tool list.
# The live agent uses build_agent_tools(task.size) so the model sees only the
# layout names and decision fields valid for the current card size.
AGENT_TOOLS = build_agent_tools()


def execute_tool(name: str, arguments: dict[str, Any], state: OrderedWorkflowState) -> dict[str, Any]:
    if name == "read_generation_resource":
        return state.read_generation_resource(str(arguments.get("name", "")))
    if name == "submit_card_jsx":
        decision = None if state.expected_card_size == "2x4" else arguments.get("decision")
        if decision is not None and not isinstance(decision, dict):
            return {"ok": False, "error": "decision must be an object"}
        return state.submit_card_jsx(
            str(arguments.get("jsx", "")),
            decision,
            arguments.get("coverage"),
            arguments.get("unmetRequirements"),
        )
    return {"ok": False, "error": f"unsupported tool {name!r}"}


def tool_result_message(tool_call_id: str, result: dict[str, Any]) -> dict[str, str]:
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": json.dumps(result, ensure_ascii=False),
    }
