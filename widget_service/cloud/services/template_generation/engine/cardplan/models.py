"""Strict immutable models for the trusted Python CardPlan implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

TEMPLATE_CHILD_SLOT_COMPONENT = "__CardTplChildSlot"
_BUSINESS_TEMPLATE_SUPPORTED_LAYOUTS = (
    "SingleFocusLayout",
    "HeroActionLayout",
    "FullIconActionLayout",
    "CompactTwoActionLayout",
    "TwoSupportLayout",
    "WideSingleFocusLayout",
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceSpan(StrictModel):
    start: int = Field(ge=0)
    end: int = Field(ge=0)


class HybridLimits(StrictModel):
    max_raw_components: int = Field(gt=0)
    max_expanded_components: int = Field(gt=0)
    max_nesting_depth: int = Field(gt=0)
    vertical_budget_vp: int = Field(gt=0)


class ActionBinding(StrictModel):
    action_id: str
    event_id: str = Field(exclude=True)
    display_label: str
    call: str
    args: dict[str, Any]
    importance: Literal["primary", "secondary"] = "primary"
    material_hint: Literal["frosted", "brand-solid", "semantic-solid", "icon-control"] = "frosted"


class HybridBodyContract(StrictModel):
    contract_version: Literal["hybrid-body-contract/0.5"] = "hybrid-body-contract/0.5"
    theme_profile_id: str
    allowed_components: tuple[str, ...]
    allowed_design_tokens: tuple[str, ...]
    allowed_layout_tokens: tuple[str, ...]
    allowed_template_ids: tuple[str, ...]
    required_template_groups: tuple[tuple[str, ...], ...] = ()
    allowed_asset_sources: tuple[str, ...]
    asset_semantic_tags_by_source: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    required_asset_sources: tuple[str, ...] = ()
    trusted_literals: tuple[str, ...]
    trusted_numbers: tuple[int | float, ...]
    required_numbers: tuple[int | float, ...] = ()
    required_literals: tuple[str, ...]
    protected_literals: tuple[str, ...]
    action_bindings: tuple[ActionBinding, ...] = ()
    content_action_ids: tuple[str, ...] = ()
    allowed_layout_component_ids: tuple[str, ...] = ()
    allowed_business_component_ids: tuple[str, ...] = ()
    required_business_component_ids: tuple[str, ...] = ()
    template_only_composition: bool = False
    limits: HybridLimits


class TemplateValue(StrictModel):
    kind: Literal[
        "literal",
        "parameter",
        "optional-parameter",
        "binding",
        "event-action",
        "theme",
        "interpolation",
        "expression",
        "compile-time-conditional",
        "array",
        "object",
    ]
    value: str | int | float | bool | None = None
    name: str | None = None
    items: tuple[TemplateValue, ...] = ()
    properties: dict[str, TemplateValue] = Field(default_factory=dict)


class TemplateNode(StrictModel):
    component: str
    values: tuple[TemplateValue, ...] = ()
    children: tuple[TemplateNode, ...] = ()
    spread_children: bool = Field(default=False, alias="spreadChildren")


class TemplateParameterRelation(StrictModel):
    """Cross-parameter invariant enforced by the trusted Template expander."""

    kind: Literal["number-matches-text"]
    number_parameter: str = Field(alias="numberParameter", min_length=1)
    text_parameter: str = Field(alias="textParameter", min_length=1)
    allowed_suffixes: tuple[str, ...] = Field(default=("",), alias="allowedSuffixes")


class TemplateBinding(StrictModel):
    path: str = Field(pattern=r"^/(?:[^/~]|~[01])+(?:/(?:[^/~]|~[01])+)*$")
    data_type: Literal["string", "integer", "number", "boolean", "null"] = Field(alias="type")


class TemplateVariant(StrictModel):
    size: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9-]{0,31}$")
    parameters_schema: dict[str, Any] = Field(alias="parametersSchema")
    parameter_relations: tuple[TemplateParameterRelation, ...] = Field(
        default=(),
        alias="parameterRelations",
    )
    supported_card_sizes: tuple[Literal["2x2", "2x4"], ...] = Field(
        default=(),
        alias="supportedCardSizes",
    )
    supported_roles: tuple[Literal["hero", "support", "peer", "list"], ...] = Field(
        default=(),
        alias="supportedRoles",
    )
    required_bindings: tuple[str, ...] = Field(default=(), alias="requiredBindings")
    optional_bindings: tuple[str, ...] = Field(default=(), alias="optionalBindings")
    root: TemplateNode
    expanded_node_budget: int = Field(alias="expandedNodeBudget", gt=0)
    expanded_depth_budget: int = Field(alias="expandedDepthBudget", gt=0)


class RecommendedVariantLayout(StrictModel):
    inline_sizes: tuple[str, ...] = Field(alias="inlineSizes")
    full_width_sizes: tuple[str, ...] = Field(alias="fullWidthSizes")
    max_inline_items: int = Field(alias="maxInlineItems", gt=0)
    inline_layout_token: str = Field(alias="inlineLayoutToken")


class TemplateLayoutActionStyle(StrictModel):
    """Provider-owned style override for an enclosing layout Action."""

    background_opacity: float = Field(alias="backgroundOpacity", ge=0, le=1)


class TemplateDefinition(StrictModel):
    template_id: str = Field(alias="templateId")
    version: int = Field(gt=0)
    description: str
    domain_tags: tuple[str, ...] = Field(alias="domainTags")
    compatible_theme_profile_ids: tuple[str, ...] = Field(alias="compatibleThemeProfileIds")
    recommended_container_layout_token: str | None = Field(
        default=None,
        alias="recommendedContainerLayoutToken",
    )
    recommended_variant_order: tuple[str, ...] | None = Field(
        default=None,
        alias="recommendedVariantOrder",
    )
    recommended_variant_layout: RecommendedVariantLayout | None = Field(
        default=None,
        alias="recommendedVariantLayout",
    )
    allowed_parent_components: tuple[str, ...] = Field(alias="allowedParentComponents")
    action_policy: Literal["none", "optional", "required"] = Field(alias="actionPolicy")
    requires_layout_action: bool = Field(default=False, alias="requiresLayoutAction")
    layout_action_style: TemplateLayoutActionStyle | None = Field(
        default=None,
        alias="layoutActionStyle",
    )
    supported_sizes: tuple[str, ...] = Field(alias="supportedSizes")
    allowed_design_tokens: tuple[str, ...] = Field(alias="allowedDesignTokens")
    allowed_layout_tokens: tuple[str, ...] = Field(alias="allowedLayoutTokens")
    asset_parameter_semantic_tags: dict[str, tuple[str, ...]] = Field(
        default_factory=dict,
        alias="assetParameterSemanticTags",
    )
    provider_id: str | None = Field(default=None, alias="providerId")
    business_id: str | None = Field(default=None, alias="businessId")
    capability_id: str | None = Field(default=None, alias="capabilityId")
    data_domain: str | None = Field(default=None, alias="dataDomain")
    primary_data: tuple[str, ...] = Field(default=(), alias="primaryData")
    primary_data_fields: tuple[TemplateBinding, ...] = Field(
        default=(),
        alias="primaryDataFields",
    )
    secondary_data: tuple[str, ...] = Field(default=(), alias="secondaryData")
    secondary_data_fields: tuple[TemplateBinding, ...] = Field(
        default=(),
        alias="secondaryDataFields",
    )
    optional_data: tuple[str, ...] = Field(default=(), alias="optionalData")
    optional_data_fields: tuple[TemplateBinding, ...] = Field(
        default=(),
        alias="optionalDataFields",
    )
    accepts_children: bool = Field(default=False, alias="acceptsChildren")
    bindings: dict[str, TemplateBinding] = Field(default_factory=dict)
    source_format: Literal["registry-json", "cardtpl/1"] = Field(
        default="registry-json",
        alias="sourceFormat",
    )
    variants: tuple[TemplateVariant, ...]

    @property
    def wire_id(self) -> str:
        return f"{self.template_id}@{self.version}"

    @property
    def required_data(self) -> tuple[str, ...]:
        """All hard-gated data, ordered as primary data before secondary data."""
        return (*self.primary_data, *self.secondary_data)

    @property
    def required_data_fields(self) -> tuple[TemplateBinding, ...]:
        return (*self.primary_data_fields, *self.secondary_data_fields)


@dataclass(frozen=True)
class BusinessTemplateGroup:
    """从 Provider 模板条目派生的单业务分组，不是独立配置模型。"""

    name: str
    provider_id: str
    description: str
    supported_card_sizes: tuple[Literal["2x2", "2x4"], ...]
    data_capability_ids: tuple[str, ...]
    local_template_ids: tuple[str, ...]

    @property
    def domain_id(self) -> str:
        return self.provider_id

    @property
    def variants(self) -> tuple[str, ...]:
        return ("template",)

    @property
    def roles(self) -> tuple[Literal["hero"], ...]:
        return ("hero",)

    @property
    def max_items_by_size(self) -> dict[Literal["2x2", "2x4"], int]:
        return {"2x2": 1, "2x4": 1}

    @property
    def supported_layouts(self) -> tuple[str, ...]:
        return _BUSINESS_TEMPLATE_SUPPORTED_LAYOUTS

    @property
    def detection_terms(self) -> tuple[str, ...]:
        return (self.name, self.description)

    @property
    def implementation(self) -> Literal["template"]:
        return "template"

    def enabled_variants(self, capability_ids: set[str]) -> tuple[str, ...]:
        if capability_ids.intersection(self.data_capability_ids):
            return self.variants
        return ()


class CardActionStyle(StrictModel):
    background_color: str = Field(alias="backgroundColor", pattern=r"^#[0-9A-Fa-f]{8}$")
    content_color: str = Field(alias="contentColor", pattern=r"^#[0-9A-Fa-f]{8}$")


class CardSupportContentStyle(StrictModel):
    background_color: str = Field(alias="backgroundColor", pattern=r"^#[0-9A-Fa-f]{8}$")
    border_radius: int | float = Field(alias="borderRadius", ge=0)


class FusionBallStyle(StrictModel):
    scene: Literal[
        "weather",
        "sleep",
        "health-sport",
        "schedule-warm",
        "battery",
        "schedule-cool",
    ]
    business_ids: tuple[str, ...] = Field(alias="businessIds", min_length=1)
    large_color: str = Field(alias="largeColor", pattern=r"^#[0-9A-Fa-f]{8}$")
    medium_color: str = Field(alias="mediumColor", pattern=r"^#[0-9A-Fa-f]{8}$")
    small_color: str = Field(alias="smallColor", pattern=r"^#[0-9A-Fa-f]{8}$")


class MarkdownRuleReference(StrictModel):
    path: str = Field(min_length=1)


class ThemeDefinition(StrictModel):
    theme_format: Literal["card-theme/2"] = Field(alias="themeFormat")
    theme_profile_id: str = Field(alias="themeProfileId")
    description: str
    supported_capability_ids: tuple[str, ...] = Field(alias="supportedCapabilityIds")
    supported_layout_ids: tuple[str, ...] = Field(default=(), alias="supportedLayoutIds")
    palette_scene_ids: tuple[str, ...] = Field(default=(), alias="paletteSceneIds")
    primary_color: str = Field(alias="primaryColor", pattern=r"^#[0-9A-Fa-f]{8}$")
    support_content_color: str = Field(
        alias="supportContentColor",
        pattern=r"^#[0-9A-Fa-f]{8}$",
    )
    progress_color: str | None = Field(
        default=None,
        alias="progressColor",
        pattern=r"^#[0-9A-Fa-f]{8}$",
    )
    progress_background_color: str | None = Field(
        default=None,
        alias="progressBackgroundColor",
        pattern=r"^#[0-9A-Fa-f]{8}$",
    )
    root_style: dict[str, Any] = Field(alias="rootStyle")
    action_style: CardActionStyle = Field(alias="actionStyle")
    support_content_style: CardSupportContentStyle | None = Field(
        default=None,
        alias="supportContentStyle",
    )
    fusion_ball_style: FusionBallStyle | None = Field(default=None, alias="fusionBallStyle")
    first_layer_rule: MarkdownRuleReference = Field(alias="firstLayerRule")

    @property
    def reference_values(self) -> dict[str, Any]:
        support_style = self.support_content_style
        support_background = self.action_style.background_color
        support_radius: int | float = 18
        if support_style is not None:
            support_background = support_style.background_color
            support_radius = support_style.border_radius
        else:
            root_radius = self.root_style.get("borderRadius")
            if isinstance(root_radius, (int, float)) and not isinstance(root_radius, bool):
                support_radius = root_radius
        return {
            "primaryColor": self.primary_color,
            "supportContentColor": self.support_content_color,
            "progressColor": self.progress_color or self.primary_color,
            "progressBackgroundColor": (
                self.progress_background_color or self.action_style.background_color
            ),
            "actionStyle.backgroundColor": self.action_style.background_color,
            "actionStyle.contentColor": self.action_style.content_color,
            "supportContentStyle.backgroundColor": support_background,
            "supportContentStyle.borderRadius": support_radius,
        }


class ExpansionStats(StrictModel):
    template_call_count: int = 0
    template_used_ids: tuple[str, ...] = ()
    template_variant_normalization_count: int = 0
    template_provider_param_normalization_count: int = 0
    template_relation_number_normalization_count: int = 0
    expanded_component_count: int = 0
    raw_component_count: int = 0
    max_depth: int = 0
    estimated_height_vp: int = 0
    vertical_budget_vp: int = 0
    space_constrained: bool = False
    action_used_ids: tuple[str, ...] = ()


class Fact(StrictModel):
    source: str
    path: str
    value: str | int | float | bool | None

    @field_validator("path")
    @classmethod
    def pointer_path(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("fact path must be a JSON Pointer")
        return value
