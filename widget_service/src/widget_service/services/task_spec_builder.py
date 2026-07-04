from copy import deepcopy
from typing import Any

from widget_service.models.capability import AssetCapability, DataCapability
from widget_service.models.generation import EventAction, TaskSpec, WidgetSize


class TaskSpecBuilder:
    def build(
        self,
        user_query: str,
        size: WidgetSize,
        effective_data_capabilities: list[DataCapability],
        event_candidates: list[EventAction],
        asset_candidates: list[AssetCapability],
    ) -> TaskSpec:
        data_model_value: dict[str, Any] = {}
        for capability in effective_data_capabilities:
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
        for key, value in incoming.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
        return base
