"""高级组件选择阶段的稳定数据模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ComponentRole = Literal["hero", "support", "peer", "list", "action", "micro"]
Presentation = Literal["auto", "compact", "standard", "expanded"]
UX_LAYOUT_COMPONENT_IDS = frozenset(
    {
        "SingleFocusLayout",
        "HeroActionLayout",
        "FullIconActionLayout",
        "CompactTwoActionLayout",
        "TwoSupportLayout",
        "WideSingleFocusLayout",
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
        sizes = self.supported_card_sizes
        if not sizes:
            raise ValueError("UX Layout must support at least one card size")
        expected_sizes = set(sizes)
        if set(self.max_children_by_size) != expected_sizes:
            raise ValueError("UX Layout child budget must match supportedCardSizes")
        if not set(self.min_children_by_size).issubset(expected_sizes):
            raise ValueError("UX Layout minimum child budget has an unsupported card size")
        if set(self.min_action_children_by_size) != expected_sizes:
            raise ValueError("UX Layout minimum Action budget must match supportedCardSizes")
        if set(self.max_action_children_by_size) != expected_sizes:
            raise ValueError("UX Layout maximum Action budget must match supportedCardSizes")
        if set(self.lowering_by_size) != expected_sizes:
            raise ValueError("UX Layout lowering must match supportedCardSizes")
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


class TemplateComponentCandidate(StrictModel):
    """首层批准交给第二层的单个业务组件模板候选集。"""

    component_id: str = Field(alias="componentId", min_length=1)
    available_template_ids: tuple[str, ...] = Field(
        alias="availableTemplateIds",
        min_length=1,
        max_length=24,
    )

    @field_validator("component_id")
    @classmethod
    def normalized_component_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("componentId must not be empty")
        return normalized

    @field_validator("available_template_ids")
    @classmethod
    def unique_non_empty_template_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(value.strip() for value in values)
        if any(not value for value in normalized):
            raise ValueError("availableTemplateIds must not contain empty IDs")
        if len(normalized) != len(set(normalized)):
            raise ValueError("availableTemplateIds must be unique")
        return normalized


class TemplateRouteDecision(StrictModel):
    """第四接口 create 路由的首层模板完整覆盖判断。"""

    theme: str = Field(min_length=1)
    component_candidates: tuple[TemplateComponentCandidate, ...] = Field(
        alias="componentCandidates",
        max_length=4,
    )
    action_ids: tuple[str, ...] = Field(default=(), alias="action", max_length=2)

    @field_validator("theme")
    @classmethod
    def normalized_theme(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("theme must be a non-empty candidate ID")
        return normalized

    @field_validator("component_candidates")
    @classmethod
    def unique_component_ids(
        cls,
        values: tuple[TemplateComponentCandidate, ...],
    ) -> tuple[TemplateComponentCandidate, ...]:
        component_ids = tuple(value.component_id for value in values)
        if len(component_ids) != len(set(component_ids)):
            raise ValueError("componentCandidates componentId values must be unique")
        return values

    @field_validator("action_ids", mode="before")
    @classmethod
    def normalized_actions(cls, value: Any) -> tuple[str, ...]:
        if value is None:
            return ()
        values = (value,) if isinstance(value, str) else tuple(value)
        normalized = tuple(item.strip() for item in values if isinstance(item, str))
        if len(normalized) != len(values) or any(not item for item in normalized):
            raise ValueError("action must contain only non-empty eventIds")
        if len(normalized) != len(set(normalized)):
            raise ValueError("action eventIds must be unique")
        return normalized

    @model_validator(mode="after")
    def route_fields_match_decision(self) -> TemplateRouteDecision:
        if not self.component_candidates and self.action_ids:
            raise ValueError("rejected Template route must clear action and retain theme")
        template_count = sum(
            len(candidate.available_template_ids) for candidate in self.component_candidates
        )
        if template_count > 24:
            raise ValueError("componentCandidates may expose at most 24 Templates")
        return self

    @property
    def component_ids(self) -> tuple[str, ...]:
        return tuple(item.component_id for item in self.component_candidates)


class TemplateRouteSelection(StrictModel):
    """服务端校验后的模板范围，不直接暴露为首层 LLM 输出。"""

    scope: AdvancedScopeBrief
    component_candidates: tuple[TemplateComponentCandidate, ...] = Field(
        alias="componentCandidates"
    )
    action_ids: tuple[str, ...] = Field(default=(), alias="actionIds", max_length=2)
    required_template_groups: tuple[tuple[str, ...], ...] = Field(
        default=(),
        alias="requiredTemplateGroups",
    )

    @property
    def action_id(self) -> str | None:
        """Compatibility view for callers that only inspect the first selected Action."""
        return self.action_ids[0] if self.action_ids else None

    @property
    def allowed_template_ids(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                template_id
                for candidate in self.component_candidates
                for template_id in candidate.available_template_ids
            )
        )


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
