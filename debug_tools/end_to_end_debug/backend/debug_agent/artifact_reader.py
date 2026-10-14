from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from debug_tools.paths import WIDGET_SERVICE_ROOT

from .schemas import ArtifactPreview

if TYPE_CHECKING:
    from services.source_artifact_repository import SourceArtifactRepository


class ArtifactReader:
    """通过正式来源 repository 回读当前会话生成过的 artifact。"""

    def __init__(self, repository: SourceArtifactRepository | None = None) -> None:
        if repository is None:
            repository = _source_repository_type()()
        self.repository = repository

    async def read(
        self,
        run_id: str,
        artifact_url: str,
        expected_digest: str = "",
    ) -> tuple[ArtifactPreview | None, str | None]:
        try:
            loaded = await asyncio.to_thread(self._load_artifact, artifact_url)
        except Exception as exc:
            raw_code = getattr(exc, "error_code", None)
            error_code = getattr(raw_code, "value", raw_code)
            if not isinstance(error_code, str):
                raise
            return None, f"{error_code}: {exc}"
        artifact = loaded.artifact.model_dump(mode="json", exclude_none=True)
        digest_matches: bool | None = None
        if expected_digest:
            digest_matches = loaded.artifact_digest == expected_digest
        preview = ArtifactPreview(
            runId=run_id,
            artifactUrl=artifact_url,
            artifactDigest=loaded.artifact_digest,
            digestMatches=digest_matches,
            genui=str(artifact.get("genui") or ""),
            cardSpec=_dict_value(artifact, "cardSpec"),
            taskSpec=_dict_value(artifact, "taskSpec"),
            effectiveCapabilities=_dict_value(artifact, "effectiveCapabilities"),
            removedCapabilities=_list_value(artifact, "removedCapabilities"),
            generationPlan=_dict_value(artifact, "generationPlan"),
            meta=_dict_value(artifact, "meta"),
            designToken=loaded.design_token,
        )
        return preview, None

    def _load_artifact(self, artifact_url: str) -> Any:
        """优先从生成服务返回的 URL 读取，失败后回退到本地 workspace 文件。"""
        get_settings = _settings_loader()

        remote_error: Exception | None = None
        try:
            return self.repository.load(artifact_url)
        except Exception as exc:
            # 本地调试时远端 OBS 地址通常不可达，此时继续尝试 workspace 中的同名文件。
            remote_error = exc

        parsed_url = urlsplit(artifact_url)
        # ``mock://artifact.md`` stores the filename in netloc while
        # ``/mock_obs/artifact.md`` stores it in path.  Both forms are used by
        # local debug fixtures, but neither may escape the configured roots.
        name = Path(parsed_url.path).name or Path(parsed_url.netloc).name
        workspace_root = get_settings().WORKSPACE_ROOT
        candidates = _artifact_candidates(workspace_root, name)
        local_path = next((candidate for candidate in candidates if candidate.is_file()), None)
        if local_path is not None:
            try:
                parsed = self.repository.parse_document(local_path.read_text(encoding="utf-8"))
                repository_module = _source_repository_module()
                calculate_artifact_digest = repository_module.calculate_artifact_digest

                return SimpleNamespace(
                    artifact=parsed.artifact,
                    design_token=parsed.design_token,
                    artifact_digest=calculate_artifact_digest(parsed.artifact),
                    url_hash="",
                    read_latency_ms=0.0,
                    parse_latency_ms=0.0,
                    download_mode="local-workspace",
                )
            except Exception as local_error:
                # 已找到本地副本但解析失败时，返回本地错误，便于定位副本内容问题。
                if remote_error is not None:
                    raise local_error from remote_error
                raise
        if remote_error is not None:
            raise remote_error
        raise FileNotFoundError(name)


def _dict_value(value: dict[str, Any], key: str) -> dict[str, Any]:
    item = value.get(key)
    return dict(item) if isinstance(item, dict) else {}


def _list_value(value: dict[str, Any], key: str) -> list[Any]:
    item = value.get(key)
    return list(item) if isinstance(item, list) else []


def _source_repository_module() -> Any:
    module_names = (
        "services.source_artifact_repository",
    )
    last_error: ImportError | None = None
    original_sys_path = list(sys.path)
    repo_root = _repo_root()
    cloud_root = repo_root / "cloud"
    conflicting_path = cloud_root / "services" / "multi_step_generation"
    cloud_root_text = str(cloud_root)
    if cloud_root_text not in sys.path:
        sys.path.insert(0, cloud_root_text)
    try:
        sys.path[:] = [
            item
            for item in sys.path
            if _resolved_path(item) != conflicting_path.resolve()
        ]
        for module_name in module_names:
            try:
                return importlib.import_module(module_name)
            except ImportError as exc:
                last_error = exc
    finally:
        sys.path[:] = original_sys_path
    if last_error is not None:
        raise last_error
    raise ImportError("source artifact repository is unavailable")


def _resolved_path(value: str) -> Path | None:
    if not value:
        return None
    try:
        return Path(value).resolve()
    except (OSError, RuntimeError):
        return None


def _source_repository_type() -> Any:
    return _source_repository_module().SourceArtifactRepository


def _settings_loader() -> Any:
    module_names = ("config.config",)
    last_error: ImportError | None = None
    for module_name in module_names:
        try:
            return importlib.import_module(module_name).get_settings
        except ImportError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise ImportError("settings module is unavailable")


def _artifact_candidates(workspace_root: Path, name: str) -> tuple[Path, ...]:
    cloud_root = _repo_root() / "cloud"
    roots = (workspace_root, cloud_root / "workspace", cloud_root)
    candidates: list[Path] = []
    for root in roots:
        for candidate in (root / name, root / "mock_obs" / name):
            if candidate not in candidates:
                candidates.append(candidate)
    return tuple(candidates)


def _repo_root() -> Path:
    return WIDGET_SERVICE_ROOT
