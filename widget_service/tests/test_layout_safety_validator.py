from types import SimpleNamespace

from cloud.services.card_validation.diagnostics import Reporter
from cloud.services.card_validation.quality.layout_safety_validator import (
    LayoutSafetyValidator,
)


def _validate(children: list[dict]) -> Reporter:
    root = {
        "id": "root",
        "component": "Stack",
        "children": [child["id"] for child in children],
        "styles": {"alignContent": "center"},
    }
    components = [root, *children]
    context = SimpleNamespace(
        root_id="root",
        components=components,
        components_by_id={component["id"]: component for component in components},
    )
    reporter = Reporter()
    LayoutSafetyValidator().validate(context, None, reporter)
    return reporter


def _text(component_id: str, visibility: str | None = None) -> dict:
    styles = {"width": 100, "height": 30}
    if visibility is not None:
        styles["visibility"] = visibility
    return {"id": component_id, "component": "Text", "content": "label", "styles": styles}


def test_stack_allows_provably_mutually_exclusive_visibility_branches() -> None:
    condition = "{{ ${/connected} ? 'visible' : 'none' }}"
    inverse = "{{ ${/connected} ? 'none' : 'visible' }}"

    reporter = _validate([_text("connected", condition), _text("disconnected", inverse)])

    assert not reporter.has_code("LAYOUT.STACK_CONTENT_FLOW")


def test_stack_checks_checkbox_labels_for_overlapping_text_content() -> None:
    checkbox_a = {
        "id": "first",
        "component": "Checkbox",
        "label": "第一项",
        "styles": {"width": 100, "height": 30},
    }
    checkbox_b = {
        "id": "second",
        "component": "Checkbox",
        "label": "第二项",
        "styles": {"width": 100, "height": 30},
    }

    reporter = _validate([checkbox_a, checkbox_b])

    assert reporter.has_code("LAYOUT.STACK_CONTENT_FLOW")
