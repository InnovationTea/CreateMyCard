from __future__ import annotations

from typing import Any

from ..catalog.display_values import DisplayPlan, apply_source_update
from ..ir.a2ui_nodes import A2UINode, flatten_tree

CATALOG_ID = "ohos.a2ui.extended.catalog.form"
PROTOCOL_VERSION = "v0.9"


def build_messages(root: A2UINode, surface_id: str, data_model: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = [
        {
            "version": PROTOCOL_VERSION,
            "createSurface": {"surfaceId": surface_id, "catalogId": CATALOG_ID},
        },
        {
            "version": PROTOCOL_VERSION,
            "updateComponents": {
                "surfaceId": surface_id,
                "components": flatten_tree(root),
            },
        },
    ]
    if data_model is not None:
        messages.append(
            {
                "version": PROTOCOL_VERSION,
                "updateDataModel": {"surfaceId": surface_id, "path": "/", "value": data_model},
            }
        )
    return messages


def build_source_update_messages(
    surface_id: str,
    source_path: str,
    raw_value: Any,
) -> tuple[list[dict[str, Any]], DisplayPlan]:
    """Build synchronized source and EmphasizedData display-model updates."""
    messages: list[dict[str, Any]] = []

    def append_update(path: str, value: Any) -> None:
        messages.append({
            "version": PROTOCOL_VERSION,
            "updateDataModel": {
                "surfaceId": surface_id,
                "path": path,
                "value": value,
            },
        })

    plan = apply_source_update(append_update, source_path, raw_value)
    return messages, plan
