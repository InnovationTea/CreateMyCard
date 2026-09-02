"""Repository-local launcher that does not require installing the package."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from jsx_to_a2ui.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
