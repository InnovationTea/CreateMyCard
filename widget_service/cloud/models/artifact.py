# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from models.capability import RemovedCapability
from models.generation import CandidateDataBinding


class GenerationPlan(BaseModel):
    """供多轮编辑继承的完整候选计划。"""

    model_config = ConfigDict(extra="forbid")

    candidateDataBindings: list[CandidateDataBinding] = Field(default_factory=list)
    candidateEventCandidates: list[dict[str, Any]] = Field(default_factory=list)
    candidateAssetIds: list[str] = Field(default_factory=list)


class ArtifactMeta(BaseModel):
    apiVersion: str = "v1"
    taskSpecVersion: str = "task-spec-v1"
    cardSpecVersion: str = "card-spec-v1"
    dslProtocolVersion: str = "v0.9"
    skillVersion: str = "skill-widget-v1"
    protocolProfileId: str
    capabilityRegistryVersion: str
    artifactSchemaVersion: Literal["widget-artifact-v2"] = "widget-artifact-v2"
    generationMode: Literal["create", "edit"] = "create"
    artifactId: str = "00000000-0000-0000-0000-000000000000"
    sourceArtifactDigest: str | None = None
    createdAt: int


class WidgetArtifact(BaseModel):
    schemaVersion: Literal["widget-artifact-v2"] = "widget-artifact-v2"
    genui: str
    cardSpec: dict[str, Any]
    taskSpec: dict[str, Any]
    effectiveCapabilities: dict[str, list[Any]] = Field(default_factory=dict)
    removedCapabilities: list[RemovedCapability] = Field(default_factory=list)
    generationPlan: GenerationPlan = Field(default_factory=GenerationPlan)
    meta: ArtifactMeta
