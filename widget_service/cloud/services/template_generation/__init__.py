"""模板源 DSL 生成接口。"""

from .engine.fusion_ball_a2ui_converter import (
    FusionBallA2UIConversionError,
    convert_a2ui_with_fusion_ball,
)
from .facade import request_template_source_dsl
from .source_generator import TemplateSourceGenerator

__all__ = [
    "FusionBallA2UIConversionError",
    "TemplateSourceGenerator",
    "convert_a2ui_with_fusion_ball",
    "request_template_source_dsl",
]
