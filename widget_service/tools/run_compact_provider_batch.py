"""通过现有Fusion Runner请求解析器运行指定模型通道；每条只发起一次服务请求。"""

import argparse
import asyncio
import getpass
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType

CLOUD = Path(__file__).resolve().parents[1] / "cloud"
PROVIDERS = ("deepseek_official_http", "aliyun_bailian")


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_runner(native: Path, port: int) -> ModuleType:
    spec = importlib.util.spec_from_file_location("native_provider_runner", native / "runner.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载已有Fusion Runner")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    runner.CLOUD_DIR = CLOUD
    runner.WORKSPACE_DIR = CLOUD / "workspace"
    runner.SERVER_PORT = port
    return runner


def _environment(runner: ModuleType, args: argparse.Namespace) -> dict[str, str]:
    env = runner._runner_environment()
    env.update({
        "PYTHONUTF8": "1",
        "WIDGET_SERVICE_LOCAL_FLAG": "true",
        "WIDGET_SERVICE_ENABLE_A2UI_MODEL_MOCK": "false",
        "WIDGET_SERVICE_DESIGN_COMPACT_MODEL_BACKEND": "openai",
        "WIDGET_SERVICE_OPENAI_MASTER_CLIENT": args.provider,
        "WIDGET_SERVICE_ENABLE_OPENAI_FALLBACK": "false",
        "WIDGET_SERVICE_ENABLE_SENSITIVE_LOG_FIELDS": "false",
        "WIDGET_SERVICE_ENABLE_CARD_TEMPLATE": "false",
        "WIDGET_SERVICE_ENABLE_JSX_GENERATION": "false",
        "WIDGET_SERVICE_WORKSPACE_ROOT": str(runner.WORKSPACE_DIR),
        "WIDGET_SERVICE_SERVER_HOST": runner.SERVER_HOST,
        "WIDGET_SERVICE_SERVER_PORT": str(args.port),
        "WIDGET_SERVICE_ENABLE_DESIGN_COMPACT_FEW_SHOTS": "true",
        "WIDGET_SERVICE_ENABLE_DESIGN_COMPACT_FEW_SHOT_SELECTION": "false",
        "WIDGET_SERVICE_ENABLE_DESIGN_COMPACT_RUNTIME_PROMPT_CONTEXT": "false",
        "WIDGET_SERVICE_ENABLE_VALIDATION_FAILURE_RETRY": "true",
        "WIDGET_SERVICE_VALIDATION_FAILURE_MAX_REPAIR_ATTEMPTS": str(args.repairs),
        "WIDGET_SERVICE_ENABLE_COMPACT_DSL_INTERFACE_RETRY": "false",
        "WIDGET_SERVICE_ENABLE_COMPACT_DSL_ARGUMENT_REPAIR_FALLBACK": "false",
        "WIDGET_SERVICE_ENABLE_MODEL_FAILURE_RETRY": "false",
        "WIDGET_SERVICE_ENABLE_DROP_PLAN_FACT_VALIDATION": "false",
    })
    if args.provider == "aliyun_bailian":
        if args.base_url:
            env["WIDGET_SERVICE_ALIYUN_BAILIAN_BASE_URL"] = args.base_url
        if args.model:
            env["WIDGET_SERVICE_ALIYUN_BAILIAN_MODEL"] = args.model
        if args.ask_api_key:
            env["WIDGET_SERVICE_ALIYUN_BAILIAN_API_KEY"] = getpass.getpass("API key (hidden): ")
        if not env.get("WIDGET_SERVICE_ALIYUN_BAILIAN_API_KEY"):
            raise ValueError("请提供WIDGET_SERVICE_ALIYUN_BAILIAN_API_KEY或--ask-api-key")
    elif not runner._configure_model_key(env):
        raise ValueError("请提供官方DeepSeek密钥")
    runner._configure_trace_environment(env, args.output)
    return env


def _trace_counts(run: Path, result: dict) -> dict:
    trace = run / result.get("traceDirectory", "") / "trace.jsonl"
    counts = {}
    if trace.is_file():
        for line in trace.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            if entry.get("event") == "request.completed":
                counts = entry.get("details", {}).get("attemptCounts", {})
    return counts


async def run(args: argparse.Namespace) -> None:
    runner = _load_runner(args.native, args.port)
    if runner.is_port_in_use(args.port):
        raise RuntimeError("端口已被占用，不操作现有服务")
    inputs = args.spec_dir or args.native / "cardSpec24"
    files = sorted(inputs.glob("Q*.json"))
    if args.cases:
        files = [file for file in files if int(re.search(r"\d+", file.stem).group()) in args.cases]
    if not files:
        raise ValueError("没有匹配的原始任务")
    env = _environment(runner, args)
    args.output.mkdir(parents=True, exist_ok=False)
    snapshot = {}
    for name, value in env.items():
        if name.startswith("WIDGET_SERVICE_") and not re.search("KEY|SECRET|TOKEN", name):
            if name in {
                "WIDGET_SERVICE_OPENAI_MASTER_CLIENT", "WIDGET_SERVICE_ALIYUN_BAILIAN_BASE_URL",
                "WIDGET_SERVICE_ALIYUN_BAILIAN_MODEL",
            } or "ENABLE_" in name or "REPAIR_ATTEMPTS" in name:
                snapshot[name] = value
    commit = subprocess.check_output(
        ["git", "-c", f"safe.directory={CLOUD.parents[1].as_posix()}", "rev-parse", "HEAD"],
        cwd=CLOUD.parents[1], text=True,
    ).strip()
    _write_json(args.output / "experiment-config.json", {
        "base": commit, "settings": snapshot, "inputs": str(inputs), "taskCount": len(files),
        "requestsPerCase": 1, "provider": args.provider,
    })
    log = (args.output / "server.log").open("w", encoding="utf-8")
    options = runner._server_process_options()
    proc = subprocess.Popen(
        [sys.executable, "start_websocket_server.py"], cwd=CLOUD, env=env,
        stdout=log, stderr=subprocess.STDOUT, **options,
    )
    started = time.perf_counter()
    results = []
    try:
        for _ in range(30):
            if proc.poll() is not None:
                raise RuntimeError("服务启动失败，请查看server.log")
            if runner.is_port_in_use(args.port):
                break
            await asyncio.sleep(1)
        else:
            raise RuntimeError("服务启动超时")
        for file in files:
            result = await runner.run_single(file, args.output, max_retries=1)
            counts = _trace_counts(args.output, result)
            result["modelCallCounts"] = counts
            repairs = counts.get("qualityRepairAttempts", 0)
            if repairs > args.repairs:
                raise RuntimeError("超过配置的修复预算")
            result.update(qualityRepairAttempts=repairs, totalAttempts=repairs + 1)
            result["totalElapsed_ms"] = result.get("elapsed_ms")
            _write_json(args.output / f"q{result.get('index')}_meta.json", result)
            results.append(result)
            success = sum(item.get("status") == "success" for item in results)
            failed = sum(item.get("status") == "failed" for item in results)
            _write_json(args.output / "summary.json", {
                "results": results, "total": len(results), "success": success, "failed": failed,
                "other": len(results) - success - failed,
                "totalElapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            })
            print(f"[Progress] {len(results)}/{len(files)}", flush=True)
    finally:
        if os.name == "nt" and proc.poll() is None:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True, check=False)
        else:
            runner.stop_server(proc)
        log.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--spec-dir", type=Path)
    parser.add_argument("--cases", nargs="*", type=int)
    parser.add_argument("--provider", choices=PROVIDERS, default="deepseek_official_http")
    parser.add_argument("--base-url", help="百炼公共或专属部署base URL")
    parser.add_argument("--model", help="百炼部署中真实存在的模型ID")
    parser.add_argument("--ask-api-key", action="store_true", help="隐藏输入百炼密钥，不落盘")
    parser.add_argument("--repairs", type=int, default=5)
    parser.add_argument("--port", type=int, default=9015)
    options = parser.parse_args()
    if options.repairs < 1:
        parser.error("--repairs必须为正整数")
    asyncio.run(run(options))
