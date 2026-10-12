from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from debug_tools.postprocess_plugins.device_capture import (
    DeviceCaptureConfig,
    DeviceCaptureManager,
    DeviceRenderer,
    run_builtin,
)
from PIL import Image


class FakeRenderer:
    def __init__(self, failed_ids: set[str] | None = None) -> None:
        self.failed_ids = failed_ids or set()
        self.rendered: list[str] = []

    async def availability(self) -> dict[str, Any]:
        return {"configured": True, "available": True, "reason": "", "device": "ABC***123"}

    async def require_available(self) -> None:
        return None

    async def render(
        self,
        _genui_path: Path,
        _size: str,
        work_dir: Path,
        full_output: Path,
        card_output: Path,
        _log_path: Path,
    ) -> None:
        sample_id = work_dir.name
        self.rendered.append(sample_id)
        if sample_id in self.failed_ids:
            raise RuntimeError("设备断开")
        full_output.parent.mkdir(parents=True, exist_ok=True)
        card_output.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (1280, 720), "white").save(full_output, format="JPEG")
        Image.new("RGB", (300, 150), "blue").save(card_output, format="PNG")

    async def stop(self) -> None:
        return None


def _write_run(output_root: Path, run_id: str, sample_ids: list[str]) -> Path:
    run_dir = output_root / run_id
    samples: list[dict[str, Any]] = []
    for index, sample_id in enumerate(sample_ids):
        samples.append(
            {
                "id": sample_id,
                "query": "制作 2x2 卡片",
                "size": "2x2",
                "sequence": index + 1,
            }
        )
        sample_dir = run_dir / sample_id
        attempt_dir = sample_dir / "attempt_000"
        attempt_dir.mkdir(parents=True)
        (sample_dir / "result.json").write_text(
            json.dumps({"finalAttempt": 0}),
            encoding="utf-8",
        )
        (attempt_dir / "genui.jsonl").write_text(
            '{"createSurface":{"surfaceId":"surface"}}\n',
            encoding="utf-8",
        )
    (run_dir / "summary.json").write_text(
        json.dumps({"runId": run_id, "samples": samples}),
        encoding="utf-8",
    )
    return run_dir


@pytest.mark.asyncio
async def test_device_capture_runs_in_background_and_keeps_sample_failures(
    tmp_path: Path,
) -> None:
    run_id = "batch_20261005_000000_1234abcd"
    _write_run(tmp_path, run_id, ["Q001", "Q002"])
    renderer = FakeRenderer({"Q002"})
    finished: list[str] = []
    manager = DeviceCaptureManager(
        tmp_path,
        renderer=renderer,  # type: ignore[arg-type]
        on_terminal=finished.append,
    )

    await manager.start()
    queued = manager.enqueue(run_id)
    assert queued.get("status") == "queued"
    await manager.queue.join()
    status = manager.status(run_id)
    await manager.close()

    assert status.get("status") == "partial"
    assert status.get("succeeded") == 1
    assert status.get("failed") == 1
    assert finished == [run_id]
    first = manager.sample(run_id, "Q001")
    second = manager.sample(run_id, "Q002")
    assert first.get("cardUrl", "").endswith("/Q001/card")
    assert second.get("error") == "RuntimeError: 设备断开"
    assert manager.image_path(run_id, "Q001", "card").is_file()


@pytest.mark.asyncio
async def test_device_gallery_embeds_device_screenshots_and_failures(tmp_path: Path) -> None:
    run_id = "batch_20261005_gallery_1234abcd"
    _write_run(tmp_path, run_id, ["Q001", "Q002"])
    manager = DeviceCaptureManager(
        tmp_path,
        renderer=FakeRenderer({"Q002"}),  # type: ignore[arg-type]
    )

    await manager.start()
    result = await run_builtin(manager, run_id, tmp_path / "plugin", {})
    gallery_path = manager.gallery_path(run_id)
    await manager.close()

    document = gallery_path.read_text(encoding="utf-8")
    dataset_artifacts = result.get("datasetResult", {}).get("artifacts", [])
    assert result.get("status") == "partial"
    assert "真机截图画廊" in document
    assert "data:image/png;base64," in document
    assert "RuntimeError: 设备断开" in document
    assert any(item.get("key") == "device-gallery" for item in dataset_artifacts)
    assert manager.gallery_url(run_id).endswith(f"/{run_id}/device-gallery.html")


@pytest.mark.asyncio
async def test_device_capture_skips_missing_genui_and_restart_marks_interrupted(
    tmp_path: Path,
) -> None:
    run_id = "batch_20261005_000001_1234abcd"
    run_dir = _write_run(tmp_path, run_id, ["Q001"])
    (run_dir / "Q001" / "attempt_000" / "genui.jsonl").unlink()
    (run_dir / "device_capture.json").write_text(
        json.dumps({"status": "running", "items": []}),
        encoding="utf-8",
    )
    manager = DeviceCaptureManager(
        tmp_path,
        renderer=FakeRenderer(),  # type: ignore[arg-type]
    )

    await manager.start()
    interrupted = manager.status(run_id)
    manager.enqueue(run_id, retry=True)
    await manager.queue.join()
    completed = manager.status(run_id)
    await manager.close()

    assert interrupted.get("status") == "interrupted"
    assert completed.get("status") == "ready"
    assert completed.get("skipped") == 1
    item = manager.sample(run_id, "Q001")
    assert item.get("status") == "skipped"
    with pytest.raises(KeyError):
        manager.image_path(run_id, "../outside", "card")


def test_device_size_resolution_prefers_cardspec_and_crop_uses_selected_box(
    tmp_path: Path,
) -> None:
    attempt_dir = tmp_path / "attempt_000"
    attempt_dir.mkdir()
    (attempt_dir / "blocks.json").write_text(
        json.dumps({"cardSpec": {"suggestSize": "2x4"}}),
        encoding="utf-8",
    )
    size = DeviceCaptureManager._resolve_size(
        attempt_dir,
        {"query": "制作 2x2 卡片", "size": "2x2"},
    )
    source = tmp_path / "display.jpeg"
    output = tmp_path / "card.png"
    Image.new("RGB", (1280, 720), "white").save(source, format="JPEG")
    renderer = DeviceRenderer(DeviceCaptureConfig())
    renderer._crop(source, output, size)

    assert size == "2x4"
    with Image.open(output) as image:
        assert image.size == (1097, 480)


def test_device_capture_config_is_loaded_from_debug_agent_yaml(tmp_path: Path) -> None:
    render_project = tmp_path / "renderer"
    sdk = tmp_path / "sdk"
    java = tmp_path / "java"
    hvigor = tmp_path / "hvigorw.bat"
    emulator = tmp_path / "Emulator.exe"
    emulator_instances = tmp_path / "emulators"
    emulator_images = tmp_path / "images"
    config_path = tmp_path / "debug_agent.yaml"
    config_path.write_text(
        "device_capture:\n"
        "  hdc: D:/tools/hdc.exe\n"
        "  device_sn: test-device\n"
        f"  render_project: {render_project.as_posix()}\n"
        f"  deveco_sdk_home: {sdk.as_posix()}\n"
        f"  java_home: {java.as_posix()}\n"
        f"  hvigor: {hvigor.as_posix()}\n"
        "  render_wait_seconds: 6\n"
        "  command_timeout_seconds: 120\n"
        "  auto_start_emulator: true\n"
        f"  emulator: {emulator.as_posix()}\n"
        "  emulator_name: Test_Phone\n"
        f"  emulator_instance_root: {emulator_instances.as_posix()}\n"
        f"  emulator_image_root: {emulator_images.as_posix()}\n"
        "  emulator_start_timeout_seconds: 90\n"
        "  emulator_poll_seconds: 1\n",
        encoding="utf-8",
    )

    config = DeviceCaptureConfig.from_debug_agent(config_path)

    assert config.hdc == "D:/tools/hdc.exe"
    assert config.device_sn == "test-device"
    assert config.render_project == render_project
    assert config.deveco_sdk_home == sdk
    assert config.java_home == java
    assert config.hvigor == hvigor
    assert config.render_wait_seconds == 6.0
    assert config.command_timeout_seconds == 120.0
    assert config.auto_start_emulator is True
    assert config.emulator == emulator
    assert config.emulator_name == "Test_Phone"
    assert config.emulator_instance_root == emulator_instances
    assert config.emulator_image_root == emulator_images
    assert config.emulator_start_timeout_seconds == 90.0
    assert config.emulator_poll_seconds == 1.0


@pytest.mark.asyncio
async def test_device_availability_auto_starts_emulator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = DeviceCaptureConfig(
        auto_start_emulator=True,
        emulator_name="Test_Phone",
        emulator_start_timeout_seconds=1.0,
        emulator_poll_seconds=0.001,
    )
    renderer = DeviceRenderer(config)
    process = type("FakeProcess", (), {"returncode": None})()
    list_targets = AsyncMock(
        side_effect=[[], [], ["127.0.0.1:5555"], ["127.0.0.1:5555"]]
    )
    launch = AsyncMock(return_value=process)
    monkeypatch.setattr(renderer, "_validate_static_config", lambda: None)
    monkeypatch.setattr(renderer, "_validate_emulator_config", lambda: None)
    monkeypatch.setattr(renderer, "_list_targets", list_targets)
    monkeypatch.setattr(renderer, "_launch_emulator", launch)

    result = await renderer.availability()

    assert result == {
        "configured": True,
        "available": True,
        "reason": "",
        "device": "127***555",
    }
    launch.assert_awaited_once()


def test_device_emulator_reports_commit_memory_failure(tmp_path: Path) -> None:
    instance_root = tmp_path / "emulators"
    log_path = instance_root / "Test_Phone" / "Emulator.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text(
        '[Warning] "Commit charge is not enough!"\n',
        encoding="utf-8",
    )
    renderer = DeviceRenderer(
        DeviceCaptureConfig(
            emulator_name="Test_Phone",
            emulator_instance_root=instance_root,
        )
    )

    assert renderer._emulator_failure_detail() == (
        "虚拟器启动失败：系统提交内存不足，请增加可用内存或页面文件"
    )
