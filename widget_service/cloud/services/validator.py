# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import traceback
from typing import Any

from app.logger import json_for_log, logger
from models.artifact import WidgetArtifact
from services.card_validator import validate_card
from services.compact_dsl_protocol import is_compact_dsl, validate_compact_dsl


class ArtifactValidator:
    def validate(
        self,
        artifact: WidgetArtifact,
        protocol_profile: dict,
        allowed_asset_sources: set[str] | None = None,
    ) -> list[str]:
        """校验完整 artifact。

        入参：
        - artifact：待校验的完整卡片产物。
        - protocol_profile：当前 A2UI 协议 profile。
        - allowed_asset_sources：本次生成请求实际可用的素材路径集合。
        出参：错误信息列表；空列表表示校验通过。
        """
        # 校验入口接收完整 artifact，具体协议、组件、布局和绑定规则由 card_validator 模块统一处理。
        validator_name = (
            "services.compact_dsl_protocol.validate_compact_dsl"
            if is_compact_dsl(protocol_profile)
            else "services.card_validator.validate_card"
        )
        logger.info(
            f"artifact_validation_started protocol_profile_id={protocol_profile['id']} "
            f"validator_module={validator_name}"
        )
        try:
            # 直接调用本地模块方法，避免运行时动态加载脚本文件导致部署路径和缓存行为不可控。
            if is_compact_dsl(protocol_profile):
                report = validate_compact_dsl(
                    genui_text=artifact.genui,
                    cardspec=artifact.cardSpec,
                    component_whitelist=protocol_profile.get("componentWhitelist"),
                )
            else:
                report = validate_card(
                    genui_text=artifact.genui,
                    cardspec=artifact.cardSpec,
                    allowed_asset_sources=allowed_asset_sources,
                )
        except Exception as exc:
            # 校验模块异常转成错误列表，供生成服务记录、重试并按非阻断策略继续。
            errors = [f"validator execution failed: {exc}"]
            logger.error(
                f"artifact_validation_failed errors={json_for_log(errors)} "
                f"validator_module={validator_name} "
                f"exception_type={type(exc).__name__} exception={exc!r} "
                f"traceback={traceback.format_exc()}"
            )
            return errors

        errors = self._normalize_messages(report.errors)
        warnings = self._normalize_messages(report.warnings)
        if errors:
            logger.error(
                f"artifact_validation_failed errors={json_for_log(errors)} "
                f"warnings={json_for_log(warnings)}"
            )
        else:
            logger.info(
                f"artifact_validation_completed warning_count={len(warnings)} "
                f"warnings={json_for_log(warnings)}"
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
