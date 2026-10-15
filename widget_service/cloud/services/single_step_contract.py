# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""只交接事实和字号，不把失败布局交给重新生成的单步模型。"""

import copy
import re

from services.card_validation.compact_validation.semantic.numeric_display import (
    _collect_numeric_component_errors,
)
from services.compact_component_runtime import visual_recipe_part
from services.compact_dsl_a2ui_converter import (
    build_compact_data_model,
    parse_compact_dsl_rows,
)
from services.compact_high_level_components import (
    ComponentRow,
    DataRow,
    expand_high_level_component_rows,
)

_PATH = re.compile(r"\$\{(?P<path>/[^}]+)\}")
_FACT_FIELDS = ("requirement", "priority", "dataId", "text", "actionId")


def clean_fallback_plan(plan: dict | None) -> dict:
    facts = plan.get("info_required") if isinstance(plan, dict) else None
    clean: list[dict] = []
    if isinstance(facts, list):
        for fact in facts:
            if not isinstance(fact, dict):
                continue
            item = {}
            for field in _FACT_FIELDS:
                value = fact.get(field)
                if isinstance(value, str):
                    item[field] = value
            clean.append(item)
    return {"info_required": clean}


def compact_font_requirements(
    source: str, *, size: str, task_spec: dict | None = None,
) -> tuple[list[dict], list[str]]:
    """用现有Recipe只读展开文字；不校验或复用失败源的父子布局。"""
    try:
        rows = parse_compact_dsl_rows(source)
        data_rows = [row for row in rows if isinstance(row, DataRow)]
        data_model = build_compact_data_model(data_rows)
    except (ValueError, TypeError) as error:
        return [], [f"Initial font contract unavailable: {type(error).__name__}"]
    requirements: dict[tuple[str, str], dict] = {}
    skipped: list[str] = []
    for row in rows:
        if not isinstance(row, ComponentRow):
            continue
        semantic_errors: list[str] = []
        _collect_numeric_component_errors([row], task_spec or {}, semantic_errors)
        if semantic_errors:
            skipped.append(f"{row.component_id}: invalid numeric display role")
            continue
        try:
            if row.component_type == "SingleLineTitle":
                _kind, styles = visual_recipe_part("SingleLineTitle", "title", size=size)
                _add_font(requirements, row.props.get("title"), styles.get("fontSize"))
                continue
            expanded = expand_high_level_component_rows([row], size=size, data_model=data_model)
        except (ValueError, TypeError) as error:
            skipped.append(f"{row.component_id}: {type(error).__name__}")
            continue
        for item in expanded:
            field = {"Text": "content", "Button": "label", "Checkbox": "label"}.get(
                item.component_type
            )
            if field is not None:
                _add_font(requirements, item.props.get(field), item.props.get("fontSize"))
    return list(requirements.values()), skipped


def clean_font_requirements(value: object) -> list[dict]:
    """白名单复制语义字号，任何调用者都不能通过额外字段泄漏旧布局。"""
    clean: dict[tuple[str, str], dict] = {}
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            font = item.get("fontSize")
            if not _valid_font(font):
                continue
            for field in ("dataId", "text"):
                content = item.get(field)
                if isinstance(content, str) and content.strip():
                    _retain_font(clean, field, content, font)
    return copy.deepcopy(list(clean.values()))


def _add_font(target: dict, content: object, font: object) -> None:
    if not _valid_font(font):
        return
    if isinstance(content, dict):
        path = content.get("path")
        if set(content) == {"path"} and isinstance(path, str):
            _retain_font(target, "dataId", path, font)
    elif isinstance(content, str) and content.strip():
        paths = list(_PATH.finditer(content))
        if paths:
            for match in paths:
                _retain_font(target, "dataId", match.group("path"), font)
        else:
            _retain_font(target, "text", content, font)


def _retain_font(target: dict, field: str, content: str, font: int | float) -> None:
    key = (field, content)
    previous = target.get(key)
    if previous is None or font > previous.get("fontSize", 0):
        target[key] = {field: content, "fontSize": font}


def _valid_font(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 < value <= 72
