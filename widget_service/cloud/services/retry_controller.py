# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from collections.abc import Callable

from models.service import RetryResult


class RetryController:
    def run(
        self,
        operation: Callable[[], str],
        validate: Callable[[str], list[str]],
        *,
        retry_on_validation_failure: bool = False,
        repair: Callable[[str, list[str]], str] | None = None,
    ) -> RetryResult:
        """执行首次生成和校验，并按开关决定是否定向修复一次。

        入参：
        - operation：无参生成函数，返回生成结果。
        - validate：校验函数，入参为生成结果，返回错误列表。
        - retry_on_validation_failure：error 存在时是否修复一次，默认关闭。
        - repair：接收非法 DSL 和首次错误列表的修复回调。
        出参：结构化结果，包含最终输出、首次及最终错误和修复次数。
        """
        result = operation()
        initial_errors = validate(result)
        should_repair = bool(initial_errors) and retry_on_validation_failure
        if not should_repair:
            return RetryResult(
                result=result,
                retryCount=0,
                errors=initial_errors,
                initialErrors=initial_errors,
            )

        if repair is None:
            raise ValueError("Repair callback is required when validation retry is enabled")
        result = repair(result, initial_errors)
        errors = validate(result)
        return RetryResult(
            result=result,
            retryCount=1,
            errors=errors,
            initialErrors=initial_errors,
            repairAttempted=True,
        )
