"""编译期 elseif 的顺序、作用域和端侧运行时边界。"""

from __future__ import annotations

import json
from itertools import product

import pytest

from services.card_validation import validate_card
from services.template_generation.engine.cardplan.compiler import (
    _instantiate_blueprint,
    _serialize_node,
)
from services.template_generation.engine.cardplan.models import TemplateDefinition
from services.template_generation.engine.cardplan.provider_bundle import (
    _parse_component_body,
    compile_card_template,
)
from services.template_generation.engine.tersel_converter import Nested2Node, convert_tersel_to_a2ui
from services.template_generation.profile import read_tersel_protocol_profile

_NAMES = ("first", "second", "third")


def _definition(body: str) -> TemplateDefinition:
    return compile_card_template(
        "#Template PresenceFull@1(props: { label?: string, flag?: boolean, count?: number })\n"
        'data = { first: $optionalPath("/first"), second: $optionalPath("/second"), '
        'third: $optionalPath("/third") }\nColumn(\n' + body + "\n)\n#End",
        provider_id="example.presence",
        business_id="Presence",
        expected_wire_id="PresenceFull@1",
        expected_capability_id="GetCalendarEvents",
        data_domain="/data/context",
        description="可选数据多分支测试",
        supported_card_sizes=("2x2",),
        primary_data=(),
        secondary_data=(),
        optional_data=tuple(f"/{name}" for name in _NAMES),
        output_schema={
            "type": "object",
            "properties": {name: {"type": "string"} for name in _NAMES},
        },
    )


def _bindings(names: tuple[str, ...]) -> dict[str, str]:
    return {name: "${data.context." + name + "}" for name in names}


def _texts(node: Nested2Node) -> list[object]:
    values: list[object] = []
    if node.component_type == "Text":
        values.append(node.values[0])
    for child in node.children:
        values.extend(_texts(child))
    return values


@pytest.mark.parametrize("ending", ("#endif", "#end"))
@pytest.mark.parametrize("available", tuple(product((False, True), repeat=3)))
def test_elseif_selects_first_available_binding(
    ending: str, available: tuple[bool, bool, bool]
) -> None:
    definition = _definition(
        "#if data.first\nText(data.first)\n"
        "#elseif data.second\nText(data.second)\n"
        '#elseif data.third\nText(data.third)\n#else\nText("无数据")\n' + ending
    )
    names: list[str] = []
    for name, present in zip(_NAMES, available, strict=True):
        if present:
            names.append(name)
    bindings = _bindings(tuple(names))
    root = _instantiate_blueprint(definition.variants[0].root, {}, bindings)
    expected = next(iter(bindings.values()), "无数据")
    assert _texts(root) == [expected]
    assert "IfBind" not in _serialize_node(root)
    assert "IfMissingBind" not in _serialize_node(root)


@pytest.mark.parametrize("name,value", (("label", ""), ("flag", False), ("count", 0)))
@pytest.mark.parametrize("state", ("present", "none", "missing"))
def test_elseif_props_use_presence_not_truthiness(name: str, value: object, state: str) -> None:
    definition = _definition(
        '#if data.first\nText("首选")\n'
        f'#elseif props.{name}\nText("参数分支")\n'
        '#elseif data.second\nText("数据分支")\n#end'
    )
    params = {}
    if state == "present":
        params[name] = value
    elif state == "none":
        params[name] = None
    root = _instantiate_blueprint(definition.variants[0].root, params, _bindings(("second",)))
    assert _texts(root) == ["参数分支" if state == "present" else "数据分支"]


@pytest.mark.parametrize("names", ((), ("first",), ("second",), ("first", "second")))
def test_elseif_grouped_binding_guard(names: tuple[str, ...]) -> None:
    definition = _definition(
        '#if props.flag\nText("标记")\n'
        "#elseif data.first && data.second\nText(data.first),\nText(data.second)\n"
        '#elseif data.second\nText(data.second)\n#else\nText("无数据")\n#endif'
    )
    root = _instantiate_blueprint(definition.variants[0].root, {}, _bindings(names))
    expected = ["无数据"]
    if names == ("first", "second"):
        expected = list(_bindings(names).values())
    elif "second" in names:
        expected = list(_bindings(("second",)).values())
    assert _texts(root) == expected


@pytest.mark.parametrize(
    "names,expected",
    (
        ((), ["前", "外后备", "后"]),
        (("second",), ["前", "内后备", "后"]),
        (("second", "third"), ["前", "内命中", "后"]),
        (("first",), ["前", "外命中", "后"]),
    ),
)
def test_elseif_nested_blocks_keep_sibling_order(
    names: tuple[str, ...], expected: list[str]
) -> None:
    definition = _definition(
        'Text("前"),\n#if data.first\nText("外命中")\n#elseif data.second\n'
        '#if data.first\nText("内首选")\n#elseif data.third\nText("内命中")\n'
        '#else\nText("内后备")\n#endif\n#else\nText("外后备")\n#end\nText("后")'
    )
    root = _instantiate_blueprint(definition.variants[0].root, {}, _bindings(names))
    assert _texts(root) == expected


@pytest.mark.parametrize("empty_branch", ("first", "second"))
def test_empty_matched_branch_does_not_fall_through(empty_branch: str) -> None:
    definition = _definition(
        '#if data.first\n#elseif data.second\n#elseif data.third\nText("第三")\n'
        '#else\nText("后备")\n#end'
    )
    root = _instantiate_blueprint(
        definition.variants[0].root, {}, _bindings((empty_branch, "third"))
    )
    assert root.children == ()


def test_unmatched_chain_without_else_emits_nothing() -> None:
    definition = _definition(
        "#if data.first\nText(data.first)\n#elseif data.second\nText(data.second)\n#end"
    )
    assert _instantiate_blueprint(definition.variants[0].root, {}).children == ()


@pytest.mark.parametrize(
    "body",
    (
        "#if data.first\nText(data.first)\n#elseif data.second\nText(data.first)\n#endif",
        "#if data.first\nText(data.first)\n#elseif data.second\nText(data.third)\n#endif",
        "#if props.label\nText(props.label)\n#elseif data.second\nText(props.label)\n#endif",
        '#if data.first\nText(data.first)\n#elseif data.unknown\nText("未知")\n#endif',
        '#if data.first\nText(data.first)\n#elseif props.unknown\nText("未知")\n#endif',
    ),
)
def test_elseif_cannot_borrow_other_branch_guards(body: str) -> None:
    with pytest.raises(ValueError):
        _definition(body)


@pytest.mark.parametrize(
    "body",
    (
        '#elseif data.first\nText("无 if")',
        '#if data.first\nText("首选")\n#else\nText("后备")\n#elseif data.second\n#end',
        "#if data.first\n#elseif data.second\n#else\n#else\n#end",
        "#if data.first\n#elseif data.second",
        "#if data.first\n#elseif\n#end",
        "#if data.first\n#elseif data.second.value\n#end",
        "#if data.first\n#elseif data.second || data.third\n#end",
        "#if data.first\n#elseif data.second && props.label\n#end",
        "#if data.first\n#elseif data.first && data.second && data.third\n#end",
        "#if data.first\n#elseif data.second && data.second\n#end",
        "#if data.first\n#elseif Expr(data.second)\n#end",
        "#if data.first\n#elseif data.second == 0\n#end",
        "#if data.first\n#elseif data.second\n#end extra",
        "#if data.first\n#elseif data.second\n#endif extra",
        "#end",
        "#endif",
    ),
)
def test_elseif_rejects_malformed_directives(body: str) -> None:
    with pytest.raises(ValueError):
        _parse_component_body("Column(\n" + body + "\n)")


def test_elseif_text_inside_multiline_literal_is_not_a_directive() -> None:
    definition = _definition(
        '#if data.first\nText(Expr(data.first ? `说明\n#elseif data.second\n#end` : ""))\n'
        "#elseif data.second\nText(data.second)\n#endif"
    )
    root = _instantiate_blueprint(definition.variants[0].root, {}, _bindings(("first",)))
    text = _texts(root)[0]
    assert isinstance(text, str)
    assert "#elseif data.second" in text
    assert "#end" in text


def test_elseif_preserves_runtime_expression_and_a2ui_paths() -> None:
    definition = _definition(
        '#if props.flag\nText("标记")\n#elseif data.first\n'
        'Text(Expr(data.first == "" ? "空值" : data.first))\n'
        '#else\nText("无绑定")\n#end'
    )
    root = _instantiate_blueprint(definition.variants[0].root, {}, _bindings(("first",)))
    assert root.children[0].component_type == "Text"
    a2ui = convert_tersel_to_a2ui(
        _serialize_node(root),
        size="2x2",
        protocol_profile=read_tersel_protocol_profile(),
        task_spec={
            "dataModelSchema": {
                "data": {
                    "context": {
                        "first": {"type": "string", "sampleValue": ""},
                    }
                }
            }
        },
    )
    assert "${/data/context/first}" in a2ui
    assert " == '' ? '空值' : " in a2ui
    assert "无绑定" not in a2ui
    assert "IfMissing" not in a2ui
    assert not validate_card(dsl_text=a2ui).diagnostics
    message = json.loads(a2ui.splitlines()[1])
    assert isinstance(message.get("updateComponents"), dict)
