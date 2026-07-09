# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

WidgetSize = Literal["2x2", "2x4"]


class DeviceContext(BaseModel):
    deviceId: str | None = None
    deviceType: str | None = None
    sysVersion: str | None = None
    deviceName: str | None = None
    odid: str | None = None
    udid: str | None = None
    romVersion: str
    marketingName: str | None = None
    ohosApiVersion: int


class CandidateDataBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capabilityId: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    writeResultTo: str
    updateModel: dict[str, Any] = Field(default_factory=dict)


class EventAction(BaseModel):
    id: str | None = None
    call: str
    args: dict[str, Any]


class GenerationOptions(BaseModel):
    allowDegradation: bool = True
    returnArtifactInline: bool = False


class CardSpec(BaseModel):
    suggestSize: WidgetSize
    dataBindings: list[CandidateDataBinding] | None = None


class TaskSpec(BaseModel):
    userQuery: str
    size: WidgetSize
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    eventCandidates: list[EventAction] = Field(default_factory=list)
    dataModel: dict[str, Any]
    assetCandidates: list[dict[str, Any]] = Field(default_factory=list)
