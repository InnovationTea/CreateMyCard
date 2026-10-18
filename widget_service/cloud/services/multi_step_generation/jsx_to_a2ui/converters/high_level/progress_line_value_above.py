from __future__ import annotations

from ...ir.a2ui_nodes import A2UINode, ConversionContext
from ...parser.jsx_ast import JSXElement
from .progress_line_bar import convert_progress_line_bar


def convert_progress_line_value_above(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    return convert_progress_line_bar(node, ctx)
