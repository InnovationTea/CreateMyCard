"""Trace 新分支与调试端 JSON/配置链路的契约回归。"""

import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from debug_tools.batch_testing.managed_config import (
    GENERATION_OPTIONS,
    read_configuration,
    runtime_values,
    save_configuration,
    validate_changes,
)
from debug_tools.batch_testing.trace_parser import TraceImporter
from debug_tools.end_to_end_debug.backend.debug_agent.upstream_ws_client import (
    UpstreamToolError,
    parse_legacy_stream_content,
)
from debug_tools.postprocess_plugins.data_analysis.metrics import aggregate, analyze_request
from jsonschema import Draft202012Validator
from pydantic import BaseModel, Field

from services import post_layout_theme
from services.generation_trace_recorder import (
    GenerationTraceRecorder,
    trace_flow,
    trace_increment_attempt,
    trace_phase,
)

UID = "batch-1234abcd-00001-000"


@pytest.mark.parametrize("prefix", ["", "参数错误：", "  参数错误：  "])
@pytest.mark.parametrize("status", ["success", "failed"])
def test_standard_json_response_preserves_business_fields(prefix, status):
    payload = {
        "requestId": "session&interaction", "operation": "generateWidgetCardCompactDsl",
        "status": status, "data": {"text": "包含 type= 和中文：的内容", "flag": False},
        "error": None,
    }
    assert parse_legacy_stream_content(prefix + json.dumps(payload)) == payload


def test_invalid_json_response_is_explicit():
    with pytest.raises(UpstreamToolError, match="JSON"):
        parse_legacy_stream_content('参数错误：{"status":')


def _start(root):
    recorder = GenerationTraceRecorder()
    recorder.bind_request(UID, enabled=True, trace_root=root)
    return recorder, recorder.activate()


def _finish(recorder, token, root, status):
    recorder.finalize(status=status)
    recorder.deactivate(token)
    importer = TraceImporter(root)
    directory = importer.directory_for_uid(UID)
    assert directory is not None
    schema_path = (
        Path(__file__).parents[1] / "cloud/data/trace_schemas/generation-trace-v2.schema.json"
    )
    validator = Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8")))
    for line in (directory / "trace.jsonl").read_text(encoding="utf-8").splitlines():
        validator.validate(json.loads(line))
    view = importer.read(UID)
    assert view.get("status") == "complete", view.get("warnings")
    return view


class _Meta(BaseModel):
    generationMode: str = "create"


class _Artifact(BaseModel):
    genui: str = "layout"
    cardSpec: dict = Field(default_factory=dict)
    taskSpec: dict = Field(default_factory=dict)
    effectiveCapabilities: dict = Field(default_factory=dict)
    meta: _Meta = Field(default_factory=_Meta)


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_final", [False, True])
async def test_theme_records_real_validation_and_failed_fallback(tmp_path, monkeypatch, fail_final):
    async def select(*args, **kwargs):
        return "themed", {"theme": {"kind": "gradient"}, "themeId": "gradient-blue"}

    monkeypatch.setattr(post_layout_theme, "select_theme", select)
    monkeypatch.setattr(post_layout_theme, "apply_theme", lambda *args: "fallback")
    monkeypatch.setattr(post_layout_theme, "fallback_theme", lambda *args: {"id": "fallback"})
    validator = SimpleNamespace(
        validate=lambda *args, **kwargs: ["invalid"] if fail_final else [],
    )
    recorder, token = _start(tmp_path)
    try:
        if fail_final:
            with pytest.raises(ValueError, match="Final gradient validation failed"):
                await post_layout_theme.theme_artifact(_Artifact(), {}, None, validator, {})
        else:
            result = await post_layout_theme.theme_artifact(_Artifact(), {}, None, validator, {})
            assert result.genui == "themed"
    finally:
        view = _finish(recorder, token, tmp_path, "failed" if fail_final else "success")
    nodes = view.get("nodes")
    assert isinstance(nodes, list)
    theme = next(node for node in nodes if node.get("operation") == "theme")
    assert theme.get("status") == ("failed" if fail_final else "success")
    content_index = theme.get("contentIndex")
    assert isinstance(content_index, list)
    content_ids = [ref.get("id") for ref in content_index]
    assert len(content_ids) == len(set(content_ids))
    validations = [node for node in nodes if node.get("operation") == "theme.validation"]
    assert len(validations) == (2 if fail_final else 1)
    for node in validations:
        refs = node.get("artifacts")
        assert isinstance(refs, list)
        assert any(ref.get("name") == "theme_validation_errors" for ref in refs)


@pytest.mark.asyncio
async def test_recursive_branch_keeps_parent_and_accumulated_attempts(tmp_path):
    @trace_flow
    async def generate(*, policy):
        trace_phase("dsl")
        trace_increment_attempt("modelPhysicalAttempts")
        if not policy.single_step:
            await generate(policy=SimpleNamespace(
                single_step=True, source_format="single-step-edit-patch",
            ))
        return SimpleNamespace(status="success")

    recorder, token = _start(tmp_path)
    try:
        await generate(policy=SimpleNamespace(single_step=False))
    finally:
        view = _finish(recorder, token, tmp_path, "success")
    nodes = view.get("nodes")
    assert isinstance(nodes, list)
    branches = [node for node in nodes if node.get("operation") == "generation.branch"]
    assert len(branches) == 2
    branch_names = set()
    for node in branches:
        attributes = node.get("attributes")
        assert isinstance(attributes, dict)
        branch_names.add(attributes.get("generationBranch"))
    assert branch_names == {"fusion", "single_step_edit"}
    summary = view.get("summary")
    assert isinstance(summary, dict)
    assert summary.get("attemptCounts", {}).get("modelPhysicalAttempts") == 2


def test_changed_trace_steps_always_supply_measured_duration():
    root = Path(__file__).parents[1] / "cloud"
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id != "trace_step":
                continue
            assert any(keyword.arg == "duration_ms" for keyword in node.keywords), (
                path, node.lineno,
            )


def test_theme_statistics_have_separate_phase():
    view = {
        "status": "complete", "timingMode": "exact", "nodes": [
            {"operation": "theme", "startOffsetMs": 1.0, "durationMs": 7.0},
            {"operation": "model.physical_call", "attributes": {"phase": "theme"},
             "metrics": {"firstTokenLatencyMs": 2.0, "tokensPerSecond": 3.0}},
        ],
    }
    request = analyze_request(view, {}, "trace")
    assert request.get("phasesMs", {}).get("theme") == 7.0
    models = request.get("models")
    assert isinstance(models, list)
    assert models[0].get("phase") == "theme"
    result = aggregate([{"requests": [request]}])
    assert result.get("themeMs", {}).get("mean") == 7.0
    assert result.get("models", {}).get("theme", {}).get("ttftMs", {}).get("mean") == 2.0


def test_new_configuration_inherits_and_allows_task_overrides(tmp_path):
    root = tmp_path / "service"
    config_dir = root / "cloud/config"
    config_dir.mkdir(parents=True)
    declarations = ["class Settings:"]
    values = {}
    for name in GENERATION_OPTIONS:
        declarations.append(f"    {name}: bool = False")
        values[name] = False
    (config_dir / "config.py").write_text("\n".join(declarations), encoding="utf-8")
    (config_dir / "default_config.yaml").write_text(yaml.safe_dump(values), encoding="utf-8")
    debug_path = tmp_path / "debug.yaml"
    debug_path.write_text("widget_backend: {}", encoding="utf-8")
    config = read_configuration(root, debug_path=debug_path)
    assert set(GENERATION_OPTIONS) <= set(config.exposed)
    updates = validate_changes(config, {"enable_single_step_widget_edit": True}, exposed=True)
    config.values.update(updates)
    assert runtime_values(config).get("enable_single_step_widget_edit") is True


@pytest.mark.asyncio
@pytest.mark.parametrize("valid", [True, False])
async def test_batch_json_final_preserves_correlation_and_failed_frames(monkeypatch, valid):
    from debug_tools.batch_testing import runner

    frame = {"reply": {"streamInfo": {"streamType": "final", "streamContent": json.dumps({
        "requestId": "s&i" if valid else "another-request",
        "operation": "generateWidgetCardCompactDsl", "status": "success",
        "data": {"artifactUrl": "mock://card.md"},
    })}}}

    class Connection:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def send(self, payload):
            return None

        async def recv(self):
            return json.dumps(frame)

    monkeypatch.setattr(runner.websockets, "connect", lambda *args, **kwargs: Connection())
    request = {"session": {"sessionId": "s", "interactionId": "i"}}
    if valid:
        result = await runner.invoke_generate("ws://localhost", request, 1)
        assert result.get("status") == "success"
        assert result.get("frames") == [frame]
    else:
        with pytest.raises(UpstreamToolError, match="requestId") as failure:
            await runner.invoke_generate("ws://localhost", request, 1)
        assert failure.value.frames == (frame,)


def test_new_configuration_save_preserves_explicit_default_group(tmp_path):
    root = tmp_path / "widget_service"
    config_dir = root / "cloud/config"
    config_dir.mkdir(parents=True)
    (config_dir / "config.py").write_text(
        "class Settings:\n    enable_single_step_widget_edit: bool = True\n", encoding="utf-8",
    )
    (config_dir / "default_config.yaml").write_text(
        "enable_single_step_widget_edit: true\n", encoding="utf-8",
    )
    debug_path = tmp_path / "debug_tools/debug_tool.yaml"
    debug_path.parent.mkdir()
    debug_path.write_text(
        "widget_backend:\n  defaults:\n    enable_single_step_widget_edit: false\n",
        encoding="utf-8",
    )
    config = read_configuration(root)
    assert config.values.get("enable_single_step_widget_edit") is False
    assert "enable_single_step_widget_edit" not in config.exposed
    updated = save_configuration(root, {"enable_single_step_widget_edit": True}, config.version)
    assert updated.get("values", {}).get("enable_single_step_widget_edit") is True
    document = yaml.safe_load(debug_path.read_text(encoding="utf-8"))
    assert document.get("widget_backend", {}).get("defaults", {}).get(
        "enable_single_step_widget_edit"
    ) is True


@pytest.mark.asyncio
async def test_real_fusion_pipeline_produces_importable_theme_trace(tmp_path, monkeypatch):
    from api.schemas import GenerateWidgetCardRequest
    from config.config import get_settings
    from custom.a2ui_model_client import A2UIModelClient
    from services.artifact_store import ArtifactStore
    from services.widget_generation_service import WidgetGenerationService

    settings = get_settings()
    monkeypatch.setattr(settings, "enable_generation_trace_recording", True)
    monkeypatch.setattr(settings, "generation_trace_root", tmp_path)
    monkeypatch.setattr(settings, "enable_a2ui_model_mock", True)
    monkeypatch.setattr(settings, "enable_artifact_validation", True)
    monkeypatch.setattr(settings, "enable_photo_background_theme", False)
    monkeypatch.setattr(WidgetGenerationService, "_enable_card_template", lambda self: False)
    monkeypatch.setattr(WidgetGenerationService, "_enable_jsx_generation", lambda self: False)
    source = '\n'.join([
        '["root","Layout",{"layout":"S-center"},["value"]]',
        '["value","DataDisplay",{"label":"静态卡片","value":"就绪","supportingText":"状态"}]',
    ])

    def model(self, profile, prompt):
        return '{"themeId":"gradient-blue"}' if profile.get("format") == "raw-json" else source

    async def save(self, artifact):
        return SimpleNamespace(artifactUrl="mock://trace.md", artifactDigest="sha256:test")

    monkeypatch.setattr(A2UIModelClient, "_load_mock_data", model)
    monkeypatch.setattr(ArtifactStore, "save", save)
    service = WidgetGenerationService()
    response = await service.generate_widget_card_compact_dsl(GenerateWidgetCardRequest(
        uid=UID, prdVer="11.7.7.331", device={"romVersion": "7.0"},
        userQuery="生成一个名为静态卡片的卡片", size="2x2", title="静态卡片",
        description="完整主题 Trace 回归",
    ))
    assert response.status.value == "success"
    view = _finish(service.trace_recorder, None, tmp_path, "success")
    nodes = view.get("nodes")
    assert isinstance(nodes, list)
    theme = next(node for node in nodes if node.get("operation") == "theme")
    final = next(node for node in nodes if node.get("operation") == "artifact.final.built")
    assert theme.get("parentId") == final.get("id")
    assert any(node.get("operation") == "dsl.semantic_layout.expanded" for node in nodes)
