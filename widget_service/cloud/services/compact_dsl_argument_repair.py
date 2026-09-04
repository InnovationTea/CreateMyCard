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
from app.logger import json_for_log, logger
from config.config import get_settings
from core.json_pointer import parse_json_pointer
from custom.a2ui_model_client import A2UIModelClient
from custom.model_runtime import ModelExecutionRuntime
from custom.model_transport import ModelBackend
from models.capability import EventDynamicArgument
from models.generation import ModelRequestContext
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
_CANDIDATE_PATH = re.compile(
    r"^/(candidateDataBindings|candidateEventCandidates|candidateAssetIds)/(\d+)(?:/|$)"
)
_MISSING = object()


class CompactDslArgumentRepairError(ValueError):
    """表示模型候选无法作为生成请求的 content 使用。"""


@dataclass(frozen=True)
class CompactDslArgumentRecoveryResult:
    """参数恢复模块返回给路由的完整结果。"""

    content: dict[str, Any]
    mode: Literal["model", "model_retry", "minimal"]
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
            )
            raw_output = ""
            try:
                raw_output = await client.generate(
                    prompt,
                    _RAW_JSON_PROFILE,
                    suppress_prompt_log=True,
                    phase="argument_repair",
                )
                repaired_content, dropped, warnings = _normalize_model_output(
                    raw_output,
                    content,
                    payload,
                    registry,
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

    minimal_content = _build_minimal_content(raw_arguments, content)
    warnings = [*registry_warnings, *validation_errors]
    warnings.append("模型未返回合法请求，已使用最小静态请求继续生成。")
    result = CompactDslArgumentRecoveryResult(
        content=minimal_content,
        mode="minimal",
        attempts=normalized_attempts,
        dropped_candidates=("dynamicCandidates:*",),
        warnings=tuple(warnings),
        raw_arguments_hash=raw_hash,
    )
    _log_recovery_result(result)
    return result


def _build_repair_prompt(
    content: dict[str, Any],
    *,
    previous_output: str = "",
    validation_errors: list[str] | None = None,
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
) -> tuple[dict[str, Any], list[str], list[str]]:
    repaired = _strict_json_object(raw_output)
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
    return normalized, dropped, warnings


def _strict_json_object(raw_output: str) -> dict[str, Any]:
    candidate = _strip_json_fence(raw_output)
    try:
        loaded = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise CompactDslArgumentRepairError(
            f"model output is invalid JSON at line {exc.lineno} column {exc.colno}"
        ) from exc
    if not isinstance(loaded, dict):
        raise CompactDslArgumentRepairError("model output root must be a JSON object")
    if not loaded:
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


def _build_minimal_content(
    raw_arguments: str,
    outer_content: dict[str, Any],
) -> dict[str, Any]:
    source_url = _extract_json_value(raw_arguments, "sourceArtifactUrl")
    user_query = _first_non_empty_extracted_text(
        raw_arguments,
        "userQuery",
        "description",
        "title",
    )
    user_query = user_query or "根据用户请求生成卡片"
    minimal: dict[str, Any] = {"userQuery": user_query}
    if isinstance(source_url, str) and source_url.strip():
        minimal["sourceArtifactUrl"] = source_url
        minimal["options"] = {"allowDegradation": True}
    else:
        title = _extract_json_value(raw_arguments, "title")
        description = _extract_json_value(raw_arguments, "description")
        minimal.update(
            {
                "size": _extracted_size(raw_arguments),
                "title": title if isinstance(title, str) and title.strip() else "智能卡片",
                "description": (
                    description
                    if isinstance(description, str) and description.strip()
                    else user_query
                ),
                "candidateDataBindings": [],
                "candidateEventCandidates": [],
                "candidateAssetIds": [],
                "options": {"allowDegradation": True},
            }
        )
    for key in ("bundleName", "romVersion"):
        value = _extract_json_value(raw_arguments, key)
        if isinstance(value, str) and value.strip():
            minimal[key] = value
    _preserve_outer_content_values(minimal, outer_content)
    return minimal


def _extract_json_value(raw_arguments: str, key: str) -> Any:
    pattern = re.compile(rf'(?<!\\)"{re.escape(key)}"\s*:')
    decoder = json.JSONDecoder()
    matches = list(pattern.finditer(raw_arguments))
    for match in reversed(matches):
        value_start = match.end()
        while value_start < len(raw_arguments) and raw_arguments[value_start].isspace():
            value_start += 1
        try:
            value, _end = decoder.raw_decode(raw_arguments, value_start)
        except json.JSONDecodeError:
            continue
        return value
    return None


def _first_non_empty_extracted_text(raw_arguments: str, *keys: str) -> str:
    for key in keys:
        value = _extract_json_value(raw_arguments, key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _extracted_size(raw_arguments: str) -> str:
    size = _extract_json_value(raw_arguments, "size")
    return size if size in {"2x2", "2x4"} else "2x2"


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
        f"content_keys={json_for_log(sorted(result.content))}"
    )
