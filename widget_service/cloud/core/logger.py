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


def get_logger(name: str) -> AppLogger:
    """获取业务统一日志对象。

    入参：
    - name：日志命名空间。
    出参：AppLogger 实例。
    """
    return AppLogger(name)
