import json
from typing import Any

from services.card_validation import validate_card


def _dsl(components: list[dict[str, Any]], size: str = "2x2") -> str:
    messages = [
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
            "updateDataModel": {"surfaceId": "card", "path": "/", "value": {}},
        },
    ]
    return "\n".join(json.dumps(message, ensure_ascii=False) for message in messages)


def test_layout_distribution_reports_large_vertical_gap() -> None:
    components = [
        {
            "id": "root",
            "component": "Column",
            "children": ["title", "button"],
            "styles": {"width": "matchParent", "height": "matchParent", "padding": 12},
        },
        {
            "id": "title",
            "component": "Text",
            "content": "标题",
            "styles": {"width": 100, "height": 18},
        },
        {
            "id": "button",
            "component": "Button",
            "content": "打开",
            "styles": {"width": 100, "height": 32},
        },
    ]

    reporter = validate_card(dsl_text=_dsl(components))

    issues = [
        item for item in reporter.diagnostics if item.code == "QUALITY.LAYOUT_UNBALANCED"
    ]
    assert len(issues) == 1
    assert issues[0].severity == "warning"
    assert issues[0].actual["remaining"] > 24


def test_layout_distribution_accepts_space_between() -> None:
    components = [
        {
            "id": "root",
            "component": "Column",
            "children": ["title", "button"],
            "styles": {
                "width": "matchParent",
                "height": "matchParent",
                "padding": 12,
                "justifyContent": "spaceBetween",
            },
        },
        {
            "id": "title",
            "component": "Text",
            "content": "标题",
            "styles": {"width": 100, "height": 18},
        },
        {
            "id": "button",
            "component": "Button",
            "content": "打开",
            "styles": {"width": 100, "height": 32},
        },
    ]

    reporter = validate_card(dsl_text=_dsl(components))

    assert not any(
        item.code == "QUALITY.LAYOUT_UNBALANCED" for item in reporter.diagnostics
    )


def test_layout_distribution_skips_marked_template() -> None:
    components = [
        {
            "id": "root",
            "component": "Column",
            "children": ["template_root"],
            "styles": {"width": "matchParent", "height": "matchParent"},
        },
        {
            "id": "template_root",
            "component": "Column",
            "children": ["title", "button"],
            "styles": {"width": "matchParent", "height": "matchParent"},
        },
        {
            "id": "title",
            "component": "Text",
            "content": "标题",
            "styles": {"width": 100, "height": 18},
        },
        {
            "id": "button",
            "component": "Button",
            "content": "打开",
            "styles": {"width": 100, "height": 32},
        },
    ]

    reporter = validate_card(dsl_text=_dsl(components))

    assert not any(item.code.startswith("QUALITY.LAYOUT_") for item in reporter.diagnostics)


def test_layout_distribution_reports_redundant_same_axis_container() -> None:
    components = [
        {
            "id": "root",
            "component": "Column",
            "children": ["section"],
            "styles": {"width": "matchParent", "height": "matchParent"},
        },
        {
            "id": "section",
            "component": "Column",
            "children": ["label"],
            "styles": {"width": "matchParent", "height": 32},
        },
        {
            "id": "label",
            "component": "Text",
            "content": "内容",
            "styles": {"width": 80, "height": 18},
        },
    ]

    reporter = validate_card(dsl_text=_dsl(components))

    assert any(
        item.code == "QUALITY.LAYOUT_REDUNDANT_CONTAINER" for item in reporter.diagnostics
    )
