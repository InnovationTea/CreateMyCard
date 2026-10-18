"""模板内部 Tersel 协议资源入口。"""

from pathlib import Path
from typing import Any

from services.protocol_registry import A2UIProtocolRegistry

TERSEL_PROTOCOL_PROFILE_ID = "terse-dsl-nested-2"
_PROFILES_ROOT = Path(__file__).resolve().parent / "resources" / "protocol_profiles"


def read_tersel_protocol_profile() -> dict[str, Any]:
    """读取模板内部 Tersel 转换所需的 A2UI 协议参数。"""
    return A2UIProtocolRegistry.read_design_protocol_profile(
        TERSEL_PROTOCOL_PROFILE_ID,
        _PROFILES_ROOT,
    )
