"""Repository paths shared by the standalone debug tools package."""

from __future__ import annotations

import os
from pathlib import Path

# Debug Tools 始终是本地开发入口。在任何调试应用导入云侧模块前设置默认值，
# 确保正式 Compact 转换器不会把日志写到云环境的 /opt/huawei。
os.environ.setdefault("WIDGET_SERVICE_LOCAL_FLAG", "true")

DEBUG_TOOLS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = DEBUG_TOOLS_ROOT.parent
WIDGET_SERVICE_ROOT = REPOSITORY_ROOT / "widget_service"
CLOUD_ROOT = WIDGET_SERVICE_ROOT / "cloud"
# 浏览器直接读取真机工程的图片，不维护第二份媒体副本。
RENDER_RESOURCE_ROOT = DEBUG_TOOLS_ROOT / "a2ui_render/entry/src/main/resources"
RENDER_ASSET_ROOT = DEBUG_TOOLS_ROOT / "card_renderer/assets"


def ensure_cloud_import_path() -> None:
    """Expose the cloud source tree for its existing top-level imports."""

    import sys

    cloud_root = str(CLOUD_ROOT)
    if cloud_root not in sys.path:
        sys.path.insert(0, cloud_root)
