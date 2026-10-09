"""端到端调试工作台后端包。"""

from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[3]
CLOUD_ROOT = PACKAGE_ROOT / "cloud"
if str(CLOUD_ROOT) not in sys.path:
    sys.path.insert(0, str(CLOUD_ROOT))

__all__ = ["CLOUD_ROOT", "PACKAGE_ROOT"]
