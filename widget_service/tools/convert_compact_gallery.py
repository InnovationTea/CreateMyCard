"""批量将 Gallery 中的 Compact DSL 转换为正式 A2UI。"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

os.environ.setdefault("WIDGET_SERVICE_LOCAL_FLAG", "true")


def _ensure_local_hostname_resolution() -> None:
    """本地调试机 hostname 不可解析时，仅为本机名回退到 loopback。"""

    hostname = socket.gethostname()
    try:
        socket.gethostbyname(hostname)
    except OSError:
        original_resolver = socket.gethostbyname

        def resolve(name: str) -> str:
            if name == hostname:
                return "127.0.0.1"
            return original_resolver(name)

        socket.gethostbyname = resolve


_ensure_local_hostname_resolution()
CLOUD_ROOT = Path(__file__).resolve().parents[1] / "cloud"
sys.path.insert(0, str(CLOUD_ROOT))

from services.compact_dsl_a2ui_converter import (  # noqa: E402
    CompactDslConversionError,
    convert_compact_dsl_to_a2ui,
)


@dataclass(frozen=True)
class ConversionRequest:
    key: str
    source: str
    size: str
    preview: bool
    app_version: str | None


def _parse_request(value: Any, index: int) -> ConversionRequest:
    if not isinstance(value, dict):
        raise ValueError(f"requests[{index}] must be an object")
    key = value.get("key")
    source = value.get("source")
    size = value.get("size")
    preview = value.get("preview", False)
    app_version = value.get("appVersion")
    if not isinstance(key, str) or not key:
        raise ValueError(f"requests[{index}].key must be a non-empty string")
    if not isinstance(source, str) or not source:
        raise ValueError(f"requests[{index}].source must be a non-empty string")
    if size not in {"2x2", "2x4"}:
        raise ValueError(f"requests[{index}].size must be 2x2 or 2x4")
    if not isinstance(preview, bool):
        raise ValueError(f"requests[{index}].preview must be a boolean")
    if app_version is not None and not isinstance(app_version, str):
        raise ValueError(f"requests[{index}].appVersion must be a string or null")
    return ConversionRequest(key, source, size, preview, app_version)


def convert_requests(payload: Any) -> dict[str, list[dict[str, str]]]:
    if not isinstance(payload, dict):
        raise ValueError("input must be an object")
    raw_requests = payload.get("requests")
    if not isinstance(raw_requests, list):
        raise ValueError("input.requests must be an array")
    requests = [_parse_request(value, index) for index, value in enumerate(raw_requests)]
    results: list[dict[str, str]] = []
    for request in requests:
        profile = {"version": "v0.9"}
        if request.app_version:
            profile["appVersion"] = request.app_version
        try:
            genui = convert_compact_dsl_to_a2ui(
                request.source,
                size=request.size,
                protocol_profile=profile,
                skip_compact_dsl_validation=request.preview,
            )
            results.append({"key": request.key, "genui": genui})
        except CompactDslConversionError as exc:
            results.append({"key": request.key, "error": str(exc)})
    return {"results": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    converted = convert_requests(payload)
    args.output.write_text(
        json.dumps(converted, ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
