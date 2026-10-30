"""静态受控外观、辅助文本空值矩阵及覆盖/容量回归。"""

import json

import pytest

from models.artifact import ArtifactMeta, WidgetArtifact
from services.card_validation import validate_compact_dsl
from services.card_validation.compact_validation.semantic.static_content import (
    static_display_groups,
    static_fact_coverage,
    static_group_errors,
)
from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.compact_region_layout import reference_region_boxes
from services.generation_content_policy import STATIC_CONTENT_POLICY, content_policy_scope
from services.post_layout_theme import apply_theme
from services.post_layout_theme_registry import fallback_theme
from services.protocol_registry import A2UIProtocolRegistry
from services.static_content_context import final_static_display_errors, standard_components
from services.theme_style_roles import layout_phase
from services.validator import ArtifactValidator


def source_for(kind, props, size="2x2"):
    prefix = "S" if size == "2x2" else "W"
    rows = [
        ["root", "Layout", {"layout": prefix + "-static-content"}, ["header", "body"]],
        ["header", "SingleLineTitle", {"title": "共同主题"}],
        ["body", kind, props],
    ]
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def convert(kind, props, size="2x2"):
    source = source_for(kind, props, size)
    with content_policy_scope(STATIC_CONTENT_POLICY):
        objects, shared = static_display_groups(source)
        facts = []
        groups = []
        for group_kind, displays in (("object", objects), ("shared", shared)):
            for display in displays:
                indexes = []
                for part in display.parts:
                    indexes.append(len(facts))
                    facts.append({"text": part, "priority": "must", "sourceTexts": ["测试原文"]})
                groups.append({"id": str(len(groups)), "kind": group_kind, "identity": None,
                               "factIndexes": indexes})
        validate_compact_dsl(
            source, card_spec={"suggestSize": size},
            task_spec={"size": size, "dataModelSchema": {"data": {}},
                       "eventCandidates": [], "assetCandidates": []},
            compact_plan={"info_required": facts, "contentGroups": groups},
        )
        with layout_phase(True):
            standard = convert_compact_dsl_to_a2ui(source, size=size)
        profile = A2UIProtocolRegistry().get_profile()
        artifact = WidgetArtifact(
            genui=standard, taskSpec={"size": size},
            cardSpec={"suggestSize": size, "title": "组件验证", "description": "验证固定组件"},
            effectiveCapabilities={"data": [], "event": [], "asset": []},
            meta=ArtifactMeta(protocolProfileId=profile.get("id"), createdAt=0,
                              capabilityRegistryVersion="offline-test"),
        )
        assert ArtifactValidator({}).validate_layout(artifact, profile) == []
        return standard_components(standard)


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("secondary,bottom", [
    ("紧随说明", None), (None, "底部说明"), ("紧随说明", ""), ("", "底部说明"),
    ("紧随说明", "  "), ("  ", "底部说明"), (None, None), ("", ""),
    ("紧随说明", "底部说明"),
])
def test_single_nonempty_support_is_always_at_bottom(size, secondary, bottom):
    nodes = convert("EmphasisText", {
        "mainText": "主要结论", "secondaryText": secondary, "bottomText": bottom,
    }, size)
    body = nodes.get("body")
    top = nodes.get("body__static_top")
    assert body and top
    supports = []
    for key, value in (("secondaryText", secondary), ("bottomText", bottom)):
        if isinstance(value, str) and value.strip():
            supports.append(key)
    assert top.get("children", [])[0] == "body__static_mainText"
    if len(supports) == 2:
        assert top.get("children") == ["body__static_mainText", "body__static_secondaryText"]
        assert body.get("children") == ["body__static_top", "body__static_bottomText"]
    elif supports:
        assert top.get("children") == ["body__static_mainText"]
        assert body.get("children") == ["body__static_top", "body__static_" + supports[0]]
    else:
        assert top.get("children") == ["body__static_mainText"]
        assert body.get("children") == ["body__static_top"]
    if supports:
        assert top.get("styles", {}).get("layoutWeight") == 1
        assert top.get("styles", {}).get("padding") == {"bottom": 6}
    title = nodes.get("header__static_title")
    assert title and title.get("styles", {}).get("fontWeight") == 400
    for node in nodes.values():
        assert node.get("component") != "SecondaryBody"
        if node.get("component") == "Column":
            assert node.get("children")


@pytest.mark.parametrize("value", [False, 12, [], {}])
def test_optional_support_rejects_non_text_values(value):
    with pytest.raises(ValueError):
        convert("EmphasisText", {"mainText": "结论", "bottomText": value})


def test_two_support_blocks_must_fit_total_height_without_shrinking():
    with pytest.raises(ValueError, match="可用104vp"):
        convert("EmphasisText", {
            "mainText": "主要结论需要换行展示",
            "secondaryText": "这是一段辅助文字" * 5,
            "bottomText": "另一段底部辅助文字" * 5,
        })


@pytest.mark.parametrize("size,expected_width", [("2x2", 126), ("2x4", 284)])
@pytest.mark.parametrize("count", [1, 2, 3, 4])
def test_single_line_panel_contract_and_dense_fallback(size, expected_width, count):
    nodes = convert("SingleLineList", {
        "items": [{"text": "标签", "assist": "20元"} for _ in range(count)],
    }, size)
    boxes = reference_region_boxes(list(nodes.values()), size=size)
    body = nodes.get("body")
    assert body
    for index in range(count):
        row_id = f"body__static_item{index}"
        row = nodes.get(row_id)
        assert row
        styles = row.get("styles", {})
        value = nodes.get(f"body__static_item{index}_assist")
        assert value
        if count <= 3:
            box = boxes.get(row_id)
            assert box and box.width == expected_width
            assert styles.get("height") == 32
            assert styles.get("padding") == {"left": 12, "right": 12}
            assert styles.get("borderRadius") == 8
            assert styles.get("backgroundColor")
            assert value.get("styles", {}).get("fontWeight") == 700
        else:
            assert styles.get("height") == 16
            assert "backgroundColor" not in styles
            assert value.get("styles", {}).get("fontWeight") == 500
    if count == 3:
        assert body.get("styles", {}).get("justifyContent") in {"space-between", "spaceBetween"}
        assert body.get("styles", {}).get("constraintSize") == {"minHeight": 104}
    elif count < 3:
        wrapper = nodes.get("__layout__root__static_body")
        assert wrapper and wrapper.get("styles", {}).get("justifyContent") == "end"


def test_numbered_list_keeps_model_facts_separate_from_generated_badges():
    props = {"items": [{"primaryText": "公园", "secondaryText": "免费"},
                       {"primaryText": "展馆", "secondaryText": "20元"}]}
    nodes = convert("TextList", props)
    source = source_for("TextList", props)
    with content_policy_scope(STATIC_CONTENT_POLICY):
        groups, _shared = static_display_groups(source)
    assert len(groups) == 2
    assert groups[0].parts == ["公园", "免费"]
    for index in range(2):
        badge = nodes.get(f"body__static_item{index}_badge")
        assert badge and badge.get("content") == str(index + 1)
        assert badge.get("styles", {}).get("height") == 16
        assert badge.get("styles", {}).get("fontSize") == 10


def test_bottom_text_is_covered_and_missing_bottom_text_is_reported():
    source = source_for("EmphasisText", {"mainText": "结论", "bottomText": "必要条件"})
    plan = {"info_required": [{"text": "结论", "priority": "must"},
                               {"text": "必要条件", "priority": "must"}],
            "contentGroups": [{"id": "one", "kind": "object", "identity": None,
                               "factIndexes": [0, 1]}]}
    with content_policy_scope(STATIC_CONTENT_POLICY):
        assert not static_group_errors(source, plan)
        assert all(item.visible for item in static_fact_coverage(source, plan))
        missing = source_for("EmphasisText", {"mainText": "结论"})
        assert static_group_errors(missing, plan)


@pytest.mark.parametrize("family", ["blue", "purple", "warm"])
def test_runtime_decorations_and_support_positions_survive_theme(family):
    for kind, props in (
        ("TextList", {"items": [{"primaryText": "公园", "secondaryText": "免费"},
                                {"primaryText": "展馆", "secondaryText": "20元"}]}),
        ("SingleLineList", {"items": [{"text": "开放", "assist": "09:00"}]}),
        ("EmphasisText", {"mainText": "结论", "secondaryText": "说明", "bottomText": "条件"}),
    ):
        with content_policy_scope(STATIC_CONTENT_POLICY), layout_phase(True):
            standard = convert_compact_dsl_to_a2ui(source_for(kind, props), size="2x2")
        themed = apply_theme(
            standard, fallback_theme(family), {"size": "2x2"}, {"suggestSize": "2x2"},
        )
        assert not final_static_display_errors(standard, themed)
