"""Input and output helpers for batch generation."""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

from .dsl_parser import parse_dsl_objects

DSL_SEPARATOR = "----- DSL -----"


def read_queries(input_path: Path) -> list[dict[str, str]]:
    if not input_path.exists():
        sys.exit(f"错误：输入文件不存在：{input_path}")

    suffix = input_path.suffix.lower()
    rows: list[dict[str, str]] = []
    if suffix == ".csv":
        with input_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or "query" not in reader.fieldnames:
                sys.exit("错误：CSV 必须包含 query 表头")
            for idx, row in enumerate(reader, 1):
                query = (row.get("query") or "").strip()
                if not query:
                    continue
                item = {k: (v or "") for k, v in row.items()}
                item["id"] = (item.get("id") or f"q{idx}").strip()
                item["query"] = query
                rows.append(item)
    else:
        with input_path.open("r", encoding="utf-8") as f:
            for idx, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as exc:
                    sys.exit(f"错误：输入 JSONL 第 {idx} 行不是合法 JSON：{exc}")
                query = str(obj.get("query", "")).strip()
                if not query:
                    continue
                obj["id"] = str(obj.get("id") or f"q{idx}")
                obj["query"] = query
                rows.append(obj)
    if not rows:
        sys.exit("错误：输入文件中没有有效 query")
    return rows


def safe_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", name).strip("._") or "item"


def result_to_output_record(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": result["id"],
        "category": result.get("input_metadata", {}).get("category", ""),
        "query": result["query"],
        "keywords": result.get("keywords", []),
        "separator": DSL_SEPARATOR,
        "dsl": parse_dsl_objects(result.get("dsl", "")),
        "metadata": {
            "model": result.get("model"),
            "elapsed_ms": result.get("elapsed_ms"),
            "timestamp": result.get("timestamp"),
            "retry_count": result.get("retry_count", 0),
            "error": result.get("error"),
            "validation": result.get("validation", {}),
            "input_metadata": result.get("input_metadata", {}),
        },
    }


def write_results(output_path: Path, results: list[dict[str, Any]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    records = [result_to_output_record(result) for result in results]
    output_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def write_item_json(item_output_dir: Path, result: dict[str, Any]) -> Path | None:
    item_output_dir.mkdir(parents=True, exist_ok=True)
    item_path = item_output_dir / f"{safe_filename(str(result['id']))}.json"
    try:
        item_path.write_text(
            json.dumps(result_to_output_record(result), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return item_path
    except OSError as exc:
        print(f"错误：无法写入单条 JSON 文件 {item_path}：{exc}", file=sys.stderr)
        return None


def write_item_dat(item_output_dir: Path, result: dict[str, Any]) -> Path | None:
    item_output_dir.mkdir(parents=True, exist_ok=True)
    dat_path = item_output_dir / f"{safe_filename(str(result['id']))}.dat"
    try:
        dat_path.write_text(result.get("dsl", "").rstrip() + "\n", encoding="utf-8")
        return dat_path
    except OSError as exc:
        print(f"错误：无法写入裸 DSL 文件 {dat_path}：{exc}", file=sys.stderr)
        return None
