"""迁移后的 Main Agent 调试实现。"""

import sys
from pathlib import Path


def _ensure_cloud_import_path() -> None:
    for candidate in Path(__file__).resolve().parents:
        cloud_root = candidate / "cloud"
        if (cloud_root / "models").is_dir():
            cloud_root_text = str(cloud_root)
            if cloud_root_text not in sys.path:
                sys.path.insert(0, cloud_root_text)
            return


_ensure_cloud_import_path()
