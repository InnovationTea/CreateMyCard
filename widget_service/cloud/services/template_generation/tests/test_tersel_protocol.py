# -*- coding: utf-8 -*-
"""模板内部 Tersel DesignToken 与内联样式回归（已场景金样化，Layer C）。

原先 6 个独立用例全部转为场景金样：DesignToken 与内联样式的解析树、
DesignToken 先合并内联样式覆盖的完整 A2UI 消息、``$theme`` 引用在解析
期的解析结果，以及各封闭性错误（未批准 Theme 路径、未选主题、保留内部
名、未知组件 designToken、云端 FusionBall 组件）的类型与报错文案，均由
``tests/goldens/scenarios/`` 下的快照整体冻结。引擎或协议改动后按
golden 工作流 ``check --diff`` / ``bless --declared`` 复核；本文件不再
保留独立测试函数，pytest 仅通过导入完成场景注册。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from services.template_generation.engine.tersel_converter import (
    Nested2Node,
    convert_tersel_to_a2ui,
    parse_tersel,
)
from services.template_generation.profile import read_tersel_protocol_profile
from services.template_generation.test_support.golden_scenarios import scenario


def _dump_tree(node: Nested2Node) -> dict[str, Any]:
    """把解析树整理成可冻结的 canonical 结构（值 + 子树）。"""
    return {
        "component": node.component_type,
        "values": list(node.values),
        "children": [_dump_tree(child) for child in node.children],
    }


def _error(build: Callable[[], Any]) -> dict[str, str]:
    """执行构建并冻结错误类型与报错文案；未抛错时返回哨兵。"""
    try:
        build()
    except Exception as exc:  # noqa: BLE001 - 错误本身就是被冻结的产物
        return {"errorType": type(exc).__name__, "message": str(exc)}
    return {"error": "NO_ERROR"}


_DESIGN_TOKEN_SOURCES: tuple[tuple[str, str], ...] = (
    ("design_token", 'Column("Compact",Text("hello world","title"))'),
    (
        "token_and_inline",
        'Column("Compact",{"width":120},'
        'Text("hello world","title",{"fontColor":"#FF1122"}))',
    ),
    (
        "inline_only",
        'Column({"width":120},'
        'Text("hello world",{"fontColor":"#FF1122","fontSize":30}))',
    ),
)


@scenario("tersel_protocol__parse_design_token")
def _build_parse_design_token() -> dict[str, Any]:
    return {
        key: _dump_tree(parse_tersel(source))
        for key, source in _DESIGN_TOKEN_SOURCES
    }


_MERGE_SOURCE = (
    'Column("card",Column("Compact",{"itemMargin":9},'
    'Text("token only","title"),'
    'Text("token and inline","title",{"fontColor":"#FF1122"}),'
    'Text("inline only",{"fontColor":"#FF3344","fontSize":30})))'
)


@scenario("tersel_protocol__merge_token_inline")
def _build_merge_token_inline() -> dict[str, Any]:
    a2ui = convert_tersel_to_a2ui(
        _MERGE_SOURCE,
        size="2x2",
        protocol_profile=read_tersel_protocol_profile(),
    )
    return {
        "a2ui": [json.loads(line) for line in a2ui.splitlines() if line.strip()],
    }


_THEME_VALUES = {
    "primaryColor": "#FF112233",
    "supportContentColor": "#99112233",
    "progressColor": "#FF445566",
    "actionStyle.backgroundColor": "#33FFFFFF",
    "actionStyle.contentColor": "#FFCCDDEE",
}
_THEME_SOURCE = (
    'Column({"backgroundColor":$theme("actionStyle.backgroundColor")},'
    'Text("主内容",{"fontColor":$theme("primaryColor")}),'
    'Text("辅助内容",{"fontColor":$theme("supportContentColor")}),'
    'Progress({"value":50,"total":100,"color":$theme("progressColor")}))'
)


@scenario("tersel_protocol__theme_resolution")
def _build_theme_resolution() -> dict[str, Any]:
    return _dump_tree(parse_tersel(_THEME_SOURCE, theme_values=_THEME_VALUES))


_THEME_REFERENCE_ERRORS: tuple[tuple[str, str], ...] = (
    ("unapproved_path", 'Column({"backgroundColor":$theme("unknownColor")})'),
    ("theme_not_selected", 'Column({"backgroundColor":$theme("primaryColor")})'),
    (
        "reserved_internal_name",
        'Column({"backgroundColor":_TerselTheme("primaryColor")})',
    ),
)


@scenario("tersel_protocol__theme_reference_errors")
def _build_theme_reference_errors() -> dict[str, Any]:
    return {
        key: _error(lambda source=source: parse_tersel(source))
        for key, source in _THEME_REFERENCE_ERRORS
    }


@scenario("tersel_protocol__component_rejections")
def _build_component_rejections() -> dict[str, Any]:
    profile = read_tersel_protocol_profile()
    return {
        "unknown_design_token": _error(lambda: convert_tersel_to_a2ui(
            'Column("card",Text("hello","not-a-token"))',
            size="2x2",
            protocol_profile=profile,
        )),
        "cloud_only_fusion_ball": _error(lambda: convert_tersel_to_a2ui(
            'Column("card",Stack(FusionBall("#FF121259","#FF2B65D9","#FF57AED9"),'
            'Stack({"_id":"cardContent"},Text("天气","body"))))',
            size="2x2",
            protocol_profile=profile,
        )),
    }
