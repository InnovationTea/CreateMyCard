#!/usr/bin/env python3
"""通过 Terse DSL Nested-2 接口批量生成 Provider 模板画廊 A2UI。"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

_WIDGET_SERVICE_ROOT = Path(__file__).resolve().parents[1]
_CLOUD_ROOT = _WIDGET_SERVICE_ROOT / "cloud"
if str(_CLOUD_ROOT) not in sys.path:
    sys.path.insert(0, str(_CLOUD_ROOT))

_DEFAULT_INPUT_ROOT = (
    _WIDGET_SERVICE_ROOT
    / "cloud"
    / "services"
    / "template_generation"
    / "test"
    / "provider_gallery_inputs"
)
_DEFAULT_OUTPUT_ROOT = (
    _WIDGET_SERVICE_ROOT
    / "cloud"
    / "services"
    / "template_generation"
    / "test"
    / "provider_gallery_output"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=_DEFAULT_INPUT_ROOT)
    parser.add_argument("--output-root", type=Path, default=_DEFAULT_OUTPUT_ROOT)
    parser.add_argument(
        "--provider",
        action="append",
        default=[],
        help="只生成指定 Provider ID，可重复传入",
    )
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument(
        "--refresh-inputs",
        action="store_true",
        help="先按当前 Provider 配置重建模拟输入",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="不调用模型，只生成端侧可识别的待生成/缺失结果清单",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="存在生成失败时返回非零退出码；模板缺失不计为生成失败",
    )
    parser.add_argument(
        "--disable-fusion-ball",
        action="store_true",
        help="通过请求级开关关闭融球 Theme，不向模型或服务端模板链暴露融球能力",
    )
    return parser.parse_args()


async def run(args: argparse.Namespace) -> int:
    input_root = args.input_root.resolve()
    output_root = args.output_root.resolve()
    original_working_directory = Path.cwd()
    os.chdir(_WIDGET_SERVICE_ROOT)
    try:
        from services.template_generation.test_support.provider_gallery import (
            generate_provider_gallery,
            write_gallery_input_dataset,
        )

        if args.refresh_inputs or not (input_root / "manifest.json").is_file():
            manifest = write_gallery_input_dataset(input_root)
            case_count = sum(len(provider.cases) for provider in manifest.providers)
            print(
                f"画廊模拟输入已生成：Provider={len(manifest.providers)}，"
                f"用例={case_count}"
            )
        provider_ids = set(args.provider) or None
        summary = await generate_provider_gallery(
            input_root,
            output_root,
            concurrency=args.concurrency,
            provider_ids=provider_ids,
            dry_run=args.dry_run,
            enable_fusion_ball=not args.disable_fusion_ball,
        )
        print(
            "Provider 画廊批跑完成："
            f"total={summary.total} success={summary.success} "
            f"failed={summary.failed} missing={summary.missing} "
            f"not_generated={summary.not_generated} output={summary.manifest_path}"
        )
        if args.strict and summary.failed > 0:
            return 1
        return 0
    finally:
        os.chdir(original_working_directory)


def main() -> int:
    return asyncio.run(run(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
