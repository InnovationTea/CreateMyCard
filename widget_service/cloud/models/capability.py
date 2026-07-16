# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.json_pointer import parse_json_pointer

OUTPUT_LEAF_TYPES = {"string", "number", "integer", "boolean", "null"}


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
    model_config = ConfigDict(extra="forbid")

    packageName: str


class Dependencies(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requiredPackages: list[RequiredPackage] = Field(default_factory=list)


class DataCapability(BaseModel):
    id: str
    type: Literal["data"] = "data"
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
        """保证输出 schema 可遍历，且每个叶子都能还原为模型字段说明。"""
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
        if "sampleValue" not in schema:
            return [f"{pointer}: sampleValue is required"], 1
        if not _sample_value_matches_type(schema["sampleValue"], schema_type):
            return [f"{pointer}: sampleValue does not match type {schema_type}"], 1
        return [], 1


class EventCapability(BaseModel):
    id: str
    type: Literal["event"] = "event"
    call: str
    description: str
    targetApp: str | None = None
    targetScene: str | None = None
    argsTemplate: dict[str, Any] = Field(default_factory=dict)
    parametersSchema: dict[str, Any] = Field(default_factory=dict)
    dependencies: Dependencies = Field(default_factory=Dependencies)


class AssetCapability(BaseModel):
    id: str
    type: Literal["asset"] = "asset"
    src: str
    description: str
    sceneTags: list[str] = Field(default_factory=list)
    minXiaoyiVersion: str | None = None


class RemovedCapability(BaseModel):
    id: str
    type: str = "data"
    reason: str
    userReadableReason: str
