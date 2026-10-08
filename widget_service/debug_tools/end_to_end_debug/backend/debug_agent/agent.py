from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from models.generation import ModelRequestContext

if TYPE_CHECKING:
    from config.config import Settings

from .artifact_reader import ArtifactReader
from .config import DebugSettings
from .logging_utils import DebugLogger
from .skill_loader import SkillLoader
from .tool_dispatcher import ToolDispatcher
from .tool_registry import ToolRegistry

EventSink = Callable[[str, dict[str, Any], str], Awaitable[None]]
BrowserToolInvoker = Callable[..., Awaitable[tuple[dict[str, Any], tuple[dict[str, Any], ...]]]]


def _timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class AgentRunError(RuntimeError):
    """模型循环无法产生合法结果。"""


class DebugAgentSession:
    """单个浏览器连接对应的主 Agent 会话和完整工具历史。"""

    def __init__(
        self,
        debug_settings: DebugSettings,
        *,
        production_settings: Settings | None = None,
        event_sink: EventSink | None = None,
        model_client_factory: Callable[..., Any] | None = None,
        upstream_client: Any | None = None,
        browser_tool_invoker: BrowserToolInvoker | None = None,
    ) -> None:
        self.debug_settings = debug_settings
        self.debug_logger = DebugLogger(
            skill=debug_settings.skill_name,
            trace=debug_settings.log_trace,
            limit=debug_settings.log_value_limit,
        )
        if production_settings is None:
            from config.config import get_settings

            production_settings = get_settings()
        self.production_settings = production_settings
        self.session_id = uuid.uuid4().hex
        self.context = None
        self.current_query = ""
        self.running = False
        self.cancel_event = asyncio.Event()
        self._event_sink = event_sink
        self._model_client_factory = model_client_factory or self._default_model_client
        self._upstream_client = upstream_client
        self._browser_tool_invoker = browser_tool_invoker
        self.loader: SkillLoader
        self.registry: ToolRegistry
        self.dispatcher: ToolDispatcher
        self.history: list[dict[str, Any]] = []
        self.last_artifact_url = ""
        self.artifacts: list[dict[str, Any]] = []
        self._generated_call_ids: dict[int, str] = {}
        self._force_final_response = False
        self._initialize()

    def _initialize(self) -> None:
        skills_root = self.debug_settings.skill_root or (
            self.production_settings.repo_root / "skills"
        )
        self.loader = SkillLoader(
            skills_root.parent
            if skills_root.name == self.debug_settings.skill_name
            else skills_root,
            self.debug_settings.skill_name,
            self.debug_settings.skill_resource_max_bytes,
            self.debug_settings.skill_directory,
        )
        self.registry = ToolRegistry(
            self.loader.skill_root, self.loader.catalog, self.debug_settings.bundle_name
        )
        self.dispatcher = ToolDispatcher(
            self.debug_settings,
            self.loader,
            self.registry,
            self._upstream_client,
            browser_invoke=self._browser_tool_invoker,
        )
        self.history = [{"role": "system", "content": self._system_prompt()}]
        self.debug_logger.event(
            "skill_initialized",
            component="agent",
            skill_version=self.debug_settings.skill_version,
            skill_path=str(self.loader.skill_root),
            prompt_path=str(self.debug_settings.system_prompt_path or "default"),
            tool_count=len(self.registry.tools),
        )

    def configure(self, context: Any) -> None:
        if self.running or len(self.history) != 1:
            raise ValueError("会话开始后不能修改配置，请新建会话")
        self.context = context

    def reset(self) -> None:
        if self.running:
            raise ValueError("运行中不能重置会话")
        preserved_context = self.context
        self.session_id = uuid.uuid4().hex
        self.current_query = ""
        self.last_artifact_url = ""
        self.artifacts.clear()
        self.cancel_event = asyncio.Event()
        self._generated_call_ids.clear()
        self._force_final_response = False
        self._initialize()
        self.context = preserved_context

    async def run(self, query: str, *, run_id: str | None = None) -> None:
        if self.running:
            raise ValueError("当前会话已有运行中的任务")
        if self.context is None:
            from .schemas import DeviceDebugContext

            self.context = DeviceDebugContext(
                uid=self.debug_settings.default_uid,
                odid=self.debug_settings.default_device_id,
                deviceId=self.debug_settings.default_device_id,
                phoneType=self.debug_settings.default_phone_type,
                appVersion=self.debug_settings.default_app_version,
                romVersion=self.debug_settings.default_rom_version,
                locale=self.debug_settings.default_locale,
                countryCode=self.debug_settings.default_country_code,
            )
        self.running = True
        self.cancel_event.clear()
        self.current_query = query
        self._force_final_response = False
        active_run_id = run_id or uuid.uuid4().hex
        started = time.perf_counter()
        await self.emit("run_started", {"query": query}, active_run_id)
        self.debug_logger.event(
            "run_started", component="agent", run_id=active_run_id, status="started"
        )
        self.history.append({"role": "user", "content": query})
        try:
            await self._loop(active_run_id)
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            await self.emit(
                "run_completed",
                {"durationMs": duration_ms},
                active_run_id,
            )
            self.debug_logger.event(
                "run_completed",
                component="agent",
                run_id=active_run_id,
                status="success",
                duration_ms=duration_ms,
            )
        except asyncio.CancelledError:
            self.debug_logger.event(
                "run_cancelled",
                component="agent",
                run_id=active_run_id,
                status="cancelled",
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            await self.emit("run_cancelled", {}, active_run_id)
            raise
        except AgentRunError as exc:
            detail = _exception_detail(exc)
            self.debug_logger.event(
                "run_failed",
                component="agent",
                run_id=active_run_id,
                status="failed",
                error_type=type(exc).__name__,
                error_message=detail,
            )
            await self.emit("run_failed", {"error": detail}, active_run_id)
        except Exception as exc:  # pragma: no cover - 兜底保证页面得到稳定事件
            detail = _exception_detail(exc)
            self.debug_logger.event(
                "run_failed",
                component="agent",
                run_id=active_run_id,
                status="failed",
                error_type=type(exc).__name__,
                error_message=detail,
            )
            await self.emit("run_failed", {"error": detail}, active_run_id)
        finally:
            self.running = False

    async def cancel(self) -> None:
        self.cancel_event.set()

    async def emit(self, event_type: str, data: dict[str, Any], run_id: str = "") -> None:
        if self._event_sink is not None:
            await self._event_sink(event_type, data, run_id)

    async def _loop(self, run_id: str) -> None:
        for step in range(1, self.debug_settings.max_steps + 1):
            if self.cancel_event.is_set():
                raise asyncio.CancelledError
            client = self._model_client_factory(self._model_context(), self.production_settings)
            started = time.perf_counter()
            tool_choice = "none" if self._force_final_response else "auto"
            model_tools = [] if self._force_final_response else self.registry.model_tools
            completion = await client.complete(
                list(self.history),
                tools=model_tools,
                tool_choice=tool_choice,
                max_tokens=self.debug_settings.max_tokens,
                enable_thinking=client.thinking_mode != "disable",
            )
            content = str(getattr(completion, "content", "") or "")
            tool_calls = tuple(getattr(completion, "tool_calls", ()) or ())
            self.debug_logger.event(
                "model_completed",
                component="model",
                run_id=run_id,
                step=step,
                status="success",
                history_count=len(self.history),
                model_tool_count=len(model_tools),
                content_chars=len(content),
                tool_call_count=len(tool_calls),
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            if content:
                await self.emit("assistant_message", {"content": content, "step": step}, run_id)
                # if _contains_output_leak(content):
                #     await self.emit(
                #         "diagnostic",
                #         {
                #             "kind": "assistant_output_leak",
                #             "message": "模型回复疑似暴露产物或内部字段",
                #         },
                #         run_id,
                #     )
            if not tool_calls:
                if not content.strip():
                    raise AgentRunError("模型返回空内容且没有工具调用")
                self.history.append({"role": "assistant", "content": content})
                return
            if self._force_final_response:
                raise AgentRunError("生成 DSL 成功后模型仍返回工具调用")
            assistant_message = {
                "role": "assistant",
                "content": content,
                "tool_calls": [self._tool_call_dict(call) for call in tool_calls],
            }
            self.history.append(assistant_message)
            for call in tool_calls:
                if self.cancel_event.is_set():
                    raise asyncio.CancelledError
                await self._execute_tool_call(call, run_id, step)
        raise AgentRunError(f"达到单轮最大模型步骤数 {self.debug_settings.max_steps}")

    async def _execute_tool_call(self, call: Any, run_id: str, step: int) -> None:
        call_id = self._tool_call_id(call)
        function_name = str(_call_attr(call, "name") or "")
        raw_arguments = str(_call_attr(call, "arguments") or "")
        await self.emit(
            "tool_call",
            {
                "name": function_name,
                "callId": call_id,
                "arguments": raw_arguments,
                "functionName": self._tool_function_name(function_name, raw_arguments),
                "step": step,
            },
            run_id,
        )
        result, frames = await self._dispatch_call(
            function_name,
            raw_arguments,
            call_id=call_id,
            run_id=run_id,
            step=step,
        )
        for frame in frames:
            await self.emit("upstream_frame", frame, run_id)
        await self._append_tool_result(call_id, result, run_id, step, call)
        operation = self._tool_function_name(function_name, raw_arguments)
        if operation == "generateWidgetCardCompactDsl" and _is_successful_result(result):
            # A successful generation is the terminal tool step for this run.
            # The next model request may only produce the user-facing answer.
            self._force_final_response = True
        await self._maybe_preview(run_id, function_name, result)

    async def _dispatch_call(
        self,
        function_name: str,
        raw_arguments: str,
        *,
        call_id: str = "",
        run_id: str = "",
        step: int = 0,
    ) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
        try:
            arguments = json.loads(raw_arguments)
        except json.JSONDecodeError as exc:
            return {"ok": False, "error": {"code": "INVALID_JSON", "message": str(exc)}}, ()
        if function_name == "load_skill":
            return await self.dispatcher.dispatch_load_skill(arguments), ()
        if function_name == "invoke":
            return await self.dispatcher.dispatch_invoke(
                arguments,
                self.context,
                self.session_id,
                self.current_query,
                call_id=call_id,
                run_id=run_id,
                step=step,
            )
        return {"ok": False, "error": {"code": "UNKNOWN_TOOL", "message": function_name}}, ()

    @staticmethod
    def _tool_function_name(tool_name: str, raw_arguments: str) -> str:
        if tool_name != "invoke":
            return ""
        try:
            parsed = json.loads(raw_arguments)
        except (TypeError, ValueError):
            return ""
        value = parsed.get("functionName") if isinstance(parsed, dict) else None
        return value if isinstance(value, str) else ""

    async def _append_tool_result(
        self,
        call_id: str,
        result: dict[str, Any],
        run_id: str,
        step: int,
        call: Any,
    ) -> None:
        result_text = json.dumps(result, ensure_ascii=False)
        self.history.append({"role": "tool", "tool_call_id": call_id, "content": result_text})
        await self.emit(
            "tool_result",
            {
                "callId": call_id,
                "result": result,
                "step": step,
                "name": str(_call_attr(call, "name") or ""),
                "functionName": _function_name_from_result(call, result),
            },
            run_id,
        )

    @staticmethod
    def _tool_function_name(tool_name: str, raw_arguments: str) -> str:
        if tool_name != "invoke":
            return ""
        try:
            parsed = json.loads(raw_arguments)
        except (TypeError, ValueError):
            return ""
        value = parsed.get("functionName") if isinstance(parsed, dict) else None
        return value if isinstance(value, str) else ""

    async def _maybe_preview(self, run_id: str, function_name: str, result: dict[str, Any]) -> None:
        if function_name != "invoke":
            return
        status = result.get("status", "success")
        if status not in {"success", "degraded"}:
            return
        raw_artifact_url = result.get("artifactUrl") or result.get("artifact_reference")
        if isinstance(raw_artifact_url, dict):
            raw_artifact_url = raw_artifact_url.get("url") or raw_artifact_url.get("artifactUrl")
        artifact_url = (
            _normalize_artifact_url(raw_artifact_url)
            if isinstance(raw_artifact_url, str)
            else ""
        )
        if artifact_url and not _is_artifact_url(artifact_url):
            await self.emit(
                "diagnostic",
                {"kind": "artifact_url_invalid", "message": "生成结果未返回合法 artifact URL"},
                run_id,
            )
            artifact_url = ""

        genui = result.get("genui")
        card_spec = result.get("cardSpec")
        if not isinstance(genui, str):
            genui = ""
        if not isinstance(card_spec, dict):
            card_spec = {}
        if not genui and not card_spec:
            if artifact_url:
                try:
                    artifact_reader = ArtifactReader()
                    loaded_preview, read_error = await artifact_reader.read(
                        run_id,
                        artifact_url,
                        str(result.get("artifactDigest") or ""),
                    )
                except Exception as error:  # noqa: BLE001 - diagnostics must not abort the run
                    loaded_preview = None
                    read_error = _exception_detail(error)
                if loaded_preview is None:
                    await self.emit(
                        "diagnostic",
                        {
                            "kind": "artifact_download_failed",
                            "artifactUrl": artifact_url,
                            "message": read_error or "artifact 下载失败",
                        },
                        run_id,
                    )
                    return
                preview = loaded_preview.model_dump(mode="json", exclude_none=True)
                self.last_artifact_url = artifact_url
                self.artifacts.append(preview)
                await self.emit("artifact_preview", preview, run_id)
            return

        if artifact_url and artifact_url == self.last_artifact_url:
            await self.emit(
                "diagnostic",
                {"kind": "artifact_source_reused", "artifactUrl": artifact_url},
                run_id,
            )
            return
        self.last_artifact_url = artifact_url
        preview = {
            "runId": run_id,
            "artifactUrl": artifact_url,
            "artifactDigest": str(result.get("artifactDigest") or ""),
            "genui": genui,
            "cardSpec": card_spec,
        }
        for field in (
            "taskSpec",
            "effectiveCapabilities",
            "removedCapabilities",
            "generationPlan",
            "meta",
            "designToken",
        ):
            if field in result:
                preview[field] = result[field]
        self.artifacts.append(preview)
        await self.emit("artifact_preview", preview, run_id)

    def _model_context(self) -> ModelRequestContext:
        context = self.context
        return ModelRequestContext(
            session_id=self.session_id,
            interaction_id=uuid.uuid4().hex,
            device_id=context.deviceId,
            country_code=context.countryCode,
            app_version=context.appVersion,
            app_name="com.huawei.hmos.vassistant",
        )

    def _default_model_client(
        self, request_context: ModelRequestContext, settings: Settings
    ) -> Any:
        from services.multi_step_generation.core.model_adapter import PlatformChatClient

        provider = settings.openai_master_client
        allowed = {"deepseek_platform", "llmclient", "deepseek_official_http"}
        if provider not in allowed:
            raise ValueError(f"Debug 服务不支持当前模型 Provider: {provider}")
        thinking_enabled = (
            settings.deepseek_official_http_enable_thinking
            if provider == "deepseek_official_http"
            else settings.deepseek_enable_thinking
        )
        return PlatformChatClient(
            settings,
            request_context,
            thinking_mode="high" if thinking_enabled else "disable",
            request_timeout=settings.model_request_timeout_seconds,
        )

    def _system_prompt(self) -> str:
        prompt_path = self.debug_settings.system_prompt_path
        if prompt_path is not None:
            content = prompt_path.read_text(encoding="utf-8")
        else:
            content = "请根据 Skill catalog 调用 load_skill，再通过 invoke 串行执行已注册函数。"
        return (
            f"{content}\n当前 Skill：{self.loader.catalog.name}\n"
            "模型工具仅允许：load_skill、invoke。"
            "首先使用如下工具调用导入初始化skill"
            + json.dumps(
                {
                    "skillName": self.debug_settings.skill_name,
                    "resourceId": "instructions",
                },
                ensure_ascii=False,
            )
        )

    def _tool_call_id(self, call: Any) -> str:
        raw_id = _call_attr(call, "id")
        if raw_id:
            return str(raw_id)
        key = id(call)
        generated = self._generated_call_ids.get(key)
        if generated is None:
            generated = uuid.uuid4().hex
            self._generated_call_ids[key] = generated
        return generated

    def _tool_call_dict(self, call: Any) -> dict[str, Any]:
        call_id = self._tool_call_id(call)
        name = str(_call_attr(call, "name") or "")
        arguments = str(_call_attr(call, "arguments") or "")
        return {
            "id": call_id,
            "type": "function",
            "function": {"name": name, "arguments": arguments},
        }


def _call_attr(call: Any, name: str) -> Any:
    if isinstance(call, dict):
        return call.get(name)
    return getattr(call, name, None)


def _function_name_from_result(call: Any, _result: dict[str, Any]) -> str:
    if str(_call_attr(call, "name") or "") != "invoke":
        return str(_call_attr(call, "name") or "")
    raw_arguments = _call_attr(call, "arguments")
    try:
        parsed = json.loads(str(raw_arguments or ""))
    except json.JSONDecodeError:
        parsed = {}
    function_name = parsed.get("functionName") if isinstance(parsed, dict) else None
    return str(function_name) if isinstance(function_name, str) else "invoke"


def _is_successful_result(result: dict[str, Any]) -> bool:
    """判断浏览器工具结果是否已经到达可收尾的成功终态。"""

    if result.get("ok") is False:
        return False
    error_code = result.get("errorCode")
    if error_code not in (None, "", 0, "0"):
        return False
    status = str(result.get("status") or "").strip().lower()
    return status in {"success", "degraded", "final"}


def _contains_output_leak(content: str) -> bool:
    markers = ("artifactUrl", "genWidgetResult", "genuiResult", "http://", "https://")
    return any(marker in content for marker in markers)


def _is_artifact_url(value: str) -> bool:
    parsed = urlsplit(value.strip())
    if any(char.isspace() for char in value):
        return False
    if parsed.scheme in {"http", "https"}:
        return bool(parsed.netloc)
    if parsed.scheme == "mock":
        return bool(parsed.netloc or parsed.path)
    # Local fixture paths are resolved by ArtifactReader against the project
    # mock_obs/workspace roots, never against an arbitrary browser path.
    if not parsed.scheme:
        normalized = parsed.path.replace("\\", "/").lstrip("/")
        return normalized.startswith(("mock_obs/", "workspace/")) and bool(
            Path(normalized).name
        )
    return False


def _normalize_artifact_url(value: str) -> str:
    """清理本地联调结果中包裹 URL 的 Markdown 边界标记。"""
    normalized = value.strip().strip("`\"'")
    if normalized.startswith("["):
        normalized = normalized[1:].lstrip()
    if "](" in normalized:
        normalized = normalized.split("](", 1)[0]
    if normalized.endswith("]"):
        normalized = normalized[:-1].rstrip()
    return normalized


def _exception_detail(error: BaseException) -> str:
    parts: list[str] = []
    current: BaseException | None = error
    while current is not None and len(parts) < 4:
        text = f"{type(current).__name__}: {current}"
        if text not in parts:
            parts.append(text)
        current = current.__cause__ or current.__context__
    return " <- ".join(parts)

