"""通过完整 validate_compact_dsl 入口回放样例并核对错误列表。"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sys
from pathlib import Path


def load_validator(cloud: Path):
    sys.path.insert(0, str(cloud))
    return importlib.import_module("services.card_validation.compact_dsl_validator")


def verify(folder: Path, validator) -> str | None:
    expected = json.loads((folder / "expected.json").read_text(encoding="utf-8"))
    for name, checksum in expected.get("sha256", {}).items():
        actual = hashlib.sha256((folder / name).read_bytes()).hexdigest()
        if actual != checksum:
            return f"{name} 内容已变化"
    dsl = (folder / "sample_compact.dsl").read_text(encoding="utf-8")
    task = json.loads((folder / "sample_task_spec.json").read_text(encoding="utf-8"))
    card = json.loads((folder / "sample_card_spec.json").read_text(encoding="utf-8"))
    errors = []
    exception_type = None
    try:
        validator.validate_compact_dsl(dsl, task_spec=task, card_spec=card)
    except validator.CompactDslValidationError as exc:
        errors = list(exc.errors)
        exception_type = type(exc).__name__
    except validator.CompactDslConversionError as exc:
        errors = [str(exc)]
        exception_type = type(exc).__name__
    if errors != expected.get("expectedErrors"):
        return f"错误列表不一致，实际：{errors}"
    if exception_type != expected.get("exceptionType"):
        return f"异常类型不一致，实际：{exception_type}"
    return None


def main() -> int:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cloud", type=Path, default=root.parents[1] / "widget_service/cloud")
    args = parser.parse_args()
    validator = load_validator(args.cloud)
    passed = 0
    failed = 0
    for expected_file in sorted(root.rglob("expected.json")):
        problem = verify(expected_file.parent, validator)
        if problem is None:
            passed += 1
        else:
            failed += 1
            print(f"失败 {expected_file.parent.relative_to(root)}: {problem}")
    print(f"回放完成：{passed} 通过，{failed} 失败")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
