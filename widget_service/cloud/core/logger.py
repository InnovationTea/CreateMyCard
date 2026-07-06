import re
import traceback
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

    def error_with_exception(self, event: str, exc: BaseException) -> None:
        """输出带完整异常堆栈的 error 日志。

        入参：
        - event：日志事件文本。
        - exc：捕获到的异常对象。
        出参：无。
        """
        # 按当前排障要求，异常日志先完整打印异常类型、异常内容和 traceback。
        self.error(
            f"exception_type={type(exc).__name__} exception={exc!r} "
            f"traceback={traceback.format_exc()} event={event}"
        )

    def desensitized_error(
        self,
        event: str,
        sensitive_values: list[str] | None = None,
    ) -> None:
        """输出脱敏后的 error 日志。

        入参：
        - event：原始日志文本。
        - sensitive_values：需要直接替换的敏感值列表。
        出参：无。
        """
        # 该方法先提供给后续手动替换使用；默认会处理常见 token/key/sign/password 字段。
        self.error(self._desensitize(event, sensitive_values or []))

    def _desensitize(self, event: str, sensitive_values: list[str]) -> str:
        """脱敏日志文本。

        入参：
        - event：原始日志文本。
        - sensitive_values：需要直接替换的敏感值列表。
        出参：脱敏后的日志文本。
        """
        result = event
        for value in sensitive_values:
            if value:
                result = result.replace(value, "***")
        patterns = [
            r"(?i)(idsSign|sign|secretKey|accessKey|password|token)=([^,\s}]+)",
            r"(?i)('(?:idsSign|sign|secretKey|accessKey|password|token)':\s*)'[^']+'",
            r'(?i)("(?:idsSign|sign|secretKey|accessKey|password|token)":\s*)"[^"]+"',
        ]
        for pattern in patterns:
            result = re.sub(pattern, r"\1***", result)
        return result

    def critical(self, event: str, **kwargs: Any) -> None:
        """输出 critical 日志。

        入参：
        - event：日志事件名。
        - kwargs：结构化日志字段。
        出参：无。
        """
        self._logger.critical(event, **kwargs)


def get_logger(name: str) -> AppLogger:
    """获取业务统一日志对象。

    入参：
    - name：日志命名空间。
    出参：AppLogger 实例。
    """
    return AppLogger(name)
