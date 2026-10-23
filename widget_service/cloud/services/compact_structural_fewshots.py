"""Plan之后按占位、容量与候选检索完整案例；不读取业务关键词或测试标签。"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from services.compact_layout_runtime import load_layout_contract
from services.compact_whole_card_click import WHOLE_CARD_LAYOUTS

WEIGHTS = {"action": 0.30, "density": 0.35, "layout": 0.20, "component": 0.15}
_PATH = re.compile(r"/data/[A-Za-z0-9_~/-]+")


@dataclass(frozen=True)
class Features:
    size: str
    fact_count: int
    buttons: int
    action_mode: str
    mean_length: float | None
    max_length: int | None
    layouts: tuple[str, ...] = ()
    components: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class Example:
    identifier: str
    section: str
    features: Features
    fingerprint: str


@dataclass(frozen=True)
class Match:
    example: Example
    score: float
    dimensions: dict[str, float | None]


@dataclass(frozen=True)
class Selection:
    content: str
    identifiers: tuple[str, ...]
    matches: tuple[Match, ...]


def _paths(value: Any) -> set[str]:
    return set(_PATH.findall(json.dumps(value, ensure_ascii=False)))


def _sample(task: dict[str, Any], pointer: str) -> Any:
    node = task.get("dataModelSchema", {})
    for token in pointer.strip("/").split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(node, list):
            if not token.isdigit() or int(token) >= len(node):
                return None
            node = node[int(token)]
        elif isinstance(node, dict):
            if token in node:
                node = node.get(token)
            else:
                properties = node.get("properties", {})
                node = properties.get(token) if isinstance(properties, dict) else None
        else:
            return None
    return node.get("sampleValue") if isinstance(node, dict) else None


def _pressure(values: list[Any]) -> tuple[float | None, int | None]:
    lengths = []
    for value in values:
        if isinstance(value, (str, int, float, bool)) and value != "":
            lengths.append(len(str(value)))
    if not lengths:
        return None, None
    return sum(lengths) / len(lengths), max(lengths)


def query_features(plan: dict[str, Any], task: dict[str, Any]) -> Features:
    """只计Plan实际接受的事实和动作，候选事件不等于必须生成的按钮。"""
    seen: set[tuple[str, str]] = set()
    values = []
    actions: set[str] = set()
    components = []
    for fact in plan.get("info_required", []):
        action = fact.get("actionId")
        if action:
            actions.add(action)
        else:
            path = fact.get("dataId")
            text = fact.get("text")
            key = ("data", path) if path else ("text", text)
            if key not in seen:
                seen.add(key)
                values.append(_sample(task, path) if path else text)
        hints = fact.get("componentHints", [])
        if hints:
            components.append(tuple(hints))
    whole = plan.get("wholeCardActionId") in actions
    buttons = len(actions) - int(whole)
    layouts = list(plan.get("layoutHints", []))
    composition = plan.get("composition")
    if isinstance(composition, dict):
        layout = composition.get("layout")
        if isinstance(layout, str) and layout not in layouts:
            layouts.insert(0, layout)
    mean_length, max_length = _pressure(values)
    return Features(
        str(task.get("size")), len(seen), buttons,
        "whole-card" if whole else "buttons" if buttons else "none",
        mean_length, max_length, tuple(layouts), tuple(components),
    )


def _shape(identifier: str, nodes: dict[str, list], ancestors: frozenset[str]) -> list:
    if identifier in ancestors or identifier not in nodes:
        raise ValueError("Few-shot存在悬空引用或循环")
    row = nodes.get(identifier)
    assert row is not None
    props = row[2]
    settings = {}
    for key in ("layout", "variant", "orientation"):
        if key in props:
            settings[key] = props.get(key)
    bindings = {}
    for key, value in props.items():
        if key != "onClick" and _paths(value):
            bindings[key] = len(_paths(value))
    settings["bindingsPerProp"] = bindings
    if isinstance(props.get("items"), list):
        settings["items"] = len(props.get("items", []))
    children = []
    for child in row[3] if len(row) == 4 else []:
        children.append(_shape(child, nodes, ancestors | {identifier}))
    return [row[1], settings, children]


def _example(identifier: str, section: str, task: dict, rows: list[list]) -> Example:
    nodes = {}
    visible_paths: set[str] = set()
    buttons = 0
    whole = False
    names: set[str] = set()
    for row in rows:
        if len(row) < 3:
            continue
        nodes[row[0]] = row
        names.add(row[1])
        props = dict(row[2])
        if props.pop("onClick", []):
            if row[0] == "root":
                whole = True
            else:
                buttons += 1
        visible_paths.update(_paths(props))
    root = nodes.get("root")
    if root is None:
        raise ValueError(f"Few-shot {identifier}缺少root")
    layout = root[2].get("layout")
    if not isinstance(layout, str):
        raise ValueError(f"Few-shot {identifier}缺少语义父布局")
    values = []
    for pointer in sorted(visible_paths):
        values.append(_sample(task, pointer))
    mean_length, max_length = _pressure(values)
    features = Features(
        str(task.get("size")), len(visible_paths), buttons,
        "whole-card" if whole else "buttons" if buttons else "none",
        mean_length, max_length, (layout,), (tuple(sorted(names)),),
    )
    fingerprint = hashlib.sha256(
        json.dumps(_shape("root", nodes, frozenset()), sort_keys=True).encode()
    ).hexdigest()
    return Example(identifier, section, features, fingerprint)


@lru_cache(maxsize=8)
def parse_examples(source: str) -> tuple[Example, ...]:
    examples = []
    for section in re.split(r"(?m)(?=^## )", source)[1:]:
        identifier = re.search(r"2x[24]-V\d+", section.splitlines()[0])
        task = re.search(r"```json\s*\n(.*?)\n```", section, re.S)
        dsl = re.search(r"```genui\s*\n(.*?)\n```", section, re.S)
        if identifier is None or task is None or dsl is None:
            raise ValueError("Few-shot缺少编号、输入或完整DSL")
        rows = []
        for line in dsl.group(1).splitlines():
            if line.strip():
                rows.append(json.loads(line))
        examples.append(_example(identifier.group(), section, json.loads(task.group(1)), rows))
    return tuple(examples)


def compatible(query: Features, example: Example) -> bool:
    features = example.features
    if features.size != query.size:
        return False
    layout = features.layouts[0]
    if query.action_mode == "whole-card":
        return query.buttons == 0 and layout in WHOLE_CARD_LAYOUTS
    if features.action_mode == "whole-card":
        return False
    contract = load_layout_contract().get("layouts", {}).get(layout)
    if not isinstance(contract, dict):
        return False
    bounds = contract.get("actionCount", {})
    return bounds.get("min", 0) <= query.buttons <= bounds.get("max", 0)


def _similarity(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return 1 / (1 + abs(left - right) / max(2, max(left, right) * 0.5))


def score(query: Features, example: Example) -> Match:
    other = example.features
    action = 0.8 / (1 + abs(query.buttons - other.buttons))
    action += 0.2 * (query.action_mode == other.action_mode)
    terms = (
        (0.6, _similarity(query.fact_count, other.fact_count)),
        (0.2, _similarity(query.mean_length, other.mean_length)),
        (0.2, _similarity(query.max_length, other.max_length)),
    )
    total, weight_sum = 0.0, 0.0
    for weight, value in terms:
        if value is not None:
            total += weight * value
            weight_sum += weight
    layout = None
    if query.layouts:
        layout = 0.0
        if other.layouts[0] in query.layouts:
            layout = max(0.0, 1 - 0.2 * query.layouts.index(other.layouts[0]))
    component = None
    if query.components:
        matches = []
        for hints in query.components:
            value = 0.0
            for index, name in enumerate(hints[:3]):
                if name in other.components[0]:
                    value = max(value, (1, 0.6, 0.3)[index])
            matches.append(value)
        component = sum(matches) / len(matches)
    dimensions = {"action": action, "density": total / weight_sum,
                  "layout": layout, "component": component}
    total, weight_sum = 0.0, 0.0
    for name, weight in WEIGHTS.items():
        value = dimensions.get(name)
        if value is not None:
            total += weight * value
            weight_sum += weight
    return Match(example, total / weight_sum, dimensions)


def select_structural_fewshots(
    source: str, plan: dict[str, Any], task: dict[str, Any], *, limit: int = 4,
) -> Selection:
    query = query_features(plan, task)
    matches = []
    for example in parse_examples(source):
        if compatible(query, example):
            matches.append(score(query, example))
    matches.sort(key=lambda item: (-item.score, item.example.identifier))
    selected = []
    seen: set[str] = set()
    for match in matches:
        if len(selected) >= limit:
            break
        if match.example.fingerprint not in seen:
            selected.append(match)
            seen.add(match.example.fingerprint)
    sections = [re.split(r"(?m)(?=^## )", source)[0].strip()]
    identifiers = []
    for match in selected:
        sections.append(match.example.section.strip())
        identifiers.append(match.example.identifier)
    content = "\n\n".join(sections) if selected else ""
    return Selection(content, tuple(identifiers), tuple(selected))
