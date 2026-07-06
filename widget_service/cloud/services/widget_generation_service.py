# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import time

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
from app.logger import logger
from core.errors import ErrorCode, GenerationStatus
from models.artifact import ArtifactMeta, WidgetArtifact
from models.generation import EventAction
from services.a2ui_model_client import A2UIModelClient
from services.artifact_store import ArtifactStore
from services.capability_registry import CapabilityRegistry
from services.card_spec_builder import CardSpecBuilder
from services.device_capability_resolver import DeviceCapabilityResolver
from services.prompt_builder import PromptBuilder
from services.protocol_registry import A2UIProtocolRegistry
from services.response_planner import ResponsePlanner
from services.retry_controller import RetryController
from services.task_spec_builder import TaskSpecBuilder
from services.validator import ArtifactValidator


class WidgetGenerationService:
    """编排微服务暴露的三个工具能力。"""

    def widget_card_service(
        self,
        request: WidgetCardServiceRequest,
    ) -> CapabilityOverviewResponse | DataCapabilitySchemasResponse | GenerateWidgetCardResponse:
        """统一云侧卡片工具入口。

        入参：
        - request：包含 operation 和对应能力参数的统一工具请求。
        出参：根据 operation 返回能力概述、数据能力 schema 或卡片生成结果。
        """
        # 统一工具层只暴露一个工具名，通过 operation 分发到三个真实业务流程。
        logger.info(
            f"widget_card_service_dispatch_started operation={request.operation} "
            f"uid={request.uid} device_rom_version={request.device.romVersion} "
            f"ohos_api_version={request.device.ohosApiVersion}"
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

        if request.operation == "generateWidgetCard":
            # 生成阶段必须带原始用户需求，模型 prompt、TaskSpec 和用户话术都依赖它。
            if not request.userQuery:
                raise ValueError("userQuery is required for generateWidgetCard.")
            # dataCapabilityIds 只属于 schema 加载接口，生成请求下沉时需要剔除。
            payload = request.model_dump(exclude={"operation", "dataCapabilityIds"})
            # 尺寸是主 Agent 建议值；未传时服务用 2x4 作为一期默认推荐尺寸。
            payload["size"] = payload.get("size") or "2x4"
            return self.generate_widget_card(GenerateWidgetCardRequest(**payload))

        raise ValueError(f"Unknown operation: {request.operation}")

    def get_widget_capability_overview(
        self,
        request: CapabilityOverviewRequest,
    ) -> CapabilityOverviewResponse:
        """获取能力概述。

        入参：
        - request：包含 locale、uid、device 等版本上下文。
        出参：数据能力 id+描述，以及全量事件能力和素材清单。
        """
        logger.info(
            f"capability_overview_started uid={request.uid} "
            f"device_rom_version={request.device.romVersion} "
            f"ohos_api_version={request.device.ohosApiVersion} "
            f"request={request.model_dump(mode='json', exclude_none=True)}"
        )
        # 能力注册表按 device.ohosApiVersion+device.romVersion 文件夹隔离。
        registry = self._capability_registry(request)
        logger.info(
            "capability_registry_selected operation=getWidgetCapabilityOverview "
            f"registry_version={registry.version}"
        )
        response = CapabilityOverviewResponse(
            capabilityRegistryVersion=registry.version,
            dataCapabilities=[
                # 第一接口只暴露数据能力 id+description，完整 schema 留给第二接口渐进加载。
                DataCapabilityOverview(
                    id=item.id,
                    description=item.description,
                )
                for item in registry.list_data_capabilities()
            ],
            eventCapabilities=registry.list_event_capabilities(),
            assetCandidates=registry.list_asset_capabilities(),
        )
        logger.info(
            f"capability_overview_completed registry_version={registry.version} "
            f"data_count={len(response.dataCapabilities)} "
            f"event_count={len(response.eventCapabilities)} "
            f"asset_count={len(response.assetCandidates)}"
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
            f"data_capability_schemas_started uid={request.uid} "
            f"data_capability_ids={request.dataCapabilityIds} "
            f"request={request.model_dump(mode='json', exclude_none=True)}"
        )
        # 这里返回完整 inputSchema/outputSchema，供主 Agent 生成合法 candidateDataBindings。
        registry = self._capability_registry(request)
        logger.info(
            "capability_registry_selected operation=getDataCapabilitySchemas "
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
            f"data_capability_schemas_completed registry_version={registry.version} "
            f"found_count={len(capabilities)} missing_ids={missing}"
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
        # 主流程：解析能力、生成 CardSpec/TaskSpec、生成 genui、校验 artifact、返回结构化状态。
        logger.info(
            f"generate_widget_card_started uid={request.uid} size={request.size} "
            f"data_binding_count={len(request.candidateDataBindings)} "
            f"event_count={len(request.candidateEventCandidates)} "
            f"asset_count={len(request.candidateAssetIds)} "
            f"request={request.model_dump(mode='json', exclude_none=True)}"
        )
        # registry 负责读取当前版本的能力清单，后续所有过滤都以这份清单为准。
        registry = self._capability_registry(request)
        logger.info(
            f"generate_flow_step_registry_ready uid={request.uid} "
            f"registry_version={registry.version}"
        )
        # 协议 profile 决定 A2UI 组件白名单、DSL 行数要求和校验规则。
        protocol_registry = A2UIProtocolRegistry(request.protocolProfileId)
        protocol_profile = protocol_registry.get_profile()
        logger.info(
            f"generate_flow_step_protocol_ready uid={request.uid} "
            f"protocol_profile_id={protocol_profile['id']} "
            f"protocol_version={protocol_profile['version']}"
        )
        # resolver 负责把主 Agent 候选能力裁决成当前设备真实可用能力。
        resolver = DeviceCapabilityResolver(registry)

        # 数据能力过滤输出三份数据：最终写入 CardSpec 的 bindings、传给模型的能力定义、移除原因。
        effective_bindings, effective_data_capabilities, removed_data = (
            resolver.resolve_data_bindings(
                request.candidateDataBindings,
                request.device,
            )
        )
        logger.info(
            f"data_capability_resolved effective_binding_count={len(effective_bindings)} "
            f"removed_count={len(removed_data)} "
            f"effective_binding_ids={[item.capabilityId for item in effective_bindings]} "
            f"removed_data={[item.model_dump(mode='json') for item in removed_data]}"
        )
        # 事件候选先从外部协议结构转换成内部 EventAction，再进入统一能力裁决。
        candidate_events = self._normalize_event_candidates(request)
        # 事件能力过滤后，只把当前设备真实可用的点击动作放入 TaskSpec。
        effective_events, removed_events = resolver.resolve_event_candidates(
            candidate_events,
            request.device,
        )
        logger.info(
            f"event_capability_resolved effective_event_count={len(effective_events)} "
            f"removed_count={len(removed_events)} "
            f"effective_events={[item.model_dump(mode='json') for item in effective_events]} "
            f"removed_events={[item.model_dump(mode='json') for item in removed_events]}"
        )
        asset_candidates = []
        removed_assets = []
        for asset_id in request.candidateAssetIds:
            # 素材只允许来自注册表，防止模型引用未打包、未授权或版本不兼容的资源。
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
            f"asset_capability_resolved effective_asset_count={len(asset_candidates)} "
            f"removed_count={len(removed_assets)} "
            f"effective_asset_ids={[item.id for item in asset_candidates]} "
            f"removed_assets={[item.model_dump(mode='json') for item in removed_assets]}"
        )
        if request.candidateDataBindings and not effective_bindings and not effective_events:
            # 没有剩余动态数据或可用入口时，不调用模型，也不伪造数据绑定。
            logger.warning(
                f"generate_widget_card_unsupported uid={request.uid} "
                f"removed_count={len(removed)} "
                f"error_code={ErrorCode.NO_EFFECTIVE_CAPABILITY.value}"
            )
            return GenerateWidgetCardResponse(
                status=GenerationStatus.UNSUPPORTED,
                suggestSize=request.size,
                message="当前设备上没有可用的数据能力或入口能力，暂时不能生成这类实时卡片。你可以试试天气、日历或系统状态类卡片。",
                removedCapabilities=removed,
                errorCode=ErrorCode.NO_EFFECTIVE_CAPABILITY.value,
            )

        # CardSpec 是端侧运行时刷新数据的契约，只包含裁决后的有效数据绑定。
        card_spec = CardSpecBuilder().build(request.size, effective_bindings)
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
            f"card_and_task_spec_built data_binding_count={len(effective_bindings)} "
            f"card_spec={card_spec.model_dump(mode='json', exclude_none=True)} "
            f"task_spec={task_spec.model_dump(mode='json', exclude_none=True)} "
            f"task_data_model_keys={list(task_spec.dataModel.get('value', {}).keys())}"
        )
        # prompt 只作为模型生成 DSL 的约束输入，最终协议仍由 CardSpec 和 Validator 兜底。
        prompt = PromptBuilder().build(
            task_spec,
            protocol_profile,
            "；".join(f"{item.id}:{item.reason}" for item in removed),
        )
        logger.info(
            f"a2ui_prompt_built uid={request.uid} "
            f"prompt={prompt.model_dump(mode='json', exclude_none=True)}"
        )

        model_client = A2UIModelClient()
        retry_controller = RetryController()

        def operation() -> str:
            """执行一次 A2UI 模型生成。

            入参：无。
            出参：三行 JSONL genui 字符串。
            """
            # mock 模型客户端当前返回稳定 DSL；后续替换真实模型时保持 generate 入参不变。
            logger.info(f"a2ui_model_operation_started uid={request.uid}")
            return model_client.generate(task_spec, protocol_profile, prompt)

        def validate_genui(genui: str) -> list[str]:
            """校验单次模型输出。

            入参：
            - genui：模型生成的三行 JSONL 字符串。
            出参：校验错误列表；空列表表示通过。
            """
            # 每次模型输出都临时组装 artifact，再用同一套 Validator 校验完整契约。
            logger.info(
                f"a2ui_genui_validation_started uid={request.uid} "
                f"genui_length={len(genui)}"
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
                registry.version,
            )
            return ArtifactValidator().validate(artifact, protocol_profile)

        # RetryController 把“生成一次”和“校验一次”组合起来，失败时可重试生成。
        retry_result = retry_controller.run(operation, validate_genui)
        genui = retry_result.result
        errors = retry_result.errors
        logger.info(
            f"a2ui_generation_completed retry_count={retry_result.retryCount} "
            f"validation_error_count={len(errors)}"
        )
        if errors:
            logger.error(
                f"a2ui_generation_validation_failed uid={request.uid} errors={errors}"
            )
            return GenerateWidgetCardResponse(
                status=GenerationStatus.FAILED,
                suggestSize=request.size,
                message="卡片生成过程中校验失败，请稍后再试。",
                removedCapabilities=removed,
                errorCode=ErrorCode.VALIDATION_FAILED.value,
            )

        # 校验通过后重新组装最终 artifact，确保保存内容和最后一次成功 genui 一致。
        artifact = self._build_artifact(
            genui,
            card_spec.model_dump(mode="json", exclude_none=True),
            task_spec.model_dump(mode="json", exclude_none=True),
            effective_data_capabilities,
            effective_events,
            asset_candidates,
            removed,
            protocol_profile["id"],
            registry.version,
        )
        # ArtifactStore 当前是本地 mock/OBS TODO 入口，返回端侧可下载 URL 和摘要。
        logger.info(
            f"artifact_built uid={request.uid} "
            f"effective_capabilities={artifact.effectiveCapabilities} "
            f"removed_count={len(artifact.removedCapabilities)}"
        )
        artifact_save_result = ArtifactStore().save(artifact)
        # ResponsePlanner 根据移除能力和最终产物判断 success/degraded/failed 等用户状态。
        response_plan = ResponsePlanner().plan(
            len(request.candidateDataBindings),
            len(effective_bindings),
            removed,
            has_artifact=True,
        )
        logger.info(
            f"generate_widget_card_completed status={response_plan.status.value} "
            f"artifact_url={artifact_save_result.artifactUrl} "
            f"removed_count={len(removed)} error_code={response_plan.errorCode}"
        )
        return GenerateWidgetCardResponse(
            status=response_plan.status,
            artifactUrl=artifact_save_result.artifactUrl,
            artifactDigest=artifact_save_result.artifactDigest,
            suggestSize=card_spec.suggestSize,
            message=response_plan.message,
            removedCapabilities=removed,
            errorCode=response_plan.errorCode,
            # 生产默认不内联 artifact；调试时可通过内部 options 打开，避免 WS 响应体过大。
            artifact=artifact.model_dump(mode="json", exclude_none=True)
            if request.options.returnArtifactInline
            else None,
            effectiveCapabilities=artifact.effectiveCapabilities,
        )

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

    def _capability_registry(self, request) -> CapabilityRegistry:
        """按请求版本上下文创建能力注册表。

        入参：
        - request：包含 capabilityRegistryVersion 和 device 版本字段的请求对象。
        出参：对应版本的 CapabilityRegistry。
        """
        # capabilityRegistryVersion 显式传入时优先使用；
        # 否则根据 device.ohosApiVersion+device.romVersion 推导能力清单文件夹名。
        logger.info(
            f"capability_registry_building requested_version="
            f"{request.capabilityRegistryVersion} "
            f"ohos_api_version={request.device.ohosApiVersion} "
            f"device_rom_version={request.device.romVersion}"
        )
        registry = CapabilityRegistry(
            version=request.capabilityRegistryVersion,
            ohos_api_version=request.device.ohosApiVersion,
            device_rom_version=request.device.romVersion,
        )
        logger.info(f"capability_registry_built registry_version={registry.version}")
        return registry

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
        capability_registry_version: str,
    ) -> WidgetArtifact:
        """组装完整 artifact。

        入参：
        - genui：三行 JSONL DSL。
        - card_spec：最终 CardSpec。
        - task_spec：传给 A2UI 模型的 TaskSpec。
        - data_capabilities：有效数据能力列表。
        - event_candidates：有效事件候选列表。
        - asset_candidates：有效素材候选列表。
        - removed：被移除能力列表。
        - protocol_profile_id：协议 profile ID。
        - capability_registry_version：能力注册表版本。
        出参：完整 WidgetArtifact。
        """
        # artifact 是端侧下载后的唯一交付物，里面同时包含 DSL、CardSpec、TaskSpec 和能力裁决结果。
        logger.info(
            f"artifact_building protocol_profile_id={protocol_profile_id} "
            f"capability_registry_version={capability_registry_version} "
            f"data_capability_count={len(data_capabilities)} "
            f"event_candidate_count={len(event_candidates)} "
            f"asset_candidate_count={len(asset_candidates)} removed_count={len(removed)}"
        )
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
            meta=ArtifactMeta(
                protocolProfileId=protocol_profile_id,
                capabilityRegistryVersion=capability_registry_version,
                createdAt=int(time.time() * 1000),
            ),
        )
