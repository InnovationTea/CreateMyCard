#!/usr/bin/env python3
"""通过 Terse DSL Nested-2 接口批量生成 Provider 模板画廊 A2UI。"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

_TEMPLATE_ROOT = Path(__file__).resolve().parents[1]
_CLOUD_ROOT = Path(__file__).resolve().parents[3]
_WIDGET_SERVICE_ROOT = Path(__file__).resolve().parents[4]
if str(_CLOUD_ROOT) not in sys.path:
    sys.path.insert(0, str(_CLOUD_ROOT))

_DEFAULT_INPUT_ROOT = _TEMPLATE_ROOT / "test" / "provider_gallery_inputs"
_DEFAULT_OUTPUT_ROOT = _TEMPLATE_ROOT / "test" / "provider_gallery_output"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=_DEFAULT_INPUT_ROOT)
    parser.add_argument("--output-root", type=Path, default=_DEFAULT_OUTPUT_ROOT)
    parser.add_argument(
        "--env-file", type=Path,
        help="显式读取本地模型配置，兼容 WIDGET_SERVICE_ 前缀；不修改生产配置",
    )
    parser.add_argument(
        "--provider",
        action="append",
        default=[],
        help="只生成指定 Provider ID，可重复传入",
    )
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument(
        "--size", action="append", choices=("2x2", "2x4"),
        help="选择尺寸，可重复；默认同时生成 2x2 与 2x4",
    )
    parser.add_argument(
        "--appearance", action="append", choices=("fusion", "plain"),
        help="选择版本外观，可重复；默认同时生成高版本与非融球版本",
    )
    parser.add_argument(
        "--include-template-examples", action="store_true",
        help="追加模版场景示例页签的八个演示需求，不改变默认画廊矩阵",
    )
    parser.add_argument(
        "--model-failure-attempts",
        type=int,
        default=2,
        help="仅对 A2UI_GENERATION_FAILED 执行的单用例最大尝试次数",
    )
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
    return parser.parse_args()


async def run(args: argparse.Namespace) -> int:
    input_root = args.input_root.resolve()
    output_root = args.output_root.resolve()
    env_file = args.env_file.resolve() if args.env_file else None
    original_working_directory = Path.cwd()
    os.chdir(_WIDGET_SERVICE_ROOT)
    try:
        from services.template_generation.test_support.gallery_model_runtime import (
            GalleryHttpTransport,
            configure_gallery_environment,
        )

        http_config = configure_gallery_environment(env_file) if env_file else None
        from services.template_generation.test_support.provider_gallery import (
            generate_provider_gallery,
            write_gallery_input_dataset,
        )

        selection_changed = bool(args.size or args.appearance)
        if args.refresh_inputs or selection_changed or not (input_root / "manifest.json").is_file():
            manifest = write_gallery_input_dataset(
                input_root, card_sizes=tuple(args.size or ("2x2", "2x4")),
                appearances=tuple(args.appearance or ("fusion", "plain")),
            )
            case_count = sum(len(provider.cases) for provider in manifest.providers)
            print(
                f"画廊模拟输入已生成：Provider={len(manifest.providers)}，"
                f"用例={case_count}"
            )
        if args.include_template_examples:
            from services.template_generation.test_support.template_examples import (
                append_template_examples,
            )

            append_template_examples(input_root)
        provider_ids = set(args.provider) or None
        runtime = None
        if http_config is not None:
            from custom.model_runtime import ModelExecutionRuntime

            runtime = ModelExecutionRuntime(llmclient_transport=GalleryHttpTransport(http_config))
        summary = await generate_provider_gallery(
            input_root,
            output_root,
            concurrency=args.concurrency,
            provider_ids=provider_ids,
            dry_run=args.dry_run,
            model_failure_attempts=args.model_failure_attempts,
            runtime=runtime,
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
