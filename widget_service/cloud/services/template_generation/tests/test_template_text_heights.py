"""模板 Text 字号-行高契约与公共转换的行高保持（场景金样化）。

三类确定性输出契约已固化为场景金样（Layer C）：

- ``text_heights__registry_matrix``：全注册表扫描——每个模板里 fontSize 12
  的 Text 节点解析出的显式 height（含未显式设置的 null，覆盖「12vp 字号
  不得配 12 高度」矩阵），以及 Timezone/Date 两个表头 Row 的组件类型与
  实际 height（原阈值断言 ≥16 由快照逐值冻结替代）；
- ``text_heights__public_conversion``：全部预览用例经
  convert_a2ui_to_compact_dsl → convert_compact_dsl_to_a2ui 往返后，
  fontSize 12 文本的转换前/转换后 height 逐组件对照表（id 缺失记为
  ``__absent__``），把「公共转换保持行高且不落入 12」固化为可 diff 的
  精确值。

原有内联断言全部迁入金样，本文件仅保留注册与金样比对入口；转换器或
模板改动后按 golden 工作流 `check --diff` / `bless --declared` 复核。
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.template_generation.engine.cardplan.models import TemplateNode, TemplateValue
from services.template_generation.engine.cardplan.preview_dataset import (
    build_template_preview_cases,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.compact_dsl_a2ui_converter import (
    convert_a2ui_to_compact_dsl,
)
from services.template_generation.test_support.golden_scenarios import (
    assert_golden_scenario,
    scenario,
)

_HEADER_ROW_TEMPLATE_IDS = ("ScheduleOverviewTimezoneFull@1", "ScheduleOverviewDateFull@1")


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


@scenario("text_heights__registry_matrix")
def _build_registry_matrix() -> dict[str, Any]:
    font12_heights: dict[str, list[int | None]] = {}
    for template_id, styles in _text_styles():
        font = styles.get("fontSize")
        if font is None or font.value != 12:
            continue
        height = styles.get("height")
        font12_heights.setdefault(template_id, []).append(
            None if height is None else height.value
        )
    registry = CardPlanRegistry(disabled_provider_ids=(), disabled_template_ids=())
    header_rows: dict[str, dict[str, Any]] = {}
    for template_id in _HEADER_ROW_TEMPLATE_IDS:
        definition = registry.require_template(template_id)
        header = definition.variants[0].root.children[0]
        options = next(value for value in header.values if value.kind == "object")
        height = options.properties.get("height")
        header_rows[template_id] = {
            "component": header.component,
            "height": None if height is None else height.value,
        }
    return {"font12TextHeights": font12_heights, "headerRows": header_rows}


@scenario("text_heights__public_conversion")
def _build_public_conversion() -> dict[str, Any]:
    matrix: dict[str, dict[str, dict[str, Any]]] = {}
    for case in build_template_preview_cases():
        a2ui = "\n".join(json.dumps(message) for message in case.messages)
        original_styles: dict[str, dict[str, Any]] = {}
        for message in case.messages:
            for component in message.get("updateComponents", {}).get("components", []):
                original_styles[component.get("id")] = component.get("styles", {})
        compact = convert_a2ui_to_compact_dsl(a2ui, size=case.size)
        converted = convert_compact_dsl_to_a2ui(compact, size=case.size)
        entries: dict[str, dict[str, Any]] = {}
        for line in converted.splitlines():
            update = json.loads(line).get("updateComponents", {})
            for component in update.get("components", []):
                if component.get("component") != "Text":
                    continue
                styles = component.get("styles", {})
                if styles.get("fontSize") != 12:
                    continue
                before = original_styles.get(component.get("id"))
                entries[component.get("id")] = {
                    "before": (
                        "__absent__" if before is None else before.get("height")
                    ),
                    "after": styles.get("height"),
                }
        matrix[f"{case.template_id}::{case.size}"] = entries
    return matrix


def test_template_text_height_scenarios_match_goldens() -> None:
    assert_golden_scenario("text_heights__registry_matrix")
    assert_golden_scenario("text_heights__public_conversion")
