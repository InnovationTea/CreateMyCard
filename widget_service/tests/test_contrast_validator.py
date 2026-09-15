import json
from typing import Any

import pytest

from services.card_validation import validate_card
from services.card_validation.context import ValidationContext
from services.card_validation.contrast_validator import ContrastValidator
from services.card_validation.diagnostics import Reporter
from services.card_validation.source_parser import SourceParser


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


def test_fusion_ball_scene_defers_contrast_to_render_review() -> None:
    components = [
        {
            "id": "root",
            "component": "Stack",
            "children": ["fusionBallBackground", "content"],
            "styles": {"backgroundColor": "#00000000"},
        },
        {
            "id": "fusionBallBackground",
            "component": "Stack",
            "children": ["ball"],
        },
        {
            "id": "ball",
            "component": "Divider",
            "styles": {"backgroundColor": "#FF172F73"},
        },
        {
            "id": "content",
            "component": "Column",
            "children": ["label"],
        },
        {
            "id": "label",
            "component": "Text",
            "content": "融合背景文字",
            "styles": {"fontColor": "#FFFFFFFF"},
        },
    ]

    reporter = validate_card(dsl_text=_component_dsl(components))

    contrast = [item for item in reporter.diagnostics if item.code == "VISUAL.CONTRAST"]
    assert len(contrast) == 1
    assert contrast[0].severity == "warning"
    assert contrast[0].actual == {"scene": "fusionBall", "requiresRenderReview": True}


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
def test_template_root_skips_whole_card_contrast(template_first: bool) -> None:
    components = _template_components()
    children = ["template_root", "external"]
    components[0]["children"] = children if template_first else list(reversed(children))
    components.append({
        "id": "external", "component": "Text", "content": "非模板内容",
        "styles": {"fontColor": "#FFFFFFFF"},
    })
    reporter = validate_card(dsl_text=_component_dsl(components))

    assert not reporter.has_code("VISUAL.CONTRAST")


@pytest.mark.parametrize("fusion", [False, True])
def test_direct_contrast_validator_uses_template_marker_without_fusion_dependency(
    fusion: bool, caplog,
) -> None:
    components = _template_components()
    if fusion:
        children = components[0].get("children")
        assert isinstance(children, list)
        children.append("fusionBallBackground")
        components.append({"id": "fusionBallBackground", "component": "Stack"})
    reporter = Reporter({})
    context = SourceParser().parse(_component_dsl(components), "", reporter)
    with caplog.at_level("INFO"):
        ContrastValidator().validate(context, {}, reporter)
    assert not reporter.has_code("VISUAL.CONTRAST")
    assert "quality_validation_skipped reason=template_root validator=contrast" in caplog.text


@pytest.mark.parametrize(
    ("root_id", "children", "template_exists", "duplicate_ids", "expected"),
    [
        ("root", ["template_root"], True, set(), True),
        ("root", ["template_root", "fusionBallBackground"], True, set(), True),
        ("root", ["fusionBallBackground"], True, set(), False),
        ("root", ["template_root"], False, set(), False),
        ("root", ["content"], True, set(), False),
        ("root", "template_root", True, set(), False),
        ("root", ["template_root_0"], True, set(), False),
        ("other_root", ["template_root"], True, set(), False),
        ("root", ["template_root"], True, {"template_root"}, False),
    ],
)
def test_template_root_exemption_keeps_structural_guards(
    root_id: str, children: Any, template_exists: bool,
    duplicate_ids: set[str], expected: bool,
) -> None:
    root = {"id": root_id, "component": "Stack", "children": children}
    components = {root_id: root}
    if template_exists:
        components["template_root"] = {"id": "template_root", "component": "Column"}
    context = ValidationContext(
        root_id=root_id, root_component=root, components_by_id=components,
        duplicate_component_ids=duplicate_ids,
    )
    assert context.has_fusion_template_root() is expected


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
    assert contrast[0].severity == "warning"
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
