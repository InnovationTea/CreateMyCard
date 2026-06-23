"""Surface consistency rules."""

from __future__ import annotations

try:
    from .common import MESSAGE_KEYS, Finding, SURFACE_ID_RE, ValidationContext, error, warning
except ImportError:
    from common import MESSAGE_KEYS, Finding, SURFACE_ID_RE, ValidationContext, error, warning  # type: ignore


def validate(ctx: ValidationContext) -> list[Finding]:
    findings: list[Finding] = []
    surface_ids: list[str] = []

    for index, msg in enumerate(ctx.messages):
        bodies = [key for key in MESSAGE_KEYS if key in msg]
        if len(bodies) != 1:
            continue
        body = msg[bodies[0]]
        if not isinstance(body, dict):
            continue
        surface_id = body.get("surfaceId")
        if not isinstance(surface_id, str) or not surface_id:
            findings.append(error("RULE_SURFACE_002", f"message {index + 1}: surfaceId must be non-empty", 10))
            continue
        surface_ids.append(surface_id)
        if not SURFACE_ID_RE.match(surface_id):
            findings.append(warning("RULE_SURFACE_003", f"surfaceId '{surface_id}' is not kebab-case"))

    if len(set(surface_ids)) > 1:
        findings.append(error("RULE_SURFACE_001", f"messages use multiple surfaceIds: {sorted(set(surface_ids))}", 10))

    return findings
