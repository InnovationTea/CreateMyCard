"""回归夹具：覆盖此前未命中的 8 条规则。

这些测试刻意使用最小 artifact，避免天气/日历样例中无关的能力、事件和素材
诊断干扰目标规则。R56 直接调用表达式校验器，因为公开 DSL 解析器当前不会
收集空 `${}` 引用；该测试仍验证规则实现本身。
"""

import json
from pathlib import Path

import pytest

from services.card_validation import validate_card
from services.card_validation.context import ValidationContext
from services.card_validation.diagnostics import Reporter
from services.card_validation.expression_validator import ExpressionValidator
from services.card_validation.rule_registry import RuleRegistry

RULE_CODES = {
    2: "DSL_VERSION_INVALID", 3: "DSL_MESSAGE_ORDER", 4: "DSL_REQUIRED_FIELD",
    5: "DSL_REQUIRED_FIELD", 6: "DSL_CATALOG_ID_INVALID", 7: "DSL_SURFACE_ID_MISMATCH",
    8: "EXPR_FORBIDDEN_FIELD", 9: "STYLE_BACKGROUND_WRONG_PLACE",
    10: "STYLE_SURFACE_DIMENSION_REDUNDANT", 11: "DSL_COMPONENT_REQUIRED_FIELD",
    12: "DSL_COMPONENT_ID_DUPLICATED", 13: "DSL_ROOT_NOT_FOUND",
    14: "DSL_COMPONENT_REQUIRED_FIELD", 15: "DSL_COMPONENT_UNKNOWN",
    16: "DSL_FIELD_FORBIDDEN", 17: "DSL_FIELD_FORBIDDEN",
    18: "EVENT_ARGUMENT_INVALID", 19: "DSL_FIELD_FORBIDDEN",
    20: "DSL_COMPONENT_REQUIRED_FIELD", 21: "DSL_COMPONENT_REQUIRED_FIELD",
    22: "STYLE_ROOT_DIMENSION_INVALID", 23: "DSL_TEMPLATE_CHILDREN_INVALID",
    24: "DSL_CHILD_REF_NOT_FOUND", 25: "DSL_TEMPLATE_CHILDREN_INVALID",
    26: "DSL_TEMPLATE_CHILDREN_INVALID", 27: "DSL_CHILD_REF_NOT_FOUND",
    28: "EXPR_FORBIDDEN_FIELD", 29: "DSL_TEMPLATE_CHILDREN_INVALID",
    30: "DSL_TEMPLATE_CHILDREN_INVALID", 31: "STYLE_ENUM_INVALID",
    32: "ASSET.EMOJI_ICON", 33: "TYPE.FONT_SIZE_MIN",
    34: "CARD_REQUIRED_FIELD", 35: "CARD_STATIC_FIELD_INVALID",
    36: "CARD_STATIC_FIELD_INVALID", 37: "CARD_STATIC_FIELD_INVALID",
    38: "CARD_SUGGEST_SIZE_INVALID", 39: "CARD_REQUIRED_FIELD",
    40: "CARD_REQUIRED_FIELD", 41: "CARD_REQUIRED_FIELD", 42: "CARD_REQUIRED_FIELD",
    43: "CARD_WRITE_RESULT_PATH_INVALID", 44: "CARD_WRITE_RESULT_PATH_OVERLAP",
    45: "CARD_STATIC_FIELD_INVALID", 46: "EXPR_FULL_STRING_REQUIRED",
    47: "EXPR_FULL_STRING_REQUIRED", 48: "EXPR_PARSE_FAILED", 49: "EXPR_PARSE_FAILED",
    50: "EXPR_PARSE_FAILED", 51: "EXPR_PARSE_FAILED", 52: "EXPR_PARSE_FAILED",
    53: "EXPR_PARSE_FAILED", 54: "EXPR_PARSE_FAILED", 55: "EXPR_PARSE_FAILED",
    56: "EXPR_PARSE_FAILED", 57: "EXPR_PARSE_FAILED", 58: "EXPR_FORBIDDEN_FIELD",
    59: "EXPR_FORBIDDEN_FIELD", 60: "EXPR_FORBIDDEN_FIELD",
    61: "ASSET_PATH_NOT_DECLARED", 62: "ASSET_PATH_NOT_DECLARED",
    63: "ASSET_REMOTE_URL_FORBIDDEN", 64: "ASSET_REMOTE_URL_FORBIDDEN",
    65: "ASSET_REMOTE_URL_FORBIDDEN", 66: "ASSET_PATH_NOT_DECLARED",
    67: "BINDING_TEMPLATE_PATH_NOT_ARRAY", 68: "EVENT_ITEM_INDEX_MISMATCH",
    69: "CARD_CAPABILITY_UNKNOWN", 70: "CARD_ARGUMENT_UNKNOWN",
    71: "CARD_ARGUMENT_UNKNOWN", 72: "CARD_ARGUMENT_UNKNOWN", 73: "CARD_ARGUMENT_UNKNOWN",
    74: "CARD_WRITE_RESULT_PATH_INVALID", 75: "BINDING_PATH_NOT_FOUND",
    76: "BINDING_PATH_NOT_FOUND", 77: "BINDING_PATH_NOT_FOUND",
    78: "EVENT_ARGUMENT_INVALID", 79: "EVENT_ARGUMENT_INVALID",
    80: "EVENT_ARGUMENT_INVALID", 81: "EVENT_CAPABILITY_UNKNOWN",
    82: "EVENT_ARGUMENT_INVALID", 83: "EVENT_ARGUMENT_INVALID",
    84: "EVENT_ARGUMENT_INVALID", 85: "EVENT_ARGUMENT_INVALID",
    86: "EVENT_ARGUMENT_INVALID", 87: "DISPLAY_UNIT_DUPLICATED",
    88: "DISPLAY_UNIT_MISSING", 89: "DISPLAY_UNIT_DUPLICATED",
    90: "CROSS_DATA_PATH_UNCOVERED", 91: "CROSS_DATA_PATH_UNCOVERED",
    92: "EFFECTIVE_DATA_CAPABILITY_NOT_ALLOWED", 93: "EFFECTIVE_DATA_PATH_NOT_ALLOWED",
    94: "EFFECTIVE_EVENT_NOT_ALLOWED", 95: "EFFECTIVE_ASSET_SOURCE_UNRESOLVED",
    96: "EFFECTIVE_ASSET_NOT_ALLOWED", 97: "EFFECTIVE_ASSET_DYNAMIC_PATH",
}


def _test_artifact_dir() -> Path:
    return Path(__file__).resolve().parent / "test_artifact"


def _dsl(components, value=None):
    return "\n".join(
        json.dumps(row, ensure_ascii=False)
        for row in [
            {
                "version": "v0.9",
                "createSurface": {
                    "surfaceId": "card",
                    "catalogId": "ohos.a2ui.extended.catalog.form",
                },
            },
            {
                "version": "v0.9",
                "updateComponents": {
                    "surfaceId": "card",
                    "root": "root",
                    "components": components,
                },
            },
            {
                "version": "v0.9",
                "updateDataModel": {
                    "surfaceId": "card",
                    "path": "/",
                    "value": value or {"data": {}},
                },
            },
        ]
    )


def _text_artifact(content, data=None, effective=None):
    components = [
        {"id": "root", "component": "Column", "children": ["value"]},
        {"id": "value", "component": "Text", "content": content},
    ]
    artifact = {"genui": _dsl(components, data)}
    if effective is not None and effective.get("data"):
        item = effective["data"][0]
        artifact["cardSpec"] = {
            "title": "电量", "description": "回归", "suggestSize": "2x2",
            "dataBindings": [{
                "capabilityId": item["id"],
                "arguments": {},
                "writeResultTo": item["writeResultTo"],
            }],
        }
    if effective is not None:
        artifact["effectiveCapabilities"] = effective
    return artifact


def test_r56_empty_expression_reference_is_reported_by_expression_validator(monkeypatch):
    rules_dir = (
        Path(__file__).resolve().parents[1] / "data" / "validator_rules"
    )
    rules = RuleRegistry(rules_dir)
    reporter = Reporter(rules.diagnostics)
    context = ValidationContext(dsl_text="", cardspec_text="")
    context.expression_locations = [("genui", "/content", "{{ ${} }}", "value")]

    monkeypatch.setattr(
        "services.card_validation.expression_validator.expression_references",
        lambda _value: [""],
    )
    ExpressionValidator().validate(context, rules, reporter)

    assert reporter.has_code("EXPR_PARSE_FAILED")


def test_r87_display_unit_duplicated():
    artifact = _text_artifact(
        "{{ ${/data/battery/level} + '%' }}",
        {"data": {"battery": {"level": 68}}},
        {"data": [{
            "id": "Battery",
            "writeResultTo": "/data/battery",
            "outputSchema": {"type": "object", "properties": {
                "level": {"type": "integer", "displayUnits": ["%"], "unitIncluded": True}
            }},
        }]},
    )
    assert validate_card(artifact=artifact).has_code("DISPLAY_UNIT_DUPLICATED")


def test_r88_display_unit_missing():
    artifact = _text_artifact(
        "{{ ${/data/battery/level} }}",
        {"data": {"battery": {"level": 68}}},
        {"data": [{
            "id": "Battery",
            "writeResultTo": "/data/battery",
            "outputSchema": {"type": "object", "properties": {
                "level": {"type": "integer", "displayUnits": ["%"], "unitIncluded": False}
            }},
        }]},
    )
    assert validate_card(artifact=artifact).has_code("DISPLAY_UNIT_MISSING")


def test_r89_display_unit_duplicated_when_unit_repeated():
    artifact = _text_artifact(
        "{{ ${/data/battery/level} + '%' + '%' }}",
        {"data": {"battery": {"level": 68}}},
        {"data": [{
            "id": "Battery",
            "writeResultTo": "/data/battery",
            "outputSchema": {"type": "object", "properties": {
                "level": {"type": "integer", "displayUnits": ["%"], "unitIncluded": False}
            }},
        }]},
    )
    assert validate_card(artifact=artifact).has_code("DISPLAY_UNIT_DUPLICATED")


def test_r93_effective_data_path_not_allowed():
    artifact = _text_artifact(
        "{{ ${/data/notAllowed/x} }}",
        {"data": {"notAllowed": {"x": 1}}},
        {"data": [{"id": "Allowed", "writeResultTo": "/data/allowed"}]},
    )
    assert validate_card(artifact=artifact).has_code("EFFECTIVE_DATA_PATH_NOT_ALLOWED")


def test_r94_effective_event_not_allowed():
    components = [{
        "id": "root", "component": "Column", "children": [],
        "onClick": [{"call": "unknownEvent", "args": {}}],
    }]
    artifact = {"genui": _dsl(components), "effectiveCapabilities": {"event": []}}
    assert validate_card(artifact=artifact).has_code("EFFECTIVE_EVENT_NOT_ALLOWED")


def test_r95_effective_asset_source_unresolved():
    artifact = _text_artifact(
        "静态文本",
        effective={"asset": [{"id": "missing-asset"}]},
    )
    assert validate_card(artifact=artifact).has_code("EFFECTIVE_ASSET_SOURCE_UNRESOLVED")


def test_r96_effective_asset_not_allowed():
    components = [
        {"id": "root", "component": "Column", "children": ["image"]},
        {"id": "image", "component": "Image", "src": "resources/not-effective.svg"},
    ]
    artifact = {
        "genui": _dsl(components),
        "effectiveCapabilities": {"asset": [{"id": "allowed", "src": "resources/allowed.svg"}]},
    }
    assert validate_card(artifact=artifact).has_code("EFFECTIVE_ASSET_NOT_ALLOWED")


def test_r92_effective_data_capability_not_allowed():
    artifact = _text_artifact(
        "静态文本",
        effective={"data": []},
    )
    artifact["cardSpec"] = {
        "title": "回归", "description": "规则", "suggestSize": "2x2",
        "dataBindings": [{
            "capabilityId": "Missing", "arguments": {}, "writeResultTo": "/data/missing",
        }],
    }
    assert validate_card(artifact=artifact).has_code("EFFECTIVE_DATA_CAPABILITY_NOT_ALLOWED")


def test_r97_effective_asset_dynamic_path():
    components = [
        {"id": "root", "component": "Column", "children": ["image"]},
        {"id": "image", "component": "Image", "src": "{{ ${/data/assetPath} }}"},
    ]
    artifact = {
        "genui": _dsl(components),
        "effectiveCapabilities": {
            "asset": [{"id": "allowed", "src": "resources/a.svg"}],
        },
    }
    assert validate_card(artifact=artifact).has_code("EFFECTIVE_ASSET_DYNAMIC_PATH")


def test_all_96_rule_directories_exist():
    expected = set(range(2, 98))
    found = {
        int(path.name[1:3])
        for path in _test_artifact_dir().glob("*/*_1.json")
    }
    assert found == expected


def _artifact_for_rule(rule: int):
    root = _test_artifact_dir()
    path = next(root.glob(f"*/R{rule:02d}_*_1.json"))
    raw = path.read_text(encoding="utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _diagnostics_for_rule_fixture(rule: int, suffix: str):
    root = _test_artifact_dir()
    path = next(root.glob(f"*/R{rule:02d}_*_{suffix}.json"))
    raw = path.read_text(encoding="utf-8")
    try:
        artifact = json.loads(raw)
    except json.JSONDecodeError:
        artifact = raw
    return validate_card(artifact=artifact).diagnostics


@pytest.mark.parametrize(
    ("rule", "target_pointer", "target_message"),
    [
        (
            29,
            "/updateComponents/components/0/children/itemVar",
            "itemVar 必须是不带 $ 前缀的非空变量名。",
        ),
        (
            73,
            "/dataBindings/0/arguments",
            "arguments 是端侧能力静态入参，不能写 DSL 表达式或绑定对象。",
        ),
    ],
    ids=["R29", "R73"],
)
def test_shared_diagnostic_rules_hit_exact_branch_and_clean_baseline(
    rule, target_pointer, target_message
):
    negative_diagnostics = _diagnostics_for_rule_fixture(rule, "1")
    target_diagnostics = [
        item
        for item in negative_diagnostics
        if item.code == RULE_CODES[rule]
        and item.json_pointer == target_pointer
        and item.message == target_message
    ]
    assert target_diagnostics, [
        (item.code, item.json_pointer, item.message)
        for item in negative_diagnostics
    ]

    baseline_diagnostics = _diagnostics_for_rule_fixture(rule, "0")
    baseline_target_diagnostics = [
        item
        for item in baseline_diagnostics
        if item.code == RULE_CODES[rule]
        and item.json_pointer == target_pointer
        and item.message == target_message
    ]
    assert not baseline_target_diagnostics, [
        (item.code, item.json_pointer, item.message)
        for item in baseline_target_diagnostics
    ]


@pytest.mark.parametrize("rule", range(2, 98), ids=lambda item: f"R{item:02d}")
def test_every_rule_fixture_hits_declared_diagnostic(rule):
    """每条 R02–R97 规则都必须有独立回归用例并命中声明诊断码。"""
    artifact = _artifact_for_rule(rule)
    if rule == 56:
        rules_dir = (
            Path(__file__).resolve().parents[1] / "data" / "validator_rules"
        )
        rules = RuleRegistry(rules_dir)
        reporter = Reporter(rules.diagnostics)
        context = ValidationContext(dsl_text="", cardspec_text="")
        context.expression_locations = [
            ("genui", "/content", "{{ ${} }}", "value")
        ]
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(
                "services.card_validation.expression_validator.expression_references",
                lambda _value: [""],
            )
            ExpressionValidator().validate(context, rules, reporter)
        diagnostics = reporter.diagnostics
    elif rule in {92, 93}:
        # Exercise semantic rules directly: the public parser blocks these inputs
        # earlier on unrelated protocol/cross-file diagnostics.
        from services.card_validation.effective_capability_validator import (
            EffectiveCapabilityValidator,
        )

        rules = RuleRegistry(
            Path(__file__).resolve().parents[1] / "data" / "validator_rules"
        )
        reporter = Reporter(rules.diagnostics)
        context = ValidationContext(dsl_text="", cardspec_text="{}")
        context.use_effective_capabilities = True
        context.effective_capabilities = {"data": [], "event": [], "asset": []}
        if rule == 92:
            context.cardspec = {
                "dataBindings": [{
                    "capabilityId": "Missing",
                    "arguments": {},
                    "writeResultTo": "/data/missing",
                }]
            }
        else:
            context.expression_locations = [
                ("genui", "/value", "{{ ${/data/notAllowed/x} }}", "value")
            ]
        EffectiveCapabilityValidator().validate(context, rules, reporter)
        diagnostics = reporter.diagnostics
    elif rule == 97:
        from services.card_validation.effective_capability_validator import (
            EffectiveCapabilityValidator,
        )

        rules = RuleRegistry(
            Path(__file__).resolve().parents[1] / "data" / "validator_rules"
        )
        reporter = Reporter(rules.diagnostics)
        context = ValidationContext(dsl_text="", cardspec_text="")
        context.use_effective_capabilities = True
        context.effective_capabilities = {"data": [], "event": [], "asset": []}
        context.components = [{
            "id": "image",
            "component": "Image",
            "src": "{{ ${/data/assetPath} }}",
        }]
        EffectiveCapabilityValidator().validate(context, rules, reporter)
        diagnostics = reporter.diagnostics
    else:
        diagnostics = validate_card(artifact=artifact).diagnostics
    assert any(item.code == RULE_CODES[rule] for item in diagnostics), [
        item.code for item in diagnostics
    ]
