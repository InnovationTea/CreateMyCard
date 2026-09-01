"""Load CLI Provider Bundles and compile declarative ``.cardtpl`` assets."""

from __future__ import annotations

import ast
import io
import json
import re
import tokenize
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from jsonschema import Draft202012Validator
from pydantic import Field, model_validator

from config.config import get_settings
from models.generation import TaskSpec
from services.template_generation.engine.advanced.models import UxLayoutComponentCapability
from services.template_generation.engine.theme_reference import (
    THEME_REFERENCE_PATHS,
    ThemeReferenceSyntaxError,
    translate_theme_reference_calls,
)

from .models import (
    TEMPLATE_CHILD_SLOT_COMPONENT,
    BusinessTemplateGroup,
    StrictModel,
    TemplateBinding,
    TemplateDefinition,
    TemplateNode,
    TemplateValue,
    TemplateVariant,
)

_COMPONENTS = frozenset(
    {
        "Text",
        "Image",
        "Divider",
        "Progress",
        "Button",
        "Checkbox",
        "Row",
        "Column",
        "List",
        "Stack",
    }
)
_LAYOUT_COMPONENTS = frozenset(
    {
        "SingleFocusLayout",
        "HeroActionLayout",
        "FullIconActionLayout",
        "CompactTwoActionLayout",
        "TwoSupportLayout",
        "WideSingleFocusLayout",
    }
)
_CONDITIONAL_PARAMETER_COMPONENTS = frozenset({"IfParam", "IfMissingParam"})
_SINGLE_CONDITIONAL_BINDING_COMPONENTS = frozenset({"IfBind", "IfMissingBind"})
_GROUPED_CONDITIONAL_BINDING_COMPONENTS = frozenset(
    {"IfAllBind", "IfAnyMissingBind"}
)
_CONDITIONAL_BINDING_COMPONENTS = (
    _SINGLE_CONDITIONAL_BINDING_COMPONENTS
    | _GROUPED_CONDITIONAL_BINDING_COMPONENTS
)
_CONDITIONAL_COMPONENTS = _CONDITIONAL_PARAMETER_COMPONENTS | _CONDITIONAL_BINDING_COMPONENTS
_TEMPLATE_COMPONENTS = _COMPONENTS | _LAYOUT_COMPONENTS | _CONDITIONAL_COMPONENTS
_CONTAINERS = (
    frozenset({"Row", "Column", "List", "Stack"})
    | _LAYOUT_COMPONENTS
    | _CONDITIONAL_COMPONENTS
)
_REFERENCE_CALLS = frozenset(
    {
        "Bind",
        "Param",
        "Asset",
        "Expr",
        "EventAction",
        "_CardTplOptionalParam",
        "_CardTplInterpolation",
        "_CardTplTheme",
        "_CardTplConditional",
    }
)
_FORBIDDEN_KEYS = frozenset({"__proto__", "prototype", "constructor"})
_TEMPLATE_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]{0,63}$")
_REFERENCE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_PROVIDER_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9-]*)+$")
_PROVIDER_VERSION_RE = re.compile(r"^[1-9][0-9]*\.[0-9]+\.[0-9]+(?:-[a-z0-9.-]+)?$")
_MAX_BUNDLE_FILE_BYTES = 1_048_576
_MAX_TEMPLATE_SOURCE_CHARS = 262_144
_MAX_INDEXED_TEMPLATE_CHILDREN = 256
_PROVIDER_TEMPLATE_LAYOUT_KINDS = (
    "WideHero",
    "WideFull",
    "Support",
    "Compact",
    "Hero",
    "Full",
)
_PROVIDER_TEMPLATE_FAMILIES = (
    "BluetoothDeviceOverview",
    "ResourceUsageOverview",
    "AppUsageOverview",
    "HeartRateOverview",
    "ActivityOverview",
    "ScheduleOverview",
    "CountdownOverview",
    "WeatherOverview",
    "BatteryOverview",
    "WorkoutOverview",
    "SleepOverview",
    "DateOverview",
)


class ProviderDataSchema(StrictModel):
    path: str = Field(min_length=1)
    version: str = Field(min_length=1)


class ProviderRuleReference(StrictModel):
    path: str = Field(min_length=1)


class ProviderCapabilityEntry(StrictModel):
    capability_id: str | None = Field(default=None, alias="capabilityId", min_length=1)
    data_domain: str | None = Field(
        default=None,
        alias="dataDomain",
        pattern=r"^/data(?:/[^/~]+(?:~[01][^/~]*)*)*$",
    )
    data_schema: ProviderDataSchema | None = Field(default=None, alias="dataSchema")

    @model_validator(mode="after")
    def data_contract_is_all_or_none(self) -> ProviderCapabilityEntry:
        values = (self.capability_id, self.data_domain, self.data_schema)
        if any(value is not None for value in values) and not all(
            value is not None for value in values
        ):
            raise ValueError(
                "Provider capabilityId, dataDomain and dataSchema must be declared together"
            )
        return self


class ProviderTemplateEntry(StrictModel):
    template_id: str = Field(alias="templateId", min_length=1)
    business_id: str | None = Field(
        default=None,
        alias="businessId",
        pattern=r"^[A-Z][A-Za-z0-9]{0,63}$",
    )
    capability_id: str | None = Field(default=None, alias="capabilityId", min_length=1)
    description: str = Field(min_length=1)
    primary_data: tuple[str, ...] = Field(default=(), alias="primaryData")
    secondary_data: tuple[str, ...] = Field(default=(), alias="secondaryData")
    optional_data: tuple[str, ...] = Field(default=(), alias="optionalData")
    entry: str = Field(min_length=1)

    @model_validator(mode="after")
    def data_paths_are_disjoint(self) -> ProviderTemplateEntry:
        primary = set(self.primary_data)
        secondary = set(self.secondary_data)
        optional = set(self.optional_data)
        paths_are_unique = (
            len(primary) == len(self.primary_data)
            and len(secondary) == len(self.secondary_data)
            and len(optional) == len(self.optional_data)
        )
        if not paths_are_unique:
            raise ValueError("Provider Template data paths must be unique")
        if primary & secondary or primary & optional or secondary & optional:
            raise ValueError(
                "Provider Template primaryData, secondaryData and optionalData must be disjoint"
            )
        for path in (*self.primary_data, *self.secondary_data, *self.optional_data):
            if not _provider_relative_data_path(path):
                raise ValueError(f"Provider Template data path is invalid: {path}")
        has_data = bool(self.primary_data or self.secondary_data or self.optional_data)
        if has_data and self.capability_id is None:
            raise ValueError("Provider data Template must declare capabilityId")
        if self.capability_id is not None and self.business_id is None:
            raise ValueError("Provider data Template must declare businessId")
        if self.capability_id is not None:
            _provider_template_layout_kind(self.template_id)
        return self

    @property
    def supported_card_sizes(self) -> tuple[Literal["2x2", "2x4"], ...]:
        if self.capability_id is None:
            return ()
        layout_kind = _provider_template_layout_kind(self.template_id)
        return ("2x4",) if layout_kind in {"WideHero", "WideFull"} else ("2x2",)

    @property
    def requires_layout_action(self) -> bool:
        if self.capability_id is None:
            return False
        return _provider_template_layout_kind(self.template_id) in {"Hero", "WideHero"}


class ProviderCompatibility(StrictModel):
    template_language: str = Field(alias="templateLanguage")
    catalog_id: str = Field(alias="catalogId")
    a2ui_wire_version: str = Field(alias="a2uiWireVersion")


class ProviderManifest(StrictModel):
    bundle_format: str = Field(alias="bundleFormat")
    provider_id: str = Field(alias="providerId", min_length=1)
    provider_version: str = Field(alias="providerVersion", min_length=1)
    capabilities: tuple[ProviderCapabilityEntry, ...] = ()
    templates: tuple[ProviderTemplateEntry, ...] = ()
    layout_components: tuple[UxLayoutComponentCapability, ...] = Field(
        default=(),
        alias="layoutComponents",
    )
    first_layer_rule: ProviderRuleReference | None = Field(default=None, alias="firstLayerRule")
    second_layer_rule: ProviderRuleReference | None = Field(default=None, alias="secondLayerRule")
    compatibility: ProviderCompatibility

    @model_validator(mode="after")
    def declares_provider_content(self) -> ProviderManifest:
        content = (self.templates, self.layout_components)
        if not any(content):
            raise ValueError("Provider must declare Templates or Layout Components")
        layout_names = tuple(item.name for item in self.layout_components)
        if len(layout_names) != len(set(layout_names)):
            raise ValueError("Provider layoutComponents must be unique")
        return self


@dataclass(frozen=True)
class LoadedProviderBundle:
    manifest: ProviderManifest
    templates: tuple[TemplateDefinition, ...]
    business_groups: tuple[BusinessTemplateGroup, ...]
    first_layer_rule: str
    second_layer_rule: str


@dataclass(frozen=True)
class ProviderTemplateAdmission:
    admitted: bool
    reason: str = ""
    binding_name: str | None = None
    path: str | None = None
    expected_type: str | None = None
    actual_type: str | None = None


@dataclass(frozen=True)
class _UiTemplateSignature:
    properties: dict[str, dict[str, Any]]
    required_params: tuple[str, ...]
    asset_tags: dict[str, tuple[str, ...]]
    accepts_children: bool


@dataclass(frozen=True)
class _UiTemplateData:
    bindings: dict[str, TemplateBinding]
    required_bindings: dict[str, TemplateBinding]
    optional_bindings: dict[str, TemplateBinding]
    body: str


def _data_fields(
    paths: tuple[str, ...],
    output_schema: dict[str, Any],
) -> tuple[dict[str, str], ...]:
    """Preserve the Provider schema type for retrieval across all declared data tiers."""
    fields: list[dict[str, str]] = []
    for path in paths:
        leaf = _schema_leaf(output_schema, path)
        data_type = leaf.get("type") if isinstance(leaf, dict) else None
        if not isinstance(data_type, str):
            raise ValueError(f"Provider Template data path has no schema type: {path}")
        fields.append({"path": path, "type": data_type})
    return tuple(fields)


def load_provider_templates(providers_root: Path) -> tuple[TemplateDefinition, ...]:
    """Compile every registered Provider Bundle below one trusted source root."""
    return tuple(
        definition
        for bundle in load_provider_bundles(providers_root)
        for definition in bundle.templates
    )


def load_provider_bundles(providers_root: Path) -> tuple[LoadedProviderBundle, ...]:
    """Load every Provider Bundle together with its two explicit rule documents."""
    if not providers_root.is_dir():
        return ()
    bundles: list[LoadedProviderBundle] = []
    seen: set[str] = set()
    manifests = sorted(providers_root.glob("*/provider.json"))
    for manifest_path in manifests:
        bundle = load_provider_bundle(manifest_path.parent)
        for definition in bundle.templates:
            if definition.wire_id in seen:
                raise ValueError(f"duplicate Provider Template: {definition.wire_id}")
            seen.add(definition.wire_id)
        bundles.append(bundle)
    return tuple(bundles)


def load_provider_bundle(bundle_root: Path) -> LoadedProviderBundle:
    """Validate one Bundle and compile all referenced CardTemplate files."""
    root = bundle_root.resolve()
    manifest_path = _bundle_file(root, "provider.json")
    payload = _read_object(manifest_path)
    _reject_forbidden_keys(payload)
    manifest = ProviderManifest.model_validate(payload)
    if manifest.bundle_format != "card-provider-bundle/1":
        raise ValueError("unsupported Provider Bundle format")
    if _PROVIDER_ID_RE.fullmatch(manifest.provider_id) is None:
        raise ValueError(f"invalid Provider ID: {manifest.provider_id}")
    if _PROVIDER_VERSION_RE.fullmatch(manifest.provider_version) is None:
        raise ValueError(f"invalid Provider version: {manifest.provider_version}")
    _validate_compatibility(manifest.compatibility)

    template_entries = _unique_template_entries(manifest.templates)
    capabilities = _capabilities_by_id(manifest.capabilities)
    first_layer_rule = (
        _load_rule_document(root, manifest.first_layer_rule, "first-layer")
        if manifest.first_layer_rule is not None
        else ""
    )
    second_layer_rule = (
        _load_rule_document(root, manifest.second_layer_rule, "second-layer")
        if manifest.second_layer_rule is not None
        else ""
    )
    definitions: list[TemplateDefinition] = []
    for wire_id, entry in template_entries.items():
        capability = (
            capabilities.get(entry.capability_id)
            if entry.capability_id is not None
            else None
        )
        if entry.capability_id is not None and capability is None:
            raise ValueError(
                f"Provider Template references an unknown capability: {wire_id}"
            )
        output_schema = _load_data_schema(root, capability) if capability is not None else {}

        template_path = _bundle_file(root, entry.entry)
        template_bytes = _bounded_file_bytes(template_path)
        definition = compile_card_template(
            template_bytes.decode("utf-8"),
            provider_id=manifest.provider_id,
            business_id=entry.business_id,
            expected_wire_id=wire_id,
            expected_capability_id=entry.capability_id,
            data_domain=capability.data_domain if capability is not None else None,
            description=entry.description,
            supported_card_sizes=entry.supported_card_sizes,
            primary_data=entry.primary_data,
            secondary_data=entry.secondary_data,
            optional_data=entry.optional_data,
            output_schema=output_schema,
        )
        definition = definition.model_copy(
            update={"requires_layout_action": entry.requires_layout_action}
        )
        _validate_provider_template_data_contract(definition, entry)
        definitions.append(definition)

    referenced_capability_ids = {
        entry.capability_id
        for entry in template_entries.values()
        if entry.capability_id is not None
    }
    if set(capabilities) != referenced_capability_ids:
        unused = sorted(set(capabilities) - referenced_capability_ids)
        raise ValueError(f"Provider capability has no Templates: {unused}")
    business_groups = _derive_business_groups(manifest, template_entries, definitions)
    return LoadedProviderBundle(
        manifest,
        tuple(definitions),
        business_groups,
        first_layer_rule,
        second_layer_rule,
    )


def compile_card_template(
    source: str,
    *,
    provider_id: str,
    business_id: str | None,
    expected_wire_id: str,
    expected_capability_id: str | None,
    data_domain: str | None,
    description: str,
    supported_card_sizes: tuple[Literal["2x2", "2x4"], ...],
    primary_data: tuple[str, ...],
    secondary_data: tuple[str, ...],
    optional_data: tuple[str, ...],
    output_schema: dict[str, Any],
) -> TemplateDefinition:
    """Compile one non-executable ``cardtpl/1`` source into the trusted Template IR."""
    if len(source) > _MAX_TEMPLATE_SOURCE_CHARS:
        raise ValueError("Provider Template source exceeds the size limit")
    if re.search(r"(?m)^\s*#Template\s+[A-Za-z]", source) is None:
        raise ValueError("Provider Template must use the cardtpl/1 UI syntax")
    return _compile_ui_card_template(
        source,
        provider_id=provider_id,
        business_id=business_id,
        expected_wire_id=expected_wire_id,
        expected_capability_id=expected_capability_id,
        data_domain=data_domain,
        description=description,
        supported_card_sizes=supported_card_sizes,
        primary_data=primary_data,
        secondary_data=secondary_data,
        optional_data=optional_data,
        output_schema=output_schema,
    )


def _compile_ui_card_template(
    source: str,
    *,
    provider_id: str,
    business_id: str | None,
    expected_wire_id: str,
    expected_capability_id: str | None,
    data_domain: str | None,
    description: str,
    supported_card_sizes: tuple[Literal["2x2", "2x4"], ...],
    primary_data: tuple[str, ...],
    secondary_data: tuple[str, ...],
    optional_data: tuple[str, ...],
    output_schema: dict[str, Any],
) -> TemplateDefinition:
    """Compile the UI-oriented ``#Template Id(props, ...children)`` syntax."""
    signature, block = _ui_template_block(source, expected_wire_id)
    signature_contract = _ui_template_signature(signature)
    properties = signature_contract.properties
    required_params = signature_contract.required_params
    asset_tags = signature_contract.asset_tags
    accepts_children = signature_contract.accepts_children
    template_data = _ui_template_data(block, output_schema)
    bindings = template_data.bindings
    required_bindings = template_data.required_bindings
    optional_bindings = template_data.optional_bindings
    body = template_data.body
    required_data = (*primary_data, *secondary_data)
    if not {binding.path for binding in required_bindings.values()} <= set(required_data):
        raise ValueError(
            "Provider Template primaryData/secondaryData do not match $path declarations: "
            f"{expected_wire_id}"
        )
    if not {binding.path for binding in optional_bindings.values()} <= set(optional_data):
        raise ValueError(
            "Provider Template optionalData does not match $optionalPath declarations: "
            f"{expected_wire_id}"
        )
    if bindings and (expected_capability_id is None or data_domain is None):
        raise ValueError("Provider data Template requires capabilityId and dataDomain")
    transformed = _translate_ui_template_body(body)
    root = _parse_component_body(transformed)
    if root.component in _CONDITIONAL_COMPONENTS:
        raise ValueError("Provider Template conditional cannot be the Template root")
    spreads_children = any(node.spread_children for node in _walk_template_nodes(root))
    indexed_children = _template_child_slot_indexes(root)
    uses_children = spreads_children or bool(indexed_children)
    if uses_children and not accepts_children:
        raise ValueError("Provider Template body uses children without ...children")
    if accepts_children and not uses_children:
        raise ValueError("Provider Template declares ...children but does not place children")
    if spreads_children and indexed_children:
        raise ValueError("Provider Template cannot mix children and children[index] slots")
    _validate_template_child_slot_indexes(indexed_children)
    _validate_interpolation_bindings(root, bindings)
    _validate_event_action_placement(root)
    binding_references, parameter_references = _template_references(root)
    if not binding_references <= set(bindings):
        unknown_data = sorted(binding_references - set(bindings))
        raise ValueError(f"unknown Provider Template data reference: {unknown_data}")
    if not parameter_references <= set(properties):
        raise ValueError(
            "unknown Provider Template props reference: "
            f"{sorted(parameter_references - set(properties))}"
        )
    guarded_params, guarded_bindings = _validate_conditional_guards(
        root,
        properties,
        bindings,
        set(required_params),
        set(required_bindings),
    )
    if not set(required_bindings) <= binding_references:
        raise ValueError("Provider Template must reference every $path declaration")
    if not binding_references <= set(required_bindings) | guarded_bindings:
        raise ValueError("Provider Template $optionalPath reference must be conditionally guarded")
    if not set(required_params) <= parameter_references:
        raise ValueError("Provider Template must reference every required prop")
    if not parameter_references <= set(required_params) | guarded_params:
        raise ValueError("Provider Template optional prop reference must be conditionally guarded")
    schema = {
        "type": "object",
        "properties": properties,
        "required": list(required_params),
        "additionalProperties": False,
    }
    Draft202012Validator.check_schema(schema)
    node_count, depth = _template_shape(root)
    template_id, version = _split_wire_id(expected_wire_id)
    variant = TemplateVariant.model_validate(
        {
            "size": "default",
            "parametersSchema": schema,
            "supportedCardSizes": supported_card_sizes,
            "supportedRoles": [],
            "requiredBindings": tuple(required_bindings),
            "optionalBindings": tuple(optional_bindings),
            "root": root.model_dump(by_alias=True),
            "expandedNodeBudget": max(node_count, 1),
            "expandedDepthBudget": max(depth, 1),
        }
    )
    layout_action_opacity = _ui_root_literal_option(root, "_layoutActionBackgroundOpacity")
    layout_action_style = (
        {"backgroundOpacity": layout_action_opacity}
        if isinstance(layout_action_opacity, (int, float))
        and not isinstance(layout_action_opacity, bool)
        else None
    )
    return TemplateDefinition.model_validate(
        {
            "templateId": template_id,
            "version": version,
            "description": description,
            "domainTags": [],
            "compatibleThemeProfileIds": [],
            "allowedParentComponents": [],
            "actionPolicy": "none",
            "layoutActionStyle": layout_action_style,
            "supportedSizes": ["default"],
            "allowedDesignTokens": [],
            "allowedLayoutTokens": [],
            "assetParameterSemanticTags": asset_tags,
            "providerId": provider_id,
            "businessId": business_id,
            "capabilityId": expected_capability_id,
            "dataDomain": data_domain,
            "primaryData": primary_data,
            "primaryDataFields": _data_fields(primary_data, output_schema),
            "secondaryData": secondary_data,
            "secondaryDataFields": _data_fields(secondary_data, output_schema),
            "optionalData": optional_data,
            "optionalDataFields": _data_fields(optional_data, output_schema),
            "acceptsChildren": accepts_children,
            "bindings": {
                name: binding.model_dump(by_alias=True) for name, binding in bindings.items()
            },
            "sourceFormat": "cardtpl/1",
            "variants": [variant.model_dump(by_alias=True)],
        }
    )


def _ui_root_literal_option(root: TemplateNode, name: str) -> Any:
    for value in root.values:
        if value.kind != "object":
            continue
        item = value.properties.get(name)
        if item is not None and item.kind == "literal":
            return item.value
    return None


def _ui_template_block(source: str, expected_wire_id: str) -> tuple[str, str]:
    lines = source.splitlines()
    blocks: dict[str, tuple[str, str]] = {}
    index = 0
    header_re = re.compile(
        r"^\s*#Template\s+([A-Za-z][A-Za-z0-9-]{0,63}@[1-9][0-9]*)\((.*)\)\s*$"
    )
    while index < len(lines):
        if not lines[index].strip():
            index += 1
            continue
        match = header_re.fullmatch(lines[index])
        if match is None:
            raise ValueError(f"expected UI #Template declaration at line {index + 1}")
        wire_id, signature = match.groups()
        if wire_id in blocks:
            raise ValueError(f"duplicate Provider Template block: {wire_id}")
        end = index + 1
        while end < len(lines) and lines[end].strip() != "#End":
            end += 1
        if end == len(lines):
            raise ValueError(f"Provider Template is not closed: {wire_id}")
        body_lines = lines[slice(index + 1, end)]
        blocks[wire_id] = (signature.strip(), "\n".join(body_lines).strip())
        index = end + 1
    try:
        return blocks[expected_wire_id]
    except KeyError as exc:
        raise ValueError(f"Provider Template ID mismatch: {expected_wire_id}") from exc


def _ui_template_signature(
    signature: str,
) -> _UiTemplateSignature:
    match = re.fullmatch(r"props\s*:\s*\{(.*)\}\s*(,\s*\.\.\.children\s*)?", signature)
    if match is None:
        raise ValueError("Provider Template signature must declare props and optional ...children")
    props_source, raw_children = match.groups()
    properties: dict[str, dict[str, Any]] = {}
    required: list[str] = []
    asset_tags: dict[str, tuple[str, ...]] = {}
    type_map = {
        "string": "string",
        "asset": "string",
        "number": "number",
        "integer": "integer",
        "boolean": "boolean",
    }
    for raw_prop in (item.strip() for item in props_source.split(",")):
        if not raw_prop:
            continue
        prop_match = re.fullmatch(
            r"([A-Za-z_][A-Za-z0-9_]*)(\?)?\s*:\s*(string|asset|number|integer|boolean)",
            raw_prop,
        )
        if prop_match is None:
            raise ValueError(f"invalid Provider Template prop: {raw_prop}")
        name, optional, declared_type = prop_match.groups()
        if name in properties:
            raise ValueError(f"duplicate Provider Template prop: {name}")
        properties[name] = {"type": type_map[declared_type]}
        if declared_type == "asset":
            asset_tags[name] = ()
        if optional is None:
            required.append(name)
    return _UiTemplateSignature(
        properties=properties,
        required_params=tuple(required),
        asset_tags=asset_tags,
        accepts_children=raw_children is not None,
    )


def _ui_template_data(
    block: str,
    output_schema: dict[str, Any],
) -> _UiTemplateData:
    match = re.match(r"\s*data\s*=\s*\{", block)
    if match is None:
        raise ValueError("Provider Template must declare one data object")
    open_index = block.find("{", match.start())
    close_index = _matching_delimiter(block, open_index, "{", "}")
    source = block[slice(open_index + 1, close_index)]
    body = block[slice(close_index + 1, None)].strip()
    bindings: dict[str, TemplateBinding] = {}
    required: dict[str, TemplateBinding] = {}
    optional: dict[str, TemplateBinding] = {}
    entry_re = re.compile(
        r"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*\$(path|optionalPath)\(\s*"
        r"(\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*')\s*\)\s*(?:,|$)",
        re.S,
    )
    cursor = 0
    for item in entry_re.finditer(source):
        if source[slice(cursor, item.start())].strip():
            raise ValueError("invalid Provider Template data declaration")
        name, function_name, raw_path = item.groups()
        path = ast.literal_eval(raw_path)
        if name in bindings or not isinstance(path, str) or not _provider_relative_data_path(path):
            raise ValueError(f"invalid Provider Template data binding: {name}")
        leaf = _schema_leaf(output_schema, path)
        if not isinstance(leaf, dict) or leaf.get("type") not in {
            "string",
            "integer",
            "number",
            "boolean",
            "null",
        }:
            raise ValueError(f"Provider Template data path does not match outputSchema: {path}")
        binding = TemplateBinding(path=path, type=leaf["type"])
        bindings[name] = binding
        (required if function_name == "path" else optional)[name] = binding
        cursor = item.end()
    if source[cursor:].strip():
        raise ValueError("invalid Provider Template data declaration")
    if not body:
        raise ValueError("Provider Template body is empty")
    return _UiTemplateData(
        bindings=bindings,
        required_bindings=required,
        optional_bindings=optional,
        body=body,
    )


def _matching_delimiter(
    source: str,
    open_index: int,
    opener: str,
    closer: str,
) -> int:
    depth = 0
    quote: str | None = None
    escaped = False
    for index in range(open_index, len(source)):
        char = source[index]
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {'"', "'", "`"}:
            quote = char
        elif char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return index
    raise ValueError("Provider Template data object is not closed")


def _translate_ui_template_body(body: str) -> str:
    body = re.sub(
        r"\b(IfPresent|IfAbsent)\(\s*"
        r"data\.([A-Za-z_][A-Za-z0-9_]*)\s*&\s*"
        r"data\.([A-Za-z_][A-Za-z0-9_]*)\s*,",
        _translate_grouped_binding_guard,
        body,
    )
    body = re.sub(
        r"\b(IfPresent|IfAbsent)\(\s*data\.([A-Za-z_][A-Za-z0-9_]*)\s*,",
        lambda match: ("IfBind" if match.group(1) == "IfPresent" else "IfMissingBind")
        + f'("{match.group(2)}",',
        body,
    )
    body = re.sub(
        r"\b(IfPresent|IfAbsent)\(\s*props\.([A-Za-z_][A-Za-z0-9_]*)\s*,",
        lambda match: (
            "IfParam" if match.group(1) == "IfPresent" else "IfMissingParam"
        )
        + f'("{match.group(2)}",',
        body,
    )
    return re.sub(
        r"\bprops\?\.\s*([A-Za-z_][A-Za-z0-9_]*)",
        lambda match: f'_CardTplOptionalParam("{match.group(1)}")',
        body,
    )


def _translate_grouped_binding_guard(match: re.Match[str]) -> str:
    component = "IfAllBind" if match.group(1) == "IfPresent" else "IfAnyMissingBind"
    binding_names = [match.group(2), match.group(3)]
    serialized_names = json.dumps(binding_names, separators=(",", ":"))
    return f"{component}({serialized_names},"


def _validate_provider_template_data_contract(
    definition: TemplateDefinition,
    entry: ProviderTemplateEntry,
) -> None:
    referenced = {binding.path for binding in definition.bindings.values()}
    for variant in definition.variants:
        properties = variant.parameters_schema.get("properties", {})
        for parameter in properties.values():
            if isinstance(parameter, dict):
                referenced.update(parameter.get("sourcePaths", ()))
    declared = set(entry.primary_data) | set(entry.secondary_data) | set(entry.optional_data)
    if referenced <= declared:
        return
    missing = sorted(referenced - declared)
    raise ValueError(
        "Provider Template data contract does not match CardTemplate references: "
        f"{entry.template_id}; missing={missing}"
    )


def _provider_relative_data_path(value: str) -> bool:
    return bool(
        isinstance(value, str)
        and value.startswith("/")
        and not value.startswith("/data/")
        and _binding_pointer_is_encodable(value)
    )


def _provider_template_layout_kind(wire_id: str) -> str:
    template_id, separator, _version = wire_id.rpartition("@")
    if not separator:
        raise ValueError(f"Provider Template ID must include a version: {wire_id}")
    for layout_kind in _PROVIDER_TEMPLATE_LAYOUT_KINDS:
        if template_id.endswith(layout_kind):
            return layout_kind
    allowed = ", ".join(_PROVIDER_TEMPLATE_LAYOUT_KINDS)
    raise ValueError(
        f"Provider Template ID must end with one layout kind ({allowed}): {wire_id}"
    )


def provider_template_family_identity(wire_id: str) -> tuple[str, str] | None:
    """Resolve one UI-specific Template ID to its business family and shape."""
    identity: tuple[str, str] | None = None
    template_id, separator, raw_version = wire_id.rpartition("@")
    if separator:
        for base in _PROVIDER_TEMPLATE_FAMILIES:
            if template_id == base:
                singleton = {"CountdownOverview": "countdown", "WorkoutOverview": "latest"}
                shape = singleton.get(base)
                if shape is not None:
                    identity = (f"{base}@{raw_version}", shape)
                break
            if template_id.startswith(base):
                suffix = template_id.removeprefix(base)
                if suffix:
                    identity = (f"{base}@{raw_version}", suffix[:1].lower() + suffix[1:])
                    break
    return identity


def provider_template_layout_kind(wire_id: str) -> str | None:
    """Return the normalized layout suffix for one Provider business Template."""
    template_id, separator, _version = wire_id.rpartition("@")
    if not separator:
        return None
    for base in _PROVIDER_TEMPLATE_FAMILIES:
        if template_id.startswith(base):
            return _provider_template_layout_kind(wire_id)
    return None


def _parse_component_body(body: str) -> TemplateNode:
    if not body:
        raise ValueError("Provider Template body is empty")
    if re.search(
        r"\b(?:_CardTplConditional|_CardTplInterpolation|_CardTplTheme)\s*\(",
        body,
    ):
        raise ValueError("Provider Template uses a reserved internal name")
    try:
        with_template_strings = _translate_template_strings(body)
        with_theme_calls = translate_theme_reference_calls(
            with_template_strings,
            "_CardTplTheme",
        )
        with_conditionals = _translate_compile_time_conditionals(with_theme_calls)
    except ThemeReferenceSyntaxError as exc:
        raise ValueError(str(exc)) from exc
    translated = _python_compatible_source(with_conditionals)
    try:
        module = ast.parse(translated, mode="exec")
    except SyntaxError as exc:
        raise ValueError(f"Provider Template body syntax error: {exc.msg}") from exc
    if len(module.body) != 1 or not isinstance(module.body[0], ast.Expr):
        raise ValueError("Provider Template body must contain exactly one component")
    return _component_node(module.body[0].value)


def _component_node(node: ast.AST) -> TemplateNode:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        raise ValueError("Provider Template body accepts direct component calls only")
    if node.keywords:
        raise ValueError("Provider Template component calls do not accept keyword arguments")
    component = node.func.id
    if component not in _TEMPLATE_COMPONENTS:
        raise ValueError(f"unsupported Provider Template component: {component}")
    values: list[TemplateValue] = []
    children: list[TemplateNode] = []
    child_started = False
    spread_children = False
    for argument in node.args:
        if isinstance(argument, ast.Name) and argument.id == "children":
            if component not in _CONTAINERS or spread_children:
                raise ValueError("Provider Template children may appear once in a container")
            child_started = True
            spread_children = True
            continue
        child_index = _indexed_template_child(argument)
        if child_index is not None:
            if component not in _CONTAINERS:
                raise ValueError("Provider Template leaf cannot contain children[index]")
            child_started = True
            children.append(_template_child_slot(child_index))
            continue
        is_reference = _is_reference_call(argument)
        if isinstance(argument, ast.Call) and not is_reference:
            child_started = True
            children.append(_component_node(argument))
            continue
        if child_started:
            raise ValueError("Provider Template values must precede child components")
        values.append(_template_value(argument))
    if children and component not in _CONTAINERS:
        raise ValueError(f"Provider Template leaf cannot contain children: {component}")
    if spread_children and component not in _CONTAINERS:
        raise ValueError(f"Provider Template leaf cannot spread children: {component}")
    if component in _GROUPED_CONDITIONAL_BINDING_COMPONENTS:
        if len(values) != 1 or len(children) != 1:
            raise ValueError(
                f"Provider Template {component} requires two binding names and one child"
            )
        _grouped_conditional_binding_names(values[0])
    elif component in _CONDITIONAL_COMPONENTS:
        has_single_value = len(values) == 1
        has_literal_name = has_single_value and values[0].kind == "literal"
        has_string_name = has_literal_name and isinstance(values[0].value, str)
        if not has_string_name or len(children) != 1:
            raise ValueError(
                f"Provider Template {component} requires one parameter name and one child"
            )
    return TemplateNode(
        component=component,
        values=tuple(values),
        children=tuple(children),
        spreadChildren=spread_children,
    )


def _grouped_conditional_binding_names(value: TemplateValue) -> tuple[str, str]:
    if value.kind != "array" or len(value.items) != 2:
        raise ValueError(
            "Provider Template grouped conditional requires two binding names"
        )
    binding_names: list[str] = []
    for item in value.items:
        if item.kind != "literal" or not isinstance(item.value, str):
            raise ValueError(
                "Provider Template grouped conditional binding must be a string"
            )
        binding_names.append(item.value)
    first_name, second_name = binding_names
    if first_name == second_name:
        raise ValueError(
            "Provider Template grouped conditional bindings must be different"
        )
    return first_name, second_name


def _indexed_template_child(node: ast.AST) -> int | None:
    if not isinstance(node, ast.Subscript):
        return None
    if not isinstance(node.value, ast.Name) or node.value.id != "children":
        return None
    index_node = node.slice
    is_integer = isinstance(index_node, ast.Constant) and isinstance(index_node.value, int)
    if not is_integer or isinstance(index_node.value, bool):
        raise ValueError("Provider Template children index must be a non-negative integer literal")
    index = index_node.value
    if index < 0 or index >= _MAX_INDEXED_TEMPLATE_CHILDREN:
        raise ValueError("Provider Template children index is outside the supported range")
    return index


def _template_child_slot(index: int) -> TemplateNode:
    return TemplateNode(
        component=TEMPLATE_CHILD_SLOT_COMPONENT,
        values=(TemplateValue(kind="literal", value=index),),
    )


def _template_child_slot_indexes(root: TemplateNode) -> tuple[int, ...]:
    indexes: list[int] = []
    for node in _walk_template_nodes(root):
        if node.component != TEMPLATE_CHILD_SLOT_COMPONENT:
            continue
        value = node.values[0].value if len(node.values) == 1 else None
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("Provider Template contains an invalid children slot")
        indexes.append(value)
    return tuple(indexes)


def _validate_template_child_slot_indexes(indexes: tuple[int, ...]) -> None:
    if not indexes:
        return
    if len(indexes) != len(set(indexes)):
        raise ValueError("Provider Template children indexes must be unique")
    if sorted(indexes) != list(range(len(indexes))):
        raise ValueError("Provider Template children indexes must be contiguous from zero")


def _template_value(node: ast.AST) -> TemplateValue:
    owner = node.value if isinstance(node, ast.Attribute) else None
    has_supported_owner = isinstance(owner, ast.Name) and owner.id in {"props", "data"}
    has_valid_name = isinstance(node, ast.Attribute) and _REFERENCE_NAME_RE.fullmatch(node.attr)
    if has_supported_owner and has_valid_name:
        if not isinstance(owner, ast.Name) or not isinstance(node, ast.Attribute):
            raise ValueError("Provider Template reference is invalid")
        return TemplateValue(
            kind="parameter" if owner.id == "props" else "binding",
            name=node.attr,
        )
    if _is_reference_call(node):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            raise ValueError("Provider Template reference call is invalid")
        if node.func.id == "EventAction":
            return _event_action_value(node)
        if node.func.id == "_CardTplOptionalParam":
            raise ValueError(
                "Provider Template optional props access is only supported in EventAction"
            )
        if node.func.id == "_CardTplInterpolation":
            return _interpolation_value(node)
        if node.func.id == "Expr":
            if node.keywords or len(node.args) != 1:
                raise ValueError("Expr requires one template string")
            argument = node.args[0]
            if (
                not isinstance(argument, ast.Call)
                or not isinstance(argument.func, ast.Name)
                or argument.func.id != "_CardTplInterpolation"
            ):
                raise ValueError("Expr requires one backtick template string")
            interpolation = _interpolation_value(argument)
            return TemplateValue(kind="expression", items=interpolation.items)
        if node.func.id == "_CardTplConditional":
            return _compile_time_conditional_value(node)
        if node.func.id == "_CardTplTheme":
            args = _call_literal_args(node, "$theme")
            path = args[0] if len(args) == 1 else None
            if not isinstance(path, str) or path not in THEME_REFERENCE_PATHS:
                raise ValueError("$theme requires one approved Theme path")
            return TemplateValue(kind="theme", name=path)
        args = _call_literal_args(node, node.func.id)
        if len(args) != 1 or not isinstance(args[0], str):
            raise ValueError(f"{node.func.id} requires one string name")
        kind = "binding" if node.func.id == "Bind" else "parameter"
        return TemplateValue(kind=kind, name=args[0])
    if isinstance(node, ast.Constant):
        value = node.value
        if value is None or isinstance(value, (str, int, float, bool)):
            return TemplateValue(kind="literal", value=value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _literal_value(node)
        return TemplateValue(kind="literal", value=value)
    if isinstance(node, ast.List):
        return TemplateValue(
            kind="array",
            items=tuple(_template_value(item) for item in node.elts),
        )
    if isinstance(node, ast.Dict):
        properties: dict[str, TemplateValue] = {}
        for key_node, value_node in zip(node.keys, node.values, strict=True):
            key = _literal_value(key_node)
            if not isinstance(key, str):
                raise ValueError("Provider Template object keys must be strings")
            if key in _FORBIDDEN_KEYS or key in properties:
                raise ValueError(f"invalid Provider Template object key: {key}")
            properties[key] = _template_value(value_node)
        return TemplateValue(kind="object", properties=properties)
    raise ValueError(
        "Provider Template values must be literals, bindings, template strings, "
        "compile-time conditionals, Expr, EventAction, Param, Asset or $theme"
    )


def _compile_time_conditional_value(call: ast.Call) -> TemplateValue:
    if call.keywords or len(call.args) != 3:
        raise ValueError("Provider Template compile-time conditional requires three operands")
    items = tuple(_template_value(argument) for argument in call.args)
    condition = items[0]
    if condition.kind not in {"binding", "parameter"}:
        raise ValueError(
            "Provider Template compile-time conditional condition must be data.xxx or props.xxx"
        )
    for branch in items[1:]:
        if branch.kind not in {
            "binding",
            "parameter",
            "literal",
            "compile-time-conditional",
        }:
            raise ValueError(
                "Provider Template compile-time conditional branches only support "
                "data, props, literals or nested conditionals"
            )
    return TemplateValue(kind="compile-time-conditional", items=items)


def _event_action_value(call: ast.Call) -> TemplateValue:
    if call.keywords or len(call.args) != 1:
        raise ValueError("EventAction requires one props parameter")
    argument = call.args[0]
    if isinstance(argument, ast.Call):
        function = argument.func
        is_optional_param = (
            isinstance(function, ast.Name) and function.id == "_CardTplOptionalParam"
        )
        if not is_optional_param:
            raise ValueError("EventAction requires one props parameter")
        args = _call_literal_args(argument, "props optional access")
        name = args[0] if len(args) == 1 else None
        if not isinstance(name, str) or not _REFERENCE_NAME_RE.fullmatch(name):
            raise ValueError("EventAction requires one props parameter")
        return TemplateValue(
            kind="event-action",
            items=(TemplateValue(kind="optional-parameter", name=name),),
        )
    if not isinstance(argument, ast.Attribute):
        raise ValueError("EventAction requires one props parameter")
    owner = argument.value
    valid_owner = isinstance(owner, ast.Name) and owner.id == "props"
    valid_name = _REFERENCE_NAME_RE.fullmatch(argument.attr) is not None
    if not valid_owner or not valid_name:
        raise ValueError("EventAction requires one props parameter")
    return TemplateValue(
        kind="event-action",
        items=(TemplateValue(kind="parameter", name=argument.attr),),
    )


def _interpolation_value(call: ast.Call) -> TemplateValue:
    args = _call_literal_args(call, "template string")
    if len(args) != 1 or not isinstance(args[0], str):
        raise ValueError("CardTemplate interpolation is invalid")
    source = args[0]
    parts: list[TemplateValue] = []
    cursor = 0
    matches = tuple(
        re.finditer(
            r"\$\{(?:(props|data)\.)?([A-Za-z_][A-Za-z0-9_]*)\}",
            source,
        )
    )
    if not matches:
        raise ValueError("CardTemplate interpolation requires one ${binding}")
    for match in matches:
        literal = source[slice(cursor, match.start())]
        if "${" in literal:
            raise ValueError("CardTemplate interpolation contains an invalid placeholder")
        if literal:
            parts.append(TemplateValue(kind="literal", value=literal))
        namespace, name = match.groups()
        parts.append(
            TemplateValue(
                kind="parameter" if namespace == "props" else "binding",
                name=name,
            )
        )
        cursor = match.end()
    literal = source[slice(cursor, None)]
    if "${" in literal:
        raise ValueError("CardTemplate interpolation contains an invalid placeholder")
    if literal:
        parts.append(TemplateValue(kind="literal", value=literal))
    return TemplateValue(kind="interpolation", items=tuple(parts))


def _binding_pointer_is_encodable(pointer: str) -> bool:
    parts = pointer.removeprefix("/").split("/")
    return all(part.isdigit() or _REFERENCE_NAME_RE.fullmatch(part) is not None for part in parts)


def _schema_leaf(schema: dict[str, Any], pointer: str) -> dict[str, Any] | None:
    current: Any = schema
    for raw_part in pointer.removeprefix("/").split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict):
            return None
        if current.get("type") == "array":
            if part != "0":
                return None
            current = current.get("items")
            continue
        properties = current.get("properties")
        if not isinstance(properties, dict) or part not in properties:
            return None
        current = properties[part]
    return current if isinstance(current, dict) else None


def _call_literal_args(call: ast.Call, label: str) -> list[Any]:
    if call.keywords:
        raise ValueError(f"{label} does not accept keyword arguments")
    return [_literal_value(argument) for argument in call.args]


def _literal_value(node: ast.AST | None) -> Any:
    if node is None:
        raise ValueError("Provider Template dictionary unpacking is forbidden")
    if isinstance(node, ast.Constant):
        value = node.value
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        operand = _literal_value(node.operand)
        if isinstance(operand, bool) or not isinstance(operand, (int, float)):
            raise ValueError("Provider Template unary signs require numbers")
        return operand if isinstance(node.op, ast.UAdd) else -operand
    if isinstance(node, ast.List):
        return [_literal_value(item) for item in node.elts]
    if isinstance(node, ast.Dict):
        result: dict[str, Any] = {}
        for key_node, value_node in zip(node.keys, node.values, strict=True):
            key = _literal_value(key_node)
            if not isinstance(key, str) or key in _FORBIDDEN_KEYS or key in result:
                raise ValueError(f"invalid Provider Template metadata key: {key}")
            result[key] = _literal_value(value_node)
        return result
    raise ValueError("Provider Template directives accept literal data only")


def _translate_template_strings(source: str) -> str:
    translated: list[str] = []
    quote: str | None = None
    escaped = False
    comment = False
    index = 0
    while index < len(source):
        char = source[index]
        if comment:
            translated.append(char)
            comment = char != "\n"
            index += 1
            continue
        if quote is not None:
            translated.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in {'"', "'"}:
            quote = char
            translated.append(char)
            index += 1
            continue
        if char == "#":
            comment = True
            translated.append(char)
            index += 1
            continue
        if char == "`":
            value, index = _read_template_string(source, index)
            translated.append(f"_CardTplInterpolation({value!r})")
            continue
        translated.append(char)
        index += 1
    return "".join(translated)


def _read_template_string(source: str, start: int) -> tuple[str, int]:
    value: list[str] = []
    index = start + 1
    while index < len(source):
        char = source[index]
        if char == "`":
            return "".join(value), index + 1
        if char == "\\":
            if index + 1 >= len(source):
                break
            following = source[index + 1]
            if following in {"`", "\\"}:
                value.append(following)
            else:
                value.extend((char, following))
            index += 2
            continue
        value.append(char)
        index += 1
    raise ValueError("CardTemplate interpolation is not closed")


def _translate_compile_time_conditionals(source: str) -> str:
    """Lower parenthesized ``condition ? first : second`` into trusted IR calls."""
    result = _translate_compile_time_conditional_segments(source)
    if _contains_unquoted_question_mark(result):
        raise ValueError(
            "Provider Template compile-time conditional must wrap each ternary in parentheses"
        )
    return result


def _translate_compile_time_conditional_segments(source: str) -> str:
    translated: list[str] = []
    delimiter_pairs = {"(": ")", "[": "]", "{": "}"}
    index = 0
    while index < len(source):
        char = source[index]
        if char in {'"', "'"}:
            end = _quoted_source_end(source, index)
            translated.append(source[slice(index, end)])
            index = end
            continue
        if char == "#":
            end = source.find("\n", index)
            if end < 0:
                translated.append(source[index:])
                index = len(source)
            else:
                translated.append(source[slice(index, end + 1)])
                index = end + 1
            continue
        closer = delimiter_pairs.get(char)
        if closer is None:
            translated.append(char)
            index += 1
            continue
        end = _matching_delimiter(source, index, char, closer)
        inner = _translate_compile_time_conditional_segments(source[slice(index + 1, end)])
        parts = _compile_time_conditional_parts(inner) if char == "(" else None
        if parts is None:
            translated.extend((char, inner, closer))
        else:
            condition, present_value, fallback_value = parts
            translated.append(
                f"_CardTplConditional({condition},{present_value},{fallback_value})"
            )
        index = end + 1
    return "".join(translated)


def _quoted_source_end(source: str, start: int) -> int:
    quote = source[start]
    escaped = False
    for index in range(start + 1, len(source)):
        char = source[index]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == quote:
            return index + 1
    raise ValueError("Provider Template string literal is not closed")


def _compile_time_conditional_parts(source: str) -> tuple[str, str, str] | None:
    question_index: int | None = None
    colon_index: int | None = None
    has_top_level_comma = False
    delimiter_pairs = {"(": ")", "[": "]", "{": "}"}
    index = 0
    while index < len(source):
        char = source[index]
        if char in {'"', "'"}:
            index = _quoted_source_end(source, index)
            continue
        closer = delimiter_pairs.get(char)
        if closer is not None:
            index = _matching_delimiter(source, index, char, closer) + 1
            continue
        if char == ",":
            has_top_level_comma = True
            break
        if char == "?":
            if question_index is not None:
                raise ValueError(
                    "Provider Template compile-time conditional must parenthesize nested ternaries"
                )
            question_index = index
        elif char == ":" and question_index is not None:
            if colon_index is not None:
                raise ValueError(
                    "Provider Template compile-time conditional has multiple fallback branches"
                )
            colon_index = index
        index += 1
    result: tuple[str, str, str] | None = None
    if not has_top_level_comma and question_index is not None:
        if colon_index is None:
            raise ValueError("Provider Template compile-time conditional is missing ':'")
        condition = source[:question_index].strip()
        present_value = source[slice(question_index + 1, colon_index)].strip()
        fallback_prefix = source[: colon_index + 1]
        fallback_value = source.removeprefix(fallback_prefix).strip()
        if not condition or not present_value or not fallback_value:
            raise ValueError("Provider Template compile-time conditional operand is empty")
        result = condition, present_value, fallback_value
    return result


def _contains_unquoted_question_mark(source: str) -> bool:
    index = 0
    while index < len(source):
        if source[index] in {'"', "'"}:
            index = _quoted_source_end(source, index)
            continue
        if source[index] == "?":
            return True
        index += 1
    return False


def _python_compatible_source(source: str) -> str:
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except tokenize.TokenError as exc:
        raise ValueError(f"Provider Template tokenization failed: {exc.args[0]}") from exc
    translated: list[tokenize.TokenInfo] = []
    literals = {"true": "True", "false": "False", "null": "None"}
    for index, token in enumerate(tokens):
        value = literals.get(token.string, token.string)
        token_type = token.type
        if token.type == tokenize.NAME and _next_token_is_colon(tokens, index):
            value = repr(token.string)
            token_type = tokenize.STRING
        translated.append(tokenize.TokenInfo(token_type, value, token.start, token.end, token.line))
    return tokenize.untokenize(translated)


def _next_token_is_colon(tokens: list[tokenize.TokenInfo], index: int) -> bool:
    ignored = {
        tokenize.INDENT,
        tokenize.DEDENT,
        tokenize.NL,
        tokenize.NEWLINE,
        tokenize.COMMENT,
    }
    for candidate in tokens[slice(index + 1, None)]:
        if candidate.type in ignored:
            continue
        return candidate.type == tokenize.OP and candidate.string == ":"
    return False


def _is_reference_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _REFERENCE_CALLS
    )


def _split_wire_id(wire_id: str) -> tuple[str, int]:
    if "@" not in wire_id:
        raise ValueError(f"Provider Template ID must be versioned: {wire_id}")
    template_id, raw_version = wire_id.rsplit("@", 1)
    if _TEMPLATE_ID_RE.fullmatch(template_id) is None:
        raise ValueError(f"invalid Provider Template ID: {wire_id}")
    if not raw_version.isdigit() or raw_version.startswith("0"):
        raise ValueError(f"invalid Provider Template version: {wire_id}")
    return template_id, int(raw_version)


def _template_shape(root: TemplateNode) -> tuple[int, int]:
    if root.component == TEMPLATE_CHILD_SLOT_COMPONENT:
        return 0, 0
    if root.component in _CONDITIONAL_COMPONENTS:
        return _template_shape(root.children[0])
    if root.component == "Text" and root.values and root.values[0].kind == "interpolation":
        return 1 + len(root.values[0].items), 2
    child_shapes = [_template_shape(child) for child in root.children]
    count = 1 + sum(shape[0] for shape in child_shapes)
    depth = 1 + max((shape[1] for shape in child_shapes), default=0)
    return count, depth


def _template_references(root: TemplateNode) -> tuple[set[str], set[str]]:
    bindings: set[str] = set()
    parameters: set[str] = set()

    def visit_value(value: TemplateValue) -> None:
        if value.kind == "binding" and value.name:
            bindings.add(value.name)
        elif value.kind in {"parameter", "optional-parameter"} and value.name:
            parameters.add(value.name)
        for item in value.items:
            visit_value(item)
        for item in value.properties.values():
            visit_value(item)

    def visit_node(node: TemplateNode) -> None:
        for value in node.values:
            visit_value(value)
        for child in node.children:
            visit_node(child)

    visit_node(root)
    return bindings, parameters


def _validate_conditional_guards(
    root: TemplateNode,
    properties: dict[str, Any],
    bindings: dict[str, TemplateBinding],
    required_params: set[str],
    required_bindings: set[str],
) -> tuple[set[str], set[str]]:
    guarded_params: set[str] = set()
    guarded_bindings: set[str] = set()

    def visit_value(
        value: TemplateValue,
        active_param_guards: set[str],
        active_binding_guards: set[str],
    ) -> None:
        if value.kind == "compile-time-conditional":
            condition, present_value, fallback_value = value.items
            next_param_guards = set(active_param_guards)
            next_binding_guards = set(active_binding_guards)
            if condition.kind == "parameter" and condition.name:
                guarded_params.add(condition.name)
                next_param_guards.add(condition.name)
            elif condition.kind == "binding" and condition.name:
                guarded_bindings.add(condition.name)
                next_binding_guards.add(condition.name)
            visit_value(present_value, next_param_guards, next_binding_guards)
            visit_value(fallback_value, active_param_guards, active_binding_guards)
            return
        if value.kind == "optional-parameter" and value.name:
            if value.name in required_params:
                raise ValueError(
                    "Provider Template optional props access requires an optional prop: "
                    f"{value.name}"
                )
            guarded_params.add(value.name)
        elif value.kind == "parameter" and value.name:
            if value.name not in required_params and value.name not in active_param_guards:
                raise ValueError(
                    "Provider Template optional Param/Asset must be nested under "
                    f"IfPresent(props.{value.name}, ...) or tested by a compile-time conditional"
                )
        elif value.kind == "binding" and value.name:
            if value.name not in required_bindings and value.name not in active_binding_guards:
                raise ValueError(
                    "Provider Template optional Bind must be nested under "
                    f"IfPresent(data.{value.name}, ...) or tested by a compile-time conditional"
                )
        for item in value.items:
            visit_value(item, active_param_guards, active_binding_guards)
        for item in value.properties.values():
            visit_value(item, active_param_guards, active_binding_guards)

    def visit(
        node: TemplateNode,
        active_param_guards: set[str],
        active_binding_guards: set[str],
    ) -> None:
        if node.component in _CONDITIONAL_PARAMETER_COMPONENTS:
            parameter_name = node.values[0].value
            if not isinstance(parameter_name, str):
                raise ValueError("Provider Template conditional parameter must be a string")
            if parameter_name not in properties:
                raise ValueError(
                    f"unknown Provider Template conditional parameter: {parameter_name}"
                )
            guarded_params.add(parameter_name)
            child_param_guards = set(active_param_guards)
            if node.component == "IfParam":
                child_param_guards.add(parameter_name)
            visit(node.children[0], child_param_guards, active_binding_guards)
            return
        if node.component in _SINGLE_CONDITIONAL_BINDING_COMPONENTS:
            binding_name = node.values[0].value
            if not isinstance(binding_name, str):
                raise ValueError("Provider Template conditional binding must be a string")
            if binding_name not in bindings:
                raise ValueError(f"unknown Provider Template conditional binding: {binding_name}")
            guarded_bindings.add(binding_name)
            child_binding_guards = set(active_binding_guards)
            if node.component == "IfBind":
                child_binding_guards.add(binding_name)
            visit(node.children[0], active_param_guards, child_binding_guards)
            return
        if node.component in _GROUPED_CONDITIONAL_BINDING_COMPONENTS:
            binding_names = _grouped_conditional_binding_names(node.values[0])
            unknown_bindings = set(binding_names) - set(bindings)
            if unknown_bindings:
                unknown_name = sorted(unknown_bindings)[0]
                raise ValueError(
                    f"unknown Provider Template conditional binding: {unknown_name}"
                )
            guarded_bindings.update(binding_names)
            child_binding_guards = set(active_binding_guards)
            if node.component == "IfAllBind":
                child_binding_guards.update(binding_names)
            visit(node.children[0], active_param_guards, child_binding_guards)
            return
        for value in node.values:
            visit_value(value, active_param_guards, active_binding_guards)
        for child in node.children:
            visit(child, active_param_guards, active_binding_guards)

    visit(root, set(), set())
    return guarded_params, guarded_bindings


def _validate_interpolation_bindings(
    root: TemplateNode,
    bindings: dict[str, TemplateBinding],
) -> None:
    for node in _walk_template_nodes(root):
        for index, value in enumerate(node.values):
            if value.kind == "interpolation" and (node.component != "Text" or index != 0):
                raise ValueError("CardTemplate interpolation must be the first Text value")
            _validate_dynamic_template_value(value, bindings, direct=True)


def _validate_event_action_placement(root: TemplateNode) -> None:
    for node in _walk_template_nodes(root):
        for value in node.values:
            if not _contains_template_value_kind(value, "event-action"):
                continue
            event_action = value.properties.get("onClick") if value.kind == "object" else None
            has_direct_event_action = (
                event_action is not None and event_action.kind == "event-action"
            )
            other_values = (
                item
                for key, item in value.properties.items()
                if key != "onClick"
            )
            nested_elsewhere = any(
                _contains_template_value_kind(item, "event-action") for item in other_values
            )
            if not has_direct_event_action or nested_elsewhere:
                raise ValueError("EventAction must be the direct onClick option")


def _validate_dynamic_template_value(
    value: TemplateValue,
    bindings: dict[str, TemplateBinding],
    *,
    direct: bool,
) -> None:
    if value.kind == "interpolation" and not direct:
        raise ValueError("CardTemplate interpolation must be a direct Text value")
    if value.kind in {"interpolation", "expression"}:
        has_binding = False
        for item in value.items:
            binding = bindings.get(item.name) if item.kind == "binding" else None
            if binding is not None:
                has_binding = True
            if (
                value.kind == "interpolation"
                and binding is not None
                and binding.data_type != "string"
            ):
                raise ValueError(f"CardTemplate interpolation must use strings: {item.name}")
        if value.kind == "expression" and not has_binding:
            raise ValueError("CardTemplate Expr must reference at least one binding")
        return
    for item in value.items:
        _validate_dynamic_template_value(item, bindings, direct=False)
    for item in value.properties.values():
        _validate_dynamic_template_value(item, bindings, direct=False)


def _contains_template_value_kind(value: TemplateValue, kind: str) -> bool:
    return any(
        item.kind == kind or _contains_template_value_kind(item, kind)
        for item in (*value.items, *value.properties.values())
    )


def _walk_template_nodes(root: TemplateNode) -> Iterator[TemplateNode]:
    yield root
    for child in root.children:
        yield from _walk_template_nodes(child)


def _skip_whitespace(source: str, offset: int) -> int:
    while offset < len(source) and source[offset].isspace():
        offset += 1
    return offset


def _bundle_file(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute():
        raise ValueError(f"Provider Bundle path must be relative: {relative}")
    resolved = (root / candidate).resolve()
    if root not in resolved.parents or not resolved.is_file():
        raise ValueError(f"Provider Bundle file is unavailable: {relative}")
    return resolved


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(_bounded_file_bytes(path))
    if not isinstance(value, dict):
        raise ValueError(f"Provider Bundle JSON must be an object: {path.name}")
    return value


def _load_rule_document(
    root: Path,
    reference: ProviderRuleReference,
    layer: str,
) -> str:
    relative = Path(reference.path)
    if relative.suffix.lower() != ".md":
        raise ValueError(f"Provider {layer} rule must be a Markdown file")
    path = _bundle_file(root, reference.path)
    try:
        content = _bounded_file_bytes(path).decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise ValueError(f"Provider {layer} rule must be UTF-8") from exc
    if not content:
        raise ValueError(f"Provider {layer} rule must not be empty")
    return content


def _bounded_file_bytes(path: Path) -> bytes:
    if path.stat().st_size > _MAX_BUNDLE_FILE_BYTES:
        raise ValueError(f"Provider Bundle file exceeds the size limit: {path.name}")
    return path.read_bytes()


def _reject_forbidden_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in _FORBIDDEN_KEYS:
                raise ValueError(f"forbidden Provider Bundle key: {key}")
            _reject_forbidden_keys(child)
    elif isinstance(value, list):
        for child in value:
            _reject_forbidden_keys(child)


def _validate_compatibility(compatibility: ProviderCompatibility) -> None:
    if compatibility.template_language != "cardtpl/1":
        raise ValueError("unsupported Provider Template language")
    if compatibility.catalog_id != "ohos.a2ui.extended.catalog.form":
        raise ValueError("Provider Bundle Catalog mismatch")
    if compatibility.a2ui_wire_version != "v0.9":
        raise ValueError("Provider Bundle A2UI wire version mismatch")


def _unique_template_entries(
    entries: tuple[ProviderTemplateEntry, ...],
) -> dict[str, ProviderTemplateEntry]:
    result: dict[str, ProviderTemplateEntry] = {}
    for entry in entries:
        _split_wire_id(entry.template_id)
        if entry.template_id in result:
            raise ValueError(f"duplicate Provider Template entry: {entry.template_id}")
        result[entry.template_id] = entry
    return result


def _capabilities_by_id(
    capabilities: tuple[ProviderCapabilityEntry, ...],
) -> dict[str, ProviderCapabilityEntry]:
    result: dict[str, ProviderCapabilityEntry] = {}
    for capability in capabilities:
        capability_id = capability.capability_id
        if capability_id is None:
            raise ValueError("Provider capability must declare capabilityId")
        if capability_id in result:
            raise ValueError(f"duplicate Provider capability: {capability_id}")
        result[capability_id] = capability
    return result


def _derive_business_groups(
    manifest: ProviderManifest,
    entries: dict[str, ProviderTemplateEntry],
    definitions: list[TemplateDefinition],
) -> tuple[BusinessTemplateGroup, ...]:
    definitions_by_id = {definition.wire_id: definition for definition in definitions}
    business_ids = tuple(
        dict.fromkeys(
            entry.business_id for entry in entries.values() if entry.business_id is not None
        )
    )
    groups: list[BusinessTemplateGroup] = []
    for business_id in business_ids:
        group_entries = tuple(
            entry for entry in entries.values() if entry.business_id == business_id
        )
        template_ids = tuple(entry.template_id for entry in group_entries)
        capability_ids = tuple(
            dict.fromkeys(
                entry.capability_id
                for entry in group_entries
                if entry.capability_id is not None
            )
        )
        supported_sizes = _business_supported_sizes(
            tuple(definitions_by_id[template_id] for template_id in template_ids)
        )
        descriptions = tuple(dict.fromkeys(entry.description for entry in group_entries))
        groups.append(
            BusinessTemplateGroup(
                name=business_id,
                provider_id=manifest.provider_id,
                description=" ".join(descriptions),
                supported_card_sizes=supported_sizes,
                data_capability_ids=capability_ids,
                local_template_ids=template_ids,
            )
        )
    return tuple(groups)


def _business_supported_sizes(
    definitions: tuple[TemplateDefinition, ...],
) -> tuple[Literal["2x2", "2x4"], ...]:
    declared: set[Literal["2x2", "2x4"]] = set()
    has_unrestricted_variant = False
    for definition in definitions:
        for variant in definition.variants:
            declared.update(variant.supported_card_sizes)
            if not variant.supported_card_sizes:
                has_unrestricted_variant = True
    if has_unrestricted_variant:
        return ("2x2", "2x4")
    return tuple(size for size in ("2x2", "2x4") if size in declared)


def _load_data_schema(
    root: Path,
    capability: ProviderCapabilityEntry,
) -> dict[str, Any]:
    if capability.data_schema is None or capability.capability_id is None:
        raise ValueError("Layout Provider capability has no dataSchema")
    schema_path = _resolve_data_schema(root, capability.data_schema)
    payload = json.loads(_bounded_file_bytes(schema_path))
    _reject_forbidden_keys(payload)
    schema: Any
    if isinstance(payload, list):
        matches = [
            item
            for item in payload
            if isinstance(item, dict) and item.get("id") == capability.capability_id
        ]
        if len(matches) != 1:
            raise ValueError(
                f"Provider dataSchema capability resolution failed: {capability.capability_id}"
            )
        schema = matches[0].get("outputSchema")
    elif isinstance(payload, dict) and payload.get("id") == capability.capability_id:
        schema = payload.get("outputSchema")
    else:
        schema = payload
    if not isinstance(schema, dict):
        raise ValueError(
            f"Provider dataSchema must resolve to an object: {capability.capability_id}"
        )
    Draft202012Validator.check_schema(schema)
    return schema


def _resolve_data_schema(
    root: Path,
    data_schema: ProviderDataSchema,
) -> Path:
    relative = Path(data_schema.path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Provider dataSchema path must be relative")
    data_root = get_settings().data_root.resolve()
    upstream_path = (data_root / relative).resolve()
    if data_root in upstream_path.parents and upstream_path.is_file():
        upstream_relative = upstream_path.relative_to(data_root)
        if data_schema.version not in upstream_relative.parts:
            raise ValueError("Provider upstream dataSchema version does not match its path")
        return upstream_path
    return _bundle_file(root, data_schema.path)


def provider_template_admission(
    definition: TemplateDefinition,
    task_spec: TaskSpec,
    card_spec: dict[str, Any] | None,
) -> ProviderTemplateAdmission:
    context_admission = provider_template_context_admission(definition, task_spec)
    if not context_admission.admitted:
        return context_admission
    if definition.source_format != "cardtpl/1":
        return ProviderTemplateAdmission(True)
    if not definition.bindings:
        return ProviderTemplateAdmission(True)
    capability_id = definition.capability_id
    if not capability_id:
        return ProviderTemplateAdmission(False, "missing-capability-id")
    root = _provider_data_root(card_spec, capability_id)
    if isinstance(root, ProviderTemplateAdmission):
        return root
    if definition.data_domain is not None and root != definition.data_domain:
        return ProviderTemplateAdmission(False, "data-domain-mismatch", path=root)
    failures: list[ProviderTemplateAdmission] = []
    for variant in definition.variants:
        admission = _provider_variant_binding_admission(
            definition,
            variant,
            task_spec,
            root,
        )
        if admission.admitted:
            return admission
        failures.append(admission)
    return failures[0] if failures else ProviderTemplateAdmission(False, "variant-unavailable")


def provider_template_variant_admission(
    definition: TemplateDefinition,
    variant: TemplateVariant,
    task_spec: TaskSpec,
    card_spec: dict[str, Any] | None,
) -> ProviderTemplateAdmission:
    context_admission = provider_template_context_admission(definition, task_spec)
    if not context_admission.admitted:
        return context_admission
    if definition.source_format != "cardtpl/1":
        return ProviderTemplateAdmission(True)
    if not definition.bindings:
        return ProviderTemplateAdmission(True)
    capability_id = definition.capability_id
    if not capability_id:
        return ProviderTemplateAdmission(False, "missing-capability-id")
    root = _provider_data_root(card_spec, capability_id)
    if isinstance(root, ProviderTemplateAdmission):
        return root
    if definition.data_domain is not None and root != definition.data_domain:
        return ProviderTemplateAdmission(False, "data-domain-mismatch", path=root)
    return _provider_variant_binding_admission(definition, variant, task_spec, root)


def provider_template_context_admission(
    definition: TemplateDefinition,
    task_spec: TaskSpec,
) -> ProviderTemplateAdmission:
    """Apply Provider-owned constraints that depend on the selected generation context."""
    if definition.requires_layout_action and not task_spec.eventCandidates:
        return ProviderTemplateAdmission(False, "layout-action-required")
    return ProviderTemplateAdmission(True)


def _provider_variant_binding_admission(
    definition: TemplateDefinition,
    variant: TemplateVariant,
    task_spec: TaskSpec,
    root: str,
) -> ProviderTemplateAdmission:
    for relative_path in definition.required_data:
        path = f"{root.rstrip('/')}{relative_path}"
        if _task_spec_schema_leaf(task_spec.dataModelSchema, path) is None:
            return ProviderTemplateAdmission(
                False,
                "required-data-unavailable",
                path=path,
            )
    for name in variant.required_bindings:
        binding = definition.bindings[name]
        path = f"{root.rstrip('/')}{binding.path}"
        leaf = _task_spec_schema_leaf(task_spec.dataModelSchema, path)
        if leaf is None:
            return ProviderTemplateAdmission(
                False,
                "binding-path-unavailable",
                binding_name=name,
                path=path,
                expected_type=binding.data_type,
            )
        actual_type = leaf.get("type")
        if not _provider_binding_types_match(binding.data_type, actual_type):
            return ProviderTemplateAdmission(
                False,
                "binding-type-mismatch",
                binding_name=name,
                path=path,
                expected_type=binding.data_type,
                actual_type=str(actual_type),
            )
    values_by_field = _provider_sample_values_by_field(task_spec.dataModelSchema)
    properties = variant.parameters_schema.get("properties", {})
    for name in variant.parameters_schema.get("required", ()):
        if name in definition.asset_parameter_semantic_tags:
            continue
        candidates = list(dict.fromkeys(values_by_field.get(name, ())))
        if len(candidates) != 1:
            return ProviderTemplateAdmission(
                False,
                "parameter-value-unavailable",
                binding_name=name,
            )
        expected_type = properties.get(name, {}).get("type")
        if not _parameter_value_matches_type(candidates[0], expected_type):
            return ProviderTemplateAdmission(
                False,
                "parameter-type-mismatch",
                binding_name=name,
                expected_type=str(expected_type),
                actual_type=type(candidates[0]).__name__,
            )
    return ProviderTemplateAdmission(True)


def _provider_sample_values_by_field(value: object) -> dict[str, tuple[object, ...]]:
    collected: dict[str, list[object]] = {}

    def visit(current: object, field_name: str | None = None) -> None:
        if isinstance(current, dict) and "sampleValue" in current and field_name:
            sample = current["sampleValue"]
            if sample is None or isinstance(sample, (str, int, float, bool)):
                collected.setdefault(field_name, []).append(sample)
            return
        if isinstance(current, dict):
            for key, child in current.items():
                visit(child, key)
        elif isinstance(current, list):
            for child in current[:1]:
                visit(child, field_name)

    visit(value)
    return {key: tuple(values) for key, values in collected.items()}


def _parameter_value_matches_type(value: object, expected: object) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return False


def _provider_data_root(
    card_spec: dict[str, Any] | None,
    capability_id: str,
) -> str | ProviderTemplateAdmission:
    if card_spec is None:
        return ProviderTemplateAdmission(False, "card-spec-unavailable")
    raw_bindings = card_spec.get("dataBindings")
    if not isinstance(raw_bindings, list):
        return ProviderTemplateAdmission(False, "data-bindings-unavailable")
    roots = {
        item.get("writeResultTo")
        for item in raw_bindings
        if isinstance(item, dict)
        and item.get("capabilityId") == capability_id
        and _valid_runtime_data_root(item.get("writeResultTo"))
    }
    if not roots:
        return ProviderTemplateAdmission(False, "capability-binding-unavailable")
    if len(roots) > 1:
        return ProviderTemplateAdmission(False, "capability-binding-ambiguous")
    return next(iter(roots))


def _valid_runtime_data_root(value: Any) -> bool:
    return isinstance(value, str) and (value == "/data" or value.startswith("/data/"))


def _task_spec_schema_leaf(
    schema: dict[str, Any],
    pointer: str,
) -> dict[str, Any] | None:
    current: Any = schema
    for raw_part in pointer.removeprefix("/").split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            current = current.get(part)
            continue
        if isinstance(current, list) and part == "0" and current:
            current = current[0]
            continue
        return None
    if not isinstance(current, dict) or not isinstance(current.get("type"), str):
        return None
    return current


def _provider_binding_types_match(provider_type: str, data_type: Any) -> bool:
    return provider_type == data_type or (provider_type == "integer" and data_type == "number")


__all__ = [
    "LoadedProviderBundle",
    "ProviderTemplateAdmission",
    "compile_card_template",
    "load_provider_bundle",
    "load_provider_bundles",
    "load_provider_templates",
    "provider_template_admission",
    "provider_template_variant_admission",
    "provider_template_family_identity",
    "provider_template_layout_kind",
]
