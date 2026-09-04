# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import json
import threading
from collections import OrderedDict
from typing import Any

import json_repair

from app.logger import json_for_log, logger
from custom.a2ui_model_client import A2UIModelClient
from custom.model_runtime import ModelExecutionRuntime
from custom.model_transport import ModelBackend
from models.generation import ModelRequestContext
from services.protocol_registry import DESIGN_COMPACT_PROFILE_ID, A2UIProtocolRegistry

_MODULE = "[Compact DSL Argument Repair]"
_RAW_JSON_PROFILE = {
    "id": "compact-dsl-argument-repair",
    "format": "raw-json",
}
_WRAPPER_KEYS = frozenset({"arguments", "content", "functionName", "skillName"})
_PROTECTED_TRANSPORT_KEYS = frozenset({"odid", "uid"})


class CompactDslArgumentRepairError(ValueError):
    """表示模型未能返回可作为 content 使用的 JSON 对象。"""


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


async def repair_compact_dsl_content(
    payload: dict[str, Any],
    *,
    backend: ModelBackend,
    model_runtime: ModelExecutionRuntime | None,
    request_context: ModelRequestContext,
) -> dict[str, Any]:
    """使用 A2UI client 把字符串化工具参数恢复为标准 content 对象。"""
    content = payload.get("content")
    if not isinstance(content, dict):
        raise CompactDslArgumentRepairError("content must be an object")
    prompt = _build_repair_prompt(content)
    client = A2UIModelClient(
        use_mock=False,
        backend=backend,
        runtime=model_runtime,
        request_context=request_context,
        operation_name="generateWidgetCardCompactDsl.argumentRepair",
    )
    try:
        raw_output = await client.generate(
            prompt,
            _RAW_JSON_PROFILE,
            suppress_prompt_log=True,
            phase="argument_repair",
        )
    finally:
        await client.aclose()
    repaired_content = _parse_repaired_content(raw_output)
    _preserve_outer_content_values(repaired_content, content)
    logger.info(f"{_MODULE} repair_completed content_keys={json_for_log(sorted(repaired_content))}")
    return repaired_content


def _build_repair_prompt(content: dict[str, Any]) -> list[dict[str, str]]:
    model_content = {
        key: value for key, value in content.items() if key not in _PROTECTED_TRANSPORT_KEYS
    }
    invalid_arguments = model_content.get("arguments")
    if not isinstance(invalid_arguments, str):
        raise CompactDslArgumentRepairError("content.arguments must be a string")
    preserved_outer_content = _outer_content_values(model_content)
    repair_input: dict[str, Any] = {"brokenJson": invalid_arguments}
    if preserved_outer_content:
        repair_input["preservedTopLevelFields"] = preserved_outer_content
    recovered_candidate = _machine_recovered_candidate(model_content)
    if recovered_candidate is not None:
        repair_input["machineRecoveredCandidate"] = recovered_candidate
    system_prompt = A2UIProtocolRegistry.read_design_argument_repair_prompt(
        DESIGN_COMPACT_PROFILE_ID
    )
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": json.dumps(repair_input, ensure_ascii=False),
        },
    ]


def _machine_recovered_candidate(
    content: dict[str, Any],
) -> dict[str, Any] | None:
    raw_arguments = content.get("arguments")
    if not isinstance(raw_arguments, str):
        return None
    recovered = _loads_json_object(raw_arguments)
    if recovered is None:
        return None
    reference = dict(recovered)
    _preserve_outer_content_values(reference, content)
    for key in _WRAPPER_KEYS:
        reference.pop(key, None)
    return reference


def _parse_repaired_content(raw_output: str) -> dict[str, Any]:
    repaired = _loads_json_object(_strip_json_fence(raw_output))
    if repaired is None:
        raise CompactDslArgumentRepairError("argument repair model did not return a JSON object")
    nested_content = repaired.get("content")
    if isinstance(nested_content, dict):
        repaired = dict(nested_content)
    repaired = _unwrap_repaired_arguments(repaired)
    for key in _WRAPPER_KEYS:
        repaired.pop(key, None)
    if not repaired:
        raise CompactDslArgumentRepairError("repaired content must not be empty")
    return repaired


def _unwrap_repaired_arguments(repaired: dict[str, Any]) -> dict[str, Any]:
    nested_arguments = repaired.get("arguments")
    if isinstance(nested_arguments, str):
        nested_arguments = _loads_json_object(nested_arguments)
        if nested_arguments is None:
            raise CompactDslArgumentRepairError(
                "repaired arguments must be a JSON object"
            )
    if not isinstance(nested_arguments, dict):
        return repaired
    outer_content = _outer_content_values(repaired)
    return {**nested_arguments, **outer_content}


def _loads_json_object(value: str) -> dict[str, Any] | None:
    try:
        loaded = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        try:
            loaded = json_repair.loads(value)
        except Exception as exc:
            logger.warning(f"{_MODULE} json_repair_failed exception_type={type(exc).__name__}")
            return None
    return loaded if isinstance(loaded, dict) else None


def _strip_json_fence(value: str) -> str:
    stripped = value.strip()
    if not stripped.startswith("```"):
        return stripped
    first_line, separator, remainder = stripped.partition("\n")
    if not separator or not first_line.startswith("```"):
        return stripped
    if remainder.rstrip().endswith("```"):
        return remainder.rstrip()[:-3].strip()
    return stripped


def _outer_content_values(source: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in source.items()
        if key not in _WRAPPER_KEYS
    }


def _preserve_outer_content_values(
    target: dict[str, Any],
    source: dict[str, Any],
) -> None:
    target.update(_outer_content_values(source))
