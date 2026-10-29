# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import copy
import hashlib
import json
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import ValidationError

from api.schemas import GenerateWidgetCardRequest
from app.logger import json_for_log, json_text_for_log, logger
from config.config import get_settings
from core.errors import ErrorCode
from core.json_pointer import parse_json_pointer
from custom.a2ui_model_client import A2UIModelClient
from custom.model_runtime import ModelExecutionRuntime
from custom.model_transport import ModelBackend
from models.capability import EventDynamicArgument
from models.generation import CandidateDataBinding, GenerationOptions, ModelRequestContext
from models.preflight import GenerationPreflightError
from services.agent_feedback import request_validation_feedback
from services.argument_json_recovery import (
    DECODER,
    PreservedArguments,
    extract_fragments,
    repair_syntax,
    validate_recovery_depth,
)
from services.capability_registry import CapabilityRegistry
from services.card_validation.base import expression_references
from services.edit_request_normalizer import EditRequestNormalizer
from services.generation_preflight import GenerationPreflight
from services.protocol_registry import DESIGN_COMPACT_PROFILE_ID, A2UIProtocolRegistry

_MODULE = "[Compact DSL Argument Repair]"
_RAW_JSON_PROFILE = {
    "id": "compact-dsl-argument-repair",
    "format": "raw-json",
}
_WRAPPER_KEYS = frozenset({"arguments", "content", "functionName", "skillName"})
_PROTECTED_TRANSPORT_KEYS = frozenset({"odid", "uid"})
_PRESERVED_OUTER_KEYS = frozenset({"bundleName", "odid", "romVersion", "uid"})
_BUSINESS_KEYS = frozenset(
    {
        "userQuery",
        "sourceArtifactUrl",
        "size",
        "title",
        "description",
        "candidateDataBindings",
        "candidateEventCandidates",
        "candidateAssetIds",
        "options",
    }
)
_TARGET_STRUCTURE = {
    "bundleName": "string, optional",
    "romVersion": "string, optional",
    "userQuery": "non-empty string, required",
    "sourceArtifactUrl": "non-empty string, edit only, optional",
    "size": "2x2 or 2x4, optional",
    "title": "non-empty string, required when sourceArtifactUrl is absent",
    "description": "non-empty string, required when sourceArtifactUrl is absent",
    "candidateAssetIds": ["string"],
    "candidateDataBindings": [
        {
            "capabilityId": "string",
            "arguments": "object",
            "writeResultTo": "string",
            "candidateOutputFields": ["string"],
        }
    ],
    "candidateEventCandidates": [
        {
            "capabilityId": "string",
            "action": {
                "call": "string",
                "args": "object",
            },
        }
    ],
    "options": {"allowDegradation": "boolean"},
}
_MISSING = object()
_MAX_ARGUMENT_CHARS = 131072


class CompactDslArgumentRepairError(ValueError):
    """表示模型候选无法作为生成请求的 content 使用。"""

    def __init__(self, message: str, *, feedback: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.feedback = feedback


class CompactDslArgumentRepairExhaustedError(ValueError):
    """参数恢复失败是本轮生成的终态，不再让 Agent 自动改参循环。"""

    error_code = ErrorCode.A2UI_GENERATION_FAILED

    def __init__(
        self,
        message: str,
        *,
        diagnostic: dict[str, Any] | None = None,
        attempts: int | None = None,
    ) -> None:
        super().__init__(message)
        self.diagnostic = diagnostic
        self.attempts = attempts

    def details(self) -> dict[str, Any]:
        details: dict[str, Any] = {
            "stage": "argumentRepair",
            "retryable": False,
            "requiredActions": ["NOTIFY_USER"],
            "agentInstruction": (
                "停止本轮自动调用并告知用户生成失败，保留原有效来源。"
            ),
        }
        if self.diagnostic is not None:
            details["diagnostic"] = self.diagnostic
            details["agentInstruction"] += "diagnostic 仅供定位，不授予重试权限。"
        if self.attempts is not None:
            details["repairAttempts"] = self.attempts
        return details


def argument_repair_diagnostic(exc: Exception) -> dict[str, Any]:
    """仅保留受控校验诊断；不将原始异常、参数值或内部修复指令返回主 Agent。"""
    diagnostic: dict[str, Any] = {
        "stage": "argumentRepair",
        "message": "参数恢复未通过完整性或结构检查，无法安全还原完整业务对象。",
    }
    if isinstance(exc, CompactDslArgumentRepairError) and exc.feedback is not None:
        issues = []
        for issue in exc.feedback.get("issues", []):
            item = {}
            for name in ("code", "path", "message", "expected", "actualType", "referenceSource"):
                if name in issue:
                    item[name] = issue.get(name)
            issues.append(item)
        diagnostic = {"stage": exc.feedback.get("stage"), "issues": issues}
    elif isinstance(exc, json.JSONDecodeError):
        diagnostic = {
            "stage": "argumentRepair",
            "message": "内层参数未能解析为合法 JSON；核对括号、逗号、引号及转义。",
            "line": exc.lineno,
            "column": exc.colno,
        }
    elif not isinstance(exc, ValueError):
        diagnostic = {"stage": "argumentRepair", "message": "参数恢复执行异常，未取得可用结果。"}
    return diagnostic


@dataclass(frozen=True)
class CompactDslArgumentRecoveryResult:
    """参数恢复模块返回给路由的完整结果。"""

    content: dict[str, Any]
    mode: Literal["decoded", "syntax", "structure", "model", "model_retry"]
    attempts: int
    dropped_candidates: tuple[str, ...]
    warnings: tuple[str, ...]
    raw_arguments_hash: str


class ConsecutiveArgumentIssueTracker:
    """按 requestId 记录连续字符串化 arguments 的出现次数。"""

    def __init__(self, max_entries: int = 2048) -> None:
        self._max_entries = max_entries
        self._counts: OrderedDict[str, int] = OrderedDict()
        self._lock = threading.Lock()

    def record(self, request_id: str, reminder_count: int) -> tuple[int, bool]:
        """记录一次问题；超过允许提醒次数时返回需要进入兜底。"""
        normalized_reminder_count = max(reminder_count, 0)
        with self._lock:
            issue_count = self._counts.pop(request_id, 0) + 1
            self._counts[request_id] = issue_count
            while len(self._counts) > self._max_entries:
                self._counts.popitem(last=False)
        return issue_count, issue_count > normalized_reminder_count

    def reset(self, request_id: str | None) -> None:
        """清除一个 requestId；缺少关联 ID 时不影响其它请求。"""
        if request_id is None:
            return
        with self._lock:
            self._counts.pop(request_id, None)

    def clear(self) -> None:
        """清除全部状态，供测试隔离和进程收口使用。"""
        with self._lock:
            self._counts.clear()


compact_dsl_argument_issue_tracker = ConsecutiveArgumentIssueTracker()


def has_explicit_stringified_arguments(payload: dict[str, Any]) -> bool:
    """判断 content 是否明确携带字符串化 arguments。"""
    content = payload.get("content")
    if not isinstance(content, dict):
        return False
    return isinstance(content.get("arguments"), str)


def recover_deterministic_content(
    payload: dict[str, Any],
) -> CompactDslArgumentRecoveryResult | None:
    """先尝试不调用模型的解码／语法／登记结构恢复；失败不修改原请求。"""
    content = payload.get("content")
    if not isinstance(content, dict):
        return None
    raw = content.get("arguments")
    if not isinstance(raw, str) and not _has_encoded_fields(content):
        return None
    validate_recovery_depth(content)
    mode: Literal["decoded", "syntax", "structure", "model", "model_retry"] = "structure"
    if isinstance(raw, str):
        mode = "decoded"
        if len(raw) > _MAX_ARGUMENT_CHARS:
            raise CompactDslArgumentRepairError("arguments exceed recovery size limit")
        try:
            source = DECODER.decode(raw)
        except json.JSONDecodeError:
            source = DECODER.decode(repair_syntax(raw))
            mode = "syntax"
        except RecursionError as exc:
            raise CompactDslArgumentRepairError("arguments exceed recovery depth limit") from exc
        if not isinstance(source, dict):
            raise CompactDslArgumentRepairError("arguments root must be an object")
        validate_recovery_depth(source)
        source = _merge_outer_business(source, content)
    else:
        source = copy.deepcopy(content)
    for name in ("functionName", "skillName", "uid", "odid"):
        source.pop(name, None)
    registry, warnings = _select_capability_registry(payload, source)
    normalized, _dropped, structure_warnings = _normalize_model_output(
        json.dumps(source, ensure_ascii=False), content, payload, registry,
    )
    if not isinstance(raw, str) and _same_values(normalized, content):
        return None
    return CompactDslArgumentRecoveryResult(
        content=normalized, mode=mode, attempts=0, dropped_candidates=(),
        warnings=tuple([*warnings, *structure_warnings]),
        raw_arguments_hash=hashlib.sha256(
            json.dumps(content, ensure_ascii=False).encode("utf-8")
        ).hexdigest(),
    )


def _has_encoded_fields(content: dict[str, Any]) -> bool:
    bindings = content.get("candidateDataBindings")
    if isinstance(bindings, list):
        for binding in bindings:
            if isinstance(binding, dict) and isinstance(binding.get("arguments"), str):
                return True
    events = content.get("candidateEventCandidates")
    if isinstance(events, list):
        for candidate in events:
            if not isinstance(candidate, dict):
                continue
            if "actionTemplate" in candidate:
                return True
            action = candidate.get("action")
            if isinstance(action, str):
                return True
            if isinstance(action, dict) and isinstance(action.get("args"), str):
                return True
    return False


def _merge_outer_business(
    source: dict[str, Any], content: dict[str, Any],
) -> dict[str, Any]:
    merged = copy.deepcopy(source)
    for name, value in content.items():
        if name in _WRAPPER_KEYS:
            continue
        if name in _PROTECTED_TRANSPORT_KEYS:
            merged.pop(name, None)
            continue
        if name in _PRESERVED_OUTER_KEYS:
            merged[name] = copy.deepcopy(value)
            continue
        if name in merged and not _same_values(merged.get(name), value):
            raise CompactDslArgumentRepairError(f"conflicting outer field: {name}")
        merged[name] = copy.deepcopy(value)
    for name in _PROTECTED_TRANSPORT_KEYS:
        merged.pop(name, None)
    return merged


def _same_values(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        if left.keys() != right.keys():
            return False
        return all(_same_values(value, right.get(key)) for key, value in left.items())
    if isinstance(left, list):
        if len(left) != len(right):
            return False
        return all(_same_values(a, b) for a, b in zip(left, right, strict=True))
    return left == right


def _decode_object_fields(content: dict[str, Any]) -> None:
    """只解码已登记的对象位置，不将展示文案或业务参数中的字符串解释成对象。"""
    bindings = content.get("candidateDataBindings")
    if isinstance(bindings, list):
        for binding in bindings:
            if isinstance(binding, dict):
                _decode_object_at(binding, "arguments")
    events = content.get("candidateEventCandidates")
    if not isinstance(events, list):
        return
    for candidate in events:
        if not isinstance(candidate, dict):
            continue
        if "actionTemplate" in candidate:
            if "action" in candidate:
                raise CompactDslArgumentRepairError("action and actionTemplate conflict")
            candidate["action"] = candidate.pop("actionTemplate")
        _decode_object_at(candidate, "action")
        action = candidate.get("action")
        if isinstance(action, dict):
            _decode_object_at(action, "args")


def _decode_object_at(container: dict[str, Any], name: str) -> None:
    value = container.get(name)
    if isinstance(value, str):
        container[name] = _strict_json_object(value, allow_empty=True)


async def recover_compact_dsl_content(
    payload: dict[str, Any],
    *,
    backend: ModelBackend,
    model_runtime: ModelExecutionRuntime | None,
    request_context: ModelRequestContext,
    max_attempts: int,
) -> CompactDslArgumentRecoveryResult:
    """恢复字符串参数，并把模型结果规范化为可进入生成流程的 content。"""
    content = payload.get("content")
    if not isinstance(content, dict):
        raise CompactDslArgumentRepairError("content must be an object")
    raw_arguments = content.get("arguments")
    if not isinstance(raw_arguments, str):
        raise CompactDslArgumentRepairError("content.arguments must be a string")
    if len(raw_arguments) > _MAX_ARGUMENT_CHARS:
        raise CompactDslArgumentRepairError("arguments exceed recovery size limit")

    normalized_attempts = min(max(max_attempts, 1), 3)
    raw_hash = hashlib.sha256(raw_arguments.encode("utf-8")).hexdigest()
    registry, registry_warnings = _select_capability_registry(payload, content)
    preserved = _preserve_valid_fragments(raw_arguments, registry)
    for key in ("bundleName", "romVersion"):
        if key in content:
            preserved.fields[key] = content.get(key)
    previous_output = ""
    validation_errors: list[str] = []
    last_diagnostic: dict[str, Any] | None = None
    client = A2UIModelClient(
        use_mock=False,
        backend=backend,
        runtime=model_runtime,
        request_context=request_context,
        operation_name="generateWidgetCardCompactDsl.argumentRepair",
    )
    try:
        for attempt in range(1, normalized_attempts + 1):
            prompt = _build_repair_prompt(
                content,
                previous_output=previous_output,
                validation_errors=validation_errors,
                preserved=preserved,
            )
            raw_output = ""
            try:
                raw_output = await client.generate(
                    prompt,
                    _RAW_JSON_PROFILE,
                    suppress_prompt_log=True,
                    phase="argument_repair",
                )
                logger.info(
                    f"{_MODULE} model_output attempt={attempt} "
                    f"raw_arguments_hash={raw_hash} output={json_text_for_log(raw_output)}"
                )
                repaired_content, dropped, warnings = _normalize_model_output(
                    raw_output,
                    content,
                    payload,
                    registry,
                    preserved=preserved,
                )
            except Exception as exc:
                previous_output = raw_output
                validation_errors = _repair_error_messages(exc)
                last_diagnostic = argument_repair_diagnostic(exc)
                logger.warning(
                    f"{_MODULE} model_candidate_rejected attempt={attempt} "
                    f"max_attempts={normalized_attempts} "
                    f"will_retry={json_for_log(attempt < normalized_attempts)} "
                    f"exception_type={type(exc).__name__} "
                    f"diagnostic={json_for_log(last_diagnostic)}"
                )
                continue
            mode: Literal["model", "model_retry"] = (
                "model_retry" if attempt > 1 else "model"
            )
            combined_warnings = (*registry_warnings, *warnings)
            result = CompactDslArgumentRecoveryResult(
                content=repaired_content,
                mode=mode,
                attempts=attempt,
                dropped_candidates=tuple(dropped),
                warnings=tuple(combined_warnings),
                raw_arguments_hash=raw_hash,
            )
            _log_recovery_result(result)
            return result
    finally:
        try:
            await client.aclose()
        except Exception as exc:
            logger.warning(
                f"{_MODULE} model_client_close_failed "
                f"exception_type={type(exc).__name__}"
            )

    logger.error(
        f"{_MODULE} recovery_failed attempts={normalized_attempts} "
        f"raw_arguments_hash={raw_hash} will_retry=false "
        f"diagnostic={json_for_log(last_diagnostic)}"
    )
    raise CompactDslArgumentRepairExhaustedError(
        "卡片生成失败，请重试一下。", diagnostic=last_diagnostic, attempts=normalized_attempts,
    )


def _build_repair_prompt(
    content: dict[str, Any],
    *,
    previous_output: str = "",
    validation_errors: list[str] | None = None,
    preserved: PreservedArguments | None = None,
) -> list[dict[str, str]]:
    model_content = {
        key: value for key, value in content.items() if key not in _PROTECTED_TRANSPORT_KEYS
    }
    raw_arguments = model_content.get("arguments")
    if not isinstance(raw_arguments, str):
        raise CompactDslArgumentRepairError("content.arguments must be a string")
    repair_input: dict[str, Any] = {
        "rawArguments": raw_arguments,
        "targetStructure": _TARGET_STRUCTURE,
    }
    preserved_fields = _outer_content_values(model_content)
    if preserved_fields:
        repair_input["preservedTopLevelFields"] = preserved_fields
    if previous_output:
        repair_input["previousOutput"] = previous_output
    if validation_errors:
        repair_input["validationErrors"] = validation_errors
    if preserved is not None:
        repair_input["lockedFields"] = preserved.fields
        repair_input["lockedArrayItems"] = preserved.items
        repair_input["requiredRepairFields"] = preserved.required_fields
    try:
        DECODER.decode(raw_arguments)
    except ValueError:
        try:
            repair_input["syntaxRepairSuggestion"] = DECODER.decode(repair_syntax(raw_arguments))
        except ValueError as exc:
            repair_input["syntaxRepairWarning"] = str(exc)
    system_prompt = A2UIProtocolRegistry.read_design_argument_repair_prompt(
        DESIGN_COMPACT_PROFILE_ID
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(repair_input, ensure_ascii=False)},
    ]


def _normalize_model_output(
    raw_output: str,
    outer_content: dict[str, Any],
    payload: dict[str, Any],
    registry: CapabilityRegistry | None,
    *,
    preserved: PreservedArguments | None = None,
) -> tuple[dict[str, Any], list[str], list[str]]:
    repaired = _strict_json_object(
        raw_output, allow_empty=preserved is not None and bool(preserved.fields)
    )
    if preserved is not None:
        try:
            repaired = preserved.merge(repaired)
        except ValueError as exc:
            raise CompactDslArgumentRepairError(str(exc)) from exc
        if preserved.raw is not None:
            original = _strict_json_object(preserved.raw)
            original = _merge_outer_business(original, outer_content)
            _check_recovery_fields(original)
            original, _dropped, _warnings = _canonicalize_candidates(original, registry)
            # 模型只能恢复结构；完整原始字段在规范化前逐项保持，含损坏字段后方的内容。
            original_request = _validate_generation_content(original, payload)
            expected = _normalized_business_content(original, original_request)
            _preserve_outer_content_values(expected, outer_content)
            actual = _merge_outer_business(repaired, outer_content)
            actual, _dropped, _warnings = _canonicalize_candidates(actual, registry)
            actual_request = _validate_generation_content(actual, payload)
            actual = _normalized_business_content(actual, actual_request)
            _preserve_outer_content_values(actual, outer_content)
            if not _same_values(expected, actual):
                raise CompactDslArgumentRepairError("repair changed original fields or values")
    repaired = _merge_outer_business(repaired, outer_content)
    _check_recovery_fields(repaired)
    dropped: list[str] = []
    warnings: list[str] = []
    repaired, dropped, warnings = _canonicalize_candidates(repaired, registry)
    request = _validate_generation_content(repaired, payload)
    if registry is not None and "sourceArtifactUrl" not in request.model_fields_set:
        preflight_request = EditRequestNormalizer.normalize_create(request)
        preflight = GenerationPreflight(registry).run(preflight_request)
        if preflight.blocking_issues:
            issue = preflight.blocking_issues[0]
            raise CompactDslArgumentRepairError(
                f"preflight rejected {issue.path}: {issue.code}",
                feedback=GenerationPreflightError(preflight).details(),
            )
    normalized = _normalized_business_content(repaired, request)
    _preserve_outer_content_values(normalized, outer_content)
    if not normalized:
        raise CompactDslArgumentRepairError("repaired content must not be empty")
    if preserved is not None:
        try:
            preserved.assert_retained(normalized)
        except ValueError as exc:
            raise CompactDslArgumentRepairError(str(exc)) from exc
    return normalized, dropped, warnings


def _check_recovery_fields(content: dict[str, Any]) -> None:
    forbidden = sorted(set(content) & _WRAPPER_KEYS)
    if forbidden:
        raise CompactDslArgumentRepairError(
            "model output contains wrapper fields: " + ", ".join(forbidden)
        )
    allowed_fields = _BUSINESS_KEYS | {"bundleName", "romVersion"}
    unknown_fields = sorted(set(content) - allowed_fields)
    if unknown_fields:
        raise CompactDslArgumentRepairError(
            "model output contains unknown fields: " + ", ".join(unknown_fields)
        )


def _strict_json_object(raw_output: str, *, allow_empty: bool = False) -> dict[str, Any]:
    candidate = _strip_json_fence(raw_output)
    if len(candidate) > _MAX_ARGUMENT_CHARS:
        raise CompactDslArgumentRepairError("arguments exceed recovery size limit")
    try:
        loaded = DECODER.decode(candidate)
    except json.JSONDecodeError as exc:
        try:
            repaired = repair_syntax(candidate)
            loaded = DECODER.decode(repaired)
        except ValueError as repair_exc:
            raise CompactDslArgumentRepairError(
                f"model output is invalid JSON at line {exc.lineno} column {exc.colno}; "
                f"syntax repair rejected: {repair_exc}"
            ) from repair_exc
        logger.info(f"{_MODULE} syntax_repaired output={json_text_for_log(repaired)}")
    except ValueError as exc:
        raise CompactDslArgumentRepairError(str(exc)) from exc
    except RecursionError as exc:
        raise CompactDslArgumentRepairError("arguments exceed recovery depth limit") from exc
    if not isinstance(loaded, dict):
        raise CompactDslArgumentRepairError("model output root must be a JSON object")
    if not loaded and not allow_empty:
        raise CompactDslArgumentRepairError("model output object must not be empty")
    validate_recovery_depth(loaded)
    return loaded


def _strip_json_fence(value: str) -> str:
    stripped = value.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    valid_opening = lines and lines[0].strip().lower() in {"```", "```json"}
    valid_closing = len(lines) >= 3 and lines[-1].strip() == "```"
    if not valid_opening or not valid_closing:
        raise CompactDslArgumentRepairError("model output contains an incomplete JSON fence")
    return "\n".join(lines[1:-1]).strip()


def _select_capability_registry(
    payload: dict[str, Any],
    content: dict[str, Any],
) -> tuple[CapabilityRegistry | None, list[str]]:
    settings = get_settings()
    device_info = payload.get("deviceInfo")
    device_values = device_info if isinstance(device_info, dict) else {}
    app_version = device_values.get("prdVer") or settings.default_prd_version
    rom_version = content.get("romVersion") or device_values.get("romVersion")
    rom_version = rom_version or settings.default_device_rom_version
    try:
        return CapabilityRegistry(
            app_version=str(app_version),
            device_rom_version=str(rom_version),
        ), []
    except ValueError as exc:
        if not settings.enable_default_capability_registry_fallback:
            return None, [f"能力清单未命中，保留候选交由生成流程裁决：{exc}"]
        try:
            registry = CapabilityRegistry(version=settings.capability_registry_version)
        except ValueError as fallback_exc:
            warning = f"默认能力清单不可用，保留候选交由生成流程裁决：{fallback_exc}"
            return None, [warning]
        return registry, [f"能力清单未命中，参数恢复使用默认清单：{registry.version}"]


def _canonicalize_candidates(
    content: dict[str, Any],
    registry: CapabilityRegistry | None,
) -> tuple[dict[str, Any], list[str], list[str]]:
    normalized = copy.deepcopy(content)
    dropped: list[str] = []
    warnings: list[str] = []
    _decode_object_fields(normalized)
    if registry is not None:
        _rebuild_event_candidates(normalized, registry, dropped, warnings)
    return normalized, dropped, warnings


def _rebuild_event_candidates(
    content: dict[str, Any],
    registry: CapabilityRegistry,
    dropped: list[str],
    warnings: list[str],
) -> None:
    candidates = content.get("candidateEventCandidates")
    if not isinstance(candidates, list):
        return
    rebuilt = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            rebuilt.append(candidate)
            continue
        capability_id = candidate.get("capabilityId")
        if not isinstance(capability_id, str):
            rebuilt.append(candidate)
            continue
        capability = registry.get_event_capability(capability_id)
        if capability is None:
            rebuilt.append(candidate)
            continue
        unknown = set(candidate) - {"capabilityId", "action", "dynamicArguments"}
        if unknown:
            raise CompactDslArgumentRepairError(f"unknown event fields: {sorted(unknown)}")
        action = candidate.get("action")
        if action is not None and not isinstance(action, dict):
            raise CompactDslArgumentRepairError("action must be an object")
        if action is None and not isinstance(candidate.get("dynamicArguments"), dict):
            raise CompactDslArgumentRepairError("event is missing its original action")
        source_action = action if isinstance(action, dict) else {}
        if "dynamicArguments" in candidate:
            source_action = dict(source_action)
            source_action.setdefault("dynamicArguments", candidate.get("dynamicArguments"))
        template = capability.actionTemplate.model_dump(mode="json")
        template_args = template.get("args")
        if not isinstance(template_args, dict):
            raise CompactDslArgumentRepairError("event action template args must be an object")
        _validate_source_action(source_action, template, capability_id, capability.dynamicArguments)
        for dynamic_argument in capability.dynamicArguments:
            _copy_dynamic_argument(
                source_action,
                template_args,
                dynamic_argument,
                capability_id,
                warnings,
            )
        rebuilt.append({"capabilityId": capability_id, "action": template})
    content["candidateEventCandidates"] = rebuilt


def _validate_source_action(
    action: dict[str, Any], template: dict[str, Any], capability_id: str,
    dynamic_arguments: list[EventDynamicArgument],
) -> None:
    unknown = set(action) - {"call", "args", "dynamicArguments"}
    if unknown:
        raise CompactDslArgumentRepairError(f"unknown action fields: {sorted(unknown)}")
    call = action.get("call", _MISSING)
    if call is not _MISSING and call not in (template.get("call"), capability_id):
        raise CompactDslArgumentRepairError("event call conflicts with registered template")
    paths = {argument.path for argument in dynamic_arguments}
    args = action.get("args", {})
    if not isinstance(args, dict):
        raise CompactDslArgumentRepairError("action.args must be an object")
    _validate_action_values(args, template.get("args"), paths, "")
    metadata = action.get("dynamicArguments")
    if isinstance(metadata, dict) and set(metadata) - paths:
        raise CompactDslArgumentRepairError("unknown legacy dynamic paths")
    if metadata is not None and not isinstance(metadata, (dict, list)):
        raise CompactDslArgumentRepairError("invalid dynamic argument metadata")
    if isinstance(metadata, list):
        for item in metadata:
            if not isinstance(item, dict):
                raise CompactDslArgumentRepairError("invalid dynamic argument metadata")
            if set(item) - {"path", "type", "description", "enum"}:
                raise CompactDslArgumentRepairError("unknown dynamic argument metadata fields")
            matches = []
            for argument in dynamic_arguments:
                if argument.path == item.get("path"):
                    matches.append(argument)
            if len(matches) != 1 or item.get("type") != matches[0].type:
                raise CompactDslArgumentRepairError("dynamic argument metadata mismatch")
            if "enum" in item and item.get("enum") != matches[0].enum:
                raise CompactDslArgumentRepairError("dynamic argument enum mismatch")
    if call == template.get("call") and not _has_legacy_dynamic_values(args, action):
        _require_action_fields(args, template.get("args"), "")


def _has_legacy_dynamic_values(args: dict[str, Any], action: dict[str, Any]) -> bool:
    if isinstance(action.get("dynamicArguments"), dict):
        return True
    if isinstance(args.get("dynamicArguments"), dict):
        return True
    return any(name.startswith("/") for name in args)


def _require_action_fields(actual: Any, template: Any, path: str) -> None:
    if not isinstance(template, dict):
        return
    if not isinstance(actual, dict):
        raise CompactDslArgumentRepairError(f"missing action object: {path}")
    for name, value in template.items():
        if name not in actual:
            raise CompactDslArgumentRepairError(f"missing action field: {path}/{name}")
        _require_action_fields(actual.get(name), value, f"{path}/{name}")


def _validate_action_values(
    actual: Any, template: Any, dynamic_paths: set[str], path: str,
) -> None:
    if path in dynamic_paths:
        return
    if isinstance(actual, dict):
        if not isinstance(template, dict):
            raise CompactDslArgumentRepairError(f"action structure mismatch: {path}")
        for name, value in actual.items():
            if name == "dynamicArguments" and isinstance(value, dict):
                if set(value) - dynamic_paths:
                    raise CompactDslArgumentRepairError("unknown legacy dynamic paths")
                continue
            if name in dynamic_paths:
                continue
            if name not in template:
                raise CompactDslArgumentRepairError(f"unknown action argument: {path}/{name}")
            pointer_name = name.replace("~", "~0").replace("/", "~1")
            _validate_action_values(
                value, template.get(name), dynamic_paths, f"{path}/{pointer_name}",
            )
        return
    if not _same_values(actual, template):
        raise CompactDslArgumentRepairError(f"fixed action value mismatch: {path}")


def _copy_dynamic_argument(
    source_action: dict[str, Any],
    template_args: dict[str, Any],
    dynamic_argument: EventDynamicArgument,
    capability_id: str,
    warnings: list[str],
) -> None:
    parts = parse_json_pointer(dynamic_argument.path)
    if parts is None:
        return
    source_args = source_action.get("args")
    sources = [source_args, source_action]
    value: Any = _MISSING
    for source in sources:
        if not isinstance(source, dict):
            continue
        candidate_value = _read_dynamic_argument(source, parts, dynamic_argument.path)
        if candidate_value is _MISSING:
            continue
        candidate_value = _restore_binding_expression(
            candidate_value, _read_path(template_args, parts),
        )
        if value is not _MISSING and not _same_values(value, candidate_value):
            raise CompactDslArgumentRepairError("conflicting dynamic argument values")
        value = candidate_value
    template_value = _read_path(template_args, parts)
    if value is _MISSING:
        _reject_unresolved_array_argument(template_value, capability_id, dynamic_argument.path)
        raise CompactDslArgumentRepairError(
            f"missing dynamic argument: {capability_id}{dynamic_argument.path}"
        )
    value = _restore_binding_expression(value, template_value)
    _reject_unresolved_array_argument(value, capability_id, dynamic_argument.path)
    if not _dynamic_value_is_valid(value, dynamic_argument):
        _reject_unresolved_array_argument(template_value, capability_id, dynamic_argument.path)
        raise CompactDslArgumentRepairError(
            f"invalid dynamic argument: {capability_id}{dynamic_argument.path}"
        )
    _write_existing_path(template_args, parts, value)


def _read_dynamic_argument(source: dict[str, Any], parts: tuple[str, ...], path: str) -> Any:
    """仅恢复已声明路径，优先沿用正式嵌套参数，再读取旧格式。"""
    value: Any = _read_path(source, parts)
    legacy = source.get("dynamicArguments")
    legacy_value: Any = _MISSING
    if isinstance(legacy, dict):
        legacy_value = legacy.get(path, _MISSING)
    for candidate in (source.get(path, _MISSING), legacy_value):
        if candidate is _MISSING:
            continue
        if value is not _MISSING and not _same_values(value, candidate):
            raise CompactDslArgumentRepairError("conflicting legacy dynamic argument values")
        value = candidate
    return value


def _restore_binding_expression(value: Any, template_value: Any) -> Any:
    restored: Any = value
    if not isinstance(value, str) or not isinstance(template_value, str):
        return restored
    match = re.fullmatch(r"\s*\{\{\s*\$\{([^{}]+)\}\s*\}\}\s*", template_value)
    if match is not None and value.startswith("/data/"):
        if GenerationPreflight._event_reference_matches(value, match.group(1)):
            restored = "{{ ${" + value + "} }}"
    return restored


def _reject_unresolved_array_argument(value: Any, capability_id: str, path: str) -> None:
    if not isinstance(value, str):
        return
    references = expression_references(value)
    if value.startswith("/data/"):
        references.append(value)
    for reference in references:
        if not GenerationPreflight._event_reference_matches(reference, reference):
            raise CompactDslArgumentRepairError(
                f"事件 {capability_id} 的动态参数 {path} 尚未指定实际数组下标，"
                "不能保留模板占位符 i。"
            )


def _read_path(source: Any, parts: tuple[str, ...]) -> Any:
    current = source
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        if isinstance(current, list) and part.isdigit():
            index = int(part)
            if index < len(current):
                current = current[index]
                continue
        return _MISSING
    return current


def _write_existing_path(target: Any, parts: tuple[str, ...], value: Any) -> None:
    if not parts:
        return
    parent = _read_path(target, parts[:-1]) if len(parts) > 1 else target
    final = parts[-1]
    if isinstance(parent, dict) and final in parent:
        parent[final] = copy.deepcopy(value)
        return
    if isinstance(parent, list) and final.isdigit():
        index = int(final)
        if index < len(parent):
            parent[index] = copy.deepcopy(value)


def _dynamic_value_is_valid(value: Any, argument: EventDynamicArgument) -> bool:
    expected = argument.type
    if expected == "string":
        type_matches = isinstance(value, str)
    elif expected == "integer":
        type_matches = isinstance(value, int) and not isinstance(value, bool)
    elif expected == "number":
        type_matches = isinstance(value, (int, float)) and not isinstance(value, bool)
    elif expected == "boolean":
        type_matches = isinstance(value, bool)
    elif expected == "object":
        type_matches = isinstance(value, dict)
    elif expected == "array":
        type_matches = isinstance(value, list)
    else:
        type_matches = value is None if expected == "null" else False
    if not type_matches:
        return False
    return argument.enum is None or value in argument.enum


def _validate_generation_content(
    content: dict[str, Any],
    payload: dict[str, Any],
) -> GenerateWidgetCardRequest:
    device_info = payload.get("deviceInfo")
    device_values = device_info if isinstance(device_info, dict) else {}
    rom_version = content.get("romVersion") or device_values.get("romVersion") or "0"
    business_content = {
        key: value for key, value in content.items() if key in _BUSINESS_KEYS
    }
    try:
        return GenerateWidgetCardRequest.model_validate(
            {
                "uid": "argument-repair-validation",
                "locale": str(device_values.get("locale") or "zh-CN"),
                "prdVer": str(device_values.get("prdVer") or "0"),
                "device": {
                    "romVersion": CapabilityRegistry.normalize_rom_version(str(rom_version)),
                },
                **business_content,
            },
            strict=True,
        )
    except ValidationError as exc:
        errors = []
        for item in exc.errors(include_context=False, include_input=False):
            location = "/" + "/".join(str(part) for part in item.get("loc", ()))
            errors.append(f"{location}: {item.get('msg', 'invalid value')}")
        raise CompactDslArgumentRepairError(
            "; ".join(errors),
            feedback=request_validation_feedback(
                exc, "generateWidgetCardCompactDsl", arguments=business_content,
            ),
        ) from exc


def _normalized_business_content(
    source: dict[str, Any],
    request: GenerateWidgetCardRequest,
) -> dict[str, Any]:
    request_values = request.model_dump(mode="json", exclude_none=True)
    normalized = {}
    for key in _BUSINESS_KEYS:
        if key not in source:
            continue
        if source.get(key) is None:
            normalized[key] = None
        elif key in request_values:
            normalized[key] = request_values.get(key)
    bundle_name = source.get("bundleName")
    if isinstance(bundle_name, str) and bundle_name.strip():
        normalized["bundleName"] = bundle_name
    rom_version = source.get("romVersion")
    if isinstance(rom_version, str) and rom_version.strip():
        normalized["romVersion"] = rom_version
    return normalized


def _preserve_valid_fragments(
    raw: str,
    registry: CapabilityRegistry | None,
) -> PreservedArguments:
    fragments = extract_fragments(raw)
    preserved = PreservedArguments(required_fields=list(fragments.damaged_fields), raw=raw)
    text_fields = {
        "userQuery", "title", "description", "sourceArtifactUrl", "bundleName", "romVersion"
    }
    for name, value in fragments.fields.items():
        if name in text_fields and isinstance(value, str) and value.strip():
            preserved.fields[name] = value
        elif name == "size" and value in ("2x2", "2x4"):
            preserved.fields[name] = value
    for name in ("candidateDataBindings", "candidateAssetIds"):
        values = fragments.fields.get(name, fragments.array_prefixes.get(name))
        if not isinstance(values, list):
            continue
        locked: dict[int, Any] = {}
        for index, value in enumerate(values):
            if _fragment_is_valid(name, value, registry):
                locked[index] = value
        complete = name in fragments.fields and len(locked) == len(values)
        if complete:
            preserved.fields[name] = values
        elif locked:
            preserved.items[name] = locked
        if not complete and name not in preserved.required_fields:
            preserved.required_fields.append(name)
    options = fragments.fields.get("options")
    if isinstance(options, dict):
        try:
            GenerationOptions.model_validate(options, strict=True)
        except ValidationError as exc:
            logger.info(f"{_MODULE} options_require_repair error_count={exc.error_count()}")
        else:
            preserved.fields["options"] = options
    for name, value in fragments.fields.items():
        if name not in _BUSINESS_KEYS or name in preserved.fields:
            continue
        if name == "candidateEventCandidates" and value == []:
            preserved.fields[name] = []
        elif name not in preserved.required_fields:
            preserved.required_fields.append(name)
    logger.info(
        f"{_MODULE} fragments_preserved fields={json_for_log(preserved.fields)} "
        f"items={json_for_log(preserved.items)} "
        f"required_repair_fields={json_for_log(preserved.required_fields)}"
    )
    return preserved


def _fragment_is_valid(
    name: str,
    value: Any,
    registry: CapabilityRegistry | None,
) -> bool:
    if registry is None:
        return False
    if name == "candidateAssetIds":
        return isinstance(value, str) and registry.get_asset_capability(value) is not None
    try:
        binding = CandidateDataBinding.model_validate(value, strict=True)
    except ValidationError:
        return False
    capability = registry.get_data_capability(binding.capabilityId)
    if capability is None:
        return False
    # 此对象仅供独立候选预检，绝不作为恢复结果或生成请求下发。
    probe = GenerateWidgetCardRequest(
        uid="argument-repair-validation",
        locale="zh-CN",
        prdVer="0",
        device={"romVersion": "0"},
        userQuery="参数恢复校验",
        title="参数恢复校验",
        description="参数恢复校验",
        size="2x2",
        candidateDataBindings=[binding],
    )
    preflight = GenerationPreflight(registry).run(EditRequestNormalizer.normalize_create(probe))
    return not preflight.blocking_issues


def _repair_error_messages(exc: Exception) -> list[str]:
    if isinstance(exc, CompactDslArgumentRepairError):
        return [str(exc)]
    return [f"model call failed: {type(exc).__name__}"]


def _outer_content_values(source: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in source.items() if key in _PRESERVED_OUTER_KEYS}


def _preserve_outer_content_values(
    target: dict[str, Any],
    source: dict[str, Any],
) -> None:
    target.update(_outer_content_values(source))


def _log_recovery_result(result: CompactDslArgumentRecoveryResult) -> None:
    logger.info(
        f"{_MODULE} recovery_completed mode={result.mode} attempts={result.attempts} "
        f"raw_arguments_hash={result.raw_arguments_hash} "
        f"dropped_candidates={json_for_log(result.dropped_candidates)} "
        f"warning_count={len(result.warnings)} "
        f"warnings={json_for_log(result.warnings)} "
        f"content={json_for_log(result.content)}"
    )
