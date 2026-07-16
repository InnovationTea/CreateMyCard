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
    ) -> RetryResult:
        """执行生成操作，并按开关决定校验失败后是否重试一次。

        入参：
        - operation：无参生成函数，返回生成结果。
        - validate：校验函数，入参为生成结果，返回错误列表。
        - retry_on_validation_failure：校验失败时是否重新生成一次，默认关闭。
        出参：结构化重试结果，包含最终生成结果、重试次数和最终校验错误列表。
        """
        retry_count = 0
        result = operation()
        errors = validate(result)
        if not errors or not retry_on_validation_failure:
            return RetryResult(result=result, retryCount=retry_count, errors=errors)

        retry_count = 1
        result = operation()
        errors = validate(result)
        return RetryResult(result=result, retryCount=retry_count, errors=errors)
