from __future__ import annotations

import argparse
import sys

from .log_parser import parse_log_file
from .query_analyzer import analyze_queries, export_analysis_json, print_analysis_report
from .html_report import export_analysis_html


def _configure_stdout_encoding() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    _configure_stdout_encoding()
    parser = argparse.ArgumentParser(
        description="解析 OpenClaw session 日志 (JSONL)，按用户 query 展示行为链路与各阶段时延。",
    )
    parser.add_argument("log_file", help="OpenClaw JSONL 日志文件路径")
    parser.add_argument("--json", dest="json_output", metavar="FILE", help="导出 JSON 报告")
    parser.add_argument(
        "--html",
        dest="html_output",
        metavar="FILE",
        nargs="?",
        const="report.html",
        help="导出 HTML 可视化报告（默认 report.html）",
    )
    parser.add_argument("--no-console", action="store_true", help="不输出控制台报告")
    args = parser.parse_args(argv)

    try:
        log = parse_log_file(args.log_file)
        queries = analyze_queries(log)
        if not args.no_console:
            print_analysis_report(log, queries)
        if args.json_output:
            export_analysis_json(args.json_output, log, queries)
            print(f"\nJSON 报告已写入: {args.json_output}")
        if args.html_output is not None:
            export_analysis_html(args.html_output, log, queries)
            print(f"HTML 报告已写入: {args.html_output}")
    except (OSError, ValueError, FileNotFoundError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
