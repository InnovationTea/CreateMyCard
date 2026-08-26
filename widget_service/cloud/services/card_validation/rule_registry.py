# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class RuleRegistry:
    """加载微服务内置的 validator rule JSON。

    静态规则、schema、allowlist 和 diagnostics 均从 ``cloud/data/validator_rules``
    读取；动态 ``effectiveCapabilities`` 和能力目录只通过 ``validate_card`` API
    显式传入，不依赖 Skill 或命令行脚本目录。
    """

    def __init__(self, rules_dir: Path) -> None:
        self.rules_dir = rules_dir
        self.config_dir = self.rules_dir / "config"
        self.schemas_dir = self.rules_dir / "schemas"
        self.protocol = self._load_json(self.config_dir / "protocol.json", {})
        self.layout = self._load_json(self.config_dir / "layout.json", {})
        self.style = self._load_json(self.config_dir / "style.json", {})
        self.asset = self._load_json(self.config_dir / "asset.json", {})
        self.expression = self._load_json(self.config_dir / "expression.json", {})
        self.diagnostics = self._load_json(self.config_dir / "diagnostics.zh-CN.json", {})
        self.capabilities = self._load_capabilities()
        self.event_schema = self._load_json(self.schemas_dir / "event.click.schema.json", {})
        self.allowed_components = set(self.protocol.get("allowedComponents", []))
        self.asset_allowlist = set(self.asset.get("allowlist", []))

    def _load_json(self, path: Path, fallback: Any) -> Any:
        if not path.exists():
            return fallback
        return json.loads(path.read_text(encoding="utf-8"))

    def _load_capabilities(self) -> dict[str, Any]:
        capabilities: dict[str, Any] = {}
        for path in sorted(self.schemas_dir.glob("capability.*.schema.json")):
            data = self._load_json(path, {})
            capability_id = data.get("capabilityId")
            if capability_id:
                data["_source"] = str(path)
                capabilities[capability_id] = data
        return capabilities
