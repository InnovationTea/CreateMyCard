"""数据集迁移、版本快照与共享截图/画廊的业务回归。"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from debug_tools.batch_testing.api import register_batch_routes
from debug_tools.batch_testing.runner import BatchRunManager, discover_datasets
from debug_tools.batch_testing.task_manager import BatchTaskManager
from debug_tools.dataset_metadata import read_version
from debug_tools.postprocess_plugins.device_capture.plugin import _capture_sample
from debug_tools.postprocess_plugins.export_names import sample_stem
from debug_tools.postprocess_plugins.gallery.capture import run_capture
from debug_tools.postprocess_plugins.gallery.plugin import BatchGalleryManager
from debug_tools.postprocess_plugins.gallery.report import run_gallery
from debug_tools.postprocess_plugins.validation_failure_gallery.plugin import (
    ValidationFailureGalleryManager,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _version(number: int = 1) -> dict:
    history = []
    for index in range(1, number + 1):
        history.append(
            {"version": f"v{index}", "update_date": "2026-10-21", "commits": [],
             "changes": ["新增样本" if index == 1 else "替换素材"]}
        )
    return {"current_version": f"v{number}", "update_date": "2026-10-21",
            "history_versions": history}


@pytest.mark.parametrize(
    ("name", "count"), [("open_domain", 55), ("online_updated", 114), ("request_baseline", 88)]
)
def test_migrated_samples_have_independent_versions_and_available_assets(name, count):
    directory = ROOT / "debug_tools/Datasets" / name
    metadata = read_version(directory)
    assert metadata.get("current_version")
    items = discover_datasets(directory)
    assert len(items) == count
    assert all(item.valid for item in items)
    assert "version" not in [item.sample_id for item in items]
    registry = ROOT / "widget_service/cloud/data/capabilities/app-11.7.7.300_rom-7.0"
    assets = json.loads((registry / "asset_capabilities.json").read_text(encoding="utf-8"))
    known = {record.get("id"): record for record in assets}
    for item in items:
        payload = json.loads(item.path.read_text(encoding="utf-8"))
        content = payload.get("content")
        assert isinstance(content, dict)
        candidates = content.get("candidateAssetIds", [])
        assert len(candidates) == len(set(candidates)), item.sample_id
        for asset_id in candidates:
            asset = known.get(asset_id)
            assert isinstance(asset, dict), (item.sample_id, asset_id)
            source = asset.get("src")
            assert isinstance(source, str)
            assert (ROOT / source).is_file()
            assert (ROOT / "debug_tools/a2ui_render/entry/src/main" / source).is_file()


def test_online_dataset_outer_fields_match_business_content():
    directory = ROOT / "debug_tools/Datasets/online_updated"
    removed = {"Q036", "Q112", "Q113", "Q115", "Q117"}
    for sample_id in removed:
        assert not (directory / f"{sample_id}.json").exists()
    for path in directory.glob("Q*.json"):
        document = json.loads(path.read_text(encoding="utf-8"))
        content = document.get("content")
        assert isinstance(content, dict)
        for key in document.keys() & content.keys():
            assert document.get(key) == content.get(key), (path.stem, key)


@pytest.mark.parametrize(
    ("sample_id", "capability_id", "destination", "arguments", "fields"),
    [
        ("Q006", "GetHealthAndSportSummary", "/data/healthSport", {"targetDayOffset": -1}, []),
        ("Q009", "GetCalendarEvents", "/data/calendar", {"futureDays": 1}, []),
        ("Q040", "ViewWeather", "/data/weather", {"prefectureName": "佛山市"}, []),
        ("Q040", "ViewWeather", "/data/weather2", {"prefectureName": "南京市"}, []),
        ("Q022", "GetHealthAndSportSummary", "/data/healthSport", {}, ["/dailySteps"]),
        ("Q037", "ViewWeather", "/data/weather", {},
         ["/current/windLevel", "/daily/0/rainProbabilityPercent"]),
        ("Q075", "GetHealthAndSportSummary", "/data/healthSport", {"targetDayOffset": -1},
         ["/deepSleepDurationText"]),
        ("Q121", "GetPhoneBatteryInfo", "/data/phoneBattery", {},
         ["/batterySOCText", "/chargingStatusDesc"]),
    ],
)
def test_online_dataset_keeps_imported_data_requirements(
    sample_id, capability_id, destination, arguments, fields,
):
    path = ROOT / "debug_tools/Datasets/online_updated" / f"{sample_id}.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    content = document.get("content")
    assert isinstance(content, dict)
    bindings = content.get("candidateDataBindings")
    assert isinstance(bindings, list)
    matches = []
    for binding in bindings:
        if binding.get("capabilityId") != capability_id:
            continue
        if binding.get("writeResultTo") != destination:
            continue
        matches.append(binding)
    assert len(matches) == 1
    binding = matches[0]
    assert binding.get("arguments") == arguments
    actual_fields = binding.get("candidateOutputFields")
    assert isinstance(actual_fields, list)
    assert set(fields).issubset(actual_fields)


@pytest.mark.parametrize(
    ("sample_id", "required"),
    [
        ("Q005", {"asset.emoji_time", "asset.cake_fill"}),
        ("Q017", {"asset.music_fill", "asset.emoji_music"}),
        ("Q037", {"asset.icon_earphone", "asset.emoji_earbud_case_black"}),
    ],
)
def test_online_dataset_preserves_both_versions_icon_choices(sample_id, required):
    path = ROOT / "debug_tools/Datasets/online_updated" / f"{sample_id}.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    content = document.get("content")
    assert isinstance(content, dict)
    candidates = content.get("candidateAssetIds")
    assert isinstance(candidates, list)
    assert required.issubset(candidates)
    assert len(candidates) == len(set(candidates))


@pytest.mark.parametrize("case", ["number", "date", "history", "entry", "duplicate", "fields"])
def test_invalid_version_metadata_is_rejected(tmp_path, case):
    document = _version()
    if case == "number":
        document["current_version"] = "v1.1"
    elif case == "date":
        document["update_date"] = "2026-02-30"
    elif case == "history":
        document["history_versions"] = {}
    elif case == "entry":
        document["history_versions"] = [{"version": "v2"}]
    elif case == "duplicate":
        document = _version(2)
        history = document.get("history_versions")
        assert isinstance(history, list)
        history.append(history[0])
    else:
        document["extra"] = True
    _write(tmp_path / "version.json", document)
    with pytest.raises(ValueError):
        read_version(tmp_path)


@pytest.mark.parametrize("case", ["date", "past_only", "retained_newer", "partial", "empty"])
def test_version_reader_preserves_historical_metadata_without_inference(tmp_path, case):
    document = _version(2)
    history = document.get("history_versions")
    assert isinstance(history, list)
    if case == "date":
        document["update_date"] = "2026-10-22"
    elif case == "past_only":
        document["current_version"] = "v3"
    elif case == "retained_newer":
        document["current_version"] = "v1"
    elif case == "partial":
        document["history_versions"] = [history[1]]
    else:
        document["history_versions"] = []
    path = tmp_path / "version.json"
    _write(path, document)
    original = path.read_bytes()
    assert read_version(tmp_path) == document
    assert path.read_bytes() == original


@pytest.mark.parametrize("broken", ["json", "metadata", "unreadable"])
def test_dataset_api_isolates_metadata_errors_and_keeps_old_runs(
    tmp_path, caplog, monkeypatch, broken,
):
    datasets = tmp_path / "Datasets"
    for name in ("broken", "legacy", "healthy"):
        _write(datasets / name / "Q001.json", {"content": {"userQuery": "天气"}})
    _write(datasets / "healthy/version.json", _version())
    path = datasets / "broken/version.json"
    if broken == "json":
        path.write_text("{", encoding="utf-8")
    else:
        _write(path, {"current_version": "invalid"})
    original = path.read_bytes()
    if broken == "unreadable":
        read_text = Path.read_text

        def guarded_read(file_path, *args, **kwargs):
            if file_path == path:
                raise PermissionError("版本文件不可读")
            return read_text(file_path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", guarded_read)
    output = tmp_path / "output"
    _write(output / "old_run/summary.json", {
        "runId": "old_run", "status": "completed", "datasetId": "20261015_open_domain",
        "samples": [{"id": "Q001", "status": "success"}],
    })
    manager = BatchTaskManager(datasets, output, tmp_path / "trace", tmp_path / "cloud")
    app = FastAPI()
    register_batch_routes(app, task_manager=manager)
    client = TestClient(app)
    response = client.get("/debug/batch/datasets")
    assert response.status_code == 200
    items = response.json().get("items")
    assert isinstance(items, list)
    assert len(items) == 3
    by_name = {item.get("id"): item for item in items}
    failed = by_name.get("broken")
    assert isinstance(failed, dict)
    assert failed.get("versionError")
    assert failed.get("validSampleCount") == 1
    assert "version" not in failed
    healthy = by_name.get("healthy")
    assert isinstance(healthy, dict)
    assert healthy.get("version") == _version()
    legacy = by_name.get("legacy")
    assert isinstance(legacy, dict)
    assert "version" not in legacy and "versionError" not in legacy
    assert "broken" in caplog.text
    assert path.read_bytes() == original
    runs = client.get("/debug/batch/runs")
    assert runs.status_code == 200
    records = runs.json().get("items")
    assert isinstance(records, list)
    assert records[0].get("datasetId") == "20261015_open_domain"
    assert not records[0].get("datasetVersion")
    samples = client.get("/debug/batch/datasets/broken/samples")
    assert samples.status_code == 200


def test_existing_tasks_resolve_old_dataset_names(tmp_path):
    directory = tmp_path / "request_baseline"
    directory.mkdir()
    host = object.__new__(BatchTaskManager)
    host.datasets_root = tmp_path.resolve()
    assert host._dataset_path("20261016_request_baseline") == directory.resolve()
    assert host._dataset_path("request_baseline") == directory.resolve()
    with pytest.raises(KeyError):
        host._dataset_path("../request_baseline")


@pytest.mark.parametrize("kind", ["browser", "device"])
@pytest.mark.asyncio
async def test_shared_capture_and_gallery_keep_dataset_identity(tmp_path, kind):
    run_dir = tmp_path / "run"
    summary = {"datasetId": "20261016_request_baseline", "datasetVersion": _version(),
               "samples": [{"id": "Q001", "query": "天气", "size": "2x2"}]}
    _write(run_dir / "summary.json", summary)
    output = run_dir / "postprocess/exec/plugins" / f"{kind}-capture"
    output.mkdir(parents=True)
    if kind == "browser":
        async def capture(_url, directory):
            (directory / "Q001.png").write_bytes(b"capture")
            return {"items": [{"id": "Q001", "file": "Q001.png", "quality": {}}]}

        host = BatchGalleryManager(tmp_path, "http://localhost/debug", capture=capture)
        result = await run_capture(host, "run", output, {})
        capture_index = json.loads((output / "capture.json").read_text(encoding="utf-8"))
        indexed = capture_index.get("items")
        assert isinstance(indexed, list)
        assert indexed[0].get("file") == "Q0001_request_baseline.png"
    else:
        _write(run_dir / "Q001/result.json", {"finalAttempt": 0})
        _write(run_dir / "Q001/attempt_000/genui.jsonl", {})
        _write(run_dir / "Q001/attempt_000/blocks.json", {"genui": "{}"})

        class Session:
            async def render(self, _genui, _size, card, full, **_kwargs):
                for path in (card, full):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"capture")
                return SimpleNamespace(public=lambda: {})

        sample = await _capture_sample(Session(), run_dir, output, "Q001", "2x2", 0.0)
        result = {"sampleResults": [sample]}
        assert (output / "full/Q0001_request_baseline.png").is_file()
    samples = result.get("sampleResults")
    assert isinstance(samples, list)
    artifacts = samples[0].get("artifacts")
    assert isinstance(artifacts, list)
    for artifact in artifacts:
        relative = artifact.get("path")
        if relative:
            assert "Q0001_request_baseline.png" in relative
            assert (output / relative).is_file()
            artifact["url"] = (
                f"/debug/batch/runs/run/postprocess/exec/assets/{kind}-capture/{relative}"
            )
    gallery_dir = output.parent / f"{kind}-gallery"
    gallery = await run_gallery(
        SimpleNamespace(output_root=tmp_path), kind, "run", gallery_dir, {},
        upstream_results=[{"id": f"{kind}-capture", **result}],
    )
    document = (gallery_dir / f"request_baseline_{kind}_gallery.html").read_text(encoding="utf-8")
    assert "request_baseline · v1" in document
    assert '"id": "Q001"' in document
    assert "data:image/png;base64," in document
    assert gallery.get("status") == "success"
    assert (gallery_dir / "Q0001_request_baseline.png").read_bytes() == b"capture"


def test_failure_screenshot_uses_shareable_name(tmp_path):
    temporary = tmp_path / "temporary"
    temporary.mkdir()
    (temporary / "Q001.png").write_bytes(b"failure capture")
    output = tmp_path / "plugin"
    result = ValidationFailureGalleryManager._persist_captures(
        output, {"items": [{"id": "Q001", "file": "Q001.png"}]}, temporary,
        {"datasetId": "request_baseline"},
    )
    assert (output / "samples/Q001/Q0001_request_baseline.png").is_file()
    assert result.get("Q001", {}).get("file") == "Q0001_request_baseline.png"


@pytest.mark.parametrize("dataset", ["../../outside", "a/b", "a?b", "中文数据集", "x" * 150])
def test_shared_filenames_cannot_escape_output_directory(dataset):
    name = sample_stem("Q001", {"datasetId": dataset})
    assert "/" not in name and "\\" not in name
    assert name != sample_stem("Q001", {"datasetId": dataset + "!"})
    assert name.startswith("Q0001_")


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy", [False, True])
async def test_batch_keeps_original_version_when_dataset_changes(tmp_path, monkeypatch, legacy):
    dataset = tmp_path / "dataset"
    _write(dataset / "Q001.json", {"content": {"userQuery": "天气"}})
    _write(dataset / "version.json", _version())
    manager = BatchRunManager(dataset, tmp_path / "output", tmp_path / "trace", tmp_path / "cloud")

    async def execute(_state, _available):
        await asyncio.sleep(0)

    monkeypatch.setattr(manager, "_execute_run", execute)
    state = manager.start_run(["Q001"], "ws://localhost/tool", 1, 0, dataset_id="example")
    run_id = state.get("runId")
    assert isinstance(run_id, str)
    pending = manager.tasks.get(run_id)
    assert pending is not None
    await pending
    run_dir = tmp_path / "output" / run_id
    snapshot = json.loads((run_dir / "dataset_version.json").read_text(encoding="utf-8"))
    assert snapshot == _version()
    _write(dataset / "version.json", _version(2))
    summary_path = run_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["status"] = "interrupted"
    if legacy:
        summary.pop("datasetVersion", None)
        (run_dir / "dataset_version.json").unlink()
    _write(summary_path, summary)
    continued = manager.continue_run(
        run_id, "ws://localhost/tool", dataset_root=dataset,
        service_status="external", request_overrides={},
    )
    pending = manager.tasks.get(run_id)
    assert pending is not None
    await pending
    if legacy:
        assert continued.get("datasetVersion") == {}
        assert not (run_dir / "dataset_version.json").exists()
    else:
        assert continued.get("datasetVersion") == _version()
        stored = json.loads((run_dir / "dataset_version.json").read_text(encoding="utf-8"))
        assert stored == snapshot


@pytest.mark.asyncio
async def test_legacy_browser_routes_read_new_and_existing_artifacts(tmp_path):
    run_dir = tmp_path / "run"
    _write(run_dir / "summary.json", {
        "datasetId": "request_baseline", "samples": [{"id": "Q001", "query": "天气"}],
    })

    async def capture(_url, directory):
        (directory / "Q001.png").write_bytes(b"legacy browser capture")
        return {"items": [{"id": "Q001", "file": "Q001.png"}]}

    manager = BatchGalleryManager(tmp_path, "http://localhost/debug", capture=capture)
    manager.start("run")
    pending = manager.tasks.get("run")
    assert pending is not None
    await pending
    assert manager.status("run").get("status") == "ready"
    gallery = manager.gallery_path("run")
    assert gallery.name == "request_baseline_browser_gallery.html"
    assert "request_baseline" in gallery.read_text(encoding="utf-8")
    image = manager.capture_path("run", "Q001")
    assert image.name == "Q0001_request_baseline.png"
    image.rename(image.with_name("Q001.png"))
    gallery.rename(gallery.with_name("gallery.html"))
    assert manager.capture_path("run", "Q001").read_bytes() == b"legacy browser capture"
    assert manager.gallery_path("run").name == "gallery.html"
