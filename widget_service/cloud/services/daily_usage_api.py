"""每日次数 API 适配器；只负责 HTTP 契约，不连接数据库或读取数据库密码。"""

import base64
import hashlib
import hmac
import time
from time import perf_counter
from typing import Any

import httpx

from app.logger import logger, task_logger
from config.config import Settings
from services.daily_usage_limiter import DailyUsageLimiter, DailyUsageRecord, DailyUsageSnapshot
from utils.base_utils import sts_config

OSMS_SECRET_CONFIG_KEY = "hag.osms.sk"


def _format_timestamp() -> str:
    """生成 Unix 毫秒时间戳。"""
    return str(time.time_ns() // 1_000_000)


def _build_auth_headers(access_key: str) -> dict[str, str]:
    """使用 STS 密钥对本次请求的时间戳签名。"""
    if not access_key:
        raise ValueError("每日次数接口鉴权 access key 为空")
    secret_key = sts_config.get_sts_config(OSMS_SECRET_CONFIG_KEY)
    secret_bytes = secret_key.encode("utf-8") if isinstance(secret_key, str) else secret_key
    if not secret_bytes:
        raise ValueError("每日次数接口鉴权 secret key 为空")
    timestamp = _format_timestamp()
    digest = hmac.new(secret_bytes, timestamp.encode("utf-8"), hashlib.sha256).digest()
    return {
        "Content-Type": "application/json",
        "x-access-key": access_key,
        "x-ts": timestamp,
        "x-sign": base64.b64encode(digest).decode("utf-8"),
    }


class APIDailyUsageRepository:
    def __init__(
        self,
        client: httpx.AsyncClient,
        snapshot_url: httpx.URL,
        record_url: httpx.URL,
        access_key: str,
    ) -> None:
        self.client = client
        self.snapshot_url = snapshot_url
        self.record_url = record_url
        self.access_key = access_key

    async def _post(
        self, url: httpx.URL, record: DailyUsageRecord, operation: str
    ) -> dict[str, Any]:
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
        started_at = perf_counter()
        logger.info(
            f"[Daily Usage] api_started operation={operation} record_id={record.record_id}"
        )
        try:
            headers = _build_auth_headers(self.access_key)
            response = await self.client.post(
                url, json=payload, headers=headers
            )
        except Exception as exc:
            logger.error(
                f"[Daily Usage] api_failed operation={operation} record_id={record.record_id} "
                f"exception_type={type(exc).__name__} "
                f"duration_ms={(perf_counter() - started_at) * 1000:.2f}"
            )
            raise
        logger.info(
            f"[Daily Usage] api_response operation={operation} record_id={record.record_id} "
            f"http_status={response.status_code} "
            f"duration_ms={(perf_counter() - started_at) * 1000:.2f}"
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
        result = await self._post(self.snapshot_url, record, "snapshot")
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
        await self._post(self.record_url, record, "record_success")

    async def aclose(self) -> None:
        await self.client.aclose()


def _api_url(base_url: str, path: str) -> httpx.URL:
    if not path.startswith("/") or path.startswith("//"):
        raise ValueError("daily usage API path must be an absolute local path")
    if "?" in path or "#" in path:
        raise ValueError("daily usage API path must not contain query or fragment")
    base = httpx.URL(base_url.strip())
    if base.scheme not in ("http", "https") or not base.host:
        raise ValueError("daily usage API requires an absolute HTTP(S) daily_usage_slb")
    if base.userinfo or base.query or base.fragment:
        raise ValueError("daily_usage_slb must not contain credentials, query or fragment")
    # 接口路径从域名根目录开始，保留 daily_usage_slb 的协议、主机和端口。
    return base.copy_with(path=path)


async def create_daily_usage_limiter(settings: Settings) -> DailyUsageLimiter | None:
    limiter: DailyUsageLimiter | None = None
    logger.info(
        f"[Daily Usage] initializing enabled={settings.enable_daily_usage_limit} "
        f"limit={settings.daily_usage_limit} "
        f"timeout_seconds={settings.daily_usage_api_timeout_seconds}"
    )
    if settings.enable_daily_usage_limit:
        snapshot_url = _api_url(
            settings.daily_usage_slb, settings.daily_usage_api_snapshot_path
        )
        record_url = _api_url(
            settings.daily_usage_slb, settings.daily_usage_api_record_path
        )
        # 内部 HTTP(S) 调用，不走环境代理、不跟随重定向，不在启动时发送请求。
        client = httpx.AsyncClient(
            timeout=settings.daily_usage_api_timeout_seconds,
            follow_redirects=False,
            trust_env=False,
        )
        limiter = DailyUsageLimiter(
            APIDailyUsageRepository(client, snapshot_url, record_url, settings.hag_osms_ak),
            settings.daily_usage_limit,
            settings.daily_usage_api_timeout_seconds,
        )
    logger.info(f"[Daily Usage] initialized client_ready={limiter is not None}")
    return limiter
