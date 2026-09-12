from __future__ import annotations

import asyncio
import json
import sys
import time
from collections.abc import Callable
from typing import Any

from .config import MODEL_THINKING_MODE, THINKING_MODES
from .prompt import (
    build_plan_context,
    build_plan_prompt,
    build_system_prompt,
    build_user_prompt,
)
from .resources import GenerationResources
from .tool_arguments import ToolArgumentError
from .tool_arguments import parse_tool_arguments as _arguments
from .validation import (
    browser_layout_fingerprints,
    browser_layout_needs_restructure,
    browser_overlap_involves_emphasized_data,
    browser_layout_requires_pattern_change,
    compact_validation_feedback,
    validate_generated_card,
)
from .workflow import (
    CompiledSubmission,
    OrderedWorkflowState,
    browser_repair_preservation_findings,
    build_agent_tools,
    execute_tool,
    submission_reference_ids,
    tool_result_message,
    validate_plan_arguments,
)


SUBMIT_MODES = ("direct", "auto")
PLAN_MAX_TOKENS = 2048
LAYOUT_FALLBACK_SUBMISSION_LIMITS = {
    "compact_component": 2,
    "drop_optional_component": 3,
}

MAX_CONSECUTIVE_NO_TOOL_CALLS = 3


class MissingToolCallError(RuntimeError):
    """The endpoint repeatedly returned no tool call for the current stage."""


def _stage_directive(tool_name: str, fallback_strategy: str | None = None) -> str | None:
    if tool_name == "submit_card_plan":
        return build_plan_prompt()
    if tool_name == "submit_card_jsx":
        return (
            "当前只允许调用 submit_card_jsx。不要输出普通文本、分析、解释、"
            "推理过程或 Markdown；请立即用紧凑参数调用该工具。"
        )
    if tool_name == "apply_layout_fallback" and fallback_strategy is not None:
        return (
            "当前只允许调用 apply_layout_fallback。不要输出普通文本、分析、解释、"
            "推理过程或 Markdown；strategy 必须填写 "
            f"{fallback_strategy!r}。"
        )
    return None


def _tool_choice_label(tool_choice: Any) -> str:
    """Return a compact, JSON-safe label for one outbound tool choice."""

    if tool_choice == "auto":
        return "auto"
    if isinstance(tool_choice, dict):
        function = tool_choice.get("function")
        if isinstance(function, dict):
            name = str(function.get("name") or "").strip()
            if name:
                return f"required:{name}"
    return str(tool_choice or "unknown")


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
    if status_code not in {400, 422}:
        return False
    for marker in compatibility_markers:
        if marker in message:
            return True
    return False


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
        "fallbackStage",
        "fallbackAttempt",
        "fallbackAttemptLimit",
        "fallbackRemainingAttempts",
        "nextFallbackStrategy",
        "strategy",
        "layoutBudgetFailures",
        "repairStrategy",
        "repeatedFindings",
        "findings",
        "warnings",
        "validationMode",
    )
    return {field: result[field] for field in fields if field in result}


def _is_static_layout_failure(result: dict[str, Any]) -> bool:
    """Return whether a failed submission contains a proven layout-budget error."""
    if result.get("ok"):
        return False
    if result.get("phase") == "layout_budget":
        return True
    findings = result.get("findings")
    if not isinstance(findings, list):
        return False
    return any(
        isinstance(item, dict)
        and item.get("severity") == "error"
        and item.get("code") == "layout-budget"
        for item in findings
    )


def _static_layout_repair_feedback(
    result: dict[str, Any],
    consecutive_failures: int,
) -> dict[str, Any]:
    """Escalate repeated static layout repairs without changing validation severity."""
    updated = {
        **result,
        "layoutBudgetFailures": consecutive_failures,
        "repairStrategy": "targeted",
    }
    if consecutive_failures == 1:
        return updated
    if consecutive_failures == 2:
        updated["repairStrategy"] = "rebudget"
        updated["instruction"] = (
            "这是连续第 2 次确定性布局预算失败。不要只修改当前报错中的一个数字；"
            "请从每个受影响组件的共同父容器重新计算标题、正文、按钮的固定最小尺寸，"
            "以及全部 gap、padding、top 和 bottom，并一次解决 findings 中的所有 ERROR。"
            "WARNING 仍只作提示；必须保留用户明确要求的信息、动态 dataIds 和 actionId，"
            "不得依赖 overflow、裁剪或压缩固定组件规避问题。"
        )
        return updated
    updated["repairStrategy"] = "structural"
    updated["instruction"] = (
        f"这是连续第 {consecutive_failures} 次确定性布局预算失败，当前布局仍未闭合。"
        "停止逐个调整 2–4vp 或只移动单个组件；请重新分配整个受影响内容区，"
        "重新分组共同父容器，并在必要时更换 Layout Pattern。"
        "如果原结构经过完整重算可以闭合，也可以保留，但必须一次满足所有固定最小尺寸"
        "和规范间距。必须保留用户明确要求的信息、动态 dataIds 和 actionId；"
        "不得通过删除必需内容、静态化动态值、overflow 或裁剪绕过校验。"
    )
    return updated


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
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        provider: str | None = None,
        max_turns: int = 20,
        max_tokens: int | None = None,
        thinking_mode: str = MODEL_THINKING_MODE,
        request_timeout: float = 900.0,
        max_validation_repairs: int = 3,
        browser_validation: bool = False,
        validation_enabled: bool = True,
        layout_budget_validation: bool = True,
        validate_dynamic_values: bool = True,
        validate_non_empty_data_ids: bool = True,
        enable_dynamic_data_binding: bool = True,
        submit_mode: str = "direct",
        plan_max_tokens: int = PLAN_MAX_TOKENS,
        resources: GenerationResources | None = None,
        verbose: bool = True,
        client: Any | None = None,
    ) -> None:
        resolved_model = model
        resolved_provider = provider
        if client is None:
            from . import config as runtime_config

            try:
                from openai import AsyncOpenAI
            except ModuleNotFoundError as exc:
                raise RuntimeError("缺少 openai Python SDK；请先安装 openai") from exc
            resolved_key = api_key or getattr(runtime_config, "MODEL_API_KEY", None)
            if not resolved_key:
                raise RuntimeError("缺少 MODEL_API_KEY 配置")
            resolved_model = resolved_model or getattr(runtime_config, "MODEL_NAME", None)
            resolved_provider = resolved_provider or getattr(
                runtime_config,
                "MODEL_PROVIDER",
                "auto",
            )
            resolved_base_url = base_url or getattr(runtime_config, "MODEL_BASE_URL", None)
            client = AsyncOpenAI(
                api_key=resolved_key,
                base_url=resolved_base_url,
                timeout=request_timeout,
            )
        if not resolved_model:
            raise RuntimeError("缺少模型名称")
        resolved_provider = resolved_provider or "auto"
        mode = str(thinking_mode).lower()
        if mode not in THINKING_MODES:
            raise ValueError(f"不支持的 thinking mode：{thinking_mode!r}")
        self.client = client
        self.model = resolved_model
        self.provider = _resolve_provider(resolved_provider, resolved_model)
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
        self.validate_non_empty_data_ids = validate_non_empty_data_ids
        self.enable_dynamic_data_binding = enable_dynamic_data_binding
        self.submit_mode = resolved_submit_mode
        if not 1 <= plan_max_tokens <= PLAN_MAX_TOKENS:
            raise ValueError(
                f"plan_max_tokens must be between 1 and {PLAN_MAX_TOKENS}"
            )
        self.plan_enabled = True
        self.plan_max_tokens = plan_max_tokens
        self.resources = resources or GenerationResources()
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
            resources=getattr(self, "resources", None) or GenerationResources(),
            compile_context=compile_context,
            prompt_task=task,
            defer_browser_validation=validation_enabled,
            validation_enabled=validation_enabled,
            validate_layout_budget=layout_budget_validation,
            validate_dynamic_values=getattr(self, "validate_dynamic_values", True),
            validate_non_empty_data_ids=getattr(
                self,
                "validate_non_empty_data_ids",
                True,
            ),
            enable_dynamic_data_binding=getattr(self, "enable_dynamic_data_binding", True),
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
        plan: dict[str, Any] | None = None
        failed_submissions = 0
        repair_calls = 0
        fallback_calls = 0
        fallback_history: list[str] = []
        fallback_attempts = {
            "compact_component": 0,
            "drop_optional_component": 0,
        }
        tool_argument_repairs = 0
        protocol_retries = 0
        repair_pending = False
        browser_failures = 0
        static_layout_failure_streak = 0
        previous_layout_fingerprints: frozenset[str] = frozenset()
        structural_browser_repair = False
        browser_repair_baseline: CompiledSubmission | None = None
        last_preserved_submission: CompiledSubmission | None = None
        drop_fallback_baseline: CompiledSubmission | None = None
        agent_tools = build_agent_tools(task.get("size"))
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
                "plan": plan,
            })

        self._log(
            f"[JSX Agent] provider={self.provider}，model={self.model}，"
            f"thinking_request={self.thinking_mode}，max_tokens={self.max_tokens}，"
            f"max_turns={self.max_turns}，"
            f"submit_mode={submit_mode}，"
            f"validation={'enabled' if validation_enabled else 'disabled'}，"
            f"layout_budget_validation={'enabled' if layout_budget_validation else 'disabled'}，"
            f"non_empty_data_id_validation="
            f"{'enabled' if getattr(self, 'validate_non_empty_data_ids', True) else 'disabled'}，"
            f"dynamic_data_binding={'enabled' if getattr(self, 'enable_dynamic_data_binding', True) else 'disabled'}，"
            f"browser_validation={'enabled' if browser_validation else 'disabled'}，"
            f"plan={'enabled' if getattr(self, 'plan_enabled', False) else 'disabled'}，"
            f"plan_max_tokens={getattr(self, 'plan_max_tokens', PLAN_MAX_TOKENS)}，"
            f"browser_fallback_after={self.max_validation_repairs}，"
            "fallback_submission_limits="
            f"{LAYOUT_FALLBACK_SUBMISSION_LIMITS}"
        )

        last_directive_target: str | None = None
        consecutive_no_tool_calls = 0
        recovery_message_index: int | None = None
        for turn in range(1, self.max_turns + 1):
            expected_target = (
                state.expected_stage.key
                if state.expected_stage is not None
                else "submit_card_plan"
                if getattr(self, "plan_enabled", False) and plan is None
                else f"layout_fallback:{state.required_layout_fallback}"
                if state.required_layout_fallback is not None
                else "submit_card_jsx"
            )
            expected_tool = (
                "read_generation_resource"
                if state.expected_stage is not None
                else "submit_card_plan"
                if getattr(self, "plan_enabled", False) and plan is None
                else "apply_layout_fallback"
                if state.required_layout_fallback is not None
                else "submit_card_jsx"
            )
            if repair_pending and expected_tool == "submit_card_jsx":
                repair_calls += 1
            directive = (
                _stage_directive(expected_tool, state.required_layout_fallback)
                if submit_mode == "direct" or expected_tool == "submit_card_plan"
                else None
            )
            if directive is not None and last_directive_target != expected_target:
                messages.append({"role": "user", "content": directive})
                last_directive_target = expected_target
            expected_tools = [
                tool
                for tool in agent_tools
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
                    else getattr(self, "plan_max_tokens", PLAN_MAX_TOKENS)
                    if expected_tool == "submit_card_plan"
                    else min(self.max_tokens, 512)
                ),
            }
            if expected_tool == "submit_card_jsx" and submit_mode == "auto":
                request["tool_choice"] = "auto"
            turn_thinking_mode = (
                "disable" if expected_tool == "submit_card_plan" else self.thinking_mode
            )
            if self.provider == "glm":
                request["extra_body"] = {
                    "thinking": {
                        "type": "disabled" if turn_thinking_mode == "disable" else "enabled"
                    }
                }
            elif self.provider == "dashscope":
                request["extra_body"] = {
                    "enable_thinking": turn_thinking_mode != "disable"
                }
                if turn_thinking_mode != "disable":
                    request["reasoning_effort"] = turn_thinking_mode
            elif self.provider == "deepseek":
                request["extra_body"] = {
                    "thinking": {
                        "type": "disabled" if turn_thinking_mode == "disable" else "enabled"
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
                if turn_thinking_mode != "disable":
                    request["reasoning_effort"] = turn_thinking_mode
            elif turn_thinking_mode != "disable":
                request["reasoning_effort"] = turn_thinking_mode
            requested_tool_choice = _tool_choice_label(request.get("tool_choice"))
            effective_tool_choice = requested_tool_choice
            model_request_attempts = 1
            tool_choice_fallback_reason: str | None = None
            self._log(f"[JSX Agent {turn}/{self.max_turns}] 当前目标：{expected_target}")
            request_started = time.monotonic()
            tool_choice_fallback = False
            is_deepseek_direct_tool = (
                self.provider == "deepseek"
                and submit_mode == "direct"
                and expected_tool in {"submit_card_plan", "submit_card_jsx"}
            )
            try:
                try:
                    response = await self._request(request, turn)
                except Exception as exc:
                    forced_tool_choice_requested = request.get("tool_choice") != "auto"
                    if is_deepseek_direct_tool and forced_tool_choice_requested:
                        if _is_tool_choice_compatibility_error(exc):
                            self._deepseek_forced_tool_choice_supported = False
                            request = {**request, "tool_choice": "auto"}
                            tool_choice_fallback = True
                            tool_choice_fallback_reason = (
                                "deepseek-forced-tool-choice-unsupported"
                            )
                            effective_tool_choice = _tool_choice_label(
                                request.get("tool_choice")
                            )
                            model_request_attempts += 1
                            self._log(
                                f"[JSX Agent {turn}/{self.max_turns}] "
                                "当前 DeepSeek 接口不支持强制工具调用，"
                                "已回退 tool_choice=auto；本批后续任务将复用该结果"
                            )
                            response = await self._request(request, turn)
                        else:
                            raise exc
                    else:
                        raise exc
            except Exception as exc:
                api_elapsed = round(time.monotonic() - request_started, 2)
                turn_trace.append({
                    "turn": turn,
                    "target": expected_target,
                    "api_elapsed_seconds": api_elapsed,
                    "status": "request_error",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "configured_submit_mode": submit_mode,
                    "requested_tool_choice": requested_tool_choice,
                    "effective_tool_choice": effective_tool_choice,
                    "model_request_attempts": model_request_attempts,
                    "requested_max_tokens": request["max_tokens"],
                    "no_tool_call_recovery_attempt": consecutive_no_tool_calls,
                })
                if tool_choice_fallback_reason is not None:
                    turn_trace[-1]["tool_choice_fallback"] = "auto"
                    turn_trace[-1]["tool_choice_fallback_reason"] = (
                        tool_choice_fallback_reason
                    )
                setattr(exc, "turn_trace", turn_trace)
                setattr(exc, "loaded_resources", list(state.loaded_resources))
                setattr(exc, "resource_reads", list(state.resource_reads))
                setattr(exc, "validation_reports", validation_reports)
                setattr(exc, "plan", plan)
                raise exc

            forced_tool_choice_succeeded = request.get("tool_choice") != "auto"
            if is_deepseek_direct_tool and forced_tool_choice_succeeded:
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
                "configured_submit_mode": submit_mode,
                "requested_tool_choice": requested_tool_choice,
                "effective_tool_choice": effective_tool_choice,
                "model_request_attempts": model_request_attempts,
                "requested_max_tokens": request["max_tokens"],
                "no_tool_call_recovery_attempt": consecutive_no_tool_calls,
                "thinking_mode": turn_thinking_mode,
            }
            if tool_choice_fallback:
                turn_record["tool_choice_fallback"] = "auto"
                turn_record["tool_choice_fallback_reason"] = tool_choice_fallback_reason
            if assistant_content:
                turn_record["assistant_content"] = assistant_content
            if not calls:
                consecutive_no_tool_calls += 1
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
                turn_record["consecutive_no_tool_calls"] = consecutive_no_tool_calls
                turn_record["assistant_content_retained_in_messages"] = False
                recovery_exhausted = consecutive_no_tool_calls >= MAX_CONSECUTIVE_NO_TOOL_CALLS
                turn_record["no_tool_call_recovery_exhausted"] = recovery_exhausted
                turn_trace.append(turn_record)
                checkpoint()
                self._log(
                    f"[JSX Agent {turn}/{self.max_turns}] 模型未调用工具；"
                    f"finish_reason={finish_reason or 'unknown'}，API耗时={api_elapsed:.2f}s"
                )
                if recovery_exhausted:
                    error = MissingToolCallError(
                        f"模型连续 {consecutive_no_tool_calls} 次未返回当前阶段 "
                        f"{expected_target} 要求的工具调用，已停止恢复重试。"
                    )
                    error.turn_trace = turn_trace
                    error.loaded_resources = list(state.loaded_resources)
                    error.resource_reads = list(state.resource_reads)
                    error.validation_reports = validation_reports
                    raise error
                if recovery_message_index is None:
                    recovery_message_index = len(messages)
                    messages.append({"role": "user", "content": recovery})
                else:
                    messages[recovery_message_index] = {"role": "user", "content": recovery}
                continue

            messages.append(assistant_payload)
            recovery_message_index = None
            first = calls[0]
            function = first.function
            if function.name == expected_tool:
                if consecutive_no_tool_calls:
                    turn_record["no_tool_call_recovery_succeeded"] = True
                consecutive_no_tool_calls = 0
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
                elif function.name == "submit_card_plan":
                    result = validate_plan_arguments(
                        arguments,
                        task.get("size"),
                        prompt_task=task,
                    )
                    if result.get("ok"):
                        plan = arguments
                        turn_record["plan"] = plan
                elif function.name == "submit_card_jsx" and isinstance(arguments.get("jsx"), str):
                    submitted_jsx = arguments["jsx"]
                    if isinstance(arguments.get("decision"), dict):
                        turn_record["decision"] = arguments["decision"]
                    result = execute_tool(function.name, arguments, state)
                else:
                    result = execute_tool(function.name, arguments, state)
                    if function.name == "apply_layout_fallback" and result.get("ok"):
                        fallback_calls += 1
                        fallback_history.append(str(result.get("strategy") or ""))
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
                            require_all_data_ids=(
                                state.active_layout_fallback == "compact_component"
                            ),
                            drop_baseline=drop_fallback_baseline,
                        )
                    )
                if not preservation_errors and state.active_layout_fallback != "drop_optional_component":
                    last_preserved_submission = state.pending_submission
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
                        browser_warnings = []
                        for item in report.get("findings", []):
                            if isinstance(item, dict) and item.get("severity") == "warning":
                                browser_warnings.append(item)
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
                        report_errors = []
                        for item in report.get("findings", []):
                            if isinstance(item, dict) and item.get("severity") != "warning":
                                report_errors.append(item)
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
                        requires_pattern_change = browser_layout_requires_pattern_change(report)
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
                                "浏览器已确认至少一个业务组件的真实尺寸明显超过直接父槽，"
                                "当前 Layout Pattern / Sub Pattern 容量不成立。必须更换布局或子布局，"
                                "为该组件分配更大的连续区域；不要继续通过 flex、justify、gap 或固定"
                                "尺寸做局部微调，也不得删除必需信息或 Action。"
                                if requires_pattern_change
                                else
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
                            if browser_overlap_involves_emphasized_data(report):
                                repair_instruction += (
                                    " 重叠涉及 EmphasizedData：先复核业务语义；若其内容是可无损保留的"
                                    "短文本、状态或完整格式化字符串，并且能从现有需求提供真实的"
                                    "secondaryText，优先尝试替换为 EmphasisText。将原 value 的可见内容"
                                    "与 dataIds.value 迁移到 mainText 和 dataIds.mainText，不得丢失、"
                                    "拆分或静态化动态值。纯数值单位、进度关系以及应使用 EventCard 的"
                                    "日程事件不得仅为消除重叠而替换。"
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
                            active_fallback = state.active_layout_fallback
                            fallback_attempt = 0
                            fallback_attempt_limit = 0
                            if active_fallback in fallback_attempts:
                                fallback_attempts[active_fallback] += 1
                                fallback_attempt = fallback_attempts[active_fallback]
                                fallback_attempt_limit = (
                                    LAYOUT_FALLBACK_SUBMISSION_LIMITS[active_fallback]
                                )
                                result.update({
                                    "fallbackStage": active_fallback,
                                    "fallbackAttempt": fallback_attempt,
                                    "fallbackAttemptLimit": fallback_attempt_limit,
                                    "fallbackRemainingAttempts": max(
                                        0,
                                        fallback_attempt_limit - fallback_attempt,
                                    ),
                                })
                            result["browserFailures"] = browser_failures
                            result["remainingRepairs"] = max(
                                0,
                                self.max_validation_repairs - browser_failures,
                            )
                            if active_fallback == "compact_component":
                                if fallback_attempt < fallback_attempt_limit:
                                    result["instruction"] = (
                                        "紧凑组件替换第 "
                                        f"{fallback_attempt}/{fallback_attempt_limit} 次提交"
                                        "仍未通过浏览器校验。保持 compact_component 策略，"
                                        "根据本轮全部 findings 再重组一次布局；下一轮直接调用 "
                                        "submit_card_jsx，不要再次调用 apply_layout_fallback。"
                                    )
                                else:
                                    drop_fallback_baseline = last_preserved_submission or browser_repair_baseline
                                    state.require_layout_fallback("drop_optional_component")
                                    result.update({
                                        "nextFallbackStrategy": "drop_optional_component",
                                        "instruction": (
                                            "紧凑组件替换的两次提交均未通过浏览器校验。"
                                            "下一轮只调用 apply_layout_fallback，并填写 "
                                            "strategy='drop_optional_component'。"
                                        ),
                                    })
                            elif active_fallback == "drop_optional_component":
                                if fallback_attempt < fallback_attempt_limit:
                                    result["instruction"] = (
                                        "信息组件合并或删除后的第 "
                                        f"{fallback_attempt}/{fallback_attempt_limit} 次提交"
                                        "仍未通过浏览器校验。继续沿用 drop_optional_component 策略，"
                                        "先固定并保留全部 Action 组件及 actionId，再重新分配剩余内容的空间；"
                                        "下一轮直接调用 submit_card_jsx，不得删除任何 Action。"
                                    )
                                else:
                                    terminal_error = RuntimeError(
                                        "JSX 在信息组件合并或删除的三次最终兜底提交后仍未通过"
                                        "浏览器校验；"
                                        f"最后错误：{feedback}"
                                    )
                            elif browser_failures >= self.max_validation_repairs:
                                state.require_layout_fallback("compact_component")
                                result.update({
                                    "fallbackStage": "normal_repair",
                                    "nextFallbackStrategy": "compact_component",
                                    "instruction": (
                                        f"JSX 已连续 {browser_failures} 次未通过浏览器布局校验。"
                                        "下一轮只调用 apply_layout_fallback，并填写 "
                                        "strategy='compact_component'。"
                                    ),
                                })
            if function.name == "submit_card_jsx":
                if _is_static_layout_failure(result):
                    static_layout_failure_streak += 1
                    result = _static_layout_repair_feedback(
                        result,
                        static_layout_failure_streak,
                    )
                else:
                    static_layout_failure_streak = 0
            failed_submit = function.name == "submit_card_jsx" and not result.get("ok")
            non_retryable_failure = result.get("retryable") is False and terminal_error is None
            if failed_submit and non_retryable_failure:
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
                repair_pending = function.name == "apply_layout_fallback"
            messages.append(tool_result_message(first.id, result))
            if function.name == "submit_card_plan" and result.get("ok") and plan is not None:
                messages.append({"role": "user", "content": build_plan_context(plan)})
            for extra in calls[1:]:
                messages.append(tool_result_message(extra.id, {"ok": False, "error": "每轮只能调用一个工具"}))
            if repairable_failure and terminal_error is None:
                next_strategy = state.required_layout_fallback
                messages.append({
                    "role": "user",
                    "content": (
                        _stage_directive("apply_layout_fallback", next_strategy)
                        if next_strategy is not None else
                        "上一次提交未通过。请根据上一条工具结果中的 findings 和修复要求，"
                        "直接调用 submit_card_jsx，提交修复后的完整 JSX 和必需参数。"
                        "保留要求的数据绑定和动作，不要输出普通文本、分析、解释或 Markdown。"
                    ),
                })
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
            rejected_submission = (
                function.name == "submit_card_jsx"
                and not result.get("ok")
                and submitted_jsx is not None
            )
            if rejected_submission:
                turn_record["rejected_jsx"] = submitted_jsx
            turn_trace.append(turn_record)
            checkpoint()

            if terminal_error is not None:
                setattr(terminal_error, "turn_trace", turn_trace)
                setattr(terminal_error, "loaded_resources", list(state.loaded_resources))
                setattr(terminal_error, "resource_reads", list(state.resource_reads))
                setattr(terminal_error, "validation_reports", validation_reports)
                setattr(terminal_error, "plan", plan)
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
                    "compile_context": state.submission.compile_context,
                    "coverage": state.submission.coverage,
                    "unmet_requirements": state.submission.unmet_requirements,
                    "semantic_status": state.submission.semantic_status,
                    "warnings": state.submission.warnings,
                    "loaded_resources": state.loaded_resources,
                    "resource_reads": state.resource_reads,
                    "model": self.model,
                    "provider": self.provider,
                    "thinking_mode": self.thinking_mode,
                    **({"plan": plan} if getattr(self, "plan_enabled", False) else {}),
                    "turns": turn,
                    "failed_submissions": failed_submissions,
                    "repair_calls": repair_calls,
                    "fallback_calls": fallback_calls,
                    "fallback_history": fallback_history,
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
                    "dynamic_data_binding": (
                        "enabled" if getattr(self, "enable_dynamic_data_binding", True) else "disabled"
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
        setattr(error, "plan", plan)
        raise error
