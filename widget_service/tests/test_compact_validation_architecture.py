"""检查迁移清单、分类归属和单向依赖，防止后续新增检查绕过设计约定。"""

import ast
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from services.card_validation.compact_validation.rule_catalog import RULE_CODES

PACKAGE = Path(__file__).parents[1] / "cloud/services/card_validation/compact_validation"
REGISTRY = Path(__file__).parent / "fixtures/compact_validation_rule_inventory.json"


def _value(values: dict[str | None, ast.expr], key: str) -> Any:
    node = values.get(key)
    assert node is not None, key
    return ast.literal_eval(node)


def _current_sites() -> list[dict[str, Any]]:
    sites = []
    for file in PACKAGE.rglob("*.py"):
        tree = ast.parse(file.read_text(encoding="utf-8"))
        for function in tree.body:
            if not isinstance(function, ast.FunctionDef):
                continue
            if file.name == "diagnostics.py" and function.name == "emit_error":
                # 该适配器将已有诊断写入普通字符串列表，不是新的违规判定。
                continue
            for call in ast.walk(function):
                if not isinstance(call, ast.Call):
                    continue
                code = None
                category = None
                if isinstance(call.func, ast.Name) and call.func.id == "CompactDiagnostic":
                    values = {keyword.arg: keyword.value for keyword in call.keywords}
                    legacy = values.get("legacy_message")
                    code = _value(values, "code")
                    category = _value(values, "category")
                    validation_class = _value(values, "validation_class")
                    assert values.get("expected") is not None, code
                    message = values.get("message")
                    assert isinstance(message, (ast.Constant, ast.JoinedStr)), code
                    if isinstance(message, ast.Constant):
                        assert isinstance(message.value, str) and message.value.strip(), code
                    relative = file.relative_to(PACKAGE).as_posix()
                    if relative.startswith("syntax/"):
                        assert validation_class == "syntax"
                        expected_category = {
                            "components": "component",
                            "expressions": "expression",
                        }.get(file.stem)
                    else:
                        assert relative.startswith("semantic/"), (relative, code)
                        assert validation_class == "semantic"
                        if relative.startswith("semantic/layout/"):
                            expected_category = "layout"
                        else:
                            expected_category = {
                                "bindings": "binding",
                                "cross_file": "cross_file",
                                "effective": "effective",
                                "display": "display",
                            }.get(file.stem)
                    assert category == expected_category, (relative, code, category)
                    status = "structured"
                elif ast.unparse(call.func) == "errors.append":
                    legacy = call.args[0]
                    status = "legacy"
                else:
                    continue
                assert legacy is not None
                sites.append(
                    {
                        "module": file.relative_to(PACKAGE).as_posix(),
                        "function": function.name,
                        "code": code,
                        "category": category,
                        "status": status,
                        "legacyAstSha256": hashlib.sha256(ast.dump(legacy).encode()).hexdigest(),
                    }
                )
    return sites


def _site_key(site: dict[str, Any]) -> str:
    fields = ("module", "function", "code", "category", "status", "legacyAstSha256")
    values = {}
    for field in fields:
        assert field in site, field
        values[field] = site.get(field)
    return json.dumps(values, ensure_ascii=False, sort_keys=True)


def test_all_original_sites_keep_legacy_expressions_and_registered_ownership() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    recorded = registry.get("sites")
    assert isinstance(recorded, list)
    assert len(recorded) == 153
    assert len({site.get("observation") for site in recorded}) == 153
    current = _current_sites()
    assert Counter(_site_key(site) for site in current) == Counter(
        _site_key(site) for site in recorded
    )
    codes = set()
    legacy_observations = set()
    for site in recorded:
        if site.get("status") == "structured":
            codes.add(site.get("code"))
            assert site.get("behaviorCovered") is True, site.get("observation")
            assert site.get("tests"), site.get("observation")
        else:
            legacy_observations.add(site.get("observation"))
    assert codes == RULE_CODES
    assert legacy_observations == {
        "OBS-L3455",
        "OBS-L3909",
        "OBS-L4139",
        "OBS-L4302",
        "OBS-L4306",
    }


def test_rule_modules_never_import_flows_entry_or_repair_presentation() -> None:
    forbidden = (".flows", ".api", ".repair_guidance", ".model_feedback")
    for folder in ("syntax", "semantic"):
        for file in (PACKAGE / folder).rglob("*.py"):
            tree = ast.parse(file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert not any(part in node.module for part in forbidden), (file, node.module)
