#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from design_system import DesignSystem, read_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble Harmony Form genui and CardSpec from design-plan-v1.")
    parser.add_argument("design_plan", help="Path to a design-plan-v1 JSON file.")
    parser.add_argument("--plan-id", help="Select surfaceId from a reference-plans-v1 document.")
    parser.add_argument("--genui-out", help="Write three-line genui JSONL to this path.")
    parser.add_argument("--cardspec-out", help="Write CardSpec JSON to this path.")
    parser.add_argument("--format", choices=["combined", "json"], default="combined")
    args = parser.parse_args()

    skill_dir = SCRIPT_DIR.parent
    system = DesignSystem(skill_dir)
    plan = read_json(Path(args.design_plan))
    if isinstance(plan.get("plans"), list):
        if not args.plan_id:
            parser.error("--plan-id is required when design_plan contains a plans array")
        plan = next((item for item in plan["plans"] if isinstance(item, dict) and item.get("surfaceId") == args.plan_id), {})
        if not plan:
            parser.error(f"unknown plan id: {args.plan_id}")
    issues = system.validate_catalog() + system.validate_plan(plan)
    if issues:
        for item in issues:
            print(f"{item.severity.upper()} {item.code} {item.location}: {item.message}", file=sys.stderr)
        return 1

    dsl, cardspec = system.assemble(plan)
    if args.genui_out:
        Path(args.genui_out).write_text(dsl + "\n", encoding="utf-8")
    if args.cardspec_out:
        Path(args.cardspec_out).write_text(json.dumps(cardspec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.format == "json":
        print(json.dumps({"genui": dsl, "cardspec": cardspec}, ensure_ascii=False, indent=2))
    else:
        print("```genui")
        print(dsl)
        print("```")
        print()
        print("```cardspec")
        print(json.dumps(cardspec, ensure_ascii=False, separators=(",", ":")))
        print("```")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
