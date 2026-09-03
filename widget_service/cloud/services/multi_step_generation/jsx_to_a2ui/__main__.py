import sys
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from jsx_to_a2ui.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
