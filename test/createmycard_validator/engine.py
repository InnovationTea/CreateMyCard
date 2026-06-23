"""Rule engine for configurable scoring, profiles, and module selection."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from .common import Finding
    from .registry import DEFAULT_MODULES, DEFAULT_PROFILE, MODULE_REGISTRY
except ImportError:
    from common import Finding  # type: ignore
    from registry import DEFAULT_MODULES, DEFAULT_PROFILE, MODULE_REGISTRY  # type: ignore

ENGINE_VERSION = "0.2.0"
ROOT = Path(__file__).resolve().parent
RULES_DIR = ROOT / "rules"
PROFILES_DIR = ROOT / "profiles"


@dataclass
class RuleBook:
    rules: dict[str, dict[str, Any]]
    rules_version: str
    profile_name: str
    enabled_modules: list[str]
    disabled_modules: list[str] = field(default_factory=list)
    disabled_rules: list[str] = field(default_factory=list)
    enabled_rules: list[str] = field(default_factory=list)
    depends_on: dict[str, list[str]] = field(default_factory=dict)

    def module_enabled(self, module: str) -> bool:
        return module in self.enabled_modules and module not in self.disabled_modules

    def rule_enabled(self, rule_id: str) -> bool:
        rule = self.rules.get(rule_id)
        if not rule:
            return True
        if rule_id in self.disabled_rules:
            return False
        if self.enabled_rules and rule_id not in self.enabled_rules:
            return False
        return bool(rule.get("enabled", True)) and self.module_enabled(str(rule.get("module", "")))

    def enrich(self, finding: Finding) -> Finding | None:
        rule = self.rules.get(finding.rule_id)
        if not rule:
            return finding
        if not self.rule_enabled(finding.rule_id):
            return None
        finding.module = str(rule.get("module", finding.module))
        finding.dimension = str(rule.get("dimension", finding.dimension))
        variant = None
        if finding.rule_id == "RULE_PROTOCOL_005" and finding.message.startswith("static widget"):
            variant = self.static_variant(finding.rule_id)
        source = variant or rule
        finding.severity = str(source.get("severity", finding.severity))
        # 优先使用规则 JSON 中定义的 deduct 值（包括 WARNING 级别）
        deduct_from_rule = source.get("deduct")
        if deduct_from_rule is not None:
            finding.deduct = int(deduct_from_rule)
        else:
            finding.deduct = finding.deduct if finding.severity == "ERROR" else 0
        if variant and variant.get("message"):
            finding.message = str(variant["message"])
        return finding

    def make_finding(self, rule_id: str, message: str | None = None, severity: str | None = None, deduct: int | None = None) -> Finding | None:
        rule = self.rules.get(rule_id, {})
        if not self.rule_enabled(rule_id):
            return None
        final_severity = severity or str(rule.get("severity", "ERROR"))
        final_deduct = int(deduct if deduct is not None else rule.get("deduct", 0))
        return Finding(
            rule_id=rule_id,
            module=str(rule.get("module", "")),
            dimension=str(rule.get("dimension", "未分类")),
            severity=final_severity,
            deduct=final_deduct,
            message=message or str(rule.get("message", rule_id)),
        )

    def static_variant(self, rule_id: str) -> dict[str, Any] | None:
        rule = self.rules.get(rule_id, {})
        variant = rule.get("static_without_data")
        return variant if isinstance(variant, dict) else None

    def metadata(self) -> dict[str, Any]:
        return {
            "validator_version": ENGINE_VERSION,
            "rules_version": self.rules_version,
            "profile": self.profile_name,
            "enabled_modules": self.enabled_modules,
            "disabled_modules": self.disabled_modules,
            "disabled_rules": self.disabled_rules,
            "enabled_rules": self.enabled_rules,
        }


def load_rules(rules_dir: Path = RULES_DIR) -> tuple[dict[str, dict[str, Any]], str]:
    rules: dict[str, dict[str, Any]] = {}
    versions: set[str] = set()
    for path in sorted(rules_dir.glob("*_rules.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("rules_version"):
            versions.add(str(data["rules_version"]))
        for rule in data.get("rules", []):
            if not isinstance(rule, dict) or "id" not in rule:
                continue
            rules[str(rule["id"])] = rule
    version = "+".join(sorted(versions)) if versions else "unknown"
    return rules, version


def load_profile(profile: str = DEFAULT_PROFILE, profiles_dir: Path = PROFILES_DIR) -> dict[str, Any]:
    path = Path(profile)
    if not path.suffix:
        path = profiles_dir / f"{profile}.json"
    elif not path.exists():
        path = profiles_dir / path.name
    if not path.exists():
        raise SystemExit(f"Unknown validation profile: {profile}")
    return json.loads(path.read_text(encoding="utf-8"))


def build_rulebook(
    profile: str = DEFAULT_PROFILE,
    enabled_modules: list[str] | None = None,
    disabled_modules: list[str] | None = None,
    enabled_rules: list[str] | None = None,
    disabled_rules: list[str] | None = None,
    rules_dir: Path = RULES_DIR,
) -> RuleBook:
    rules, rules_version = load_rules(rules_dir)
    profile_data = load_profile(profile)
    modules = list(enabled_modules or profile_data.get("enabled_modules") or DEFAULT_MODULES)
    disabled = list(disabled_modules or [])
    profile_disabled_rules = list(profile_data.get("disabled_rules", []))
    rulebook = RuleBook(
        rules=rules,
        rules_version=rules_version,
        profile_name=str(profile_data.get("name", profile)),
        enabled_modules=modules,
        disabled_modules=disabled,
        disabled_rules=profile_disabled_rules + list(disabled_rules or []),
        enabled_rules=list(enabled_rules or []),
        depends_on=dict(profile_data.get("depends_on", {})),
    )
    unknown_enabled = [name for name in rulebook.enabled_modules if name not in MODULE_REGISTRY]
    if unknown_enabled:
        raise SystemExit(f"Unknown validator module(s): {', '.join(unknown_enabled)}")
    unknown_disabled = [name for name in rulebook.disabled_modules if name not in MODULE_REGISTRY]
    if unknown_disabled:
        raise SystemExit(f"Unknown disabled validator module(s): {', '.join(unknown_disabled)}")
    unknown_enabled_rules = [rule_id for rule_id in rulebook.enabled_rules if rule_id not in rules]
    if unknown_enabled_rules:
        raise SystemExit(f"Unknown enabled rule(s): {', '.join(unknown_enabled_rules)}")
    unknown_disabled_rules = [rule_id for rule_id in rulebook.disabled_rules if rule_id not in rules]
    if unknown_disabled_rules:
        raise SystemExit(f"Unknown disabled rule(s): {', '.join(unknown_disabled_rules)}")
    return rulebook


def should_skip_module(module: str, failed_modules: set[str], rulebook: RuleBook) -> str | None:
    deps = rulebook.depends_on.get(module, [])
    failed = [dep for dep in deps if dep in failed_modules]
    if failed:
        return "skipped because dependency module(s) failed: " + ", ".join(failed)
    return None
