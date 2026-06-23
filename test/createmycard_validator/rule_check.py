"""Rule implementation metadata helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

try:
    from .common import Finding, ValidationContext
except ImportError:
    from common import Finding, ValidationContext  # type: ignore

RuleCheck = Callable[[ValidationContext], list[Finding]]


@dataclass(frozen=True)
class RuleCheckSpec:
    """A check function and the rule/module it implements."""

    rule_id: str
    module: str
    check: RuleCheck


def run_rule_checks(ctx: ValidationContext, checks: list[RuleCheckSpec]) -> list[Finding]:
    findings: list[Finding] = []
    seen_checks = set()
    for spec in checks:
        if spec.check in seen_checks:
            continue
        seen_checks.add(spec.check)
        findings.extend(spec.check(ctx))
    return findings
