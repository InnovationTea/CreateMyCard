"""单步兜底与展开后编辑的离线回归，不进行真实模型/设备调用。"""

import copy
import json
from types import SimpleNamespace

import pytest

from api.schemas import GenerateWidgetCardRequest
from config.config import get_settings
from core.errors import ErrorCode, GenerationStatus
from custom.a2ui_model_client import A2UIModelClient, A2UIModelGenerationError
from models.generation import TaskSpec
from models.preflight import GenerationPreflightError
from services.artifact_store import ArtifactStore
from services.card_validation.standard_plan_coverage import standard_plan_coverage_errors
from services.compact_repair_strategy import CompactRepairStrategyTracker
from services.generation_pipeline import (
    DslProcessingResult,
    DslProcessorKind,
    QualityIssue,
    get_dsl_processor,
)
from services.single_step_contract import compact_font_requirements
from services.single_step_edit import EDIT_FORMAT, source_digest
from services.single_step_output import SingleStepOutputError, extract_single_step_output
from services.single_step_prompt import SingleStepPromptBuilder
from services.source_artifact_repository import SourceArtifactError, SourceArtifactLoadResult
from services.theme_style_roles import in_layout_phase
from services.validator import ArtifactValidator
from services.widget_edit_protocol.converter import convert_compact_dsl_to_a2ui
from services.widget_edit_protocol.resources import MODEL_FORMAT
from services.widget_generation_service import WidgetGenerationService


def _default_switch_settings(monkeypatch):
    from config.config import Settings

    for field in (
        "enable_single_step_generation_fallback", "enable_single_step_widget_edit",
        "enable_widget_edit",
    ):
        for alias in (f"WIDGET_SERVICE_{field.upper()}", field.upper(), field):
            monkeypatch.delenv(alias, raising=False)
    return Settings(_env_file=None)


def _standard(font_size=14, text="测试卡片"):
    messages = [
        {"version": "v0.9", "createSurface": {
            "surfaceId": "card", "catalogId": "ohos.a2ui.extended.catalog.form",
        }},
        {"version": "v0.9", "updateComponents": {
            "surfaceId": "card", "root": "root", "components": [
                {"id": "root", "component": "Column", "children": ["title"], "styles": {
                    "width": "matchParent", "height": "matchParent", "padding": 12,
                    "borderRadius": 20, "clip": True, "backgroundColor": "#FFFFFFFF",
                    "alignItems": "start", "justifyContent": "center",
                }},
                {"id": "title", "component": "Text", "content": text, "styles": {
                    "fontSize": font_size, "fontWeight": 400, "fontColor": "#FF111111",
                    "maxLines": 1, "width": "matchParent",
                }},
            ],
        }},
        {"version": "v0.9", "updateDataModel": {
            "surfaceId": "card", "path": "/", "value": {"label": "测试卡片"},
        }},
    ]
    return "\n".join(json.dumps(message, ensure_ascii=False) for message in messages)


def _request(**changes):
    values = {
        "uid": "single-step-test", "prdVer": "11.7.7.331", "device": {"romVersion": "7.0"},
        "userQuery": "创建测试卡片", "size": "2x4", "title": "测试卡片", "description": "测试",
        "candidateDataBindings": [], "candidateEventCandidates": [], "candidateAssetIds": [],
    }
    values.update(changes)
    return GenerateWidgetCardRequest(**values)


def _as_legacy_source(standard):
    if standard == "not-json":
        return standard
    messages = [json.loads(line) for line in standard.splitlines()]
    update = messages[1].get("updateComponents")
    assert isinstance(update, dict)
    rows = []
    for component in update.get("components", []):
        props = copy.deepcopy(component.get("styles", {}))
        for key, value in component.items():
            if key not in {"styles", "id", "component", "children"}:
                props[key] = copy.deepcopy(value)
        row = [component.get("id"), component.get("component"), props]
        if "children" in component:
            row.append(component.get("children"))
        rows.append(row)
    data = messages[2].get("updateDataModel")
    assert isinstance(data, dict)
    rows.append(["/", data.get("value")])
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def _converted_standard(standard):
    return convert_compact_dsl_to_a2ui(_as_legacy_source(standard), size="2x4")


def _edit_patch_response(messages, desired):
    if desired == "not-json":
        return desired
    payload = json.loads(messages[1].get("content", "{}"))
    original = payload.get("previousGenui")
    query = payload.get("editInstruction")
    assert isinstance(original, str) and isinstance(query, str)
    field = "fontSize"
    identity = "title"
    for candidate in ("backgroundColor", "color", "fontSize"):
        if candidate in query:
            field = candidate
            break
    for candidate in ("progress", "root", "title"):
        if candidate in query:
            identity = candidate
            break
    source_update = json.loads(original.splitlines()[1]).get("updateComponents", {})
    desired_update = json.loads(desired.splitlines()[1]).get("updateComponents", {})
    source_nodes = source_update.get("components")
    desired_nodes = desired_update.get("components")
    assert isinstance(source_nodes, list) and isinstance(desired_nodes, list)
    node = next(item for item in source_nodes if item.get("id") == identity)
    edited = next(item for item in desired_nodes if item.get("id") == identity)
    styles = node.get("styles", {})
    before = {"exists": field in styles}
    if field in styles:
        before["value"] = styles.get(field)
    return json.dumps({"sourceDigest": source_digest(original), "changes": [{
        "componentId": identity, "property": f"styles.{field}", "before": before,
        "value": edited.get("styles", {}).get(field), "requestQuote": query,
    }]}, ensure_ascii=False)


@pytest.fixture
def single_step_run(monkeypatch):
    settings = get_settings()
    # 本组保留旧字段补丁回滚路线；默认语义编辑由独立专项验证。
    monkeypatch.setattr(settings, "enable_semantic_widget_edit", False)
    monkeypatch.setattr(settings, "enable_a2ui_model_mock", False)
    monkeypatch.setattr(settings, "enable_artifact_validation", False)
    monkeypatch.setattr(settings, "enable_validation_failure_retry", True)
    monkeypatch.setattr(settings, "validation_failure_max_repair_attempts", 5)
    monkeypatch.setattr(settings, "enable_single_step_generation_fallback", True)
    monkeypatch.setattr(settings, "enable_single_step_widget_edit", True)
    monkeypatch.setattr(settings, "enable_widget_edit", True)
    monkeypatch.setattr(settings, "enable_generation_trace_recording", False)
    monkeypatch.setattr(settings, "enable_design_compact_runtime_prompt_context", False)
    state = SimpleNamespace(
        calls=[], saved=[], standard=_standard(), primary_success=False,
        compact_source="invalid-compact", repaired_compact_source="invalid-compact",
        envelope=None, profiles=[], theme_calls=[],
    )

    def standard_output(client, profile, messages):
        if (profile or {}).get("format") == EDIT_FORMAT:
            source = _edit_patch_response(messages, state.standard)
        else:
            source = _as_legacy_source(state.standard)
        if state.envelope is None:
            return source
        raw = f"```{state.envelope}\n{source}\n```"
        return client._process_model_output(raw, profile or {})

    async def generate(_client, messages, profile=None, **_kwargs):
        model_format = (profile or {}).get("format")
        if (profile or {}).get("id") == "post-layout-theme":
            state.theme_calls.append(copy.deepcopy(messages))
            return '{"themeId":"gradient-blue"}'
        state.calls.append(("generate", model_format, copy.deepcopy(messages)))
        state.profiles.append(copy.deepcopy(profile))
        if model_format == "raw-json":
            return json.dumps({"name": "submit_card_plan", "arguments": {
                "info_required": [{"text": "测试卡片", "requirement": "显示测试卡片标题",
                                   "priority": "must",
                                   "componentHints": ["EmphasisText"]}],
                "layoutHints": ["W-top-bottom"],
            }}, ensure_ascii=False)
        if model_format in {MODEL_FORMAT, EDIT_FORMAT}:
            return standard_output(_client, profile, messages)
        return state.compact_source

    async def repair(_client, messages, profile=None, **_kwargs):
        model_format = (profile or {}).get("format")
        state.calls.append(("repair", model_format, copy.deepcopy(messages)))
        state.profiles.append(copy.deepcopy(profile))
        if model_format in {MODEL_FORMAT, EDIT_FORMAT}:
            return standard_output(_client, profile, messages)
        return state.repaired_compact_source

    def process(source, _context):
        if state.primary_success:
            return DslProcessingResult(source_dsl=source, standard_dsl=state.standard)
        return DslProcessingResult(source_dsl=source, issues=(QualityIssue(
            stage="validation", code="COMPACT_DSL_VALIDATION_FAILED",
            message="component root: vertical layout requires at least 150vp within 126vp",
        ),))

    async def save(_store, artifact):
        state.saved.append((artifact.model_copy(deep=True), _store.design_token))
        return SimpleNamespace(
            artifactUrl=f"https://artifact.test/widget/{len(state.saved)}.md",
            artifactDigest=f"sha256:result-{len(state.saved)}",
        )

    monkeypatch.setattr(A2UIModelClient, "generate", generate)
    monkeypatch.setattr(A2UIModelClient, "generate_repair", repair)
    monkeypatch.setattr(get_dsl_processor(DslProcessorKind.DESIGN_COMPACT), "process", process)
    monkeypatch.setattr(ArtifactStore, "save", save)
    monkeypatch.setattr(WidgetGenerationService, "_enable_card_template", lambda _self: False)
    monkeypatch.setattr(WidgetGenerationService, "_enable_jsx_generation", lambda _self: False)
    monkeypatch.setattr(CompactRepairStrategyTracker, "next_directive", lambda *_a, **_k:
                        SimpleNamespace(retryable=True, to_prompt_payload=lambda: {
                            "category": "layout_capacity", "scope": "sublayout",
                            "repairStrategy": "rebudget", "retryable": True,
                        }))
    return state


@pytest.mark.asyncio
async def test_five_repairs_then_one_standard_call_and_forced_validation(single_step_run):
    state = single_step_run
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert response.status == GenerationStatus.SUCCESS
    assert [call[1] for call in state.calls] == [
        "raw-json", "compact-dsl", *(["compact-dsl"] * 5), MODEL_FORMAT,
    ]
    assert len(state.saved) == 1
    artifact, token = state.saved[0]
    assert token is None
    from services.post_layout_theme import foreground_signature

    assert len(state.theme_calls) == 1
    assert foreground_signature(artifact.genui) == foreground_signature(
        _converted_standard(state.standard),
    )
    assert "linearGradient" in artifact.genui
    final_messages = state.calls[-1][2]
    assert "极简协议" in final_messages[0].get("content", "")
    content = final_messages[1].get("content")
    assert isinstance(content, str)
    payload = json.loads(content)
    assert payload.get("userQuery") == "创建测试卡片"
    assert "fallbackFacts" not in payload
    assert "fontRequirements" not in payload
    assert "failedSourceDsl" not in payload
    assert "qualityErrors" not in payload
    assert "componentHints" not in content
    assert "layoutHints" not in content
    assert "invalid-compact" not in content


@pytest.mark.asyncio
async def test_switch_off_preserves_original_failure(single_step_run, monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_single_step_generation_fallback", False)
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert response.errorCode == ErrorCode.VALIDATION_FAILED.value
    assert len(single_step_run.calls) == 7
    assert not single_step_run.saved


@pytest.mark.asyncio
async def test_primary_success_never_uses_single_step(single_step_run):
    single_step_run.primary_success = True
    single_step_run.compact_source = _compact_text()
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert response.status == GenerationStatus.SUCCESS
    assert [call[1] for call in single_step_run.calls] == ["raw-json", "compact-dsl"]
    assert single_step_run.saved[0][1] is not None
    assert len(single_step_run.theme_calls) == 1


@pytest.mark.asyncio
async def test_bad_standard_does_not_save_or_recurse(single_step_run):
    single_step_run.standard = "not-json"
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert response.errorCode == ErrorCode.VALIDATION_FAILED.value
    assert len(single_step_run.calls) == 8
    assert not single_step_run.saved
    assert not single_step_run.theme_calls


@pytest.mark.asyncio
async def test_legacy_fallback_does_not_add_fusion_plan_coverage_gate(single_step_run):
    single_step_run.standard = _standard(text="无关文字")
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert response.status == GenerationStatus.SUCCESS
    assert len(single_step_run.saved) == 1


@pytest.mark.asyncio
async def test_network_error_never_uses_single_step(single_step_run, monkeypatch):
    async def failure(*_args, **_kwargs):
        raise A2UIModelGenerationError("offline test model failure")

    monkeypatch.setattr(A2UIModelClient, "generate", failure)
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert response.errorCode == ErrorCode.A2UI_GENERATION_FAILED.value
    assert not single_step_run.saved


@pytest.mark.parametrize("entry", [
    "generate_widget_card_compact_dsl", "generate_widget_card_a2ui_form",
    "generate_widget_card_terse_dsl_nested2",
])
@pytest.mark.parametrize("envelope", [None, "jsonl"])
@pytest.mark.asyncio
async def test_all_edit_entries_use_expanded_source_without_token(
    single_step_run, monkeypatch, entry, envelope,
):
    state = single_step_run
    service = WidgetGenerationService()
    created = await service.generate_widget_card_compact_dsl(_request())
    assert created.status == GenerationStatus.SUCCESS
    source_artifact = state.saved[-1][0]
    original = source_artifact.model_dump_json()
    defaults = _default_switch_settings(monkeypatch)
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_widget_edit", defaults.enable_widget_edit)
    monkeypatch.setattr(
        settings, "enable_single_step_widget_edit", defaults.enable_single_step_widget_edit,
    )
    monkeypatch.setattr(
        settings, "enable_single_step_generation_fallback",
        defaults.enable_single_step_generation_fallback,
    )
    source = SourceArtifactLoadResult(
        artifact=source_artifact, design_token=None, artifact_digest="sha256:source",
        url_hash="source-hash", read_latency_ms=0.0, parse_latency_ms=0.0, download_mode="mock",
    )
    monkeypatch.setattr("services.source_artifact_repository.SourceArtifactRepository.load",
                        lambda *_args: source)
    monkeypatch.setattr(WidgetGenerationService, "_enable_card_template", lambda _self: True)
    monkeypatch.setattr(WidgetGenerationService, "_enable_jsx_generation", lambda _self: True)
    state.standard = _standard(font_size=20)
    state.envelope = envelope
    state.calls.clear()
    state.theme_calls.clear()
    edited = await getattr(service, entry)(GenerateWidgetCardRequest(
        uid="single-step-test", prdVer="11.7.7.331", device={"romVersion": "7.0"},
        userQuery="仅把标题字号改为20", sourceArtifactUrl=created.artifactUrl,
    ))
    assert edited.status == GenerationStatus.SUCCESS
    assert len(state.calls) == 1
    assert not state.theme_calls
    assert state.calls[0][1] == EDIT_FORMAT
    content = state.calls[0][2][1].get("content")
    assert isinstance(content, str)
    payload = json.loads(content)
    assert payload.get("previousGenui") == source_artifact.genui
    assert payload.get("editInstruction") == "仅把标题字号改为20"
    assert state.saved[-1][0].meta.generationMode == "edit"
    assert state.saved[-1][0].meta.sourceArtifactDigest == "sha256:source"
    assert state.saved[-1][1] is None
    assert edited.artifactUrl != created.artifactUrl
    assert source_artifact.model_dump_json() == original


def test_coverage_does_not_accept_initialized_but_invisible_data():
    plan = {"info_required": [{"dataId": "/label", "componentHints": ["SingleLineTitle"]}]}
    assert standard_plan_coverage_errors(_standard(), plan, {})
    assert not standard_plan_coverage_errors(_standard(text="{{ ${/label} }}"), plan, {})


def test_coverage_rejects_unreachable_and_hidden_fact():
    plan = {"info_required": [{"text": "测试卡片"}]}
    for mode in ("unreachable", "hidden"):
        messages = [json.loads(line) for line in _standard().splitlines()]
        update = messages[1].get("updateComponents")
        assert isinstance(update, dict)
        components = update.get("components")
        assert isinstance(components, list)
        if mode == "unreachable":
            components[0]["children"] = []
        else:
            styles = components[0].get("styles")
            assert isinstance(styles, dict)
            styles["visibility"] = "hidden"
        source = "\n".join(json.dumps(row) for row in messages)
        assert standard_plan_coverage_errors(source, plan, {})


def test_prompt_is_isolated_from_fusion_and_previous_input_is_data():
    task = TaskSpec(userQuery="标题改20", size="2x4", eventCandidates=[],
                    dataModelSchema={}, assetCandidates=[])
    prompt = SingleStepPromptBuilder.build(task, {"catalogId": "catalog"},
                                          previous_genui="untrusted source")
    content = prompt[1].get("content")
    assert isinstance(content, str)
    payload = json.loads(content)
    assert payload.get("previousGenui") == "untrusted source"
    assert "untrusted source" not in prompt[0].get("content", "")
    assert "W-plan-guided" not in prompt[0].get("content", "")
    repair = SingleStepPromptBuilder.build_repair(
        prompt, "bad", [{"message": "invalid"}], dsl_format=EDIT_FORMAT,
    )
    assert len(repair) == 4
    assert repair[0].get("content", "").startswith(prompt[0].get("content", ""))


def test_generation_fallback_defaults_off_and_single_step_edit_defaults_on(monkeypatch):
    settings = _default_switch_settings(monkeypatch)
    assert settings.enable_single_step_generation_fallback is False
    assert settings.enable_single_step_widget_edit is True
    assert settings.enable_widget_edit is True
    assert settings.validation_failure_max_repair_attempts == 5


@pytest.mark.parametrize("field", [
    "enable_single_step_generation_fallback", "enable_single_step_widget_edit",
    "enable_widget_edit",
])
@pytest.mark.parametrize("enabled", [False, True])
def test_single_step_switches_can_be_overridden_by_environment(monkeypatch, field, enabled):
    from config.config import Settings

    _default_switch_settings(monkeypatch)
    monkeypatch.setenv(f"WIDGET_SERVICE_{field.upper()}", str(enabled).lower())
    assert getattr(Settings(_env_file=None), field) is enabled


@pytest.mark.asyncio
async def test_edit_master_switch_still_blocks_single_step(single_step_run, monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_widget_edit", False)
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(_request(
        sourceArtifactUrl="https://artifact.test/widget/source.md",
    ))
    assert response.errorCode == ErrorCode.WIDGET_EDIT_DISABLED.value
    assert not single_step_run.calls
    assert not single_step_run.saved


@pytest.mark.asyncio
async def test_original_early_stop_is_preserved_and_does_not_trigger_fallback(
    single_step_run, monkeypatch,
):
    monkeypatch.setattr(CompactRepairStrategyTracker, "next_directive", lambda *_a, **_k:
                        SimpleNamespace(retryable=False, to_prompt_payload=lambda: {
                            "retryable": False, "noProgress": True,
                        }))
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert response.errorCode == ErrorCode.VALIDATION_FAILED.value
    assert [call[1] for call in single_step_run.calls] == [
        "raw-json", "compact-dsl",
    ]
    assert not single_step_run.saved


@pytest.mark.asyncio
async def test_three_repair_config_does_not_allow_early_fallback(single_step_run, monkeypatch):
    monkeypatch.setattr(get_settings(), "validation_failure_max_repair_attempts", 3)
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert response.errorCode == ErrorCode.VALIDATION_FAILED.value
    assert [call[1] for call in single_step_run.calls] == [
        "raw-json", "compact-dsl", *(["compact-dsl"] * 3),
    ]
    assert not single_step_run.saved


@pytest.mark.asyncio
async def test_first_repair_success_returns_without_single_step(single_step_run, monkeypatch):
    state = single_step_run
    state.repaired_compact_source = _compact_text()

    def process(source, _context):
        repaired = any(call[0] == "repair" for call in state.calls)
        issues = () if repaired else (QualityIssue(
            stage="validation", code="COMPACT_DSL_VALIDATION_FAILED", message="layout error",
        ),)
        return DslProcessingResult(
            source_dsl=source, standard_dsl=state.standard if repaired else "", issues=issues,
        )

    monkeypatch.setattr(get_dsl_processor(DslProcessorKind.DESIGN_COMPACT), "process", process)
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert response.status == GenerationStatus.SUCCESS
    assert [call[1] for call in state.calls] == ["raw-json", "compact-dsl", "compact-dsl"]
    assert state.saved[0][1] is not None


@pytest.mark.asyncio
async def test_capability_preflight_failure_has_no_model_fallback(single_step_run):
    with pytest.raises(GenerationPreflightError):
        await WidgetGenerationService().generate_widget_card_compact_dsl(
            _request(candidateAssetIds=["asset.not_registered"])
        )
    assert not single_step_run.calls
    assert not single_step_run.saved


@pytest.mark.asyncio
async def test_custom_primary_limit_is_not_rewritten(single_step_run, monkeypatch):
    monkeypatch.setattr(get_settings(), "validation_failure_max_repair_attempts", 7)
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert response.status == GenerationStatus.SUCCESS
    assert [call[1] for call in single_step_run.calls] == [
        "raw-json", "compact-dsl", *(["compact-dsl"] * 7), MODEL_FORMAT,
    ]


@pytest.mark.asyncio
async def test_retry_disabled_does_not_add_fallback_call(single_step_run, monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_validation_failure_retry", False)
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert response.errorCode == ErrorCode.VALIDATION_FAILED.value
    assert len(single_step_run.calls) == 2
    assert not single_step_run.saved


@pytest.mark.asyncio
async def test_invalid_edit_source_never_becomes_create(single_step_run, monkeypatch):
    def invalid_source(*_args):
        raise SourceArtifactError(ErrorCode.SOURCE_ARTIFACT_NOT_FOUND, "offline missing source")

    monkeypatch.setattr("services.source_artifact_repository.SourceArtifactRepository.load",
                        invalid_source)
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(
        GenerateWidgetCardRequest(
            uid="single-step-test", prdVer="11.7.7.331", device={"romVersion": "7.0"},
            userQuery="标题改20", sourceArtifactUrl="https://artifact.test/missing.md",
        )
    )
    assert response.errorCode == ErrorCode.SOURCE_ARTIFACT_NOT_FOUND.value
    assert not single_step_run.calls
    assert not single_step_run.saved


def test_plan_action_is_not_satisfied_by_data_or_wrong_handler():
    task = {"eventCandidates": [{"id": "open", "call": "clickToApi", "args": {"id": "x"}}]}
    plan = {"info_required": [{"actionId": "open"}]}
    source = _standard()
    assert standard_plan_coverage_errors(source, plan, task)
    messages = [json.loads(line) for line in source.splitlines()]
    update = messages[1].get("updateComponents")
    assert isinstance(update, dict)
    components = update.get("components")
    assert isinstance(components, list)
    components[1]["onClick"] = [{"call": "clickToApi", "args": {"id": "x"}}]
    source = "\n".join(json.dumps(row) for row in messages)
    assert not standard_plan_coverage_errors(source, plan, task)


@pytest.mark.asyncio
async def test_edit_result_can_be_edited_again_without_compact_token(single_step_run, monkeypatch):
    state = single_step_run
    service = WidgetGenerationService()
    current = await service.generate_widget_card_compact_dsl(_request())
    assert current.status == GenerationStatus.SUCCESS

    def load_latest(*_args):
        return SourceArtifactLoadResult(
            artifact=state.saved[-1][0], design_token=None, artifact_digest="sha256:last",
            url_hash="last", read_latency_ms=0.0, parse_latency_ms=0.0, download_mode="mock",
        )

    monkeypatch.setattr("services.source_artifact_repository.SourceArtifactRepository.load",
                        load_latest)
    state.calls.clear()
    state.theme_calls.clear()
    for font in (20, 18):
        state.standard = _standard(font_size=font)
        previous = current.artifactUrl
        current = await service.generate_widget_card_compact_dsl(GenerateWidgetCardRequest(
            uid="single-step-test", prdVer="11.7.7.331", device={"romVersion": "7.0"},
            userQuery=f"仅把标题改为{font}号字", sourceArtifactUrl=previous,
        ))
        assert current.status == GenerationStatus.SUCCESS
        assert current.artifactUrl != previous
        assert state.saved[-1][1] is None
    assert len(state.calls) == 2
    assert not state.theme_calls
    assert all(call[1] == EDIT_FORMAT for call in state.calls)


def _compact_text(font=18):
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in [
        ["root", "Column", {}, ["old-layout-body"]],
        ["old-layout-body", "EmphasisText", {"mainText": "测试卡片", "fontSize": font}],
    ])


def test_clean_fallback_payload_never_includes_old_layout_errors_or_ids():
    task = TaskSpec(userQuery="原始需求", size="2x4", dataModelSchema={})
    prompt = SingleStepPromptBuilder.build(task, {}, fallback_context={
        "acceptedPlan": {
            "info_required": [{"text": "必需事实", "actionId": "open",
                               "componentHints": ["old-layout-body"], "width": 200}],
            "layoutHints": ["old-layout-body"],
        },
        "failedSourceDsl": "old-layout-body",
        "qualityErrors": [{"message": "old error"}],
        "fontRequirements": [{"text": "必需事实", "fontSize": 18,
                              "id": "old-layout-body", "height": 200}],
    })
    content = prompt[1].get("content")
    assert isinstance(content, str)
    payload = json.loads(content)
    assert payload == task.model_dump(mode="json", exclude_none=True, exclude={"appVersion"})
    assert "fallbackFacts" not in payload
    assert "fontRequirements" not in payload
    assert "old-layout-body" not in content
    assert "old error" not in content


def test_font_contract_extracts_recipe_secondary_text_title_and_unit_without_layout():
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in [
        ["root", "Column", {}, ["title", "number", "body"]],
        ["title", "SingleLineTitle", {"title": "电量卡片"}],
        ["number", "EmphasizedData", {"value": {"path": "/battery"}, "unit": "%"}],
        ["body", "EmphasisText", {"mainText": "状态", "secondaryText": {"path": "/state"}}],
        ["/battery", 68], ["/state", "未充电"],
    ])
    fonts, skipped = compact_font_requirements(source, size="2x4")
    assert not skipped
    assert {"text": "电量卡片", "fontSize": 12} in fonts
    assert {"dataId": "/battery", "fontSize": 30} in fonts
    assert {"text": "%", "fontSize": 12} in fonts
    assert {"text": "状态", "fontSize": 18} in fonts
    assert {"dataId": "/state", "fontSize": 12} in fonts
    assert all(set(item) <= {"text", "dataId", "fontSize"} for item in fonts)


def test_font_contract_does_not_freeze_illegal_recipe_size_or_malformed_source():
    assert compact_font_requirements("not-compact", size="2x4")[0] == []
    fonts, skipped = compact_font_requirements(_compact_text(font=9), size="2x4")
    assert not fonts
    assert skipped


def test_font_contract_does_not_freeze_misused_numeric_component():
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in [
        ["root", "Column", {}, ["value"]],
        ["value", "EmphasizedData", {"value": "未充电"}],
    ])
    fonts, skipped = compact_font_requirements(source, size="2x4")
    assert not fonts
    assert any("invalid numeric display role" in issue for issue in skipped)


@pytest.mark.asyncio
async def test_legacy_fallback_does_not_inherit_fusion_font_contract(single_step_run):
    state = single_step_run
    state.compact_source = _compact_text()
    state.repaired_compact_source = _compact_text(font=14)
    state.standard = _standard(font_size=18)
    result = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert result.status == GenerationStatus.SUCCESS
    content = state.calls[-1][2][1].get("content")
    assert isinstance(content, str)
    assert "fontRequirements" not in json.loads(content)
    assert "old-layout-body" not in content


@pytest.mark.asyncio
async def test_legacy_legal_font_is_not_blocked_by_fusion_recipe(single_step_run):
    state = single_step_run
    state.compact_source = _compact_text()
    result = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert result.status == GenerationStatus.SUCCESS
    assert len(state.calls) == 8
    assert len(state.saved) == 1


def test_font_guard_requires_visible_matching_binding_and_size():
    requirement = [{"dataId": "/label", "fontSize": 18}]
    assert standard_plan_coverage_errors(
        _standard(text="{{ ${/label} }}"), None, {}, font_requirements=requirement,
    )
    assert not standard_plan_coverage_errors(
        _standard(text="{{ ${/label} }}", font_size=18), None, {},
        font_requirements=requirement,
    )


@pytest.mark.parametrize("language", ["genui", "jsonl", "JSONL", "GENUI"])
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_single_step_extracts_one_envelope_without_changing_dsl(language, newline):
    source = _standard().replace("\n", newline)
    raw = f"  ```{language}  {newline}{source}{newline}```  "
    assert extract_single_step_output(raw) == source
    assert extract_single_step_output(source) == source


@pytest.mark.parametrize("raw", [
    "```jsonl\n{}", "```json\n{}\n```", "```\n{}\n```",
    "解释\n```genui\n{}\n```", "```genui\n{}\n```\n解释",
    "```genui\n{}\n```\n```genui\n{}\n```",
    "```jsonl\n```genui\n{}\n```\n```",
])
def test_single_step_rejects_ambiguous_or_incomplete_envelopes(raw):
    with pytest.raises(SingleStepOutputError):
        extract_single_step_output(raw)


def test_single_step_extraction_does_not_repair_invalid_json_or_change_strings():
    assert extract_single_step_output("```jsonl\nnot-json\n```") == "not-json"
    source = _standard(text="代码标记 ```jsonl 也是正文")
    assert extract_single_step_output(f"```jsonl\n{source}\n```") == source


def test_single_step_extraction_precedes_existing_standard_normalization():
    source = _standard().replace('"width": "matchParent", "height": "matchParent"',
                                 '"width": 300, "height": 150')
    client = A2UIModelClient()
    profile = {"id": "a2ui-form-rom6.0-v1", "format": "a2ui-form", "singleStepOutput": True}
    result = client._process_model_output(f"```jsonl\n{source}\n```", profile)
    assert result == client.convert_dsl(source)
    update = json.loads(result.splitlines()[1]).get("updateComponents")
    assert isinstance(update, dict)
    components = update.get("components")
    assert isinstance(components, list)
    styles = components[0].get("styles")
    assert isinstance(styles, dict)
    assert styles.get("width") == "matchParent"
    assert styles.get("height") == "matchParent"
    with pytest.raises(A2UIModelGenerationError):
        client._process_model_output("```genui\n{}\n```\n解释", profile)


@pytest.mark.parametrize("profile", [
    {"id": "design-compact-dsl", "format": "compact-dsl"},
    {"id": "a2ui-form-rom6.0-v1", "format": "a2ui-form"},
])
def test_untagged_output_retains_original_extraction(profile):
    client = A2UIModelClient()
    raw = f"```jsonl\n{_standard()}\n```"
    expected = client.extract_genui_payload(raw)
    if profile.get("format") == "a2ui-form":
        expected = client.convert_dsl(expected)
    assert client._process_model_output(raw, profile) == expected


@pytest.mark.asyncio
async def test_five_repairs_then_jsonl_fallback_without_changing_primary(single_step_run):
    state = single_step_run
    state.envelope = "jsonl"
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert response.status == GenerationStatus.SUCCESS
    assert len(state.calls) == 8
    assert all("singleStepOutput" not in profile for profile in state.profiles[:-1])
    assert state.profiles[-1].get("singleStepOutput") is True
    from services.post_layout_theme import foreground_signature

    actual = state.saved[-1][0].genui
    assert len(state.theme_calls) == 1
    assert foreground_signature(actual) == foreground_signature(_converted_standard(state.standard))


@pytest.mark.asyncio
async def test_edit_repair_also_extracts_jsonl(single_step_run, monkeypatch):
    state = single_step_run
    service = WidgetGenerationService()
    created = await service.generate_widget_card_compact_dsl(_request())
    assert created.status == GenerationStatus.SUCCESS
    source = SourceArtifactLoadResult(
        artifact=state.saved[-1][0], design_token=None, artifact_digest="sha256:source",
        url_hash="source", read_latency_ms=0.0, parse_latency_ms=0.0, download_mode="mock",
    )
    monkeypatch.setattr("services.source_artifact_repository.SourceArtifactRepository.load",
                        lambda *_args: source)
    original_repair = A2UIModelClient.generate_repair

    async def repair(client, messages, profile=None, **kwargs):
        state.standard = _standard(font_size=20)
        return await original_repair(client, messages, profile, **kwargs)

    monkeypatch.setattr(A2UIModelClient, "generate_repair", repair)
    state.calls.clear()
    state.envelope = "jsonl"
    state.standard = "not-json"
    response = await service.generate_widget_card_compact_dsl(GenerateWidgetCardRequest(
        uid="single-step-test", prdVer="11.7.7.331", device={"romVersion": "7.0"},
        userQuery="仅把标题字号改为20", sourceArtifactUrl=created.artifactUrl,
    ))
    assert response.status == GenerationStatus.SUCCESS
    assert [call[0] for call in state.calls] == ["generate", "repair"]
    assert all(call[1] == EDIT_FORMAT for call in state.calls)


@pytest.mark.parametrize("text", [
    "{{ '地点 ' + ${/label} }}", "{{ ${/label} + ' 地点' }}",
    "{{ ('地' + '点 ') + (${/label}) }}", "{{ '地点 ' + ${/label} + '（会议）' }}",
    "{{ '地点' }}", "{{ '地\\u70b9 ' + ${/label} }}",
])
def test_literal_labels_in_concatenation_are_visible_at_original_font(text):
    plan = {"info_required": [{"text": "地点"}]}
    requirement = [{"text": "地点 ", "fontSize": 14}]
    assert not standard_plan_coverage_errors(
        _standard(text=text), plan, {}, font_requirements=requirement,
    )
    assert standard_plan_coverage_errors(
        _standard(text=text, font_size=12), plan, {}, font_requirements=requirement,
    )


@pytest.mark.parametrize("text", [
    "{{ ${/label} }}", "{{ ${/label} == '地点' }}",
    "{{ ${/label} ? '地点' : '未知' }}", "{{ size('地点') + ${/label} }}",
    "{{ '地点' if ${/label} else '' }}", "{{ '地点' * 0 + ${/label} }}",
])
def test_labels_in_conditions_or_non_concatenation_are_not_assumed_visible(text):
    assert standard_plan_coverage_errors(
        _standard(text=text), {"info_required": [{"text": "地点"}]}, {},
    )


@pytest.mark.asyncio
async def test_single_step_theme_selection_failure_uses_common_gradient(
    single_step_run, monkeypatch,
):
    state = single_step_run
    generate = A2UIModelClient.generate
    phases = []

    async def fail_theme(client, messages, profile=None, **kwargs):
        phases.append(kwargs.get("phase"))
        if (profile or {}).get("id") == "post-layout-theme":
            raise A2UIModelGenerationError("theme selection unavailable")
        return await generate(client, messages, profile, **kwargs)

    monkeypatch.setattr(A2UIModelClient, "generate", fail_theme)
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert response.status == GenerationStatus.SUCCESS
    assert phases.count("theme") == 1
    assert len(state.calls) == 8
    assert len(state.saved) == 1
    assert "linearGradient" in state.saved[0][0].genui


@pytest.mark.asyncio
async def test_single_step_final_theme_validation_cannot_save_failure(single_step_run, monkeypatch):
    validate = ArtifactValidator.validate

    def reject_final(validator, artifact, profile):
        if in_layout_phase():
            return validate(validator, artifact, profile)
        return ["TEST_FINAL_ARTIFACT_REJECTED"]

    monkeypatch.setattr(ArtifactValidator, "validate", reject_final)
    with pytest.raises(ValueError, match="Final gradient validation failed"):
        await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert len(single_step_run.calls) == 8
    assert len(single_step_run.theme_calls) == 1
    assert not single_step_run.saved


@pytest.mark.asyncio
async def test_themed_card_edit_keeps_font_background_and_progress_overrides(
    single_step_run, monkeypatch,
):
    state = single_step_run
    records = [json.loads(line) for line in state.standard.splitlines()]
    update = records[1].get("updateComponents")
    assert isinstance(update, dict)
    nodes = update.get("components")
    assert isinstance(nodes, list)
    nodes[0]["children"].append("progress")
    nodes.append({"id": "progress", "component": "Progress", "value": 80, "total": 100,
                  "type": "ring", "styles": {"width": 44, "height": 44, "strokeWidth": 6,
                                               "color": "#FF1F4799",
                                               "backgroundColor": "#331F4799"}})
    state.standard = "\n".join(json.dumps(row, ensure_ascii=False) for row in records)
    service = WidgetGenerationService()
    current = await service.generate_widget_card_compact_dsl(_request())
    assert current.status == GenerationStatus.SUCCESS
    assert len(state.theme_calls) == 1

    def load_latest(*_args):
        return SourceArtifactLoadResult(
            artifact=state.saved[-1][0], design_token=None, artifact_digest="sha256:themed",
            url_hash="themed", read_latency_ms=0.0, parse_latency_ms=0.0, download_mode="mock",
        )

    monkeypatch.setattr("services.source_artifact_repository.SourceArtifactRepository.load",
                        load_latest)
    changes = [("title", "fontSize", 18), ("root", "backgroundColor", "#FFE8F0FE"),
               ("progress", "color", "#FF9C27B0")]
    state.calls.clear()
    for identity, key, value in changes:
        original = state.saved[-1][0]
        original_json = original.model_dump_json()
        edited = [json.loads(line) for line in original.genui.splitlines()]
        edited_update = edited[1].get("updateComponents")
        assert isinstance(edited_update, dict)
        target = next(node for node in edited_update.get("components", [])
                      if node.get("id") == identity)
        styles = target.get("styles")
        assert isinstance(styles, dict)
        styles[key] = value
        if key == "backgroundColor":
            styles.pop("linearGradient", None)
        state.standard = "\n".join(json.dumps(row, ensure_ascii=False) for row in edited)
        current = await service.generate_widget_card_compact_dsl(GenerateWidgetCardRequest(
            uid="single-step-test", prdVer="11.7.7.331", device={"romVersion": "7.0"},
            userQuery=f"仅修改{identity}的styles.{key}为{value}",
            sourceArtifactUrl=current.artifactUrl,
        ))
        assert current.status == GenerationStatus.SUCCESS
        assert original.model_dump_json() == original_json
        actual = [json.loads(line) for line in state.saved[-1][0].genui.splitlines()]
        assert actual == edited
    assert len(state.calls) == 3
    assert len(state.theme_calls) == 1
    final = state.saved[-1][0].genui
    assert "#FF9C27B0" in final and "#FFE8F0FE" in final


@pytest.mark.parametrize("mode", ["full_rewrite", "downstream_change"])
@pytest.mark.asyncio
async def test_edit_never_saves_non_target_changes_or_falls_back_to_create(
    single_step_run, monkeypatch, mode,
):
    state = single_step_run
    service = WidgetGenerationService()
    created = await service.generate_widget_card_compact_dsl(_request())
    assert created.status == GenerationStatus.SUCCESS
    source = state.saved[-1][0]
    source_json = source.model_dump_json()
    loaded = SourceArtifactLoadResult(
        artifact=source, design_token=None, artifact_digest="sha256:source",
        url_hash="source", read_latency_ms=0.0, parse_latency_ms=0.0, download_mode="mock",
    )
    monkeypatch.setattr("services.source_artifact_repository.SourceArtifactRepository.load",
                        lambda *_args: loaded)
    monkeypatch.setattr(get_settings(), "validation_failure_max_repair_attempts", 1)
    state.standard = _standard(font_size=18)
    state.calls.clear()
    state.theme_calls.clear()
    if mode == "full_rewrite":
        monkeypatch.setattr(
            "test_single_step_generation._edit_patch_response",
            lambda _messages, desired: _as_legacy_source(desired),
        )
    else:
        original_build = WidgetGenerationService._build_artifact

        def alter_unrequested_height(service, *args, **kwargs):
            artifact = original_build(service, *args, **kwargs)
            records = [json.loads(line) for line in artifact.genui.splitlines()]
            update = records[1].get("updateComponents", {})
            components = update.get("components")
            assert isinstance(components, list)
            styles = components[0].get("styles")
            assert isinstance(styles, dict)
            styles["height"] = 120
            artifact.genui = "\n".join(json.dumps(record, ensure_ascii=False) for record in records)
            return artifact

        monkeypatch.setattr(WidgetGenerationService, "_build_artifact", alter_unrequested_height)
    response = await service.generate_widget_card_compact_dsl(GenerateWidgetCardRequest(
        uid="single-step-test", prdVer="11.7.7.331", device={"romVersion": "7.0"},
        userQuery="仅把标题字号改为18", sourceArtifactUrl=created.artifactUrl,
    ))
    assert response.status == GenerationStatus.FAILED
    assert response.errorCode == ErrorCode.VALIDATION_FAILED.value
    assert len(state.saved) == 1
    assert len(state.calls) == 2
    assert all(call[1] == EDIT_FORMAT for call in state.calls)
    assert not state.theme_calls
    assert source.model_dump_json() == source_json
