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
                    "padding": "padding_level6",
                    "borderRadius": "corner_radius_level9",
                    "backgroundColor": "comp_background_list_card",
                    "space": "padding_level4",
                },
                ["title", "progress", "action"],
            ],
            [
                "title",
                "Text",
                {
                    "content": {"path": "/data/title"},
                    "design": "title-s",
                    "fontColor": "font_primary",
                },
            ],
            ["/data/title", "清理无忧"],
            [
                "progress",
                "Progress",
                {
                    "value": {"path": "/data/storage/usedPercent"},
                    "total": 100,
                    "design": "linear",
                },
            ],
            ["/data/storage/usedPercent", 72],
            [
                "action",
                "Button",
                {
                    "width": 116,
                    "label": "立即清理",
                    "design": "primary-sm",
                    "action": {
                        "functionCall": {
                            "call": "clickToIntent",
                            "args": {
                                "intentName": "StorageClean",
                                "params": {
                                    "entityId": {
                                        "path": "/data/storage/entityId",
                                    },
                                },
                            },
                        },
                    },
                },
            ],
            ["/data/storage/entityId", "storage-1"],
            ["/data/items/0/name", "缓存"],
        ]
        self.compact_dsl = "\n".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":"))
            for row in rows
        )

    def test_expands_design_tokens(self) -> None:
        normalized = normalize_compact_dsl_design_tokens(self.compact_dsl)
        rows = [json.loads(line) for line in normalized.splitlines()]
        components = {}
        for row in rows:
            if len(row) >= 3:
                components[row[0]] = row

        self.assertEqual(components["root"][2]["padding"], 12)
        self.assertEqual(components["root"][2]["borderRadius"], 18)
        self.assertEqual(components["root"][2]["backgroundColor"], "#FFFFFFFF")
        self.assertEqual(components["title"][2]["fontSize"], 20)
        self.assertEqual(components["title"][2]["fontWeight"], 700)
        self.assertNotIn("design", components["title"][2])
        self.assertEqual(components["action"][2]["height"], 28)
        self.assertEqual(
            components["action"][2]["backgroundColor"],
            "#FF0A59F7",
        )

    def test_converts_components_actions_bindings_and_data(self) -> None:
        a2ui = convert_compact_dsl_to_a2ui(
            self.compact_dsl,
            size="2x2",
            protocol_profile=self.profile,
        )
        messages = [json.loads(line) for line in a2ui.splitlines()]
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0]["createSurface"]["width"], 140)

        components = {}
        for component in messages[1]["updateComponents"]["components"]:
            components[component["id"]] = component

        root = components["root"]
        self.assertEqual(root["itemMargin"], 8)
        self.assertEqual(root["styles"]["width"], "matchParent")
        self.assertEqual(root["styles"]["height"], "matchParent")
        self.assertEqual(components["title"]["content"], "{{ ${/data/title} }}")
        self.assertEqual(components["progress"]["value"], "{{ ${/data/storage/usedPercent} }}")
        self.assertEqual(components["action"]["onClick"][0]["call"], "clickToIntent")

        entity_id = components["action"]["onClick"][0]["args"]["params"]["entityId"]
        self.assertEqual(entity_id, "{{ ${/data/storage/entityId} }}")
        data_model = messages[2]["updateDataModel"]["value"]
        self.assertEqual(data_model["data"]["title"], "清理无忧")
        self.assertEqual(data_model["data"]["items"][0]["name"], "缓存")

    def test_supports_dark_theme_and_2x4_size(self) -> None:
        a2ui = convert_compact_dsl_to_a2ui(
            self.compact_dsl,
            size="2x4",
            protocol_profile=self.profile,
            theme="dark",
        )
        messages = [json.loads(line) for line in a2ui.splitlines()]
        self.assertEqual(messages[0]["createSurface"]["width"], 300)

        components = {}
        for component in messages[1]["updateComponents"]["components"]:
            components[component["id"]] = component
        self.assertEqual(
            components["root"]["styles"]["backgroundColor"],
            "#19FFFFFF",
        )
        self.assertEqual(
            components["title"]["styles"]["fontColor"],
            "#E5FFFFFF",
        )

    def test_preserves_native_on_click_handlers(self) -> None:
        compact_dsl = "\n".join(
            (
                '["root","Column",{},["action"]]',
                '["action","Button",{"label":"查看","design":"default-sm",'
                '"onClick":[{"call":"clickToApi","args":{"intentName":"ViewDetail",'
                '"params":{"entityId":{"path":"/data/entityId"}}}}]}]',
                '["/data/entityId","entity-1"]',
            )
        )
        a2ui = convert_compact_dsl_to_a2ui(
            compact_dsl,
            size="2x2",
            protocol_profile=self.profile,
        )
        messages = [json.loads(line) for line in a2ui.splitlines()]
        action = messages[1]["updateComponents"]["components"][1]

        self.assertEqual(action["onClick"][0]["call"], "clickToApi")
        entity_id = action["onClick"][0]["args"]["params"]["entityId"]
        self.assertEqual(entity_id, "{{ ${/data/entityId} }}")
        self.assertNotIn("onClick", action["styles"])

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

    def test_rejects_unknown_design(self) -> None:
        invalid = "\n".join(
            (
                '["root","Column",{},["title"]]',
                '["title","Text",{"content":"标题","design":"unknown"}]',
            )
        )
        with self.assertRaisesRegex(
            CompactDslConversionError,
            'unsupported Text.design "unknown"',
        ):
            normalize_compact_dsl_design_tokens(invalid)


if __name__ == "__main__":
    unittest.main()
