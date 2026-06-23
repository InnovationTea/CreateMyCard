#!/usr/bin/env python3
"""CreateMyCard CLI for HarmonyOS A2UI v0.9 DSL batch generation."""

from __future__ import annotations

import argparse
import sys

from createmycard_generator.config import (
    DEFAULT_BASE_URL,
    DEFAULT_DELAY,
    DEFAULT_ITEM_OUTPUT_DIR,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT,
    SCRIPT_DIR,
    disable_proxy_env,
    load_api_config,
    load_env_file,
    mask_secret,
    resolve_path,
)
from createmycard_generator.io_utils import read_queries
from createmycard_generator.pipeline import process_batch
from createmycard_generator.prompt_builder import assemble_system_prompt
from createmycard_generator.validator_adapter import VALIDATOR_IMPORT, validator_available


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CreateMyCard：HarmonyOS A2UI v0.9 DSL 批量生成工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python batch_generate.py -i queries.jsonl -o output/results.json
    python batch_generate.py -i queries.jsonl --validate --max-retry 2
        """,
    )
    parser.add_argument("-i", "--input", default=str(SCRIPT_DIR / "queries.jsonl"), help="输入 queries JSONL 或 CSV 文件路径")
    parser.add_argument("-o", "--output", default=str(SCRIPT_DIR / "output" / "results.json"), help="汇总 results JSON 文件路径")
    parser.add_argument("--item-output-dir", default=str(SCRIPT_DIR / DEFAULT_ITEM_OUTPUT_DIR), help="每条 query 的独立 JSON/dat 输出目录")
    parser.add_argument("--skill-dir", default=str(SCRIPT_DIR / "skills" / "generate-harmonyos-a2ui-widget"), help="skill 目录路径")
    parser.add_argument("--model", default=None, help=f"模型名称覆盖 (默认: {DEFAULT_MODEL})")
    parser.add_argument("--base-url", default=None, help=f"API base URL 覆盖 (默认: {DEFAULT_BASE_URL})")
    parser.add_argument("--auth-token", default=None, help="API auth token 覆盖")
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE, help="模型温度 (默认: 不发送)")
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS, help=f"每次请求最大 token 数 (默认: {DEFAULT_MAX_TOKENS})")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"API 请求超时秒数 (默认: {DEFAULT_TIMEOUT})")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help=f"请求间隔秒数 (默认: {DEFAULT_DELAY})")
    parser.add_argument("--config", default=str(SCRIPT_DIR / ".claude" / "settings.local.json"), help="API 配置文件路径")
    parser.add_argument("--validate", action="store_true", default=False, help="是否启用静态校验")
    parser.add_argument("--write-items", action="store_true", default=False, help="额外输出每条 query 的独立 JSON/dat 文件")
    parser.add_argument("--single-file", action="store_true", default=False, help="兼容旧参数；当前默认只输出汇总 results.json")
    parser.add_argument("--extract-keywords", dest="extract_keywords", action="store_true", default=True, help="让 LLM 提取关键词（默认开启）")
    parser.add_argument("--no-extract-keywords", dest="extract_keywords", action="store_false", help="关闭关键词提取")
    parser.add_argument("--max-retry", type=int, default=1, help="校验不通过时最多重试次数")
    parser.add_argument("--dry-run", action="store_true", default=False, help="只检查配置和输入，不调用 API")
    return parser


def main() -> None:
    load_env_file(SCRIPT_DIR)
    disable_proxy_env()
    args = build_parser().parse_args()

    input_path = resolve_path(args.input)
    output_path = resolve_path(args.output)
    item_output_dir = resolve_path(args.item_output_dir)
    skill_dir = resolve_path(args.skill_dir)
    config_path = resolve_path(args.config)

    if not skill_dir.is_dir():
        sys.exit(f"错误：skill 目录不存在：{skill_dir}")
    if args.validate and not validator_available():
        sys.exit(f"错误：无法加载校验器：{VALIDATOR_IMPORT}")

    api_config = load_api_config(config_path)
    if args.model:
        api_config["model"] = args.model
    if args.base_url:
        api_config["base_url"] = args.base_url
    if args.auth_token:
        api_config["auth_token"] = args.auth_token

    print(f"API Base URL: {api_config['base_url']}")
    print(f"Model:        {api_config['model']}")
    print(f"Auth Token:   {mask_secret(api_config['auth_token'])}")
    print(f"Input:        {input_path}")
    print(f"Output:       {output_path}")
    if args.write_items:
        print(f"Item output:  {item_output_dir}")
    else:
        print("Output mode:  summary only (results.json)")
    if args.validate:
        print("Validation:   enabled (with auto-fix retry)")
        print(f"Max retry:    {args.max_retry} (total attempts: {args.max_retry + 1})")
    else:
        print("Validation:   disabled (DSL generation only)")
    if args.extract_keywords:
        print("Keywords:     enabled (for OCR comparison)")
    print()

    if args.dry_run:
        queries = read_queries(input_path)
        system_prompt = assemble_system_prompt(skill_dir)
        print("Dry run OK")
        print(f"Queries:       {len(queries)}")
        print(f"System prompt: {len(system_prompt)} chars")
        return

    process_batch(
        input_path=input_path,
        output_path=output_path,
        item_output_dir=item_output_dir,
        skill_dir=skill_dir,
        api_config=api_config,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        request_timeout=args.timeout,
        delay_between_queries=args.delay,
        validate_enabled=args.validate,
        write_items=args.write_items,
        extract_keywords=args.extract_keywords,
        max_retry=args.max_retry,
    )


if __name__ == "__main__":
    main()
