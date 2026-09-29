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
from services.argument_json_recovery import (
    DECODER,
    PreservedArguments,
    extract_fragments,
    repair_syntax,
)
from services.capability_registry import CapabilityRegistry
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
        "extrainfo",
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
    "extrainfo": ["non-empty string, optional"],
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
_CANDIDATE_PATH = re.compile(
    r"^/(candidateDataBindings|candidateEventCandidates|candidateAssetIds)/(\d+)(?:/|$)"
)
_MISSING = object()


class CompactDslArgumentRepairError(ValueError):
    """表示模型候选无法作为生成请求的 content 使用。"""


class CompactDslArgumentRepairExhaustedError(ValueError):
    """参数恢复失败是本轮生成的终态，不再让 Agent 自动改参循环。"""

    error_code = ErrorCode.A2UI_GENERATION_FAILED

    def details(self) -> dict[str, Any]:
        return {
            "stage": "argumentRepair",
            "retryable": False,
            "requiredActions": ["NOTIFY_USER"],
            "agentInstruction": (
                "本次 DSL 生成失败：参数修复及重试均未成功，未生成卡片结果。"
                "请停止本轮自动调用，并提示用户：卡片生成失败，请重试一下。"
            ),
        }


@dataclass(frozen=True)
class CompactDslArgumentRecoveryResult:
    """参数恢复模块返回给路由的完整结果。"""

    content: dict[str, Any]
    mode: Literal["model", "model_retry"]
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

    normalized_attempts = min(max(max_attempts, 1), 3)
    raw_hash = hashlib.sha256(raw_arguments.encode("utf-8")).hexdigest()
    registry, registry_warnings = _select_capability_registry(payload, content)
    preserved = _preserve_valid_fragments(raw_arguments, registry)
    for key in ("bundleName", "romVersion"):
        if key in content:
            preserved.fields[key] = content.get(key)
    previous_output = ""
    validation_errors: list[str] = []
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
                logger.warning(
                    f"{_MODULE} model_candidate_rejected attempt={attempt} "
                    f"exception_type={type(exc).__name__} "
                    f"errors={json_for_log(validation_errors)}"
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
        f"raw_arguments_hash={raw_hash} errors={json_for_log(validation_errors)}"
    )
    raise CompactDslArgumentRepairExhaustedError("卡片生成失败，请重试一下。")


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
    forbidden = sorted(set(repaired) & _WRAPPER_KEYS)
    if forbidden:
        raise CompactDslArgumentRepairError(
            "model output contains wrapper fields: " + ", ".join(forbidden)
        )
    allowed_fields = _BUSINESS_KEYS | {"bundleName", "romVersion"}
    unknown_fields = sorted(set(repaired) - allowed_fields)
    if unknown_fields:
        raise CompactDslArgumentRepairError(
            "model output contains unknown fields: " + ", ".join(unknown_fields)
        )
    dropped: list[str] = []
    warnings: list[str] = []
    if registry is not None:
        repaired, dropped, warnings = _canonicalize_candidates(repaired, registry)
    request = _validate_generation_content(repaired, payload)
    if registry is not None and "sourceArtifactUrl" not in request.model_fields_set:
        repaired, request, preflight_dropped = _remove_blocking_candidates(
            repaired,
            request,
            registry,
            payload,
        )
        dropped.extend(preflight_dropped)
    normalized = _normalized_business_content(repaired, request)
    _preserve_outer_content_values(normalized, outer_content)
    if not normalized:
        raise CompactDslArgumentRepairError("repaired content must not be empty")
    candidate_fields = ("candidateDataBindings", "candidateEventCandidates", "candidateAssetIds")
    if dropped and not any(normalized.get(name) for name in candidate_fields):
        raise CompactDslArgumentRepairError("no usable candidates remain after repair validation")
    if preserved is not None:
        try:
            preserved.assert_retained(normalized)
        except ValueError as exc:
            raise CompactDslArgumentRepairError(str(exc)) from exc
    return normalized, dropped, warnings


def _strict_json_object(raw_output: str, *, allow_empty: bool = False) -> dict[str, Any]:
    candidate = _strip_json_fence(raw_output)
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
    if not isinstance(loaded, dict):
        raise CompactDslArgumentRepairError("model output root must be a JSON object")
    if not loaded and not allow_empty:
        raise CompactDslArgumentRepairError("model output object must not be empty")
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
    registry: CapabilityRegistry,
) -> tuple[dict[str, Any], list[str], list[str]]:
    normalized = dict(content)
    dropped: list[str] = []
    warnings: list[str] = []
    _filter_registered_data_candidates(normalized, registry, dropped)
    _filter_registered_assets(normalized, registry, dropped)
    _rebuild_event_candidates(normalized, registry, dropped, warnings)
    return normalized, dropped, warnings


def _filter_registered_data_candidates(
    content: dict[str, Any],
    registry: CapabilityRegistry,
    dropped: list[str],
) -> None:
    candidates = content.get("candidateDataBindings")
    if not isinstance(candidates, list):
        return
    filtered = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            filtered.append(candidate)
            continue
        capability_id = candidate.get("capabilityId")
        if not isinstance(capability_id, str):
            filtered.append(candidate)
            continue
        if registry.get_data_capability(capability_id) is None:
            dropped.append(f"candidateDataBindings:{capability_id}")
            continue
        filtered.append(candidate)
    content["candidateDataBindings"] = filtered


def _filter_registered_assets(
    content: dict[str, Any],
    registry: CapabilityRegistry,
    dropped: list[str],
) -> None:
    asset_ids = content.get("candidateAssetIds")
    if not isinstance(asset_ids, list):
        return
    filtered = []
    for asset_id in asset_ids:
        if not isinstance(asset_id, str):
            filtered.append(asset_id)
            continue
        if registry.get_asset_capability(asset_id) is None:
            dropped.append(f"candidateAssetIds:{asset_id}")
            continue
        filtered.append(asset_id)
    content["candidateAssetIds"] = filtered


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
            dropped.append(f"candidateEventCandidates:{capability_id}")
            continue
        action = candidate.get("action")
        source_action = action if isinstance(action, dict) else {}
        template = capability.actionTemplate.model_dump(mode="json")
        template_args = template.get("args")
        if not isinstance(template_args, dict):
            raise CompactDslArgumentRepairError("event action template args must be an object")
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
    value = _MISSING
    for source in sources:
        if not isinstance(source, dict):
            continue
        value = _read_path(source, parts)
        if value is not _MISSING:
            break
    if value is _MISSING:
        return
    if not _dynamic_value_is_valid(value, dynamic_argument):
        warnings.append(
            f"事件 {capability_id} 的动态参数 {dynamic_argument.path} 类型或取值非法，"
            "已保留能力清单默认值。"
        )
        return
    _write_existing_path(template_args, parts, value)


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
        return GenerateWidgetCardRequest(
            uid="argument-repair-validation",
            locale=str(device_values.get("locale") or "zh-CN"),
            prdVer=str(device_values.get("prdVer") or "0"),
            device={
                "romVersion": CapabilityRegistry.normalize_rom_version(str(rom_version)),
            },
            **business_content,
        )
    except ValidationError as exc:
        errors = []
        for item in exc.errors(include_context=False, include_input=False):
            location = "/" + "/".join(str(part) for part in item.get("loc", ()))
            errors.append(f"{location}: {item.get('msg', 'invalid value')}")
        raise CompactDslArgumentRepairError("; ".join(errors)) from exc


def _remove_blocking_candidates(
    content: dict[str, Any],
    request: GenerateWidgetCardRequest,
    registry: CapabilityRegistry,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], GenerateWidgetCardRequest, list[str]]:
    normalized_content = dict(content)
    dropped: list[str] = []
    for _iteration in range(4):
        preflight_request = EditRequestNormalizer.normalize_create(request)
        preflight = GenerationPreflight(registry).run(preflight_request)
        if not preflight.blocking_issues:
            return normalized_content, request, dropped
        removals: dict[str, set[int]] = {}
        for issue in preflight.blocking_issues:
            match = _CANDIDATE_PATH.match(issue.path)
            if match is None:
                raise CompactDslArgumentRepairError(
                    f"preflight rejected repaired content at {issue.path}: {issue.code}"
                )
            removals.setdefault(match.group(1), set()).add(int(match.group(2)))
        if not _drop_candidate_indexes(normalized_content, removals, dropped):
            raise CompactDslArgumentRepairError(
                "preflight rejected repaired content without removable candidates"
            )
        request = _validate_generation_content(normalized_content, payload)
    raise CompactDslArgumentRepairError("repaired content did not pass generation preflight")


def _drop_candidate_indexes(
    content: dict[str, Any],
    removals: dict[str, set[int]],
    dropped: list[str],
) -> bool:
    changed = False
    for field_name, indexes in removals.items():
        candidates = content.get(field_name)
        if not isinstance(candidates, list):
            continue
        for index in sorted(indexes, reverse=True):
            if index >= len(candidates):
                continue
            candidate = candidates.pop(index)
            dropped.append(f"{field_name}:{_candidate_label(candidate)}")
            changed = True
    return changed


def _candidate_label(candidate: Any) -> str:
    if isinstance(candidate, str):
        return candidate
    if isinstance(candidate, dict):
        value = candidate.get("capabilityId")
        if isinstance(value, str):
            return value
    return "invalid"


def _normalized_business_content(
    source: dict[str, Any],
    request: GenerateWidgetCardRequest,
) -> dict[str, Any]:
    request_values = request.model_dump(mode="json", exclude_none=True)
    normalized = {}
    for key in _BUSINESS_KEYS:
        if key in source and key in request_values:
            normalized[key] = request_values[key]
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
    preserved = PreservedArguments(required_fields=list(fragments.damaged_fields))
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
