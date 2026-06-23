"""DSL extraction and serialization helpers."""

from __future__ import annotations

import json
import re
import sys
from typing import Any


def extract_jsonl_from_text(raw_text: str) -> tuple[str, dict[str, int]]:
    """清洗模型输出，提取纯 JSONL。"""
    text = raw_text.strip()
    stats = {
        "total_lines": 0,
        "valid_lines": 0,
        "invalid_json": 0,
        "missing_version": 0,
        "empty_lines": 0,
    }
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    fence_pattern = re.compile(r"^`{3}(?:jsonl?|JSONL?)?\s*$")
    all_lines = text.split("\n")
    in_fence = False
    content_lines: list[str] = []
    for line in all_lines:
        stripped = line.strip()
        if fence_pattern.match(stripped):
            in_fence = not in_fence
            continue
        if in_fence:
            content_lines.append(line)
    if not content_lines:
        content_lines = all_lines

    stats["total_lines"] = len(content_lines)

    valid_lines: list[str] = []
    skipped_missing_version: list[tuple[int, str]] = []
    skipped_invalid_json: list[tuple[int, str, str, int]] = []
    for i, line in enumerate(content_lines):
        stripped = line.strip()
        if not stripped:
            stats["empty_lines"] += 1
            continue
        if stripped.upper().startswith("KEYWORDS"):
            continue
        try:
            obj = json.loads(stripped)
            if isinstance(obj, dict) and "version" in obj:
                valid_lines.append(stripped)
                stats["valid_lines"] += 1
            else:
                stats["missing_version"] += 1
                skipped_missing_version.append((i + 1, stripped[:80]))
        except json.JSONDecodeError as exc:
            fixed = fix_json(stripped)
            if fixed:
                try:
                    obj = json.loads(fixed)
                    if isinstance(obj, dict) and "version" in obj:
                        valid_lines.append(fixed)
                        stats["valid_lines"] += 1
                        print(f"提示：第 {i + 1} 行 JSON 修复成功", file=sys.stderr)
                        continue
                except json.JSONDecodeError:
                    pass
            stats["invalid_json"] += 1
            skipped_invalid_json.append((i + 1, exc.msg, stripped[:80], exc.pos))

    print_parse_warnings(skipped_missing_version, skipped_invalid_json)
    return "\n".join(valid_lines), stats


def print_parse_warnings(
    missing_version: list[tuple[int, str]],
    invalid_json: list[tuple[int, str, str, int]],
) -> None:
    if missing_version:
        line_no, sample = missing_version[0]
        print(
            f"[WARN] 已过滤 {len(missing_version)} 行缺少 version 字段的 JSON；"
            f"示例：第 {line_no} 行: {sample}...",
            file=sys.stderr,
        )
    if invalid_json:
        line_no, msg, sample, pos = invalid_json[0]
        print(
            f"[WARN] 已过滤 {len(invalid_json)} 行非 JSONL 文本/非法 JSON；"
            f"示例：第 {line_no} 行（{msg}，位置 {pos}）: {sample}...",
            file=sys.stderr,
        )


def fix_json(text: str) -> str | None:
    original = text
    fixed = re.sub(r",\s*([}\]])", r"\1", text)
    fixed = fixed.replace("}{", "},{").replace("][", "],[")
    return fixed if fixed != original else None


def parse_dsl_objects(dsl_text: str) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for line in dsl_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            objects.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return objects
