"""Focused test doubles for stages outside a test's scope."""

import pytest


@pytest.fixture
def ids_retry_clock(monkeypatch):
    """IDS 退避使用虚拟单调时钟，不真实等待、不影响全局 time 模块。"""
    import time
    from types import SimpleNamespace

    from services import ids_client

    clock = SimpleNamespace(now=0.0, sleeps=[])

    def sleep(delay):
        clock.sleeps.append(delay)
        clock.now += delay

    monkeypatch.setattr(ids_client, "time", SimpleNamespace(
        time=time.time, monotonic=lambda: clock.now, sleep=sleep,
    ))
    return clock


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


@pytest.fixture
def existing_generation_policy(monkeypatch):
    """既有创建链路测试显式隔离静态策略；静态专项继续验证默认准入。"""
    from config.config import get_settings

    monkeypatch.setattr(get_settings(), "enable_static_content_generation_policy", False)
