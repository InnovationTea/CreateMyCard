"""Compact/TerseDSL-Nested-2 的模板路由入口。"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from api.schemas import GenerateWidgetCardRequest, GenerateWidgetCardResponse
from app.logger import json_for_log, logger
from core.errors import ErrorCode, GenerationStatus
from custom.model_runtime import ModelExecutionRuntime
from models.generation import DEFAULT_WIDGET_SIZE, ModelRequestContext, WidgetSize
from services.artifact_store import ArtifactStore
from services.capability_registry import CapabilityRegistry
from services.card_spec_builder import CardSpecBuilder
from services.edit_request_normalizer import EditRequestNormalizer
from services.generation_pipeline import DslProcessorKind, GenerationRoutePolicy
from services.generation_preflight import GenerationPreflight
from services.protocol_registry import A2UIProtocolRegistry
from services.response_planner import ResponsePlanner
from services.task_spec_builder import TaskSpecBuilder
from services.template_generation.archive import (
    TemplateArchiveError,
    build_template_archive,
    build_terse_template_archive,
)
from services.template_generation.artifact_builder import build_template_artifact
from services.template_generation.binding_dependencies import enrich_template_bindings
from services.template_generation.engine.advanced.scope_planner import (
    TemplateRouteNotApplicable,
)
from services.template_generation.engine.pipeline import (
    TemplateGenerationError,
    generate_template_a2ui,
)
from services.template_generation.model_client import (
    create_template_model_client,
)
from services.validator import ArtifactValidator

_MODULE = "[Template Generation]"
ModelStartCallback = Callable[[WidgetSize], Awaitable[None]]


async def generate_strict_terse_template_artifact(
    request: GenerateWidgetCardRequest,
    policy: GenerationRoutePolicy,
    *,
    registry: CapabilityRegistry,
    model_runtime: ModelExecutionRuntime | None,
    model_request_context: ModelRequestContext,
    before_model_call: ModelStartCallback | None = None,
) -> GenerateWidgetCardResponse:
    """Terse create 只允许模板成功；edit 或任一模板失败均不回退旧流程。"""
    if "sourceArtifactUrl" in request.model_fields_set:
        logger.info(f"{_MODULE} terse_route_rejected reason=edit_not_supported fallback=disabled")
        return _template_failure_response(request, "模板路线暂不支持二次更新。")

    try:
        return await generate_template_artifact(
            request,
            policy,
            registry=registry,
            model_runtime=model_runtime,
            model_request_context=model_request_context,
            before_model_call=before_model_call,
        )
    except TemplateRouteNotApplicable as exc:
        logger.info(
            f"{_MODULE} terse_route_rejected reason={type(exc).__name__} "
            f"fallback=disabled detail={json_for_log(str(exc))}"
        )
        return _template_failure_response(request, "当前需求没有可完整呈现的模板。")
    except Exception as exc:
        logger.error(
            f"{_MODULE} terse_route_failed reason={type(exc).__name__} "
            f"fallback=disabled detail={json_for_log(str(exc))}"
        )
        return _template_failure_response(request, "卡片模板生成失败，请稍后再试。")


def _template_failure_response(
    request: GenerateWidgetCardRequest,
    message: str,
) -> GenerateWidgetCardResponse:
    return GenerateWidgetCardResponse(
        status=GenerationStatus.FAILED,
        suggestSize=request.size or DEFAULT_WIDGET_SIZE,
        message=message,
        errorCode=ErrorCode.A2UI_GENERATION_FAILED.value,
    )


async def generate_template_artifact(
    request: GenerateWidgetCardRequest,
    policy: GenerationRoutePolicy,
    *,
    registry: CapabilityRegistry,
    model_runtime: ModelExecutionRuntime | None,
    model_request_context: ModelRequestContext,
    before_model_call: ModelStartCallback | None = None,
) -> GenerateWidgetCardResponse:
    """独立执行模板生成并直接返回接口结果，异常交由调用入口降级。"""
    if "sourceArtifactUrl" in request.model_fields_set:
        raise TemplateRouteNotApplicable("template generation does not support edit mode")
    normalized_request = EditRequestNormalizer.normalize_create(request)
    preflight = GenerationPreflight(registry).run(normalized_request)
    if preflight.blocking_issues or not preflight.effective_bindings:
        raise TemplateRouteNotApplicable("template candidate plan is not applicable")
    effective_bindings = enrich_template_bindings(list(preflight.effective_bindings))
    data_capabilities = list(preflight.effective_data_capabilities)
    effective_events = list(preflight.effective_events)
    asset_candidates = list(preflight.effective_assets)

    try:
        protocol_profile = A2UIProtocolRegistry(policy.protocol_profile_id).get_profile()
        design_protocol_profile = A2UIProtocolRegistry.read_design_protocol_profile(
            policy.model_profile_id
        )
    except ValueError as exc:
        raise TemplateRouteNotApplicable("template protocol profile is unavailable") from exc

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
        model_runtime,
        model_request_context,
    )
    if before_model_call is not None:
        await before_model_call(card_spec.suggestSize)
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
    artifact = build_template_artifact(
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
