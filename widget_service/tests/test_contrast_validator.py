import json
from typing import Any

import pytest

from services.card_validation import validate_card


def _dsl(text_color: str, background_color: str) -> str:
    rows = [
        {"version": "v0.9", "createSurface": {"surfaceId": "card"}},
        {
            "version": "v0.9",
            "updateComponents": {
                "root": "root",
                "components": [
                    {
                        "id": "root",
                        "component": "Column",
                        "children": ["label"],
                        "styles": {"backgroundColor": background_color},
                    },
                    {
                        "id": "label",
                        "component": "Text",
                        "content": "Readable label",
                        "styles": {"fontColor": text_color},
                    },
                ],
            },
        },
        {"version": "v0.9", "updateDataModel": {"path": "/", "value": {}}},
    ]
    return "\n".join(json.dumps(row) for row in rows)


def test_contrast_validator_reports_low_contrast_text() -> None:
    reporter = validate_card(dsl_text=_dsl("#FF777777", "#FFFFFFFF"))

    contrast = [item for item in reporter.diagnostics if item.code == "VISUAL.CONTRAST"]
    assert len(contrast) == 1
    assert contrast[0].severity == "warning"
    assert contrast[0].actual < 4.5


def test_contrast_validator_accepts_high_contrast_text() -> None:
    reporter = validate_card(dsl_text=_dsl("#FF000000", "#FFFFFFFF"))

    assert not any(item.code == "VISUAL.CONTRAST" for item in reporter.diagnostics)


def _component_dsl(components: list[dict[str, Any]]) -> str:
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
    return "\n".join(json.dumps(message) for message in messages)


def test_gradient_does_not_retain_uncovered_default_background() -> None:
    components = [
        {
            "id": "root",
            "component": "Column",
            "children": ["label"],
            "styles": {
                "width": "matchParent",
                "height": "matchParent",
                "linearGradient": {
                    "angle": 180,
                    "colors": [
                        ["#FF1D3A6A", 0],
                        ["#FF1D588F", 0.45],
                        ["#FF0D8FBC", 1],
                    ],
                },
            },
        },
        {
            "id": "label",
            "component": "Text",
            "content": "北京出行",
            "styles": {"fontColor": "#FFFFFFFF"},
        },
    ]

    reporter = validate_card(dsl_text=_component_dsl(components))

    assert not reporter.has_code("VISUAL.CONTRAST")


def test_gradient_still_reports_when_multiple_samples_have_low_contrast() -> None:
    components = [
        {
            "id": "root",
            "component": "Column",
            "children": ["label"],
            "styles": {
                "width": "matchParent",
                "height": "matchParent",
                "linearGradient": {
                    "angle": 180,
                    "colors": [
                        ["#FFFFFFFF", 0],
                        ["#FFF4F4F4", 0.5],
                        ["#FFE8E8E8", 1],
                    ],
                },
            },
        },
        {
            "id": "label",
            "component": "Text",
            "content": "低对比文字",
            "styles": {"fontColor": "#FFFFFFFF"},
        },
    ]

    reporter = validate_card(dsl_text=_component_dsl(components))

    contrast = [
        item for item in reporter.diagnostics if item.code == "VISUAL.CONTRAST"
    ]
    assert len(contrast) == 1
    assert contrast[0].severity == "error"
    assert contrast[0].actual < 3


@pytest.mark.parametrize(
    "content",
    [
        {"path": "/data/label"},
        "{{ ${/data/label} }}",
    ],
)
def test_dynamic_text_also_participates_in_contrast_validation(content: Any) -> None:
    components = [
        {
            "id": "root",
            "component": "Column",
            "children": ["label"],
            "styles": {
                "width": "matchParent",
                "height": "matchParent",
                "backgroundColor": "#FFFFFFFF",
            },
        },
        {
            "id": "label",
            "component": "Text",
            "content": content,
            "styles": {"fontColor": "#FFFFFFFF"},
        },
    ]

    reporter = validate_card(dsl_text=_component_dsl(components))

    assert reporter.has_code("VISUAL.CONTRAST")
