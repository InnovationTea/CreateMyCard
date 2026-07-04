from widget_service.models.generation import TaskSpec


class PromptBuilder:
    def build(
        self, task_spec: TaskSpec, protocol_profile: dict, removed_capability_summary: str = ""
    ) -> dict:
        return {
            "system": (
                "Generate HarmonyOS A2UI Form genui JSONL only. "
                "Use exactly createSurface, updateComponents, updateDataModel in order."
            ),
            "user": {
                "taskSpec": task_spec.model_dump(mode="json", exclude_none=True),
                "protocolProfile": {
                    "id": protocol_profile["id"],
                    "version": protocol_profile["version"],
                    "catalogId": protocol_profile["catalogId"],
                    "sizes": protocol_profile["sizes"],
                    "componentWhitelist": protocol_profile["componentWhitelist"],
                },
                "degradationContext": removed_capability_summary,
            },
        }
