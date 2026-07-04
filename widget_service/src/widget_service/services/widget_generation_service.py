import time

from widget_service.api.schemas import (
    AssetCandidateOverview,
    CapabilityOverviewRequest,
    CapabilityOverviewResponse,
    DataCapabilityOverview,
    DataCapabilitySchemasRequest,
    DataCapabilitySchemasResponse,
    EventCapabilityOverview,
    GenerateWidgetCardRequest,
    GenerateWidgetCardResponse,
)
from widget_service.core.errors import ErrorCode, GenerationStatus
from widget_service.models.artifact import ArtifactMeta, WidgetArtifact
from widget_service.models.generation import EventAction
from widget_service.services.a2ui_model_client import A2UIModelClient
from widget_service.services.artifact_store import ArtifactStore
from widget_service.services.capability_registry import CapabilityRegistry
from widget_service.services.card_spec_builder import CardSpecBuilder
from widget_service.services.device_capability_resolver import DeviceCapabilityResolver
from widget_service.services.prompt_builder import PromptBuilder
from widget_service.services.protocol_registry import A2UIProtocolRegistry
from widget_service.services.response_planner import ResponsePlanner
from widget_service.services.retry_controller import RetryController
from widget_service.services.task_spec_builder import TaskSpecBuilder
from widget_service.services.validator import ArtifactValidator


class WidgetGenerationService:
    def get_widget_capability_overview(
        self,
        request: CapabilityOverviewRequest,
    ) -> CapabilityOverviewResponse:
        registry = CapabilityRegistry(request.capabilityRegistryVersion)
        return CapabilityOverviewResponse(
            capabilityRegistryVersion=registry.version,
            dataCapabilities=[
                DataCapabilityOverview(
                    id=item.id,
                    description=item.description,
                    descriptionForLLM=item.descriptionForLLM,
                )
                for item in registry.list_data_capabilities()
            ],
            eventCapabilities=[
                EventCapabilityOverview(
                    id=item.id,
                    call=item.call,
                    description=item.description,
                    parametersSchema=item.parametersSchema,
                )
                for item in registry.list_event_capabilities()
            ],
            assetCandidates=[
                AssetCandidateOverview(
                    id=item.id,
                    src=item.src,
                    description=item.description,
                    sceneTags=item.sceneTags,
                )
                for item in registry.list_asset_capabilities()
            ],
        )

    def get_data_capability_schemas(
        self,
        request: DataCapabilitySchemasRequest,
    ) -> DataCapabilitySchemasResponse:
        registry = CapabilityRegistry(request.capabilityRegistryVersion)
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
        registry = CapabilityRegistry(request.capabilityRegistryVersion)
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
        candidate_events = self._normalize_event_candidates(request, registry)
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
            return model_client.generate(task_spec, protocol_profile, prompt)

        def validate_genui(genui: str) -> list[str]:
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
        registry: CapabilityRegistry,
    ) -> list[EventAction]:
        candidates: list[EventAction] = []
        used_ids: set[str] = set()

        for index, action in enumerate(request.candidateEventActions):
            capability_id = action.id
            if not capability_id and index < len(request.candidateEventCapabilityIds):
                capability_id = request.candidateEventCapabilityIds[index]
            candidates.append(EventAction(id=capability_id, call=action.call, args=action.args))
            if capability_id:
                used_ids.add(capability_id)

        for capability_id in request.candidateEventCapabilityIds:
            if capability_id in used_ids:
                continue
            capability = registry.get_event_capability(capability_id)
            call = capability.call if capability else "unknown"
            candidates.append(EventAction(id=capability_id, call=call, args={}))
            used_ids.add(capability_id)

        for action in request.candidateEventCapabilities:
            candidates.append(action)

        return candidates

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
