#!/usr/bin/env python3
"""Validate datamodel-first HarmonyOS A2UI Form DSL and CardSpec drafts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from validators.asset_validator import AssetValidator
from validators.binding_validator import BindingValidator
from validators.cardspec_validator import CardSpecValidator
from validators.color_validator import ColorValidator
from validators.component_validator import ComponentValidator
from validators.cross_validator import CrossValidator
from validators.diagnostics import Reporter
from validators.expression_validator import ExpressionValidator
from validators.protocol_validator import ProtocolValidator
from validators.quality_validator import QualityValidator
from validators.rule_registry import RuleRegistry
from validators.source_parser import SourceParser, extract_combined, normalize_cardspec_text, normalize_dsl_text


VALIDATORS = [
    ProtocolValidator(),
    ComponentValidator(),
    CardSpecValidator(),
    ExpressionValidator(),
    AssetValidator(),
    BindingValidator(),
    CrossValidator(),
    ColorValidator(),
    QualityValidator(),
]


PIPELINE_BLOCKING_CODES = {
    "DSL_JSON_PARSE_FAILED",
}


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


def selected_stages(stage: str) -> list[str]:
    if stage == "hard":
        return ["hard"]
    if stage == "semantic":
        return ["hard", "semantic"]
    if stage == "quality":
        return ["hard", "semantic", "quality"]
    return ["hard", "semantic", "quality"]


def run_pipeline(context, rules, reporter: Reporter, stage: str, *, stop_on_stage_error: bool = False) -> None:
    stages = selected_stages(stage)
    for current_stage in stages:
        if stop_on_stage_error and current_stage == "semantic" and reporter.has_error("hard"):
            return
        if stop_on_stage_error and current_stage == "quality" and reporter.error_count:
            return
        for validator in VALIDATORS:
            if validator.stage == current_stage:
                validator.validate(context, rules, reporter)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate datamodel-first HarmonyOS A2UI Form DSL and CardSpec.")
    parser.add_argument("path", nargs="?", help="Combined draft file. Reads stdin when omitted or '-'.")
    parser.add_argument("--dsl", help="Path to genui JSONL file or fenced genui block.")
    parser.add_argument("--cardspec", help="Path to cardspec JSON file or fenced cardspec block.")
    parser.add_argument("--stage", choices=["hard", "semantic", "quality", "all"], default="all")
    parser.add_argument("--format", choices=["text", "json", "model"], default="text")
    parser.add_argument("--max-errors", type=int, default=50)
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
    parser.add_argument(
        "--stop-on-stage-error",
        action="store_true",
        help="Stop after hard/semantic errors. Default collects independent later-stage issues to reduce repair rounds.",
    )
    args = parser.parse_args()

    skill_dir = SCRIPT_DIR.parent
    rules = RuleRegistry(skill_dir)
    reporter = Reporter(rules.diagnostics, max_errors=args.max_errors)

    dsl_text, cardspec_text = resolve_inputs(args)
    context = SourceParser().parse(dsl_text, cardspec_text, reporter)
    if not reporter.has_code(*PIPELINE_BLOCKING_CODES):
        run_pipeline(context, rules, reporter, args.stage, stop_on_stage_error=args.stop_on_stage_error)

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
