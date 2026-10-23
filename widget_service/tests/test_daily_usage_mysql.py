"""MySQL 存储适配、配置及应用生命周期测试。"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import start_websocket_server
from config.config import Settings, get_settings
from services import daily_usage_mysql
from services.daily_usage_limiter import DailyUsageRecord
from test_daily_usage_limiter import NOW


def connection_mocks():
    pool = MagicMock()
    connection = MagicMock()
    cursor = MagicMock()
    pool.acquire.return_value.__aenter__.return_value = connection
    connection.cursor.return_value.__aenter__.return_value = cursor
    cursor.execute = AsyncMock()
    cursor.fetchone = AsyncMock(return_value=(0, 19))
    pool.wait_closed = AsyncMock()
    return pool, connection, cursor


def record():
    return DailyUsageRecord("record-id", "a" * 64, "b" * 64, NOW.date())


@pytest.mark.asyncio
async def test_repository_uses_parameterized_queries_and_idempotent_insert():
    pool, _connection, cursor = connection_mocks()
    repository = daily_usage_mysql.MySQLDailyUsageRepository(pool)
    snapshot = await repository.snapshot(record())
    assert snapshot.used_count == 19
    assert snapshot.already_counted is False
    await repository.insert_success(record())
    assert cursor.execute.await_count == 2
    sql, parameters = cursor.execute.call_args.args
    assert "ON DUPLICATE KEY UPDATE" in sql
    assert parameters == ("record-id", "a" * 64, "b" * 64, NOW.date())
    assert "a" * 64 not in sql
    await repository.aclose()
    pool.close.assert_called_once()
    pool.wait_closed.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["snapshot", "insert_success"])
@pytest.mark.parametrize("exception", [OSError, asyncio.CancelledError])
async def test_error_or_cancellation_discards_connection(method, exception):
    pool, connection, cursor = connection_mocks()
    cursor.execute.side_effect = exception
    repository = daily_usage_mysql.MySQLDailyUsageRepository(pool)
    with pytest.raises(exception):
        await getattr(repository, method)(record())
    connection.close.assert_called_once()


@pytest.mark.asyncio
async def test_missing_snapshot_row_is_an_error_not_zero_usage():
    pool, connection, cursor = connection_mocks()
    cursor.fetchone.return_value = None
    repository = daily_usage_mysql.MySQLDailyUsageRepository(pool)
    with pytest.raises(RuntimeError):
        await repository.snapshot(record())
    connection.close.assert_called_once()


@pytest.mark.asyncio
async def test_disabled_factory_never_creates_pool(monkeypatch):
    factory = AsyncMock()
    monkeypatch.setattr(daily_usage_mysql.aiomysql, "create_pool", factory)
    assert (
        await daily_usage_mysql.create_daily_usage_limiter(Settings(enable_daily_usage_limit=False))
        is None
    )
    factory.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["host", "database", "user"])
async def test_enabled_factory_requires_connection_configuration(monkeypatch, missing):
    factory = AsyncMock()
    monkeypatch.setattr(daily_usage_mysql.aiomysql, "create_pool", factory)
    config = {
        "enable_daily_usage_limit": True,
        "daily_usage_mysql_host": "localhost",
        "daily_usage_mysql_database": "test",
        "daily_usage_mysql_user": "test",
    }
    config[f"daily_usage_mysql_{missing}"] = ""
    with pytest.raises(ValueError):
        await daily_usage_mysql.create_daily_usage_limiter(Settings(**config))
    factory.assert_not_called()


@pytest.mark.asyncio
async def test_factory_uses_bounded_async_pool_and_secret_password(monkeypatch):
    pool, _connection, _cursor = connection_mocks()
    factory = AsyncMock(return_value=pool)
    monkeypatch.setattr(daily_usage_mysql.aiomysql, "create_pool", factory)
    settings = Settings(
        enable_daily_usage_limit=True,
        daily_usage_mysql_host="localhost",
        daily_usage_mysql_database="test",
        daily_usage_mysql_user="test",
        daily_usage_mysql_password="test-only-secret",
    )
    assert "test-only-secret" not in repr(settings)
    limiter = await daily_usage_mysql.create_daily_usage_limiter(settings)
    assert limiter is not None
    options = factory.call_args.kwargs
    assert options.get("minsize") == 0
    assert options.get("maxsize") == 10
    assert options.get("autocommit") is True
    assert options.get("connect_timeout") == 3.0
    assert options.get("password") == "test-only-secret"
    await limiter.aclose()


@pytest.mark.parametrize(
    "option,value",
    [
        ("daily_usage_limit", 0),
        ("daily_usage_limit", -1),
        ("daily_usage_limit", "invalid"),
        ("daily_usage_limit", True),
        ("daily_usage_limit", 2.0),
        ("daily_usage_mysql_pool_size", 0),
        ("daily_usage_mysql_timeout_seconds", 0),
        ("daily_usage_mysql_port", 65536),
    ],
)
def test_invalid_configuration_rejected(option, value):
    with pytest.raises(ValidationError):
        Settings(**{option: value})


def test_environment_settings_override_defaults(monkeypatch):
    monkeypatch.setenv("WIDGET_SERVICE_ENABLE_DAILY_USAGE_LIMIT", "true")
    monkeypatch.setenv("WIDGET_SERVICE_DAILY_USAGE_LIMIT", "7")
    settings = Settings()
    assert settings.enable_daily_usage_limit is True
    assert settings.daily_usage_limit == 7


def test_lifespan_closes_pool_and_preserves_query_health(monkeypatch):
    limiter = Mock(aclose=AsyncMock())
    factory = AsyncMock(return_value=limiter)
    monkeypatch.setattr(start_websocket_server, "create_daily_usage_limiter", factory)
    application = start_websocket_server.create_app()
    with TestClient(application) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert application.state.daily_usage_limiter is limiter
    limiter.aclose.assert_awaited_once()
    assert application.state.daily_usage_limiter is None
    factory.assert_awaited_once_with(get_settings())


@pytest.mark.asyncio
async def test_tls_ca_enables_certificate_verification(monkeypatch):
    pool, _connection, _cursor = connection_mocks()
    factory = AsyncMock(return_value=pool)
    context = Mock()
    create_context = Mock(return_value=context)
    monkeypatch.setattr(daily_usage_mysql.aiomysql, "create_pool", factory)
    monkeypatch.setattr(daily_usage_mysql.ssl, "create_default_context", create_context)
    limiter = await daily_usage_mysql.create_daily_usage_limiter(
        Settings(
            enable_daily_usage_limit=True,
            daily_usage_mysql_host="db.example.test",
            daily_usage_mysql_database="test",
            daily_usage_mysql_user="test",
            daily_usage_mysql_ssl_ca="test-ca.pem",
        )
    )
    create_context.assert_called_once_with(cafile="test-ca.pem")
    assert factory.call_args.kwargs.get("ssl") is context
    assert limiter is not None
    await limiter.aclose()
