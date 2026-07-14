# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import re

from app.logger import logger
from config.config import get_settings

A2UI_FORM_PROTOCOL_PROFILE_ID = "a2ui-form-rom7-v1"
COMPACT_DSL_PROTOCOL_PROFILE_ID = "compact-dsl-v1"


class A2UIProtocolRegistry:
    def __init__(self, profile_id: str | None = None) -> None:
        """初始化 A2UI 协议注册表。

        入参：
        - profile_id：协议 profile 文件夹名；不传时使用默认配置。
        出参：无。
        """
        self.settings = get_settings()
        self.profile_id = profile_id or self.settings.protocol_profile_id

    def get_profile(self) -> dict:
        """读取 A2UI 协议 profile。

        入参：无。
        出参：协议 profile 字典，包含协议版本、catalogId、尺寸、白名单和原始 md 文档。
        """
        profile_dir = self.settings.data_root / "protocol_profiles" / self.profile_id
        if not profile_dir.exists():
            raise ValueError(f"Protocol profile not found: {self.profile_id}")
        logger.info(f"protocol_profile_loading profile_id={self.profile_id}")
        protocol_md = self._read_markdown(profile_dir, "protocol.md")
        component_catalog_md = self._read_markdown(profile_dir, "component-catalog.md")
        data_binding_md = self._read_markdown(profile_dir, "data-binding.md")
        profile = {
            "id": self.profile_id,
            "version": self._extract_quoted_value(protocol_md, "version", "v0.9"),
            "format": self._extract_quoted_value(protocol_md, "format", "a2ui-form"),
            "catalogId": self._extract_quoted_value(
                protocol_md,
                "catalogId",
                "ohos.a2ui.extended.catalog",
            ),
            "minRomVersion": "7.0.0",
            "sizes": {
                "2x2": {"width": 140, "height": 140},
                "2x4": {"width": 300, "height": 140},
            },
            "componentWhitelist": self._extract_component_whitelist(component_catalog_md),
            "styleWhitelist": [
                "width",
                "height",
                "padding",
                "borderRadius",
                "clip",
                "background",
                "backgroundColor",
                "fontSize",
                "fontWeight",
                "objectFit",
            ],
            "fontSizeSteps": [10, 12, 14, 16, 18, 20, 32, 40],
            "spacingSteps": [2, 4, 6, 8, 10, 12, 14, 16],
            "documents": {
                "protocol.md": protocol_md,
                "component-catalog.md": component_catalog_md,
                "data-binding.md": data_binding_md,
            },
        }
        logger.info(
            f"protocol_profile_loaded profile_id={self.profile_id} "
            f"version={profile['version']} "
            f"component_count={len(profile['componentWhitelist'])}"
        )
        return profile

    def _read_markdown(self, profile_dir, filename: str) -> str:
        """读取协议版本目录下的 md 原文。

        入参：
        - profile_dir：协议版本目录。
        - filename：md 文件名。
        出参：md 原文字符串。
        """
        path = profile_dir / filename
        if not path.exists():
            raise ValueError(f"Protocol markdown not found: {path}")
        return path.read_text(encoding="utf-8")

    def _extract_quoted_value(self, markdown: str, key: str, default: str) -> str:
        """从 md 原文中提取固定字段的反引号值。

        入参：
        - markdown：协议 md 原文。
        - key：字段名，例如 version 或 catalogId。
        - default：提取不到时使用的默认值。
        出参：字段值。
        """
        match = re.search(rf"`{re.escape(key)}`[^\"“”]*[\"“]([^\"”]+)[\"”]", markdown)
        return match.group(1) if match else default

    def _extract_component_whitelist(self, component_catalog_md: str) -> list[str]:
        """从组件目录 md 中提取允许组件白名单。

        入参：
        - component_catalog_md：component-catalog.md 原文。
        出参：组件名称列表。
        """
        match = re.search(r"允许组件：(.+)", component_catalog_md)
        if not match:
            return [
                "Text",
                "Image",
                "Divider",
                "Progress",
                "Button",
                "Checkbox",
                "Row",
                "Column",
                "List",
                "Stack",
            ]
        return re.findall(r"`([^`]+)`", match.group(1))
