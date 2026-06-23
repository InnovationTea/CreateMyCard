"""JSONL legality rules."""

from __future__ import annotations

try:
    from .common import Finding, ValidationContext
except ImportError:
    from common import Finding, ValidationContext  # type: ignore


def validate(ctx: ValidationContext) -> list[Finding]:
    return list(ctx.line_errors)
