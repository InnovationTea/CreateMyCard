"""实际修改交付、最佳候选与受控恢复回归。"""

import json

import pytest

from core.errors import GenerationStatus
from custom.a2ui_model_client import A2UIModelClient, A2UIModelGenerationError
from services.single_step_edit import source_digest
from services.widget_edit_contract import apply_edit_output
from services.widget_generation_service import WidgetGenerationService
from test_semantic_widget_edit import _intent, _nodes, _patch, _request, _rows
from test_semantic_widget_edit import edit_run as edit_run
from test_semantic_widget_edit import source as source


def _goal():
    return {"componentId": "title", "property": "styles.fontSize",
            "operator": "equal", "value": 20}


@pytest.mark.asyncio
@pytest.mark.parametrize("partial", [True, False])
async def test_partial_delivery_requires_permission_and_real_change(edit_run, source, partial):
    edit_run.intent = _intent(expectations=[_goal()], allowPartial=partial)
    edit_run.outputs = [json.dumps(_patch(source, value=18))]
    result = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    expected = GenerationStatus.DEGRADED if partial else GenerationStatus.FAILED
    assert result.status == expected
    assert len(edit_run.saved) == int(partial)
    if partial:
        assert result.artifactUrl
        assert result.editFeedback
        assert edit_run.saved[0].genui != source
        assert "title" not in result.editFeedback
        assert "字号" in result.editFeedback
        assert len(edit_run.calls) == 3


@pytest.mark.asyncio
async def test_best_candidate_survives_later_invalid_result(edit_run, source):
    edit_run.intent = _intent(expectations=[_goal()])
    edit_run.outputs = [json.dumps(_patch(source, value=18)),
                        json.dumps(_patch(source, value=16)), "invalid"]
    result = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert result.status == GenerationStatus.DEGRADED
    assert _nodes(_rows(edit_run.saved[0].genui))[1].get("styles", {}).get("fontSize") == 18


@pytest.mark.asyncio
async def test_noop_never_becomes_partial_delivery(edit_run, source):
    edit_run.intent = _intent(expectations=[_goal()])
    edit_run.outputs = [json.dumps(_patch(source, value=14))]
    result = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert result.status == GenerationStatus.FAILED
    assert not edit_run.saved


@pytest.mark.asyncio
async def test_best_candidate_survives_model_failure(edit_run, source, monkeypatch):
    edit_run.intent = _intent(expectations=[_goal()])
    calls = []

    async def generate(_client, _messages, _profile=None, **kwargs):
        if kwargs.get("phase") == "edit_intent":
            return edit_run.intent.model_dump_json()
        calls.append(True)
        if len(calls) > 1:
            raise A2UIModelGenerationError("模拟后续模型失败")
        return json.dumps(_patch(source, value=18))

    monkeypatch.setattr(A2UIModelClient, "generate", generate)
    result = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert result.status == GenerationStatus.DEGRADED
    assert len(edit_run.saved) == 1


@pytest.mark.asyncio
async def test_preserve_remains_hard_constraint(edit_run, source):
    goal = {"componentId": "title", "property": "styles.fontSize", "operator": "preserve"}
    edit_run.intent = _intent(expectations=[goal])
    edit_run.outputs = [json.dumps(_patch(source))]
    result = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert result.status == GenerationStatus.FAILED
    assert not edit_run.saved


def test_recovery_restores_protected_style_and_missing_title(source):
    rows = _rows(source)
    nodes = _nodes(rows)
    nodes[0]["children"] = ["value"]
    nodes[1].get("styles", {})["fontSize"] = 18
    nodes[2].get("styles", {})["fontSize"] = 30
    intent = _intent(mode="layout", targets=["root"], dimensions=["layout", "typography"],
                     protectedTargets=["value"])
    output = json.dumps({"sourceDigest": source_digest(source), "genui": rows})
    final = apply_edit_output(source, output, intent, recover=True)
    restored = _nodes(_rows(final))
    assert restored[0].get("children") == ["title", "value"]
    assert restored[1].get("styles", {}).get("fontSize") == 18
    assert restored[2].get("styles", {}).get("fontSize") == 24


@pytest.mark.parametrize("mutation", ["cycle", "business", "digest"])
def test_recovery_does_not_bypass_hard_guards(source, mutation):
    rows = _rows(source)
    nodes = _nodes(rows)
    digest = source_digest(source)
    if mutation == "cycle":
        nodes[0]["children"] = ["root"]
    elif mutation == "business":
        nodes[1]["content"] = "替换业务内容"
    else:
        digest = "wrong"
    intent = _intent(mode="layout", targets=["root"], dimensions=["layout", "typography"])
    output = json.dumps({"sourceDigest": digest, "genui": rows})
    with pytest.raises(ValueError):
        apply_edit_output(source, output, intent, recover=True)


@pytest.mark.asyncio
async def test_better_completion_replaces_previous_candidate(edit_run, source):
    edit_run.intent = _intent(dimensions=["typography", "palette"], expectations=[
        _goal(), {"componentId": "title", "property": "styles.fontColor",
                  "operator": "equal", "value": "#FF000000"},
    ])
    edit_run.outputs = [json.dumps(_patch(source, value=18)),
                        json.dumps(_patch(source, value=20)), "invalid"]
    result = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert result.status == GenerationStatus.DEGRADED
    assert _nodes(_rows(edit_run.saved[0].genui))[1].get("styles", {}).get("fontSize") == 20
    assert "文字颜色" in result.editFeedback


@pytest.mark.asyncio
async def test_recovered_layout_passes_full_delivery_validation(edit_run, source):
    rows = _rows(source)
    nodes = _nodes(rows)
    nodes[0]["children"] = ["value"]
    nodes[1].get("styles", {})["fontSize"] = 18
    nodes[2].get("styles", {})["fontSize"] = 30
    edit_run.intent = _intent(mode="layout", targets=["root"],
                              dimensions=["layout", "typography"], protectedTargets=["value"])
    edit_run.outputs = [json.dumps({"sourceDigest": source_digest(source), "genui": rows})]
    result = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert result.status == GenerationStatus.SUCCESS
    assert len(edit_run.saved) == 1
    assert _nodes(_rows(edit_run.saved[0].genui))[0].get("children") == ["title", "value"]


@pytest.mark.parametrize("dynamic", [False, True])
def test_omitted_protected_styles_restore_only_static_values(source, dynamic):
    from services.widget_edit_contract import dump_rows

    original_rows = _rows(source)
    if dynamic:
        _nodes(original_rows)[2].get("styles", {})["fontSize"] = "{{ ${/font} }}"
    original = dump_rows(original_rows)
    rows = _rows(original)
    nodes = _nodes(rows)
    nodes[1].get("styles", {})["fontSize"] = 18
    nodes[2].pop("styles")
    intent = _intent(mode="layout", targets=["root"], dimensions=["layout", "typography"],
                     protectedTargets=["value"])
    output = json.dumps({"sourceDigest": source_digest(original), "genui": rows})
    if dynamic:
        with pytest.raises(ValueError):
            apply_edit_output(original, output, intent, recover=True)
    else:
        final = apply_edit_output(original, output, intent, recover=True)
        assert _nodes(_rows(final))[2].get("styles") == _nodes(original_rows)[2].get("styles")


def test_authorized_background_removal_is_not_undone_by_recovery(source):
    from services.widget_edit_contract import dump_rows, validate_intent

    original_rows = _rows(source)
    _nodes(original_rows)[0].get("styles", {})["backgroundImage"] = "original-background"
    original = dump_rows(original_rows)
    rows = _rows(original)
    _nodes(rows)[0].get("styles", {}).pop("backgroundImage")
    intent = _intent(mode="layout", targets=["root"], dimensions=["layout", "palette"],
                     backgroundTargets=["root"])
    validate_intent(intent, original, "2x4", None)
    output = json.dumps({"sourceDigest": source_digest(original), "genui": rows})
    final = apply_edit_output(original, output, intent, recover=True)
    assert "backgroundImage" not in _nodes(_rows(final))[0].get("styles", {})


@pytest.mark.asyncio
async def test_partial_feedback_reaches_agent_and_device_success(edit_run, source):
    from api.routes import _build_plugin_stream_response, _generation_result_directive
    from models.service import WidgetWebSocketResultMessage

    edit_run.intent = _intent(expectations=[_goal()])
    edit_run.outputs = [json.dumps(_patch(source, value=18))]
    result = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    data = result.model_dump(mode="json", exclude_none=True)
    assert data.get("status") == "degraded"
    assert data.get("editFeedback")
    assert "message" not in data
    message = WidgetWebSocketResultMessage(
        tool="generateWidgetCardCompactDsl", operation="generateWidgetCardCompactDsl",
        requestId="partial-delivery", data=data, status="degraded",
    )
    envelope = _build_plugin_stream_response(message)
    payload = json.loads(envelope.reply.streamInfo.streamContent)
    delivered = payload.get("data")
    assert isinstance(delivered, dict)
    assert delivered.get("editFeedback") == result.editFeedback
    state, url = _generation_result_directive(data)
    assert state.name == "SUCCESS"
    assert url == result.artifactUrl
