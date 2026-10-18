from __future__ import annotations

# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import copy
from typing import Any


def task_spec_payload(task_spec: object, size: object) -> dict[str, Any]:
    """把平台 TaskSpec 转为 Runner 的原始任务输入，不扩展协议字段。"""
    if hasattr(task_spec, "model_dump"):
        payload = task_spec.model_dump(mode="json", exclude_none=True)
    elif isinstance(task_spec, dict):
        payload = copy.deepcopy(task_spec)
    else:
        raise TypeError("task_spec must be a mapping or Pydantic model")
    if size not in {"2x2", "2x4"}:
        raise ValueError(f"unsupported widget size: {size!r}")
    task_size = payload.get("size")
    if task_size not in {"2x2", "2x4"}:
        raise ValueError(f"TaskSpec has unsupported widget size: {task_size!r}")
    if task_size != size:
        raise ValueError(
            f"TaskSpec size {task_size!r} does not match platform size {size!r}"
        )
    actions = payload.get("eventCandidates")
    if not isinstance(actions, list):
        raise ValueError("eventCandidates must be an array")
    provided_ids: set[str] = set()
    for index, action in enumerate(actions):
        if not isinstance(action, dict):
            raise ValueError(f"eventCandidates[{index}] must be an object")
        action_id = action.get("id")
        if not isinstance(action_id, str) or not action_id.strip():
            continue
        if action_id in provided_ids:
            raise ValueError(f"duplicate event candidate id: {action_id}")
        provided_ids.add(action_id)
    assigned_ids = set(provided_ids)
    for index, action in enumerate(actions):
        action_id = action.get("id")
        if isinstance(action_id, str) and action_id.strip():
            continue
        action_id = f"event.generated.{index + 1}"
        suffix = 1
        while action_id in assigned_ids:
            suffix += 1
            action_id = f"event.generated.{index + 1}.{suffix}"
        action["id"] = action_id
        assigned_ids.add(action_id)
    return payload
