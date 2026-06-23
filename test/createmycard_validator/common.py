"""Shared utilities for A2UI DSL validation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


ALLOWED_COMPONENTS = {
    "Button",
    "Text",
    "TextInput",
    "Row",
    "Column",
    "List",
    "Stack",
    "Grid",
    "Image",
    "Divider",
    "Toggle",
    "Progress",
    "Radio",
    "Checkbox",
    "CheckboxGroup",
    "If",
    "Select",
    "Tabs",
    "TabContent",
    "Navigation",
    "NavContainer",
    "Web",
}

PATH_RE = re.compile(r"^/(?:[^~/]|~[01])*(?:/(?:[^~/]|~[01])*)*$")
EXPR_RE = re.compile(r"^\{\{.*\}\}$", re.DOTALL)
SURFACE_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
MESSAGE_KEYS = {"createSurface", "updateComponents", "updateDataModel", "deleteSurface"}
CANONICAL_MESSAGE_KEYS = {
    "createsurface": "createSurface",
    "updatecomponents": "updateComponents",
    "updatedatamodel": "updateDataModel",
    "deletesurface": "deleteSurface",
}


@dataclass(frozen=True)
class DataBinding:
    component_id: str
    path: str
    scope_path: str | None = None
    repeated: bool = False

    @property
    def is_relative(self) -> bool:
        return not self.path.startswith("/")


@dataclass
class Finding:
    rule_id: str
    severity: str
    message: str
    deduct: int = 0
    module: str = ""
    dimension: str = "未分类"
    count: int = 1
    items: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "rule_id": self.rule_id,
            "module": self.module,
            "dimension": self.dimension,
            "severity": self.severity,
            "message": self.message,
            "deduct": self.deduct,
        }
        if self.count != 1:
            data["count"] = self.count
        if self.items:
            data["items"] = self.items
        return data


@dataclass
class ValidationContext:
    dsl_text: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    line_errors: list[Finding] = field(default_factory=list)
    components: list[dict[str, Any]] = field(default_factory=list)
    data_roots: dict[str, Any] = field(default_factory=dict)
    bindings: list[DataBinding] = field(default_factory=list)

    def iter_components(self, component_type: str | None = None):
        for component in self.components:
            if component_type is None or component.get("component") == component_type:
                yield component

    def get_component(self, component_id: str) -> dict[str, Any] | None:
        return self.component_map.get(component_id)

    @property
    def component_map(self) -> dict[str, dict[str, Any]]:
        return component_id_map(self.components)

    def iter_texts(self):
        return self.iter_components("Text")

    def iter_buttons(self):
        return self.iter_components("Button")

    def has_data_path(self, path: str) -> bool:
        exists, _ = self.get_data_path(path)
        return exists

    def get_data_path(self, path: str) -> tuple[bool, Any]:
        return json_pointer_get(self.data_roots, path)


def error(rule_id: str, message: str, deduct: int) -> Finding:
    return Finding(rule_id=rule_id, severity="ERROR", message=message, deduct=deduct)


def warning(rule_id: str, message: str) -> Finding:
    return Finding(rule_id=rule_id, severity="WARNING", message=message, deduct=0)


def walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def root_field(path: str) -> str | None:
    if not path.startswith("/") or path == "/":
        return None
    return path.split("/", 2)[1].replace("~1", "/").replace("~0", "~")


def json_pointer_get(root: Any, pointer: str) -> tuple[bool, Any]:
    if pointer == "/":
        return True, root
    if not pointer.startswith("/"):
        return False, None
    current = root
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if token not in current:
                return False, None
            current = current[token]
        elif isinstance(current, list):
            if not token.isdigit():
                return False, None
            idx = int(token)
            if idx < 0 or idx >= len(current):
                return False, None
            current = current[idx]
        else:
            return False, None
    return True, current


def component_id_map(components: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        component["id"]: component
        for component in components
        if isinstance(component.get("id"), str) and component.get("id")
    }


def referenced_ids(component: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    children = component.get("children")
    if isinstance(children, list):
        refs.extend(item for item in children if isinstance(item, str))
    elif isinstance(children, dict):
        component_id = children.get("componentId")
        if isinstance(component_id, str):
            refs.append(component_id)
    for field in ("childrenIf", "childrenElse"):
        value = component.get(field)
        if isinstance(value, list):
            refs.extend(item for item in value if isinstance(item, str))
    for field in ("child", "trigger", "content"):
        value = component.get(field)
        if isinstance(value, str) and value and field != "content":
            refs.append(value)
    return refs


def collect_bindings(component: dict[str, Any], repeated_sources: dict[str, str]) -> list[DataBinding]:
    bindings: list[DataBinding] = []
    component_id = str(component.get("id", "<unknown>"))
    source_path = repeated_sources.get(component_id)
    repeated = source_path is not None
    for node in walk(component):
        path = node.get("path")
        if isinstance(path, str):
            bindings.append(DataBinding(component_id, path, source_path, repeated))
    return bindings


def collect_context(dsl_text: str) -> ValidationContext:
    ctx = ValidationContext(dsl_text=dsl_text)
    if "```" in dsl_text:
        ctx.line_errors.append(error("RULE_JSON_002", "DSL contains Markdown code fence", 20))

    for line_no, raw in enumerate(dsl_text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if not line.startswith("{"):
            ctx.line_errors.append(error("RULE_JSON_003", f"line {line_no}: non-JSON explanatory text", 20))
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            ctx.line_errors.append(error("RULE_JSON_001", f"line {line_no}: invalid JSON: {exc.msg}", 20))
            continue
        if not isinstance(obj, dict):
            ctx.line_errors.append(error("RULE_JSON_004", f"line {line_no}: message must be one JSON object", 10))
            continue
        ctx.messages.append(obj)

    for msg in ctx.messages:
        body = msg.get("updateComponents")
        if isinstance(body, dict) and isinstance(body.get("components"), list):
            ctx.components.extend(item for item in body["components"] if isinstance(item, dict))
        data = msg.get("updateDataModel")
        if isinstance(data, dict):
            path = data.get("path", "/")
            value = data.get("value")
            if path == "/" and isinstance(value, dict):
                ctx.data_roots.update(value)
            elif isinstance(path, str) and path.startswith("/"):
                field = root_field(path)
                if field:
                    ctx.data_roots[field] = value

    repeated_sources: dict[str, str] = {}
    for component in ctx.components:
        children = component.get("children")
        if isinstance(children, dict):
            component_id = children.get("componentId")
            source_path = children.get("path")
            if isinstance(component_id, str) and isinstance(source_path, str):
                repeated_sources[component_id] = source_path

    component_map = component_id_map(ctx.components)
    queue = list(repeated_sources)
    while queue:
        parent_id = queue.pop(0)
        parent = component_map.get(parent_id)
        if not parent:
            continue
        for child_id in referenced_ids(parent):
            if child_id not in repeated_sources:
                repeated_sources[child_id] = repeated_sources[parent_id]
                queue.append(child_id)

    for component in ctx.components:
        ctx.bindings.extend(collect_bindings(component, repeated_sources))

    return ctx
