#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""从能力注册表同步微服务 Validator 数据能力 schema。"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

VALIDATION_KEYS = frozenset(
    {
        "$defs",
        "$ref",
        "additionalProperties",
        "allOf",
        "anyOf",
        "const",
        "contains",
        "dependentRequired",
        "else",
        "enum",
        "exclusiveMaximum",
        "exclusiveMinimum",
        "format",
        "if",
        "items",
        "maxContains",
        "maxItems",
        "maxLength",
        "maxProperties",
        "maximum",
        "minContains",
        "minItems",
        "minLength",
        "minProperties",
        "minimum",
        "multipleOf",
        "not",
        "oneOf",
        "pattern",
        "patternProperties",
        "prefixItems",
        "properties",
        "propertyNames",
        "required",
        "then",
        "type",
        "unevaluatedProperties",
        "uniqueItems",
    }
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _project_schema(canonical: Any, existing: Any = None) -> Any:
    """仅保留注册表校验语义，并保留 Validator 既有的对象封闭策略。"""
    if isinstance(canonical, list):
        existing_items = existing if isinstance(existing, list) else []
        return [
            _project_schema(item, existing_items[index] if index < len(existing_items) else None)
            for index, item in enumerate(canonical)
        ]
    if not isinstance(canonical, dict):
        return canonical

    existing_object = existing if isinstance(existing, dict) else {}
    projected: dict[str, Any] = {}
    for key, value in canonical.items():
        if key not in VALIDATION_KEYS:
            continue
        existing_value = existing_object.get(key)
        if key in {"properties", "patternProperties", "$defs"}:
            existing_children = existing_value if isinstance(existing_value, dict) else {}
            projected[key] = {
                name: _project_schema(child, existing_children.get(name))
                for name, child in value.items()
            }
            continue
        projected[key] = _project_schema(value, existing_value)

    preserves_closed_object = "additionalProperties" not in projected
    existing_closed = existing_object.get("additionalProperties") is False
    if preserves_closed_object and existing_closed:
        projected["additionalProperties"] = False
    return projected


def _registry_versions(capabilities_root: Path) -> list[str]:
    index = _read_json(capabilities_root / "registry_ranges.json")
    versions = []
    for item in index.get("ranges", []):
        version = item.get("registryVersion")
        if isinstance(version, str) and version not in versions:
            versions.append(version)
    return versions


def _canonical_capabilities(capabilities_root: Path) -> dict[str, dict[str, Any]]:
    capabilities: dict[str, dict[str, Any]] = {}
    for version in _registry_versions(capabilities_root):
        path = capabilities_root / version / "data_capabilities.json"
        for capability in _read_json(path):
            capability_id = capability["id"]
            current = capabilities.get(capability_id)
            projected = {
                "preferredWriteResultTo": capability.get("defaultWriteResultTo"),
                "inputSchema": _project_schema(capability.get("inputSchema", {})),
                "outputSchema": _project_schema(capability.get("outputSchema", {})),
            }
            if current is not None and current != projected:
                raise ValueError(
                    f"{capability_id} has incompatible schemas across registry versions"
                )
            capabilities[capability_id] = projected
    return capabilities


def _schema_files(schema_root: Path) -> dict[str, Path]:
    result = {}
    for path in sorted(schema_root.glob("capability.*.schema.json")):
        payload = _read_json(path)
        capability_id = payload.get("capabilityId")
        if not isinstance(capability_id, str) or not capability_id:
            raise ValueError(f"{path} does not declare capabilityId")
        if capability_id in result:
            raise ValueError(f"duplicate validator schema for {capability_id}")
        result[capability_id] = path
    return result


def _expected_schema(
    capability_id: str,
    canonical: dict[str, Any],
    existing: dict[str, Any],
) -> dict[str, Any]:
    return {
        "capabilityId": capability_id,
        "preferredWriteResultTo": canonical["preferredWriteResultTo"],
        "inputSchema": _project_schema(
            canonical["inputSchema"],
            existing.get("inputSchema"),
        ),
        "outputSchema": _project_schema(
            canonical["outputSchema"],
            existing.get("outputSchema"),
        ),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    path.write_text(content, encoding="utf-8", newline="\n")


def synchronize(project_root: Path, check_only: bool) -> list[str]:
    capabilities_root = project_root / "widget_service" / "cloud" / "data" / "capabilities"
    service_root = (
        project_root / "widget_service" / "cloud" / "data" / "validator_rules" / "schemas"
    )
    canonical = _canonical_capabilities(capabilities_root)
    service_files = _schema_files(service_root)
    missing_files = sorted(set(canonical) - set(service_files))
    if missing_files:
        joined = ", ".join(missing_files)
        raise ValueError(f"validator schema file mapping is missing for: {joined}")

    changes: list[str] = []
    for capability_id, capability in canonical.items():
        service_path = service_files[capability_id]
        current = _read_json(service_path)
        expected = _expected_schema(capability_id, capability, current)
        if current != expected:
            changes.append(str(service_path.relative_to(project_root)))
            if not check_only:
                _write_json(service_path, expected)

    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="只检查差异，不修改文件；发现未同步内容时返回非零退出码。",
    )
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[2]
    try:
        changes = synchronize(project_root, args.check)
    except (OSError, ValueError) as exc:
        print(f"capability schema sync failed: {exc}", file=sys.stderr)
        return 2
    if args.check and changes:
        print("capability schema files are stale:", file=sys.stderr)
        for path in changes:
            print(f"- {path}", file=sys.stderr)
        return 1
    action = "checked" if args.check else "synchronized"
    print(f"capability schemas {action}; changed={len(changes)}")
    return 0


if __name__ == "__main__":
    main()
