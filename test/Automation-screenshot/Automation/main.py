from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import sys

# 把项目根目录加入Python路径
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from automation.config import AutomationConfig
from automation.hdc import HdcClient
from automation.pipeline import AutomationPipeline
from automation.queries import QueryCase, load_queries
from visual_aesthetics.config import AestheticsConfig

DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]

def add_common_arguments(parser: argparse.ArgumentParser, *, with_defaults: bool) -> None:
    default = None if with_defaults else argparse.SUPPRESS
    parser.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT if with_defaults else default)
    parser.add_argument("--hdc", default="hdc" if with_defaults else default)
    parser.add_argument("--sn", default=None if with_defaults else default)
    parser.add_argument("--extract-delay", type=float, default=30 if with_defaults else default)
    parser.add_argument("--reply-timeout", type=float, default=120 if with_defaults else default)
    parser.add_argument("--post-query-wait", type=float, default=30 if with_defaults else default)
    parser.add_argument("--query-attempt-timeout", type=float, default=90 if with_defaults else default)
    parser.add_argument("--query-max-attempts", type=int, default=3 if with_defaults else default)
    parser.add_argument("--build-timeout", type=float, default=300 if with_defaults else default)
    parser.add_argument("--render-wait", type=float, default=5 if with_defaults else default)
    parser.add_argument("--deveco-sdk-home", type=Path, default=default)
    parser.add_argument("--java-home", type=Path, default=default)
    parser.add_argument("--bundle-name", default="yyx.test.test" if with_defaults else default)
    parser.add_argument("--ability-name", default="EntryAbility" if with_defaults else default)
    parser.add_argument("--module-name", default="entry" if with_defaults else default)
    parser.add_argument("--screenshot-min-bytes", type=int, default=1000 if with_defaults else default)
    parser.add_argument("--screenshot-retries", type=int, default=3 if with_defaults else default)
    parser.add_argument("--screenshot-write-wait", type=float, default=1 if with_defaults else default)
    
    # 审美打分相关参数
    parser.add_argument("--enable-aesthetics", action="store_true", default=False if with_defaults else default, help="开启UI审美打分功能")
    parser.add_argument("--aesthetics-base-url", type=str, default=default, help="打分模型API地址")
    parser.add_argument("--aesthetics-api-key", type=str, default=default, help="打分模型API密钥")
    parser.add_argument("--aesthetics-model", type=str, default="doubao-seed-2-0-lite" if with_defaults else default, help="打分模型名称")
    parser.add_argument("--aesthetics-output-mode", type=str, choices=["full", "score-only"], default="full" if with_defaults else default, help="打分输出模式：full全量/score-only仅得分")
    parser.add_argument("--aesthetics-timeout", type=int, default=360 if with_defaults else default, help="API调用超时时间(秒)")
    parser.add_argument("--aesthetics-max-retries", type=int, default=3 if with_defaults else default, help="API调用最大重试次数")
    parser.add_argument("--aesthetics-max-tokens", type=int, default=1200 if with_defaults else default, help="模型输出最大token数")
    parser.add_argument("--aesthetics-temperature", type=float, default=0.0 if with_defaults else default, help="模型温度，0为确定性输出")
    parser.add_argument("--aesthetics-disable-cache", action="store_true", default=False if with_defaults else default, help="禁用本地缓存，每次都重新调用API")
    parser.add_argument("--aesthetics-max-workers", type=int, default=2 if with_defaults else default, help="打分最大并发数")
    parser.add_argument("--debug", action="store_true", default=False if with_defaults else default, help="开启DEBUG日志")
    parser.add_argument("--aesthetics-fail-fast", action="store_true", default=False if with_defaults else default, help="打分失败中断整个流程")

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Xiaoyi DSL render automation")
    add_common_arguments(parser, with_defaults=True)
    subparsers = parser.add_subparsers(dest="command", required=True)

    one = subparsers.add_parser("one", help="Send one query, extract DSL, render, and screenshot")
    add_common_arguments(one, with_defaults=False)
    one.add_argument("--qid", default="manual")
    one.add_argument("--query", required=True)

    from_file = subparsers.add_parser("one-from-file", help="Run one query from queries.jsonl by id")
    add_common_arguments(from_file, with_defaults=False)
    from_file.add_argument("--qid", required=True)
    from_file.add_argument("--queries", type=Path)

    batch = subparsers.add_parser("batch", help="Collect all DSLs first, then render all screenshots")
    add_common_arguments(batch, with_defaults=False)
    batch.add_argument("--queries", type=Path)
    
    parallel = subparsers.add_parser("parallel", help="Run the full query batch on multiple devices")
    add_common_arguments(parallel, with_defaults=False)
    parallel.add_argument("--queries", type=Path)
    parallel.add_argument("--devices", default="auto", help="Use 'auto' or a comma-separated SN list")
    parallel.add_argument("--max-workers", type=int, help="最大并行设备数，默认等于设备数")
    
    # 独立的审美打分子命令，不用跑完整流程，直接给已有截图打分
    aesthetics = subparsers.add_parser("aesthetics", help="Independent UI aesthetic judging command, judge existing screenshots directly")
    add_common_arguments(aesthetics, with_defaults=False)
    aesthetics.add_argument("--input", type=Path, required=True, help="Input image directory or single image file")
    aesthetics.add_argument("--output", type=Path, help="Output directory or file path, default to input directory")
    aesthetics.add_argument("--skip-report", action="store_true", help="Skip generating HTML report")

    return parser

def make_config(args: argparse.Namespace, *, sn: str | None = None) -> tuple[AutomationConfig, AestheticsConfig]:
    values = {
        "project_root": args.project_root,
        "hdc": args.hdc,
        "sn": sn if sn is not None else args.sn,
        "extract_delay": args.extract_delay,
        "reply_timeout": args.reply_timeout,
        "post_query_wait": args.post_query_wait,
        "query_attempt_timeout": args.query_attempt_timeout,
        "query_max_attempts": args.query_max_attempts,
        "build_timeout": args.build_timeout,
        "render_wait": args.render_wait,
        "bundle_name": args.bundle_name,
        "ability_name": args.ability_name,
        "module_name": args.module_name,
        "screenshot_min_bytes": args.screenshot_min_bytes,
        "screenshot_retries": args.screenshot_retries,
        "screenshot_write_wait": args.screenshot_write_wait,
    }
    if args.deveco_sdk_home is not None:
        values["deveco_sdk_home"] = args.deveco_sdk_home
    if args.java_home is not None:
        values["java_home"] = args.java_home
    
    automation_config = AutomationConfig(**values)
    
    # 构造审美配置
    aesthetics_values = {}
    if hasattr(args, "enable_aesthetics"):
        aesthetics_values["enable"] = args.enable_aesthetics
    aesthetics_values["base_url"] = getattr(args, "aesthetics_base_url", "")
    aesthetics_values["api_key"] = getattr(args, "aesthetics_api_key", "")
    aesthetics_values["model"] = getattr(args, "aesthetics_model", "doubao-seed-2-0-lite")
    aesthetics_values["output_mode"] = getattr(args, "aesthetics_output_mode", "full")
    aesthetics_values["timeout"] = getattr(args, "aesthetics_timeout", 360)
    aesthetics_values["max_retries"] = getattr(args, "aesthetics_max_retries", 3)
    aesthetics_values["max_tokens"] = getattr(args, "aesthetics_max_tokens", 1200)
    aesthetics_values["temperature"] = getattr(args, "aesthetics_temperature", 0.0)
    # 缓存默认关闭。需要开启时传 --aesthetics-disable-cache（不传）或设置环境变量
    aesthetics_values["enable_cache"] = False
    aesthetics_values["max_workers"] = getattr(args, "aesthetics_max_workers", 2)
    aesthetics_values["fail_fast"] = getattr(args, "aesthetics_fail_fast", False)
    
    aesthetics_config = AestheticsConfig(**aesthetics_values)
    return automation_config, aesthetics_config

def main() -> int:
    args = build_parser().parse_args()
    
    # 独立打分子命令
    if args.command == "aesthetics":
        from visual_aesthetics.judge import VisualAestheticsJudge
        config, aesthetics_config = make_config(args)
        judge = VisualAestheticsJudge(aesthetics_config)
        input_path = args.input.absolute()
        output_path = args.output.absolute() if args.output else input_path
        
        if input_path.is_file():
            # 单张图片
            result = judge.judge_image(input_path, qid=input_path.stem, sn=args.sn or "")
            print(f"打分完成: {input_path.name}, 得分: {result.final_score_100:.0f}分, {'成功' if result.success else '失败: ' + result.error_msg}")
            if args.output and args.output.is_file():
                output_path.parent.mkdir(parents=True, exist_ok=True)
                import json
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "qid": result.qid,
                        "sn": result.sn,
                        "final_score": result.final_score,
                        "final_score_100": result.final_score_100,
                        "success": result.success,
                        "error_msg": result.error_msg
                    }, f, ensure_ascii=False, indent=2)
            elif not args.skip_report:
                # 单张图片也生成报告
                temp_jsonl = output_path / "temp_scores.jsonl"
                judge.batch_judge(input_path.parent, sn=args.sn or "", output_jsonl_path=temp_jsonl)
                judge.build_report(temp_jsonl, output_path / "report.html", image_dir=input_path.parent)
                temp_jsonl.unlink()
        else:
            # 批量目录
            output_jsonl = output_path / "scores.jsonl" if output_path.is_dir() else output_path
            results = judge.batch_judge(input_path, sn=args.sn or "", output_jsonl_path=output_jsonl)
            success = sum(1 for r in results if r.success)
            avg_score = sum(r.final_score_100 for r in results if r.success) / success if success > 0 else 0
            print(f"批量打分完成: 总数{len(results)}, 成功{success}, 失败{len(results)-success}, 平均得分{avg_score:.1f}分")
            
            if not args.skip_report:
                report_path = output_path / "report.html" if output_path.is_dir() else output_path.with_suffix(".html")
                judge.build_report(output_jsonl, report_path, image_dir=input_path)
                print(f"报告已生成: {report_path}")
        return 0

    config, aesthetics_config = make_config(args)
    
    if args.command == "parallel":
        return run_parallel(args, aesthetics_config)
    
    pipeline = AutomationPipeline(config, aesthetics_config)

    if args.command == "one":
        result = pipeline.run_one(QueryCase(qid=args.qid, query=args.query))
        print_result(result.qid, result.dsl_path, result.screenshot_path, sn=config.safe_sn)
        return 0

    if args.command == "one-from-file":
        queries = load_queries(args.queries or config.queries_path)
        matches = [case for case in queries if case.qid == args.qid]
        if not matches:
            raise SystemExit(f"Query id not found: {args.qid}")
        result = pipeline.run_one(matches[0])
        print_result(result.qid, result.dsl_path, result.screenshot_path, sn=config.safe_sn)
        return 0

    if args.command == "batch":
        results = pipeline.run_batch(args.queries)
        for result in results:
            print_result(result.qid, result.dsl_path, result.screenshot_path, sn=config.safe_sn)
        if aesthetics_config.enable:
            print(f"审美打分完成，报告路径: {config.report_html_path}")
        return 0

    raise AssertionError(args.command)

def run_parallel(args: argparse.Namespace, aesthetics_config: AestheticsConfig) -> int:
    devices = resolve_devices(args.devices, args.hdc)
    max_workers = args.max_workers or len(devices)
    if max_workers < 1:
        raise SystemExit("--max-workers must be greater than 0")

    print(f"并行设备数: {len(devices)}, 设备列表: {', '.join(devices)}")
    failed = False
    
    # 每个设备跑完整的batch流程
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_sn = {}
        for sn in devices:
            config, aest_config = make_config(args, sn=sn)
            # 每个设备的aesthetic配置是独立的，继承公共配置
            pipeline = AutomationPipeline(config, aest_config if aesthetics_config.enable else None)
            future = executor.submit(pipeline.run_batch, args.queries)
            future_to_sn[future] = sn
        
        for future in as_completed(future_to_sn):
            sn = future_to_sn[future]
            try:
                results = future.result()
                print(f"设备[{sn}]执行完成，成功处理{len(results)}个query")
                if aesthetics_config.enable:
                    print(f"设备[{sn}]打分报告路径: {results[0] and results[0].screenshot_path.parent / 'report.html' or ''}")
            except Exception as e:
                failed = True
                print(f"设备[{sn}]执行失败: {e}")
                continue

    return 1 if failed else 0

def resolve_devices(raw_devices: str, hdc: str) -> list[str]:
    if raw_devices.strip().lower() == "auto":
        devices = HdcClient.list_targets(hdc)
    else:
        devices = [part.strip() for part in raw_devices.split(",") if part.strip()]

    unique_devices: list[str] = []
    for device in devices:
        if device not in unique_devices:
            unique_devices.append(device)
    if not unique_devices:
        raise SystemExit("No HDC devices found. Connect devices or pass --devices SN1,SN2.")
    return unique_devices

def print_result(qid: str, dsl_path: Path, screenshot_path: Path, *, sn: str | None = None) -> None:
    prefix = f"[{sn}] " if sn else ""
    print(f"{prefix}{qid}: DSL={dsl_path} SCREENSHOT={screenshot_path}")

if __name__ == "__main__":
    raise SystemExit(main())

