from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class RuleRegistry:
    """Loads all rule JSON under ``scripts/rules/``.

    The validator is closed against ``scripts/`` for static mode: rules,
    schemas, allowlists and diagnostics all live under
    ``scripts/rules/config/`` and ``scripts/rules/schemas/``. External data
    (dynamic ``effectiveCapabilities`` or ``capabilities_dir``) is only
    consumed through the ``validate_card`` call sites, never read from disk
    outside the scripts directory.
    """

    def __init__(self, skill_dir: Path) -> None:
        self.skill_dir = skill_dir
        self.rules_dir = skill_dir / "scripts" / "rules"
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
