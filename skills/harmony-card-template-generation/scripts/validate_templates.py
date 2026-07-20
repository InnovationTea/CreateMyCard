#!/usr/bin/env python3
"""Validate the bundled template index, manifests, skeletons and CardSpec files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator
except ImportError:  # The bundled runtime may omit this optional dependency.
    Draft202012Validator = None

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
TEMPLATES_DIR = SKILL_DIR / "assets" / "templates"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from validators import ValidationOptions, validate_card


REQUIRED_MANIFEST_FIELDS = {
    "schemaVersion",
    "id",
    "size",
    "pattern",
    "summary",
    "template",
    "cardspec",
    "sourceProvenance",
    "useWhen",
    "avoidWhen",
    "layout",
    "componentVariants",
    "slots",
    "defaultStyleProfile",
    "allowedStyleProfiles",
    "colorRoles",
    "allowedEdits",
    "forbiddenEdits",
    "deleteRules",
}
STYLE_PROFILES = {"neutral-light", "dark-focus", "ambient-scene", "media-surface"}
SIZE_RULES = {
    "2x2": {"width": 160, "height": 160, "borderRadius": 18, "bindingLimit": 1},
    "2x4": {"width": 320, "height": 160, "borderRadius": 18, "bindingLimit": 2},
}
WIDE_GEOMETRY = {
    "content-action-sidebar": {
        "header": (296, 24),
        "contentPanel": (200, 104),
        "actionSidebar": (84, 104),
    },
    "dual-action-panel": {
        "contentPanel": (180, 136),
        "operationPanel": (104, 136),
        "topAction": (104, 62),
        "bottomAction": (104, 62),
    },
    "hero-context-action": {
        "heroPanel": (104, 136),
        "contextColumn": (180, 136),
        "contextPanel": (180, 96),
        "primaryAction": (180, 32),
    },
    "metric-dashboard-action": {
        "primaryMetric": (92, 136),
        "metricsPanel": (124, 136),
        "actionPanel": (64, 136),
    },
}
MANIFEST_SCHEMA = json.loads((TEMPLATES_DIR / "manifest.schema.json").read_text(encoding="utf-8"))


def load_json(path: Path, issues: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        issues.append(issue("error", "FILE_MISSING", kind, str(path)))
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        issues.append(issue("error", "JSON_INVALID", kind, str(exc)))
        return {}
    if not isinstance(value, dict):
        issues.append(issue("error", "JSON_OBJECT_REQUIRED", kind, str(path)))
        return {}
    return value


def issue(severity: str, code: str, file_kind: str, message: str) -> dict[str, Any]:
    return {"severity": severity, "code": code, "fileKind": file_kind, "message": message}


def validate_manifest_shape(manifest: dict[str, Any], template_id: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    missing = sorted(REQUIRED_MANIFEST_FIELDS - set(manifest))
    if missing:
        issues.append(issue("error", "MANIFEST_FIELDS_MISSING", "manifest", f"{template_id}: {missing}"))
        return issues
    if manifest.get("schemaVersion") != "template-v1":
        issues.append(issue("error", "MANIFEST_VERSION_INVALID", "manifest", template_id))
    if manifest.get("id") != template_id:
        issues.append(issue("error", "MANIFEST_ID_MISMATCH", "manifest", template_id))

    size = manifest.get("size")
    rule = SIZE_RULES.get(size)
    if rule is None:
        issues.append(issue("error", "MANIFEST_SIZE_INVALID", "manifest", str(size)))
        return issues
    layout = manifest.get("layout") if isinstance(manifest.get("layout"), dict) else {}
    canvas = layout.get("canvas") if isinstance(layout.get("canvas"), dict) else {}
    root = layout.get("root") if isinstance(layout.get("root"), dict) else {}
    safe_area = layout.get("safeArea") if isinstance(layout.get("safeArea"), dict) else {}
    for key in ("width", "height"):
        if canvas.get(key) != rule[key] or root.get(key) != rule[key]:
            issues.append(issue("error", "MANIFEST_CANVAS_INVALID", "manifest", f"{template_id}: {key}"))
    if root.get("padding") != 12 or root.get("borderRadius") != rule["borderRadius"] or root.get("clip") is not True:
        issues.append(issue("error", "MANIFEST_ROOT_INVALID", "manifest", template_id))
    expected_safe_area = {
        "x": 12,
        "y": 12,
        "width": rule["width"] - 24,
        "height": rule["height"] - 24,
    }
    if safe_area != expected_safe_area:
        issues.append(
            issue(
                "error",
                "MANIFEST_SAFE_AREA_INVALID",
                "manifest",
                f"{template_id}: expected {expected_safe_area}, got {safe_area}",
            )
        )

    regions = layout.get("regions") if isinstance(layout.get("regions"), list) else []
    region_ids = [item.get("id") for item in regions if isinstance(item, dict)]
    if len(regions) < 2 or len(region_ids) != len(set(region_ids)):
        issues.append(issue("error", "MANIFEST_REGIONS_INVALID", "manifest", template_id))
    variants = manifest.get("componentVariants") if isinstance(manifest.get("componentVariants"), dict) else {}
    if set(variants) != set(region_ids):
        issues.append(issue("error", "MANIFEST_VARIANTS_INCOMPLETE", "manifest", template_id))
    for region in regions:
        if not isinstance(region, dict):
            continue
        region_id = region.get("id")
        if not isinstance(region.get("width"), (int, float)) or not isinstance(region.get("height"), (int, float)):
            issues.append(issue("error", "MANIFEST_REGION_SIZE_INVALID", "manifest", str(region_id)))
        choices = variants.get(region_id, [])
        if not isinstance(choices, list) or not choices or choices[0].get("id") != "default":
            issues.append(issue("error", "MANIFEST_DEFAULT_VARIANT_MISSING", "manifest", str(region_id)))
            continue
        allowed = set(region.get("allowedComponents", []))
        for choice in choices:
            if not isinstance(choice, dict):
                issues.append(issue("error", "MANIFEST_VARIANT_INVALID", "manifest", str(region_id)))
                continue
            choice_allowed = set(choice.get("allowedComponents", []))
            if choice.get("rootComponent") not in allowed or not choice_allowed.issubset(allowed):
                issues.append(
                    issue(
                        "error",
                        "MANIFEST_VARIANT_COMPONENT_INVALID",
                        "manifest",
                        f"{template_id}/{region_id}/{choice.get('id')}",
                    )
                )

    slots = manifest.get("slots") if isinstance(manifest.get("slots"), dict) else {}
    for name, slot in slots.items():
        if not isinstance(slot, dict) or slot.get("region") not in set(region_ids):
            issues.append(issue("error", "MANIFEST_SLOT_REGION_INVALID", "manifest", str(name)))
        if not isinstance(slot, dict) or not isinstance(slot.get("path"), str) or not slot["path"].startswith("/"):
            issues.append(issue("error", "MANIFEST_SLOT_PATH_INVALID", "manifest", str(name)))

    default_style = manifest.get("defaultStyleProfile")
    allowed_styles = set(manifest.get("allowedStyleProfiles", []))
    if default_style not in allowed_styles or not allowed_styles.issubset(STYLE_PROFILES):
        issues.append(issue("error", "MANIFEST_STYLE_INVALID", "manifest", template_id))

    expected_geometry = WIDE_GEOMETRY.get(manifest.get("pattern"))
    if expected_geometry is not None:
        actual_geometry = {
            region.get("id"): (region.get("width"), region.get("height"))
            for region in regions
            if isinstance(region, dict)
        }
        if actual_geometry != expected_geometry:
            issues.append(
                issue(
                    "error",
                    "MANIFEST_WIDE_GEOMETRY_INVALID",
                    "manifest",
                    f"{template_id}: expected {expected_geometry}, got {actual_geometry}",
                )
            )
    return issues


def validate_manifest_schema(manifest: dict[str, Any], template_id: str) -> list[dict[str, Any]]:
    if Draft202012Validator is None:
        return []
    validator = Draft202012Validator(MANIFEST_SCHEMA)
    issues = []
    for error in sorted(validator.iter_errors(manifest), key=lambda item: list(item.absolute_path)):
        location = "/" + "/".join(str(item) for item in error.absolute_path)
        issues.append(
            issue(
                "error",
                "MANIFEST_SCHEMA_INVALID",
                "manifest",
                f"{template_id}{location}: {error.message}",
            )
        )
    return issues


def load_skeleton_components(path: Path, issues: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(lines) != 3:
            raise ValueError(f"expected 3 JSONL lines, got {len(lines)}")
        message = json.loads(lines[1])
        components = message["updateComponents"]["components"]
        if not isinstance(components, list):
            raise TypeError("components must be an array")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        issues.append(issue("error", "TEMPLATE_SKELETON_INVALID", "genui", str(exc)))
        return {}
    return {
        component["id"]: component
        for component in components
        if isinstance(component, dict) and isinstance(component.get("id"), str)
    }


def validate_skeleton_contract(
    manifest: dict[str, Any],
    components: dict[str, dict[str, Any]],
    template_id: str,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    regions = manifest.get("layout", {}).get("regions", [])
    variants = manifest.get("componentVariants", {})
    slots = manifest.get("slots", {})
    region_ids = {
        region.get("id")
        for region in regions
        if isinstance(region, dict) and isinstance(region.get("id"), str)
    }

    def child_ids(component: dict[str, Any]) -> list[str]:
        children = component.get("children", [])
        return [child for child in children if isinstance(child, str)] if isinstance(children, list) else []

    def subtree_ids(region_id: str) -> set[str]:
        result: set[str] = set()
        pending = [region_id]
        while pending:
            current = pending.pop()
            if current in result or current not in components:
                continue
            result.add(current)
            for child in child_ids(components[current]):
                if child not in region_ids or child == region_id:
                    pending.append(child)
        return result

    region_subtrees = {region_id: subtree_ids(region_id) for region_id in region_ids}
    for region in regions:
        if not isinstance(region, dict) or not isinstance(region.get("id"), str):
            continue
        region_id = region["id"]
        component = components.get(region_id)
        if component is None:
            issues.append(issue("error", "TEMPLATE_REGION_MISSING", "genui", f"{template_id}/{region_id}"))
            continue
        parent_id = region.get("parent")
        parent = components.get(parent_id)
        if parent is None or region_id not in child_ids(parent):
            issues.append(
                issue(
                    "error",
                    "TEMPLATE_REGION_PARENT_INVALID",
                    "genui",
                    f"{template_id}/{region_id}: parent={parent_id}",
                )
            )
        styles = component.get("styles") if isinstance(component.get("styles"), dict) else {}
        for dimension in ("width", "height"):
            if styles.get(dimension) != region.get(dimension):
                issues.append(
                    issue(
                        "error",
                        "TEMPLATE_REGION_SIZE_MISMATCH",
                        "genui",
                        f"{template_id}/{region_id}/{dimension}",
                    )
                )
        if len(child_ids(component)) > region.get("maxChildren", 0):
            issues.append(
                issue(
                    "error",
                    "TEMPLATE_REGION_CHILD_LIMIT_EXCEEDED",
                    "genui",
                    f"{template_id}/{region_id}",
                )
            )
        default_variants = [
            item for item in variants.get(region_id, []) if isinstance(item, dict) and item.get("id") == "default"
        ]
        if default_variants:
            default = default_variants[0]
            subtree_types = {
                components[component_id].get("component")
                for component_id in region_subtrees[region_id]
            }
            if component.get("component") != default.get("rootComponent") or not subtree_types.issubset(
                set(default.get("allowedComponents", []))
            ):
                issues.append(
                    issue(
                        "error",
                        "TEMPLATE_DEFAULT_VARIANT_MISMATCH",
                        "genui",
                        f"{template_id}/{region_id}",
                    )
                )

    for slot_name, slot in slots.items() if isinstance(slots, dict) else []:
        if not isinstance(slot, dict):
            continue
        component_id = slot.get("component")
        region_id = slot.get("region")
        if component_id is not None and (not isinstance(component_id, str) or component_id not in components):
            issues.append(
                issue(
                    "error",
                    "TEMPLATE_SLOT_COMPONENT_MISSING",
                    "genui",
                    f"{template_id}/{slot_name}: {component_id}",
                )
            )
        elif component_id is not None and component_id not in region_subtrees.get(region_id, set()):
            issues.append(
                issue(
                    "error",
                    "TEMPLATE_SLOT_COMPONENT_OUTSIDE_REGION",
                    "genui",
                    f"{template_id}/{slot_name}: {component_id} not in {region_id}",
                )
            )
    return issues


def validate_template(template_id: str, index_entry: dict[str, Any], strict: bool) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    template_dir = TEMPLATES_DIR / template_id
    manifest_path = template_dir / "manifest.json"
    dsl_path = template_dir / "template.genui.jsonl"
    cardspec_path = template_dir / "cardspec.json"
    manifest = load_json(manifest_path, issues, "manifest")
    cardspec = load_json(cardspec_path, issues, "cardspec")
    issues.extend(validate_manifest_schema(manifest, template_id))
    issues.extend(validate_manifest_shape(manifest, template_id))
    components = load_skeleton_components(dsl_path, issues) if dsl_path.exists() else {}
    if components:
        issues.extend(validate_skeleton_contract(manifest, components, template_id))

    expected_paths = {
        "manifest": f"{template_id}/manifest.json",
        "template": f"{template_id}/template.genui.jsonl",
        "cardspec": f"{template_id}/cardspec.json",
    }
    if any(index_entry.get(key) != value for key, value in expected_paths.items()):
        issues.append(issue("error", "INDEX_PATH_INVALID", "index", template_id))
    if (
        index_entry.get("size") != manifest.get("size")
        or index_entry.get("pattern") != manifest.get("pattern")
        or cardspec.get("suggestSize") != manifest.get("size")
    ):
        issues.append(issue("error", "INDEX_SIZE_MISMATCH", "index", template_id))

    if dsl_path.exists() and cardspec:
        reporter = validate_card(
            dsl_text=dsl_path.read_text(encoding="utf-8"),
            cardspec=cardspec,
            options=ValidationOptions(skill_dir=SKILL_DIR, template_id=template_id),
        )
        issues.extend(
            {
                "severity": diagnostic.severity,
                "code": diagnostic.code,
                "fileKind": diagnostic.file_kind,
                "message": diagnostic.message,
            }
            for diagnostic in reporter.diagnostics
        )
    elif not dsl_path.exists():
        issues.append(issue("error", "FILE_MISSING", "genui", str(dsl_path)))

    errors = sum(item["severity"] == "error" for item in issues)
    warnings = sum(item["severity"] == "warning" for item in issues)
    return {
        "templateId": template_id,
        "valid": errors == 0 and (not strict or warnings == 0),
        "errorCount": errors,
        "warningCount": warnings,
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the template-driven Harmony card library.")
    parser.add_argument("template_ids", nargs="*", help="Specific template ids to validate.")
    parser.add_argument("--all", action="store_true", help="Validate every template in index order.")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    index_issues: list[dict[str, Any]] = []
    index = load_json(TEMPLATES_DIR / "index.json", index_issues, "index")
    entries = index.get("templates") if isinstance(index.get("templates"), list) else []
    by_id = {entry.get("id"): entry for entry in entries if isinstance(entry, dict) and isinstance(entry.get("id"), str)}
    if index.get("schemaVersion") != "template-index-v1":
        index_issues.append(issue("error", "INDEX_VERSION_INVALID", "index", "schemaVersion"))
    if len(entries) != 13 or len(by_id) != 13:
        index_issues.append(issue("error", "INDEX_TEMPLATE_COUNT_INVALID", "index", f"expected 13, got {len(entries)}"))
    fallbacks = index.get("safeFallbacks") if isinstance(index.get("safeFallbacks"), dict) else {}
    for size in ("2x2", "2x4"):
        fallback_id = fallbacks.get(size)
        if fallback_id not in by_id or by_id[fallback_id].get("size") != size:
            index_issues.append(issue("error", "INDEX_SAFE_FALLBACK_INVALID", "index", size))

    if args.all:
        selected = [entry.get("id") for entry in entries if isinstance(entry, dict)]
    elif args.template_ids:
        selected = args.template_ids
    else:
        parser.error("pass --all or at least one template id")
    for template_id in selected:
        if template_id not in by_id:
            index_issues.append(issue("error", "INDEX_TEMPLATE_MISSING", "index", str(template_id)))

    results = [validate_template(template_id, by_id[template_id], args.strict) for template_id in selected if template_id in by_id]
    index_errors = sum(item["severity"] == "error" for item in index_issues)
    index_warnings = sum(item["severity"] == "warning" for item in index_issues)
    valid = index_errors == 0 and (not args.strict or index_warnings == 0) and all(item["valid"] for item in results)
    report = {"valid": valid, "indexIssues": index_issues, "templates": results}

    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for item in index_issues:
            print(f"{item['severity'].upper()} {item['code']}: {item['message']}")
        for result in results:
            status = "OK" if result["valid"] else "FAIL"
            print(f"{status} {result['templateId']} errors={result['errorCount']} warnings={result['warningCount']}")
            for item in result["issues"]:
                print(f"  {item['severity'].upper()} {item['code']}: {item['message']}")
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
