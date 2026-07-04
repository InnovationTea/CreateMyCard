import json
from typing import Any

from widget_service.models.artifact import WidgetArtifact


class ArtifactValidator:
    def validate(self, artifact: WidgetArtifact, protocol_profile: dict) -> list[str]:
        errors: list[str] = []
        lines = [line for line in artifact.genui.splitlines() if line.strip()]
        if len(lines) != 3:
            return ["genui must contain exactly 3 JSONL lines"]

        parsed: list[dict[str, Any]] = []
        for line in lines:
            try:
                parsed.append(json.loads(line))
            except json.JSONDecodeError as exc:
                errors.append(f"invalid JSONL: {exc.msg}")
        if errors:
            return errors

        expected_keys = ["createSurface", "updateComponents", "updateDataModel"]
        for item, key in zip(parsed, expected_keys, strict=True):
            if key not in item:
                errors.append(f"missing {key}")
            if item.get("version") != protocol_profile["version"]:
                errors.append(f"invalid protocol version for {key}")

        surface_ids = [
            parsed[0].get("createSurface", {}).get("surfaceId"),
            parsed[1].get("updateComponents", {}).get("surfaceId"),
            parsed[2].get("updateDataModel", {}).get("surfaceId"),
        ]
        if len(set(surface_ids)) != 1:
            errors.append("surfaceId must be consistent")

        create_surface = parsed[0].get("createSurface", {})
        if create_surface.get("catalogId") != protocol_profile["catalogId"]:
            errors.append("catalogId mismatch")

        size = artifact.cardSpec.get("suggestSize")
        expected_size = protocol_profile["sizes"].get(size)
        if expected_size:
            if create_surface.get("width") != expected_size["width"]:
                errors.append("surface width mismatch")
            if create_surface.get("height") != expected_size["height"]:
                errors.append("surface height mismatch")

        update_data_model_value = parsed[2].get("updateDataModel", {}).get("value")
        task_data_model_value = artifact.taskSpec.get("dataModel", {}).get("value")
        if update_data_model_value != task_data_model_value:
            errors.append("updateDataModel.value mismatch")

        allowed_components = set(protocol_profile["componentWhitelist"])
        components = parsed[1].get("updateComponents", {}).get("components", [])
        for component in components:
            if component.get("type") not in allowed_components:
                errors.append(f"component not allowed: {component.get('type')}")

        bindings = artifact.cardSpec.get("dataBindings", [])
        for binding in bindings:
            if not binding.get("writeResultTo", "").startswith("/data/"):
                errors.append("CardSpec writeResultTo must start with /data/")

        return errors
