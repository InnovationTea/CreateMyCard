from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
from debug_tools.batch_testing.postprocess import PostprocessManager
from debug_tools.postprocess_plugins.gallery.plugin import BatchGalleryManager, run_builtin

PLUGIN_DIR = Path(__file__).resolve().parents[1] / "debug_tools/postprocess_plugins/quality-score"
SPEC = importlib.util.spec_from_file_location("quality_plugin_test", PLUGIN_DIR / "plugin.py")
assert SPEC is not None and SPEC.loader is not None
plugin = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(plugin)


def make_context(tmp_path: Path, findings: list | None = None) -> dict:
    attempt = tmp_path / "run" / "Q001" / "attempt_000"
    attempt.mkdir(parents=True)
    source = '["root","Text",{"content":"文字"}]\n'
    (attempt / "genui.jsonl").write_text(source, encoding="utf-8", newline="\n")
    image = tmp_path / "run" / "capture.png"
    # 最小 PNG 文件只用于文件配对单测；浏览器测试另外产出真实截图。
    image.write_bytes(b"test image bytes")
    output = tmp_path / "run" / "score"
    output.mkdir()
    evidence = {
        "schemaVersion": "web-quality-v1",
        "complete": True,
        "sourceSha256": hashlib.sha256(source.encode()).hexdigest(),
        "renderContext": {"query": "显示文字", "size": "2x2", "blocks": None},
        "imageRunPath": "capture.png",
        "imageSha256": hashlib.sha256(image.read_bytes()).hexdigest(),
        "findings": findings or [],
        "parseWarnings": [],
        "coverage": [
            "text-clipping",
            "card-boundary",
            "text-overlap-candidates",
            "image-loading",
            "parser-warnings",
        ],
    }
    return {
        "apiVersion": "batch-postprocess-v2",
        "runDir": str(tmp_path / "run"),
        "sample": {"id": "Q001", "query": "显示文字", "size": "2x2"},
        "finalAttemptDir": str(attempt),
        "outputDir": str(output),
        "upstreamResults": [
            {
                "pluginId": "browser-gallery",
                "result": {
                    "artifacts": [{"key": "web-quality-evidence", "data": evidence}],
                },
            }
        ],
    }


def test_clean_scoped_score_and_manifest(tmp_path: Path) -> None:
    result = plugin.process_sample(make_context(tmp_path))
    assert result.get("facts", {}).get("score") == 100
    assert "训练验收" in result.get("summary", "")
    manifest = json.loads((PLUGIN_DIR / "plugin.json").read_text(encoding="utf-8"))
    PostprocessManager._validate_manifest(manifest, PLUGIN_DIR)
    normalized = PostprocessManager._normalize_result(
        result,
        manifest=manifest,
        scope="sample",
        asset_root=tmp_path / "run/score",
        asset_base_url="/test-assets",
    )
    assert normalized.get("status") == "success"


@pytest.mark.parametrize(
    "mutation", ["missing", "source", "context", "image", "path", "incomplete", "empty-proof"]
)
def test_missing_and_stale_never_get_full_score(tmp_path: Path, mutation: str) -> None:
    context = make_context(tmp_path)
    evidence = plugin._evidence(context)
    assert evidence is not None
    if mutation == "missing":
        context["upstreamResults"] = []
    elif mutation == "source":
        evidence["sourceSha256"] = "outdated"
    elif mutation == "context":
        evidence["renderContext"] = {}
    elif mutation == "image":
        evidence["imageSha256"] = "outdated"
    elif mutation == "path":
        evidence["imageRunPath"] = "missing.png"
    elif mutation == "incomplete":
        evidence["complete"] = False
    else:
        evidence.pop("coverage")
    result = plugin.process_sample(context)
    assert result.get("facts", {}).get("score") is None


def test_dedupe_and_uncertainty(tmp_path: Path) -> None:
    finding = {
        "rule_id": "GEOMETRY.CLIP_TEXT",
        "severity": "P1",
        "evidence_type": "程序已证实",
        "components": ["title"],
    }
    result = plugin.process_sample(make_context(tmp_path, [finding, finding]))
    assert result.get("facts", {}).get("score") == 85
    assert result.get("facts", {}).get("confirmed") == 1
    normalized = plugin.model.normalize({**finding, "evidence_type": "待确认"}, "test")
    assert plugin.model.score([normalized]).get("range") == [85, 100]


def test_render_failure_is_quality_reject_not_plugin_failure(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    evidence = plugin._evidence(context)
    assert evidence is not None
    evidence.update({"renderFailed": True, "complete": False})
    result = plugin.process_sample(context)
    assert result.get("status") == "success"
    assert result.get("facts", {}).get("score") == 0
    assert result.get("facts", {}).get("verdict") == "Web渲染淘汰"


def test_phone_exemption_and_unknown_rules() -> None:
    exempt = plugin.model.normalize({"code": "event.phone_target_unresolved"}, "test")
    assert plugin.model.score([exempt]).get("score") == 100
    unknown = plugin.model.normalize({"code": "new.unknown"}, "test")
    assert plugin.model.score([unknown]).get("score") is None


def test_paths_cannot_escape_run(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    evidence = plugin._evidence(context)
    assert evidence is not None
    evidence["imageRunPath"] = "../outside.png"
    with pytest.raises(ValueError, match="越过"):
        plugin.process_sample(context)


def test_dataset_keeps_unknown_and_zero_separate() -> None:
    result = plugin.process_dataset(
        {
            "sampleResults": [
                {"sampleId": "a", "facts": {"score": 100, "scoreLow": 100}},
                {"sampleId": "b", "facts": {"score": 0, "scoreLow": 0, "verdict": "Web渲染淘汰"}},
                {"sampleId": "c", "facts": {"score": None, "scoreLow": None}},
            ]
        }
    )
    assert result.get("facts") == {"total": 3, "scored": 2, "pending": 1, "rejected": 1}


def test_real_worker_imports_from_arbitrary_output_directory(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    context_path, output_path = tmp_path / "context.json", tmp_path / "result.json"
    context_path.write_text(json.dumps(context, ensure_ascii=False), encoding="utf-8")
    worker = PLUGIN_DIR.parents[1] / "batch_testing/plugin_worker.py"
    subprocess.run(
        [
            sys.executable,
            str(worker),
            "--entrypoint",
            str(PLUGIN_DIR / "plugin.py"),
            "--hook",
            "process_sample",
            "--context",
            str(context_path),
            "--result",
            str(output_path),
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    result = json.loads(output_path.read_text(encoding="utf-8"))
    assert result.get("facts", {}).get("score") == 100


@pytest.mark.asyncio
async def test_gallery_keeps_quality_and_history_image(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "summary.json").write_text(
        json.dumps({"runId": "run", "samples": [{"id": "Q001"}]}), encoding="utf-8"
    )

    async def capture(_url: str, output: Path) -> dict:
        (output / "1.png").write_bytes(b"first image")
        return {
            "items": [
                {"id": "Q001", "file": "1.png", "quality": {"schemaVersion": "web-quality-v1"}}
            ]
        }

    manager = BatchGalleryManager(tmp_path, "http://localhost/debug", capture=capture)
    output = run_dir / "postprocess/one/plugins/browser-gallery"
    output.mkdir(parents=True)
    result = await run_builtin(manager, "run", output, {})
    sample = result.get("sampleResults", [])[0]
    assert any(x.get("key") == "web-quality-evidence" for x in sample.get("artifacts", []))
    manager.capture_path("run", "Q001").write_bytes(b"second image")
    assert (output / "Q001.png").read_bytes() == b"first image"
    manifest = json.loads((PLUGIN_DIR.parent / "gallery/plugin.json").read_text(encoding="utf-8"))
    PostprocessManager._normalize_stage("browser-gallery", result, manifest)


@pytest.mark.asyncio
async def test_host_runs_browser_dependency_and_scores_without_new_frontend(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    sample = context.get("sample")
    assert isinstance(sample, dict)
    run_dir = tmp_path / "run"
    (run_dir / "summary.json").write_text(
        json.dumps({"runId": "run", "status": "completed", "samples": [sample]}),
        encoding="utf-8",
    )
    (run_dir / "Q001/result.json").write_text('{"finalAttempt":0}', encoding="utf-8")
    evidence = plugin._evidence(context)

    async def capture(_url: str, output: Path) -> dict:
        (output / "1.png").write_bytes(b"test image bytes")
        return {"items": [{"id": "Q001", "file": "1.png", "quality": evidence}]}

    gallery = BatchGalleryManager(tmp_path, "http://localhost/debug", capture=capture)

    async def builtin(run_id: str, output: Path, config: dict) -> dict:
        return await run_builtin(gallery, run_id, output, config)

    manager = PostprocessManager(
        tmp_path, PLUGIN_DIR.parent, builtin_runners={"browser-gallery": builtin}
    )
    await manager.start()
    try:
        state = manager.enqueue("run", ["quality-score"])
        await manager.queue.join()
        execution = state.get("executionId")
        assert isinstance(execution, str)
        result = manager.sample_result("run", execution, "quality-score", "Q001")
        assert result.get("facts", {}).get("score") == 100
        artifacts = result.get("artifacts", [])
        capture_artifact = next(x for x in artifacts if x.get("key") == "capture")
        assert capture_artifact.get("url", "").endswith("/samples/Q001/card.png")
    finally:
        await manager.close()
