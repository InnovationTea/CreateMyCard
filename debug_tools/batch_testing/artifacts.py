"""批跑 artifact 下载、拆分与保存工具。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

_BLOCK_PATTERN = re.compile(
    r"```(?P<name>[a-zA-Z0-9_-]+)\r?\n(?P<body>.*?)\r?\n```",
    re.DOTALL,
)
DEFAULT_MAX_ARTIFACT_BYTES = 20 * 1024 * 1024


def download_artifact(
    artifact_url: str,
    output_path: Path,
    artifact_roots: tuple[Path, ...],
    max_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES,
) -> str:
    """优先读取本地 mock artifact，必要时下载服务返回的 HTTP(S) URL。"""

    parsed_url = urlsplit(artifact_url)
    name = Path(parsed_url.path).name or Path(parsed_url.netloc).name
    if not name or name in {".", ".."}:
        raise ValueError("artifactUrl 缺少文件名")
    for root in artifact_roots:
        candidates = (root / name, root / "mock_obs" / name)
        for candidate in candidates:
            if not candidate.is_file():
                continue
            content = candidate.read_bytes()
            if len(content) > max_bytes:
                raise ValueError("artifact 超过大小限制")
            output_path.write_bytes(content)
            return content.decode("utf-8")
    if parsed_url.scheme not in {"http", "https"}:
        raise ValueError("artifactUrl 不是受支持的 HTTP(S) 地址")
    request = Request(artifact_url, headers={"User-Agent": "CreateMyCard-batch"})
    with urlopen(request, timeout=35) as response:  # nosec B310: URL 来自受信微服务
        content = response.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise ValueError("artifact 超过大小限制")
    output_path.write_bytes(content)
    return content.decode("utf-8")


def parse_artifact_blocks(content: str) -> dict[str, Any]:
    blocks: dict[str, Any] = {}
    for match in _BLOCK_PATTERN.finditer(content):
        name = match.group("name").lower()
        if name in blocks:
            raise ValueError(f"artifact 存在重复 block: {name}")
        body = match.group("body")
        try:
            blocks[name] = json.loads(body)
        except json.JSONDecodeError:
            blocks[name] = body
    return blocks


def write_artifact_blocks(result_dir: Path, blocks: dict[str, Any]) -> None:
    block_dir = result_dir / "blocks"
    block_dir.mkdir(parents=True, exist_ok=True)
    for name, value in blocks.items():
        suffix = ".json" if not isinstance(value, str) else ".txt"
        target = block_dir / f"{name}{suffix}"
        if isinstance(value, str):
            target.write_text(value, encoding="utf-8")
        else:
            target.write_text(
                json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
