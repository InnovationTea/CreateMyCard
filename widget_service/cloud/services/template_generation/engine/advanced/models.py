"""高级组件选择阶段的稳定数据模型。"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Availability = Literal[
    "available",
    "empty",
    "error",
    "unavailable",
    "permissionDenied",
    "unsupported",
    "stale",
]
ComponentRole = Literal["hero", "support", "peer", "list", "action", "micro"]
Presentation = Literal["auto", "compact", "standard", "expanded"]
PrivacyMode = Literal["full", "masked", "hidden"]
PaletteScene = Literal[
    "generic",
    "office.focus",
    "office.schedule",
    "weather.sunnyCare",
    "weather.rainyCommute",
    "sport.action",
    "sleep.violet",
    "device.earbuds",
    "device.lowPower",
    "device.cleanup",
    "digitalWellbeing",
]
UX_LAYOUT_COMPONENT_IDS = frozenset(
    {
        "SingleFocusLayout",
        "HeroActionLayout",
        "HeroSupportLayout",
        "HeroSupportActionLayout",
        "PeerPairLayout",
        "SequentialSummaryLayout",
        "EqualItemsLayout",
        "ListActionLayout",
        "ActionMatrixLayout",
        "WeatherNowForecastLayout",
    }
)
UX_DIRECT_BUSINESS_COMPONENT_IDS = frozenset(
    {
        "ActivityOverview",
        "AppUsageOverview",
        "BatteryOverview",
        "BluetoothDeviceOverview",
        "DateOverview",
        "HeartRateOverview",
        "ResourceUsageOverview",
        "ScheduleOverview",
        "SleepOverview",
        "WeatherOverview",
        "WorkoutOverview",
    }
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class DataEnvelope(StrictModel):
    """领域数据的统一可用性包装；零值与无数据保持不同语义。"""

    data: Any = None
    availability: Availability
    updated_at: str | None = Field(default=None, alias="updatedAt")
    source: str | None = None

    @model_validator(mode="after")
    def availability_matches_data(self) -> DataEnvelope:
        if self.availability == "available" and self.data is None:
            raise ValueError("available data must not be null")
        if self.availability in {
            "empty",
            "error",
            "unavailable",
            "permissionDenied",
            "unsupported",
        }:
            if self.data is not None:
                raise ValueError("unavailable data must be null")
        return self


class AdvancedComponentCapability(StrictModel):
    name: str
    domain_id: str = Field(alias="domainId")
    description: str
    supported_roles: tuple[ComponentRole, ...] = Field(alias="supportedRoles")
    supported_card_sizes: tuple[Literal["2x2", "2x4"], ...] = Field(alias="supportedCardSizes")
    min_area: Presentation = Field(alias="minArea")
    variants: tuple[str, ...]
    default_variant: str = Field(alias="defaultVariant")
    field_priorities: dict[Literal["mustShow", "preferShow", "expandedOnly"], tuple[str, ...]] = (
        Field(alias="fieldPriorities")
    )
    max_items_by_presentation: dict[Presentation, int] = Field(
        default_factory=dict,
        alias="maxItemsByPresentation",
    )
    supports_primary_action: bool = Field(alias="supportsPrimaryAction")
    supports_primary_chart: bool = Field(alias="supportsPrimaryChart")
    sensitive_fields: tuple[str, ...] = Field(alias="sensitiveFields")
    detection_terms: tuple[str, ...] = Field(alias="detectionTerms")
    variant_terms: dict[str, tuple[str, ...]] = Field(alias="variantTerms")
    local_template_ids: tuple[str, ...] = Field(alias="localTemplateIds")

    @model_validator(mode="after")
    def valid_default_variant(self) -> AdvancedComponentCapability:
        if self.default_variant not in self.variants:
            raise ValueError("defaultVariant must be registered")
        return self


class UxBusinessComponentCapability(StrictModel):
    """UX 设计包中的业务高级组件能力；与旧整卡 Registry 隔离。"""

    name: str
    domain_id: str = Field(alias="domainId")
    description: str
    variants: tuple[str, ...]
    supported_card_sizes: tuple[Literal["2x2", "2x4"], ...] = Field(alias="supportedCardSizes")
    min_region: Literal["compact", "half", "full"] = Field(alias="minRegion")
    roles: tuple[Literal["hero", "support", "peer", "list", "action"], ...]
    max_items_by_size: dict[Literal["2x2", "2x4"], int] = Field(alias="maxItemsBySize")
    supported_layouts: tuple[str, ...] = Field(alias="supportedLayouts")
    supports_action: bool = Field(alias="supportsAction")
    palette_scenes: tuple[PaletteScene, ...] = Field(alias="paletteScenes")
    sensitive_fields: tuple[str, ...] = Field(default=(), alias="sensitiveFields")
    detection_terms: tuple[str, ...] = Field(alias="detectionTerms")
    data_capability_ids: tuple[str, ...] = Field(alias="dataCapabilityIds")
    enabled_variants_by_capability: dict[str, tuple[str, ...]] = Field(
        alias="enabledVariantsByCapability"
    )
    implementation: Literal["template", "terse-dsl"] = "template"
    local_template_ids: tuple[str, ...] = Field(default=(), alias="localTemplateIds")

    @model_validator(mode="after")
    def valid_capability(self) -> UxBusinessComponentCapability:
        if not self.variants:
            raise ValueError("UX Business Component must register variants")
        if not self.supported_layouts:
            raise ValueError("UX Business Component must register layouts")
        if self.implementation == "template" and not self.local_template_ids:
            raise ValueError("UX Business Component must register local Templates")
        if self.implementation == "terse-dsl" and self.name not in UX_DIRECT_BUSINESS_COMPONENT_IDS:
            raise ValueError("UX Business Component has an unsupported TerseDSL implementation")
        if set(self.enabled_variants_by_capability) != set(self.data_capability_ids):
            raise ValueError("UX Business Component capability variant gates are incomplete")
        if any(
            variant not in self.variants
            for variants in self.enabled_variants_by_capability.values()
            for variant in variants
        ):
            raise ValueError("UX Business Component capability gate references unknown variant")
        return self

    def enabled_variants(self, capability_ids: set[str]) -> tuple[str, ...]:
        """Return variants backed by at least one effective production capability."""
        return tuple(
            dict.fromkeys(
                variant
                for capability_id in self.data_capability_ids
                if capability_id in capability_ids
                for variant in self.enabled_variants_by_capability[capability_id]
            )
        )


class UxLayoutComponentCapability(StrictModel):
    """只描述几何职责的布局高级组件，不能读取业务字段。"""

    name: str
    description: str
    supported_card_sizes: tuple[Literal["2x2", "2x4"], ...] = Field(alias="supportedCardSizes")
    min_children: int = Field(alias="minChildren", ge=0)
    min_children_by_size: dict[Literal["2x2", "2x4"], int] = Field(
        default_factory=dict,
        alias="minChildrenBySize",
    )
    max_children_by_size: dict[Literal["2x2", "2x4"], int] = Field(alias="maxChildrenBySize")
    action_policy: Literal["none", "optional", "required"] = Field(alias="actionPolicy")
    min_action_children_by_size: dict[Literal["2x2", "2x4"], int] = Field(
        alias="minActionChildrenBySize"
    )
    max_action_children_by_size: dict[Literal["2x2", "2x4"], int] = Field(
        alias="maxActionChildrenBySize"
    )
    parameters_schema: dict[str, Any] = Field(alias="parametersSchema")
    lowering_by_size: dict[Literal["2x2", "2x4"], Literal["row", "column"]] = Field(
        alias="loweringBySize"
    )

    @model_validator(mode="after")
    def valid_child_budget(self) -> UxLayoutComponentCapability:
        sizes: tuple[Literal["2x2", "2x4"], ...] = ("2x2", "2x4")
        expected_sizes = set(sizes)
        if set(self.max_children_by_size) != expected_sizes:
            raise ValueError("UX Layout child budget is incomplete")
        if set(self.min_action_children_by_size) != expected_sizes:
            raise ValueError("UX Layout minimum Action budget is incomplete")
        if set(self.max_action_children_by_size) != expected_sizes:
            raise ValueError("UX Layout maximum Action budget is incomplete")
        minimums = {size: self.min_children_by_size.get(size, self.min_children) for size in sizes}
        if any(self.max_children_by_size[size] < minimums[size] for size in sizes):
            raise ValueError("UX Layout child budget is invalid")
        if any(
            self.max_action_children_by_size[size] < self.min_action_children_by_size[size]
            for size in sizes
        ):
            raise ValueError("UX Layout Action budget is invalid")
        if self.action_policy == "none" and any(self.max_action_children_by_size.values()):
            raise ValueError("UX Layout without Actions must have a zero Action budget")
        if self.action_policy == "required" and any(
            minimum == 0 for minimum in self.min_action_children_by_size.values()
        ):
            raise ValueError("UX Layout requiring Actions must have a positive minimum")
        schema_is_object = self.parameters_schema.get("type") == "object"
        if not schema_is_object or self.parameters_schema.get("additionalProperties") is not False:
            raise ValueError("UX Layout parametersSchema must be a closed object schema")
        return self

    def minimum_children(self, size: Literal["2x2", "2x4"]) -> int:
        return self.min_children_by_size.get(size, self.min_children)


class UxCardSizeBudget(StrictModel):
    size: Literal["2x2", "2x4"]
    recommended_business_components: int = Field(alias="recommendedBusinessComponents", gt=0)
    max_business_components: int = Field(alias="maxBusinessComponents", gt=0)
    max_primary_actions: int = Field(alias="maxPrimaryActions", ge=0)
    max_primary_charts: int = Field(alias="maxPrimaryCharts", ge=0)
    max_list_items: int = Field(alias="maxListItems", ge=0)
    max_information_levels: int = Field(alias="maxInformationLevels", gt=0)


class AdvancedScopeBrief(StrictModel):
    """第五接口新第一层 LLM 的唯一输出：主题和业务高级组件范围。"""

    scope_version: Literal["advanced-scope-brief/1"] = Field(
        default="advanced-scope-brief/1",
        alias="scopeVersion",
    )
    theme_id: str = Field(alias="themeId", min_length=1)
    advanced_component_ids: tuple[str, ...] = Field(
        alias="advancedComponentIds",
        min_length=1,
        max_length=4,
    )

    @field_validator("theme_id")
    @classmethod
    def non_empty_theme(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("themeId must not be empty")
        return value

    @field_validator("advanced_component_ids")
    @classmethod
    def unique_component_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("advancedComponentIds must be unique")
        return values


class TemplateRouteDecision(StrictModel):
    """第四接口 create 路由的首层模板完整覆盖判断。"""

    theme: str | None
    component: tuple[str, ...] = Field(max_length=4)
    action: tuple[str, ...] = Field(max_length=4)

    @field_validator("theme")
    @classmethod
    def normalized_theme(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("theme must be null or a non-empty candidate ID")
        return normalized

    @field_validator("component", "action")
    @classmethod
    def unique_non_empty_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value.strip() for value in values):
            raise ValueError("component and action IDs must not be empty")
        if len(values) != len(set(values)):
            raise ValueError("component and action IDs must be unique")
        return values

    @model_validator(mode="after")
    def route_fields_match_decision(self) -> TemplateRouteDecision:
        has_scope = bool(self.theme and self.component)
        if has_scope:
            return self
        if self.theme is not None or self.component or self.action:
            raise ValueError("rejected Template route must clear theme, component and action")
        return self


class TemplateRouteSelection(StrictModel):
    """服务端校验后的模板范围，不直接暴露为首层 LLM 输出。"""

    scope: AdvancedScopeBrief
    action_ids: tuple[str, ...] = ()


class AdaptiveTemplateSlot(StrictModel):
    name: str
    kind: Literal["advanced", "action"]
    role: ComponentRole | None = None
    required: bool


class AdaptiveTemplateFamily(StrictModel):
    template_id: str = Field(alias="templateId")
    description: str
    supported_card_sizes: tuple[Literal["2x2", "2x4"], ...] = Field(alias="supportedCardSizes")
    slots: tuple[AdaptiveTemplateSlot, ...]
    max_components_by_size: dict[Literal["2x2", "2x4"], int] = Field(alias="maxComponentsBySize")
    supports_primary_action: bool = Field(alias="supportsPrimaryAction")
    supports_primary_chart: bool = Field(alias="supportsPrimaryChart")
    required_data_signals: tuple[str, ...] = Field(alias="requiredDataSignals")


class CardSizeContentBudget(StrictModel):
    size: Literal["2x2", "2x4"]
    recommended_advanced_components: int = Field(
        gt=0,
        alias="recommendedAdvancedComponents",
    )
    max_advanced_components: int = Field(gt=0, alias="maxAdvancedComponents")
    max_primary_actions: int = Field(ge=0, alias="maxPrimaryActions")
    max_action_hit_zones: int = Field(ge=0, alias="maxActionHitZones")
    max_primary_charts: int = Field(ge=0, alias="maxPrimaryCharts")
    max_list_items: int = Field(ge=0, alias="maxListItems")
    max_information_levels: int = Field(gt=0, alias="maxInformationLevels")


class AdvancedComponentAssignment(StrictModel):
    component_id: str
    domain_id: str
    role: ComponentRole
    variant: str
    presentation: Presentation
    privacy_mode: PrivacyMode
    max_items: int | None = Field(default=None, ge=1)
    uses_primary_chart: bool = False
    score: float = Field(ge=0)
    local_template_ids: tuple[str, ...] = ()
    visible_field_keys: tuple[str, ...] = ()


class AdvancedCompositionPlan(StrictModel):
    registry_version: str
    size: Literal["2x2", "2x4"]
    primary_domain: str
    primary_goal: str
    adaptive_template_id: str | None = None
    assignments: tuple[AdvancedComponentAssignment, ...]
    action_count: int = Field(ge=0)
    primary_chart_count: int = Field(ge=0)
    max_list_items: int = Field(ge=0)
    information_levels: int = Field(gt=0)
    data_signals: tuple[str, ...] = ()
    local_template_ids: tuple[str, ...] = ()
    dropped_domain_ids: tuple[str, ...] = ()


class FieldProfile(BaseModel):
    """TaskSpec 中一个叶子字段的语义摘要。"""

    path: str
    name: str
    data_type: str
    description: str = ""
    roles: list[str] = Field(default_factory=list)


class DataShape(BaseModel):
    """供确定性组件选择使用的数据形状，不包含实际业务数据。"""

    numeric_count: int = 0
    text_count: int = 0
    collection_count: int = 0
    metric_count: int = 0
    duration_count: int = 0
    time_range_count: int = 0
    percentage_count: int = 0
    action_count: int = 0
    repeated_metric_group_count: int = 0
    fields: list[FieldProfile] = Field(default_factory=list)


class UIBrief(BaseModel):
    """第一轮模型输出的抽象视觉意图，不能包含组件或布局实现细节。"""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    purpose: str
    domain: Literal[
        "weather",
        "sports",
        "health",
        "digital-wellbeing",
        "device",
        "schedule",
        "productivity",
        "general",
    ] = "general"
    scenario: Literal[
        "family-care",
        "race-countdown",
        "countdown",
        "sleep-summary",
        "usage-control",
        "low-power",
        "upcoming-event",
        "ongoing-event",
        "resource-monitoring",
        "memory-cleanup",
        "bad-weather-commute",
        "status-summary",
        "schedule-detail",
        "general",
    ] = "general"
    layout_archetype: Literal[
        "auto",
        "hero-metric-action",
        "hero-metric-icon-action",
        "dual-ring-primary-action",
        "hero-countdown",
        "dual-duration-action",
        "usage-summary-action",
        "status-ring-action",
        "upcoming-event-action",
        "timeline-event-action",
    ] = Field(
        default="auto",
        alias="layoutArchetype",
        description=(
            "纯视觉结构选择，不表达业务名称：单主指标、带双图标的单主指标、"
            "双环指标、倒计时、双时长、使用摘要、状态环、未来事项或时间线事项。"
        ),
    )
    status_semantics: list[
        Literal["do-not-disturb", "low-power", "warning", "active", "sleep-quality"]
    ] = Field(default_factory=list, alias="statusSemantics")
    content_semantics: list[
        Literal[
            "location",
            "temperature",
            "countdown",
            "duration",
            "app-usage",
            "battery-level",
            "event-title",
            "time-range",
            "event-count",
            "location-detail",
            "metric",
            "memory-usage",
            "storage-usage",
            "percentage",
            "status",
        ]
    ] = Field(default_factory=list, alias="contentSemantics")
    action_semantics: list[
        Literal[
            "call-contact",
            "open-event",
            "remind-sleep",
            "manage-usage",
            "enable-power-saving",
            "open-dnd-settings",
            "enable-focus",
            "join-meeting",
            "open-details",
            "primary-action",
            "clean-memory",
            "hail-taxi",
        ]
    ] = Field(default_factory=list, alias="actionSemantics")
    primary_information: list[str] = Field(alias="primaryInformation", min_length=1)
    information_hierarchy: list[str] = Field(alias="informationHierarchy", min_length=1)
    density: Literal["sparse", "normal", "compact"] = "normal"
    temporality: Literal["now", "upcoming", "historical", "timeless"] = "now"
    interaction: Literal["none", "one-primary-action", "multiple-actions"] = "one-primary-action"
    attention: Literal["normal", "prominent", "warning-capable", "urgent"] = "normal"
    visual_tone: str = Field(alias="visualTone")
    theme_id: str | None = Field(default=None, alias="themeId")
    theme_semantics: list[str] = Field(default_factory=list, alias="themeSemantics")
    layout_semantics: list[str] = Field(default_factory=list, alias="layoutSemantics")
    local_template_ids: list[str] = Field(default_factory=list, alias="localTemplateIds")
    action_placement: Literal["auto", "card", "content", "none"] = Field(
        default="auto",
        alias="actionPlacement",
    )
    advanced_component_ids: list[str] = Field(
        default_factory=list,
        alias="advancedComponentIds",
    )
    adaptive_template_id: str | None = Field(default=None, alias="adaptiveTemplateId")
    primary_domain: str | None = Field(default=None, alias="primaryDomain")
    content_priorities: list[str] = Field(alias="contentPriorities", min_length=1)
    reason: str

    @field_validator("purpose", "visual_tone", "reason")
    @classmethod
    def non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty")
        return value.strip()

    @field_validator("status_semantics", mode="before")
    @classmethod
    def known_status_semantics(cls, values: Any) -> Any:
        allowed = {"do-not-disturb", "low-power", "warning", "active", "sleep-quality"}
        return (
            [value for value in values if value in allowed] if isinstance(values, list) else values
        )

    @field_validator("content_semantics", mode="before")
    @classmethod
    def known_content_semantics(cls, values: Any) -> Any:
        allowed = {
            "location",
            "temperature",
            "countdown",
            "duration",
            "app-usage",
            "battery-level",
            "event-title",
            "time-range",
            "event-count",
            "location-detail",
            "metric",
            "memory-usage",
            "storage-usage",
            "percentage",
            "status",
        }
        return (
            [value for value in values if value in allowed] if isinstance(values, list) else values
        )

    @field_validator("action_semantics", mode="before")
    @classmethod
    def known_action_semantics(cls, values: Any) -> Any:
        allowed = {
            "call-contact",
            "open-event",
            "remind-sleep",
            "manage-usage",
            "enable-power-saving",
            "open-dnd-settings",
            "enable-focus",
            "join-meeting",
            "open-details",
            "primary-action",
            "clean-memory",
            "hail-taxi",
        }
        return (
            [value for value in values if value in allowed] if isinstance(values, list) else values
        )

    @field_validator("local_template_ids")
    @classmethod
    def versioned_template_ids(cls, values: list[str]) -> list[str]:
        pattern = re.compile(r"^[A-Za-z][A-Za-z0-9-]{0,63}@[1-9][0-9]*$")
        if any(pattern.fullmatch(value) is None for value in values):
            raise ValueError("localTemplateIds must contain versioned IDs")
        return list(dict.fromkeys(values))


class SelectionConstraints(BaseModel):
    size: Literal["2x2", "2x4"]
    action_count: int
    asset_count: int = 0


class ComponentSpec(BaseModel):
    component_id: str
    description: str
    slots: list[str] = Field(default_factory=list)
    supported_sizes: list[str]
    required_signals: dict[str, float] = Field(default_factory=dict)
    preferred_signals: dict[str, float] = Field(default_factory=dict)
    min_actions: int = 0
    max_actions: int = 1
    min_assets: int = 0
    min_fields: int = 0
    required_field_roles: dict[str, int] = Field(default_factory=dict)
    domains: list[str] = Field(default_factory=list)
    scenarios: list[str] = Field(default_factory=list)
    status_semantics: list[str] = Field(default_factory=list)
    content_semantics: list[str] = Field(default_factory=list)
    action_semantics: list[str] = Field(default_factory=list)
    temporalities: list[str] = Field(default_factory=list)
    min_semantic_score: float = 0.0
    layout_archetypes: list[str] = Field(default_factory=list)


class CandidateScore(BaseModel):
    component_id: str
    score: float
    matched: list[str] = Field(default_factory=list)
    penalties: list[str] = Field(default_factory=list)


class ComponentSelection(BaseModel):
    component_id: str
    confidence: float
    candidates: list[CandidateScore]


class BindingRef(BaseModel):
    path: str
    fallback: Any = None

    @field_validator("path")
    @classmethod
    def valid_pointer(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("binding path must be a JSON Pointer")
        return value


class ActionRef(BaseModel):
    event_id: str
    label: str = Field(min_length=1)
    icon: str | None = None


class AdvancedPipelineOutput(BaseModel):
    component_id: str
    style_id: str
    source_dsl: str
    source_format: Literal["terse", "a2ui"]
    ui_brief: UIBrief | AdvancedScopeBrief
    invocation: dict[str, Any]
    planner_mode: Literal["llm", "offline"]
    mapper_mode: Literal["llm", "offline"]
    route: Literal["whole-card-template", "hybrid-template"] = "whole-card-template"
    whole_card_confidence: float = 0.0
    whole_card_candidates: list[CandidateScore] = Field(default_factory=list)
    confidence_bypassed: bool = False
    raw_output: str = ""
    effective_output: str = ""
    compiled_a2ui: str = ""
    fallback_used: bool = False
    template_call_count: int = 0
    template_used_ids: list[str] = Field(default_factory=list)
    expanded_component_count: int = 0
    advanced_composition: AdvancedCompositionPlan | None = None
    trusted_internal_asset_sources: tuple[str, ...] = ()
