"""模板路由的有效绑定边界。"""

from __future__ import annotations

from models.generation import CandidateDataBinding


def enrich_template_bindings(
    bindings: list[CandidateDataBinding],
) -> list[CandidateDataBinding]:
    """保留调用方已裁决字段；模板缺字段时自然不匹配。"""
    return [binding.model_copy() for binding in bindings]
