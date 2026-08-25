# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""A2UI Form expression normalization tests."""

from __future__ import annotations

import json

import pytest

from services.a2ui_expression import A2UIExpressionError, normalize_terse_expression
from services.card_validation import validate_card
from services.protocol_registry import (
    TERSE_DSL_NESTED2_PROFILE_ID,
    A2UIProtocolRegistry,
)
from services.template_generation.engine.cardplan.compiler import (
    _provider_runtime_expression,
)
from services.template_generation.engine.cardplan.models import TemplateValue
from services.template_generation.engine.terse_dsl_nested2_converter import (
    TerseDslNested2ConversionError,
    convert_terse_dsl_nested2_to_a2ui,
)


def test_expression_normalizes_supported_data_reference_forms() -> None:
    expression = normalize_terse_expression(
        "size(${data.items}) > 0 && $__dataModel.data.connected ? ${/data/score} * 2 : 0"
    )

    assert expression.value == (
        "{{ size(${/data/items}) > 0 && ${/data/connected} ? ${/data/score} * 2 : 0 }}"
    )
    assert expression.references == (
        "/data/items",
        "/data/connected",
        "/data/score",
    )


@pytest.mark.parametrize(
    "body",
    [
        "true ? 'on' : 'off'",
        "fetch(${data.value})",
        "${data.value}.toString()",
        "${data.value} + {key: 1}",
        "size(${data.items}, ${data.other})",
        "{{ ${data.value} }}",
    ],
)
def test_expression_rejects_static_or_executable_syntax(body: str) -> None:
    with pytest.raises(A2UIExpressionError):
        normalize_terse_expression(body)


def test_expression_enforces_form_length_and_nesting_limits() -> None:
    too_deep = "(" * 21 + "${data.value}" + ")" * 21
    too_long = "${data.value} + '" + "x" * 2048 + "'"

    with pytest.raises(A2UIExpressionError, match="nesting exceeds"):
        normalize_terse_expression(too_deep)
    with pytest.raises(A2UIExpressionError, match="2048-character"):
        normalize_terse_expression(too_long)


def test_template_nested2_converts_expr_and_container_size() -> None:
    profile = A2UIProtocolRegistry.read_design_protocol_profile(
        TERSE_DSL_NESTED2_PROFILE_ID
    )
    task_spec = {
        "dataModelSchema": {
            "data": {
                "items": {"type": "array", "sampleValue": ["A", "B"]},
            }
        }
    }
    source = (
        'Column("card",Text(Expr("size(${data.items}) > 0 ? \'有数据\' : \'无数据\'"),'
        '"body")); data={"items":["A","B"]}'
    )

    a2ui = convert_terse_dsl_nested2_to_a2ui(
        source,
        size="2x2",
        protocol_profile=profile,
        task_spec=task_spec,
    )
    messages = [json.loads(line) for line in a2ui.splitlines()]
    text_component = messages[1]["updateComponents"]["components"][1]

    assert text_component["content"] == (
        "{{ size(${/data/items}) > 0 ? '有数据' : '无数据' }}"
    )
    assert validate_card(dsl_text=a2ui).diagnostics == []


def test_provider_expr_uses_shared_a2ui_expression_rules() -> None:
    expression = TemplateValue(
        kind="expression",
        items=(
            TemplateValue(kind="binding", name="score"),
            TemplateValue(
                kind="literal",
                value=" <= 20 ? '#FFF9A01E' : '#FF64BB5C'",
            ),
        ),
    )

    assert _provider_runtime_expression(
        expression,
        {"score": "${data.battery.score}"},
    ) == (
        "{{ ${/data/battery/score} <= 20 ? '#FFF9A01E' : '#FF64BB5C' }}"
    )

    invalid_expression = TemplateValue(
        kind="expression",
        items=(
            TemplateValue(kind="binding", name="score"),
            TemplateValue(kind="literal", value=" + fetch()"),
        ),
    )
    with pytest.raises(TerseDslNested2ConversionError, match="valid A2UI expression"):
        _provider_runtime_expression(
            invalid_expression,
            {"score": "${data.battery.score}"},
        )
