"""模板路由及旧 Python 诊断入口。"""

from .facade import route_compact_generation, route_terse_nested2_generation
from .legacy_python import route_legacy_python_terse_generation

__all__ = [
    "route_compact_generation",
    "route_legacy_python_terse_generation",
    "route_terse_nested2_generation",
]
