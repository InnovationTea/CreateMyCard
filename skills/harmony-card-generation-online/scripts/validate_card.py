#!/usr/bin/env python3
"""Validate datamodel-first HarmonyOS A2UI Form DSL and CardSpec drafts.

Default runtime posture (both CLI and Python API):

- 只校验传入的 DSL（`--dsl` / stdin / combined 草稿 / artifact）。缺 CardSpec
  时校验器只跑 DSL 相关规则，不追加 CardSpec 必填错误。
- 输出 ``model`` 格式：面向模型的紧凑修复清单，而不是给终端阅读的长报告。
- 无论有多少 error / warning，退出码永远为 0，不阻塞调用方。要恢复"有 error
  就退出 1"的历史行为，加 ``--fail-on-error``。

需要更详细报告或 CI 阻塞时显式覆盖：``--format text|json``、``--strict``、
``--fail-on-error``、``--cardspec`` 等。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from validators.api import ValidationOptions, validate_card
from validators.source_parser import extract_combined, normalize_cardspec_text, normalize_dsl_text


def read_text(path: str | None) -> str:
    if not path or path == "-":
        return sys.stdin.read().lstrip("﻿")
    return Path(path).read_text(encoding="utf-8-sig")


def resolve_inputs(args: argparse.Namespace) -> tuple[str, str]:
    if args.dsl or args.cardspec:
        dsl_text = normalize_dsl_text(read_text(args.dsl)) if args.dsl else ""
        cardspec_text = normalize_cardspec_text(read_text(args.cardspec)) if args.cardspec else ""
        return dsl_text, cardspec_text
    if not args.path:
        return "", ""
    raw = read_text(args.path)
    return extract_combined(raw)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate datamodel-first HarmonyOS A2UI Form DSL and CardSpec.")
    parser.add_argument("path", nargs="?", help="Combined draft file. Reads stdin when omitted or '-'.")
    parser.add_argument("--dsl", help="Path to genui JSONL file or fenced genui block.")
    parser.add_argument("--cardspec", help="Path to cardspec JSON file or fenced cardspec block. Optional; DSL-only by default.")
    parser.add_argument("--artifact", help="Path to a full WidgetArtifact JSON file.")
    parser.add_argument("--effective", help="Path to effectiveCapabilities JSON, or a JSON file containing effectiveCapabilities.")
    parser.add_argument("--capabilities-dir", help="Path to cloud-new capability registry directory, used to resolve effective asset ids.")
    parser.add_argument("--stage", choices=["hard", "semantic", "quality", "all"], default="all")
    parser.add_argument("--format", choices=["text", "json", "model"], default="model", help="Output format. Default: model (compact, model-friendly).")
    parser.add_argument("--max-errors", type=int, default=50)
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors when computing the exit code (only meaningful with --fail-on-error).")
    parser.add_argument(
        "--stop-on-stage-error",
        action="store_true",
        help="Stop after hard/semantic errors. Default collects independent later-stage issues to reduce repair rounds.",
    )
    parser.add_argument(
        "--fail-on-error",
        action="store_true",
        help="Exit with code 1 when errors are found. By default the CLI always exits 0 to stay non-blocking for the caller.",
    )
    args = parser.parse_args()

    dsl_text = ""
    cardspec_text = ""
    if not args.artifact:
        dsl_text, cardspec_text = resolve_inputs(args)
    elif args.dsl or args.cardspec:
        dsl_text, cardspec_text = resolve_inputs(args)

    artifact_text = read_text(args.artifact) if args.artifact else ""
    effective_text = read_text(args.effective) if args.effective else ""
    capabilities_dir = Path(args.capabilities_dir) if args.capabilities_dir else None
    reporter = validate_card(
        dsl_text=dsl_text,
        cardspec=cardspec_text,
        artifact=artifact_text,
        effective_capabilities=effective_text,
        options=ValidationOptions(
            stage=args.stage,
            max_errors=args.max_errors,
            stop_on_stage_error=args.stop_on_stage_error,
            skill_dir=SCRIPT_DIR.parent,
            capabilities_dir=capabilities_dir,
        ),
    )

    if args.format == "json":
        print(reporter.render_json())
    elif args.format == "text":
        print(reporter.render_text())
    else:
        print(reporter.render_model())

    if args.fail_on_error and (reporter.error_count or (args.strict and reporter.warning_count)):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
