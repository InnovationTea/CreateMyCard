"""可选真实 MySQL 验证；只创建/删除本测试随机命名的独立数据库。"""

import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import aiomysql
import pytest
from fastapi.testclient import TestClient

from api import routes
from config.config import Settings, get_settings
from core.errors import ErrorCode
from services import daily_usage_mysql
from services.daily_usage_limiter import DailyUsageError, DailyUsageLimiter
from start_websocket_server import create_app
from test_compact_dsl_interface_retry import make_response
from test_daily_usage_limiter import NOW
from test_daily_usage_routes import final_message, frame_info, payload

pytestmark = pytest.mark.skipif(
    not os.environ.get("WIDGET_TEST_MYSQL_HOST"), reason="isolated MySQL endpoint not configured"
)


@pytest.fixture(autouse=True)
def test_sts_password(monkeypatch):
    password = os.environ.get("WIDGET_TEST_MYSQL_PASSWORD", "")
    loader = Mock(return_value=password.encode("utf-8"))
    monkeypatch.setattr(daily_usage_mysql.sts_config, "get_sts_config", loader)
    return loader


@asynccontextmanager
async def mysql_limiter():
    database = "widget_usage_test_" + uuid.uuid4().hex
    options = {
        "host": os.environ.get("WIDGET_TEST_MYSQL_HOST", "127.0.0.1"),
        "port": int(os.environ.get("WIDGET_TEST_MYSQL_PORT", "3306")),
        "user": os.environ.get("WIDGET_TEST_MYSQL_USER", "root"),
        "password": os.environ.get("WIDGET_TEST_MYSQL_PASSWORD", ""),
        "autocommit": True,
    }
    admin = await aiomysql.connect(**options)
    limiter = None
    try:
        async with admin.cursor() as cursor:
            await cursor.execute(f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4")
            await cursor.execute(f"USE `{database}`")
            ddl_path = Path(__file__).resolve().parents[1] / "sql" / "daily_usage.sql"
            await cursor.execute(ddl_path.read_text(encoding="utf-8"))
        settings = Settings(
            enable_daily_usage_limit=True,
            daily_usage_limit=1,
            daily_usage_mysql_host=options.get("host"),
            daily_usage_mysql_port=options.get("port"),
            daily_usage_mysql_user=options.get("user"),
            daily_usage_mysql_database=database,
        )
        limiter = await daily_usage_mysql.create_daily_usage_limiter(settings)
        assert limiter is not None
        limiter.clock = lambda: NOW
        yield limiter, settings
    finally:
        if limiter is not None:
            await limiter.aclose()
        try:
            async with admin.cursor() as cursor:
                # database 是本函数生成的固定前缀 UUID，不来自用户或环境配置。
                await cursor.execute(f"DROP DATABASE IF EXISTS `{database}`")
        finally:
            admin.close()


@pytest.mark.asyncio
async def test_mysql_unique_key_handles_duplicate_concurrent_inserts():
    async with mysql_limiter() as (limiter, _settings):
        first = await limiter.check("user';--", "s&1")
        duplicate = await limiter.check("user';--", "s&1")
        assert first is not None
        assert duplicate is not None
        await asyncio.gather(
            limiter.repository.insert_success(first),
            limiter.repository.insert_success(duplicate),
            limiter.repository.insert_success(first),
        )
        snapshot = await limiter.repository.snapshot(first)
        assert snapshot.already_counted is True
        assert snapshot.used_count == 1
        assert await limiter.check("user';--", "s&1") is None
        with pytest.raises(DailyUsageError) as captured:
            await limiter.check("user';--", "s&2")
        assert captured.value.code == ErrorCode.DAILY_USAGE_LIMIT_EXCEEDED
        assert await limiter.check("another-user", "s&1") is not None


@pytest.mark.asyncio
async def test_mysql_cross_day_and_pool_recreation_keep_deduplication():
    async with mysql_limiter() as (limiter, settings):
        record = await limiter.check("user", "s&1")
        assert record is not None
        limiter.clock = lambda: NOW + timedelta(minutes=2)
        await limiter.record_success(record)
        reloaded = await daily_usage_mysql.create_daily_usage_limiter(settings)
        assert reloaded is not None
        try:
            reloaded.clock = lambda: NOW + timedelta(minutes=2)
            assert await reloaded.check("user", "s&1") is None
            assert await reloaded.check("user", "s&2") is not None
            assert (await reloaded.repository.snapshot(record)).used_count == 1
        finally:
            await reloaded.aclose()


@pytest.mark.asyncio
async def test_mysql_timeout_discards_connection_and_next_query_recovers(monkeypatch):
    async with mysql_limiter() as (limiter, _settings):
        bounded = DailyUsageLimiter(limiter.repository, 20, 0.03)
        original_sql = daily_usage_mysql._SNAPSHOT_SQL
        monkeypatch.setattr(
            daily_usage_mysql,
            "_SNAPSHOT_SQL",
            "SELECT SLEEP(0.3), 0 WHERE %s IS NOT NULL AND %s IS NOT NULL "
            "AND %s IS NOT NULL AND %s IS NOT NULL",
        )
        with pytest.raises(DailyUsageError) as captured:
            await bounded.check("user", "s&1")
        assert captured.value.code == ErrorCode.DAILY_USAGE_LIMIT_UNAVAILABLE
        monkeypatch.setattr(daily_usage_mysql, "_SNAPSHOT_SQL", original_sql)
        assert await limiter.check("user", "s&1") is not None


@pytest.mark.asyncio
async def test_mysql_missing_table_rejects_check_and_does_not_fail_delivered_result():
    async with mysql_limiter() as (limiter, _settings):
        record = await limiter.check("user", "s&1")
        assert record is not None
        async with limiter.repository.pool.acquire() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute("DROP TABLE t_genuiagent_daily_usage")
        with pytest.raises(DailyUsageError) as captured:
            await limiter.check("user", "s&2")
        assert captured.value.code == ErrorCode.DAILY_USAGE_LIMIT_UNAVAILABLE
        await limiter.record_success(record)


@pytest.mark.asyncio
async def test_real_app_lifespan_websocket_and_mysql_end_to_end(monkeypatch):
    async with mysql_limiter() as (limiter, configured):
        settings = get_settings()
        for option in (
            "enable_daily_usage_limit",
            "daily_usage_limit",
            "daily_usage_mysql_host",
            "daily_usage_mysql_port",
            "daily_usage_mysql_database",
            "daily_usage_mysql_user",
            "daily_usage_mysql_password_sts_config_key",
        ):
            monkeypatch.setattr(settings, option, getattr(configured, option))
        monkeypatch.setattr(settings, "enable_widget_directive_commands", True)
        monkeypatch.setattr(settings, "enable_compact_dsl_interface_retry", False)
        calls = []

        async def generate(request, *, before_model_call):
            calls.append(request)
            await before_model_call("2x2")
            return make_response()

        service = SimpleNamespace(trace_recorder=Mock(), generate_widget_card_compact_dsl=generate)
        monkeypatch.setattr(routes, "get_service", lambda _runtime: service)
        application = create_app()
        results = []
        with TestClient(application) as client:
            with client.websocket_connect(
                "/api/v1/ws/tools/generateWidgetCardCompactDsl"
            ) as websocket:
                for interaction in ("1", "1", "2"):
                    websocket.send_json(payload(interaction=interaction))
                    frames = []
                    while True:
                        received = websocket.receive_json()
                        frames.append(received)
                        if frame_info(received).get("streamType") == "final":
                            break
                    results.append(final_message(frames))
        assert len(calls) == 2
        assert results[0].get("status") == "success"
        assert results[1].get("status") == "success"
        assert results[2].get("errorCode") == ErrorCode.DAILY_USAGE_LIMIT_EXCEEDED
        assert application.state.daily_usage_limiter is None
        assert await limiter.check("user", "session&1") is None
