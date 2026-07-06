import json
import uuid

from app.logger import logger
from models.generation import TaskSpec
from models.service import A2UIPromptPayload


class A2UIModelClient:
    def generate(
        self,
        task_spec: TaskSpec,
        protocol_profile: dict,
        prompt: A2UIPromptPayload,
    ) -> str:
        """生成 A2UI genui JSONL。

        入参：
        - task_spec：模型任务输入。
        - protocol_profile：A2UI 协议 profile。
        - prompt：PromptBuilder 生成的模型输入。
        出参：三行 JSONL 格式的 genui 字符串。
        """
        # 当前是模拟 A2UI 模型输出；后续可替换为真实模型客户端，但要保留三行 JSONL 契约。
        logger.info(
            f"a2ui_model_generate_started size={task_spec.size} "
            f"event_count={len(task_spec.eventCandidates)} "
            f"asset_count={len(task_spec.assetCandidates)}"
        )
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
            },
        }
        update_components = {
            "version": protocol_profile["version"],
            "updateComponents": {
                "surfaceId": surface_id,
                "root": root_id,
                "components": [
                    {
                        "id": root_id,
                        "component": "Column",
                        "styles": {
                            "width": size["width"],
                            "height": size["height"],
                            "padding": 12,
                            "borderRadius": 18 if task_spec.size == "2x2" else 22,
                            "clip": True,
                        },
                        "itemMargin": 8,
                        "children": ["title", "summary"],
                    },
                    {
                        "id": "title",
                        "component": "Text",
                        "content": self._title(task_spec.userQuery),
                        "styles": {
                            "fontSize": 16,
                            "fontWeight": 700,
                        },
                    },
                    {
                        "id": "summary",
                        "component": "Text",
                        "content": "正在为你刷新最新信息",
                        "styles": {
                            "fontSize": 12,
                        },
                    },
                ],
            },
        }
        update_data_model = {
            "version": protocol_profile["version"],
            "updateDataModel": {
                "surfaceId": surface_id,
                "path": "/",
                "value": data_model_value,
            },
        }
        genui = "\n".join(
            json.dumps(item, ensure_ascii=False, separators=(",", ":"))
            for item in [create_surface, update_components, update_data_model]
        )
        logger.info(f"a2ui_model_generate_completed surface_id={surface_id}")
        return genui

    def _title(self, user_query: str) -> str:
        """从用户需求生成 mock 标题。

        入参：
        - user_query：用户原始需求。
        出参：用于 mock DSL 的短标题。
        """
        return user_query[:18] or "桌面卡片"
