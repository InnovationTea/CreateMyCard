from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .skill_loader import SkillCatalog, SkillLoadError


class ToolValidationError(ValueError):
    """模型工具调用不符合当前运行时注册表。"""


@dataclass(frozen=True)
class RegisteredTool:
    name: str
    bundle_name: str
    plugin_type: str
    description: str
    parameters: dict[str, Any]
    snapshot: dict[str, Any]


def _json_type(value: str) -> str:
    if value.startswith("Array"):
        return "array"
    if value == "String":
        return "string"
    if value == "Boolean":
        return "boolean"
    if value in {"Integer", "Number"}:
        return "number"
    if value == "Object":
        return "object"
    return "object"


def _convert_property(value: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {"type": _json_type(str(value.get("type", "object")))}
    description = value.get("description")
    if isinstance(description, str) and description:
        result["description"] = description
    if result["type"] == "array":
        type_name = str(value.get("type", ""))
        result["items"] = {"type": "string" if "<String>" in type_name else "object"}
        item = (
            value.get("properties", {}).get("ArrayItem")
            if isinstance(value.get("properties"), dict)
            else None
        )
        if isinstance(item, dict):
            result["items"] = _convert_property(item)
    elif result["type"] == "object" and isinstance(value.get("properties"), dict):
        result["properties"] = {
            str(key): _convert_property(item)
            for key, item in value["properties"].items()
            if isinstance(item, dict)
        }
    return result


class ToolRegistry:
    """由 Skill frontmatter 与工具快照构造的 Debug 运行时注册表。"""

    def __init__(self, skill_root: Path, catalog: SkillCatalog, bundle_name: str) -> None:
        self.skill_root = skill_root
        self.catalog = catalog
        self.bundle_name = bundle_name
        self.tools = self._load_tools()

    def _load_tools(self) -> dict[str, RegisteredTool]:
        registered: dict[str, RegisteredTool] = {}
        for item in self.catalog.tools:
            bundle = item.get("bundleName", "")
            name = item.get("toolName", "")
            if bundle != self.bundle_name or not name:
                raise SkillLoadError("frontmatter 工具 bundle 与 Debug 配置不一致")
            path = self.skill_root / "references" / "tools" / f"{bundle}__{name}.json"
            try:
                snapshot = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise SkillLoadError(f"工具快照读取失败: {name}") from exc
            if snapshot.get("toolName") != name or snapshot.get("bundleName") != bundle:
                raise SkillLoadError(f"工具快照与 frontmatter 不一致: {name}")
            plugin_type = str(snapshot.get("pluginType") or "").strip().capitalize()
            if plugin_type not in {"Cloud", "Device"}:
                raise SkillLoadError(f"invalid pluginType: {name}")
            raw_arguments = snapshot.get("arguments")
            if not isinstance(raw_arguments, dict):
                raise SkillLoadError(f"工具快照缺少 arguments: {name}")
            properties = raw_arguments.get("properties")
            if not isinstance(properties, dict):
                properties = {}
            parameters = {
                "type": "object",
                "properties": {
                    str(key): _convert_property(value)
                    for key, value in properties.items()
                    if isinstance(value, dict)
                },
                "required": [
                    str(key) for key in raw_arguments.get("required", []) if isinstance(key, str)
                ],
            }
            registered[name] = RegisteredTool(
                name=name,
                bundle_name=bundle,
                plugin_type=plugin_type,
                description=str(snapshot.get("description") or ""),
                parameters=parameters,
                snapshot=snapshot,
            )
        return registered

    @property
    def model_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "load_skill",
                    "description": "按逻辑资源 ID 渐进加载当前 Skill 内容。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "skillName": {"type": "string"},
                            "resourceId": {"type": "string"},
                        },
                        "required": ["skillName", "resourceId"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "invoke",
                    "description": "串行执行当前 Skill 注册的端侧或云侧工具。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "skillName": {"type": "string"},
                            "functionName": {"type": "string"},
                            "arguments": {"type": "object"},
                        },
                        "required": ["skillName", "functionName", "arguments"],
                        "additionalProperties": False,
                    },
                },
            },
        ]

    def get(self, function_name: str) -> RegisteredTool:
        if not isinstance(function_name, str):
            raise ToolValidationError("工具名称必须是字符串")
        tool = self.tools.get(function_name)
        if tool is None:
            raise ToolValidationError(f"未知工具: {function_name}")
        return tool

    def validate_arguments(self, function_name: str, arguments: object) -> dict[str, Any]:
        tool = self.get(function_name)
        if not isinstance(arguments, dict):
            raise ToolValidationError("arguments 必须是 JSON 对象")
        unknown = set(arguments) - set(tool.parameters["properties"])
        if unknown:
            raise ToolValidationError(f"工具参数包含未声明字段: {sorted(unknown)}")
        missing = set(tool.parameters.get("required", [])) - set(arguments)
        if missing:
            raise ToolValidationError(f"工具参数缺少必填字段: {sorted(missing)}")
        for key, value in arguments.items():
            schema = tool.parameters["properties"].get(key)
            if isinstance(schema, dict) and not _matches_schema(value, schema):
                expected = schema.get("type", "object")
                raise ToolValidationError(f"工具参数 {key} 类型错误，期望 {expected}")
        return dict(arguments)


def _matches_schema(value: object, schema: dict[str, Any]) -> bool:
    expected = schema.get("type")
    if expected == "string":
        return isinstance(value, str)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "array":
        items = schema.get("items")
        if not isinstance(value, list):
            return False
        return not isinstance(items, dict) or all(_matches_schema(item, items) for item in value)
    if expected == "object":
        return isinstance(value, dict)
    return True

