"""每日次数 API 适配器；只负责 HTTP 契约，不连接数据库或读取数据库密码。"""

import platform
from typing import Any

import httpx

from app.logger import task_logger
from config.config import Settings, get_container_ip
from services.daily_usage_limiter import DailyUsageLimiter, DailyUsageRecord, DailyUsageSnapshot


class APIDailyUsageRepository:
    def __init__(
        self,
        client: httpx.AsyncClient,
        snapshot_url: httpx.URL,
        record_url: httpx.URL,
    ) -> None:
        self.client = client
        self.snapshot_url = snapshot_url
        self.record_url = record_url

    async def _post(self, url: httpx.URL, record: DailyUsageRecord) -> dict[str, Any]:
        # 参考 ops_metrics 的包络，但必须等待响应，不使用后台 fire-and-forget。
        payload = {
            "sessionId": task_logger.get_session_id() or record.record_id,
            "body": {
                "recordId": record.record_id,
                "uidHash": record.uid_hash,
                "requestIdHash": record.request_id_hash,
                "usageDate": record.usage_date.isoformat(),
            },
        }
        response = await self.client.post(
            url, json=payload, headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError("daily usage API must return HTTP 200 after completion")
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError("daily usage API response must be an object")
        if result.get("success") is not True:
            raise ValueError("daily usage API did not confirm success")
        return result

    async def snapshot(self, record: DailyUsageRecord) -> DailyUsageSnapshot:
        result = await self._post(self.snapshot_url, record)
        data = result.get("data")
        if not isinstance(data, dict):
            raise ValueError("daily usage API snapshot data must be an object")
        counted = data.get("alreadyCounted")
        used_count = data.get("usedCount")
        if not isinstance(counted, bool):
            raise ValueError("daily usage API alreadyCounted must be boolean")
        if type(used_count) is not int:
            raise ValueError("daily usage API usedCount must be integer")
        if used_count < 0:
            raise ValueError("daily usage API usedCount must be nonnegative")
        return DailyUsageSnapshot(already_counted=counted, used_count=used_count)

    async def insert_success(self, record: DailyUsageRecord) -> None:
        await self._post(self.record_url, record)

    async def aclose(self) -> None:
        await self.client.aclose()


def _api_url(host: str, port: int, path: str) -> httpx.URL:
    if not path.startswith("/") or path.startswith("//"):
        raise ValueError("daily usage API path must be an absolute local path")
    if "?" in path or "#" in path:
        raise ValueError("daily usage API path must not contain query or fragment")
    return httpx.URL(scheme="http", host=host, port=port, path=path)


async def create_daily_usage_limiter(settings: Settings) -> DailyUsageLimiter | None:
    limiter: DailyUsageLimiter | None = None
    if settings.enable_daily_usage_limit:
        host = settings.daily_usage_api_host.strip()
        if not host:
            host = "127.0.0.1" if platform.system() == "Windows" else get_container_ip()
        if not isinstance(host, str) or not host.strip():
            raise ValueError("daily usage API host is required")
        snapshot_url = _api_url(
            host, settings.daily_usage_api_port, settings.daily_usage_api_snapshot_path
        )
        record_url = _api_url(
            host, settings.daily_usage_api_port, settings.daily_usage_api_record_path
        )
        # 内部同容器 HTTP 调用，不走环境代理、不跟随重定向，不在启动时发送请求。
        client = httpx.AsyncClient(
            timeout=settings.daily_usage_api_timeout_seconds,
            follow_redirects=False,
            trust_env=False,
        )
        limiter = DailyUsageLimiter(
            APIDailyUsageRepository(client, snapshot_url, record_url),
            settings.daily_usage_limit,
            settings.daily_usage_api_timeout_seconds,
        )
    return limiter
