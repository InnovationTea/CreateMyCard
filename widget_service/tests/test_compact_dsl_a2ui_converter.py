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
        self.assertEqual(components["action"][2]["borderRadius"], 18)
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

        self.assertEqual(action[2]["width"], 36)
        self.assertEqual(action[2]["height"], 36)
        self.assertEqual(action[2]["borderRadius"], 18)
        self.assertNotIn("design", action[2])

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
        self.assertEqual(messages[0]["createSurface"]["width"], 140)
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

    def test_uses_2x4_profile_dimensions_for_4x2(self) -> None:
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

        self.assertEqual(create_surface["width"], 300)
        self.assertEqual(create_surface["height"], 140)

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
