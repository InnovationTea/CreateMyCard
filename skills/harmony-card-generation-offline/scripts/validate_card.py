#!/usr/bin/env python3
"""Validate datamodel-first HarmonyOS A2UI Form DSL and CardSpec drafts."""

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
        return sys.stdin.read().lstrip("\ufeff")
    return Path(path).read_text(encoding="utf-8-sig")


def resolve_inputs(args: argparse.Namespace) -> tuple[str, str]:
    if args.dsl or args.cardspec:
        dsl_text = normalize_dsl_text(read_text(args.dsl)) if args.dsl else ""
        cardspec_text = normalize_cardspec_text(read_text(args.cardspec)) if args.cardspec else ""
        return dsl_text, cardspec_text
    raw = read_text(args.path)
    return extract_combined(raw)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate datamodel-first HarmonyOS A2UI Form DSL and CardSpec.")
    parser.add_argument("path", nargs="?", help="Combined draft file. Reads stdin when omitted or '-'.")
    parser.add_argument("--dsl", help="Path to genui JSONL file or fenced genui block.")
    parser.add_argument("--cardspec", help="Path to cardspec JSON file or fenced cardspec block.")
    parser.add_argument("--artifact", help="Path to a full WidgetArtifact JSON file.")
    parser.add_argument("--effective", help="Path to effectiveCapabilities JSON, or a JSON file containing effectiveCapabilities.")
    parser.add_argument("--capabilities-dir", help="Path to cloud-new capability registry directory, used to resolve effective asset ids.")
    parser.add_argument("--stage", choices=["hard", "semantic", "quality", "all"], default="all")
    parser.add_argument("--format", choices=["text", "json", "model"], default="text")
    parser.add_argument("--max-errors", type=int, default=50)
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
    parser.add_argument(
        "--stop-on-stage-error",
        action="store_true",
        help="Stop after hard/semantic errors. Default collects independent later-stage issues to reduce repair rounds.",
    )
    parser.add_argument(
        "--enable-aesthetic",
        action="store_true",
        help="Enable the aesthetic quality validator (still under alignment with offline content).",
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
            enable_aesthetic=args.enable_aesthetic,
        ),
    )

    if args.format == "json":
        print(reporter.render_json())
    elif args.format == "model":
        print(reporter.render_model())
    else:
        print(reporter.render_text())

    if reporter.error_count or (args.strict and reporter.warning_count):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
