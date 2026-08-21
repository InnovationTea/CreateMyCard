"""将模板 A2UI 转换为当前公共 Processor 对应的源 DSL。"""

from __future__ import annotations

import json
from typing import Any

from services.generation_pipeline import DslProcessorKind
from services.template_generation.engine.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    convert_a2ui_to_compact_dsl,
)


class TemplateSourceAdapterError(RuntimeError):
    """模板输出无法转换为当前路由要求的源 DSL。"""


def prepare_template_source_dsl(
    template_a2ui: str,
    *,
    processor_kind: DslProcessorKind,
    size: str,
    protocol_profile: dict[str, Any],
) -> str:
    """返回与 Processor 匹配的源格式，使公共转换和校验链保持不变。"""
    adapted_a2ui = _adapt_to_protocol_profile(template_a2ui, protocol_profile)
    if processor_kind == DslProcessorKind.STANDARD_A2UI:
        return adapted_a2ui
    if processor_kind != DslProcessorKind.DESIGN_COMPACT:
        raise TemplateSourceAdapterError(
            f"unsupported template processor kind: {processor_kind}"
        )
    try:
        return convert_a2ui_to_compact_dsl(adapted_a2ui, size=size)
    except CompactDslConversionError as exc:
        raise TemplateSourceAdapterError(
            "template A2UI cannot be converted to Design Compact DSL"
        ) from exc


def _adapt_to_protocol_profile(
    a2ui: str,
    protocol_profile: dict[str, Any],
) -> str:
    messages = _parse_three_messages(a2ui)
    create_surface = messages[0]["createSurface"]
    update_components = messages[1]["updateComponents"]
    update_data_model = messages[2]["updateDataModel"]
    surface_ids = {
        create_surface.get("surfaceId"),
        update_components.get("surfaceId"),
        update_data_model.get("surfaceId"),
    }
    surface_ids_match = len(surface_ids) == 1
    surface_ids_valid = all(isinstance(item, str) and item for item in surface_ids)
    if not surface_ids_match or not surface_ids_valid:
        raise TemplateSourceAdapterError("template A2UI surfaceId values do not match")
    create_surface["catalogId"] = protocol_profile["catalogId"]
    components = update_components.get("components")
    if not isinstance(components, list):
        raise TemplateSourceAdapterError("template A2UI components must be an array")
    root = next(
        (
            item
            for item in components
            if isinstance(item, dict) and item.get("id") == update_components.get("root")
        ),
        None,
    )
    if root is None:
        raise TemplateSourceAdapterError("template A2UI root component is missing")
    styles = root.setdefault("styles", {})
    if not isinstance(styles, dict):
        raise TemplateSourceAdapterError("template A2UI root styles must be an object")
    styles.update(
        {
            "width": "matchParent",
            "height": "matchParent",
            "borderRadius": 18,
            "clip": True,
        }
    )
    return "\n".join(
        json.dumps(item, ensure_ascii=False, separators=(",", ":"))
        for item in messages
    )


def _parse_three_messages(a2ui: str) -> list[dict[str, Any]]:
    lines = [line.strip() for line in a2ui.splitlines() if line.strip()]
    if len(lines) != 3:
        raise TemplateSourceAdapterError(
            "template A2UI must contain exactly three messages"
        )
    messages: list[dict[str, Any]] = []
    expected_keys = ("createSurface", "updateComponents", "updateDataModel")
    for line, expected_key in zip(lines, expected_keys, strict=True):
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            raise TemplateSourceAdapterError("template A2UI contains invalid JSON") from exc
        message_has_expected_body = isinstance(message, dict) and isinstance(
            message.get(expected_key),
            dict,
        )
        if not message_has_expected_body:
            raise TemplateSourceAdapterError(f"template A2UI is missing {expected_key}")
        if message.get("version") != "v0.9":
            raise TemplateSourceAdapterError("template A2UI wire version must be v0.9")
        messages.append(message)
    return messages
