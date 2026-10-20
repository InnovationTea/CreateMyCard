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
        """返回供标准日志复用的稳定键值字段。"""

        fields = (
            f"operation={self.operation} "
            f"generation_mode={self.generation_mode} "
            f"phase={self.phase} "
            f"attempt={self.attempt} "
            f"purpose={self.purpose}"
        )
        if self.candidate_index is not None:
            fields += f" candidate_index={self.candidate_index}"
        return fields
