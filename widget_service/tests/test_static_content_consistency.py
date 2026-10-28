"""静态展示一致性：词元、布局、标题可见性、遗漏对账和角色。"""

import copy
import json

import pytest

from services.card_validation import validate_compact_dsl
from services.card_validation.compact_validation.semantic.static_content import (
    _fact_covered,
    _identity_covered,
    static_group_errors,
)
from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.compact_high_level_components import CompactDslConversionError
from services.compact_plan import (
    CompactPlanValidationError,
    compact_plan_omitted_facts,
    parse_compact_plan_call,
)
from services.generation_content_policy import (
    EXISTING_CONTENT_POLICY,
    STATIC_CONTENT_POLICY,
    content_policy_scope,
)
from services.static_content_context import standard_components


def fact(text, priority="must", **extras):
    return {
        "requirement": text,
        "text": text,
        "priority": priority,
        "sourceTexts": [text],
        **extras,
    }


def source(component, props, *, size="2x4", variant="flow", header=None):
    children = ["body"]
    rows = []
    if header:
        children.insert(0, "header")
        rows.append(["header", "SingleLineTitle", header])
    prefix = "S" if size == "2x2" else "W"
    rows.insert(
        0, ["root", "Layout", {"layout": prefix + "-static-content", "variant": variant}, children]
    )
    rows.extend([["body", component, props], ["/state/ready", True]])
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def accept(value, query, size="2x4"):
    raw = json.dumps({"name": "submit_card_plan", "arguments": value})
    return parse_compact_plan_call(raw, {"userQuery": query, "size": size}).plan


@pytest.fixture
def static_scope():
    with content_policy_scope(STATIC_CONTENT_POLICY):
        yield


@pytest.mark.parametrize(
    "name,visible",
    [
        ("Charlie Puth", "Charlie Puth Whatever's Clever"),
        ("Adele", "Adele · Moonlight Tour"),
        ("Alpha Beta", "Alpha Beta | Future"),
        ("Bruno Mars", "Bruno   Mars — An Evening"),
    ],
)
def test_independent_english_name_keeps_word_boundaries(name, visible):
    assert _identity_covered(name, [visible])
    assert _fact_covered(fact(name), [visible])


@pytest.mark.parametrize(
    "name,visible",
    [
        ("GPT", "ChatGPT"),
        ("Adele", "Adeles"),
        ("Charlie Puth", "Charlie PuthX"),
        ("Bruno Mars", "Mars Bruno"),
    ],
)
def test_name_does_not_borrow_partial_or_reordered_words(name, visible):
    assert not _identity_covered(name, [visible])


@pytest.mark.parametrize(
    "text,parts",
    [
        ("30GB", ["130GB"]),
        ("30GB", ["3", "0GB"]),
        ("500分钟", ["1500分钟"]),
        ("-5℃", ["5℃"]),
    ],
)
def test_boundary_fix_keeps_full_readings(text, parts):
    assert not _fact_covered(fact(text), parts)


@pytest.mark.usefixtures("static_scope")
@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("variant", ["flow", "compact"])
def test_guided_layout_matches_its_own_compiler_contract(size, variant):
    value = {
        "info_required": [fact("完整内容")],
        "contentGroups": [
            {"id": "a", "kind": "object", "identity": None, "factIndexes": [0]},
        ],
    }
    prefix = "S" if size == "2x2" else "W"
    validate_compact_dsl(
        source("ContentBlock", {"body": "完整内容"}, size=size, variant=variant),
        task_spec={"size": size, "userQuery": "完整内容", "dataModelSchema": {"data": {}}},
        card_spec={"suggestSize": size},
        compact_plan=value,
        layout_scope=prefix + "-static-content-guided",
    )


@pytest.mark.usefixtures("static_scope")
def test_long_static_header_fails_instead_of_clipping():
    dsl = source(
        "ContentBlock",
        {"body": "完整内容"},
        size="2x2",
        header={
            "title": "上海油价 2026年10月10日24时调价",
            "fontSize": 12,
        },
    )
    with pytest.raises(CompactDslConversionError, match="COMPACT_STATIC_TEXT_CAPACITY"):
        convert_compact_dsl_to_a2ui(dsl, size="2x2")


@pytest.mark.usefixtures("static_scope")
def test_static_header_line_box_and_icon_budget_are_owned():
    dsl = source("ContentBlock", {"body": "内容"}, size="2x2", header={"title": "短标题"})
    nodes = standard_components(convert_compact_dsl_to_a2ui(dsl, size="2x2"))
    title = nodes.get("header__static_title")
    assert title
    assert title.get("styles", {}).get("height") == 16
    assert title.get("styles", {}).get("fontSize") == 12
    dsl = source(
        "ContentBlock",
        {"body": "内容"},
        size="2x2",
        header={
            "title": "一二三四五六七八九十",
            "icon": "resources/test.svg",
        },
    )
    with pytest.raises(CompactDslConversionError, match="COMPACT_STATIC_TEXT_CAPACITY"):
        convert_compact_dsl_to_a2ui(dsl, size="2x2")


def test_dynamic_header_recipe_is_unchanged():
    dsl = source("ContentBlock", {"body": "内容"}, size="2x2", header={"title": "短标题"})
    with content_policy_scope(EXISTING_CONTENT_POLICY):
        with pytest.raises(CompactDslConversionError):
            convert_compact_dsl_to_a2ui(dsl, size="2x2")
    from services.compact_component_runtime import component_visual_recipe

    with content_policy_scope(EXISTING_CONTENT_POLICY):
        recipe = component_visual_recipe("SingleLineTitle", size="2x2")
    title = recipe.get("parts", {}).get("title", {}).get("styles", {})
    assert title.get("lineHeight") == 1


@pytest.mark.usefixtures("static_scope")
@pytest.mark.parametrize("restored", [True, False])
def test_referenced_omission_is_decided_by_final_visibility(restored):
    value = {
        "info_required": [fact("核心"), fact("补充", "should")],
        "contentGroups": [
            {"id": "a", "kind": "object", "identity": None, "factIndexes": [0, 1]},
        ],
        "omittedContents": [{"description": "可能省略补充", "factIndexes": [1]}],
    }
    accepted = accept(value, "核心；补充")
    dsl = source("ContentBlock", {"body": "核心；补充" if restored else "核心"})
    omitted = compact_plan_omitted_facts(dsl, accepted, {}, ())
    assert len(omitted) == (0 if restored else 1)
    assert accepted.get("omissionCandidates")
    assert accepted.get("omittedContents") == []


@pytest.mark.usefixtures("static_scope")
def test_unselected_input_loss_and_legacy_declarations_remain_conservative():
    value = {
        "info_required": [fact("核心")],
        "contentGroups": [
            {"id": "a", "kind": "object", "identity": None, "factIndexes": [0]},
        ],
        "omittedContents": [{"description": "未选择的独立内容", "factIndexes": []}, "旧版自由说明"],
    }
    accepted = accept(value, "核心；未选择的独立内容")
    omitted = compact_plan_omitted_facts(source("ContentBlock", {"body": "核心"}), accepted, {}, ())
    assert len(omitted) == 2


@pytest.mark.usefixtures("static_scope")
@pytest.mark.parametrize("indexes", [[True], [-1], [2], [0]])
def test_omission_references_downgrade_core_or_invalid_indexes(indexes):
    value = {
        "info_required": [fact("核心"), fact("补充", "should")],
        "contentGroups": [
            {"id": "a", "kind": "object", "identity": None, "factIndexes": [0, 1]},
        ],
        "omittedContents": [{"description": "说明", "factIndexes": indexes}],
    }
    raw = json.dumps({"name": "submit_card_plan", "arguments": value})
    result = parse_compact_plan_call(raw, {"userQuery": "核心；补充", "size": "2x4"})
    assert result.plan.get("omittedContents") == ["说明"]
    assert not result.plan.get("omissionCandidates")
    assert any("已撤销删除授权" in warning for warning in result.warnings)


@pytest.mark.usefixtures("static_scope")
@pytest.mark.parametrize("indexes", [[1, 1], "1"])
def test_omission_reference_shape_errors_remain_blocking(indexes):
    value = {
        "info_required": [fact("核心"), fact("补充", "should")],
        "contentGroups": [
            {"id": "a", "kind": "object", "identity": None, "factIndexes": [0, 1]},
        ],
        "omittedContents": [{"description": "说明", "factIndexes": indexes}],
    }
    with pytest.raises(CompactPlanValidationError):
        accept(value, "核心；补充")


@pytest.mark.usefixtures("static_scope")
def test_protected_should_omission_is_downgraded():
    value = {
        "info_required": [fact("核心"), fact("原文补充", "should", protectedTexts=["原文补充"])],
        "contentGroups": [
            {"id": "a", "kind": "object", "identity": None, "factIndexes": [0, 1]},
        ],
        "omittedContents": [{"description": "不删除原文补充", "factIndexes": [1]}],
    }
    raw = json.dumps({"name": "submit_card_plan", "arguments": value})
    result = parse_compact_plan_call(raw, {"userQuery": "核心；原文补充", "size": "2x4"})
    assert result.plan.get("omittedContents") == ["不删除原文补充"]
    assert not result.plan.get("omissionCandidates")
    assert any("受保护事实" in warning for warning in result.warnings)


@pytest.mark.usefixtures("static_scope")
def test_omission_indexes_follow_deduplication():
    value = {
        "info_required": [fact("核心"), fact("核心"), fact("补充", "should")],
        "contentGroups": [
            {"id": "a", "kind": "object", "identity": None, "factIndexes": [0, 1, 2]},
        ],
        "omittedContents": [{"description": "补充", "factIndexes": [2]}],
    }
    before = copy.deepcopy(value)
    accepted = accept(value, "核心；补充")
    candidates = accepted.get("omissionCandidates")
    assert candidates and candidates[0].get("factIndexes") == [1]
    assert value == before


@pytest.mark.usefixtures("static_scope")
@pytest.mark.parametrize("role,expected", [("body", None), ("value", "end")])
def test_attribute_alignment_follows_declared_role(role, expected):
    dsl = source(
        "ContentBlock",
        {
            "attributes": [
                {"label": "字段", "value": "内容", "valueRole": role},
            ]
        },
    )
    nodes = standard_components(convert_compact_dsl_to_a2ui(dsl, size="2x4"))
    node = nodes.get("body__static_attr0_value")
    assert node and node.get("styles", {}).get("textAlign") == expected


@pytest.mark.usefixtures("static_scope")
def test_attribute_role_metadata_is_not_visible_text():
    value = {
        "info_required": [fact("body")],
        "contentGroups": [
            {"id": "a", "kind": "object", "identity": None, "factIndexes": [0]},
        ],
    }
    dsl = source("ContentBlock", {"attributes": [{"value": "别的文字", "valueRole": "body"}]})
    assert static_group_errors(dsl, value)


@pytest.mark.usefixtures("static_scope")
def test_long_shared_header_can_use_complete_body_context_without_clipping():
    header = "上海油价 2026年10月10日24时调价"
    value = {
        "info_required": [
            fact(header, displayRole="title"),
            fact("92号汽油7.32元/升"),
            fact("95号汽油7.80元/升"),
            fact("0号柴油6.95元/升"),
        ],
        "contentGroups": [
            {"id": "h", "kind": "shared", "identity": None, "factIndexes": [0]},
            {"id": "a", "kind": "object", "identity": None, "factIndexes": [1]},
            {"id": "b", "kind": "object", "identity": None, "factIndexes": [2]},
            {"id": "c", "kind": "object", "identity": None, "factIndexes": [3]},
        ],
    }
    plan = accept(
        value, "；".join(item.get("text", "") for item in value.get("info_required", [])), "2x2"
    )
    dsl = plan.get("staticPresentation")
    assert dsl and header in dsl
    assert not static_group_errors(dsl, plan)
    convert_compact_dsl_to_a2ui(dsl, size="2x2")


def test_line_break_keeps_closing_punctuation_off_new_lines():
    from services.static_text_capacity import measure_text, text_spec

    text = "甲乙丙丁，戊己庚辛；壬癸（说明）"
    capacity = measure_text(text, 50.4, text_spec("attributeBody"))
    assert "".join(capacity.wrapped_lines) == text
    for line in capacity.wrapped_lines:
        assert not line.startswith(("，", "；", "）"))
        assert not line.endswith("（")


@pytest.mark.usefixtures("static_scope")
def test_exact_duplicate_name_is_relocated_not_deleted_by_candidate():
    value = {
        "info_required": [fact("主体", displayRole="label"), fact("完整说明")],
        "contentGroups": [
            {"id": "a", "kind": "object", "identity": "主体", "factIndexes": [0, 1]},
        ],
    }
    accepted = accept(value, "主体完整说明")
    dsl = accepted.get("staticPresentation")
    assert dsl and dsl.count("主体") == 1
    assert not static_group_errors(dsl, accepted)


@pytest.mark.usefixtures("static_scope")
def test_new_submissions_require_omission_references_but_legacy_parse_remains_supported():
    value = {
        "info_required": [fact("核心")],
        "contentGroups": [
            {"id": "a", "kind": "object", "identity": None, "factIndexes": [0]},
        ],
        "omittedContents": ["自由说明"],
    }
    raw = json.dumps({"name": "submit_card_plan", "arguments": value})
    with pytest.raises(CompactPlanValidationError, match="新静态遗漏声明"):
        parse_compact_plan_call(
            raw, {"userQuery": "核心", "size": "2x4"}, require_static_omission_refs=True
        )
    assert parse_compact_plan_call(raw, {"userQuery": "核心", "size": "2x4"}).plan


@pytest.mark.usefixtures("static_scope")
@pytest.mark.parametrize("font", [11, 10])
def test_static_header_cannot_be_shrunk_to_fit(font):
    dsl = source("ContentBlock", {"body": "内容"}, header={"title": "短标题", "fontSize": font})
    with pytest.raises(CompactDslConversionError, match="固定12字号"):
        convert_compact_dsl_to_a2ui(dsl, size="2x4")


@pytest.mark.usefixtures("static_scope")
def test_omission_reference_cannot_hide_a_core_fact_after_deduplication():
    value = {
        "info_required": [fact("相同文字"), fact("相同文字", "should")],
        "contentGroups": [
            {"id": "a", "kind": "object", "identity": None, "factIndexes": [0, 1]},
        ],
        "omittedContents": [{"description": "补充", "factIndexes": [1]}],
    }
    raw = json.dumps({"name": "submit_card_plan", "arguments": value})
    result = parse_compact_plan_call(raw, {"userQuery": "相同文字", "size": "2x4"})
    assert result.plan.get("omittedContents") == ["补充"]
    assert not result.plan.get("omissionCandidates")
    assert any("去重后指向 must" in warning for warning in result.warnings)


@pytest.mark.usefixtures("static_scope")
@pytest.mark.parametrize("value_role", [None, "unknown", {}])
def test_attribute_role_rejects_unregistered_values(value_role):
    dsl = source(
        "ContentBlock",
        {
            "attributes": [
                {"label": "字段", "value": "内容", "valueRole": value_role},
            ]
        },
    )
    with pytest.raises(CompactDslConversionError, match="valueRole只允许"):
        convert_compact_dsl_to_a2ui(dsl, size="2x4")
