# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""由调用入口提供的 Compact DSL 来源，不从 DSL 内容推断解析权限。"""

from dataclasses import dataclass
from enum import StrEnum


class CompactDslSource(StrEnum):
    """区分模型输出和模板编译产物。"""

    MODEL = "model"
    TEMPLATE = "template"


@dataclass(frozen=True)
class CompactDslParseContext:
    """在解析、修复、校验和转换之间共享的不可变来源上下文。"""

    source: CompactDslSource = CompactDslSource.MODEL

    @property
    def is_template(self) -> bool:
        """仅模板来源允许编译器使用的基础组件。"""
        return self.source is CompactDslSource.TEMPLATE


MODEL_PARSE_CONTEXT = CompactDslParseContext()
TEMPLATE_PARSE_CONTEXT = CompactDslParseContext(source=CompactDslSource.TEMPLATE)
