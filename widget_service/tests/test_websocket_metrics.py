# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import asyncio
import importlib
import sys
from contextlib import suppress
from pathlib import Path

CLOUD_ROOT = Path(__file__).resolve().parents[1] / "cloud"
if str(CLOUD_ROOT) not in sys.path:
    sys.path.insert(0, str(CLOUD_ROOT))

metrics_module = importlib.import_module("app.websocket_metrics")
WebSocketMetrics = metrics_module.WebSocketMetrics
report_websocket_metrics = metrics_module.report_websocket_metrics


def test_websocket_metrics_tracks_process_wide_counts():
    metrics = WebSocketMetrics()

    metrics.connection_opened()
    metrics.connection_opened()
    metrics.task_started()
    metrics.connection_closed()

    snapshot = metrics.snapshot()
    assert snapshot.active_connections == 1
    assert snapshot.total_connections == 2
    assert snapshot.running_tasks == 1

    metrics.task_finished()
    metrics.connection_closed()
    snapshot = metrics.snapshot()
    assert snapshot.active_connections == 0
    assert snapshot.total_connections == 2
    assert snapshot.running_tasks == 0


def test_websocket_metrics_reporter_prints_all_counts(monkeypatch):
    messages: list[str] = []

    class CapturedLogger:
        def info(self, message, *_args, **_kwargs):
            messages.append(str(message))

    monkeypatch.setattr(metrics_module, "logger", CapturedLogger())
    metrics = WebSocketMetrics()
    metrics.connection_opened()
    metrics.task_started()

    async def scenario() -> None:
        reporter = asyncio.create_task(
            report_websocket_metrics(metrics, interval_seconds=0.01)
        )
        await asyncio.sleep(0.03)
        reporter.cancel()
        with suppress(asyncio.CancelledError):
            await reporter

    asyncio.run(scenario())

    assert messages
    assert "active_connections=1" in messages[0]
    assert "total_connections=1" in messages[0]
    assert "running_tasks=1" in messages[0]
