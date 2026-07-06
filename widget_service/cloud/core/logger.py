# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import re
from typing import Any

import structlog


class AppLogger:
    """业务统一日志包装器。

    入参：
    - name：日志命名空间，一般传 `__name__`。
    出参：提供 debug、info、warning、warn、error、exception、critical 方法的日志对象。
    """

    def __init__(self, name: str) -> None:
        """初始化日志包装器。

        入参：
        - name：日志命名空间。
        出参：无。
        """
        self._logger = structlog.get_logger(name)

    def debug(self, event: str, **kwargs: Any) -> None:
        """输出 debug 日志。

        入参：
        - event：日志事件名。
        - kwargs：结构化日志字段。
        出参：无。
        """
        self._logger.debug(event, **kwargs)

    def info(self, event: str, **kwargs: Any) -> None:
        """输出 info 日志。

        入参：
        - event：日志事件名。
        - kwargs：结构化日志字段。
        出参：无。
        """
        self._logger.info(event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        """输出 warning 日志。

        入参：
        - event：日志事件名。
        - kwargs：结构化日志字段。
        出参：无。
        """
        self._logger.warning(event, **kwargs)

    def warn(self, event: str, **kwargs: Any) -> None:
        """输出 warn 日志。

        入参：
        - event：日志事件名。
        - kwargs：结构化日志字段。
        出参：无；内部转调 warning，兼容常见 logger.warn 写法。
        """
        self.warning(event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        """输出 error 日志。

        入参：
        - event：日志事件名。
        - kwargs：结构化日志字段。
        出参：无。
        """
        self._logger.error(event, **kwargs)

    def critical(self, event: str, **kwargs: Any) -> None:
        """输出 critical 日志。

        入参：
        - event：日志事件名。
        - kwargs：结构化日志字段。
        出参：无。
        """
        self._logger.critical(event, **kwargs)


class DesensitizedErrorTool:
    """脱敏 error 日志工具类。

    该工具类用于后续将敏感 error 日志手动替换为脱敏输出，业务 logger 方法仍然使用
    `logger.error(...)`。
    """

    @classmethod
    def error(
        cls,
        logger: AppLogger,
        event: str,
        sensitive_values: list[str] | None = None,
    ) -> None:
        """输出脱敏后的 error 日志。

        入参：
        - logger：业务统一 logger。
        - event：原始日志文本。
        - sensitive_values：需要直接替换的敏感值列表。
        出参：无。
        """
        logger.error(cls.sanitize(event, sensitive_values or []))

    @classmethod
    def sanitize(cls, event: str, sensitive_values: list[str] | None = None) -> str:
        """脱敏日志文本。

        入参：
        - event：原始日志文本。
        - sensitive_values：需要直接替换的敏感值列表。
        出参：脱敏后的日志文本。
        """
        result = event
        for value in sensitive_values or []:
            if value:
                result = result.replace(value, "***")
        patterns = [
            (
                r"(?i)(idsSign|sign|secretKey|accessKey|password|token)=([^,\s}]+)",
                r"\1=***",
            ),
            (
                r"(?i)('(?:idsSign|sign|secretKey|accessKey|password|token)':\s*)'[^']+'",
                r"\1'***'",
            ),
            (
                r'(?i)("(?:idsSign|sign|secretKey|accessKey|password|token)":\s*)"[^"]+"',
                r'\1"***"',
            ),
        ]
        for pattern, replacement in patterns:
            result = re.sub(pattern, replacement, result)
        return result


def get_logger(name: str) -> AppLogger:
    """获取业务统一日志对象。

    入参：
    - name：日志命名空间。
    出参：AppLogger 实例。
    """
    return AppLogger(name)
