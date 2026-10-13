from __future__ import annotations

import argparse
import cgi
import json
import mimetypes
import re
import shutil
import sys
import uuid
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .html_report import render_analysis_html
from .log_parser import parse_log_text
from .query_analyzer import analyze_queries, build_analysis_payload

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
REPORT_CACHE_DIR = Path(__file__).resolve().parent.parent / ".report_cache"
_REPORT_ID_RE = re.compile(r"^[a-f0-9]{12}$")


@dataclass
class StoredReport:
    id: str
    filename: str
    html: str
    data: dict[str, Any] = field(default_factory=dict)


_reports: dict[str, StoredReport] = {}


def _normalize_report_id(report_id: str) -> str:
    return unquote(report_id or "").strip("/")


def _report_dir(report_id: str) -> Path:
    safe_id = _normalize_report_id(report_id)
    if not _REPORT_ID_RE.fullmatch(safe_id):
        raise ValueError(f"invalid report id: {report_id!r}")
    return REPORT_CACHE_DIR / safe_id


def _save_report_to_disk(report: StoredReport) -> None:
    report_dir = _report_dir(report.id)
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "meta.json").write_text(
        json.dumps({"id": report.id, "filename": report.filename}, ensure_ascii=False),
        encoding="utf-8",
    )
    (report_dir / "report.html").write_text(report.html, encoding="utf-8")
    (report_dir / "data.json").write_text(
        json.dumps(report.data, ensure_ascii=False),
        encoding="utf-8",
    )


def _load_report_from_disk(report_id: str) -> StoredReport | None:
    try:
        report_dir = _report_dir(report_id)
    except ValueError:
        return None
    html_path = report_dir / "report.html"
    data_path = report_dir / "data.json"
    meta_path = report_dir / "meta.json"
    if not html_path.is_file():
        return None
    html = html_path.read_text(encoding="utf-8")
    data: dict[str, Any] = {}
    if data_path.is_file():
        data = json.loads(data_path.read_text(encoding="utf-8"))
    filename = "upload.jsonl"
    if meta_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        filename = meta.get("filename") or filename
    return StoredReport(id=_normalize_report_id(report_id), filename=filename, html=html, data=data)


def get_report(report_id: str) -> StoredReport | None:
    safe_id = _normalize_report_id(report_id)
    if not safe_id:
        return None
    cached = _reports.get(safe_id)
    if cached is not None:
        return cached
    loaded = _load_report_from_disk(safe_id)
    if loaded is not None:
        _reports[safe_id] = loaded
    return loaded


def store_report(report: StoredReport) -> None:
    _reports[report.id] = report
    REPORT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _save_report_to_disk(report)


def delete_report(report_id: str) -> bool:
    safe_id = _normalize_report_id(report_id)
    if not safe_id:
        return False
    _reports.pop(safe_id, None)
    try:
        report_dir = _report_dir(safe_id)
    except ValueError:
        return False
    if report_dir.is_dir():
        shutil.rmtree(report_dir, ignore_errors=True)
        return True
    return safe_id in _reports


def analyze_jsonl_text(filename: str, raw_text: str) -> StoredReport:
    log = parse_log_text(raw_text)
    queries = analyze_queries(log)
    payload = build_analysis_payload(log, queries)
    html = render_analysis_html(log, queries)
    report_id = uuid.uuid4().hex[:12]
    report = StoredReport(id=report_id, filename=filename, html=html, data=payload)
    store_report(report)
    return report


def _report_summary(report: StoredReport) -> dict[str, Any]:
    return {
        "id": report.id,
        "filename": report.filename,
        "sessionId": report.data.get("sessionId", ""),
        "queryCount": report.data.get("queryCount", 0),
        "eventCount": report.data.get("eventCount", 0),
        "queries": [
            {
                "index": q["index"],
                "text": q["text"],
                "totalDurationMs": q["totalDurationMs"],
                "stepCount": len(q.get("steps", [])),
            }
            for q in report.data.get("queries", [])
        ],
    }


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _send_html(
    handler: BaseHTTPRequestHandler,
    html: str,
    *,
    inline: bool,
    download_name: str = "report.html",
) -> None:
    body = html.encode("utf-8")
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    disposition = "inline" if inline else f'attachment; filename="{download_name}"'
    handler.send_header("Content-Disposition", disposition)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class AnalyzerHTTPRequestHandler(BaseHTTPRequestHandler):
    server_version = "OpenClawAnalyzerWeb/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), fmt % args))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()
            return

        if path == "/api/reports":
            ids = {p.name for p in REPORT_CACHE_DIR.iterdir() if p.is_dir()} if REPORT_CACHE_DIR.is_dir() else set()
            ids.update(_reports.keys())
            items = []
            for report_id in sorted(ids):
                report = get_report(report_id)
                if report is not None:
                    items.append(_report_summary(report))
            _json_response(self, HTTPStatus.OK, {"reports": items})
            return

        if path.startswith("/api/report/"):
            report_id = path.removeprefix("/api/report/").strip("/")
            report = get_report(report_id)
            if not report:
                _json_response(self, HTTPStatus.NOT_FOUND, {"error": "report not found"})
                return
            _json_response(
                self,
                HTTPStatus.OK,
                {
                    "summary": _report_summary(report),
                    "html": report.html,
                    "data": report.data,
                },
            )
            return

        if path.startswith("/api/view/"):
            report_id = path.removeprefix("/api/view/").strip("/")
            report = get_report(report_id)
            if not report:
                self.log_message("GET /api/view/%s -> 404 (not found)", report_id)
                self.send_error(HTTPStatus.NOT_FOUND, "report not found")
                return
            self.log_message("GET /api/view/%s -> 200 (%d bytes)", report.id, len(report.html))
            _send_html(self, report.html, inline=True)
            return

        if path.startswith("/api/download/"):
            report_id = path.removeprefix("/api/download/").strip("/")
            report = get_report(report_id)
            if not report:
                self.send_error(HTTPStatus.NOT_FOUND, "report not found")
                return
            safe_name = report.filename.rsplit(".", 1)[0] + ".html"
            _send_html(self, report.html, inline=False, download_name=safe_name)
            return

        if path in ("", "/"):
            path = "/index.html"

        file_path = (WEB_DIR / path.lstrip("/")).resolve()
        if not str(file_path).startswith(str(WEB_DIR.resolve())):
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        content = file_path.read_bytes()
        mime, _ = mimetypes.guess_type(str(file_path))
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        if file_path.name in ("index.html", "app.js", "styles.css"):
            self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/analyze":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": "expected multipart/form-data"})
            return

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
            },
        )
        file_field = form["file"] if "file" in form else None
        if file_field is None or not getattr(file_field, "file", None):
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": "missing file field"})
            return

        filename = getattr(file_field, "filename", None) or "upload.jsonl"
        raw_bytes = file_field.file.read()
        try:
            raw_text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                raw_text = raw_bytes.decode("utf-8-sig")
            except UnicodeDecodeError:
                raw_text = raw_bytes.decode("utf-8", errors="replace")

        try:
            report = analyze_jsonl_text(filename, raw_text)
        except Exception as exc:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        self.log_message("POST /api/analyze -> id=%s queries=%d", report.id, report.data.get("queryCount", 0))
        _json_response(
            self,
            HTTPStatus.OK,
            {
                "summary": _report_summary(report),
                "data": report.data,
                "html": report.html,
            },
        )

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/report/"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        report_id = parsed.path.removeprefix("/api/report/").strip("/")
        if not delete_report(report_id):
            _json_response(self, HTTPStatus.NOT_FOUND, {"error": "report not found"})
            return
        _json_response(self, HTTPStatus.OK, {"ok": True})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OpenClaw 日志分析 Web 界面（本地）")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址（默认 127.0.0.1）")
    parser.add_argument("--port", type=int, default=8765, help="端口（默认 8765）")
    args = parser.parse_args(argv)

    if not WEB_DIR.is_dir():
        print(f"错误: web 目录不存在: {WEB_DIR}", file=sys.stderr)
        return 1

    REPORT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((args.host, args.port), AnalyzerHTTPRequestHandler)
    url = f"http://{args.host}:{args.port}/"
    print(f"OpenClaw 日志分析 Web 已启动: {url}")
    print(f"报告缓存目录: {REPORT_CACHE_DIR}")
    print("上传 JSONL 生成报告，支持双屏对比与 Query PK。按 Ctrl+C 停止。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
