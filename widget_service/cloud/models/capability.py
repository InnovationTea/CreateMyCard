# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.json_pointer import parse_json_pointer

OUTPUT_LEAF_TYPES = {"string", "number", "integer", "boolean", "null"}
EVENT_PARAMETER_TYPES = OUTPUT_LEAF_TYPES | {"object", "array"}


def _sample_value_matches_type(value: Any, schema_type: str) -> bool:
    if schema_type == "string":
        return isinstance(value, str)
    if schema_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if schema_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if schema_type == "boolean":
        return isinstance(value, bool)
    return value is None


class RequiredPackage(BaseModel):
    # 运行时只消费包名；旧清单中的 minVersion 等字段保留兼容但不参与过滤。
    model_config = ConfigDict(extra="ignore")

    packageName: str


class Dependencies(BaseModel):
    # ROM/App/provider/intent 等旧依赖字段已经退出过滤逻辑。加载旧清单时忽略
    # 这些元数据，只保留当前实际使用的 requiredPackages，避免阻断整个接口。
    model_config = ConfigDict(extra="ignore")

    requiredPackages: list[RequiredPackage] = Field(default_factory=list)


class DataCapability(BaseModel):
    id: str
    type: Literal["data"] = "data"
    # 仅用于注册表内部控制临时上下线，不下发给主 Agent。
    enabled: bool = Field(default=True, exclude=True)
    description: str
    descriptionForLLM: str = ""
    inputSchema: dict[str, Any] = Field(default_factory=dict)
    outputSchema: dict[str, Any] = Field(default_factory=dict)
    # 可选的推荐写入根路径；实际生成始终以请求绑定中的 writeResultTo 为准。
    defaultWriteResultTo: str | None = None
    dataModelSkeleton: dict[str, Any] = Field(default_factory=dict)
    # 未声明依赖等价于不需要额外安装包，避免无依赖能力因缺字段而加载失败。
    dependencies: Dependencies = Field(default_factory=Dependencies)

    @model_validator(mode="after")
    def validate_output_leaf_metadata(self) -> "DataCapability":
        """保证输出 schema 可遍历，且叶子类型和说明可用于模型字段还原。"""
        if self.defaultWriteResultTo is not None:
            write_parts = parse_json_pointer(self.defaultWriteResultTo)
            if write_parts is None or len(write_parts) < 2 or write_parts[0] != "data":
                raise ValueError(
                    "defaultWriteResultTo must be a valid JSON Pointer below /data/"
                )
        errors, leaf_count = self._output_schema_errors(self.outputSchema)
        if leaf_count == 0:
            errors.append("/: outputSchema must contain at least one leaf field")
        if errors:
            raise ValueError("invalid outputSchema: " + ", ".join(errors))
        return self

    @classmethod
    def _output_schema_errors(
        cls,
        schema: dict[str, Any],
        path: tuple[str, ...] = (),
    ) -> tuple[list[str], int]:
        pointer = "/" + "/".join(path)
        if not isinstance(schema, dict):
            return [f"{pointer}: schema node must be an object"], 0
        schema_type = schema.get("type")
        if schema_type == "object":
            properties = schema.get("properties")
            if not isinstance(properties, dict) or not properties:
                return [f"{pointer}: object properties must be a non-empty object"], 0
            errors: list[str] = []
            leaf_count = 0
            for name, child in properties.items():
                child_errors, child_leaf_count = cls._output_schema_errors(
                    child,
                    (*path, name),
                )
                errors.extend(child_errors)
                leaf_count += child_leaf_count
            return errors, leaf_count
        if schema_type == "array":
            items = schema.get("items")
            if not isinstance(items, dict):
                return [f"{pointer}/0: array items must be a schema object"], 0
            return cls._output_schema_errors(items, (*path, "0"))
        if not path:
            return [f"{pointer}: root type must be object or array"], 0
        if schema_type not in OUTPUT_LEAF_TYPES:
            return [f"{pointer}: unsupported leaf type {schema_type!r}"], 0
        description = schema.get("description")
        if not isinstance(description, str) or not description:
            return [f"{pointer}: description must be a non-empty string"], 1
        # sampleValue 是生成质量提示，不是能力加载门禁。旧注册表缺失时由
        # TaskSpecBuilder 生成受控的类型默认值；显式提供但类型错误仍拒绝。
        if "sampleValue" in schema and not _sample_value_matches_type(
            schema["sampleValue"], schema_type
        ):
            return [f"{pointer}: sampleValue does not match type {schema_type}"], 1
        return [], 1


class EventDynamicArgument(BaseModel):
    """事件动作模板中允许主 Agent 替换的参数。"""

    path: str
    description: str
    type: str
    enum: list[Any] | None = None


class EventActionTemplate(BaseModel):
    """可直接复制到生成请求 action 的完整事件骨架。"""

    call: str
    args: dict[str, Any]


class EventCapabilityOverview(BaseModel):
    """第一接口向主 Agent 暴露的精简事件能力。"""

    id: str
    description: str
    actionTemplate: EventActionTemplate
    dynamicArguments: list[EventDynamicArgument] = Field(default_factory=list)


class EventCapability(EventCapabilityOverview):
    type: Literal["event"] = "event"
    targetApp: str | None = None
    targetScene: str | None = None
    parametersSchema: dict[str, Any]
    dependencies: Dependencies = Field(default_factory=Dependencies)

    @model_validator(mode="after")
    def validate_parameter_descriptions(self) -> "EventCapability":
        """保证动作模板、动态参数说明和内部参数 schema 始终一致。"""
        errors = self._parameter_schema_errors(self.parametersSchema)
        errors.extend(
            self._template_schema_errors(
                self.actionTemplate.args,
                self.parametersSchema,
            )
        )
        errors.extend(
            self._dynamic_argument_errors(
                self.dynamicArguments,
                self.parametersSchema,
            )
        )
        if errors:
            raise ValueError("invalid event parametersSchema: " + ", ".join(errors))
        return self

    @classmethod
    def _parameter_schema_errors(
        cls,
        schema: dict[str, Any],
        path: tuple[str, ...] = (),
        *,
        require_description: bool = False,
    ) -> list[str]:
        pointer = "/" + "/".join(path)
        if not isinstance(schema, dict):
            return [f"{pointer}: schema node must be an object"]
        errors: list[str] = []
        description = schema.get("description")
        description_missing = not isinstance(description, str) or not description.strip()
        if require_description and description_missing:
            errors.append(f"{pointer}: description must be a non-empty string")
        schema_type = schema.get("type")
        if schema_type not in EVENT_PARAMETER_TYPES:
            errors.append(f"{pointer}: unsupported parameter type {schema_type!r}")
            return errors
        if schema_type == "object":
            properties = schema.get("properties")
            if not isinstance(properties, dict):
                errors.append(f"{pointer}: object properties must be an object")
                return errors
            root_is_empty = not path and not properties
            if root_is_empty:
                errors.append("/: root properties must not be empty")
            for name, child in properties.items():
                errors.extend(
                    cls._parameter_schema_errors(
                        child,
                        (*path, name),
                        require_description=True,
                    )
                )
        elif schema_type == "array":
            items = schema.get("items")
            errors.extend(
                cls._parameter_schema_errors(
                    items,
                    (*path, "0"),
                    require_description=False,
                )
            )
        return errors

    @classmethod
    def _dynamic_argument_errors(
        cls,
        arguments: list[EventDynamicArgument],
        schema: dict[str, Any],
    ) -> list[str]:
        """保证注册表显式声明的动态参数没有遗漏或重复。"""
        expected = cls._dynamic_parameter_nodes(schema)
        actual_paths = [item.path for item in arguments]
        actual = {item.path: item for item in arguments}
        errors = []
        if len(actual) != len(actual_paths):
            errors.append("dynamicArguments paths must be unique")
        missing_paths = sorted(set(expected) - set(actual))
        extra_paths = sorted(set(actual) - set(expected))
        errors.extend(f"{path}: dynamic argument is missing" for path in missing_paths)
        errors.extend(f"{path}: dynamic argument is not declared by schema" for path in extra_paths)
        for path in sorted(set(expected) & set(actual)):
            node = expected[path]
            argument = actual[path]
            if argument.description != node.get("description"):
                errors.append(f"{path}: dynamic argument description does not match schema")
            if argument.type != node.get("type"):
                errors.append(f"{path}: dynamic argument type does not match schema")
            expected_enum = node.get("enum")
            if argument.enum != expected_enum:
                errors.append(f"{path}: dynamic argument enum does not match schema")
        return errors

    @classmethod
    def _dynamic_parameter_nodes(
        cls,
        schema: dict[str, Any],
        path: tuple[str, ...] = (),
    ) -> dict[str, dict[str, Any]]:
        """提取没有 const 的参数叶子，作为注册表 dynamicArguments 的权威集合。"""
        schema_type = schema.get("type")
        if schema_type == "object":
            nodes = {}
            for name, child in schema.get("properties", {}).items():
                nodes.update(cls._dynamic_parameter_nodes(child, (*path, name)))
            return nodes
        if schema_type == "array":
            return cls._dynamic_parameter_nodes(schema.get("items", {}), (*path, "0"))
        if "const" in schema:
            return {}
        pointer = "/" + "/".join(path)
        return {pointer: schema}

    @classmethod
    def _template_schema_errors(
        cls,
        template: Any,
        schema: dict[str, Any],
        path: tuple[str, ...] = (),
    ) -> list[str]:
        """保证参数模板与带说明的 schema 一一对应。"""
        if schema.get("type") != "object":
            return []
        pointer = "/" + "/".join(path)
        if not isinstance(template, dict):
            return [f"{pointer}: actionTemplate.args node must be an object"]
        properties = schema.get("properties", {})
        template_fields = set(template)
        schema_fields = set(properties)
        field_prefix = pointer.rstrip("/")
        errors = [
            f"{field_prefix}/{name}: actionTemplate.args field is missing from schema"
            for name in sorted(template_fields - schema_fields)
        ]
        errors.extend(
            f"{field_prefix}/{name}: schema field is missing from actionTemplate.args"
            for name in sorted(schema_fields - template_fields)
        )
        for name in sorted(template_fields & schema_fields):
            errors.extend(
                cls._template_schema_errors(
                    template[name],
                    properties[name],
                    (*path, name),
                )
            )
        return errors


class AssetCapabilityOverview(BaseModel):
    """第一接口向主 Agent 暴露的精简素材能力。"""

    id: str
    description: str


class AssetCapability(AssetCapabilityOverview):
    type: Literal["asset"] = "asset"
    src: str
    sceneTags: list[str] = Field(default_factory=list)
    minXiaoyiVersion: str | None = None


class RemovedCapability(BaseModel):
    id: str
    type: str = "data"
    reason: str
    userReadableReason: str
