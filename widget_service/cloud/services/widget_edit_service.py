"""独立的二次编辑编排；不进入首次生成、模板、Compact 或主题流程。"""

from __future__ import annotations

import copy
import inspect
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from anyio import to_thread

from api.schemas import GenerateWidgetCardRequest, GenerateWidgetCardResponse
from app.logger import logger
from config.config import get_settings
from core.errors import ErrorCode, GenerationStatus
from custom.a2ui_model_client import A2UIModelClient, A2UIModelGenerationError
from models.artifact import WidgetArtifact
from models.generation import WidgetSize
from models.preflight import GenerationPreflightError, GenerationPreflightResult
from services.artifact_store import ArtifactStore, ArtifactUploadError
from services.card_validation.edit_validation.artifact import (
    edit_expectation_errors,
    validate_edit_artifact,
)
from services.edit_request_normalizer import EditRequestNormalizer
from services.generation_pipeline import GenerationRoutePolicy
from services.generation_preflight import GenerationPreflight
from services.generation_trace_recorder import trace_record, trace_span
from services.post_layout_theme_registry import registered_themes
from services.single_step_edit import _load_json
from services.source_artifact_repository import SourceArtifactError, SourceArtifactRepository
from services.widget_edit_contract import (
    EditIntent,
    apply_edit_output,
    has_layout_change,
    validate_edit_source_structure,
    validate_intent,
)
from services.widget_edit_prompt import execution_prompt, intent_prompt, repair_feedback

if TYPE_CHECKING:
    from services.widget_generation_service import WidgetGenerationService

_PROFILE = {"id": "semantic-widget-edit", "format": "raw-json", "singleStepOutput": False}


class WidgetEditService:
    def __init__(self, host: WidgetGenerationService) -> None:
        self.host = host

    async def generate(
        self, request: GenerateWidgetCardRequest, policy: GenerationRoutePolicy,
        before_model_call: Callable[[WidgetSize], Awaitable[None]] | None = None,
    ) -> GenerateWidgetCardResponse:
        settings = get_settings()
        if not settings.enable_widget_edit:
            return self._response(request, GenerationStatus.UNSUPPORTED,
                                  "当前暂未开放卡片继续编辑能力。", ErrorCode.WIDGET_EDIT_DISABLED)
        if not policy.supports_edit:
            return self._response(request, GenerationStatus.UNSUPPORTED,
                                  "当前协议不支持继续编辑。", ErrorCode.WIDGET_EDIT_UNSUPPORTED)
        try:
            loaded = await to_thread.run_sync(SourceArtifactRepository().load,
                                             request.sourceArtifactUrl or "")
        except SourceArtifactError as exc:
            return self._response(request, GenerationStatus.FAILED,
                                  "上一版卡片无法安全读取，原卡片不受影响。", exc.error_code)
        original = loaded.artifact.model_copy(deep=True)
        try:
            validate_edit_source_structure(original.genui)
        except (ValueError, TypeError, RecursionError) as exc:
            trace_record("edit.source.structure.failed", stage="edit.source", status="failed",
                         details={"reason": str(exc)})
            return self._response(request, GenerationStatus.FAILED,
                                  "来源卡片结构无效。", ErrorCode.SOURCE_ARTIFACT_INVALID)
        source_size = original.cardSpec.get("suggestSize")
        if source_size not in {"2x2", "2x4"}:
            return self._response(request, GenerationStatus.FAILED,
                                  "来源卡片规格无效。", ErrorCode.SOURCE_ARTIFACT_INVALID)
        normalized = EditRequestNormalizer().normalize_edit(request, original).request
        if not _same_business_candidates(original, normalized):
            return self._response(
                normalized, GenerationStatus.UNSUPPORTED,
                "本次视觉编辑不能新增、删除或替换数据、点击行为和素材。",
                ErrorCode.WIDGET_EDIT_UNSUPPORTED, feedback=True,
            )
        explicit_size = request.size
        try:
            registry = self.host._capability_registry(normalized)
        except ValueError:
            return self._response(normalized, GenerationStatus.UNSUPPORTED,
                                  "当前版本暂无可用能力清单。", ErrorCode.APP_VERSION_UNSUPPORTED)
        preflight = GenerationPreflight(registry).run(normalized)
        if preflight.blocking_issues:
            raise GenerationPreflightError(preflight)
        runtime_changes = _runtime_changes(original, preflight, request)
        client = A2UIModelClient(
            backend=policy.backend, runtime=self.host.model_runtime,
            request_context=self.host._resolve_model_request_context(normalized),
            operation_name="semanticWidgetEdit",
        )
        trace_record("edit.started", stage="edit", status="started", details={
            "sourceDigest": loaded.artifact_digest, "sourceSize": source_size,
            "explicitSize": explicit_size,
        })
        try:
            with trace_span("edit.intent", stage="edit.intent"):
                intent = await self._intent(
                    client, original.genui, normalized.userQuery,
                    source_size, explicit_size, runtime_changes,
                )
            runtime_only = intent.outcome == "unchanged" and bool(runtime_changes)
            runtime_only = runtime_only and intent.targetSize == source_size
            if intent.outcome != "ready" and not runtime_only:
                return self._business_result(normalized, intent)
            normalized = normalized.model_copy(update={"size": intent.targetSize})
            # 目标规格由接受的意图裁决后重新构造，不让模型修改最终运行配置。
            preflight = GenerationPreflight(registry).run(normalized)
            if preflight.blocking_issues:
                raise GenerationPreflightError(preflight)
            candidate = self._candidate(original, normalized, preflight, policy,
                                        registry.version, loaded.artifact_digest)
            if before_model_call is not None:
                await before_model_call(intent.targetSize)
            with trace_span("edit.execute", stage="edit.execute"):
                if runtime_only:
                    # 原组件树没有变更，仍须完整验证新运行配置，不能漏掉参数更新。
                    result = await to_thread.run_sync(
                        validate_edit_artifact, original, candidate, intent,
                    )
                    if result.errors:
                        raise ValueError("; ".join(result.errors))
                    final = candidate
                else:
                    final = await self._execute(
                        client, original, candidate, normalized.userQuery, intent,
                    )
        except A2UIModelGenerationError:
            return self._response(
                normalized, GenerationStatus.FAILED,
                "编辑模型调用失败，原卡片不受影响。", ErrorCode.A2UI_GENERATION_FAILED,
            )
        except (ValueError, TypeError, RecursionError) as exc:
            trace_record("edit.validation.failed", stage="edit.validation", status="failed",
                         details={"reason": str(exc)})
            return self._response(
                normalized, GenerationStatus.FAILED,
                "本次修改未通过编辑校验，原卡片不受影响。", ErrorCode.WIDGET_EDIT_INVALID,
            )
        # 保存/上传失败向外传播，不通过重新生成卡片处理存储问题。
        store = ArtifactStore(request_body=self.host._request_body_for_artifact(request))
        saved = store.save(final)
        if inspect.isawaitable(saved):
            saved = await saved
        if not saved.artifactUrl or saved.artifactUrl == request.sourceArtifactUrl:
            raise ArtifactUploadError("编辑保存必须产生独立的新产物地址")
        trace_record("edit.completed", stage="edit", status="success", details={
            "targetSize": intent.targetSize, "mode": intent.mode,
        }, json_artifacts={"edit_final_artifact": final.model_dump(mode="json", exclude_none=True)})
        return GenerateWidgetCardResponse(
            status=GenerationStatus.SUCCESS, artifactUrl=saved.artifactUrl,
            artifactDigest=saved.artifactDigest, suggestSize=intent.targetSize,
            message="已按你的要求修改卡片。", effectiveCapabilities=final.effectiveCapabilities,
        )

    async def _intent(self, client: A2UIModelClient, original: str, query: str,
                      source_size: str, explicit_size: str | None,
                      runtime_changes: dict) -> EditIntent:
        messages = intent_prompt(original, query, source_size, explicit_size, runtime_changes)
        budget = get_settings().widget_edit_max_repair_attempts
        for attempt in range(budget + 1):
            output = await self._call(client, messages, "edit_intent")
            try:
                intent = EditIntent.model_validate(_load_json(output))
                validate_intent(intent, original, source_size, explicit_size)
                if intent.outcome == "unchanged":
                    unmet = edit_expectation_errors(original, original, intent)
                    if unmet:
                        raise ValueError("; ".join(unmet))
            except (ValueError, TypeError, RecursionError) as exc:
                messages.extend(repair_feedback(output, [str(exc)], "intent"))
                if attempt == budget:
                    raise ValueError("编辑意图合同修复次数耗尽") from exc
                continue
            trace_record("edit.intent.accepted", stage="edit.intent", status=intent.outcome,
                         json_artifacts={"edit_intent": intent.model_dump(mode="json")})
            return intent
        raise AssertionError("编辑意图循环异常结束")

    async def _execute(self, client: A2UIModelClient, original: WidgetArtifact,
                       candidate: WidgetArtifact, query: str, intent: EditIntent) -> WidgetArtifact:
        messages = execution_prompt(original.genui, query, intent)
        budget = get_settings().widget_edit_max_repair_attempts
        for attempt in range(budget + 1):
            output = await self._call(client, messages, "edit_execute")
            current = candidate.model_copy(deep=True)
            errors: list[str] = []
            try:
                current.genui = apply_edit_output(original.genui, output, intent)
                if original.cardSpec.get("suggestSize") != intent.targetSize:
                    if not has_layout_change(original.genui, current.genui):
                        raise ValueError("尺寸适配必须实际调整布局，不能只改变颜色或元信息")
                result = await to_thread.run_sync(validate_edit_artifact, original, current, intent)
                errors = result.errors
                trace_record("edit.validation.completed", stage="edit.validation",
                             status="failed" if errors else "success", details={"attempt": attempt},
                             json_artifacts={"edit_diagnostics": {
                                 "errors": errors, "warnings": result.warnings,
                             }})
            except (ValueError, TypeError, RecursionError) as exc:
                errors.append(str(exc))
            if not errors:
                return current
            logger.warning(f"[Widget Edit] validation_failed attempt={attempt} errors={errors}")
            messages.extend(repair_feedback(output, errors, "execute"))
        raise ValueError("编辑执行修复次数耗尽")

    @staticmethod
    async def _call(client: A2UIModelClient, messages: list[dict], phase: str) -> str:
        output = client.generate(messages, _PROFILE, phase=phase, suppress_prompt_log=True)
        if inspect.isawaitable(output):
            output = await output
        return output

    def _candidate(self, original: WidgetArtifact, request: GenerateWidgetCardRequest,
                   preflight: GenerationPreflightResult, policy: GenerationRoutePolicy,
                   registry_version: str, digest: str) -> WidgetArtifact:
        from services.protocol_registry import A2UIProtocolRegistry

        if preflight.card_spec is None or preflight.task_spec is None:
            raise ValueError("编辑预检未构建完整运行配置")
        profile = A2UIProtocolRegistry(policy.protocol_profile_id).get_profile()
        candidate = self.host._build_artifact(
            original.genui, preflight.card_spec.model_dump(mode="json", exclude_none=True),
            preflight.task_spec.model_dump(mode="json", exclude_none=True),
            list(preflight.effective_data_capabilities), list(preflight.effective_events),
            list(preflight.effective_assets), list(preflight.removed_capabilities),
            policy.protocol_profile_id, profile.get("version", "v0.9"), registry_version,
            data_bindings=list(preflight.effective_bindings), generation_mode="edit",
            source_artifact_digest=digest,
        )
        _retain_source_assets(original, candidate)
        return candidate

    @staticmethod
    def _business_result(request: GenerateWidgetCardRequest,
                         intent: EditIntent) -> GenerateWidgetCardResponse:
        statuses = {
            "needs_clarification": GenerationStatus.NEEDS_CLARIFICATION,
            "unchanged": GenerationStatus.UNCHANGED,
            "unsupported": GenerationStatus.UNSUPPORTED,
        }
        status = statuses.get(intent.outcome)
        if status is None:
            raise ValueError("不是可结束的编辑业务结果")
        error = ErrorCode.WIDGET_EDIT_UNSUPPORTED if intent.outcome == "unsupported" else None
        return WidgetEditService._response(
            request, status, intent.explanation, error, feedback=True,
        )

    @staticmethod
    def _response(
        request: GenerateWidgetCardRequest, status: GenerationStatus, message: str,
        error: ErrorCode | None, *, feedback: bool = False,
    ) -> GenerateWidgetCardResponse:
        return GenerateWidgetCardResponse(
            status=status, suggestSize=request.size or "2x2", message=message,
            errorCode=error.value if error is not None else "",
            editFeedback=message if feedback else None,
        )


def _retain_source_assets(original: WidgetArtifact, candidate: WidgetArtifact) -> None:
    """保留原卡已使用素材的地址，及登记主题；不授权新图像或重新映射原卡。"""
    allowed = set(candidate.effectiveCapabilities.get("asset", []))
    theme_ids = set()
    for theme in registered_themes(include_disabled=True):
        theme_ids.add(theme.get("id"))
    source_assets = original.taskSpec.get("assetCandidates", [])
    if not isinstance(source_assets, list):
        raise ValueError("原卡素材候选必须为数组")
    by_id: dict[str, dict[str, Any]] = {}
    for item in candidate.taskSpec.get("assetCandidates", []):
        by_id[item.get("id")] = item
    for item in source_assets:
        if not isinstance(item, dict):
            continue
        identity = item.get("id")
        if not isinstance(identity, str):
            continue
        if identity in allowed or identity in theme_ids:
            by_id[identity] = copy.deepcopy(item)
            allowed.add(identity)
    candidate.taskSpec["assetCandidates"] = list(by_id.values())
    existing = candidate.effectiveCapabilities.setdefault("asset", [])
    for identity in by_id:
        if identity not in existing:
            existing.append(identity)


def _same_business_candidates(original: WidgetArtifact, request: GenerateWidgetCardRequest) -> bool:
    """视觉编辑不接受候选替换；已有参数修改保留相同能力和写入路径。"""
    from services.single_step_edit import _same

    plan = original.generationPlan
    old_bindings = [(item.capabilityId, item.writeResultTo) for item in plan.candidateDataBindings]
    new_bindings = []
    for item in request.candidateDataBindings or []:
        new_bindings.append((item.capabilityId, item.writeResultTo))
    if old_bindings != new_bindings:
        return False
    events = []
    for event in request.candidateEventCandidates or []:
        events.append(event.model_dump(mode="json", exclude_none=True))
    if not _same(plan.candidateEventCandidates, events):
        return False
    return _same(plan.candidateAssetIds, request.candidateAssetIds)


def _runtime_changes(original: WidgetArtifact, preflight: GenerationPreflightResult,
                     request: GenerateWidgetCardRequest) -> dict:
    from services.single_step_edit import _same

    changes: dict = {}
    if preflight.card_spec is None:
        return changes
    current = preflight.card_spec.model_dump(mode="json", exclude_none=True)
    request_fields = {"title": "title", "description": "description",
                      "dataBindings": "candidateDataBindings"}
    for key, request_field in request_fields.items():
        if request_field not in request.model_fields_set:
            continue
        if not _same(original.cardSpec.get(key), current.get(key)):
            changes[key] = {"before": original.cardSpec.get(key), "after": current.get(key)}
    return changes
