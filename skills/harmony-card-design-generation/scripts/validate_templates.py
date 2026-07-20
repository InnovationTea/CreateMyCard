#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
FIXTURE_DIR = SCRIPT_DIR / "tests" / "fixtures"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from design_system import DesignIssue, DesignSystem
from validators import ValidationOptions, validate_card


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def validate_reference_fixtures(system: DesignSystem) -> list[DesignIssue]:
    issues: list[DesignIssue] = []
    try:
        plans_doc = load_json(FIXTURE_DIR / "reference-plans.json")
        golden_doc = load_json(FIXTURE_DIR / "golden-cards.json")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [DesignIssue("error", "REFERENCE_FIXTURE_INVALID", "fixtures", str(exc))]
    plans = plans_doc.get("plans", [])
    cards = golden_doc.get("cards", {})
    if plans_doc.get("schemaVersion") != "reference-plans-v1" or golden_doc.get("schemaVersion") != "reference-golden-v1":
        issues.append(DesignIssue("error", "REFERENCE_FIXTURE_VERSION_INVALID", "fixtures", "参考 fixture 版本无效。"))
    if not isinstance(plans, list) or len(plans) != 13:
        issues.append(DesignIssue("error", "REFERENCE_FIXTURE_COUNT_INVALID", "fixtures/reference-plans", f"必须包含 13 个 Design Plan，当前为 {len(plans) if isinstance(plans, list) else 0}。"))
        return issues
    surface_ids = [plan.get("surfaceId") for plan in plans if isinstance(plan, dict)]
    if len(surface_ids) != len(set(surface_ids)):
        issues.append(DesignIssue("error", "REFERENCE_FIXTURE_ID_DUPLICATE", "fixtures/reference-plans", "surfaceId 必须唯一。"))
    for plan in plans:
        if not isinstance(plan, dict):
            issues.append(DesignIssue("error", "REFERENCE_FIXTURE_INVALID", "fixtures/reference-plans", "Design Plan 必须是 object。"))
            continue
        plan_id = str(plan.get("surfaceId"))
        for issue in system.validate_plan(plan):
            issues.append(DesignIssue(issue.severity, issue.code, f"fixtures/{plan_id}/{issue.location}", issue.message))
        if any(item.location.startswith(f"fixtures/{plan_id}/") for item in issues):
            continue
        dsl, cardspec = system.assemble(plan)
        golden = cards.get(plan_id) if isinstance(cards, dict) else None
        if not isinstance(golden, dict) or golden.get("genui") != dsl or golden.get("cardspec") != cardspec:
            issues.append(DesignIssue("error", "REFERENCE_GOLDEN_MISMATCH", f"fixtures/{plan_id}", "黄金产物与当前确定性装配结果不一致。"))
            continue
        reporter = validate_card(
            dsl_text=dsl,
            cardspec=cardspec,
            options=ValidationOptions(skill_dir=SKILL_DIR, design_plan=plan),
        )
        for diagnostic in reporter.diagnostics:
            issues.append(
                DesignIssue(
                    diagnostic.severity,
                    diagnostic.code,
                    f"fixtures/{plan_id}/{diagnostic.file_kind}",
                    diagnostic.message,
                )
            )
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the layered Harmony card design system.")
    parser.add_argument("--all", action="store_true", help="Validate catalogs and all reference fixtures.")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()
    if not args.all:
        parser.error("pass --all")

    system = DesignSystem(SKILL_DIR)
    issues = system.validate_catalog() + validate_reference_fixtures(system)
    errors = sum(item.severity == "error" for item in issues)
    warnings = sum(item.severity == "warning" for item in issues)
    valid = errors == 0 and (not args.strict or warnings == 0)
    if args.format == "json":
        print(json.dumps({"valid": valid, "errorCount": errors, "warningCount": warnings, "issues": [item.as_dict() for item in issues]}, ensure_ascii=False, indent=2))
    else:
        for item in issues:
            print(f"{item.severity.upper()} {item.code} {item.location}: {item.message}")
        print(f"{'OK' if valid else 'FAIL'} design-system layouts={len(system.layouts)} modules={len(system.modules)} elements={len(system.elements)} fixtures=13 errors={errors} warnings={warnings}")
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
