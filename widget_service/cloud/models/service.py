# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from core.errors import GenerationStatus


class IDSQueryKeys(BaseModel):
    """IDS 查询 key 对象。

    入参：
    - odid：设备 odid；缺失时由调用方使用 deviceId 兜底。
    出参：可序列化为 IDS queryRequestData.keys 的实体对象。
    """

    odid: str


class IDSQueryRequestData(BaseModel):
    """IDS 单条查询条件。

    入参：
    - keys：IDS 查询键值。
    出参：可序列化为 IDS queryRequestData 数组元素。
    """

    keys: IDSQueryKeys


class IDSNamespaceQuery(BaseModel):
    """IDS namespace 查询对象。

    入参：
    - dataType：IDS 数据类型。
    - queryRequestData：该 namespace 下的查询条件列表。
    出参：可序列化为 IDS nameSpaces 数组元素。
    """

    dataType: str
    queryRequestData: list[IDSQueryRequestData]


class IDSInstalledAppsQueryBody(BaseModel):
    """IDS 已安装应用查询 body。

    入参：
    - requestId：本次查询请求 ID。
    - callingUid：调用方标识。
    - nameSpaces：查询 namespace 列表。
    出参：可序列化为 IDS HTTP 请求 body。
    """

    requestId: str
    callingUid: str
    nameSpaces: list[IDSNamespaceQuery]


class IDSRequestHeaders(BaseModel):
    """IDS HTTP 请求头。

    入参：
    - contentType：内容类型，对外序列化为 `Content-Type`。
    - devFakeId：调试设备 fake id。
    - idsSign：IDS 签名。
    出参：可序列化为 HTTP headers。
    """

    model_config = ConfigDict(populate_by_name=True)

    contentType: str = Field(alias="Content-Type")
    devFakeId: str
    idsSign: str


class IDSHttpRequest(BaseModel):
    """IDS HTTP 请求定义。

    入参：
    - method：HTTP 方法。
    - url：IDS 查询 URL。
    - headers：请求头实体。
    - body：请求 body 实体。
    出参：可用于真实 HTTP 调用或测试断言的结构化请求。
    """

    method: Literal["GET", "POST"]
    url: str
    headers: IDSRequestHeaders
    body: IDSInstalledAppsQueryBody


class WidgetWebSocketResultMessage(BaseModel):
    """WebSocket result 消息。

    入参：
    - type：固定为 result。
    - tool：工具名。
    - operation：本次调用的 operation。
    - requestId：客户端请求 ID。
    - data：业务响应对象。
    - status：本次调用状态；生成接口透传业务状态，其它接口成功时为 success。
    - errorCode：错误码；成功时为空字符串。
    - error：错误详情；成功时为空对象，预留给后续扩展。
    出参：可发送给客户端的 result 消息。
    """

    type: Literal["result"] = "result"
    tool: str = "widgetCardService"
    operation: str
    requestId: str | None = None
    data: dict[str, Any]
    status: str = "success"
    errorCode: str = ""
    error: dict[str, Any] = Field(default_factory=dict)


class WidgetWebSocketErrorMessage(BaseModel):
    """WebSocket error 消息。

    入参：
    - type：固定为 error。
    - tool：工具名。
    - operation：本次调用的 operation。
    - requestId：客户端请求 ID。
    - data：业务响应对象；失败时为空对象。
    - status：本次调用状态；异常时固定为 failed。
    - errorCode：错误码。
    - error：错误详情对象，包含 message/details 等排障信息。
    出参：可发送给客户端的 error 消息。
    """

    type: Literal["error"] = "error"
    tool: str = "widgetCardService"
    operation: str
    requestId: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    status: Literal["failed"] = "failed"
    errorCode: str
    error: dict[str, Any] = Field(default_factory=dict)


class WidgetStreamInfo(BaseModel):
    """华为流处理插件默认输出参数 streamInfo。

    入参：
    - streamContent：截止当前帧的全量答复文本。
    - streamingTextId：一次请求内稳定的流式文本 ID。
    - streamType：流式帧类型，支持 start、partial 和 final。
    - textType：文本格式，支持 markdown 和 plainText。
    出参：符合流处理插件输出参数配置的 streamInfo 对象。
    """

    streamContent: str
    streamingTextId: str
    streamType: Literal["start", "partial", "final"] = "final"
    textType: Literal["markdown", "plainText"] = "plainText"


class WidgetPluginReply(BaseModel):
    """华为流处理插件 reply 响应内容。

    入参：
    - streamInfo：答复文本结构。
    - items：结构化业务数据；当前完整旧出参整体放在 items[0]。
    出参：符合流处理插件输出参数配置的 reply 对象。
    """

    streamInfo: WidgetStreamInfo
    items: list[dict[str, Any]] = Field(default_factory=list)


class WidgetPluginStreamResponse(BaseModel):
    """华为流处理插件 WebSocket 输出包络。

    入参：
    - errorCode：插件响应码，成功为 "0"，非 "0" 视为失败。
    - errorMessage：错误描述或空字符串。
    - reply：响应内容，包含 streamInfo 和 items。
    出参：发送给小艺插件平台的流处理插件响应。
    """

    errorCode: str = "0"
    errorMessage: str = ""
    reply: WidgetPluginReply


class ArtifactSaveResult(BaseModel):
    """artifact 保存结果。

    入参：
    - artifactUrl：端侧可下载地址。
    - artifactDigest：artifact sha256 摘要。
    出参：结构化保存结果。
    """

    artifactUrl: str
    artifactDigest: str


class ResponsePlan(BaseModel):
    """生成响应规划结果。

    入参：
    - status：生成状态。
    - message：用户可读话术。
    - errorCode：错误码；成功时为空字符串。
    出参：结构化响应规划结果。
    """

    status: GenerationStatus
    message: str
    errorCode: str = ""


class RetryResult(BaseModel):
    """重试控制结果。

    入参：
    - result：最终操作结果。
    - retryCount：实际重试次数。
    - errors：最终校验错误列表。
    出参：结构化重试结果。
    """

    result: str
    retryCount: int
    errors: list[str] = Field(default_factory=list)


class A2UIPromptProtocolProfile(BaseModel):
    """A2UI prompt 中暴露给模型的协议摘要。

    入参：
    - id：协议 profile ID。
    - version：A2UI 协议版本。
    - catalogId：组件 catalog ID。
    - sizes：支持尺寸定义。
    - componentWhitelist：组件白名单。
    出参：模型 prompt 内的协议摘要实体。
    """

    id: str
    version: str
    catalogId: str
    sizes: dict[str, dict[str, int]]
    componentWhitelist: list[str]


class A2UIPromptUserMessage(BaseModel):
    """A2UI prompt 的 user 部分。

    入参：
    - taskSpec：微服务构造的 TaskSpec。
    - protocolProfile：协议 profile 摘要。
    - degradationContext：降级上下文。
    出参：模型 prompt user 消息实体。
    """

    taskSpec: dict[str, Any]
    protocolProfile: A2UIPromptProtocolProfile
    degradationContext: str = ""


class A2UIPromptPayload(BaseModel):
    """A2UI 模型调用 prompt。

    入参：
    - system：系统提示词。
    - user：用户侧结构化输入。
    出参：结构化模型调用 prompt。
    """

    system: str
    user: A2UIPromptUserMessage
