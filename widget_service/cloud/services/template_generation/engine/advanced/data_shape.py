"""从当前微服务 TaskSpec 提取高级组件选择所需的数据形状。"""

from __future__ import annotations

import re
from typing import Any

from models.generation import TaskSpec

from .models import DataShape, FieldProfile

_PERCENT_RE = re.compile(r"percent|percentage|ratio|soc|占比|百分比|电量", re.I)
_DURATION_RE = re.compile(r"duration|时长|持续|睡眠.*(?:小时|分钟)", re.I)
_DURATION_PART_RE = re.compile(r"hours?|minutes?|seconds?|小时数|分钟数|秒数", re.I)
_TIME_RE = re.compile(r"(?:^|_)(?:time|start|end)(?:$|_)|时间|日期", re.I)
_START_RE = re.compile(r"dtstart|starttime|start_time|开始", re.I)
_END_RE = re.compile(r"dtend|endtime|end_time|结束", re.I)
_STATUS_RE = re.compile(r"status|state|condition|状态|告警", re.I)
_METRIC_RE = re.compile(
    r"score|count|total|used|usage|memory|capacity|得分|数量|总量|占用|内存|容量",
    re.I,
)


def _field_roles(name: str, description: str, data_type: str) -> list[str]:
    text = f"{name} {description}"
    roles: set[str] = set()
    if _PERCENT_RE.search(text):
        roles.update(("percentage", "metric"))
    if _DURATION_RE.search(text):
        roles.update(("duration", "metric"))
    if _DURATION_PART_RE.search(text):
        roles.update(("duration-part", "metric"))
    if _TIME_RE.search(text):
        roles.add("time")
    if _START_RE.search(text):
        roles.add("time-start")
    if _END_RE.search(text):
        roles.add("time-end")
    if _STATUS_RE.search(text):
        roles.add("status")
    if _METRIC_RE.search(text) or data_type in {"integer", "number"}:
        roles.add("metric")
    return sorted(roles)


def extract_data_shape(task_spec: TaskSpec) -> DataShape:
    """只分析 schema，不读取或生成运行时数据。"""
    fields: list[FieldProfile] = []
    collection_count = 0

    def visit(node: Any, path: str, name: str) -> None:
        nonlocal collection_count
        if isinstance(node, dict) and {"type", "description"}.issubset(node):
            data_type = str(node["type"]).lower()
            description = str(node["description"])
            fields.append(
                FieldProfile(
                    path=path,
                    name=name,
                    data_type=data_type,
                    description=description,
                    roles=_field_roles(name, description, data_type),
                )
            )
            return
        if isinstance(node, dict):
            for key, value in node.items():
                visit(value, f"{path}/{key}" if path else f"/{key}", str(key))
            return
        if isinstance(node, list):
            collection_count += 1
            if node:
                visit(node[0], f"{path}/0", name)

    visit(task_spec.dataModelSchema, "", "data")
    numeric_count = sum(field.data_type in {"integer", "number"} for field in fields)
    metric_count = sum("metric" in field.roles for field in fields)
    parents_with_start: set[str] = set()
    parents_with_end: set[str] = set()
    for field in fields:
        parent = field.path.rsplit("/", 1)[0]
        if "time-start" in field.roles:
            parents_with_start.add(parent)
        if "time-end" in field.roles:
            parents_with_end.add(parent)
    return DataShape(
        numeric_count=numeric_count,
        text_count=sum(field.data_type == "string" for field in fields),
        collection_count=collection_count,
        metric_count=metric_count,
        duration_count=sum("duration" in field.roles for field in fields),
        time_range_count=len(parents_with_start & parents_with_end),
        percentage_count=sum("percentage" in field.roles for field in fields),
        action_count=len(task_spec.eventCandidates),
        repeated_metric_group_count=1 if collection_count and metric_count >= 2 else 0,
        fields=fields,
    )
