# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from typing import Any

from pydantic import BaseModel, Field

from models.capability import RemovedCapability


class ArtifactMeta(BaseModel):
    apiVersion: str = "v1"
    taskSpecVersion: str = "task-spec-v1"
    cardSpecVersion: str = "card-spec-v1"
    dslProtocolVersion: str = "v0.9"
    skillVersion: str = "skill-widget-v1"
    protocolProfileId: str
    capabilityRegistryVersion: str
    artifactSchemaVersion: str = "widget-artifact-v1"
    createdAt: int


class WidgetArtifact(BaseModel):
    schemaVersion: str = "widget-artifact-v1"
    genui: str
    cardSpec: dict[str, Any]
    taskSpec: dict[str, Any]
    effectiveCapabilities: dict[str, list[Any]] = Field(default_factory=dict)
    removedCapabilities: list[RemovedCapability] = Field(default_factory=list)
    meta: ArtifactMeta
