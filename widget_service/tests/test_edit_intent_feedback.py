"""编辑意图路径反馈、修复消费及背景图改色回归。"""

import json

import pytest

from core.errors import GenerationStatus
from custom.a2ui_model_client import A2UIModelClient
from services.single_step_edit import source_digest
from services.widget_edit_contract import (
    EditExpectation,
    apply_edit_output,
    dump_rows,
    validate_intent,
)
from services.widget_generation_service import WidgetGenerationService
from test_semantic_widget_edit import _intent, _nodes, _patch, _request, _rows
from test_semantic_widget_edit import edit_run as edit_run
from test_semantic_widget_edit import source as source


@pytest.mark.parametrize("prop", ["backgroundColor", "linearGradient", "fontColor"])
def test_bare_style_feedback_has_location_and_exact_path(source, prop):
    intent = _intent(dimensions=["palette"], expectations=[{
        "componentId": "title", "property": prop, "operator": "equal", "value": "#FFFFFFFF",
    }])
    with pytest.raises(ValueError) as caught:
        validate_intent(intent, source, "2x4", None)
    message = str(caught.value)
    assert "expectations[0] componentId=title" in message
    assert f"改为 styles.{prop}" in message
    assert intent.expectations[0].property == prop


def test_feedback_collects_all_targets_without_changing_contract(source):
    intent = _intent(dimensions=["palette"], targets=["root"], expectations=[
        {"componentId": "root", "property": "backgroundColor",
         "operator": "equal", "value": "#FF001F3F"},
        {"componentId": "root", "property": "linearGradient", "operator": "remove"},
        {"componentId": "title", "property": "fontColor",
         "operator": "equal", "value": "#FFFFFFFF"},
    ])
    with pytest.raises(ValueError) as caught:
        validate_intent(intent, source, "2x4", None)
    for index in range(3):
        assert f"expectations[{index}]" in str(caught.value)


@pytest.mark.parametrize("prop", ["backgroundImage", "styles.backgroundImage"])
def test_image_removal_feedback_does_not_invent_style(source, prop):
    rows = _rows(source)
    nodes = _nodes(rows)
    nodes[0]["children"] = ["photo", "title", "value"]
    nodes.append({"id": "photo", "component": "Image", "src": "photo.jpg",
                  "styles": {"width": "matchParent", "height": "matchParent"}})
    intent = _intent(dimensions=["palette"], targets=["root"], expectations=[{
        "componentId": "photo", "property": prop, "operator": "remove",
    }])
    with pytest.raises(ValueError) as caught:
        validate_intent(intent, dump_rows(rows), "2x4", None)
    assert "backgroundTargets" in str(caught.value)
    assert "使用 src 的 Image" in str(caught.value)


def test_nested_style_feedback_keeps_whole_object_contract(source):
    intent = _intent(dimensions=["spacing"], expectations=[{
        "componentId": "title", "property": "styles.padding.top", "operator": "equal",
        "value": 4,
    }])
    with pytest.raises(ValueError, match="使用 styles.padding 整个属性"):
        validate_intent(intent, source, "2x4", None)


def test_missing_remove_feedback_identifies_original_path(source):
    intent = _intent(dimensions=["palette"], targets=["root"], expectations=[{
        "componentId": "root", "property": "styles.linearGradient", "operator": "remove",
    }])
    with pytest.raises(ValueError) as caught:
        validate_intent(intent, source, "2x4", None)
    assert "property=styles.linearGradient" in str(caught.value)
    assert "原属性不存在" in str(caught.value)


def test_authorized_photo_removal_preserves_business_and_data(source):
    rows = _rows(source)
    nodes = _nodes(rows)
    nodes[0]["component"] = "Stack"
    nodes[0]["children"] = ["photo", "title", "value"]
    nodes.append({"id": "photo", "component": "Image", "src": "photo.jpg",
                  "styles": {"width": "matchParent", "height": "matchParent"}})
    original = dump_rows(rows)
    intent = _intent(mode="layout", dimensions=["palette", "layout"], targets=["root"],
                     backgroundTargets=["photo"], expectations=[{
                         "componentId": "root", "property": "styles.backgroundColor",
                         "operator": "equal", "value": "#FF001F3F",
                     }])
    validate_intent(intent, original, "2x4", None)
    nodes.pop()
    nodes[0]["children"] = ["title", "value"]
    styles = nodes[0].get("styles")
    assert isinstance(styles, dict)
    styles["backgroundColor"] = "#FF001F3F"
    output = json.dumps({"sourceDigest": source_digest(original), "genui": rows})
    result = _rows(apply_edit_output(original, output, intent))
    assert result[2] == rows[2]
    assert _nodes(result)[1:] == nodes[1:]
    intent.backgroundTargets = []
    with pytest.raises(ValueError):
        apply_edit_output(original, output, intent)


@pytest.mark.asyncio
async def test_model_receives_actionable_path_feedback_and_recovers(edit_run, monkeypatch):
    generate = A2UIModelClient.generate
    attempts = []
    edit_run.intent.expectations = [EditExpectation(
        componentId="title", property="styles.fontSize", operator="equal", value=18,
    )]

    async def respond(client, messages, *args, **kwargs):
        if kwargs.get("phase") == "edit_intent":
            attempts.append(messages)
            if len(attempts) == 1:
                broken = edit_run.intent.model_copy(deep=True)
                broken.expectations = [EditExpectation(
                    componentId="title", property="fontSize", operator="equal", value=18,
                )]
                return broken.model_dump_json()
            feedback = json.loads(messages[-1].get("content", "{}"))
            assert "styles.fontSize" in str(feedback.get("errors"))
            assert "expectations[0]" in str(feedback.get("errors"))
        return await generate(client, messages, *args, **kwargs)

    monkeypatch.setattr(A2UIModelClient, "generate", respond)
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert response.status == GenerationStatus.SUCCESS
    assert len(attempts) == 2
    assert len(edit_run.saved) == 1


@pytest.mark.parametrize("failure", ["path", "before", "value"])
def test_patch_feedback_locates_failures_without_changing_source(source, failure):
    payload = _patch(source)
    changes = payload.get("changes")
    assert isinstance(changes, list)
    change = changes[0]
    if failure == "path":
        change["property"] = "fontSize"
    elif failure == "before":
        change["before"] = {"exists": True, "value": 999}
    else:
        change["value"] = "large"
    with pytest.raises(ValueError) as caught:
        apply_edit_output(source, json.dumps(payload), _intent())
    message = str(caught.value)
    assert "componentId=title" in message
    assert "property=" in message
    if failure == "before":
        assert "previousGenui" in message
    if failure == "path":
        assert "改为 styles.fontSize" in message
    valid = apply_edit_output(source, json.dumps(_patch(source)), _intent())
    assert valid != source


def test_combined_object_patch_preserves_unmodified_values(source):
    rows = _rows(source)
    root = _nodes(rows)[0]
    styles = root.get("styles")
    assert isinstance(styles, dict)
    styles["padding"] = {"top": 4, "right": 8, "bottom": 4, "left": 8}
    original = dump_rows(rows)
    intent = _intent(targets=["root"], dimensions=["spacing"])
    payload = _patch(original, "root", "padding",
                     {"top": 6, "right": 8, "bottom": 6, "left": 8})
    result = _rows(apply_edit_output(original, json.dumps(payload), intent))
    assert _nodes(result)[1:] == _nodes(rows)[1:]
    assert result[2] == rows[2]
    changes = payload.get("changes")
    assert isinstance(changes, list)
    changes.append(dict(changes[0]))
    with pytest.raises(ValueError, match=r"changes\[1\].*字段重复"):
        apply_edit_output(original, json.dumps(payload), intent)
