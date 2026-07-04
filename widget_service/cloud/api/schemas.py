from typing import Any

from pydantic import BaseModel, Field

from core.errors import GenerationStatus
from models.capability import (
    AssetCapability,
    DataCapability,
    EventCapability,
    RemovedCapability,
)
from models.generation import (
    CandidateDataBinding,
    DeviceContext,
    EventAction,
    GenerationOptions,
    WidgetSize,
)


class VersionedToolRequest(BaseModel):
    locale: str = "zh-CN"
    appVersion: str = "1.0.0"
    romVersion: str = "7.0.0"
    xiaoyiVersion: str = "1.0.0"
    capabilityRegistryVersion: str | None = None
    protocolProfileId: str | None = None


class CapabilityOverviewRequest(VersionedToolRequest):
    pass


class DataCapabilityOverview(BaseModel):
    id: str
    description: str


class CapabilityOverviewResponse(BaseModel):
    apiVersion: str = "v1"
    capabilityRegistryVersion: str
    dataCapabilities: list[DataCapabilityOverview]
    eventCapabilities: list[EventCapability]
    assetCandidates: list[AssetCapability]


class DataCapabilitySchemasRequest(VersionedToolRequest):
    dataCapabilityIds: list[str]


class DataCapabilitySchemasResponse(BaseModel):
    apiVersion: str = "v1"
    capabilityRegistryVersion: str
    dataCapabilities: list[DataCapability]
    missingCapabilityIds: list[str] = Field(default_factory=list)


class GenerateWidgetCardRequest(VersionedToolRequest):
    userQuery: str
    size: WidgetSize = "2x4"
    candidateDataBindings: list[CandidateDataBinding] = Field(default_factory=list)
    candidateEventCapabilityIds: list[str] = Field(default_factory=list)
    candidateEventActions: list[EventAction] = Field(default_factory=list)
    candidateEventCapabilities: list[EventAction] = Field(default_factory=list)
    candidateAssetIds: list[str] = Field(default_factory=list)
    options: GenerationOptions = Field(default_factory=GenerationOptions)
    uid: str | None = None
    device: DeviceContext | None = None


class GenerateWidgetCardResponse(BaseModel):
    apiVersion: str = "v1"
    status: GenerationStatus
    artifactUrl: str = ""
    artifactDigest: str = ""
    suggestSize: WidgetSize
    userMessage: str
    removedCapabilities: list[RemovedCapability] = Field(default_factory=list)
    errorCode: str = ""
    artifact: dict[str, Any] | None = None
    effectiveCapabilities: dict[str, list[Any]] = Field(default_factory=dict)


class ToolDispatchRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)
