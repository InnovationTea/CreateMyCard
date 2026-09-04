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


def _template_components(
    wrapper_ids: tuple[str, ...] = ("template_root",),
    text_color: str = "#FFFFFFFF",
) -> list[dict[str, Any]]:
    components: list[dict[str, Any]] = [{
        "id": "root",
        "component": "Column",
        "children": [wrapper_ids[0]],
        "styles": {
            "width": "matchParent",
            "height": "matchParent",
            "backgroundColor": "#FFFFFFFF",
            "padding": 12,
            "borderRadius": 18,
            "clip": True,
        },
    }]
    for index, wrapper_id in enumerate(wrapper_ids):
        child_id = wrapper_ids[index + 1] if index + 1 < len(wrapper_ids) else "label"
        components.append({
            "id": wrapper_id,
            "component": "Column",
            "children": [child_id],
        })
    components.append({
        "id": "label",
        "component": "Text",
        "content": "模板内容",
        "styles": {"fontColor": text_color},
    })
    return components


@pytest.mark.parametrize("text_color", ["#FFFFFFFF", "#FF777777"])
@pytest.mark.parametrize("wrapper_ids", [
    ("template_root",),
    ("template_root", "__genui_render_component__template_root", "root_1"),
])
def test_template_subtree_skips_contrast_errors_and_warnings(
    wrapper_ids: tuple[str, ...], text_color: str,
) -> None:
    reporter = validate_card(dsl_text=_component_dsl(_template_components(wrapper_ids, text_color)))

    assert not reporter.has_code("VISUAL.CONTRAST")


def test_template_root_text_itself_skips_contrast() -> None:
    components = _template_components()
    components[1] = {
        "id": "template_root", "component": "Text", "content": "模板根文本",
        "styles": {"fontColor": "#FFFFFFFF"},
    }
    reporter = validate_card(dsl_text=_component_dsl(components[:2]))

    assert not reporter.has_code("VISUAL.CONTRAST")


@pytest.mark.parametrize("template_first", [True, False])
def test_template_subtree_does_not_skip_non_template_siblings(template_first: bool) -> None:
    components = _template_components()
    children = ["template_root", "external"]
    components[0]["children"] = children if template_first else list(reversed(children))
    components.append({
        "id": "external", "component": "Text", "content": "非模板内容",
        "styles": {"fontColor": "#FFFFFFFF"},
    })
    reporter = validate_card(dsl_text=_component_dsl(components))

    contrast = [item for item in reporter.diagnostics if item.code == "VISUAL.CONTRAST"]
    assert len(contrast) == 1
    assert contrast[0].severity == "error"
    assert "/external/" in contrast[0].json_pointer


@pytest.mark.parametrize("wrapper_id", [
    "template_root_0", "other_template_root", "Template_root",
    "__genui_render_component__template_root", "regular",
])
def test_contrast_exemption_requires_exact_template_root_id(wrapper_id: str) -> None:
    components = _template_components((wrapper_id,))
    reporter = validate_card(dsl_text=_component_dsl(components))

    contrast = [item for item in reporter.diagnostics if item.code == "VISUAL.CONTRAST"]
    assert len(contrast) == 1
    assert contrast[0].severity == "error"


def test_unreachable_template_marker_does_not_skip_normal_card() -> None:
    components = _template_components(("regular",))
    components.append({"id": "template_root", "component": "Text", "content": "未引用"})
    reporter = validate_card(dsl_text=_component_dsl(components))

    assert reporter.has_code("VISUAL.CONTRAST")


@pytest.mark.parametrize(("field", "value", "expected_code"), [
    ("component", "UnsupportedTemplateComponent", "DSL_COMPONENT_UNKNOWN"),
    ("content", "{{ ${/data/missing} }}", "BINDING_PATH_NOT_FOUND"),
    ("content", "{{ }}", "EXPR_PARSE_FAILED"),
    ("onClick", [{"call": "unknownTemplateAction", "args": {}}], "EVENT_CAPABILITY_UNKNOWN"),
    ("undeclaredField", True, "DSL_FIELD_FORBIDDEN"),
])
def test_template_subtree_retains_other_validation(
    field: str, value: Any, expected_code: str,
) -> None:
    components = _template_components()
    components[-1][field] = value
    reporter = validate_card(dsl_text=_component_dsl(components))

    assert reporter.has_code(expected_code)
    assert not reporter.has_code("VISUAL.CONTRAST")
