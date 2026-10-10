# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from __future__ import annotations

import json
import unittest

from services.card_validation import (
    CompactDslValidationError,
    validate_compact_dsl,
)
from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    convert_compact_dsl_to_a2ui,
    normalize_compact_dsl_design_tokens,
    repair_compact_dsl_binding_paths,
)


def _serialize(rows: list[list[object]]) -> str:
    values: list[str] = []
    for row in rows:
        values.append(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
    return "\n".join(values)


class CompactDslA2uiConverterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = {
            "version": "v0.9",
            "catalogId": "ohos.a2ui.extended.catalog.form",
            "sizes": {
                "2x2": {"width": 140, "height": 140},
                "2x4": {"width": 300, "height": 140},
            },
        }
        rows = [
            [
                "root",
                "Column",
                {
                    "width": 160,
                    "height": 160,
                    "padding": 8,
                    "borderRadius": 16,
                    "clip": True,
                    "itemMargin": 8,
                    "linearGradient": {
                        "angle": 142,
                        "colors": [
                            ["#FFFFFFFF", 0],
                            ["#FF86C5E3", 1],
                        ],
                    },
                },
                ["title", "events", "action"],
            ],
            [
                "title",
                "Text",
                {
                    "content": {"path": "/data/title"},
                    "design": "heading-secondary-sm",
                    "fontColor": "font_primary",
                },
            ],
            [
                "events",
                "Column",
                {"itemMargin": 4},
                ["event_title"],
            ],
            [
                "event_title",
                "Text",
                {
                    "content": {"path": "/data/calendar/events/0/title"},
                    "design": "body-regular-sm",
                    "fontColor": "font_secondary",
                },
            ],
            [
                "action",
                "PillButton",
                {
                    "label": "查看详情",
                    "actionSurface": "#331F4799",
                    "actionInk": "#FF1F4799",
                    "onClick": [
                        {
                            "call": "clickToApi",
                            "args": {
                                "intentName": "ViewDetail",
                                "params": {
                                    "entityId": {
                                        "path": ("/data/calendar/events/0/entityId"),
                                    },
                                },
                            },
                        },
                    ],
                },
            ],
            ["/data/title", "今日日程"],
            [
                "/data/calendar/events",
                [
                    {
                        "title": "产品评审",
                        "entityId": "event-1",
                    },
                ],
            ],
        ]
        self.compact_dsl = _serialize(rows)

        self.task_spec = {
            "size": "2x2",
            "dataModelSchema": {
                "data": {
                    "title": {
                        "type": "string",
                        "sampleValue": "Today",
                    },
                    "calendar": {
                        "events": [
                            {
                                "title": {
                                    "type": "string",
                                    "sampleValue": "Review",
                                },
                                "entityId": {
                                    "type": "string",
                                    "sampleValue": "event-1",
                                },
                            }
                        ],
                    },
                },
            },
            "assetCandidates": [],
            "eventCandidates": [
                {
                    "id": "event.view.detail",
                    "call": "clickToApi",
                    "args": {
                        "intentName": "ViewDetail",
                        "params": {
                            "entityId": {
                                "path": "/data/calendar/events/0/entityId",
                            },
                        },
                    },
                },
            ],
        }
        self.card_spec = {
            "suggestSize": "2x2",
            "dataBindings": [
                {
                    "capabilityId": "GetCalendarEvents",
                    "arguments": {},
                    "writeResultTo": "/data",
                },
            ],
        }

    def test_single_line_title_uses_visual_recipe(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": "matchParent", "height": "matchParent"},
                    ["header"],
                ],
                [
                    "header",
                    "SingleLineTitle",
                    {
                        "title": "今日概览",
                        "fontColor": "#FF1F4799",
                    },
                ],
            ]
        )

        result = convert_compact_dsl_to_a2ui(
            compact_dsl,
            size="2x2",
            protocol_profile=self.profile,
        )
        update = json.loads(result.splitlines()[1])["updateComponents"]
        components = {item["id"]: item for item in update["components"]}

        self.assertEqual(components["header"]["component"], "Row")
        self.assertEqual(components["header"]["itemMargin"], 0)
        self.assertEqual(components["header"]["styles"]["height"], 20)
        self.assertEqual(components["header_title"]["styles"]["fontSize"], 12)
        self.assertEqual(components["header_title"]["styles"]["fontWeight"], 400)
        self.assertNotIn("header_icon", components)
        self.assertNotIn("_visualRecipe", result)

    def test_single_line_title_accepts_one_title_per_independent_panel(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Row",
                    {"width": "matchParent", "height": "matchParent"},
                    ["left", "right"],
                ],
                ["left", "Column", {"width": 132}, ["left_header"]],
                [
                    "left_header",
                    "SingleLineTitle",
                    {
                        "title": "手机",
                        "fontColor": "#FF1F4799",
                        "width": 132,
                        "height": 20,
                    },
                ],
                ["right", "Column", {"width": 132}, ["right_header"]],
                [
                    "right_header",
                    "SingleLineTitle",
                    {
                        "title": "手表",
                        "fontColor": "#FF1F4799",
                        "width": 132,
                        "height": 20,
                    },
                ],
            ]
        )

        result = convert_compact_dsl_to_a2ui(
            compact_dsl,
            size="2x4",
            protocol_profile=self.profile,
        )
        update = json.loads(result.splitlines()[1])["updateComponents"]
        component_ids = {item["id"] for item in update["components"]}
        self.assertIn("left_header_title", component_ids)
        self.assertIn("right_header_title", component_ids)

    def test_single_line_title_rejects_height_override(self) -> None:
        compact_dsl = _serialize(
            [
                ["root", "Column", {}, ["header"]],
                [
                    "header",
                    "SingleLineTitle",
                    {
                        "title": "分区标题",
                        "fontColor": "#FF1F4799",
                        "height": 24,
                    },
                ],
            ]
        )

        with self.assertRaisesRegex(
            CompactDslConversionError,
            "SingleLineTitle.height must be 20",
        ):
            convert_compact_dsl_to_a2ui(
                compact_dsl,
                size="2x4",
                protocol_profile=self.profile,
            )

    def test_rejects_removed_direct_input_components(self) -> None:
        for component_type in (
            "ActionUnit",
            "Button",
            "CardHeader",
            "Checkbox",
            "Divider",
            "Image",
            "List",
            "Progress",
        ):
            with self.subTest(component_type=component_type):
                compact_dsl = _serialize(
                    [
                        ["root", "Column", {"width": 160, "height": 160}, ["item"]],
                        ["item", component_type, {}],
                    ]
                )
                with self.assertRaisesRegex(
                    CompactDslConversionError,
                    f"unsupported component type {component_type}",
                ):
                    convert_compact_dsl_to_a2ui(
                        compact_dsl,
                        size="2x2",
                        protocol_profile=self.profile,
                    )
    def test_removes_empty_children_from_leaf_component(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": 160, "height": 160},
                    ["title"],
                ],
                ["title", "Text", {"content": "Weather"}, []],
            ]
        )

        normalized = normalize_compact_dsl_design_tokens(compact_dsl)
        title = json.loads(normalized.splitlines()[1])

        self.assertEqual(len(title), 3)


    def test_expands_latest_text_design(self) -> None:
        compact_dsl = _serialize(
            [
                ["root", "Column", {"width": 160, "height": 160}, ["metric"]],
                [
                    "metric",
                    "Text",
                    {"content": "68%", "design": "metric-display-md"},
                ],
            ]
        )

        normalized = normalize_compact_dsl_design_tokens(compact_dsl)
        rows = [json.loads(line) for line in normalized.splitlines()]
        components = {}
        for row in rows:
            components[row[0]] = row[2]

        self.assertEqual(components["metric"]["fontSize"], 36)
        self.assertEqual(components["metric"]["fontWeight"], 700)

    def test_progress_circle_expands_with_runtime_style_and_free_box_size(self) -> None:
        compact_dsl = _serialize(
            [
                ["root", "Column", {}, ["circle"]],
                [
                    "circle",
                    "ProgressCircle",
                    {
                        "externalText": {"path": "/battery"},
                        "icon": "resources/base/media/battery.svg",
                        "accessibility": {"label": "手机电量百分比"},
                        "width": 72,
                        "height": 76,
                        "fontColor": "#FF1F4799",
                        "fillColor": "#991F4799",
                        "color": "#FF1F4799",
                        "backgroundColor": "#331F4799",
                    },
                ],
                ["/battery", 68],
            ]
        )

        result = convert_compact_dsl_to_a2ui(
            compact_dsl,
            size="2x4",
            protocol_profile=self.profile,
        )
        update = json.loads(result.splitlines()[1])["updateComponents"]
        components = {item["id"]: item for item in update["components"]}

        self.assertEqual(components["circle"]["styles"]["width"], 72)
        self.assertEqual(components["circle"]["styles"]["height"], 76)
        self.assertEqual(components["circle_ring"]["styles"]["width"], 60)
        self.assertEqual(components["circle_ring"]["styles"]["height"], 60)
        self.assertEqual(components["circle_ring"]["styles"]["strokeWidth"], 6)
        self.assertEqual(components["circle_ring"]["component"], "Progress")
        self.assertEqual(components["circle_ring"]["value"], "{{ ${/battery} }}")
        self.assertEqual(
            components["circle_external_text"]["content"],
            "{{ ${/battery} + '%' }}",
        )

    def test_progress_circle_normalizes_bound_percentage_text(self) -> None:
        compact_dsl = _serialize(
            [
                ["root", "Column", {}, ["circle"]],
                [
                    "circle",
                    "ProgressCircle",
                    {
                        "externalText": {"path": "/data/weather/rainProbability"},
                        "icon": "resources/base/media/rain.svg",
                        "accessibility": {"label": "降雨概率"},
                        "width": 72,
                        "height": 76,
                        "fontColor": "#FF1F4799",
                        "color": "#FF1F4799",
                        "backgroundColor": "#331F4799",
                    },
                ],
                ["/data/weather/rainProbability", "20%"],
            ]
        )

        result = convert_compact_dsl_to_a2ui(
            compact_dsl,
            size="2x4",
            protocol_profile=self.profile,
        )
        messages = [json.loads(line) for line in result.splitlines()]
        components = {
            item["id"]: item
            for item in messages[1]["updateComponents"]["components"]
        }
        data_model = messages[2]["updateDataModel"]["value"]

        self.assertEqual(
            components["circle_ring"]["value"],
            "{{ ${/__display/data/weather/rainProbability/progressValue} }}",
        )
        self.assertEqual(
            components["circle_external_text"]["content"],
            "{{ ${/data/weather/rainProbability} }}",
        )
        self.assertEqual(
            data_model["__display"]["data"]["weather"]["rainProbability"][
                "progressValue"
            ],
            20,
        )

    def test_progress_components_normalize_percentage_text_against_total(self) -> None:
        compact_dsl = _serialize(
            [
                ["root", "Column", {}, ["line", "single"]],
                [
                    "line",
                    "ProgressLine2",
                    {
                        "value": {"path": "/data/task/completionText"},
                        "total": 10,
                        "displayValue": {"path": "/data/task/completionText"},
                        "fontColor": "#FF563D99",
                        "color": "#FF563D99",
                        "backgroundColor": "#33563D99",
                    },
                ],
                [
                    "single",
                    "ProgressCircleSingle",
                    {
                        "value": {"path": "/data/device/batteryText"},
                        "total": 100,
                        "icon": "resources/base/media/battery_leaf_fill.svg",
                        "displayValue": {"path": "/data/device/batteryText"},
                        "label": "当前电量",
                        "fontColor": "#FF1F4799",
                        "color": "#FF1F4799",
                        "backgroundColor": "#331F4799",
                    },
                ],
                ["/data/task/completionText", "60%"],
                ["/data/device/batteryText", "68％"],
            ]
        )

        result = convert_compact_dsl_to_a2ui(
            compact_dsl,
            size="2x4",
            protocol_profile=self.profile,
        )
        messages = [json.loads(line) for line in result.splitlines()]
        components = {
            item["id"]: item
            for item in messages[1]["updateComponents"]["components"]
        }
        data_model = messages[2]["updateDataModel"]["value"]

        self.assertEqual(
            components["line_bar"]["value"],
            "{{ ${/__display/data/task/completionText/progressValue} }}",
        )
        self.assertEqual(
            data_model["__display"]["data"]["task"]["completionText"][
                "progressValue"
            ],
            6,
        )
        self.assertEqual(
            components["single_ring"]["value"],
            "{{ ${/__display/data/device/batteryText/progressValue} }}",
        )
        self.assertEqual(
            data_model["__display"]["data"]["device"]["batteryText"][
                "progressValue"
            ],
            68,
        )

    def test_progress_components_reject_business_copy_containing_percentage(self) -> None:
        compact_dsl = _serialize(
            [
                ["root", "Column", {}, ["circle"]],
                [
                    "circle",
                    "ProgressCircle",
                    {
                        "externalText": {"path": "/data/weather/rainProbability"},
                        "icon": "resources/base/media/rain.svg",
                        "accessibility": {"label": "降雨概率"},
                        "width": 72,
                        "height": 76,
                        "fontColor": "#FF1F4799",
                        "color": "#FF1F4799",
                        "backgroundColor": "#331F4799",
                    },
                ],
                ["/data/weather/rainProbability", "降雨概率 20%"],
            ]
        )

        with self.assertRaisesRegex(
            CompactDslConversionError,
            "complete numeric percentage",
        ):
            convert_compact_dsl_to_a2ui(
                compact_dsl,
                size="2x4",
                protocol_profile=self.profile,
            )

    def test_progress_circle_rejects_insufficient_ring_space(self) -> None:
        compact_dsl = _serialize(
            [
                ["root", "Column", {}, ["circle"]],
                [
                    "circle",
                    "ProgressCircle",
                    {
                        "externalText": 68,
                        "icon": "resources/base/media/battery.svg",
                        "accessibility": {"label": "手机电量百分比"},
                        "width": 44,
                        "height": 30,
                        "fontColor": "#FF1F4799",
                        "color": "#FF1F4799",
                        "backgroundColor": "#331F4799",
                    },
                ],
            ]
        )

        with self.assertRaisesRegex(
            CompactDslConversionError,
            "leave less than 40vp for the ring",
        ):
            convert_compact_dsl_to_a2ui(
                compact_dsl,
                size="2x2",
                protocol_profile=self.profile,
            )

    def test_progress_circle_rejects_internal_progress_props(self) -> None:
        compact_dsl = _serialize(
            [
                ["root", "Column", {}, ["circle"]],
                [
                    "circle",
                    "ProgressCircle",
                    {
                        "externalText": "68%",
                        "icon": "resources/base/media/battery.svg",
                        "accessibility": {"label": "手机电量百分比"},
                        "width": 44,
                        "height": 60,
                        "value": 68,
                        "fontColor": "#FF1F4799",
                        "color": "#FF1F4799",
                        "backgroundColor": "#331F4799",
                    },
                ],
            ]
        )

        with self.assertRaisesRegex(
            CompactDslConversionError,
            "ProgressCircle does not allow value",
        ):
            convert_compact_dsl_to_a2ui(
                compact_dsl,
                size="2x2",
                protocol_profile=self.profile,
            )

    def test_theme_is_compatibility_only(self) -> None:
        light = normalize_compact_dsl_design_tokens(
            self.compact_dsl,
            theme="light",
        )
        dark = normalize_compact_dsl_design_tokens(
            self.compact_dsl,
            theme="dark",
        )

        self.assertEqual(light, dark)

    def test_converts_components_events_bindings_and_array_data(self) -> None:
        a2ui = convert_compact_dsl_to_a2ui(
            self.compact_dsl,
            size="2x2",
            protocol_profile=self.profile,
        )
        messages = [json.loads(line) for line in a2ui.splitlines()]

        self.assertEqual(len(messages), 3)
        self.assertNotIn("width", messages[0]["createSurface"])
        self.assertNotIn("height", messages[0]["createSurface"])
        update = messages[1]["updateComponents"]
        self.assertEqual(update["root"], "root")
        components = {}
        for component in update["components"]:
            components[component["id"]] = component

        self.assertEqual(components["root"]["itemMargin"], 8)
        self.assertEqual(components["root"]["styles"]["width"], "matchParent")
        self.assertEqual(components["root"]["styles"]["height"], "matchParent")
        self.assertEqual(components["events"]["itemMargin"], 4)
        self.assertEqual(
            components["title"]["content"],
            "{{ ${/data/title} }}",
        )
        handler = components["action"]["onClick"][0]
        self.assertEqual(handler["call"], "clickToApi")
        entity_id = handler["args"]["params"]["entityId"]
        self.assertEqual(
            entity_id,
            "{{ ${/data/calendar/events/0/entityId} }}",
        )
        data_model = messages[2]["updateDataModel"]["value"]
        event = data_model["data"]["calendar"]["events"][0]
        self.assertEqual(event["title"], "产品评审")

    def test_always_uses_form_catalog_id(self) -> None:
        profile = dict(self.profile)
        profile["catalogId"] = "ohos.a2ui.extended.catalog"

        a2ui = convert_compact_dsl_to_a2ui(
            self.compact_dsl,
            size="2x2",
            protocol_profile=profile,
        )
        create_surface = json.loads(a2ui.splitlines()[0])["createSurface"]

        self.assertEqual(
            create_surface["catalogId"],
            "ohos.a2ui.extended.catalog.form",
        )

    def test_pill_button_uses_explicit_surface_and_text_style(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {
                        "width": "matchParent",
                        "height": "matchParent",
                        "backgroundColor": "#FFFFF6E5",
                    },
                    ["cta"],
                ],
                [
                    "cta",
                    "PillButton",
                    {
                        "label": "导航去公司",
                        "actionSurface": "#FFF0DCB8",
                        "actionInk": "#FF9E6D20",
                        "fontSize": 14,
                        "fontWeight": 400,
                        "onClick": [{"call": "navigate", "args": {}}],
                    },
                ],
                ["/state/ready", True],
            ]
        )

        result = convert_compact_dsl_to_a2ui(
            compact_dsl,
            size="2x2",
            protocol_profile=self.profile,
        )
        update = json.loads(result.splitlines()[1])["updateComponents"]
        components = {item["id"]: item for item in update["components"]}
        action_styles = components["cta"]["styles"]

        self.assertEqual(components["cta"]["component"], "Button")
        self.assertEqual(action_styles["backgroundColor"], "#FFF0DCB8")
        self.assertEqual(action_styles["fontColor"], "#FF9E6D20")
        self.assertEqual(action_styles["height"], 36)
        self.assertEqual(action_styles["borderRadius"], 30)
        self.assertEqual(action_styles["fontSize"], 14)
        self.assertEqual(action_styles["fontWeight"], 400)
        self.assertEqual(action_styles["textAlign"], "center")

    def test_expands_two_by_two_content_components(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": "matchParent", "height": "matchParent"},
                    ["metric", "info", "table"],
                ],
                [
                    "metric",
                    "EmphasizedData",
                    {
                        "value": "82",
                        "unit": "分",
                        "fontColor": "#FF1F4799",
                    },
                ],
                [
                    "info",
                    "InfoBlock",
                    {
                        "primaryText": "夜间睡眠",
                        "secondaryText": "7小时1分",
                        "fontColor": "#FF1F4799",
                        "backgroundColor": "#CCFFFFFF",
                    },
                ],
                [
                    "table",
                    "TableText",
                    {
                        "items": [
                            {"label": "紫外线", "value": "中等"},
                            {"label": "空气质量", "value": "良"},
                        ],
                        "fontColor": "#FF1F4799",
                    },
                ],
            ]
        )

        result = convert_compact_dsl_to_a2ui(
            compact_dsl,
            size="2x2",
            protocol_profile=self.profile,
        )
        update = json.loads(result.splitlines()[1])["updateComponents"]
        components = {item["id"]: item for item in update["components"]}

        self.assertEqual(components["metric"]["component"], "Row")
        self.assertEqual(
            components["metric"]["children"],
            ["metric_value", "metric_unit"],
        )
        self.assertEqual(components["metric"]["styles"]["width"], "matchParent")
        self.assertEqual(components["metric_value"]["styles"]["fontSize"], 30)
        self.assertEqual(components["metric_unit"]["styles"]["margin"], {"top": 14})
        self.assertEqual(components["info"]["component"], "Column")
        self.assertEqual(components["info"]["styles"]["height"], 63)
        self.assertEqual(components["info_primary"]["styles"]["fontWeight"], 700)
        self.assertEqual(components["table"]["component"], "Column")
        self.assertEqual(
            components["table"]["children"],
            ["table_row0", "table_row1"],
        )
        self.assertEqual(components["table_row0_label"]["styles"]["layoutWeight"], 31)
        self.assertEqual(components["table_row0_value"]["styles"]["layoutWeight"], 28)
        self.assertEqual(components["table_row0_value"]["styles"]["fontSize"], 12)

    def test_expands_claw_shared_semantic_components(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": "matchParent", "height": "matchParent"},
                    ["title", "badge", "emphasis", "secondary", "chart", "ratio"],
                ],
                [
                    "title",
                    "DoubleLineTitle",
                    {
                        "title": "城市空气质量",
                        "secondaryInfo": "更新于 10:30",
                        "fontColor": "#FF1F4799",
                    },
                ],
                [
                    "badge",
                    "Badge",
                    {
                        "value": 3,
                        "fontColor": "#FF1F4799",
                        "backgroundColor": "#331F4799",
                    },
                ],
                [
                    "emphasis",
                    "EmphasisText",
                    {
                        "mainText": "适宜户外活动",
                        "secondaryText": "紫外线较弱",
                        "fontColor": "#FF1F4799",
                    },
                ],
                [
                    "secondary",
                    "SecondaryBody",
                    {
                        "items": [
                            {"label": "湿度", "value": "48%"},
                            {"label": "风力", "value": "2级"},
                        ],
                        "fontColor": "#FF1F4799",
                    },
                ],
                [
                    "chart",
                    "H_BarChart",
                    {
                        "items": [
                            {"label": "客厅", "valueUnit": "3.2千瓦时", "percent": 80},
                            {"label": "书房", "valueUnit": "1.8千瓦时", "percent": 45},
                        ],
                        "fontColor": "#FF1F4799",
                        "barColor": "#FF1F4799",
                        "trackColor": "#331F4799",
                    },
                ],
                [
                    "ratio",
                    "NumericRatioStack",
                    {
                        "direction": "row",
                        "items": [
                            {"icon": "a.svg", "value": 82, "unit": "%"},
                            {"icon": "b.svg", "value": 61, "unit": "%"},
                            {"icon": "c.svg", "value": 34, "unit": "%"},
                        ],
                        "fontColor": "#FF1F4799",
                        "fillColor": "#FF1F4799",
                    },
                ],
            ]
        )

        result = convert_compact_dsl_to_a2ui(
            compact_dsl,
            size="2x4",
            protocol_profile=self.profile,
        )
        update = json.loads(result.splitlines()[1])["updateComponents"]
        components = {item["id"]: item for item in update["components"]}

        self.assertEqual(components["title_title"]["styles"]["fontWeight"], 700)
        self.assertEqual(components["badge"]["component"], "Text")
        self.assertEqual(components["emphasis_main"]["styles"]["fontSize"], 18)
        self.assertEqual(components["secondary_row0"]["component"], "Row")
        self.assertEqual(components["chart_item0_bar"]["component"], "Progress")
        self.assertEqual(components["ratio_item0_icon"]["styles"]["width"], 12)
        self.assertEqual(
            components["ratio_item0"]["children"],
            ["ratio_item0_icon_slot", "ratio_item0_value_group"],
        )
        self.assertEqual(
            components["ratio_item0_value_group"]["children"],
            ["ratio_item0_value", "ratio_item0_unit"],
        )

    def test_secondary_body_supports_bound_body_metadata_and_supporting_text(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": "matchParent", "height": "matchParent"},
                    ["body", "metadata", "supporting"],
                ],
                [
                    "body",
                    "SecondaryBody",
                    {
                        "role": "body",
                        "items": [
                            {
                                "value": {"path": "/data/description"},
                                "maxLines": 2,
                            }
                        ],
                        "fontColor": "#FF1F4799",
                    },
                ],
                [
                    "metadata",
                    "SecondaryBody",
                    {
                        "role": "metadata",
                        "items": [
                            {"value": "{{ '更新 ' + ${/data/updatedAt} }}"}
                        ],
                        "fontColor": "#FF1F4799",
                    },
                ],
                [
                    "supporting",
                    "SecondaryBody",
                    {
                        "role": "supporting",
                        "items": [{"label": "状态 ", "value": "正常"}],
                        "fontColor": "#FF1F4799",
                    },
                ],
                ["/data/description", "今天适宜户外活动，紫外线较弱"],
                ["/data/updatedAt", "10:30"],
            ]
        )

        result = convert_compact_dsl_to_a2ui(
            compact_dsl,
            size="2x2",
            protocol_profile=self.profile,
        )
        update = json.loads(result.splitlines()[1])["updateComponents"]
        components = {item["id"]: item for item in update["components"]}

        self.assertEqual(components["body_item0_value"]["content"], "{{ ${/data/description} }}")
        self.assertEqual(components["body_item0_value"]["styles"]["fontSize"], 14)
        self.assertEqual(components["body_item0_value"]["styles"]["fontWeight"], 400)
        self.assertEqual(components["body_item0_value"]["styles"]["maxLines"], 2)
        self.assertEqual(components["body_item0_value"]["styles"]["height"], 40)
        self.assertEqual(components["metadata_item0_value"]["styles"]["fontSize"], 12)
        self.assertEqual(components["metadata_item0_value"]["styles"]["fontWeight"], 400)
        self.assertEqual(components["metadata_item0_value"]["styles"]["maxLines"], 1)
        self.assertEqual(components["supporting_item0_label"]["content"], "状态 ")
        self.assertEqual(components["supporting_item0_value"]["content"], "正常")

    def test_secondary_body_rejects_uncontrolled_text_shapes(self) -> None:
        invalid_props = [
            {"items": [{"value": "正文"}], "fontColor": "#FF1F4799"},
            {
                "role": "metadata",
                "items": [{"value": "更新时间", "maxLines": 2}],
                "fontColor": "#FF1F4799",
            },
            {
                "role": "body",
                "items": [{"label": "说明", "value": "正文"}],
                "fontColor": "#FF1F4799",
            },
            {
                "role": "body",
                "items": [{"value": "正文"}],
                "fontSize": 18,
                "fontColor": "#FF1F4799",
            },
        ]
        for props in invalid_props:
            with self.subTest(props=props):
                compact_dsl = _serialize(
                    [
                        ["root", "Column", {}, ["body"]],
                        ["body", "SecondaryBody", props],
                    ]
                )
                with self.assertRaises(CompactDslConversionError):
                    convert_compact_dsl_to_a2ui(
                        compact_dsl,
                        size="2x2",
                        protocol_profile=self.profile,
                    )

    def test_expands_info_block_progress_visual_and_two_event_card_items(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": "matchParent", "height": "matchParent"},
                    ["info", "events"],
                ],
                [
                    "info",
                    "InfoBlock",
                    {
                        "variant": "slot",
                        "primaryText": {"path": "/data/battery"},
                        "unit": "%",
                        "secondaryText": "设备电量",
                        "visual": {
                            "type": "progressCircle",
                            "icon": "resources/base/media/battery_leaf_fill.svg",
                        },
                        "fontColor": "#FF1F4799",
                        "backgroundColor": "#99FFFFFF",
                    },
                ],
                [
                    "events",
                    "EventCard",
                    {
                        "items": [
                            {"title": "产品评审", "time": "09:00", "location": "A3"},
                            {"title": "版本复盘", "time": "15:00"},
                        ],
                        "density": "compact",
                        "fontColor": "#FF8C4B1C",
                    },
                ],
                ["/data/battery", 68],
            ]
        )

        result = convert_compact_dsl_to_a2ui(
            compact_dsl,
            size="2x4",
            protocol_profile=self.profile,
        )
        update = json.loads(result.splitlines()[1])["updateComponents"]
        components = {item["id"]: item for item in update["components"]}

        self.assertEqual(components["info_visual_progress"]["component"], "Progress")
        self.assertEqual(components["info_visual_progress"]["value"], "{{ ${/data/battery} }}")
        self.assertEqual(components["info_visual_icon"]["styles"]["width"], 20)
        self.assertEqual(
            components["events"]["children"],
            ["events_item0", "events_item1"],
        )
        self.assertEqual(components["events"]["styles"]["height"], 72)
        self.assertEqual(components["events_item0_title"]["styles"]["fontWeight"], 700)
        self.assertEqual(components["events_item0_time"]["styles"]["fontSize"], 10)

    def test_expands_two_by_four_content_components(self) -> None:
        handler = {"call": "openDetails", "args": {}}
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": "matchParent", "height": "matchParent"},
                    ["info", "progress", "details", "action"],
                ],
                [
                    "info",
                    "InfoBlock",
                    {
                        "variant": "aux",
                        "primaryText": "夜间睡眠",
                        "secondaryText": "7小时1分",
                        "fontColor": "#FF563D99",
                        "backgroundColor": "#99FFFFFF",
                    },
                ],
                [
                    "progress",
                    "ProgressLine2",
                    {
                        "value": 82,
                        "total": 100,
                        "displayValue": 82,
                        "unit": "分",
                        "fontColor": "#FF563D99",
                        "color": "#FF563D99",
                        "backgroundColor": "#33563D99",
                    },
                ],
                [
                    "details",
                    "TextBlock",
                    {
                        "items": [
                            {"label": "睡眠时长", "value": "7小时1分"},
                            {"label": "深睡时长", "value": "2小时15分"},
                        ],
                        "fontColor": "#FF563D99",
                        "backgroundColor": "#99FFFFFF",
                    },
                ],
                [
                    "action",
                    "CardButton",
                    {
                        "label": "查看详情",
                        "onClick": [handler],
                        "fontColor": "#FF563D99",
                        "backgroundColor": "#99FFFFFF",
                    },
                ],
            ]
        )

        result = convert_compact_dsl_to_a2ui(
            compact_dsl,
            size="2x4",
            protocol_profile=self.profile,
        )
        update = json.loads(result.splitlines()[1])["updateComponents"]
        components = {item["id"]: item for item in update["components"]}

        self.assertEqual(components["info"]["styles"]["width"], "matchParent")
        self.assertEqual(components["info"]["styles"]["height"], 57)
        self.assertEqual(components["progress"]["children"][-1], "progress_bar")
        self.assertEqual(components["progress_bar"]["component"], "Progress")
        self.assertEqual(components["progress_bar"]["styles"]["strokeWidth"], 8)
        self.assertEqual(components["progress_unit"]["styles"]["fontSize"], 12)
        self.assertEqual(
            components["details"]["children"],
            ["details_item0", "details_item1"],
        )
        self.assertEqual(components["details_item0"]["styles"]["height"], "matchParent")
        self.assertEqual(
            components["details_item0"]["styles"]["constraintSize"]["minWidth"],
            64,
        )
        self.assertEqual(components["action"]["component"], "Row")
        self.assertEqual(components["action"]["onClick"], [handler])
        self.assertEqual(
            components["action"]["children"],
            ["action_label", "action_visual"],
        )
        self.assertEqual(components["action_label"]["styles"]["fontSize"], 14)
        self.assertEqual(components["action_visual"]["component"], "Divider")

    def test_text_block_expands_two_to_four_items_with_equal_width(self) -> None:
        compact_dsl = _serialize(
            [
                ["root", "Column", {}, ["details"]],
                [
                    "details",
                    "TextBlock",
                    {
                        "items": [
                            {"label": "上午", "value": "晴"},
                            {"label": "中午", "value": "多云"},
                            {"label": "下午", "value": "小雨"},
                            {"label": "晚上", "value": "阴"},
                        ],
                        "fontColor": "#FF1F4799",
                        "backgroundColor": "#99FFFFFF",
                    },
                ],
            ]
        )

        result = convert_compact_dsl_to_a2ui(
            compact_dsl,
            size="2x4",
            protocol_profile=self.profile,
        )
        update = json.loads(result.splitlines()[1])["updateComponents"]
        components = {item["id"]: item for item in update["components"]}

        self.assertEqual(
            components["details"]["children"],
            [
                "details_item0",
                "details_item1",
                "details_item2",
                "details_item3",
            ],
        )
        for index in range(4):
            self.assertEqual(
                components[f"details_item{index}"]["styles"]["constraintSize"]["minWidth"],
                64,
            )

    def test_info_block_rejects_on_click(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": "matchParent", "height": "matchParent"},
                    ["info"],
                ],
                [
                    "info",
                    "InfoBlock",
                    {
                        "primaryText": "手机电量",
                        "secondaryText": "68%",
                        "fontColor": "#FF1F4799",
                        "backgroundColor": "#CCFFFFFF",
                        "onClick": [{"call": "openSettings", "args": {}}],
                    },
                ],
            ]
        )

        with self.assertRaisesRegex(
            CompactDslConversionError,
            "InfoBlock does not allow onClick",
        ):
            convert_compact_dsl_to_a2ui(
                compact_dsl,
                size="2x2",
                protocol_profile=self.profile,
            )

    def test_visual_recipe_preserves_bindings_expressions_and_events(self) -> None:
        display_expression = "{{ ${/data/sleep/score} + '分' }}"
        handler = {
            "call": "openDetails",
            "args": {"entityId": {"path": "/data/sleep/entityId"}},
        }
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": "matchParent", "height": "matchParent"},
                    ["progress", "action"],
                ],
                [
                    "progress",
                    "ProgressLine2",
                    {
                        "value": {"path": "/data/sleep/score"},
                        "total": 100,
                        "displayValue": display_expression,
                        "fontColor": "#FF563D99",
                        "color": "#FF563D99",
                        "backgroundColor": "#33563D99",
                    },
                ],
                [
                    "action",
                    "CardButton",
                    {
                        "label": "查看详情",
                        "onClick": [handler],
                        "fontColor": "#FF563D99",
                        "backgroundColor": "#99FFFFFF",
                    },
                ],
                ["/data/sleep/score", 82],
                ["/data/sleep/entityId", "sleep-001"],
            ]
        )

        result = convert_compact_dsl_to_a2ui(
            compact_dsl,
            size="2x4",
            protocol_profile=self.profile,
        )
        update = json.loads(result.splitlines()[1])["updateComponents"]
        components = {item["id"]: item for item in update["components"]}

        self.assertEqual(components["progress_value"]["content"], display_expression)
        self.assertEqual(
            components["progress_bar"]["value"],
            "{{ ${/data/sleep/score} }}",
        )
        self.assertEqual(
            components["action_label"]["content"],
            "查看详情",
        )
        self.assertEqual(
            components["action"]["onClick"][0]["args"]["entityId"],
            "{{ ${/data/sleep/entityId} }}",
        )
        self.assertNotIn("_visualRecipe", result)

    def test_expands_second_batch_two_by_two_components(self) -> None:
        data_display_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": "matchParent", "height": "matchParent"},
                    ["display"],
                ],
                [
                    "display",
                    "DataDisplay",
                    {
                        "label": "运动会倒计时",
                        "value": 32,
                        "supportingText": "天",
                        "fontColor": "#FFFFFFFF",
                    },
                ],
            ]
        )
        result = convert_compact_dsl_to_a2ui(
            data_display_dsl,
            size="2x2",
            protocol_profile=self.profile,
        )
        update = json.loads(result.splitlines()[1])["updateComponents"]
        components = {item["id"]: item for item in update["components"]}

        self.assertEqual(
            components["display"]["children"],
            ["display_label", "display_value", "display_supporting"],
        )
        self.assertEqual(components["display_value"]["styles"]["fontSize"], 56)
        self.assertEqual(components["display_value"]["styles"]["height"], 60)
        self.assertEqual(
            components["display_label"]["styles"]["fontColor"],
            "#99FFFFFF",
        )
        self.assertEqual(
            components["display_supporting"]["styles"]["fontColor"],
            "#99FFFFFF",
        )

        event_card_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": "matchParent", "height": "matchParent"},
                    ["day_area", "content_area"],
                ],
                [
                    "day_area",
                    "Row",
                    {
                        "width": 126,
                        "height": 16,
                        "justifyContent": "start",
                        "alignItems": "center",
                        "flexShrink": 0,
                    },
                    ["day_tag"],
                ],
                [
                    "day_tag",
                    "Text",
                    {"content": "下一场会议", "textAlign": "start"},
                ],
                [
                    "content_area",
                    "EventCard",
                    {
                        "title": {"path": "/data/calendar/events/0/title"},
                        "time": {"path": "/data/calendar/events/0/dtStart"},
                        "location": "A 会议室",
                        "fontColor": "#FF8C4B1C",
                    },
                ],
                ["/data/calendar/events/0/title", "UI需求评审会"],
                ["/data/calendar/events/0/dtStart", "14:00 - 15:30"],
            ]
        )
        result = convert_compact_dsl_to_a2ui(
            event_card_dsl,
            size="2x2",
            protocol_profile=self.profile,
        )
        update = json.loads(result.splitlines()[1])["updateComponents"]
        components = {item["id"]: item for item in update["components"]}

        self.assertEqual(components["content_area"]["component"], "Row")
        self.assertEqual(
            components["content_area"]["children"],
            ["content_area_rail", "content_area_texts"],
        )
        self.assertEqual(
            components["content_area_texts"]["children"],
            [
                "content_area_title",
                "content_area_time",
                "content_area_location",
            ],
        )
        self.assertEqual(components["content_area_rail"]["styles"]["height"], 50)
        self.assertEqual(components["content_area_rail_line"]["styles"]["height"], 32)
        self.assertEqual(
            components["content_area_time"]["styles"]["fontColor"],
            "#998C4B1C",
        )

    def test_expands_second_batch_two_by_four_components(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": "matchParent", "height": "matchParent"},
                    ["circle", "metrics", "list"],
                ],
                [
                    "circle",
                    "ProgressCircleSingle",
                    {
                        "value": 68,
                        "total": 100,
                        "icon": "resources/base/media/battery_leaf_fill.svg",
                        "displayValue": "68%",
                        "label": "当前电量",
                        "secondaryLabel": "未充电",
                        "fontColor": "#FF1F4799",
                        "color": "#FF1F4799",
                        "backgroundColor": "#331F4799",
                    },
                ],
                [
                    "metrics",
                    "TopTextBottomValue",
                    {
                        "items": [
                            {"label": "睡眠得分", "value": 80, "unit": "分"},
                            {"label": "消耗热量", "value": 92, "unit": "千卡"},
                            {"label": "今日步数", "value": 2031, "unit": "步"},
                        ],
                        "fontColor": "#FF563D99",
                        "dividerColor": "#33563D99",
                    },
                ],
                [
                    "list",
                    "SummaryList",
                    {
                        "items": ["项目阶段性汇报", "确认Q3设计需求", "申请下周出差"],
                        "fontColor": "#FF8C4B1C",
                        "backgroundColor": "#99FFFFFF",
                    },
                ],
            ]
        )

        result = convert_compact_dsl_to_a2ui(
            compact_dsl,
            size="2x4",
            protocol_profile=self.profile,
        )
        update = json.loads(result.splitlines()[1])["updateComponents"]
        components = {item["id"]: item for item in update["components"]}

        self.assertEqual(components["circle"]["styles"]["width"], "matchParent")
        self.assertEqual(components["circle"]["styles"]["height"], 46)
        self.assertEqual(
            components["circle"]["children"],
            ["circle_ring_stack", "circle_labels"],
        )
        self.assertEqual(components["circle_ring"]["component"], "Progress")
        self.assertEqual(components["circle_ring"]["styles"]["strokeWidth"], 6)
        self.assertEqual(components["circle_icon"]["component"], "Image")
        self.assertEqual(components["circle_icon"]["styles"]["width"], 20)
        self.assertEqual(
            components["metrics"]["children"],
            [
                "metrics_item0",
                "metrics_divider0",
                "metrics_item1",
                "metrics_divider1",
                "metrics_item2",
            ],
        )
        self.assertEqual(components["metrics_item0"]["children"][0], "metrics_item0_label")
        self.assertEqual(components["metrics_item0_value"]["styles"]["fontSize"], 24)
        self.assertEqual(components["metrics_item0_unit"]["styles"]["fontSize"], 12)
        self.assertEqual(components["list"]["styles"]["height"], 102)
        self.assertEqual(len(components["list"]["children"]), 3)

    def test_shared_components_expand_in_both_sizes(self) -> None:
        small_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": "matchParent", "height": "matchParent"},
                    ["circle"],
                ],
                [
                    "circle",
                    "ProgressCircleSingle",
                    {
                        "value": 68,
                        "total": 100,
                        "icon": "resources/base/media/battery_leaf_fill.svg",
                        "displayValue": "68%",
                        "label": "当前电量",
                        "secondaryLabel": "未充电",
                        "fontColor": "#FF1F4799",
                        "color": "#FF1F4799",
                        "backgroundColor": "#331F4799",
                    },
                ],
            ]
        )

        small_result = convert_compact_dsl_to_a2ui(
            small_dsl,
            size="2x2",
            protocol_profile=self.profile,
        )
        small_update = json.loads(small_result.splitlines()[1])["updateComponents"]
        small_components = {item["id"]: item for item in small_update["components"]}

        self.assertEqual(small_components["circle"]["styles"]["height"], 52)
        self.assertEqual(small_components["circle_ring_stack"]["styles"]["width"], 52)
        self.assertEqual(small_components["circle_ring"]["styles"]["width"], 52)
        self.assertEqual(small_components["circle_labels"]["styles"]["width"], 66)
        self.assertEqual(small_components["circle_display"]["styles"]["fontSize"], 10)
        self.assertEqual(small_components["circle_secondary"]["styles"]["height"], 16)

        wide_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": "matchParent", "height": "matchParent"},
                    ["table", "event"],
                ],
                [
                    "table",
                    "TableText",
                    {
                        "items": [
                            {"label": "紫外线", "value": "弱"},
                            {"label": "空气质量", "value": "优"},
                        ],
                        "fontColor": "#FF1F4799",
                    },
                ],
                [
                    "event",
                    "EventCard",
                    {
                        "title": "项目评审",
                        "time": "14:00–15:00",
                        "location": "三楼会议室",
                        "fontColor": "#FF1F4799",
                    },
                ],
            ]
        )

        wide_result = convert_compact_dsl_to_a2ui(
            wide_dsl,
            size="2x4",
            protocol_profile=self.profile,
        )
        wide_update = json.loads(wide_result.splitlines()[1])["updateComponents"]
        wide_components = {item["id"]: item for item in wide_update["components"]}

        self.assertEqual(wide_components["table"]["children"], ["table_row0", "table_row1"])
        self.assertEqual(wide_components["table_row0"]["styles"]["height"], 18)
        self.assertEqual(wide_components["event"]["styles"]["width"], "matchParent")
        self.assertEqual(wide_components["event_rail"]["styles"]["height"], 50)

    def test_timeline_unit_is_no_longer_a_supported_component(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": "matchParent", "height": "matchParent"},
                    ["timeline"],
                ],
                [
                    "timeline",
                    "TimelineUnit",
                    {"color": "#FF8C4B1C", "lineColor": "#1A8C4B1C"},
                ],
            ]
        )

        with self.assertRaisesRegex(
            CompactDslConversionError,
            "unsupported component type TimelineUnit",
        ):
            convert_compact_dsl_to_a2ui(
                compact_dsl,
                size="2x2",
                protocol_profile=self.profile,
            )

    def test_high_level_components_are_validated_before_base_components(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": "matchParent", "height": "matchParent"},
                    ["action"],
                ],
                [
                    "action",
                    "CardButton",
                    {
                        "label": "查看详情",
                        "onClick": [{"call": "openDetails", "args": {}}],
                        "fontColor": "#FF563D99",
                        "backgroundColor": "#99FFFFFF",
                    },
                ],
            ]
        )

        with self.assertRaisesRegex(
            CompactDslValidationError,
            "must exactly match a TaskSpec eventCandidate",
        ):
            validate_compact_dsl(
                compact_dsl,
                task_spec={
                    "size": "2x4",
                    "dataModelSchema": {},
                    "assetCandidates": [],
                    "eventCandidates": [],
                },
                card_spec={"suggestSize": "2x4", "dataBindings": []},
            )

    def test_high_level_optional_icons_follow_visual_recipe_slots(self) -> None:
        handler = {"call": "openDetails", "args": {}}
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Row",
                    {"width": "matchParent", "height": "matchParent"},
                    ["info", "action"],
                ],
                [
                    "info",
                    "InfoBlock",
                    {
                        "variant": "small",
                        "primaryText": "手机电量",
                        "secondaryText": "68%",
                        "fontColor": "#FF1F4799",
                        "backgroundColor": "#99FFFFFF",
                        "icon": "resources/base/media/battery.svg",
                        "fillColor": "#FF1F4799",
                    },
                ],
                [
                    "action",
                    "CardButton",
                    {
                        "label": "查看详情",
                        "onClick": [handler],
                        "fontColor": "#FF1F4799",
                        "backgroundColor": "#99FFFFFF",
                    },
                ],
            ]
        )

        result = convert_compact_dsl_to_a2ui(
            compact_dsl,
            size="2x4",
            protocol_profile=self.profile,
        )
        update = json.loads(result.splitlines()[1])["updateComponents"]
        components = {item["id"]: item for item in update["components"]}

        self.assertEqual(components["info"]["children"], ["info_text", "info_visual"])
        self.assertEqual(components["info_text"]["styles"]["flexShrink"], 1)
        self.assertEqual(components["info_visual"]["styles"]["width"], 24)
        self.assertEqual(
            components["info_visual"]["styles"]["fillColor"],
            "#FF1F4799",
        )
        self.assertEqual(
            components["action"]["children"],
            ["action_label", "action_visual"],
        )
        self.assertEqual(components["action_visual"]["component"], "Divider")

    def test_rejects_invalid_high_level_component_contracts(self) -> None:
        cases = (
            (
                "2x2",
                [
                    "progress",
                    "ProgressLine2",
                    {
                        "value": 0,
                        "total": 0,
                        "displayValue": "0分",
                        "fontColor": "#FF1F4799",
                        "color": "#FF1F4799",
                        "backgroundColor": "#331F4799",
                    },
                ],
                "ProgressLine2 currently requires a 2x4 card",
            ),
            (
                "2x4",
                [
                    "progress",
                    "ProgressLine2",
                    {
                        "value": 0,
                        "total": 0,
                        "displayValue": "0分",
                        "fontColor": "#FF1F4799",
                        "color": "#FF1F4799",
                        "backgroundColor": "#331F4799",
                    },
                ],
                "total must be a positive number",
            ),
            (
                "2x4",
                [
                    "metrics",
                    "TopTextBottomValue",
                    {
                        "items": [
                            {"label": "睡眠得分", "value": 80, "unit": "分"},
                            {"label": "今日步数", "value": 2031, "unit": "步"},
                        ],
                        "fontColor": "#FF563D99",
                        "dividerColor": "#33563D99",
                    },
                ],
                "TopTextBottomValue.items requires 3 to 3 entries",
            ),
            (
                "2x4",
                [
                    "details",
                    "TextBlock",
                    {
                        "items": [
                            {"label": "一", "value": "1"},
                            {"label": "二", "value": "2"},
                            {"label": "三", "value": "3"},
                            {"label": "四", "value": "4"},
                            {"label": "五", "value": "5"},
                        ],
                        "fontColor": "#FF563D99",
                        "backgroundColor": "#99FFFFFF",
                    },
                ],
                "TextBlock.items requires 2 to 4 entries",
            ),
            (
                "2x4",
                [
                    "list",
                    "SummaryList",
                    {
                        "items": ["只有一项"],
                        "fontColor": "#FF8C4B1C",
                        "backgroundColor": "#99FFFFFF",
                    },
                ],
                "SummaryList.items requires 2 to 3 entries",
            ),
            (
                "2x4",
                [
                    "display",
                    "DataDisplay",
                    {
                        "label": "倒计时",
                        "value": 32,
                        "supportingText": "天",
                        "fontColor": "#FFFFFFFF",
                    },
                ],
                "DataDisplay currently requires a 2x2 card",
            ),
            (
                "2x4",
                [
                    "action",
                    "CircleButton",
                    {
                        "icon": "resources/base/media/settings.svg",
                        "accessibility": {"label": "打开设置"},
                        "actionSurface": "#331F4799",
                        "actionInk": "#FF1F4799",
                        "onClick": [{"call": "openSettings", "args": {}}],
                    },
                ],
                "CircleButton requires a 2x2 card",
            ),
        )
        for size, component, expected_error in cases:
            with self.subTest(size=size, expected_error=expected_error):
                compact_dsl = _serialize(
                    [
                        [
                            "root",
                            "Column",
                            {"width": "matchParent", "height": "matchParent"},
                            ["progress"],
                        ],
                        component,
                    ]
                )
                with self.assertRaisesRegex(
                    CompactDslConversionError,
                    expected_error,
                ):
                    convert_compact_dsl_to_a2ui(
                        compact_dsl,
                        size=size,
                        protocol_profile=self.profile,
                    )

    def test_icon_pill_button_keeps_explicit_colors_on_known_gradient(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {
                        "width": "matchParent",
                        "height": "matchParent",
                        "linearGradient": {
                            "angle": 180,
                            "colors": [
                                ["#FFFFE9E5", 0],
                                ["#FFFFF6F3", 0.5],
                                ["#FFFFFFFF", 1],
                            ],
                        },
                    },
                    ["cta"],
                ],
                [
                    "cta",
                    "PillButton",
                    {
                        "label": "免打扰设置",
                        "icon": "resources/base/media/moon.svg",
                        "actionSurface": "#FFF0DCB8",
                        "actionInk": "#FF9E6D20",
                        "fontSize": 14,
                        "fontWeight": 500,
                        "onClick": [{"call": "openSettings", "args": {}}],
                    },
                ],
                ["/state/ready", True],
            ]
        )

        result = convert_compact_dsl_to_a2ui(
            compact_dsl,
            size="2x2",
            protocol_profile=self.profile,
        )
        update = json.loads(result.splitlines()[1])["updateComponents"]
        components = {item["id"]: item for item in update["components"]}

        self.assertEqual(
            components["cta"]["styles"]["backgroundColor"],
            "#FFF0DCB8",
        )
        self.assertEqual(
            components["cta_icon"]["styles"]["fillColor"],
            "#FF9E6D20",
        )
        self.assertEqual(
            components["cta_text"]["styles"]["fontColor"],
            "#FF9E6D20",
        )
        self.assertEqual(components["cta_text"]["styles"]["fontWeight"], 500)

    def test_pill_button_uses_versioned_visual_geometry(self) -> None:
        handler = {"call": "openSettings", "args": {}}
        shared_props = {
            "label": "免打扰设置",
            "icon": "resources/base/media/moon.svg",
            "actionSurface": "#FFF0DCB8",
            "actionInk": "#FF9E6D20",
            "fontSize": 14,
            "fontWeight": 500,
            "onClick": [handler],
        }

        def convert(component_type: str, props: dict) -> dict:
            compact_dsl = _serialize(
                [
                    [
                        "root",
                        "Column",
                        {"width": "matchParent", "height": "matchParent"},
                        ["cta"],
                    ],
                    ["cta", component_type, props],
                ]
            )
            result = convert_compact_dsl_to_a2ui(
                compact_dsl,
                size="2x2",
                protocol_profile=self.profile,
            )
            return json.loads(result.splitlines()[1])["updateComponents"]

        pill_output = convert("PillButton", shared_props)
        pill_components = {item["id"]: item for item in pill_output["components"]}
        self.assertEqual(pill_components["cta"]["styles"]["width"], "matchParent")
        self.assertEqual(pill_components["cta"]["styles"]["borderRadius"], 30)
        self.assertEqual(pill_components["cta"]["onClick"], [handler])

    def test_circle_button_expands_inside_right_anchor_slot(self) -> None:
        handler = {"call": "openBluetooth", "args": {}}
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": "matchParent", "height": "matchParent"},
                    ["body"],
                ],
                ["body", "Column", {"width": 126, "height": 100}, ["anchor"]],
                [
                    "anchor",
                    "Row",
                    {
                        "width": 126,
                        "height": 40,
                        "justifyContent": "spaceBetween",
                        "alignItems": "center",
                    },
                    ["hint", "action_slot"],
                ],
                ["hint", "Text", {"content": "蓝牙"}],
                [
                    "action_slot",
                    "Stack",
                    {"width": 40, "height": 40, "alignContent": "center"},
                    ["action"],
                ],
                [
                    "action",
                    "CircleButton",
                    {
                        "icon": "resources/base/media/bluetooth_fill.svg",
                        "accessibility": {"label": "打开蓝牙设置"},
                        "actionSurface": "#331F4799",
                        "actionInk": "#FF1F4799",
                        "onClick": [handler],
                    },
                ],
            ]
        )

        result = convert_compact_dsl_to_a2ui(
            compact_dsl,
            size="2x2",
            protocol_profile=self.profile,
        )
        update = json.loads(result.splitlines()[1])["updateComponents"]
        components = {item["id"]: item for item in update["components"]}

        self.assertEqual(components["action"]["component"], "Stack")
        self.assertEqual(components["action"]["styles"]["width"], 40)
        self.assertEqual(components["action"]["styles"]["height"], 40)
        self.assertEqual(components["action"]["styles"]["borderRadius"], 20)
        self.assertEqual(components["action_icon"]["styles"]["width"], 20)
        self.assertEqual(components["action"]["onClick"], [handler])

    def test_circle_button_rejects_missing_anchor_slot(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": "matchParent", "height": "matchParent"},
                    ["action"],
                ],
                [
                    "action",
                    "CircleButton",
                    {
                        "icon": "resources/base/media/bluetooth_fill.svg",
                        "accessibility": {"label": "打开蓝牙设置"},
                        "actionSurface": "#331F4799",
                        "actionInk": "#FF1F4799",
                        "onClick": [{"call": "openBluetooth", "args": {}}],
                    },
                ],
            ]
        )

        with self.assertRaisesRegex(
            CompactDslConversionError,
            "CircleButton requires a centered 40x40 Stack slot",
        ):
            convert_compact_dsl_to_a2ui(
                compact_dsl,
                size="2x2",
                protocol_profile=self.profile,
            )

    def test_circle_button_requires_accessibility_label(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": "matchParent", "height": "matchParent"},
                    ["body"],
                ],
                ["body", "Column", {"width": 126, "height": 100}, ["anchor"]],
                [
                    "anchor",
                    "Row",
                    {
                        "width": 126,
                        "height": 40,
                        "justifyContent": "spaceBetween",
                        "alignItems": "center",
                    },
                    ["hint", "action_slot"],
                ],
                ["hint", "Text", {"content": "蓝牙"}],
                [
                    "action_slot",
                    "Stack",
                    {"width": 40, "height": 40, "alignContent": "center"},
                    ["action"],
                ],
                [
                    "action",
                    "CircleButton",
                    {
                        "icon": "resources/base/media/bluetooth_fill.svg",
                        "actionSurface": "#331F4799",
                        "actionInk": "#FF1F4799",
                        "onClick": [{"call": "openBluetooth", "args": {}}],
                    },
                ],
            ]
        )

        with self.assertRaisesRegex(
            CompactDslConversionError,
            "CircleButton requires accessibility",
        ):
            convert_compact_dsl_to_a2ui(
                compact_dsl,
                size="2x2",
                protocol_profile=self.profile,
            )

    def test_rejects_pill_button_missing_required_props_without_key_error(self) -> None:
        handler = {"call": "openWeather", "args": {}}
        cases = (
            (
                {
                    "label": "查看天气",
                    "actionInk": "#FF1F4799",
                    "onClick": [handler],
                },
                "PillButton requires actionSurface",
            ),
            (
                {
                    "actionInk": "#FF1F4799",
                    "actionSurface": "#331F4799",
                    "onClick": [handler],
                },
                "PillButton requires label",
            ),
            (
                {
                    "label": "查看天气",
                    "actionInk": "#FF1F4799",
                    "actionSurface": "#331F4799",
                },
                "PillButton requires onClick",
            ),
        )
        for props, expected_error in cases:
            with self.subTest(expected_error=expected_error):
                compact_dsl = _serialize(
                    [
                        [
                            "root",
                            "Column",
                            {"width": 160, "height": 160},
                            ["cta"],
                        ],
                        ["cta", "PillButton", props],
                        ["/state/ready", True],
                    ]
                )
                with self.assertRaisesRegex(
                    CompactDslConversionError,
                    expected_error,
                ):
                    convert_compact_dsl_to_a2ui(
                        compact_dsl,
                        size="2x2",
                        protocol_profile=self.profile,
                    )

    def test_reports_removed_action_unit_before_conversion(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": 160, "height": 160},
                    ["cta"],
                ],
                [
                    "cta",
                    "ActionUnit",
                    {"state": "capsule", "label": "查看天气"},
                ],
                ["/state/ready", True],
            ]
        )

        with self.assertRaisesRegex(
            CompactDslValidationError,
            "unsupported component type ActionUnit",
        ):
            validate_compact_dsl(
                compact_dsl,
                task_spec={
                    "dataModelSchema": {"data": {}},
                    "assetCandidates": [],
                    "eventCandidates": [{"call": "openWeather", "args": {}}],
                },
                card_spec={"dataBindings": []},
            )

    def test_rejects_on_click_that_does_not_match_event_candidate(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {
                        "width": 160,
                        "height": 160,
                        "onClick": [{"call": "openCalendar", "args": {}}],
                    },
                    [],
                ],
                ["/state/ready", True],
            ]
        )

        with self.assertRaisesRegex(
            CompactDslValidationError,
            "must exactly match a TaskSpec eventCandidate",
        ):
            validate_compact_dsl(
                compact_dsl,
                task_spec={
                    "dataModelSchema": {"data": {}},
                    "assetCandidates": [],
                    "eventCandidates": [{"call": "openWeather", "args": {}}],
                },
                card_spec={"dataBindings": []},
            )

    def test_accepts_one_genui_fence(self) -> None:
        fenced = f"```genui\n{self.compact_dsl}\n```"

        result = convert_compact_dsl_to_a2ui(
            fenced,
            size="2x2",
            protocol_profile=self.profile,
        )

        self.assertEqual(len(result.splitlines()), 3)

    def test_repairs_bom_json_fence_and_surrounding_text(self) -> None:
        source = f"\ufeffModel output follows.\n```json\n{self.compact_dsl}\n```\nEnd of output."

        result = convert_compact_dsl_to_a2ui(
            source,
            size="2x2",
            protocol_profile=self.profile,
        )

        self.assertEqual(len(result.splitlines()), 3)

    def test_repairs_unclosed_fence_and_extra_eof_closers(self) -> None:
        source = f"```genui\n{self.compact_dsl}\n]}}"

        result = convert_compact_dsl_to_a2ui(
            source,
            size="2x2",
            protocol_profile=self.profile,
        )

        self.assertEqual(len(result.splitlines()), 3)

    def test_repairs_concatenated_and_multiline_rows(self) -> None:
        source_rows = self.compact_dsl.splitlines()
        concatenated = "".join(source_rows)
        multiline_rows: list[str] = []
        for row in source_rows:
            value = json.loads(row)
            multiline_rows.append(json.dumps(value, ensure_ascii=False, indent=2))

        for source in (concatenated, "\n".join(multiline_rows)):
            with self.subTest(source_length=len(source)):
                result = convert_compact_dsl_to_a2ui(
                    source,
                    size="2x2",
                    protocol_profile=self.profile,
                )
                self.assertEqual(len(result.splitlines()), 3)

    def test_repairs_component_rows_emitted_out_of_order(self) -> None:
        source_rows = self.compact_dsl.splitlines()
        component_rows = list(reversed(source_rows[:5]))
        data_rows = source_rows[5:]

        result = convert_compact_dsl_to_a2ui(
            "\n".join([*component_rows, *data_rows]),
            size="2x2",
            protocol_profile=self.profile,
        )

        update_components = json.loads(result.splitlines()[1])
        components = update_components["updateComponents"]["components"]
        self.assertEqual(components[0]["id"], "root")
        self.assertEqual(
            [component["id"] for component in components],
            ["root", "title", "events", "event_title", "action"],
        )

    def test_reports_missing_root_as_possible_truncated_output(self) -> None:
        source_rows = self.compact_dsl.splitlines()[1:]

        with self.assertRaisesRegex(
            CompactDslConversionError,
            "The root component is missing; model output may be truncated",
        ):
            convert_compact_dsl_to_a2ui(
                "\n".join(source_rows),
                size="2x2",
                protocol_profile=self.profile,
            )

    def test_accepts_root_row_for_wide_card(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Row",
                    {"width": 320, "height": 160, "itemMargin": 8},
                    ["title", "value"],
                ],
                ["title", "Text", {"content": "通勤助手"}],
                ["value", "Text", {"content": "09:30"}],
            ]
        )

        result = convert_compact_dsl_to_a2ui(
            compact_dsl,
            size="2x4",
            protocol_profile=self.profile,
        )
        update_components = json.loads(result.splitlines()[1])
        components = update_components["updateComponents"]["components"]

        self.assertEqual(components[0]["id"], "root")
        self.assertEqual(components[0]["component"], "Row")

    def test_repairs_trailing_comma_and_missing_eof_closer(self) -> None:
        source_rows = self.compact_dsl.splitlines()
        source_rows[0] = f"{source_rows[0][:-1]},]"
        source_rows[-1] = source_rows[-1][:-1]

        result = convert_compact_dsl_to_a2ui(
            "\n".join(source_rows),
            size="2x2",
            protocol_profile=self.profile,
        )

        self.assertEqual(len(result.splitlines()), 3)

    def test_omits_surface_dimensions_for_4x2(self) -> None:
        wide_rows = [
            [
                "root",
                "Column",
                {
                    "width": 320,
                    "height": 160,
                    "padding": 8,
                    "itemMargin": 8,
                },
                ["title"],
            ],
            [
                "title",
                "Text",
                {"content": "横向卡片", "design": "body-regular-sm"},
            ],
        ]

        result = convert_compact_dsl_to_a2ui(
            _serialize(wide_rows),
            size="4x2",
            protocol_profile=self.profile,
        )
        create_surface = json.loads(result.splitlines()[0])["createSurface"]

        self.assertNotIn("width", create_surface)
        self.assertNotIn("height", create_surface)

    def test_validates_task_and_capability_context(self) -> None:
        result = validate_compact_dsl(
            self.compact_dsl,
            task_spec=self.task_spec,
            card_spec=self.card_spec,
        )

        self.assertEqual(result.warnings, ())

    def test_rejects_fixed_root_children_that_overflow_safe_height(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {
                        "width": "matchParent",
                        "height": "matchParent",
                        "padding": 12,
                        "itemMargin": 8,
                    },
                    ["title_area", "zone_top", "zone_bottom"],
                ],
                ["title_area", "Text", {"content": "标题", "height": 20}],
                ["zone_top", "Text", {"content": "上区", "height": 64}],
                ["zone_bottom", "Text", {"content": "下区", "height": 64}],
            ]
        )

        with self.assertRaisesRegex(
            CompactDslValidationError,
            "vertical layout requires at least 164vp within 126vp",
        ):
            validate_compact_dsl(
                compact_dsl,
                task_spec={
                    "size": "2x2",
                    "dataModelSchema": {},
                    "assetCandidates": [],
                    "eventCandidates": [],
                },
                card_spec={"suggestSize": "2x2", "dataBindings": []},
            )

    def test_rejects_distributed_root_when_minimum_gaps_overflow(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {
                        "width": "matchParent",
                        "height": "matchParent",
                        "padding": 12,
                        "itemMargin": 8,
                        "justifyContent": "spaceBetween",
                    },
                    ["health_area", "battery_area", "action_area"],
                ],
                ["health_area", "Text", {"content": "健康", "height": 64}],
                ["battery_area", "Text", {"content": "电池", "height": 40}],
                ["action_area", "Column", {}, ["cta"]],
                ["cta", "Text", {"content": "补充信息", "height": 36}],
            ]
        )

        with self.assertRaises(CompactDslValidationError) as raised:
            validate_compact_dsl(
                compact_dsl,
                task_spec={
                    "size": "2x4",
                    "dataModelSchema": {},
                    "assetCandidates": [],
                    "eventCandidates": [],
                },
                card_spec={"suggestSize": "2x4", "dataBindings": []},
            )

        message = str(raised.exception)
        self.assertIn(
            "vertical layout requires at least 156vp within 126vp",
            message,
        )

    def test_accepts_distributed_root_with_item_margin_when_it_fits(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {
                        "width": "matchParent",
                        "height": "matchParent",
                        "padding": 12,
                        "itemMargin": 4,
                        "justifyContent": "spaceBetween",
                    },
                    ["title_area", "content_area", "action_area"],
                ],
                ["title_area", "Text", {"content": "标题", "height": 20}],
                ["content_area", "Text", {"content": "内容", "height": 40}],
                ["action_area", "Column", {}, ["cta"]],
                ["cta", "Text", {"content": "补充信息", "height": 36}],
            ]
        )

        result = validate_compact_dsl(
            compact_dsl,
            task_spec={
                "size": "2x2",
                "dataModelSchema": {},
                "assetCandidates": [],
                "eventCandidates": [],
            },
            card_spec={"suggestSize": "2x2", "dataBindings": []},
        )

        self.assertEqual(result.warnings, ())

    def test_accepts_s4_vertical_regions_at_exact_safe_height(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {
                        "width": "matchParent",
                        "height": "matchParent",
                        "padding": 8,
                        "itemMargin": 8,
                    },
                    ["zone_top", "zone_bottom"],
                ],
                ["zone_top", "Text", {"content": "上区", "height": 63}],
                ["zone_bottom", "Text", {"content": "下区", "height": 63}],
            ]
        )

        result = validate_compact_dsl(
            compact_dsl,
            task_spec={
                "size": "2x2",
                "dataModelSchema": {},
                "assetCandidates": [],
                "eventCandidates": [],
            },
            card_spec={"suggestSize": "2x2", "dataBindings": []},
        )

        self.assertEqual(result.warnings, ())

    def test_validates_sparse_projected_array_index(self) -> None:
        compact_dsl = _serialize(
            [
                ["root", "Column", {"width": 160, "height": 160}, ["weather"]],
                [
                    "weather",
                    "Text",
                    {"content": {"path": "/data/weather/daily/4/condition"}},
                ],
                ["/data/weather/daily/4/condition", "多云"],
            ]
        )
        daily_schema = [{}, {}, {}, {}, {"condition": {"type": "string"}}]
        task_spec = {
            "dataModelSchema": {"data": {"weather": {"daily": daily_schema}}},
            "assetCandidates": [],
            "eventCandidates": [],
        }
        card_spec = {
            "dataBindings": [{"writeResultTo": "/data/weather"}],
        }

        repaired = repair_compact_dsl_binding_paths(
            compact_dsl,
            task_spec=task_spec,
            card_spec=card_spec,
        )
        result = validate_compact_dsl(
            repaired,
            task_spec=task_spec,
            card_spec=card_spec,
        )

        self.assertEqual(repaired, compact_dsl)
        self.assertEqual(result.warnings, ())

    def test_validates_array_index_against_homogeneous_item_schema(self) -> None:
        compact_dsl = _serialize(
            [
                ["root", "Column", {"width": 160, "height": 160}, ["weather"]],
                [
                    "weather",
                    "Text",
                    {"content": {"path": "/data/weather/daily/4/condition"}},
                ],
                ["/data/weather/daily/4/condition", "多云"],
            ]
        )
        task_spec = {
            "dataModelSchema": {
                "data": {
                    "weather": {
                        "daily": [{"condition": {"type": "string"}}],
                    }
                }
            },
            "assetCandidates": [],
            "eventCandidates": [],
        }
        card_spec = {
            "dataBindings": [{"writeResultTo": "/data/weather"}],
        }

        result = validate_compact_dsl(
            compact_dsl,
            task_spec=task_spec,
            card_spec=card_spec,
        )

        self.assertEqual(result.warnings, ())

    def test_rejects_expression_that_wraps_quoted_json_pointer(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": 160, "height": 160},
                    ["temperature"],
                ],
                [
                    "temperature",
                    "Text",
                    {"content": ("{{ '/data/weather/current/temperatureText' }}")},
                ],
                ["/data/weather/current/temperatureText", "26℃"],
            ]
        )

        with self.assertRaisesRegex(
            CompactDslValidationError,
            "expression wraps quoted JSON Pointer",
        ):
            validate_compact_dsl(
                compact_dsl,
                task_spec={
                    "dataModelSchema": {"data": {}},
                    "assetCandidates": [],
                    "eventCandidates": [],
                },
                card_spec={"dataBindings": []},
            )

    def test_rejects_quoted_json_pointer_mixed_with_valid_binding(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": 160, "height": 160},
                    ["reminder"],
                ],
                [
                    "reminder",
                    "Text",
                    {
                        "content": (
                            "{{ '/data/calendar/events/0/dtStart' + ' · ' + "
                            "${/data/calendar/events/0/remindTime/0} }}"
                        )
                    },
                ],
                ["/data/calendar/events/0/dtStart", "14:00"],
                ["/data/calendar/events/0/remindTime/0", "15"],
            ]
        )
        task_spec = {
            "dataModelSchema": {
                "data": {
                    "calendar": {
                        "events": [
                            {
                                "dtStart": {"type": "string"},
                                "remindTime": [{"type": "string"}],
                            }
                        ]
                    }
                }
            },
            "assetCandidates": [],
            "eventCandidates": [],
        }

        with self.assertRaisesRegex(
            CompactDslValidationError,
            "expression wraps quoted JSON Pointer",
        ):
            validate_compact_dsl(
                compact_dsl,
                task_spec=task_spec,
                card_spec={"dataBindings": []},
            )

    def test_allows_slash_as_expression_display_separator(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": 160, "height": 160},
                    ["ratio"],
                ],
                [
                    "ratio",
                    "Text",
                    {"content": ("{{ ${/data/metrics/used} + '/' + ${/data/metrics/total} }}")},
                ],
                ["/data/metrics/used", 2],
                ["/data/metrics/total", 5],
            ]
        )
        task_spec = {
            "dataModelSchema": {
                "data": {
                    "metrics": {
                        "used": {"type": "integer"},
                        "total": {"type": "integer"},
                    }
                }
            },
            "assetCandidates": [],
            "eventCandidates": [],
        }

        result = validate_compact_dsl(
            compact_dsl,
            task_spec=task_spec,
            card_spec={"dataBindings": []},
        )

        self.assertEqual(result.warnings, ())

    def test_rejects_compact_data_path_missing_from_task_spec(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": 160, "height": 160},
                    ["temperature"],
                ],
                [
                    "temperature",
                    "Text",
                    {"content": ("{{ ${/data/weather/current/temperatureText} }}")},
                ],
                ["/data/weather/current/temperatureText", "26℃"],
            ]
        )

        with self.assertRaisesRegex(
            CompactDslValidationError,
            "path is not declared by TaskSpec.dataModelSchema",
        ):
            validate_compact_dsl(
                compact_dsl,
                task_spec={
                    "dataModelSchema": {"data": {}},
                    "assetCandidates": [],
                    "eventCandidates": [],
                },
                card_spec={"dataBindings": []},
            )

    def test_repairs_only_unique_missing_data_root(self) -> None:
        rows = [
            ["root", "Column", {"width": 160, "height": 160}, ["value"]],
            [
                "value",
                "Text",
                {"content": {"path": "/data/current/temperatureC"}},
            ],
            ["/data/current/temperatureC", 26],
        ]
        schema = {
            "current": {
                "temperatureC": {
                    "type": "number",
                    "sampleValue": 26,
                },
            },
        }
        task_spec = {
            "dataModelSchema": {"data": {"weather": schema}},
        }
        card_spec = {
            "dataBindings": [{"writeResultTo": "/data/weather"}],
        }
        compact_dsl = _serialize(rows)

        repaired = repair_compact_dsl_binding_paths(
            compact_dsl,
            task_spec=task_spec,
            card_spec=card_spec,
        )
        repaired_rows = [json.loads(line) for line in repaired.splitlines()]
        self.assertEqual(
            repaired_rows[1][2]["content"]["path"],
            "/data/weather/current/temperatureC",
        )
        self.assertEqual(
            repaired_rows[2][0],
            "/data/weather/current/temperatureC",
        )

        task_spec["dataModelSchema"]["data"]["backup"] = schema
        card_spec["dataBindings"].append({"writeResultTo": "/data/backup"})
        self.assertEqual(
            repair_compact_dsl_binding_paths(
                compact_dsl,
                task_spec=task_spec,
                card_spec=card_spec,
            ),
            compact_dsl,
        )

    def test_does_not_replace_different_event_item_index(self) -> None:
        event_handler = {
            "call": "clickToIntent",
            "args": {
                "intentName": "ViewCalendarEvent",
                "params": {
                    "entityId": {
                        "path": "/data/calendar/events/1/entityId",
                    },
                },
            },
        }
        rows = [
            ["root", "Column", {"width": 160, "height": 160}, ["event1"]],
            [
                "event1",
                "Column",
                {"onClick": [event_handler]},
                ["event1_title"],
            ],
            [
                "event1_title",
                "Text",
                {"content": {"path": "/data/calendar/events/1/title"}},
            ],
        ]
        task_spec = {
            "dataModelSchema": {
                "data": {
                    "calendar": {
                        "events": [
                            {"entityId": {"type": "string"}},
                            {
                                "title": {"type": "string"},
                                "entityId": {"type": "string"},
                            },
                        ],
                    },
                },
            },
            "eventCandidates": [
                {
                    "call": "clickToIntent",
                    "args": {
                        "intentName": "ViewCalendarEvent",
                        "params": {
                            "entityId": {
                                "path": "/data/calendar/events/0/entityId",
                            },
                        },
                    },
                },
            ],
        }
        compact_dsl = _serialize(rows)

        repaired = repair_compact_dsl_binding_paths(
            compact_dsl,
            task_spec=task_spec,
            card_spec={"dataBindings": [{"writeResultTo": "/data/calendar"}]},
        )

        repaired_handler = json.loads(repaired.splitlines()[1])[2]["onClick"][0]
        self.assertEqual(
            repaired_handler["args"]["params"]["entityId"]["path"],
            "/data/calendar/events/1/entityId",
        )

    def test_does_not_restore_invalid_weather_uri_after_repair(self) -> None:
        repaired_uri = (
            "{{ 'hww://www.huawei.com/totemweather?enterType=share&cityCode=' "
            "+ ${/data/weather/location/cityCode} }}"
        )
        invalid_candidate_uri = (
            "hww://www.huawei.com/totemweather?enterType=share&"
            "cityCode={{ ${/data/weather/location/cityCode} }}"
        )
        handler = {
            "call": "clickToDeeplink",
            "args": {
                "intentName": "Weather_CityCode",
                "bundleName": "",
                "abilityName": "",
                "uri": repaired_uri,
            },
        }
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": 160, "height": 160, "onClick": [handler]},
                    [],
                ],
            ]
        )
        task_spec = {
            "eventCandidates": [
                {
                    "call": "clickToDeeplink",
                    "args": {
                        "intentName": "Weather_CityCode",
                        "bundleName": "",
                        "abilityName": "",
                        "uri": invalid_candidate_uri,
                    },
                }
            ],
        }

        repaired = repair_compact_dsl_binding_paths(
            compact_dsl,
            task_spec=task_spec,
            card_spec={"dataBindings": []},
        )

        repaired_handler = json.loads(repaired)[2]["onClick"][0]
        self.assertEqual(repaired_handler["args"]["uri"], repaired_uri)

    def test_inlines_local_values_without_data_capabilities(self) -> None:
        rows = [
            [
                "root",
                "Column",
                {"width": 160, "height": 160},
                ["value", "progress"],
            ],
            ["value", "Text", {"content": {"path": "/battery/level"}}],
            [
                "progress",
                "ProgressCircle",
                {
                    "externalText": {"path": "/battery/level"},
                    "icon": "resources/base/media/battery.svg",
                    "accessibility": {"label": "电量百分比"},
                    "width": 44,
                    "height": 60,
                    "fontColor": "#FF1F4799",
                    "fillColor": "#991F4799",
                    "color": "#FF1F4799",
                    "backgroundColor": "#331F4799",
                },
            ],
            ["/battery/level", 68],
        ]
        repaired = repair_compact_dsl_binding_paths(
            _serialize(rows),
            task_spec={"dataModelSchema": {}},
            card_spec={"dataBindings": []},
        )
        repaired_rows = [json.loads(line) for line in repaired.splitlines()]

        self.assertEqual(repaired_rows[1][2]["content"], "68")
        self.assertEqual(repaired_rows[2][2]["externalText"], 68)
        self.assertEqual(len(repaired_rows), 3)
        validate_compact_dsl(
            repaired,
            task_spec={
                "size": "2x2",
                "dataModelSchema": {},
                "assetCandidates": [
                    {
                        "src": "resources/base/media/battery.svg",
                        "description": "可染色的电量单色图标",
                    }
                ],
                "eventCandidates": [],
            },
            card_spec={"suggestSize": "2x2", "dataBindings": []},
        )

    def test_rejects_data_value_that_disagrees_with_schema_type(self) -> None:
        rows = [
            [
                "root",
                "Column",
                {"width": 160, "height": 160},
                ["humidity"],
            ],
            [
                "humidity",
                "Text",
                {"content": {"path": "/data/weather/humidityPercent"}},
            ],
            ["/data/weather/humidityPercent", "68%"],
        ]
        task_spec = {
            "dataModelSchema": {
                "data": {
                    "weather": {
                        "humidityPercent": {
                            "type": "number",
                            "sampleValue": 68,
                        },
                    },
                },
            },
            "assetCandidates": [],
            "eventCandidates": [],
        }
        card_spec = {
            "dataBindings": [
                {
                    "capabilityId": "ViewWeather",
                    "arguments": {},
                    "writeResultTo": "/data/weather",
                },
            ],
        }

        with self.assertRaisesRegex(
            CompactDslValidationError,
            "does not match schema type number",
        ):
            validate_compact_dsl(
                _serialize(rows),
                task_spec=task_spec,
                card_spec=card_spec,
            )

    def test_warns_when_declared_data_capability_is_unused(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": 160, "height": 160},
                    ["title"],
                ],
                ["title", "Text", {"content": "Static title"}],
            ]
        )

        result = validate_compact_dsl(
            compact_dsl,
            task_spec={
                "dataModelSchema": {"data": {"weather": {}}},
                "assetCandidates": [],
                "eventCandidates": [],
            },
            card_spec={
                "dataBindings": [
                    {
                        "capabilityId": "ViewWeather",
                        "arguments": {},
                        "writeResultTo": "/data/weather",
                    },
                ],
            },
        )

        self.assertEqual(len(result.warnings), 1)
        self.assertIn("/data/weather", result.warnings[0])


if __name__ == "__main__":
    unittest.main()
