"""端到端调试 Agent 的应用工厂。

进程启动统一由 :mod:`debug_tools.__main__` 管理；本模块只保留应用工厂兼容导入，
不再承担独立启动职责。
"""

from __future__ import annotations

from ..server import create_app

__all__ = ["create_app"]
