from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml
from debug_tools.batch_testing.postprocess import PostprocessManager
from debug_tools.device_debug.api import register_device_routes
from debug_tools.device_debug.commands import DeviceError
from debug_tools.device_debug.config import Config
from debug_tools.device_debug.devices import Devices, Target
from debug_tools.device_debug.jobs import Jobs
from debug_tools.device_debug.runner import (
    CropPx,
    RenderProject,
    RenderSession,
    parse_terminal_events,
    validate_crop,
)
from debug_tools.postprocess_plugins.device_capture import DeviceCaptureManager, run_builtin
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image


def _config(tmp_path: Path) -> Config:
    project = Path(__file__).resolve().parents[2] / "debug_tools/a2ui_render"
    return Config(
        hdc=tmp_path / "hdc",
        project=project,
        sdk=tmp_path / "sdk",
        java=tmp_path / "java",
        node=tmp_path / "node",
        hvigor=tmp_path / "hvigor",
        ohpm=tmp_path / "ohpm",
        emulator=tmp_path / "emulator",
        instances=tmp_path / "instances",
        images=tmp_path / "images",
        output=tmp_path / "output",
        render_timeout=1.0,
        capture_attempts=2,
        start_timeout=0.2,
        start_poll=0.01,
    )


def test_terminal_log_parser_keeps_warning_state_and_crop() -> None:
    text = "noise\nA2UI_RUN " + json.dumps(
        {
            "runId": "run-one",
            "state": "READY_WITH_WARNINGS",
            "warnings": ["unknown property"],
            "cropPx": {"left": 10, "top": 20, "width": 150, "height": 150},
        }
    )
    event = parse_terminal_events(text, "run-one")[-1]
    assert event.state == "READY_WITH_WARNINGS"
    assert event.warnings == ["unknown property"]
    assert event.crop == CropPx(10, 20, 150, 150)


@pytest.mark.parametrize(
    "crop",
    [CropPx(-1, 0, 10, 10), CropPx(0, 0, 0, 10), CropPx(90, 0, 11, 10)],
)
def test_crop_validation_rejects_invalid_or_out_of_bounds_crop(crop: CropPx) -> None:
    with pytest.raises(DeviceError):
        validate_crop(crop, 100, 100)


def test_hap_selection_requires_signed_build_for_physical_target(tmp_path: Path) -> None:
    config = _config(tmp_path)
    project = RenderProject(config)
    project.path = tmp_path / "project"
    output = project.path / "entry/build/default/outputs/default"
    output.mkdir(parents=True, exist_ok=True)
    unsigned = output / "entry-default-unsigned.hap"
    unsigned.write_bytes(b"unsigned")
    with pytest.raises(DeviceError, match="signed HAP"):
        project._select_hap("physical")
    assert project._select_hap("emulator") == unsigned
    unsigned.unlink()


def test_build_cache_matches_content_fingerprint_and_target_type(tmp_path: Path) -> None:
    project = RenderProject(_config(tmp_path))
    project.path = tmp_path / "project"
    hap = project.path / "entry/build/default/outputs/default/entry-default-unsigned.hap"
    hap.parent.mkdir(parents=True)
    hap.write_bytes(b"hap")
    marker = project.path / ".hvigor/debug-tools-build.json"
    marker.parent.mkdir(parents=True)
    marker.write_text(
        json.dumps({"fingerprint": "fingerprint", "hap": str(hap)}),
        encoding="utf-8",
    )
    assert project._cached_hap("emulator", "fingerprint") == hap
    assert project._cached_hap("emulator", "changed") is None
    assert project._cached_hap("physical", "fingerprint") is None


@pytest.mark.asyncio
async def test_local_emulator_start_waits_for_matching_hdc_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)
    instance = config.instances / "PuraX"
    image = config.images / "PuraX"
    instance.mkdir(parents=True)
    image.mkdir(parents=True)
    (image / "system.img").write_bytes(b"image")
    (instance / "hardware-qemu.ini").write_text("hw.hdc.port = notset\n", encoding="utf-8")
    (config.instances / "lists.json").write_text(
        json.dumps([{"name": "Pura X", "path": str(instance), "imageDir": "PuraX"}]),
        encoding="utf-8",
    )
    config.emulator.write_bytes(b"executable")
    target = Target("emulator-target", "127.0.0.1:5555", "Pura X", "emulator")
    refresh_count = 0

    async def refresh(self: Devices) -> list[Target]:
        nonlocal refresh_count
        refresh_count += 1
        values = [] if refresh_count == 1 else [target]
        self.targets = {item.id: item for item in values}
        return values

    monkeypatch.setattr(Devices, "refresh", refresh)
    monkeypatch.setattr(Devices, "_is_running", lambda _self, _emulator: True)
    devices = Devices(config)
    emulator = devices.emulators()[0]
    operation = await devices.start(emulator.id)
    assert operation["status"] == "running"
    await asyncio.wait_for(asyncio.gather(*devices.launch_tasks), timeout=1.0)
    assert operation["status"] == "success"
    assert operation["targetId"] == target.id
    assert operation["serial"] == target.serial


class FakeDevices:
    def __init__(self, target: Target) -> None:
        self.current = target
        self.calls: list[list[str]] = []

    async def target(self, _target_id: str) -> Target:
        return self.current

    async def hdc(self, _serial: str, args: list[str], **_kwargs: Any) -> str:
        self.calls.append(args)
        if args[:3] == ["shell", "hilog", "-x"]:
            run_id = args[args.index("-e") + 1]
            return "A2UI_RUN " + json.dumps(
                {
                    "runId": run_id,
                    "state": "READY",
                    "cropPx": {"left": 100, "top": 250, "width": 150, "height": 150},
                }
            )
        if args[:4] == ["shell", "aa", "dump", "-a"]:
            return "mission name com.example.myapplication state #FOREGROUND"
        if args[:2] == ["file", "recv"]:
            destination = Path(args[-1])
            destination.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (500, 700), "white").save(destination, format="JPEG")
        return "success"


class ChunkFallbackDevices(FakeDevices):
    async def hdc(self, _serial: str, args: list[str], **_kwargs: Any) -> str:
        self.calls.append(args)
        if args[:4] == ["shell", "-b", "com.example.myapplication", "pwd"]:
            return "[Fail][E003001] Invalid bundle name: com.example.myapplication"
        return "success"


class LockedThenReadyDevices(FakeDevices):
    def __init__(self, target: Target) -> None:
        super().__init__(target)
        self.start_attempts = 0

    async def hdc(self, _serial: str, args: list[str], **_kwargs: Any) -> str:
        self.calls.append(args)
        if args[:3] == ["shell", "aa", "start"]:
            self.start_attempts += 1
            if self.start_attempts == 1:
                return (
                    "error: failed to start ability.\n"
                    "Error Code:10106102 Error Message:The device screen is locked"
                )
        return "success"


@pytest.mark.asyncio
async def test_one_session_installs_once_and_renders_mixed_samples(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = Target("target", "serial", "emulator", "emulator")
    devices = FakeDevices(target)
    hap = tmp_path / "entry-default-unsigned.hap"
    hap.write_bytes(b"hap")

    async def build(_self: RenderProject, _kind: str, _log: Path) -> Path:
        return hap

    monkeypatch.setattr(RenderProject, "build", build)
    source = tmp_path / "sample.jsonl"
    source.write_text("{}\n", encoding="utf-8")
    session = RenderSession(_config(tmp_path), devices, target, tmp_path / "device.log")  # type: ignore[arg-type]
    async with session:
        first = await session.render(source, "2x2", tmp_path / "one.png", tmp_path / "one-full.png")
        second = await session.render(
            source,
            "2x4",
            tmp_path / "two.png",
            tmp_path / "two-full.png",
        )
    installs = [args for args in devices.calls if args[:2] == ["install", "-r"]]
    sends = [args for args in devices.calls if args[:2] == ["file", "send"]]
    assert len(installs) == 1
    assert len(sends) == 2
    assert first.card_path.is_file() and second.card_path.is_file()
    assert Image.open(first.card_path).size == (150, 150)


@pytest.mark.asyncio
async def test_unsigned_emulator_falls_back_to_chunked_ability_transfer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = Target("target", "serial", "emulator", "emulator")
    devices = ChunkFallbackDevices(target)
    hap = tmp_path / "entry-default-unsigned.hap"
    hap.write_bytes(b"hap")

    async def build(_self: RenderProject, _kind: str, _log: Path) -> Path:
        return hap

    monkeypatch.setattr(RenderProject, "build", build)
    source = tmp_path / "sample.jsonl"
    source.write_text('{"text":"设备分块传输"}\n', encoding="utf-8")
    session = RenderSession(_config(tmp_path), devices, target, tmp_path / "device.log")  # type: ignore[arg-type]
    async with session:
        assert session._sandbox_transport is False
        parameters = session._parameters("run-id", "run-id.json", 150, 150)
        await session._send_sample_chunks(source, parameters)

    sends = [args for args in devices.calls if args[:2] == ["file", "send"]]
    chunk_starts = [
        args
        for args in devices.calls
        if args[:3] == ["shell", "aa", "start"] and "sampleChunk" in args
    ]
    assert sends == []
    assert chunk_starts
    encoded_chunks = [args[args.index("sampleChunk") + 1] for args in chunk_starts]
    decoded = base64.b64decode("".join(encoded_chunks))
    assert decoded == source.read_bytes()


def test_hdc_reported_failure_is_not_treated_as_success() -> None:
    with pytest.raises(DeviceError, match="启动 A2UI_Render Ability失败"):
        RenderSession._require_hdc_success(
            "Error Code:10106102 device screen is locked",
            "启动 A2UI_Render Ability",
        )


@pytest.mark.asyncio
async def test_locked_screen_start_waits_for_auto_unlock_and_retries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = Target("target", "serial", "emulator", "emulator")
    devices = LockedThenReadyDevices(target)
    monkeypatch.setattr(
        "debug_tools.device_debug.runner.LOCKED_START_RETRY_DELAYS",
        (0.0,),
    )
    messages: list[str] = []
    session = RenderSession(
        _config(tmp_path),
        devices,  # type: ignore[arg-type]
        target,
        tmp_path / "device.log",
        messages.append,
    )
    await session._start_app([])
    assert devices.start_attempts == 2
    assert messages == ["设备屏幕锁定，等待自动解锁后重试（1/1）"]


@dataclass
class FakeCapture:
    sample_id: str
    card_path: Path
    full_path: Path

    def public(self) -> dict[str, Any]:
        return {
            "deviceRunId": self.sample_id,
            "terminal": "READY_WITH_WARNINGS" if self.sample_id == "Q001" else "READY",
            "warnings": ["warning"] if self.sample_id == "Q001" else [],
            "cropPx": {"left": 0, "top": 0, "width": 10, "height": 10},
        }


class FakeSession:
    def __init__(self) -> None:
        self.rendered: list[tuple[str, str]] = []
        self.capture_delays: list[float] = []

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, *_args: Any) -> None:
        return None

    async def render(
        self, source: Path, size: str, card: Path, full: Path, *,
        capture_delay_seconds: float = 0.0,
    ) -> FakeCapture:
        sample_id = source.parents[1].name
        self.rendered.append((sample_id, size))
        self.capture_delays.append(capture_delay_seconds)
        if sample_id == "Q002":
            raise RuntimeError("设备断开")
        card.parent.mkdir(parents=True, exist_ok=True)
        full.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (10, 10), "blue").save(card)
        Image.new("RGB", (20, 20), "white").save(full)
        return FakeCapture(sample_id, card, full)


class FakeRenderer:
    def __init__(self, session: FakeSession) -> None:
        self.value = session
        self.session_count = 0

    async def session(self, _target_id: str, _log: Path) -> FakeSession:
        self.session_count += 1
        return self.value


def _write_run(output_root: Path, run_id: str) -> None:
    run_dir = output_root / run_id
    samples = []
    for index, sample_id in enumerate(("Q001", "Q002", "Q003")):
        size = "2x4" if index == 2 else "2x2"
        samples.append({"id": sample_id, "size": size, "query": f"制作 {size} 卡片"})
        attempt = run_dir / sample_id / "attempt_000"
        attempt.mkdir(parents=True)
        (run_dir / sample_id / "result.json").write_text(
            json.dumps({"finalAttempt": 0}), encoding="utf-8"
        )
        (attempt / "genui.jsonl").write_text("{}\n", encoding="utf-8")
    (run_dir / "summary.json").write_text(
        json.dumps({"runId": run_id, "samples": samples}), encoding="utf-8"
    )


@pytest.mark.asyncio
async def test_plugin_uses_one_session_and_isolates_sample_failure(tmp_path: Path) -> None:
    run_id = "batch_20261013_000000_deadbeef"
    _write_run(tmp_path, run_id)
    session = FakeSession()
    renderer = FakeRenderer(session)
    manager = DeviceCaptureManager(tmp_path, renderer=renderer)
    checkpoints: list[dict[str, Any]] = []
    result = await run_builtin(
        manager,
        run_id,
        tmp_path / "v2",
        {"targetId": "target-one"},
        checkpoints.append,
    )
    assert renderer.session_count == 1
    assert session.rendered == [("Q001", "2x2"), ("Q002", "2x2"), ("Q003", "2x4")]
    assert session.capture_delays == [1.0, 1.0, 1.0]
    assert [item.get("status") for item in result["sampleResults"]] == [
        "success",
        "failed",
        "success",
    ]
    assert result["datasetResult"]["facts"]["warningSamples"] == 1
    assert len(checkpoints) == 3
    assert not (tmp_path / "v2/gallery.html").exists()


@pytest.mark.asyncio
async def test_plugin_requires_target_id(tmp_path: Path) -> None:
    run_id = "batch_20261013_000000_deadbeef"
    _write_run(tmp_path, run_id)
    manager = DeviceCaptureManager(tmp_path, renderer=FakeRenderer(FakeSession()))
    with pytest.raises(ValueError, match="在线设备"):
        await run_builtin(manager, run_id, tmp_path / "v2", {})


@pytest.mark.asyncio
@pytest.mark.parametrize("delay", [0.0, 0.5, 30.0])
async def test_plugin_passes_configured_delay_to_each_sample(tmp_path: Path, delay: float) -> None:
    _write_run(tmp_path, "run_delay")
    session = FakeSession()
    manager = DeviceCaptureManager(tmp_path, renderer=FakeRenderer(session))
    manager.config = replace(_config(tmp_path), capture_delay_seconds=delay)
    result = await run_builtin(
        manager, "run_delay", tmp_path / "capture",
        {"targetId": "target", "captureDelaySeconds": 2},
    )
    assert session.capture_delays == [delay, delay, delay]
    samples = result.get("sampleResults")
    assert isinstance(samples, list)
    first = samples[0]
    assert first.get("facts", {}).get("captureDelaySeconds") == delay
    artifacts = first.get("artifacts")
    assert isinstance(artifacts, list)
    assert artifacts[0].get("data", {}).get("captureDelaySeconds") == delay


@pytest.mark.asyncio
@pytest.mark.parametrize("delay", [-1, 31, "2", True, float("nan"), float("inf")])
async def test_config_rejects_invalid_delay_before_opening_device(
    tmp_path: Path, delay: Any
) -> None:
    config_path = tmp_path / "debug_tool.yaml"

    config_path.write_text(yaml.safe_dump({"platform": {"device_capture": {
        "capture_delay_seconds": delay,
    }}}), encoding="utf-8")
    with pytest.raises(DeviceError, match="0 到 30"):
        Config.load(config_path)


@pytest.mark.parametrize("delay", [None, 0.0, 1.5, 30.0])
def test_config_loads_capture_delay_from_yaml(tmp_path: Path, monkeypatch, delay):
    paths = _config(tmp_path)
    toolchain = SimpleNamespace(
        hdc=paths.hdc, sdk_home=paths.sdk, java_home=paths.java,
        node_executable=paths.node, hvigor=paths.hvigor, ohpm=paths.ohpm,
        emulator=paths.emulator, path_variables={}, node_source="configured",
    )
    monkeypatch.setattr("debug_tools.device_debug.config.load_toolchain", lambda _path: toolchain)
    values: dict[str, Any] = {
        "emulator_instance_root": str(paths.instances),
        "emulator_image_root": str(paths.images),
        "output_root": str(paths.output),
    }
    if delay is not None:
        values["capture_delay_seconds"] = delay
    config_path = tmp_path / "debug_tool.yaml"

    config_path.write_text(
        yaml.safe_dump({"platform": {"device_capture": values}}), encoding="utf-8"
    )
    loaded = Config.load(config_path)
    assert loaded.capture_delay_seconds == (1.0 if delay is None else delay)


@pytest.mark.asyncio
@pytest.mark.parametrize("delay", [0.0, 1.5])
@pytest.mark.parametrize("retry_capture", [False, True])
async def test_session_waits_after_ready_before_snapshot(
    tmp_path: Path, monkeypatch, delay: float, retry_capture: bool
):
    target = Target("target", "serial", "emulator", "emulator")
    devices = FakeDevices(target)

    async def sleep(seconds):
        devices.calls.append(["test-sleep", str(seconds)])

    monkeypatch.setattr("debug_tools.device_debug.runner.asyncio.sleep", sleep)
    session = RenderSession(_config(tmp_path), devices, target, tmp_path / "device.log")
    session._prepared = True
    if retry_capture:
        guard_results = iter([False, True])
        monkeypatch.setattr(session, "_white_guard", lambda _path: next(guard_results))
    source = tmp_path / "sample.jsonl"
    source.write_text("{}\n", encoding="utf-8")
    await session.render(
        source, "2x2", tmp_path / "card.png", tmp_path / "full.png", capture_delay_seconds=delay
    )
    snapshot_indices = [
        index for index, args in enumerate(devices.calls)
        if args[:2] == ["shell", "snapshot_display"]
    ]
    assert len(snapshot_indices) == (2 if retry_capture else 1)
    if delay > 0:
        for snapshot_index in snapshot_indices:
            assert devices.calls[snapshot_index - 1] == ["test-sleep", str(delay)]
            assert devices.calls[snapshot_index - 2][:4] == ["shell", "aa", "dump", "-a"]
    else:
        assert ["test-sleep", "0.0"] not in devices.calls


@pytest.mark.asyncio
async def test_cancel_during_capture_delay_does_not_take_snapshot(tmp_path: Path, monkeypatch):
    target = Target("target", "serial", "emulator", "emulator")
    devices = FakeDevices(target)

    async def sleep(seconds):
        if seconds == 2.5:
            raise asyncio.CancelledError

    monkeypatch.setattr("debug_tools.device_debug.runner.asyncio.sleep", sleep)
    session = RenderSession(_config(tmp_path), devices, target, tmp_path / "device.log")
    session._prepared = True
    source = tmp_path / "sample.jsonl"
    source.write_text("{}\n", encoding="utf-8")
    with pytest.raises(asyncio.CancelledError):
        await session.render(
            source, "2x2", tmp_path / "card.png", tmp_path / "full.png", capture_delay_seconds=2.5
        )
    assert not any(args[:2] == ["shell", "snapshot_display"] for args in devices.calls)


@pytest.mark.asyncio
async def test_capture_metadata_passes_checkpoint_and_final_host_validation(tmp_path: Path) -> None:
    run_id = "batch_20261013_000000_deadbeef"
    _write_run(tmp_path, run_id)
    manager = DeviceCaptureManager(tmp_path, renderer=FakeRenderer(FakeSession()))
    plugin_dir = (
        Path(__file__).resolve().parents[2] / "debug_tools/postprocess_plugins/device_capture"
    )
    manifest = json.loads((plugin_dir / "plugin.json").read_text(encoding="utf-8"))
    manifest = PostprocessManager._validate_manifest(manifest, plugin_dir)
    output_dir = tmp_path / "v2"
    checkpoints: list[dict[str, Any]] = []

    def checkpoint(value: dict[str, Any]) -> None:
        normalized = PostprocessManager._normalize_stage(
            "device-capture",
            value,
            manifest,
            asset_root=output_dir,
        )
        checkpoints.append(normalized)

    result = await run_builtin(
        manager,
        run_id,
        output_dir,
        {"targetId": "target-one"},
        checkpoint,
    )
    normalized = PostprocessManager._normalize_stage(
        "device-capture",
        result,
        manifest,
        asset_root=output_dir,
    )
    assert len(checkpoints) == 3
    samples = normalized.get("sampleResults")
    assert isinstance(samples, list)
    assert [item.get("status") for item in samples] == ["success", "failed", "success"]
    facts = samples[0].get("facts")
    assert isinstance(facts, dict)
    assert "cropPx" not in facts
    assert facts.get("terminal") == "READY_WITH_WARNINGS"
    assert facts.get("warnings") == ["warning"]
    artifacts = samples[0].get("artifacts")
    assert isinstance(artifacts, list)
    metadata = next(item for item in artifacts if item.get("key") == "device-capture-metadata")
    assert metadata.get("dataType") == "json"
    data = metadata.get("data")
    assert isinstance(data, dict)
    assert data.get("cropPx") == {"left": 0, "top": 0, "width": 10, "height": 10}
    assert not (output_dir / "gallery.html").exists()


def test_crop_object_is_not_an_index_fact() -> None:
    with pytest.raises(ValueError, match="插件 fact 值无效: cropPx"):
        PostprocessManager._normalize_facts(
            {
                "cropPx": {"left": 0, "top": 0, "width": 10, "height": 10},
            }
        )


def test_job_image_path_is_bounded(tmp_path: Path) -> None:
    config = _config(tmp_path)
    jobs = Jobs(config, object())  # type: ignore[arg-type]
    job_id = "a" * 32
    directory = config.output / job_id
    directory.mkdir(parents=True)
    state = {"id": job_id, "status": "success"}
    jobs.states[job_id] = state
    (directory / "card.png").write_bytes(b"png")
    assert jobs.image_path(job_id, "card") == directory / "card.png"
    with pytest.raises(DeviceError):
        jobs.image_path(job_id, "../state.json")


def test_device_api_lists_online_targets_and_has_no_profile_routes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = Target("target-one", "serial", "Pura Test", "physical")

    async def refresh(self: Any) -> list[Target]:
        self.targets = {target.id: target}
        return [target]

    monkeypatch.setattr("debug_tools.device_debug.devices.Devices.refresh", refresh)
    app = FastAPI()
    register_device_routes(app, _config(tmp_path))
    with TestClient(app) as client:
        response = client.get("/debug/device/targets")
        assert response.status_code == 200
        assert response.json()["targets"][0]["id"] == "target-one"
        assert client.get("/debug/device/profiles").status_code == 404
