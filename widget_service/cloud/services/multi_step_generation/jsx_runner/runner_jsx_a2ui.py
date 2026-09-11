"""Generate constrained Design System JSX and compile it to standard A2UI."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
SKILL_DIR = PACKAGE_DIR.parent
REPO_ROOT = SKILL_DIR
CLOUD_ROOT = SKILL_DIR.parents[1]
sys.path.insert(0, str(CLOUD_ROOT))

from config.config import get_settings  # noqa: E402
from services.multi_step_generation.core.bridge import JsxA2UIBridge  # noqa: E402
from services.multi_step_generation.core.options import BridgeOptions  # noqa: E402
from services.multi_step_generation.jsx_to_a2ui.exceptions import (  # noqa: E402
    ConversionError,
)
from services.multi_step_generation.jsx_runner.run_summary import (  # noqa: E402
    build_run_summary,
    render_run_summary_markdown,
    terminal_summary_lines,
)
from services.multi_step_generation.jsx_runner.agent import (  # noqa: E402
    PLAN_MAX_TOKENS,
    SUBMIT_MODES,
    JsxA2UIAgent,
)
from services.multi_step_generation.jsx_runner.artifacts import (  # noqa: E402
    build_component_name,
    create_run_dir,
    load_tasks,
    preview_template_components,
    select_tasks,
    write_card,
    write_json,
    write_rejected_card,
)
from services.multi_step_generation.jsx_runner.data_processing import (  # noqa: E402
    is_raw_task,
    prepare_task,
    prepare_tasks_from_views,
)
from services.multi_step_generation.jsx_runner.config import (  # noqa: E402
    MODEL_THINKING_MODE,
    DEFAULT_INPUT,
    DEFAULT_OUTPUT_ROOT,
    JSX_VALIDATOR_PATH,
    THINKING_MODES,
)
from services.multi_step_generation.jsx_runner.validation import (  # noqa: E402
    browser_runtime_missing_files,
)
from services.multi_step_generation.jsx_runner.resources import (  # noqa: E402
    GenerationResources,
)
from services.multi_step_generation.jsx_runner.resources import (  # noqa: E402
    generation_contract_sync_errors,
    generatable_contracts,
)


def _persist_current_trace(
    *,
    traces_path: Path,
    traces: list[dict[str, Any]],
    task_trace_path: Path,
    trace_entry: dict[str, Any],
) -> None:
    """Keep the aggregate trace and one card's standalone trace in sync."""
    write_json(traces_path, traces)
    write_json(task_trace_path, trace_entry)


def _checkpoint_trace(
    update: dict[str, Any],
    *,
    traces_path: Path,
    traces: list[dict[str, Any]],
    task_trace_path: Path,
    trace_entry: dict[str, Any],
    generated_component_name: str,
    task: dict[str, Any],
    run_dir: Path,
) -> None:
    """Persist one trace update without closing over loop variables."""
    for turn_record in update.get("turn_trace", []):
        rejected_jsx = turn_record.get("rejected_jsx")
        if not isinstance(rejected_jsx, str) or "rejected_artifacts" in turn_record:
            continue
        try:
            turn_record["rejected_artifacts"] = write_rejected_card(
                jsx=rejected_jsx,
                component_name=generated_component_name,
                turn=int(turn_record.get("turn", 0)),
                task=task,
                run_dir=run_dir,
            )
        except Exception as exc:
            # Preview persistence is diagnostic and must not mask the original
            # validation result or stop the generation loop.
            turn_record["rejected_artifact_error"] = f"{type(exc).__name__}: {exc}"
    trace_entry.update(update)
    _persist_current_trace(
        traces_path=traces_path,
        traces=traces,
        task_trace_path=task_trace_path,
        trace_entry=trace_entry,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="按0820设计系统生成声明式 JSX，并编译为标准 A2UI v0.9。")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument(
        "--context",
        type=Path,
        help="当 --input 是最终模型输入时，指定配套的私有 compile context 文件。",
    )
    selector = parser.add_mutually_exclusive_group()
    selector.add_argument("--id", dest="task_id")
    selector.add_argument("--index", type=int)
    selector.add_argument("--all", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--run-id", help="指定运行目录名；默认使用当前时间。")
    parser.add_argument("--max-turns", type=int, default=20)
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=8192,
        help="模型单轮最大输出 Token（默认：8192）。",
    )
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=get_settings().model_request_timeout_seconds,
    )
    parser.add_argument(
        "--submit-mode",
        choices=SUBMIT_MODES,
        default="direct",
        help=(
            "最终提交策略：direct 强制调用 submit_card_jsx，并在接口不兼容时自动回退；"
            "auto 使用旧版自动工具选择且不追加紧凑提交指令（默认：direct）。"
        ),
    )
    parser.add_argument(
        "--browser-fallback-after",
        type=int,
        default=3,
        help=(
            "浏览器布局校验失败达到多少次后进入紧凑组件兜底（默认：3）；"
            "普通静态校验由 --max-turns 控制。"
        ),
    )
    validation_group = parser.add_mutually_exclusive_group()
    validation_group.add_argument(
        "--with-browser-validation",
        dest="with_browser_validation",
        action="store_true",
        help="启用 React/Chromium 几何与真实资源渲染校验（默认启用；保留该参数以兼容旧命令）。",
    )
    validation_group.add_argument(
        "--no-browser-validation",
        dest="with_browser_validation",
        action="store_false",
        help="关闭 React/Chromium 浏览器校验，仅执行静态校验和 A2UI 编译。",
    )
    validation_group.add_argument(
        "--no-validation",
        action="store_true",
        help=("跳过 Runner 静态/浏览器校验，并禁止失败后的模型修复重试；仍执行生成 A2UI 所必需的 JSX 解析和转换。"),
    )
    parser.set_defaults(with_browser_validation=True)
    layout_budget_group = parser.add_mutually_exclusive_group()
    layout_budget_group.add_argument(
        "--no-layout-budget-validation",
        dest="no_layout_budget_validation",
        action="store_true",
        help="关闭 Python 横向/纵向尺寸预算校验（默认关闭；保留该参数以兼容旧命令）。",
    )
    layout_budget_group.add_argument(
        "--with-layout-budget-validation",
        dest="no_layout_budget_validation",
        action="store_false",
        help="启用 Python 横向/纵向尺寸预算校验；不影响其他静态校验或浏览器校验。",
    )
    parser.set_defaults(no_layout_budget_validation=True)
    parser.add_argument("--thinking-mode", choices=THINKING_MODES, default=MODEL_THINKING_MODE)
    parser.add_argument(
        "--plan-max-tokens",
        type=int,
        default=PLAN_MAX_TOKENS,
        help=f"规划阶段最大输出 Token（1～{PLAN_MAX_TOKENS}，默认：{PLAN_MAX_TOKENS}）。",
    )
    parser.add_argument(
        "--few-shot",
        action="store_true",
        help="在 2x4 的 layout_patterns 中加载 few-shot 示例；默认关闭，2x2 不受影响。",
    )
    failure_group = parser.add_mutually_exclusive_group()
    failure_group.add_argument(
        "--continue-on-error",
        dest="continue_on_error",
        action="store_true",
        help="批量运行时记录失败任务并继续处理后续任务（默认启用；保留该参数以兼容旧命令）。",
    )
    failure_group.add_argument(
        "--stop-on-error",
        dest="continue_on_error",
        action="store_false",
        help="批量运行遇到首个失败任务后停止。",
    )
    parser.set_defaults(continue_on_error=True)
    parser.add_argument(
        "--skip-dynamic-value-validation",
        action="store_true",
        help=(
            "跳过未绑定动态样例值的静态化校验；未知 dataId、绑定类型、"
            "组件合同、布局、资源、交互、浏览器和 A2UI 编译校验仍然执行。"
        ),
    )
    parser.add_argument(
        "--skip-empty-data-id-validation",
        action="store_true",
        help="跳过 dataIds 空值校验；不关闭其他绑定、布局和协议校验。",
    )
    binding_group = parser.add_mutually_exclusive_group()
    binding_group.add_argument(
        "--enable-dynamic-data-binding",
        dest="enable_dynamic_data_binding",
        action="store_true",
        help="生成动态数据绑定（默认启用）。",
    )
    binding_group.add_argument(
        "--disable-dynamic-data-binding",
        dest="enable_dynamic_data_binding",
        action="store_false",
        help="仅离线静态预览：保留 JSX 字面值，不生成实时数据绑定。",
    )
    parser.set_defaults(enable_dynamic_data_binding=True)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--check", action="store_true", help="只执行本地兼容性预检，不调用模型。")
    return parser.parse_args(argv)


def preflight(
    input_path: Path,
    context_path: Path | None = None,
    *,
    browser_validation: bool = False,
    include_few_shot: bool = False,
) -> None:
    resources = GenerationResources(include_few_shot=include_few_shot)
    missing = resources.missing_files()
    if not JSX_VALIDATOR_PATH.is_file():
        missing.append(JSX_VALIDATOR_PATH)
    if not input_path.exists():
        missing.append(input_path)
    if context_path is not None and not context_path.exists():
        missing.append(context_path)
    if browser_validation:
        missing.extend(browser_runtime_missing_files())
    if missing:
        raise FileNotFoundError("缺少生成资源：\n" + "\n".join(str(path) for path in missing))
    missing_template_components = sorted(set(generatable_contracts()) - preview_template_components())
    if missing_template_components:
        raise ValueError("template.html 未向生成 JSX 注册以下组件：" + ", ".join(missing_template_components))
    contract_errors = generation_contract_sync_errors()
    if contract_errors:
        raise ValueError("Runtime 与 JSX→A2UI 合同不同步：\n" + "\n".join(contract_errors))


async def async_main(args: argparse.Namespace) -> int:
    validation_enabled = not args.no_validation
    browser_validation = validation_enabled and args.with_browser_validation
    layout_budget_validation = validation_enabled and not args.no_layout_budget_validation
    bridge_options = BridgeOptions(
        max_turns=args.max_turns,
        max_tokens=args.max_tokens,
        thinking_mode=args.thinking_mode,
        request_timeout=args.request_timeout,
        browser_fallback_after=args.browser_fallback_after,
        browser_validation=browser_validation,
        validation_enabled=validation_enabled,
        layout_budget_validation=layout_budget_validation,
        validate_dynamic_values=not args.skip_dynamic_value_validation,
        validate_non_empty_data_ids=not args.skip_empty_data_id_validation,
        enable_dynamic_data_binding=args.enable_dynamic_data_binding,
        include_few_shot=args.few_shot,
        plan_max_tokens=args.plan_max_tokens,
        submit_mode=args.submit_mode,
        verbose=not args.quiet,
    )
    preflight(
        args.input,
        args.context,
        browser_validation=browser_validation,
        include_few_shot=bridge_options.include_few_shot,
    )
    loaded_tasks = load_tasks(args.input.resolve())
    selected_loaded_tasks = select_tasks(
        loaded_tasks,
        task_id=args.task_id,
        index=args.index,
        run_all=args.all,
    )
    selected_object_ids = {id(task) for task in selected_loaded_tasks}
    selected_records = [
        (source_index, task)
        for source_index, task in enumerate(loaded_tasks, start=1)
        if id(task) in selected_object_ids
    ]
    source_indices = [source_index for source_index, _task in selected_records]
    selected_tasks = [task for _source_index, task in selected_records]
    preprocessed_tasks = sum(1 for task in selected_tasks if is_raw_task(task))
    if args.context is not None:
        if preprocessed_tasks:
            raise ValueError("raw task 输入不应指定 --context；Runner 会直接在内存中拆分。")
        context_records = load_tasks(args.context.resolve())
        if len(context_records) != len(loaded_tasks):
            raise ValueError(f"模型输入与私有上下文条数不一致：{len(loaded_tasks)} != {len(context_records)}。")
        selected_contexts = [context_records[index - 1] for index in source_indices]
        prepared_tasks = prepare_tasks_from_views(
            selected_tasks,
            selected_contexts,
            source_indices=source_indices,
        )
    else:
        prepared_tasks = [prepare_task(task, source_index) for source_index, task in selected_records]
    if preprocessed_tasks and not args.quiet:
        print(
            f"[Input] 已在内存中预处理 {preprocessed_tasks}/{len(selected_tasks)} 条已选 raw task，"
            "模型将接收 processed task。",
            file=sys.stderr,
        )
    if args.check:
        print(
            json.dumps(
                {
                    "ok": True,
                    "input": str(args.input.resolve()),
                    "loadedTasks": len(loaded_tasks),
                    "selectedTasks": len(prepared_tasks),
                    "preprocessedTasks": preprocessed_tasks,
                    "fewShotEnabled": bridge_options.include_few_shot,
                    "planMaxTokens": bridge_options.plan_max_tokens,
                    "browserFallbackAfter": bridge_options.browser_fallback_after,
                    "generatableComponents": sorted(generatable_contracts()),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    tasks = prepared_tasks
    task_names = [
        build_component_name(prepared.prompt_task, prepared.source_index or index)
        for index, prepared in enumerate(tasks, start=1)
    ]
    duplicate_names = sorted({name for name in task_names if task_names.count(name) > 1})
    if duplicate_names:
        raise ValueError("任务生成的组件名重复：" + ", ".join(duplicate_names))
    bridge = JsxA2UIBridge(options=bridge_options)
    agent = bridge.create_agent(agent_factory=JsxA2UIAgent)
    run_id, run_dir = create_run_dir(args.output_dir, args.run_id)
    run_started_at = datetime.now(UTC).astimezone()
    run_started_monotonic = time.monotonic()
    manifest: dict[str, Any] = {
        "runId": run_id,
        "status": "running",
        "startedAt": run_started_at.isoformat(),
        "model": getattr(agent, "model", bridge.model_name),
        "provider": getattr(agent, "provider", "platform"),
        "thinkingMode": args.thinking_mode,
        "maxTokens": agent.max_tokens,
        "maxTurns": args.max_turns,
        "submitMode": args.submit_mode,
        "requestTimeoutSeconds": args.request_timeout,
        "browserFallbackAfter": (
            bridge_options.browser_fallback_after if validation_enabled else 0
        ),
        "planMaxTokens": bridge_options.plan_max_tokens,
        "fewShotEnabled": bridge_options.include_few_shot,
        "nonEmptyDataIdValidationEnabled": bridge_options.validate_non_empty_data_ids,
        "dynamicDataBindingEnabled": bridge_options.enable_dynamic_data_binding,
        "browserValidationEnabled": browser_validation,
        "layoutBudgetValidationEnabled": layout_budget_validation,
        "validationMode": (
            "disabled" if not validation_enabled else "browser" if browser_validation else "static-only"
        ),
        "continueOnError": args.continue_on_error,
        "dynamicValueValidationEnabled": not args.skip_dynamic_value_validation,
        "input": str(args.input.resolve()),
        "contextInput": str(args.context.resolve()) if args.context is not None else None,
        "loadedTasks": len(loaded_tasks),
        "preprocessedTasks": preprocessed_tasks,
        "requestedTasks": len(tasks),
        "attemptedTasks": 0,
        "completedTasks": 0,
        "partialTasks": 0,
        "insufficientInputTasks": 0,
        "unverifiedTasks": 0,
        "failedTasks": 0,
        "cards": [],
        "failures": [],
    }
    traces: list[dict[str, Any]] = []
    manifest_path = run_dir / "manifest.json"
    traces_path = run_dir / "traces.json"
    summary_path = run_dir / "summary.json"
    summary_markdown_path = run_dir / "summary.md"

    def persist_summary() -> None:
        try:
            manifest["summary"] = {
                "json": summary_path.name,
                "markdown": summary_markdown_path.name,
            }
            summary = build_run_summary(manifest, traces)
            write_json(summary_path, summary)
            summary_markdown_path.write_text(
                render_run_summary_markdown(summary),
                encoding="utf-8",
            )
            write_json(manifest_path, manifest)
            for line in terminal_summary_lines(summary):
                print(line, file=sys.stderr)
            print(f"[Summary] report={summary_markdown_path}", file=sys.stderr)
        except Exception as exc:
            print(
                f"[Summary] 汇总生成失败，不影响本次运行结果：{type(exc).__name__}: {exc}",
                file=sys.stderr,
            )

    # Persist run metadata before the first API request so first-task failures
    # still leave a discoverable, machine-readable run record.
    write_json(manifest_path, manifest)
    write_json(traces_path, traces)

    for index, prepared in enumerate(tasks, start=1):
        task = prepared.prompt_task
        compile_context = prepared.compile_context
        source_index = prepared.source_index or index
        name = build_component_name(task, source_index)
        task_id = task.get("id", source_index)
        task_started = time.monotonic()
        manifest["attemptedTasks"] = int(manifest["attemptedTasks"]) + 1
        trace_entry: dict[str, Any] = {
            "task": task,
            "status": "running",
            "task_id": task_id,
            "component_name": name,
            "loaded_resources": [],
            "resource_reads": [],
            "reasoning_trace": [],
            "turn_trace": [],
            "validation_reports": [],
        }
        traces.append(trace_entry)
        task_trace_path = run_dir / "jsx" / f"{name}.trace.json"

        write_json(manifest_path, manifest)
        _persist_current_trace(
            traces_path=traces_path,
            traces=traces,
            task_trace_path=task_trace_path,
            trace_entry=trace_entry,
        )
        checkpoint_trace = partial(
            _checkpoint_trace,
            traces_path=traces_path,
            traces=traces,
            task_trace_path=task_trace_path,
            trace_entry=trace_entry,
            generated_component_name=name,
            task=task,
            run_dir=run_dir,
        )

        print(f"[{index}/{len(tasks)}] 生成 {name}...", file=sys.stderr)
        try:
            result = await agent.render(
                task,
                name,
                compile_context=compile_context,
                trace_callback=checkpoint_trace,
            )
            effective_compile_context = result.get("compile_context", compile_context)
            paths = write_card(
                result,
                run_dir,
                task,
                compile_context=effective_compile_context,
            )
        except Exception as exc:
            failure = {
                "taskId": task_id,
                "componentName": name,
                "status": "failed",
                "errorType": type(exc).__name__,
                "error": str(exc),
                "elapsedSeconds": round(time.monotonic() - task_started, 2),
            }
            loaded_resources = getattr(exc, "loaded_resources", None)
            resource_reads = getattr(exc, "resource_reads", None)
            if loaded_resources is not None:
                failure["loadedResources"] = loaded_resources
            manifest["failedTasks"] = int(manifest["failedTasks"]) + 1
            manifest["failures"].append(failure)
            manifest["status"] = "running_with_failures" if args.continue_on_error else "failed"
            trace_entry.update(
                {
                    "task": task,
                    "status": "failed",
                    "task_id": task_id,
                    "component_name": name,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "elapsed_seconds": failure["elapsedSeconds"],
                    "loaded_resources": loaded_resources or [],
                    "resource_reads": resource_reads or [],
                    "turn_trace": getattr(exc, "turn_trace", []),
                    "validation_reports": getattr(exc, "validation_reports", []),
                }
            )
            write_json(manifest_path, manifest)
            _persist_current_trace(
                traces_path=traces_path,
                traces=traces,
                task_trace_path=task_trace_path,
                trace_entry=trace_entry,
            )
            print(
                json.dumps({"runId": run_id, **failure, "runDir": str(run_dir)}, ensure_ascii=False),
                file=sys.stderr,
            )
            if not args.continue_on_error:
                manifest["finishedAt"] = datetime.now(UTC).astimezone().isoformat()
                manifest["elapsedSeconds"] = round(time.monotonic() - run_started_monotonic, 2)
                write_json(manifest_path, manifest)
                persist_summary()
                raise exc
            continue

        semantic_status = str(result.get("semantic_status") or "completed")
        if semantic_status not in {"completed", "partial", "insufficient_input", "unverified"}:
            semantic_status = "unverified"
        validation_status = (
            "passed"
            if result.get("browser_validation", "enabled" if browser_validation else "skipped") == "enabled"
            else "unverified"
        )
        if semantic_status == "completed":
            card_status = "completed" if validation_status == "passed" else "completed_unverified"
            manifest["completedTasks"] = int(manifest["completedTasks"]) + 1
        elif semantic_status in {"partial", "unverified"}:
            card_status = "partial" if validation_status == "passed" else "partial_unverified"
            manifest["partialTasks"] = int(manifest["partialTasks"]) + 1
        else:
            card_status = "insufficient_input"
            manifest["insufficientInputTasks"] = int(manifest["insufficientInputTasks"]) + 1
        if validation_status == "unverified":
            manifest["unverifiedTasks"] = int(manifest["unverifiedTasks"]) + 1

        card_entry = {
            "taskId": task_id,
            "componentName": name,
            "status": card_status,
            "semanticStatus": semantic_status,
            "validationStatus": validation_status,
            **paths,
        }
        manifest["cards"].append(card_entry)
        task_elapsed_seconds = round(time.monotonic() - task_started, 2)
        trace_entry.update(
            {
                "task": task,
                "status": card_status,
                **{key: value for key, value in result.items() if key not in {"source", "jsx", "a2ui"}},
                "agent_elapsed_seconds": result.get("elapsed_seconds"),
                "elapsed_seconds": task_elapsed_seconds,
            }
        )
        write_json(manifest_path, manifest)
        _persist_current_trace(
            traces_path=traces_path,
            traces=traces,
            task_trace_path=task_trace_path,
            trace_entry=trace_entry,
        )
        print(json.dumps({"runId": run_id, **card_entry, "runDir": str(run_dir)}, ensure_ascii=False))

    has_warnings = any(int(manifest[key]) for key in ("partialTasks", "insufficientInputTasks", "unverifiedTasks"))
    manifest["status"] = (
        "partial_failed" if manifest["failedTasks"] else "completed_with_warnings" if has_warnings else "completed"
    )
    manifest["finishedAt"] = datetime.now(UTC).astimezone().isoformat()
    manifest["elapsedSeconds"] = round(time.monotonic() - run_started_monotonic, 2)
    write_json(manifest_path, manifest)
    write_json(traces_path, traces)
    persist_summary()
    await bridge.aclose()
    return 1 if manifest["failedTasks"] else 0


def main(argv: list[str] | None = None) -> int:
    try:
        return asyncio.run(async_main(parse_args(argv)))
    except (FileNotFoundError, ValueError, RuntimeError, ConversionError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
