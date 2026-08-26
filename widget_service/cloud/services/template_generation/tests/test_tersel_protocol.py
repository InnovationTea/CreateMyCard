"""Tersel DesignToken、内联样式和兼容入口回归测试。"""

from __future__ import annotations

import json
from typing import Any

import pytest

from services.protocol_registry import (
    TERSE_DSL_NESTED2_PROFILE_ID,
    A2UIProtocolRegistry,
)
from services.template_generation.engine.terse_dsl_nested2_converter import (
    TerseDslNested2ConversionError,
    convert_tersel_to_a2ui,
    parse_tersel,
)


@pytest.mark.parametrize(
    ("source", "expected_root_values", "expected_text_values"),
    [
        (
            'Column("Compact",Text("hello world","title"))',
            ("Compact",),
            ("hello world", "title"),
        ),
        (
            'Column("Compact",{"width":120},'
            'Text("hello world","title",{"fontColor":"#FF1122"}))',
            ("Compact", {"width": 120}),
            ("hello world", "title", {"fontColor": "#FF1122"}),
        ),
        (
            'Column({"width":120},'
            'Text("hello world",{"fontColor":"#FF1122","fontSize":30}))',
            ({"width": 120},),
            ("hello world", {"fontColor": "#FF1122", "fontSize": 30}),
        ),
    ],
)
def test_tersel_parser_accepts_design_token_and_inline_style_options(
    source: str,
    expected_root_values: tuple[Any, ...],
    expected_text_values: tuple[Any, ...],
) -> None:
    root = parse_tersel(source)

    assert root.values == expected_root_values
    assert root.children[0].values == expected_text_values


def test_tersel_converter_merges_design_token_before_inline_styles() -> None:
    profile = A2UIProtocolRegistry.read_design_protocol_profile(
        TERSE_DSL_NESTED2_PROFILE_ID
    )
    source = (
        'Column("card",Column("Compact",{"itemMargin":9},'
        'Text("token only","title"),'
        'Text("token and inline","title",{"fontColor":"#FF1122"}),'
        'Text("inline only",{"fontColor":"#FF3344","fontSize":30})))'
    )

    a2ui = convert_tersel_to_a2ui(
        source,
        size="2x2",
        protocol_profile=profile,
    )
    messages = [json.loads(line) for line in a2ui.splitlines()]
    components = messages[1]["updateComponents"]["components"]
    nested_column = components[1]
    token_only = components[2]
    token_and_inline = components[3]
    inline_only = components[4]

    assert nested_column["styles"]["width"] == "matchParent"
    assert nested_column["itemMargin"] == 9
    assert token_only["styles"]["fontSize"] == 20
    assert token_only["styles"]["fontWeight"] == 700
    assert token_and_inline["styles"]["fontColor"] == "#FF1122"
    assert inline_only["styles"]["fontColor"] == "#FF3344"
    assert inline_only["styles"]["fontSize"] == 30
    assert "fontWeight" not in inline_only["styles"]


def test_tersel_theme_reference_is_resolved_inside_inline_styles() -> None:
    values = {
        "primaryColor": "#FF112233",
        "supportContentColor": "#99112233",
        "actionStyle.backgroundColor": "#33FFFFFF",
        "actionStyle.contentColor": "#FFCCDDEE",
    }
    root = parse_tersel(
        'Column({"backgroundColor":$theme("actionStyle.backgroundColor")},'
        'Text("主内容",{"fontColor":$theme("primaryColor")}),'
        'Text("辅助内容",{"fontColor":$theme("supportContentColor")}))',
        theme_values=values,
    )

    assert root.values == ({"backgroundColor": "#33FFFFFF"},)
    assert root.children[0].values[-1]["fontColor"] == "#FF112233"
    assert root.children[1].values[-1]["fontColor"] == "#99112233"


@pytest.mark.parametrize(
    ("source", "error"),
    [
        (
            'Column({"backgroundColor":$theme("unknownColor")})',
            "approved Theme path",
        ),
        (
            'Column({"backgroundColor":$theme("primaryColor")})',
            "Theme reference is unavailable",
        ),
        (
            'Column({"backgroundColor":_TerselTheme("primaryColor")})',
            "reserved internal name",
        ),
    ],
)
def test_tersel_theme_reference_is_closed_and_requires_selected_theme(
    source: str,
    error: str,
) -> None:
    with pytest.raises(TerseDslNested2ConversionError, match=error):
        parse_tersel(source)


def test_tersel_rejects_unknown_component_design_token() -> None:
    profile = A2UIProtocolRegistry.read_design_protocol_profile(
        TERSE_DSL_NESTED2_PROFILE_ID
    )

    with pytest.raises(TerseDslNested2ConversionError, match="designToken"):
        convert_tersel_to_a2ui(
            'Column("card",Text("hello","not-a-token"))',
            size="2x2",
            protocol_profile=profile,
        )
