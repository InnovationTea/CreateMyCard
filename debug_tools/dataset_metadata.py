"""数据集版本读取与旧目录名称兼容；不参与业务协议。"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

LEGACY_DATASETS = {
    "20261015_open_domain": "open_domain",
    "20261016_online_updated": "online_updated",
    "20261016_request_baseline": "request_baseline",
}


def read_version(directory: Path) -> dict[str, Any]:
    path = directory / "version.json"
    value: dict[str, Any] = {}
    if path.is_file():
        document = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(document, dict):
            raise ValueError(f"数据集版本必须是对象：{path}")
        if set(document) != {"current_version", "update_date", "history_versions"}:
            raise ValueError(f"数据集版本字段不完整：{path}")
        current = document.get("current_version")
        if not isinstance(current, str) or not re.fullmatch(r"v[1-9][0-9]*", current):
            raise ValueError(f"数据集版本号无效：{path}")
        updated = document.get("update_date")
        if not isinstance(updated, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", updated):
            raise ValueError(f"数据集更新日期无效：{path}")
        date.fromisoformat(updated)
        history = document.get("history_versions")
        if not isinstance(history, list):
            raise ValueError(f"数据集版本历史必须是数组：{path}")
        seen: set[str] = set()
        for entry in history:
            if not isinstance(entry, dict):
                raise ValueError(f"数据集历史版本必须是对象：{path}")
            entry_version = entry.get("version")
            if not isinstance(entry_version, str):
                raise ValueError(f"数据集历史版本号无效：{path}")
            if not re.fullmatch(r"v[1-9][0-9]*", entry_version):
                raise ValueError(f"数据集历史版本号无效：{path}")
            if entry_version in seen:
                raise ValueError(f"数据集历史版本号重复：{path}")
            seen.add(entry_version)
            if not entry.get("changes") or not isinstance(entry.get("commits"), list):
                raise ValueError(f"数据集历史缺少变更或提交记录：{path}")
            entry_date = entry.get("update_date")
            if not isinstance(entry_date, str):
                raise ValueError(f"数据集历史日期无效：{path}")
            date.fromisoformat(entry_date)
        value = document
    return value
