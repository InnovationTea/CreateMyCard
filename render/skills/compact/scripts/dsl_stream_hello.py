from __future__ import annotations

import argparse
import sys
from typing import TextIO

INTERVAL = 10
SUFFIX = "hello world"

_DEFAULT_DEMO_LEN = 25


def write_dsl_with_hello(
    out: TextIO,
    dsl: str,
    *,
    interval: int = INTERVAL,
    suffix: str = SUFFIX,
) -> None:
    """Write *dsl* to *out*; after every *interval* characters, write *suffix*."""
    if interval < 1:
        raise ValueError("interval must be >= 1")
    n = 0
    for ch in dsl:
        out.write(ch)
        n += 1
        if n == interval:
            out.write(suffix)
            n = 0


def _demo_dsl() -> str:
    # Runtime-computed sample DSL (length not a multiple of INTERVAL to show remainder).
    return "x" * _DEFAULT_DEMO_LEN


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Stream DSL text: after every 10 characters, append the literal 'hello world'."
        )
    )
    p.add_argument(
        "file",
        nargs="?",
        default=None,
        help="Path to UTF-8 text, or '-' for stdin. If omitted, run a small built-in demo.",
    )
    p.add_argument(
        "--interval",
        type=int,
        default=INTERVAL,
        metavar="N",
        help=f"insert suffix after this many characters (default: {INTERVAL})",
    )
    p.add_argument(
        "--suffix",
        default=SUFFIX,
        help="string to append (default: hello world)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.file is None:
        text = _demo_dsl()
    elif args.file == "-":
        text = sys.stdin.read()
    else:
        with open(args.file, encoding="utf-8") as f:
            text = f.read()
    write_dsl_with_hello(
        sys.stdout, text, interval=args.interval, suffix=args.suffix
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
