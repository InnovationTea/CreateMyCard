"""Template-generation feature gates derived from the current TaskSpec."""

from __future__ import annotations

from typing import Any

from packaging.version import InvalidVersion, Version

from config.config import get_settings

FUSION_BALL_MIN_PRD_VERSION_CONFIG = "fusion_ball_min_prd_version"


def fusion_ball_enabled(app_version: Any) -> bool:
    """Return whether template fusion-ball themes are enabled for this version."""
    minimum_version = get_settings().CONFIG.get(FUSION_BALL_MIN_PRD_VERSION_CONFIG)
    if not isinstance(app_version, str) or not isinstance(minimum_version, str):
        return False
    if not app_version or not minimum_version:
        return False
    try:
        current = Version(app_version)
        minimum = Version(minimum_version)
    except InvalidVersion:
        return False
    return current >= minimum
