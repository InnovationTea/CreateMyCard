"""依据已接受 Plan 的信息容量与组件候选选例，不按业务名决定布局。"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from services.compact_plan import compact_plan_data_paths

_PATH = re.compile(r"/data/[^\s'\"${}()+,]+")
_BASE_COMPONENTS = frozenset(
    {"Row", "Column", "Stack", "List", "Text", "Image", "Divider", "Button", "Progress"}
)


@dataclass(frozen=True)
class Example:
    identifier: str
    content: str
    components: frozenset[str]
    facts: int
    actions: int
    objects: int


@dataclass(frozen=True)
class Selection:
    content: str
    identifiers: tuple[str, ...]


@dataclass(frozen=True)
class Requirements:
    facts: int
    actions: int
    objects: int
    hints: Counter[str]


def _paths(value: Any) -> set[str]:
    paths: set[str] = set()
    if isinstance(value, str):
        paths.update(_PATH.findall(value))
    elif isinstance(value, dict):
        for key, item in value.items():
            if key not in {"onClick", "accessibility"}:
                paths.update(_paths(item))
    elif isinstance(value, list):
        for item in value:
            paths.update(_paths(item))
    return paths


def _objects(paths: set[str]) -> int:
    roots: set[str] = set()
    for path in paths:
        parts = path.split("/")
        if len(parts) > 2:
            roots.add(parts[2])
    return len(roots)


@lru_cache(maxsize=8)
def _examples(source: str) -> tuple[str, tuple[Example, ...]]:
    sections = re.split(r"(?m)(?=^## )", source)
    preamble = sections[0]
    examples: list[Example] = []
    for section in sections[1:]:
        identifier = re.search(r"2x[24]-V\d+", section.splitlines()[0])
        dsl = re.search(r"```genui\s*\n(.*?)\n```", section, re.S)
        if identifier is None or dsl is None:
            raise ValueError("Compact few-shot 缺少编号或完整 DSL")
        components: set[str] = set()
        paths: set[str] = set()
        actions: set[str] = set()
        for line in dsl.group(1).splitlines():
            row = json.loads(line)
            if not isinstance(row, list) or len(row) < 3:
                continue
            name, props = row[1], row[2]
            if not isinstance(name, str) or not isinstance(props, dict):
                raise ValueError(f"Invalid Compact example: {identifier.group()}")
            components.add(name)
            paths.update(_paths(props))
            for event in props.get("onClick", []):
                actions.add(json.dumps(event, sort_keys=True))
        examples.append(
            Example(
                identifier.group(), section, frozenset(components),
                len(paths), len(actions), _objects(paths),
            )
        )
    if not examples:
        raise ValueError("Compact few-shot 不能为空")
    return preamble, tuple(examples)


def _requirements(
    task_spec: dict[str, Any], plan: dict[str, Any] | None,
) -> Requirements:
    hints: Counter[str] = Counter()
    if plan is None:
        paths = set(compact_plan_data_paths(task_spec))
        return Requirements(
            len(paths), len(task_spec.get("eventCandidates", [])), _objects(paths), hints,
        )
    paths: set[str] = set()
    actions: set[str] = set()
    static_facts: set[str] = set()
    for fact in plan.get("info_required", []):
        if not isinstance(fact, dict):
            continue
        data_id = fact.get("dataId")
        action_id = fact.get("actionId")
        text = fact.get("text")
        if isinstance(data_id, str):
            paths.add(data_id)
        if isinstance(action_id, str):
            actions.add(action_id)
        if isinstance(text, str):
            static_facts.add(text)
        for priority, hint in enumerate(fact.get("componentHints", [])):
            if isinstance(hint, str) and hint not in _BASE_COMPONENTS:
                hints[hint] += max(1, 3 - priority)
    return Requirements(len(paths) + len(static_facts), len(actions), _objects(paths), hints)


def select_plan_fewshots(
    source: str, task_spec: dict[str, Any], plan: dict[str, Any] | None,
) -> Selection:
    """优先避免动作/容量不足，再匹配软候选；选例不证明最终布局能放下。"""
    preamble, examples = _examples(source)
    required = _requirements(task_spec, plan)

    def capacity(example: Example) -> tuple[int, int, int]:
        return (
            max(0, required.actions - example.actions),
            max(0, required.facts - example.facts),
            max(0, required.objects - example.objects),
        )

    def rank(example: Example) -> tuple:
        matches = sum(required.hints[name] for name in example.components)
        return (
            *capacity(example),
            abs(required.actions - example.actions),
            -matches,
            abs(required.facts - example.facts),
            abs(required.objects - example.objects),
            example.identifier,
        )

    ranked = sorted(examples, key=rank)
    first = ranked[0]
    chosen = [first]
    missing = set(required.hints) - first.components
    # 第二例只补充尚未示范的候选，不仅为了凑足两个例子而加入另一种构图。
    for example in ranked[1:]:
        if capacity(example) > capacity(first) or example.actions != first.actions:
            continue
        if missing.intersection(example.components):
            chosen.append(example)
            break
    return Selection(
        content=preamble + "\n".join(example.content for example in chosen),
        identifiers=tuple(example.identifier for example in chosen),
    )
