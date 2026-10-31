"""普通业务日志所需的有界诊断，不记录请求正文或完整资源。"""

import hashlib
import os
import re
from pathlib import Path
from typing import Any

from app.logger import json_for_log, logger


def exception_summary(exc: BaseException) -> dict[str, Any]:
    """保留直接原因，遮蔽异常文字中的地址、身份及凭证。"""
    result: dict[str, Any] = {"exceptionType": type(exc).__name__}
    for key, error in (("reason", exc), ("cause", exc.__cause__)):
        if error is None:
            continue
        message = re.sub(r"https?://[^\s\"'<>]+", "<redacted-url>", str(error))
        message = re.sub(
            r"(?i)(?:uid|odid|token|secret|password|authorization|api[_-]?key)"
            r"[\"']?\s*[:=]\s*[\"']?[^\s,;\"'}]+",
            "<redacted>", message,
        )
        result[key] = {"type": type(error).__name__, "message": message[:1000]}
    return result


def service_fingerprints(cloud_root: Path) -> dict[str, Any]:
    """使用部署文件内容识别版本，部署环境无需包含 Git 或 Git 元数据。"""
    digests = {}
    for kind, root, suffixes in (
        ("code", cloud_root, {".py"}),
        ("resources", cloud_root / "data", {".json", ".md", ".yaml"}),
    ):
        digest = hashlib.sha256()
        count = 0
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix not in suffixes:
                continue
            if "tests" in path.parts or "multi_step_generation" in path.parts:
                continue
            digest.update(path.relative_to(cloud_root).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
            count += 1
        digests[kind] = {"sha256": digest.hexdigest(), "fileCount": count}
    return {"buildRevision": os.environ.get("WIDGET_SERVICE_BUILD_REVISION"), **digests}


def log_service_fingerprints(cloud_root: Path) -> None:
    """诊断读取失败不影响服务启动。"""
    try:
        logger.info(
            f"[Main] service_build details={json_for_log(service_fingerprints(cloud_root))}"
        )
    except OSError as exc:
        logger.warning(
            f"[Main] service_build_unavailable details={json_for_log(exception_summary(exc))}"
        )
