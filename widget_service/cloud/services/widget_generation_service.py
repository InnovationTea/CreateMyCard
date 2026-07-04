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
        if request.operation == "getWidgetCapabilityOverview":
            return self.get_widget_capability_overview(
                CapabilityOverviewRequest(**request.model_dump(exclude={"operation"}))
            )

        if request.operation == "getDataCapabilitySchemas":
            if not request.dataCapabilityIds:
                raise ValueError("dataCapabilityIds is required for getDataCapabilitySchemas.")
            return self.get_data_capability_schemas(
                DataCapabilitySchemasRequest(**request.model_dump(exclude={"operation"}))
            )

        if request.operation == "generateWidgetCard":
            if not request.userQuery:
                raise ValueError("userQuery is required for generateWidgetCard.")
            payload = request.model_dump(exclude={"operation", "dataCapabilityIds"})
            payload["size"] = payload.get("size") or "2x4"
            return self.generate_widget_card(GenerateWidgetCardRequest(**payload))

        raise ValueError(f"Unknown operation: {request.operation}")

    def get_widget_capability_overview(
        self,
        request: CapabilityOverviewRequest,
    ) -> CapabilityOverviewResponse:
        """获取能力概述。

        入参：
        - request：包含 locale、appVersion、romVersion 等版本上下文。
        出参：数据能力 id+描述，以及全量事件能力和素材清单。
        """
        registry = self._capability_registry(request)
        return CapabilityOverviewResponse(
            capabilityRegistryVersion=registry.version,
            dataCapabilities=[
                DataCapabilityOverview(
                    id=item.id,
                    description=item.description,
                )
                for item in registry.list_data_capabilities()
            ],
            eventCapabilities=registry.list_event_capabilities(),
            assetCandidates=registry.list_asset_capabilities(),
        )

    def get_data_capability_schemas(
        self,
        request: DataCapabilitySchemasRequest,
    ) -> DataCapabilitySchemasResponse:
        """获取数据能力完整 schema。

        入参：
        - request：包含数据能力 ID 列表和版本上下文。
        出参：已注册数据能力完整定义，以及缺失能力 ID 列表。
        """
        registry = self._capability_registry(request)
        capabilities = []
        missing = []
        for capability_id in request.dataCapabilityIds:
            capability = registry.get_data_capability(capability_id)
            if capability is None:
                missing.append(capability_id)
            else:
                capabilities.append(capability)
        return DataCapabilitySchemasResponse(
            capabilityRegistryVersion=registry.version,
            dataCapabilities=capabilities,
            missingCapabilityIds=missing,
        )

    def generate_widget_card(
        self, request: GenerateWidgetCardRequest
    ) -> GenerateWidgetCardResponse:
        """生成卡片。

        入参：
        - request：用户需求、尺寸、候选数据绑定、候选事件、候选素材和版本上下文。
        出参：生成状态、artifact 地址、摘要、用户话术、降级原因和有效能力。
        """
        # 主流程：解析能力、生成 CardSpec/TaskSpec、生成 genui、校验 artifact、返回结构化状态。
        registry = self._capability_registry(request)
        protocol_registry = A2UIProtocolRegistry(request.protocolProfileId)
        protocol_profile = protocol_registry.get_profile()
        resolver = DeviceCapabilityResolver(registry)

        effective_bindings, effective_data_capabilities, removed_data = (
            resolver.resolve_data_bindings(
                request.candidateDataBindings,
                request.romVersion,
                request.appVersion,
                request.xiaoyiVersion,
            )
        )
        candidate_events = self._normalize_event_candidates(request)
        effective_events, removed_events = resolver.resolve_event_candidates(
            candidate_events,
            request.romVersion,
            request.appVersion,
            request.xiaoyiVersion,
        )
        asset_candidates = []
        removed_assets = []
        for asset_id in request.candidateAssetIds:
            asset = registry.get_asset_capability(asset_id)
            if asset is None:
                removed_assets.append(
                    resolver._removed(asset_id, ErrorCode.UNKNOWN_CAPABILITY, "asset")
                )
            else:
                asset_candidates.append(asset)

        removed = removed_data + removed_events + removed_assets
        if request.candidateDataBindings and not effective_bindings and not effective_events:
            # 没有剩余动态数据或可用入口时，不调用模型，也不伪造数据绑定。
            return GenerateWidgetCardResponse(
                status=GenerationStatus.UNSUPPORTED,
                suggestSize=request.size,
                userMessage="当前设备上没有可用的数据能力或入口能力，暂时不能生成这类实时卡片。你可以试试天气、日历或系统状态类卡片。",
                removedCapabilities=removed,
                errorCode=ErrorCode.NO_EFFECTIVE_CAPABILITY.value,
            )

        card_spec = CardSpecBuilder().build(request.size, effective_bindings)
        task_spec = TaskSpecBuilder().build(
            request.userQuery,
            request.size,
            effective_data_capabilities,
            effective_events,
            asset_candidates,
        )
        prompt = PromptBuilder().build(
            task_spec,
            protocol_profile,
            "；".join(f"{item.id}:{item.reason}" for item in removed),
        )

        model_client = A2UIModelClient()
        retry_controller = RetryController()

        def operation() -> str:
            """执行一次 A2UI 模型生成。

            入参：无。
            出参：三行 JSONL genui 字符串。
            """
            return model_client.generate(task_spec, protocol_profile, prompt)

        def validate_genui(genui: str) -> list[str]:
            """校验单次模型输出。

            入参：
            - genui：模型生成的三行 JSONL 字符串。
            出参：校验错误列表；空列表表示通过。
            """
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

        genui, retry_count, errors = retry_controller.run(operation, validate_genui)
        if errors:
            return GenerateWidgetCardResponse(
                status=GenerationStatus.FAILED,
                suggestSize=request.size,
                userMessage="卡片生成过程中校验失败，请稍后再试。",
                removedCapabilities=removed,
                errorCode=ErrorCode.VALIDATION_FAILED.value,
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
        artifact_url, artifact_digest = ArtifactStore().save(artifact)
        status, user_message, error_code = ResponsePlanner().plan(
            len(request.candidateDataBindings),
            len(effective_bindings),
            removed,
            has_artifact=True,
        )
        return GenerateWidgetCardResponse(
            status=status,
            artifactUrl=artifact_url,
            artifactDigest=artifact_digest,
            suggestSize=card_spec.suggestSize,
            userMessage=user_message,
            removedCapabilities=removed,
            errorCode=error_code,
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
        - request：包含 capabilityRegistryVersion、appVersion、romVersion 的请求对象。
        出参：对应版本的 CapabilityRegistry。
        """
        return CapabilityRegistry(
            version=request.capabilityRegistryVersion,
            app_version=request.appVersion,
            rom_version=request.romVersion,
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
        return WidgetArtifact(
            genui=genui,
            cardSpec=card_spec,
            taskSpec=task_spec,
            effectiveCapabilities={
                "data": [item.id for item in data_capabilities],
                "event": [
                    item.model_dump(mode="json", exclude_none=True) for item in event_candidates
                ],
                "asset": [item.id for item in asset_candidates],
            },
            removedCapabilities=removed,
            meta=ArtifactMeta(
                protocolProfileId=protocol_profile_id,
                capabilityRegistryVersion=capability_registry_version,
                createdAt=int(time.time() * 1000),
            ),
        )
