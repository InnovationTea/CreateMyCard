"""批跑后处理插件最小示例。"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def process_sample(context: dict[str, Any]) -> dict[str, Any]:
    sample_dir = Path(str(context.get("sampleDir") or ""))
    config = context.get("config")
    include_hidden = isinstance(config, dict) and config.get("includeHidden") is True
    count = 0
    for path in sample_dir.rglob("*"):
        if not path.is_file():
            continue
        if not include_hidden and any(part.startswith(".") for part in path.parts):
            continue
        count += 1
    return {
        "status": "success",
        "summary": f"发现 {count} 个产物文件",
        "facts": {"fileCount": count},
        "artifacts": [
            {
                "key": "sample-files",
                "data": [{"label": "文件数", "value": count}],
            }
        ],
    }


def process_dataset(context: dict[str, Any]) -> dict[str, Any]:
    sample_results = context.get("sampleResults")
    items = sample_results if isinstance(sample_results, list) else []
    succeeded = sum(
        1
        for item in items
        if isinstance(item, dict) and item.get("status") == "success"
    )
    return {
        "status": "success",
        "summary": f"已处理 {len(items)} 个样本",
        "facts": {"sampleCount": len(items), "succeeded": succeeded},
        "artifacts": [
            {
                "key": "dataset-summary",
                "data": [
                    {"label": "样本数", "value": len(items)},
                    {"label": "成功数", "value": succeeded},
                ],
            }
        ],
    }
