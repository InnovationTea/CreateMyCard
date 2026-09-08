from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent
SKILL_DIR = PACKAGE_DIR.parent
SCRIPT_DIR = SKILL_DIR / "scripts"
REPO_ROOT = SKILL_DIR
JSX_VALIDATOR_PATH = SCRIPT_DIR / "validate-generated-card.js"
PLATFORM_REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
PLATFORM_RESOURCE_ROOT = PLATFORM_REPOSITORY_ROOT / "resources"
PLAYWRIGHT_BROWSERS_ROOT = SKILL_DIR / "playwright-browsers"

DEFAULT_INPUT = SKILL_DIR / "data" / "20_tasks_2x2_raw.json"
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
    ResourceStage("info_process", "卡片信息处理与组件初选", SKILL_DIR / "references" / "info_process.md"),
    ResourceStage("component_style", "按输入 size 选择的组件语义、视觉与数据动作绑定规范"),
    ResourceStage("jsx_contract", "核心 JSX 语法与组件合同", SKILL_DIR / "references" / "core.md"),
    ResourceStage("layout_patterns", "按输入 size 选择的卡片布局约束"),
)
