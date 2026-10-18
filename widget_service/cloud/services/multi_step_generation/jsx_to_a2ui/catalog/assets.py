from __future__ import annotations

import re

from ..exceptions import ValidationError

ASSET_ROOT = "resources/base/media/"


def asset_url(value: str | None) -> str:
    if not value:
        return ""
    source = str(value)
    if re.match(r"^https?://", source, re.I):
        return source
    if re.match(r"^data:", source, re.I):
        raise ValidationError(f"A2UI Form images do not accept inline data URLs: {source!r}")
    if source.startswith(("/", ".")) or "/" in source or "\\" in source:
        return source.replace("\\", "/")
    return f"{ASSET_ROOT}{source if '.' in source else source + '.svg'}"
