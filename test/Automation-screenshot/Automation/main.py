from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import sys

# Add the project root to Python path for direct script execution.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from automation.config import AutomationConfig
from automation.hdc import HdcClient, HdcError
from automation.pipeline import AutomationPipeline
from automation.queries import QueryCase, load_queries
from visual_aesthetics.config import AestheticsConfig

DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUTOMATION_CONFIG = DEFAULT_PROJECT_ROOT / "Automation" / "config" / "automation.json"
DEFAULT_CARD_CROP_CONFIG = DEFAULT_PROJECT_ROOT / "Automation" / "config" / "card_crop.json"

def add_common_arguments(
    parser: argparse.ArgumentParser,
    *,
    with_defaults: bool,
    include_card_crop: bool = False,
    include_card_crop_enable: bool = False,
    include_aesthetics: bool = False,
) -> None:
    default = None if with_defaults else argparse.SUPPRESS
    hidden = argparse.SUPPRESS
    config_default = DEFAULT_AUTOMATION_CONFIG if with_defaults else default

    parser.add_argument("--config", type=Path, default=config_default, help="Runtime JSON config path")
    parser.add_argument("--sn", default=default, help="Target device SN")
    parser.add_argument("--debug", action="store_true", default=default, help="Enable debug logging")

    if include_card_crop_enable:
        parser.add_argument("--enable-card-crop", action="store_true", default=default, help="Crop card images after screenshots")
    if include_card_crop:
        parser.add_argument("--card-crop-debug", action="store_true", default=default, help="Save annotated card crop debug images")

    if include_aesthetics:
        parser.add_argument("--enable-aesthetics", action="store_true", default=default, help="Enable UI aesthetics scoring")
        parser.add_argument("--aesthetics-base-url", type=str, default=default, help="Aesthetics model API base URL")
        parser.add_argument("--aesthetics-api-key", type=str, default=default, help="Aesthetics model API key")

    # Advanced compatibility knobs. Prefer Automation/config/automation.json for these.
    parser.add_argument("--project-root", type=Path, default=default, help=hidden)
    parser.add_argument("--hdc", default=default, help=hidden)
    parser.add_argument("--ready-timeout", type=float, default=default, help=hidden)
    parser.add_argument("--extract-delay", type=float, default=default, help=hidden)
    parser.add_argument("--reply-timeout", type=float, default=default, help=hidden)
    parser.add_argument("--post-query-wait", type=float, default=default, help=hidden)
    parser.add_argument("--query-attempt-timeout", type=float, default=default, help=hidden)
    parser.add_argument("--query-max-attempts", type=int, default=default, help=hidden)
    parser.add_argument("--build-timeout", type=float, default=default, help=hidden)
    parser.add_argument("--render-wait", type=float, default=default, help=hidden)
    parser.add_argument("--deveco-sdk-home", type=Path, default=default, help=hidden)
    parser.add_argument("--java-home", type=Path, default=default, help=hidden)
    parser.add_argument("--bundle-name", default=default, help=hidden)
    parser.add_argument("--ability-name", default=default, help=hidden)
    parser.add_argument("--module-name", default=default, help=hidden)
    parser.add_argument("--screenshot-min-bytes", type=int, default=default, help=hidden)
    parser.add_argument("--screenshot-retries", type=int, default=default, help=hidden)
    parser.add_argument("--screenshot-write-wait", type=float, default=default, help=hidden)
    parser.add_argument("--card-crop-config", type=Path, default=default, help=hidden)
    
    parser.add_argument("--aesthetics-model", type=str, default=default, help=hidden)
    parser.add_argument("--aesthetics-output-mode", type=str, choices=["full", "score-only"], default=default, help=hidden)
    parser.add_argument("--aesthetics-timeout", type=int, default=default, help=hidden)
    parser.add_argument("--aesthetics-max-retries", type=int, default=default, help=hidden)
    parser.add_argument("--aesthetics-max-tokens", type=int, default=default, help=hidden)
    parser.add_argument("--aesthetics-temperature", type=float, default=default, help=hidden)
    parser.add_argument("--aesthetics-disable-cache", action="store_true", default=default, help=hidden)
    parser.add_argument("--aesthetics-enable-cache", action="store_true", default=default, help=hidden)
    parser.add_argument("--aesthetics-max-workers", type=int, default=default, help=hidden)
    parser.add_argument("--aesthetics-fail-fast", action="store_true", default=default, help=hidden)

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Xiaoyi DSL render automation")
    add_common_arguments(parser, with_defaults=True)
    subparsers = parser.add_subparsers(dest="command", required=True)

    one = subparsers.add_parser("one", help="Send one query, extract DSL, render, and screenshot")
    add_common_arguments(one, with_defaults=False, include_card_crop=True, include_card_crop_enable=True, include_aesthetics=True)
    one.add_argument("--qid", default="manual")
    one.add_argument("--query", required=True)

    from_file = subparsers.add_parser("one-from-file", help="Run one query from queries.jsonl by id")
    add_common_arguments(from_file, with_defaults=False, include_card_crop=True, include_card_crop_enable=True, include_aesthetics=True)
    from_file.add_argument("--qid", required=True)
    from_file.add_argument("--queries", type=Path)

    batch = subparsers.add_parser("batch", help="Collect all DSLs first, then render all screenshots")
    add_common_arguments(batch, with_defaults=False, include_card_crop=True, include_card_crop_enable=True, include_aesthetics=True)
    batch.add_argument("--queries", type=Path)

    collect_dsl = subparsers.add_parser("collect-dsl", help="Send queries and save DSL files only")
    add_common_arguments(collect_dsl, with_defaults=False)
    collect_dsl.add_argument("--queries", type=Path)

    render_dsl_dir = subparsers.add_parser("render-dsl-dir", help="Render existing DSL files and screenshot")
    add_common_arguments(render_dsl_dir, with_defaults=False, include_card_crop=True, include_card_crop_enable=True)
    render_dsl_dir.add_argument("--dsl-dir", type=Path, help="Directory containing *.jsonl DSL files")
    
    parallel = subparsers.add_parser("parallel", help="Run the full query batch on multiple devices")
    add_common_arguments(parallel, with_defaults=False, include_card_crop=True, include_card_crop_enable=True, include_aesthetics=True)
    parallel.add_argument("--queries", type=Path)
    parallel.add_argument("--devices", default="auto", help="Use 'auto' or a comma-separated SN list")
    parallel.add_argument("--max-workers", type=int, help="Maximum parallel devices")
    
    aesthetics = subparsers.add_parser("aesthetics", help="Independent UI aesthetic judging command, judge existing screenshots directly")
    add_common_arguments(aesthetics, with_defaults=False, include_aesthetics=True)
    aesthetics.add_argument("--input", type=Path, required=True, help="Input image directory or single image file")
    aesthetics.add_argument("--output", type=Path, help="Output directory or file path, default to input directory")
    aesthetics.add_argument("--skip-report", action="store_true", help="Skip generating HTML report")

    crop_card = subparsers.add_parser("crop-card", help="Crop card images from existing screenshots")
    add_common_arguments(crop_card, with_defaults=False, include_card_crop=True)
    crop_card.add_argument("--input", type=Path, required=True, help="Input screenshot file or directory")
    crop_card.add_argument("--output", type=Path, help="Output directory or output file for single input")

    return parser

def make_config(args: argparse.Namespace, *, sn: str | None = None) -> tuple[AutomationConfig, AestheticsConfig]:
    runtime_config = load_runtime_config(args.config)
    automation_section = runtime_config.get("automation", {})
    aesthetics_section = runtime_config.get("aesthetics", {})

    def value(name: str, default_value=None):
        cli_value = getattr(args, name, None)
        if cli_value is not None:
            return cli_value
        return automation_section.get(name, default_value)

    values = {
        "project_root": value("project_root", DEFAULT_PROJECT_ROOT),
        "hdc": value("hdc", "hdc"),
        "sn": sn if sn is not None else value("sn", None),
        "ready_timeout": value("ready_timeout", 60),
        "extract_delay": value("extract_delay", 30),
        "reply_timeout": value("reply_timeout", 120),
        "post_query_wait": value("post_query_wait", 30),
        "query_attempt_timeout": value("query_attempt_timeout", 90),
        "query_max_attempts": value("query_max_attempts", 3),
        "build_timeout": value("build_timeout", 300),
        "render_wait": value("render_wait", 5),
        "bundle_name": value("bundle_name", "yyx.test.test"),
        "ability_name": value("ability_name", "EntryAbility"),
        "module_name": value("module_name", "entry"),
        "screenshot_min_bytes": value("screenshot_min_bytes", 1000),
        "screenshot_retries": value("screenshot_retries", 3),
        "screenshot_write_wait": value("screenshot_write_wait", 1),
        "enable_card_crop": value("enable_card_crop", False),
        "card_crop_config": value("card_crop_config", DEFAULT_CARD_CROP_CONFIG),
        "card_crop_debug": value("card_crop_debug", False),
        "debug": value("debug", False),
    }
    if value("deveco_sdk_home") is not None:
        values["deveco_sdk_home"] = value("deveco_sdk_home")
    if value("java_home") is not None:
        values["java_home"] = value("java_home")

    values = coerce_automation_values(values)
    
    automation_config = AutomationConfig(**values)
    
    aesthetics_config = make_aesthetics_config(args, aesthetics_section, automation_config.project_root)
    return automation_config, aesthetics_config

def load_runtime_config(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise SystemExit(f"Runtime config must be a JSON object: {path}")
    return data

def make_aesthetics_config(args: argparse.Namespace, config: dict, project_root: Path) -> AestheticsConfig:
    env_config = AestheticsConfig.from_env(project_root)

    def value(cli_name: str, config_name: str, env_value):
        cli_value = getattr(args, cli_name, None)
        if cli_value is not None:
            return cli_value
        return config.get(config_name, config.get(cli_name, env_value))

    enable_cache = value("aesthetics_enable_cache", "enable_cache", env_config.enable_cache)
    if getattr(args, "aesthetics_enable_cache", None) is not None:
        enable_cache = True
    if getattr(args, "aesthetics_disable_cache", None) is not None:
        enable_cache = False

    return AestheticsConfig(
        enable=value("enable_aesthetics", "enable", False),
        base_url=value("aesthetics_base_url", "base_url", env_config.base_url),
        api_key=value("aesthetics_api_key", "api_key", env_config.api_key),
        model=value("aesthetics_model", "model", env_config.model),
        output_mode=value("aesthetics_output_mode", "output_mode", env_config.output_mode),
        timeout=value("aesthetics_timeout", "timeout", env_config.timeout),
        max_retries=value("aesthetics_max_retries", "max_retries", env_config.max_retries),
        max_tokens=value("aesthetics_max_tokens", "max_tokens", env_config.max_tokens),
        temperature=value("aesthetics_temperature", "temperature", env_config.temperature),
        enable_cache=enable_cache,
        cache_dir=Path(value("aesthetics_cache_dir", "cache_dir", env_config.cache_dir)),
        max_workers=value("aesthetics_max_workers", "max_workers", env_config.max_workers),
        fail_fast=value("aesthetics_fail_fast", "fail_fast", env_config.fail_fast),
    )

def coerce_automation_values(values: dict) -> dict:
    path_keys = {"project_root", "deveco_sdk_home", "java_home", "card_crop_config"}
    coerced = {key: Path(value) if key in path_keys and value is not None else value for key, value in values.items()}
    if coerced.get("project_root") == Path("."):
        coerced["project_root"] = DEFAULT_PROJECT_ROOT
    return coerced

def main() -> int:
    args = build_parser().parse_args()
    
    if args.command == "crop-card":
        return run_crop_card(args)

    if args.command == "aesthetics":
        from visual_aesthetics.judge import VisualAestheticsJudge
        config, aesthetics_config = make_config(args)
        judge = VisualAestheticsJudge(aesthetics_config)
        input_path = args.input.absolute()
        output_path = args.output.absolute() if args.output else input_path
        
        if input_path.is_file():
            result = judge.judge_image(input_path, qid=input_path.stem, sn=args.sn or "")
            status = "success" if result.success else f"failed: {result.error_msg}"
            print(f"Scoring done: {input_path.name}, score={result.final_score_100:.0f}, {status}")
            if args.output and output_path.suffix.lower() in {".json", ".jsonl"}:
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
                temp_jsonl = output_path / "temp_scores.jsonl"
                judge.batch_judge(input_path.parent, sn=args.sn or "", output_jsonl_path=temp_jsonl)
                judge.build_report(temp_jsonl, output_path / "report.html", image_dir=input_path.parent)
                temp_jsonl.unlink()
        else:
            output_jsonl = output_path / "scores.jsonl" if output_path.is_dir() else output_path
            results = judge.batch_judge(input_path, sn=args.sn or "", output_jsonl_path=output_jsonl)
            success = sum(1 for r in results if r.success)
            avg_score = sum(r.final_score_100 for r in results if r.success) / success if success > 0 else 0
            print(f"Batch scoring done: total={len(results)}, success={success}, failed={len(results)-success}, avg_score={avg_score:.1f}")
            
            if not args.skip_report:
                report_path = output_path / "report.html" if output_path.is_dir() else output_path.with_suffix(".html")
                judge.build_report(output_jsonl, report_path, image_dir=input_path)
                print(f"Report generated: {report_path}")
        return 0

    config, aesthetics_config = make_config(args)
    
    if args.command == "parallel":
        return run_parallel(args, aesthetics_config)
    
    validate_device_target(config)
    pipeline = AutomationPipeline(config, aesthetics_config)

    if args.command == "one":
        result = pipeline.run_one(QueryCase(qid=args.qid, query=args.query))
        print_result(result.qid, result.dsl_path, result.screenshot_path, result.card_path, sn=config.safe_sn)
        return 0

    if args.command == "one-from-file":
        queries = load_queries(args.queries or config.queries_path)
        matches = [case for case in queries if case.qid == args.qid]
        if not matches:
            raise SystemExit(f"Query id not found: {args.qid}")
        result = pipeline.run_one(matches[0])
        print_result(result.qid, result.dsl_path, result.screenshot_path, result.card_path, sn=config.safe_sn)
        return 0

    if args.command == "batch":
        results = pipeline.run_batch(args.queries)
        for result in results:
            print_result(result.qid, result.dsl_path, result.screenshot_path, result.card_path, sn=config.safe_sn)
        if aesthetics_config.enable:
            print(f"Aesthetics scoring done, report={config.report_html_path}")
        return 0

    if args.command == "collect-dsl":
        results = pipeline.collect_dsls(args.queries)
        for result in results:
            print(f"{result.qid}: DSL={result.dsl_path}")
        return 0

    if args.command == "render-dsl-dir":
        results = pipeline.render_dsl_dir(args.dsl_dir)
        for result in results:
            print_result(result.qid, result.dsl_path, result.screenshot_path, result.card_path, sn=config.safe_sn)
        return 0

    raise AssertionError(args.command)

def run_crop_card(args: argparse.Namespace) -> int:
    from automation.card_crop import CardCropper, find_image_files, load_card_crop_config

    config, _ = make_config(args)
    cropper = CardCropper(load_card_crop_config(config.card_crop_config or config.default_card_crop_config_path))
    input_path = args.input.absolute()
    image_files = find_image_files(input_path)
    if not image_files:
        raise SystemExit(f"No images found: {input_path}")

    output = args.output.absolute() if args.output else None
    failed = 0
    for image_path in image_files:
        try:
            output_path = output if output and input_path.is_file() and output.suffix else None
            output_dir = output.parent if output_path else output or image_path.parent
            result = cropper.crop(
                image_path,
                output_dir,
                output_path=output_path,
                debug=config.card_crop_debug,
                debug_dir=(output_dir / "_debug") if config.card_crop_debug else None,
            )
        except Exception as exc:
            failed += 1
            print(f"Card crop failed: {image_path} error={exc}")
            continue
        print(f"Card crop done: {image_path.name} type={result.card_type} box={result.box} output={result.card_path}")

    return 1 if failed else 0

def run_parallel(args: argparse.Namespace, aesthetics_config: AestheticsConfig) -> int:
    devices = resolve_devices(args.devices, args.hdc)
    max_workers = args.max_workers or len(devices)
    if max_workers < 1:
        raise SystemExit("--max-workers must be greater than 0")

    print(f"Parallel devices: {len(devices)}, devices: {', '.join(devices)}")
    failed = False
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_sn = {}
        for sn in devices:
            config, aest_config = make_config(args, sn=sn)
            pipeline = AutomationPipeline(config, aest_config if aesthetics_config.enable else None)
            future = executor.submit(pipeline.run_batch, args.queries)
            future_to_sn[future] = sn
        
        for future in as_completed(future_to_sn):
            sn = future_to_sn[future]
            try:
                results = future.result()
                print(f"Device[{sn}] done, processed={len(results)}")
                if aesthetics_config.enable:
                    print(f"Device[{sn}] report={results[0] and results[0].screenshot_path.parent / 'report.html' or ''}")
            except Exception as e:
                failed = True
                print(f"Device[{sn}] failed: {e}")
                continue

    return 1 if failed else 0

def validate_device_target(config: AutomationConfig) -> None:
    try:
        devices = HdcClient.list_targets(config.hdc)
    except HdcError as exc:
        raise SystemExit(str(exc)) from exc

    if config.sn:
        if config.sn not in devices:
            raise SystemExit(f"HDC device not found: {config.sn}. Available devices: {', '.join(devices) or '[Empty]'}")
        return

    if not devices:
        raise SystemExit("No HDC devices found. Connect a device or pass --sn after it is online.")
    if len(devices) > 1:
        raise SystemExit(f"Multiple HDC devices found. Pass --sn with one of: {', '.join(devices)}")

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

def print_result(qid: str, dsl_path: Path, screenshot_path: Path, card_path: Path | None = None, *, sn: str | None = None) -> None:
    prefix = f"[{sn}] " if sn else ""
    card = f" CARD={card_path}" if card_path else ""
    print(f"{prefix}{qid}: DSL={dsl_path} SCREENSHOT={screenshot_path}{card}")

if __name__ == "__main__":
    raise SystemExit(main())

