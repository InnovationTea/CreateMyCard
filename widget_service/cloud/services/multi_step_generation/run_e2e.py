#!/usr/bin/env python3
"""从本地 CardSpec 用例调用平台 generateWidgetCard WebSocket 端到端链路。"""

from __future__ import annotations

import argparse
import ast
import asyncio
import json
import re
import shutil
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
import urllib3
import websockets

CLOUD_DIR = Path(__file__).resolve().parents[2]
if str(CLOUD_DIR) not in sys.path:
    sys.path.insert(0, str(CLOUD_DIR))

from services.multi_step_generation.jsx_runner.run_summary import (  # noqa: E402
    build_run_summary,
    render_run_summary_markdown,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MULTI_STEP_ROOT = Path(__file__).resolve().parent
DEFAULT_CARDSPEC_DIR = MULTI_STEP_ROOT / "cardSpec"
DEFAULT_OUTPUT_ROOT = MULTI_STEP_ROOT / "output"
WORKSPACE_DIR = MULTI_STEP_ROOT / "workspace"
E2E_CAPTURE_ROOT = WORKSPACE_DIR / "e2e_capture"
DEFAULT_WS_URL = "ws://localhost:8855/api/v1/ws/tools/generateWidgetCard"
DEFAULT_TIMEOUT_SECONDS = 600.0
_BEIJING_TIMEZONE = timezone(timedelta(hours=8))
_E2E_CAPTURE_MARKER = ".enabled"
_HEADER_PATTERN = re.compile(
    r"^type=(?P<type>'(?:\\.|[^'])*') "
    r"tool=(?P<tool>'(?:\\.|[^'])*') "
    r"operation=(?P<operation>'(?:\\.|[^'])*') "
    r"requestId=(?P<request_id>None|'(?:\\.|[^'])*')$"
)
_RAW_COMPONENT_PATTERN = re.compile(
    r"^raw_(?:jsx|a2ui|trace|context)_(?P<component>CardGenerated_[A-Za-z0-9_$]+)"
)
_RAW_REJECTED_PATTERN = re.compile(
    r"^raw_rejected_(?P<component>CardGenerated_[A-Za-z0-9_$]+)_turn(?P<turn>\d+)\.jsx$"
)


@dataclass(frozen=True, slots=True)
class E2ECaptureSession:
    """一次本地 E2E 请求对应的隔离诊断目录。"""

    session_id: str
    directory: Path


@dataclass(frozen=True, slots=True)
class CapturedArtifacts:
    """整理为标准 JSX Runner run-dir 后的单卡产物。"""

    component_name: str
    jsx: str = ""
    a2ui: str = ""
    context: str = ""
    trace: dict[str, Any] = field(default_factory=dict)


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
    task: dict[str, Any] = field(default_factory=dict)
    captured: CapturedArtifacts | None = None


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
    name = round_name or datetime.now(_BEIJING_TIMEZONE).strftime(
        "round_%Y%m%d_%H%M%S",
    )
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


def _prepare_e2e_capture(payload: dict[str, Any]) -> E2ECaptureSession:
    """为本地 E2E 请求注册一个不会影响普通请求的采集 session。"""
    session = payload.get("session")
    if not isinstance(session, dict):
        raise ValueError("CardSpec session 必须是对象")
    session_id = uuid.uuid4().hex
    session["sessionId"] = session_id
    session["interactionId"] = uuid.uuid4().hex
    capture_directory = E2E_CAPTURE_ROOT / session_id
    capture_directory.mkdir(parents=True, exist_ok=False)
    marker_path = capture_directory / _E2E_CAPTURE_MARKER
    marker_path.write_text("local run_e2e capture\n", encoding="utf-8")
    return E2ECaptureSession(session_id=session_id, directory=capture_directory)


def _cleanup_e2e_capture(capture: E2ECaptureSession) -> None:
    """只清理本次创建的隔离采集目录。"""
    capture_root = E2E_CAPTURE_ROOT.resolve()
    capture_directory = capture.directory.resolve()
    if capture_directory.parent != capture_root:
        raise RuntimeError(f"拒绝清理非 E2E 采集目录：{capture_directory}")
    if capture_directory.exists():
        shutil.rmtree(capture_directory)


def _capture_component_name(capture_directory: Path) -> str:
    for pattern in ("raw_trace_*", "raw_jsx_*", "raw_a2ui_*"):
        for raw_path in sorted(capture_directory.glob(pattern)):
            match = _RAW_COMPONENT_PATTERN.match(raw_path.name)
            if match is not None:
                return match.group("component")
    return ""


def _copy_capture_file(source: Path, target: Path, run_dir: Path) -> str:
    if not source.is_file():
        return ""
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return target.relative_to(run_dir).as_posix()


def _read_capture_trace(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"[E2E] 读取 trace 失败 {path.name}: {type(exc).__name__}: {exc}",
            flush=True,
        )
        return {}
    return value if isinstance(value, dict) else {}


def _wrap_rejected_jsx(component_name: str, jsx: str) -> str:
    stripped = jsx.strip()
    if stripped.startswith("function "):
        return f"{stripped}\n"
    return f"function {component_name}() {{\n  return (\n{stripped}\n  );\n}}\n"


def _copy_rejected_artifacts(
    capture_directory: Path,
    run_dir: Path,
    component_name: str,
) -> None:
    for source in sorted(capture_directory.glob("raw_rejected_*.jsx")):
        match = _RAW_REJECTED_PATTERN.fullmatch(source.name)
        if match is None or match.group("component") != component_name:
            continue
        turn = int(match.group("turn"))
        target = run_dir / "jsx" / f"{component_name}.turn-{turn:02d}.rejected.jsx"
        target.parent.mkdir(parents=True, exist_ok=True)
        jsx = source.read_text(encoding="utf-8")
        target.write_text(_wrap_rejected_jsx(component_name, jsx), encoding="utf-8")


def _collect_capture_artifacts(
    run_dir: Path,
    task_num: int,
    capture: E2ECaptureSession,
) -> CapturedArtifacts | None:
    """将请求隔离目录中的文件整理为标准 JSX Runner 产物。"""
    component_name = _capture_component_name(capture.directory)
    if not component_name:
        return None
    jsx_source = capture.directory / f"raw_jsx_{component_name}.jsx"
    a2ui_source = capture.directory / f"raw_a2ui_{component_name}.json"
    trace_source = capture.directory / f"raw_trace_{component_name}.json"
    context_source = capture.directory / f"raw_context_{component_name}.json"

    jsx = _copy_capture_file(
        jsx_source,
        run_dir / "jsx" / f"{component_name}.jsx",
        run_dir,
    )
    a2ui = _copy_capture_file(
        a2ui_source,
        run_dir / "a2ui" / f"{component_name}.a2ui.json",
        run_dir,
    )
    context = _copy_capture_file(
        context_source,
        run_dir / "context" / f"{component_name}.context.json",
        run_dir,
    )
    _copy_capture_file(
        trace_source,
        run_dir / "jsx" / f"{component_name}.trace.json",
        run_dir,
    )
    if a2ui:
        _copy_capture_file(a2ui_source, run_dir / "dsl" / f"q{task_num}.jsonl", run_dir)
    _copy_rejected_artifacts(capture.directory, run_dir, component_name)
    return CapturedArtifacts(
        component_name=component_name,
        jsx=jsx,
        a2ui=a2ui,
        context=context,
        trace=_read_capture_trace(trace_source),
    )


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
            detail = "缺少合法的 capabilityId/arguments/writeResultTo"
            raise ValueError(f"CardSpec dataBindings[{index}] {detail}：{path}")
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
    task_num = _task_index(path) or position
    started = time.perf_counter()
    capture: E2ECaptureSession | None = None
    task: dict[str, Any] = {}
    try:
        payload = load_cardspec_request(path)
        content = payload.get("content")
        if not isinstance(content, dict):
            raise ValueError("CardSpec content 必须是对象")
        title = content.get("title", "")
        size = content.get("size", "")
        task = {
            "id": task_num,
            "size": size,
            "userQuery": content.get("userQuery") or title,
        }
        bindings = content.get("candidateDataBindings")
        caps = []
        if isinstance(bindings, list):
            for binding in bindings:
                if isinstance(binding, dict):
                    caps.append(binding.get("capabilityId", "?"))
        print(f"[q{task_num}] {title} | size={size} | caps={caps}", flush=True)

        capture = _prepare_e2e_capture(payload)
        frame = await call_platform(
            args.url,
            payload,
            timeout=args.timeout,
            show_frames=args.show_frames,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        result = _business_result(frame)
    except (OSError, ValueError, RuntimeError) as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        captured = _collect_capture_artifacts(run_dir, task_num, capture) if capture else None
        if capture is not None:
            _cleanup_e2e_capture(capture)
        print(f"       ERROR {type(exc).__name__}: {exc} | {elapsed_ms}ms", flush=True)
        return CaseResult(
            path,
            False,
            True,
            index=task_num,
            error_message=f"{type(exc).__name__}: {exc}",
            elapsed_ms=elapsed_ms,
            task=task,
            captured=captured,
        )
    captured = _collect_capture_artifacts(run_dir, task_num, capture)
    _cleanup_e2e_capture(capture)
    capture_error = ""
    if captured is None:
        capture_error = "本地 E2E 未收到 JSX 诊断产物，请确认服务已加载当前 Bridge 代码"
        print(f"       ERROR {capture_error}", flush=True)
    succeeded = _business_succeeded(result) and captured is not None
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

    # 本地采集没有 A2UI 时，从 artifact.md 提取最终 DSL。
    dsl_file = run_dir / "dsl" / f"q{task_num}.jsonl"
    if artifact_downloaded and not dsl_file.exists():
        fallback_size = data.get("suggestSize", data.get("size", "2x2"))
        dsl_content = _convert_md_to_dsl(
            artifact_path.read_text(encoding="utf-8"),
            size=str(fallback_size),
        )
        if dsl_content:
            dsl_file.parent.mkdir(parents=True, exist_ok=True)
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
        bool(capture_error),
        index=task_num,
        response=result,
        elapsed_ms=elapsed_ms,
        artifact_url=artifact_url,
        artifact_digest=artifact_digest,
        artifact_downloaded=artifact_downloaded,
        error_message=capture_error,
        task=task,
        captured=captured,
    )


def _case_business_status(result: CaseResult) -> str:
    response = result.response
    if not isinstance(response, dict):
        return "failed"
    data = response.get("data")
    if not isinstance(data, dict):
        return "failed"
    status = data.get("status")
    return status if isinstance(status, str) else "failed"


def _trace_entry(result: CaseResult) -> dict[str, Any]:
    trace = dict(result.captured.trace) if result.captured is not None else {}
    component_name = result.captured.component_name if result.captured is not None else ""
    trace.setdefault("task_id", result.index)
    trace.setdefault("component_name", component_name or f"CardGenerated_{result.index}")
    trace.setdefault("task", result.task)
    trace.setdefault("elapsed_seconds", round(result.elapsed_ms / 1000, 2))
    trace.setdefault("turn_trace", [])
    trace.setdefault("validation_reports", [])
    if result.succeeded:
        semantic_status = str(trace.get("semantic_status") or "completed")
        allowed_statuses = {"completed", "partial", "insufficient_input", "unverified"}
        if semantic_status not in allowed_statuses:
            semantic_status = "unverified"
        if _case_business_status(result) == "degraded" and semantic_status == "completed":
            semantic_status = "partial"
        browser_validation = trace.get("browser_validation")
        validation_status = "passed" if browser_validation == "enabled" else "unverified"
        if semantic_status == "completed":
            status = "completed" if validation_status == "passed" else "completed_unverified"
        elif semantic_status in {"partial", "unverified"}:
            status = "partial" if validation_status == "passed" else "partial_unverified"
        else:
            status = "insufficient_input"
        trace["status"] = status
        trace["semantic_status"] = semantic_status
        trace["validation_status"] = validation_status
    else:
        trace["status"] = "failed"
        trace["error"] = result.error_message or "平台 E2E 生成失败"
    return trace


def _manifest_card(result: CaseResult, trace: dict[str, Any]) -> dict[str, Any] | None:
    captured = result.captured
    if captured is None or not captured.jsx:
        return None
    card = {
        "taskId": result.index,
        "componentName": captured.component_name,
        "status": trace.get("status", "completed"),
        "semanticStatus": trace.get("semantic_status", "completed"),
        "validationStatus": trace.get("validation_status", "unknown"),
        "jsx": captured.jsx,
    }
    if captured.a2ui:
        card["a2ui"] = captured.a2ui
    if captured.context:
        card["context"] = captured.context
    return card


def _first_trace_value(traces: list[dict[str, Any]], key: str, fallback: Any) -> Any:
    for trace in traces:
        value = trace.get(key)
        if value not in (None, ""):
            return value
    return fallback


def _build_manifest(
    run_dir: Path,
    paths: list[Path],
    results: list[CaseResult],
    traces: list[dict[str, Any]],
    started_at: datetime,
    elapsed_seconds: float,
) -> dict[str, Any]:
    cards: list[dict[str, Any]] = []
    for result, trace in zip(results, traces, strict=True):
        card = _manifest_card(result, trace)
        if card is not None:
            cards.append(card)
    completed = 0
    partial = 0
    insufficient = 0
    unverified = 0
    failed = 0
    for trace in traces:
        if trace.get("status") == "failed":
            failed += 1
            continue
        semantic_status = trace.get("semantic_status")
        if semantic_status == "completed":
            completed += 1
        elif semantic_status in {"partial", "unverified"}:
            partial += 1
        elif semantic_status == "insufficient_input":
            insufficient += 1
        if trace.get("validation_status") == "unverified":
            unverified += 1
    has_warnings = bool(partial or insufficient or unverified)
    if failed:
        status = "partial_failed"
    elif has_warnings:
        status = "completed_with_warnings"
    else:
        status = "completed"
    browser_validation = _first_trace_value(traces, "browser_validation", "unknown")
    layout_validation = _first_trace_value(
        traces,
        "layout_budget_validation",
        "unknown",
    )
    return {
        "runId": run_dir.name,
        "status": status,
        "startedAt": started_at.isoformat(),
        "finishedAt": datetime.now(_BEIJING_TIMEZONE).isoformat(),
        "elapsedSeconds": round(elapsed_seconds, 2),
        "model": _first_trace_value(traces, "model", "platform-configured"),
        "provider": _first_trace_value(traces, "provider", "deepseek"),
        "thinkingMode": _first_trace_value(traces, "thinking_mode", "unknown"),
        "validationMode": _first_trace_value(traces, "validation_mode", "unknown"),
        "browserValidationEnabled": browser_validation == "enabled",
        "layoutBudgetValidationEnabled": layout_validation == "enabled",
        "input": str(paths[0].parent) if paths else "",
        "requestedTasks": len(paths),
        "attemptedTasks": len(results),
        "completedTasks": completed,
        "partialTasks": partial,
        "insufficientInputTasks": insufficient,
        "unverifiedTasks": unverified,
        "failedTasks": failed,
        "cards": cards,
        "failures": [
            {
                "taskId": result.index,
                "error": result.error_message,
            }
            for result in results
            if not result.succeeded
        ],
        "summary": {"json": "summary.json", "markdown": "summary.md"},
    }


def _platform_e2e_summary(results: list[CaseResult]) -> dict[str, Any]:
    succeeded = sum(result.succeeded for result in results)
    return {
        "operation": "generateWidgetCard",
        "total": len(results),
        "success": succeeded,
        "failed": len(results) - succeeded,
        "infrastructureErrors": sum(result.infrastructure_error for result in results),
        "artifactDownloaded": sum(result.artifact_downloaded for result in results),
        "results": [
            {
                "index": result.index,
                "file": result.path.name,
                "status": "success" if result.succeeded else "failed",
                "artifactUrl": result.artifact_url,
                "artifactDigest": result.artifact_digest,
                "artifactDownloaded": result.artifact_downloaded,
                "elapsed_ms": result.elapsed_ms,
                "errorCode": result.error_message,
            }
            for result in results
        ],
    }


def _persist_run_reports(
    run_dir: Path,
    manifest: dict[str, Any],
    traces: list[dict[str, Any]],
    results: list[CaseResult],
) -> None:
    platform_summary = _platform_e2e_summary(results)
    summary = build_run_summary(manifest, traces)
    summary["platformE2E"] = platform_summary
    markdown = render_run_summary_markdown(summary)
    infrastructure_errors = platform_summary.get("infrastructureErrors", 0)
    artifact_downloaded = platform_summary.get("artifactDownloaded", 0)
    markdown += (
        "\n\n## Platform E2E\n\n"
        f"- Infrastructure errors: **{infrastructure_errors}**\n"
        f"- Artifacts downloaded: **{artifact_downloaded}**\n"
    )
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (run_dir / "traces.json").write_text(
        json.dumps(traces, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (run_dir / "summary.md").write_text(f"{markdown.rstrip()}\n", encoding="utf-8")


async def async_main(args: argparse.Namespace) -> int:
    paths = select_cardspecs(args)
    run_dir = _create_run_dir(args.output_dir, args.round)
    started_at = datetime.now(_BEIJING_TIMEZONE)
    started = time.perf_counter()
    print(f"Server: {args.url}", flush=True)
    print(f"输出目录: {run_dir}", flush=True)
    print(f"任务总数: {len(paths)}", flush=True)
    print(
        "请确认平台已关闭模板方案并开启 JSX 方案；服务日志应出现 jsx_generation_started。",
        flush=True,
    )
    results: list[CaseResult] = []
    for position, path in enumerate(paths, start=1):
        results.append(await _run_case(args, path, run_dir, position))
    traces = [_trace_entry(result) for result in results]
    elapsed_seconds = time.perf_counter() - started
    manifest = _build_manifest(
        run_dir,
        paths,
        results,
        traces,
        started_at,
        elapsed_seconds,
    )
    _persist_run_reports(run_dir, manifest, traces, results)
    total = len(results)
    succeeded = sum(result.succeeded for result in results)
    infrastructure_errors = sum(result.infrastructure_error for result in results)
    artifact_downloaded = sum(result.artifact_downloaded for result in results)

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
