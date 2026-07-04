from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

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

WidgetCardOperation = Literal[
    "getWidgetCapabilityOverview",
    "getDataCapabilitySchemas",
    "generateWidgetCard",
]


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


class CandidateEventCandidate(BaseModel):
    """主 Agent 推荐的候选事件单项。

    入参：
    - capabilityId：来自能力概述的事件能力 ID。
    - action：候选事件动作，包含 call 和 args。
    出参：Pydantic 模型对象。
    """

    model_config = ConfigDict(extra="forbid")

    capabilityId: str
    action: EventAction


class GenerateWidgetCardRequest(VersionedToolRequest):
    userQuery: str
    size: WidgetSize = "2x4"
    candidateDataBindings: list[CandidateDataBinding] = Field(default_factory=list)
    candidateEventCandidates: list[CandidateEventCandidate] = Field(default_factory=list)
    candidateAssetIds: list[str] = Field(default_factory=list)
    options: GenerationOptions = Field(default_factory=GenerationOptions)
    uid: str | None = None
    device: DeviceContext | None = None


class WidgetCardServiceRequest(VersionedToolRequest):
    """统一云侧卡片生成工具请求。

    入参：
    - operation：要调用的能力名称。
    - dataCapabilityIds：获取数据能力 schema 时使用的数据能力 ID。
    - userQuery：生成卡片时使用的用户原始需求。
    - size：生成卡片时主 Agent 建议的尺寸。
    - candidateDataBindings：生成卡片时的候选数据能力调用。
    - candidateEventCandidates：生成卡片时的候选点击事件单数组。
    - candidateAssetIds：生成卡片时的候选素材 ID。
    出参：Pydantic 模型对象。
    """

    operation: WidgetCardOperation
    dataCapabilityIds: list[str] = Field(default_factory=list)
    userQuery: str | None = None
    size: WidgetSize | None = None
    candidateDataBindings: list[CandidateDataBinding] = Field(default_factory=list)
    candidateEventCandidates: list[CandidateEventCandidate] = Field(default_factory=list)
    candidateAssetIds: list[str] = Field(default_factory=list)
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
