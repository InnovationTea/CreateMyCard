# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from enum import Enum
from types import SimpleNamespace
from typing import List, Literal, Optional, Any, Union

from pydantic import BaseModel, Field

from errors.codes import StatusCode
from errors.errors import raise_error


class Role(str, Enum):
    """Message role options"""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


ROLE_VALUES = tuple(role.value for role in Role)
ROLE_TYPE = Literal[ROLE_VALUES]  # type: ignore


class ToolChoice(str, Enum):
    """Tool choice options"""

    NONE = "none"
    AUTO = "auto"
    REQUIRED = "required"


TOOL_CHOICE_VALUES = tuple(choice.value for choice in ToolChoice)
TOOL_CHOICE_TYPE = Literal[TOOL_CHOICE_VALUES]  # type: ignore
MCP_TOOL_PREFIX = "mcp_"
OFFLOAD_MESSAGE_FOLDER_NAME = "offload"


class StepResult(str, Enum):
    """Step execution states"""

    RUNNING = "RUNNING"
    ERROR = "ERROR"
    PAUSE = "PAUSE"


class AgentState(str, Enum):
    """Agent execution states"""

    IDLE = "IDLE"
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"
    ERROR = "ERROR"


class Function(BaseModel):
    name: str
    arguments: str


class ToolCall(BaseModel):
    """Represents a tool/function call in a message"""

    id: str
    type: str = "function"
    function: Function


class Message(BaseModel):
    """Represents a chat message in the conversation"""

    role: ROLE_TYPE = Field(...)  # type: ignore
    content: Optional[str] = Field(default=None)
    tool_calls: Optional[List[ToolCall]] = Field(default=None)
    name: Optional[str] = Field(default=None)
    tool_call_id: Optional[str] = Field(default=None)
    base64_image: Optional[str] = Field(default=None)

    def __add__(self, other) -> List["Message"]:
        """支持 Message + list 或 Message + Message 的操作"""
        if not isinstance(other, (list, Message)):
            raise_error(
                StatusCode.FLOW_VALIDATE_INPUT_MESSAGE_ERROR,
                error_msg=(
                    f"unsupported operand types for +: "
                    f"'{type(self).__name__}' and '{type(other).__name__}'"
                )
            )

        if isinstance(other, Message):
            other = [other]

        return [self] + other

    def __radd__(self, other) -> List["Message"]:
        """支持 list + Message 的操作"""
        if not isinstance(other, list):
            raise_error(
                StatusCode.FLOW_VALIDATE_INPUT_MESSAGE_ERROR,
                error_msg=(
                    f"unsupported operand types for +: "
                    f"'{type(other).__name__}' and '{type(self).__name__}'"
                )
            )

        return other + [self]

    def to_dict(self) -> dict:
        """Convert message to dictionary format"""
        message = {"role": self.role}
        if self.content is not None:
            message["content"] = self.content
        if self.tool_calls is not None:
            message["tool_calls"] = [tool_call.dict() for tool_call in self.tool_calls]
        if self.name is not None:
            message["name"] = self.name
        if self.tool_call_id is not None:
            message["tool_call_id"] = self.tool_call_id
        if self.base64_image is not None:
            message["base64_image"] = self.base64_image
        return message

    @classmethod
    def user_message(
            cls, content: str, base64_image: Optional[str] = None
    ) -> "Message":
        """Create a user message"""
        return cls(role=Role.USER, content=content, base64_image=base64_image)

    @classmethod
    def system_message(cls, content: str) -> "Message":
        """Create a system message"""
        return cls(role=Role.SYSTEM, content=content)

    @classmethod
    def assistant_message(
            cls, content: Optional[str] = None, base64_image: Optional[str] = None
    ) -> "Message":
        """Create an assistant message"""
        return cls(role=Role.ASSISTANT, content=content, base64_image=base64_image)

    @classmethod
    def tool_message(
            cls, content: str, name, tool_call_id: str, base64_image: Optional[str] = None
    ) -> "Message":
        """Create a tool message"""
        return cls(
            role=Role.TOOL,
            content=content,
            name=name,
            tool_call_id=tool_call_id,
            base64_image=base64_image,
        )

    @classmethod
    def from_tool_calls(
            cls,
            tool_calls: List[Any],
            content: Union[str, List[str]] = "",
            base64_image: Optional[str] = None,
            **kwargs,
    ):
        """Create ToolCallsMessage from raw tool calls.

        Args:
            tool_calls: Raw tool calls from LLM
            content: Optional message content
            base64_image: Optional base64 encoded image
        """
        formatted_calls = []

        for call in tool_calls:
            if isinstance(call, dict):
                call_id = call.get('id') or call.get('name')
                formatted_calls.append({"id": call_id, "function": dict(call.function), "type": "function"})

            elif isinstance(call, SimpleNamespace):
                call_id = getattr(call, 'id', None) or getattr(call, 'name', None)
                formatted_calls.append({"id": call_id, "function": call.function.__dict__, "type": "function"})
            else:
                # 不再用 call.get
                call_id = getattr(call, "id", None) or getattr(call, "name", None)

                function = getattr(call, "function", None)
                if hasattr(function, "model_dump"):
                    function = function.model_dump()
                elif hasattr(function, "dict"):
                    function = function.dict()
                else:
                    function = getattr(function, "__dict__", function)
                formatted_calls.append({
                    "id": call_id,
                    "function": function,
                    "type": "function",
                })
        return cls(
            role=Role.ASSISTANT,
            content=content,
            tool_calls=formatted_calls,
            base64_image=base64_image,
            **kwargs,
        )
