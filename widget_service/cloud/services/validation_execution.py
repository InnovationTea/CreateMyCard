# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""编排日志及 Artifact 校验身份，用于区分正式校验、修复重试和主题回退。"""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class ValidationExecutionContext:
    """由生成编排层创建并传入校验器的只读执行身份。"""

    operation: str = "standalone"
    generation_mode: str = "standalone"
    phase: str = "standalone"
    attempt: int = 1
    purpose: str = "standalone"
    candidate_index: int | None = None

    @classmethod
    def for_request(
        cls,
        *,
        operation: str,
        generation_mode: str,
    ) -> ValidationExecutionContext:
        """创建请求级身份；具体校验必须继续派生阶段和用途。"""

        return cls(
            operation=operation,
            generation_mode=generation_mode,
            purpose="request",
        )

    def for_phase(
        self,
        phase: str,
        *,
        attempt: int,
    ) -> ValidationExecutionContext:
        """保留请求身份，派生阶段自己的尝试次数。"""

        return replace(self, phase=phase, attempt=attempt)

    def with_purpose(
        self,
        purpose: str,
        *,
        candidate_index: int | None = None,
    ) -> ValidationExecutionContext:
        """保留请求和重试身份，为子校验标记具体用途。"""

        return replace(
            self,
            purpose=purpose,
            candidate_index=candidate_index,
        )

    def log_fields(self) -> str:
        """兼容现有调用；标准字段格式由观测辅助模块统一维护。"""

        from services.validation_observability import format_validation_execution_fields

        return format_validation_execution_fields(self)
