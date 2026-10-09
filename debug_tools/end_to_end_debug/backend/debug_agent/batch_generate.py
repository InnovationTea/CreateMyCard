"""批量调用 generateWidgetCardCompactDsl 并拆分 artifact 代码块。

用法示例::

    python -m debug_tools.end_to_end_debug.backend.debug_agent.batch_generate \
        --input-dir ./requests --output-dir ./batch-results

输入目录中的每个 ``*.json`` 文件应包含一个 GenerateWidgetCardRequest 对象。
请求按文件名排序、串行执行；单个请求失败不会阻止后续请求。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

from debug_tools.batch_testing.artifacts import (
    DEFAULT_MAX_ARTIFACT_BYTES,
    download_artifact,
    parse_artifact_blocks,
    write_artifact_blocks,
)
from debug_tools.paths import WIDGET_SERVICE_ROOT

from .schemas import DeviceDebugContext

_FUNCTION_NAME = "generateWidgetCardCompactDsl"


async def _invoke(
    endpoint: str,
    arguments: dict[str, Any],
    context: DeviceDebugContext,
    timeout_seconds: float,
) -> dict[str, Any]:
    """调用单个 WebSocket 请求并等待 final 帧。"""
    import websockets

    from .upstream_ws_client import UpstreamToolError, parse_legacy_stream_content

    session_id = uuid.uuid4().hex
    interaction_id = uuid.uuid4().hex
    request_id = f"{session_id}&{interaction_id}"
    business = dict(arguments)
    bundle_name = str(business.get("bundleName") or "com.omega_w_0823.hmservice")
    business.pop("bundleName", None)
    business.pop("uid", None)
    payload = {
        "content": {"odid": context.odid, **business},
        "deviceInfo": {
            "countryCode": context.countryCode,
            "deviceFormation": "phone",
            "deviceType": 0,
            "locale": context.locale,
            "phoneType": context.phoneType,
            "prdVer": context.appVersion,
            "sysVer": "HarmonyOS",
            "romVersion": context.romVersion,
            "deviceId": context.deviceId,
        },
        "pagination": {"limit": 5, "start": ""},
        "session": {"sessionId": session_id, "interactionId": interaction_id, "isNew": False},
        "userAuth": {"user": {"userId": context.uid}},
        "utterance": {"original": str(arguments.get("userQuery", "")), "type": "text"},
        "version": "1.0",
        "bundleName": bundle_name,
    }
    frames: list[dict[str, Any]] = []
    try:
        async with websockets.connect(endpoint, open_timeout=10, close_timeout=2) as websocket:
            await websocket.send(json.dumps(payload, ensure_ascii=False))
            while True:
                raw = await asyncio.wait_for(websocket.recv(), timeout_seconds)
                if not isinstance(raw, str):
                    raise UpstreamToolError("正式工具返回非文本 WebSocket 帧")
                try:
                    frame = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise UpstreamToolError("正式工具返回非法 JSON") from exc
                if not isinstance(frame, dict):
                    raise UpstreamToolError("正式工具返回帧不是对象")
                frames.append(frame)
                outer_error = frame.get("errorCode")
                if outer_error not in (None, "", "0", 0):
                    raise UpstreamToolError(f"正式工具外层错误: {outer_error}")
                reply = frame.get("reply")
                stream_info = reply.get("streamInfo") if isinstance(reply, dict) else None
                if not isinstance(stream_info, dict):
                    raise UpstreamToolError("正式工具帧缺少 streamInfo")
                if stream_info.get("streamType", "final") in {"start", "partial", "command"}:
                    continue
                if stream_info.get("streamType", "final") != "final":
                    raise UpstreamToolError("正式工具返回未知流类型")
                content = stream_info.get("streamContent")
                if not isinstance(content, str) or not content:
                    raise UpstreamToolError("正式工具 final 缺少 streamContent")
                parsed = parse_legacy_stream_content(content)
                if parsed.get("requestId") != request_id:
                    raise UpstreamToolError("正式工具 requestId 与当前 invoke 不匹配")
                if parsed.get("operation") != _FUNCTION_NAME:
                    raise UpstreamToolError("正式工具 operation 与当前 invoke 不匹配")
                data = parsed.get("data")
                return {
                    "status": str(parsed.get("status") or "failed"),
                    "errorCode": str(parsed.get("errorCode") or ""),
                    "error": str(parsed.get("error") or ""),
                    "data": data if isinstance(data, dict) else {},
                    "requestId": request_id,
                    "frames": frames,
                }
    except TimeoutError as exc:
        raise UpstreamToolError("正式工具 WebSocket 调用超时") from exc
    except (OSError, websockets.WebSocketException) as exc:
        raise UpstreamToolError(f"正式工具 WebSocket 调用失败: {type(exc).__name__}") from exc


def _context_from_request(
    arguments: dict[str, Any], defaults: argparse.Namespace
) -> DeviceDebugContext:
    device = arguments.get("device") if isinstance(arguments.get("device"), dict) else {}
    return DeviceDebugContext(
        uid=str(arguments.get("uid") or defaults.uid),
        odid=str(device.get("odid") or arguments.get("odid") or defaults.device_id),
        deviceId=str(device.get("deviceId") or defaults.device_id),
        phoneType=str(device.get("deviceType") or defaults.phone_type),
        appVersion=str(arguments.get("prdVer") or defaults.app_version),
        romVersion=str(device.get("romVersion") or defaults.rom_version),
        locale=str(arguments.get("locale") or defaults.locale),
        countryCode=defaults.country_code,
    )


async def _run(args: argparse.Namespace) -> int:
    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    roots = tuple(path.resolve() for path in args.artifact_root)
    summary: list[dict[str, Any]] = []
    input_paths = sorted(input_dir.glob("*.json"))
    if not input_paths:
        (output_dir / "summary.json").write_text("[]\n", encoding="utf-8")
        return 1
    for input_path in input_paths:
        result_dir = output_dir / input_path.stem
        result_dir.mkdir(parents=True, exist_ok=True)
        record: dict[str, Any] = {"input": str(input_path), "status": "failed"}
        try:
            arguments = json.loads(input_path.read_text(encoding="utf-8"))
            if not isinstance(arguments, dict):
                raise ValueError("输入 JSON 根节点必须是对象")
            context = _context_from_request(arguments, args)
            response = await _invoke(args.endpoint, arguments, context, args.timeout)
            (result_dir / "response.json").write_text(
                json.dumps(response, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            record.update({"status": response["status"], "errorCode": response["errorCode"]})
            artifact_url = response["data"].get("artifactUrl")
            if artifact_url:
                artifact_path = result_dir / "artifact.md"
                artifact_text = download_artifact(
                    str(artifact_url), artifact_path, roots, args.max_bytes
                )
                blocks = parse_artifact_blocks(artifact_text)
                (result_dir / "blocks.json").write_text(
                    json.dumps(blocks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                write_artifact_blocks(result_dir, blocks)
                record["blockCount"] = len(blocks)
            else:
                record["error"] = "响应未返回 artifactUrl"
        except Exception as exc:  # 单个输入失败需继续批跑
            record.update({"error": f"{type(exc).__name__}: {exc}"})
            (result_dir / "error.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        summary.append(record)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0 if all(item["status"] in {"success", "degraded"} for item in summary) else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir", type=Path, required=True, help="GenerateWidgetCardRequest JSON 目录"
    )
    parser.add_argument("--output-dir", type=Path, required=True, help="批跑结果目录")
    parser.add_argument(
        "--endpoint",
        default="ws://127.0.0.1:8855/api/v1/ws/tools/generateWidgetCardCompactDsl",
        help="完整 WebSocket 地址；无 /api/v1 的服务请显式传入对应地址",
    )
    parser.add_argument("--timeout", type=float, default=180.0, help="单帧接收超时时间（秒）")
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_ARTIFACT_BYTES)
    parser.add_argument(
        "--artifact-root",
        type=Path,
        action="append",
        default=[],
        help="本地 mock artifact 搜索目录，可重复",
    )
    parser.add_argument("--uid", default="debug-user")
    parser.add_argument("--device-id", dest="device_id", default="debug-device")
    parser.add_argument("--phone-type", dest="phone_type", default="ALN-AL00")
    parser.add_argument("--app-version", dest="app_version", default="11.7.7.332")
    parser.add_argument("--rom-version", dest="rom_version", default="ALN-AL00 7.0.0.100")
    parser.add_argument("--locale", default="zh-CN")
    parser.add_argument("--country-code", dest="country_code", default="CN")
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not args.artifact_root:
        cloud_root = _repo_root() / "cloud"
        args.artifact_root = [
            cloud_root / "workspace",
            cloud_root,
            cloud_root / "mock_obs",
        ]
    return asyncio.run(_run(args))


def _repo_root() -> Path:
    return WIDGET_SERVICE_ROOT


if __name__ == "__main__":
    raise SystemExit(main())
