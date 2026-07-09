# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import asyncio
import shutil
from pathlib import Path
from urllib.parse import quote

from config.config import get_settings


class UploadFileOSMS:
    """OBS 文件上传适配器。

    当前为本地 mock 实现：将上传文件复制到 workspace/mock_obs，
    并返回与真实 OBS 一致形式的访问地址。
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
        self.mock_storage_dir = Path(
            mock_storage_dir or settings.WORKSPACE_ROOT / "mock_obs"
        )

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
