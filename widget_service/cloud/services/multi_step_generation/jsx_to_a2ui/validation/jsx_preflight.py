from __future__ import annotations

from ..converters.high_level.emphasized_data import (
    collect_emphasized_data_conversion_errors,
)
from ..converters.high_level.card_button import collect_card_button_conversion_errors
from ..converters.high_level.helpers import collect_segmented_text_conversion_errors
from ..converters.high_level.gauge import collect_gauge_conversion_errors
from ..converters.high_level.h_bar_chart import collect_h_bar_chart_conversion_errors
from ..converters.high_level.info_block import collect_info_block_conversion_errors
from ..converters.high_level.numeric_ratio import collect_numeric_ratio_conversion_errors
from ..converters.high_level.numeric_ratio_stack import (
    collect_numeric_ratio_stack_conversion_errors,
)
from ..converters.high_level.progress_line_bar import (
    collect_progress_line2_conversion_errors,
)
from ..converters.high_level.table_text import collect_table_text_conversion_errors
from ..converters.high_level.text_block import collect_text_block_conversion_errors
from ..converters.high_level.top_text_bottom_value import (
    collect_top_text_bottom_value_conversion_errors,
)
from ..converters.structural.flex_stack import collect_stack_conversion_errors
from ..converters.structural.grid import collect_grid_conversion_errors
from ..parser.jsx_ast import JSXElement


def collect_conversion_preflight_errors(root: JSXElement) -> list[str]:
    """Collect model-fixable JSX inputs that would fail A2UI lowering.

    The checks live beside, and are reused by, their converters.  This pass
    only exposes all independent failures before conversion; converters keep
    the same checks as final invariant guards.
    """
    errors: list[str] = []

    def walk(node: JSXElement, parent: JSXElement | None = None) -> None:
        if node.tag == "Card" and not node.child_elements():
            errors.append("<Card> must contain at least one component child")
        elif node.tag == "Grid":
            errors.extend(collect_grid_conversion_errors(node))
        elif node.tag == "Stack":
            allow_absolute = (
                node.props.get("position") == "absolute"
                and parent is not None
                and parent.tag == "Stack"
                and parent.props.get("position") == "relative"
            )
            errors.extend(
                collect_stack_conversion_errors(
                    node,
                    allow_absolute=allow_absolute,
                )
            )
        elif node.tag == "EmphasizedData":
            errors.extend(collect_emphasized_data_conversion_errors(node))
        elif node.tag == "NumericRatio":
            errors.extend(collect_numeric_ratio_conversion_errors(node))
        elif node.tag == "NumericRatioStack":
            errors.extend(collect_numeric_ratio_stack_conversion_errors(node))
        elif node.tag == "ProgressLine2":
            errors.extend(collect_progress_line2_conversion_errors(node))
        elif node.tag == "TableText":
            errors.extend(collect_table_text_conversion_errors(node))
        elif node.tag == "InfoBlock":
            errors.extend(collect_info_block_conversion_errors(node))
        elif node.tag == "TopTextBottomValue":
            errors.extend(collect_top_text_bottom_value_conversion_errors(node))
        elif node.tag == "TextBlock":
            errors.extend(collect_text_block_conversion_errors(node))
        elif node.tag == "H_BarChart":
            errors.extend(collect_h_bar_chart_conversion_errors(node))
        elif node.tag == "Gauge":
            errors.extend(collect_gauge_conversion_errors(node))
        elif node.tag == "CardButton":
            errors.extend(collect_card_button_conversion_errors(node))
        elif node.tag in {"Summary", "SecondaryBody"} and "items" in node.props:
            errors.extend(collect_segmented_text_conversion_errors(node))
        for child in node.child_elements():
            walk(child, node)

    walk(root)
    return list(dict.fromkeys(errors))
