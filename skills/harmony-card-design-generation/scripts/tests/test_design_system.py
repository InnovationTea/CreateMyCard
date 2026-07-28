from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = SKILL_DIR.parents[1]
SCRIPTS_DIR = SKILL_DIR / "scripts"
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from design_system import ASSET_TABLE_PATTERN, CATALOG_ID, DesignSystem
from validators import ValidationOptions, validate_card


class DesignSystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.system = DesignSystem(SKILL_DIR)
        cls.plans = json.loads((FIXTURE_DIR / "reference-plans.json").read_text(encoding="utf-8"))["plans"]
        cls.golden = json.loads((FIXTURE_DIR / "golden-cards.json").read_text(encoding="utf-8"))["cards"]

    def test_catalog_is_valid_and_has_expected_layers(self) -> None:
        self.assertEqual(self.system.validate_catalog(), [])
        self.assertEqual(len(self.system.layouts), 12)
        self.assertGreaterEqual(len(self.system.modules), 12)
        self.assertGreaterEqual(len(self.system.elements), 20)
        self.assertEqual(self.system.index["catalogId"], CATALOG_ID)

    def test_thirteen_reference_plans_are_valid_and_golden(self) -> None:
        self.assertEqual(len(self.plans), 13)
        for plan in self.plans:
            with self.subTest(plan=plan["surfaceId"]):
                self.assertEqual(self.system.validate_plan(plan), [])
                dsl, cardspec = self.system.assemble(plan)
                self.assertEqual(self.golden[plan["surfaceId"]], {"genui": dsl, "cardspec": cardspec})
                self.assertEqual(json.loads(dsl.splitlines()[0])["createSurface"]["catalogId"], CATALOG_ID)

    def test_plan_rejects_incompatible_footprint(self) -> None:
        plan = copy.deepcopy(self.plans[0])
        plan["regions"][1]["moduleId"] = "primary-summary"
        plan["regions"][1]["variantId"] = "compact-136x50"
        codes = {item.code for item in self.system.validate_plan(plan)}
        self.assertIn("DESIGN_PLAN_FOOTPRINT_MISMATCH", codes)

    def test_plan_rejects_undeclared_element_token(self) -> None:
        plan = copy.deepcopy(self.plans[0])
        plan["regions"][1]["elements"]["meter"] = "icon-48"
        codes = {item.code for item in self.system.validate_plan(plan)}
        self.assertIn("DESIGN_PLAN_ELEMENT_TOKEN_INVALID", codes)

    def test_plan_rejects_missing_must_keep_mapping(self) -> None:
        plan = copy.deepcopy(self.plans[0])
        del plan["regions"][1]["content"]["caption"]
        codes = {item.code for item in self.system.validate_plan(plan)}
        self.assertIn("DESIGN_PLAN_REQUIRED_SLOT_MISSING", codes)
        self.assertIn("DESIGN_PLAN_MUST_KEEP_MAPPING_INVALID", codes)

    def test_plan_rejects_unrecorded_should_keep_deletion(self) -> None:
        plan = copy.deepcopy(self.plans[3])
        del plan["regions"][2]["content"]["meta"]
        plan["regions"][2]["elements"].pop("meta")
        codes = {item.code for item in self.system.validate_plan(plan)}
        self.assertIn("DESIGN_PLAN_DEGRADATION_UNRECORDED", codes)

    def test_plan_rejects_arbitrary_size(self) -> None:
        plan = copy.deepcopy(self.plans[0])
        plan["featureProfile"]["size"] = "4x4"
        codes = {item.code for item in self.system.validate_plan(plan)}
        self.assertIn("DESIGN_PLAN_SIZE_INVALID", codes)

    def test_plan_rejects_text_overflow(self) -> None:
        plan = copy.deepcopy(self.plans[0])
        plan["regions"][0]["content"]["object"]["value"] = "这是一个超过预算的服务对象标题"
        codes = {item.code for item in self.system.validate_plan(plan)}
        self.assertIn("DESIGN_PLAN_TEXT_OVERFLOW", codes)

    def test_plan_rejects_too_many_capabilities(self) -> None:
        plan = copy.deepcopy(self.plans[0])
        plan["featureProfile"]["dataNeeds"] = ["天气", "日历"]
        plan["cardSpec"]["dataBindings"] = [
            {"capabilityId": "ViewWeather", "arguments": {}, "writeResultTo": "/data/weather"},
            {"capabilityId": "GetCalendarEvents", "arguments": {}, "writeResultTo": "/data/calendar"},
        ]
        codes = {item.code for item in self.system.validate_plan(plan)}
        self.assertIn("DESIGN_PLAN_CAPABILITY_LIMIT_EXCEEDED", codes)

    def test_plan_rejects_missing_action_event(self) -> None:
        plan = copy.deepcopy(self.plans[0])
        plan["regions"][2].pop("events")
        codes = {item.code for item in self.system.validate_plan(plan)}
        self.assertIn("DESIGN_PLAN_ACTION_EVENT_MISSING", codes)

    def test_plan_rejects_undeclared_asset(self) -> None:
        plan = copy.deepcopy(next(item for item in self.plans if item["surfaceId"] == "ref-product-stat-tiles"))
        plan["regions"][0]["content"]["image"]["value"] = "resources/base/media/not-declared.png"
        codes = {item.code for item in self.system.validate_plan(plan)}
        self.assertIn("DESIGN_PLAN_ASSET_NOT_DECLARED", codes)

    def test_offline_asset_paths_are_synchronized_verbatim(self) -> None:
        offline_asset_doc = SKILL_DIR.parent / "harmony-card-generation-offline" / "reference" / "design" / "asset-library.md"
        offline_paths = set(ASSET_TABLE_PATTERN.findall(offline_asset_doc.read_text(encoding="utf-8")))
        self.assertEqual(self.system.asset_allowlist, offline_paths)
        actual_paths = {
            path.relative_to(REPO_ROOT).as_posix()
            for path in (REPO_ROOT / "resources" / "base" / "media").iterdir()
            if path.is_file()
        }
        self.assertEqual(offline_paths, actual_paths)
        for skill_name in ("harmony-card-generation-offline", "harmony-card-generation-online"):
            config_path = SKILL_DIR.parent / skill_name / "scripts" / "rules" / "config" / "asset.json"
            allowlist = set(json.loads(config_path.read_text(encoding="utf-8"))["allowlist"])
            self.assertEqual(allowlist, actual_paths)

    def test_declared_svg_asset_is_assembled_without_path_rewrite(self) -> None:
        plan = copy.deepcopy(next(item for item in self.plans if item["surfaceId"] == "ref-product-stat-tiles"))
        src = "resources/base/media/earphone_case_16644.svg"
        plan["regions"][0]["content"]["image"]["value"] = src
        self.assertEqual(self.system.validate_plan(plan), [])

        dsl, _ = self.system.assemble(plan)
        components = json.loads(dsl.splitlines()[1])["updateComponents"]["components"]
        image = next(item for item in components if item.get("component") == "Image")
        self.assertEqual(image["src"], src)

        reporter = validate_card(
            dsl_text=dsl,
            cardspec=plan["cardSpec"],
            options=ValidationOptions(skill_dir=SKILL_DIR, design_plan=plan),
        )
        self.assertFalse(reporter.has_code("ASSET_PATH_NOT_DECLARED"))

    def test_card_validator_rejects_manual_component_edit(self) -> None:
        plan = self.plans[0]
        dsl, cardspec = self.system.assemble(plan)
        messages = [json.loads(line) for line in dsl.splitlines()]
        messages[1]["updateComponents"]["components"].append({"id": "manual", "component": "Text", "content": "manual"})
        edited = "\n".join(json.dumps(item, ensure_ascii=False) for item in messages)
        reporter = validate_card(
            dsl_text=edited,
            cardspec=cardspec,
            options=ValidationOptions(skill_dir=SKILL_DIR, design_plan=plan),
        )
        self.assertTrue(reporter.has_code("DESIGN_PLAN_COMPONENT_SET_MISMATCH"))

    def test_card_validator_rejects_non_form_catalog(self) -> None:
        plan = self.plans[0]
        dsl, cardspec = self.system.assemble(plan)
        messages = [json.loads(line) for line in dsl.splitlines()]
        messages[0]["createSurface"]["catalogId"] = "ohos.a2ui.extended.catalog"
        edited = "\n".join(json.dumps(item, ensure_ascii=False) for item in messages)
        reporter = validate_card(dsl_text=edited, cardspec=cardspec, options=ValidationOptions(skill_dir=SKILL_DIR))
        self.assertTrue(reporter.has_code("DSL_CATALOG_ID_INVALID"))

    def test_routing_cases_assert_layered_choices(self) -> None:
        cases = json.loads((Path(__file__).with_name("routing_cases.json")).read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(cases), 13)
        query_corpus = " ".join(case["query"] for case in cases)
        for scene in ("天气", "日程", "低电量", "睡眠", "应用使用时长", "耳机", "内存", "倒计时"):
            self.assertIn(scene, query_corpus)
        for case in cases:
            with self.subTest(query=case["query"]):
                layout = self.system.layouts[case["layoutId"]]
                self.assertEqual(layout["size"], case["size"])
                self.assertIn(case["style"], self.system.styles)
                for module_id in case["modules"].values():
                    self.assertIn(module_id, self.system.modules)
                for token_id in case["elements"]:
                    self.assertIn(token_id, self.system.elements)

    def test_query_script_returns_only_compatible_modules(self) -> None:
        layout = self.system.layouts["header-main-footer"]
        main = next(item for item in layout["regions"] if item["id"] == "main")
        matches = []
        for module in self.system.modules.values():
            for variant in module["variants"]:
                if module["role"] in main["allowedModuleRoles"] and variant["footprint"] == {"width": main["width"], "height": main["height"]}:
                    matches.append((module["id"], variant["id"]))
        self.assertEqual(set(matches), {("meter-summary", "compact-136x58"), ("schedule-summary", "compact-136x58")})

    def test_routing_edge_cases_cover_layered_failures(self) -> None:
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
                "footprint-mismatch",
                "arbitrary-size",
            },
        )


if __name__ == "__main__":
    unittest.main()
