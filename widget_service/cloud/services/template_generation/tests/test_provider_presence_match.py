"""CardTemplate v2 有序可选项匹配与守卫转换测试。"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pytest

from services.template_generation.engine.cardplan.compiler import _instantiate_blueprint
from services.template_generation.engine.cardplan.models import TemplateDefinition
from services.template_generation.engine.cardplan.provider_bundle import (
    _parse_component_body,
    compile_card_template,
    load_provider_bundle,
)
from services.template_generation.engine.tersel_converter import Nested2Node

_NAMES = ("city", "temperature", "uv")
_AVAILABLE_SETS = (
    (),
    ("city",),
    ("temperature",),
    ("uv",),
    ("city", "temperature"),
    ("city", "uv"),
    ("temperature", "uv"),
    ("city", "temperature", "uv"),
)


def _definition(
    body: str,
    *,
    template_language: Literal["cardtpl/1", "cardtpl/2"] = "cardtpl/2",
) -> TemplateDefinition:
    source = (
        "#Template PresenceFull@1(props: { label?: string })\n"
        "data = {\n"
        '  city: $optionalPath("/city"),\n'
        '  temperature: $optionalPath("/temperature"),\n'
        '  uv: $optionalPath("/uv")\n'
        "}\n"
        "Column({},\n"
        f"{body}\n"
        ")\n"
        "#End"
    )
    return compile_card_template(
        source,
        template_language=template_language,
        provider_id="example.presence",
        business_id="Presence",
        expected_wire_id="PresenceFull@1",
        expected_capability_id="GetPresenceData",
        data_domain="/data/context",
        description="有序可选字段测试",
        supported_card_sizes=("2x2",),
        primary_data=(),
        secondary_data=(),
        optional_data=tuple(f"/{name}" for name in _NAMES),
        output_schema={
            "type": "object",
            "properties": {name: {"type": "string"} for name in _NAMES},
        },
    )


def _match_body() -> str:
    return """#match present(
  data.city,
  data.temperature,
  (data.uv => `紫外线等级${data.uv}`)
) as items
#case 0
  Text("暂无数据")
#case 1
  Text(items[0])
#case 2
  Row({"itemMargin": 4},
    Text(items[0]),
    Text(items[1])
  )
#default
  Column({"itemMargin": 2},
    Text(items[0]),
    Text(items[1]),
    Text(items[2])
  )
#end"""


def _bindings(names: tuple[str, ...]) -> dict[str, str]:
    return {name: "${data.context." + name + "}" for name in names}


def _texts(node: Nested2Node) -> list[object]:
    values: list[object] = []
    if node.component_type == "Text":
        values.append(node.values[0])
    for child in node.children:
        values.extend(_texts(child))
    return values


@pytest.mark.parametrize(
    "available",
    _AVAILABLE_SETS,
)
def test_presence_match_selects_layout_and_preserves_order(
    available: tuple[str, ...],
) -> None:
    definition = _definition(_match_body())
    root = _instantiate_blueprint(
        definition.variants[0].root,
        {},
        _bindings(available),
    )
    selected_layout = root.children[0]
    expected_layout = {0: "Text", 1: "Text", 2: "Row", 3: "Column"}[len(available)]
    assert selected_layout.component_type == expected_layout
    values = _texts(selected_layout)
    if not available:
        assert values == ["暂无数据"]
        return
    assert len(values) == len(available)
    for name, value in zip(available, values, strict=True):
        if name == "uv":
            assert "紫外线等级" in str(value)
            assert "/data/context/uv" in str(value)
        else:
            assert value == _bindings((name,))[name]


def test_presence_match_transformation_keeps_runtime_binding() -> None:
    definition = _definition(_match_body())
    root = _instantiate_blueprint(
        definition.variants[0].root,
        {},
        _bindings(("uv",)),
    )
    value = root.children[0].values[0]
    assert isinstance(value, str)
    assert value.startswith("{{")
    assert "紫外线等级" in value
    assert "${/data/context/uv}" in value
    assert definition.source_format == "cardtpl/2"


def test_presence_match_props_use_presence_not_truthiness() -> None:
    definition = _definition(
        """#match present(props.label) as items
#case 0
  Text("缺失")
#case 1
  Text(items[0])
#end"""
    )
    present = _instantiate_blueprint(definition.variants[0].root, {"label": ""})
    missing = _instantiate_blueprint(definition.variants[0].root, {})
    assert _texts(present) == [""]
    assert _texts(missing) == ["缺失"]


def test_presence_match_requires_cardtpl2() -> None:
    with pytest.raises(ValueError, match="#match requires cardtpl/2"):
        _definition(_match_body(), template_language="cardtpl/1")


def test_provider_bundle_propagates_cardtpl2_language(tmp_path: Path) -> None:
    templates_root = tmp_path / "templates"
    templates_root.mkdir()
    (tmp_path / "provider.json").write_text(
        """{
  "bundleFormat": "card-provider-bundle/1",
  "providerId": "example.layout",
  "providerVersion": "1.0.0",
  "templates": [{
    "templateId": "SingleFocusLayout@1",
    "description": "CardTemplate v2 manifest propagation test.",
    "entry": "templates/layout.cardtpl"
  }],
  "compatibility": {
    "templateLanguage": "cardtpl/2",
    "catalogId": "ohos.a2ui.extended.catalog.form",
    "a2uiWireVersion": "v0.9"
  }
}""",
        encoding="utf-8",
    )
    (templates_root / "layout.cardtpl").write_text(
        """#Template SingleFocusLayout@1(props: { label?: string })
data = {
}
Column({},
  #match present(props.label) as items
  #case 0
    Text("缺失")
  #case 1
    Text(items[0])
  #end
)
#End
""",
        encoding="utf-8",
    )

    bundle = load_provider_bundle(tmp_path)

    assert bundle.templates[0].source_format == "cardtpl/2"


@pytest.mark.parametrize(
    ("body", "message"),
    (
        (
            """#match present(data.city) as items
#case 1
  Text(items[1])
#end""",
            "items\\[1\\] is out of range",
        ),
        (
            """#match present(data.city, data.temperature) as items
#case 1
  Text(items[0])
#default
  Text(items[0])
#end""",
            "items\\[0\\] is out of range",
        ),
        (
            """#match present(data.city, data.city) as items
#case 2
  Text(items[0])
#end""",
            "guards must be unique",
        ),
        (
            """#match present(data.city => `城市${data.city}`) as items
#case 1
  Text(items[0])
#end""",
            "must use '\\(guard => value\\)'",
        ),
        (
            """#match present(data.city) as items
#case 2
  Text(items[0])
#end""",
            "#case exceeds present",
        ),
        (
            """#match present(
  data.first,
  data.second,
  data.third,
  data.fourth,
  data.fifth
) as items
#case 0
  Text("empty")
#end""",
            "exceeds the four-item limit",
        ),
    ),
)
def test_presence_match_rejects_invalid_structure(body: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _parse_component_body(body, template_language="cardtpl/2")


def test_presence_match_transform_cannot_borrow_missing_optional_binding() -> None:
    body = """#match present(
  (data.city => `${data.city} ${data.temperature}`)
) as items
#case 1
  Text(items[0])
#end"""
    with pytest.raises(ValueError, match="optional Bind must be nested"):
        _definition(body)
