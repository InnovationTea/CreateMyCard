from collections.abc import Callable


class RetryController:
    def run(
        self, operation: Callable[[], str], validate: Callable[[str], list[str]]
    ) -> tuple[str, int, list[str]]:
        retry_count = 0
        result = operation()
        errors = validate(result)
        if not errors:
            return result, retry_count, errors

        retry_count = 1
        result = operation()
        errors = validate(result)
        return result, retry_count, errors
