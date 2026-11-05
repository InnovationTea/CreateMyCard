"""背景删除的纯包装祖先清理及完整编辑产物回归。"""

import copy
import json

import pytest

from core.errors import GenerationStatus
from services.card_validation.edit_validation.artifact import validate_edit_artifact
from services.single_step_edit import source_digest
from services.widget_edit_contract import apply_edit_output, dump_rows
from services.widget_generation_service import WidgetGenerationService
from test_semantic_widget_edit import _intent, _nodes, _request, _rows
from test_semantic_widget_edit import edit_run as edit_run
from test_semantic_widget_edit import source as source


def _background(source, kind="Stack"):
    rows = _rows(source)
    nodes = _nodes(rows)
    nodes[0]["component"] = "Stack"
    nodes[0]["children"] = ["outer", "title", "value"]
    nodes.extend([
        {"id": "outer", "component": kind, "children": ["inner"],
         "styles": {"width": "matchParent", "height": "matchParent"}},
        {"id": "inner", "component": kind, "children": ["photo"],
         "styles": {"width": "matchParent", "height": "matchParent"}},
        {"id": "photo", "component": "Image", "src": "photo.jpg",
         "styles": {"width": "matchParent", "height": "matchParent"}},
    ])
    return rows


def _plan(**changes):
    values = {"mode": "layout", "dimensions": ["palette", "layout"],
              "targets": ["root"], "backgroundTargets": ["photo"]}
    values.update(changes)
    return _intent(**values)


def _output(original, removed):
    rows = _rows(original)
    nodes = _nodes(rows)
    nodes[:] = [node for node in nodes if node.get("id") not in removed]
    for node in nodes:
        children = node.get("children")
        if isinstance(children, list):
            node["children"] = [child for child in children if child not in removed]
    return json.dumps({"sourceDigest": source_digest(original), "genui": rows})


@pytest.mark.parametrize("kind", ["Stack", "Row", "Column"])
@pytest.mark.parametrize("recover", [False, True])
def test_nested_background_cleanup_passes_full_artifact(edit_run, kind, recover):
    original = edit_run.source
    original.genui = dump_rows(_background(original.genui, kind))
    candidate = original.model_copy(deep=True)
    candidate.genui = apply_edit_output(
        original.genui, _output(original.genui, {"photo", "inner", "outer"}),
        _plan(), recover=recover,
    )
    result = validate_edit_artifact(original, candidate, _plan())
    assert result.errors == []
    assert result.unmet == []
    assert _nodes(_rows(candidate.genui))[1:] == _nodes(_rows(original.genui))[1:3]


@pytest.mark.parametrize("blocker", [
    "protected", "scope", "expectation", "action", "dynamic", "decoration", "business",
])
def test_cleanup_respects_original_container_semantics(source, blocker):
    rows = _background(source)
    nodes = _nodes(rows)
    outer = nodes[3]
    plan = _plan()
    if blocker == "protected":
        plan.protectedTargets = ["outer"]
    elif blocker == "scope":
        plan.targets = ["inner"]
        plan.linkedTargets = ["root"]
    elif blocker == "expectation":
        plan = _plan(expectations=[{
            "componentId": "outer", "property": "styles.width", "operator": "preserve",
        }])
    elif blocker == "action":
        outer["onClick"] = [{"call": "test"}]
    elif blocker == "dynamic":
        outer["styles"] = {"padding": "{{ ${/value} }}"}
    elif blocker == "decoration":
        outer["styles"] = {"backgroundColor": "#FFFFFFFF"}
    else:
        outer["children"] = ["inner", "title"]
        nodes[0]["children"] = ["outer", "value"]
    original = dump_rows(rows)
    payload = json.loads(_output(original, {"photo", "inner", "outer"}))
    candidate_rows = payload.get("genui")
    assert isinstance(candidate_rows, list)
    if blocker == "business":
        _nodes(candidate_rows)[0]["children"] = ["title", "value"]
    with pytest.raises(ValueError):
        apply_edit_output(original, json.dumps(payload), plan)


def test_partial_background_removal_keeps_nonempty_wrapper(source):
    rows = _background(source)
    nodes = _nodes(rows)
    second = copy.deepcopy(nodes[-1])
    second["id"] = "second"
    nodes.append(second)
    nodes[4]["children"] = ["photo", "second"]
    original = dump_rows(rows)
    result = apply_edit_output(original, _output(original, {"photo"}), _plan())
    assert _nodes(_rows(result))[4].get("children") == ["second"]
    with pytest.raises(ValueError):
        apply_edit_output(original, _output(original, {"photo", "inner", "outer"}), _plan())


@pytest.mark.asyncio
async def test_empty_wrapper_feedback_repaired_through_service(edit_run):
    original = dump_rows(_background(edit_run.source.genui))
    edit_run.source.genui = original
    edit_run.intent = _plan()
    edit_run.outputs = [
        _output(original, {"photo"}),
        _output(original, {"photo", "inner", "outer"}),
    ]
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert response.status == GenerationStatus.SUCCESS
    assert len(edit_run.saved) == 1
    calls = [messages for phase, messages in edit_run.calls if phase == "edit_execute"]
    assert len(calls) == 2
    assert "componentId=inner property=children" in str(calls[1])
    assert "可清理该容器" in str(calls[1])


def test_preexisting_empty_wrapper_is_not_background_cleanup(source):
    rows = _background(source)
    _nodes(rows)[4]["children"] = []
    _nodes(rows)[0]["children"] = ["outer", "photo", "title", "value"]
    original = dump_rows(rows)
    with pytest.raises(ValueError):
        apply_edit_output(original, _output(original, {"photo", "inner", "outer"}), _plan())


def test_all_authorized_background_branches_can_be_cleaned(source):
    rows = _background(source)
    nodes = _nodes(rows)
    second = copy.deepcopy(nodes[-1])
    second["id"] = "second"
    nodes.append(second)
    nodes[3]["children"] = ["inner", "second"]
    original = dump_rows(rows)
    plan = _plan(backgroundTargets=["photo", "second"])
    result = apply_edit_output(
        original, _output(original, {"photo", "second", "inner", "outer"}), plan,
    )
    assert _nodes(_rows(result))[0].get("children") == ["title", "value"]


def test_reparenting_background_does_not_authorize_wrapper_deletion(source):
    original = dump_rows(_background(source))
    payload = json.loads(_output(original, {"inner", "outer"}))
    rows = payload.get("genui")
    assert isinstance(rows, list)
    _nodes(rows)[0]["children"] = ["photo", "title", "value"]
    with pytest.raises(ValueError, match="不得删除"):
        apply_edit_output(original, json.dumps(payload), _plan())
