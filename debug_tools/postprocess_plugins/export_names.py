"""共享产物命名；样本和 Trace 的内部标识保持原样。"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from debug_tools.dataset_metadata import LEGACY_DATASETS


def run_summary(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "summary.json"
    result: dict[str, Any] = {}
    if path.is_file():
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("批跑摘要必须是对象")
        result = value
    return result


def dataset_name(summary: dict[str, Any]) -> str:
    value = summary.get("datasetId")
    name = value if isinstance(value, str) else ""
    return LEGACY_DATASETS.get(name, name)


def _safe_name(name: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", name):
        return name
    normalized = re.sub(r"[^A-Za-z0-9._-]", "_", name).strip("._-")[:60]
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]
    return f"{normalized or 'dataset'}_{digest}"


def sample_stem(sample_id: str, summary: dict[str, Any]) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", sample_id):
        raise ValueError("样本标识无效")
    name = dataset_name(summary)
    stem = sample_id
    if name:
        match = re.fullmatch(r"Q([0-9]+)", sample_id)
        if match is not None:
            stem = "Q" + match.group(1).zfill(4)
        stem = f"{stem}_{_safe_name(name)}"
    return stem


def gallery_name(summary: dict[str, Any], kind: str) -> str:
    name = dataset_name(summary)
    return f"{_safe_name(name)}_{kind}_gallery.html" if name else "gallery.html"


def gallery_title(title: str, summary: dict[str, Any]) -> str:
    name = dataset_name(summary) or "未记录数据集"
    version = summary.get("datasetVersion")
    current = version.get("current_version") if isinstance(version, dict) else None
    label = f"{name} · {current}" if current else name
    return f"{title} · {label}"
