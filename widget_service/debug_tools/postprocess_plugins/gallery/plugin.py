"""浏览器渲染画廊后处理插件实现。"""

from __future__ import annotations

import asyncio
import base64
import html
import json
import os
import re
import shutil
import tempfile
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .._io import atomic_write_json

GalleryCapture = Callable[[str, Path], Awaitable[dict[str, Any]]]
_TERMINAL_SAMPLE_STATUSES = {"success", "degraded", "failed", "unsupported", "cancelled"}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


class BatchGalleryManager:
    """为批跑结果生成内嵌浏览器截图的独立 HTML。"""

    def __init__(
        self,
        output_root: Path,
        capture_base_url: str,
        *,
        capture: GalleryCapture | None = None,
    ) -> None:
        self.output_root = output_root.resolve()
        self.capture_base_url = capture_base_url.rstrip("/")
        self.capture = capture or self._capture_with_browser
        self.tasks: dict[str, asyncio.Task[None]] = {}

    def status(self, run_id: str) -> dict[str, Any]:
        try:
            run_dir = self._safe_run_dir(run_id)
        except KeyError:
            return {"status": "not_started"}
        status_path = run_dir / "gallery.json"
        if not status_path.is_file():
            return {"status": "not_started"}
        try:
            value = json.loads(status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"status": "failed", "error": "画廊状态文件损坏"}
        if not isinstance(value, dict):
            return {"status": "failed", "error": "画廊状态文件格式无效"}
        result = dict(value)
        if result.get("status") == "ready":
            result["url"] = self.gallery_url(run_id)
        return result

    def start(self, run_id: str, *, force: bool = False) -> dict[str, Any]:
        run_dir = self._safe_run_dir(run_id)
        existing_task = self.tasks.get(run_id)
        if existing_task is not None and not existing_task.done():
            return self.status(run_id)
        current = self.status(run_id)
        if current.get("status") == "ready" and not force:
            return current
        if not (run_dir / "summary.json").is_file():
            raise ValueError("批跑结果尚未落盘，无法生成画廊")
        metadata = {
            "status": "generating",
            "startedAt": _utc_now(),
            "generatedAt": None,
            "error": "",
        }
        atomic_write_json(run_dir / "gallery.json", metadata)
        task = asyncio.create_task(self._generate(run_id, run_dir))
        self.tasks[run_id] = task
        task.add_done_callback(lambda _task: self.tasks.pop(run_id, None))
        return metadata

    async def close(self) -> None:
        active = [task for task in self.tasks.values() if not task.done()]
        for task in active:
            task.cancel()
        if active:
            await asyncio.gather(*active, return_exceptions=True)

    def gallery_path(self, run_id: str) -> Path:
        run_dir = self._safe_run_dir(run_id)
        if self.status(run_id).get("status") != "ready":
            raise KeyError(run_id)
        path = (run_dir / "gallery.html").resolve()
        if not path.is_relative_to(run_dir) or not path.is_file():
            raise KeyError(run_id)
        return path

    @staticmethod
    def gallery_url(run_id: str) -> str:
        return f"/debug/batch/runs/{quote(run_id, safe='')}/gallery.html"

    def capture_path(self, run_id: str, sample_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", sample_id):
            raise KeyError(sample_id)
        root = (self._safe_run_dir(run_id) / "gallery_captures").resolve()
        path = (root / f"{sample_id}.png").resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise KeyError(sample_id)
        return path

    @staticmethod
    def capture_url(run_id: str, sample_id: str) -> str:
        return (
            f"/debug/batch/runs/{quote(run_id, safe='')}/gallery-captures/"
            f"{quote(sample_id, safe='')}"
        )

    async def _generate(self, run_id: str, run_dir: Path) -> None:
        status_path = run_dir / "gallery.json"
        try:
            summary = self._read_json(run_dir / "summary.json")
            capture_url = (
                f"{self.capture_base_url}/batch/runs/"
                f"{quote(run_id, safe='')}/gallery-capture"
            )
            with tempfile.TemporaryDirectory(prefix="gallery-", dir=run_dir) as temporary:
                temporary_dir = Path(temporary)
                capture_result = await self.capture(capture_url, temporary_dir)
                document = self.build_html(summary, capture_result, temporary_dir)
                capture_items = self._persist_captures(run_dir, capture_result, temporary_dir)
            temporary_html = run_dir / "gallery.html.tmp"
            temporary_html.write_text(document, encoding="utf-8")
            os.replace(temporary_html, run_dir / "gallery.html")
            atomic_write_json(
                status_path,
                {
                    "status": "ready",
                    "startedAt": self.status(run_id).get("startedAt"),
                    "generatedAt": _utc_now(),
                    "error": "",
                    "items": capture_items,
                },
            )
        except asyncio.CancelledError:
            self._write_failure(status_path, "画廊生成因调试服务关闭而中断")
            raise
        except Exception as exc:
            self._write_failure(status_path, f"{type(exc).__name__}: {exc}")

    @staticmethod
    def _write_failure(status_path: Path, message: str) -> None:
        atomic_write_json(
            status_path,
            {"status": "failed", "generatedAt": _utc_now(), "error": message},
        )

    @staticmethod
    def _persist_captures(
        run_dir: Path,
        capture_result: dict[str, Any],
        temporary_dir: Path,
    ) -> list[dict[str, str]]:
        target_root = run_dir / "gallery_captures"
        target_root.mkdir(parents=True, exist_ok=True)
        result: list[dict[str, str]] = []
        for item in list(capture_result.get("items") or []):
            if not isinstance(item, dict):
                continue
            sample_id = str(item.get("id") or "")
            file_name = item.get("file")
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", sample_id):
                continue
            if isinstance(file_name, str) and file_name:
                source = (temporary_dir / file_name).resolve()
                inside_root = source.is_relative_to(temporary_dir.resolve())
                if inside_root and source.is_file():
                    shutil.copy2(source, target_root / f"{sample_id}.png")
                    result.append({"sampleId": sample_id, "status": "success"})
                    continue
            result.append(
                {
                    "sampleId": sample_id,
                    "status": "failed",
                    "error": str(item.get("error") or "Web 渲染截图未生成"),
                }
            )
        return result

    async def _capture_with_browser(self, capture_url: str, output_dir: Path) -> dict[str, Any]:
        node = shutil.which("node")
        if node is None:
            raise RuntimeError("未找到 Node.js，无法生成卡片截图")
        script = Path(__file__).resolve().parents[2] / "scripts" / "capture_batch_gallery.mjs"
        if not script.is_file():
            raise RuntimeError("画廊截图脚本不存在")
        process = await asyncio.create_subprocess_exec(
            node,
            str(script),
            "--url",
            capture_url,
            "--output",
            str(output_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=script.parents[1],
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=900.0)
        except asyncio.CancelledError:
            process.kill()
            await process.communicate()
            raise
        except TimeoutError as exc:
            process.kill()
            await process.communicate()
            raise RuntimeError("画廊截图超时") from exc
        if process.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace").strip()
            if not detail:
                detail = stdout.decode("utf-8", errors="replace").strip()
            raise RuntimeError(detail or "画廊截图进程失败")
        return self._read_json(output_dir / "capture.json")

    @classmethod
    def build_html(
        cls,
        summary: dict[str, Any],
        capture_result: dict[str, Any],
        screenshot_root: Path,
        *,
        gallery_title: str = "浏览器渲染画廊",
        gallery_subtitle: str = "浏览器调试渲染，不替代正式端侧验收",
        image_alt_suffix: str = "浏览器渲染截图",
        missing_title: str = "无浏览器渲染截图",
        missing_message: str = "该样本没有可渲染的 GenUI",
    ) -> str:
        captures_value = capture_result.get("items")
        captures = captures_value if isinstance(captures_value, list) else []
        captures_by_id: dict[str, dict[str, Any]] = {}
        for capture in captures:
            if not isinstance(capture, dict):
                continue
            sample_id = capture.get("id")
            if isinstance(sample_id, str):
                captures_by_id[sample_id] = capture
        samples_value = summary.get("samples")
        samples = samples_value if isinstance(samples_value, list) else []
        cards: list[str] = []
        for sample in samples:
            if not isinstance(sample, dict):
                continue
            sample_id = str(sample.get("id") or "")
            capture = captures_by_id.get(sample_id)
            cards.append(
                cls._sample_card(
                    sample,
                    capture,
                    screenshot_root,
                    image_alt_suffix=image_alt_suffix,
                    missing_title=missing_title,
                    missing_message=missing_message,
                )
            )
        replacements = {
            "{{RUN_ID}}": html.escape(str(summary.get("runId") or "")),
            "{{GALLERY_TITLE}}": html.escape(gallery_title),
            "{{GALLERY_SUBTITLE}}": html.escape(gallery_subtitle),
            "{{GENERATED_AT}}": html.escape(_utc_now()),
            "{{CARDS}}": "\n".join(cards),
            "{{TOTAL}}": str(len(samples)),
            "{{SUCCESS}}": str(int(summary.get("success") or 0)),
            "{{DEGRADED}}": str(int(summary.get("degraded") or 0)),
            "{{FAILED}}": str(int(summary.get("failed") or 0)),
            "{{CANCELLED}}": str(int(summary.get("cancelled") or 0)),
            "{{AVERAGE}}": html.escape(str(summary.get("averageElapsedMs") or 0)),
        }
        template_path = Path(__file__).resolve().parent / "templates" / "gallery.html"
        document = template_path.read_text(encoding="utf-8")
        for placeholder, value in replacements.items():
            document = document.replace(placeholder, value)
        return document

    @classmethod
    def _sample_card(
        cls,
        sample: dict[str, Any],
        capture: dict[str, Any] | None,
        screenshot_root: Path,
        *,
        image_alt_suffix: str,
        missing_title: str,
        missing_message: str,
    ) -> str:
        sample_id = str(sample.get("id") or "")
        title = str(sample.get("title") or sample_id)
        query_text = str(sample.get("query") or "")
        status_value = str(sample.get("status") or "failed")
        status = status_value if status_value in _TERMINAL_SAMPLE_STATUSES else "failed"
        screenshot_html = cls._screenshot_html(
            title,
            sample,
            capture,
            screenshot_root,
            image_alt_suffix=image_alt_suffix,
            missing_title=missing_title,
            missing_message=missing_message,
        )
        status_label = {
            "success": "成功",
            "degraded": "降级",
            "failed": "失败",
            "unsupported": "不支持",
            "cancelled": "已取消",
        }.get(status, status)
        error_html = cls._error_html(sample)
        capture_size = capture.get("size") if capture is not None else None
        size = str(capture_size or sample.get("size") or "2x2")
        safe_size = size if size in {"2x2", "2x4"} else "2x2"
        search_value = html.escape(
            f"{sample_id} {title} {query_text}".lower(),
            quote=True,
        )
        return (
            f'<article class="result-item" data-status="{status}" '
            f'data-size="{safe_size}" data-search="{search_value}">'
            '<div class="item-head"><div>'
            f"<h2>{html.escape(title)}</h2>"
            f'<span class="task-id">{html.escape(sample_id)}</span></div>'
            f'<span class="status-badge {status}">{status_label}</span></div>'
            f'<div class="card-stage">{screenshot_html}</div>'
            '<div class="metrics">'
            f"<span><b>{safe_size}</b><small>尺寸</small></span>"
            f"<span><b>{html.escape(str(sample.get('elapsedMs') or 0))}ms</b>"
            "<small>耗时</small></span>"
            f"<span><b>{html.escape(str(sample.get('attemptCount') or 0))}</b>"
            "<small>尝试</small></span>"
            f"<span><b>{html.escape(str(sample.get('traceRecordCount') or 0))}</b>"
            "<small>Trace</small></span></div>"
            f'<p class="query">{html.escape(query_text)}</p>{error_html}</article>'
        )

    @staticmethod
    def _screenshot_html(
        title: str,
        sample: dict[str, Any],
        capture: dict[str, Any] | None,
        screenshot_root: Path,
        *,
        image_alt_suffix: str,
        missing_title: str,
        missing_message: str,
    ) -> str:
        capture_error = ""
        if capture is not None:
            capture_error = str(capture.get("error") or "")
            file_name = capture.get("file")
            if isinstance(file_name, str) and file_name:
                screenshot_path = (screenshot_root / file_name).resolve()
                inside_root = screenshot_path.is_relative_to(screenshot_root.resolve())
                if inside_root and screenshot_path.is_file():
                    encoded = base64.b64encode(screenshot_path.read_bytes()).decode("ascii")
                    return (
                        f'<img src="data:image/png;base64,{encoded}" '
                        f'alt="{html.escape(title, quote=True)} '
                        f'{html.escape(image_alt_suffix, quote=True)}">'
                    )
        message = capture_error or str(sample.get("error") or "")
        message = message or missing_message
        return (
            f'<div class="render-error"><strong>{html.escape(missing_title)}</strong>'
            f"<span>{html.escape(message)}</span></div>"
        )

    @staticmethod
    def _error_html(sample: dict[str, Any]) -> str:
        error_code = str(sample.get("errorCode") or "")
        error = str(sample.get("error") or "")
        if not error_code and not error:
            return ""
        return (
            '<details class="details"><summary>错误信息</summary>'
            f"<p>{html.escape(error_code)}</p>"
            f"<pre>{html.escape(error)}</pre></details>"
        )

    def _safe_run_dir(self, run_id: str) -> Path:
        allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
        if not run_id or any(character not in allowed for character in run_id):
            raise KeyError(run_id)
        run_dir = (self.output_root / run_id).resolve()
        if not run_dir.is_relative_to(self.output_root) or not run_dir.is_dir():
            raise KeyError(run_id)
        return run_dir

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"无法读取画廊输入: {path.name}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"画廊输入不是对象: {path.name}")
        return value


async def run_builtin(
    manager: BatchGalleryManager,
    run_id: str,
    _output_dir: Path,
    _config: dict[str, Any],
) -> dict[str, Any]:
    """按统一插件结果协议执行画廊生成。"""

    manager.start(run_id, force=True)
    tasks = getattr(manager, "tasks", {})
    task = tasks.get(run_id) if isinstance(tasks, dict) else None
    if task is not None:
        await task
    status = manager.status(run_id)
    ready = status.get("status") == "ready"
    artifacts: list[dict[str, Any]] = []
    if ready:
        artifacts.append(
            {
                "key": "browser-gallery",
                "label": "打开浏览器渲染画廊",
                "url": status.get("url", ""),
            }
        )
    sample_results: list[dict[str, Any]] = []
    for item in list(status.get("items") or []):
        if not isinstance(item, dict):
            continue
        sample_id = str(item.get("sampleId") or "")
        sample_status = "success" if item.get("status") == "success" else "failed"
        sample_artifacts: list[dict[str, Any]] = []
        if sample_status == "success":
            sample_artifacts.append(
                {
                    "key": "browser-capture",
                    "url": manager.capture_url(run_id, sample_id),
                    "alt": f"{sample_id} Web 渲染截图",
                }
            )
        sample_results.append(
            {
                "sampleId": sample_id,
                "status": sample_status,
                "summary": str(item.get("error") or "Web 渲染截图已生成"),
                "facts": {"captureStatus": sample_status},
                "artifacts": sample_artifacts,
            }
        )
    return {
        "status": "success" if ready else "failed",
        "sampleResults": sample_results,
        "datasetResult": {
            "status": "success" if ready else "failed",
            "summary": (
                "浏览器渲染画廊已生成"
                if ready
                else str(status.get("error") or "画廊生成失败")
            ),
            "facts": {"captured": len(sample_results)},
            "artifacts": artifacts,
        },
    }
