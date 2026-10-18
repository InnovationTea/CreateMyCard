# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Shared semantic roles for model-facing Compact components."""

CORE_INFORMATION_COMPONENT_TYPES = frozenset(
    {
        "DataDisplay",
        "EmphasizedData",
        "EmphasisText",
        "EventCard",
        "H_BarChart",
        "InfoBlock",
        "NumericRatioStack",
        "ProgressCircle",
        "ProgressCircleSingle",
        "ProgressLine2",
        "SummaryList",
        "TableText",
        "TextBlock",
        "TopTextBottomValue",
    }
)

SHARED_FACT_COMPONENTS = (
    "SingleLineTitle", "DoubleLineTitle", "Badge", "EmphasizedData", "EmphasisText",
    "SecondaryBody", "InfoBlock", "H_BarChart", "NumericRatioStack", "ProgressCircleSingle",
    "ProgressCircle", "TableText", "EventCard", "PillButton",
)

MODEL_COMPONENT_TYPES_BY_SIZE = {
    "2x2": (*SHARED_FACT_COMPONENTS, "DataDisplay", "CircleButton"),
    "2x4": (
        *SHARED_FACT_COMPONENTS, "ProgressLine2", "TextBlock", "CardButton",
        "TopTextBottomValue", "SummaryList",
    ),
}
