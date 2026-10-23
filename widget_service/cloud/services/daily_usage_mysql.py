"""MySQL 成功记录单表访问；连接池生命周期由应用管理。"""

import ssl

import aiomysql

from config.config import Settings
from services.daily_usage_limiter import DailyUsageLimiter, DailyUsageRecord, DailyUsageSnapshot

_SNAPSHOT_SQL = """
SELECT EXISTS(
    SELECT 1 FROM t_genuiagent_daily_usage
    WHERE uid_hash = %s AND request_id_hash = %s
), (
    SELECT COUNT(*) FROM t_genuiagent_daily_usage
    WHERE uid_hash = %s AND usage_date = %s
)
"""
_INSERT_SQL = """
INSERT INTO t_genuiagent_daily_usage (id, uid_hash, request_id_hash, usage_date)
VALUES (%s, %s, %s, %s)
ON DUPLICATE KEY UPDATE id = id
"""


class MySQLDailyUsageRepository:
    def __init__(self, pool: aiomysql.Pool) -> None:
        self.pool = pool

    async def snapshot(self, record: DailyUsageRecord) -> DailyUsageSnapshot:
        async with self.pool.acquire() as connection:
            try:
                async with connection.cursor() as cursor:
                    await cursor.execute(
                        _SNAPSHOT_SQL,
                        (
                            record.uid_hash,
                            record.request_id_hash,
                            record.uid_hash,
                            record.usage_date,
                        ),
                    )
                    row = await cursor.fetchone()
                    if row is None:
                        raise RuntimeError("daily usage snapshot returned no row")
                    return DailyUsageSnapshot(already_counted=bool(row[0]), used_count=int(row[1]))
            except BaseException:
                # 查询超时/取消后丢弃连接，不能把协议状态未知的连接放回池中。
                connection.close()
                raise

    async def insert_success(self, record: DailyUsageRecord) -> None:
        async with self.pool.acquire() as connection:
            try:
                async with connection.cursor() as cursor:
                    await cursor.execute(
                        _INSERT_SQL,
                        (
                            record.record_id,
                            record.uid_hash,
                            record.request_id_hash,
                            record.usage_date,
                        ),
                    )
            except BaseException:
                connection.close()
                raise

    async def aclose(self) -> None:
        self.pool.close()
        await self.pool.wait_closed()


async def create_daily_usage_limiter(settings: Settings) -> DailyUsageLimiter | None:
    limiter: DailyUsageLimiter | None = None
    if settings.enable_daily_usage_limit:
        required_values = (
            settings.daily_usage_mysql_host,
            settings.daily_usage_mysql_database,
            settings.daily_usage_mysql_user,
        )
        if not all(value.strip() for value in required_values):
            raise ValueError("daily usage MySQL host, database and user are required")
        ssl_context = None
        if settings.daily_usage_mysql_ssl_ca:
            ssl_context = ssl.create_default_context(cafile=settings.daily_usage_mysql_ssl_ca)
        # minsize=0：数据库临时不可用时仍可启动，查询接口不受影响；生成检查失败则拒绝。
        pool = await aiomysql.create_pool(
            host=settings.daily_usage_mysql_host,
            port=settings.daily_usage_mysql_port,
            user=settings.daily_usage_mysql_user,
            password=settings.daily_usage_mysql_password.get_secret_value(),
            db=settings.daily_usage_mysql_database,
            charset="utf8mb4",
            autocommit=True,
            minsize=0,
            maxsize=settings.daily_usage_mysql_pool_size,
            connect_timeout=settings.daily_usage_mysql_timeout_seconds,
            pool_recycle=300,
            ssl=ssl_context,
        )
        limiter = DailyUsageLimiter(
            MySQLDailyUsageRepository(pool),
            settings.daily_usage_limit,
            settings.daily_usage_mysql_timeout_seconds,
        )
    return limiter
