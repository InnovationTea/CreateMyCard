"""模板源 DSL 生成接口及旧 Python 诊断入口。"""

from .engine.fusion_ball_a2ui_converter import (
    FusionBallA2UIConversionError,
    convert_a2ui_with_fusion_ball,
)
from .facade import request_template_source_dsl
from .legacy_python import route_legacy_python_terse_generation

__all__ = [
    "FusionBallA2UIConversionError",
    "convert_a2ui_with_fusion_ball",
    "request_template_source_dsl",
    "route_legacy_python_terse_generation",
]
