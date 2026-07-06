from typing import Any

from app.logger import logger
from models.artifact import WidgetArtifact
from services.card_validator import validate_card


class ArtifactValidator:
    def validate(self, artifact: WidgetArtifact, protocol_profile: dict) -> list[str]:
        """校验完整 artifact。

        入参：
        - artifact：待校验的完整卡片产物。
        - protocol_profile：当前 A2UI 协议 profile。
        出参：错误信息列表；空列表表示校验通过。
        """
        # 校验入口接收完整 artifact，具体协议、组件、布局和绑定规则由 card_validator 模块统一处理。
        logger.info(
            f"artifact_validation_started protocol_profile_id={protocol_profile['id']} "
            "validator_module=services.card_validator.validate_card"
        )
        try:
            # 直接调用本地模块方法，避免运行时动态加载脚本文件导致部署路径和缓存行为不可控。
            report = validate_card(
                genui_text=artifact.genui,
                cardspec=artifact.cardSpec,
            )
        except Exception as exc:
            # 校验模块异常属于服务侧校验链路异常，需要返回为校验失败，避免产物绕过校验。
            errors = [f"validator execution failed: {exc}"]
            logger.error_with_exception(
                f"artifact_validation_failed errors={errors} "
                "validator_module=services.card_validator.validate_card",
                exc,
            )
            return errors

        errors = self._normalize_messages(report.errors)
        warnings = self._normalize_messages(report.warnings)
        if errors:
            logger.error(
                f"artifact_validation_failed errors={errors} warnings={warnings}"
            )
        else:
            logger.info(
                f"artifact_validation_completed warning_count={len(warnings)} "
                f"warnings={warnings}"
            )
        return errors

    def _normalize_messages(self, messages: list[Any]) -> list[str]:
        """归一化校验模块返回的问题列表。

        入参：
        - messages：校验结果中的 errors 或 warnings。
        出参：字符串列表，便于日志和响应统一处理。
        """
        # 当前校验模块返回字符串；保留兜底转换，方便后续扩展结构化问题对象时服务不中断。
        return [str(message) for message in messages]
