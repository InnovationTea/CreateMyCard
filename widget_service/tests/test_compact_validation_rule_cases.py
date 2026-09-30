"""从重构前实现捕获复合规则的固定输入，覆盖不同提前返回与错误交错顺序。"""

import importlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from services.card_validation.compact_validation.diagnostics import (
    MISSING,
    CompactDiagnostic,
    DiagnosticCollector,
)
from services.card_validation.compact_validation.model_feedback import (
    format_compact_issue_for_model,
)
from services.compact_dsl_a2ui_converter import ComponentRow, DataRow


def _cases() -> list[dict[str, Any]]:
    path = Path(__file__).parent / "fixtures/compact_validation_rule_cases.json"
    baseline = json.loads(path.read_text(encoding="utf-8"))
    cases = baseline.get("cases")
    assert isinstance(cases, list)
    return cases


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case.get("name"))
def test_rule_flow_matches_original(case: dict[str, Any]) -> None:
    records = case.get("components")
    arguments = case.get("arguments")
    assert isinstance(records, list)
    assert isinstance(arguments, dict)
    components = []
    for record in records:
        assert isinstance(record, list) and len(record) == 4
        components.append(ComponentRow(record[0], record[1], deepcopy(record[2]), tuple(record[3])))
    index = {component.component_id: component for component in components}
    errors = DiagnosticCollector()
    kwargs: dict[str, Any] = {"errors": errors}
    for key, value in arguments.items():
        if isinstance(value, dict) and value.get("$ref") == "components":
            kwargs[key] = components
        elif isinstance(value, dict) and value.get("$ref") == "index":
            kwargs[key] = index
        elif isinstance(value, dict) and value.get("$ref") == "component":
            component = index.get(value.get("id"))
            assert component is not None
            kwargs[key] = component
        elif isinstance(value, dict) and value.get("$ref") == "dataRow":
            path = value.get("path")
            assert isinstance(path, str)
            assert "value" in value
            kwargs[key] = DataRow(path, deepcopy(value.get("value")))
        else:
            kwargs[key] = deepcopy(value)
    module_name = case.get("module")
    function_name = case.get("function")
    assert isinstance(module_name, str)
    assert isinstance(function_name, str)
    module = importlib.import_module("services.card_validation.compact_validation." + module_name)
    rule = getattr(module, function_name)
    rule(**kwargs)
    assert list(errors) == case.get("expectedErrors")
    codes = []
    for diagnostic in errors.records:
        if not isinstance(diagnostic, CompactDiagnostic):
            continue
        assert diagnostic.expected is not MISSING
        assert diagnostic.message.strip()
        payload = diagnostic.to_payload()
        serialized = json.loads(json.dumps(payload, ensure_ascii=False))
        feedback = format_compact_issue_for_model({"compactDiagnostics": [payload]})
        assert format_compact_issue_for_model({"compactDiagnostics": [serialized]}) == feedback
        assert diagnostic.code in feedback
        assert "约束：" in feedback
        codes.append(diagnostic.code)
    assert codes == case.get("expectedCodes")
