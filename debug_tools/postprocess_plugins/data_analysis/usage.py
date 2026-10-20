"""从最终产物识别实际组件、素材、动作及数据绑定。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from debug_tools.paths import CLOUD_ROOT


@dataclass(frozen=True)
class UsageRegistry:
    asset_aliases: dict[str, str]
    events: list[dict[str, Any]]
    components: set[str]


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON 根节点必须是对象：{path.name}")
    return value


def _object(value: object) -> dict[str, Any]:
    if isinstance(value, str):
        value = json.loads(value)
    return value if isinstance(value, dict) else {}


def _matches(template: object, actual: object, dynamic: set[str], path: str = "") -> bool:
    if path in dynamic:
        return True
    if isinstance(template, dict):
        if not isinstance(actual, dict):
            return False
        for key, value in template.items():
            if key not in actual:
                return False
            if not _matches(value, actual.get(key), dynamic, f"{path}/{key}"):
                return False
        return True
    return template == actual


def _registries() -> UsageRegistry:
    aliases: dict[str, str] = {}
    events = []
    for directory in sorted((CLOUD_ROOT / "data" / "capabilities").glob("app-*")):
        for name in ("asset_capabilities.json", "event_capabilities.json"):
            path = directory / name
            if not path.is_file():
                continue
            rows = json.loads(path.read_text(encoding="utf-8"))
            for item in rows:
                if not isinstance(item, dict):
                    continue
                identifier = item.get("id")
                if not isinstance(identifier, str):
                    continue
                if name == "asset_capabilities.json":
                    aliases[identifier] = identifier
                    src = item.get("src")
                    if isinstance(src, str):
                        aliases[src] = identifier
                else:
                    events.append(item)
    path = (
        CLOUD_ROOT
        / "data/protocol_profiles/design-compact-dsl-fusion/runtime/visual-recipes-v1.json"
    )
    components = read_object(path).get("components")
    registered = set(components) if isinstance(components, dict) else set()
    return UsageRegistry(aliases, events, registered)


def analyze_usage(final_dir: Path | None) -> dict[str, Any]:
    usage: dict[str, Any] = {"components": None, "assets": None, "events": None, "data": None}
    warnings: list[str] = []
    if final_dir is None:
        return {**usage, "warnings": ["没有最终产物"]}
    try:
        registry = _registries()
        aliases = registry.asset_aliases
        registry_events = registry.events
        registered = registry.components
        blocks = read_object(final_dir / "blocks.json")
    except (OSError, ValueError, TypeError) as exc:
        return {**usage, "warnings": [f"产物或注册表不可读：{type(exc).__name__}: {exc}"]}
    compact = blocks.get("designcompactdsl") or blocks.get("compactdsl")
    rows: list[Any] | None = None
    if isinstance(compact, str):
        try:
            rows = []
            for line in compact.splitlines():
                if line.strip():
                    rows.append(json.loads(line))
        except ValueError as exc:
            rows = None
            warnings.append(f"Compact DSL 解析失败：{exc}")
    elif isinstance(compact, list):
        rows = compact
    if rows is not None:
        components: set[str] = set()
        for row in rows:
            if isinstance(row, list) and len(row) >= 3:
                component = row[1]
                if isinstance(component, str) and component in registered:
                    components.add(component)
        usage["components"] = sorted(components)
    genui_path = final_dir / "genui.jsonl"
    genui = blocks.get("genui")
    try:
        if genui_path.is_file():
            genui = genui_path.read_text(encoding="utf-8")
        documents = []
        if isinstance(genui, str) and genui.strip():
            for line in genui.splitlines():
                if line.strip():
                    documents.append(json.loads(line))
        elif isinstance(genui, dict | list):
            documents.append(genui)
        if not documents:
            raise ValueError("缺少可解析的 A2UI")
        component_rows = []
        has_component_update = False
        messages = []
        for document in documents:
            if isinstance(document, list):
                messages.extend(document)
            else:
                messages.append(document)
        for document in messages:
            if not isinstance(document, dict):
                continue
            update = document.get("updateComponents")
            if not isinstance(update, dict):
                continue
            components = update.get("components")
            if isinstance(components, list):
                has_component_update = True
                component_rows.extend(components)
        if not has_component_update:
            raise ValueError("A2UI 缺少可分析的组件更新")
        assets: set[str] = set()
        actions: list[dict[str, Any]] = []
        for item in component_rows:
            if not isinstance(item, dict):
                continue
            src = item.get("src")
            is_image = item.get("component") == "Image"
            if is_image and isinstance(src, str) and src in aliases:
                identifier = aliases.get(src)
                if identifier is not None:
                    assets.add(identifier)
            on_click = item.get("onClick")
            if isinstance(on_click, list):
                for action in on_click:
                    if isinstance(action, dict):
                        actions.append(action)
        usage["assets"] = sorted(assets)
        task = _object(blocks.get("taskspec") or blocks.get("taskSpec"))
        candidates = task.get("eventCandidates") or []
        events: set[str] = set()
        for action in actions:
            matched = False
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    continue
                identifier = candidate.get("capabilityId") or candidate.get("id")
                expected = candidate.get("action")
                valid_action = isinstance(expected, dict) and isinstance(expected.get("call"), str)
                if isinstance(identifier, str) and valid_action:
                    if _matches(expected, action, set()):
                        events.add(identifier)
                        matched = True
            if matched:
                continue
            for event in registry_events:
                dynamic: set[str] = set()
                for argument in event.get("dynamicArguments") or []:
                    if isinstance(argument, dict) and isinstance(argument.get("path"), str):
                        dynamic.add(f"/args{argument.get('path')}")
                expected = event.get("actionTemplate")
                identifier = event.get("id")
                if isinstance(expected, dict) and isinstance(identifier, str):
                    if _matches(expected, action, dynamic):
                        events.add(identifier)
        usage["events"] = sorted(events)
    except (OSError, ValueError, TypeError) as exc:
        warnings.append(f"渲染产物解析失败：{type(exc).__name__}: {exc}")
    try:
        spec_value = blocks.get("cardspec") or blocks.get("cardSpec")
        if spec_value is None:
            raise ValueError("缺少 CardSpec")
        if isinstance(spec_value, str):
            spec_value = json.loads(spec_value)
        if not isinstance(spec_value, dict):
            raise ValueError("CardSpec 不是对象")
        spec = _object(spec_value)
        bindings = spec.get("dataBindings", [])
        if not isinstance(bindings, list):
            raise ValueError("dataBindings 不是数组")
        data: set[str] = set()
        for binding in bindings:
            if not isinstance(binding, dict):
                raise ValueError("数据绑定不是对象")
            identifier = binding.get("capabilityId")
            if not isinstance(identifier, str):
                raise ValueError("数据绑定缺少标识")
            data.add(identifier)
        usage["data"] = sorted(data)
    except (ValueError, TypeError) as exc:
        warnings.append(f"数据绑定不可分析：{exc}")
    return {**usage, "warnings": warnings}
