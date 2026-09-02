from __future__ import annotations

from ..catalog.contracts import validate_jsx_component
from ..catalog.bindings import CompileContext
from ..ir.a2ui_nodes import A2UINode, ConversionContext, IdAllocator
from ..parser.jsx_ast import JSXElement
from .high_level import (
    convert_badge,
    convert_checklist_item,
    convert_circle_button,
    convert_card_button,
    convert_data_display,
    convert_double_line_title,
    convert_emphasis_text,
    convert_emphasized_data,
    convert_event_card,
    convert_gauge,
    convert_h_bar_chart,
    convert_info_block,
    convert_numeric_ratio,
    convert_numeric_ratio_stack,
    convert_pill_button,
    convert_progress_circle_even,
    convert_progress_circle_single,
    convert_progress_line_bar,
    convert_progress_line_labels_below,
    convert_progress_line_value_above,
    convert_progress_ring,
    convert_secondary_body,
    convert_secondary_body_card,
    convert_single_line_title,
    convert_summary,
    convert_table_text,
    convert_text_block,
    convert_top_text_bottom_value,
    convert_weather_summary_card,
)
from .structural import convert_card, convert_flex_stack, convert_grid
from .structural.icon import convert_app_icon, convert_icon, convert_weather_icon


CONVERTERS = {
    "Card": convert_card,
    "Stack": convert_flex_stack,
    "Grid": convert_grid,
    "Icon": convert_icon,
    "AppIcon": convert_app_icon,
    "WeatherIcon": convert_weather_icon,
    "SingleLineTitle": convert_single_line_title,
    "DoubleLineTitle": convert_double_line_title,
    "Badge": convert_badge,
    "DataDisplay": convert_data_display,
    "InfoBlock": convert_info_block,
    "TopTextBottomValue": convert_top_text_bottom_value,
    "TableText": convert_table_text,
    "TextBlock": convert_text_block,
    "EmphasizedData": convert_emphasized_data,
    "EmphasisText": convert_emphasis_text,
    "SecondaryBody": convert_secondary_body,
    "Summary": convert_summary,
    "WeatherSummaryCard": convert_weather_summary_card,
    "SecondaryBodyCard": convert_secondary_body_card,
    "ProgressLine1": convert_progress_line_labels_below,
    "ProgressLine2": convert_progress_line_bar,
    "ProgressLine2WithData": convert_progress_line_value_above,
    "H_BarChart": convert_h_bar_chart,
    "Gauge": convert_gauge,
    "ProgressRing": convert_progress_ring,
    "ProgressCircleSingle": convert_progress_circle_single,
    "ProgressCircle": convert_progress_circle_even,
    "NumericRatio": convert_numeric_ratio,
    "NumericRatioStack": convert_numeric_ratio_stack,
    "ChecklistItem": convert_checklist_item,
    "EventCard": convert_event_card,
    "PillButton": convert_pill_button,
    "CircleButton": convert_circle_button,
    "CardButton": convert_card_button,
}


def convert_element(node: JSXElement, ctx: ConversionContext) -> A2UINode:
    validate_jsx_component(node)
    ctx.validate_bindings(node)
    return CONVERTERS[node.tag](node, ctx)


def create_context(
    card_name: str,
    appearance: str = "blue-soft",
    compile_context: CompileContext | dict | None = None,
) -> ConversionContext:
    return ConversionContext(
        IdAllocator(card_name),
        convert_element,
        appearance,
        compile_context=CompileContext.from_payload(compile_context),
    )
