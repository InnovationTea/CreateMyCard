"""调试工具共享的原子文件写入，兼容 Windows 短暂的文件占用。"""

from __future__ import annotations

import logging
import os
import tempfile
import time
from pathlib import Path

_REPLACE_DELAYS = (0.01, 0.02, 0.04, 0.08, 0.16, 0.2, 0.2)
_WINDOWS_REPLACE_ERRORS = frozenset({5, 32, 33})
_logger = logging.getLogger(__name__)


def _replace_with_retry(source: Path, target: Path) -> None:
    for attempt in range(len(_REPLACE_DELAYS) + 1):
        try:
            os.replace(source, target)
            return
        except PermissionError as exc:
            retryable = getattr(exc, "winerror", None) in _WINDOWS_REPLACE_ERRORS
            exhausted = attempt == len(_REPLACE_DELAYS)
            if not retryable or exhausted:
                raise
            time.sleep(_REPLACE_DELAYS[attempt])


def atomic_write_text(path: Path, content: str) -> None:
    """完整写入并关闭独立临时文件后替换目标；失败不删除或截断原目标。

    调用方负责创建父目录。只重试 Windows 的访问/共享/锁冲突，累计退避不超过 0.71 秒；
    持续权限问题和其它 I/O 错误仍按原异常向上传播。
    """

    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(content)
        _replace_with_retry(temporary, path)
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError as exc:
                _logger.warning(
                    "原子写入临时文件清理失败，保留原写入结果：path=%s error=%s: %s",
                    temporary,
                    type(exc).__name__,
                    exc,
                )
