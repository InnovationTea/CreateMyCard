"""双输入复用评分：真实导入/宿主链路、安全边界、证据失效和单卡配对。"""

import base64
import importlib.util
import io
import json
from pathlib import Path

import pytest
from debug_tools.batch_testing.api import register_batch_routes
from debug_tools.batch_testing.postprocess import PostprocessManager
from debug_tools.batch_testing.quality import compare
from debug_tools.batch_testing.quality_import import import_batch
from debug_tools.batch_testing.task_manager import BatchTaskManager
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont
from test_debug_quality_workflow import PLUGINS, save_scores


def module(name):
    spec = importlib.util.spec_from_file_location(name, PLUGINS / "quality-score" / (name + ".py"))
    assert spec is not None and spec.loader is not None
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def payload(dsl=None):
    buffer = io.BytesIO()
    Image.new("RGB", (80, 80), "white").save(buffer, format="PNG")
    actions = [
        {"version": "v0.9", "createSurface": {"surfaceId": "card"}},
        {"version": "v0.9", "updateComponents": {"root": "root", "components": [
            {"id": "root", "component": "Text", "content": "显示天气"},
        ]}},
        {"version": "v0.9", "updateDataModel": {"path": "/", "value": {}}},
    ]
    return {"name": "导入测试", "imageSource": "native", "samples": [{
        "id": "Q001", "query": "显示天气", "size": "2x2",
        "dsl": json.dumps(actions, ensure_ascii=False) if dsl is None else dsl,
        "imageBase64": base64.b64encode(buffer.getvalue()).decode(),
    }]}


def context(root, value):
    summary = import_batch(root, value)
    run = root / summary.get("runId")
    output = run / "test-output"
    output.mkdir()
    return {"sample": summary.get("samples")[0], "runDir": str(run),
            "sampleDir": str(run / "Q001"), "outputDir": str(output)}


def test_import_http_is_explicit_and_keeps_history(tmp_path):
    manager = BatchTaskManager(tmp_path / "datasets", tmp_path / "output",
                               tmp_path / "traces", tmp_path / "cloud")
    app = FastAPI()
    register_batch_routes(app, task_manager=manager)
    client = TestClient(app)
    run_ids = []
    for _ in range(2):
        response = client.post("/debug/batch/quality/import", json=payload())
        assert response.status_code == 200
        run_id = response.json().get("runId")
        run_ids.append(run_id)
        detail = client.get(f"/debug/batch/runs/{run_id}").json()
        assert detail.get("sourceType") == "external-quality"
        assert detail.get("samples")[0].get("status") == "imported"
        assert detail.get("success") == 0
    assert run_ids[0] != run_ids[1]
    assert len(client.get("/debug/batch/runs").json().get("items")) == 2
    assert manager.postprocess_manager.queue.empty()


@pytest.mark.parametrize("bad", ["path", "reserved", "duplicate", "image", "sha", "query"])
def test_bad_import_is_atomic(tmp_path, bad):
    value = payload()
    sample = value.get("samples")[0]
    if bad == "path":
        sample["id"] = "../escape"
    elif bad == "reserved":
        sample["id"] = "CON.json"
    elif bad == "duplicate":
        value.get("samples").append({**sample, "id": "q001"})
    elif bad == "image":
        sample["imageBase64"] = base64.b64encode(b"not an image").decode()
    elif bad == "sha":
        sample["sourceSha256"] = "0" * 64
    else:
        sample["query"] = " "
    with pytest.raises(ValueError):
        import_batch(tmp_path, value)
    assert not list(tmp_path.iterdir())


def test_offline_ocr_clue_and_unavailable_share_model(tmp_path, monkeypatch):
    checker, plugin = module("external"), module("plugin")
    ctx = context(tmp_path, payload())
    monkeypatch.setattr(checker.core, "check_ocr", lambda *_: ["[待复核·文字缺失]天气"])
    findings, evidence, picture, boundary = checker.inspect(ctx)
    result = plugin._score_result(ctx, findings, evidence, picture, boundary)
    assert result.get("facts", {}).get("score") == 100
    assert result.get("facts", {}).get("scoreLow") == 85
    monkeypatch.setattr(checker.core, "check_ocr", lambda *_: ["[检测失败·OCR]ImportError"])
    result = plugin._score_result(ctx, *checker.inspect(ctx))
    assert result.get("facts", {}).get("score") is None
    assert result.get("facts", {}).get("verdict") == "待评"
    (Path(ctx.get("sampleDir")) / "input/genui.jsonl").write_text("changed")
    with pytest.raises(ValueError, match="已变化"):
        checker.inspect(ctx)


@pytest.mark.parametrize("dsl", ['[["root", "Text", {}]]', '[{"version":"v1.0"}]'])
def test_unsupported_protocol_is_pending_not_rejected(tmp_path, dsl):
    result = module("plugin").process_sample(context(tmp_path, payload(dsl)))
    assert result.get("facts", {}).get("score") is None
    assert result.get("facts", {}).get("verdict") == "待评"


@pytest.mark.asyncio
async def test_import_worker_skips_browser_gallery_and_serves_image(tmp_path):
    summary = import_batch(tmp_path, payload("{invalid-json"))
    run_id = summary.get("runId")
    manager = PostprocessManager(tmp_path, PLUGINS)
    await manager.start()
    try:
        execution = manager.enqueue(run_id, ["quality-score"])
        await manager.queue.join()
        execution_id = execution.get("executionId")
        stages = manager.executions(run_id)[0].get("plugins")
        assert [stage.get("id") for stage in stages] == ["quality-score"]
        result = manager.sample_result(run_id, execution_id, "quality-score", "Q001")
        assert result.get("facts", {}).get("score") == 0
        assert result.get("facts", {}).get("verdict") == "输入硬错误淘汰"
        captures = [item for item in result.get("artifacts", []) if item.get("key") == "capture"]
        assert len(captures) == 1
        assert captures[0].get("url", "").startswith("/debug/batch/runs/")
        api_manager = BatchTaskManager(tmp_path / "datasets", tmp_path,
                                       tmp_path / "traces", tmp_path / "cloud")
        app = FastAPI()
        register_batch_routes(app, task_manager=api_manager)
        image = TestClient(app).get(captures[0].get("url"))
        assert image.status_code == 200
        assert image.content.startswith(b"\x89PNG")
        result = compare(manager, run_id, run_id, left_sample_id="Q001", right_sample_id="Q001")
        assert result.get("rows")[0].get("left", {}).get("imageUrl") == captures[0].get("url")
    finally:
        await manager.close()


@pytest.mark.parametrize("mismatch", ["comparisonScope", "appVersion"])
def test_single_different_ids_and_scope_mismatch(tmp_path, mismatch):
    manager = PostprocessManager(tmp_path, PLUGINS)
    save_scores(manager, "before", {"a": 85, "b": 100})
    save_scores(manager, "after", {"c": 100})
    result = compare(manager, "before", "after", left_sample_id="a", right_sample_id="c")
    row = result.get("rows")[0]
    assert row.get("left", {}).get("sampleId") == "a"
    assert row.get("right", {}).get("sampleId") == "c"
    assert row.get("scoreDelta") == row.get("scoreLowDelta") == 15
    assert result.get("left", {}).get("total") == 1
    with pytest.raises(ValueError, match="同时指定"):
        compare(manager, "before", "after", left_sample_id="a")
    with pytest.raises(ValueError, match="对应样本"):
        compare(manager, "before", "after", left_sample_id="missing", right_sample_id="c")
    path = tmp_path / "after/postprocess/exec_1/plugins/quality-score/samples/c/result.json"
    stored = json.loads(path.read_text(encoding="utf-8"))
    for item in stored.get("artifacts", []):
        if item.get("key") == "detail":
            evidence = item.get("data", {}).get("evidence", {})
            if mismatch == "comparisonScope":
                evidence["comparisonScope"] = {"imageSource": "native"}
            else:
                evidence.setdefault("renderContext", {})["appVersion"] = "11.7.7.300"
    path.write_text(json.dumps(stored), encoding="utf-8")
    result = compare(manager, "before", "after", left_sample_id="a", right_sample_id="c")
    assert result.get("rows")[0].get("scoreDelta") is None
    assert result.get("rows")[0].get("alignment") == "evidence-mismatch"


def test_real_ocr_when_local_dependency_and_chinese_font_available(tmp_path):
    """可选的真实 OCR 联调；没有依赖/字库时明确跳过，其余测试不依赖 OCR。"""
    pytest.importorskip("rapidocr_onnxruntime")
    try:
        font = ImageFont.truetype("msyh.ttc", 40)
    except OSError:
        pytest.skip("本机无中文测试字库")
    picture = Image.new("RGB", (500, 160), "white")
    ImageDraw.Draw(picture).text((25, 45), "显示天气", fill="black", font=font)
    buffer = io.BytesIO()
    picture.save(buffer, format="PNG")
    value = payload()
    sample = value.get("samples")[0]
    sample["imageBase64"] = base64.b64encode(buffer.getvalue()).decode()
    sample["expectedIntents"] = []  # 该测试 Query 只有文本展示，无交互需求。
    result = module("plugin").process_sample(context(tmp_path, value))
    assert result.get("facts", {}).get("score") == 100
    assert result.get("facts", {}).get("scoreLow") == 100
    assert result.get("facts", {}).get("verdict") == "范围内未扣分"
