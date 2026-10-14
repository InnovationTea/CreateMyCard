"""验证 Fusion 规则归属与已退出流程的边界。"""

import ast
import json
from pathlib import Path

from services.card_validation.compact_validation.rule_catalog import RULE_CODES

PACKAGE = Path(__file__).parents[1] / "cloud/services/card_validation/compact_validation"


def test_current_structured_rules_have_one_registered_owner() -> None:
    registry = json.loads(
        (Path(__file__).parent / "fixtures/compact_validation_rule_inventory.json").read_text(
            encoding="utf-8"
        )
    )
    sites = registry.get("sites")
    assert isinstance(sites, list)
    actual = []
    for file in sorted(PACKAGE.rglob("*.py")):
        for function in ast.parse(file.read_text(encoding="utf-8")).body:
            if not isinstance(function, ast.FunctionDef):
                continue
            for node in ast.walk(function):
                if not isinstance(node, ast.Call):
                    continue
                if not isinstance(node.func, ast.Name) or node.func.id != "CompactDiagnostic":
                    continue
                values = {keyword.arg: keyword.value for keyword in node.keywords}
                code = values.get("code")
                class_node = values.get("validation_class")
                category = values.get("category")
                assert isinstance(code, ast.Constant)
                assert class_node is not None and category is not None
                relative = file.relative_to(PACKAGE).as_posix()
                classification = ast.literal_eval(class_node)
                assert relative.startswith(classification + "/")
                assert values.get("expected") is not None
                actual.append(
                    {
                        "module": relative,
                        "function": function.name,
                        "code": code.value,
                        "class": classification,
                        "category": ast.literal_eval(category),
                    }
                )
    assert actual == sites
    codes = {site.get("code") for site in actual}
    assert codes == RULE_CODES
    assert len(codes) == len(actual)


def test_active_rules_do_not_depend_on_retired_flows_or_presentation() -> None:
    forbidden = (".flows", ".api", ".repair_guidance", ".model_feedback", ".compatibility")
    for folder in ("syntax", "semantic"):
        for file in (PACKAGE / folder).rglob("*.py"):
            for node in ast.walk(ast.parse(file.read_text(encoding="utf-8"))):
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert not any(part in node.module for part in forbidden), file
    api = (PACKAGE / "api.py").read_text(encoding="utf-8")
    for retired in ("_collect_hero_value_errors", "dual_action", "w9", "w1", "s4"):
        assert retired not in api
    for file in PACKAGE.rglob("*.py"):
        source = file.read_text(encoding="utf-8")
        assert "validate_card_header_layout" not in source
        assert "validate_timeline_unit_layout" not in source
        assert "compact_dual_action_validator" not in source
