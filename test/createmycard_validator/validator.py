"""A2UI JSONL DSL scoring validator.

Public API remains backward compatible:
    validate(dsl_text)
    validate_file(path)
    validate_directory(dir)

New optional controls:
    profile, enabled_modules, disabled_modules, enabled_rules, disabled_rules
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from .common import Finding, collect_context
    from .engine import RuleBook, build_rulebook, should_skip_module
    from .registry import DEFAULT_PROFILE, MODULE_REGISTRY
except ImportError:  # Allows: python createmycard_validator/validator.py <file>
    from common import Finding, collect_context  # type: ignore
    from engine import RuleBook, build_rulebook, should_skip_module  # type: ignore
    from registry import DEFAULT_PROFILE, MODULE_REGISTRY  # type: ignore


def dedupe_findings(findings: list[Finding]) -> list[Finding]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[Finding] = []
    for item in findings:
        key = (item.rule_id, item.severity, item.message)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def apply_aggregation(findings: list[Finding], rulebook: RuleBook) -> list[Finding]:
    grouped: dict[str, list[Finding]] = defaultdict(list)
    output: list[Finding] = []
    for item in findings:
        rule = rulebook.rules.get(item.rule_id, {})
        aggregation = rule.get("aggregation", {}) if isinstance(rule.get("aggregation"), dict) else {}
        if aggregation.get("enabled") and aggregation.get("mode", "by_rule") == "by_rule":
            grouped[item.rule_id].append(item)
        else:
            output.append(item)

    for rule_id, items in grouped.items():
        if len(items) == 1:
            output.append(items[0])
            continue
        rule = rulebook.rules.get(rule_id, {})
        max_items = int(rule.get("aggregation", {}).get("max_items", 20)) if isinstance(rule.get("aggregation"), dict) else 20
        names: list[str] = []
        for item in items[:max_items]:
            message = item.message
            # Heuristic: collect quoted component id from messages like Text 'xxx'...
            if "'" in message:
                parts = message.split("'")
                if len(parts) >= 3:
                    names.append(parts[1])
                    continue
            names.append(message)
        if len(items) > max_items:
            names.append(f"... (+{len(items) - max_items} more)")
        first = items[0]
        output.append(
            Finding(
                rule_id=rule_id,
                module=first.module,
                dimension=first.dimension,
                severity=first.severity,
                deduct=first.deduct,
                message=f"{len(items)} findings for {rule_id}: " + ", ".join(names),
                count=len(items),
                items=names,
            )
        )
    return output


def summarize_dimensions(findings: list[Finding], rulebook: RuleBook) -> tuple[dict[str, int], dict[str, int], dict[str, Any]]:
    all_dimensions = {
        str(rule.get("dimension", "未分类"))
        for rule in rulebook.rules.values()
        if rulebook.module_enabled(str(rule.get("module", ""))) and rulebook.rule_enabled(str(rule.get("id", "")))
    }
    deduct_by_dimension: dict[str, int] = defaultdict(int)
    hit_by_dimension: dict[str, int] = defaultdict(int)
    summary: dict[str, dict[str, Any]] = {}

    for dimension in all_dimensions:
        hit_by_dimension.setdefault(dimension, 0)
        summary[dimension] = {
            "score": 100,
            "deduct": 0,
            "error_count": 0,
            "warning_count": 0,
            "rules": [],
            "messages": [],
        }

    for item in findings:
        dimension = item.dimension
        hit_by_dimension[dimension] += item.count
        entry = summary.setdefault(
            dimension,
            {"score": 100, "deduct": 0, "error_count": 0, "warning_count": 0, "rules": [], "messages": []},
        )
        if item.severity == "ERROR":
            entry["error_count"] += item.count
            entry["deduct"] += item.deduct
            deduct_by_dimension[dimension] += item.deduct
        elif item.severity == "WARNING":
            entry["warning_count"] += item.count
        if item.rule_id not in entry["rules"]:
            entry["rules"].append(item.rule_id)
        entry["messages"].append(item.message)

    dimension_scores = {
        dimension: max(0, 100 - deduct_by_dimension.get(dimension, 0))
        for dimension in summary
    }
    for dimension, entry in summary.items():
        entry["score"] = dimension_scores[dimension]
        entry["rules"] = sorted(entry["rules"])

    return (
        dict(sorted(dimension_scores.items())),
        dict(sorted(hit_by_dimension.items())),
        dict(sorted(summary.items())),
    )


def validate(
    dsl_text: str,
    profile: str = DEFAULT_PROFILE,
    enabled_modules: list[str] | None = None,
    disabled_modules: list[str] | None = None,
    enabled_rules: list[str] | None = None,
    disabled_rules: list[str] | None = None,
) -> dict[str, Any]:
    rulebook = build_rulebook(
        profile=profile,
        enabled_modules=enabled_modules,
        disabled_modules=disabled_modules,
        enabled_rules=enabled_rules,
        disabled_rules=disabled_rules,
    )
    ctx = collect_context(dsl_text)
    findings: list[Finding] = []
    skipped_modules: dict[str, str] = {}
    failed_modules: set[str] = set()

    for module_name in rulebook.enabled_modules:
        if not rulebook.module_enabled(module_name):
            skipped_modules[module_name] = "disabled"
            continue
        reason = should_skip_module(module_name, failed_modules, rulebook)
        if reason:
            skipped_modules[module_name] = reason
            continue
        module = MODULE_REGISTRY[module_name]
        module_findings = []
        for finding in module.validate(ctx):
            enriched = rulebook.enrich(finding)
            if enriched:
                module_findings.append(enriched)
        findings.extend(module_findings)
        if any(item.severity == "ERROR" for item in module_findings):
            failed_modules.add(module_name)

    unique = apply_aggregation(dedupe_findings(findings), rulebook)
    total_deduct = sum(item.deduct for item in unique if item.severity == "ERROR")
    score = max(0, 100 - total_deduct)
    passed = not any(item.severity == "ERROR" for item in unique)
    dimension_scores, dimension_hits, dimension_summary = summarize_dimensions(unique, rulebook)
    return {
        **rulebook.metadata(),
        "score": score,
        "passed": passed,
        "dimension_scores": dimension_scores,
        "dimension_hits": dimension_hits,
        "dimension_summary": dimension_summary,
        "skipped_modules": skipped_modules,
        "errors": [item.to_dict() for item in unique],
    }


def dsl_array_to_text(dsl_array: list[dict[str, Any]]) -> str:
    """将 DSL 数组格式转换为纯 JSONL 字符串格式。"""
    return "\n".join(json.dumps(item, ensure_ascii=False) for item in dsl_array)


def dsl_value_to_text(value: Any) -> tuple[str, str] | None:
    if isinstance(value, list):
        return dsl_array_to_text(value), "results-array"
    if isinstance(value, str):
        return value, "results-single"
    return None


def extract_dsl_entries_from_file(path: Path) -> list[tuple[str, str, str]]:
    """从文件中提取一个或多个 DSL 文本。

    Returns:
        [(item_id, dsl_text, format_type), ...]
    """
    content = path.read_text(encoding="utf-8-sig")
    try:
        data = json.loads(content)
        if isinstance(data, list):
            entries: list[tuple[str, str, str]] = []
            for index, item in enumerate(data, 1):
                if not isinstance(item, dict) or "dsl" not in item:
                    continue
                converted = dsl_value_to_text(item["dsl"])
                if converted:
                    dsl_text, format_type = converted
                    entries.append((str(item.get("id") or index), dsl_text, format_type))
            if entries:
                return entries
        elif isinstance(data, dict) and "dsl" in data:
            converted = dsl_value_to_text(data["dsl"])
            if converted:
                dsl_text, format_type = converted
                return [(str(data.get("id") or path.stem), dsl_text, format_type)]
    except json.JSONDecodeError:
        pass
    return [(path.stem, content, "jsonl")]


def extract_dsl_from_file(path: Path) -> tuple[str, str]:
    entries = extract_dsl_entries_from_file(path)
    return entries[0][1], entries[0][2]


def validate_file(
    path: str | Path,
    profile: str = DEFAULT_PROFILE,
    enabled_modules: list[str] | None = None,
    disabled_modules: list[str] | None = None,
    enabled_rules: list[str] | None = None,
    disabled_rules: list[str] | None = None,
) -> dict[str, Any]:
    path = Path(path)
    entries = extract_dsl_entries_from_file(path)
    if len(entries) > 1:
        return aggregate_file_results(
            path,
            [
                validate_dsl_entry(item_id, dsl_text, format_type, path, profile, enabled_modules, disabled_modules, enabled_rules, disabled_rules)
                for item_id, dsl_text, format_type in entries
            ],
            profile=profile,
            enabled_modules=enabled_modules,
            disabled_modules=disabled_modules,
            enabled_rules=enabled_rules,
            disabled_rules=disabled_rules,
        )
    item_id, dsl_text, format_type = entries[0]
    return validate_dsl_entry(item_id, dsl_text, format_type, path, profile, enabled_modules, disabled_modules, enabled_rules, disabled_rules)


def validate_dsl_entry(
    item_id: str,
    dsl_text: str,
    format_type: str,
    path: Path,
    profile: str,
    enabled_modules: list[str] | None,
    disabled_modules: list[str] | None,
    enabled_rules: list[str] | None,
    disabled_rules: list[str] | None,
) -> dict[str, Any]:
    result = validate(
        dsl_text,
        profile=profile,
        enabled_modules=enabled_modules,
        disabled_modules=disabled_modules,
        enabled_rules=enabled_rules,
        disabled_rules=disabled_rules,
    )
    result["file"] = str(path)
    result["item_id"] = item_id
    result["dsl_format"] = format_type
    return result


def aggregate_file_results(
    path: Path,
    results: list[dict[str, Any]],
    profile: str,
    enabled_modules: list[str] | None,
    disabled_modules: list[str] | None,
    enabled_rules: list[str] | None,
    disabled_rules: list[str] | None,
) -> dict[str, Any]:
    return aggregate_results(
        results,
        directory=str(path),
        profile=profile,
        enabled_modules=enabled_modules,
        disabled_modules=disabled_modules,
        enabled_rules=enabled_rules,
        disabled_rules=disabled_rules,
    )


def validate_directory(
    directory: str | Path,
    profile: str = DEFAULT_PROFILE,
    enabled_modules: list[str] | None = None,
    disabled_modules: list[str] | None = None,
    enabled_rules: list[str] | None = None,
    disabled_rules: list[str] | None = None,
) -> dict[str, Any]:
    directory = Path(directory)
    native_candidates = (
        list(directory.glob("*.dat"))
        + list(directory.glob("*.jsonl"))
        + list(directory.glob("*.dsl"))
    )
    json_candidates = [
        path for path in directory.glob("*.json")
        if path.name != "validation_report.json"
        and not path.name.endswith(".report.json")
        and not path.name.endswith("_report.json")
        and (path.name != "results.json" or not native_candidates)
    ]
    files = sorted(
        path for path in native_candidates + json_candidates
        if not path.name.endswith("_results.jsonl")
    )
    results = [
        validate_file(
            path,
            profile=profile,
            enabled_modules=enabled_modules,
            disabled_modules=disabled_modules,
            enabled_rules=enabled_rules,
            disabled_rules=disabled_rules,
        )
        for path in files
    ]
    return aggregate_results(
        results,
        directory=str(directory),
        profile=profile,
        enabled_modules=enabled_modules,
        disabled_modules=disabled_modules,
        enabled_rules=enabled_rules,
        disabled_rules=disabled_rules,
    )


def aggregate_results(
    results: list[dict[str, Any]],
    directory: str,
    profile: str,
    enabled_modules: list[str] | None,
    disabled_modules: list[str] | None,
    enabled_rules: list[str] | None,
    disabled_rules: list[str] | None,
) -> dict[str, Any]:
    pass_count = sum(1 for item in results if item["passed"])
    fail_count = len(results) - pass_count
    avg_score = round(sum(item["score"] for item in results) / len(results), 2) if results else 0
    rule_hits: Counter[str] = Counter()
    dimension_scores: dict[str, list[int]] = defaultdict(list)
    directory_dimension_summary: dict[str, dict[str, Any]] = {}
    for item in results:
        for finding in item["errors"]:
            rule_hits[finding["rule_id"]] += finding.get("count", 1)
        for dimension, score in item.get("dimension_scores", {}).items():
            dimension_scores[dimension].append(score)
        for dimension, summary in item.get("dimension_summary", {}).items():
            entry = directory_dimension_summary.setdefault(
                dimension,
                {"average_score": 100.0, "deduct": 0, "error_count": 0, "warning_count": 0, "rules": set(), "messages": []},
            )
            entry["deduct"] += int(summary.get("deduct", 0))
            entry["error_count"] += int(summary.get("error_count", 0))
            entry["warning_count"] += int(summary.get("warning_count", 0))
            entry["rules"].update(summary.get("rules", []))
            entry["messages"].extend(summary.get("messages", []))
    avg_dimension_scores = {
        dimension: round(sum(values) / len(values), 2)
        for dimension, values in sorted(dimension_scores.items())
    }
    for dimension, entry in directory_dimension_summary.items():
        entry["average_score"] = avg_dimension_scores.get(dimension, 100.0)
        entry["rules"] = sorted(entry["rules"])
    meta = results[0] if results else validate("", profile=profile, enabled_modules=enabled_modules, disabled_modules=disabled_modules, enabled_rules=enabled_rules, disabled_rules=disabled_rules)
    all_findings = [finding for item in results for finding in item.get("errors", [])]
    return {
        "validator_version": meta.get("validator_version"),
        "rules_version": meta.get("rules_version"),
        "profile": meta.get("profile"),
        "enabled_modules": meta.get("enabled_modules"),
        "disabled_modules": meta.get("disabled_modules"),
        "directory": directory,
        "total": len(results),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "score": avg_score,
        "passed": fail_count == 0,
        "average_score": avg_score,
        "dimension_scores": avg_dimension_scores,
        "dimension_summary": dict(sorted(directory_dimension_summary.items())),
        "rule_hits": dict(sorted(rule_hits.items())),
        "errors": all_findings,
        "results": results,
    }


def list_modules() -> list[dict[str, Any]]:
    return [{"name": name, "module": module.__name__} for name, module in MODULE_REGISTRY.items()]


def list_rules(profile: str = DEFAULT_PROFILE) -> list[dict[str, Any]]:
    rulebook = build_rulebook(profile=profile)
    return [
        {
            "id": rule_id,
            "module": rule.get("module"),
            "dimension": rule.get("dimension"),
            "severity": rule.get("severity"),
            "deduct": rule.get("deduct"),
            "enabled": rulebook.rule_enabled(rule_id),
            "message": rule.get("message"),
        }
        for rule_id, rule in sorted(rulebook.rules.items())
    ]


def explain_rule(rule_id: str, profile: str = DEFAULT_PROFILE) -> dict[str, Any]:
    rulebook = build_rulebook(profile=profile)
    rule = rulebook.rules.get(rule_id)
    if not rule:
        raise SystemExit(f"Unknown rule id: {rule_id}")
    return {**rule, "effective_enabled": rulebook.rule_enabled(rule_id), "profile": rulebook.profile_name, "rules_version": rulebook.rules_version}


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Score A2UI JSONL DSL files")
    parser.add_argument("path", nargs="?", help="DSL file or directory")
    parser.add_argument("--output", "-o", help="Write JSON report to this path")
    parser.add_argument("--profile", default=DEFAULT_PROFILE, help="Validation profile name or path")
    parser.add_argument("--enable", nargs="*", dest="enabled_modules", help="Only run these modules")
    parser.add_argument("--disable", nargs="*", dest="disabled_modules", default=[], help="Disable these modules")
    parser.add_argument("--enable-rule", nargs="*", dest="enabled_rules", default=[], help="Only enable these rule IDs")
    parser.add_argument("--disable-rule", nargs="*", dest="disabled_rules", default=[], help="Disable these rule IDs")
    parser.add_argument("--list-modules", action="store_true", help="List registered validator modules")
    parser.add_argument("--list-rules", action="store_true", help="List configured rules")
    parser.add_argument("--explain-rule", help="Print one rule definition")
    args = parser.parse_args()

    if args.list_modules:
        text = json.dumps(list_modules(), ensure_ascii=False, indent=2)
        print(text)
        return
    if args.list_rules:
        text = json.dumps(list_rules(args.profile), ensure_ascii=False, indent=2)
        print(text)
        return
    if args.explain_rule:
        text = json.dumps(explain_rule(args.explain_rule, args.profile), ensure_ascii=False, indent=2)
        print(text)
        return
    if not args.path:
        parser.error("path is required unless --list-modules, --list-rules, or --explain-rule is used")

    path = Path(args.path)
    kwargs = {
        "profile": args.profile,
        "enabled_modules": args.enabled_modules,
        "disabled_modules": args.disabled_modules,
        "enabled_rules": args.enabled_rules,
        "disabled_rules": args.disabled_rules,
    }
    report = validate_directory(path, **kwargs) if path.is_dir() else validate_file(path, **kwargs)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
