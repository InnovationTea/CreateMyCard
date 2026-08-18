# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

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
    dataBindings: list[CardSpecDataBinding] | None = None


class TaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    userQuery: str
    size: WidgetSize
    eventCandidates: list[EventAction] = Field(default_factory=list)
    dataModelSchema: dict[str, Any]
    assetCandidates: list[dict[str, Any]] = Field(default_factory=list)
