from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from ..base import BaseValidator
from .common import add, component_pointer, iter_components


class AssetQualityValidator(BaseValidator):
    stage = "quality"
    name = "asset_quality"

    def validate(self, context: Any, rules: Any, reporter: Any) -> None:
        allowed_hosts = getattr(rules, "asset_allowed_hosts", set()) if rules is not None else set()
        for index, component in iter_components(context):
            candidates = []
            if component.get("component") == "Image":
                candidates.append(("src", component.get("src")))
            styles = component.get("styles")
            if isinstance(styles, dict) and "backgroundImage" in styles:
                candidates.append(("styles/backgroundImage", styles.get("backgroundImage")))
            for field, src in candidates:
                if not self._is_forbidden_source(src, allowed_hosts):
                    continue
                add(
                    reporter,
                    "ASSET.REMOTE_SRC",
                    component_pointer(index, field),
                    "图片素材不得使用远程地址或内嵌 data URI。",
                    src,
                    "本地受控素材路径",
                )

    @staticmethod
    def _is_forbidden_source(value: Any, allowed_hosts: set[str]) -> bool:
        if not isinstance(value, str):
            return False
        source = value.strip()
        lowered = source.lower()
        if lowered.startswith(("{{", "${")):
            return False
        if lowered.startswith(("data:image", "data:;base64")):
            return True
        if not lowered.startswith(("http://", "https://")):
            return False
        host = urlparse(source).hostname
        normalized_hosts = {
            item.strip().lower() for item in allowed_hosts if isinstance(item, str) and item.strip()
        }
        return host not in normalized_hosts
