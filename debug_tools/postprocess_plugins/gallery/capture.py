"""浏览器截图前置插件，保留检测证据，不生成画廊。"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote

from .plugin import BatchGalleryManager


async def run_capture(
    manager: BatchGalleryManager,
    run_id: str,
    output_dir: Path,
    _config: dict[str, Any],
) -> dict[str, Any]:
    run_dir = manager._safe_run_dir(run_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    capture_url = f"{manager.capture_base_url}/batch/runs/{quote(run_id, safe='')}/gallery-capture"
    captured = await manager.capture(capture_url, output_dir)
    samples = []
    for item in captured.get("items") or []:
        if not isinstance(item, dict):
            continue
        sample_id = str(item.get("id") or "")
        file_name = item.get("file")
        success = False
        artifacts = []
        if isinstance(file_name, str) and file_name:
            path = (output_dir / file_name).resolve()
            if path.is_relative_to(output_dir.resolve()) and path.is_file():
                success = True
                artifacts.append(
                    {"key": "browser-capture", "path": file_name, "alt": f"{sample_id} 浏览器截图"}
                )
        quality = item.get("quality")
        if isinstance(quality, dict):
            quality = dict(quality)
            if success:
                quality["imageRunPath"] = path.relative_to(run_dir).as_posix()
            artifacts.append({"key": "web-quality-evidence", "data": quality})
        samples.append(
            {
                "sampleId": sample_id,
                "status": "success" if success else "failed",
                "summary": "浏览器截图已生成"
                if success
                else str(item.get("error") or "未生成截图"),
                "facts": {
                    "captureStatus": "success" if success else "failed",
                    "size": item.get("size"),
                    "warnings": list((quality or {}).get("parseWarnings") or []),
                },
                "artifacts": artifacts,
            }
        )
    succeeded = sum(item.get("status") == "success" for item in samples)
    # 即使全部样本无法截图，也让画廊消费失败证据并展示原因占位。
    status = "success" if succeeded == len(samples) else "partial"
    return {
        "status": status,
        "sampleResults": samples,
        "datasetResult": {
            "status": status,
            "summary": f"浏览器截图完成：{succeeded}/{len(samples)}",
            "facts": {"captured": succeeded},
            "artifacts": [
                {
                    "key": "capture-summary",
                    "data": [
                        {"label": "成功", "value": succeeded},
                        {"label": "失败", "value": len(samples) - succeeded},
                    ],
                }
            ],
        },
    }
