import json
import uuid

from models.generation import TaskSpec


class A2UIModelClient:
    def generate(self, task_spec: TaskSpec, protocol_profile: dict, prompt: dict) -> str:
        """生成 A2UI genui JSONL。

        入参：
        - task_spec：模型任务输入。
        - protocol_profile：A2UI 协议 profile。
        - prompt：PromptBuilder 生成的模型输入。
        出参：三行 JSONL 格式的 genui 字符串。
        """
        # 当前是模拟 A2UI 模型输出；后续可替换为真实模型客户端，但要保留三行 JSONL 契约。
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
        """从用户需求生成 mock 标题。

        入参：
        - user_query：用户原始需求。
        出参：用于 mock DSL 的短标题。
        """
        return user_query[:18] or "桌面卡片"
