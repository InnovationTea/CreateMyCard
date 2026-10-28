"""正式 WebSocket 入口的脚本→复检→模型→保存回归；仅替换模型及主题阶段。"""

import json

import pytest
from compact_script_helpers import example
from config.config import get_settings
from custom.a2ui_model_client import A2UIModelClient
from debug_tools.batch_testing.trace_parser import TraceImporter
from fastapi.testclient import TestClient
from services import artifact_store
from services.prompt_builder import PromptBuilder
from services.widget_generation_service import WidgetGenerationService
from test_compact_dsl_interface_retry_routes import final_result
from test_compact_script_repair import broken_height
from test_tool_dispatch_routes import (
    DEVICE_INFO,
    _receive_frames_until_final,
    _request_id,
    _tool_payload,
    app,
)
from utils.upload_file_obs import UploadFileOSMS


@pytest.mark.parametrize("limit,repairs", [(12, 0), (1, 1), (0, 1), (1, 2)])
def test_error_script_then_original_model_chain(
    tmp_path,
    monkeypatch,
    existing_generation_policy,
    isolated_theme_stage,
    limit,
    repairs,
):
    settings = get_settings()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    for key, value in {
        "WORKSPACE_ROOT": workspace,
        "enable_generation_trace_recording": True,
        "generation_trace_root": tmp_path / "traces",
        "enable_a2ui_model_mock": True,
        "enable_artifact_validation": True,
        "enable_validation_failure_retry": True,
        "validation_failure_max_repair_attempts": 2,
        "enable_compact_script_repair": True,
        "compact_script_max_candidates": limit,
    }.items():
        monkeypatch.setattr(settings, key, value)
    for method in ("_enable_card_template", "_enable_jsx_generation"):
        monkeypatch.setattr(WidgetGenerationService, method, staticmethod(lambda: False))
    monkeypatch.setattr(
        artifact_store,
        "file_obs",
        UploadFileOSMS(
            base_url="https://artifact.test",
            mock_storage_dir=tmp_path / "mock_obs",
        ),
    )
    phases = []
    repair_inputs = []
    real_build = PromptBuilder.build_repair

    def build_repair(self, active, source, errors, **kwargs):
        repair_inputs.append((source, errors))
        return real_build(self, active, source, errors, **kwargs)

    async def generate(_client, _prompt, *_args, phase="initial", **_kwargs):
        phases.append(phase)
        if repairs == 2 and phase == "repair" and phases.count("repair") == 1:
            return broken_height(both=True)
        return example("会议") if phase == "repair" else broken_height(both=True)

    monkeypatch.setattr(PromptBuilder, "build_repair", build_repair)
    monkeypatch.setattr(A2UIModelClient, "generate", generate)
    content = {
        "uid": "create-STATIC01-00001-000",
        "userQuery": "展示两组静态文字",
        "title": "静态修复",
        "description": "容器空间不足",
        "size": "2x4",
        "romVersion": "7.0",
    }
    interaction = "static-error-first"
    device = {**DEVICE_INFO, "prdVer": "11.7.7.300", "romVersion": "7.0"}
    with TestClient(app).websocket_connect("/api/v1/ws/tools/generateWidgetCardCompactDsl") as ws:
        ws.send_json(_tool_payload(content, interaction, device_info=device))
        frames = _receive_frames_until_final(ws, _request_id(interaction))
    assert final_result(frames).get("status") == "success"
    assert phases.count("repair") == repairs
    assert len(list(workspace.glob("artifact_*.md"))) == 1
    view = TraceImporter(tmp_path / "traces").read("create-STATIC01-00001-000")
    nodes = view.get("nodes")
    assert isinstance(nodes, list)
    candidates = [node for node in nodes if node.get("operation") == "compact.script.candidate"]
    assert len(candidates) <= limit
    if limit:
        assert candidates
    if limit == 1:
        source, errors = repair_inputs[0]
        props = {}
        for line in source.splitlines():
            row = json.loads(line)
            if len(row) >= 3:
                props[row[0]] = row[2]
        assert props.get("left", {}).get("height") == 40
        assert props.get("right", {}).get("height") == 20
        assert len(errors) == 1
        assert errors[0].get("compactDiagnostics")[0].get("componentId") == "right"
