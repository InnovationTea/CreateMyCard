"""将模板引擎的 A2UI 适配为主生成链可校验、可归档的输出。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from services.generation_pipeline import (
    DslProcessingContext,
    DslProcessingResult,
    DslProcessorKind,
    GenerationRoutePolicy,
    get_dsl_processor,
)
from services.template_generation.engine.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    convert_a2ui_to_compact_dsl,
)


class TemplateA2UIAdapterError(RuntimeError):
    """模板 A2UI 无法进入当前主生成链。"""


@dataclass(frozen=True)
class PreparedTemplateA2UI:
    """模板 A2UI 的通用处理结果与可选源格式 Token。"""

    processing_result: DslProcessingResult
    design_token: str | None = None


def prepare_template_a2ui(
    template_a2ui: str,
    policy: GenerationRoutePolicy,
    context: DslProcessingContext,
    protocol_profile: dict[str, Any],
) -> PreparedTemplateA2UI:
    """适配最终 Profile，Compact 路线再经原 Processor 回转以保持编辑兼容。"""
    adapted_a2ui = _adapt_to_protocol_profile(template_a2ui, protocol_profile)
    if policy.processor_kind != DslProcessorKind.DESIGN_COMPACT:
        return PreparedTemplateA2UI(
            processing_result=DslProcessingResult(
                source_dsl=adapted_a2ui,
                standard_dsl=adapted_a2ui,
            )
        )
    try:
        design_token = convert_a2ui_to_compact_dsl(
            adapted_a2ui,
            size=context.size,
        )
    except CompactDslConversionError as exc:
        raise TemplateA2UIAdapterError(
            "template A2UI cannot be archived as Compact DSL"
        ) from exc
    processing_result = get_dsl_processor(DslProcessorKind.DESIGN_COMPACT).process(
        design_token,
        context,
    )
    return PreparedTemplateA2UI(
        processing_result=processing_result,
        design_token=design_token,
    )


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
        raise TemplateA2UIAdapterError("template A2UI surfaceId values do not match")
    create_surface["catalogId"] = protocol_profile["catalogId"]
    components = update_components.get("components")
    if not isinstance(components, list):
        raise TemplateA2UIAdapterError("template A2UI components must be an array")
    root = next(
        (
            item
            for item in components
            if isinstance(item, dict) and item.get("id") == update_components.get("root")
        ),
        None,
    )
    if root is None:
        raise TemplateA2UIAdapterError("template A2UI root component is missing")
    styles = root.setdefault("styles", {})
    if not isinstance(styles, dict):
        raise TemplateA2UIAdapterError("template A2UI root styles must be an object")
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
        raise TemplateA2UIAdapterError("template A2UI must contain exactly three messages")
    messages: list[dict[str, Any]] = []
    expected_keys = ("createSurface", "updateComponents", "updateDataModel")
    for line, expected_key in zip(lines, expected_keys, strict=True):
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            raise TemplateA2UIAdapterError("template A2UI contains invalid JSON") from exc
        message_has_expected_body = isinstance(message, dict) and isinstance(
            message.get(expected_key),
            dict,
        )
        if not message_has_expected_body:
            raise TemplateA2UIAdapterError(f"template A2UI is missing {expected_key}")
        if message.get("version") != "v0.9":
            raise TemplateA2UIAdapterError("template A2UI wire version must be v0.9")
        messages.append(message)
    return messages
