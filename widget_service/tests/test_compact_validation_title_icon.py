"""标题图标合入分类校验后，素材策略、占高与模型反馈保持一致。"""

import json
from typing import Any

import pytest

from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.card_validation.compact_validation.semantic.plan_contracts import (
    collect_plan_contract_errors,
)
from services.compact_dsl_a2ui_converter import ComponentRow, convert_compact_dsl_to_a2ui
from services.generation_pipeline import DesignCompactProcessor
from services.prompt_builder import PromptBuilder

SVG = "resources/weather.svg"
COLOR = "#FF112233"


def _source(props: dict[str, Any], *, panel_height: int = 40) -> str:
    rows = [
        ["root", "Column", {}, ["panel"]],
        ["panel", "Column", {"height": panel_height}, ["header"]],
        ["header", "SingleLineTitle", {"title": "天气", "fontColor": COLOR, **props}],
    ]
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def _task(size: str, icon: str = SVG, description: str = "可染色") -> dict[str, Any]:
    return {
        "size": size,
        "dataModelSchema": {"data": {}},
        "assetCandidates": [{"src": icon, "description": description}],
    }


def _validate(source: str, task: dict[str, Any]) -> None:
    result = validate_compact_dsl(
        source,
        task_spec=task,
        card_spec={"suggestSize": task.get("size")},
        enforce_model_component_types=True,
    )
    assert result.warnings == ()


def _nodes(source: str, size: str) -> dict[str, dict[str, Any]]:
    converted = convert_compact_dsl_to_a2ui(source, size=size)
    update = json.loads(converted.splitlines()[1]).get("updateComponents")
    assert isinstance(update, dict)
    components = update.get("components")
    assert isinstance(components, list)
    result = {}
    for component in components:
        identifier = component.get("id")
        assert isinstance(identifier, str)
        result[identifier] = component
    return result


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize(
    ("props", "description"),
    [
        ({"icon": SVG, "fillColor": COLOR}, "默认黑色 SVG"),
        ({"icon": SVG}, "多色，保留原色"),
        ({"icon": "resources/weather.png"}, "天气图标"),
    ],
)
def test_title_icon_validates_and_renders_with_runtime_color_policy(
    size: str, props: dict[str, Any], description: str,
) -> None:
    source = _source(props)
    icon = props.get("icon")
    assert isinstance(icon, str)
    _validate(source, _task(size, icon, description))
    nodes = _nodes(source, size)
    title = nodes.get("header")
    image = nodes.get("header_icon")
    assert isinstance(title, dict) and isinstance(image, dict)
    assert title.get("children") == ["header_title", "header_icon"]
    title_styles = title.get("styles")
    image_styles = image.get("styles")
    assert isinstance(title_styles, dict) and isinstance(image_styles, dict)
    assert title.get("component") == "Row"
    assert title_styles.get("height") == 20
    assert title_styles.get("justifyContent") == "spaceBetween"
    assert title_styles.get("alignItems") == "center"
    title_text = nodes.get("header_title")
    assert isinstance(title_text, dict)
    title_text_styles = title_text.get("styles")
    assert isinstance(title_text_styles, dict)
    assert title_text_styles.get("width") == "wrapContent"
    assert title_text_styles.get("layoutWeight") == 1
    assert image_styles.get("width") == image_styles.get("height") == 20
    assert image.get("src") == icon
    assert "onClick" not in image
    if icon.lower().endswith(".svg"):
        assert image_styles.get("fillColor") == "#FF1F4799"
    else:
        assert "fillColor" not in image_styles


@pytest.mark.parametrize(
    ("candidates", "code", "category"),
    [([], "COMPACT_ASSET_NOT_ALLOWED", "effective")],
)
def test_title_icon_failure_has_original_location_and_model_repair_text(
    candidates: list[dict[str, Any]], code: str, category: str,
) -> None:
    source = _source({"icon": SVG})
    task = _task("2x2")
    task["assetCandidates"] = candidates
    with pytest.raises(CompactDslValidationError) as captured:
        _validate(source, task)
    error = captured.value
    assert len(error.diagnostics) == 1
    diagnostic = error.diagnostics[0]
    assert diagnostic.code == code
    assert diagnostic.validation_class == "semantic"
    assert diagnostic.category == category
    assert diagnostic.component_id == "header"
    assert diagnostic.property_path == "/icon"
    assert diagnostic.source_line == 3
    assert diagnostic.fix_hint
    issues = DesignCompactProcessor._validation_failure(source, error.errors, groups=error.groups)
    prompt = PromptBuilder().build_repair(
        [{"role": "system", "content": "合同"}, {"role": "user", "content": "{}"}],
        source,
        [issue.to_prompt_payload() for issue in issues.errors],
    )
    content = prompt[1].get("content")
    assert isinstance(content, str)
    assert code in content and diagnostic.fix_hint in content
    assert "compactDiagnostics" not in content


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("with_icon", [False, True])
def test_title_height_budget_matches_rendered_recipe(size: str, with_icon: bool) -> None:
    props = {"icon": SVG} if with_icon else {}
    height = 20 if with_icon else 12
    task = _task(size, description="保留原色")
    _validate(_source(props, panel_height=height), task)
    tolerance = 2 if size == "2x2" else 0
    source = _source(props, panel_height=height - tolerance - 1)
    with pytest.raises(CompactDslValidationError) as captured:
        _validate(source, task)
    diagnostic = next(
        item for item in captured.value.diagnostics if item.code == "COMPACT_LAYOUT_HEIGHT_OVERFLOW"
    )
    assert diagnostic.component_id == "panel"
    assert diagnostic.actual.get("minimumRequiredHeight") == height
    assert diagnostic.actual.get("overflow") == tolerance + 1
    removable = diagnostic.actual.get("removableTitleIcon")
    if with_icon:
        assert removable == {"componentId": "header", "heightSaving": 8}
    else:
        assert removable is None


@pytest.mark.parametrize("fill", [None, 42, False, {}, [], "red"])
def test_invalid_explicit_title_color_remains_validation_error(fill: Any) -> None:
    with pytest.raises(CompactDslValidationError, match="fillColor must use #AARRGGBB"):
        _validate(_source({"icon": SVG, "fillColor": fill}), _task("2x2"))


@pytest.mark.parametrize(
    ("props", "message"),
    [
        ({"fillColor": COLOR}, "fillColor requires icon"),
        ({"icon": "resources/weather.png", "fillColor": COLOR}, "bitmap icon"),
        ({"icon": 42}, "static asset path"),
        ({"icon": " "}, "static asset path"),
        ({"icon": {"path": "/data/icon"}}, "static"),
    ],
)
def test_title_icon_keeps_component_contract_errors(props: dict[str, Any], message: str) -> None:
    icon = props.get("icon")
    candidate = icon if isinstance(icon, str) else SVG
    with pytest.raises(CompactDslValidationError, match=message):
        _validate(_source(props), _task("2x2", candidate))


def test_title_icon_cannot_reuse_an_info_block_visual_icon() -> None:
    components = [
        ComponentRow("title", "SingleLineTitle", {"title": "天气", "icon": SVG}, ()),
        ComponentRow(
            "weather",
            "InfoBlock",
            {"visual": {"type": "icon", "icon": SVG}},
            (),
        ),
    ]
    errors: list[str] = []

    collect_plan_contract_errors(
        components,
        {"assetCandidates": [{"src": SVG}]},
        None,
        errors,
        size="2x4",
    )

    assert errors == [
        "SingleLineTitle reuses icon 'resources/weather.svg' with card content components "
        "['weather']; keep the content icon and replace the title icon with another unused "
        "matching asset; remove it only when no alternative candidate exists."
    ]
