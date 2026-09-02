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
        values.append(
            json.dumps(row, ensure_ascii=False, separators=(",", ":"))
        )
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
                "List",
                {"space": 4},
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
                "Button",
                {
                    "label": "查看详情",
                    "design": "action-capsule-primary",
                    "width": "matchParent",
                    "onClick": [
                        {
                            "call": "clickToApi",
                            "args": {
                                "intentName": "ViewDetail",
                                "params": {
                                    "entityId": {
                                        "path": (
                                            "/data/calendar/events/0/entityId"
                                        ),
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
            "dataBindings": [
                {
                    "capabilityId": "GetCalendarEvents",
                    "arguments": {},
                    "writeResultTo": "/data",
                },
            ],
        }

    def test_expands_only_current_prompt_design_aliases(self) -> None:
        normalized = normalize_compact_dsl_design_tokens(self.compact_dsl)
        rows = [json.loads(line) for line in normalized.splitlines()]
        components = {}
        for row in rows:
            if len(row) >= 3:
                components[row[0]] = row

        self.assertEqual(components["root"][2]["padding"], 8)
        self.assertEqual(components["title"][2]["fontSize"], 14)
        self.assertEqual(components["title"][2]["fontWeight"], 500)
        self.assertEqual(components["title"][2]["fontColor"], "#E5000000")
        self.assertNotIn("design", components["title"][2])
        self.assertEqual(components["action"][2]["height"], 36)
        self.assertEqual(components["action"][2]["borderRadius"], 20)
        self.assertEqual(
            components["action"][2]["padding"],
            {"left": 8, "top": 0, "right": 8, "bottom": 0},
        )
        self.assertEqual(components["action"][2]["minFontSize"], 12)
        self.assertEqual(components["action"][2]["maxFontSize"], 14)
        self.assertEqual(components["action"][2]["fontWeight"], 500)
        self.assertEqual(
            components["action"][2]["backgroundColor"],
            "#190A59F7",
        )

    def test_expands_action_icon_round_design(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": 160, "height": 160},
                    ["action"],
                ],
                [
                    "action",
                    "Button",
                    {"label": "打开", "design": "action-icon-round"},
                ],
            ]
        )

        normalized = normalize_compact_dsl_design_tokens(compact_dsl)
        action = json.loads(normalized.splitlines()[1])

        self.assertEqual(action[2]["width"], 30)
        self.assertEqual(action[2]["height"], 30)
        self.assertEqual(action[2]["borderRadius"], 15)
        self.assertEqual(action[2]["padding"], 0)
        self.assertIn("label", action[2])
        self.assertNotIn("design", action[2])

    def test_preserves_button_image_child_in_a2ui(self) -> None:
        event = {
            "call": "clickToApi",
            "args": {"intentName": "Open"},
        }
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": 160, "height": 160},
                    ["action"],
                ],
                [
                    "action",
                    "Button",
                    {
                        "label": "Open",
                        "design": "action-icon-round",
                        "onClick": [
                            {
                                "call": event["call"],
                                "args": event["args"],
                            }
                        ],
                    },
                    ["action_icon"],
                ],
                [
                    "action_icon",
                    "Image",
                    {"src": "resources/base/media/weather.svg"},
                ],
            ]
        )

        normalized = normalize_compact_dsl_design_tokens(compact_dsl)
        rows = [json.loads(line) for line in normalized.splitlines()]

        self.assertEqual(
            [row[0] for row in rows],
            ["root", "action", "action_icon"],
        )
        self.assertEqual(rows[1][3], ["action_icon"])
        validate_compact_dsl(
            compact_dsl,
            task_spec={
                "dataModelSchema": {},
                "assetCandidates": [
                    {"src": "resources/base/media/weather.svg"},
                ],
                "eventCandidates": [event],
            },
            card_spec={"dataBindings": []},
        )
        a2ui = convert_compact_dsl_to_a2ui(
            compact_dsl,
            size="2x2",
            protocol_profile=self.profile,
        )
        messages = [json.loads(line) for line in a2ui.splitlines()]
        components = messages[1]["updateComponents"]["components"]

        self.assertEqual(
            [component["id"] for component in components],
            ["root", "action", "action_icon"],
        )
        self.assertEqual(components[1]["children"], ["action_icon"])
        self.assertNotIn("label", components[1])
        self.assertEqual(
            components[2]["src"],
            "resources/base/media/weather.svg",
        )

    def test_preserves_label_less_icon_round_button_image_child(self) -> None:
        event = {
            "call": "clickToDeeplink",
            "args": {
                "intentName": "Music",
                "uri": "hwmusic://com.huawei.hmsapp.music/showMusicList",
            },
        }
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": 160, "height": 160},
                    ["action_area"],
                ],
                [
                    "action_area",
                    "Column",
                    {"flexShrink": 0},
                    ["cta"],
                ],
                [
                    "cta",
                    "Button",
                    {
                        "design": "action-icon-round",
                        "fontColor": "#FF0A59F7",
                        "onClick": [event],
                    },
                    ["action_icon"],
                ],
                [
                    "action_icon",
                    "Image",
                    {
                        "width": 16,
                        "height": 16,
                        "src": "resources/base/media/play_fill.svg",
                    },
                ],
            ]
        )

        a2ui = convert_compact_dsl_to_a2ui(
            compact_dsl,
            size="2x2",
            protocol_profile=self.profile,
        )
        components = json.loads(a2ui.splitlines()[1])["updateComponents"]["components"]
        components_by_id = {component["id"]: component for component in components}

        self.assertEqual(components_by_id["action_area"]["children"], ["cta"])
        self.assertEqual(components_by_id["cta"]["children"], ["action_icon"])
        self.assertNotIn("label", components_by_id["cta"])
        self.assertEqual(
            components_by_id["action_icon"]["src"],
            "resources/base/media/play_fill.svg",
        )

    def test_repairs_empty_button_label(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": 160, "height": 160},
                    ["navigate_btn"],
                ],
                [
                    "navigate_btn",
                    "Button",
                    {
                        "label": "",
                        "onClick": [
                            {
                                "call": "clickToIntent",
                                "args": {"intentName": "StartNavigate"},
                            },
                        ],
                    },
                ],
            ]
        )

        a2ui = convert_compact_dsl_to_a2ui(
            compact_dsl,
            size="2x2",
            protocol_profile=self.profile,
        )
        messages = [json.loads(line) for line in a2ui.splitlines()]
        components = messages[1]["updateComponents"]["components"]

        self.assertEqual(components[1]["label"], "")

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

    def test_preserves_non_image_button_child(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": 160, "height": 160},
                    ["action"],
                ],
                [
                    "action",
                    "Button",
                    {"label": "Open", "design": "action-capsule-primary"},
                    ["action_text"],
                ],
                ["action_text", "Text", {"content": "Open"}],
            ]
        )

        normalized = normalize_compact_dsl_design_tokens(compact_dsl)
        action = json.loads(normalized.splitlines()[1])

        self.assertEqual(action[3], ["action_text"])

    def test_expands_latest_text_progress_and_checkbox_designs(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": 160, "height": 160},
                    [
                        "metric",
                        "linear",
                        "segmented",
                        "threshold",
                        "choice",
                    ],
                ],
                [
                    "metric",
                    "Text",
                    {"content": "68%", "design": "metric-display-md"},
                ],
                [
                    "linear",
                    "Progress",
                    {
                        "value": 68,
                        "total": 100,
                        "design": "progress-linear-primary",
                    },
                ],
                [
                    "segmented",
                    "Progress",
                    {
                        "value": 2,
                        "total": 4,
                        "design": "progress-linear-segmented",
                    },
                ],
                [
                    "threshold",
                    "Progress",
                    {
                        "value": 80,
                        "threshold": 60,
                        "total": 100,
                        "design": "progress-linear-threshold",
                    },
                ],
                [
                    "choice",
                    "Checkbox",
                    {
                        "label": "同意",
                        "select": True,
                        "design": "checkbox-circle-default",
                    },
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
        self.assertEqual(components["linear"]["type"], "linear")
        self.assertEqual(components["linear"]["height"], 8)
        self.assertEqual(components["linear"]["borderRadius"], 4)
        self.assertEqual(components["segmented"]["height"], 8)
        self.assertEqual(components["threshold"]["height"], 20)
        self.assertEqual(components["threshold"]["backgroundColor"], "#6B7F91")
        self.assertEqual(components["threshold"]["color"], "#C8F000")
        self.assertEqual(components["choice"]["selectedColor"], "#FF0A59F7")
        self.assertEqual(components["choice"]["unSelectedColor"], "#66000000")
        self.assertEqual(
            components["choice"]["mark"],
            {"strokeColor": "#FFFFFFFF", "size": 20, "strokeWidth": 2},
        )

        a2ui = convert_compact_dsl_to_a2ui(
            compact_dsl,
            size="2x2",
            protocol_profile=self.profile,
        )
        update = json.loads(a2ui.splitlines()[1])["updateComponents"]
        a2ui_components = {}
        for component in update["components"]:
            a2ui_components[component["id"]] = component
        self.assertNotIn("threshold", a2ui_components["threshold"]["styles"])

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
        self.assertEqual(components["events"]["space"], 4)
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

    def test_action_unit_capsule_uses_explicit_surface_and_text_style(self) -> None:
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
                    "ActionUnit",
                    {
                        "state": "capsule",
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
        self.assertEqual(action_styles["borderRadius"], 20)
        self.assertEqual(action_styles["fontSize"], 14)
        self.assertEqual(action_styles["fontWeight"], 400)

    def test_icon_action_unit_keeps_explicit_colors_on_known_gradient(self) -> None:
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
                    "ActionUnit",
                    {
                        "state": "capsule",
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

    def test_rejects_action_unit_missing_required_props_without_key_error(self) -> None:
        handler = {"call": "openWeather", "args": {}}
        cases = (
            ({"label": "查看天气", "onClick": [handler]}, "ActionUnit.state"),
            ({"state": "capsule", "onClick": [handler]}, "ActionUnit.label"),
            ({"state": "capsule", "label": "查看天气"}, "ActionUnit.onClick"),
            ({"state": "icon-round", "onClick": [handler]}, "ActionUnit.icon"),
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
                        ["cta", "ActionUnit", props],
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

    def test_reports_missing_action_unit_on_click_before_conversion(self) -> None:
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
            "ActionUnit.onClick is required",
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
        source = (
            "\ufeffModel output follows.\n"
            f"```json\n{self.compact_dsl}\n```\n"
            "End of output."
        )

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
                    {
                        "content": (
                            "{{ '/data/weather/current/temperatureText' }}"
                        )
                    },
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
                    {
                        "content": (
                            "{{ ${/data/weather/current/temperatureText} }}"
                        )
                    },
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
        card_spec["dataBindings"].append(
            {"writeResultTo": "/data/backup"}
        )
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
                "Progress",
                {"value": {"path": "/battery/level"}, "total": 100},
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
        self.assertEqual(repaired_rows[2][2]["value"], 68)
        self.assertEqual(len(repaired_rows), 3)
        validate_compact_dsl(
            repaired,
            task_spec={
                "dataModelSchema": {},
                "assetCandidates": [],
                "eventCandidates": [],
            },
            card_spec={"dataBindings": []},
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
