# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import asyncio
from dataclasses import dataclass
from threading import Lock

from app.logger import logger


@dataclass(frozen=True)
class WebSocketMetricsSnapshot:
    """WebSocket 进程级统计快照。"""

    active_connections: int
    total_connections: int
    running_tasks: int


class WebSocketMetrics:
    """统计当前进程内全部 WebSocket 连接和正在处理的任务。"""

    def __init__(self) -> None:
        self._lock = Lock()
        self._active_connections = 0
        self._total_connections = 0
        self._running_tasks = 0

    def connection_opened(self) -> None:
        with self._lock:
            self._active_connections += 1
            self._total_connections += 1

    def connection_closed(self) -> None:
        with self._lock:
            self._active_connections = max(0, self._active_connections - 1)

    def task_started(self) -> None:
        with self._lock:
            self._running_tasks += 1

    def task_finished(self) -> None:
        with self._lock:
            self._running_tasks = max(0, self._running_tasks - 1)

    def snapshot(self) -> WebSocketMetricsSnapshot:
        with self._lock:
            return WebSocketMetricsSnapshot(
                active_connections=self._active_connections,
                total_connections=self._total_connections,
                running_tasks=self._running_tasks,
            )


async def report_websocket_metrics(
    metrics: WebSocketMetrics,
    interval_seconds: float = 10.0,
) -> None:
    """按固定周期打印当前进程的 WebSocket 统计。"""
    while True:
        await asyncio.sleep(interval_seconds)
        snapshot = metrics.snapshot()
        logger.info(
            "websocket_metrics "
            f"active_connections={snapshot.active_connections} "
            f"total_connections={snapshot.total_connections} "
            f"running_tasks={snapshot.running_tasks}"
        )
