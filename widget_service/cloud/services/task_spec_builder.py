from copy import deepcopy
from typing import Any

from models.capability import AssetCapability, DataCapability
from models.generation import EventAction, TaskSpec, WidgetSize


class TaskSpecBuilder:
    def build(
        self,
        user_query: str,
        size: WidgetSize,
        effective_data_capabilities: list[DataCapability],
        event_candidates: list[EventAction],
        asset_candidates: list[AssetCapability],
    ) -> TaskSpec:
        """构造传给 A2UI 模型的 TaskSpec。

        入参：
        - user_query：用户原始需求。
        - size：最终卡片尺寸。
        - effective_data_capabilities：过滤后的有效数据能力定义。
        - event_candidates：过滤后的有效事件候选。
        - asset_candidates：过滤后的有效素材候选。
        出参：符合协议约束的 TaskSpec。
        """
        data_model_value: dict[str, Any] = {}
        for capability in effective_data_capabilities:
            # 将所有有效数据能力的 DataModel 骨架合并为一个 TaskSpec DataModel。
            data_model_value = self._deep_merge(
                data_model_value, deepcopy(capability.dataModelSkeleton)
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
