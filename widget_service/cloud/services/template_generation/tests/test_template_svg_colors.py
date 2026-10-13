"""逐模板验证 SVG 颜色及公共结构修复、转换，避免首个失败掩盖后续模板。"""

from __future__ import annotations

import json

import pytest

from services.compact_dsl_a2ui_converter import (
    convert_compact_dsl_to_a2ui,
    repair_compact_dsl_safe_structure,
)
from services.template_generation.engine.cardplan.preview_dataset import (
    TemplatePreviewCase,
    build_template_preview_cases,
)
from services.template_generation.engine.compact_dsl_a2ui_converter import (
    convert_a2ui_to_compact_dsl,
)


@pytest.mark.parametrize("case", build_template_preview_cases(), ids=lambda case: case.template_id)
def test_template_preview_svg_colors_survive_public_conversion(case: TemplatePreviewCase) -> None:
    original_colors: dict[str, str] = {}
    for message in case.messages:
        for component in message.get("updateComponents", {}).get("components", []):
            if component.get("component") != "Image":
                continue
            source = component.get("src")
            if not isinstance(source, str) or not source.endswith(".svg"):
                continue
            component_id = component.get("id")
            assert isinstance(component_id, str)
            color = component.get("styles", {}).get("fillColor")
            assert isinstance(color, str) and color, component_id
            original_colors[component_id] = color

    a2ui = "\n".join(json.dumps(message) for message in case.messages)
    compact = convert_a2ui_to_compact_dsl(a2ui, size=case.size)
    repaired = repair_compact_dsl_safe_structure(
        compact, size=case.size, skip_compact_dsl_validation=True,
    )
    converted = convert_compact_dsl_to_a2ui(
        repaired, size=case.size, skip_compact_dsl_validation=True,
    )
    converted_colors: dict[str, str] = {}
    for line in converted.splitlines():
        for component in json.loads(line).get("updateComponents", {}).get("components", []):
            component_id = component.get("id")
            if component_id not in original_colors:
                continue
            converted_colors[component_id] = component.get("styles", {}).get("fillColor")
    assert converted_colors == original_colors
