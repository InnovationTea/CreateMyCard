"""编译期 elseif 的顺序、作用域和端侧运行时边界（场景金样化）。

指令对解析矩阵（``provider_elseif__directive_pairs``）、四组错误路径
（非法目标 ``invalid_target_errors``、无守卫引用 ``unguarded_references``、
跨分支借用 ``branch_scoping``、畸形指令 ``malformed_directives``，错误类型
与消息整体入快照）、各选择矩阵（取反绑定、取反参数、elseif 首个可用分支
16 组合、参数 presence、分组守卫、嵌套兄弟顺序、空分支、无 else）、多行
字面量内的伪指令（``multiline_literal``）与端侧 A2UI 路径/运行时表达式/
校验诊断（``runtime_a2ui_paths``）均固化为场景金样（Layer C）；改动后按
golden 工作流 `check --diff` / `bless --declared` 复核。
保留普通测试：``_template_directive_components`` 的单一 return 出口 AST
不变量（代码检查约束，非渲染产物）。
"""

from __future__ import annotations

import ast
import inspect
import json
from collections.abc import Callable
from itertools import product
from typing import Any

import pytest

from services.card_validation import validate_card
from services.template_generation.engine.cardplan.compiler import (
    _instantiate_blueprint,
    _serialize_node,
)
from services.template_generation.engine.cardplan.models import TemplateDefinition
from services.template_generation.engine.cardplan.provider_bundle import (
    _parse_component_body,
    _template_directive_components,
    compile_card_template,
)
from services.template_generation.engine.tersel_converter import Nested2Node, convert_tersel_to_a2ui
from services.template_generation.profile import read_tersel_protocol_profile
from services.template_generation.test_support.golden_scenarios import (
    assert_golden_scenario,
    scenario,
)

_NAMES = ("first", "second", "third")
_PRESENCE_STATES = ("present", "none", "missing")


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


def _selected(root: Nested2Node) -> dict[str, Any]:
    """固化一个实例化结果：命中的 Text 值与整棵序列化树（含守卫消失语义）。"""
    return {"texts": _texts(root), "serialized": _serialize_node(root)}


def _error_payload(build: Callable[[], object]) -> dict[str, str]:
    """执行构建并固化错误类型与消息；未抛错时写入哨兵值。"""
    try:
        build()
    except Exception as error:  # noqa: BLE001 - 快照要冻结的正是错误本身
        return {"errorType": type(error).__name__, "message": str(error)}
    return {"error": "NO_ERROR"}


# --------------------------------------------------------------------------
# 指令对解析（#if/#elseif 共用同一目标解析器）
# --------------------------------------------------------------------------

_DIRECTIVE_KEYWORDS = ("if", "elseif")

_PAIR_TARGETS: tuple[tuple[str, str], ...] = (
    ("bind_first", "data.first"),
    ("param_flag", "props.flag"),
    ("negated_bind_first", "!data.first"),
    ("negated_param_flag", "! props.flag"),
    ("grouped_first_second", "data.first && data.second"),
)


@scenario("provider_elseif__directive_pairs")
def _build_directive_pairs() -> dict[str, list[str]]:
    return {
        f"{keyword}__{slug}": list(
            _template_directive_components(f"#{keyword} {target}", 23)
        )
        for keyword in _DIRECTIVE_KEYWORDS
        for slug, target in _PAIR_TARGETS
    }


_INVALID_TARGETS: tuple[tuple[str, str], ...] = (
    ("duplicate_binding", "data.first && data.first"),
    ("mixed_namespaces", "data.first && props.flag"),
    ("disjunction", "data.first || data.second"),
    ("double_negation", "!!data.first"),
    ("nested_path", "data.first.value"),
)


@scenario("provider_elseif__invalid_target_errors")
def _build_invalid_target_errors() -> dict[str, dict[str, str]]:
    return {
        f"{keyword}__{slug}": _error_payload(
            lambda keyword=keyword, target=target: _template_directive_components(
                f"#{keyword} {target}", 23
            )
        )
        for keyword in _DIRECTIVE_KEYWORDS
        for slug, target in _INVALID_TARGETS
    }


# --------------------------------------------------------------------------
# 错误路径（模板编译期）
# --------------------------------------------------------------------------

_UNGUARDED_BODIES: tuple[tuple[str, str], ...] = (
    ("unguarded_binding_reference", "#if !data.first\nText(data.first)\n#endif"),
    ("unguarded_param_reference", "#if !props.label\nText(props.label)\n#endif"),
    ("unknown_binding", '#if !data.unknown\nText("未知")\n#endif'),
    ("unknown_param", '#if !props.unknown\nText("未知")\n#endif'),
    ("double_negation", '#if !!data.first\nText("重复")\n#endif'),
    ("single_ampersand", '#if !data.first & props.label\nText("混合")\n#endif'),
    ("mixed_namespace_group", '#if !data.first && props.label\nText("混合")\n#endif'),
)


@scenario("provider_elseif__unguarded_references")
def _build_unguarded_references() -> dict[str, dict[str, str]]:
    return {
        slug: _error_payload(lambda body=body: _definition(body))
        for slug, body in _UNGUARDED_BODIES
    }


_BORROW_BODIES: tuple[tuple[str, str], ...] = (
    (
        "reuse_first_binding",
        "#if data.first\nText(data.first)\n#elseif data.second\nText(data.first)\n#endif",
    ),
    (
        "borrow_other_binding",
        "#if data.first\nText(data.first)\n#elseif data.second\nText(data.third)\n#endif",
    ),
    (
        "borrow_param_reference",
        "#if props.label\nText(props.label)\n#elseif data.second\nText(props.label)\n#endif",
    ),
    (
        "unknown_binding_in_elseif",
        '#if data.first\nText(data.first)\n#elseif data.unknown\nText("未知")\n#endif',
    ),
    (
        "unknown_param_in_elseif",
        '#if data.first\nText(data.first)\n#elseif props.unknown\nText("未知")\n#endif',
    ),
)


@scenario("provider_elseif__branch_scoping")
def _build_branch_scoping() -> dict[str, dict[str, str]]:
    return {
        slug: _error_payload(lambda body=body: _definition(body))
        for slug, body in _BORROW_BODIES
    }


_MALFORMED_BODIES: tuple[tuple[str, str], ...] = (
    ("elseif_without_if", '#elseif data.first\nText("无 if")'),
    (
        "else_if_after_else",
        '#if data.first\nText("首选")\n#else\nText("后备")\n#elseif data.second\n#end',
    ),
    ("double_else", "#if data.first\n#elseif data.second\n#else\n#else\n#end"),
    ("unterminated_chain", "#if data.first\n#elseif data.second"),
    ("elseif_without_target", "#if data.first\n#elseif\n#end"),
    ("elseif_nested_path", "#if data.first\n#elseif data.second.value\n#end"),
    ("elseif_disjunction", "#if data.first\n#elseif data.second || data.third\n#end"),
    ("elseif_mixed_namespaces", "#if data.first\n#elseif data.second && props.label\n#end"),
    (
        "elseif_triple_group",
        "#if data.first\n#elseif data.first && data.second && data.third\n#end",
    ),
    ("elseif_duplicate_group", "#if data.first\n#elseif data.second && data.second\n#end"),
    ("elseif_expression_call", "#if data.first\n#elseif Expr(data.second)\n#end"),
    ("elseif_comparison", "#if data.first\n#elseif data.second == 0\n#end"),
    ("trailing_text_after_end", "#if data.first\n#elseif data.second\n#end extra"),
    ("trailing_text_after_endif", "#if data.first\n#elseif data.second\n#endif extra"),
    ("lone_end", "#end"),
    ("lone_endif", "#endif"),
)


@scenario("provider_elseif__malformed_directives")
def _build_malformed_directives() -> dict[str, dict[str, str]]:
    return {
        slug: _error_payload(
            lambda body=body: _parse_component_body("Column(\n" + body + "\n)")
        )
        for slug, body in _MALFORMED_BODIES
    }


# --------------------------------------------------------------------------
# 选择矩阵（实例化期）
# --------------------------------------------------------------------------

_NEGATED_PREFIXES: tuple[tuple[str, str], ...] = (
    ("leading_if", "#if"),
    ("after_first_branch", '#if props.flag\nText("首选")\n#elseif'),
)
_NEGATED_SPACINGS: tuple[tuple[str, str], ...] = (("tight", ""), ("spaced", " "))
_BINDING_STATES = ("absent", "present")


@scenario("provider_elseif__negated_binding_selection")
def _build_negated_binding_selection() -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for prefix_slug, prefix in _NEGATED_PREFIXES:
        for spacing_slug, spacing in _NEGATED_SPACINGS:
            for state in _BINDING_STATES:
                definition = _definition(
                    f'{prefix} !{spacing}data.first\nText("缺失")\n'
                    '#else\nText(data.first)\n#end'
                )
                bindings = _bindings(("first",)) if state == "present" else {}
                root = _instantiate_blueprint(definition.variants[0].root, {}, bindings)
                payload[f"{prefix_slug}__{spacing_slug}__{state}"] = _selected(root)
    return payload


_FALSY_PARAMS: tuple[tuple[str, object], ...] = (
    ("label", ""),
    ("flag", False),
    ("count", 0),
)


def _params_for_state(name: str, value: object, state: str) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if state == "present":
        params[name] = value
    elif state == "none":
        params[name] = None
    return params


@scenario("provider_elseif__negated_prop_presence")
def _build_negated_prop_presence() -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for name, value in _FALSY_PARAMS:
        definition = _definition(
            f'#if !props.{name}\nText("缺失")\n#else\nText("存在")\n#endif'
        )
        for state in _PRESENCE_STATES:
            root = _instantiate_blueprint(
                definition.variants[0].root, _params_for_state(name, value, state)
            )
            payload[f"{name}__{state}"] = _selected(root)
    return payload


@scenario("provider_elseif__elseif_first_available")
def _build_elseif_first_available() -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for ending_slug, ending in (("end", "#end"), ("endif", "#endif")):
        definition = _definition(
            "#if data.first\nText(data.first)\n"
            "#elseif data.second\nText(data.second)\n"
            '#elseif data.third\nText(data.third)\n#else\nText("无数据")\n' + ending
        )
        for available in product((False, True), repeat=3):
            names = tuple(
                name for name, present in zip(_NAMES, available, strict=True) if present
            )
            root = _instantiate_blueprint(
                definition.variants[0].root, {}, _bindings(names)
            )
            key = ending_slug + "__" + ("_".join(names) if names else "none")
            payload[key] = _selected(root)
    return payload


@scenario("provider_elseif__elseif_prop_presence")
def _build_elseif_prop_presence() -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for name, value in _FALSY_PARAMS:
        definition = _definition(
            '#if data.first\nText("首选")\n'
            f'#elseif props.{name}\nText("参数分支")\n'
            '#elseif data.second\nText("数据分支")\n#end'
        )
        for state in _PRESENCE_STATES:
            root = _instantiate_blueprint(
                definition.variants[0].root,
                _params_for_state(name, value, state),
                _bindings(("second",)),
            )
            payload[f"{name}__{state}"] = _selected(root)
    return payload


_GROUPED_NAME_CASES: tuple[tuple[str, ...], ...] = (
    (),
    ("first",),
    ("second",),
    ("first", "second"),
)


@scenario("provider_elseif__grouped_guard")
def _build_grouped_guard() -> dict[str, Any]:
    definition = _definition(
        '#if props.flag\nText("标记")\n'
        "#elseif data.first && data.second\nText(data.first),\nText(data.second)\n"
        '#elseif data.second\nText(data.second)\n#else\nText("无数据")\n#endif'
    )
    payload: dict[str, Any] = {}
    for names in _GROUPED_NAME_CASES:
        root = _instantiate_blueprint(definition.variants[0].root, {}, _bindings(names))
        payload["_".join(names) if names else "none"] = _selected(root)
    return payload


_NESTED_CASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("none", ()),
    ("second", ("second",)),
    ("second_third", ("second", "third")),
    ("first", ("first",)),
)


@scenario("provider_elseif__nested_sibling_order")
def _build_nested_sibling_order() -> dict[str, Any]:
    definition = _definition(
        'Text("前"),\n#if data.first\nText("外命中")\n#elseif data.second\n'
        '#if data.first\nText("内首选")\n#elseif data.third\nText("内命中")\n'
        '#else\nText("内后备")\n#endif\n#else\nText("外后备")\n#end\nText("后")'
    )
    payload: dict[str, Any] = {}
    for slug, names in _NESTED_CASES:
        root = _instantiate_blueprint(definition.variants[0].root, {}, _bindings(names))
        payload[slug] = _selected(root)
    return payload


@scenario("provider_elseif__empty_branch")
def _build_empty_branch() -> dict[str, Any]:
    definition = _definition(
        '#if data.first\n#elseif data.second\n#elseif data.third\nText("第三")\n'
        '#else\nText("后备")\n#end'
    )
    payload: dict[str, Any] = {}
    for empty_branch in ("first", "second"):
        root = _instantiate_blueprint(
            definition.variants[0].root, {}, _bindings((empty_branch, "third"))
        )
        payload[empty_branch] = _selected(root)
    return payload


@scenario("provider_elseif__no_else")
def _build_no_else() -> dict[str, Any]:
    definition = _definition(
        "#if data.first\nText(data.first)\n#elseif data.second\nText(data.second)\n#end"
    )
    root = _instantiate_blueprint(definition.variants[0].root, {})
    return _selected(root)


@scenario("provider_elseif__multiline_literal")
def _build_multiline_literal() -> dict[str, Any]:
    definition = _definition(
        '#if data.first\nText(Expr(data.first ? `说明\n#elseif data.second\n#end` : ""))\n'
        "#elseif data.second\nText(data.second)\n#endif"
    )
    root = _instantiate_blueprint(definition.variants[0].root, {}, _bindings(("first",)))
    return _selected(root)


# --------------------------------------------------------------------------
# 端侧运行时（A2UI 转换 + 校验）
# --------------------------------------------------------------------------

@scenario("provider_elseif__runtime_a2ui_paths")
def _build_runtime_a2ui_paths() -> dict[str, Any]:
    definition = _definition(
        '#if props.flag\nText("标记")\n#elseif data.first\n'
        'Text(Expr(data.first == "" ? "空值" : data.first))\n'
        '#else\nText("无绑定")\n#end'
    )
    root = _instantiate_blueprint(definition.variants[0].root, {}, _bindings(("first",)))
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
    reporter = validate_card(dsl_text=a2ui)
    message = json.loads(a2ui.splitlines()[1])
    return {
        "rootChild": root.children[0].component_type,
        "membership": {
            "resolvedBindingPath": "${/data/context/first}" in a2ui,
            "runtimeExpression": " == '' ? '空值' : " in a2ui,
            "unmatchedElseTextAbsent": "无绑定" not in a2ui,
            "directiveMarkersAbsent": "IfMissing" not in a2ui,
        },
        "diagnostics": [item.to_json() for item in reporter.diagnostics],
        "updateComponents": message.get("updateComponents"),
    }


_SCENARIO_IDS = (
    "provider_elseif__directive_pairs",
    "provider_elseif__invalid_target_errors",
    "provider_elseif__unguarded_references",
    "provider_elseif__branch_scoping",
    "provider_elseif__malformed_directives",
    "provider_elseif__negated_binding_selection",
    "provider_elseif__negated_prop_presence",
    "provider_elseif__elseif_first_available",
    "provider_elseif__elseif_prop_presence",
    "provider_elseif__grouped_guard",
    "provider_elseif__nested_sibling_order",
    "provider_elseif__empty_branch",
    "provider_elseif__no_else",
    "provider_elseif__multiline_literal",
    "provider_elseif__runtime_a2ui_paths",
)


@pytest.mark.parametrize("scenario_id", _SCENARIO_IDS)
def test_provider_elseif_scenarios_match_goldens(scenario_id: str) -> None:
    assert_golden_scenario(scenario_id)


def test_directive_components_keep_one_return_for_codecheck() -> None:
    """固定单一返回出口，防止再次混用条件表达式和二元组返回。"""
    function = ast.parse(inspect.getsource(_template_directive_components)).body[0]
    returns = [node for node in ast.walk(function) if isinstance(node, ast.Return)]
    assert len(returns) == 1
