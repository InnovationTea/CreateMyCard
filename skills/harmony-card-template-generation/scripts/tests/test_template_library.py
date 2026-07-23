from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = SKILL_DIR.parents[1]
SCRIPTS_DIR = SKILL_DIR / "scripts"
TEMPLATES_DIR = SKILL_DIR / "assets" / "templates"
ASSET_LIBRARY = SKILL_DIR / "references" / "design" / "asset-library.md"
RESOURCE_PATTERN = re.compile(r"resources/base/media/[A-Za-z0-9_.-]+")
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from validate_templates import STYLE_PROFILES, validate_manifest_schema, validate_manifest_shape
from validators import ValidationOptions, validate_card


EXPECTED_TEMPLATE_IDS = {
    "meter-side-action",
    "multi-meter-action",
    "bar-dual-metric-action",
    "countdown-panel",
    "meeting-action-badge",
    "product-stat-tiles",
    "quadrant-ambient-action",
    "spotlight-context-action",
    "stacked-schedule-action",
    "content-action-sidebar",
    "dual-action-panel",
    "hero-context-action",
    "metric-dashboard-action",
}


class TemplateLibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.index = json.loads((TEMPLATES_DIR / "index.json").read_text(encoding="utf-8"))
        cls.asset_paths = set(RESOURCE_PATTERN.findall(ASSET_LIBRARY.read_text(encoding="utf-8")))

    def test_asset_library_matches_repository_media(self) -> None:
        actual_paths = {
            path.relative_to(REPO_ROOT).as_posix()
            for path in (REPO_ROOT / "resources" / "base" / "media").iterdir()
            if path.is_file()
        }
        self.assertEqual(self.asset_paths, actual_paths)

    def test_index_has_thirteen_unique_templates(self) -> None:
        entries = self.index["templates"]
        self.assertEqual(len(entries), 13)
        self.assertEqual({entry["id"] for entry in entries}, EXPECTED_TEMPLATE_IDS)
        self.assertEqual(
            set(self.index["safeFallbacks"].values()),
            {"spotlight-context-action", "hero-context-action"},
        )

    def test_every_manifest_matches_contract(self) -> None:
        for entry in self.index["templates"]:
            with self.subTest(template=entry["id"]):
                manifest = json.loads((TEMPLATES_DIR / entry["manifest"]).read_text(encoding="utf-8"))
                self.assertEqual(validate_manifest_schema(manifest, entry["id"]), [])
                self.assertEqual(validate_manifest_shape(manifest, entry["id"]), [])
                self.assertIn(manifest["defaultStyleProfile"], STYLE_PROFILES)

    def test_every_skeleton_uses_current_catalog(self) -> None:
        for entry in self.index["templates"]:
            with self.subTest(template=entry["id"]):
                source = (TEMPLATES_DIR / entry["template"]).read_text(encoding="utf-8")
                lines = source.splitlines()
                self.assertEqual(len(lines), 3)
                create = json.loads(lines[0])["createSurface"]
                self.assertEqual(create["catalogId"], "ohos.a2ui.extended.catalog")
                self.assertEqual(create["width"], "matchParent")
                self.assertEqual(create["height"], "matchParent")
                self.assertNotIn('"theme"', source)
                self.assertNotIn("data:image", source)
                self.assertNotIn("http://", source)
                self.assertNotIn("https://", source)
                for asset_path in RESOURCE_PATTERN.findall(source):
                    self.assertIn(asset_path, self.asset_paths)
                    self.assertTrue((REPO_ROOT / asset_path).is_file())
                self.assertFalse(any(0x1F300 <= ord(char) <= 0x1FAFF for char in source))

    def test_routing_cases_reference_valid_templates_and_styles(self) -> None:
        cases = json.loads((Path(__file__).with_name("routing_cases.json")).read_text(encoding="utf-8"))
        by_id = {entry["id"]: entry for entry in self.index["templates"]}
        self.assertGreaterEqual(len(cases), 13)
        self.assertEqual({case["templateId"] for case in cases}, EXPECTED_TEMPLATE_IDS)
        query_corpus = " ".join(case["query"] for case in cases)
        for required_scene in ("天气", "日程", "低电量", "睡眠", "应用使用时长", "耳机", "内存", "倒计时"):
            self.assertIn(required_scene, query_corpus)
        for case in cases:
            with self.subTest(query=case["query"]):
                entry = by_id[case["templateId"]]
                manifest = json.loads((TEMPLATES_DIR / entry["manifest"]).read_text(encoding="utf-8"))
                self.assertEqual(entry["size"], case["size"])
                self.assertIn(case["style"], manifest["allowedStyleProfiles"])

    def test_routing_edge_cases_cover_degradation_contract(self) -> None:
        cases = json.loads((Path(__file__).with_name("routing_edge_cases.json")).read_text(encoding="utf-8"))
        self.assertEqual(
            {case["category"] for case in cases},
            {
                "neutral-light",
                "dark-focus",
                "ambient-scene",
                "media-surface",
                "asset-missing",
                "event-missing",
                "text-overflow",
                "capability-missing",
                "information-overload",
            },
        )

    def test_template_validator_rejects_added_component_id(self) -> None:
        template_id = "content-action-sidebar"
        template_dir = TEMPLATES_DIR / template_id
        messages = [json.loads(line) for line in (template_dir / "template.genui.jsonl").read_text(encoding="utf-8").splitlines()]
        messages[1]["updateComponents"]["components"].append(
            {"id": "extra", "component": "Text", "content": "extra"}
        )
        dsl = "\n".join(json.dumps(item, ensure_ascii=False) for item in messages)
        cardspec = json.loads((template_dir / "cardspec.json").read_text(encoding="utf-8"))
        reporter = validate_card(
            dsl_text=dsl,
            cardspec=cardspec,
            options=ValidationOptions(skill_dir=SKILL_DIR, template_id=template_id),
        )
        self.assertTrue(reporter.has_code("TEMPLATE_COMPONENT_ID_ADDED"))

    def test_template_validator_rejects_changed_region_size(self) -> None:
        template_id = "content-action-sidebar"
        template_dir = TEMPLATES_DIR / template_id
        messages = [json.loads(line) for line in (template_dir / "template.genui.jsonl").read_text(encoding="utf-8").splitlines()]
        header = next(item for item in messages[1]["updateComponents"]["components"] if item["id"] == "header")
        header["styles"]["height"] = 22
        dsl = "\n".join(json.dumps(item, ensure_ascii=False) for item in messages)
        cardspec = json.loads((template_dir / "cardspec.json").read_text(encoding="utf-8"))
        reporter = validate_card(
            dsl_text=dsl,
            cardspec=cardspec,
            options=ValidationOptions(skill_dir=SKILL_DIR, template_id=template_id),
        )
        self.assertTrue(reporter.has_code("TEMPLATE_REGION_SIZE_CHANGED"))

    def test_template_validator_enforces_capability_limit(self) -> None:
        template_id = "meter-side-action"
        template_dir = TEMPLATES_DIR / template_id
        cardspec = json.loads((template_dir / "cardspec.json").read_text(encoding="utf-8"))
        cardspec["dataBindings"] = [
            {"capabilityId": "ViewWeather", "arguments": {}, "writeResultTo": "/data/weather"},
            {"capabilityId": "GetCalendarEvents", "arguments": {}, "writeResultTo": "/data/calendar"},
        ]
        reporter = validate_card(
            dsl_text=(template_dir / "template.genui.jsonl").read_text(encoding="utf-8"),
            cardspec=cardspec,
            options=ValidationOptions(skill_dir=SKILL_DIR, template_id=template_id),
        )
        self.assertTrue(reporter.has_code("TEMPLATE_CAPABILITY_LIMIT_EXCEEDED"))

    def test_template_validator_enforces_text_budget(self) -> None:
        template_id = "meter-side-action"
        template_dir = TEMPLATES_DIR / template_id
        messages = [json.loads(line) for line in (template_dir / "template.genui.jsonl").read_text(encoding="utf-8").splitlines()]
        messages[2]["updateDataModel"]["value"]["card"]["title"] = "这是一个超过预算的标题"
        dsl = "\n".join(json.dumps(item, ensure_ascii=False) for item in messages)
        cardspec = json.loads((template_dir / "cardspec.json").read_text(encoding="utf-8"))
        reporter = validate_card(
            dsl_text=dsl,
            cardspec=cardspec,
            options=ValidationOptions(skill_dir=SKILL_DIR, template_id=template_id),
        )
        self.assertTrue(reporter.has_code("TEMPLATE_SLOT_TEXT_OVERFLOW"))

    def test_asset_validator_allows_declared_svg(self) -> None:
        template_id = "meter-side-action"
        template_dir = TEMPLATES_DIR / template_id
        messages = [json.loads(line) for line in (template_dir / "template.genui.jsonl").read_text(encoding="utf-8").splitlines()]
        messages[2]["updateDataModel"]["value"]["asset"]["primaryIcon"] = "resources/base/media/bolt_fill.svg"
        dsl = "\n".join(json.dumps(item, ensure_ascii=False) for item in messages)
        cardspec = json.loads((template_dir / "cardspec.json").read_text(encoding="utf-8"))
        reporter = validate_card(
            dsl_text=dsl,
            cardspec=cardspec,
            options=ValidationOptions(skill_dir=SKILL_DIR, template_id=template_id),
        )
        self.assertFalse(reporter.has_code("ASSET_REMOTE_URL_FORBIDDEN"), reporter.render_text())
        self.assertFalse(reporter.has_code("ASSET_PATH_NOT_DECLARED"), reporter.render_text())

    def test_asset_validator_rejects_undeclared_svg(self) -> None:
        template_id = "meter-side-action"
        template_dir = TEMPLATES_DIR / template_id
        messages = [json.loads(line) for line in (template_dir / "template.genui.jsonl").read_text(encoding="utf-8").splitlines()]
        messages[2]["updateDataModel"]["value"]["asset"]["primaryIcon"] = "resources/base/media/not-declared.svg"
        dsl = "\n".join(json.dumps(item, ensure_ascii=False) for item in messages)
        cardspec = json.loads((template_dir / "cardspec.json").read_text(encoding="utf-8"))
        reporter = validate_card(
            dsl_text=dsl,
            cardspec=cardspec,
            options=ValidationOptions(skill_dir=SKILL_DIR, template_id=template_id),
        )
        self.assertTrue(reporter.has_code("ASSET_PATH_NOT_DECLARED"), reporter.render_text())


if __name__ == "__main__":
    unittest.main()
