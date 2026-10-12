"""无外层引号的模板 Expr 语法、绑定保留及 A2UI 转换回归。

Expr 的确定性渲染结果与报错矩阵已固化为场景金样（Layer C）：
``provider_expr__bare_vs_legacy`` 冻结裸表达式与 legacy 反引号表达式的
逐对渲染等价；``provider_expr__calendar_runtime_a2ui`` 冻结日历 Expr 在
三种 start 样例值下的运行时文本与校验诊断（样例值不得内联、路径保留）；
``provider_expr__literal_render`` 冻结引号字面量、可选绑定守卫、模板串
字符串拼接与转义序列的完整渲染；``provider_expr__value_kinds`` 冻结编译期
条件/表达式/插值的类型判定与多行体、正文内同名调用忽略；
``provider_expr__deferred_binding`` 冻结绑定名与符号化路径的延迟解析；
``provider_expr__optional_guard`` 冻结 #if 可选绑定的实例化输出与未守卫
报错；``provider_expr__rejected_input``、``provider_expr__limits_matrix``、
``provider_expr__unknown_binding`` 冻结不安全/非法语法、长度深度复杂度
上限与未声明绑定的精确报错类型与文案；``provider_expr__runtime_height``
冻结数值分支 style 高度的运行时渲染。原文件全部测试函数均已转换为金样，
仅保留场景比对入口。引擎改动后按 golden 工作流 `check --diff` /
`bless --declared` 复核。
"""

from __future__ import annotations

import json
from typing import Any, Callable

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
from services.template_generation.test_support.golden_scenarios import (
    assert_golden_scenario,
    scenario,
)


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


def _capture(build: Callable[[], Any]) -> dict[str, Any]:
    try:
        return {"error": "NO_ERROR", "result": build()}
    except Exception as exc:  # noqa: BLE001 - 场景金样冻结精确错误类型与文案
        return {"errorType": type(exc).__name__, "message": str(exc)}


def _convert_a2ui(node: Any, task_spec: dict[str, Any]) -> str:
    return convert_tersel_to_a2ui(
        _serialize_node(node),
        size="2x2",
        protocol_profile=read_tersel_protocol_profile(),
        task_spec=task_spec,
    )


def _diagnostics(a2ui: str) -> list[dict[str, str]]:
    return [
        {"severity": item.severity, "code": item.code, "message": item.message}
        for item in validate_card(dsl_text=a2ui).diagnostics
    ]


def _update_components(a2ui: str) -> list[dict[str, Any]]:
    message = json.loads(a2ui.splitlines()[1])
    update = message.get("updateComponents")
    assert isinstance(update, dict)
    components = update.get("components")
    assert isinstance(components, list)
    return components


_BARE_LEGACY_CASES = (
    ("identity", "data.value", "${data.value}"),
    ("arithmetic", "data.value * 2 + 1", "${data.value} * 2 + 1"),
    ("fraction", "'' + ((data.value + 0.5) % 1)", "'' + ((${data.value} + 0.5) % 1)"),
    (
        "ternary_empty",
        'data.value == "" ? "空" : data.value',
        "${data.value} == '' ? '空' : ${data.value}",
    ),
    ("size_and", "size(data.value) > 0 && true", "size(${data.value}) > 0 && true"),
    ("not_or", "!(data.value > 0) || false", "!(${data.value} > 0) || false"),
    (
        "nested_ternary",
        "data.value > 1 ? 2 : data.value > 0 ? 1 : 0",
        "${data.value} > 1 ? 2 : ${data.value} > 0 ? 1 : 0",
    ),
)


@scenario("provider_expr__bare_vs_legacy")
def _build_bare_vs_legacy() -> dict[str, dict[str, str]]:
    return {
        slug: {
            "bare": _expression(f"Expr({bare})"),
            "legacy": _expression(f"Expr(`{legacy}`)"),
        }
        for slug, bare, legacy in _BARE_LEGACY_CASES
    }


_CALENDAR_EXPRESSIONS = (
    ("template_literal", 'Expr(data.start == "" ? "" : `${data.start} - ${data.end}`)'),
    ("string_concat", 'Expr(data.start == "" ? "" : data.start + " - " + data.end)'),
)
_CALENDAR_STARTS = (("empty", ""), ("time", "09:00"), ("other", "其他值"))


def _calendar_a2ui(expression: str, start: str) -> str:
    definition = _definition(f"Column(Text({expression}))", ("start", "end"))
    bindings = {"start": "${data.calendar.start}", "end": "${data.calendar.end}"}
    node = _instantiate_blueprint(definition.variants[0].root, {}, bindings)
    return _convert_a2ui(node, {
        "dataModelSchema": {
            "data": {
                "calendar": {
                    "start": {"type": "string", "sampleValue": start},
                    "end": {"type": "string", "sampleValue": "10:00"},
                }
            }
        },
    })


@scenario("provider_expr__calendar_runtime_a2ui")
def _build_calendar_runtime() -> dict[str, dict[str, Any]]:
    payload: dict[str, dict[str, Any]] = {}
    for expr_slug, expression in _CALENDAR_EXPRESSIONS:
        for start_slug, start in _CALENDAR_STARTS:
            a2ui = _calendar_a2ui(expression, start)
            payload[f"{expr_slug}__{start_slug}"] = {
                "text": _update_components(a2ui)[1]["content"],
                "diagnostics": _diagnostics(a2ui),
            }
    return payload


@scenario("provider_expr__literal_render")
def _build_literal_render() -> dict[str, str]:
    return {
        "quotedLiterals": _expression(
            r"""Expr(data.value + "Expr(fake) data.start ${data.end} ) #Expr(" + "a\"b\\c\n")"""
        ),
        "optionalLiteral": _expression('Expr(data.value + "props?.label")'),
        "templateCoercion": _expression(
            'Expr(size(`数值 ${data.value}`) > 0 ? `${data.value}${data.value}` : "")'
        ),
        "escapeSequences": _expression(r'Expr(data.value ? `\${data.private} \`文本\`` : "")'),
    }


@scenario("provider_expr__value_kinds")
def _build_value_kinds() -> dict[str, Any]:
    coexistence = _definition(
        'Column(Text(#Expr(data.value ? data.value : "缺失")), '
        'Text(Expr(data.value == "" ? "空" : data.value)), Text(`${data.value} 后缀`))'
    )
    multiline = _definition(
        'Column(\n# ignored Expr( " `\nText("Expr(data.private)"),\n'
        'Text(Expr (\n  size(data.value) > 0\n  ? data.value\n  : "空"\n)))'
    )
    children = coexistence.variants[0].root.children
    multiline_children = multiline.variants[0].root.children
    return {
        "compileTimeCoexistence": [
            children[0].values[0].kind,
            children[1].values[0].kind,
            children[2].values[0].kind,
        ],
        "multilineIgnoredCallText": multiline_children[0].values[0].value,
        "multilineExprKind": multiline_children[1].values[0].kind,
    }


@scenario("provider_expr__deferred_binding")
def _build_deferred_binding() -> dict[str, Any]:
    definition = _definition('Column(Text(Expr(data.value + "单位")))')
    expression = definition.variants[0].root.children[0].values[0]
    return {
        "bindings": [
            item.name for item in expression.items if item.kind == "binding"
        ],
        "rendered": {
            path: _provider_runtime_expression(expression, {"value": "${" + path + "}"})
            for path in ("data.first.value", "data.second.nested.value")
        },
    }


@scenario("provider_expr__optional_guard")
def _build_optional_guard() -> dict[str, Any]:
    body = 'Column(\n#if data.value\nText(Expr(data.value + "单位"))\n#endif\n)'
    definition = _definition(body, optional=True)
    root = definition.variants[0].root
    empty = _instantiate_blueprint(root, {})
    bound = _instantiate_blueprint(root, {}, {"value": "${data.calendar.value}"})
    return {
        "emptyBindingsSerialized": _serialize_node(empty),
        "boundSerialized": _serialize_node(bound),
        "unguardedError": _capture(
            lambda: _definition('Column(Text(Expr(data.value + "单位")))', optional=True)
        ),
    }


_REJECTED_EXPRESSIONS = (
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
)


@scenario("provider_expr__rejected_input")
def _build_rejected_input() -> dict[str, dict[str, str]]:
    return {
        expression: _capture(lambda e=expression: _definition(f"Column(Text({e}))"))
        for expression in _REJECTED_EXPRESSIONS
    }


@scenario("provider_expr__limits_matrix")
def _build_limits_matrix() -> dict[str, dict[str, str]]:
    too_deep = "(" * 21 + "data.value" + ")" * 21
    too_long = 'data.value + "' + "x" * 2048 + '"'
    too_complex = "!" * 1500 + "data.value"
    accepted = "(" * 20 + "data.value" + ")" * 20
    return {
        "tooDeep": _capture(lambda: _expression(f"Expr({too_deep})")),
        "tooLong": _capture(lambda: _expression(f"Expr({too_long})")),
        "tooComplex": _capture(lambda: _expression(f"Expr({too_complex})")),
        "acceptedAtLimit": {
            "rendered": _expression(f"Expr({accepted})"),
        },
    }


_UNKNOWN_BINDING_BODIES = (
    ("ternary_missing", 'Column(Text(Expr(data.missing == "" ? "" : data.missing)))'),
    ("sum_missing", 'Column(Text(Expr(data.value + data.missing)))'),
    ("style_missing", 'Column({"height": Expr(data.missing == "" ? 54 : 24)}, Text(data.value))'),
)


@scenario("provider_expr__unknown_binding")
def _build_unknown_binding() -> dict[str, dict[str, str]]:
    return {
        slug: _capture(lambda body=body: _definition(body))
        for slug, body in _UNKNOWN_BINDING_BODIES
    }


@scenario("provider_expr__runtime_height")
def _build_runtime_height() -> dict[str, dict[str, Any]]:
    payload: dict[str, dict[str, Any]] = {}
    for start_slug, start in (("empty", ""), ("time", "09:00")):
        definition = _definition(
            'Column(Row({"height": Expr(data.start == "" ? 54 : 24)}, Text(data.start)))',
            ("start",),
        )
        root = _instantiate_blueprint(
            definition.variants[0].root, {}, {"start": "${data.calendar.start}"}
        )
        a2ui = _convert_a2ui(root, {
            "dataModelSchema": {
                "data": {"calendar": {"start": {"type": "string", "sampleValue": start}}}
            }
        })
        row = next(
            component for component in _update_components(a2ui)
            if component.get("component") == "Row"
        )
        styles = row.get("styles")
        assert isinstance(styles, dict)
        payload[start_slug] = {
            "height": styles.get("height"),
            "diagnostics": _diagnostics(a2ui),
        }
    return payload


def test_provider_runtime_expression_scenarios_match_goldens() -> None:
    assert_golden_scenario("provider_expr__bare_vs_legacy")
    assert_golden_scenario("provider_expr__calendar_runtime_a2ui")
    assert_golden_scenario("provider_expr__literal_render")
    assert_golden_scenario("provider_expr__value_kinds")
    assert_golden_scenario("provider_expr__deferred_binding")
    assert_golden_scenario("provider_expr__optional_guard")
    assert_golden_scenario("provider_expr__rejected_input")
    assert_golden_scenario("provider_expr__limits_matrix")
    assert_golden_scenario("provider_expr__unknown_binding")
    assert_golden_scenario("provider_expr__runtime_height")
