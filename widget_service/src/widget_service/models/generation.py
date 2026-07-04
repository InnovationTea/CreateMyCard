from typing import Any, Literal

from pydantic import BaseModel, Field

WidgetSize = Literal["2x2", "2x4"]


class DeviceContext(BaseModel):
    deviceId: str | None = None
    deviceType: str | None = None
    sysVersion: str | None = None
    deviceName: str | None = None
    odid: str | None = None
    udid: str | None = None
    romVersion: str | None = None
    marketingName: str | None = None
    ohosApiVersion: int | None = None


class CandidateDataBinding(BaseModel):
    capabilityId: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    writeResultTo: str | None = None


class EventAction(BaseModel):
    id: str | None = None
    call: str
    args: dict[str, Any] = Field(default_factory=dict)


class GenerationOptions(BaseModel):
    allowDegradation: bool = True
    returnArtifactInline: bool = False


class CardSpec(BaseModel):
    suggestSize: WidgetSize
    dataBindings: list[CandidateDataBinding] | None = None


class TaskSpec(BaseModel):
    userQuery: str
    size: WidgetSize
    eventCandidates: list[EventAction] = Field(default_factory=list)
    dataModel: dict[str, Any]
    assetCandidates: list[dict[str, Any]] = Field(default_factory=list)
