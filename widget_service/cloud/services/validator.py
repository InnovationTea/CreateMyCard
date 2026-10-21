# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from typing import Any

from app.logger import logger
from config.config import get_settings
from models.artifact import WidgetArtifact
from services.card_validation import ValidationOptions, validate_card
from services.card_validation.diagnostics import Diagnostic
from services.card_validation.theme_phase_validator import theme_phase_errors
from services.theme_style_roles import in_layout_phase
from services.validation_execution import ValidationExecutionContext
from services.validation_observability import ValidationObserver

_MODULE = "[Validator]"


class ArtifactValidator:
    """保存最近一次校验的辅助结果；仅支持顺序调用，不支持同一实例并发校验。"""

    def validate_layout(
        self,
        artifact: WidgetArtifact,
        protocol_profile: dict,
        *,
        execution_context: ValidationExecutionContext | None = None,
    ) -> list[str]:
        """内部定稿门禁：保留结构、能力和语义检查，不提前解析色值。"""
        from services.theme_style_roles import layout_phase

        with layout_phase():
            return self.validate(artifact, protocol_profile, execution_context=execution_context)

    def __init__(
        self,
        asset_src_url_mapping: dict[str, str] | None = None,
    ) -> None:
        self.error_categories: list[str] = []
        self.error_prompt_contexts: list[dict[str, Any]] = []
        mapping = (
            get_settings().asset_src_url_mapping
            if asset_src_url_mapping is None else asset_src_url_mapping
        )
        self.asset_src_url_mapping = dict(mapping)

    def validate(
        self,
        artifact: WidgetArtifact,
        protocol_profile: dict,
        *,
        execution_context: ValidationExecutionContext | None = None,
    ) -> list[str]:
        """校验完整 artifact。

        入参：
        - artifact：待校验的完整卡片产物。
        - protocol_profile：当前 A2UI 协议 profile。
        出参：错误信息列表；空列表表示校验通过。
        """
        # 校验入口接收完整 artifact；标准 A2UI 通过服务内 Python API 调用最新校验流水线。
        validator_name = "services.card_validation.validate_card"
        identity = execution_context or ValidationExecutionContext()
        observer = ValidationObserver(
            logger,
            component=_MODULE,
            event_prefix="artifact_validation",
            execution_context=identity,
        )
        observer.started(
            protocol_profile_id=protocol_profile["id"],
            validator_module=validator_name,
        )
        self.error_categories = []
        self.error_prompt_contexts = []
        phase_errors = theme_phase_errors(artifact.genui, layout=in_layout_phase())
        if phase_errors:
            self.error_categories = ["THEME_PHASE"]
            observer.failed(
                level="warning",
                error_count=len(phase_errors),
                category="THEME_PHASE",
            )
            return phase_errors
        try:
            settings = get_settings()
            reporter = validate_card(
                artifact=artifact.model_dump(mode="json", exclude_none=True),
                options=ValidationOptions(
                    asset_src_url_mapping=self.asset_src_url_mapping,
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
            observer.failed(
                errors=errors,
                validator_module=validator_name,
                exception=exc,
            )
            return errors

        if errors:
            observer.failed(errors=errors, warnings=warnings)
        else:
            observer.completed(warning_count=len(warnings), warnings=warnings)
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
        """保留确定性诊断细节，避免修复模型再次猜测具体规则。"""
        context: dict[str, Any] = {
            "stage": "validation",
            "category": "ARTIFACT_VALIDATION_FAILED",
            "code": item.code,
            "validatorStage": item.stage,
            "fileKind": item.file_kind,
            "message": item.message,
        }
        optional_values = {
            "line": item.line,
            "jsonPointer": item.json_pointer,
            "actual": item.actual,
            "expected": item.expected,
            "fixHint": item.fix_hint,
        }
        for key, value in optional_values.items():
            if value not in (None, "", []):
                context[key] = value
        return context
