"""端到端调试工作台后端包。"""

from __future__ import annotations

from debug_tools.paths import CLOUD_ROOT, WIDGET_SERVICE_ROOT, ensure_cloud_import_path

PACKAGE_ROOT = WIDGET_SERVICE_ROOT
ensure_cloud_import_path()

__all__ = ["CLOUD_ROOT", "PACKAGE_ROOT"]
