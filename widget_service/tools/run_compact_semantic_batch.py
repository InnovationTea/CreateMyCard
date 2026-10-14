"""用现有 cardSpec24 串行验证语义布局，复用原 Runner 和 .env，不整轮重跑。"""

import argparse
import asyncio
import importlib.util
import json
import os
import re
import subprocess
import time
from pathlib import Path

CLOUD = Path(__file__).resolve().parents[1] / "cloud"


def save_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def trace_counts(directory: Path) -> dict:
    result = {}
    file = directory / "trace.jsonl"
    if not file.is_file():
        return result
    for line in file.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("event") == "request.completed":
            result = record.get("details", {}).get("attemptCounts", {})
    return result


def prepare_preview(run: Path, meta: dict) -> None:
    index = meta["index"]
    preview = run / "preview"
    directory = run / meta["traceDirectory"] / "artifacts"
    artifact_file = run / "md" / f"q{index}_artifact.md"
    artifact = artifact_file.read_text(encoding="utf-8") if artifact_file.exists() else ""
    for label, suffix in (("request", "raw_request"), ("taskspec", "task_spec_attempt-1")):
        if f"```{label}" in artifact:
            continue
        candidates = sorted(directory.glob(f"*_{suffix}.json"))
        if candidates:
            artifact += f"\n```{label}\n" + candidates[-1].read_text(encoding="utf-8") + "\n```\n"
    if "```designcompactdsl" not in artifact:
        candidates = sorted(directory.glob("*_dsl_processing_input_*.txt"))
        if candidates:
            source = candidates[-1].read_text(encoding="utf-8")
            artifact += "\n```designcompactdsl\n" + source + "\n```\n"
            meta["previewSourceFromTrace"] = True
    (preview / "md").mkdir(parents=True, exist_ok=True)
    (preview / "md" / f"q{index}_artifact.md").write_text(artifact, encoding="utf-8")
    save_json(preview / f"q{index}_meta.json", meta)


async def run(args: argparse.Namespace) -> None:
    spec = importlib.util.spec_from_file_location(
        "native_semantic_runner", args.native / "runner.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载原始 Runner")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    runner.CLOUD_DIR = CLOUD
    runner.WORKSPACE_DIR = CLOUD / "workspace"
    runner.SERVER_PORT = args.port
    if runner.is_port_in_use(args.port):
        raise RuntimeError("实验端口被占用，不停止现有服务")
    settings = {
        "WIDGET_SERVICE_ENABLE_DESIGN_COMPACT_FEW_SHOTS": "true",
        "WIDGET_SERVICE_ENABLE_DESIGN_COMPACT_FEW_SHOT_SELECTION": "false",
        "WIDGET_SERVICE_ENABLE_DESIGN_COMPACT_RUNTIME_PROMPT_CONTEXT": "false",
        "WIDGET_SERVICE_ENABLE_VALIDATION_FAILURE_RETRY": "true",
        "WIDGET_SERVICE_VALIDATION_FAILURE_MAX_REPAIR_ATTEMPTS": str(args.repairs),
        "WIDGET_SERVICE_ENABLE_COMPACT_DSL_INTERFACE_RETRY": "false",
        "WIDGET_SERVICE_ENABLE_COMPACT_DSL_ARGUMENT_REPAIR_FALLBACK": "false",
        "WIDGET_SERVICE_ENABLE_MODEL_FAILURE_RETRY": "false",
    }
    os.environ.update(settings)
    files = sorted((args.native / "cardSpec24").glob("Q*.json"))
    if args.cases:
        files = [file for file in files if int(re.search(r"\d+", file.stem).group()) in args.cases]
    if not files:
        raise ValueError("没有可运行的原始任务")
    args.output.mkdir(parents=True, exist_ok=False)
    save_json(args.output / "experiment-config.json", {
        "base": "2d43d55", "settings": settings, "inputs": str(args.native / "cardSpec24"),
        "taskCount": len(files), "requestsPerCase": 1, "dropReset": False,
        "fewshotContentChange": "V23 only: supporting columns=1 to retain full mA",
    })
    proc = runner.start_server(args.output)
    if proc is None:
        raise RuntimeError("服务启动失败")
    results = []
    started = time.perf_counter()
    try:
        for file in files:
            meta = await runner.run_single(file, args.output, max_retries=1)
            counts = trace_counts(args.output / meta["traceDirectory"])
            meta["modelCallCounts"] = counts
            meta["qualityRepairAttempts"] = counts.get("qualityRepairAttempts", 0)
            meta["totalAttempts"] = meta["qualityRepairAttempts"] + 1
            meta["totalElapsed_ms"] = meta["elapsed_ms"]
            if meta["qualityRepairAttempts"] > args.repairs:
                raise RuntimeError("请求突破修复预算")
            save_json(args.output / f"q{meta['index']}_meta.json", meta)
            prepare_preview(args.output, meta)
            results.append(meta)
            summary = {"results": results,
                       "totalElapsed_ms": round((time.perf_counter() - started) * 1000, 2)}
            save_json(args.output / "summary.json", summary)
            save_json(args.output / "preview/summary.json", summary)
            print(f"[Progress] {len(results)}/{len(files)}", flush=True)
    finally:
        if os.name == "nt" and proc.poll() is None:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True, check=False)
        else:
            runner.stop_server(proc)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", nargs="*", type=int)
    parser.add_argument("--repairs", type=int, default=10)
    parser.add_argument("--port", type=int, default=9009)
    args = parser.parse_args()
    if args.repairs < 1:
        raise ValueError("repairs must be positive")
    asyncio.run(run(args))
