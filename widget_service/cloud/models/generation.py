# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from dataclasses import dataclass
from typing import Any, Literal

from packaging.version import InvalidVersion, Version
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator

WidgetSize = Literal["2x2", "2x4"]
DEFAULT_WIDGET_SIZE: WidgetSize = "2x2"


@dataclass(frozen=True)
class ModelRequestContext:
    """一次工具请求传递给物理模型服务的稳定会话上下文。"""

    session_id: str
    interaction_id: str
    device_id: str
    country_code: str
    app_version: str
    app_name: str


class DeviceContext(BaseModel):
    _source_rom_version: str | None = PrivateAttr(default=None)

    deviceId: str | None = None
    deviceType: str | None = None
    sysVersion: str | None = None
    deviceName: str | None = None
    odid: str | None = None
    udid: str | None = None
    romVersion: str
    marketingName: str | None = None


class CandidateDataBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capabilityId: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    writeResultTo: str
    candidateOutputFields: list[str] = Field(default_factory=list)


class CardSpecDataBinding(BaseModel):
    """微服务裁决后写入最终 CardSpec 的数据绑定。"""

    model_config = ConfigDict(extra="forbid")

    capabilityId: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    writeResultTo: str


class EventAction(BaseModel):
    id: str | None = None
    description: str | None = None
    call: str
    args: dict[str, Any]


class GenerationOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowDegradation: bool = True


class CardSpec(BaseModel):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    suggestSize: WidgetSize
    imageDomainWhitelist: list[str] | None = None
    dataBindings: list[CardSpecDataBinding] | None = None


class TaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    userQuery: str
    size: WidgetSize
    appVersion: str = "11.7.5.208"
    eventCandidates: list[EventAction] = Field(default_factory=list)
    dataModelSchema: dict[str, Any]
    assetCandidates: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("appVersion")
    @classmethod
    def validate_app_version(cls, value: str) -> str:
        """保证下游始终获得可比较的原始端侧版本。"""
        if not value.strip():
            raise ValueError("appVersion must be a non-empty version string")
        try:
            Version(value)
        except InvalidVersion as error:
            raise ValueError(f"Invalid appVersion: {value}") from error
        return value
