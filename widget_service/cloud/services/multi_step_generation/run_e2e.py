#!/usr/bin/env python3
"""从本地 CardSpec 用例调用平台 generateWidgetCard WebSocket 端到端链路。"""

from __future__ import annotations

import argparse
import ast
import asyncio
import json
import re
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import urllib3
import websockets

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MULTI_STEP_ROOT = Path(__file__).resolve().parent
DEFAULT_CARDSPEC_DIR = MULTI_STEP_ROOT / "cardSpec"
DEFAULT_OUTPUT_ROOT = MULTI_STEP_ROOT / "output"
WORKSPACE_DIR = MULTI_STEP_ROOT / "workspace"
DEFAULT_WS_URL = "ws://localhost:8855/api/v1/ws/tools/generateWidgetCard"
DEFAULT_TIMEOUT_SECONDS = 600.0
_HEADER_PATTERN = re.compile(
    r"^type=(?P<type>'(?:\\.|[^'])*') "
    r"tool=(?P<tool>'(?:\\.|[^'])*') "
    r"operation=(?P<operation>'(?:\\.|[^'])*') "
    r"requestId=(?P<request_id>None|'(?:\\.|[^'])*')$"
)


@dataclass(frozen=True, slots=True)
class CaseResult:
    """一个 CardSpec 端到端用例的执行结果。"""

    path: Path
    succeeded: bool
    infrastructure_error: bool
    index: int = 0
    response: dict[str, Any] | None = None
    elapsed_ms: float = 0.0
    artifact_url: str = ""
    artifact_digest: str = ""
    artifact_downloaded: bool = False
    error_message: str = ""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "读取 multi_step_generation/cardSpec 中的 CardSpec，调用平台 "
            "generateWidgetCard WebSocket，完整经过 TaskSpec、JSX Agent、"
            "JSX→A2UI 和 artifact 保存。"
        ),
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--batch",
        action="store_true",
        help="按文件名自然排序，顺序执行 cardSpec 目录中的全部 JSON。",
    )
    selection.add_argument(
        "--index",
        type=int,
        metavar="N",
        help="按自然排序执行第 N 个 CardSpec；N 从 1 开始。",
    )
    selection.add_argument(
        "--input",
        type=Path,
        help="兼容入口：直接指定一个 CardSpec JSON 文件。",
    )
    parser.add_argument(
        "--cardspec-dir",
        type=Path,
        default=DEFAULT_CARDSPEC_DIR,
        help=f"CardSpec 用例目录，默认 {DEFAULT_CARDSPEC_DIR}。",
    )
    parser.add_argument("--url", default=DEFAULT_WS_URL, help="平台 WebSocket 地址。")
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="每个 CardSpec 等待 final 帧的超时秒数。",
    )
    parser.add_argument(
        "--show-frames",
        action="store_true",
        help="打印 start、partial 和 final 原始帧。",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help=f"结果输出目录，默认 {DEFAULT_OUTPUT_ROOT}。",
    )
    parser.add_argument(
        "--round",
        type=str,
        default=None,
        help="指定运行目录名；默认使用当前时间戳。",
    )
    return parser.parse_args(argv)


def _natural_path_key(path: Path) -> tuple[tuple[int, object], ...]:
    parts = re.split(r"(\d+)", path.name.casefold())
    key: list[tuple[int, object]] = []
    for part in parts:
        if part.isdigit():
            key.append((0, int(part)))
        else:
            key.append((1, part))
    return tuple(key)


def _task_index(path: Path) -> int:
    match = re.search(r"(\d+)", path.stem)
    return int(match.group(1)) if match else 0


def _create_run_dir(output_root: Path, round_name: str | None) -> Path:
    name = round_name or datetime.now(timezone.utc).strftime("round_%Y%m%d_%H%M%S")
    run_dir = output_root / name
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _fetch_artifact(artifact_url: str, save_path: Path) -> bool:
    """从 artifactUrl 下载 artifact 文件内容并保存。"""
    if not artifact_url:
        return False
    try:
        if artifact_url.startswith("file:///"):
            local_path = Path(artifact_url[8:])
            save_path.write_text(local_path.read_text(encoding="utf-8"), encoding="utf-8")
        elif artifact_url.startswith("http"):
            resp = requests.get(artifact_url, timeout=30, verify=False, stream=True)
            resp.raise_for_status()
            save_path.write_text(resp.text, encoding="utf-8")
        else:
            print(f"  不支持的 URL 格式: {artifact_url}", flush=True)
            return False
        return True
    except Exception as exc:
        print(f"  下载 artifact 失败: {type(exc).__name__}: {exc}", flush=True)
        return False


_ROOT_DIMENSIONS = {
    "2x2": {"width": 160, "height": 160},
    "2x4": {"width": 320, "height": 160},
    "4x2": {"width": 320, "height": 160},
}


def _convert_md_to_dsl(md_content: str, size: str = "2x2") -> str | None:
    """从 artifact.md 中提取 genui 代码块并转换为 JSON 数组。"""
    pattern = r"```genui\n(.*?)```"
    match = re.search(pattern, md_content, re.DOTALL)
    if not match:
        return None
    json_str = match.group(1)
    json_objects = json_str.strip().split("\n")
    json_array = [json.loads(obj) for obj in json_objects if obj.strip()]
    dimensions = _ROOT_DIMENSIONS.get(size)
    if dimensions:
        for msg in json_array:
            update_components = msg.get("updateComponents")
            if not isinstance(update_components, dict):
                continue
            components = update_components.get("components")
            if not isinstance(components, list):
                continue
            for comp in components:
                if isinstance(comp, dict) and comp.get("id") == "root":
                    styles = comp.setdefault("styles", {})
                    styles["width"] = dimensions["width"]
                    styles["height"] = dimensions["height"]
    return json.dumps(json_array, ensure_ascii=False, indent=2)


def _collect_workspace_raw_files(run_dir: Path, task_num: int, request_start: float) -> None:
    """从 workspace 目录抢取 bridge 落盘的 raw 文件，按类型搬到 output 子目录。

    文件命名：raw_jsx_<c>.jsx / raw_a2ui_<c>.json / raw_trace_<c>.json /
    raw_rejected_<c>_turnNN.jsx / raw_context_<c>.json
    搬到 output 的 raw_jsx/q<N>.jsx / raw_a2ui/q<N>.json / traces/q<N>.json /
    rejected/<原文件名> / context/q<N>.json
    """
    if not WORKSPACE_DIR.exists():
        return
    raw_files = sorted(
        WORKSPACE_DIR.glob("raw_*"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    for raw_path in raw_files:
        if raw_path.stat().st_mtime < request_start:
            break
        try:
            raw_content = raw_path.read_text(encoding="utf-8")
        except Exception as exc:
            print(f"[E2E] 读取 raw 文件 {raw_path.name} 失败: {type(exc).__name__}: {exc}", flush=True)
            continue
        raw_name = raw_path.name
        if raw_name.startswith("raw_jsx_"):
            target_dir = run_dir / "raw_jsx"
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / f"q{task_num}.jsx").write_text(raw_content, encoding="utf-8")
        elif raw_name.startswith("raw_a2ui_"):
            target_dir = run_dir / "raw_a2ui"
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / f"q{task_num}.json").write_text(raw_content, encoding="utf-8")
            # dsl 直接用 raw_a2ui 的原始内容
            dsl_dir = run_dir / "dsl"
            dsl_dir.mkdir(parents=True, exist_ok=True)
            (dsl_dir / f"q{task_num}.jsonl").write_text(raw_content, encoding="utf-8")
        elif raw_name.startswith("raw_trace_"):
            target_dir = run_dir / "traces"
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / f"q{task_num}.json").write_text(raw_content, encoding="utf-8")
        elif raw_name.startswith("raw_rejected_"):
            target_dir = run_dir / "rejected"
            target_dir.mkdir(parents=True, exist_ok=True)
            target_name = raw_name.replace("raw_rejected_", "")
            (target_dir / target_name).write_text(raw_content, encoding="utf-8")
        elif raw_name.startswith("raw_context_"):
            target_dir = run_dir / "context"
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / f"q{task_num}.json").write_text(raw_content, encoding="utf-8")


def discover_cardspecs(directory: Path) -> list[Path]:
    if not directory.is_dir():
        raise ValueError(f"CardSpec 目录不存在：{directory}")
    paths = sorted(directory.glob("*.json"), key=_natural_path_key)
    if not paths:
        raise ValueError(f"CardSpec 目录中没有 JSON 文件：{directory}")
    return paths


def select_cardspecs(args: argparse.Namespace) -> list[Path]:
    if args.input is not None:
        if not args.input.is_file():
            raise ValueError(f"CardSpec 文件不存在：{args.input}")
        return [args.input]
    paths = discover_cardspecs(args.cardspec_dir)
    if args.batch:
        return paths
    index = args.index if args.index is not None else 1
    if index < 1 or index > len(paths):
        raise ValueError(f"CardSpec index 必须在 1..{len(paths)} 之间，收到 {index}")
    return [paths[index - 1]]


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取 CardSpec JSON：{path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"CardSpec 顶层必须是对象：{path}")
    return value


def _required_text(card_spec: dict[str, Any], key: str, path: Path) -> str:
    value = card_spec.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"CardSpec {key} 必须是非空字符串：{path}")
    return value.strip()


def _candidate_bindings(card_spec: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    bindings = card_spec.get("dataBindings", [])
    if bindings is None:
        return []
    if not isinstance(bindings, list):
        raise ValueError(f"CardSpec dataBindings 必须是数组：{path}")
    candidates: list[dict[str, Any]] = []
    for index, binding in enumerate(bindings):
        if not isinstance(binding, dict):
            raise ValueError(f"CardSpec dataBindings[{index}] 必须是对象：{path}")
        capability_id = binding.get("capabilityId")
        arguments = binding.get("arguments")
        write_result_to = binding.get("writeResultTo")
        valid_id = isinstance(capability_id, str) and bool(capability_id.strip())
        valid_path = isinstance(write_result_to, str) and bool(write_result_to.strip())
        if not valid_id or not isinstance(arguments, dict) or not valid_path:
            raise ValueError(f"CardSpec dataBindings[{index}] 缺少合法的 capabilityId/arguments/writeResultTo：{path}")
        candidates.append(
            {
                "capabilityId": capability_id.strip(),
                "arguments": dict(arguments),
                "writeResultTo": write_result_to.strip(),
                "candidateOutputFields": [],
            }
        )
    return candidates


def cardspec_to_content(card_spec: dict[str, Any], path: Path) -> dict[str, Any]:
    title = _required_text(card_spec, "title", path)
    description = _required_text(card_spec, "description", path)
    size = card_spec.get("suggestSize") or card_spec.get("size")
    if size not in {"2x2", "2x4"}:
        raise ValueError(f"CardSpec suggestSize 必须是 '2x2' 或 '2x4'：{path}")
    return {
        "bundleName": "com.omega_w_0823.hmservice",
        "userQuery": f"{title}：{description}",
        "size": size,
        "title": title,
        "description": description,
        "candidateDataBindings": _candidate_bindings(card_spec, path),
        "candidateEventCandidates": [],
        "candidateAssetIds": [],
    }


def _wrap_content(content: dict[str, Any]) -> dict[str, Any]:
    session_id = uuid.uuid4().hex
    interaction_id = uuid.uuid4().hex
    original = content.get("userQuery")
    utterance = original if isinstance(original, str) else ""
    return {
        "content": dict(content),
        "deviceInfo": {"countryCode": "CN"},
        "session": {
            "sessionId": session_id,
            "interactionId": interaction_id,
            "isNew": True,
        },
        "userAuth": {"user": {"userId": "jsx-e2e-user"}},
        "utterance": {"original": utterance, "type": "text"},
        "version": "1.0",
        "bundleName": str(content.get("bundleName") or ""),
    }


def load_cardspec_request(path: Path) -> dict[str, Any]:
    """直接读取 cardSpec 文件作为平台请求 payload。

    cardSpec 文件本身就是完整的平台请求格式（含 content/deviceInfo/session/userAuth
    等顶层字段），无需经过 cardspec_to_content + _wrap_content 转换。
    """
    return _read_json_object(path)


def _parse_legacy_stream_content(stream_content: str) -> dict[str, Any]:
    header_start = stream_content.find("type=")
    if header_start < 0:
        raise ValueError("final 帧缺少平台业务结果")
    explanation = stream_content[:header_start].removesuffix("：")
    legacy_content = stream_content[header_start:]
    header_text, data_and_tail = legacy_content.split(" data=", 1)
    data_text, status_and_tail = data_and_tail.rsplit(" status=", 1)
    status_text, error_code_and_tail = status_and_tail.split(" errorCode=", 1)
    error_code_text, error_text = error_code_and_tail.split(" error=", 1)
    header_match = _HEADER_PATTERN.fullmatch(header_text)
    if header_match is None:
        raise ValueError("final 帧平台业务结果格式不受支持")
    return {
        "type": ast.literal_eval(header_match.group("type")),
        "tool": ast.literal_eval(header_match.group("tool")),
        "operation": ast.literal_eval(header_match.group("operation")),
        "requestId": ast.literal_eval(header_match.group("request_id")),
        "data": ast.literal_eval(data_text),
        "status": ast.literal_eval(status_text),
        "errorCode": ast.literal_eval(error_code_text),
        "error": ast.literal_eval(error_text),
        "explanation": explanation,
    }


def _stream_info(frame: object) -> dict[str, Any] | None:
    if not isinstance(frame, dict):
        return None
    reply = frame.get("reply")
    if not isinstance(reply, dict):
        return None
    stream_info = reply.get("streamInfo")
    return stream_info if isinstance(stream_info, dict) else None


async def call_platform(
    url: str,
    payload: dict[str, Any],
    *,
    timeout: float,
    show_frames: bool,
) -> dict[str, Any]:
    if timeout <= 0:
        raise ValueError("timeout 必须大于 0")
    open_timeout = min(timeout, 30.0)
    async with asyncio.timeout(timeout):
        async with websockets.connect(
            url,
            open_timeout=open_timeout,
            max_size=None,
        ) as websocket:
            await websocket.send(json.dumps(payload, ensure_ascii=False))
            async for raw_message in websocket:
                try:
                    frame = json.loads(raw_message)
                except (json.JSONDecodeError, TypeError, UnicodeDecodeError) as exc:
                    raise ValueError("平台返回了非法 JSON 帧") from exc
                if show_frames:
                    print(json.dumps(frame, ensure_ascii=False, indent=2), flush=True)
                stream_info = _stream_info(frame)
                if stream_info is None:
                    continue
                if stream_info.get("streamType") == "final":
                    if not isinstance(frame, dict):
                        raise ValueError("平台 final 帧必须是对象")
                    return frame
    raise RuntimeError("平台 WebSocket 在 final 帧之前关闭")


def _business_result(frame: dict[str, Any]) -> dict[str, Any]:
    if frame.get("errorCode") != "0":
        raise RuntimeError(f"平台传输失败：{frame.get('errorMessage')!r}")
    stream_info = _stream_info(frame)
    if stream_info is None:
        raise ValueError("平台 final 帧缺少 streamInfo")
    stream_content = stream_info.get("streamContent")
    if not isinstance(stream_content, str):
        raise ValueError("平台 final 帧缺少字符串 streamContent")
    return _parse_legacy_stream_content(stream_content)


def _business_succeeded(result: dict[str, Any]) -> bool:
    if result.get("status") != "success" or result.get("errorCode"):
        return False
    data = result.get("data")
    if not isinstance(data, dict):
        return False
    status = data.get("status")
    artifact_url = data.get("artifactUrl")
    valid_status = status in {"success", "degraded"}
    valid_url = isinstance(artifact_url, str) and bool(artifact_url.strip())
    return valid_status and valid_url


async def _run_case(
    args: argparse.Namespace,
    path: Path,
    run_dir: Path,
    position: int,
) -> CaseResult:
    task_num = _task_index(path)
    try:
        payload = load_cardspec_request(path)
        content = payload.get("content", {})
        title = content.get("title", "")
        size = content.get("size", "")
        caps = [b.get("capabilityId", "?") for b in content.get("candidateDataBindings", [])]
        print(f"[q{task_num}] {title} | size={size} | caps={caps}", flush=True)

        t0 = time.perf_counter()
        t0_epoch = time.time()
        frame = await call_platform(
            args.url,
            payload,
            timeout=args.timeout,
            show_frames=args.show_frames,
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        result = _business_result(frame)
    except (OSError, ValueError, RuntimeError) as exc:
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2) if "t0" in dir() else 0
        print(f"       ERROR {type(exc).__name__}: {exc} | {elapsed_ms}ms", flush=True)
        return CaseResult(
            path,
            False,
            True,
            index=task_num,
            error_message=f"{type(exc).__name__}: {exc}",
        )
    succeeded = _business_succeeded(result)
    data = result.get("data", {}) if isinstance(result.get("data"), dict) else {}
    status_str = data.get("status", "unknown")
    icon = "OK" if status_str == "success" else ("DEG" if status_str == "degraded" else "FAIL")
    print(f"       {icon} {status_str} | {elapsed_ms}ms", flush=True)

    # 落盘 response
    response_path = run_dir / f"q{task_num}_response.json"
    response_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    # 提取 artifact 信息并下载到 md/ 子目录
    artifact_url = data.get("artifactUrl", "")
    artifact_digest = data.get("artifactDigest", "")
    artifact_downloaded = False
    md_dir = run_dir / "md"
    md_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = md_dir / f"q{task_num}_artifact.md"
    if isinstance(artifact_url, str) and artifact_url:
        artifact_downloaded = _fetch_artifact(artifact_url, artifact_path)

    # 从 workspace 抢取 bridge 落盘的 raw 文件（jsx/a2ui/trace/rejected/context）
    _collect_workspace_raw_files(run_dir, task_num, t0_epoch)

    # fallback：如果 raw_a2ui 抢取失败，从 artifact.md 提取 DSL
    dsl_file = run_dir / "dsl" / f"q{task_num}.jsonl"
    if artifact_downloaded and not dsl_file.exists():
        dsl_content = _convert_md_to_dsl(
            artifact_path.read_text(encoding="utf-8"), size=data.get("suggestSize", data.get("size", "2x2"))
        )
        if dsl_content:
            dsl_file.write_text(dsl_content, encoding="utf-8")

    # 落盘 meta
    meta = {
        "index": task_num,
        "title": data.get("title", ""),
        "size": data.get("suggestSize", data.get("size", "")),
        "status": data.get("status", "unknown"),
        "errorCode": data.get("errorCode", ""),
        "message": data.get("message", ""),
        "artifactUrl": artifact_url,
        "artifactDigest": artifact_digest,
        "artifactDownloaded": artifact_downloaded,
        "elapsed_ms": elapsed_ms,
    }
    meta_path = run_dir / f"q{task_num}_meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return CaseResult(
        path,
        succeeded,
        False,
        index=task_num,
        response=result,
        elapsed_ms=elapsed_ms,
        artifact_url=artifact_url,
        artifact_digest=artifact_digest,
        artifact_downloaded=artifact_downloaded,
    )


async def async_main(args: argparse.Namespace) -> int:
    paths = select_cardspecs(args)
    run_dir = _create_run_dir(args.output_dir, args.round)
    print(f"Server: {args.url}", flush=True)
    print(f"输出目录: {run_dir}", flush=True)
    print(f"任务总数: {len(paths)}", flush=True)
    print(
        "请确认平台已关闭模板方案并开启 JSX 方案；服务日志应出现 jsx_generation_started。",
        flush=True,
    )
    results: list[CaseResult] = []
    total = len(paths)
    for position, path in enumerate(paths, start=1):
        results.append(await _run_case(args, path, run_dir, position))
    succeeded = sum(result.succeeded for result in results)
    infrastructure_errors = sum(result.infrastructure_error for result in results)
    artifact_downloaded = sum(result.artifact_downloaded for result in results)

    # 写 summary.json
    summary = {
        "round": run_dir.name,
        "operation": "generateWidgetCard",
        "total": total,
        "success": succeeded,
        "failed": total - succeeded,
        "infrastructureErrors": infrastructure_errors,
        "artifactDownloaded": artifact_downloaded,
        "results": [
            {
                "index": r.index,
                "file": r.path.name,
                "status": "success" if r.succeeded else "failed",
                "artifactUrl": r.artifact_url,
                "artifactDigest": r.artifact_digest,
                "artifactDownloaded": r.artifact_downloaded,
                "elapsed_ms": r.elapsed_ms,
                "errorCode": r.error_message,
            }
            for r in results
        ],
    }
    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        f"汇总：总数={total}，成功={succeeded}，"
        f"失败={total - succeeded}，基础设施错误={infrastructure_errors}，"
        f"artifact下载={artifact_downloaded}",
        flush=True,
    )
    print(f"结果目录: {run_dir}", flush=True)
    if succeeded == total:
        return 0
    return 2 if infrastructure_errors else 1


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return asyncio.run(async_main(args))
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"[E2E] {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
