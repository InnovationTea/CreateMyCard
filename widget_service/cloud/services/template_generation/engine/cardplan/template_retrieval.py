"""Search data-eligible CardTpl candidates from first-layer field requirements.

The production Search does not select Theme, Layout, business order, Action placement,
or a final Template. The legacy retrieval adapter remains in this module for the old
first-layer route and compatibility tests.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.logger import json_for_log, logger
from models.generation import CandidateDataBinding, TaskSpec
from services.template_generation.engine.advanced.data_shape import extract_data_shape
from services.template_generation.engine.advanced.models import (
    AdvancedScopeBrief,
    TemplateComponentCandidate,
    TemplateRouteSelection,
)

from .calendar_field_paths import (
    CALENDAR_CAPABILITY_ID,
    calendar_reminder_aliases,
    normalize_calendar_reminder_bindings,
)
from .provider_bundle import provider_template_layout_kind
from .registry import CardPlanRegistry
from .retrieval_index import FieldToken, TemplateVariantSearchRecord

_MAX_COMPONENT_TEMPLATE_CANDIDATES = 24
_GENERIC_SCALAR_TYPES = frozenset({"string", "integer", "number", "boolean"})
_TEMPLATE_QUERY_DISCRIMINATORS = {
    "WeatherOverviewAlertFull@1": frozenset({"/current/alertLevel"}),
}


class TemplateRetrievalMiss(ValueError):
    """No provider-backed component can cover the first-layer request."""


class TemplateSearchIntent(BaseModel):
    """First-layer semantic intent; it deliberately contains no UI decision."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    required_output_fields_by_capability: dict[str, tuple[str, ...]] = Field(
        alias="requiredOutputFieldsByCapability",
    )
    primary_output_field_by_capability: dict[str, str] = Field(
        default_factory=dict,
        alias="primaryOutputFieldByCapability",
    )
    action_ids: tuple[str, ...] = Field(default=(), alias="action", max_length=4)
    allow_calendar_view_fallback: bool = Field(
        default=False, alias="allowCalendarViewFallback", strict=True,
    )

    @field_validator("required_output_fields_by_capability")
    @classmethod
    def valid_fields(cls, values: dict[str, tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
        _validate_output_fields(values)
        return values

    @field_validator("action_ids", mode="before")
    @classmethod
    def normalized_actions(cls, value: Any) -> tuple[str, ...]:
        return _normalized_action_ids(value)

    @model_validator(mode="after")
    def valid_primary_fields(self) -> TemplateSearchIntent:
        required = self.required_output_fields_by_capability
        for capability_id, path in self.primary_output_field_by_capability.items():
            if capability_id not in required:
                raise ValueError("primary output capability must have explicit output fields")
            if path not in required[capability_id]:
                raise ValueError("primary output field must be one explicit output field")
        return self


class TemplateSearchCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    template_id: str = Field(alias="templateId", min_length=1)
    covered_explicit_fields: tuple[str, ...] = Field(alias="coveredExplicitFields")


class TemplateBusinessCandidates(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    capability_id: str = Field(alias="capabilityId", min_length=1)
    business_id: str = Field(alias="businessId", min_length=1)
    explicit_fields: tuple[str, ...] = Field(alias="explicitFields")
    candidates: tuple[TemplateSearchCandidate, ...]


class TemplateSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    card_size: str = Field(alias="cardSize", min_length=1)
    business_candidates: tuple[TemplateBusinessCandidates, ...] = Field(
        alias="businessCandidates",
        min_length=1,
    )


class TemplateRetrievalQuery(BaseModel):
    """The first-layer decision: theme, display demands, and explicit Action."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    theme_id: str = Field(alias="themeId", min_length=1)
    required_output_fields_by_capability: dict[str, tuple[str, ...]] = Field(
        alias="requiredOutputFieldsByCapability",
    )
    action_ids: tuple[str, ...] = Field(default=(), alias="action", max_length=4)

    @field_validator("required_output_fields_by_capability")
    @classmethod
    def valid_fields(cls, values: dict[str, tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
        _validate_output_fields(values)
        return values

    @field_validator("action_ids", mode="before")
    @classmethod
    def normalized_actions(cls, value: Any) -> tuple[str, ...]:
        return _normalized_action_ids(value)


def _validate_output_fields(values: dict[str, tuple[str, ...]]) -> None:
    pattern = re.compile(r"^/(?:[^/~]|~[01])+(?:/(?:[^/~]|~[01])+)*$")
    for capability_id, paths in values.items():
        if not capability_id.strip() or len(paths) != len(set(paths)):
            raise ValueError("capability IDs and output fields must be unique")
        if any(pattern.fullmatch(path) is None for path in paths):
            raise ValueError("required output fields must be JSON Pointers")


def _normalized_action_ids(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    values = (value,) if isinstance(value, str) else tuple(value)
    normalized = tuple(item.strip() for item in values if isinstance(item, str))
    if len(normalized) != len(values) or any(not item for item in normalized):
        raise ValueError("action must contain only non-empty eventIds")
    if len(normalized) != len(set(normalized)):
        raise ValueError("action eventIds must be unique")
    return normalized


def build_template_retrieval_prompt(
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
    coverage_bindings: tuple[CandidateDataBinding, ...],
) -> list[dict[str, str]]:
    """Build the first-layer marker prompt without exposing final UI choices."""
    coverage_bindings = normalize_calendar_reminder_bindings(task_spec, coverage_bindings)
    data_shape = extract_data_shape(task_spec)
    capability_ids = tuple(binding.capabilityId for binding in coverage_bindings)
    component_ids = _component_ids_for_capabilities(registry, capability_ids)
    data_roots = {binding.capabilityId: binding.writeResultTo for binding in coverage_bindings}
    payload = {
        "userQuery": task_spec.userQuery,
        "taskSpec": task_spec.model_dump(mode="json"),
        "taskSpecDataFields": [
            {
                "path": field.path,
                "name": field.name,
                "dataType": field.data_type,
                "description": field.description,
                "roles": field.roles,
            }
            for field in data_shape.fields
        ],
        "candidateDataBindings": [binding.model_dump(mode="json") for binding in coverage_bindings],
        "candidateOutputFieldsByCapability": {
            capability_id: tuple(sorted(_candidate_paths(coverage_bindings, capability_id)))
            for capability_id in dict.fromkeys(capability_ids)
        },
        "actionCandidates": [
            {"eventId": event.id, "call": event.call}
            for event in task_spec.eventCandidates
            if event.id
        ],
        "providerFirstLayerRules": registry.provider_first_layer_rules(component_ids, data_roots),
    }
    earphone_only = set(capability_ids) == {"GetEarphoneInfo"} and task_spec.size == "2x2"
    if earphone_only:
        payload["earphoneTemplateReference"] = _earphone_template_reference(
            registry, coverage_bindings,
        )
    schema = TemplateSearchIntent.model_json_schema(by_alias=True)
    ui_instruction = (
        "primaryOutputFieldByCapability 是稀疏映射：仅当用户对某个 capability 明确表达"
        "唯一主焦点字段时输出，值必须同时出现在该 capability 的显式字段数组中；"
        "无法判断时省略该 capability，不能按模板或领域常识猜测。"
        "不得输出主题。"
    )
    action_limit = 4 if task_spec.size == "2x4" else 2
    schema["properties"]["action"]["maxItems"] = action_limit
    action_rule = (
        "action 仅当用户明确要求点击、跳转或操作时才选择 actionCandidates 中"
        f"语义一致的零到 {action_limit} 个不重复 eventId；不能因候选事件存在而默认选择。"
    )
    layout_rule = (
        "不得判断业务是否能组成布局，也不得决定业务位置或 Action 消费者；"
        "这些组合约束由服务端 Planner 在数据 Search 之后处理。"
    )
    if earphone_only:
        action_rule = (
            "必须输出action字段。用户禁止按钮/跳转时action=[]；明确要求动作时选合法候选。"
            "用户未请求动作时根据earphoneTemplateReference检查：存在missingInputFields=[]且displayFields"
            "包含全部筛选后需求的Full时action=[]；无这种Full但有这种Hero且候选含"
            "event.open.settings.bluetooth时，必须action=[\"event.open.settings.bluetooth\"]；"
            "Full/Hero不可用时再检查Compact；字段覆盖且必需输入齐全则保留已有合法动作，"
            "仅从actionCandidates补齐到两个不同动作：优先未选中的event.open.settings.bluetooth；"
            "蓝牙设置已选或不在候选中时，按query及耳机场景相关性选择剩余候选，"
            "相关性相同按候选顺序，不选用户明确排除的动作，不固定第二个动作。缺一个补一个，缺两个补两个。"
            "缺任一候选则保持补齐前的action，不部分补齐、不重复、不删用户要求的动作。"
            "已有一个动作先考虑Hero，已有两个动作使用Compact，不追加。"
            "这是耳机专用入口授权，不要求query另外请求这些候选入口。"
        )
        layout_rule = "按耳机专用规则内部比较Full/Hero/Compact，最终布局仍由服务端Planner校验。"
    system = (
        "你是模板生成第一层。只输出 template-retrieval-query/1 JSON。"
        "requiredOutputFieldsByCapability 的 key 必须来自 "
        "candidateDataBindings。每个 value 仅保留 userQuery、title、description 或 taskSpec "
        "明确要求展示的字段，字段必须逐字来自 "
        "candidateOutputFieldsByCapability；不得按模板反推字段，"
        "也不得补全用户未要求展示的字段；"
        "但当用户请求创建天气卡片且只额外明确一个天气字段（例如天气更新时间）时，"
        "应将天气卡片的默认基础展示字段一并视为用户意图："
        "ViewWeather 默认包含 /location/prefectureName、/current/temperatureText 和"
        "/current/condition，再叠加用户明确要求的字段；这些默认字段仍必须来自"
        "candidateOutputFieldsByCapability，不能补充 schema 中不存在的字段；"
        "事件参数（如 actionCandidates args 中用于跳转的 entityId）不是展示字段，"
        "不得加入 requiredOutputFieldsByCapability。"
        "不得为了迁就布局限制而省略用户明确要求的其他业务字段；"
        + layout_rule
        +
        "用户只要求某领域卡片、未明确字段时，该 capability 输出空数组。"
        + action_rule
        +
        "allowCalendarViewFallback 仅标记单日历日程用户是否允许默认查看入口："
        "用户未明确禁止按钮、操作或跳转时为 true；明确说不要按钮、不需要操作、"
        "只展示不交互等时为 false；其他业务或多个业务也为 false。"
        "没有提到按钮不等于禁止按钮。不要把允许兜底当成已选动作，action 仍只含显式需求。"
        "服务端在 Search 后优先使用匹配的 Full；只有没有 Full 而有可用 Hero，"
        "且候选存在唯一、指向当前日程的查看动作时，才补选查看日程。"
        "不得自行判断上述模板条件，也不得为兜底补充展示字段或编造事件。"
        "不得输出主题、schemaVersion、组件、模板、Variant、尺寸、布局、Props 或理由。\n"
        + ui_instruction + "\n"
        + json.dumps(schema, ensure_ascii=False)
    )
    if "GetEarphoneInfo" in capability_ids:
        system += (
            "\n【蓝牙耳机意图优先】仅 GetEarphoneInfo 按 providerFirstLayerRules 中的"
            "耳机核心与辅助字段规则筛选；允许省略对 userQuery 主要问题不必要的辅助字段，"
            "该局部规则优先于上述按 title、description 或 taskSpec 收集展示字段、"
            "不得参考模板筛选字段的规则。允许参考耳机规则中的模板覆盖选择最小核心字段，"
            "普通并列项可按耳机规则降为辅助并省略；明确强调必须保留的字段不能省略。"
            "其它业务规则不变，不为匹配模板补字段。"
            "仅2x2耳机单业务允许按耳机专用动作回退规则选择输入中的候选动作："
            "未请求动作时先检查Full的核心覆盖和全部必需输入，Full可用则action为空；"
            "Full不可用而Hero覆盖核心且必需输入齐全时，才补候选中的蓝牙设置动作。"
            "Full/Hero不可用时允许按耳机规则回退Compact并补齐两个候选动作，"
            "优先未选中的蓝牙设置，再按相关性选择剩余候选，不固定其它动作；"
            "候选不足以补齐时保持原动作集合。"
            "用户明确不要按钮或跳转时禁止所有自动补动作。"
            "此例外优先于通用的仅明确请求才选动作及不得判断布局规则；"
            "只在内部核对Full/Hero/Compact可用性，仍不得输出模板或布局；其它业务及混合业务不适用。"
            "必须逐项核对耳机规则中Full的必需输入清单；覆盖用户字段但缺模板依赖不算可用。"
            "当上述Hero回退条件满足时必须输出action=[\"event.open.settings.bluetooth\"]，"
            "不能再以用户未明确请求动作为由输出空数组。"
            "earphoneTemplateReference是当前启用模板的真实字段参考；"
            "用户未请求动作且missingInputFields为空、displayFields覆盖筛选后需求的Full存在时，"
            "必须action=[]；用户已选动作不能为优先Full而删除。"
            "优先依据此参考核对，不得因Full附带其它展示字段就认定Full不可用。"
        )
    if earphone_only:
        system += (
            "\n【输出前最后自检：耳机仓电量与充电状态】"
            "仓电量是/batteryLevel，仓充电状态是/chargingStatusDesc，"
            "与左右耳字段不同。query明确要求这两项时同时保留，"
            "不能因候选还有左右耳数据就改成左右耳概览。"
            "EarbudsFull不覆盖仓字段，EarbudPairFull不覆盖仓充电状态；"
            "不能把任何一个当成该需求的可用Full。以本轮启用模板参考为准。"
            "仅当用户未明确要求动作也未禁止按钮/跳转、没有完整可用Full、"
            "参考中存在missingInputFields为空且displayFields覆盖这两项的Hero、"
            "actionCandidates含event.open.settings.bluetooth时："
            "必须输出一个蓝牙设置动作，action=[]为遗漏。"
            "正确输出示例："
            '{"requiredOutputFieldsByCapability":{"GetEarphoneInfo":'
            '["/batteryLevel","/chargingStatusDesc"]},'
            '"action":["event.open.settings.bluetooth"]}。'
            "同一需求明确说不要按钮或不要跳转时，字段不变，action=[]，"
            "允许后续报告未命中；缺候选或模板不可用时不能照抄正例。"
            "已有明确动作时保留合法动作并执行前述规则，不强行替换。"
            "\n【不要把仓场景规则套到普通耳机概览】"
            "没有必须/全部保留等硬要求时，"
            "'创建蓝牙耳机卡片，查看耳机名称、左右耳机电量和充电状态'"
            "属于三类普通概览，按耳机规则收敛为左右耳电量；"
            "EarbudsFull输入齐全且可覆盖时，正确输出为"
            '{"requiredOutputFieldsByCapability":{"GetEarphoneInfo":'
            '["/leftBatteryLevel","/rightBatteryLevel"]},"action":[]}。'
            "不要保留无关名称和充电字段后再补蓝牙设置。"
            "但'名称和左右耳电量'是简短独立目标，必须保留名称与左右电量。"
            "用户强调全部、必须或不能省略时保留所有硬要求，即使无法匹配模板。"
        )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def normalize_calendar_reminder_intent(
    intent: TemplateSearchIntent,
    task_spec: TaskSpec,
    coverage_bindings: tuple[CandidateDataBinding, ...],
) -> TemplateSearchIntent:
    """Keep first-layer explicit fields and focus consistent with approved aliases."""
    aliases = calendar_reminder_aliases(task_spec, coverage_bindings)
    requested = intent.required_output_fields_by_capability.get(CALENDAR_CAPABILITY_ID)
    if not aliases or requested is None:
        return intent
    fields: list[str] = []
    for path in requested:
        canonical = aliases.get(path, path)
        if canonical not in fields:
            fields.append(canonical)
    primary = dict(intent.primary_output_field_by_capability)
    focus = primary.get(CALENDAR_CAPABILITY_ID)
    if focus in aliases:
        primary[CALENDAR_CAPABILITY_ID] = aliases[focus]
    if tuple(fields) == requested and primary == intent.primary_output_field_by_capability:
        return intent
    required = dict(intent.required_output_fields_by_capability)
    required[CALENDAR_CAPABILITY_ID] = tuple(fields)
    return intent.model_copy(update={
        "required_output_fields_by_capability": required,
        "primary_output_field_by_capability": primary,
    })
def _earphone_template_reference(
    registry: CardPlanRegistry,
    coverage_bindings: tuple[CandidateDataBinding, ...],
) -> list[dict[str, Any]]:
    """Supply current earphone template facts to the prompt, without choosing actions."""
    candidate_paths = _candidate_paths(coverage_bindings, "GetEarphoneInfo")
    references: list[dict[str, Any]] = []
    for record in registry.template_variant_search_records:
        if record.capability_id != "GetEarphoneInfo":
            continue
        if "2x2" not in record.supported_card_sizes:
            continue
        if not registry.template_is_enabled(record.template_id):
            continue
        role = provider_template_layout_kind(record.template_id)
        if role not in {"Full", "Hero", "Compact"}:
            continue
        references.append({
            "templateId": record.template_id,
            "roles": [role],
            "displayFields": sorted(record.available_paths),
            "requiredInputFields": sorted(record.required_paths),
            "missingInputFields": sorted(record.required_paths.difference(candidate_paths)),
        })
    return references


def search_template_variants(
    intent: TemplateSearchIntent,
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
    coverage_bindings: tuple[CandidateDataBinding, ...],
    card_spec: dict[str, Any],
    *,
    preferred_template_ids: tuple[str, ...] = (),
) -> TemplateSearchResult:
    """Search only data-eligible templates for the requested card size.

    Layout, Theme, Action placement, business order, and final ranking intentionally
    remain outside this function. Small-card candidates independently cover all
    explicit fields; wide-card candidates report partial coverage for composition.
    Optional fields remain coverage, never hard admission requirements.
    """
    intent = normalize_calendar_reminder_intent(intent, task_spec, coverage_bindings)
    coverage_bindings = normalize_calendar_reminder_bindings(task_spec, coverage_bindings)
    if not intent.required_output_fields_by_capability:
        raise TemplateRetrievalMiss("template Search has no requested capability")
    candidate_ids = {binding.capabilityId for binding in coverage_bindings}
    requested_ids = set(intent.required_output_fields_by_capability)
    if not requested_ids.issubset(candidate_ids):
        raise TemplateRetrievalMiss("requested capability is outside candidate data bindings")

    result_groups: list[TemplateBusinessCandidates] = []
    matched_preferred_ids: set[str] = set()
    preferred_ids = set(preferred_template_ids)
    for capability_id, requested_paths in intent.required_output_fields_by_capability.items():
        candidate_paths = _candidate_paths(coverage_bindings, capability_id)
        if not set(requested_paths).issubset(candidate_paths):
            raise TemplateRetrievalMiss("required output fields must come from candidates")
        data_roots = _capability_data_roots(card_spec, capability_id)
        dropped_paths: set[str] = set()
        for data_root in data_roots:
            dropped_paths.update(
                _action_param_paths_to_drop(
                    task_spec, registry, capability_id, data_root, requested_paths,
                )
            )
        if dropped_paths:
            _log_action_param_fields_dropped(capability_id, ",".join(data_roots), dropped_paths)
        explicit_fields = tuple(path for path in requested_paths if path not in dropped_paths)
        query_tokens = frozenset(
            _task_spec_field_token(task_spec, data_roots, capability_id, path)
            for path in explicit_fields
        )
        matches_by_business = _component_templates_for_capability(
            registry,
            capability_id,
            query_tokens,
            task_spec,
            card_spec,
            preferred_template_ids,
            candidate_output_fields=candidate_paths,
            retain_all_candidates=task_spec.size == "2x4",
        )
        for business_id, matches in matches_by_business.items():
            candidates: list[TemplateSearchCandidate] = []
            for template_id, covered_paths in matches.items():
                if preferred_ids and template_id not in preferred_ids:
                    continue
                if task_spec.size == "2x2":
                    if not set(explicit_fields).issubset(covered_paths):
                        continue
                candidates.append(
                    TemplateSearchCandidate(
                        templateId=template_id,
                        coveredExplicitFields=tuple(
                            path for path in explicit_fields if path in covered_paths
                        ),
                    )
                )
                if template_id in preferred_ids:
                    matched_preferred_ids.add(template_id)
            if candidates:
                result_groups.append(
                    TemplateBusinessCandidates(
                        capabilityId=capability_id,
                        businessId=business_id,
                        explicitFields=explicit_fields,
                        candidates=tuple(candidates),
                    )
                )
        has_capability_result = any(
            group.capability_id == capability_id for group in result_groups
        )
        if not has_capability_result:
            raise TemplateRetrievalMiss(
                f"no provider template covers capability {capability_id} and its requested fields"
            )
    if preferred_ids and matched_preferred_ids != preferred_ids:
        raise TemplateRetrievalMiss("trusted template candidate is outside Search results")
    return TemplateSearchResult(
        cardSize=task_spec.size,
        businessCandidates=tuple(result_groups),
    )


def restrict_search_intent_to_preferred_templates(
    intent: TemplateSearchIntent,
    registry: CardPlanRegistry,
    preferred_template_ids: tuple[str, ...],
) -> TemplateSearchIntent:
    """Keep trusted-gallery field intent within the explicitly selected Templates."""
    if not preferred_template_ids:
        return intent
    legacy = TemplateRetrievalQuery(
        themeId="__unused__",
        requiredOutputFieldsByCapability=intent.required_output_fields_by_capability,
        action=intent.action_ids,
    )
    restricted = restrict_query_to_preferred_templates(
        legacy,
        registry,
        preferred_template_ids,
    )
    primary_fields = {
        capability_id: path
        for capability_id, path in intent.primary_output_field_by_capability.items()
        if path in restricted.required_output_fields_by_capability.get(capability_id, ())
    }
    return intent.model_copy(
        update={
            "required_output_fields_by_capability": (
                restricted.required_output_fields_by_capability
            ),
            "primary_output_field_by_capability": primary_fields,
        }
    )


def retrieve_template_variants(
    query: TemplateRetrievalQuery,
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
    coverage_bindings: tuple[CandidateDataBinding, ...],
    card_spec: dict[str, Any],
    *,
    preferred_template_ids: tuple[str, ...] = (),
) -> TemplateRouteSelection:
    """Return component candidate sets; never choose a final CardTpl variant."""
    selected_theme = registry.require_theme(query.theme_id)
    if selected_theme.supported_layout_ids:
        raise TemplateRetrievalMiss("first-layer Theme must not be layout-scoped")
    _validate_selected_actions(query, task_spec)
    action_count = _selected_action_count(query, task_spec)
    meeting_template = "ScheduleOverviewMeetingEntryHero@1"
    prefer_meeting_entry = "event.enter.meeting" in query.action_ids
    if prefer_meeting_entry and not preferred_template_ids:
        preferred_template_ids = (meeting_template,)
    if not query.required_output_fields_by_capability:
        raise TemplateRetrievalMiss("template retrieval has no requested capability")
    has_multiple_capabilities = len(query.required_output_fields_by_capability) > 1
    preferred_layout_suffix = None
    if not has_multiple_capabilities:
        preferred_layout_suffix = {1: "Hero", 2: "Compact"}.get(action_count)
    elif task_spec.size == "2x4" and action_count == 1:
        preferred_layout_suffix = "WideHalf"
    candidate_ids = {binding.capabilityId for binding in coverage_bindings}
    if not set(query.required_output_fields_by_capability).issubset(candidate_ids):
        raise TemplateRetrievalMiss("requested capability is outside candidate data bindings")

    by_component: dict[str, set[str]] = {}
    required_groups: list[tuple[str, ...]] = []
    for capability_id, paths in query.required_output_fields_by_capability.items():
        candidate_paths = _candidate_paths(coverage_bindings, capability_id)
        if not set(paths).issubset(candidate_paths):
            raise TemplateRetrievalMiss("required output fields must come from candidates")
        data_roots = _capability_data_roots(card_spec, capability_id)
        action_param_paths: set[str] = set()
        for data_root in data_roots:
            action_param_paths.update(
                _action_param_paths_to_drop(
                    task_spec,
                    registry,
                    capability_id,
                    data_root,
                    paths,
                )
            )
        if action_param_paths:
            _log_action_param_fields_dropped(
                capability_id,
                ",".join(data_roots),
                action_param_paths,
            )
        query_tokens = frozenset(
            _task_spec_field_token(task_spec, data_roots, capability_id, path)
            for path in paths
            if path not in action_param_paths
        )
        component_templates = _component_templates_for_capability(
            registry,
            capability_id,
            query_tokens,
            task_spec,
            card_spec,
            preferred_template_ids,
            preferred_layout_suffix,
            candidate_output_fields=candidate_paths,
        )
        if not component_templates:
            raise TemplateRetrievalMiss(
                f"no provider template covers capability {capability_id} and its requested fields"
            )
        required_groups.extend(_required_field_template_groups(query_tokens, component_templates))
        for component_id, template_paths in component_templates.items():
            by_component.setdefault(component_id, set()).update(template_paths)

    # Specialized health components can all match the same summary capability.
    # Prefer the specialized component whose single Template covers the most
    # requested fields, then use GenericMetricOverview only for the residual
    # fields.  Generic is a bounded fallback slot, never the primary business.
    repeated_generic_compact_slots = False
    primary_health: str | None = None
    primary_template_ids: set[str] = set()
    if task_spec.size == "2x4":
        health_ids = {
            "ActivityOverview", "WorkoutOverview", "HeartRateOverview",
            "SleepOverview", "GenericMetricOverview",
        }
        selected_health = health_ids.intersection(by_component)
        if len(selected_health) >= 2 and "GenericMetricOverview" in by_component:
            specialized_health = sorted(selected_health - {"GenericMetricOverview"})
            primary_coverage = 0
            for component_id in specialized_health:
                component_ids = by_component[component_id]
                coverage_by_template = {
                    template_id: sum(template_id in group for group in required_groups)
                    for template_id in component_ids
                }
                component_coverage = max(coverage_by_template.values(), default=0)
                best_ids = {
                    template_id
                    for template_id, coverage in coverage_by_template.items()
                    if coverage == component_coverage
                }
                # Stable tie-breaking keeps the richer domain view ahead of a
                # single-purpose metric view.
                priority = {
                    "SleepOverview": 0,
                    "ActivityOverview": 1,
                    "WorkoutOverview": 2,
                    "HeartRateOverview": 3,
                }.get(component_id, 9)
                current_priority = {
                    "SleepOverview": 0,
                    "ActivityOverview": 1,
                    "WorkoutOverview": 2,
                    "HeartRateOverview": 3,
                }.get(primary_health or "", 9)
                if component_coverage > primary_coverage or (
                    component_coverage == primary_coverage and priority < current_priority
                ):
                    primary_health = component_id
                    primary_template_ids = best_ids
                    primary_coverage = component_coverage

            for component_id in selected_health:
                if component_id not in {"GenericMetricOverview", primary_health}:
                    by_component.pop(component_id, None)

            if primary_health is not None:
                by_component[primary_health].intersection_update(primary_template_ids)

            generic_ids = by_component["GenericMetricOverview"]
            residual_groups: list[tuple[str, ...]] = []
            generic_field_count = 0
            for group in required_groups:
                group_ids = set(group)
                if primary_template_ids.intersection(group_ids):
                    # The specialized primary owns this field; do not also
                    # advertise it as a Generic parameter candidate.
                    residual_groups.append(
                        tuple(item for item in group if item not in generic_ids)
                    )
                    continue
                residual_groups.append(group)
                if generic_ids.intersection(group_ids):
                    generic_field_count += 1
            required_groups = residual_groups
            if generic_field_count > 2:
                logger.info(
                    "[Template Retrieval] generic_capacity_exceeded "
                    f"primary_component={primary_health} "
                    f"primary_coverage={primary_coverage} "
                    f"residual_field_count={generic_field_count} capacity=2"
                )
                raise TemplateRetrievalMiss(
                    "generic compact capacity cannot cover all residual requested fields"
                )
            if generic_field_count == 0:
                by_component.pop("GenericMetricOverview", None)
                generic_ids = set()
            preferred_generic_name = "GenericMetricOverviewCompact@1"
            if generic_ids and preferred_generic_name in generic_ids:
                # Generic Compact is repeatable. For two residual metrics, keep
                # two separate Compact slots so 2x4 can use the existing
                # WideFullTwoCompactLayout instead of a dedicated Full+Compact
                # layout. The repeated slot marker is materialized below in
                # required_groups; componentCandidates remains de-duplicated.
                by_component["GenericMetricOverview"] = {preferred_generic_name}
                repeated_generic_compact_slots = generic_field_count >= 2
            logger.info(
                "[Template Retrieval] specialized_primary_selected "
                f"component_id={primary_health} coverage={primary_coverage} "
                f"template_ids={sorted(primary_template_ids)} "
                f"generic_residual_count={generic_field_count}"
            )

            # Current 2x4 layouts provide three visible slots in total.  With
            # an explicit Action, only two slots remain for business content.
            # Do not silently discard the specialized primary or pretend that
            # a bounded Generic Compact covers an arbitrary number of fields.
            required_slot_count = len(by_component) + action_count
            if action_count and len(by_component) > 2:
                requested_fields = {
                    capability_id: list(paths)
                    for capability_id, paths in query.required_output_fields_by_capability.items()
                }
                logger.info(
                    "[Template Retrieval] layout_capacity_exceeded "
                    f"card_size=2x4 available_slot_count=3 "
                    f"required_slot_count={required_slot_count} "
                    f"business_components={sorted(by_component)} "
                    f"action_count={action_count} "
                    f"requested_fields={json_for_log(requested_fields)}"
                )
                raise TemplateRetrievalMiss(
                    "2x4 layout capacity is insufficient for the specialized primary, "
                    "generic residual metrics, and selected Action"
                )

    candidates = tuple(
        TemplateComponentCandidate(
            componentId=component_id,
            availableTemplateIds=tuple(sorted(template_ids)),
        )
        for component_id, template_ids in sorted(
            by_component.items(), key=_component_candidate_order_key
        )
    )
    resolved_theme_id = query.theme_id
    if task_spec.size == "2x2":
        candidates, required_groups = _apply_2x2_combination_policy(
            candidates,
            action_count,
            required_groups,
        )
    else:
        # 2x4 only (TaskSpec size is Literal["2x2", "2x4"]).  One business slot
        # may split into a Full + Compact pair whose union of field bindings
        # covers every demanded group; the health specialized-primary path keeps
        # strict single-template semantics via allow_pair=False.
        candidates_with_slots = [
            _candidate_with_complete_field_coverage_or_pair(
                candidate,
                required_groups,
                allow_pair=primary_health is None,
            )
            for candidate in candidates
        ]
        candidates = tuple(candidate for candidate, _ in candidates_with_slots)
        slot_groups_by_candidate = [slots for _, slots in candidates_with_slots]
        if prefer_meeting_entry:
            candidates = _prefer_eligible_template(candidates, meeting_template)
        prefer_case_settings = (
            len(candidates) == 2
            and action_count == 2
            and "event.open.settings.bluetooth" in query.action_ids
        )
        if prefer_case_settings:
            candidates = _prefer_eligible_template(
                candidates, "BluetoothDeviceOverviewCaseSettingsHero@1"
            )
        if action_count == 1:
            candidates = _prefer_half_compact_pair(candidates)
        required_groups = []
        for candidate, slots in zip(candidates, slot_groups_by_candidate):
            if slots is not None:
                # Split candidate: the Full and Compact halves each become one
                # slot group so downstream layout selection sees two positions.
                # Post-split pref narrowing (_prefer_eligible_template) cannot
                # orphan a half today (pref ids are Hero-kind); if it ever did,
                # the second-layer exact-slot filter fails loudly.
                required_groups.extend(slots)
            else:
                required_groups.append(candidate.available_template_ids)
        if repeated_generic_compact_slots and primary_health is not None:
            primary_group = next(
                (
                    candidate.available_template_ids
                    for candidate in candidates
                    if candidate.component_id == primary_health
                ),
                (),
            )
            generic_group = next(
                (
                    candidate.available_template_ids
                    for candidate in candidates
                    if candidate.component_id == "GenericMetricOverview"
                ),
                (),
            )
            if primary_group and generic_group:
                required_groups = []
                for candidate in candidates:
                    required_groups.append(candidate.available_template_ids)
                    if candidate.component_id == "GenericMetricOverview":
                        required_groups.append(candidate.available_template_ids)
    logger.info(
        "[Template Retrieval] candidate_groups_resolved "
        f"group_count={len(required_groups)} "
        f"groups={json_for_log([list(group) for group in required_groups])} "
        f"repeated_generic_compact_slots={repeated_generic_compact_slots}"
    )
    selected_template_ids: list[str] = []
    for candidate in candidates:
        selected_template_ids.extend(candidate.available_template_ids)
    resolved_theme_id = (
        registry.hero_content_theme_id(tuple(selected_template_ids), query.theme_id)
        or resolved_theme_id
    )
    scope = AdvancedScopeBrief(
        themeId=resolved_theme_id,
        advancedComponentIds=tuple(candidate.component_id for candidate in candidates),
    )
    return TemplateRouteSelection(
        scope=scope,
        componentCandidates=candidates,
        actionIds=query.action_ids,
        requiredTemplateGroups=tuple(required_groups),
        requiredOutputFieldsByCapability=query.required_output_fields_by_capability,
    )


def _prefer_eligible_template(
    candidates: tuple[TemplateComponentCandidate, ...],
    template_id: str,
) -> tuple[TemplateComponentCandidate, ...]:
    result = []
    for candidate in candidates:
        if template_id in candidate.available_template_ids:
            candidate = candidate.model_copy(update={"available_template_ids": (template_id,)})
        result.append(candidate)
    return tuple(result)


def _prefer_half_compact_pair(
    candidates: tuple[TemplateComponentCandidate, ...],
) -> tuple[TemplateComponentCandidate, ...]:
    """Use a complete half-width pairing only when both business slots support it."""
    if len(candidates) != 2:
        return candidates
    for half_index in (0, 1):
        half = candidates[half_index]
        compact = candidates[1 - half_index]
        half_ids = []
        compact_ids = []
        for template_id in half.available_template_ids:
            if provider_template_layout_kind(template_id) == "WideHalf":
                half_ids.append(template_id)
        for template_id in compact.available_template_ids:
            if provider_template_layout_kind(template_id) == "Compact":
                compact_ids.append(template_id)
        if half_ids and compact_ids:
            return (
                half.model_copy(update={"available_template_ids": tuple(half_ids)}),
                compact.model_copy(update={"available_template_ids": tuple(compact_ids)}),
            )
    return candidates


def _component_candidate_order_key(
    item: tuple[str, set[str]],
) -> tuple[int, str]:
    """Place the visually larger business before Compact-only support slots."""
    component_id, template_ids = item
    compact_only = all(
        provider_template_layout_kind(template_id) == "Compact"
        for template_id in template_ids
    )
    return (1 if compact_only else 0, component_id)


def restrict_query_to_preferred_templates(
    query: TemplateRetrievalQuery,
    registry: CardPlanRegistry,
    preferred_template_ids: tuple[str, ...],
) -> TemplateRetrievalQuery:
    """Keep gallery-only field demand within its explicitly trusted templates."""
    if not preferred_template_ids:
        return query
    preferred_ids = set(preferred_template_ids)
    available_paths_by_capability: dict[str, set[str]] = {}
    matched_ids: set[str] = set()
    for record in registry.template_variant_search_records:
        if record.template_id not in preferred_ids:
            continue
        matched_ids.add(record.template_id)
        if record.business_id == "GenericMetricOverview":
            # 通用指标没有固定字段表，保留显式请求交给 Search 校验候选来源和类型。
            available_paths_by_capability.setdefault(record.capability_id, set()).update(
                query.required_output_fields_by_capability.get(record.capability_id, ())
            )
        available_paths_by_capability.setdefault(record.capability_id, set()).update(
            record.available_paths
        )
    if matched_ids != preferred_ids:
        raise TemplateRetrievalMiss("trusted template candidate is outside Search records")
    required_fields = {
        capability_id: tuple(
            path
            for path in paths
            if path in available_paths_by_capability.get(capability_id, set())
        )
        for capability_id, paths in query.required_output_fields_by_capability.items()
    }
    return query.model_copy(
        update={"required_output_fields_by_capability": required_fields}
    )


def _apply_2x2_combination_policy(
    candidates: tuple[TemplateComponentCandidate, ...],
    action_count: int,
    required_groups: list[tuple[str, ...]],
) -> tuple[tuple[TemplateComponentCandidate, ...], list[tuple[str, ...]]]:
    """Restrict 2x2 candidates to the business and Action capacity contract."""
    component_count = len(candidates)
    if component_count > 1:
        return _apply_2x2_dual_business_policy(
            candidates,
            action_count,
            required_groups,
        )
    if action_count >= 3:
        raise TemplateRetrievalMiss("2x2 template Search supports at most two Actions")
    if component_count == 1:
        layout_suffixes = {
            0: ("Full",),
            1: ("Hero", "Full"),
            2: ("Compact",),
        }[action_count]
    else:
        raise TemplateRetrievalMiss("template Search found no business component")

    business_candidates: list[dict[str, Any]] = []
    for candidate in candidates:
        business_candidates.append(
            {
                "businessId": candidate.component_id,
                "availableTemplateIds": list(candidate.available_template_ids),
            }
        )
    layout_label = "/".join(layout_suffixes)
    layout_diagnostics = {
        "businessCount": component_count,
        "actionCount": action_count,
        "requiredLayoutSuffixes": list(layout_suffixes),
        "requiredLayoutLabel": layout_label,
        "businessCandidates": business_candidates,
    }
    logger.info(
        "[Template Retrieval] layout_policy_selected "
        f"diagnostics={json_for_log(layout_diagnostics)}"
    )

    filtered_candidates = tuple(
        _candidate_with_layout_suffixes(candidate, layout_suffixes) for candidate in candidates
    )
    allowed_template_ids = {
        template_id
        for candidate in filtered_candidates
        for template_id in candidate.available_template_ids
    }
    filtered_groups = [
        tuple(template_id for template_id in group if template_id in allowed_template_ids)
        for group in required_groups
    ]
    if any(not group for group in filtered_groups):
        diagnostics = {
            "requiredLayoutSuffixes": list(layout_suffixes),
            "requiredTemplateGroupsBeforeLayout": [list(group) for group in required_groups],
            "requiredTemplateGroupsAfterLayout": [list(group) for group in filtered_groups],
            "layoutCompatibleTemplateIds": sorted(allowed_template_ids),
        }
        logger.info(
            "[Template Retrieval] layout_field_coverage_mismatch "
            f"diagnostics={json_for_log(diagnostics)}"
        )
        raise TemplateRetrievalMiss(
            f"2x2 {layout_label} templates cannot cover all requested fields"
        )
    for candidate in filtered_candidates:
        _require_single_template_coverage(candidate, filtered_groups, layout_label)
    return filtered_candidates, filtered_groups


def _apply_2x2_dual_business_policy(
    candidates: tuple[TemplateComponentCandidate, ...],
    action_count: int,
    required_groups: list[tuple[str, ...]],
) -> tuple[tuple[TemplateComponentCandidate, ...], list[tuple[str, ...]]]:
    """Resolve the only Search-supported dual-business shape and its slot order."""
    if len(candidates) != 2 or action_count != 1:
        raise TemplateRetrievalMiss(
            "2x2 template Search does not support multiple data businesses "
            "without exactly one Action"
        )
    for title_index, content_index in ((0, 1), (1, 0)):
        title_candidate = _candidate_with_optional_layout_suffix(
            candidates[title_index],
            "HeroTitle",
        )
        content_candidate = _candidate_with_optional_layout_suffix(
            candidates[content_index],
            "HeroContent",
        )
        if title_candidate is None or content_candidate is None:
            continue
        try:
            title_candidate = _candidate_with_complete_field_coverage(
                title_candidate,
                required_groups,
            )
            content_candidate = _candidate_with_complete_field_coverage(
                content_candidate,
                required_groups,
            )
        except TemplateRetrievalMiss:
            continue
        ordered_candidates = (title_candidate, content_candidate)
        ordered_groups = [
            title_candidate.available_template_ids,
            content_candidate.available_template_ids,
        ]
        diagnostics = {
            "businessCount": 2,
            "actionCount": 1,
            "layout": "HeroTitleContentActionLayout",
            "businessOrder": [
                {
                    "businessId": title_candidate.component_id,
                    "requiredLayoutSuffix": "HeroTitle",
                },
                {
                    "businessId": content_candidate.component_id,
                    "requiredLayoutSuffix": "HeroContent",
                },
            ],
        }
        logger.info(
            "[Template Retrieval] dual_business_layout_policy_selected "
            f"diagnostics={json_for_log(diagnostics)}"
        )
        return ordered_candidates, ordered_groups
    raise TemplateRetrievalMiss(
        "2x2 template Search does not support multiple data businesses without complete "
        "HeroTitle and HeroContent coverage"
    )


def _candidate_with_optional_layout_suffix(
    candidate: TemplateComponentCandidate,
    layout_suffix: str,
) -> TemplateComponentCandidate | None:
    template_ids = tuple(
        template_id
        for template_id in candidate.available_template_ids
        if _template_has_layout_suffix(template_id, layout_suffix)
    )
    if not template_ids:
        return None
    return candidate.model_copy(update={"available_template_ids": template_ids})


def _selected_action_count(query: TemplateRetrievalQuery, task_spec: TaskSpec) -> int:
    selected_action_ids = set(query.action_ids)
    count = 0
    for event in task_spec.eventCandidates:
        if event.id in selected_action_ids:
            count += 1
    return count


def _candidate_with_layout_suffixes(
    candidate: TemplateComponentCandidate,
    layout_suffixes: tuple[str, ...],
) -> TemplateComponentCandidate:
    matching_template_ids: list[str] = []
    for template_id in candidate.available_template_ids:
        has_layout_suffix = False
        for suffix in layout_suffixes:
            if _template_has_layout_suffix(template_id, suffix):
                has_layout_suffix = True
                break
        if has_layout_suffix:
            matching_template_ids.append(template_id)
    template_ids = tuple(matching_template_ids)
    if not template_ids:
        layout_label = "/".join(layout_suffixes)
        diagnostics = {
            "businessId": candidate.component_id,
            "requiredLayoutSuffixes": list(layout_suffixes),
            "requiredLayoutLabel": layout_label,
            "availableTemplateIds": list(candidate.available_template_ids),
        }
        logger.info(
            "[Template Retrieval] layout_suffix_mismatch "
            f"diagnostics={json_for_log(diagnostics)}"
        )
        raise TemplateRetrievalMiss(
            f"2x2 business {candidate.component_id} has no {layout_label} template"
        )
    return candidate.model_copy(update={"available_template_ids": template_ids})


def _require_single_template_coverage(
    candidate: TemplateComponentCandidate,
    required_groups: list[tuple[str, ...]],
    layout_suffix: str,
) -> None:
    """A 2x2 business slot must use one layout-compatible business template."""
    candidate_ids = set(candidate.available_template_ids)
    component_groups = [
        set(group).intersection(candidate_ids)
        for group in required_groups
        if set(group).intersection(candidate_ids)
    ]
    if component_groups and not set.intersection(*component_groups):
        diagnostics = {
            "businessId": candidate.component_id,
            "requiredLayoutLabel": layout_suffix,
            "availableTemplateIds": list(candidate.available_template_ids),
            "requiredTemplateGroups": [sorted(group) for group in component_groups],
        }
        logger.info(
            "[Template Retrieval] single_template_coverage_mismatch "
            f"diagnostics={json_for_log(diagnostics)}"
        )
        raise TemplateRetrievalMiss(
            f"2x2 {layout_suffix} templates cannot cover one {candidate.component_id} slot"
        )


def _template_has_layout_suffix(template_id: str, layout_suffix: str) -> bool:
    """Match the declared business-template layout before its version suffix."""
    template_name, separator, version = template_id.rpartition("@")
    return bool(separator and version and template_name.endswith(layout_suffix))


def _candidate_with_complete_field_coverage(
    candidate: TemplateComponentCandidate,
    required_groups: list[tuple[str, ...]],
) -> TemplateComponentCandidate:
    """Keep only candidates that independently cover the first-layer display demand."""
    candidate_ids = set(candidate.available_template_ids)
    component_groups = [
        set(group).intersection(candidate_ids)
        for group in required_groups
        if set(group).intersection(candidate_ids)
    ]
    complete_ids = set.intersection(*component_groups) if component_groups else candidate_ids
    if not complete_ids:
        raise TemplateRetrievalMiss(
            f"template candidates cannot cover one {candidate.component_id} slot"
        )
    template_ids = tuple(
        template_id
        for template_id in candidate.available_template_ids
        if template_id in complete_ids
    )
    return candidate.model_copy(update={"available_template_ids": template_ids})


def _candidate_with_complete_field_coverage_or_pair(
    candidate: TemplateComponentCandidate,
    required_groups: list[tuple[str, ...]],
    *,
    allow_pair: bool,
) -> tuple[TemplateComponentCandidate, tuple[tuple[str, ...], ...] | None]:
    """Cover one slot with a single template, or split it into a Full+Compact pair.

    Returns ``(narrowed_candidate, None)`` when one template covers every
    demanded group, or ``(split_candidate, (full_ids, compact_ids))`` when no
    single template does but a Full + Compact pair's union of field bindings
    does. ``provider_template_layout_kind`` maps ``Wide*`` ids to their own
    kinds, so only natively 2x2-sized shapes enter the pair.
    """
    candidate_ids = set(candidate.available_template_ids)
    component_groups = [
        set(group).intersection(candidate_ids)
        for group in required_groups
        if set(group).intersection(candidate_ids)
    ]
    complete_ids = set.intersection(*component_groups) if component_groups else candidate_ids
    if not complete_ids:
        if not allow_pair:
            raise TemplateRetrievalMiss(
                f"template candidates cannot cover one {candidate.component_id} slot"
            )
        full_ids = sorted(
            template_id
            for template_id in candidate.available_template_ids
            if provider_template_layout_kind(template_id) == "Full"
        )
        compact_ids = sorted(
            template_id
            for template_id in candidate.available_template_ids
            if provider_template_layout_kind(template_id) == "Compact"
        )
        pair_ids = set(full_ids) | set(compact_ids)
        if (
            not full_ids
            or not compact_ids
            or not component_groups
            or not all(group.intersection(pair_ids) for group in component_groups)
        ):
            raise TemplateRetrievalMiss(
                f"template candidates cannot cover one {candidate.component_id} slot"
            )
        slots = (tuple(full_ids), tuple(compact_ids))
        return (
            candidate.model_copy(
                update={"available_template_ids": tuple(sorted(pair_ids))}
            ),
            slots,
        )
    template_ids = tuple(
        template_id
        for template_id in candidate.available_template_ids
        if template_id in complete_ids
    )
    return candidate.model_copy(update={"available_template_ids": template_ids}), None


def _component_templates_for_capability(
    registry: CardPlanRegistry,
    capability_id: str,
    query_tokens: frozenset[FieldToken],
    task_spec: TaskSpec,
    card_spec: dict[str, Any],
    preferred_template_ids: tuple[str, ...] = (),
    preferred_layout_suffix: str | None = None,
    candidate_output_fields: set[str] | None = None,
    retain_all_candidates: bool = False,
) -> dict[str, dict[str, frozenset[str]]]:
    result: dict[str, dict[str, frozenset[str]]] = {}
    data_roots = _capability_data_roots(card_spec, capability_id)
    data_root = data_roots[0]
    provided_output_fields = candidate_output_fields or set()
    task_spec_available_fields = _task_spec_field_entries(task_spec, data_root)
    business_ids = {
        record.business_id
        for record in registry.template_variant_search_records
        if record.capability_id == capability_id
    }
    for business_id in sorted(business_ids):
        group = registry.ux_business_components[business_id]
        template_ids = set(registry.enabled_template_ids(group.local_template_ids))
        matches: dict[str, frozenset[str]] = {}
        evaluations: list[dict[str, Any]] = []
        for record in registry.template_variant_search_records:
            if record.capability_id != capability_id or record.business_id != business_id:
                continue
            evaluations.append(
                _template_record_evaluation(
                    record,
                    task_spec,
                    data_root,
                    query_tokens,
                    template_ids,
                )
            )
            if record.template_id not in template_ids:
                continue
            if record.binding_count != len(data_roots):
                continue
            size_is_supported = _template_can_participate_in_size(record, task_spec.size)
            if not size_is_supported:
                continue
            if not _template_query_discriminator_is_requested(record, query_tokens):
                continue
            if not _template_required_fields_are_available(record, task_spec, card_spec):
                continue
            if business_id == "GenericMetricOverview" and task_spec.size == "2x4":
                # Generic Compact templates deliberately have no fixed field
                # allowlist in the 2x4 residual-composition route. Their path
                # props are constrained by the current candidate output fields
                # and the token type check above. Generic is deliberately not
                # admitted as a second business in 2x2, where the existing
                # single-business layout contract must remain unchanged.
                matches[record.template_id] = frozenset(
                    token.path
                    for token in query_tokens
                    if token.path in provided_output_fields
                    and token.data_type in _GENERIC_SCALAR_TYPES
                )
            else:
                matches[record.template_id] = _record_available_query_paths(
                    record, query_tokens
                )
        if query_tokens:
            matches = {template_id: paths for template_id, paths in matches.items() if paths}
        limited_matches: dict[str, frozenset[str]] = {}
        if matches:
            limited_matches = _limit_component_templates(
                matches,
                registry.enabled_template_ids(group.local_template_ids),
                query_tokens,
                preferred_template_ids,
                preferred_layout_suffix,
            )
            if retain_all_candidates:
                limited_matches = matches
            result[business_id] = limited_matches
        _log_template_candidate_evaluation(
            capability_id=capability_id,
            business_id=business_id,
            data_root=data_root,
            card_size=task_spec.size,
            user_required_fields=_field_entries_for_tokens(query_tokens),
            candidate_output_fields=provided_output_fields,
            task_spec_available_fields=task_spec_available_fields,
            disabled_provider_ids=set(getattr(registry, "disabled_provider_ids", ())),
            disabled_template_ids=set(getattr(registry, "disabled_template_ids", ())),
            evaluations=evaluations,
            matches=matches,
            limited_matches=limited_matches,
        )
    covered_paths: set[str] = set()
    for templates in result.values():
        for paths in templates.values():
            covered_paths.update(paths)
    if not {token.path for token in query_tokens}.issubset(covered_paths):
        return {}
    return result


def _limit_component_templates(
    matches: dict[str, frozenset[str]],
    declared_template_ids: tuple[str, ...],
    query_tokens: frozenset[FieldToken],
    preferred_template_ids: tuple[str, ...] = (),
    preferred_layout_suffix: str | None = None,
) -> dict[str, frozenset[str]]:
    """Keep the upstream candidate bound without dropping field coverage."""
    selected = [
        template_id
        for template_id in preferred_template_ids
        if template_id in matches
    ]
    layout_matches: list[str] = []
    if preferred_layout_suffix is not None:
        for template_id in declared_template_ids:
            if template_id not in matches:
                continue
            if not _template_has_layout_suffix(template_id, preferred_layout_suffix):
                continue
            layout_matches.append(template_id)
    for token in sorted(query_tokens):
        template_id = next(
            (item for item in layout_matches if token.path in matches[item]),
            None,
        )
        if template_id is not None and template_id not in selected:
            selected.append(template_id)
    if not query_tokens and layout_matches:
        selected.append(layout_matches[0])
    for token in sorted(query_tokens):
        template_id = next(
            (
                item
                for item in declared_template_ids
                if item in matches and token.path in matches[item]
            ),
            None,
        )
        if template_id is not None and template_id not in selected:
            selected.append(template_id)
    selected.extend(
        template_id
        for template_id in declared_template_ids
        if template_id in matches and template_id not in selected
    )
    selected = selected[:_MAX_COMPONENT_TEMPLATE_CANDIDATES]
    return {template_id: matches[template_id] for template_id in selected}


def _template_record_evaluation(
    record: TemplateVariantSearchRecord,
    task_spec: TaskSpec,
    data_root: str,
    query_tokens: frozenset[FieldToken],
    enabled_template_ids: set[str],
) -> dict[str, Any]:
    """构造单模板的字段覆盖诊断，不记录用户数据值。"""
    missing_required_fields: list[str] = []
    required_type_mismatches: list[dict[str, str]] = []
    required_types = {token.path: token.data_type for token in record.required_field_tokens}
    for path in sorted(record.required_paths):
        pointer = f"{data_root.rstrip('/')}{path}"
        leaf = _task_spec_schema_leaf(task_spec.dataModelSchema, pointer)
        if leaf is None:
            missing_required_fields.append(path)
            continue
        expected_type = required_types.get(path)
        actual_type = leaf.get("type")
        if expected_type is None or actual_type == expected_type:
            continue
        required_type_mismatches.append(
            {
                "path": path,
                "expectedType": expected_type,
                "actualType": actual_type if isinstance(actual_type, str) else "",
            }
        )

    if record.business_id == "GenericMetricOverview" and task_spec.size == "2x4":
        # GenericMetricOverview has no fixed provider field list on the wide
        # residual route. Its candidate fields are validated before this
        # diagnostic is built, so report the requested scalar paths as covered
        # instead of using the empty metadata allowlist.
        matched_user_fields = frozenset(token.path for token in query_tokens)
    else:
        matched_user_fields = _record_available_query_paths(record, query_tokens)
    unmatched_user_fields = sorted(token.path for token in query_tokens)
    unmatched_user_fields = [
        path for path in unmatched_user_fields if path not in matched_user_fields
    ]
    user_type_mismatches = _user_required_type_mismatches(record, query_tokens)
    rejection_reasons: list[str] = []
    if record.template_id not in enabled_template_ids:
        rejection_reasons.append("template_disabled")
    size_is_supported = _template_can_participate_in_size(record, task_spec.size)
    if not size_is_supported:
        rejection_reasons.append("card_size_not_supported")
    if not _template_query_discriminator_is_requested(record, query_tokens):
        rejection_reasons.append("template_query_discriminator_not_requested")
    if missing_required_fields:
        rejection_reasons.append("user_provided_data_missing_template_required_fields")
    if required_type_mismatches:
        rejection_reasons.append("user_provided_data_type_mismatch")
    if query_tokens and not matched_user_fields:
        rejection_reasons.append("user_required_data_not_covered")

    return {
        "templateId": record.template_id,
        "templateEnabled": record.template_id in enabled_template_ids,
        "supportedCardSizes": sorted(record.supported_card_sizes),
        "matchedUserRequiredFields": sorted(matched_user_fields),
        "unmatchedUserRequiredFields": unmatched_user_fields,
        "missingTemplateRequiredFields": missing_required_fields,
        "templateRequiredFieldTypeMismatches": required_type_mismatches,
        "userRequiredFieldTypeMismatches": user_type_mismatches,
        "userRequiredDataFullyCovered": not unmatched_user_fields,
        "userProvidedDataSatisfiesTemplateRequirements": (
            not missing_required_fields and not required_type_mismatches
        ),
        "rejectionReasons": rejection_reasons,
    }


def _template_can_participate_in_size(
    record: TemplateVariantSearchRecord,
    card_size: str,
) -> bool:
    """Allow standard business shapes inside a 2x4 composition layout."""
    if not record.supported_card_sizes or card_size in record.supported_card_sizes:
        return True
    if card_size != "2x4":
        return False
    return provider_template_layout_kind(record.template_id) in {
        "Full",
        "Hero",
        "Compact",
    }


def _template_query_discriminator_is_requested(
    record: TemplateVariantSearchRecord,
    query_tokens: frozenset[FieldToken],
) -> bool:
    discriminators = _TEMPLATE_QUERY_DISCRIMINATORS.get(record.template_id)
    if not discriminators:
        return True
    return bool(discriminators.intersection(token.path for token in query_tokens))


def _user_required_type_mismatches(
    record: TemplateVariantSearchRecord,
    query_tokens: frozenset[FieldToken],
) -> list[dict[str, str]]:
    template_types = {token.path: token.data_type for token in record.field_tokens}
    mismatches: list[dict[str, str]] = []
    for token in sorted(query_tokens):
        expected_type = template_types.get(token.path)
        if expected_type is None or expected_type == token.data_type:
            continue
        mismatches.append(
            {
                "path": token.path,
                "templateType": expected_type,
                "userDataType": token.data_type,
            }
        )
    return mismatches


def _field_entries_for_tokens(tokens: frozenset[FieldToken]) -> list[dict[str, str]]:
    return [{"path": token.path, "type": token.data_type} for token in sorted(tokens)]


def _task_spec_field_entries(task_spec: TaskSpec, data_root: str) -> list[dict[str, str]]:
    prefix = f"{data_root.rstrip('/')}/"
    entries: list[dict[str, str]] = []
    for field in extract_data_shape(task_spec).fields:
        if not field.path.startswith(prefix):
            continue
        relative_path = f"/{field.path.removeprefix(prefix)}"
        entries.append({"path": relative_path, "type": field.data_type})
    return sorted(entries, key=lambda item: item.get("path", ""))


def _log_template_candidate_evaluation(
    *,
    capability_id: str,
    business_id: str,
    data_root: str,
    card_size: str,
    user_required_fields: list[dict[str, str]],
    candidate_output_fields: set[str],
    task_spec_available_fields: list[dict[str, str]],
    disabled_provider_ids: set[str],
    disabled_template_ids: set[str],
    evaluations: list[dict[str, Any]],
    matches: dict[str, frozenset[str]],
    limited_matches: dict[str, frozenset[str]],
) -> None:
    eligible_ids = list(matches)
    selected_ids = list(limited_matches)
    selected_set = set(selected_ids)
    dropped_ids = [template_id for template_id in eligible_ids if template_id not in selected_set]
    for evaluation in evaluations:
        template_id = evaluation.get("templateId")
        is_eligible = isinstance(template_id, str) and template_id in matches
        is_selected = isinstance(template_id, str) and template_id in limited_matches
        evaluation.update(
            {
                "eligibleBeforeCandidateLimit": is_eligible,
                "selectedAfterCandidateLimit": is_selected,
            }
        )
        if not is_eligible or is_selected:
            continue
        reasons = evaluation.get("rejectionReasons")
        if isinstance(reasons, list):
            reasons.append("candidate_limit_exceeded")

    diagnostics = {
        "capabilityId": capability_id,
        "businessId": business_id,
        "dataRoot": data_root,
        "cardSize": card_size,
        "userRequiredFields": user_required_fields,
        "candidateOutputFields": sorted(candidate_output_fields),
        "taskSpecAvailableFields": task_spec_available_fields,
        "disabledProviderIds": sorted(disabled_provider_ids),
        "disabledTemplateIds": sorted(disabled_template_ids),
        "eligibleTemplateIdsBeforeLimit": eligible_ids,
        "selectedTemplateIdsAfterLimit": selected_ids,
        "droppedByCandidateLimit": dropped_ids,
        "templates": evaluations,
    }
    logger.info(
        "[Template Retrieval] candidate_evaluation "
        f"diagnostics={json_for_log(diagnostics)}"
    )


def _required_field_template_groups(
    query_tokens: frozenset[FieldToken],
    component_templates: dict[str, dict[str, frozenset[str]]],
) -> tuple[tuple[str, ...], ...]:
    if not query_tokens:
        template_ids: set[str] = set()
        for templates in component_templates.values():
            template_ids.update(templates)
        return (tuple(sorted(template_ids)),)
    groups: list[tuple[str, ...]] = []
    for token in sorted(query_tokens):
        matching_template_ids: list[str] = []
        for templates in component_templates.values():
            for template_id, paths in templates.items():
                if token.path in paths:
                    matching_template_ids.append(template_id)
        groups.append(tuple(sorted(matching_template_ids)))
    return tuple(groups)


def _component_ids_for_capabilities(
    registry: CardPlanRegistry,
    capability_ids: tuple[str, ...],
) -> tuple[str, ...]:
    wanted = set(capability_ids)
    return tuple(
        business_id
        for business_id, component in registry.ux_business_components.items()
        if wanted.intersection(component.data_capability_ids)
    )


def _candidate_paths(
    coverage_bindings: tuple[CandidateDataBinding, ...], capability_id: str
) -> set[str]:
    matching = [item for item in coverage_bindings if item.capabilityId == capability_id]
    if not matching:
        raise TemplateRetrievalMiss("template retrieval requires a capability binding")
    paths = set(matching[0].candidateOutputFields)
    for binding in matching[1:]:
        paths.intersection_update(binding.candidateOutputFields)
    return paths


_ACTION_ARG_PATH_PATTERN = re.compile(r"\$\{\s*(/[^{}]+?)\s*\}")


def _action_param_paths_to_drop(
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
    capability_id: str,
    data_root: str,
    required_paths: tuple[str, ...],
) -> set[str]:
    """识别不应阻塞模板覆盖门禁的事件参数字段。

    第一层可能在 requiredOutputFieldsByCapability 中误列事件 args 引用的字段
    （如跳转参数 entityId）；展开时 compiler 只逐字复制 args，模板永远不渲染
    这些字段，因此当没有任何模板可展示它们时不让覆盖门禁失败。
    """
    action_bound_paths = _action_bound_relative_paths(task_spec, data_root)
    candidates = action_bound_paths.intersection(required_paths)
    if not candidates:
        return set()
    displayable_paths: set[str] = set()
    for record in registry.template_variant_search_records:
        if record.capability_id != capability_id:
            continue
        for path in record.available_paths:
            displayable_paths.add(path)
    return {path for path in candidates if path not in displayable_paths}


def _action_bound_relative_paths(task_spec: TaskSpec, data_root: str) -> set[str]:
    prefix = f"{data_root.rstrip('/')}/"
    relative_paths: set[str] = set()
    for event in task_spec.eventCandidates:
        for value in _action_arg_string_values(event.args):
            for match in _ACTION_ARG_PATH_PATTERN.finditer(value):
                pointer = match.group(1)
                if pointer.startswith(prefix):
                    relative_paths.add(f"/{pointer.removeprefix(prefix)}")
    return relative_paths


def _action_arg_string_values(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _action_arg_string_values(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _action_arg_string_values(item)


def _log_action_param_fields_dropped(
    capability_id: str,
    data_root: str,
    dropped_paths: set[str],
) -> None:
    logger.info(
        "[Template Retrieval] action_param_fields_dropped "
        f"diagnostics={json_for_log(
            {
                'capabilityId': capability_id,
                'dataRoot': data_root,
                'droppedFields': sorted(dropped_paths),
                'reason': 'event args bind these fields; templates never render them',
            }
        )}"
    )


def _capability_data_roots(
    card_spec: dict[str, Any], capability_id: str
) -> tuple[str, ...]:
    bindings = card_spec.get("dataBindings")
    if not isinstance(bindings, list):
        raise TemplateRetrievalMiss("CardSpec data bindings are unavailable")
    roots = tuple(
        item.get("writeResultTo")
        for item in bindings
        if isinstance(item, dict) and item.get("capabilityId") == capability_id
    )
    valid = tuple(root for root in roots if isinstance(root, str) and root.startswith("/data"))
    if not valid or len(valid) != len(roots) or len(set(valid)) != len(valid):
        raise TemplateRetrievalMiss("capability data root is unavailable or ambiguous")
    return valid


def _task_spec_field_token(
    task_spec: TaskSpec,
    data_roots: tuple[str, ...],
    capability_id: str,
    relative_path: str,
) -> FieldToken:
    data_types: set[str] = set()
    for data_root in data_roots:
        pointer = f"{data_root.rstrip('/')}{relative_path}"
        leaf = _task_spec_schema_leaf(task_spec.dataModelSchema, pointer)
        if leaf is None or not isinstance(leaf.get("type"), str):
            raise TemplateRetrievalMiss(
                f"required output field is absent or untyped in TaskSpec: {relative_path}"
            )
        data_types.add(str(leaf["type"]))
    if len(data_types) != 1:
        raise TemplateRetrievalMiss(
            f"required output field has inconsistent types: {relative_path}"
        )
    return FieldToken(capability_id, relative_path, data_types.pop())


def _task_spec_schema_leaf(schema: dict[str, Any], pointer: str) -> dict[str, Any] | None:
    current: Any = schema
    for raw_part in pointer.removeprefix("/").split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            index = int(part)
            if index >= len(current):
                return None
            current = current[index]
        else:
            return None
    return current if isinstance(current, dict) else None


def _record_available_query_paths(
    record: TemplateVariantSearchRecord,
    query_tokens: frozenset[FieldToken],
) -> frozenset[str]:
    typed_by_path = {token.path: token.data_type for token in record.field_tokens}
    available_paths: set[str] = set()
    for token in query_tokens:
        if token.path not in record.available_paths:
            continue
        expected_type = typed_by_path.get(token.path, token.data_type)
        if expected_type == token.data_type:
            available_paths.add(token.path)
    return frozenset(available_paths)


def _validate_selected_actions(query: TemplateRetrievalQuery, task_spec: TaskSpec) -> None:
    _validate_selected_action_ids(query.action_ids, task_spec)


def _validate_selected_action_ids(action_ids: tuple[str, ...], task_spec: TaskSpec) -> None:
    limit = 4 if task_spec.size == "2x4" else 2
    if len(action_ids) > limit:
        raise TemplateRetrievalMiss("selected Action count exceeds the card size budget")
    if not action_ids:
        return
    candidate_ids = {event.id for event in task_spec.eventCandidates if event.id}
    if not set(action_ids).issubset(candidate_ids):
        raise TemplateRetrievalMiss("selected Action is outside TaskSpec.eventCandidates")


def _template_required_fields_are_available(
    record: TemplateVariantSearchRecord,
    task_spec: TaskSpec,
    card_spec: dict[str, Any],
) -> bool:
    data_roots = _capability_data_roots(card_spec, record.capability_id)
    if len(data_roots) != record.binding_count:
        return False
    for data_root in data_roots:
        for path in record.required_paths:
            pointer = f"{data_root.rstrip('/')}{path}"
            if _task_spec_schema_leaf(task_spec.dataModelSchema, pointer) is None:
                return False
        for token in record.required_field_tokens:
            pointer = f"{data_root.rstrip('/')}{token.path}"
            leaf = _task_spec_schema_leaf(task_spec.dataModelSchema, pointer)
            if leaf is None or leaf.get("type") != token.data_type:
                return False
    return True
