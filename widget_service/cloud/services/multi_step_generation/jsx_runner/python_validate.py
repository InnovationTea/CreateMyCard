"""CLI for checking a previously generated JSX file without a browser."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

if "." in (__package__ or ""):
    from ..jsx_to_a2ui.exceptions import ParseError
    from ..jsx_to_a2ui.parser.jsx_parser import extract_card_functions
else:
    from jsx_to_a2ui.exceptions import ParseError
    from jsx_to_a2ui.parser.jsx_parser import extract_card_functions

from .python_validation import validate_python_layout


def _batch_report(directory: Path) -> dict:
    results = []
    files = sorted(directory.rglob("*.jsx"))
    for file in files:
        relative = file.relative_to(directory).as_posix()
        try:
            source = file.read_text(encoding="utf-8-sig")
            names = list(extract_card_functions(source))
        except (OSError, ParseError) as exc:
            results.append({
                "file": relative,
                "componentName": None,
                "ok": False,
                "findings": [{
                    "severity": "error",
                    "code": "python-layout-parse",
                    "message": str(exc),
                }],
            })
            continue
        for name in names:
            report = validate_python_layout(source=source, component_name=name)
            results.append({
                "file": relative,
                "componentName": name,
                "ok": report["ok"],
                "findings": report["findings"],
            })
    passed = sum(item["ok"] for item in results)
    return {
        "ok": passed == len(results),
        "kind": "validation-batch",
        "mode": "python",
        "directory": str(directory),
        "summary": {
            "files": len(files),
            "cards": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "warnings": sum(
                finding["severity"] == "warning"
                for item in results for finding in item["findings"]
            ),
        },
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate an existing generated JSX file with Python only.")
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--jsx", type=Path, help="Path to a generated Card function .jsx file")
    source_group.add_argument("--jsx-dir", type=Path, help="Directory of .jsx files; searches subdirectories")
    parser.add_argument("--component-name", help="Function name, required when the file contains multiple Cards")
    parser.add_argument("--report", type=Path, help="Override the default report path in the JSX directory")
    args = parser.parse_args(argv)
    if args.report is not None and args.report.suffix.lower() == ".jsx":
        parser.error("--report must not overwrite a .jsx file")
    report_path = args.report or (
        (args.jsx_dir.resolve() if args.jsx_dir is not None else args.jsx.resolve().parent)
        / "python-validation-report.json"
    )

    def emit(report: dict) -> int:
        output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        try:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(output, encoding="utf-8")
        except OSError as exc:
            parser.error(f"cannot write report: {exc}")
        print(output, end="")
        return 0 if report["ok"] else 1

    if args.jsx_dir is not None:
        if args.component_name is not None:
            parser.error("--component-name is only valid with --jsx")
        if not args.jsx_dir.is_dir():
            parser.error(f"not a directory: {args.jsx_dir}")
        if not any(args.jsx_dir.rglob("*.jsx")):
            parser.error(f"no .jsx files found in {args.jsx_dir}")
        report = _batch_report(args.jsx_dir)
        return emit(report)
    try:
        source = args.jsx.read_text(encoding="utf-8-sig")
    except OSError as exc:
        parser.error(str(exc))
    component_name = args.component_name
    if component_name is None:
        try:
            names = list(extract_card_functions(source))
        except ParseError as exc:
            parser.error(str(exc))
        if len(names) != 1:
            parser.error("file contains multiple Card functions; pass --component-name")
        component_name = names[0]
    report = validate_python_layout(source=source, component_name=component_name)
    return emit(report)


if __name__ == "__main__":
    raise SystemExit(main())
