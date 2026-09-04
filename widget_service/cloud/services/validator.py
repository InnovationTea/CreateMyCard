# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import traceback
from typing import Any

from app.logger import json_for_log, logger
from config.config import get_settings
from models.artifact import WidgetArtifact
from services.card_validation import ValidationOptions, validate_card
from services.card_validation.diagnostics import Diagnostic

_MODULE = "[Validator]"


class ArtifactValidator:
    def __init__(self) -> None:
        self.error_categories: list[str] = []
        self.error_prompt_contexts: list[dict[str, Any]] = []

    def validate(
        self,
        artifact: WidgetArtifact,
        protocol_profile: dict,
    ) -> list[str]:
        """校验完整 artifact。

        入参：
        - artifact：待校验的完整卡片产物。
        - protocol_profile：当前 A2UI 协议 profile。
        出参：错误信息列表；空列表表示校验通过。
        """
        # 校验入口接收完整 artifact；标准 A2UI 通过服务内 Python API 调用最新校验流水线。
        validator_name = "services.card_validation.validate_card"
        logger.info(
            f"{_MODULE} artifact_validation_started protocol_profile_id={protocol_profile['id']} "
            f"validator_module={validator_name}"
        )
        self.error_categories = []
        self.error_prompt_contexts = []
        try:
            settings = get_settings()
            reporter = validate_card(
                artifact=artifact.model_dump(mode="json", exclude_none=True),
                options=ValidationOptions(
                    capabilities_dir=(
                        settings.data_root
                        / "capabilities"
                        / artifact.meta.capabilityRegistryVersion
                    ),
                ),
            )
            errors, self.error_prompt_contexts = self._normalize_diagnostics(
                reporter.diagnostics,
                "error",
            )
            warnings, _ = self._normalize_diagnostics(
                reporter.diagnostics,
                "warning",
            )
        except Exception as exc:
            # 校验模块异常转成错误列表，供生成服务记录，并按配置决定是否重试。
            errors = [f"validator execution failed: {exc}"]
            self.error_categories = ["VALIDATOR"]
            logger.error(
                f"{_MODULE} artifact_validation_failed errors={json_for_log(errors)} "
                f"validator_module={validator_name} "
                f"exception_type={type(exc).__name__} exception={exc!r} "
                f"traceback={traceback.format_exc()}"
            )
            return errors

        if errors:
            logger.error(
                f"{_MODULE} artifact_validation_failed errors={json_for_log(errors)} "
                f"warnings={json_for_log(warnings)}"
            )
        else:
            logger.info(
                f"{_MODULE} artifact_validation_completed warning_count={len(warnings)} "
                f"warnings={json_for_log(warnings)}"
            )
        return errors

    def _normalize_diagnostics(
        self,
        diagnostics: list[Diagnostic],
        severity: str,
    ) -> tuple[list[str], list[dict[str, Any]]]:
        """同时生成稳定日志字符串和供修复模型使用的结构化上下文。"""
        messages: list[str] = []
        prompt_contexts: list[dict[str, Any]] = []
        for item in diagnostics:
            if item.severity != severity:
                continue
            location = item.file_kind
            if item.line is not None:
                location += f":{item.line}"
            if item.json_pointer:
                location += f" {item.json_pointer}"
            messages.append(f"{item.code}: {item.message} [{location}]")
            prompt_contexts.append(self._diagnostic_prompt_context(item))
        return messages, prompt_contexts

    @staticmethod
    def _diagnostic_prompt_context(item: Diagnostic) -> dict[str, Any]:
        """保留确定性诊断细节，供日志、回放和修复反馈转换使用。"""
        context: dict[str, Any] = {
            "stage": "validation",
            "category": "ARTIFACT_VALIDATION_FAILED",
            "code": item.code,
            "validatorStage": item.stage,
            "fileKind": item.file_kind,
            "line": item.line,
            "jsonPointer": item.json_pointer,
            "actual": item.actual,
            "expected": item.expected,
            "message": item.message,
            "fixHint": item.fix_hint,
        }
        return {key: value for key, value in context.items() if value not in (None, "", [])}
