# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Convert Design Compact DSL to standard A2UI without calling a model.

Examples:
    python convert_compact_dsl_to_a2ui.py card.dsl -o card.a2ui
    type card.dsl | python convert_compact_dsl_to_a2ui.py - --size 4x2
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    ThemeMode,
    convert_compact_dsl_to_a2ui,
)

_DEFAULT_PROTOCOL_PROFILE: dict[str, Any] = {
    "version": "v0.9",
    "catalogId": "ohos.a2ui.extended.catalog.form",
    "sizes": {
        "2x2": {"width": 140, "height": 140},
        "2x4": {"width": 300, "height": 140},
        "4x2": {"width": 300, "height": 140},
    },
}


def convert_text(
    compact_dsl: str,
    *,
    size: str = "2x2",
    theme: ThemeMode = "light",
    surface_id: str = "surface_card",
    protocol_profile: dict[str, Any] | None = None,
) -> str:
    """Convert one Design Compact DSL document without model or network calls."""
    profile = _DEFAULT_PROTOCOL_PROFILE
    if protocol_profile is not None:
        profile = protocol_profile
    return convert_compact_dsl_to_a2ui(
        compact_dsl,
        size=size,
        protocol_profile=profile,
        theme=theme,
        surface_id=surface_id,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Expand PROMPT.md design aliases and convert Compact DSL "
            "to three-message A2UI NDJSON."
        ),
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="-",
        help="Compact DSL input file. Use - or omit it to read stdin.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="-",
        help="A2UI output file. Use - to write stdout.",
    )
    parser.add_argument(
        "--size",
        choices=("2x2", "2x4", "4x2"),
        default="2x2",
    )
    parser.add_argument(
        "--theme",
        choices=("light", "dark"),
        default="light",
        help=(
            "Compatibility option. The current desktop prompt uses one fixed "
            "palette, so both values expand to the same colors."
        ),
    )
    parser.add_argument("--surface-id", default="surface_card")
    parser.add_argument(
        "--protocol-profile",
        help="Optional JSON file overriding version, catalogId, and sizes.",
    )
    return parser


def _read_text(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def _read_profile(path: str | None) -> dict[str, Any] | None:
    if path is None:
        return None
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CompactDslConversionError(
            "Protocol profile JSON must contain an object."
        )
    return value


def _write_text(path: str, value: str) -> None:
    output = value.rstrip("\n") + "\n"
    if path == "-":
        sys.stdout.write(output)
        return
    Path(path).write_text(output, encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the deterministic command-line converter."""
    args = _build_parser().parse_args(argv)
    try:
        converted = convert_text(
            _read_text(args.input),
            size=args.size,
            theme=args.theme,
            surface_id=args.surface_id,
            protocol_profile=_read_profile(args.protocol_profile),
        )
        _write_text(args.output, converted)
    except (CompactDslConversionError, json.JSONDecodeError, OSError) as exc:
        print(f"conversion failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
