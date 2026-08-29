#!/usr/bin/env python3
"""生成 Provider Template 端侧画廊 A2UI 数据集。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_CLOUD_ROOT = Path(__file__).resolve().parents[3]
if str(_CLOUD_ROOT) not in sys.path:
    sys.path.insert(0, str(_CLOUD_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path, help="输出 manifest.json 和 TNNN.json 的目录")
    return parser.parse_args()


def main() -> int:
    from services.template_generation.engine.cardplan.preview_dataset import (
        write_template_preview_dataset,
    )

    args = parse_args()
    output_dir = args.output_dir.resolve()
    manifest = write_template_preview_dataset(output_dir)
    layout_counts = manifest["countsByLayout"]
    size_counts = manifest["countsBySize"]
    print(
        f"模板画廊数据生成完成：共 {manifest['templateCount']} 个，"
        f"2x2={size_counts['2x2']}，2x4={size_counts['2x4']}，"
        f"布局={layout_counts}，输出={output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
