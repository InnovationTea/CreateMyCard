# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""全流程 WebSocket 压测脚本。

模拟多用户并发执行完整四段链路：
  overview → schema → generate → validate

用法:
  py -3.12 pressure_test_ws.py
  py -3.12 pressure_test_ws.py --concurrency 5 --iterations 20
  py -3.12 pressure_test_ws.py --concurrency 10 --duration 60

环境变量:
  WIDGET_SERVICE_TEST_HOST: 服务地址 (默认 localhost)
  WIDGET_SERVICE_TEST_PORT: 服务端口 (默认 8855)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import statistics
import sys
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import websockets

# ---------------------------------------------------------------------------
# 路径与配置
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[0]
CLOUD_ROOT = (
    Path(os.getenv("WIDGET_SERVICE_CLOUD_ROOT", ""))
    if os.getenv("WIDGET_SERVICE_CLOUD_ROOT")
    else PROJECT_ROOT / "widget_service" / "cloud"
)
if str(CLOUD_ROOT) not in sys.path and CLOUD_ROOT.exists():
    sys.path.insert(0, str(CLOUD_ROOT))

SERVER_HOST = os.getenv("WIDGET_SERVICE_TEST_HOST", socket.gethostbyname("localhost"))
SERVER_PORT = int(os.getenv("WIDGET_SERVICE_TEST_PORT", "8855"))
WS_BASE_URL = f"ws://{SERVER_HOST}:{SERVER_PORT}"
WS_BASE_PATH = os.getenv("WIDGET_SERVICE_TEST_WS_BASE_PATH", "/api/v1/ws/tools")

APP_VERSION = ".".join(("11", "7", "5", "205"))
ROM_VERSION = "CLS-AL30 " + ".".join(("6", "0", "0", "328"))

DEVICE_INFO = {
    "countryCode": "CN",
    "deviceFormation": "HDSpeaker",
    "deviceType": 0,
    "locale": "zh-CN",
    "phoneType": "CLS-AL30",
    "prdVer": APP_VERSION,
    "sysVer": "EmotionUI_9.0.0",
    "romVersion": ROM_VERSION,
    "time": "20260707115342975",
}

# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


@dataclass
class StageMetrics:
    """单个阶段耗时统计 (毫秒)。"""

    values: list[float] = field(default_factory=list)

    def record(self, value: float) -> None:
        self.values.append(value)

    @property
    def count(self) -> int:
        return len(self.values)

    def summary(self) -> dict[str, float]:
        if not self.values:
            return {"count": 0}
        sorted_vals = sorted(self.values)
        return {
            "count": len(sorted_vals),
            "min": round(min(sorted_vals), 2),
            "max": round(max(sorted_vals), 2),
            "avg": round(statistics.mean(sorted_vals), 2),
            "p50": round(_percentile(sorted_vals, 50), 2),
            "p90": round(_percentile(sorted_vals, 90), 2),
            "p99": round(_percentile(sorted_vals, 99), 2),
        }


@dataclass
class UserIterationResult:
    """单用户单次迭代各阶段耗时 (毫秒)。"""

    user_index: int
    iteration: int
    overview_ms: float = 0
    schema_ms: float = 0
    generate_ms: float = 0
    validate_ms: float = 0
    total_ms: float = 0
    first_token_ms: float = 0
    total_tokens: int = 0
    completion_tokens: int = 0
    prompt_tokens: int = 0
    status: str = "success"
    error: str = ""
    error_stage: str = ""


@dataclass
class PressureReport:
    """压测汇总报告。"""

    config: dict[str, Any] = field(default_factory=dict)
    total_iterations: int = 0
    success_count: int = 0
    failure_count: int = 0
    stage_metrics: dict[str, StageMetrics] = field(default_factory=dict)
    total_metrics: StageMetrics = field(default_factory=StageMetrics)
    first_token_metrics: StageMetrics = field(default_factory=StageMetrics)
    token_metrics: dict[str, list[int]] = field(default_factory=dict)
    errors_by_stage: dict[str, int] = field(default_factory=dict)
    duration_seconds: float = 0
    throughput_qps: float = 0
    errors: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _percentile(sorted_data: list[float], pct: float) -> float:
    """计算百分位数。"""
    if not sorted_data:
        return 0
    index = (len(sorted_data) - 1) * pct / 100.0
    lower = int(index)
    upper = min(lower + 1, len(sorted_data) - 1)
    weight = index - lower
    return sorted_data[lower] * (1 - weight) + sorted_data[upper] * weight


def _tool_payload(content: dict, interaction_id: str, original: str = "") -> dict:
    """构造新协议 WebSocket 请求包络。"""
    return {
        "content": {
            "odid": "5e64f3e9-0a80-d719-d689-3c36eca5eeb6",
            **content,
        },
        "deviceInfo": DEVICE_INFO,
        "pagination": {"limit": 5, "start": ""},
        "session": {
            "interactionId": interaction_id,
            "isNew": False,
            "sessionId": str(uuid.uuid4()),
        },
        "userAuth": {"user": {"userId": f"pressure-user-{interaction_id[-8:]}"}},
        "utterance": {"original": original, "type": "text"},
        "version": "1.0",
        "bundleName": "com.omega_w_0823.hmservice",
    }


def _now_ms() -> float:
    return time.perf_counter() * 1000


# ---------------------------------------------------------------------------
# 单用户全流程执行
# ---------------------------------------------------------------------------


async def _recv_until_final(
    websocket: websockets.WebSocketClientProtocol,
    path_name: str,
    stage_name: str,
) -> tuple[dict, float, float, int, int, int]:
    """接收 WebSocket 帧直到 final，返回 (最终消息, 首token时延ms, 总时延ms, total_tokens, completion_tokens, prompt_tokens)。

    从 start 帧到第一个包含 streamContent 的 partial/final 帧的时延作为首 token 时延。
    """
    start_received = False
    first_token_at: float | None = None
    first_token_ms = 0.0
    stage_start = _now_ms()
    total_tokens = 0
    completion_tokens = 0
    prompt_tokens = 0

    while True:
        raw = await asyncio.wait_for(websocket.recv(), timeout=120.0)
        message = json.loads(raw)
        stream_info = message["reply"]["streamInfo"]
        stream_type = stream_info["streamType"]
        content = stream_info.get("streamContent", "")

        if stream_type == "start":
            start_received = True
            continue

        if stream_type == "partial":
            if first_token_at is None and content:
                first_token_at = _now_ms()
                first_token_ms = first_token_at - stage_start
            continue

        # final 帧
        if first_token_at is None and content:
            first_token_ms = _now_ms() - stage_start

        stage_elapsed = _now_ms() - stage_start

        # 尝试从 items[0] 中提取 token 统计 (generate 阶段)
        items = message.get("reply", {}).get("items", [])
        if items and isinstance(items[0], dict):
            data = items[0].get("data", {})
            if isinstance(data, dict):
                total_tokens = data.get("total_tokens", 0)
                completion_tokens = data.get("completion_tokens", 0)
                prompt_tokens = data.get("prompt_tokens", 0)

        return message, first_token_ms, stage_elapsed, total_tokens, completion_tokens, prompt_tokens


async def _run_single_user_iteration(
    user_index: int,
    iteration: int,
    semaphore: asyncio.Semaphore,
) -> UserIterationResult:
    """单个用户执行一次完整四段流程。

    入参:
    - user_index: 用户编号 (用于日志和结果标记)。
    - iteration: 当前迭代序号。
    - semaphore: 并发控制信号量。
    出参: 本次迭代各阶段耗时和状态。
    """
    result = UserIterationResult(user_index=user_index, iteration=iteration)
    iter_start = _now_ms()
    interaction_id = f"pressure-{user_index:04d}-{iteration:04d}"

    async with semaphore:
        try:
            # ---- Stage 1: getWidgetCapabilityOverview ----
            stage_start = _now_ms()
            async with websockets.connect(
                f"{WS_BASE_URL}{WS_BASE_PATH}/getWidgetCapabilityOverview",
                open_timeout=5.0,
            ) as ws:
                await ws.send(
                    json.dumps(
                        _tool_payload(
                            {"bundleName": "com.omega_w_0823.hmservice"},
                            interaction_id,
                        ),
                        ensure_ascii=False,
                    )
                )
                msg, _, elapsed, _, _, _ = await _recv_until_final(
                    ws, "getWidgetCapabilityOverview", "overview"
                )
                result.overview_ms = elapsed

                if msg.get("errorCode") != "0":
                    raise RuntimeError(f"overview error: {msg.get('errorMessage', '')}")

                overview_data = msg["reply"]["items"][0]["data"]

            # ---- Stage 2: getDataCapabilitySchemas ----
            stage_start = _now_ms()
            async with websockets.connect(
                f"{WS_BASE_URL}{WS_BASE_PATH}/getDataCapabilitySchemas",
                open_timeout=5.0,
            ) as ws:
                await ws.send(
                    json.dumps(
                        _tool_payload(
                            {
                                "bundleName": "com.omega_w_0823.hmservice",
                                "dataCapabilityIds": ["ViewWeather"],
                            },
                            interaction_id,
                        ),
                        ensure_ascii=False,
                    )
                )
                msg, _, elapsed, _, _, _ = await _recv_until_final(
                    ws, "getDataCapabilitySchemas", "schema"
                )
                result.schema_ms = elapsed

                if msg.get("errorCode") != "0":
                    raise RuntimeError(f"schema error: {msg.get('errorMessage', '')}")

            # ---- Stage 3: generateWidgetCard ----
            stage_start = _now_ms()
            async with websockets.connect(
                f"{WS_BASE_URL}{WS_BASE_PATH}/generateWidgetCard",
                open_timeout=5.0,
            ) as ws:
                await ws.send(
                    json.dumps(
                        _tool_payload(
                            {
                                "bundleName": "com.omega_w_0823.hmservice",
                                "userQuery": "帮我做通勤卡片，包含天气",
                                "size": "2x4",
                                "title": "通勤日常",
                                "description": "天气速览",
                                "candidateDataBindings": [
                                    {
                                        "capabilityId": "ViewWeather",
                                        "arguments": {
                                            "districtName": "上海",
                                            "forecastDays": 1,
                                        },
                                        "writeResultTo": "/data/weather",
                                        "candidateOutputFields": [
                                            "/location/districtName",
                                            "/current/temperatureText",
                                            "/current/condition",
                                            "/current/airQuality",
                                            "/updatedAt",
                                        ],
                                    }
                                ],
                                "candidateEventCandidates": [
                                    {
                                        "capabilityId": "event.open.weather",
                                        "action": {
                                            "call": "clickToDeeplink",
                                            "args": {
                                                "intentName": "Weather_CityCode",
                                                "bundleName": "",
                                                "abilityName": "",
                                                "uri": "hww://www.huawei.com/totemweather?enterType=share&cityCode=",
                                            },
                                        },
                                    }
                                ],
                                "candidateAssetIds": ["asset.drop_1"],
                            },
                            interaction_id,
                            "帮我做通勤卡片，包含天气",
                        ),
                        ensure_ascii=False,
                    )
                )
                msg, first_ms, elapsed, total_tok, comp_tok, prompt_tok = (
                    await _recv_until_final(ws, "generateWidgetCard", "generate")
                )
                result.generate_ms = elapsed
                result.first_token_ms = first_ms
                result.total_tokens = total_tok
                result.completion_tokens = comp_tok
                result.prompt_tokens = prompt_tok

                if msg.get("errorCode") != "0":
                    raise RuntimeError(f"generate error: {msg.get('errorMessage', '')}")

                generated = msg["reply"]["items"][0]["data"]

            # ---- Stage 4: 本地校验 (可选) ----
            stage_start = _now_ms()
            validate_ms = 0.0
            try:
                from services.card_validation import ValidationOptions, validate_card
                from services.source_artifact_repository import (
                    SourceArtifactRepository,
                )

                artifact_url = generated.get("artifactUrl", "")
                if artifact_url:
                    artifact = SourceArtifactRepository().load(artifact_url).artifact
                    capabilities_dir = (
                        CLOUD_ROOT
                        / "data"
                        / "capabilities"
                        / artifact.meta.capabilityRegistryVersion
                    )
                    validate_card(
                        artifact=artifact.model_dump(mode="json", exclude_none=True),
                        options=ValidationOptions(capabilities_dir=capabilities_dir),
                    )
            except ImportError:
                pass  # 压测环境可能未安装完整依赖
            except Exception:
                pass
            validate_ms = _now_ms() - stage_start
            result.validate_ms = validate_ms

            result.status = "success"
            result.total_ms = _now_ms() - iter_start

        except (OSError, websockets.ConnectionClosed, asyncio.TimeoutError) as exc:
            result.status = "error"
            result.error = f"{type(exc).__name__}: {exc}"
            result.total_ms = _now_ms() - iter_start
        except RuntimeError as exc:
            result.status = "error"
            result.error = str(exc)
            result.total_ms = _now_ms() - iter_start

        return result


# ---------------------------------------------------------------------------
# 压测编排
# ---------------------------------------------------------------------------


async def _run_pressure_test(
    concurrency: int,
    iterations: int,
    progress_interval: float = 2.0,
) -> PressureReport:
    """执行全流程压测。

    入参:
    - concurrency: 并发用户数。
    - iterations: 总迭代次数 (均匀分配给各用户)。
    - progress_interval: 进度打印间隔 (秒)。
    出参: 压测汇总报告。
    """
    semaphore = asyncio.Semaphore(concurrency)

    # 生成任务: 每个 (user_index, iteration) 组合
    tasks = [
        (user_index, iteration)
        for iteration in range(iterations)
        for user_index in range(concurrency)
    ]

    total_tasks = len(tasks)
    completed = 0
    results: list[UserIterationResult] = []
    lock = asyncio.Lock()

    print(f"\n{'='*60}")
    print(f"全流程 WebSocket 压测开始")
    print(f"服务地址: {WS_BASE_URL}")
    print(f"并发数: {concurrency}")
    print(f"总迭代数: {total_tasks} (每用户 {iterations} 次)")
    print(f"{'='*60}\n")

    async def _run_with_tracking(user_index: int, iteration: int) -> UserIterationResult:
        nonlocal completed
        result = await _run_single_user_iteration(user_index, iteration, semaphore)
        async with lock:
            completed += 1
            elapsed = result.total_ms / 1000
            status_icon = "✓" if result.status == "success" else "✗"
            print(
                f"[{completed:4d}/{total_tasks}] {status_icon} "
                f"user={user_index:3d} iter={iteration:3d} "
                f"total={elapsed:.2f}s "
                f"overview={result.overview_ms:.0f}ms "
                f"schema={result.schema_ms:.0f}ms "
                f"generate={result.generate_ms:.0f}ms "
                f"validate={result.validate_ms:.0f}ms "
                f"first_token={result.first_token_ms:.0f}ms "
                f"tokens={result.total_tokens} "
                + (f"ERR={result.error[:80]}" if result.status == "error" else ""),
                flush=True,
            )
        return result

    start_time = time.perf_counter()

    # 打散任务顺序，避免同一用户请求连续堆积
    import random

    shuffled = list(tasks)
    random.shuffle(shuffled)

    coros = [_run_with_tracking(uid, it) for uid, it in shuffled]
    results = await asyncio.gather(*coros)

    total_duration = time.perf_counter() - start_time

    # ---- 汇总统计 ----
    report = PressureReport(
        config={
            "concurrency": concurrency,
            "iterations": iterations,
            "total_tasks": total_tasks,
            "server": WS_BASE_URL,
        },
        duration_seconds=round(total_duration, 2),
    )

    stage_names = ["overview", "schema", "generate", "validate"]
    stage_metrics: dict[str, StageMetrics] = {
        name: StageMetrics() for name in stage_names
    }
    total_metrics = StageMetrics()
    first_token_metrics = StageMetrics()
    token_metrics: dict[str, list[int]] = {
        "total_tokens": [],
        "completion_tokens": [],
        "prompt_tokens": [],
    }
    errors_by_stage: dict[str, int] = defaultdict(int)

    for r in results:
        if r.status == "success":
            report.success_count += 1
            stage_metrics["overview"].record(r.overview_ms)
            stage_metrics["schema"].record(r.schema_ms)
            stage_metrics["generate"].record(r.generate_ms)
            stage_metrics["validate"].record(r.validate_ms)
            total_metrics.record(r.total_ms)
            if r.first_token_ms > 0:
                first_token_metrics.record(r.first_token_ms)
            if r.total_tokens > 0:
                token_metrics["total_tokens"].append(r.total_tokens)
                token_metrics["completion_tokens"].append(r.completion_tokens)
                token_metrics["prompt_tokens"].append(r.prompt_tokens)
        else:
            report.failure_count += 1
            errors_by_stage[r.error_stage or "unknown"] += 1
            report.errors.append(
                {
                    "user_index": r.user_index,
                    "iteration": r.iteration,
                    "error": r.error,
                    "stage": r.error_stage,
                }
            )

    report.total_iterations = total_tasks
    report.stage_metrics = stage_metrics
    report.total_metrics = total_metrics
    report.first_token_metrics = first_token_metrics
    report.token_metrics = token_metrics
    report.errors_by_stage = dict(errors_by_stage)
    report.throughput_qps = (
        round(total_tasks / total_duration, 2) if total_duration > 0 else 0
    )

    return report


def _print_report(report: PressureReport) -> None:
    """打印压测报告。"""
    print(f"\n{'='*60}")
    print("压测报告")
    print(f"{'='*60}")

    print(f"\n── 配置 ──")
    for key, value in report.config.items():
        print(f"  {key}: {value}")

    print(f"\n── 总体 ──")
    print(f"  总耗时: {report.duration_seconds:.2f}s")
    print(f"  总请求: {report.total_iterations}")
    print(f"  成功: {report.success_count}")
    print(f"  失败: {report.failure_count}")
    print(
        f"  成功率: {report.success_count / max(report.total_iterations, 1) * 100:.1f}%"
    )
    print(f"  吞吐量: {report.throughput_qps} 次/秒")

    print(f"\n── 各阶段耗时 (ms) ──")
    stage_labels = {
        "overview": "能力概述",
        "schema": "Schema 加载",
        "generate": "卡片生成",
        "validate": "本地校验",
    }
    header = f"  {'阶段':<12} {'次数':>6} {'min':>8} {'max':>8} {'avg':>8} {'p50':>8} {'p90':>8} {'p99':>8}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for name, metrics in report.stage_metrics.items():
        s = metrics.summary()
        if s["count"] == 0:
            continue
        print(
            f"  {stage_labels.get(name, name):<12} {s['count']:>6} "
            f"{s['min']:>8.0f} {s['max']:>8.0f} {s['avg']:>8.0f} "
            f"{s['p50']:>8.0f} {s['p90']:>8.0f} {s['p99']:>8.0f}"
        )

    print(f"\n── 端到端总耗时 (ms) ──")
    s = report.total_metrics.summary()
    if s["count"] > 0:
        print(
            f"  count={s['count']} min={s['min']:.0f} max={s['max']:.0f} "
            f"avg={s['avg']:.0f} p50={s['p50']:.0f} p90={s['p90']:.0f} p99={s['p99']:.0f}"
        )

    print(f"\n── 首 Token 时延 (ms) ──")
    s = report.first_token_metrics.summary()
    if s["count"] > 0:
        print(
            f"  count={s['count']} min={s['min']:.0f} max={s['max']:.0f} "
            f"avg={s['avg']:.0f} p50={s['p50']:.0f} p90={s['p90']:.0f} p99={s['p99']:.0f}"
        )
    else:
        print("  (无数据)")

    print(f"\n── Token 统计 ──")
    for token_type, values in report.token_metrics.items():
        if values:
            print(
                f"  {token_type}: min={min(values)} max={max(values)} "
                f"avg={statistics.mean(values):.0f} p50={_percentile(sorted(values), 50):.0f}"
            )

    if report.errors_by_stage:
        print(f"\n── 错误分布 ──")
        for stage, count in sorted(
            report.errors_by_stage.items(), key=lambda x: -x[1]
        ):
            print(f"  {stage}: {count}")

    if report.errors:
        print(f"\n── 错误详情 (前 10 条) ──")
        for err in report.errors[:10]:
            print(
                f"  user={err['user_index']} iter={err['iteration']} "
                f"stage={err['stage']}: {err['error'][:100]}"
            )

    print(f"\n{'='*60}\n")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="全流程 WebSocket 压测脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  py -3.12 pressure_test_ws.py
  py -3.12 pressure_test_ws.py --concurrency 5 --iterations 20
  py -3.12 pressure_test_ws.py --concurrency 10 --iterations 50 --output report.json
        """,
    )
    parser.add_argument(
        "--concurrency",
        "-c",
        type=int,
        default=3,
        help="并发用户数 (默认 3)",
    )
    parser.add_argument(
        "--iterations",
        "-n",
        type=int,
        default=5,
        help="每用户迭代次数 (默认 5)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="",
        help="输出 JSON 报告文件路径 (可选)",
    )
    args = parser.parse_args()

    if args.concurrency < 1:
        print("错误: --concurrency 必须 >= 1", file=sys.stderr)
        sys.exit(1)
    if args.iterations < 1:
        print("错误: --iterations 必须 >= 1", file=sys.stderr)
        sys.exit(1)

    report = asyncio.run(
        _run_pressure_test(
            concurrency=args.concurrency,
            iterations=args.iterations,
        )
    )

    _print_report(report)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(
            json.dumps(_report_to_dict(report), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"JSON 报告已保存至: {output_path.resolve()}")


def _report_to_dict(report: PressureReport) -> dict:
    """将报告转为可序列化字典。"""
    return {
        "config": report.config,
        "duration_seconds": report.duration_seconds,
        "total_iterations": report.total_iterations,
        "success_count": report.success_count,
        "failure_count": report.failure_count,
        "success_rate": round(
            report.success_count / max(report.total_iterations, 1) * 100, 1
        ),
        "throughput_qps": report.throughput_qps,
        "stage_metrics": {
            name: metrics.summary()
            for name, metrics in report.stage_metrics.items()
        },
        "total_metrics": report.total_metrics.summary(),
        "first_token_metrics": report.first_token_metrics.summary(),
        "token_metrics": {
            key: {
                "min": min(values) if values else 0,
                "max": max(values) if values else 0,
                "avg": round(statistics.mean(values)) if values else 0,
                "p50": round(_percentile(sorted(values), 50)) if values else 0,
            }
            for key, values in report.token_metrics.items()
        },
        "errors_by_stage": report.errors_by_stage,
        "errors": report.errors[:50],
    }


if __name__ == "__main__":
    main()