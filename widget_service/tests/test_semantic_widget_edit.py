"""语义编辑离线回归：自然语言、范围保护、模板隔离与首次生成边界。"""

import ast
import copy
import inspect
import json
from types import SimpleNamespace

import pytest

from api.schemas import GenerateWidgetCardRequest
from config.config import get_settings
from core.errors import ErrorCode, GenerationStatus
from custom.a2ui_model_client import A2UIModelClient
from services import widget_edit_contract, widget_edit_prompt, widget_edit_service
from services.artifact_store import ArtifactStore, ArtifactUploadError
from services.card_validation import ValidationOptions, validate_card
from services.card_validation.context import ValidationContext
from services.card_validation.edit_validation import artifact as edit_validation_module
from services.compact_dsl_interface_retry import run_compact_dsl_with_retry
from services.single_step_edit import source_digest
from services.source_artifact_repository import SourceArtifactLoadResult, SourceArtifactRepository
from services.widget_edit_contract import (
    EditIntent,
    apply_edit_output,
    dump_rows,
    validate_intent,
)
from services.widget_generation_service import WidgetGenerationService


@pytest.fixture
def source():
    rows = [
        {"version": "v0.9", "createSurface": {
            "surfaceId": "card", "catalogId": "ohos.a2ui.extended.catalog.form",
        }},
        {"version": "v0.9", "updateComponents": {
            "surfaceId": "card", "root": "root", "components": [
                {"id": "root", "component": "Column", "children": ["title", "value"],
                 "styles": {"width": "matchParent", "height": "matchParent",
                            "backgroundColor": "#FFFFFFFF", "padding": 12}},
                {"id": "title", "component": "Text", "content": "睡眠卡片",
                 "styles": {"fontSize": 14, "fontColor": "#FF111111"}},
                {"id": "value", "component": "Text", "content": "8小时",
                 "styles": {"fontSize": 24, "fontColor": "#FF111111"}},
            ],
        }},
        {"version": "v0.9", "updateDataModel": {
            "surfaceId": "card", "path": "/", "value": {"label": "睡眠卡片"},
        }},
    ]
    return dump_rows(rows)


def _intent(**changes):
    values = {
        "explanation": "只调整标题字号，保留其它内容", "targetSize": "2x4",
        "dimensions": ["typography"], "targets": ["title"],
    }
    values.update(changes)
    return EditIntent(**values)


def _rows(source):
    return [json.loads(line) for line in source.splitlines()]


def _nodes(rows):
    update = rows[1].get("updateComponents")
    assert isinstance(update, dict)
    nodes = update.get("components")
    assert isinstance(nodes, list)
    return nodes


def _patch(source, identity="title", prop="fontSize", value=18):
    node = next(item for item in _nodes(_rows(source)) if item.get("id") == identity)
    styles = node.get("styles", {})
    before = {"exists": prop in styles}
    if prop in styles:
        before["value"] = styles.get(prop)
    return {"sourceDigest": source_digest(source), "changes": [{
        "componentId": identity, "property": f"styles.{prop}", "before": before, "value": value,
    }]}


@pytest.mark.parametrize("query", [
    "把标题字体调大一点", "字号再大些，其他不要变", "标题醒目一点",
    "把整体颜色改成蒂芙尼蓝", "背景换成橙色", "把卡片调小一点",
])
def test_contract_never_matches_query_words(source, query):
    from services.widget_edit_prompt import intent_prompt

    messages = intent_prompt(source, query, "2x4", None)
    payload = json.loads(messages[1].get("content", "{}"))
    assert payload.get("editInstruction") == query
    intent = _intent()
    validate_intent(intent, source, "2x4", None)
    result = apply_edit_output(source, json.dumps(_patch(source)), intent)
    assert "18" in result


@pytest.mark.parametrize("color", ["#FF81D8D0", "#FFFFA500", "#0055AA"])
def test_palette_supports_model_resolved_named_colors(source, color):
    intent = _intent(dimensions=["palette"], targets=["root"])
    patch = _patch(source, "root", "backgroundColor", color)
    patch.get("changes").extend(_patch(source, "title", "fontColor", "#FF123333").get("changes"))
    validate_intent(intent, source, "2x4", None)
    assert color in apply_edit_output(source, json.dumps(patch), intent)


@pytest.mark.parametrize("value", ["large", True, -1, 0, float("inf"), float("nan")])
def test_bad_font_values_are_rejected(source, value):
    with pytest.raises(ValueError):
        apply_edit_output(source, json.dumps(_patch(source, value=value)), _intent())


@pytest.mark.parametrize("color", ["蒂芙尼蓝", "#GG0000", "#FFF", "#00123456", "#-00001"])
def test_output_color_still_requires_protocol_value(source, color):
    intent = _intent(dimensions=["palette"])
    with pytest.raises(ValueError):
        apply_edit_output(source, json.dumps(_patch(source, prop="fontColor", value=color)), intent)


def test_local_edit_does_not_change_unmentioned_region(source):
    with pytest.raises(ValueError, match="范围"):
        apply_edit_output(source, json.dumps(_patch(source, "value")), _intent())


def test_protected_region_is_excluded_from_global_edit(source):
    intent = _intent(targets=["root"], protectedTargets=["value"])
    with pytest.raises(ValueError, match="范围"):
        apply_edit_output(source, json.dumps(_patch(source, "value")), intent)


def test_explicit_container_link_is_allowed(source):
    intent = _intent(dimensions=["typography", "layout"], linkedTargets=["root"])
    patch = _patch(source)
    patch.get("changes").extend(_patch(source, "root", "height", "100%").get("changes"))
    assert "18" in apply_edit_output(source, json.dumps(patch), intent)


def _layout(source):
    rows = _rows(source)
    _nodes(rows)[0]["component"] = "Row"
    return {"sourceDigest": source_digest(source), "genui": rows}


@pytest.mark.parametrize("mutation", ["data", "surface", "delete", "action", "content",
                                     "hidden", "cycle", "duplicate", "new_fact"])
def test_layout_cannot_break_business_baseline(source, mutation):
    payload = _layout(source)
    rows = payload.get("genui")
    assert isinstance(rows, list)
    nodes = _nodes(rows)
    if mutation == "data":
        rows[2]["updateDataModel"]["value"] = {"invented": 1}
    elif mutation == "surface":
        rows[0]["createSurface"]["surfaceId"] = "other"
    elif mutation == "delete":
        nodes.pop()
    elif mutation == "action":
        nodes[1]["onClick"] = [{"call": "invented", "args": {}}]
    elif mutation == "content":
        nodes[1]["content"] = "改成静态假数据"
    elif mutation == "hidden":
        nodes[1].get("styles")["visibility"] = "hidden"
    elif mutation == "cycle":
        nodes[0]["children"] = ["root", "title", "value"]
    elif mutation == "duplicate":
        nodes[0]["children"] = ["title", "value", "value"]
    else:
        nodes.append({"id": "invented", "component": "Text", "content": "假数据"})
    intent = _intent(mode="layout", dimensions=["layout"], targets=["root"])
    with pytest.raises(ValueError):
        apply_edit_output(source, json.dumps(payload), intent)


def test_layout_can_reflow_without_changing_content(source):
    intent = _intent(mode="layout", dimensions=["layout"], targets=["root"], targetSize="2x2")
    validate_intent(intent, source, "2x4", "2x2")
    result = apply_edit_output(source, json.dumps(_layout(source)), intent)
    assert _nodes(_rows(result))[0].get("component") == "Row"
    assert _nodes(_rows(result))[1:] == _nodes(_rows(source))[1:]


def test_size_requires_layout_and_respects_explicit_target(source):
    with pytest.raises(ValueError, match="规格"):
        validate_intent(_intent(targetSize="2x2"), source, "2x4", None)
    with pytest.raises(ValueError, match="显式"):
        validate_intent(_intent(), source, "2x4", "2x2")


def test_stale_patch_and_empty_patch_do_not_count_as_success(source):
    patch = _patch(source)
    patch["sourceDigest"] = "stale"
    with pytest.raises(ValueError, match="摘要"):
        apply_edit_output(source, json.dumps(patch), _intent())
    patch = {"sourceDigest": source_digest(source), "changes": []}
    with pytest.raises(ValueError, match="无需修改"):
        apply_edit_output(source, json.dumps(patch), _intent())


def test_template_marker_has_no_edit_quality_exemption():
    nodes = {"root": {"children": ["template_root"]}, "template_root": {}}
    context = ValidationContext(root_id="root", components_by_id=nodes,
                                root_component=nodes.get("root"))
    assert context.has_fusion_template_root()
    context.edit_mode = True
    assert not context.has_fusion_template_root()


@pytest.fixture
def edit_run(source, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_semantic_widget_edit", True)
    monkeypatch.setattr(settings, "enable_widget_edit", True)
    monkeypatch.setattr(settings, "enable_a2ui_model_mock", False)
    monkeypatch.setattr(settings, "enable_generation_trace_recording", False)
    monkeypatch.setattr(settings, "widget_edit_max_repair_attempts", 2)
    service = WidgetGenerationService()
    artifact = service._build_artifact(
        source, {"title": "睡眠卡片", "description": "睡眠", "suggestSize": "2x4"},
        {"userQuery": "睡眠卡片", "size": "2x4", "dataModelSchema": {},
         "eventCandidates": [], "assetCandidates": []},
        [], [], [], [], "a2ui-form-rom6.0-v1", "v0.9", "app-11.7.7.300_rom-7.0",
    )
    loaded = SourceArtifactLoadResult(
        artifact=artifact, design_token=None, artifact_digest="sha256:source", url_hash="source",
        read_latency_ms=0.0, parse_latency_ms=0.0, download_mode="mock",
    )
    state = SimpleNamespace(source=artifact, saved=[], calls=[], intent=_intent(),
                            outputs=[json.dumps(_patch(source))])

    async def generate(_client, messages, _profile=None, **kwargs):
        phase = kwargs.get("phase")
        state.calls.append((phase, copy.deepcopy(messages)))
        if phase == "edit_intent":
            return state.intent.model_dump_json()
        index = sum(call_phase == "edit_execute" for call_phase, _ in state.calls) - 1
        return state.outputs[min(index, len(state.outputs) - 1)]

    async def save(_store, edited):
        state.saved.append(edited.model_copy(deep=True))
        return SimpleNamespace(artifactUrl=f"https://artifact.test/new-{len(state.saved)}.md",
                               artifactDigest="sha256:new")

    def forbidden(*_args, **_kwargs):
        pytest.fail("二次编辑不得调用首次生成、模板、JSX 或主题")

    monkeypatch.setattr(SourceArtifactRepository, "load", lambda *_args: loaded)
    monkeypatch.setattr(A2UIModelClient, "generate", generate)
    monkeypatch.setattr(ArtifactStore, "save", save)
    monkeypatch.setattr(WidgetGenerationService, "generate_widget_card", forbidden)
    monkeypatch.setattr("services.template_generation.TemplateSourceGenerator.__call__", forbidden)
    monkeypatch.setattr("services.template_generation.TemplateSourceGenerator.__init__", forbidden)
    monkeypatch.setattr("services.post_layout_theme.theme_artifact", forbidden)
    monkeypatch.setattr(WidgetGenerationService, "_enable_card_template", lambda _self: True)
    monkeypatch.setattr(WidgetGenerationService, "_enable_jsx_generation", lambda _self: True)
    return state


def _request(**kwargs):
    values = {"uid": "semantic-edit", "prdVer": "11.7.7.331", "device": {"romVersion": "7.0"},
              "userQuery": "标题字体再大一点，其他保持不变", "sourceArtifactUrl": "https://old.test/1.md"}
    values.update(kwargs)
    return GenerateWidgetCardRequest(**values)


@pytest.mark.asyncio
@pytest.mark.parametrize("entry", [
    "generate_widget_card_compact_dsl", "generate_widget_card_a2ui_form",
    "generate_widget_card_terse_dsl_nested2",
])
async def test_every_edit_entry_bypasses_creation_and_templates(edit_run, entry):
    original = edit_run.source.model_dump_json()
    response = await getattr(WidgetGenerationService(), entry)(_request())
    assert response.status == GenerationStatus.SUCCESS
    assert response.artifactUrl != _request().sourceArtifactUrl
    assert edit_run.source.model_dump_json() == original
    assert len(edit_run.saved) == 1
    assert edit_run.saved[0].meta.sourceArtifactDigest == "sha256:source"
    assert [phase for phase, _ in edit_run.calls] == ["edit_intent", "edit_execute"]


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["needs_clarification", "unchanged", "unsupported"])
async def test_normal_business_outcome_never_repairs_or_saves(edit_run, outcome):
    edit_run.intent = _intent(outcome=outcome, explanation="已经是小规格，请确认是否缩小内容")
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert response.status.value == outcome
    assert response.editFeedback
    assert not response.artifactUrl
    assert not edit_run.saved
    assert len(edit_run.calls) == 1


@pytest.mark.asyncio
async def test_size_edit_updates_layout_and_runtime_together(edit_run, source):
    edit_run.intent = _intent(
        mode="layout", dimensions=["layout"], targets=["root"], targetSize="2x2",
    )
    edit_run.outputs = [json.dumps(_layout(source))]
    sizes = []

    async def notify(size):
        sizes.append(size)

    response = await WidgetGenerationService().generate_widget_card_compact_dsl(
        _request(userQuery="把卡片调小一点", size="2x2"), before_model_call=notify,
    )
    assert response.status == GenerationStatus.SUCCESS
    assert response.suggestSize == "2x2"
    assert sizes == ["2x2"]
    final = edit_run.saved[0]
    assert final.cardSpec.get("suggestSize") == final.taskSpec.get("size") == "2x2"
    assert _nodes(_rows(final.genui))[0].get("component") == "Row"


@pytest.mark.asyncio
async def test_size_edit_cannot_be_replaced_by_background_opacity(edit_run, source):
    edit_run.intent = _intent(mode="layout", dimensions=["layout", "palette"],
                             targets=["root"], targetSize="2x2")
    rows = _rows(source)
    _nodes(rows)[0].get("styles")["backgroundColor"] = "#33121E59"
    edit_run.outputs = [json.dumps({"sourceDigest": source_digest(source), "genui": rows})]
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert response.errorCode == ErrorCode.WIDGET_EDIT_INVALID.value
    assert not edit_run.saved
    assert len(edit_run.calls) == 4


@pytest.mark.asyncio
async def test_bad_result_is_repaired_from_same_source(edit_run, source):
    edit_run.outputs = ["{}", json.dumps(_patch(source))]
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert response.status == GenerationStatus.SUCCESS
    executions = [messages for phase, messages in edit_run.calls if phase == "edit_execute"]
    assert len(executions) == 2
    for messages in executions:
        assert json.loads(messages[1].get("content", "{}")).get("previousGenui") == source


@pytest.mark.asyncio
async def test_edit_failures_do_not_restart_interface_budget(edit_run):
    edit_run.outputs = ["{}"]
    response = await run_compact_dsl_with_retry(
        WidgetGenerationService().generate_widget_card_compact_dsl, _request(), enabled=True,
        retry_count=3, request_id="edit-budget",
    )
    assert response.status == GenerationStatus.FAILED
    assert len(edit_run.calls) == 4
    assert not edit_run.saved


@pytest.mark.asyncio
async def test_edit_master_switch_and_invalid_source_never_create(edit_run, monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_widget_edit", False)
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert response.errorCode == ErrorCode.WIDGET_EDIT_DISABLED.value
    assert not edit_run.calls


def test_first_generation_response_keeps_original_serialization():
    from api.schemas import GenerateWidgetCardResponse

    response = GenerateWidgetCardResponse(status=GenerationStatus.SUCCESS, suggestSize="2x2",
                                          message="内部说明")
    assert "editFeedback" not in json.loads(response.model_dump_json())
    assert "editFeedback" not in response.model_dump(mode="json")


def test_edit_validation_does_not_change_default_first_generation(source):
    regular = validate_card(dsl_text=source)
    explicit_default = validate_card(dsl_text=source, options=ValidationOptions(edit_mode=False))
    assert regular.render_json() == explicit_default.render_json()


def test_new_edit_modules_follow_control_and_comprehension_rules():
    for module in (widget_edit_contract, widget_edit_service, widget_edit_prompt,
                   edit_validation_module):
        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While)):
                count = 1
                for expression in ast.walk(node.test):
                    if isinstance(expression, ast.BoolOp):
                        count += len(expression.values) - 1
                assert count <= 3, (module.__name__, node.lineno)
            if isinstance(node, (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)):
                assert len(node.generators) == 1, (module.__name__, node.lineno)
                assert len(node.generators[0].ifs) <= 1, (module.__name__, node.lineno)


@pytest.mark.asyncio
async def test_actual_tiffany_request_updates_multiple_fusion_balls(edit_run):
    rows = _rows(edit_run.source.genui)
    nodes = _nodes(rows)
    ball_ids = ["fusionBallLarge", "fusionBallMedium", "fusionBallSmall"]
    children = nodes[0].get("children")
    assert isinstance(children, list)
    for identity in ball_ids:
        nodes.append({"id": identity, "component": "Progress",
                      "value": 50, "total": 100, "styles": {
                          "type": "ring", "width": 40, "height": 40, "color": "#00000000",
                          "backgroundColor": "#FF493D99",
                      }})
        children.append(identity)
    original = dump_rows(rows)
    edit_run.source.genui = original
    edit_run.intent = _intent(targets=["root"], dimensions=["palette"],
                             explanation="协调调整整卡配色为蒂芙尼蓝")
    payload = {"sourceDigest": source_digest(original), "changes": []}
    for identity in ball_ids:
        payload.get("changes").extend(
            _patch(original, identity, "backgroundColor", "#FF81D8D0").get("changes"),
        )
    edit_run.outputs = [json.dumps(payload)]
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(
        _request(userQuery="把这张睡眠卡片的整体颜色改成蒂芙尼蓝"),
    )
    assert response.status == GenerationStatus.SUCCESS
    assert edit_run.saved[0].genui.count("#FF81D8D0") == 3
    assert len(edit_run.calls) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["historical", "new"])
async def test_edit_contrast_policy_preserves_history_but_blocks_new_errors(edit_run, kind):
    if kind == "historical":
        rows = _rows(edit_run.source.genui)
        _nodes(rows)[1].get("styles")["fontColor"] = "#FFFFFFFF"
        edit_run.source.genui = dump_rows(rows)
        edit_run.outputs = [json.dumps(_patch(edit_run.source.genui))]
    else:
        edit_run.intent = _intent(dimensions=["palette"])
        edit_run.outputs = [json.dumps(_patch(edit_run.source.genui,
                                              prop="fontColor", value="#FFFFFFFF"))]
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    expected = GenerationStatus.SUCCESS if kind == "historical" else GenerationStatus.FAILED
    assert response.status == expected
    assert bool(edit_run.saved) == (kind == "historical")


@pytest.mark.asyncio
async def test_background_gradient_is_removed_explicitly(edit_run):
    rows = _rows(edit_run.source.genui)
    gradient = {"colors": [["#FFFFFFFF", 0], ["#FFE0EEEE", 1]]}
    _nodes(rows)[0].get("styles")["linearGradient"] = gradient
    edit_run.source.genui = dump_rows(rows)
    edit_run.intent = _intent(targets=["root"], dimensions=["palette"])
    payload = _patch(edit_run.source.genui, "root", "backgroundColor", "#FF81D8D0")
    payload.get("changes").append({
        "componentId": "root", "property": "styles.linearGradient", "operation": "remove",
        "before": {"exists": True, "value": gradient},
    })
    edit_run.outputs = [json.dumps(payload)]
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert response.status == GenerationStatus.SUCCESS
    assert "linearGradient" not in edit_run.saved[0].genui


@pytest.mark.asyncio
async def test_storage_failure_does_not_regenerate_edit(edit_run, monkeypatch):
    async def fail_save(*_args):
        raise ArtifactUploadError("临时存储失败")

    monkeypatch.setattr(ArtifactStore, "save", fail_save)
    with pytest.raises(ArtifactUploadError):
        await run_compact_dsl_with_retry(
            WidgetGenerationService().generate_widget_card_compact_dsl, _request(), enabled=True,
            retry_count=3, request_id="store-failure",
        )
    assert len(edit_run.calls) == 2


@pytest.mark.asyncio
async def test_consecutive_edits_keep_previous_changes(edit_run, monkeypatch):
    first = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert first.status == GenerationStatus.SUCCESS
    previous = edit_run.saved[0]
    loaded = SourceArtifactLoadResult(
        artifact=previous, design_token=None, artifact_digest="sha256:second", url_hash="second",
        read_latency_ms=0.0, parse_latency_ms=0.0, download_mode="mock",
    )
    monkeypatch.setattr(SourceArtifactRepository, "load", lambda *_args: loaded)
    edit_run.intent = _intent(dimensions=["palette"], targets=["root"])
    edit_run.outputs = [json.dumps(_patch(previous.genui, "root", "backgroundColor", "#FF81D8D0"))]
    second = await WidgetGenerationService().generate_widget_card_compact_dsl(
        _request(userQuery="背景换成蒂芙尼蓝", sourceArtifactUrl=first.artifactUrl),
    )
    assert second.status == GenerationStatus.SUCCESS
    assert second.artifactUrl != first.artifactUrl
    assert _nodes(_rows(edit_run.saved[-1].genui))[1].get("styles", {}).get("fontSize") == 18
    assert edit_run.saved[-1].meta.sourceArtifactDigest == "sha256:second"


def test_relative_static_text_edit_never_replaces_dynamic_expression(source):
    from services.widget_edit_contract import TextChange

    rows = _rows(source)
    _nodes(rows)[1]["content"] = "{{ ${/data/weather/current/condition} }}"
    changed = dump_rows(rows)
    intent = _intent(dimensions=["text"], textChanges=[TextChange(
        componentId="title", before="{{ ${/data/weather/current/condition} }}", after="晴",
    )])
    with pytest.raises(ValueError, match="动态"):
        validate_intent(intent, changed, "2x4", None)


def test_default_semantic_edit_and_budget_are_independent_from_creation():
    from config.config import Settings

    settings = Settings(_env_file=None)
    assert settings.enable_semantic_widget_edit is True
    assert settings.widget_edit_max_repair_attempts == 2


def test_noop_does_not_ignore_explicit_size_change(source):
    with pytest.raises(ValueError, match="无需修改"):
        validate_intent(_intent(outcome="unchanged"), source, "2x4", "2x2")


def test_authorized_photo_layer_removal_keeps_business_icon(source):
    rows = _rows(source)
    nodes = _nodes(rows)
    children = nodes[0].get("children")
    assert isinstance(children, list)
    nodes.append({
        "id": "photo", "component": "Image", "src": "resources/base/media/photo.png",
        "styles": {"width": "matchParent", "height": "matchParent", "objectFit": "cover"},
    })
    nodes.append({"id": "icon", "component": "Image", "src": "resources/base/media/sleep.svg",
                  "styles": {"width": 20, "height": 20, "objectFit": "contain"}})
    children.extend(["photo", "icon"])
    original = dump_rows(rows)
    intent = _intent(mode="layout", dimensions=["layout", "palette"], targets=["root"],
                     backgroundTargets=["photo"])
    validate_intent(intent, original, "2x4", None)
    children.remove("photo")
    nodes.remove(next(node for node in nodes if node.get("id") == "photo"))
    result = apply_edit_output(original, json.dumps({
        "sourceDigest": source_digest(original), "genui": rows,
    }), intent)
    assert "sleep.svg" in result and "photo.png" not in result
    with pytest.raises(ValueError, match="业务图标"):
        validate_intent(_intent(mode="layout", dimensions=["layout", "palette"], targets=["root"],
                                backgroundTargets=["icon"]), original, "2x4", None)


def test_style_edits_and_explicit_static_text_replacement(source):
    from services.widget_edit_contract import TextChange

    intent = _intent(dimensions=["typography", "shape", "text"], textChanges=[TextChange(
        componentId="title", before="睡眠卡片", after="昨夜睡眠",
    )])
    patch = _patch(source, prop="fontWeight", value=700)
    patch.get("changes").append({"componentId": "title", "property": "content",
                                  "before": {"exists": True, "value": "睡眠卡片"},
                                  "value": "昨夜睡眠"})
    validate_intent(intent, source, "2x4", None)
    result = apply_edit_output(source, json.dumps(patch, ensure_ascii=False), intent)
    assert "昨夜睡眠" in result and "700" in result


def test_execution_cannot_change_dynamic_paths_or_action_parameters(source):
    rows = _rows(source)
    node = _nodes(rows)[1]
    node["content"] = "{{ ${/data/weather/current/condition} }}"
    node["onClick"] = [{"call": "openWeather", "args": {"city": "上海"}}]
    original = dump_rows(rows)
    intent = _intent(mode="layout", dimensions=["layout", "palette"], targets=["root"])
    changed = copy.deepcopy(rows)
    _nodes(changed)[1]["onClick"] = [{"call": "openWeather", "args": {"city": "北京"}}]
    with pytest.raises(ValueError, match="业务"):
        apply_edit_output(original, json.dumps({
            "sourceDigest": source_digest(original), "genui": changed,
        }), intent)


def test_severe_fixed_text_clipping_is_blocked(edit_run):
    from services.card_validation.edit_validation.artifact import validate_edit_artifact

    original = edit_run.source
    candidate = original.model_copy(deep=True)
    rows = _rows(candidate.genui)
    _nodes(rows)[1].get("styles").update({"fontSize": 100, "height": 12})
    candidate.genui = dump_rows(rows)
    intent = _intent(dimensions=["typography", "layout"])
    result = validate_edit_artifact(original, candidate, intent)
    assert any("EDIT_TEXT_CLIPPED" in error for error in result.errors)


@pytest.mark.parametrize("old_font,new_font,parent_height,min_font,blocked", [
    (12, 16, 12, None, True),
    (12, 100, 12, None, True),
    (16, 16, 12, None, False),
    (16, 14, 12, None, False),
    (12, 16, 12, 12, False),
    (12, 16, 20, None, False),
])
def test_fixed_parent_checks_changed_text_and_preserves_historical_deficit(
    old_font, new_font, parent_height, min_font, blocked,
):
    from services.card_validation.edit_validation.artifact import (
        EditValidationResult,
        _fixed_container_errors,
    )

    before = {
        "parent": {"component": "Row", "children": ["text"],
                   "styles": {"height": parent_height}},
        "text": {"component": "Text", "styles": {"fontSize": old_font}},
    }
    after = copy.deepcopy(before)
    text = after.get("text")
    assert text is not None
    styles = text.get("styles")
    assert styles is not None
    styles["fontSize"] = new_font
    if min_font is not None:
        styles["minFontSize"] = min_font
    result = EditValidationResult()
    _fixed_container_errors(before, after, result)
    assert bool(result.errors) is blocked


@pytest.mark.asyncio
async def test_visual_edit_cannot_smuggle_new_data_candidate(edit_run):
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(_request(
        candidateDataBindings=[{"capabilityId": "ViewWeather", "writeResultTo": "/data/weather",
                                "arguments": {"prefectureName": "上海市", "forecastDays": 1}}],
    ))
    assert response.status == GenerationStatus.UNSUPPORTED
    assert not edit_run.calls and not edit_run.saved


@pytest.mark.parametrize("outcome", ["needs_clarification", "unchanged"])
def test_edit_normal_outcomes_close_device_wait_without_success(outcome):
    from api.routes import _generation_result_directive
    from services.widget_directive import WidgetDirectiveState

    state, url = _generation_result_directive({"status": outcome, "artifactUrl": ""})
    assert state == WidgetDirectiveState.FAILURE
    assert not url


@pytest.mark.parametrize("gradient", [
    {"colors": [["not-a-color", 0], ["#FFFFFFFF", 1]]},
    {"colors": [["#FF000000", 1], ["#FFFFFFFF", 0]]},
    {"colors": [["#FF000000", 0], ["#FFFFFFFF", 2]]},
])
def test_gradient_edits_cannot_bypass_output_color_or_stop_validation(source, gradient):
    intent = _intent(dimensions=["palette"], targets=["root"])
    with pytest.raises(ValueError):
        apply_edit_output(source, json.dumps(_patch(source, "root", "linearGradient", gradient)),
                          intent)


@pytest.mark.asyncio
async def test_runtime_metadata_update_is_not_lost_when_visuals_are_unchanged(edit_run):
    edit_run.intent = _intent(outcome="unchanged", explanation="原卡视觉无需调整")
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(
        _request(userQuery="仅修改卡片名称元信息，原显示不变", title="新的睡眠卡片"),
    )
    assert response.status == GenerationStatus.SUCCESS
    assert len(edit_run.calls) == 1
    assert edit_run.saved[0].cardSpec.get("title") == "新的睡眠卡片"
    assert edit_run.saved[0].genui == edit_run.source.genui


@pytest.mark.parametrize("stage", ["intent", "execute"])
def test_edit_prompts_are_file_backed_and_stage_specific(source, stage):
    if stage == "intent":
        messages = widget_edit_prompt.intent_prompt(source, "大一点", "2x4", None)
    else:
        messages = widget_edit_prompt.execution_prompt(source, "大一点", _intent())
    system = messages[0].get("content", "")
    for filename in (f"{stage}.md", "protocol.md", "design.md", "examples.md"):
        fragment = (widget_edit_prompt.PROMPT_DIR / filename).read_text(encoding="utf-8").strip()
        assert fragment in system
    assert "{{CREATE_SYSTEM_PROMPT}}" not in system
    assert "previousGenui" in system
    payload = json.loads(messages[1].get("content", "{}"))
    assert payload.get("previousGenui") == source
    assert payload.get("editContract") == widget_edit_contract.edit_contract()


@pytest.mark.parametrize("missing", [True, False])
def test_missing_or_empty_edit_resource_never_falls_back_to_creation(
    tmp_path, monkeypatch, missing,
):
    monkeypatch.setattr(widget_edit_prompt, "PROMPT_DIR", tmp_path)
    if not missing:
        (tmp_path / "intent.md").write_text("  \n", encoding="utf-8")
    with pytest.raises(ValueError, match="编辑提示词"):
        widget_edit_prompt.intent_prompt("original", "edit", "2x4", None)


def test_edit_prompt_styles_use_the_same_component_and_dimension_intersection():
    rules = widget_edit_contract.edit_contract()
    matrix = rules.get("editableStylesByComponent", {})
    common = set(rules.get("commonStyleFields", []))
    for kind, fields in rules.get("componentStyleFields", {}).items():
        actual = matrix.get(kind, {})
        for dimension, permitted in rules.get("editableDimensions", {}).items():
            assert set(actual.get(dimension, [])) == (common | set(fields)) & set(permitted)
    assert "fontSize" not in matrix.get("Column", {}).get("typography", [])


@pytest.mark.parametrize("operator,value,updated,blocked", [
    ("equal", 20, 20, False),
    ("equal", 20, 18, True),
    ("increase", None, 18, False),
    ("increase", None, 12, True),
    ("increase", None, 14, True),
    ("decrease", None, 12, False),
    ("decrease", None, 18, True),
    ("preserve", None, 14, False),
    ("preserve", None, 18, True),
    ("remove", None, None, False),
    ("remove", None, 14, True),
])
def test_final_edit_checks_explicit_and_relative_property_goals(
    source, operator, value, updated, blocked,
):
    goal = {"componentId": "title", "property": "styles.fontSize", "operator": operator}
    if value is not None:
        goal["value"] = value
    intent = _intent(expectations=[goal])
    validate_intent(intent, source, "2x4", None)
    rows = _rows(source)
    styles = _nodes(rows)[1].get("styles")
    assert styles is not None
    if updated is None:
        styles.pop("fontSize")
    else:
        styles["fontSize"] = updated
    errors = edit_validation_module.edit_expectation_errors(source, dump_rows(rows), intent)
    assert bool(errors) is blocked


@pytest.mark.parametrize("goal", [
    {"componentId": "title", "property": "styles.fontSize", "operator": "equal"},
    {"componentId": "title", "property": "styles.fontSize", "operator": "increase", "value": 20},
    {"componentId": "title", "property": "content", "operator": "increase"},
    {"componentId": "title", "property": "onClick", "operator": "equal", "value": []},
    {"componentId": "title", "property": "styles.padding.top", "operator": "equal", "value": 8},
    {"componentId": "missing", "property": "styles.fontSize", "operator": "equal", "value": 20},
    {"componentId": "value", "property": "styles.fontSize", "operator": "equal", "value": 20},
])
def test_invalid_or_unauthorized_edit_goals_are_rejected(source, goal):
    with pytest.raises(ValueError):
        validate_intent(_intent(expectations=[goal]), source, "2x4", None)


def test_duplicate_or_dynamic_goals_cannot_bypass_edit_contract(source):
    goal = {"componentId": "title", "property": "styles.fontSize", "operator": "increase"}
    with pytest.raises(ValueError, match="重复"):
        validate_intent(_intent(expectations=[goal, goal]), source, "2x4", None)
    rows = _rows(source)
    _nodes(rows)[1].get("styles")["fontSize"] = "{{ $__dataModel.fontSize }}"
    with pytest.raises(ValueError, match="静态数值"):
        validate_intent(_intent(expectations=[goal]), dump_rows(rows), "2x4", None)


def test_exact_color_goals_accept_equivalent_opaque_hex(source):
    goal = {"componentId": "title", "property": "styles.fontColor",
            "operator": "equal", "value": "#111111"}
    intent = _intent(dimensions=["palette"], expectations=[goal])
    validate_intent(intent, source, "2x4", None)
    assert not edit_validation_module.edit_expectation_errors(source, source, intent)


@pytest.mark.asyncio
async def test_unmet_exact_goal_repairs_without_losing_the_accepted_target(edit_run, source):
    edit_run.intent = _intent(expectations=[{
        "componentId": "title", "property": "styles.fontSize", "operator": "equal", "value": 20,
    }])
    edit_run.outputs = [json.dumps(_patch(source, value=18)), json.dumps(_patch(source, value=20))]
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(
        _request(userQuery="标题字号改为20"),
    )
    assert response.status == GenerationStatus.SUCCESS
    executions = [messages for phase, messages in edit_run.calls if phase == "edit_execute"]
    assert len(executions) == 2
    feedback = json.loads(executions[1][-1].get("content", "{}"))
    assert "EDIT_EXPECTATION_UNMET" in str(feedback.get("errors"))
    assert feedback.get("repairStage") == "execute"
    assert (widget_edit_prompt.PROMPT_DIR / "repair.md").read_text(encoding="utf-8").strip() == (
        feedback.get("instruction")
    )
    final_nodes = _nodes(_rows(edit_run.saved[0].genui))
    assert final_nodes[1].get("styles", {}).get("fontSize") == 20


@pytest.mark.asyncio
@pytest.mark.parametrize("target,expected_status,call_count", [
    (14, GenerationStatus.UNCHANGED, 1), (20, GenerationStatus.FAILED, 3),
])
async def test_unchanged_must_satisfy_declared_goals(edit_run, target, expected_status, call_count):
    edit_run.intent = _intent(outcome="unchanged", expectations=[{
        "componentId": "title", "property": "styles.fontSize", "operator": "equal", "value": target,
    }])
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert response.status == expected_status
    assert len(edit_run.calls) == call_count
    assert not edit_run.saved


@pytest.mark.asyncio
async def test_unmet_relative_goal_never_saves_or_calls_creation(edit_run, source):
    edit_run.intent = _intent(expectations=[{
        "componentId": "title", "property": "styles.fontSize", "operator": "increase",
    }])
    edit_run.outputs = [json.dumps(_patch(source, value=12))]
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert response.errorCode == ErrorCode.WIDGET_EDIT_INVALID.value
    assert len(edit_run.calls) == 4
    assert not edit_run.saved
