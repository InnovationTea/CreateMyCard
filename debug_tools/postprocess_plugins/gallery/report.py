"""画廊只消费截图和分析结果；不调用渲染器或重新分析 Trace。"""

from __future__ import annotations

import base64
import html
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from ..data_analysis.metrics import aggregate


def artifact_data(result: dict[str, Any], key: str) -> dict[str, Any]:
    for artifact in result.get("artifacts") or []:
        if artifact.get("key") == key and isinstance(artifact.get("data"), dict):
            return artifact.get("data")
    return {}


def _asset_path(
    run_dir: Path,
    run_id: str,
    artifact: dict[str, Any],
    plugin_id: str,
) -> Path | None:
    url = str(artifact.get("url") or "")
    parsed = urlsplit(url)
    prefix = f"/debug/batch/runs/{run_id}/postprocess/"
    path = unquote(parsed.path)
    if parsed.scheme or parsed.netloc or not path.startswith(prefix):
        return None
    tail = path.removeprefix(prefix)
    execution_id, separator, asset = tail.partition("/assets/")
    if not separator or not re.fullmatch(r"[A-Za-z0-9._-]+", execution_id):
        return None
    if not asset.startswith(f"{plugin_id}/"):
        return None
    resolved = (run_dir / "postprocess" / execution_id / "plugins" / asset).resolve()
    root = (run_dir / "postprocess" / execution_id / "plugins" / plugin_id).resolve()
    valid = resolved.is_relative_to(root) and resolved.is_file()
    return resolved if valid else None


def _read_products(run_dir: Path, sample_id: str) -> tuple[str, str]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", sample_id):
        return "", ""
    try:
        state = json.loads((run_dir / sample_id / "result.json").read_text(encoding="utf-8"))
        attempt = state.get("finalAttempt")
        if not isinstance(attempt, int) or attempt < 0:
            return "", ""
        directory = run_dir / sample_id / f"attempt_{attempt:03d}"
        blocks = json.loads((directory / "blocks.json").read_text(encoding="utf-8"))
        compact = blocks.get("designcompactdsl") or blocks.get("compactdsl") or ""
        genui = directory / "genui.jsonl"
        a2ui = genui.read_text(encoding="utf-8") if genui.is_file() else blocks.get("genui", "")
        if not isinstance(compact, str):
            compact = json.dumps(compact, ensure_ascii=False, indent=2)
        if not isinstance(a2ui, str):
            a2ui = json.dumps(a2ui, ensure_ascii=False, indent=2)
        return compact, a2ui
    except (OSError, ValueError, AttributeError) as exc:
        return f"产物读取失败：{type(exc).__name__}: {exc}", ""


def build_document(title: str, run_id: str, cases: list[dict[str, Any]]) -> str:
    payload = json.dumps({"runId": run_id, "cases": cases}, ensure_ascii=False, allow_nan=False)
    # JSON script 文本中也必须转义 <，防止用户输入提前结束 script 标签。
    payload = payload.replace("<", "\\u003c").replace("\u2028", "\\u2028")
    template = (Path(__file__).parent / "templates/report.html").read_text(encoding="utf-8")
    replacements = {
        "{{TITLE}}": html.escape(title),
        "{{CREATED}}": html.escape(datetime.now(UTC).isoformat()),
        "{{DATA}}": payload,
    }
    for key, value in replacements.items():
        template = template.replace(key, value)
    return template


async def run_gallery(
    manager: Any,
    kind: str,
    run_id: str,
    output_dir: Path,
    _config: dict[str, Any],
    *,
    upstream_results: list[dict[str, Any]],
) -> dict[str, Any]:
    run_dir = (manager.output_root / run_id).resolve()
    if not run_dir.is_relative_to(manager.output_root.resolve()):
        raise ValueError("运行目录越界")
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    sources: dict[str, dict[str, Any]] = {}
    analyses: dict[str, dict[str, Any]] = {}
    for stage in upstream_results:
        for sample in stage.get("sampleResults") or []:
            sample_id = str(sample.get("sampleId") or "")
            if stage.get("id") == f"{kind}-capture":
                sources[sample_id] = sample
            elif stage.get("id") == "data-analysis":
                analyses[sample_id] = artifact_data(sample, "analysis")
    cases = []
    results = []
    output_dir.mkdir(parents=True, exist_ok=True)
    for sample in summary.get("samples") or []:
        sample_id = str(sample.get("id") or "")
        captured = sources.get(sample_id, {})
        facts = captured.get("facts") or {}
        image = ""
        artifacts = []
        for artifact in captured.get("artifacts") or []:
            if artifact.get("key") != f"{kind}-capture":
                continue
            path = _asset_path(run_dir, run_id, artifact, f"{kind}-capture")
            if path is not None:
                content = path.read_bytes()
                image = "data:image/png;base64," + base64.b64encode(content).decode("ascii")
                # 输出路径不引用其它插件目录；将本次画廊图片保存为自身快照。
                if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", sample_id):
                    raise ValueError("样本标识无效")
                (output_dir / f"{sample_id}.png").write_bytes(content)
                artifacts.append({"key": f"{kind}-capture", "path": f"{sample_id}.png"})
        analysis = analyses.get(sample_id, {})
        compact, a2ui = _read_products(run_dir, sample_id)
        stats = aggregate([analysis]) if analysis else aggregate([])
        cases.append(
            {
                "id": sample_id,
                "title": sample.get("title") or sample_id,
                "query": sample.get("query") or "",
                "size": facts.get("size") or sample.get("size"),
                "status": sample.get("status"),
                "captureStatus": captured.get("status", "skipped"),
                "image": image,
                "error": "" if image else captured.get("summary") or "没有截图记录",
                "warnings": facts.get("warnings") or [],
                "compact": compact,
                "a2ui": a2ui,
                "analysis": analysis,
                "statistics": stats,
            }
        )
        results.append(
            {
                "sampleId": sample_id,
                "status": "success" if image else "skipped",
                "summary": "截图与分析已组装" if image else "无截图，画廊保留原因占位",
                "facts": {"captureStatus": captured.get("status", "skipped")},
                "artifacts": artifacts,
            }
        )
    title = "浏览器渲染画廊" if kind == "browser" else "真机截图画廊"
    document = build_document(title, run_id, cases)
    temporary = output_dir / "gallery.html.tmp"
    temporary.write_text(document, encoding="utf-8")
    temporary.replace(output_dir / "gallery.html")
    return {
        "status": "success",
        "sampleResults": results,
        "datasetResult": {
            "status": "success",
            "summary": f"{title}已生成，共 {len(cases)} 个样本",
            "facts": {"sampleCount": len(cases)},
            "artifacts": [
                {"key": f"{kind}-gallery", "path": "gallery.html", "label": f"打开{title}"}
            ],
        },
    }
