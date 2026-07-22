# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import hashlib
import json
import time
import uuid

from api.schemas import (
    CapabilityOverviewRequest,
    CapabilityOverviewResponse,
    DataCapabilityOverview,
    DataCapabilitySchemasRequest,
    DataCapabilitySchemasResponse,
    GenerateWidgetCardRequest,
    GenerateWidgetCardResponse,
    WidgetCardServiceRequest,
)
from app.logger import json_for_log, logger
from config.config import get_settings
from core.errors import ErrorCode, GenerationStatus
from custom.a2ui_model_client import A2UIModelClient
from models.artifact import ArtifactMeta, GenerationPlan, WidgetArtifact
from models.generation import EventAction
from services.artifact_store import ArtifactStore
from services.capability_registry import CapabilityRegistry
from services.card_spec_builder import CardSpecBuilder
from services.compact_dsl_protocol import (
    build_compact_binding_context,
    is_compact_dsl,
    preflight_compact_dsl,
)
from services.device_capability_resolver import DeviceCapabilityResolver
from services.edit_request_normalizer import EditRequestNormalizer
from services.prompt_builder import PromptBuilder
from services.protocol_registry import (
    A2UI_FORM_PROTOCOL_PROFILE_ID,
    COMPACT_DSL_PROTOCOL_PROFILE_ID,
    A2UIProtocolRegistry,
)
from services.response_planner import ResponsePlanner
from services.retry_controller import RetryController
from services.source_artifact_repository import (
    SourceArtifactError,
    SourceArtifactRepository,
)
from services.task_spec_builder import TaskSpecBuilder
from services.validator import ArtifactValidator

_MODULE = "[Generation Service]"


class WidgetGenerationService:
    """编排微服务暴露的卡片工具能力。"""

    def widget_card_service(
        self,
        request: WidgetCardServiceRequest,
    ) -> (
        CapabilityOverviewResponse
        | DataCapabilitySchemasResponse
        | GenerateWidgetCardResponse
    ):
        """统一云侧卡片工具入口。

        入参：
        - request：包含 operation 和对应能力参数的统一工具请求。
        出参：根据 operation 返回能力概述、数据能力 schema 或卡片生成结果。
        """
        # 兼容统一工具层时，通过 operation 分发到三个正式业务流程及协议变体。
        logger.info(
            f"{_MODULE} widget_card_service_dispatch_started operation={request.operation} "
            f"prd_ver={request.prdVer} "
            f"device_rom_version={request.device.romVersion}"
        )
        if request.operation == "getWidgetCapabilityOverview":
            # overview 只需要版本上下文，不需要读取完整数据 schema，避免首轮工具返回过大。
            return self.get_widget_capability_overview(
                CapabilityOverviewRequest(**request.model_dump(exclude={"operation"}))
            )

        if request.operation == "getDataCapabilitySchemas":
            # schema 是按需加载能力详情，必须明确传入主 Agent 已筛选出的数据能力 ID。
            if not request.dataCapabilityIds:
                raise ValueError("dataCapabilityIds is required for getDataCapabilitySchemas.")
            return self.get_data_capability_schemas(
                DataCapabilitySchemasRequest(**request.model_dump(exclude={"operation"}))
            )

        if request.operation in {"generateWidgetCard", "generateWidgetCardCompactDsl"}:
            # 生成阶段必须带原始用户需求，模型 prompt、TaskSpec 和用户话术都依赖它。
            if not request.userQuery:
                raise ValueError("userQuery is required for generateWidgetCard.")
            # dataCapabilityIds 只属于 schema 加载接口，生成请求下沉时需要剔除。
            payload = request.model_dump(
                exclude={"operation", "dataCapabilityIds"},
                exclude_unset=True,
            )
            generation_request = GenerateWidgetCardRequest(**payload)
            if request.operation == "generateWidgetCardCompactDsl":
                return self.generate_widget_card_compact_dsl(generation_request)
            return self.generate_widget_card_a2ui_form(generation_request)

        raise ValueError(f"Unknown operation: {request.operation}")

    def get_widget_capability_overview(
        self,
        request: CapabilityOverviewRequest,
    ) -> CapabilityOverviewResponse:
        """获取能力概述。

        入参：
        - request：包含 locale、uid、device 等版本上下文。
        出参：实际可用的数据能力概述、事件、素材及不可用能力清单。
        """
        logger.info(
            f"{_MODULE} capability_overview_started prd_ver={request.prdVer} "
            f"device_rom_version={request.device.romVersion} "
            "request="
            f"{json_for_log(request.model_dump(mode='json', exclude={'uid'}, exclude_none=True))}"
        )
        # 能力注册表按 prdVer+device.romVersion 文件夹隔离。
        try:
            registry = self._capability_registry(request)
        except ValueError as exc:
            version = self._capability_registry_version_hint(request)
            logger.error(
                f"{_MODULE} capability_overview_registry_missing registry_version={version} "
                f"error={exc}"
            )
            return CapabilityOverviewResponse(
                dataCapabilities=[],
                eventCapabilities=[],
                assetCandidates=[],
                unavailableCapabilities=[],
            )
        logger.info(
            f"{_MODULE} capability_registry_selected operation=getWidgetCapabilityOverview "
            f"registry_version={registry.version}"
        )
        resolver = DeviceCapabilityResolver(registry)
        data_capabilities, event_capabilities, asset_capabilities, removed = (
            resolver.resolve_capability_overview(request.device)
        )
        response = CapabilityOverviewResponse(
            dataCapabilities=[
                # 第一接口只暴露数据能力 id+description，完整 schema 留给第二接口渐进加载。
                DataCapabilityOverview(
                    id=item.id,
                    description=item.description,
                )
                for item in data_capabilities
            ],
            eventCapabilities=event_capabilities,
            assetCandidates=asset_capabilities,
            unavailableCapabilities=[item.id for item in removed],
        )
        logger.info(
            f"{_MODULE} capability_overview_completed registry_version={registry.version} "
            f"data_count={len(response.dataCapabilities)} "
            f"event_count={len(response.eventCapabilities)} "
            f"asset_count={len(response.assetCandidates)} "
            f"unavailable_count={len(response.unavailableCapabilities)}"
        )
        return response

    def get_data_capability_schemas(
        self,
        request: DataCapabilitySchemasRequest,
    ) -> DataCapabilitySchemasResponse:
        """获取数据能力完整 schema。

        入参：
        - request：包含数据能力 ID 列表和版本上下文。
        出参：已注册数据能力完整定义，以及缺失能力 ID 列表。
        """
        logger.info(
            f"{_MODULE} data_capability_schemas_started "
            f"data_capability_ids={json_for_log(request.dataCapabilityIds)} "
            "request="
            f"{json_for_log(request.model_dump(mode='json', exclude={'uid'}, exclude_none=True))}"
        )
        # 这里返回完整 inputSchema/outputSchema，供主 Agent 生成合法 candidateDataBindings。
        try:
            registry = self._capability_registry(request)
        except ValueError as exc:
            version = self._capability_registry_version_hint(request)
            logger.error(
                f"{_MODULE} data_capability_schemas_registry_missing registry_version={version} "
                f"data_capability_ids={json_for_log(request.dataCapabilityIds)} "
                f"error={exc}"
            )
            return DataCapabilitySchemasResponse(
                capabilityRegistryVersion=version,
                dataCapabilities=[],
                missingCapabilityIds=request.dataCapabilityIds,
            )
        logger.info(
            f"{_MODULE} capability_registry_selected operation=getDataCapabilitySchemas "
            f"registry_version={registry.version}"
        )
        capabilities = []
        missing = []
        for capability_id in request.dataCapabilityIds:
            # 单个 ID 缺失不阻断整个响应，统一放入 missingCapabilityIds 让主 Agent 自行降级。
            capability = registry.get_data_capability(capability_id)
            if capability is None:
                missing.append(capability_id)
            else:
                capabilities.append(capability)
        response = DataCapabilitySchemasResponse(
            capabilityRegistryVersion=registry.version,
            dataCapabilities=capabilities,
            missingCapabilityIds=missing,
        )
        logger.info(
            f"{_MODULE} data_capability_schemas_completed registry_version={registry.version} "
            f"found_count={len(capabilities)} missing_ids={json_for_log(missing)}"
        )
        return response

    def generate_widget_card(
        self, request: GenerateWidgetCardRequest
    ) -> GenerateWidgetCardResponse:
        """生成卡片。

        入参：
        - request：用户需求、尺寸、候选数据绑定、候选事件、候选素材和版本上下文。
        出参：生成状态、artifact 地址、摘要、用户话术、降级原因和有效能力。
        """
        generation_started_at = time.perf_counter()
        stage_started_at = generation_started_at
        latency_by_stage: dict[str, float] = {}
        settings = get_settings()
        generation_mode = (
            "edit" if "sourceArtifactUrl" in request.model_fields_set else "create"
        )
        source_load_result = None
        source_url_hash = ""
        inherited_categories: tuple[str, ...] = ()
        replaced_categories: tuple[str, ...] = ()

        if generation_mode == "edit":
            source_url_hash = hashlib.sha256(
                (request.sourceArtifactUrl or "").encode("utf-8")
            ).hexdigest()
            if not settings.enable_widget_edit:
                logger.warning(
                    f"{_MODULE} widget_edit_rejected reason=feature_disabled "
                    f"source_url_hash={source_url_hash}"
                )
                return GenerateWidgetCardResponse(
                    status=GenerationStatus.UNSUPPORTED,
                    suggestSize=request.size or "2x4",
                    message="当前暂未开放卡片继续编辑能力。",
                    errorCode=ErrorCode.WIDGET_EDIT_DISABLED.value,
                )
            try:
                source_load_result = SourceArtifactRepository().load(
                    request.sourceArtifactUrl or "",
                )
                normalized = EditRequestNormalizer().normalize_edit(
                    request,
                    source_load_result.artifact,
                )
                request = normalized.request
                inherited_categories = normalized.inherited_categories
                replaced_categories = normalized.replaced_categories
                logger.info(
                    f"{_MODULE} source_artifact_loaded "
                    f"source_url_hash={source_load_result.url_hash} "
                    f"source_digest={source_load_result.artifact_digest} "
                    "source_schema_version="
                    f"{source_load_result.artifact.schemaVersion} "
                    f"source_read_latency_ms={source_load_result.read_latency_ms} "
                    f"source_parse_latency_ms={source_load_result.parse_latency_ms} "
                    f"source_download_mode={source_load_result.download_mode} "
                    "inherited_categories="
                    f"{json_for_log(list(inherited_categories))} "
                    "replaced_categories="
                    f"{json_for_log(list(replaced_categories))}"
                )
                latency_by_stage["sourceArtifact"] = self._elapsed_ms(stage_started_at)
                stage_started_at = time.perf_counter()
            except SourceArtifactError as exc:
                logger.error(
                    f"{_MODULE} source_artifact_load_failed "
                    f"source_url_hash={source_url_hash} "
                    f"error_code={exc.error_code.value} error={exc}"
                )
                return GenerateWidgetCardResponse(
                    status=GenerationStatus.FAILED,
                    suggestSize=request.size or "2x4",
                    message="上一版卡片无法安全读取，本次修改未完成，原卡片不受影响。",
                    errorCode=exc.error_code.value,
                )
            except ValueError as exc:
                logger.error(
                    f"{_MODULE} source_artifact_normalization_failed "
                    f"error_code={ErrorCode.SOURCE_ARTIFACT_INVALID.value} error={exc}"
                )
                return GenerateWidgetCardResponse(
                    status=GenerationStatus.FAILED,
                    suggestSize=request.size or "2x4",
                    message="上一版卡片结构不完整，本次修改未完成，原卡片不受影响。",
                    errorCode=ErrorCode.SOURCE_ARTIFACT_INVALID.value,
                )
        else:
            request = EditRequestNormalizer.normalize_create(request)

        # 主流程：解析能力、生成 CardSpec/TaskSpec、生成 genui、校验 artifact、返回结构化状态。
        logger.info(
            f"{_MODULE} generate_widget_card_started generation_mode={generation_mode} "
            f"size={request.size} "
            f"data_binding_count={len(request.candidateDataBindings)} "
            f"event_count={len(request.candidateEventCandidates)} "
            f"asset_count={len(request.candidateAssetIds)} "
            "request="
            + json_for_log(
                request.model_dump(
                    mode="json",
                    exclude={"uid", "sourceArtifactUrl"},
                    exclude_none=True,
                )
            )
        )
        # registry 负责读取当前版本的能力清单，后续所有过滤都以这份清单为准。
        try:
            registry = self._capability_registry(request)
        except ValueError as exc:
            version = self._capability_registry_version_hint(request)
            logger.error(
                f"{_MODULE} generate_widget_card_registry_missing registry_version={version} "
                f"error={exc}"
            )
            response = GenerateWidgetCardResponse(
                status=GenerationStatus.UNSUPPORTED,
                suggestSize=request.size,
                message="当前 App/ROM 版本暂无可用能力清单，暂时不能生成这类卡片。",
                errorCode=ErrorCode.APP_VERSION_UNSUPPORTED.value,
                effectiveCapabilities={"data": [], "event": [], "asset": []},
            )
            self._log_generation_summary(
                request,
                capability_registry_version=version,
                status=response.status,
                error_code=response.errorCode,
                latency_by_stage={
                    "registry": self._elapsed_ms(stage_started_at),
                    "total": self._elapsed_ms(generation_started_at),
                },
            )
            return response
        logger.info(
            f"{_MODULE} generate_flow_step_registry_loaded registry_version={registry.version}"
        )
        # 协议 profile 决定 A2UI 组件白名单、DSL 行数要求和校验规则。
        protocol_registry = A2UIProtocolRegistry(request.protocolProfileId)
        protocol_profile = protocol_registry.get_profile()
        compact_dsl = is_compact_dsl(protocol_profile)
        logger.info(
            f"{_MODULE} generate_flow_step_protocol_loaded "
            f"protocol_profile_id={protocol_profile['id']} "
            f"protocol_version={protocol_profile['version']}"
        )
        latency_by_stage["registryAndProtocol"] = self._elapsed_ms(stage_started_at)
        stage_started_at = time.perf_counter()
        # 设备可用性已由第一个接口完成；生成接口只做绑定结构校验，不再查询 IDS。
        resolver = DeviceCapabilityResolver(registry)
        effective_bindings, effective_data_capabilities, removed_data = (
            resolver.resolve_generation_data_bindings(request.candidateDataBindings)
        )
        logger.info(
            f"{_MODULE} prevalidated_data_capability_loaded "
            f"effective_binding_count={len(effective_bindings)} "
            f"removed_count={len(removed_data)} "
            "effective_binding_ids="
            f"{json_for_log([item.capabilityId for item in effective_bindings])} "
            "removed_data="
            f"{json_for_log([item.model_dump(mode='json') for item in removed_data])}"
        )
        # 事件候选来自第一个接口的可用清单；这里只做注册表存在性检查。
        candidate_events = self._normalize_event_candidates(request)
        effective_events = []
        removed_events = []
        for event in candidate_events:
            if not event.id or registry.get_event_capability(event.id) is None:
                removed_events.append(
                    resolver._removed(
                        event.id or "",
                        ErrorCode.UNKNOWN_CAPABILITY,
                        "event",
                    )
                )
                continue
            effective_events.append(event)
        logger.info(
            f"{_MODULE} event_capability_resolved effective_event_count={len(effective_events)} "
            f"removed_count={len(removed_events)} "
            "effective_events="
            f"{json_for_log([item.model_dump(mode='json') for item in effective_events])} "
            "removed_events="
            f"{json_for_log([item.model_dump(mode='json') for item in removed_events])}"
        )
        asset_candidates = []
        removed_assets = []
        for asset_id in request.candidateAssetIds:
            # 素材同样只解析第一个接口返回的可用 ID。
            asset = registry.get_asset_capability(asset_id)
            if asset is None:
                removed_assets.append(
                    resolver._removed(asset_id, ErrorCode.UNKNOWN_CAPABILITY, "asset")
                )
            else:
                asset_candidates.append(asset)

        # removed 是统一降级信息源，最终会同时进入 prompt、artifact 和响应。
        removed = removed_data + removed_events + removed_assets
        logger.info(
            f"{_MODULE} asset_capability_resolved effective_asset_count={len(asset_candidates)} "
            f"removed_count={len(removed_assets)} "
            "effective_asset_ids="
            f"{json_for_log([item.id for item in asset_candidates])} "
            "removed_assets="
            f"{json_for_log([item.model_dump(mode='json') for item in removed_assets])}"
        )
        latency_by_stage["capabilityResolution"] = self._elapsed_ms(stage_started_at)
        stage_started_at = time.perf_counter()
        if request.candidateDataBindings and not effective_bindings and not effective_events:
            # 没有剩余动态数据或可用入口时，不调用模型，也不伪造数据绑定。
            logger.warning(
                f"{_MODULE} generate_widget_card_unsupported removed_count={len(removed)} "
                f"error_code={ErrorCode.NO_EFFECTIVE_CAPABILITY.value}"
            )
            response = GenerateWidgetCardResponse(
                status=GenerationStatus.UNSUPPORTED,
                suggestSize=request.size,
                message="当前设备上没有可用的数据能力或入口能力，暂时不能生成这类实时卡片。你可以试试天气、日历或系统状态类卡片。",
                removedCapabilities=removed,
                errorCode=ErrorCode.NO_EFFECTIVE_CAPABILITY.value,
            )
            latency_by_stage["total"] = self._elapsed_ms(generation_started_at)
            self._log_generation_summary(
                request,
                protocol_profile_id=protocol_profile["id"],
                capability_registry_version=registry.version,
                removed=removed,
                status=response.status,
                error_code=response.errorCode,
                latency_by_stage=latency_by_stage,
            )
            return response

        # CardSpec 是端侧运行时刷新数据的契约，只包含裁决后的有效数据绑定。
        # CardSpec 由服务侧统一组装；标题和说明直接透传第三个生成接口的入参。
        card_spec = CardSpecBuilder().build(
            request.size,
            effective_bindings,
            request.title,
            request.description,
        )
        # TaskSpec 是给 A2UI 模型的输入，包含用户目标、有效能力、事件和素材。
        task_spec = TaskSpecBuilder().build(
            request.userQuery,
            request.size,
            effective_bindings,
            effective_data_capabilities,
            effective_events,
            asset_candidates,
        )
        logger.info(
            f"{_MODULE} card_and_task_spec_built data_binding_count={len(effective_bindings)} "
            "card_spec="
            f"{json_for_log(card_spec.model_dump(mode='json', exclude_none=True))} "
            "task_spec="
            f"{json_for_log(task_spec.model_dump(mode='json', exclude_none=True))} "
            "task_data_model_schema_keys="
            f"{json_for_log(list(task_spec.dataModelSchema))}"
        )
        # prompt 约束模型生成 DSL；Validator 用于质量观测，重试由配置控制，不作为保存门禁。
        prompt = PromptBuilder().build(
            task_spec,
            protocol_profile,
            "；".join(f"{item.id}:{item.reason}" for item in removed),
            previous_genui=(
                source_load_result.artifact.genui if source_load_result else None
            ),
        )
        if compact_dsl:
            compact_binding_context = build_compact_binding_context(
                card_spec.model_dump(mode="json", exclude_none=True),
                effective_data_capabilities,
            )
            if compact_binding_context is not None:
                prompt[0]["content"] = "\n".join(
                    [
                        prompt[0]["content"],
                        "Dynamic binding context JSON:",
                        json.dumps(
                            compact_binding_context,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    ]
                )

        logger.info(
            f"{_MODULE} a2ui_prompt_built prompt={json_for_log(prompt)}"
        )
        latency_by_stage["specAndPrompt"] = self._elapsed_ms(stage_started_at)
        stage_started_at = time.perf_counter()

        model_client = A2UIModelClient()
        retry_controller = RetryController()
        artifact_id = str(uuid.uuid4())
        compact_operation_error = ""

        def operation() -> str:
            """执行一次 A2UI 模型生成。

            入参：无。
            出参：三行 JSONL genui 字符串。
            """
            nonlocal compact_operation_error
            logger.info(f"{_MODULE} a2ui_model_operation_started")
            generated = model_client.generate(prompt, protocol_profile)
            if not compact_dsl:
                return generated
            if not generated.strip():
                compact_operation_error = "model output is empty"
                return ""

            preflight_started_at = time.perf_counter()
            preflight = preflight_compact_dsl(
                generated,
                card_spec.model_dump(mode="json", exclude_none=True),
                effective_data_capabilities,
                effective_events,
                task_spec.model_dump(mode="json", exclude_none=True),
            )
            preflight_duration_ms = self._elapsed_ms(preflight_started_at)
            categories = sorted(
                {item.category for item in preflight.diagnostics}
            )
            logger.info(
                f"{_MODULE} compact_preflight_completed passed={preflight.passed} "
                f"duration_ms={preflight_duration_ms} "
                f"repair_count={len(preflight.repairs)} "
                f"repairs={json_for_log(list(preflight.repairs))} "
                f"error_count={len(preflight.error_messages)} "
                f"categories={json_for_log(categories)}"
            )
            if preflight.passed:
                return preflight.genui

            compact_operation_error = " | ".join(
                f"[{item.category}] {item.message}"
                for item in preflight.diagnostics
                if item.severity == "error"
            )
            logger.error(
                f"{_MODULE} compact_preflight_failed "
                f"errors={json_for_log(list(preflight.error_messages))} "
                f"categories={json_for_log(categories)}"
            )
            return ""

        def validate_genui(genui: str) -> list[str]:
            """校验单次模型输出。

            入参：
            - genui：模型生成的三行 JSONL 字符串。
            出参：校验错误列表；空列表表示通过。
            """
            if compact_dsl and not genui.strip():
                error = compact_operation_error or "model output is empty"
                logger.error(
                    f"{_MODULE} compact_genui_empty error={error}"
                )
                return [error]
            # 每次模型输出都临时组装 artifact，再用同一套 Validator 校验完整契约。
            if not settings.enable_artifact_validation and not compact_dsl:
                logger.info(
                    f"{_MODULE} a2ui_genui_validation_skipped "
                    "reason=enable_artifact_validation_false"
                )
                return []
            logger.info(
                f"{_MODULE} a2ui_genui_validation_started genui_length={len(genui)}"
            )
            artifact = self._build_artifact(
                genui,
                card_spec.model_dump(mode="json", exclude_none=True),
                task_spec.model_dump(mode="json", exclude_none=True),
                effective_data_capabilities,
                effective_events,
                asset_candidates,
                removed,
                protocol_profile["id"],
                protocol_profile["version"],
                registry.version,
                data_bindings=effective_bindings,
                artifact_id=artifact_id,
                generation_mode=generation_mode,
                source_artifact_digest=(
                    source_load_result.artifact_digest if source_load_result else None
                ),
            )
            artifact_validator = ArtifactValidator()
            validation_errors = artifact_validator.validate(
                artifact,
                protocol_profile,
            )
            if compact_dsl and validation_errors:
                logger.info(
                    f"{_MODULE} compact_validation_failed "
                    "model_retry_skipped=true reason=single_pass_policy "
                    f"categories={json_for_log(artifact_validator.error_categories)}"
                )
            if source_load_result:
                source_write_roots = {
                    item.writeResultTo
                    for item in source_load_result.artifact.generationPlan.candidateDataBindings
                }
                current_write_roots = {
                    item.writeResultTo for item in effective_bindings
                }
                for removed_root in sorted(source_write_roots - current_write_roots):
                    if removed_root in genui:
                        validation_errors.append(
                            f"removed data path remains in edited genui: {removed_root}"
                        )
            return validation_errors

        # 工具3保留部署配置的重试行为；工具4依靠本地 preflight 修复并保持单次模型调用。
        retry_on_validation_failure = (
            settings.enable_validation_failure_retry and not compact_dsl
        )
        retry_result = retry_controller.run(
            operation,
            validate_genui,
            retry_on_validation_failure=retry_on_validation_failure,
        )
        genui = retry_result.result
        errors = retry_result.errors
        latency_by_stage["modelAndValidation"] = self._elapsed_ms(stage_started_at)

        logger.info(
            f"{_MODULE} a2ui_generation_completed retry_count={retry_result.retryCount} "
            "validation_failure_retry_enabled="
            f"{json_for_log(retry_on_validation_failure)} "
            f"validation_error_count={len(errors)}"
        )
        if compact_dsl and errors:
            logger.error(
                f"{_MODULE} compact_generation_validation_failed "
                f"errors={json_for_log(errors)}"
            )
            response = GenerateWidgetCardResponse(
                status=GenerationStatus.FAILED,
                suggestSize=request.size,
                message="卡片生成过程中校验失败，请稍后再试。",
                removedCapabilities=removed,
                errorCode=ErrorCode.VALIDATION_FAILED.value,
            )
            latency_by_stage["total"] = self._elapsed_ms(generation_started_at)
            self._log_generation_summary(
                request,
                protocol_profile_id=protocol_profile["id"],
                capability_registry_version=registry.version,
                removed=removed,
                status=response.status,
                error_code=response.errorCode,
                latency_by_stage=latency_by_stage,
                retry_count=retry_result.retryCount,
                generation_mode=generation_mode,
            )
            return response
        if errors:
            logger.error(
                f"{_MODULE} a2ui_generation_validation_failed_non_blocking "
                f"protocol_profile_id={protocol_profile['id']} "
                f"validation_error_code={ErrorCode.VALIDATION_FAILED.value} "
                f"retry_count={retry_result.retryCount} "
                "validation_failure_retry_enabled="
                f"{json_for_log(retry_on_validation_failure)} "
                f"errors={json_for_log(errors)} "
                "proceeding_to_artifact_save=true"
            )
        stage_started_at = time.perf_counter()

        # 工具3沿用非阻断校验；工具4仅在 Compact 校验通过后组装 artifact。
        artifact = self._build_artifact(
            genui,
            card_spec.model_dump(mode="json", exclude_none=True),
            task_spec.model_dump(mode="json", exclude_none=True),
            effective_data_capabilities,
            effective_events,
            asset_candidates,
            removed,
            protocol_profile["id"],
            protocol_profile["version"],
            registry.version,
            data_bindings=effective_bindings,
            artifact_id=artifact_id,
            generation_mode=generation_mode,
            source_artifact_digest=(
                source_load_result.artifact_digest if source_load_result else None
            ),
        )
        # ArtifactStore 当前是本地 mock/OBS TODO 入口，返回端侧可下载 URL 和摘要。
        logger.info(
            f"{_MODULE} artifact_built "
            f"effective_capabilities={json_for_log(artifact.effectiveCapabilities)} "
            f"removed_count={len(artifact.removedCapabilities)}"
        )
        artifact_save_result = ArtifactStore().save(artifact)
        latency_by_stage["artifactStore"] = self._elapsed_ms(stage_started_at)
        # ResponsePlanner 根据移除能力和最终产物判断 success/degraded/failed 等用户状态。
        response_plan = ResponsePlanner().plan(
            len(request.candidateDataBindings),
            len(effective_bindings),
            removed,
            has_artifact=True,
            generation_mode=generation_mode,
        )
        logger.info(
            f"{_MODULE} generate_widget_card_completed status={response_plan.status.value} "
            f"artifact_url={artifact_save_result.artifactUrl} "
            f"removed_count={len(removed)} error_code={response_plan.errorCode}"
        )
        response = GenerateWidgetCardResponse(
            status=response_plan.status,
            artifactUrl=artifact_save_result.artifactUrl,
            artifactDigest=artifact_save_result.artifactDigest,
            suggestSize=card_spec.suggestSize,
            message=response_plan.message,
            removedCapabilities=removed,
            errorCode=response_plan.errorCode,
            effectiveCapabilities=artifact.effectiveCapabilities,
        )
        latency_by_stage["total"] = self._elapsed_ms(generation_started_at)
        self._log_generation_summary(
            request,
            protocol_profile_id=protocol_profile["id"],
            capability_registry_version=registry.version,
            effective_capabilities=artifact.effectiveCapabilities,
            removed=removed,
            status=response.status,
            error_code=response.errorCode,
            latency_by_stage=latency_by_stage,
            retry_count=retry_result.retryCount,
            artifact_digest=artifact_save_result.artifactDigest,
            generation_mode=generation_mode,
            source_artifact_digest=(
                source_load_result.artifact_digest if source_load_result else ""
            ),
            source_artifact_url_hash=(
                source_load_result.url_hash if source_load_result else ""
            ),
        )
        return response

    @staticmethod
    def _elapsed_ms(started_at: float) -> float:
        return round((time.perf_counter() - started_at) * 1000, 2)

    def _log_generation_summary(
        self,
        request: GenerateWidgetCardRequest,
        *,
        status: GenerationStatus,
        error_code: str,
        protocol_profile_id: str = "",
        capability_registry_version: str = "",
        effective_capabilities: dict | None = None,
        removed: list | None = None,
        latency_by_stage: dict[str, float] | None = None,
        retry_count: int = 0,
        artifact_digest: str = "",
        generation_mode: str = "create",
        source_artifact_digest: str = "",
        source_artifact_url_hash: str = "",
    ) -> None:
        """输出一次生成请求的统一观测字段，不记录 uid 和原始设备标识。"""
        candidate_capabilities = {
            "data": [item.capabilityId for item in request.candidateDataBindings or []],
            "event": [
                item.capabilityId for item in request.candidateEventCandidates or []
            ],
            "asset": list(request.candidateAssetIds or []),
        }
        removed_capabilities = [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            for item in (removed or [])
        ]
        query_hash = hashlib.sha256(request.userQuery.encode("utf-8")).hexdigest()
        device_identifier = request.device.deviceId or request.device.odid or ""
        device_id_hash = (
            hashlib.sha256(device_identifier.encode("utf-8")).hexdigest()[:16]
            if device_identifier
            else ""
        )
        logger.info(
            f"{_MODULE} widget_generation_summary "
            f"query_hash={query_hash} "
            f"device_id_hash={device_id_hash} "
            "skill_version=skill-widget-v1 "
            f"protocol_profile_id={protocol_profile_id} "
            f"capability_registry_version={capability_registry_version} "
            f"candidate_capabilities={json_for_log(candidate_capabilities)} "
            "effective_capabilities="
            f"{json_for_log(effective_capabilities or {'data': [], 'event': [], 'asset': []})} "
            f"removed_capabilities={json_for_log(removed_capabilities)} "
            f"status={status.value} error_code={error_code} "
            f"latency_by_stage={json_for_log(latency_by_stage or {})} "
            f"retry_count={retry_count} artifact_digest={artifact_digest} "
            f"generation_mode={generation_mode} "
            f"source_artifact_url_hash={source_artifact_url_hash} "
            f"source_artifact_digest={source_artifact_digest}"
        )

    def generate_widget_card_a2ui_form(
        self,
        request: GenerateWidgetCardRequest,
    ) -> GenerateWidgetCardResponse:
        """使用原 A2UI Form profile 生成卡片。"""
        return self._generate_widget_card_with_profile(
            request,
            A2UI_FORM_PROTOCOL_PROFILE_ID,
        )

    def generate_widget_card_compact_dsl(
        self,
        request: GenerateWidgetCardRequest,
    ) -> GenerateWidgetCardResponse:
        """使用 Compact DSL profile 生成卡片。"""
        if "sourceArtifactUrl" in request.model_fields_set:
            return GenerateWidgetCardResponse(
                status=GenerationStatus.UNSUPPORTED,
                suggestSize=request.size or "2x4",
                message="Compact DSL 调试入口不支持多轮编辑。",
                errorCode=ErrorCode.WIDGET_EDIT_DISABLED.value,
            )
        return self._generate_widget_card_with_profile(
            request,
            COMPACT_DSL_PROTOCOL_PROFILE_ID,
        )

    def _generate_widget_card_with_profile(
        self,
        request: GenerateWidgetCardRequest,
        protocol_profile_id: str,
    ) -> GenerateWidgetCardResponse:
        """复制请求并锁定路由对应的协议 profile。"""
        profiled_request = request.model_copy(
            update={"protocolProfileId": protocol_profile_id}
        )
        return self.generate_widget_card(profiled_request)

    def _normalize_event_candidates(
        self,
        request: GenerateWidgetCardRequest,
    ) -> list[EventAction]:
        """归一化候选事件入参。

        入参：
        - request：生成接口请求。
        出参：统一后的 EventAction 列表。
        """
        # 最新云侧方案要求 capabilityId 和 action 放在同一候选项里，避免能力 ID 与事件参数错配。
        candidates: list[EventAction] = []
        for candidate in request.candidateEventCandidates:
            # EventAction 是模型 TaskSpec 使用的内部结构，id 用于后续设备能力过滤。
            candidates.append(
                EventAction(
                    id=candidate.capabilityId,
                    call=candidate.action.call,
                    args=candidate.action.args,
                )
            )

        return candidates

    def _capability_registry(
        self,
        request,
    ) -> CapabilityRegistry:
        """按请求版本上下文创建能力注册表。

        入参：
        - request：包含 capabilityRegistryVersion 和 device 版本字段的请求对象。
        出参：对应版本的 CapabilityRegistry。
        """
        # capabilityRegistryVersion 显式传入时优先使用；
        # 否则根据 prdVer+device.romVersion 推导能力清单文件夹名。
        logger.info(
            f"{_MODULE} capability_registry_building requested_version="
            f"{request.capabilityRegistryVersion} "
            f"prd_ver={request.prdVer} "
            f"device_rom_version={request.device.romVersion}"
        )
        try:
            registry = CapabilityRegistry(
                version=request.capabilityRegistryVersion,
                app_version=request.prdVer,
                device_rom_version=request.device.romVersion,
            )
        except ValueError as exc:
            settings = get_settings()
            if not settings.enable_default_capability_registry_fallback:
                raise
            requested_version = self._capability_registry_version_hint(request)
            fallback_version = settings.capability_registry_version
            if requested_version == fallback_version:
                raise
            logger.warning(
                f"{_MODULE} capability_registry_fallback "
                f"requested_version={requested_version} "
                f"fallback_version={fallback_version} reason={exc}"
            )
            registry = CapabilityRegistry(version=fallback_version)
        logger.info(f"{_MODULE} capability_registry_built registry_version={registry.version}")
        return registry

    def _capability_registry_version_hint(self, request) -> str:
        """推导请求对应的能力清单版本名。

        入参：
        - request：包含 prdVer 和 device.romVersion 的请求对象。
        出参：即使目录不存在也能用于响应和日志的版本文件夹名。
        """
        if request.capabilityRegistryVersion:
            return request.capabilityRegistryVersion
        settings = get_settings()
        return CapabilityRegistry.from_app_rom_versions(
            request.prdVer or settings.default_prd_version,
            request.device.romVersion,
        )

    def _build_artifact(
        self,
        genui: str,
        card_spec: dict,
        task_spec: dict,
        data_capabilities: list,
        event_candidates: list,
        asset_candidates: list,
        removed: list,
        protocol_profile_id: str,
        protocol_profile_version: str,
        capability_registry_version: str,
        data_bindings: list | None = None,
        artifact_id: str | None = None,
        generation_mode: str = "create",
        source_artifact_digest: str | None = None,
    ) -> WidgetArtifact:
        """组装完整 artifact。

        入参：
        - genui：三行 JSONL DSL。
        - card_spec：最终 CardSpec。
        - task_spec：传给 A2UI 模型的 TaskSpec。
        - data_bindings：有效数据绑定列表，保留字段投影用于下一轮继承。
        - data_capabilities：有效数据能力列表。
        - event_candidates：有效事件候选列表。
        - asset_candidates：有效素材候选列表。
        - removed：被移除能力列表。
        - protocol_profile_id：协议 profile ID。
        - protocol_profile_version：协议 profile 版本。
        - capability_registry_version：能力注册表版本。
        - artifact_id：本轮不可变产物 UUID。
        - generation_mode：create 或 edit。
        - source_artifact_digest：编辑来源摘要；首次生成为空。
        出参：完整 WidgetArtifact。
        """
        # artifact 是端侧下载后的唯一交付物，里面同时包含 DSL、CardSpec、TaskSpec 和能力裁决结果。
        logger.info(
            f"{_MODULE} artifact_building protocol_profile_id={protocol_profile_id} "
            f"protocol_profile_version={protocol_profile_version} "
            f"capability_registry_version={capability_registry_version} "
            f"data_capability_count={len(data_capabilities)} "
            f"event_candidate_count={len(event_candidates)} "
            f"asset_candidate_count={len(asset_candidates)} removed_count={len(removed)}"
        )
        artifact_id = artifact_id or str(uuid.uuid4())
        return WidgetArtifact(
            genui=genui,
            cardSpec=card_spec,
            taskSpec=task_spec,
            effectiveCapabilities={
                # data 只暴露能力 ID，端侧按 CardSpec.dataBindings 执行真实数据刷新。
                "data": [item.id for item in data_capabilities],
                # event 保留完整 call/args，方便端侧直接绑定点击行为。
                "event": [
                    item.model_dump(mode="json", exclude_none=True) for item in event_candidates
                ],
                # asset 只暴露素材 ID，端侧从资源包或素材注册表解析具体文件。
                "asset": [item.id for item in asset_candidates],
            },
            removedCapabilities=removed,
            generationPlan=GenerationPlan(
                candidateDataBindings=data_bindings or [],
                candidateEventCandidates=[
                    {
                        "capabilityId": item.id,
                        "action": {
                            "call": item.call,
                            "args": item.args,
                        },
                    }
                    for item in event_candidates
                ],
                candidateAssetIds=[item.id for item in asset_candidates],
            ),
            meta=ArtifactMeta(
                dslProtocolVersion=protocol_profile_version,
                protocolProfileId=protocol_profile_id,
                capabilityRegistryVersion=capability_registry_version,
                generationMode=generation_mode,
                artifactId=artifact_id,
                sourceArtifactDigest=source_artifact_digest,
                createdAt=int(time.time() * 1000),
            ),
        )
