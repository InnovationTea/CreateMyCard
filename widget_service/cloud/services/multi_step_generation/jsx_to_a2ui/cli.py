from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .compiler import compile_file
from .exceptions import ConversionError


CONVERTER_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = CONVERTER_ROOT / "converted-cards"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compile declarative card JSX to standard HarmonyOS A2UI messages.")
    sub = parser.add_subparsers(dest="command", required=True)
    convert = sub.add_parser("convert", help="convert a JSX file")
    convert.add_argument("input", type=Path)
    choice = convert.add_mutually_exclusive_group(required=True)
    choice.add_argument("--card", help="Card function name, e.g. Card0813_19")
    choice.add_argument("--all", action="store_true", help="compile every Card* function")
    convert.add_argument("--output", type=Path, help="single output file; with --all this contains an object keyed by card name")
    convert.add_argument(
        "--output-dir",
        type=Path,
        help=f"write one .a2ui.json file per card (default with --all: {DEFAULT_OUTPUT_DIR})",
    )
    convert.add_argument("--format", choices=("json", "jsonl"), default="json")
    convert.add_argument("--compact", action="store_true")
    convert.add_argument(
        "--context",
        type=Path,
        help=(
            "compile-time binding context JSON; with --card use one {data, actions} object, "
            "with --all use an object keyed by card name"
        ),
    )
    return parser


def _serialize(messages, output_format: str, compact: bool) -> str:
    if output_format == "jsonl":
        return "\n".join(json.dumps(message, ensure_ascii=False, separators=(",", ":")) for message in messages) + "\n"
    return json.dumps(messages, ensure_ascii=False, indent=None if compact else 2, separators=(",", ":") if compact else None) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        compile_contexts = None
        if args.context:
            context_payload = json.loads(args.context.read_text(encoding="utf-8"))
            if not isinstance(context_payload, dict):
                raise ConversionError("--context must contain a JSON object")
            if args.card:
                compile_contexts = {args.card: context_payload}
            else:
                if "data" in context_payload or "actions" in context_payload:
                    raise ConversionError("--all requires --context to be keyed by card name")
                compile_contexts = context_payload
        outputs = compile_file(
            args.input,
            card=args.card,
            compile_all=args.all,
            compile_contexts=compile_contexts,
        )
        output_dir = args.output_dir
        if args.all and args.output is None and output_dir is None:
            output_dir = DEFAULT_OUTPUT_DIR
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            for name, messages in outputs.items():
                target = output_dir / f"{name}.a2ui.{args.format}"
                target.write_text(_serialize(messages, args.format, args.compact), encoding="utf-8")
            return 0
        if args.output:
            if len(outputs) == 1:
                content = _serialize(next(iter(outputs.values())), args.format, args.compact)
            elif args.format == "jsonl":
                raise ConversionError("--format jsonl with --all requires --output-dir")
            else:
                content = json.dumps(outputs, ensure_ascii=False, indent=None if args.compact else 2) + "\n"
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(content, encoding="utf-8")
            return 0
        if len(outputs) != 1:
            print(json.dumps(outputs, ensure_ascii=False, indent=2))
        else:
            sys.stdout.write(_serialize(next(iter(outputs.values())), args.format, args.compact))
        return 0
    except (ConversionError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
