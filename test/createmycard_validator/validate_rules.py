#!/usr/bin/env python3
"""Validate validator rule/profile configuration files."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from .engine import PROFILES_DIR, RULES_DIR
    from .registry import MODULE_REGISTRY
except ImportError:
    from engine import PROFILES_DIR, RULES_DIR  # type: ignore
    from registry import MODULE_REGISTRY  # type: ignore

VALID_SEVERITIES = {"ERROR", "WARNING"}


def finding(severity: str, message: str, file: str | None = None) -> dict[str, str]:
    item = {"severity": severity, "message": message}
    if file:
        item["file"] = file
    return item


def load_json(path: Path) -> tuple[Any | None, list[dict[str, str]]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except Exception as exc:  # noqa: BLE001 - config validation should report all parse failures
        return None, [finding("ERROR", f"invalid JSON: {exc}", str(path))]


def validate_rule_files(rules_dir: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    findings: list[dict[str, str]] = []
    rules: dict[str, dict[str, Any]] = {}
    seen_files: dict[str, str] = {}

    for path in sorted(rules_dir.glob("*_rules.json")):
        data, parse_findings = load_json(path)
        findings.extend(parse_findings)
        if data is None:
            continue
        if not isinstance(data, dict):
            findings.append(finding("ERROR", "rule file root must be object", str(path)))
            continue
        if not isinstance(data.get("rules_version"), str) or not data.get("rules_version"):
            findings.append(finding("ERROR", "rules_version must be a non-empty string", str(path)))
        entries = data.get("rules")
        if not isinstance(entries, list):
            findings.append(finding("ERROR", "rules must be an array", str(path)))
            continue
        for index, rule in enumerate(entries, 1):
            where = f"{path}#{index}"
            if not isinstance(rule, dict):
                findings.append(finding("ERROR", "rule entry must be object", where))
                continue
            rule_id = rule.get("id")
            if not isinstance(rule_id, str) or not rule_id:
                findings.append(finding("ERROR", "rule.id must be a non-empty string", where))
                continue
            if rule_id in rules:
                findings.append(finding("ERROR", f"duplicate rule id {rule_id}; first defined in {seen_files[rule_id]}", where))
            rules[rule_id] = rule
            seen_files[rule_id] = where

            module = rule.get("module")
            if module not in MODULE_REGISTRY:
                findings.append(finding("ERROR", f"rule {rule_id}: unknown module {module!r}", where))
            dimension = rule.get("dimension")
            if not isinstance(dimension, str) or not dimension:
                findings.append(finding("ERROR", f"rule {rule_id}: dimension must be non-empty string", where))
            severity = rule.get("severity")
            if severity not in VALID_SEVERITIES:
                findings.append(finding("ERROR", f"rule {rule_id}: severity must be ERROR or WARNING", where))
            deduct = rule.get("deduct")
            if not isinstance(deduct, int) or deduct < 0:
                findings.append(finding("ERROR", f"rule {rule_id}: deduct must be non-negative integer", where))
            if severity == "ERROR" and isinstance(deduct, int) and deduct == 0:
                findings.append(finding("WARNING", f"rule {rule_id}: ERROR rule has zero deduct", where))
            enabled = rule.get("enabled")
            if not isinstance(enabled, bool):
                findings.append(finding("ERROR", f"rule {rule_id}: enabled must be boolean", where))
            message = rule.get("message")
            if not isinstance(message, str) or not message:
                findings.append(finding("ERROR", f"rule {rule_id}: message must be non-empty string", where))
            aggregation = rule.get("aggregation")
            if aggregation is not None:
                if not isinstance(aggregation, dict):
                    findings.append(finding("ERROR", f"rule {rule_id}: aggregation must be object", where))
                else:
                    if "enabled" in aggregation and not isinstance(aggregation["enabled"], bool):
                        findings.append(finding("ERROR", f"rule {rule_id}: aggregation.enabled must be boolean", where))
                    if "max_items" in aggregation and (not isinstance(aggregation["max_items"], int) or aggregation["max_items"] <= 0):
                        findings.append(finding("ERROR", f"rule {rule_id}: aggregation.max_items must be positive integer", where))
    return rules, findings


def validate_profiles(profiles_dir: Path, rules: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for path in sorted(profiles_dir.glob("*.json")):
        data, parse_findings = load_json(path)
        findings.extend(parse_findings)
        if data is None:
            continue
        if not isinstance(data, dict):
            findings.append(finding("ERROR", "profile root must be object", str(path)))
            continue
        enabled_modules = data.get("enabled_modules")
        if not isinstance(enabled_modules, list) or not enabled_modules:
            findings.append(finding("ERROR", "enabled_modules must be a non-empty array", str(path)))
        else:
            for module in enabled_modules:
                if module not in MODULE_REGISTRY:
                    findings.append(finding("ERROR", f"unknown enabled module {module!r}", str(path)))
        disabled_rules = data.get("disabled_rules", [])
        if not isinstance(disabled_rules, list):
            findings.append(finding("ERROR", "disabled_rules must be an array", str(path)))
        else:
            for rule_id in disabled_rules:
                if rule_id not in rules:
                    findings.append(finding("ERROR", f"disabled rule does not exist: {rule_id}", str(path)))
        depends_on = data.get("depends_on", {})
        if not isinstance(depends_on, dict):
            findings.append(finding("ERROR", "depends_on must be an object", str(path)))
        else:
            for module, deps in depends_on.items():
                if module not in MODULE_REGISTRY:
                    findings.append(finding("ERROR", f"depends_on references unknown module {module!r}", str(path)))
                if not isinstance(deps, list):
                    findings.append(finding("ERROR", f"depends_on.{module} must be an array", str(path)))
                    continue
                for dep in deps:
                    if dep not in MODULE_REGISTRY:
                        findings.append(finding("ERROR", f"depends_on.{module} references unknown module {dep!r}", str(path)))
    return findings


RULE_ID_RE = re.compile(r"RULE_[A-Z]+_\d+")


def collect_implemented_rules(root: Path) -> dict[str, set[str]]:
    implemented: dict[str, set[str]] = {name: set() for name in MODULE_REGISTRY}
    for module_name in MODULE_REGISTRY:
        path = root / f"{module_name}_validator.py"
        if path.exists():
            implemented[module_name].update(RULE_ID_RE.findall(path.read_text(encoding="utf-8")))
    common_path = root / "common.py"
    if common_path.exists():
        implemented.setdefault("json", set()).update(
            rule_id for rule_id in RULE_ID_RE.findall(common_path.read_text(encoding="utf-8"))
            if rule_id.startswith("RULE_JSON_")
        )
    return implemented


def validate_rule_implementation_coverage(root: Path, rules: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    implemented_by_module = collect_implemented_rules(root)
    implemented = set().union(*implemented_by_module.values()) if implemented_by_module else set()

    for rule_id, rule in sorted(rules.items()):
        if rule.get("enabled", True) and rule_id not in implemented:
            findings.append(finding("WARNING", f"enabled rule has no detected implementation: {rule_id}"))

    for module_name, rule_ids in sorted(implemented_by_module.items()):
        for rule_id in sorted(rule_ids):
            rule = rules.get(rule_id)
            if rule is None:
                findings.append(finding("ERROR", f"implemented rule is missing metadata: {rule_id}", f"{module_name}_validator.py"))
                continue
            configured_module = rule.get("module")
            if configured_module != module_name:
                findings.append(finding("WARNING", f"rule {rule_id} is implemented in {module_name!r} but configured for {configured_module!r}"))
    return findings


def validate_configs(rules_dir: Path = RULES_DIR, profiles_dir: Path = PROFILES_DIR) -> dict[str, Any]:
    rules, rule_findings = validate_rule_files(rules_dir)
    profile_findings = validate_profiles(profiles_dir, rules)
    implementation_findings = validate_rule_implementation_coverage(rules_dir.parent, rules)
    findings = rule_findings + profile_findings + implementation_findings
    error_count = sum(1 for item in findings if item["severity"] == "ERROR")
    warning_count = sum(1 for item in findings if item["severity"] == "WARNING")
    return {
        "passed": error_count == 0,
        "rule_count": len(rules),
        "profile_count": len(list(profiles_dir.glob("*.json"))),
        "error_count": error_count,
        "warning_count": warning_count,
        "findings": findings,
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Validate validator rule/profile configuration")
    parser.add_argument("--rules-dir", default=str(RULES_DIR))
    parser.add_argument("--profiles-dir", default=str(PROFILES_DIR))
    parser.add_argument("--output", "-o", help="Write JSON report to this path")
    args = parser.parse_args()

    report = validate_configs(Path(args.rules_dir), Path(args.profiles_dir))
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text, encoding="utf-8")
    print(text)
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
