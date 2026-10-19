"""示例配置必须能够加载项目内置在线 Skill 的工具。"""

from types import SimpleNamespace

from debug_tools.end_to_end_debug.backend.debug_agent.config import (
    DebugSettings,
    load_debug_config,
)
from debug_tools.end_to_end_debug.backend.debug_agent.skill_loader import SkillLoader
from debug_tools.end_to_end_debug.backend.debug_agent.tool_registry import ToolRegistry
from debug_tools.paths import DEBUG_TOOLS_ROOT, REPOSITORY_ROOT


def test_example_config_matches_online_skill_tools() -> None:
    config = load_debug_config(DEBUG_TOOLS_ROOT / "debug_tool.yaml.example", REPOSITORY_ROOT)
    settings = DebugSettings.from_config(config, SimpleNamespace(server_port=8855))
    loader = SkillLoader(
        config.skill_root,
        settings.skill_name,
        skill_directory=settings.skill_directory,
    )

    registry = ToolRegistry(loader.skill_root, loader.catalog, settings.bundle_name)

    assert registry.tools
    for tool in registry.tools.values():
        assert tool.bundle_name == settings.bundle_name
