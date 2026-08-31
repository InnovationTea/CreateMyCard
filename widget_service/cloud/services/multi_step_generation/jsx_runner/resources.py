from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from ..jsx_to_a2ui.catalog.bindings import bindable_prop_type_labels
from ..jsx_to_a2ui.catalog.contracts import CONTRACTS, Contract

from .card_sizes import CARD_SIZE_DIMENSIONS, DEFAULT_CARD_SIZE
from .config import RESOURCE_STAGES, SKILL_DIR


_CONTRACT_BLOCK = re.compile(
    r"const\s+componentContracts\s*=\s*Object\.freeze\(\{(?P<body>.*?)\n\s*\}\);",
    re.DOTALL,
)
_CONTRACT_LINE = re.compile(r"^\s*(?P<name>[A-Za-z_$][\w$]*)\s*:\s*\{(?P<body>.*)\},?\s*$")
_ARRAY_FIELD = r"\b{field}\s*:\s*\[(?P<values>[^]]*)\]"


# Model-facing Card appearances follow the 0819 designer source. The browser
# runtime supports neutral-soft only for old JSX, so it is intentionally absent
# here. The JSX-to-A2UI appearance catalog accepts this same generated set.
GENERATION_CARD_APPEARANCES = frozenset({
    "blue-soft",
    "pink-soft",
    "yellow-soft",
    "green-soft",
    "cyan-soft",
    "sunny-gradient",
    "cloudy-gradient",
    "slate-gradient",
    "purple-gradient",
    "orange-gradient",
    "type0-gradient",
})


# Runtime and converter capabilities are intentionally broader than the model-facing
# generation surface. Keep this list explicit so internal/catalog and compatibility
# components do not become generatable merely because runtime has a contract.
GENERATION_COMPONENTS_COMMON = frozenset({
    "Badge",
    "Card",
    "DoubleLineTitle",
    "EmphasisText",
    "EmphasizedData",
    "EventCard",
    "Grid",
    "H_BarChart",
    "InfoBlock",
    "NumericRatio",
    "NumericRatioStack",
    "PillButton",
    "ProgressCircle",
    "ProgressCircleSingle",
    "ProgressLine2",
    "SecondaryBody",
    "SingleLineTitle",
    "Stack",
    "Summary",
    "TableText",
})

GENERATION_COMPONENTS_BY_SIZE = {
    "2x2": frozenset({"DataDisplay", "CircleButton"}),
    "2x4": frozenset({"TopTextBottomValue", "TextBlock", "CardButton"}),
}

# Keep this explicit literal for the Node validator's static contract discovery.
# Size-scoped model reads and Python submission validation use the helper below.
GENERATION_COMPONENTS = frozenset({
    "Badge",
    "Card",
    "CardButton",
    "CircleButton",
    "DataDisplay",
    "DoubleLineTitle",
    "EmphasisText",
    "EmphasizedData",
    "EventCard",
    "Grid",
    "H_BarChart",
    "InfoBlock",
    "NumericRatio",
    "NumericRatioStack",
    "PillButton",
    "ProgressCircle",
    "ProgressCircleSingle",
    "ProgressLine2",
    "SecondaryBody",
    "SingleLineTitle",
    "Stack",
    "Summary",
    "TableText",
    "TextBlock",
    "TopTextBottomValue",
})


def generation_components_for_size(card_size: str | None = None) -> frozenset[str]:
    if card_size is None:
        return GENERATION_COMPONENTS
    try:
        size_specific = GENERATION_COMPONENTS_BY_SIZE[card_size]
    except KeyError as exc:
        allowed = ", ".join(sorted(GENERATION_COMPONENTS_BY_SIZE))
        raise ValueError(
            f"unsupported task size {card_size!r}; expected one of {allowed}"
        ) from exc
    return GENERATION_COMPONENTS_COMMON | size_specific

_GENERATION_FORBIDDEN_PROPS = {
    "Card": frozenset({"background"}),
    "Stack": frozenset({"wrap", "alignSelf"}),
    "PillButton": frozenset({"color"}),
    "CircleButton": frozenset({"color"}),
    "ProgressLine2": frozenset({"barColor"}),
    "ProgressCircleSingle": frozenset({"trackColor", "barColor"}),
    "ProgressCircle": frozenset({"value", "trackColor", "barColor", "density"}),
}

_GENERATION_REQUIRED_PROPS = {
    # Generated cards must state both the semantic task size and the approved
    # palette explicitly. The compiler still accepts legacy numeric Card sizes
    # for old checked-in examples, but they are outside the 0820 generation API.
    "Card": frozenset({"size", "appearance"}),
    # The runtime keeps mode optional for catalog use, but generated cards must
    # choose it from the enclosing Card appearance so the white-40% or
    # black-10% track remains visible against the card background.
    "ProgressLine2": frozenset({"mode"}),
    "H_BarChart": frozenset({"mode"}),
    # Generated cards must opt into the Card-specific icon and palette path.
    # The browser validator already enforces these requirements; keeping them
    # in the prompt contract prevents avoidable validation/retry cycles.
    "ProgressCircleSingle": frozenset({"appearance", "ariaLabel"}),
    "ProgressCircle": frozenset({"appearance", "ariaLabel"}),
    "NumericRatio": frozenset({"appearance"}),
    "NumericRatioStack": frozenset({"appearance"}),
    "PillButton": frozenset({"appearance"}),
    "CircleButton": frozenset({"appearance"}),
}

_GENERATION_ENUM_OVERRIDES = {
    "Card": {
        "size": frozenset(CARD_SIZE_DIMENSIONS),
        "appearance": GENERATION_CARD_APPEARANCES,
    },
    "Stack": {
        # Keep generated JSX inside the exact CSS/A2UI intersection. A2UI has
        # no baseline alignment and the browser ignores top/bottom as
        # align-items values.
        "align": frozenset({"stretch", "flex-start", "center", "flex-end"}),
    },
    "H_BarChart": {"mode": frozenset({"light", "dark"})},
    **{
        name: {"appearance": frozenset({"card"})}
        for name in (
            "ProgressCircleSingle",
            "ProgressCircle",
            "NumericRatio",
            "NumericRatioStack",
            "PillButton",
            "CircleButton",
        )
    },
}

def _quoted_values(source: str) -> set[str]:
    return set(re.findall(r'["\']([^"\']+)["\']', source))


def runtime_component_contracts(runtime_path: Path | None = None) -> dict[str, Contract]:
    path = runtime_path or (SKILL_DIR / "design-system-runtime.jsx")
    source = path.read_text(encoding="utf-8")
    match = _CONTRACT_BLOCK.search(source)
    if not match:
        raise ValueError(f"cannot find componentContracts in {path}")
    result: dict[str, Contract] = {}
    for line in match.group("body").splitlines():
        item = _CONTRACT_LINE.match(line)
        if not item:
            continue
        body = item.group("body")
        fields: dict[str, frozenset[str]] = {}
        for field in ("required", "optional", "requiredOneOf"):
            values = re.search(_ARRAY_FIELD.format(field=field), body)
            fields[field] = frozenset(
                _quoted_values(values.group("values")) if values else set()
            )
        enums: dict[str, frozenset[object]] = {}
        for enum_match in re.finditer(
            r"(?:^|,)\s*(?P<name>[A-Za-z_$][\w$]*)\s*:\s*\[(?P<values>[^]]*)\]",
            body,
        ):
            name = enum_match.group("name")
            if name in {"required", "optional", "requiredOneOf"}:
                continue
            enums[name] = frozenset(_quoted_values(enum_match.group("values")))
        required = fields["required"]
        required_one_of = fields["requiredOneOf"]
        optional = (
            (fields["optional"] - {"children"})
            | (set(enums) - set(required) - set(required_one_of))
        )
        result[item.group("name")] = Contract(
            required=required,
            optional=frozenset(optional),
            required_one_of=required_one_of,
            enums=enums,
        )
    return result


def runtime_component_props(runtime_path: Path | None = None) -> dict[str, set[str]]:
    return {
        name: set(item.required) | set(item.optional) | set(item.required_one_of)
        for name, item in runtime_component_contracts(runtime_path).items()
    }


def generatable_contracts(card_size: str | None = None) -> dict[str, Contract]:
    runtime = runtime_component_props()
    available_components = generation_components_for_size(card_size)
    result: dict[str, Contract] = {}
    for name, item in CONTRACTS.items():
        if name not in available_components:
            continue
        runtime_props = runtime.get(name)
        if (
            runtime_props is None
            or not item.required.issubset(runtime_props)
            or not item.required_one_of.issubset(runtime_props)
        ):
            continue
        forbidden = _GENERATION_FORBIDDEN_PROPS.get(name, frozenset())
        required = item.required | _GENERATION_REQUIRED_PROPS.get(name, frozenset())
        # dataValueMaps is compiler metadata.  It is validated and consumed
        # before the visual runtime, so it need not be a DOM/runtime Prop.
        compiler_metadata = {"dataValueMaps"} if "dataIds" in runtime_props else set()
        optional = (
            (item.optional & (runtime_props | compiler_metadata)) - forbidden
        ) - required
        enums = {
            key: values
            for key, values in (item.enums or {}).items()
            if key in required or key in optional
        }
        for key, values in _GENERATION_ENUM_OVERRIDES.get(name, {}).items():
            if key in required or key in optional:
                enums[key] = values
        result[name] = Contract(
            required=required,
            optional=optional,
            enums=enums,
            required_one_of=item.required_one_of,
        )
    return result


def generation_contract_sync_errors() -> list[str]:
    """Report generated-component contract drift between runtime and converter."""
    runtime = runtime_component_contracts()
    errors: list[str] = []
    declared_sizes = set(GENERATION_COMPONENTS_BY_SIZE)
    expected_sizes = set(CARD_SIZE_DIMENSIONS)
    if declared_sizes != expected_sizes:
        errors.append(
            "size-scoped generation component sets differ from supported Card sizes: "
            f"declared={sorted(declared_sizes)!r}, expected={sorted(expected_sizes)!r}"
        )
    scoped_components = set(GENERATION_COMPONENTS_COMMON)
    for card_size, components in GENERATION_COMPONENTS_BY_SIZE.items():
        common_overlap = set(components) & set(GENERATION_COMPONENTS_COMMON)
        if common_overlap:
            errors.append(
                f"Card size {card_size!r} repeats common generation components: "
                + ", ".join(sorted(common_overlap))
            )
        scoped_components.update(components)
    size_entries = list(GENERATION_COMPONENTS_BY_SIZE.items())
    for index, (left_size, left_components) in enumerate(size_entries):
        for right_size, right_components in size_entries[index + 1:]:
            overlap = set(left_components) & set(right_components)
            if overlap:
                errors.append(
                    f"Card sizes {left_size!r} and {right_size!r} share size-specific "
                    "generation components: " + ", ".join(sorted(overlap))
                )
    if scoped_components != set(GENERATION_COMPONENTS):
        missing = scoped_components - set(GENERATION_COMPONENTS)
        extra = set(GENERATION_COMPONENTS) - scoped_components
        errors.append(
            "GENERATION_COMPONENTS differs from common + size-specific components: "
            f"missing={sorted(missing)!r}, extra={sorted(extra)!r}"
        )
    for name in sorted(GENERATION_COMPONENTS):
        item = CONTRACTS.get(name)
        if item is None:
            errors.append(f"compiler contract is missing generated component {name}")
            continue
        runtime_item = runtime.get(name)
        if runtime_item is None:
            errors.append(f"runtime contract is missing generated component {name}")
            continue
        compiler_props = set(item.required) | set(item.optional) | set(item.required_one_of)
        runtime_props = (
            set(runtime_item.required)
            | set(runtime_item.optional)
            | set(runtime_item.required_one_of)
        )
        missing = runtime_props - compiler_props
        compiler_only_metadata = {
            "dataValueMaps"
        } if "dataIds" in runtime_props else set()
        extra = compiler_props - runtime_props - compiler_only_metadata
        if missing:
            errors.append(
                f"compiler contract for {name} is missing runtime props: {', '.join(sorted(missing))}"
            )
        if extra:
            errors.append(
                f"compiler contract for {name} contains props removed from runtime: "
                f"{', '.join(sorted(extra))}"
            )
        if item.required != runtime_item.required:
            errors.append(
                f"required props differ for {name}: converter={sorted(item.required)!r}, "
                f"runtime={sorted(runtime_item.required)!r}"
            )
        if item.required_one_of != runtime_item.required_one_of:
            errors.append(
                f"required-one-of props differ for {name}: "
                f"converter={sorted(item.required_one_of)!r}, "
                f"runtime={sorted(runtime_item.required_one_of)!r}"
            )
        for prop, runtime_values in (runtime_item.enums or {}).items():
            converter_values = (item.enums or {}).get(prop)
            if converter_values != runtime_values:
                errors.append(
                    f"enum values differ for {name}.{prop}: "
                    f"converter={sorted(converter_values or ())!r}, "
                    f"runtime={sorted(runtime_values)!r}"
                )
    return errors


def format_generation_contract(card_size: str | None = None) -> str:
    lines = [
        "# 可生成 JSX 合同",
        "",
        "只允许提交一个以 <Card> 为根的声明式 JSX 表达式。",
        "禁止原生 HTML、style/className、spread props、变量读取、函数调用、条件表达式、Hooks 和副作用。",
        "属性表达式只允许字符串、数字、布尔值、null，以及 JSON-like 数组/对象；布局必须显式表达。",
        "Stack.alignSelf 与 Stack.wrap 仅属于浏览器 runtime 能力，不属于可生成子集。",
        "禁止使用 Card.background 和仅供实现层覆盖的硬编码颜色属性。",
        "",
        "Card appearance 必选值：" + ", ".join(sorted(GENERATION_CARD_APPEARANCES)),
        "",
        "## 组件",
    ]
    for name, item in generatable_contracts(card_size).items():
        lines.append(f"\n### {name}")
        lines.append("required: " + (", ".join(sorted(item.required)) or "无"))
        lines.append("requiredOneOf: " + (", ".join(sorted(item.required_one_of)) or "无"))
        lines.append("optional: " + (", ".join(sorted(item.optional)) or "无"))
        for prop, type_label in sorted(bindable_prop_type_labels(name).items()):
            lines.append(f"{prop} type: {type_label}")
        for prop, values in sorted((item.enums or {}).items()):
            lines.append(f"{prop}: " + ", ".join(str(value) for value in sorted(values, key=str)))
    return "\n".join(lines) + "\n"


class GenerationResources:
    def __init__(self) -> None:
        self._by_key = {stage.key: stage for stage in RESOURCE_STAGES}

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(stage.key for stage in RESOURCE_STAGES)

    def missing_files(self) -> list[Path]:
        paths = [stage.path for stage in RESOURCE_STAGES if stage.path is not None]
        paths.append(SKILL_DIR / "references" / "components" / "components_common.md")
        paths.extend(
            SKILL_DIR / "references" / "components" / f"components_{size}.md"
            for size in CARD_SIZE_DIMENSIONS
        )
        paths.extend(
            SKILL_DIR / "references" / "layouts" / f"layout_patterns_{size}.md"
            for size in CARD_SIZE_DIMENSIONS
        )
        paths.append(SKILL_DIR / "design-system-runtime.jsx")
        return [path for path in paths if not path.exists()]

    def source_files(self, key: str, *, card_size: str | None = None) -> tuple[Path, ...]:
        """Return the source files whose contents form one model-visible resource."""
        stage = self._by_key.get(key)
        if stage is None:
            raise KeyError(f"unknown generation resource {key!r}")
        if key == "jsx_contract":
            return (SKILL_DIR / "references" / "core.md",)
        if key == "component_style":
            resolved_size = card_size or DEFAULT_CARD_SIZE
            if resolved_size not in CARD_SIZE_DIMENSIONS:
                allowed = ", ".join(sorted(CARD_SIZE_DIMENSIONS))
                raise ValueError(f"unsupported task size {resolved_size!r}; expected one of {allowed}")
            component_dir = SKILL_DIR / "references" / "components"
            return (
                component_dir / "components_common.md",
                component_dir / f"components_{resolved_size}.md",
            )
        if key == "layout_patterns":
            resolved_size = card_size or DEFAULT_CARD_SIZE
            if resolved_size not in CARD_SIZE_DIMENSIONS:
                allowed = ", ".join(sorted(CARD_SIZE_DIMENSIONS))
                raise ValueError(f"unsupported task size {resolved_size!r}; expected one of {allowed}")
            return (
                SKILL_DIR / "references" / "layouts" / f"layout_patterns_{resolved_size}.md",
            )
        assert stage.path is not None
        return (stage.path,)

    def read(self, key: str, *, card_size: str | None = None) -> str:
        source_files = self.source_files(key, card_size=card_size)
        return "\n\n".join(path.read_text(encoding="utf-8") for path in source_files)

def iter_asset_values(value: object, *, key: str | None = None) -> Iterable[str]:
    if isinstance(value, dict):
        for nested_key, nested_value in value.items():
            yield from iter_asset_values(nested_value, key=str(nested_key))
    elif isinstance(value, list):
        for nested in value:
            yield from iter_asset_values(nested, key=key)
    elif key in {"icon", "src", "checkIcon"} and isinstance(value, str):
        yield value
