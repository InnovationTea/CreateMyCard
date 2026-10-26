"""Focused test doubles for stages outside a test's scope."""

import pytest


@pytest.fixture
def daily_usage_auth(monkeypatch):
    """每日次数 HTTP 测试使用独立假密钥，不访问真实 STS。"""
    from services import daily_usage_api

    def load_secret(config_key):
        assert config_key == "hag.osms.sk"
        return b"usage-test-secret"

    monkeypatch.setattr(daily_usage_api.sts_config, "get_sts_config", load_secret)


@pytest.fixture
def isolated_theme_stage(monkeypatch):
    """Plan/repair tests use partial artifacts and finite layout-model responses."""
    async def theme(artifact, *_args, **_kwargs):
        return artifact

    monkeypatch.setattr("services.post_layout_theme.theme_artifact", theme)
