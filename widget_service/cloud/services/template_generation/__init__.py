"""模板源 DSL 生成接口。"""

from .facade import request_template_source_dsl
from .source_generator import TemplateSourceGenerator

__all__ = [
    "TemplateSourceGenerator",
    "request_template_source_dsl",
]
