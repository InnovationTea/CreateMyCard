# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from typing import Any, Literal

from pydantic import BaseModel, Field


class RequiredPackage(BaseModel):
    packageName: str
    minVersion: str | None = None


class Dependencies(BaseModel):
    minRomVersion: str | None = None
    minAppVersion: str | None = None
    minXiaoyiVersion: str | None = None
    requiredPackages: list[RequiredPackage] = Field(default_factory=list)
    requiredProviders: list[str] = Field(default_factory=list)
    requiredIntentTargets: list[str] = Field(default_factory=list)
    requiredPermissions: list[str] = Field(default_factory=list)


class DataCapability(BaseModel):
    id: str
    type: Literal["data"] = "data"
    description: str
    descriptionForLLM: str = ""
    inputSchema: dict[str, Any] = Field(default_factory=dict)
    outputSchema: dict[str, Any] = Field(default_factory=dict)
    defaultWriteResultTo: str | None = None
    dataModelSkeleton: dict[str, Any] = Field(default_factory=dict)
    dependencies: Dependencies = Field(default_factory=Dependencies)


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
