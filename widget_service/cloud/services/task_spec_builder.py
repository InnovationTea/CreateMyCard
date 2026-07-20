# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from copy import deepcopy
from typing import Any

from app.logger import json_for_log, logger
from core.json_pointer import parse_json_pointer
from models.capability import AssetCapability, DataCapability
from models.generation import CandidateDataBinding, EventAction, TaskSpec, WidgetSize

PathPart = str | int

_MODULE = "[TaskSpec Builder]"

DEFAULT_SAMPLE_VALUES: dict[str, Any] = {
    "string": "示例",
    "integer": 0,
    "number": 0,
    "boolean": False,
    "null": None,
}


class TaskSpecBuilder:
    def build(
        self,
        user_query: str,
        size: WidgetSize,
        effective_bindings: list[CandidateDataBinding],
        effective_data_capabilities: list[DataCapability],
        event_candidates: list[EventAction],
        asset_candidates: list[AssetCapability],
    ) -> TaskSpec:
        """按有效能力 outputSchema 构造传给 A2UI 模型的 TaskSpec。"""
        data_model_schema: dict[str, Any] = {"data": {}}
        capability_by_id = {item.id: item for item in effective_data_capabilities}

        for binding in effective_bindings:
            capability = capability_by_id.get(binding.capabilityId)
            if capability is None:
                continue

            requested_paths = binding.candidateOutputFields
            valid_fields: list[tuple[tuple[PathPart, ...], dict[str, Any]]] = []
            invalid_paths: list[str] = []
            seen: set[tuple[PathPart, ...]] = set()

            for pointer in requested_paths:
                resolved = self._resolve_leaf(capability.outputSchema, pointer)
                if resolved is None:
                    invalid_paths.append(pointer)
                    continue
                parts, leaf = resolved
                if parts not in seen:
                    seen.add(parts)
                    valid_fields.append((parts, leaf))

            if invalid_paths:
                logger.warning(
                    f"{_MODULE} candidate_output_fields_ignored capability_id={binding.capabilityId} "
                    f"invalid_paths={json_for_log(invalid_paths)}"
                )

            # 未传投影或全部投影非法时，回退为该能力全部合法叶子，保证模型仍有可用结构。
            if not requested_paths or not valid_fields:
                valid_fields = list(self._iter_valid_leaves(capability.outputSchema))
                logger.info(
                    f"{_MODULE} candidate_output_fields_fallback capability_id={binding.capabilityId} "
                    f"reason={'missing' if not requested_paths else 'all_invalid'} "
                    f"field_count={len(valid_fields)}"
                )

            write_parts = parse_json_pointer(binding.writeResultTo)
            if write_parts is None:
                continue
            generated_sample_count = 0
            for relative_parts, leaf in valid_fields:
                if "sampleValue" in leaf:
                    sample_value = deepcopy(leaf["sampleValue"])
                else:
                    sample_value = DEFAULT_SAMPLE_VALUES[leaf["type"]]
                    generated_sample_count += 1
                metadata = {
                    "type": leaf["type"],
                    "description": leaf["description"],
                    "sampleValue": sample_value,
                }
                self._set_by_parts(data_model_schema, (*write_parts, *relative_parts), metadata)
            if generated_sample_count:
                logger.warning(
                    f"{_MODULE} output_schema_sample_value_fallback "
                    f"capability_id={binding.capabilityId} "
                    f"fallback_count={generated_sample_count}"
                )

        return TaskSpec(
            userQuery=user_query,
            size=size,
            eventCandidates=event_candidates,
            dataModelSchema=data_model_schema,
            assetCandidates=[
                {"id": item.id, "src": item.src, "description": item.description}
                for item in asset_candidates
            ],
        )

    def _resolve_leaf(
        self,
        schema: dict[str, Any],
        pointer: str,
    ) -> tuple[tuple[PathPart, ...], dict[str, Any]] | None:
        parts = parse_json_pointer(pointer)
        if not parts:
            return None
        current = schema
        resolved_parts: list[PathPart] = []
        for part in parts:
            schema_type = current.get("type")
            if schema_type == "object":
                child = current.get("properties", {}).get(part)
                if not isinstance(child, dict):
                    return None
                current = child
                resolved_parts.append(part)
            elif schema_type == "array":
                # 字段投影描述的是数组元素 schema，统一使用 canonical `/0`，
                # 避免模型通过大下标制造稀疏 DataModel 或改变字段结构语义。
                if part != "0" or not isinstance(current.get("items"), dict):
                    return None
                current = current["items"]
                resolved_parts.append(0)
            else:
                return None
        if current.get("type") in {"object", "array"}:
            return None
        if not {"type", "description"}.issubset(current):
            return None
        return tuple(resolved_parts), current

    def _iter_valid_leaves(
        self,
        schema: dict[str, Any],
        parts: tuple[PathPart, ...] = (),
    ):
        """递归枚举 outputSchema 中具备类型和说明的合法叶子。"""
        schema_type = schema.get("type")
        if schema_type == "object":
            for name, child in schema.get("properties", {}).items():
                if isinstance(child, dict):
                    yield from self._iter_valid_leaves(child, (*parts, name))
            return
        if schema_type == "array":
            items = schema.get("items")
            if isinstance(items, dict):
                yield from self._iter_valid_leaves(items, (*parts, 0))
            return
        if parts and {"type", "description"}.issubset(schema):
            yield parts, schema

    def _set_by_parts(
        self,
        root: dict[str, Any],
        parts: tuple[PathPart, ...],
        value: Any,
    ) -> None:
        current: Any = root
        for index, part in enumerate(parts):
            is_last = index == len(parts) - 1
            if isinstance(current, list):
                if not isinstance(part, int):
                    return
                while len(current) <= part:
                    current.append({})
                if is_last:
                    current[part] = value
                    return
                next_is_index = isinstance(parts[index + 1], int)
                if not isinstance(current[part], (dict, list)):
                    current[part] = [] if next_is_index else {}
                current = current[part]
                continue

            if not isinstance(part, str):
                return
            if is_last:
                current[part] = value
                return
            next_is_index = isinstance(parts[index + 1], int)
            expected_type = list if next_is_index else dict
            if not isinstance(current.get(part), expected_type):
                current[part] = [] if next_is_index else {}
            current = current[part]
