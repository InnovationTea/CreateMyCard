from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
SKILL_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from validators import ValidationOptions, validate_card


def jsonl(messages: list[dict]) -> str:
    return "\n".join(
        json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        for message in messages
    )


VALID_MESSAGES = [
    {
        "version": "v0.9",
        "createSurface": {
            "surfaceId": "card",
            "catalogId": "ohos.a2ui.extended.catalog.form",
            "width": "matchParent",
            "height": "matchParent",
        },
    },
    {
        "version": "v0.9",
        "updateComponents": {
            "surfaceId": "card",
            "root": "root",
            "components": [
                {
                    "id": "root",
                    "component": "Column",
                    "children": ["title"],
                    "styles": {
                        "width": "matchParent",
                        "height": "matchParent",
                        "padding": 12,
                        "borderRadius": 18,
                        "clip": True,
                        "backgroundColor": "#FFFFFFFF",
                        "justifyContent": "center",
                        "alignItems": "center",
                    },
                },
                {
                    "id": "title",
                    "component": "Text",
                    "content": "今日天气",
                    "styles": {
                        "width": 136,
                        "height": 20,
                        "fontSize": 16,
                        "fontWeight": 700,
                        "fontColor": "#E5000000",
                        "maxLines": 1,
                        "textAlign": "center",
                    },
                },
            ],
        },
    },
    {
        "version": "v0.9",
        "updateDataModel": {
            "surfaceId": "card",
            "path": "/",
            "value": {"state": {"loading": False}},
        },
    },
]

VALID_CARDSPEC = {
    "title": "天气卡片",
    "description": "今日天气",
    "suggestSize": "2x2",
}


class ValidationTests(unittest.TestCase):
    def validate(
        self,
        messages: list[dict],
        *,
        cardspec: dict | None = None,
        stage: str = "all",
        aesthetic: bool = True,
    ):
        return validate_card(
            dsl_text=jsonl(messages),
            cardspec=cardspec or VALID_CARDSPEC,
            options=ValidationOptions(
                skill_dir=SKILL_DIR,
                stage=stage,
                enable_aesthetic=aesthetic,
            ),
        )

    def test_valid_card_runs_aesthetic_by_default(self) -> None:
        report = self.validate(copy.deepcopy(VALID_MESSAGES))
        self.assertEqual(report.error_count, 0, report.render_text())
        self.assertIsNotNone(report.quality_score)

    def test_invalid_json_is_blocking(self) -> None:
        report = validate_card(
            dsl_text='{"version":',
            options=ValidationOptions(skill_dir=SKILL_DIR),
        )
        self.assertTrue(report.has_code("DSL_JSON_PARSE_FAILED"))

    def test_old_catalog_is_rejected(self) -> None:
        messages = copy.deepcopy(VALID_MESSAGES)
        messages[0]["createSurface"]["catalogId"] = "ohos.a2ui.extended.catalog"
        report = self.validate(messages, stage="hard", aesthetic=False)
        self.assertGreater(report.error_count, 0)
        self.assertTrue(any("CATALOG" in item.code for item in report.diagnostics))

    def test_missing_child_reference_is_rejected(self) -> None:
        messages = copy.deepcopy(VALID_MESSAGES)
        messages[1]["updateComponents"]["components"][0]["children"] = ["missing"]
        report = self.validate(messages, stage="hard", aesthetic=False)
        self.assertGreater(report.error_count, 0)
        self.assertTrue(any("CHILD" in item.code for item in report.diagnostics))

    def test_low_contrast_is_reported(self) -> None:
        messages = copy.deepcopy(VALID_MESSAGES)
        messages[1]["updateComponents"]["components"][1]["styles"]["fontColor"] = "#FFFFFFFF"
        report = self.validate(messages)
        self.assertTrue(report.has_code("AESTHETIC_COLOR_CONTRAST_LOW"), report.render_text())

    def test_declared_svg_asset_is_allowed(self) -> None:
        messages = copy.deepcopy(VALID_MESSAGES)
        root = messages[1]["updateComponents"]["components"][0]
        root["children"].append("icon")
        messages[1]["updateComponents"]["components"].append(
            {
                "id": "icon",
                "component": "Image",
                "src": "resources/base/media/icon_weather1.svg",
                "styles": {"width": 24, "height": 24, "objectFit": "contain"},
            }
        )
        report = self.validate(messages, stage="hard", aesthetic=False)
        self.assertFalse(report.has_code("ASSET_PATH_NOT_DECLARED"), report.render_text())

    def test_model_output_keeps_diagnostic_code(self) -> None:
        messages = copy.deepcopy(VALID_MESSAGES)
        messages[0]["createSurface"]["catalogId"] = "ohos.a2ui.extended.catalog"
        report = self.validate(messages, stage="hard", aesthetic=False)
        rendered = report.render_model()
        self.assertIn("CATALOG", rendered)

    def test_current_call_phone_event_is_allowed(self) -> None:
        messages = copy.deepcopy(VALID_MESSAGES)
        root = messages[1]["updateComponents"]["components"][0]
        root["children"].append("action")
        messages[1]["updateComponents"]["components"].append(
            {
                "id": "action",
                "component": "Button",
                "label": "拨打",
                "onClick": [
                    {
                        "call": "clickToApi",
                        "args": {
                            "intentName": "CallPhone",
                            "params": {"relationship": "母亲", "phoneNumber": ""},
                        },
                    }
                ],
                "styles": {"width": 72, "height": 32},
            }
        )
        report = self.validate(messages, stage="semantic", aesthetic=False)
        self.assertFalse(report.has_code("EVENT_CAPABILITY_UNKNOWN"), report.render_text())
        self.assertFalse(report.has_code("EVENT_ARGUMENT_INVALID"), report.render_text())

    def test_deeplink_requires_declared_intent(self) -> None:
        messages = copy.deepcopy(VALID_MESSAGES)
        root = messages[1]["updateComponents"]["components"][0]
        root["children"].append("action")
        messages[1]["updateComponents"]["components"].append(
            {
                "id": "action",
                "component": "Button",
                "label": "天气",
                "onClick": [
                    {
                        "call": "clickToDeeplink",
                        "args": {
                            "bundleName": "",
                            "abilityName": "",
                            "uri": "hww://www.huawei.com/totemweather?enterType=share&cityCode=",
                        },
                    }
                ],
                "styles": {"width": 72, "height": 32},
            }
        )
        report = self.validate(messages, stage="semantic", aesthetic=False)
        self.assertTrue(report.has_code("EVENT_ARGUMENT_INVALID"), report.render_text())

    def test_unknown_static_data_capability_requests_context(self) -> None:
        messages = copy.deepcopy(VALID_MESSAGES)
        messages[2]["updateDataModel"]["value"]["data"] = {"phoneBattery": {}}
        cardspec = {
            "title": "手机电量",
            "description": "电量状态",
            "suggestSize": "2x2",
            "dataBindings": [
                {
                    "capabilityId": "GetPhoneBatteryInfo",
                    "arguments": {},
                    "writeResultTo": "/data/phoneBattery",
                }
            ],
        }
        report = self.validate(
            messages,
            cardspec=cardspec,
            stage="semantic",
            aesthetic=False,
        )
        self.assertEqual(report.error_count, 0, report.render_text())
        self.assertTrue(report.has_code("CARD_CAPABILITY_UNKNOWN"))


if __name__ == "__main__":
    unittest.main()
