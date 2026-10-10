"""Browser-free layout checks for the constrained generated JSX subset.

The existing budget rules prove conflicts from declared geometry and component
minimum sizes. Large estimated vertical overflow blocks a candidate; smaller
font-dependent estimates remain advisory.
"""
from __future__ import annotations

import re
from typing import Any

if "." in (__package__ or ""):
    from ..jsx_to_a2ui.exceptions import ParseError
    from ..jsx_to_a2ui.parser.jsx_parser import extract_card_functions
else:
    from jsx_to_a2ui.exceptions import ParseError
    from jsx_to_a2ui.parser.jsx_parser import extract_card_functions

from .workflow import LayoutBudgetError, _validate_horizontal_budget, _validate_layout_budget
from .python_geometry import validate_geometry


_ESTIMATED_VERTICAL_OVERFLOW = re.compile(
    r"^.+ may need about (?P<required>\d+(?:\.\d+)?)vp vertically after text wrapping "
    r"while only (?P<available>\d+(?:\.\d+)?)vp is available;"
)


def _is_severe_estimated_overflow(message: str) -> bool:
    match = _ESTIMATED_VERTICAL_OVERFLOW.match(message)
    return bool(
        match
        and float(match.group("required")) - float(match.group("available")) >= 16
    )


def validate_python_layout(*, source: str, component_name: str) -> dict[str, Any]:
    """Return a validator-shaped report without invoking Node or a browser."""
    findings: list[dict[str, str]] = []
    try:
        root = extract_card_functions(source)[component_name]
    except (ParseError, KeyError) as exc:
        findings.append({
            "severity": "error",
            "code": "python-layout-parse",
            "message": f"Python 布局校验无法解析 {component_name}: {exc}",
        })
        return {"ok": False, "kind": "validation", "mode": "python", "findings": findings}

    risks: list[str] = []
    for check in (_validate_layout_budget, _validate_horizontal_budget):
        try:
            check(root, risks)
        except LayoutBudgetError as exc:
            findings.append({
                "severity": "error",
                "code": "python-layout-budget",
                "message": str(exc),
            })
    for message in dict.fromkeys(risks):
        severe = _is_severe_estimated_overflow(message)
        findings.append({
            "severity": "error" if severe else "warning",
            "code": "python-layout-estimated-overflow" if severe else "python-layout-risk",
            "message": message,
        })
    findings.extend(validate_geometry(root))
    return {
        "ok": not any(item["severity"] == "error" for item in findings),
        "kind": "validation",
        "mode": "python",
        "findings": findings,
    }
