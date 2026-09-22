from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent
SKILL_DIR = PACKAGE_DIR.parent
SCRIPT_DIR = SKILL_DIR / "scripts"
REPO_ROOT = SKILL_DIR
JSX_VALIDATOR_PATH = SCRIPT_DIR / "validate-generated-card.js"
PROMPT_PACKAGE_DIRS = {
    "2x2": SKILL_DIR / "references" / "prompt_2x2",
    "2x4": SKILL_DIR / "references" / "prompt_2x4",
}
PROMPT_RESOURCE_ROLES = {
    "info_process": ("information-processing",),
    "component_style": ("components", "component-combinations"),
    "jsx_contract": ("core",),
    "layout_patterns": ("layouts", "composition", "repair"),
}
PROMPT_FEW_SHOT_ROLES = {
    "2x4": ("fewshots",),
}
PLATFORM_REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
PLATFORM_RESOURCE_ROOT = PLATFORM_REPOSITORY_ROOT / "resources"
PLAYWRIGHT_BROWSERS_ROOT = SKILL_DIR / "playwright-browsers"

DEFAULT_INPUT = SKILL_DIR / "data" / "0911_2x2_raw.json"
DEFAULT_OUTPUT_ROOT = SKILL_DIR / "outputs-a2ui"
MODEL_THINKING_MODE = "disable"
THINKING_MODES = ("disable", "low", "high", "max")


def validator_subprocess_environment() -> dict[str, str]:
    """Return host-specific environment overrides for the shared Node validator."""
    environment = {"GENUI_RESOURCE_ROOT": str(PLATFORM_RESOURCE_ROOT)}
    if PLAYWRIGHT_BROWSERS_ROOT.is_dir():
        environment["PLAYWRIGHT_BROWSERS_PATH"] = str(PLAYWRIGHT_BROWSERS_ROOT)
    return environment


@dataclass(frozen=True, slots=True)
class ResourceStage:
    key: str
    label: str
    path: Path | None = None


RESOURCE_STAGES = (
    ResourceStage("info_process", "卡片信息处理与组件初选"),
    ResourceStage("component_style", "按输入 size 选择的组件语义、视觉与数据动作绑定规范"),
    ResourceStage("jsx_contract", "核心 JSX 语法与组件合同"),
    ResourceStage("layout_patterns", "按输入 size 选择的卡片布局约束"),
)
