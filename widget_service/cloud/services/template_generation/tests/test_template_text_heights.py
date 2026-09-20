"""检查模板全部条件分支的文本高度，以及公共转换后的行高。"""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.template_generation.engine.cardplan.models import TemplateNode, TemplateValue
from services.template_generation.engine.cardplan.preview_dataset import (
    build_template_preview_cases,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.compact_dsl_a2ui_converter import (
    convert_a2ui_to_compact_dsl,
)


def _walk(node: TemplateNode) -> Iterator[TemplateNode]:
    yield node
    for child in node.children:
        yield from _walk(child)


def _text_styles() -> Iterator[tuple[str, dict[str, TemplateValue]]]:
    registry = CardPlanRegistry(disabled_provider_ids=(), disabled_template_ids=())
    for template_id, definition in registry.templates.items():
        for variant in definition.variants:
            for node in _walk(variant.root):
                if node.component != "Text":
                    continue
                styles: dict[str, TemplateValue] = {}
                for value in node.values:
                    if value.kind == "object":
                        styles.update(value.properties)
                yield template_id, styles


def test_font12_template_text_never_uses_12vp_fixed_height() -> None:
    checked = 0
    for template_id, styles in _text_styles():
        font = styles.get("fontSize")
        if font is None or font.value != 12:
            continue
        height = styles.get("height")
        if height is not None:
            assert height.value != 12, template_id
        checked += 1
    assert checked > 0


@pytest.mark.parametrize("template_id", [
    "ScheduleOverviewTimezoneFull@1", "ScheduleOverviewDateFull@1",
])
def test_header_row_fits_corrected_text_height(template_id: str) -> None:
    registry = CardPlanRegistry(disabled_provider_ids=(), disabled_template_ids=())
    definition = registry.require_template(template_id)
    header = definition.variants[0].root.children[0]
    assert header.component == "Row"
    options = next(value for value in header.values if value.kind == "object")
    height = options.properties.get("height")
    assert height is not None and isinstance(height.value, (int, float))
    assert height.value >= 16


def test_all_business_previews_keep_font12_heights_after_public_conversion() -> None:
    checked = 0
    for case in build_template_preview_cases():
        a2ui = "\n".join(json.dumps(message) for message in case.messages)
        original_styles = {}
        for message in case.messages:
            for component in message.get("updateComponents", {}).get("components", []):
                original_styles[component.get("id")] = component.get("styles", {})
        compact = convert_a2ui_to_compact_dsl(a2ui, size=case.size)
        converted = convert_compact_dsl_to_a2ui(compact, size=case.size)
        for line in converted.splitlines():
            update = json.loads(line).get("updateComponents", {})
            for component in update.get("components", []):
                if component.get("component") != "Text":
                    continue
                styles = component.get("styles", {})
                if styles.get("fontSize") != 12:
                    continue
                before = original_styles.get(component.get("id"))
                assert before is not None, case.template_id
                assert styles.get("height") == before.get("height"), case.template_id
                assert styles.get("height") != 12, case.template_id
                checked += 1
    assert checked > 0
