"""对照重构前固定输入，防止分类迁移改变公开校验行为。"""

import json
from pathlib import Path
from typing import Any

import pytest

from services.card_validation.compact_dsl_validator import (
    CompactDslValidationError,
    validate_compact_dsl,
)


def _baseline_cases() -> list[dict[str, Any]]:
    path = Path(__file__).parent / "fixtures" / "compact_validation_baseline.json"
    baseline = json.loads(path.read_text(encoding="utf-8"))
    cases = baseline.get("cases")
    assert isinstance(cases, list)
    return cases


@pytest.mark.parametrize("case", _baseline_cases())
def test_public_validator_matches_original(case: dict[str, Any]) -> None:
    inputs = case.get("input")
    expected = case.get("expected")
    assert isinstance(inputs, dict)
    assert isinstance(expected, dict)
    source = inputs.get("source")
    task_spec = inputs.get("task_spec")
    card_spec = inputs.get("card_spec")
    assert isinstance(source, str)
    assert isinstance(task_spec, dict)
    assert isinstance(card_spec, dict)
    if "warnings" in expected:
        result = validate_compact_dsl(source, task_spec=task_spec, card_spec=card_spec)
        assert isinstance(result.warnings, tuple)
        assert list(result.warnings) == expected.get("warnings")
        return

    with pytest.raises(CompactDslValidationError) as raised:
        validate_compact_dsl(source, task_spec=task_spec, card_spec=card_spec)
    error = raised.value
    assert isinstance(error, ValueError)
    assert isinstance(error.errors, tuple)
    assert type(error).__name__ == expected.get("type")
    assert list(error.errors) == expected.get("errors")
    assert str(error) == expected.get("text")
    assert error.args == (expected.get("text"),)
    cause = error.__cause__
    assert (type(cause).__name__ if cause else None) == expected.get("cause_type")
    assert (str(cause) if cause else None) == expected.get("cause_text")
