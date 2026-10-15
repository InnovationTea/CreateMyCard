"""定位随服务打包的250原始提示词与样例，不读取融合资源。"""

from pathlib import Path

DESIGN_COMPACT_PROFILE_ID = "design-compact-dsl"
PROFILE_DIR = Path(__file__).resolve().parents[2] / "data/protocol_profiles/single-step-250"
MODEL_FORMAT = "single-step-250"
UPSTREAM_COMMIT = "08cff1cd7d5c6993415bfafffe3eb77db5e6d88e"


class A2UIProtocolRegistry:
    """仅为冻结PromptBuilder提供原方法签名，资源绑定到独立快照。"""

    @staticmethod
    def _read(profile_id: str, filename: str) -> str:
        if profile_id != DESIGN_COMPACT_PROFILE_ID:
            raise ValueError("250 prompt loader only accepts its frozen profile")
        return (PROFILE_DIR / filename).read_text(encoding="utf-8")

    @classmethod
    def read_design_prompt(cls, profile_id: str) -> str:
        return cls._read(profile_id, "PROMPT.md")

    @classmethod
    def read_design_edit_prompt(cls, profile_id: str) -> str:
        return cls._read(profile_id, "EDIT_SYSTEM_PROMPT.md")

    @classmethod
    def read_design_repair_prompt(cls, profile_id: str) -> str:
        return cls._read(profile_id, "REPAIR_SYSTEM_PROMPT.md")
