"""期望数据画廊：聚合导入的期望批次，支持分类／Query 筛选与删除。

画廊只暴露 ``external-quality`` 导入批次；删除操作同样只允许作用于这类批次，
避免误删普通批跑记录。删除单个样本后同步维护 ``summary.json`` 的样本数与
尺寸提示；删掉最后一个样本时整个批次目录一并移除。
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Protocol

from .expect_compare import (
    _ID_PATTERN,
    _actual_items,
    _expected_items,
    _public_side,
    _sample_list,
    expectation_runs,
)
from .quality_import import PURPOSE_ACTUAL, import_purpose
from .runner import atomic_write_json

SOURCE_TYPE = "external-quality"


class GalleryReader(Protocol):
    """画廊需要的读取接口；BatchRunManager 直接满足。"""

    output_root: Path

    def list_runs(self) -> list[dict[str, Any]]: ...

    def get_run(self, run_id: str) -> dict[str, Any]: ...

    def get_sample(self, run_id: str, sample_id: str) -> dict[str, Any]: ...


def _contains(item: dict[str, Any], keyword: str) -> bool:
    if not keyword:
        return True
    needle = keyword.casefold()
    fields = (
        item.get("query"), item.get("title"), item.get("sampleId"), item.get("runName"),
    )
    return any(needle in str(value or "").casefold() for value in fields)


def gallery(
    reader: GalleryReader,
    category: str = "",
    query: str = "",
) -> dict[str, Any]:
    """列出导入批次里的期望样本，按分类与关键词过滤。"""
    wanted_category = category.strip()
    keyword = query.strip()
    items: list[dict[str, Any]] = []
    batches: list[dict[str, Any]] = []
    categories: set[str] = set()
    warnings: list[str] = []
    for summary in expectation_runs(reader):
        run_id = str(summary.get("runId") or "")
        if not _ID_PATTERN.fullmatch(run_id):
            continue
        run_name = str(summary.get("name") or run_id)
        expected_items, run_warnings = _expected_items(reader, run_id, summary)
        warnings.extend(run_warnings)
        batches.append({
            "runId": run_id,
            "name": run_name,
            "category": str(summary.get("category") or "").strip(),
            "sampleCount": len(expected_items),
            "startedAt": summary.get("startedAt") or "",
        })
        for expected in expected_items:
            item = _public_item(run_id, run_name, expected)
            item_category = item["category"]
            if item_category:
                categories.add(item_category)
            if wanted_category and item_category != wanted_category:
                continue
            if not _contains(item, keyword):
                continue
            items.append(item)
    return {
        "items": items,
        "categories": sorted(categories),
        "batches": batches,
        "total": len(items),
        "warnings": warnings,
    }


def _public_item(run_id: str, run_name: str, expected: dict[str, Any]) -> dict[str, Any]:
    """把一条导入样本投影成画廊使用的形状；列表与单条读取共用。"""
    public = _public_side(expected)
    return {
        "runId": run_id,
        "runName": run_name,
        "sampleId": expected["sampleId"],
        "title": expected.get("title") or expected["sampleId"],
        "query": expected.get("query") or "",
        "size": expected.get("size") or "",
        "sizeSource": expected.get("sizeSource") or "",
        "category": str(expected.get("category") or "").strip(),
        "attempt": expected.get("attempt") or "",
        "genui": expected.get("genui") or "",
        "imageUrl": expected.get("imageUrl"),
        "explicit": public.get("explicit") or {},
        "fingerprint": {
            key: list(expected["fingerprint"].get(key) or [])
            for key in ("data", "actions", "icons")
        },
        "labels": public.get("labels") or {},
    }


def sample_detail(reader: GalleryReader, run_id: str, sample_id: str) -> dict[str, Any]:
    """读单条导入样本的完整内容，供导入页「编辑」时回填。

    只返回这一条：编辑一条不必把整批（含 genui 与截图）都拉下来。
    """
    if not _ID_PATTERN.fullmatch(run_id) or not _ID_PATTERN.fullmatch(sample_id):
        raise KeyError(run_id or sample_id)
    summary = reader.get_run(run_id)
    purpose = import_purpose(summary)
    if not purpose:
        raise ValueError("只有导入批次（期望输出或实际输出）里的样本可以编辑")
    read = _actual_items if purpose == PURPOSE_ACTUAL else _expected_items
    samples, _warnings = read(reader, run_id, summary)
    match = next((item for item in samples if item["sampleId"] == sample_id), None)
    if match is None:
        raise KeyError(sample_id)
    return _public_item(run_id, str(summary.get("name") or run_id), match)


def sample_ids(reader: GalleryReader, purpose: str = "") -> dict[str, Any]:
    """导入样本 ID 索引：只给 ID 与所属批次，供导入页提交前提示 ID 冲突。

    导入页不需要为了查重拉整份样本（列表里带 genui 与截图，几百条就是数 MB），
    因此这里只回 ID；``purpose`` 留空时两种用途都列。
    """
    wanted = purpose.strip()
    items: list[dict[str, str]] = []
    for summary in reader.list_runs():
        run_id = str(summary.get("runId") or "")
        if not _ID_PATTERN.fullmatch(run_id):
            continue
        side_purpose = import_purpose(summary)
        if not side_purpose or (wanted and side_purpose != wanted):
            continue
        read = _actual_items if side_purpose == PURPOSE_ACTUAL else _expected_items
        samples, _warnings = read(reader, run_id, summary)
        name = str(summary.get("name") or run_id)
        for sample in samples:
            items.append({
                "id": str(sample.get("sampleId") or ""),
                "runId": run_id,
                "runName": name,
            })
    return {"items": items, "total": len(items)}


def _safe_run_dir(root: Path, run_id: str) -> Path:
    if not _ID_PATTERN.fullmatch(run_id):
        raise KeyError(run_id)
    resolved_root = root.resolve()
    directory = (resolved_root / run_id).resolve()
    directory.relative_to(resolved_root)
    if not directory.is_dir():
        raise KeyError(run_id)
    return directory


def _require_import_run(reader: GalleryReader, run_id: str) -> tuple[Path, dict[str, Any]]:
    directory = _safe_run_dir(reader.output_root, run_id)
    summary = reader.get_run(run_id)
    # 导入批次分期望／实际两种用途，都能整批删除；普通批跑运行不在此列。
    if summary.get("sourceType") != SOURCE_TYPE:
        raise ValueError("只有导入批次（期望输出或实际输出）可以删除")
    return directory, summary


def _ensure_idle(reader: GalleryReader, run_id: str) -> None:
    active = getattr(reader, "runs", None)
    state = active.get(run_id) if isinstance(active, dict) else None
    if state is None:
        return
    status = getattr(state, "status", "")
    if status in {"queued", "running"}:
        raise ValueError("批次仍在运行，不能删除")


def delete_sample(
    reader: GalleryReader,
    run_id: str,
    sample_id: str,
) -> dict[str, Any]:
    """删除一个期望样本；最后一个样本被删掉时整批移除。"""
    if not _ID_PATTERN.fullmatch(sample_id):
        raise KeyError(sample_id)
    directory, summary = _require_import_run(reader, run_id)
    _ensure_idle(reader, run_id)
    sample_dir = (directory / sample_id).resolve()
    sample_dir.relative_to(directory)
    if not sample_dir.is_dir():
        raise KeyError(sample_id)
    remaining = [
        item for item in _sample_list(summary) if str(item.get("id")) != sample_id
    ]
    shutil.rmtree(sample_dir)
    if not remaining:
        shutil.rmtree(directory)
        return {"deleted": "run", "runId": run_id, "sampleId": sample_id}
    summary["samples"] = remaining
    for name in ("total", "completed", "imported"):
        summary[name] = len(remaining)
    summary["sizeWarnings"] = [
        note for note in summary.get("sizeWarnings") or []
        if str(note).split("：", 1)[0] != sample_id
    ]
    atomic_write_json(directory / "summary.json", summary)
    return {"deleted": "sample", "runId": run_id, "sampleId": sample_id}


def delete_run(reader: GalleryReader, run_id: str) -> dict[str, Any]:
    """删除整个导入批次目录。"""
    directory, _ = _require_import_run(reader, run_id)
    _ensure_idle(reader, run_id)
    shutil.rmtree(directory)
    active = getattr(reader, "runs", None)
    if isinstance(active, dict):
        active.pop(run_id, None)
    return {"deleted": "run", "runId": run_id}


__all__ = ["delete_run", "delete_sample", "gallery"]
