from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from decimal import Decimal, InvalidOperation
from typing import Any

if "." in (__package__ or ""):
    from ..jsx_to_a2ui.catalog.bindings import (
        BINDABLE_PROPS,
        CompileContext,
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
    from ..jsx_to_a2ui.validation.jsx_preflight import collect_conversion_preflight_errors
else:  # Support top-level package imports.
    from jsx_to_a2ui.catalog.bindings import (
        BINDABLE_PROPS,
        CompileContext,
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
    from jsx_to_a2ui.validation.jsx_preflight import collect_conversion_preflight_errors

from .card_sizes import CARD_SIZE_DIMENSIONS, card_dimensions, task_card_size
from .config import RESOURCE_STAGES
from .resources import (
    GenerationResources,
    generatable_contracts,
    iter_asset_values,
)


@dataclass(slots=True)
class CompiledSubmission:
    source: str
    jsx: str
    messages: list[dict[str, Any]]
    decision: dict[str, Any]
    coverage: list[dict[str, Any]] = field(default_factory=list)
    unmet_requirements: list[str] = field(default_factory=list)
    semantic_status: str = "completed"
    warnings: list[dict[str, str]] = field(default_factory=list)


def submission_reference_ids(
    submission: CompiledSubmission,
) -> tuple[set[str], set[str]]:
    """Return data/action references from the compiled JSX itself.

    Coverage metadata is advisory and may be absent or normalized, so browser
    repair regression checks must derive references from the JSX tree instead.
    """

    cards = extract_card_functions(submission.source)
    return _referenced_binding_ids(cards[next(iter(cards))])


def browser_repair_preservation_findings(
    baseline: CompiledSubmission,
    candidate: CompiledSubmission,
    compile_context: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Detect deterministic semantic regressions introduced by layout repair.

    Removing an action or replacing a previously bound value with its sample
    literal is a definite regression. Completely omitting a data binding can be
    a legitimate way to drop optional content, so that remains advisory.
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
        context = CompileContext.from_payload(compile_context)
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
        errors.append(
            {
                "severity": "error",
                "code": "browser-repair-staticized-binding",
                "message": (
                    "浏览器布局修复删除了动态绑定，却仍把对应样例值显示为静态文本："
                    + "; ".join(
                        f"{binding_id!r} -> {', '.join(locations)}" for binding_id, locations in staticized.items()
                    )
                    + "。请恢复 dataIds，或完整移除真正可舍弃的可见信息。"
                ),
                "details": {"staticizedDataIds": staticized},
            }
        )

    omitted = [value for value in removed_data if value not in staticized]
    if omitted:
        warnings.append(
            {
                "severity": "warning",
                "code": "browser-repair-dropped-binding",
                "message": (
                    "浏览器布局修复省略了此前展示的数据绑定："
                    + ", ".join(repr(value) for value in omitted)
                    + "。仅当这些信息确实可舍弃时才应接受该结果。"
                ),
            }
        )
    return errors, warnings


class LayoutBudgetError(ValidationError):
    """The statically known vertical content cannot fit its allocated region."""


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


def _walk(node: JSXElement):
    yield node
    for child in node.child_elements():
        yield from _walk(child)


def _validate_generation_subset(root: JSXElement, expected_size: str | None = None) -> None:
    actual_size = root.props.get("size")
    resolved_size = expected_size or (actual_size if actual_size in CARD_SIZE_DIMENSIONS else None)
    contracts = generatable_contracts(resolved_size)
    if expected_size is None and resolved_size is None:
        card_contract = contracts["Card"]
        card_enums = dict(card_contract.enums or {})
        card_enums["size"] = card_enums.get("size", frozenset()) | {160}
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
    elif actual_size not in CARD_SIZE_DIMENSIONS and actual_size != 160:
        allowed = ", ".join(repr(item) for item in CARD_SIZE_DIMENSIONS)
        errors.append(
            f"generated Card.size must be one of {allowed}; legacy size={{160}} "
            f"is accepted only when no task size is available, found {actual_size!r}"
        )
    if resolved_size == "2x2":
        info_count = sum(1 for node in _walk(root) if node.tag == "InfoBlock")
        if info_count not in {0, 2}:
            errors.append("a 2x2 Card using InfoBlock must contain exactly two InfoBlock components")
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
    lowered = value.lower()
    match = re.search(r"type\s*[-_ ]?\s*(\d+)(?:\s*[-_ ]\s*([abc]))?", lowered)
    if not match:
        return None
    number, suffix = match.groups()
    variant = re.search(r"variant\s*[-_ ]?\s*([abc])", lowered)
    suffix = suffix or (variant.group(1) if variant else None)
    return f"{int(number)}-{suffix.upper()}" if suffix else str(int(number))


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
        errors.append("decision.layoutPattern must name a documented Type layout")
    appearance = root.props.get("appearance")
    if appearance == "type0-gradient" and pattern != "0":
        errors.append("Card appearance='type0-gradient' may only be used with layout Type 0")
    if pattern == "0" and appearance != "type0-gradient":
        errors.append("layout Type 0 must use Card appearance='type0-gradient'")
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
                errors.append(f"<{node.tag}> resource {source!r} is not an exact src from input assetCandidates")
            if node.tag in {"SingleLineTitle", "DoubleLineTitle"}:
                icon_alt = node.props.get("iconAlt")
                if not isinstance(icon_alt, str) or not icon_alt.strip():
                    errors.append(f"<{node.tag}> with an Icon must declare a non-empty iconAlt")
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
        if node.tag == "Card" and _number(node.props.get("padding", 12)) != 12:
            issues.append(
                "<Card>.padding must be omitted or equal to 12vp so the "
                "documented safe content area remains deterministic"
            )
        if parent is not None and parent.tag == "Grid" and node.props.get("basis") is not None:
            issues.append(
                f"<{node.tag}>.basis has no main-axis meaning as a direct Grid child; "
                "set Grid rows/columns or the child's explicit width/height instead"
            )
        children = node.child_elements()
        for index, child in enumerate(children):
            if child.tag == "CardButton":
                width, height = _card_button_slot_dimensions(node, index)
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
    "DataDisplay": 114,
    "EmphasizedData": 38,
    "ProgressLine1": 25,
    "ProgressCircleSingle": 52,
    "NumericRatio": 16,
    "ChecklistItem": 48,
    "PillButton": 36,
    "CircleButton": 36,
    "InfoBlock": 64,
    "TopTextBottomValue": 68,
    "TextBlock": 48,
}


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
) -> None:
    """Reject action components placed in a slot for another button family."""
    issues: list[str] = []
    pill_buttons = [node for node in _walk(root) if node.tag == "PillButton"]
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
                "2x2 layout Type 0 must contain exactly one business component "
                "and cannot add a title, button, or parallel module; found: "
                + rendered
            )
    info_blocks = [node for node in _walk(root) if node.tag == "InfoBlock"]
    if size == "2x2" and info_blocks and len(info_blocks) != 2:
        issues.append("a 2x2 card using InfoBlock must contain exactly two InfoBlock components")
    if size == "2x2" and info_blocks:
        extra_business_components = [
            node.tag for node in _walk(root) if node.tag not in {"Card", "Stack", "Grid", "InfoBlock"}
        ]
        if extra_business_components:
            issues.append(
                "a 2x2 InfoBlock card may only contain its two InfoBlock business "
                "components; remove: " + ", ".join(dict.fromkeys(extra_business_components))
            )
    if info_blocks:
        appearance = root.props.get("appearance")
        if not isinstance(appearance, str) or not appearance.endswith("-gradient"):
            issues.append("InfoBlock must be placed on a *-gradient Card")
    for ratio_stack in (node for node in _walk(root) if node.tag == "NumericRatioStack"):
        items = ratio_stack.props.get("items")
        if isinstance(items, list) and len(items) != 3:
            issues.append("NumericRatioStack.items must contain exactly three items")
    if size == "2x2" and pattern in {"11-A", "14"} and pill_buttons:
        issues.append(
            f"2x2 layout Type {pattern} only provides a CircleButton action slot and "
            "cannot contain PillButton; select Type 10-A, Type 10-B, Type 10-C, "
            "Type 12, or Type 15 "
            "for a full-width PillButton"
        )

    def is_card_button_slot(node: JSXElement) -> bool:
        if node.tag == "CardButton":
            return True
        children = node.child_elements()
        return node.tag == "Stack" and len(children) == 1 and children[0].tag == "CardButton"

    if size == "2x4":
        for container in _walk(root):
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
            slot_count = sum(is_card_button_slot(child) for child in children)
            if slot_count < 2:
                continue
            if container.tag == "Grid" and (_grid_column_count(container) or 1) > 1:
                columns = _grid_column_count(container)
                if columns != 2 or slot_count not in {3, 4}:
                    issues.append(
                        "a multi-column CardButton Grid must be the documented Type 9 "
                        "layout with two columns and three or four actions"
                    )
            elif container.tag in {"Card", "Stack"} and container.props.get("direction", "column") == "row":
                issues.append(
                    "outside the documented Type 9 Grid, 2x4 CardButton actions must "
                    "be stacked vertically; a single horizontal row is not allowed"
                )
    for node in _walk(root):
        if node.tag != "Stack" or _number(node.props.get("width")) != 36 or _number(node.props.get("height")) != 36:
            continue
        if any(descendant.tag == "PillButton" for descendant in _walk(node) if descendant is not node):
            issues.append(
                "a Stack with width={36} height={36} is a CircleButton action slot and "
                "cannot contain the fixed-width PillButton; use CircleButton or select a "
                "full-width PillButton layout"
            )
    if issues:
        raise ValidationError("; ".join(dict.fromkeys(issues)))


def _validate_progress_line_theme(root: JSXElement) -> None:
    """Keep generated progress components aligned with the Card background."""
    appearance = root.props.get("appearance")
    dark_surface = isinstance(appearance, str) and appearance.endswith("-gradient")
    issues: list[str] = []
    for node in _walk(root):
        if node.tag not in {"ProgressLine2", "H_BarChart"}:
            continue
        mode = node.props.get("mode")
        expected_mode = "dark" if dark_surface else "light"
        if mode != expected_mode:
            issues.append(
                f"{node.tag} on a {'*-gradient' if dark_surface else '*-soft'} Card must use mode='{expected_mode}'"
            )
    if issues:
        raise ValidationError("; ".join(dict.fromkeys(issues)))


def _explicit_height(node: JSXElement) -> float | None:
    return _number(node.props.get("height"))


def _numeric_basis(node: JSXElement) -> float | None:
    return _number(node.props.get("basis"))


def _height_lower_bound(node: JSXElement, value: float) -> float:
    return max(value, _number(node.props.get("minHeight")) or 0)


def _vertical_padding(node: JSXElement) -> float:
    if node.tag == "Stack" and node.props.get("surface") == "backplate":
        return 12
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
) -> tuple[float | None, float | None]:
    """Return only statically provable CardButton parent-slot dimensions."""
    if parent.tag == "Stack":
        width = _number(parent.props.get("width"))
        height = _explicit_height(parent)
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
        return _height_lower_bound(node, 20 if node.props.get("icon") is not None else 18)
    if node.tag == "DoubleLineTitle":
        return _height_lower_bound(node, 40)
    if node.tag == "Summary":
        return _height_lower_bound(node, 14)
    if node.tag == "SecondaryBody":
        return _height_lower_bound(node, 19)
    if node.tag == "EmphasisText":
        return _height_lower_bound(
            node,
            27 + (16 if node.props.get("secondaryText") is not None else 0),
        )
    if node.tag == "ProgressLine2":
        return _height_lower_bound(node, 54)
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
        return _height_lower_bound(node, count * 30 + max(0, count - 1) * 11)
    if node.tag == "ProgressCircle":
        diameter = 96 if node.props.get("size", "sm") == "md" else 44
        return _height_lower_bound(node, diameter + 2 + 14)
    if node.tag == "NumericRatioStack":
        items = node.props.get("items")
        if isinstance(items, list):
            return _height_lower_bound(
                node,
                len(items) * 16 + max(0, len(items) - 1) * 4,
            )
        return _height_lower_bound(node, 0)
    if node.tag == "EventCard":
        return _height_lower_bound(
            node,
            18 + 4 + 16 + (16 if node.props.get("location") is not None else 0),
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
        "so this local flex-allocation risk is advisory only"
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
) -> tuple[float, float] | None:
    start = _number(node.props.get(start_prop))
    end = _number(node.props.get(end_prop))
    size = _number(node.props.get(size_prop))
    if size is None and start is not None and end is not None:
        size = max(0, available - start - end)
    if size is None:
        return None
    if start is not None:
        origin = start
    elif end is not None:
        origin = available - end - size
    else:
        return None
    return origin, origin + size


def _validate_absolute_sibling_geometry(
    node: JSXElement,
    available_width: float | None,
    available_height: float,
    path: str,
    issues: list[str],
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
    rectangles: list[tuple[int, JSXElement, tuple[float, float], tuple[float, float]]] = []
    for index, child in enumerate(absolute_children, start=1):
        horizontal = _absolute_axis_interval(
            child,
            available_width,
            start_prop="left",
            end_prop="right",
            size_prop="width",
        )
        vertical = _absolute_axis_interval(
            child,
            available_height,
            start_prop="top",
            end_prop="bottom",
            size_prop="height",
        )
        if horizontal is not None and vertical is not None:
            rectangles.append((index, child, horizontal, vertical))
    for left_index in range(len(rectangles)):
        first_index, first, first_x, first_y = rectangles[left_index]
        for second_index in range(left_index + 1, len(rectangles)):
            second_number, second, second_x, second_y = rectangles[second_index]
            horizontal_overlap = min(first_x[1], second_x[1]) - max(first_x[0], second_x[0])
            if horizontal_overlap <= 1e-9:
                continue
            vertical_overlap = min(first_y[1], second_y[1]) - max(first_y[0], second_y[0])
            if vertical_overlap > 1e-9:
                issues.append(
                    f"{path}/<Stack>[{first_index}] overlaps "
                    f"{path}/<Stack>[{second_number}] by {_vp(vertical_overlap)}vp vertically"
                )
                continue
            first_is_button = _contains_component(first, "PillButton")
            second_is_button = _contains_component(second, "PillButton")
            if node.props.get("surface") != "backplate" or first_is_button == second_is_button:
                continue
            gap = max(second_y[0] - first_y[1], first_y[0] - second_y[1])
            if gap < 8 - 1e-9:
                issues.append(
                    f"{path} upper content and backplate PillButton require an 8vp gap; "
                    f"found {_vp(gap)}vp"
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
    minimum = _number(node.props.get("minHeight"))
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
        if inner_width is not None and inner_width > 144 + 1e-9:
            issues.append(
                f"{path} CardButton parent slot width must be at most 144vp; "
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
                if column_width > 144 + 1e-9:
                    issues.append(
                        f"{child_path} CardButton Grid column width must be at most 144vp; "
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
            reservation = max(basis, _number(child.props.get("minHeight")) or 0)
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

    remaining = max(0, inner - fixed_total)
    total_weight = sum(weight for _, _, weight in flex_children)
    for index, child in enumerate(children, start=1):
        if child.tag not in {"Stack", "Grid"}:
            continue
        flex_entry = next((entry for entry in flex_children if entry[0] == index), None)
        if flex_entry is not None:
            child_available = remaining * flex_entry[2] / total_weight
            child_minimum = _minimum_height(child)
            if (
                parent_can_close
                and child_minimum > child_available + 1e-9
                and advisory_issues is not None
            ):
                advisory_issues.append(
                    _flex_vertical_risk_message(
                        f"{path}/<{child.tag}>[{index}]",
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


def _validate_layout_budget(
    root: JSXElement,
    advisory_issues: list[str] | None = None,
) -> None:
    dimensions = card_dimensions(root.props.get("size"))
    if dimensions is None:
        return
    height = _number(dimensions[1])
    width = _number(dimensions[0])
    if height is not None:
        issues: list[str] = []
        _validate_vertical_container(
            root,
            height,
            "<Card>",
            issues,
            available_width=width,
            advisory_issues=advisory_issues,
        )
        if issues:
            raise LayoutBudgetError("; ".join(dict.fromkeys(issues)))


def _horizontal_padding(node: JSXElement) -> float:
    if node.tag == "Stack" and node.props.get("surface") == "backplate":
        return 12
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
        "PillButton": 120 if inside_backplate else 136,
        "NumericRatio": 20,
        "InfoBlock": 136,
        "TopTextBottomValue": 296,
    }.get(node.tag, 0)
    if node.tag == "TextBlock":
        items = node.props.get("items")
        count = len(items) if isinstance(items, list) else 0
        intrinsic = count * 64 + max(0, count - 1) * 8
    if node.tag == "ProgressCircleSingle":
        # Only the 52vp ring and the 8vp content gap are renderer-independent.
        # The no-shrink text group is real, but its exact width is font-dependent
        # and is therefore reported separately as an advisory risk.
        intrinsic = 60
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
        "so verify the rendered result instead of treating it as a proven overflow"
    )


def _progress_circle_single_width_risk_message(
    path: str,
    required: float,
    available: float,
) -> str:
    return (
        f"{path} ProgressCircleSingle may need about {_vp(required)}vp while "
        f"the slot provides {_vp(available)}vp; the text group does not shrink, "
        "but this width is font-dependent, so verify it in the browser instead "
        "of treating the estimate as a proven overflow"
    )


def _wrapping_text_candidates(node: JSXElement) -> list[tuple[str, object, float]]:
    if node.tag == "DoubleLineTitle":
        return [("secondaryInfo", node.props.get("secondaryInfo"), 12)]
    if node.tag == "Summary" and "items" not in node.props:
        return [("content", node.props.get("content"), 10)]
    if node.tag == "SecondaryBody" and "items" not in node.props:
        return [("body", node.props.get("body"), 14)]
    if node.tag == "EventCard":
        return [("title", node.props.get("title"), 14)]
    if node.tag == "EmphasisText":
        return [
            ("mainText", node.props.get("mainText"), 20),
            ("secondaryText", node.props.get("secondaryText"), 12),
        ]
    return []


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
    if node.tag in {"Card", "Stack"} and direct_actions and inner > 144 + 1e-9:
        names = ", ".join(dict.fromkeys(child.tag for child in direct_actions))
        issues.append(
            f"{path} is a {_vp(inner)}vp-wide parent slot for {names}; action slots "
            "must stay within one half-card region of at most 144vp"
        )
    if node.tag == "EmphasizedData":
        required_text = _emphasized_data_width(node)
        # Character-based width estimation is not renderer measurement. It must
        # never trigger a model repair, even when the difference looks large.
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
        if not isinstance(value, str) or not value:
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
                _minimum_width(
                    child,
                    inside_backplate=children_inside_backplate,
                ),
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
    dimensions = card_dimensions(root.props.get("size"))
    if dimensions is None:
        return
    width = _number(dimensions[0])
    if width is not None:
        issues: list[str] = []
        warnings: list[str] = []
        _validate_horizontal_container(root, width, "<Card>", issues, warnings)
        if advisory_issues is not None:
            advisory_issues.extend(dict.fromkeys(warnings))
        if issues:
            raise LayoutBudgetError("; ".join(dict.fromkeys(issues)))


def _validate_metric_semantics(
    root: JSXElement,
    advisory_issues: list[tuple[str, str]],
) -> None:
    semantic_issues: list[str] = []
    for node in _walk(root):
        if node.tag not in {"Summary", "SecondaryBody"}:
            continue
        prop = "content" if node.tag == "Summary" else "body"
        items = node.props.get("items")
        if items is not None:
            if prop in node.props:
                semantic_issues.append(f"{node.tag}.{prop} and {node.tag}.items are mutually exclusive")
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
            continue
        data_ids = node.props.get("dataIds")
        if not isinstance(data_ids, dict) or prop not in data_ids:
            continue
        value = node.props.get(prop)
        if metric_requires_label(value):
            advisory_issues.append(
                (
                    "metric-context-risk",
                    f"{node.tag}.{prop}={value!r} is an isolated dynamic metric that may need "
                    "a component whose structure identifies its meaning",
                )
            )
    if semantic_issues:
        raise ValidationError("; ".join(dict.fromkeys(semantic_issues)))


def _unbound_display_values(node: JSXElement):
    allowed = BINDABLE_PROPS.get(node.tag, frozenset())
    data_ids = node.props.get("dataIds")
    bound = set(data_ids) if isinstance(data_ids, dict) else set()
    for prop in sorted(name for name in allowed if not name.startswith("items[].")):
        if prop in node.props and prop not in bound:
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


def _is_complete_numeric_metric(value: Any) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (int, float)):
        return True
    return isinstance(value, str) and _COMPLETE_NUMERIC_METRIC.fullmatch(value) is not None


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
                    "whether Summary or SecondaryBody would express it more clearly.",
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
        status = "completed"
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
    if isinstance(exc, ValidationError):
        return "contract_or_protocol"
    return "conversion"


def _error_retryable(exc: ConversionError) -> bool:
    return not isinstance(exc, A2UIProtocolOutputError)


def _validation_finding(exc: ConversionError) -> dict[str, str]:
    phase = _error_phase(exc)
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
        return {
            "ok": True,
            "resource": key,
            "content": content,
            "next": following.key if following else "submit_card_jsx",
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
        try:
            parsed_compile_context = CompileContext.from_payload(self.compile_context)
            materialize_binding_literals(root, parsed_compile_context)
            expression = _serialize_jsx(root)
            source = wrap_card_source(self.component_name, expression)
        except ConversionError as exc:
            compile_context_error = exc

        findings: list[dict[str, str]] = []
        finding_messages: set[str] = set()
        layout_warning_messages: list[str] = []
        semantic_warning_messages: list[tuple[str, str]] = []

        def add_finding(exc: ConversionError) -> None:
            message = str(exc)
            if message in finding_messages:
                return
            finding_messages.add(message)
            findings.append(_validation_finding(exc))

        if self.validation_enabled:
            validators = [
                lambda: _validate_generation_subset(root, self.expected_card_size),
                lambda: _validate_layout_values(root),
                lambda: _validate_action_slot_compatibility(
                    root,
                    decision,
                    self.expected_card_size,
                ),
                lambda: _validate_progress_line_theme(root),
                lambda: _validate_layout_decision(root, decision, self.expected_card_size),
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
                        lambda: _validate_horizontal_budget(
                            root,
                            layout_warning_messages,
                        ),
                    )
                )
            validators.append(lambda: _validate_metric_semantics(root, semantic_warning_messages))
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

            if compile_context_error is not None:
                add_finding(compile_context_error)
            if parsed_compile_context is not None:
                try:
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
        layout_warnings = [_layout_warning(message) for message in dict.fromkeys(layout_warning_messages)]
        semantic_warnings = [
            _semantic_warning(code, message) for code, message in dict.fromkeys(semantic_warning_messages)
        ]
        warnings = [*layout_warnings, *semantic_warnings, *metadata_warnings]

        if findings:
            first = findings[0]
            result = {
                "ok": False,
                "phase": first["phase"],
                "retryable": True,
                "error": first["message"],
                "findings": findings,
                "instruction": (
                    "fix the JSX by resolving every ERROR and call submit_card_jsx again; "
                    "WARNING entries are "
                    "advisory only and must not be resolved by deleting required information "
                    "or changing business semantics"
                ),
            }
            if warnings:
                result["warnings"] = warnings
            return result

        try:
            messages = compile_source(
                source,
                card=self.component_name,
                compile_contexts={self.component_name: self.compile_context},
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
            coverage=normalized_coverage,
            unmet_requirements=normalized_unmet,
            semantic_status=semantic_status,
            warnings=warnings,
        )
        if self.defer_browser_validation:
            self.pending_submission = prepared
        else:
            self.submission = prepared
        result = {
            "ok": True,
            "pendingBrowserValidation": self.defer_browser_validation,
        }
        if warnings:
            result["warnings"] = warnings
        return result

    def accept_pending_submission(self) -> None:
        if self.pending_submission is None:
            raise RuntimeError("no pending JSX submission to accept")
        self.submission = self.pending_submission
        self.pending_submission = None

    def reject_pending_submission(self) -> None:
        self.pending_submission = None


AGENT_TOOLS = [
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
                "properties": {
                    "jsx": {"type": "string"},
                    "decision": {
                        "type": "object",
                        "properties": {
                            "layoutPattern": {
                                "type": "string",
                                "minLength": 1,
                                "description": (
                                    "从当前 layout_patterns 资源中选择的布局名称，"
                                    "例如 Type 1、Type 10-A、Type 11-A。不得自定义布局名称。"
                                ),
                            },
                        },
                        "required": ["layoutPattern"],
                        "additionalProperties": True,
                    },
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
                },
                "required": ["jsx", "decision"],
                "additionalProperties": False,
            },
        },
    },
]


def execute_tool(name: str, arguments: dict[str, Any], state: OrderedWorkflowState) -> dict[str, Any]:
    if name == "read_generation_resource":
        return state.read_generation_resource(str(arguments.get("name", "")))
    if name == "submit_card_jsx":
        decision = arguments.get("decision")
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
