# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import asyncio
import shutil
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

import requests

from config.config import get_settings


class UploadFileOSMS:
    """OBS 文件上传与下载适配器。

    上传当前仍使用本地 mock；下载由配置决定读取 mock 目录或真实 HTTPS 地址。
    """

    def __init__(
        self,
        base_url: str | None = None,
        mock_storage_dir: str | Path | None = None,
    ) -> None:
        """初始化 OBS 上传适配器。

        入参：
        - base_url：mock 文件访问地址前缀；不传时读取 artifact_base_url。
        - mock_storage_dir：mock 文件落盘目录；不传时使用 workspace/mock_obs。
        出参：无。
        """
        settings = get_settings()
        self.base_url = (base_url or settings.artifact_base_url).rstrip("/")
        self._mock_storage_dir = Path(mock_storage_dir) if mock_storage_dir else None

    @property
    def mock_storage_dir(self) -> Path:
        """返回 mock OBS 目录；未显式指定时跟随当前服务配置。"""
        if self._mock_storage_dir is not None:
            return self._mock_storage_dir
        return get_settings().WORKSPACE_ROOT / "mock_obs"

    @property
    def download_mode(self) -> str:
        """返回当前下载模式，供日志和测试使用。"""
        return "mock" if get_settings().enable_artifact_download_mock else "remote"

    async def upload_file(self, file_path: str | Path) -> str:
        """上传文件并返回访问地址。

        入参：
        - file_path：待上传的本地文件路径。
        出参：mock OBS 文件访问地址。
        异常：源文件不存在时抛出 FileNotFoundError。
        """
        source_path = Path(file_path)
        if not source_path.is_file():
            raise FileNotFoundError(f"待上传文件不存在: {source_path}")

        self.mock_storage_dir.mkdir(parents=True, exist_ok=True)
        target_path = self.mock_storage_dir / source_path.name
        await asyncio.to_thread(shutil.copy2, source_path, target_path)
        return f"{self.base_url}/{quote(source_path.name)}"

    async def download_file(
        self,
        file_url: str,
        *,
        max_bytes: int,
        timeout_seconds: float,
    ) -> bytes:
        """下载文件并返回原始字节。

        默认从 mock OBS 目录读取；关闭 ``enable_artifact_download_mock`` 后，
        使用不跟随重定向的 HTTPS 请求读取真实地址。
        """
        if max_bytes <= 0:
            raise ValueError("max_bytes must be greater than zero")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")

        if self.download_mode == "mock":
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(self._download_mock, file_url, max_bytes),
                    timeout=timeout_seconds,
                )
            except TimeoutError as exc:
                raise FileObsDownloadError("mock OBS read timed out") from exc

        return await asyncio.to_thread(
            self._download_remote,
            file_url,
            max_bytes,
            timeout_seconds,
        )

    def _download_mock(self, file_url: str, max_bytes: int) -> bytes:
        file_name = unquote(Path(urlsplit(file_url).path).name)
        if not file_name or Path(file_name).name != file_name:
            raise FileObsDownloadError("mock OBS object name is invalid")

        storage_root = self.mock_storage_dir.resolve()
        file_path = (storage_root / file_name).resolve()
        if file_path.parent != storage_root:
            raise FileObsDownloadError("mock OBS object escapes configured storage")
        if not file_path.is_file():
            raise FileObsNotFoundError("mock OBS object does not exist")
        if file_path.stat().st_size > max_bytes:
            raise FileObsTooLargeError("mock OBS object exceeds size limit")
        return file_path.read_bytes()

    @staticmethod
    def _download_remote(
        file_url: str,
        max_bytes: int,
        timeout_seconds: float,
    ) -> bytes:
        try:
            with requests.get(
                file_url,
                stream=True,
                allow_redirects=False,
                timeout=timeout_seconds,
            ) as response:
                if response.status_code == 404:
                    raise FileObsNotFoundError("remote OBS object does not exist")
                if 300 <= response.status_code < 400:
                    raise FileObsDownloadError("remote OBS redirect is not allowed")
                response.raise_for_status()

                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > max_bytes:
                    raise FileObsTooLargeError("remote OBS object exceeds size limit")

                payload = bytearray()
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    payload.extend(chunk)
                    if len(payload) > max_bytes:
                        raise FileObsTooLargeError("remote OBS object exceeds size limit")
                return bytes(payload)
        except (FileObsDownloadError, FileObsNotFoundError, FileObsTooLargeError):
            raise
        except requests.Timeout as exc:
            raise FileObsDownloadError("remote OBS download timed out") from exc
        except (requests.RequestException, ValueError) as exc:
            raise FileObsDownloadError("remote OBS download failed") from exc


class FileObsDownloadError(RuntimeError):
    """OBS 下载失败。"""


class FileObsNotFoundError(FileObsDownloadError):
    """OBS 对象不存在。"""


class FileObsTooLargeError(FileObsDownloadError):
    """OBS 对象超过允许大小。"""
