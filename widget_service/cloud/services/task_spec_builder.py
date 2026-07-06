# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from copy import deepcopy
from typing import Any

from models.capability import AssetCapability, DataCapability
from models.generation import CandidateDataBinding, EventAction, TaskSpec, WidgetSize


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
        """构造传给 A2UI 模型的 TaskSpec。

        入参：
        - user_query：用户原始需求。
        - size：最终卡片尺寸。
        - effective_bindings：经过设备能力过滤后的数据绑定，包含 writeResultTo 和 updateModel。
        - effective_data_capabilities：过滤后的有效数据能力定义。
        - event_candidates：过滤后的有效事件候选。
        - asset_candidates：过滤后的有效素材候选。
        出参：符合协议约束的 TaskSpec。
        """
        data_model_value: dict[str, Any] = {}
        capability_by_id = {item.id: item for item in effective_data_capabilities}
        for binding in effective_bindings:
            capability = capability_by_id.get(binding.capabilityId)
            if binding.updateModel:
                # updateModel 是主 Agent 选择的输出字段结构，按 writeResultTo 写入 DataModel。
                self._set_by_json_pointer(
                    data_model_value,
                    binding.writeResultTo,
                    deepcopy(binding.updateModel),
                )
            elif capability is not None:
                # 未传 updateModel 时兜底使用能力注册表里的 DataModel 骨架。
                data_model_value = self._deep_merge(
                    data_model_value,
                    deepcopy(capability.dataModelSkeleton),
                )

        return TaskSpec(
            userQuery=user_query,
            size=size,
            eventCandidates=event_candidates,
            dataModel={"value": data_model_value or {"data": {}}},
            assetCandidates=[
                {"id": item.id, "src": item.src, "description": item.description}
                for item in asset_candidates
            ],
        )

    def _set_by_json_pointer(self, root: dict[str, Any], pointer: str, value: Any) -> None:
        """按 JSON Pointer 写入 DataModel。

        入参：
        - root：DataModel 根对象。
        - pointer：写入路径，例如 `/data/weather`。
        - value：待写入的 updateModel 子树。
        出参：无；函数会原地修改 root。
        """
        # writeResultTo 在能力过滤阶段已经校验必须以 /data/ 开头，这里只负责结构落位。
        parts = [part for part in pointer.strip("/").split("/") if part]
        current = root
        for part in parts[:-1]:
            # 中间层不存在时创建 dict，保留 updateModel 内部层级结构。
            current = current.setdefault(part, {})
        if parts:
            current[parts[-1]] = value

    def _deep_merge(self, base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
        """递归合并字典。

        入参：
        - base：被合并的基础字典。
        - incoming：待合入的字典。
        出参：合并后的基础字典。
        """
        for key, value in incoming.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
        return base
