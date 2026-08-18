"""Compact/TerseDSL-Nested-2 的模板路由入口。"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from api.schemas import GenerateWidgetCardResponse
from app.logger import json_for_log, logger
from core.errors import ErrorCode, GenerationStatus
from models.generation import DEFAULT_WIDGET_SIZE, EventAction, WidgetSize
from services.artifact_store import ArtifactStore
from services.card_spec_builder import CardSpecBuilder
from services.device_capability_resolver import DeviceCapabilityResolver
from services.edit_request_normalizer import EditRequestNormalizer
from services.generation_pipeline import DslProcessorKind, GenerationRoutePolicy
from services.protocol_registry import A2UIProtocolRegistry
from services.response_planner import ResponsePlanner
from services.task_spec_builder import TaskSpecBuilder
from services.template_generation.archive import (
    TemplateArchiveError,
    build_template_archive,
    build_terse_template_archive,
)
from services.template_generation.binding_dependencies import enrich_template_bindings
from services.template_generation.engine.advanced.scope_planner import (
    TemplateRouteNotApplicable,
)
from services.template_generation.engine.pipeline import (
    TemplateGenerationError,
    generate_template_a2ui,
)
from services.template_generation.model_client import (
    TemplateModelUnavailable,
    create_template_model_client,
)
from services.validator import ArtifactValidator

_MODULE = "[Template Generation]"
ModelStartCallback = Callable[[WidgetSize], Awaitable[None]]


class _ModelStartOnce:
    def __init__(self, callback: ModelStartCallback | None) -> None:
        self._callback = callback
        self._notified = False

    async def __call__(self, size: WidgetSize) -> None:
        if self._callback is None or self._notified:
            return
        await self._callback(size)
        self._notified = True


async def route_compact_generation(
    host: Any,
    request: Any,
    policy: GenerationRoutePolicy,
    *,
    before_model_call: ModelStartCallback | None = None,
) -> Any:
    """模板成功则直接返回；未匹配和 edit 均调用原始 dev 生成逻辑。"""
    notify_model_start = _ModelStartOnce(before_model_call)
    is_edit = "sourceArtifactUrl" in request.model_fields_set
    if not is_edit:
        try:
            response = await _try_generate_template_artifact(
                host,
                request,
                policy,
                notify_model_start,
            )
        except (TemplateModelUnavailable, TemplateRouteNotApplicable) as exc:
            logger.info(
                f"{_MODULE} route_fallback reason={type(exc).__name__} "
                f"detail={json_for_log(str(exc))} fallback=original_compact_flow"
            )
        except (TemplateArchiveError, TemplateGenerationError) as exc:
            logger.error(
                f"{_MODULE} selected_route_failed exception_type={type(exc).__name__} "
                f"detail={json_for_log(str(exc))} "
                "fallback=disabled"
            )
            return GenerateWidgetCardResponse(
                status=GenerationStatus.FAILED,
                suggestSize=request.size,
                message="卡片模板生成失败，请稍后再试。",
                errorCode=ErrorCode.A2UI_GENERATION_FAILED.value,
            )
        else:
            if response is not None:
                return response

    return await _call_original_generation(
        host,
        request,
        policy,
        before_model_call,
        notify_model_start,
    )


async def route_terse_nested2_generation(
    host: Any,
    request: Any,
    policy: GenerationRoutePolicy,
    *,
    before_model_call: ModelStartCallback | None = None,
) -> Any:
    """Terse create 只允许模板成功；edit、未匹配和模板错误均明确失败。"""
    if "sourceArtifactUrl" in request.model_fields_set:
        logger.info(f"{_MODULE} terse_route_rejected reason=edit_not_supported")
        return _template_failure_response(request, "模板路线暂不支持二次更新。")

    notify_model_start = _ModelStartOnce(before_model_call)
    try:
        response = await _try_generate_template_artifact(
            host,
            request,
            policy,
            notify_model_start,
        )
    except (TemplateModelUnavailable, TemplateRouteNotApplicable) as exc:
        logger.info(
            f"{_MODULE} terse_route_rejected reason={type(exc).__name__} "
            f"detail={json_for_log(str(exc))} fallback=disabled"
        )
        return _template_failure_response(request, "当前需求没有可完整呈现的模板。")
    except (TemplateArchiveError, TemplateGenerationError) as exc:
        logger.error(
            f"{_MODULE} terse_route_failed exception_type={type(exc).__name__} "
            f"detail={json_for_log(str(exc))} "
            "fallback=disabled"
        )
        return _template_failure_response(request, "卡片模板生成失败，请稍后再试。")
    if response is None:
        logger.info(f"{_MODULE} terse_route_rejected reason=capability_not_applicable")
        return _template_failure_response(request, "当前需求没有可完整呈现的模板。")
    return response


async def _call_original_generation(
    host: Any,
    request: Any,
    policy: GenerationRoutePolicy,
    before_model_call: ModelStartCallback | None,
    notify_model_start: _ModelStartOnce,
) -> Any:
    if before_model_call is None:
        return await host._generate_widget_card_with_policy(request, policy)
    return await host._generate_widget_card_with_policy(
        request,
        policy,
        before_model_call=notify_model_start,
    )


def _template_failure_response(request: Any, message: str) -> GenerateWidgetCardResponse:
    return GenerateWidgetCardResponse(
        status=GenerationStatus.FAILED,
        suggestSize=request.size or DEFAULT_WIDGET_SIZE,
        message=message,
        errorCode=ErrorCode.A2UI_GENERATION_FAILED.value,
    )


async def _try_generate_template_artifact(
    host: Any,
    request: Any,
    policy: GenerationRoutePolicy,
    notify_model_start: _ModelStartOnce,
) -> Any | None:
    normalized_request = EditRequestNormalizer.normalize_create(request)
    try:
        registry = host._capability_registry(normalized_request)
        protocol_profile = A2UIProtocolRegistry(policy.protocol_profile_id).get_profile()
        design_protocol_profile = A2UIProtocolRegistry.read_design_protocol_profile(
            policy.model_profile_id
        )
    except ValueError:
        return None

    resolver = DeviceCapabilityResolver(registry)
    effective_bindings, data_capabilities, removed_data = (
        resolver.resolve_generation_data_bindings(normalized_request.candidateDataBindings)
    )
    if removed_data or not effective_bindings:
        return None
    effective_bindings = enrich_template_bindings(effective_bindings)

    event_candidates = _normalize_event_candidates(normalized_request)
    effective_events = []
    for event in event_candidates:
        if not event.id or registry.get_event_capability(event.id) is None:
            return None
        effective_events.append(event)

    asset_candidates = []
    for asset_id in normalized_request.candidateAssetIds:
        asset = registry.get_asset_capability(asset_id)
        if asset is None:
            return None
        asset_candidates.append(asset)

    card_spec = CardSpecBuilder().build(
        normalized_request.size,
        effective_bindings,
        normalized_request.title,
        normalized_request.description,
    )
    task_spec = TaskSpecBuilder().build(
        normalized_request.userQuery,
        normalized_request.size,
        effective_bindings,
        data_capabilities,
        effective_events,
        asset_candidates,
    )
    model_client = create_template_model_client(
        host.model_runtime,
        host._resolve_model_request_context(normalized_request),
    )
    await notify_model_start(card_spec.suggestSize)
    engine_output = await generate_template_a2ui(
        task_spec,
        card_spec.model_dump(mode="json", exclude_none=True),
        tuple(effective_bindings),
        model_client,
    )
    projected_task_spec = engine_output.projected_task_spec.model_dump(
        mode="json",
        exclude_none=True,
    )
    archive = await _build_route_archive(
        policy,
        engine_output,
        size=card_spec.suggestSize,
        card_spec=card_spec.model_dump(mode="json", exclude_none=True),
        task_spec=projected_task_spec,
        protocol_profile=protocol_profile,
        design_protocol_profile=design_protocol_profile,
        design_profile_id=policy.design_profile_id or policy.model_profile_id,
        data_capabilities=data_capabilities,
        event_candidates=effective_events,
    )
    artifact = host._build_artifact(
        archive.a2ui,
        card_spec.model_dump(mode="json", exclude_none=True),
        projected_task_spec,
        data_capabilities,
        effective_events,
        asset_candidates,
        [],
        protocol_profile["id"],
        protocol_profile["version"],
        registry.version,
        data_bindings=effective_bindings,
        generation_mode="create",
    )
    artifact = _with_internal_template_assets(
        artifact,
        engine_output.trusted_internal_asset_sources,
    )
    try:
        validation_errors = ArtifactValidator().validate(artifact, protocol_profile)
    except (RuntimeError, ValueError) as exc:
        raise TemplateArchiveError("template artifact validation failed") from exc
    if validation_errors:
        logger.error(
            f"{_MODULE} artifact_validation_failed "
            f"errors={json_for_log(validation_errors)}"
        )
        raise TemplateArchiveError("template artifact validation failed")

    try:
        save_result = ArtifactStore(design_token=archive.design_token).save(artifact)
        if inspect.isawaitable(save_result):
            save_result = await save_result
    except (OSError, RuntimeError) as exc:
        raise TemplateGenerationError("template artifact save failed") from exc
    plan = ResponsePlanner().plan(
        len(normalized_request.candidateDataBindings),
        len(effective_bindings),
        [],
        has_artifact=True,
        generation_mode="create",
    )
    logger.info(
        f"{_MODULE} artifact_generated template_ids={json_for_log(engine_output.template_ids)} "
        f"expanded_component_count={engine_output.expanded_component_count}"
    )
    return GenerateWidgetCardResponse(
        status=plan.status,
        artifactUrl=save_result.artifactUrl,
        artifactDigest=save_result.artifactDigest,
        suggestSize=card_spec.suggestSize,
        message=plan.message,
        removedCapabilities=[],
        errorCode=plan.errorCode,
        effectiveCapabilities=artifact.effectiveCapabilities,
    )


def _normalize_event_candidates(request: Any) -> list[EventAction]:
    """在隔离模块内转换生成接口事件结构，避免依赖主服务私有方法。"""
    return [
        EventAction(
            id=candidate.capabilityId,
            call=candidate.action.call,
            args=candidate.action.args,
        )
        for candidate in request.candidateEventCandidates
    ]


async def _build_route_archive(
    policy: GenerationRoutePolicy,
    engine_output: Any,
    **kwargs: Any,
) -> Any:
    if policy.processor_kind == DslProcessorKind.TERSE_NESTED2:
        terse_kwargs = dict(kwargs)
        terse_kwargs.pop("protocol_profile")
        return await build_terse_template_archive(
            engine_output.terse_dsl_nested2,
            **terse_kwargs,
        )
    return await build_template_archive(engine_output.a2ui, **kwargs)


def _with_internal_template_assets(artifact: Any, sources: tuple[str, ...]) -> Any:
    if not sources:
        return artifact
    effective = dict(artifact.effectiveCapabilities)
    effective["asset"] = list(dict.fromkeys([*effective.get("asset", []), *sources]))
    return artifact.model_copy(update={"effectiveCapabilities": effective})
