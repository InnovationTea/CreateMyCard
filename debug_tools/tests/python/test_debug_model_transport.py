"""调试 Agent 的模型传输配置回归。"""

from config.config import Settings
from debug_tools.end_to_end_debug.backend.debug_agent.agent import DebugAgentSession
from services.multi_step_generation.core.model_adapter import PlatformChatClient


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "deepseek_official_http_url": "https://api.deepseek.com/chat/completions",
        "deepseek_official_http_api_key": "test-key",
        "deepseek_official_http_model": "deepseek-flash",
        "deepseek_official_http_temperature": 0.7,
        "deepseek_official_http_top_p": 0.9,
        "deepseek_official_http_max_tokens": 8192,
        "deepseek_official_http_enable_thinking": False,
    }
    values.update(overrides)
    return Settings(**values)


def test_debug_agent_uses_official_http_thinking_setting_when_selected():
    debug_settings = type("DebugSettingsStub", (), {"request_timeout_seconds": 1.0})()
    session = object.__new__(DebugAgentSession)
    session.debug_settings = debug_settings
    settings = _settings(
        openai_master_client="deepseek_official_http",
        deepseek_official_http_enable_thinking=True,
    )

    client = session._default_model_client(None, settings)

    assert isinstance(client, PlatformChatClient)
    assert client.thinking_mode == "high"
