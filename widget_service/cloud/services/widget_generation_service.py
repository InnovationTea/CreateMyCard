# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import hashlib
import inspect
import time
import uuid
from collections.abc import Awaitable, Callable

from anyio import to_thread

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
from custom.a2ui_model_client import (
    A2UIModelClient,
    A2UIModelGenerationError,
    build_prompt_log_summary,
    require_generated_dsl,
)
from custom.model_runtime import ModelExecutionRuntime
from models.artifact import ArtifactMeta, GenerationPlan, WidgetArtifact
from models.generation import DEFAULT_WIDGET_SIZE, ModelRequestContext, WidgetSize
from models.preflight import GenerationPreflightError
from services.artifact_store import ArtifactStore
from services.capability_registry import CapabilityRegistry
from services.device_capability_resolver import DeviceCapabilityResolver
from services.edit_request_normalizer import EditRequestNormalizer
from services.generation_pipeline import (
    DslProcessingContext,
    DslProcessingResult,
    DslProcessorKind,
    GenerationRoutePolicy,
    QualityIssue,
    get_dsl_processor,
)
from services.generation_preflight import GenerationPreflight
from services.prompt_builder import PromptBuilder
from services.protocol_registry import (
    A2UI_FORM_PROTOCOL_PROFILE_ID,
    TERSE_DSL_NESTED2_PROFILE_ID,
    A2UIProtocolRegistry,
    ProtocolProfileSelection,
)
from services.response_planner import ResponsePlanner
from services.retry_controller import RetryController
from services.source_artifact_repository import (
    SourceArtifactError,
    SourceArtifactLoadResult,
    SourceArtifactRepository,
)
from services.template_generation import generate_template_artifact
from services.validator import ArtifactValidator

_MODULE = "[Generation Service]"


class WidgetGenerationService:
    """编排微服务暴露的卡片工具能力。

    该类是业务主流程入口：先选择版本化能力清单并裁决候选能力，再构造 CardSpec、
    TaskSpec 和模型提示词，最后执行模型调用、校验、artifact 保存与响应规划。
    """

    def __init__(self, model_runtime: ModelExecutionRuntime | None = None) -> None:
        """注入应用生命周期共享的模型运行时。"""
        self.model_runtime = model_runtime

    async def widget_card_service(
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

        if request.operation in {
            "generateWidgetCard",
            "generateWidgetCardCompactDsl",
            "generateWidgetCardTerseDslNested2",
        }:
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
                return await self.generate_widget_card_compact_dsl(generation_request)
            if request.operation == "generateWidgetCardTerseDslNested2":
                return await self.generate_widget_card_terse_dsl_nested2(
                    generation_request
                )
            return await self.generate_widget_card_a2ui_form(generation_request)

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
        # 三个公开接口统一按 App/ROM 二维版本区间选择能力注册表。
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

    async def generate_widget_card(
        self,
        request: GenerateWidgetCardRequest,
        *,
        policy: GenerationRoutePolicy,
        before_model_call: Callable[[WidgetSize], Awaitable[None]] | None = None,
    ) -> GenerateWidgetCardResponse:
        """生成卡片。

        主流程顺序：
        1. 加载并归一化可选的上一版 artifact。
        2. 选择能力注册表和协议 Profile，裁决数据、事件与素材候选。
        3. 构造 CardSpec、TaskSpec 以及新建或编辑提示词。
        4. 调用模型；模型异常重试和 DSL error 修复分别由独立开关控制。
        5. 校验最终 DSL，保存 artifact，并生成面向主 Agent 的状态响应。

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
        previous_design_token = None
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
                    suggestSize=request.size or DEFAULT_WIDGET_SIZE,
                    message="当前暂未开放卡片继续编辑能力。",
                    errorCode=ErrorCode.WIDGET_EDIT_DISABLED.value,
                )
            try:
                source_load_result = await to_thread.run_sync(
                    SourceArtifactRepository().load,
                    request.sourceArtifactUrl or "",
                )
                if policy.stores_design_token:
                    previous_design_token = self._require_source_design_token(
                        source_load_result
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
                    suggestSize=request.size or DEFAULT_WIDGET_SIZE,
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
                    suggestSize=request.size or DEFAULT_WIDGET_SIZE,
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
        latency_by_stage["registry"] = self._elapsed_ms(stage_started_at)
        stage_started_at = time.perf_counter()
        # 设备可用性已由第一个接口完成；生成前置门禁只做确定性的注册表和结构校验。
        preflight = GenerationPreflight(registry).run(request)
        if preflight.blocking_issues:
            issue_payloads = [
                item.model_dump(mode="json") for item in preflight.blocking_issues
            ]
            logger.warning(
                f"{_MODULE} generation_preflight_rejected "
                f"issue_count={len(preflight.blocking_issues)} "
                f"issues={json_for_log(issue_payloads)}"
            )
            raise GenerationPreflightError(preflight)
        effective_bindings = list(preflight.effective_bindings)
        effective_data_capabilities = list(preflight.effective_data_capabilities)
        effective_events = list(preflight.effective_events)
        asset_candidates = list(preflight.effective_assets)
        removed = list(preflight.removed_capabilities)
        card_spec = preflight.card_spec
        task_spec = preflight.task_spec
        if card_spec is None or task_spec is None:
            raise RuntimeError("generation preflight did not build generation specs")
        latency_by_stage["generationPreflight"] = self._elapsed_ms(stage_started_at)
        stage_started_at = time.perf_counter()
        # 协议 profile 决定 A2UI 组件白名单、DSL 行数要求和校验规则。
        protocol_registry = A2UIProtocolRegistry(policy.protocol_profile_id)
        protocol_profile = protocol_registry.get_profile()
        conversion_protocol_profile = protocol_profile
        if policy.processor_kind == DslProcessorKind.TERSE_NESTED2:
            conversion_protocol_profile = A2UIProtocolRegistry.read_design_protocol_profile(
                policy.model_profile_id
            )
        if previous_design_token is not None:
            token_is_valid = await self._validate_source_design_token(
                previous_design_token,
                source_load_result,
                policy,
                conversion_protocol_profile,
            )
            if not token_is_valid:
                logger.error(
                    f"{_MODULE} source_design_token_invalid "
                    f"operation={policy.operation} source_format={policy.source_format} "
                    f"error_code={ErrorCode.SOURCE_ARTIFACT_INVALID.value}"
                )
                return GenerateWidgetCardResponse(
                    status=GenerationStatus.FAILED,
                    suggestSize=request.size or DEFAULT_WIDGET_SIZE,
                    message="上一版卡片的设计数据无效，本次修改未完成，原卡片不受影响。",
                    errorCode=ErrorCode.SOURCE_ARTIFACT_INVALID.value,
                )
        logger.info(
            f"{_MODULE} generate_flow_step_protocol_loaded "
            f"protocol_profile_id={protocol_profile['id']} "
            f"protocol_version={protocol_profile['version']} "
            f"operation={policy.operation} processor={policy.processor_kind} "
            f"model_backend={policy.backend} "
            f"design_profile_id={policy.design_profile_id or ''}"
        )
        latency_by_stage["protocol"] = self._elapsed_ms(stage_started_at)
        stage_started_at = time.perf_counter()
        logger.info(
            f"{_MODULE} prevalidated_data_capability_loaded "
            f"effective_binding_count={len(effective_bindings)} "
            "effective_binding_ids="
            f"{json_for_log([item.capabilityId for item in effective_bindings])}"
        )
        logger.info(
            f"{_MODULE} event_capability_resolved effective_event_count={len(effective_events)} "
            f"removed_count={len(removed)} "
            "effective_events="
            f"{json_for_log([item.model_dump(mode='json') for item in effective_events])} "
            "preflight_warnings="
            f"{json_for_log([item.model_dump(mode='json') for item in preflight.warnings])}"
        )
        logger.info(
            f"{_MODULE} asset_capability_resolved effective_asset_count={len(asset_candidates)} "
            f"effective_asset_ids={json_for_log([item.id for item in asset_candidates])}"
        )
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

        logger.info(
            f"{_MODULE} card_and_task_spec_built data_binding_count={len(effective_bindings)} "
            "card_spec="
            f"{json_for_log(card_spec.model_dump(mode='json', exclude_none=True))} "
            "task_spec="
            f"{json_for_log(task_spec.model_dump(mode='json', exclude_none=True))} "
            "task_data_model_schema_keys="
            f"{json_for_log(list(task_spec.dataModelSchema))}"
        )
        # Prompt 约束模型生成源 DSL；Processor 和 Validator 依次产出统一质量问题，再由策略决定门禁。
        if policy.stores_design_token:
            design_system_prompt = A2UIProtocolRegistry.read_design_prompt(
                policy.model_profile_id
            )
            prompt = PromptBuilder().build_design_token(
                task_spec,
                design_system_prompt,
                policy.source_format,
                previous_design_token=previous_design_token,
            )
        else:
            prompt = PromptBuilder().build(
                task_spec,
                protocol_profile,
                "；".join(f"{item.id}:{item.reason}" for item in removed),
                previous_genui=(
                    source_load_result.artifact.genui if source_load_result else None
                ),
            )
        prompt_log_summary = build_prompt_log_summary(
            prompt,
            settings.model_prompt_log_preview_chars,
        )
        logger.info(
            f"{_MODULE} a2ui_prompt_built "
            f"prompt_summary={json_for_log(prompt_log_summary)}"
        )
        latency_by_stage["specAndPrompt"] = self._elapsed_ms(stage_started_at)
        stage_started_at = time.perf_counter()

        model_client = A2UIModelClient(
            backend=policy.backend,
            runtime=self.model_runtime,
            request_context=self._resolve_model_request_context(request),
            operation_name=policy.operation,
        )
        model_protocol_profile = {
            "id": policy.model_profile_id,
            "format": policy.model_format,
        }
        retry_controller = RetryController()
        artifact_id = str(uuid.uuid4())
        model_call_phase = "initial"
        quality_repair_attempt_count = 0
        if policy.processor_kind == DslProcessorKind.TERSE_NESTED2:
            design_mode = "edit" if source_load_result else "create"
            repair_prompt_type = f"terse-dsl-nested-2-{design_mode}"
        elif policy.processor_kind == DslProcessorKind.DESIGN_COMPACT:
            design_mode = "edit" if source_load_result else "create"
            repair_prompt_type = f"design-compact-{design_mode}"
        elif source_load_result:
            repair_prompt_type = "edit"
        else:
            repair_prompt_type = "create"

        processor = get_dsl_processor(policy.processor_kind)
        processing_context = DslProcessingContext(
            size=card_spec.suggestSize,
            card_spec=card_spec.model_dump(mode="json", exclude_none=True),
            task_spec=task_spec.model_dump(mode="json", exclude_none=True),
            protocol_profile=conversion_protocol_profile,
            design_profile_id=policy.design_profile_id,
            data_capabilities=effective_data_capabilities,
            event_candidates=effective_events,
        )
        latest_processing_result = DslProcessingResult(source_dsl="")

        async def generate_source_dsl() -> str:
            if before_model_call is not None:
                await before_model_call(card_spec.suggestSize)
            logger.info(
                f"{_MODULE} model_source_generation_started operation={policy.operation}"
            )
            result = await self._resolve_model_result(
                model_client.generate(prompt, model_protocol_profile)
            )
            return require_generated_dsl(result)

        async def repair_source_dsl(
            invalid_source_dsl: str,
            quality_errors: list[str],
        ) -> str:
            nonlocal model_call_phase, quality_repair_attempt_count
            quality_repair_attempt_count += 1
            quality_error_payloads = [
                item.to_prompt_payload() for item in latest_processing_result.errors
            ]
            if len(quality_error_payloads) != len(quality_errors):
                raise RuntimeError("repair quality issue state is inconsistent")
            quality_error_stages = sorted(
                {item["stage"] for item in quality_error_payloads}
            )
            repair_prompt = PromptBuilder().build_repair(
                prompt,
                invalid_source_dsl,
                quality_error_payloads,
                dsl_format=policy.source_format,
            )
            logger.info(
                f"{_MODULE} a2ui_repair_started repair_prompt_type={repair_prompt_type} "
                f"operation={policy.operation} model_backend={policy.backend} "
                f"source_format={policy.source_format} "
                f"quality_error_stages={json_for_log(quality_error_stages)} "
                f"repair_attempt={quality_repair_attempt_count} "
                f"max_repair_attempts={settings.validation_failure_max_repair_attempts} "
                f"quality_error_count={len(quality_errors)}"
            )
            model_call_phase = "repair"
            result = await self._resolve_model_result(
                model_client.generate_repair(
                    repair_prompt,
                    model_protocol_profile,
                )
            )
            return require_generated_dsl(result)

        def evaluate_source_dsl_sync(source_dsl: str) -> list[str]:
            nonlocal latest_processing_result
            processing_result = processor.process(source_dsl, processing_context)
            latest_processing_result = processing_result
            warnings = [
                item.repair_message()
                for item in processing_result.issues
                if item.severity == "warning"
            ]
            if warnings:
                logger.warning(
                    f"{_MODULE} dsl_processing_warnings operation={policy.operation} "
                    f"warnings={json_for_log(warnings)}"
                )
            conversion_errors = [item.repair_message() for item in processing_result.errors]
            if conversion_errors:
                logger.error(
                    f"{_MODULE} dsl_conversion_failed operation={policy.operation} "
                    f"errors={json_for_log(conversion_errors)}"
                )
                return conversion_errors
            if not settings.enable_artifact_validation:
                logger.info(
                    f"{_MODULE} artifact_validation_skipped operation={policy.operation} "
                    "reason=enable_artifact_validation_false"
                )
                return []

            standard_dsl = processing_result.standard_dsl
            artifact = self._build_artifact(
                standard_dsl,
                processing_context.card_spec,
                processing_context.task_spec,
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
            validation_errors = artifact_validator.validate(artifact, protocol_profile)
            if source_load_result:
                source_write_roots = {
                    item.writeResultTo
                    for item in source_load_result.artifact.generationPlan.candidateDataBindings
                }
                current_write_roots = {item.writeResultTo for item in effective_bindings}
                for removed_root in sorted(source_write_roots - current_write_roots):
                    if removed_root in standard_dsl:
                        validation_errors.append(
                            f"removed data path remains in edited genui: {removed_root}"
                        )
            validation_issues = tuple(
                QualityIssue(
                    stage="validation",
                    code="ARTIFACT_VALIDATION_FAILED",
                    message=message,
                )
                for message in validation_errors
            )
            latest_processing_result = DslProcessingResult(
                source_dsl=processing_result.source_dsl,
                standard_dsl=processing_result.standard_dsl,
                issues=processing_result.issues + validation_issues,
            )
            return [item.repair_message() for item in validation_issues]

        async def evaluate_source_dsl(source_dsl: str) -> list[str]:
            return await to_thread.run_sync(evaluate_source_dsl_sync, source_dsl)

        retry_on_validation_failure = settings.enable_validation_failure_retry
        try:
            retry_result = await retry_controller.run(
                generate_source_dsl,
                evaluate_source_dsl,
                retry_on_quality_failure=retry_on_validation_failure,
                max_repair_attempts=settings.validation_failure_max_repair_attempts,
                repair=repair_source_dsl,
            )
        except A2UIModelGenerationError as exc:
            quality_repair_count = quality_repair_attempt_count
            model_failure_retry_count = model_client.model_failure_retry_count
            total_retry_count = model_failure_retry_count + quality_repair_count
            latency_by_stage["modelAndValidation"] = self._elapsed_ms(stage_started_at)
            latency_by_stage["total"] = self._elapsed_ms(generation_started_at)
            effective_capabilities = {
                "data": [item.id for item in effective_data_capabilities],
                "event": [
                    item.model_dump(mode="json", exclude_none=True)
                    for item in effective_events
                ],
                "asset": [item.id for item in asset_candidates],
            }
            logger.error(
                f"{_MODULE} a2ui_generation_failed phase={model_call_phase} "
                f"error_code={ErrorCode.A2UI_GENERATION_FAILED.value} "
                f"model_failure_retry_count={model_failure_retry_count} "
                f"quality_repair_count={quality_repair_count} "
                f"exception_type={type(exc).__name__} validation_continued=false "
                "artifact_saved=false"
            )
            response = GenerateWidgetCardResponse(
                status=GenerationStatus.FAILED,
                suggestSize=card_spec.suggestSize,
                message="卡片创建过程遇到问题了，请稍后再试。",
                removedCapabilities=removed,
                errorCode=ErrorCode.A2UI_GENERATION_FAILED.value,
                effectiveCapabilities=effective_capabilities,
            )
            self._log_generation_summary(
                request,
                protocol_profile_id=protocol_profile["id"],
                capability_registry_version=registry.version,
                effective_capabilities=effective_capabilities,
                removed=removed,
                status=response.status,
                error_code=response.errorCode,
                latency_by_stage=latency_by_stage,
                retry_count=total_retry_count,
                generation_mode=generation_mode,
                source_artifact_digest=(
                    source_load_result.artifact_digest if source_load_result else ""
                ),
                source_artifact_url_hash=(
                    source_load_result.url_hash if source_load_result else ""
                ),
            )
            return response
        source_dsl = retry_result.result
        genui = latest_processing_result.standard_dsl
        errors = retry_result.errors
        model_failure_retry_count = model_client.model_failure_retry_count
        total_retry_count = model_failure_retry_count + retry_result.retryCount
        latency_by_stage["modelAndValidation"] = self._elapsed_ms(stage_started_at)

        logger.info(
            f"{_MODULE} a2ui_generation_completed retry_count={total_retry_count} "
            f"model_failure_retry_count={model_failure_retry_count} "
            "model_failure_retry_enabled="
            f"{json_for_log(settings.enable_model_failure_retry)} "
            f"quality_repair_count={retry_result.retryCount} "
            "validation_failure_retry_enabled="
            f"{json_for_log(retry_on_validation_failure)} "
            f"initial_quality_error_count={len(retry_result.initialErrors)} "
            f"repair_attempted={json_for_log(retry_result.repairAttempted)} "
            f"repair_prompt_type={repair_prompt_type} "
            f"quality_error_count={len(errors)}"
        )
        conversion_failed = not genui.strip()
        validation_failed_blocking = policy.validation_failure_blocking and bool(errors)
        if conversion_failed or validation_failed_blocking:
            failure_category = "conversion" if conversion_failed else "validation"
            logger.error(
                f"{_MODULE} strict_generation_validation_failed "
                f"failure_category={failure_category} "
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
                retry_count=total_retry_count,
                generation_mode=generation_mode,
            )
            return response
        if errors:
            logger.error(
                f"{_MODULE} a2ui_generation_validation_failed_non_blocking "
                f"protocol_profile_id={protocol_profile['id']} "
                f"validation_error_code={ErrorCode.VALIDATION_FAILED.value} "
                f"retry_count={total_retry_count} "
                "validation_failure_retry_enabled="
                f"{json_for_log(retry_on_validation_failure)} "
                f"errors={json_for_log(errors)} "
                "proceeding_to_artifact_save=true"
            )
        stage_started_at = time.perf_counter()

        # 工具3沿用非阻断校验；工具4、5仅在转换和严格校验策略通过后组装 artifact。
        design_token = None
        if policy.stores_design_token:
            design_token = model_client.extract_genui_payload(source_dsl)
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
        artifact_save_result = ArtifactStore(design_token=design_token).save(artifact)
        if inspect.isawaitable(artifact_save_result):
            artifact_save_result = await artifact_save_result
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
            retry_count=total_retry_count,
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

    @staticmethod
    async def _resolve_model_result(value: str | Awaitable[str]) -> str:
        """兼容生产协程与测试注入的立即模型结果。"""
        if inspect.isawaitable(value):
            return await value
        return value

    @staticmethod
    def _resolve_model_request_context(
        request: GenerateWidgetCardRequest,
    ) -> ModelRequestContext:
        """优先使用路由注入的模型上下文，并为 Service 直调生成稳定兜底。"""
        if request._model_request_context is not None:
            return request._model_request_context
        settings = get_settings()
        device_id = request.device.deviceId or f"aiwidget-{uuid.uuid4().hex}"
        return ModelRequestContext(
            session_id=uuid.uuid4().hex,
            interaction_id=uuid.uuid4().hex,
            device_id=device_id,
            country_code=settings.deepseek_platform_default_country_code,
            app_version=request.prdVer or settings.default_prd_version,
            app_name=settings.deepseek_platform_default_app_name,
        )

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

    async def generate_widget_card_a2ui_form(
        self,
        request: GenerateWidgetCardRequest,
        *,
        before_model_call: Callable[[WidgetSize], Awaitable[None]] | None = None,
    ) -> GenerateWidgetCardResponse:
        """使用标准 A2UI Form profile 和配置选择的模型后端生成卡片。"""
        settings = get_settings()
        policy = GenerationRoutePolicy(
            operation="generateWidgetCard",
            protocol_profile_id=A2UI_FORM_PROTOCOL_PROFILE_ID,
            backend=settings.a2ui_form_model_backend,
            processor_kind=DslProcessorKind.STANDARD_A2UI,
            source_format="a2ui-form",
            model_profile_id=A2UI_FORM_PROTOCOL_PROFILE_ID,
            model_format="a2ui-form",
        )
        if before_model_call is None:
            return await self._generate_widget_card_with_policy(request, policy)
        return await self._generate_widget_card_with_policy(
            request,
            policy,
            before_model_call=before_model_call,
        )

    async def generate_widget_card_compact_dsl(
        self,
        request: GenerateWidgetCardRequest,
        *,
        before_model_call: Callable[[WidgetSize], Awaitable[None]] | None = None,
    ) -> GenerateWidgetCardResponse:
        """使用配置选择的后端生成 Design Compact DSL，并转换为标准 A2UI。"""
        try:
            selection = self._compact_protocol_selection(request)
        except ValueError as exc:
            logger.error(
                f"{_MODULE} compact_protocol_selection_failed "
                f"error_code={ErrorCode.APP_VERSION_UNSUPPORTED.value} error={exc}"
            )
            return GenerateWidgetCardResponse(
                status=GenerationStatus.UNSUPPORTED,
                suggestSize=request.size or DEFAULT_WIDGET_SIZE,
                message="当前 App/ROM 版本暂无可用的卡片协议，暂时不能生成卡片。",
                errorCode=ErrorCode.APP_VERSION_UNSUPPORTED.value,
            )
        policy = GenerationRoutePolicy(
            operation="generateWidgetCardCompactDsl",
            protocol_profile_id=selection.protocol_profile_id,
            backend=get_settings().design_compact_model_backend,
            processor_kind=DslProcessorKind.DESIGN_COMPACT,
            source_format=selection.design_profile_id,
            model_profile_id=selection.design_profile_id,
            model_format="compact-dsl",
            design_profile_id=selection.design_profile_id,
            validation_failure_blocking=True,
            stores_design_token=True,
        )
        try:
            return await generate_template_artifact(
                request,
                policy,
                registry=self._capability_registry(request),
                model_runtime=self.model_runtime,
                model_request_context=self._resolve_model_request_context(request),
                before_model_call=before_model_call,
            )
        except Exception as exc:
            logger.info(
                f"{_MODULE} template_route_fallback operation={policy.operation} "
                f"reason={type(exc).__name__} detail={json_for_log(str(exc))}"
            )
        if before_model_call is None:
            return await self._generate_widget_card_with_policy(request, policy)
        return await self._generate_widget_card_with_policy(
            request,
            policy,
            before_model_call=before_model_call,
        )

    async def generate_widget_card_terse_dsl_nested2(
        self,
        request: GenerateWidgetCardRequest,
        *,
        before_model_call: Callable[[WidgetSize], Awaitable[None]] | None = None,
    ) -> GenerateWidgetCardResponse:
        """使用本地 TerseDSL-Nested-2 Prompt 和转换器生成标准 A2UI。"""
        try:
            selection = self._compact_protocol_selection(request)
        except ValueError as exc:
            logger.error(
                f"{_MODULE} terse_nested2_protocol_selection_failed "
                f"error_code={ErrorCode.APP_VERSION_UNSUPPORTED.value} error={exc}"
            )
            return GenerateWidgetCardResponse(
                status=GenerationStatus.UNSUPPORTED,
                suggestSize=request.size or DEFAULT_WIDGET_SIZE,
                message="当前 App/ROM 版本暂无可用的卡片协议，暂时不能生成卡片。",
                errorCode=ErrorCode.APP_VERSION_UNSUPPORTED.value,
            )
        policy = GenerationRoutePolicy(
            operation="generateWidgetCardTerseDslNested2",
            protocol_profile_id=selection.protocol_profile_id,
            backend=get_settings().design_compact_model_backend,
            processor_kind=DslProcessorKind.TERSE_NESTED2,
            source_format=TERSE_DSL_NESTED2_PROFILE_ID,
            model_profile_id=TERSE_DSL_NESTED2_PROFILE_ID,
            model_format=TERSE_DSL_NESTED2_PROFILE_ID,
            design_profile_id=TERSE_DSL_NESTED2_PROFILE_ID,
            supports_dynamic_capabilities=False,
            validation_failure_blocking=True,
            stores_design_token=True,
        )
        try:
            return await generate_template_artifact(
                request,
                policy,
                registry=self._capability_registry(request),
                model_runtime=self.model_runtime,
                model_request_context=self._resolve_model_request_context(request),
                before_model_call=before_model_call,
            )
        except Exception as exc:
            logger.info(
                f"{_MODULE} template_route_fallback operation={policy.operation} "
                f"reason={type(exc).__name__} detail={json_for_log(str(exc))}"
            )
        if before_model_call is None:
            return await self._generate_widget_card_with_policy(request, policy)
        return await self._generate_widget_card_with_policy(
            request,
            policy,
            before_model_call=before_model_call,
        )

    async def _generate_widget_card_with_policy(
        self,
        request: GenerateWidgetCardRequest,
        policy: GenerationRoutePolicy,
        *,
        before_model_call: Callable[[WidgetSize], Awaitable[None]] | None = None,
    ) -> GenerateWidgetCardResponse:
        """复制请求并锁定路由对应的协议 profile。"""
        unsupported_response = self._policy_unsupported_response(request, policy)
        if unsupported_response is not None:
            return unsupported_response
        profiled_request = request.model_copy(
            update={"protocolProfileId": policy.protocol_profile_id}
        )
        profiled_request._model_request_context = request._model_request_context
        return await self.generate_widget_card(
            profiled_request,
            policy=policy,
            before_model_call=before_model_call,
        )

    @staticmethod
    def _require_source_design_token(
        source: SourceArtifactLoadResult,
    ) -> str:
        """源格式编辑必须取得上一轮模型原始输出，禁止使用标准 genui 兜底。"""
        design_token = source.design_token
        if not isinstance(design_token, str) or not design_token.strip():
            raise SourceArtifactError(
                ErrorCode.SOURCE_ARTIFACT_INVALID,
                "source artifact is missing a non-empty designcompactdsl block",
            )
        return design_token

    @staticmethod
    async def _validate_source_design_token(
        design_token: str,
        source: SourceArtifactLoadResult | None,
        policy: GenerationRoutePolicy,
        conversion_protocol_profile: dict,
    ) -> bool:
        """用目标接口对应 Processor 验证上一轮 Token，防止跨源格式编辑。"""
        if source is None:
            return False
        source_card_spec = source.artifact.cardSpec
        source_size = source_card_spec.get("suggestSize")
        if not isinstance(source_size, str) or not source_size:
            return False
        context = DslProcessingContext(
            size=source_size,
            card_spec=source_card_spec,
            task_spec=source.artifact.taskSpec,
            protocol_profile=conversion_protocol_profile,
            design_profile_id=policy.design_profile_id,
        )
        processor = get_dsl_processor(policy.processor_kind)
        result = await to_thread.run_sync(processor.process, design_token, context)
        return not result.errors

    @staticmethod
    def _policy_unsupported_response(
        request: GenerateWidgetCardRequest,
        policy: GenerationRoutePolicy,
    ) -> GenerateWidgetCardResponse | None:
        """按集中路由策略拒绝当前源格式尚未支持的编辑或动态能力。"""
        is_edit = "sourceArtifactUrl" in request.model_fields_set
        if is_edit and not policy.supports_edit:
            return GenerateWidgetCardResponse(
                status=GenerationStatus.UNSUPPORTED,
                suggestSize=request.size or DEFAULT_WIDGET_SIZE,
                message="当前生成协议只支持新建卡片，不支持继续编辑。",
                errorCode=ErrorCode.PROTOCOL_CAPABILITY_UNSUPPORTED.value,
            )
        has_dynamic_capabilities = bool(
            request.candidateDataBindings or request.candidateEventCandidates
        )
        if has_dynamic_capabilities and not policy.supports_dynamic_capabilities:
            return GenerateWidgetCardResponse(
                status=GenerationStatus.UNSUPPORTED,
                suggestSize=request.size or DEFAULT_WIDGET_SIZE,
                message="当前生成协议只支持字面量静态卡片，不支持动态数据或点击事件。",
                errorCode=ErrorCode.PROTOCOL_CAPABILITY_UNSUPPORTED.value,
            )
        return None

    def _compact_protocol_selection(
        self,
        request: GenerateWidgetCardRequest,
    ) -> ProtocolProfileSelection:
        """按 App/ROM 区间选择第四接口的输出协议和 Design 提示词。"""
        settings = get_settings()
        requested_app = request.prdVer or settings.default_prd_version
        requested_rom = request.device._source_rom_version or request.device.romVersion
        requested_rom = requested_rom or settings.default_device_rom_version
        selection_type = "interval"
        try:
            selection = A2UIProtocolRegistry.from_app_rom_versions(
                requested_app,
                requested_rom,
            )
        except ValueError as exc:
            if not settings.enable_default_protocol_profile_fallback:
                raise
            selection = A2UIProtocolRegistry.default_selection(
                requested_app,
                requested_rom,
            )
            A2UIProtocolRegistry(selection.protocol_profile_id).get_profile()
            A2UIProtocolRegistry.read_design_prompt(selection.design_profile_id)
            selection_type = "fallback"
            logger.warning(
                f"{_MODULE} protocol_profile_fallback "
                f"requested_app_version={requested_app} requested_rom_version={requested_rom} "
                f"fallback_profile_id={selection.protocol_profile_id} reason={exc}"
            )
        logger.info(
            f"{_MODULE} protocol_profile_selected requested_app_version={requested_app} "
            f"requested_rom_version={requested_rom} "
            f"normalized_app_version={selection.normalized_app_version} "
            f"normalized_rom_version={selection.normalized_rom_version} "
            f"protocol_profile_id={selection.protocol_profile_id} "
            f"design_profile_id={selection.design_profile_id} selection_type={selection_type}"
        )
        return selection

    def _capability_registry(
        self,
        request,
    ) -> CapabilityRegistry:
        """按请求的 App/ROM 二维版本区间创建能力注册表。"""
        settings = get_settings()
        requested_app = request.prdVer or settings.default_prd_version
        requested_rom = request.device._source_rom_version or request.device.romVersion
        requested_rom = requested_rom or settings.default_device_rom_version
        normalized_app = CapabilityRegistry.normalize_app_version(requested_app)
        normalized_rom = CapabilityRegistry.normalize_rom_version(requested_rom)
        selection_type = "interval"
        try:
            registry = CapabilityRegistry(
                app_version=requested_app,
                device_rom_version=requested_rom,
            )
        except ValueError as exc:
            if not settings.enable_default_capability_registry_fallback:
                raise
            requested_version = self._capability_registry_version_hint(request)
            fallback_version = settings.capability_registry_version
            logger.warning(
                f"{_MODULE} capability_registry_fallback "
                f"requested_version={requested_version} "
                f"fallback_version={fallback_version} reason={exc}"
            )
            registry = CapabilityRegistry(version=fallback_version)
            selection_type = "fallback"
        logger.info(
            f"{_MODULE} capability_registry_selected requested_app_version={requested_app} "
            f"requested_rom_version={requested_rom} normalized_app_version={normalized_app} "
            f"normalized_rom_version={normalized_rom} registry_version={registry.version} "
            f"selection_type={selection_type}"
        )
        return registry

    def _capability_registry_version_hint(self, request) -> str:
        """推导请求对应的能力清单版本名。

        入参：
        - request：包含 prdVer 和 device.romVersion 的请求对象。
        出参：即使目录不存在也能用于响应和日志的版本文件夹名。
        """
        settings = get_settings()
        return CapabilityRegistry.requested_version_label(
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
