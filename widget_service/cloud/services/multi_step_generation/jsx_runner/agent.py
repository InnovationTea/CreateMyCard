from __future__ import annotations

import asyncio
import json
import sys
import time
from typing import Any, Callable

from .config import (
    MODEL_THINKING_MODE,
    THINKING_MODES,
)
from .prompt import build_system_prompt, build_user_prompt
from .validation import (
    browser_layout_fingerprints,
    browser_layout_needs_restructure,
    compact_validation_feedback,
    validate_generated_card,
)
from .workflow import (
    AGENT_TOOLS,
    CompiledSubmission,
    OrderedWorkflowState,
    browser_repair_preservation_findings,
    execute_tool,
    submission_reference_ids,
    tool_result_message,
)
from .tool_arguments import ToolArgumentError, parse_tool_arguments as _arguments


SUBMIT_MODES = ("direct", "auto")


def _stage_directive(tool_name: str) -> str | None:
    if tool_name == "submit_card_jsx":
        return (
            "当前只允许调用 submit_card_jsx。不要输出普通文本、分析、解释、"
            "推理过程或 Markdown；请立即用紧凑参数调用该工具。"
        )
    return None


def _is_tool_choice_compatibility_error(exc: Exception) -> bool:
    """Return whether an OpenAI-compatible endpoint rejected forced tool choice."""

    status_code = getattr(exc, "status_code", None)
    message = str(exc).lower()
    compatibility_markers = (
        "tool_choice",
        "named tool",
        "named function",
        "function calling",
    )
    return status_code in {400, 422} and any(
        marker in message for marker in compatibility_markers
    )


def _reasoning_content(message: Any) -> str:
    reasoning = getattr(message, "reasoning_content", None)
    if reasoning:
        return str(reasoning)
    model_extra = getattr(message, "model_extra", None) or {}
    if isinstance(model_extra, dict) and model_extra.get("reasoning_content"):
        return str(model_extra["reasoning_content"])
    if hasattr(message, "model_dump"):
        dumped = message.model_dump()
        if isinstance(dumped, dict) and dumped.get("reasoning_content"):
            return str(dumped["reasoning_content"])
    return ""


def _assistant_payload(message: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "role": "assistant",
        "content": getattr(message, "content", None),
        # Some OpenAI-compatible reasoning models require this field between tool turns.
        "reasoning_content": _reasoning_content(message),
    }
    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        payload["tool_calls"] = [
            call.model_dump(exclude_none=True) if hasattr(call, "model_dump") else call
            for call in tool_calls
        ]
    return payload


def _replace_tool_call_arguments(
    assistant_payload: dict[str, Any],
    call_id: str,
    arguments: dict[str, Any],
) -> None:
    encoded = json.dumps(arguments, ensure_ascii=False, separators=(",", ":"))
    for call in assistant_payload.get("tool_calls", []):
        if isinstance(call, dict):
            if str(call.get("id") or "") != call_id:
                continue
            function = call.get("function")
            if isinstance(function, dict):
                function["arguments"] = encoded
            return
        if str(getattr(call, "id", "") or "") != call_id:
            continue
        function = getattr(call, "function", None)
        if function is not None:
            setattr(function, "arguments", encoded)
        return


def _resolve_provider(provider: str, model: str) -> str:
    """Resolve model-specific OpenAI-compatible request behavior."""
    configured = str(provider).strip().lower() or "auto"
    if configured != "auto":
        return configured
    normalized_model = model.lower()
    if normalized_model.startswith("glm-"):
        return "glm"
    if normalized_model.startswith("deepseek-"):
        return "deepseek"
    return "openai-compatible"


def _usage_payload(response: Any) -> dict[str, Any] | None:
    """Return JSON-safe token usage across OpenAI SDK representations."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    if isinstance(usage, dict):
        return usage
    if hasattr(usage, "model_dump"):
        dumped = usage.model_dump(exclude_none=True)
        return dumped if isinstance(dumped, dict) else None

    result: dict[str, Any] = {}
    for field in (
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "prompt_cache_hit_tokens",
        "prompt_cache_miss_tokens",
    ):
        value = getattr(usage, field, None)
        if value is not None:
            result[field] = value
    completion_details = getattr(usage, "completion_tokens_details", None)
    if completion_details is not None:
        if isinstance(completion_details, dict):
            result["completion_tokens_details"] = completion_details
        elif hasattr(completion_details, "model_dump"):
            result["completion_tokens_details"] = completion_details.model_dump(
                exclude_none=True
            )
    return result or None


def _tool_result_summary(result: dict[str, Any]) -> dict[str, Any]:
    """Keep tool diagnostics without duplicating large reference contents."""
    fields = (
        "ok",
        "phase",
        "retryable",
        "error",
        "instruction",
        "resource",
        "source_files",
        "next",
        "componentName",
        "browserValidation",
        "failedSubmissions",
        "repairCalls",
        "repairLimit",
        "browserFailures",
        "remainingRepairs",
        "repairStrategy",
        "repeatedFindings",
        "findings",
        "warnings",
        "validationMode",
    )
    return {field: result[field] for field in fields if field in result}


def _tool_result_log_level(result: dict[str, Any]) -> str:
    if not result.get("ok"):
        return "ERROR"
    if result.get("severity") == "warning" or result.get("warnings"):
        return "WARNING"
    return "OK"


def _tool_result_log_findings(
    result: dict[str, Any],
    *,
    limit: int = 8,
    detail_limit: int = 800,
) -> list[str]:
    """Format validation findings for concise but actionable terminal output."""

    findings = result.get("findings")
    if not isinstance(findings, list):
        return []
    lines: list[str] = []
    valid_findings = [item for item in findings if isinstance(item, dict)]
    for item in valid_findings[:limit]:
        code = str(item.get("code") or "validation-error")
        message = str(item.get("message") or "validation failed")
        line = f"  - [{code}] {message}"
        if item.get("likelyCause"):
            line += f"；可能原因={item['likelyCause']}"
        if item.get("suggestion"):
            line += f"；修改建议={item['suggestion']}"
        evidence = item.get("evidence", item.get("details"))
        if evidence is not None:
            details = json.dumps(
                evidence,
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            )
            if len(details) > detail_limit:
                details = details[:detail_limit] + "…"
            line += f"；details={details}"
        lines.append(line)
    remaining = len(valid_findings) - len(lines)
    if remaining > 0:
        lines.append(f"  - 另有 {remaining} 项，完整内容见 traces.json")
    return lines


class JsxA2UIAgent:
    def __init__(
        self,
        *,
        model: str,
        provider: str = "deepseek",
        max_turns: int = 20,
        max_tokens: int | None = None,
        thinking_mode: str = MODEL_THINKING_MODE,
        request_timeout: float = 900.0,
        max_validation_repairs: int = 5,
        browser_validation: bool = False,
        validation_enabled: bool = True,
        layout_budget_validation: bool = True,
        validate_dynamic_values: bool = True,
        submit_mode: str = "direct",
        verbose: bool = True,
        client: Any | None = None,
    ) -> None:
        if client is None:
            raise RuntimeError(
                "JsxA2UIAgent 必须由平台 Bridge 注入模型客户端；"
                "不支持独立 MODEL_* 或直连 OpenAI 配置"
            )
        mode = str(thinking_mode).lower()
        if mode not in THINKING_MODES:
            raise ValueError(f"不支持的 thinking mode：{thinking_mode!r}")
        self.client = client
        self.model = model
        self.provider = _resolve_provider(provider, model)
        self.max_turns = max_turns
        self.max_tokens = max_tokens if max_tokens is not None else 8192
        self.thinking_mode = mode
        if max_validation_repairs < 0:
            raise ValueError("max_validation_repairs must be non-negative")
        resolved_submit_mode = str(submit_mode).strip().lower()
        if resolved_submit_mode not in SUBMIT_MODES:
            raise ValueError(f"unsupported submit mode: {submit_mode!r}")
        self.max_validation_repairs = max_validation_repairs
        self.browser_validation = browser_validation
        self.validation_enabled = validation_enabled
        self.layout_budget_validation = layout_budget_validation
        self.validate_dynamic_values = validate_dynamic_values
        self.submit_mode = resolved_submit_mode
        self.verbose = verbose
        # None means unprobed. The result is cached across tasks in one batch.
        self._deepseek_forced_tool_choice_supported: bool | None = None

    def _log(self, message: str) -> None:
        if self.verbose:
            print(message, file=sys.stderr, flush=True)

    async def _request(self, request: dict[str, Any], turn: int) -> Any:
        pending = asyncio.create_task(self.client.chat.completions.create(**request))
        waited = 0
        while True:
            done, _ = await asyncio.wait({pending}, timeout=10)
            if pending in done:
                return await pending
            waited += 10
            self._log(f"[JSX Agent {turn}/{self.max_turns}] 模型仍在生成，已等待 {waited}s")

    async def render(
        self,
        task: dict[str, Any],
        component_name: str,
        compile_context: dict[str, Any] | None = None,
        trace_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        validation_enabled = getattr(self, "validation_enabled", True)
        submit_mode = getattr(self, "submit_mode", "direct")
        browser_validation = (
            validation_enabled
            and getattr(self, "browser_validation", False)
        )
        layout_budget_validation = (
            validation_enabled
            and getattr(self, "layout_budget_validation", True)
        )
        state = OrderedWorkflowState(
            component_name,
            compile_context=compile_context,
            prompt_task=task,
            defer_browser_validation=validation_enabled,
            validation_enabled=validation_enabled,
            validate_layout_budget=layout_budget_validation,
            validate_dynamic_values=getattr(self, "validate_dynamic_values", True),
        )
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": build_system_prompt(
                    component_name,
                    task.get("size"),
                    validation_enabled=validation_enabled,
                ),
            },
            {"role": "user", "content": build_user_prompt(task)},
        ]
        reasoning_trace: list[dict[str, Any]] = []
        turn_trace: list[dict[str, Any]] = []
        validation_reports: list[dict[str, Any]] = []
        failed_submissions = 0
        repair_calls = 0
        tool_argument_repairs = 0
        protocol_retries = 0
        repair_pending = False
        browser_failures = 0
        previous_layout_fingerprints: frozenset[str] = frozenset()
        structural_browser_repair = False
        browser_repair_baseline: CompiledSubmission | None = None
        started = time.monotonic()

        def checkpoint() -> None:
            if trace_callback is None:
                return
            trace_callback({
                "status": "running",
                "loaded_resources": list(state.loaded_resources),
                "resource_reads": list(state.resource_reads),
                "reasoning_trace": reasoning_trace,
                "turn_trace": turn_trace,
                "validation_reports": validation_reports,
            })

        self._log(
            f"[JSX Agent] provider={self.provider}，model={self.model}，"
            f"thinking_request={self.thinking_mode}，max_tokens={self.max_tokens}，"
            f"max_turns={self.max_turns}，"
            f"submit_mode={submit_mode}，"
            f"validation={'enabled' if validation_enabled else 'disabled'}，"
            f"layout_budget_validation={'enabled' if layout_budget_validation else 'disabled'}，"
            f"browser_validation={'enabled' if browser_validation else 'disabled'}"
        )

        last_directive_target: str | None = None
        for turn in range(1, self.max_turns + 1):
            if repair_pending:
                repair_calls += 1
            expected_target = (
                state.expected_stage.key
                if state.expected_stage is not None
                else "submit_card_jsx"
            )
            expected_tool = (
                "read_generation_resource"
                if state.expected_stage is not None
                else "submit_card_jsx"
            )
            directive = _stage_directive(expected_tool) if submit_mode == "direct" else None
            if directive is not None and last_directive_target != expected_target:
                messages.append({"role": "user", "content": directive})
                last_directive_target = expected_target
            expected_tools = [
                tool
                for tool in AGENT_TOOLS
                if tool["function"]["name"] == expected_tool
            ]
            request: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "tools": expected_tools,
                "tool_choice": {
                    "type": "function",
                    "function": {"name": expected_tool},
                },
                "max_tokens": (
                    self.max_tokens
                    if expected_tool == "submit_card_jsx"
                    else min(self.max_tokens, 512)
                ),
            }
            if expected_tool == "submit_card_jsx" and submit_mode == "auto":
                request["tool_choice"] = "auto"
            if self.provider == "glm":
                request["extra_body"] = {
                    "thinking": {
                        "type": "disabled" if self.thinking_mode == "disable" else "enabled"
                    }
                }
            elif self.provider == "dashscope":
                request["extra_body"] = {
                    "enable_thinking": self.thinking_mode != "disable"
                }
                if self.thinking_mode != "disable":
                    request["reasoning_effort"] = self.thinking_mode
            elif self.provider == "deepseek":
                request["extra_body"] = {
                    "thinking": {
                        "type": "disabled" if self.thinking_mode == "disable" else "enabled"
                    }
                }
                # Resource reads stay on the broadly compatible auto mode. The final
                # submission prefers a forced call so the model cannot spend thousands
                # of visible tokens narrating before submit_card_jsx. If the endpoint
                # rejects forced tool choice, the request loop falls back once and
                # caches auto mode for the rest of the batch.
                forced_support = getattr(
                    self, "_deepseek_forced_tool_choice_supported", None
                )
                if (
                    expected_tool == "read_generation_resource"
                    or submit_mode == "auto"
                    or forced_support is False
                ):
                    request["tool_choice"] = "auto"
                if self.thinking_mode != "disable":
                    request["reasoning_effort"] = self.thinking_mode
            elif self.thinking_mode != "disable":
                request["reasoning_effort"] = self.thinking_mode
            self._log(f"[JSX Agent {turn}/{self.max_turns}] 当前目标：{expected_target}")
            request_started = time.monotonic()
            tool_choice_fallback = False
            try:
                try:
                    response = await self._request(request, turn)
                except Exception as exc:
                    if (
                        self.provider == "deepseek"
                        and submit_mode == "direct"
                        and expected_tool == "submit_card_jsx"
                        and request.get("tool_choice") != "auto"
                        and _is_tool_choice_compatibility_error(exc)
                    ):
                        self._deepseek_forced_tool_choice_supported = False
                        request = {**request, "tool_choice": "auto"}
                        tool_choice_fallback = True
                        self._log(
                            f"[JSX Agent {turn}/{self.max_turns}] "
                            "当前 DeepSeek 接口不支持强制工具调用，"
                            "已回退 tool_choice=auto；本批后续任务将复用该结果"
                        )
                        response = await self._request(request, turn)
                    else:
                        raise
            except Exception as exc:
                api_elapsed = round(time.monotonic() - request_started, 2)
                turn_trace.append({
                    "turn": turn,
                    "target": expected_target,
                    "api_elapsed_seconds": api_elapsed,
                    "status": "request_error",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                })
                setattr(exc, "turn_trace", turn_trace)
                setattr(exc, "loaded_resources", list(state.loaded_resources))
                setattr(exc, "resource_reads", list(state.resource_reads))
                setattr(exc, "validation_reports", validation_reports)
                raise

            if (
                self.provider == "deepseek"
                and submit_mode == "direct"
                and expected_tool == "submit_card_jsx"
                and request.get("tool_choice") != "auto"
            ):
                self._deepseek_forced_tool_choice_supported = True

            api_elapsed = round(time.monotonic() - request_started, 2)
            choice = response.choices[0]
            message = choice.message
            finish_reason = str(getattr(choice, "finish_reason", "") or "")
            reasoning = _reasoning_content(message)
            assistant_content = str(getattr(message, "content", "") or "")
            if reasoning:
                reasoning_trace.append({
                    "turn": turn,
                    "target": expected_target,
                    "api_elapsed_seconds": api_elapsed,
                    "finish_reason": finish_reason,
                    "content": str(reasoning),
                })
            assistant_payload = _assistant_payload(message)
            messages.append(assistant_payload)
            calls = list(message.tool_calls or [])
            turn_record: dict[str, Any] = {
                "turn": turn,
                "target": expected_target,
                "api_elapsed_seconds": api_elapsed,
                "finish_reason": finish_reason,
                "usage": _usage_payload(response),
                "content_length": len(assistant_content),
                "reasoning_length": len(reasoning),
                "tool_call_count": len(calls),
                "tool_names": [str(getattr(call.function, "name", "")) for call in calls],
            }
            if tool_choice_fallback:
                turn_record["tool_choice_fallback"] = "auto"
            if assistant_content:
                turn_record["assistant_content"] = assistant_content
            if not calls:
                if finish_reason == "length":
                    recovery = (
                        f"上一轮在 {expected_target} 阶段因输出长度限制被截断。"
                        "不要重复解释已经读取的资料；请压缩内容，只调用当前阶段要求的一个工具。"
                        "如果当前阶段是 submit_card_jsx，请直接提交更紧凑的 JSX。"
                    )
                    turn_record["recovery"] = "length_compaction"
                else:
                    recovery = (
                        f"工作流尚未完成，当前目标是 {expected_target}。"
                        "请只调用当前阶段要求的一个工具，不要直接回答。"
                    )
                    turn_record["recovery"] = "request_expected_tool"
                turn_record["status"] = "no_tool_call"
                turn_trace.append(turn_record)
                checkpoint()
                self._log(
                    f"[JSX Agent {turn}/{self.max_turns}] 模型未调用工具；"
                    f"finish_reason={finish_reason or 'unknown'}，API耗时={api_elapsed:.2f}s"
                )
                messages.append({"role": "user", "content": recovery})
                continue

            first = calls[0]
            function = first.function
            submitted_jsx: str | None = None
            argument_repairs: list[str] = []
            try:
                arguments = _arguments(
                    function.arguments,
                    tool_name=function.name,
                    repairs=argument_repairs,
                )
                if argument_repairs:
                    _replace_tool_call_arguments(
                        assistant_payload,
                        str(first.id),
                        arguments,
                    )
                    tool_argument_repairs += 1
                    turn_record["tool_argument_repair"] = {
                        "status": "applied",
                        "rules": argument_repairs,
                    }
                    self._log(
                        f"[JSX Agent {turn}/{self.max_turns}] "
                        f"{function.name} 工具参数已本地修复：{', '.join(argument_repairs)}"
                    )
                if function.name != expected_tool:
                    result = {
                        "ok": False,
                        "error": (
                            f"expected tool {expected_tool!r} for {expected_target!r}, "
                            f"received {function.name!r}"
                        ),
                    }
                elif function.name == "submit_card_jsx" and isinstance(arguments.get("jsx"), str):
                    submitted_jsx = arguments["jsx"]
                    result = execute_tool(function.name, arguments, state)
                else:
                    result = execute_tool(function.name, arguments, state)
            except Exception as exc:
                result = {
                    "ok": False,
                    "error": f"tool execution failed: {type(exc).__name__}: {exc}",
                }
                if isinstance(exc, ToolArgumentError):
                    _replace_tool_call_arguments(
                        assistant_payload,
                        str(first.id),
                        {},
                    )
                    protocol_retries += 1
                    result.update({
                        "phase": "tool_arguments",
                        "instruction": (
                            "工具参数不是合法 JSON，且无法安全地在本地恢复。"
                            "请只重新调用当前工具，保证外层 JSON 完整，并正确转义字符串。"
                        ),
                    })
                    turn_record["recovery"] = "retry_invalid_tool_arguments"
                if finish_reason == "length":
                    result.update({
                        "phase": "truncated_tool_call",
                        "instruction": (
                            "上一轮工具参数可能被长度限制截断；"
                            "请只重新调用当前工具，并压缩参数内容。"
                        ),
                    })
                    turn_record["recovery"] = "retry_truncated_tool_call"
            terminal_error: RuntimeError | None = None
            browser_failure = False
            if function.name == "submit_card_jsx" and result.get("ok") and state.pending_submission is not None:
                preservation_errors: list[dict[str, Any]] = []
                preservation_warnings: list[dict[str, str]] = []
                if browser_validation and browser_repair_baseline is not None:
                    preservation_errors, preservation_warnings = (
                        browser_repair_preservation_findings(
                            browser_repair_baseline,
                            state.pending_submission,
                            compile_context,
                        )
                    )
                try:
                    report = await validate_generated_card(
                        source=state.pending_submission.source,
                        task=task,
                        component_name=component_name,
                        browser=browser_validation,
                    )
                except Exception as exc:
                    state.reject_pending_submission()
                    result = {
                        "ok": False,
                        "phase": "validation_infrastructure",
                        "error": f"JSX 校验器执行失败：{type(exc).__name__}: {exc}",
                    }
                    terminal_error = RuntimeError(result["error"])
                else:
                    if preservation_errors or preservation_warnings:
                        report_findings = report.get("findings")
                        if not isinstance(report_findings, list):
                            report_findings = []
                        report = {
                            **report,
                            "findings": [
                                *report_findings,
                                *preservation_errors,
                                *preservation_warnings,
                            ],
                            "ok": bool(report.get("ok")) and not preservation_errors,
                        }
                    validation_reports.append(report)
                    if report.get("ok"):
                        browser_warnings = [
                            item
                            for item in report.get("findings", [])
                            if isinstance(item, dict)
                            and item.get("severity") == "warning"
                        ]
                        for warning in browser_warnings:
                            if warning not in state.pending_submission.warnings:
                                state.pending_submission.warnings.append(warning)
                        if state.pending_submission.warnings:
                            result = {
                                **result,
                                "warnings": list(state.pending_submission.warnings),
                            }
                        state.accept_pending_submission()
                        result = {
                            **result,
                            "pendingBrowserValidation": False,
                            "browserValidation": "passed" if browser_validation else "skipped",
                            "validationMode": "browser" if browser_validation else "static-only",
                        }
                    else:
                        report_errors = [
                            item
                            for item in report.get("findings", [])
                            if isinstance(item, dict)
                            and item.get("severity") != "warning"
                        ]
                        has_browser_error = any(
                            str(item.get("code") or "").startswith("browser-")
                            for item in report_errors
                        )
                        current_layout_fingerprints = browser_layout_fingerprints(report)
                        needs_restructure, repeated_findings = (
                            browser_layout_needs_restructure(
                                report,
                                previous_fingerprints=previous_layout_fingerprints,
                            )
                        )
                        if current_layout_fingerprints:
                            previous_layout_fingerprints = current_layout_fingerprints
                            structural_browser_repair = (
                                structural_browser_repair or needs_restructure
                            )
                        use_structural_repair = bool(
                            current_layout_fingerprints and structural_browser_repair
                        )
                        if has_browser_error and browser_repair_baseline is None:
                            browser_repair_baseline = state.pending_submission
                        baseline_data, baseline_actions = submission_reference_ids(
                            browser_repair_baseline or state.pending_submission
                        )
                        state.reject_pending_submission()
                        feedback = compact_validation_feedback(
                            report,
                            structural_repair=use_structural_repair,
                        )
                        codes = {str(item.get("code")) for item in feedback}
                        phase = (
                            "duplicate_action"
                            if "duplicate-action-control" in codes
                            else "browser_layout" if has_browser_error else "static_validation"
                        )
                        if has_browser_error:
                            repair_instruction = (
                                "当前布局需要整体重构，不要继续逐个移动组件。重新分配正文区域，"
                                "一次解决 findings 中的全部冲突；可以完整省略真正可舍弃的信息，"
                                "但不得删除交互、把动态值改成静态文本或用裁剪隐藏问题。"
                                if use_structural_repair
                                else
                                "根据 findings 一次修复全部明确错误，并再次调用 submit_card_jsx；"
                                "保持现有动态绑定和交互，不要通过隐藏或删除必需信息规避问题。"
                            ) + (
                                " 修复基线使用的 dataIds="
                                f"{sorted(baseline_data)!r}，actionIds={sorted(baseline_actions)!r}。"
                            )
                        else:
                            repair_instruction = (
                                "根据 findings 修改 JSX，并再次调用 submit_card_jsx；"
                                "不要通过删掉必需信息规避问题。"
                            )
                        result = {
                            "ok": False,
                            "phase": phase,
                            "error": (
                                "JSX 未通过真实 React 浏览器校验"
                                if has_browser_error
                                else "JSX 未通过静态声明式校验"
                            ),
                            "findings": feedback,
                            "instruction": repair_instruction,
                        }
                        if has_browser_error:
                            result["repairStrategy"] = (
                                "structural" if use_structural_repair else "targeted"
                            )
                        if has_browser_error and repeated_findings:
                            result["repeatedFindings"] = repeated_findings
                        if has_browser_error:
                            browser_failure = True
                            browser_failures += 1
                            result.update({
                                "browserFailures": browser_failures,
                                "remainingRepairs": max(
                                    0,
                                    self.max_validation_repairs - browser_failures + 1,
                                ),
                            })
                            if browser_failures > self.max_validation_repairs:
                                terminal_error = RuntimeError(
                                    "JSX 浏览器校验连续失败，已用完 "
                                    f"{self.max_validation_repairs} 次修复机会；"
                                    f"最后错误：{feedback}"
                                )
            if (
                function.name == "submit_card_jsx"
                and not result.get("ok")
                and result.get("retryable") is False
                and terminal_error is None
            ):
                terminal_error = RuntimeError(
                    "JSX 已完成转换，但转换器生成的 A2UI 未通过协议校验；"
                    "该错误不能通过重新生成 JSX 修复："
                    f"{result.get('error') or 'unknown A2UI protocol output error'}"
                )
            repairable_failure = (
                function.name == "submit_card_jsx"
                and not result.get("ok")
                and result.get("retryable", True)
                and terminal_error is None
                and submitted_jsx is not None
            )
            if repairable_failure and not validation_enabled:
                terminal_error = RuntimeError(
                    "首次 JSX 提交无法转换为 A2UI；--no-validation 已禁用模型修复重试："
                    f"{result.get('error') or 'unknown conversion error'}"
                )
                repairable_failure = False
            if repairable_failure:
                failed_submissions += 1
                repair_pending = True
                result.update({
                    "failedSubmissions": failed_submissions,
                    "repairCalls": repair_calls,
                })
                if not browser_failure:
                    result["repairLimit"] = "max_turns"
            elif result.get("ok"):
                repair_pending = False
            messages.append(tool_result_message(first.id, result))
            for extra in calls[1:]:
                messages.append(tool_result_message(extra.id, {"ok": False, "error": "每轮只能调用一个工具"}))
            level = _tool_result_log_level(result)
            if result.get("ok") and result.get("warnings"):
                first_warning = result["warnings"][0]
                detail = (
                    first_warning.get("message", "warning")
                    if isinstance(first_warning, dict)
                    else str(first_warning)
                )
            else:
                detail = "ok" if result.get("ok") else result.get("error")
            self._log(
                f"[JSX Agent {turn}/{self.max_turns}] "
                f"{function.name} [{level}]: {detail}"
            )
            if not result.get("ok"):
                for finding_line in _tool_result_log_findings(result):
                    self._log(finding_line)
            trace_tool_result = _tool_result_summary(result)
            if (
                function.name == "read_generation_resource"
                and result.get("ok")
                and state.resource_reads
            ):
                trace_tool_result["source_files"] = list(
                    state.resource_reads[-1]["source_files"]
                )
            turn_record.update({
                "status": "tool_completed" if result.get("ok") else "tool_failed",
                "tool": str(function.name),
                "tool_result": trace_tool_result,
            })
            if function.name == "submit_card_jsx" and not result.get("ok") and submitted_jsx is not None:
                turn_record["rejected_jsx"] = submitted_jsx
            turn_trace.append(turn_record)
            checkpoint()

            if terminal_error is not None:
                setattr(terminal_error, "turn_trace", turn_trace)
                setattr(terminal_error, "loaded_resources", list(state.loaded_resources))
                setattr(terminal_error, "resource_reads", list(state.resource_reads))
                setattr(terminal_error, "validation_reports", validation_reports)
                raise terminal_error

            if state.submission is not None:
                elapsed = round(time.monotonic() - started, 2)
                self._log(
                    f"[JSX Agent] 工作流完成，总耗时={elapsed:.2f}s，"
                    f"turns={turn}，failed_submissions={failed_submissions}，"
                    f"repair_calls={repair_calls}，tool_argument_repairs={tool_argument_repairs}，"
                    f"protocol_retries={protocol_retries}"
                )
                return {
                    "component_name": component_name,
                    "source": state.submission.source,
                    "jsx": state.submission.jsx,
                    "a2ui": state.submission.messages,
                    "decision": state.submission.decision,
                    "coverage": state.submission.coverage,
                    "unmet_requirements": state.submission.unmet_requirements,
                    "semantic_status": state.submission.semantic_status,
                    "warnings": state.submission.warnings,
                    "loaded_resources": state.loaded_resources,
                    "resource_reads": state.resource_reads,
                    "model": self.model,
                    "provider": self.provider,
                    "thinking_mode": self.thinking_mode,
                    "turns": turn,
                    "failed_submissions": failed_submissions,
                    "repair_calls": repair_calls,
                    "tool_argument_repairs": tool_argument_repairs,
                    "protocol_retries": protocol_retries,
                    "elapsed_seconds": elapsed,
                    "reasoning_trace": reasoning_trace,
                    "turn_trace": turn_trace,
                    "validation_reports": validation_reports,
                    "browser_validation": "enabled" if browser_validation else "skipped",
                    "layout_budget_validation": (
                        "enabled" if layout_budget_validation else "disabled"
                    ),
                    "validation_mode": (
                        "disabled"
                        if not validation_enabled
                        else "browser"
                        if browser_validation
                        else "static-only"
                    ),
                }

        error = RuntimeError(
            f"JSX Agent 在 {self.max_turns} 轮内未完成；已读取 {state.loaded_resources}"
        )
        setattr(error, "turn_trace", turn_trace)
        setattr(error, "loaded_resources", list(state.loaded_resources))
        setattr(error, "resource_reads", list(state.resource_reads))
        setattr(error, "validation_reports", validation_reports)
        raise error
