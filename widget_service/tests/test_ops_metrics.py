# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import asyncio
import importlib.util
import sys
import threading
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest


def _logger_info(_message: str) -> None:
    return None


def _logger_error(_message: str) -> None:
    return None


def _get_session_id() -> str:
    return "session-from-context"


def _get_settings() -> SimpleNamespace:
    return SimpleNamespace(
        ai_widget_data_huashan_enable=True,
        hag_osms_ak="access-key",
    )


def _get_container_ip() -> str:
    return "container-host"


def _get_sts_config(_config_key: str) -> bytes:
    return b"secret-key"


@pytest.fixture
def ops_metrics_module(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    logger_module = ModuleType("app.logger")
    logger_module.logger = SimpleNamespace(
        info=_logger_info,
        error=_logger_error,
    )
    logger_module.task_logger = SimpleNamespace(
        get_session_id=_get_session_id,
    )

    config_module = ModuleType("config.config")
    config_module.get_settings = _get_settings
    config_module.get_container_ip = _get_container_ip

    base_utils_module = ModuleType("utils.base_utils")
    base_utils_module.sts_config = SimpleNamespace(
        get_sts_config=_get_sts_config,
    )

    monkeypatch.setitem(sys.modules, "app.logger", logger_module)
    monkeypatch.setitem(sys.modules, "config.config", config_module)
    monkeypatch.setitem(sys.modules, "utils.base_utils", base_utils_module)

    module_path = Path(__file__).resolve().parents[1] / "cloud" / "utils" / "ops_metrics.py"
    spec = importlib.util.spec_from_file_location("ops_metrics_under_test", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _enable_metrics(monkeypatch: pytest.MonkeyPatch, ops_metrics_module: ModuleType) -> None:
    settings = SimpleNamespace(ai_widget_data_huashan_enable=True)
    monkeypatch.setattr(ops_metrics_module, "get_settings", lambda: settings)
    monkeypatch.setattr(ops_metrics_module.platform, "system", lambda: "Linux")
    monkeypatch.setattr(ops_metrics_module, "get_container_ip", lambda: "container-host")
    monkeypatch.setattr(
        ops_metrics_module.task_logger,
        "get_session_id",
        lambda: "session-from-context",
    )


@pytest.mark.asyncio
async def test_report_ops_metrics_does_not_wait_for_async_request(
    monkeypatch: pytest.MonkeyPatch,
    ops_metrics_module: ModuleType,
) -> None:
    _enable_metrics(monkeypatch, ops_metrics_module)
    started = asyncio.Event()
    release = asyncio.Event()
    completed = asyncio.Event()
    received: dict[str, Any] = {}

    async def fake_trigger(
        url: str,
        payload: dict[str, Any],
        session_id: str,
        host: str,
    ) -> None:
        received.update(url=url, payload=payload, session_id=session_id, host=host)
        started.set()
        await release.wait()
        completed.set()

    monkeypatch.setattr(ops_metrics_module, "_report_ops_metrics_async", fake_trigger)

    result = ops_metrics_module.report_ops_metrics({"taskSuccess": 1})

    assert result is None
    await asyncio.wait_for(started.wait(), timeout=1.0)
    assert not completed.is_set()
    assert received == {
        "url": "http://container-host:8080/genui-agent/v1/mq/trigger",
        "payload": {
            "sessionId": "session-from-context",
            "body": {"taskSuccess": 1},
        },
        "session_id": "session-from-context",
        "host": "container-host",
    }

    release.set()
    await asyncio.wait_for(completed.wait(), timeout=1.0)


@pytest.mark.asyncio
async def test_report_ops_metrics_does_not_wait_when_called_from_worker_thread(
    monkeypatch: pytest.MonkeyPatch,
    ops_metrics_module: ModuleType,
) -> None:
    _enable_metrics(monkeypatch, ops_metrics_module)
    started = threading.Event()
    release = threading.Event()
    completed = threading.Event()

    async def fake_trigger(
        url: str,
        payload: dict[str, Any],
        session_id: str,
        host: str,
    ) -> None:
        started.set()
        while not release.is_set():
            await asyncio.sleep(0.01)
        completed.set()

    monkeypatch.setattr(ops_metrics_module, "_report_ops_metrics_async", fake_trigger)

    result = await asyncio.to_thread(
        ops_metrics_module.report_ops_metrics,
        {"taskSuccess": 1},
    )

    assert result is None
    assert await asyncio.to_thread(started.wait, 1.0)
    assert not completed.is_set()

    release.set()
    assert await asyncio.to_thread(completed.wait, 1.0)


@pytest.mark.asyncio
async def test_report_ops_metrics_uses_async_http_client(
    monkeypatch: pytest.MonkeyPatch,
    ops_metrics_module: ModuleType,
) -> None:
    response = SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {"status": "ok"},
    )
    received: dict[str, Any] = {}

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            received["timeout"] = timeout

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def post(
            self,
            url: str,
            *,
            json: dict[str, Any],
            headers: dict[str, str],
        ) -> Any:
            received.update(url=url, json=json, headers=headers)
            await asyncio.sleep(0)
            return response

    monkeypatch.setattr(ops_metrics_module.httpx, "AsyncClient", FakeAsyncClient)

    await ops_metrics_module._report_ops_metrics_async(
        "http://mq-host:8080/genui/agent/mq/trigger",
        {"sessionId": "session-id", "body": {"taskSuccess": 1}},
        "session-id",
        "mq-host",
    )

    assert received == {
        "timeout": 10.0,
        "url": "http://mq-host:8080/genui/agent/mq/trigger",
        "json": {"sessionId": "session-id", "body": {"taskSuccess": 1}},
        "headers": {"Content-Type": "application/json"},
    }
