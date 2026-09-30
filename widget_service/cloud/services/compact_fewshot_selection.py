"""保留完整语义参考，为 Plan 软候选补充同尺寸组件局部用法。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from services.compact_component_runtime import load_visual_recipe_contract


@dataclass(frozen=True)
class Example:
    identifier: str
    components: frozenset[str]
    component_rows: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Selection:
    content: str
    identifiers: tuple[str, ...]
    component_names: tuple[str, ...]
    component_identifiers: tuple[str, ...]


@lru_cache(maxsize=8)
def _examples(source: str) -> tuple[Example, ...]:
    sections = re.split(r"(?m)(?=^## )", source)
    examples: list[Example] = []
    registered = load_visual_recipe_contract().get("components", {})
    for section in sections[1:]:
        identifier = re.search(r"2x[24]-V\d+", section.splitlines()[0])
        dsl = re.search(r"```genui\s*\n(.*?)\n```", section, re.S)
        if identifier is None or dsl is None:
            raise ValueError("Compact few-shot 缺少编号或完整 DSL")
        components: set[str] = set()
        component_rows: list[tuple[str, str]] = []
        for line in dsl.group(1).splitlines():
            row = json.loads(line)
            if not isinstance(row, list) or len(row) < 3:
                continue
            name, props = row[1], row[2]
            if not isinstance(name, str) or not isinstance(props, dict):
                raise ValueError(f"Invalid Compact example: {identifier.group()}")
            components.add(name)
            # 只提取已注册、无 children 的高阶组件，不提取根布局或基础子树。
            if name in registered and len(row) == 3:
                component_rows.append((name, line))
        examples.append(Example(identifier.group(), frozenset(components), tuple(component_rows)))
    if not examples:
        raise ValueError("Compact few-shot 不能为空")
    return tuple(examples)


def _component_preferences(plan: dict[str, Any] | None) -> dict[str, int]:
    preferences: dict[str, int] = {}
    if plan is None:
        return preferences
    for fact in plan.get("info_required", []):
        if not isinstance(fact, dict):
            continue
        for priority, name in enumerate(fact.get("componentHints", [])):
            if isinstance(name, str):
                # 多个事实可合入同一组件，重复出现不意味着更多示范或更多实例。
                preferences[name] = max(preferences.get(name, 0), max(1, 3 - priority))
    return preferences


def select_plan_fewshots(
    source: str,
    plan: dict[str, Any] | None,
    *,
    reference_source: str,
) -> Selection:
    """整卡参考保持原样；最多补充两种未示范组件，不据字段计数改选整卡。"""
    references = _examples(reference_source)
    identifiers = tuple(example.identifier for example in references)
    used: set[str] = set()
    for example in references:
        used.update(example.components)
    preferences = _component_preferences(plan)
    names = sorted(preferences, key=lambda name: -preferences.get(name, 0))
    snippets: list[str] = []
    selected_names: list[str] = []
    selected_ids: list[str] = []
    examples = _examples(source)
    for name in names:
        if name in used:
            continue
        for example in examples:
            rows = dict(example.component_rows)
            row = rows.get(name)
            if row is None:
                continue
            snippets.append(
                f"### {name} 局部用法（来源 {example.identifier}，不是整卡模板）\n\n"
                f"```genui\n{row}\n```"
            )
            selected_names.append(name)
            selected_ids.append(example.identifier)
            break
        if len(selected_names) == 2:
            break
    content = reference_source
    if snippets:
        content += (
            "\n\n# Plan 候选组件的局部用法\n\n"
            "以下仅说明单个组件的 Props 与绑定形式，不提供另一套整卡结构。"
            "示例路径、值、颜色、图标及事件不是当前输入，不得照抄；不补造字段或动作。"
            "先核对本轮语义、真实字段类型、组件合法槽位及展开预算，再决定是否采用。"
            "完整参考案例与 Plan 中其余必要事实和动作必须保留；不合适时继续用基础组合。\n\n"
            + "\n\n".join(snippets)
        )
    return Selection(content, identifiers, tuple(selected_names), tuple(selected_ids))
