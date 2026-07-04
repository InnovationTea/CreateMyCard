import json
import uuid

from widget_service.models.generation import TaskSpec


class A2UIModelClient:
    def generate(self, task_spec: TaskSpec, protocol_profile: dict, prompt: dict) -> str:
        surface_id = f"surface-{uuid.uuid4().hex[:12]}"
        size = protocol_profile["sizes"][task_spec.size]
        data_model_value = task_spec.dataModel["value"]
        root_id = "root"

        create_surface = {
            "version": protocol_profile["version"],
            "createSurface": {
                "surfaceId": surface_id,
                "catalogId": protocol_profile["catalogId"],
                "width": size["width"],
                "height": size["height"],
                "root": root_id,
            },
        }
        update_components = {
            "version": protocol_profile["version"],
            "updateComponents": {
                "surfaceId": surface_id,
                "components": [
                    {
                        "id": root_id,
                        "type": "Column",
                        "width": size["width"],
                        "height": size["height"],
                        "padding": 12,
                        "borderRadius": 16,
                        "clip": True,
                        "background": "#F7F8FA",
                        "children": ["title", "summary"],
                    },
                    {
                        "id": "title",
                        "type": "Text",
                        "text": self._title(task_spec.userQuery),
                        "fontSize": 16,
                        "fontWeight": "bold",
                    },
                    {
                        "id": "summary",
                        "type": "Text",
                        "text": "正在为你刷新最新信息",
                        "fontSize": 12,
                    },
                ],
            },
        }
        update_data_model = {
            "version": protocol_profile["version"],
            "updateDataModel": {
                "surfaceId": surface_id,
                "value": data_model_value,
            },
        }
        return "\n".join(
            json.dumps(item, ensure_ascii=False, separators=(",", ":"))
            for item in [create_surface, update_components, update_data_model]
        )

    def _title(self, user_query: str) -> str:
        return user_query[:18] or "桌面卡片"
