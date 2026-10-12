# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Tersel/CardTemplate A2UI 表达式归一化（已场景金样化，Layer C）。

原先 5 个独立用例全部转为场景金样：受支持数据引用形式的归一化结果、
六类静态/可执行语法的拒绝、嵌套深度与 2048 长度上限、嵌套 Text 中
Expr 的完整 A2UI 渲染与卡片校验结果，以及 Provider 表达式走公共归一化
链路的产物与报错，均由 ``tests/goldens/scenarios/`` 下的快照整体冻结。
表达式规则改动后按 golden 工作流 ``check --diff`` / ``bless --declared``
复核；本文件不再保留独立测试函数，pytest 仅通过导入完成场景注册。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from services.card_validation import validate_card
from services.template_generation.engine.a2ui_expression import (
    normalize_tersel_expression,
)
from services.template_generation.engine.cardplan.compiler import (
    _provider_runtime_expression,
)
from services.template_generation.engine.cardplan.models import TemplateValue
from services.template_generation.engine.tersel_converter import (
    convert_tersel_to_a2ui,
)
from services.template_generation.profile import read_tersel_protocol_profile
from services.template_generation.test_support.golden_scenarios import scenario


def _error(build: Callable[[], Any]) -> dict[str, str]:
    """执行构建并冻结错误类型与报错文案；未抛错时返回哨兵。"""
    try:
        build()
    except Exception as exc:  # noqa: BLE001 - 错误本身就是被冻结的产物
        return {"errorType": type(exc).__name__, "message": str(exc)}
    return {"error": "NO_ERROR"}


_MIXED_FORM = (
    "size(${data.items}) > 0 && $__dataModel.data.connected ? ${/data/score} * 2 : 0"
)


@scenario("a2ui_expression__normalize_forms")
def _build_normalize_forms() -> dict[str, Any]:
    expression = normalize_tersel_expression(_MIXED_FORM)
    return {"value": expression.value, "references": list(expression.references)}


_REJECTED_BODIES: tuple[tuple[str, str], ...] = (
    ("static_ternary", "true ? 'on' : 'off'"),
    ("fetch_call", "fetch(${data.value})"),
    ("method_call", "${data.value}.toString()"),
    ("object_literal", "${data.value} + {key: 1}"),
    ("size_two_args", "size(${data.items}, ${data.other})"),
    ("already_wrapped", "{{ ${data.value} }}"),
)


@scenario("a2ui_expression__rejected_syntax")
def _build_rejected_syntax() -> dict[str, Any]:
    return {
        key: _error(lambda body=body: normalize_tersel_expression(body))
        for key, body in _REJECTED_BODIES
    }


@scenario("a2ui_expression__limits")
def _build_limits() -> dict[str, Any]:
    too_deep = "(" * 21 + "${data.value}" + ")" * 21
    too_long = "${data.value} + '" + "x" * 2048 + "'"
    return {
        "nesting": _error(lambda: normalize_tersel_expression(too_deep)),
        "length": _error(lambda: normalize_tersel_expression(too_long)),
    }


_NESTED_EXPR_TASK_SPEC = {
    "dataModelSchema": {
        "data": {
            "items": {"type": "array", "sampleValue": ["A", "B"]},
        }
    }
}
_NESTED_EXPR_SOURCE = (
    'Column("card",Text(Expr("size(${data.items}) > 0 ? \'有数据\' : \'无数据\'"),'
    '"body")); data={"items":["A","B"]}'
)


@scenario("a2ui_expression__nested2_expr_render")
def _build_nested2_expr_render() -> dict[str, Any]:
    a2ui = convert_tersel_to_a2ui(
        _NESTED_EXPR_SOURCE,
        size="2x2",
        protocol_profile=read_tersel_protocol_profile(),
        task_spec=_NESTED_EXPR_TASK_SPEC,
    )
    report = validate_card(dsl_text=a2ui)
    return {
        "a2ui": [json.loads(line) for line in a2ui.splitlines() if line.strip()],
        "validationCodes": sorted({item.code for item in report.diagnostics}),
    }


_SCORE_BINDINGS = {"score": "${data.battery.score}"}


def _score_expression(literal: str) -> TemplateValue:
    return TemplateValue(
        kind="expression",
        items=(
            TemplateValue(kind="binding", name="score"),
            TemplateValue(kind="literal", value=literal),
        ),
    )


@scenario("a2ui_expression__provider_expr")
def _build_provider_expr() -> dict[str, Any]:
    return {
        "normalized": _provider_runtime_expression(
            _score_expression(" <= 20 ? '#FFF9A01E' : '#FF64BB5C'"),
            _SCORE_BINDINGS,
        ),
        "invalid": _error(
            lambda: _provider_runtime_expression(
                _score_expression(" + fetch()"), _SCORE_BINDINGS,
            )
        ),
    }
