"""保留完整语义参考，为 Plan 软候选补充同尺寸组件局部用法。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from services.compact_component_bindings import collect_compact_component_binding_errors
from services.compact_component_runtime import load_visual_recipe_contract


@dataclass(frozen=True)
class Example:
    identifier: str
    components: frozenset[str]
    component_rows: tuple[tuple[str, str], ...]
    layouts: frozenset[str]
    roots: frozenset[str]


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
        layouts = frozenset(re.findall(r"\b[SW]-[a-z][a-z-]+", section))
        roots = frozenset(re.findall(r"/data/([^/}\s\"'+]+)", dsl.group(1)))
        examples.append(
            Example(
                identifier.group(), frozenset(components), tuple(component_rows), layouts, roots,
            )
        )
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


def _rank_examples(examples: tuple[Example, ...], plan: dict[str, Any] | None) -> list[Example]:
    """只为组件局部用法排序，不替换完整语义参考，不用业务名强制组件。"""
    layouts = set((plan or {}).get("layoutHints", []))
    roots: set[str] = set()
    for fact in (plan or {}).get("info_required", []):
        if not isinstance(fact, dict):
            continue
        path = fact.get("dataId")
        if isinstance(path, str) and path.startswith("/data/"):
            roots.add(path.removeprefix("/data/").split("/", maxsplit=1)[0])
    return sorted(
        examples,
        key=lambda example: (
            -len(example.layouts.intersection(layouts)),
            -len(example.roots.intersection(roots)),
        ),
    )


def _catalog_component_row(source: str, name: str, size: str) -> str | None:
    """完整案例未覆盖时，复用当前尺寸创建合同中的可转换单组件示例。"""
    from services.compact_dsl_a2ui_converter import (
        CompactDslConversionError,
        ComponentRow,
        expand_high_level_component_rows,
        validate_single_line_title_layout,
    )

    selected = None
    for block in re.findall(r"```genui\s*\n(.*?)\n```", source, re.S):
        for line in block.splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, list) or len(row) != 3:
                continue
            identifier, component, props = row
            if component != name or not isinstance(props, dict):
                continue
            if collect_compact_component_binding_errors(identifier, component, props):
                continue
            try:
                expanded = expand_high_level_component_rows(
                    [ComponentRow(identifier, component, props)], size=size,
                )
                validate_single_line_title_layout(expanded, size=size)
            except CompactDslConversionError:
                continue
            selected = line
            break
        if selected is not None:
            break
    return selected


def select_plan_fewshots(
    source: str,
    plan: dict[str, Any] | None,
    *,
    reference_source: str,
    component_source: str = "",
) -> Selection:
    """整卡参考保持原样；每种未示范的合法 Plan 候选最多补一条用法。"""
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
    examples = _rank_examples(_examples(source), plan)
    registered = load_visual_recipe_contract().get("components", {})
    size = identifiers[0].split("-", maxsplit=1)[0]
    for name in names:
        if name in used or name not in registered:
            continue
        selected_row = None
        selected_id = "组件合同"
        for example in examples:
            rows = dict(example.component_rows)
            row = rows.get(name)
            if row is None:
                continue
            selected_row, selected_id = row, example.identifier
            break
        if selected_row is None:
            selected_row = _catalog_component_row(component_source, name, size)
        if selected_row is None:
            continue
        snippets.append(
            f"### {name} 局部用法（来源 {selected_id}，不是整卡模板）\n\n"
            f"```genui\n{selected_row}\n```"
        )
        selected_names.append(name)
        selected_ids.append(selected_id)
    content = reference_source
    if snippets:
        content += (
            "\n\n# Plan 候选组件的局部用法\n\n"
            "以下仅说明单个组件的 Props 与绑定形式，不提供另一套整卡结构。"
            "示例路径、值、颜色、图标及事件不是当前输入，不得照抄；不补造字段或动作。"
            "先核对本轮语义、真实字段类型、组件合法槽位及展开预算，再决定是否采用。"
            "Plan 的全部必要事实和动作必须保留，参考案例的手写组件树不必保留。"
            "语义、类型和容量匹配时采用对应组件；只有具体合同条件不成立才回退，"
            "不能因为参考案例用了 Text 或 Row 就忽略本轮组件候选。\n\n"
            + "\n\n".join(snippets)
        )
    return Selection(content, identifiers, tuple(selected_names), tuple(selected_ids))
