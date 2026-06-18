#!/usr/bin/env python3
"""Validate a V5 CardSpec JSON file."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


PATH_RE = re.compile(r"^/(?:[^~/]|~[01])*(?:/(?:[^~/]|~[01])*)*$")

CAPABILITIES: dict[tuple[str, str], dict[str, Any]] = {
    ("calendar.events.search", "1.0"): {
        "arguments": {
            "range": "string",
            "title": "string",
            "eventLocation": "string",
            "limit": "integer",
        }
    },
    ("weather.overview.get", "1.0"): {
        "arguments": {
            "districtName": "string",
            "prefectureName": "string",
            "forecastDays": "integer",
        }
    },
}


def type_matches(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    return True


def validate_refresh(
    refresh: Any,
    binding_ids: set[str],
    errors: list[str],
) -> None:
    if refresh is None:
        return
    if not isinstance(refresh, dict):
        errors.append("refreshPlan must be an object")
        return

    def check_refs(value: Any, location: str) -> None:
        if value is None:
            return
        if not isinstance(value, list):
            errors.append(f"{location} must be an array of bindingId strings")
            return
        for binding_id in value:
            if not isinstance(binding_id, str) or binding_id not in binding_ids:
                errors.append(f"{location} references unknown binding {binding_id!r}")

    check_refs(refresh.get("onInstall"), "refreshPlan.onInstall")
    check_refs(refresh.get("onVisible"), "refreshPlan.onVisible")

    periodic = refresh.get("periodic")
    if periodic is None:
        return
    if not isinstance(periodic, dict):
        errors.append("refreshPlan.periodic must be an object")
        return
    interval = periodic.get("intervalSec")
    if not isinstance(interval, int) or isinstance(interval, bool) or interval <= 0:
        errors.append("refreshPlan.periodic.intervalSec must be a positive integer")
    check_refs(periodic.get("bindings"), "refreshPlan.periodic.bindings")


def validate(spec: Any) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(spec, dict):
        return ["CardSpec top level must be an object"], warnings

    suggest_size = spec.get("suggestSize")
    if suggest_size not in {"2x2", "2x4"}:
        errors.append("suggestSize must be '2x2' or '2x4'")

    bindings_value = spec.get("dataBindings")
    if bindings_value is None:
        if "refreshPlan" in spec:
            errors.append("refreshPlan requires dataBindings")
        return errors, warnings

    if not isinstance(bindings_value, list):
        errors.append("dataBindings must be an array")
        return errors, warnings

    if not bindings_value:
        warnings.append("dataBindings is empty; omit it for a static card")

    binding_ids: set[str] = set()
    has_binding_ids = False
    write_paths: list[tuple[str, str]] = []

    for index, binding in enumerate(bindings_value):
        if not isinstance(binding, dict):
            errors.append(f"dataBindings[{index}] must be an object")
            continue

        binding_id = binding.get("bindingId")
        if binding_id is None:
            binding_id = f"<index {index}>"
        else:
            has_binding_ids = True
            if not isinstance(binding_id, str) or not binding_id:
                errors.append(f"dataBindings[{index}].bindingId must be a non-empty string")
                binding_id = f"<index {index}>"
            elif binding_id in binding_ids:
                errors.append(f"bindingId is duplicated: {binding_id!r}")
            else:
                binding_ids.add(binding_id)

        capability_id = binding.get("capabilityId")
        version = binding.get("capabilityVersion", "1.0")
        if not isinstance(capability_id, str) or not capability_id:
            errors.append(f"binding {binding_id!r}: capabilityId must be a non-empty string")
        if not isinstance(version, str) or not version:
            errors.append(f"binding {binding_id!r}: capabilityVersion must be a non-empty string")

        capability = CAPABILITIES.get((capability_id, version))
        if capability is None:
            errors.append(
                f"binding {binding_id!r}: unknown capability "
                f"{capability_id!r} version {version!r}"
            )

        arguments = binding.get("arguments")
        if not isinstance(arguments, dict):
            errors.append(f"binding {binding_id!r}: arguments must be an object")
        elif capability is not None:
            allowed = capability["arguments"]
            for name, value in arguments.items():
                expected = allowed.get(name)
                if expected is None:
                    errors.append(f"binding {binding_id!r}: unknown argument {name!r}")
                elif not type_matches(value, expected):
                    errors.append(
                        f"binding {binding_id!r}: argument {name!r} must be {expected}"
                    )

        write_path = binding.get("writeResultTo")
        if (
            not isinstance(write_path, str)
            or not PATH_RE.match(write_path)
            or not (write_path == "/data" or write_path.startswith("/data/"))
        ):
            errors.append(
                f"binding {binding_id!r}: writeResultTo must be a JSON Pointer under /data"
            )
        else:
            write_paths.append((binding_id, write_path))

    for index, (left_id, left_path) in enumerate(write_paths):
        for right_id, right_path in write_paths[index + 1 :]:
            overlaps = (
                left_path == right_path
                or left_path.startswith(right_path + "/")
                or right_path.startswith(left_path + "/")
            )
            if overlaps:
                errors.append(
                    f"binding {left_id!r} and {right_id!r} have overlapping writeResultTo paths"
                )

    if spec.get("refreshPlan") is not None and not has_binding_ids:
        errors.append("refreshPlan requires dataBindings[].bindingId")
    validate_refresh(spec.get("refreshPlan"), binding_ids, errors)
    return errors, warnings


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: python validate_cardspec.py <temp.cardspec.json>")
        return 2

    path = Path(argv[1])
    try:
        spec = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        print(f"Failed to load CardSpec: {exc}")
        return 1

    errors, warnings = validate(spec)
    if errors:
        print(f"Found {len(errors)} error(s):")
        for error in errors:
            print(f" - {error}")
        if warnings:
            print(f"Found {len(warnings)} warning(s):")
            for warning in warnings:
                print(f" - {warning}")
        return 1

    if warnings:
        print(f"Found {len(warnings)} warning(s):")
        for warning in warnings:
            print(f" - {warning}")
    print("CardSpec validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
