# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
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


class DeviceInfoEnvelope(BaseModel):
    """外部工具请求中的 deviceInfo 结构。

    入参：
    - countryCode：设备国家码。
    - deviceFormation：设备形态。
    - deviceType：设备类型编码。
    - locale：设备语言区域。
    - phoneType：手机型号。
    - prdVer：宿主应用版本。
    - sysVer：系统版本。
    - time：端侧请求时间。
    出参：Pydantic 模型对象；未声明字段会保留，方便后续接入 romVersion 等真实字段。
    """

    model_config = ConfigDict(extra="allow")

    countryCode: str | None = None
    deviceFormation: str | None = None
    deviceType: int | str | None = None
    locale: str | None = None
    phoneType: str | None = None
    prdVer: str | None = None
    sysVer: str | None = None
    time: str | None = None


class SessionEnvelope(BaseModel):
    """外部工具请求中的 session 结构。

    入参：
    - sessionId：会话 ID。
    - interactionId：当前交互 ID。
    - isNew：是否新会话。
    出参：Pydantic 模型对象。
    """

    sessionId: str | None = None
    interactionId: str | None = None
    isNew: bool | None = None


class UserAuthUserEnvelope(BaseModel):
    """外部工具请求中的 userAuth.user 结构。

    入参：
    - userId：用户 ID。
    出参：Pydantic 模型对象。
    """

    userId: str | None = None


class UserAuthEnvelope(BaseModel):
    """外部工具请求中的 userAuth 结构。

    入参：
    - user：用户鉴权信息。
    出参：Pydantic 模型对象。
    """

    user: UserAuthUserEnvelope = Field(default_factory=UserAuthUserEnvelope)


class UtteranceEnvelope(BaseModel):
    """外部工具请求中的 utterance 结构。

    入参：
    - original：用户原始表达。
    - type：输入类型。
    出参：Pydantic 模型对象。
    """

    original: str | None = None
    type: str | None = None


class PaginationEnvelope(BaseModel):
    """外部工具请求中的 pagination 结构。

    入参：
    - limit：分页数量。
    - start：分页游标。
    出参：Pydantic 模型对象。
    """

    limit: int | None = None
    start: str | None = None


class ToolRequestEnvelope(BaseModel):
    """WebSocket 外部请求包络。

    入参：
    - content：业务入参，对应旧协议中的 arguments。
    - deviceInfo：端侧设备信息，服务会转换成内部 DeviceContext。
    - session：会话信息，服务会用 sessionId + '&' + interactionId 生成 requestId。
    - userAuth：用户鉴权信息，服务会从 user.userId 提取 uid。
    - utterance：用户原始表达；generateWidgetCard 未传 userQuery 时可兜底使用 original。
    - pagination：分页信息，当前接口暂不消费。
    - version：外部包络协议版本。
    - bundleName：宿主业务包名。
    出参：Pydantic 模型对象。
    """

    model_config = ConfigDict(extra="allow")

    content: dict[str, Any] = Field(default_factory=dict)
    deviceInfo: DeviceInfoEnvelope = Field(default_factory=DeviceInfoEnvelope)
    pagination: PaginationEnvelope | None = None
    session: SessionEnvelope = Field(default_factory=SessionEnvelope)
    userAuth: UserAuthEnvelope = Field(default_factory=UserAuthEnvelope)
    utterance: UtteranceEnvelope | None = None
    version: str | None = None
    bundleName: str | None = None


class VersionedToolRequest(BaseModel):
    locale: str = "zh-CN"
    uid: str
    device: DeviceContext
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


class GenerateWidgetCardResponse(BaseModel):
    apiVersion: str = "v1"
    status: GenerationStatus
    artifactUrl: str = ""
    artifactDigest: str = ""
    suggestSize: WidgetSize
    message: str
    removedCapabilities: list[RemovedCapability] = Field(default_factory=list)
    errorCode: str = ""
    artifact: dict[str, Any] | None = None
    effectiveCapabilities: dict[str, list[Any]] = Field(default_factory=dict)
