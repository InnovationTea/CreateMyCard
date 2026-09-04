# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator

from core.errors import GenerationStatus
from models.capability import (
    AssetCapabilityOverview,
    DataCapability,
    EventCapabilityOverview,
    RemovedCapability,
)
from models.generation import (
    CandidateDataBinding,
    DeviceContext,
    EventAction,
    GenerationOptions,
    ModelRequestContext,
    WidgetSize,
)

WidgetCardOperation = Literal[
    "getWidgetCapabilityOverview",
    "getDataCapabilitySchemas",
    "generateWidgetCard",
    "generateWidgetCardCompactDsl",
    "generateWidgetCardTerseDslNested2",
]


class DeviceInfoEnvelope(BaseModel):
    """外部工具请求中的 deviceInfo 结构。

    入参：
    - countryCode：设备国家码。
    - deviceFormation：设备形态。
    - deviceType：设备类型编码。
    - locale：设备语言区域。
    - phoneType：手机型号。
    - prdVer：端侧传入的业务 API 版本，字段名保持端侧协议原名。
    - sysVer：系统版本。
    - romVersion：ROM 完整版本字符串，字段名固定为 romVersion。
    - time：端侧请求时间。
    出参：Pydantic 模型对象；未声明字段会忽略，不作为 ROM 版本别名处理。
    """

    model_config = ConfigDict(extra="ignore")

    countryCode: str | None = None
    deviceFormation: str | None = None
    deviceType: int | str | None = None
    locale: str | None = None
    phoneType: str | None = None
    prdVer: str | None = None
    sysVer: str | None = None
    romVersion: str | None = None
    time: str | None = None
    deviceId: str | None = None
    udid: str | None = None
    marketingName: str | None = None


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
    - content：业务入参；可携带优先使用的 uid、romVersion 和可选 odid。
    - deviceInfo：端侧设备信息；content 未提供 romVersion 时作为回退来源。
    - session：会话信息，服务会用 sessionId + '&' + interactionId 生成 requestId。
    - userAuth：用户鉴权信息；content 未提供 uid 时从 user.userId 回退提取。
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
    _model_request_context: ModelRequestContext | None = PrivateAttr(default=None)
    _raw_request_body: str | None = PrivateAttr(default=None)

    locale: str = "zh-CN"
    uid: str
    device: DeviceContext
    prdVer: str | None = None
    protocolProfileId: str | None = None


class CapabilityOverviewRequest(VersionedToolRequest):
    pass


class DataCapabilityOverview(BaseModel):
    id: str
    description: str


class CapabilityOverviewResponse(BaseModel):
    dataCapabilities: list[DataCapabilityOverview]
    eventCapabilities: list[EventCapabilityOverview]
    assetCandidates: list[AssetCapabilityOverview]
    unavailableCapabilities: list[str] = Field(default_factory=list)


class DataCapabilitySchemasRequest(VersionedToolRequest):
    dataCapabilityIds: list[str] = Field(min_length=1)


class DataCapabilitySchemasResponse(BaseModel):
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
    userQuery: str = Field(min_length=1)
    sourceArtifactUrl: str | None = None
    size: WidgetSize | None = None
    title: str | None = Field(default=None, min_length=1)
    description: str | None = Field(default=None, min_length=1)
    candidateDataBindings: list[CandidateDataBinding] | None = None
    candidateEventCandidates: list[CandidateEventCandidate] | None = None
    candidateAssetIds: list[str] | None = None
    options: GenerationOptions = Field(default_factory=GenerationOptions)

    @model_validator(mode="after")
    def validate_generation_mode_fields(self) -> "GenerateWidgetCardRequest":
        """校验 create 条件必填及 edit 的显式空值。"""
        is_edit = "sourceArtifactUrl" in self.model_fields_set
        if not is_edit:
            if self.title is None:
                raise ValueError("title is required in create mode")
            if self.description is None:
                raise ValueError("description is required in create mode")
            return self

        if not isinstance(self.sourceArtifactUrl, str) or not self.sourceArtifactUrl.strip():
            raise ValueError("sourceArtifactUrl must be a non-empty string")
        nullable_edit_fields = (
            "size",
            "title",
            "description",
            "candidateDataBindings",
            "candidateEventCandidates",
            "candidateAssetIds",
        )
        for field_name in nullable_edit_fields:
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null in edit mode")
        return self


class WidgetCardServiceRequest(VersionedToolRequest):
    """统一云侧卡片生成工具请求。

    入参：
    - operation：要调用的能力名称。
    - dataCapabilityIds：获取数据能力 schema 时使用的数据能力 ID。
    - userQuery：生成卡片时使用的用户原始需求。
    - sourceArtifactUrl：编辑模式使用的上一版 artifact URL。
    - size：生成卡片时主 Agent 建议的尺寸。
    - title：生成卡片时主 Agent 建议的标题。
    - description：生成卡片时主 Agent 建议的简短说明。
    - candidateDataBindings：生成卡片时的候选数据能力调用。
    - candidateEventCandidates：生成卡片时的候选点击事件单数组。
    - candidateAssetIds：生成卡片时的候选素材 ID。
    出参：Pydantic 模型对象。
    """

    operation: WidgetCardOperation
    dataCapabilityIds: list[str] = Field(default_factory=list)
    userQuery: str | None = None
    sourceArtifactUrl: str | None = None
    size: WidgetSize | None = None
    title: str | None = Field(default=None, min_length=1)
    description: str | None = Field(default=None, min_length=1)
    candidateDataBindings: list[CandidateDataBinding] | None = None
    candidateEventCandidates: list[CandidateEventCandidate] | None = None
    candidateAssetIds: list[str] | None = None


class GenerateWidgetCardResponse(BaseModel):
    status: GenerationStatus
    artifactUrl: str = ""
    artifactDigest: str = ""
    suggestSize: WidgetSize
    message: str
    removedCapabilities: list[RemovedCapability] = Field(default_factory=list)
    errorCode: str = ""
    effectiveCapabilities: dict[str, list[Any]] = Field(default_factory=dict)
