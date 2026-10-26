# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""依据注册表补齐同对象图形驱动字段，不通过名称或首帧推断关系。"""

from app.logger import json_for_log, logger
from models.capability import DataCapability
from models.generation import CandidateDataBinding
from services.task_spec_builder import TaskSpecBuilder


def complete_related_output_fields(
    bindings: list[CandidateDataBinding], capabilities: list[DataCapability],
) -> list[CandidateDataBinding]:
    """仅扩展已通过预检的字段投影，保持原始请求与运行时写入根不变。"""
    by_id = {item.id: item for item in capabilities}
    completed: list[CandidateDataBinding] = []
    builder = TaskSpecBuilder()
    for binding in bindings:
        capability = by_id.get(binding.capabilityId)
        if capability is None or not binding.candidateOutputFields:
            completed.append(binding.model_copy(deep=True))
            continue
        selected = list(binding.candidateOutputFields)
        added: list[str] = []
        for pointer in binding.candidateOutputFields:
            resolved = builder.resolve_output_leaf(capability.outputSchema, pointer)
            if resolved is None:
                continue
            parts, leaf = resolved
            source_name = leaf.get("numericSource")
            if not isinstance(source_name, str):
                continue
            parent, _, _name = pointer.rpartition("/")
            escaped = source_name.replace("~", "~0").replace("/", "~1")
            source_pointer = f"{parent}/{escaped}"
            source = builder.resolve_output_leaf(capability.outputSchema, source_pointer)
            if source is None or source[1].get("type") not in {"number", "integer"}:
                raise ValueError(f"invalid registered numericSource for {pointer}")
            if source[0][:-1] != parts[:-1]:
                raise ValueError(f"numericSource crosses objects for {pointer}")
            if source_pointer not in selected:
                selected.append(source_pointer)
                added.append(source_pointer)
        completed.append(binding.model_copy(update={"candidateOutputFields": selected}, deep=True))
        if added:
            logger.info(
                "[Related Fields] completed "
                f"capability_id={binding.capabilityId} write_root={binding.writeResultTo} "
                f"added_fields={json_for_log(added)}"
            )
    return completed
