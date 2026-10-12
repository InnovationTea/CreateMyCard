"""Repository paths shared by the standalone debug tools package."""

from __future__ import annotations

from pathlib import Path

DEBUG_TOOLS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = DEBUG_TOOLS_ROOT.parent
WIDGET_SERVICE_ROOT = REPOSITORY_ROOT / "widget_service"
CLOUD_ROOT = WIDGET_SERVICE_ROOT / "cloud"


def ensure_cloud_import_path() -> None:
    """Expose the cloud source tree for its existing top-level imports."""

    import sys

    cloud_root = str(CLOUD_ROOT)
    if cloud_root not in sys.path:
        sys.path.insert(0, cloud_root)
