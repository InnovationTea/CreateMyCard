"""模板生成接口及旧 Python 诊断入口。"""

from .facade import generate_template_artifact
from .legacy_python import route_legacy_python_terse_generation

__all__ = [
    "generate_template_artifact",
    "route_legacy_python_terse_generation",
]
