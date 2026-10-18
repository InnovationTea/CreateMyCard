# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Minimal hard-stage readability and asset-policy baselines."""

from __future__ import annotations

from typing import Any

from .base import BaseValidator, numeric

_EMOJI_RANGES = ((0x1F000, 0x1FAFF), (0x2600, 0x27BF))
_FONT_COMPONENTS = {"Text", "Button"}


def _is_emoji(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return any(start <= ord(char) <= end for char in value for start, end in _EMOJI_RANGES)


class AestheticBaselineValidator(BaseValidator):
    """Check only hard baselines that are independent of design contracts."""

    stage = "hard"
    name = "aesthetic_baseline"

    def validate(self, context: Any, rules: Any, reporter: Any) -> None:
        del rules
        for index, component in enumerate(context.components):
            component_pointer = f"/updateComponents/components/{index}"
            content = component.get("content")
            if _is_emoji(content):
                reporter.add(
                    "error",
                    "ASSET.EMOJI_ICON",
                    self.stage,
                    "genui",
                    line=2,
                    json_pointer=f"{component_pointer}/content",
                    actual=content,
                    expected="Registered local SVG icon",
                    message="不应使用 emoji 作为视觉图标。",
                    fix_hint="将 emoji 替换为已注册的本地图标素材。",
                    source="aesthetic-baseline",
                )

            if component.get("component") not in _FONT_COMPONENTS:
                continue
            styles = component.get("styles")
            if not isinstance(styles, dict):
                continue
            font_size = numeric(styles.get("fontSize"))
            if font_size is None or font_size >= 8:
                continue
            reporter.add(
                "error",
                "TYPE.FONT_SIZE_MIN",
                self.stage,
                "genui",
                line=2,
                json_pointer=f"{component_pointer}/styles/fontSize",
                actual=font_size,
                expected=">= 8vp",
                message="字号不得低于 8vp。",
                fix_hint="将字号调整为不低于 8vp 的可读字号。",
                source="aesthetic-baseline",
            )
