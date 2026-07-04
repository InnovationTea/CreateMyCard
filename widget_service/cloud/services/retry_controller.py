from collections.abc import Callable


class RetryController:
    def run(
        self, operation: Callable[[], str], validate: Callable[[str], list[str]]
    ) -> tuple[str, int, list[str]]:
        """执行生成操作并在校验失败时最多重试一次。

        入参：
        - operation：无参生成函数，返回生成结果。
        - validate：校验函数，入参为生成结果，返回错误列表。
        出参：最终生成结果、重试次数、最终校验错误列表。
        """
        # 按 AGENTS.md 要求，生成结果校验失败后最多重试一次。
        retry_count = 0
        result = operation()
        errors = validate(result)
        if not errors:
            return result, retry_count, errors

        retry_count = 1
        result = operation()
        errors = validate(result)
        return result, retry_count, errors
