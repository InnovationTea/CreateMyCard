# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import asyncio
import hashlib
import json
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from config.config import get_settings
from core.errors import ErrorCode
from models.artifact import WidgetArtifact
from utils.download_file_from_url import (
    DownloadFileError,
    DownloadFileNotFoundError,
    DownloadFileTooLargeError,
    download_file,
)

FENCED_BLOCK_RE = re.compile(
    r"```(?P<name>[a-zA-Z0-9_-]+)\r?\n(?P<body>.*?)\r?\n```",
    re.DOTALL,
)
REQUIRED_BLOCKS = {
    "schema",
    "genui",
    "cardspec",
    "taskspec",
    "effectivecapabilities",
    "removedcapabilities",
    "generationplan",
    "meta",
}


class SourceArtifactError(Exception):
    """来源 artifact 加载错误，携带稳定业务错误码。"""

    def __init__(self, error_code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class SourceArtifactLoadResult:
    artifact: WidgetArtifact
    artifact_digest: str
    url_hash: str
    read_latency_ms: float
    parse_latency_ms: float
    download_mode: str


def calculate_artifact_digest(artifact: WidgetArtifact) -> str:
    """按 artifact 规范化 JSON 计算追踪摘要。"""
    payload = json.dumps(
        artifact.model_dump(mode="json", exclude_none=True),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


class SourceArtifactRepository:
    """通过公共下载工具按配置读取并解析 artifact v2。"""

    def load(self, source_url: str) -> SourceArtifactLoadResult:
        settings = get_settings()
        source_name = PurePosixPath(urlsplit(source_url).path).name
        download_mode = (
            "mock" if settings.enable_artifact_download_mock else "remote"
        )
        read_started_at = time.perf_counter()
        try:
            if download_mode == "mock":
                content_bytes = self._read_mock_file(
                    source_name,
                    settings.WORKSPACE_ROOT / "mock_obs",
                    settings.source_artifact_max_bytes,
                    settings.source_artifact_read_timeout_seconds,
                )
            else:
                content_bytes = self._download_remote_file(
                    source_url,
                    settings.WORKSPACE_ROOT,
                    settings.source_artifact_max_bytes,
                    settings.source_artifact_read_timeout_seconds,
                )
        except (FileNotFoundError, DownloadFileNotFoundError) as exc:
            raise SourceArtifactError(
                ErrorCode.SOURCE_ARTIFACT_NOT_FOUND,
                "source artifact does not exist",
            ) from exc
        except DownloadFileTooLargeError as exc:
            raise SourceArtifactError(
                ErrorCode.SOURCE_ARTIFACT_INVALID,
                "source artifact exceeds size limit",
            ) from exc
        except (DownloadFileError, OSError, TimeoutError) as exc:
            raise SourceArtifactError(
                ErrorCode.SOURCE_ARTIFACT_DOWNLOAD_FAILED,
                "source artifact cannot be downloaded",
            ) from exc
        try:
            content = content_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SourceArtifactError(
                ErrorCode.SOURCE_ARTIFACT_INVALID,
                "source artifact is not valid UTF-8",
            ) from exc

        read_latency_ms = round((time.perf_counter() - read_started_at) * 1000, 2)
        parse_started_at = time.perf_counter()
        artifact = self._parse(content)
        parse_latency_ms = round((time.perf_counter() - parse_started_at) * 1000, 2)
        if len(artifact.genui) > settings.source_genui_max_chars:
            raise SourceArtifactError(
                ErrorCode.SOURCE_ARTIFACT_INVALID,
                "source artifact genui exceeds size limit",
            )
        if source_name.lower() != f"artifact_{artifact.meta.artifactId}.md".lower():
            raise SourceArtifactError(
                ErrorCode.SOURCE_ARTIFACT_INVALID,
                "source artifact object name does not match artifact metadata",
            )
        return SourceArtifactLoadResult(
            artifact=artifact,
            artifact_digest=calculate_artifact_digest(artifact),
            url_hash=hashlib.sha256(source_url.encode("utf-8")).hexdigest(),
            read_latency_ms=read_latency_ms,
            parse_latency_ms=parse_latency_ms,
            download_mode=download_mode,
        )

    @staticmethod
    def _read_mock_file(
        source_name: str,
        mock_storage_dir: Path,
        max_bytes: int,
        timeout_seconds: float,
    ) -> bytes:
        storage_root = mock_storage_dir.resolve()
        file_path = (storage_root / source_name).resolve()
        if file_path.parent != storage_root:
            raise OSError("mock artifact path escapes configured storage")
        if not file_path.is_file():
            raise FileNotFoundError(file_path)
        if file_path.stat().st_size > max_bytes:
            raise DownloadFileTooLargeError("mock artifact exceeds size limit")

        async def read_with_timeout() -> bytes:
            return await asyncio.wait_for(
                asyncio.to_thread(file_path.read_bytes),
                timeout=timeout_seconds,
            )

        return asyncio.run(read_with_timeout())

    @staticmethod
    def _download_remote_file(
        source_url: str,
        workspace_root: Path,
        max_bytes: int,
        timeout_seconds: float,
    ) -> bytes:
        download_dir = workspace_root / "source_artifact_downloads"
        download_dir.mkdir(parents=True, exist_ok=True)
        download_path = download_dir / f"source_{uuid.uuid4()}.md"
        try:
            asyncio.run(
                download_file(
                    source_url,
                    str(download_path),
                    max_size_bytes=max_bytes,
                    timeout_seconds=timeout_seconds,
                    allow_redirects=False,
                )
            )
            return download_path.read_bytes()
        finally:
            download_path.unlink(missing_ok=True)

    def _parse(self, content: str) -> WidgetArtifact:
        blocks: dict[str, str] = {}
        for match in FENCED_BLOCK_RE.finditer(content):
            name = match.group("name").lower()
            if name in blocks:
                raise SourceArtifactError(
                    ErrorCode.SOURCE_ARTIFACT_INVALID,
                    f"duplicate artifact block: {name}",
                )
            blocks[name] = match.group("body")
        if "schema" not in blocks:
            raise SourceArtifactError(
                ErrorCode.SOURCE_ARTIFACT_INVALID,
                "source artifact is missing schema block",
            )
        try:
            schema = json.loads(blocks["schema"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise SourceArtifactError(
                ErrorCode.SOURCE_ARTIFACT_INVALID,
                "source artifact schema block is invalid",
            ) from exc
        if schema.get("schemaVersion") != "widget-artifact-v2":
            raise SourceArtifactError(
                ErrorCode.SOURCE_ARTIFACT_SCHEMA_UNSUPPORTED,
                "source artifact schema is not supported",
            )
        missing = sorted(REQUIRED_BLOCKS - blocks.keys())
        if missing:
            raise SourceArtifactError(
                ErrorCode.SOURCE_ARTIFACT_INVALID,
                "source artifact is missing required blocks",
            )
        try:
            return WidgetArtifact(
                schemaVersion=schema["schemaVersion"],
                genui=blocks["genui"],
                cardSpec=json.loads(blocks["cardspec"]),
                taskSpec=json.loads(blocks["taskspec"]),
                effectiveCapabilities=json.loads(blocks["effectivecapabilities"]),
                removedCapabilities=json.loads(blocks["removedcapabilities"]),
                generationPlan=json.loads(blocks["generationplan"]),
                meta=json.loads(blocks["meta"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise SourceArtifactError(
                ErrorCode.SOURCE_ARTIFACT_INVALID,
                "source artifact content is invalid",
            ) from exc
