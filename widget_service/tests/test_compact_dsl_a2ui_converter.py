# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from convert_compact_dsl_to_a2ui import main
from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    convert_compact_dsl_to_a2ui,
    normalize_compact_dsl_design_tokens,
    repair_compact_dsl_binding_paths,
    validate_compact_dsl_context,
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
                    "design": "subtitle-s",
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
                    "design": "body-s",
                    "fontColor": "font_secondary",
                },
            ],
            [
                "action",
                "Button",
                {
                    "label": "查看详情",
                    "design": "capsule",
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
        self.assertEqual(
            components["action"][2]["backgroundColor"],
            "#0C000000",
        )

    def test_expands_icon_round_design_alias(self) -> None:
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
                    {"label": "打开", "design": "icon-round"},
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

    def test_degrades_button_image_child_to_a2ui_leaf(self) -> None:
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
                        "design": "icon-round",
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

        self.assertEqual([row[0] for row in rows], ["root", "action"])
        self.assertEqual(len(rows[1]), 3)
        validate_compact_dsl_context(
            compact_dsl,
            task_spec={
                "dataModelSchema": {},
                "assetCandidates": [],
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
            ["root", "action"],
        )
        self.assertNotIn("children", components[1])
        self.assertNotIn("label", components[1])

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

    def test_rejects_non_image_button_child(self) -> None:
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
                    {"label": "Open", "design": "capsule"},
                    ["action_text"],
                ],
                ["action_text", "Text", {"content": "Open"}],
            ]
        )

        with self.assertRaisesRegex(
            CompactDslConversionError,
            "Button child must be an Image",
        ):
            normalize_compact_dsl_design_tokens(compact_dsl)

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
                    {"content": "68%", "design": "display-s"},
                ],
                [
                    "linear",
                    "Progress",
                    {"value": 68, "total": 100, "design": "linear-bar"},
                ],
                [
                    "segmented",
                    "Progress",
                    {"value": 2, "total": 4, "design": "segmented-bar"},
                ],
                [
                    "threshold",
                    "Progress",
                    {
                        "value": 80,
                        "threshold": 60,
                        "total": 100,
                        "design": "threshold-bar",
                    },
                ],
                [
                    "choice",
                    "Checkbox",
                    {
                        "label": "同意",
                        "select": True,
                        "design": "default",
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

    def test_rejects_design_aliases_removed_from_latest_prompt(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": 160, "height": 160},
                    ["progress"],
                ],
                [
                    "progress",
                    "Progress",
                    {"value": 50, "total": 100, "design": "linear"},
                ],
            ]
        )

        with self.assertRaisesRegex(
            CompactDslConversionError,
            'unsupported Progress.design "linear"',
        ):
            normalize_compact_dsl_design_tokens(compact_dsl)

    def test_requires_progress_total_for_valid_a2ui(self) -> None:
        compact_dsl = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": 160, "height": 160},
                    ["progress"],
                ],
                [
                    "progress",
                    "Progress",
                    {"value": 50, "design": "linear-bar"},
                ],
            ]
        )

        with self.assertRaisesRegex(
            CompactDslConversionError,
            "Progress.total is required",
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
            "root Column component is missing; model output may be truncated",
        ):
            convert_compact_dsl_to_a2ui(
                "\n".join(source_rows),
                size="2x2",
                protocol_profile=self.profile,
            )

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

    def test_rejects_unclosed_string_and_mismatched_delimiters(self) -> None:
        invalid_sources = (
            '["root","Column",{"width":160,"height":160},["title]]',
            '["root","Column",{"width":160],"height":160}]',
        )

        for source in invalid_sources:
            with self.subTest(source=source):
                with self.assertRaises(CompactDslConversionError):
                    convert_compact_dsl_to_a2ui(
                        source,
                        size="2x2",
                        protocol_profile=self.profile,
                    )

    def test_rejects_non_json_text_between_rows(self) -> None:
        source_rows = self.compact_dsl.splitlines()
        source_rows.insert(1, "unexpected explanation")

        with self.assertRaisesRegex(
            CompactDslConversionError,
            "non-JSON text between rows",
        ):
            convert_compact_dsl_to_a2ui(
                "\n".join(source_rows),
                size="2x2",
                protocol_profile=self.profile,
            )

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
            ["title", "Text", {"content": "横向卡片", "design": "body-s"}],
        ]

        result = convert_compact_dsl_to_a2ui(
            _serialize(wide_rows),
            size="4x2",
            protocol_profile=self.profile,
        )
        create_surface = json.loads(result.splitlines()[0])["createSurface"]

        self.assertNotIn("width", create_surface)
        self.assertNotIn("height", create_surface)

    def test_rejects_legacy_action_and_row_space(self) -> None:
        legacy_action = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": 160, "height": 160, "itemMargin": 8},
                    ["action"],
                ],
                [
                    "action",
                    "Button",
                    {
                        "label": "查看",
                        "action": {
                            "functionCall": {"call": "clickToApi", "args": {}},
                        },
                    },
                ],
            ]
        )
        row_space = _serialize(
            [
                [
                    "root",
                    "Column",
                    {"width": 160, "height": 160, "space": 8},
                    [],
                ],
            ]
        )

        with self.assertRaisesRegex(
            CompactDslConversionError,
            "legacy property action",
        ):
            convert_compact_dsl_to_a2ui(
                legacy_action,
                size="2x2",
                protocol_profile=self.profile,
            )
        with self.assertRaisesRegex(
            CompactDslConversionError,
            "must use itemMargin",
        ):
            convert_compact_dsl_to_a2ui(
                row_space,
                size="2x2",
                protocol_profile=self.profile,
            )

    def test_rejects_legacy_spacing_tokens(self) -> None:
        invalid = _serialize(
            [
                [
                    "root",
                    "Column",
                    {
                        "width": 160,
                        "height": 160,
                        "padding": "padding_level4",
                    },
                    [],
                ],
            ]
        )

        with self.assertRaisesRegex(
            CompactDslConversionError,
            "legacy token",
        ):
            normalize_compact_dsl_design_tokens(invalid)

    def test_rejects_root_dimensions_that_disagree_with_size(self) -> None:
        with self.assertRaisesRegex(
            CompactDslConversionError,
            "root dimensions must be 320x160",
        ):
            convert_compact_dsl_to_a2ui(
                self.compact_dsl,
                size="2x4",
                protocol_profile=self.profile,
            )

    def test_rejects_binding_without_data_value(self) -> None:
        rows = [
            [
                "root",
                "Column",
                {"width": 160, "height": 160, "itemMargin": 8},
                ["title"],
            ],
            [
                "title",
                "Text",
                {"content": {"path": "/data/missing"}},
            ],
        ]

        with self.assertRaisesRegex(
            CompactDslConversionError,
            "has no matching data value",
        ):
            convert_compact_dsl_to_a2ui(
                _serialize(rows),
                size="2x2",
                protocol_profile=self.profile,
            )

    def test_rejects_unknown_component_property(self) -> None:
        rows = [
            [
                "root",
                "Column",
                {
                    "width": 160,
                    "height": 160,
                    "unsupportedStyle": 1,
                },
                [],
            ],
        ]

        with self.assertRaisesRegex(
            CompactDslConversionError,
            "unsupported properties",
        ):
            convert_compact_dsl_to_a2ui(
                _serialize(rows),
                size="2x2",
                protocol_profile=self.profile,
            )

    def test_validates_task_and_capability_context(self) -> None:
        result = validate_compact_dsl_context(
            self.compact_dsl,
            task_spec=self.task_spec,
            card_spec=self.card_spec,
        )

        self.assertEqual(result.warnings, ())

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
        validate_compact_dsl_context(
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
            CompactDslConversionError,
            "does not match schema type number",
        ):
            validate_compact_dsl_context(
                _serialize(rows),
                task_spec=task_spec,
                card_spec=card_spec,
            )

    def test_rejects_event_and_asset_outside_candidates(self) -> None:
        rows = [
            [
                "root",
                "Column",
                {"width": 160, "height": 160},
                ["icon", "action"],
            ],
            [
                "icon",
                "Image",
                {"src": "resources/base/media/unknown.svg"},
            ],
            [
                "action",
                "Button",
                {
                    "label": "Open",
                    "onClick": [{"call": "unknownCall", "args": {}}],
                },
            ],
        ]
        task_spec = {
            "dataModelSchema": {},
            "assetCandidates": [
                {
                    "id": "asset.known",
                    "src": "resources/base/media/known.svg",
                },
            ],
            "eventCandidates": [
                {
                    "id": "event.known",
                    "call": "knownCall",
                    "args": {},
                },
            ],
        }

        with self.assertRaisesRegex(
            CompactDslConversionError,
            "Image.src",
        ):
            validate_compact_dsl_context(
                _serialize(rows),
                task_spec=task_spec,
                card_spec={"dataBindings": []},
            )

        task_spec["assetCandidates"][0]["src"] = (
            "resources/base/media/unknown.svg"
        )
        with self.assertRaisesRegex(
            CompactDslConversionError,
            "onClick is not present",
        ):
            validate_compact_dsl_context(
                _serialize(rows),
                task_spec=task_spec,
                card_spec={"dataBindings": []},
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

        result = validate_compact_dsl_context(
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

    def test_cli_converts_files_without_model_or_network(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "card.dsl"
            target = root / "card.a2ui"
            source.write_text(self.compact_dsl, encoding="utf-8")

            result = main([str(source), "-o", str(target), "--size", "2x2"])

            self.assertEqual(result, 0)
            messages = [
                json.loads(line)
                for line in target.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(len(messages), 3)
            self.assertIn("updateComponents", messages[1])


if __name__ == "__main__":
    unittest.main()
