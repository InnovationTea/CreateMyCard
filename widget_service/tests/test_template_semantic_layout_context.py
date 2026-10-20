"""语义布局重新解析必须保留模板上下文，普通模型输入仍受组件白名单约束。"""

import json

import pytest

from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    ComponentRow,
    expand_compact_semantic_layout,
    parse_compact_dsl_rows,
)
from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext


def _source(component_type: str, size: str, semantic: bool, props: dict) -> str:
    rows: list[list] = [
        ["root", "Column", {}, ["content"]],
        ["content", "Column", {}, ["item"]],
        ["item", component_type, props],
    ]
    if semantic:
        rows.pop(1)
    if semantic and size == "2x2":
        rows[0] = ["root", "Layout", {"layout": "S-title-content"}, ["title", "item"]]
        rows.append(["title", "SingleLineTitle", {"title": "测试"}])
    elif semantic:
        rows[0] = ["root", "Layout", {"layout": "W-split-panels"}, ["left", "right"]]
        rows.extend([
            ["left", "Region", {"variant": "center"}, ["item"]],
            ["right", "Region", {"variant": "center"}, ["secondary"]],
            ["secondary", "EmphasisText", {"mainText": "正常"}],
        ])
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


@pytest.mark.parametrize("component_type", ["Image", "Divider", "Progress", "Button"])
@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("semantic", [False, True])
def test_expansion_preserves_template_component_permissions(component_type, size, semantic):
    source = _source(component_type, size, semantic, {})
    expanded, origins = expand_compact_semantic_layout(
        source, size=size, skip_compact_dsl_validation=True,
    )
    rows = parse_compact_dsl_rows(
        expanded, expand_layouts=False, skip_compact_dsl_validation=True,
    )
    items = []
    for row in rows:
        if isinstance(row, ComponentRow) and row.component_id == "item":
            items.append(row)
    assert len(items) == 1
    assert items[0].component_type == component_type
    assert bool(origins) is semantic
    if not semantic:
        assert expanded == source
    with pytest.raises(CompactDslConversionError, match="unsupported component type"):
        expand_compact_semantic_layout(source, size=size)


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("component_type", ["Image", "Divider"])
@pytest.mark.parametrize("semantic", [False, True])
def test_processor_accepts_template_internal_components(component_type, size, semantic):
    props = {"src": "resources/base/media/test.png"} if component_type == "Image" else {}
    source = _source(component_type, size, semantic, props)
    context = DslProcessingContext(
        size=size, card_spec={"suggestSize": size},
        task_spec={"size": size, "appVersion": "11.7.7.331", "dataModelSchema": {}},
        protocol_profile={"version": "v0.9"}, skip_compact_dsl_validation=True,
    )
    result = DesignCompactProcessor().process(source, context)
    assert not result.errors, result.errors
    assert result.standard_dsl
    update = json.loads(result.standard_dsl.splitlines()[1]).get("updateComponents")
    assert isinstance(update, dict)
    components = update.get("components")
    assert isinstance(components, list)
    assert any(component.get("component") == component_type for component in components)


@pytest.mark.parametrize("template", [False, True])
@pytest.mark.parametrize(
    ("component_type", "props", "error"),
    [
        ("UnknownComponent", {}, "unsupported component type"),
        ("Column", {"_visualRecipe": {}}, "reserved for internal expansion"),
    ],
)
def test_expansion_keeps_unknown_component_and_reserved_property_checks(
    template, component_type, props, error,
):
    with pytest.raises(CompactDslConversionError, match=error):
        expand_compact_semantic_layout(
            _source(component_type, "2x2", False, props), size="2x2",
            skip_compact_dsl_validation=template,
        )


def test_template_context_does_not_disable_semantic_layout_size_check():
    with pytest.raises(CompactDslConversionError, match="仅适用于尺寸 2x4"):
        expand_compact_semantic_layout(
            _source("Image", "2x4", True, {}), size="2x2",
            skip_compact_dsl_validation=True,
        )
