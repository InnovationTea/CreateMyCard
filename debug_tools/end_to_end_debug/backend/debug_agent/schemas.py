from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class DeviceDebugContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uid: str = "debug-user"
    odid: str = "debug-device"
    deviceId: str = "debug-device"
    phoneType: str = "ALN-AL00"
    appVersion: str = "11.9.9.342"
    romVersion: str = "ALN-AL00 7.0.0.100"
    locale: str = "zh-CN"
    countryCode: str = "CN"
    deviceFormation: str = "phone"
    deviceType: int = 0
    sysVer: str = "HarmonyOS"
    paginationLimit: int = 5
    paginationStart: str = ""


class ConfigureFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["configure"]
    context: DeviceDebugContext


class MessageFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["message"]
    content: str = Field(min_length=1)


class SimpleFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["cancel", "reset"]
    profile: str | None = None


class DebugEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str
    sequence: int
    sessionId: str
    runId: str = ""
    timestamp: str
    data: dict[str, Any] = Field(default_factory=dict)


class ArtifactPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runId: str
    artifactUrl: str
    artifactDigest: str = ""
    digestMatches: bool | None = None
    genui: str = ""
    cardSpec: dict[str, Any] = Field(default_factory=dict)
    taskSpec: dict[str, Any] = Field(default_factory=dict)
    effectiveCapabilities: dict[str, Any] = Field(default_factory=dict)
    removedCapabilities: list[Any] = Field(default_factory=list)
    generationPlan: dict[str, Any] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)
    designToken: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok"]
    debugHost: str
    debugPort: int
    upstream: str
    provider: str
    model: str
    enableArtifactDownloadMock: bool
    enableWidgetEdit: bool

