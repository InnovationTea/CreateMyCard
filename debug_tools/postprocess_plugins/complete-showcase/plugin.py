"""覆盖后处理 v2 全部受控展示组件的完整示例。"""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any


def _required_mapping(context: dict[str, Any], key: str) -> dict[str, Any]:
    value = context.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"上下文缺少对象字段: {key}")
    return value


def _required_path(context: dict[str, Any], key: str) -> Path:
    value = context.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"上下文缺少路径字段: {key}")
    return Path(value)


def _sample_identity(sample: dict[str, Any]) -> tuple[str, str]:
    sample_id = sample.get("id")
    if not isinstance(sample_id, str) or not sample_id:
        raise ValueError("样本缺少 id")
    title_value = sample.get("title")
    title = title_value if isinstance(title_value, str) and title_value else sample_id
    return sample_id, title


def _write_sample_assets(
    output_dir: Path,
    sample_id: str,
    title: str,
    score: float,
    category: str,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "example.py").write_text(
        f'def describe() -> str:\n    return "后处理样本 {sample_id}"\n',
        encoding="utf-8",
    )
    (output_dir / "change.diff").write_text(
        "- status: pending\n+ status: completed\n",
        encoding="utf-8",
    )
    (output_dir / "report.txt").write_text(
        f"这是样本 {sample_id} 的可下载示例报告。\n",
        encoding="utf-8",
    )
    (output_dir / "link-target.txt").write_text(
        "该文件用于演示受控链接组件。\n",
        encoding="utf-8",
    )
    safe_title = escape(title)
    safe_category = escape(category)
    bar_width = max(0.0, min(score, 100.0)) * 4.8
    chart = f"""<svg xmlns="http://www.w3.org/2000/svg"
  width="640" height="240" viewBox="0 0 640 240">
  <rect width="640" height="240" rx="24" fill="#F4F7FB"/>
  <text x="40" y="54" fill="#17243A" font-family="sans-serif"
    font-size="24" font-weight="700">样本得分概览</text>
  <text x="40" y="86" fill="#607089" font-family="sans-serif"
    font-size="15">{safe_title} · {safe_category}</text>
  <rect x="40" y="122" width="480" height="24" rx="12" fill="#DCE5F0"/>
  <rect x="40" y="122" width="{bar_width:.1f}" height="24" rx="12" fill="#0A59F7"/>
  <text x="552" y="145" fill="#0A59F7" font-family="sans-serif"
    font-size="30" font-weight="700">{score:.1f}</text>
  <text x="40" y="190" fill="#607089" font-family="sans-serif" font-size="14">
    蓝色进度条按 0–100 分展示，可用于验证图片产物渲染。
  </text>
</svg>
"""
    (output_dir / "score-overview.svg").write_text(chart, encoding="utf-8")


def process_sample(context: dict[str, Any]) -> dict[str, Any]:
    """生成覆盖样本级展示组件的确定性示例结果。"""
    sample = _required_mapping(context, "sample")
    config = _required_mapping(context, "config")
    output_dir = _required_path(context, "outputDir")
    sample_id, title = _sample_identity(sample)
    score_value = config.get("scoreBase", 80)
    score = float(score_value) if isinstance(score_value, (int, float)) else 80.0
    category_value = config.get("category", "演示")
    category = category_value if isinstance(category_value, str) else "演示"
    include_notice = config.get("includeNotice", True) is True
    _write_sample_assets(output_dir, sample_id, title, score, category)

    issues: list[dict[str, Any]] = []
    if include_notice:
        issues.append({"level": "info", "message": "这是用于验证问题列表渲染的示例提示"})

    return {
        "status": "success",
        "summary": f"已为 {sample_id} 生成全部样本级组件",
        "facts": {
            "score": score,
            "passed": score >= 60.0,
            "category": category,
            "labels": ["完整示例", "样本级"],
        },
        "artifacts": [
            {"key": "sample-kpis", "data": [
                {"label": "示例得分", "value": score, "unit": "分"},
                {"label": "文件数量", "value": 5, "unit": "个"},
            ]},
            {"key": "sample-table", "data": [
                {"字段": "样本标识", "值": sample_id},
                {"字段": "样本标题", "值": title},
            ]},
            {"key": "sample-issues", "data": issues},
            {"key": "sample-json", "data": {
                "sample": {"id": sample_id, "title": title},
                "config": {"scoreBase": score, "category": category},
            }},
            {"key": "sample-text", "data": "纯文本内容不会按 HTML 执行。"},
            {"key": "sample-code", "path": "example.py", "language": "python"},
            {"key": "sample-diff", "path": "change.diff"},
            {
                "key": "sample-image",
                "path": "score-overview.svg",
                "alt": f"{title} 得分 {score:.1f}",
            },
            {"key": "sample-file", "path": "report.txt", "label": "下载示例报告"},
            {"key": "sample-link", "path": "link-target.txt", "label": "打开受控链接"},
        ],
    }


def process_dataset(context: dict[str, Any]) -> dict[str, Any]:
    """聚合样本结果并覆盖全部数据集级图表组件。"""
    sample_results_value = context.get("sampleResults")
    sample_results = sample_results_value if isinstance(sample_results_value, list) else []
    total = len(sample_results)
    succeeded = 0
    for result in sample_results:
        if isinstance(result, dict) and result.get("status") == "success":
            succeeded += 1
    failed = total - succeeded
    trend = [
        {"阶段": "输入", "数量": total},
        {"阶段": "完成", "数量": succeeded},
    ]
    matrix = {
        "rows": ["成功", "未成功"],
        "columns": ["样本数", "占比"],
        "cells": [
            [succeeded, round(succeeded * 100 / total, 1) if total else 0.0],
            [failed, round(failed * 100 / total, 1) if total else 0.0],
        ],
    }
    return {
        "status": "success",
        "summary": f"完整组件示例已处理 {total} 个样本",
        "facts": {"sampleCount": total, "succeeded": succeeded},
        "artifacts": [
            {"key": "dataset-kpis", "data": [
                {"label": "样本数", "value": total},
                {"label": "成功数", "value": succeeded},
            ]},
            {"key": "dataset-bars", "data": trend},
            {"key": "dataset-lines", "data": trend},
            {"key": "dataset-pie", "data": [
                {"状态": "成功", "数量": succeeded},
                {"状态": "未成功", "数量": failed},
            ]},
            {"key": "dataset-heatmap", "data": matrix},
            {"key": "dataset-matrix-table", "data": matrix},
            {"key": "dataset-issues-table", "data": [
                {"级别": "info", "说明": "用于演示 issues 的 table 渲染方式"},
            ]},
        ],
    }
