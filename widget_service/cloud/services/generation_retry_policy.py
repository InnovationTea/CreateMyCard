"""开发 Trace 使用的重试配置白名单，不改变重试决策或业务响应。"""

from typing import Any


def retry_policy_details(settings: Any) -> dict[str, bool | int]:
    """记录当前请求加载的预算；实际执行次数由独立 Trace 计数提供。"""
    return {
        "interfaceRetryEnabled": settings.enable_compact_dsl_interface_retry,
        "interfaceExtraRetries": settings.compact_dsl_interface_retry_count,
        "qualityRepairEnabled": settings.enable_validation_failure_retry,
        "qualityRepairMaxAttempts": settings.validation_failure_max_repair_attempts,
        "modelFailureRetryEnabled": settings.enable_model_failure_retry,
        "modelFailureExtraRetries": settings.model_failure_max_retry_attempts,
        "fallbackModelFailureExtraRetries": settings.fallback_model_failure_max_retry_attempts,
        "fallbackEnabled": settings.enable_openai_fallback,
        "argumentRepairEnabled": settings.enable_compact_dsl_argument_repair_fallback,
        "argumentRepairMaxAttempts": settings.compact_dsl_argument_repair_max_attempts,
        "argumentRepairReminderCount": settings.compact_dsl_argument_repair_reminder_count,
    }
