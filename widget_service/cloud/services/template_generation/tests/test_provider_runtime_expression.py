"""无外层引号的模板 Expr 语法、绑定保留及 A2UI 转换回归。"""

from __future__ import annotations

import json

import pytest

from services.card_validation import validate_card
from services.template_generation.engine.cardplan.compiler import (
    _instantiate_blueprint,
    _provider_runtime_expression,
    _serialize_node,
)
from services.template_generation.engine.cardplan.models import TemplateDefinition
from services.template_generation.engine.cardplan.provider_bundle import compile_card_template
from services.template_generation.engine.tersel_converter import convert_tersel_to_a2ui
from services.template_generation.profile import read_tersel_protocol_profile


def _definition(
    body: str,
    names: tuple[str, ...] = ("value",),
    *,
    optional: bool = False,
) -> TemplateDefinition:
    path_call = "$optionalPath" if optional else "$path"
    fields = ", ".join(f'{name}: {path_call}("/{name}")' for name in names)
    paths = tuple(f"/{name}" for name in names)
    source = f"#Template ExpressionFull@1(props: {{}})\ndata = {{{fields}}}\n{body}\n#End"
    return compile_card_template(
        source,
        provider_id="example.expression",
        business_id="Expression",
        expected_wire_id="ExpressionFull@1",
        expected_capability_id="GetCalendarEvents",
        data_domain="/data/calendar",
        description="表达式测试",
        supported_card_sizes=("2x2",),
        primary_data=() if optional else paths,
        secondary_data=(),
        optional_data=paths if optional else (),
        output_schema={
            "type": "object",
            "properties": {name: {"type": "string"} for name in names},
        },
    )


def _expression(expression: str) -> str:
    definition = _definition(f"Column(Text({expression}))")
    value = definition.variants[0].root.children[0].values[0]
    assert value.kind == "expression"
    return _provider_runtime_expression(value, {"value": "${data.calendar.value}"})


@pytest.mark.parametrize(
    ("bare", "legacy"),
    (
        ("data.value", "${data.value}"),
        ("data.value * 2 + 1", "${data.value} * 2 + 1"),
        ("'' + ((data.value + 0.5) % 1)", "'' + ((${data.value} + 0.5) % 1)"),
        ('data.value == "" ? "空" : data.value', "${data.value} == '' ? '空' : ${data.value}"),
        ("size(data.value) > 0 && true", "size(${data.value}) > 0 && true"),
        ("!(data.value > 0) || false", "!(${data.value} > 0) || false"),
        (
            "data.value > 1 ? 2 : data.value > 0 ? 1 : 0",
            "${data.value} > 1 ? 2 : ${data.value} > 0 ? 1 : 0",
        ),
    ),
)
def test_bare_expr_matches_legacy_a2ui(bare: str, legacy: str) -> None:
    assert _expression(f"Expr({bare})") == _expression(f"Expr(`{legacy}`)")


@pytest.mark.parametrize(
    "expression",
    (
        'Expr(data.start == "" ? "" : `${data.start} - ${data.end}`)',
        'Expr(data.start == "" ? "" : data.start + " - " + data.end)',
    ),
)
@pytest.mark.parametrize("start", ("", "09:00", "其他值"))
def test_calendar_expr_keeps_runtime_paths_in_a2ui(expression: str, start: str) -> None:
    definition = _definition(f"Column(Text({expression}))", ("start", "end"))
    bindings = {"start": "${data.calendar.start}", "end": "${data.calendar.end}"}
    node = _instantiate_blueprint(definition.variants[0].root, {}, bindings)
    a2ui = convert_tersel_to_a2ui(
        _serialize_node(node),
        size="2x2",
        protocol_profile=read_tersel_protocol_profile(),
        task_spec={
            "dataModelSchema": {
                "data": {
                    "calendar": {
                        "start": {"type": "string", "sampleValue": start},
                        "end": {"type": "string", "sampleValue": "10:00"},
                    }
                }
            },
        },
    )
    message = json.loads(a2ui.splitlines()[1])
    update = message.get("updateComponents")
    assert isinstance(update, dict)
    components = update.get("components")
    assert isinstance(components, list)
    text = components[1].get("content")
    assert isinstance(text, str)
    assert text.startswith("{{ ${/data/calendar/start} == '' ? '' : ")
    assert "${/data/calendar/end}" in text
    assert "09:00" not in text
    assert "10:00" not in text
    assert "其他值" not in text
    assert "`" not in text
    assert not validate_card(dsl_text=a2ui).diagnostics


def test_expr_preserves_quoted_literals_and_escapes() -> None:
    result = _expression(
        r"""Expr(data.value + "Expr(fake) data.start ${data.end} ) #Expr(" + "a\"b\\c\n")"""
    )
    assert "'Expr(fake) data.start ${data.end} ) #Expr('" in result
    assert "'a\"b\\\\c\\n'" in result
    assert "${/data/calendar/value}" in result
    assert "/data/calendar/end" not in result
    optional_literal = _expression('Expr(data.value + "props?.label")')
    assert optional_literal == "{{ ${/data/calendar/value} + 'props?.label' }}"


def test_expr_template_literal_preserves_string_coercion_and_precedence() -> None:
    result = _expression('Expr(size(`数值 ${data.value}`) > 0 ? `${data.value}${data.value}` : "")')
    assert "size(('数值 ' + ${/data/calendar/value} + ''))" in result
    assert "('' + ${/data/calendar/value} + '' + ${/data/calendar/value} + '')" in result


def test_expr_coexists_with_compile_time_choice_and_text_interpolation() -> None:
    definition = _definition(
        'Column(Text(#Expr(data.value ? data.value : "缺失")), '
        'Text(Expr(data.value == "" ? "空" : data.value)), Text(`${data.value} 后缀`))'
    )
    children = definition.variants[0].root.children
    assert children[0].values[0].kind == "compile-time-conditional"
    assert children[1].values[0].kind == "expression"
    assert children[2].values[0].kind == "interpolation"


def test_expr_defers_symbolic_binding_resolution_until_a2ui_compilation() -> None:
    definition = _definition('Column(Text(Expr(data.value + "单位")))')
    expression = definition.variants[0].root.children[0].values[0]
    bindings = tuple(item.name for item in expression.items if item.kind == "binding")
    assert bindings == ("value",)
    for path in ("data.first.value", "data.second.nested.value"):
        actual = _provider_runtime_expression(expression, {"value": "${" + path + "}"})
        expected_path = "/" + path.replace(".", "/")
        assert actual == "{{ ${" + expected_path + "} + '单位' }}"


def test_expr_supports_multiline_body_and_ignores_call_names_in_text() -> None:
    definition = _definition(
        'Column(\n# ignored Expr( " `\nText("Expr(data.private)"),\n'
        'Text(Expr (\n  size(data.value) > 0\n  ? data.value\n  : "空"\n)))'
    )
    children = definition.variants[0].root.children
    assert children[0].values[0].value == "Expr(data.private)"
    assert children[1].values[0].kind == "expression"


def test_expr_template_escapes_do_not_create_bindings() -> None:
    result = _expression(r'Expr(data.value ? `\${data.private} \`文本\`` : "")')
    assert "${data.private}" in result
    assert "`文本`" in result
    assert "/data/calendar/private" not in result


def test_expr_preserves_optional_binding_guard() -> None:
    body = 'Column(\n#if data.value\nText(Expr(data.value + "单位"))\n#endif\n)'
    definition = _definition(body, optional=True)
    root = definition.variants[0].root
    assert _instantiate_blueprint(root, {}).children == ()
    assert _instantiate_blueprint(root, {}, {"value": "${data.calendar.value}"}).children
    with pytest.raises(ValueError):
        _definition('Column(Text(Expr(data.value + "单位")))', optional=True)


@pytest.mark.parametrize(
    "expression",
    (
        "Expr()",
        "Expr(1 + 2)",
        'Expr("data.value")',
        "Expr(data.missing)",
        "Expr(props.value)",
        "Expr(fetch(data.value))",
        "Expr(data.value.toString())",
        "Expr(data.value = 1)",
        "Expr(data.value, 1)",
        "Expr(data.value ? 1)",
        "Expr(data.value + {a: 1})",
        "Expr(data.value[0])",
        "Expr(data.value; evil())",
        "Expr(${/data/private})",
        "Expr($__dataModel.data.private)",
        'Expr(data.value ? `${props.value}` : "")',
        'Expr(data.value ? `${data.missing}` : "")',
        'Expr(data.value ? `${data.value + 1}` : "")',
        'Expr(data.value ? `${data.value.extra}` : "")',
        'Expr(data.value ? `${/data/private}` : "")',
        "Expr((data.value])",
        "Expr(data.value + (1)",
        'Expr(data.value + "unterminated)',
        'Expr(data.value ? `unclosed : "")',
        r'Expr(data.value + "bad\q")',
        '_CardTplRuntimeExpr("data.value")',
        "SomeExpr(data.value)",
    ),
)
def test_expr_rejects_unsafe_or_invalid_input(expression: str) -> None:
    with pytest.raises(ValueError):
        _definition(f"Column(Text({expression}))")


def test_expr_enforces_a2ui_length_and_depth_limits() -> None:
    too_deep = "(" * 21 + "data.value" + ")" * 21
    too_long = 'data.value + "' + "x" * 2048 + '"'
    too_complex = "!" * 1500 + "data.value"
    for body in (too_deep, too_long, too_complex):
        with pytest.raises(ValueError):
            _expression(f"Expr({body})")
    accepted = "(" * 20 + "data.value" + ")" * 20
    assert "${/data/calendar/value}" in _expression(f"Expr({accepted})")


@pytest.mark.parametrize(
    "body",
    (
        'Column(Text(Expr(data.missing == "" ? "" : data.missing)))',
        'Column(Text(Expr(data.value + data.missing)))',
        'Column({"height": Expr(data.missing == "" ? 54 : 24)}, Text(data.value))',
    ),
)
def test_expr_reports_undeclared_binding_explicitly(body: str) -> None:
    with pytest.raises(ValueError, match="unknown Provider Template data reference.*missing"):
        _definition(body)


@pytest.mark.parametrize("start", ("", "09:00"))
def test_runtime_height_keeps_numeric_branches_and_data_path(start: str) -> None:
    definition = _definition(
        'Column(Row({"height": Expr(data.start == "" ? 54 : 24)}, Text(data.start)))',
        ("start",),
    )
    root = _instantiate_blueprint(
        definition.variants[0].root, {}, {"start": "${data.calendar.start}"}
    )
    a2ui = convert_tersel_to_a2ui(
        _serialize_node(root),
        size="2x2",
        protocol_profile=read_tersel_protocol_profile(),
        task_spec={
            "dataModelSchema": {
                "data": {"calendar": {"start": {"type": "string", "sampleValue": start}}}
            }
        },
    )
    message = json.loads(a2ui.splitlines()[1])
    update = message.get("updateComponents")
    assert isinstance(update, dict)
    components = update.get("components")
    assert isinstance(components, list)
    row = next(component for component in components if component.get("component") == "Row")
    styles = row.get("styles")
    assert isinstance(styles, dict)
    assert styles.get("height") == "{{ ${/data/calendar/start} == '' ? 54 : 24 }}"
    assert not validate_card(dsl_text=a2ui).diagnostics
