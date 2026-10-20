"""开发 Trace 使用的重试配置白名单，不改变重试决策或业务响应。"""

from typing import Any


def retry_policy_details(settings: Any) -> dict[str, bool | int]:
    """记录当前请求加载的预算；实际执行次数由独立 Trace 计数提供。"""
    return {
        "interfaceRetryEnabled": settings.enable_compact_dsl_interface_retry,
        "interfaceExtraRetries": settings.compact_dsl_interface_retry_count,
        "qualityRepairEnabled": settings.enable_validation_failure_retry,
        "qualityRepairMaxAttempts": settings.validation_failure_max_repair_attempts,
        "singleStepGenerationFallbackEnabled": settings.enable_single_step_generation_fallback,
        "singleStepWidgetEditEnabled": settings.enable_single_step_widget_edit,
        "dropPlanFactValidationEnabled": settings.enable_drop_plan_fact_validation,
        "photoBackgroundThemeEnabled": settings.enable_photo_background_theme,
        "subjectlessWideThemeEnabled": settings.enable_subjectless_wide_theme,
        "squareMusicPhotoExpansionEnabled": settings.enable_square_music_photo_expansion,
        "squarePhotoExpansionEnabled": settings.enable_square_photo_expansion,
        "deepseekOfficialHttpUseSdkEnabled": settings.deepseek_official_http_use_sdk,
        "modelFailureRetryEnabled": settings.enable_model_failure_retry,
        "modelFailureExtraRetries": settings.model_failure_max_retry_attempts,
        "fallbackModelFailureExtraRetries": settings.fallback_model_failure_max_retry_attempts,
        "fallbackEnabled": settings.enable_openai_fallback,
        "argumentRepairEnabled": settings.enable_compact_dsl_argument_repair_fallback,
        "argumentRepairMaxAttempts": settings.compact_dsl_argument_repair_max_attempts,
        "argumentRepairReminderCount": settings.compact_dsl_argument_repair_reminder_count,
    }
