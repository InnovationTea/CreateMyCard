#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from design_system import DesignSystem


def emit(value) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="Query layered Harmony card layouts, modules and element tokens.")
    parser.add_argument("--layouts", action="store_true", help="List layout summaries.")
    parser.add_argument("--size", choices=["2x2", "2x4"], help="Filter layout summaries by size.")
    parser.add_argument("--layout", help="Show one layout definition.")
    parser.add_argument("--compatible-modules", nargs=2, metavar=("LAYOUT_ID", "REGION_ID"), help="List exact-footprint modules for a region.")
    parser.add_argument("--module", help="Show a module or one module variant.")
    parser.add_argument("--variant", help="Variant id used with --module.")
    parser.add_argument("--element", help="Show one element token.")
    args = parser.parse_args()

    system = DesignSystem(SCRIPT_DIR.parent)
    issues = system.validate_catalog()
    if issues:
        for item in issues:
            print(f"{item.code} {item.location}: {item.message}", file=sys.stderr)
        return 1

    if args.layouts:
        emit([
            {"id": item["id"], "size": item["size"], "summary": item["summary"], "regions": [{"id": region["id"], "role": region["role"], "width": region["width"], "height": region["height"]} for region in item["regions"]]}
            for item in system.layouts.values()
            if args.size is None or item["size"] == args.size
        ])
        return 0
    if args.layout:
        value = system.layouts.get(args.layout)
        if value is None:
            parser.error(f"unknown layout: {args.layout}")
        emit(value)
        return 0
    if args.compatible_modules:
        layout_id, region_id = args.compatible_modules
        layout = system.layouts.get(layout_id)
        if layout is None:
            parser.error(f"unknown layout: {layout_id}")
        region = next((item for item in layout["regions"] if item["id"] == region_id), None)
        if region is None:
            parser.error(f"unknown region: {layout_id}/{region_id}")
        matches = []
        for module in system.modules.values():
            if module["role"] not in region["allowedModuleRoles"]:
                continue
            for variant in module["variants"]:
                if variant["footprint"] == {"width": region["width"], "height": region["height"]}:
                    matches.append({"moduleId": module["id"], "role": module["role"], "summary": module["summary"], "variantId": variant["id"], "footprint": variant["footprint"], "requiredSlots": [slot_id for slot_id, slot in variant["slots"].items() if slot.get("required")]})
        emit(matches)
        return 0
    if args.module:
        module = system.modules.get(args.module)
        if module is None:
            parser.error(f"unknown module: {args.module}")
        if args.variant:
            value = next((item for item in module["variants"] if item["id"] == args.variant), None)
            if value is None:
                parser.error(f"unknown variant: {args.module}/{args.variant}")
            emit({"moduleId": module["id"], "role": module["role"], "summary": module["summary"], "variant": value})
        else:
            emit(module)
        return 0
    if args.element:
        value = system.elements.get(args.element)
        if value is None:
            parser.error(f"unknown element: {args.element}")
        emit(value)
        return 0
    parser.error("choose --layouts, --layout, --compatible-modules, --module, or --element")


if __name__ == "__main__":
    raise SystemExit(main())
