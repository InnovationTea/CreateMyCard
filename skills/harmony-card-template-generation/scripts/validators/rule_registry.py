from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class RuleRegistry:
    def __init__(self, skill_dir: Path) -> None:
        self.skill_dir = skill_dir
        self.rules_dir = skill_dir / "scripts" / "rules"
        self.config_dir = self.rules_dir / "config"
        self.schemas_dir = self.rules_dir / "schemas"
        self.form_catalog = self._load_json(self.rules_dir / "form_catalog.json", {})
        self.protocol = self._load_json(self.config_dir / "protocol.json", {})
        self.layout = self._load_json(self.config_dir / "layout.json", {})
        self.style = self._load_json(self.config_dir / "style.json", {})
        self.color = self._load_json(self.config_dir / "color.json", {})
        self.asset = self._load_json(self.config_dir / "asset.json", {})
        self.diagnostics = self._load_json(self.config_dir / "diagnostics.zh-CN.json", {})
        self.cardspec_schema = self._load_json(self.schemas_dir / "cardspec.schema.json", {})
        self.capabilities = self._load_capabilities()
        self.event_schema = self._load_json(self.schemas_dir / "event.click.schema.json", {})
        self.allowed_components = self._allowed_components()
        self.asset_allowlist = self._asset_allowlist()
        self.allowed_color_hex = self._allowed_color_hex()

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

    def _allowed_components(self) -> set[str]:
        components = self.form_catalog.get("components")
        if isinstance(components, dict) and components:
            return set(components.keys())
        return set(self.protocol.get("allowedComponents", []))

    def _asset_allowlist(self) -> set[str]:
        result = set(self.asset.get("allowlist", []))
        asset_doc = self.skill_dir / "references" / "design" / "asset-library.md"
        if asset_doc.exists():
            text = asset_doc.read_text(encoding="utf-8")
            result.update(re.findall(r"`(resources/base/media/[^`]+\.(?:svg|png))`", text, re.I))
        return result

    def _allowed_color_hex(self) -> set[str]:
        result: set[str] = set()
        for config_value in self.color.get("tokens", {}).values():
            if isinstance(config_value, str) and config_value.startswith("#"):
                result.add(config_value.lower())
        for item in self.color.get("sceneExtensions", []):
            if isinstance(item, dict):
                for value in item.get("hex", []):
                    if isinstance(value, str):
                        result.add(value.lower())
        for path in [
            self.skill_dir / "references" / "design" / "color-token-values.md",
            self.skill_dir / "references" / "design" / "color-token-system.md",
        ]:
            if path.exists():
                text = path.read_text(encoding="utf-8")
                result.update(color.lower() for color in re.findall(r"#[0-9a-fA-F]{6,8}", text))
        return result
