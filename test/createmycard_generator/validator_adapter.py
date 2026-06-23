"""Adapter for the project A2UI validator package."""

from __future__ import annotations

from typing import Any, Callable

VALIDATOR_IMPORT = "createmycard_validator.validator:validate"
_validate_dsl: Callable[..., dict[str, Any]] | None = None
_import_error: Exception | None = None


def _load_validator() -> Callable[..., dict[str, Any]] | None:
    global _validate_dsl, _import_error
    if _validate_dsl is not None:
        return _validate_dsl
    if _import_error is not None:
        return None
    try:
        from createmycard_validator.validator import validate
    except Exception as exc:  # noqa: BLE001 - reported when validation is requested
        _import_error = exc
        return None
    _validate_dsl = validate
    return _validate_dsl


def validator_available() -> bool:
    return _load_validator() is not None


def run_validator(dsl_text: str) -> dict[str, Any]:
    validate = _load_validator()
    if validate is None:
        suffix = f": {_import_error}" if _import_error else ""
        raise RuntimeError(f"无法加载校验器：{VALIDATOR_IMPORT}{suffix}")
    return validate(dsl_text)


def parse_validation_output(result: dict[str, Any]) -> dict[str, Any]:
    all_errors = []
    all_warnings = []
    for err in result.get("errors", []):
        msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        severity = err.get("severity") if isinstance(err, dict) else None
        if severity == "WARNING":
            all_warnings.append(msg)
        else:
            all_errors.append(msg)
    return {
        "ok": result.get("passed", len(all_errors) == 0),
        "errors": all_errors,
        "warnings": all_warnings,
        "message_count": 0,
        "component_count": 0,
        "score": result.get("score", 0),
        "dimension_scores": result.get("dimension_scores", {}),
    }
