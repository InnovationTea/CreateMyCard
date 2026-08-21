"""模板 A2UI 生成接口及旧 Python 诊断入口。"""

from .facade import request_template_a2ui
from .legacy_python import route_legacy_python_terse_generation

__all__ = [
    "request_template_a2ui",
    "route_legacy_python_terse_generation",
]
