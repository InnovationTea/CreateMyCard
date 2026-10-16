"""后处理插件共享的小型文件工具。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from debug_tools.file_io import atomic_write_text


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    """以同目录临时文件原子替换 JSON 目标。"""

    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")
