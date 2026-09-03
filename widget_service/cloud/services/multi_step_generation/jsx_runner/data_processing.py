#!/usr/bin/env python3
"""Convert widget task specs into a generic generation-task format.

The converter intentionally avoids business-specific event and field mappings:

* ``eventCandidates`` becomes ``actions`` while preserving each complete event;
* ``dataModelSchema.data`` becomes a flat ``data`` array whose items contain
  a unique path-derived ``id``, a stable source ``path``, the original
  ``description``, declared or inferred ``type``, and the sample value as
  ``value``;
* ``assetCandidates`` keeps the ordered ``id``/``src``/``description`` records
  that the model may reference;
* the top-level semantic ``size`` field is preserved unchanged for layout routing;
* every data field named ``updatedAt`` is omitted;
* a source ``id`` is preserved when present and is not invented when absent.

The input is read completely before the output is written, so using the same
path for ``--input`` and ``--output`` is supported.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from jsx_runner.card_sizes import CARD_SIZE_DIMENSIONS  # noqa: E402


DEFAULT_INPUT = SKILL_DIR / "data" / "20_tasks_2x2_raw.json"
DEFAULT_OUTPUT = SKILL_DIR / "data" / "20_tasks_2x2_processed.json"
DEFAULT_CONTEXT_OUTPUT = SKILL_DIR / "data" / "20_tasks_2x2_compile_context.json"
RAW_TASK_MARKERS = frozenset({"eventCandidates", "dataModelSchema"})


@dataclass(frozen=True, slots=True)
class PreparedTask:
    prompt_task: dict[str, Any]
    compile_context: dict[str, Any]
    source_index: int | None = None


def _json_pointer(path: tuple[str | int, ...]) -> str:
    """Return an absolute JSON Pointer rooted at the generated ``data`` field."""

    def escape(segment: str | int) -> str:
        return str(segment).replace("~", "~0").replace("/", "~1")

    suffix = "/".join(escape(segment) for segment in path)
    return "/data" + (f"/{suffix}" if suffix else "")


def _binding_id(path: tuple[str | int, ...]) -> str:
    """Return a readable, deterministic ID that is unique for a source path."""
    normalized: list[str] = []
    for index, segment in enumerate(path):
        value = re.sub(r"[^\w-]+", "_", str(segment), flags=re.UNICODE).strip("_")
        normalized.append(value or f"segment{index}")
    candidate = ".".join(normalized) or "data"
    return candidate


def _deduplicate_binding_ids(records: list[dict[str, Any]]) -> None:
    """Keep IDs deterministic even if path-segment normalization collides."""
    used: dict[str, str] = {}
    used_paths: set[str] = set()
    for record in records:
        binding_id = str(record["id"])
        path = str(record["path"])
        if path in used_paths:
            raise ValueError(f"数据绑定 path 重复：{path!r}")
        used_paths.add(path)
        if binding_id in used:
            digest = hashlib.sha256(path.encode("utf-8")).hexdigest()
            length = 8
            candidate = f"{binding_id}.{digest[:length]}"
            while candidate in used:
                length += 2
                candidate = f"{binding_id}.{digest[:length]}"
            binding_id = candidate
            record["id"] = binding_id
        used[binding_id] = path


def _validate_unique_binding_records(records: list[dict[str, Any]], task_label: Any) -> None:
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for record in records:
        binding_id = str(record["id"])
        path = str(record["path"])
        if binding_id in seen_ids:
            raise ValueError(f"任务 {task_label!r} 存在重复数据 id：{binding_id!r}。")
        if path in seen_paths:
            raise ValueError(f"任务 {task_label!r} 存在重复数据 path：{path!r}。")
        seen_ids.add(binding_id)
        seen_paths.add(path)


def _validate_task_size(value: Any, task_label: Any) -> str:
    if value not in CARD_SIZE_DIMENSIONS:
        allowed = ", ".join(repr(item) for item in CARD_SIZE_DIMENSIONS)
        raise ValueError(f"任务 {task_label!r} 的 size 必须是 {allowed} 之一，收到 {value!r}。")
    return str(value)


_SUPPORTED_DATA_TYPES = frozenset({"string", "integer", "number", "boolean", "string[]"})
_SCHEMA_LEAF_KEYS = frozenset({"type", "description", "sampleValue"})


def _data_type(value: Any, declared: Any = None) -> str:
    if declared is not None:
        if not isinstance(declared, str) or not declared.strip():
            raise ValueError(f"数据字段 type 必须是非空字符串，收到 {declared!r}。")
        normalized = declared.strip().lower()
        if normalized not in _SUPPORTED_DATA_TYPES:
            allowed = ", ".join(sorted(_SUPPORTED_DATA_TYPES))
            raise ValueError(f"数据字段 type 必须是以下类型之一：{allowed}；收到 {declared!r}。")
        if normalized == "string" and not isinstance(value, str):
            compatible = False
        elif normalized == "integer":
            compatible = isinstance(value, int) and not isinstance(value, bool)
        elif normalized == "number":
            compatible = isinstance(value, (int, float)) and not isinstance(value, bool)
        elif normalized == "boolean":
            compatible = isinstance(value, bool)
        elif normalized == "string[]":
            compatible = isinstance(value, list) and all(isinstance(item, str) for item in value)
        else:
            compatible = True
        if not compatible:
            raise ValueError(f"数据字段声明为 {normalized!r}，但 sample/value 的实际类型是 {_data_type(value)!r}。")
        return normalized
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, list):
        return "string[]" if all(isinstance(item, str) for item in value) else "array"
    if value is None:
        return "null"
    return "object" if isinstance(value, dict) else type(value).__name__


def _is_schema_leaf_candidate(value: dict[str, Any]) -> bool:
    """Recognize metadata without confusing business fields named type/description."""
    keys = set(value)
    return (
        ("type" in keys and not isinstance(value.get("type"), (dict, list)))
        or ("sampleValue" in keys and not isinstance(value.get("sampleValue"), dict))
        or (keys and keys.issubset(_SCHEMA_LEAF_KEYS) and isinstance(value.get("description"), str))
    )


def convert_data(value: Any, path: tuple[str | int, ...] = ()) -> list[dict[str, Any]]:
    """Flatten schema leaves while retaining their hierarchy in source paths.

    A schema leaf such as::

        {"type": "number", "description": "当前湿度", "sampleValue": 68}

    becomes::

        {
          "id": "weather.current.humidityPercent",
          "path": "/data/weather/current/humidityPercent",
          "description": "当前湿度",
          "type": "number",
          "value": 68
        }

    Container field names are omitted from the result object because ``path``
    records the complete hierarchy. Lists retain their indices in that path.
    """
    if isinstance(value, list):
        converted: list[dict[str, Any]] = []
        for index, item in enumerate(value):
            converted.extend(convert_data(item, path + (index,)))
        return converted

    if not isinstance(value, dict):
        return [
            {
                "id": _binding_id(path),
                "path": _json_pointer(path),
                "description": "",
                "type": _data_type(value),
                "value": copy.deepcopy(value),
            }
        ]

    if _is_schema_leaf_candidate(value):
        missing = _SCHEMA_LEAF_KEYS - set(value)
        if missing:
            raise ValueError(f"数据字段 {_json_pointer(path)} 缺少 schema 元数据：" + ", ".join(sorted(missing)) + "。")
        description = value["description"]
        if not isinstance(description, str) or not description.strip():
            raise ValueError(f"数据字段 {_json_pointer(path)} 的 description 必须是非空字符串。")
        sample = value["sampleValue"]
        return [
            {
                "id": _binding_id(path),
                "path": _json_pointer(path),
                "description": description.strip(),
                "type": _data_type(sample, value.get("type")),
                "value": copy.deepcopy(sample),
            }
        ]

    converted = []
    for key, child in value.items():
        if key == "updatedAt":
            continue
        converted.extend(convert_data(child, path + (key,)))
    return converted


def convert_actions(value: Any, task_label: Any) -> list[dict[str, Any]]:
    """Preserve complete event definitions without relying on an ID whitelist."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"任务 {task_label!r} 的 eventCandidates 必须是数组。")

    actions: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, event in enumerate(value):
        if not isinstance(event, dict):
            raise ValueError(f"任务 {task_label!r} 的第 {index + 1} 个事件必须是对象。")
        action_id = event.get("id")
        if not isinstance(action_id, str) or not action_id.strip():
            raise ValueError(f"任务 {task_label!r} 的第 {index + 1} 个事件缺少非空字符串 id。")
        if action_id != action_id.strip():
            raise ValueError(f"任务 {task_label!r} 的事件 id 不得包含首尾空白：{action_id!r}。")
        if action_id in seen_ids:
            raise ValueError(f"任务 {task_label!r} 存在重复事件 id：{action_id!r}。")
        if not isinstance(event.get("call"), str) or not event["call"].strip():
            raise ValueError(f"任务 {task_label!r} 的事件 {action_id!r} 缺少非空字符串 call。")
        if not isinstance(event.get("args"), dict):
            raise ValueError(f"任务 {task_label!r} 的事件 {action_id!r} 的 args 必须是对象。")
        description = event.get("description")
        if description is not None and (not isinstance(description, str) or not description.strip()):
            raise ValueError(f"任务 {task_label!r} 的事件 {action_id!r} 的 description 必须是非空字符串。")
        seen_ids.add(action_id)
        actions.append(copy.deepcopy(event))
    return actions


def convert_asset_candidates(value: Any, task_label: Any) -> list[dict[str, str]]:
    """Validate and retain the model-facing asset candidates for one task."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"任务 {task_label!r} 的 assetCandidates 必须是数组。")

    candidates: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    seen_sources: set[str] = set()
    for index, asset in enumerate(value):
        if not isinstance(asset, dict):
            raise ValueError(f"任务 {task_label!r} 的第 {index + 1} 个资源必须是对象。")
        asset_id = asset.get("id")
        if not isinstance(asset_id, str) or not asset_id.strip():
            raise ValueError(f"任务 {task_label!r} 的第 {index + 1} 个资源缺少非空字符串 id。")
        if asset_id != asset_id.strip():
            raise ValueError(f"任务 {task_label!r} 的资源 id 不得包含首尾空白：{asset_id!r}。")
        source = asset.get("src")
        if not isinstance(source, str) or not source.strip():
            raise ValueError(f"任务 {task_label!r} 的资源 {asset_id!r} 缺少非空字符串 src。")
        if source != source.strip():
            raise ValueError(f"任务 {task_label!r} 的资源 {asset_id!r}.src 不得包含首尾空白。")
        description = asset.get("description")
        if not isinstance(description, str) or not description.strip():
            raise ValueError(f"任务 {task_label!r} 的资源 {asset_id!r} 缺少非空字符串 description。")
        if asset_id in seen_ids:
            raise ValueError(f"任务 {task_label!r} 存在重复资源 id：{asset_id!r}。")
        normalized_source = source.replace("\\", "/")
        if normalized_source in seen_sources:
            raise ValueError(f"任务 {task_label!r} 存在重复资源 src：{source!r}。")
        seen_ids.add(asset_id)
        seen_sources.add(normalized_source)
        candidates.append(
            {
                "id": asset_id,
                "src": source,
                "description": description.strip(),
            }
        )
    return candidates


def convert_task(task: dict[str, Any], fallback_index: int | None = None) -> dict[str, Any]:
    """Convert one source task and emit stable fields in generation order."""
    task_label = task.get("id", fallback_index)
    schema = task.get("dataModelSchema")
    if not isinstance(schema, dict) or not isinstance(schema.get("data"), dict):
        raise ValueError(f"任务 {task_label!r} 缺少 dataModelSchema.data 对象。")

    task_size = _validate_task_size(task.get("size"), task_label)
    converted_data = convert_data(schema["data"])
    _deduplicate_binding_ids(converted_data)
    result: dict[str, Any] = {}
    if "id" in task:
        result["id"] = copy.deepcopy(task["id"])
    result.update(
        {
            "userQuery": copy.deepcopy(task.get("userQuery")),
            "size": task_size,
            "actions": convert_actions(task.get("eventCandidates"), task_label),
            "data": converted_data,
            "assetCandidates": convert_asset_candidates(task.get("assetCandidates"), task_label),
        }
    )
    return result


def is_raw_task(task: dict[str, Any]) -> bool:
    """Return whether a task still uses the upstream raw-data schema."""
    return bool(RAW_TASK_MARKERS.intersection(task))


def prepare_task_for_prompt(task: dict[str, Any], fallback_index: int | None = None) -> dict[str, Any]:
    """Return only the compact model-facing view of one task."""
    return prepare_task(task, fallback_index).prompt_task


def prepare_task(task: dict[str, Any], fallback_index: int | None = None) -> PreparedTask:
    """Split one input into a compact prompt and a private compile context."""
    processed = convert_task(task, fallback_index) if is_raw_task(task) else copy.deepcopy(task)

    task_label = processed.get("id", fallback_index)
    task_size = _validate_task_size(processed.get("size"), task_label)
    processed["size"] = task_size
    raw_data = processed.get("data", [])
    if not isinstance(raw_data, list):
        raise ValueError(f"任务 {task_label!r} 的 data 必须是数组。")
    compile_data: list[dict[str, Any]] = []
    for index, item in enumerate(raw_data):
        if not isinstance(item, dict):
            raise ValueError(f"任务 {task_label!r} 的 data[{index}] 必须是对象。")
        if not isinstance(item.get("id"), str) or not item["id"].strip():
            raise ValueError(f"任务 {task_label!r} 的 data[{index}] 缺少非空字符串 id。")
        if item["id"] != item["id"].strip():
            raise ValueError(f"任务 {task_label!r} 的 data[{index}].id 不得包含首尾空白。")
        if not isinstance(item.get("path"), str) or not item["path"].startswith("/"):
            raise ValueError(f"任务 {task_label!r} 的 data[{index}] 缺少绝对 path。")
        description = item.get("description")
        if not isinstance(description, str) or not description.strip():
            raise ValueError(f"任务 {task_label!r} 的 data[{index}].description 必须是非空字符串。")
        if "value" not in item:
            raise ValueError(f"任务 {task_label!r} 的 data[{index}] 缺少 value。")
        normalized_item = copy.deepcopy(item)
        normalized_item["description"] = description.strip()
        normalized_item["type"] = _data_type(item["value"], item.get("type"))
        compile_data.append(normalized_item)
    _validate_unique_binding_records(compile_data, task_label)
    prompt_data = [
        {
            "id": item["id"],
            "type": item["type"],
            "description": item.get("description", ""),
            "value": copy.deepcopy(item["value"]),
        }
        for item in compile_data
    ]

    compile_actions = convert_actions(processed.get("actions", []), processed.get("id", fallback_index))
    prompt_actions = []
    for item in compile_actions:
        prompt_action = {"id": item["id"]}
        if item.get("description"):
            prompt_action["description"] = item["description"]
        prompt_actions.append(prompt_action)

    if "icons" in processed and "assetCandidates" not in processed:
        raise ValueError(f"任务 {task_label!r} 使用了旧版 icons 字段；请从 raw 数据重新生成 processed 数据。")
    prompt_assets = convert_asset_candidates(
        processed.get("assetCandidates", []),
        task_label,
    )

    prompt_task = copy.deepcopy(processed)
    prompt_task["data"] = prompt_data
    prompt_task["actions"] = prompt_actions
    prompt_task["assetCandidates"] = prompt_assets
    compile_context = {"data": compile_data, "actions": compile_actions}
    return PreparedTask(
        prompt_task=prompt_task,
        compile_context=compile_context,
        source_index=fallback_index,
    )


def prepare_tasks_for_prompt(
    tasks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Prepare a task list in source order for direct model consumption."""
    return [prepare_task_for_prompt(task, index) for index, task in enumerate(tasks, start=1)]


def prepare_tasks(tasks: list[dict[str, Any]]) -> list[PreparedTask]:
    """Prepare prompt and compile views for every task in source order."""
    return [prepare_task(task, index) for index, task in enumerate(tasks, start=1)]


def prepare_tasks_from_views(
    prompt_tasks: list[dict[str, Any]],
    context_records: list[dict[str, Any]],
    *,
    source_indices: list[int] | None = None,
) -> list[PreparedTask]:
    """Rejoin persisted model views with their private contexts safely."""
    if len(prompt_tasks) != len(context_records):
        raise ValueError(f"模型输入与私有上下文条数不一致：{len(prompt_tasks)} != {len(context_records)}。")

    if source_indices is None:
        source_indices = list(range(1, len(prompt_tasks) + 1))
    if len(source_indices) != len(prompt_tasks):
        raise ValueError(f"source_indices 与模型输入条数不一致：{len(source_indices)} != {len(prompt_tasks)}。")
    if any(not isinstance(value, int) or value < 1 for value in source_indices):
        raise ValueError("source_indices 必须全部是从 1 开始的正整数。")
    if len(set(source_indices)) != len(source_indices):
        raise ValueError("source_indices 不得重复。")

    prepared_tasks: list[PreparedTask] = []
    for source_index, prompt_task, context_record in zip(
        source_indices,
        prompt_tasks,
        context_records,
        strict=True,
    ):
        if not isinstance(context_record, dict):
            raise ValueError(f"私有上下文第 {source_index} 项必须是对象。")
        if context_record.get("sourceIndex") != source_index:
            raise ValueError(f"私有上下文第 {source_index} 项的 sourceIndex 不匹配。")
        prompt_id = prompt_task.get("id")
        if context_record.get("id") != prompt_id and ("id" in context_record or prompt_id is not None):
            raise ValueError(f"模型输入与私有上下文第 {source_index} 项的 id 不匹配。")
        merged = copy.deepcopy(prompt_task)
        merged["data"] = copy.deepcopy(context_record.get("data", []))
        merged["actions"] = copy.deepcopy(context_record.get("actions", []))
        prepared = prepare_task(merged, source_index)
        if prepared.prompt_task != prompt_task:
            raise ValueError(f"模型输入与私有上下文第 {source_index} 项内容不一致。")
        prepared_tasks.append(prepared)
    return prepared_tasks


def write_json_safely(output_path: Path, payload: Any) -> None:
    """Atomically replace the output after serialization succeeds."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.", suffix=".tmp", dir=output_path.parent
    )
    os.close(file_descriptor)
    temporary_path = Path(temporary_name)
    try:
        with temporary_path.open("w", encoding="utf-8") as handle:
            handle.write(serialized)
        temporary_path.replace(output_path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def compile_context_record(prepared: PreparedTask, source_index: int) -> dict[str, Any]:
    """Return the private binding/action context paired with one prompt task."""
    record: dict[str, Any] = {"sourceIndex": source_index}
    task_id = prepared.prompt_task.get("id")
    if task_id is not None:
        record["id"] = copy.deepcopy(task_id)
    record.update(copy.deepcopy(prepared.compile_context))
    return record


def convert(
    input_path: Path,
    output_path: Path,
    context_output_path: Path,
) -> tuple[int, Path, Path]:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not all(isinstance(task, dict) for task in payload):
        raise ValueError("输入文件顶层必须是任务对象数组。")

    prepared = prepare_tasks(payload)
    write_json_safely(output_path, [item.prompt_task for item in prepared])
    write_json_safely(
        context_output_path,
        [compile_context_record(item, index) for index, item in enumerate(prepared, start=1)],
    )
    return len(prepared), output_path, context_output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "将原始任务拆分为模型输入和私有还原上下文；"
            "模型输入不包含 path/call/args，私有上下文保留完整绑定和动作参数。"
        )
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--context-output",
        type=Path,
        default=DEFAULT_CONTEXT_OUTPUT,
        help="私有数据绑定和动作还原上下文输出文件。",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    count, output_path, context_output_path = convert(
        args.input.resolve(),
        args.output.resolve(),
        args.context_output.resolve(),
    )
    print(f"已生成 {count} 条模型输入：{output_path}")
    print(f"已生成 {count} 条私有上下文：{context_output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
