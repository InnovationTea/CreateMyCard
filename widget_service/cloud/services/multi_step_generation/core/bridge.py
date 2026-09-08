from __future__ import annotations

# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any

from app.logger import logger, task_logger
from config.config import Settings, get_settings
from models.generation import ModelRequestContext

from ..jsx_runner.agent import JsxA2UIAgent
from ..jsx_runner.data_processing import prepare_task
from .input_adapter import task_spec_payload
from .model_adapter import PlatformChatClient
from .options import BridgeOptions
from .result import BridgeResult

_MODULE = "[JSX-A2UI Bridge]"
_WORKSPACE_DIR = Path(__file__).resolve().parent.parent / "workspace"
_E2E_CAPTURE_ROOT = _WORKSPACE_DIR / "e2e_capture"
_E2E_CAPTURE_MARKER = ".enabled"
_SESSION_ID_PATTERN = re.compile(r"[0-9a-f]{32}")


class JsxA2UIBridge:
    """连接平台 TaskSpec/WS 模型与原封不动的 JSX→A2UI 工作流。"""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        request_context: ModelRequestContext | None = None,
        options: BridgeOptions | None = None,
        dump_to_workspace: bool = False,
    ) -> None:
        self.settings = settings or get_settings()
        self.request_context = request_context or self._default_request_context()
        self.options = options or BridgeOptions(
            request_timeout=self.settings.model_request_timeout_seconds,
            thinking_mode=("high" if self.settings.deepseek_enable_thinking else "disable"),
        )
        self._dump_directory = self._resolve_dump_directory(dump_to_workspace)
        self.dump_to_workspace = self._dump_directory is not None

    async def aclose(self) -> None:
        """本地 WS 客户端按请求关闭连接；保留统一清理接口。"""

    @property
    def model_name(self) -> str:
        """返回平台现有配置实际选择的模型名。"""
        if self.settings.openai_master_client == "deepseek_platform":
            return self.settings.deepseek_platform_model_name
        return self.settings.deepseek_model

    def create_agent(
        self,
        options: BridgeOptions | None = None,
        *,
        agent_factory: Any = JsxA2UIAgent,
    ) -> JsxA2UIAgent:
        """只替换模型客户端，Runner 的生成、校验和转换流程不变。"""
        resolved = options or self.options
        client = PlatformChatClient(
            self.settings,
            self.request_context,
            thinking_mode=resolved.thinking_mode,
            request_timeout=resolved.request_timeout,
        )
        return agent_factory(
            model=self.model_name,
            provider="deepseek",
            max_turns=resolved.max_turns,
            max_tokens=resolved.max_tokens,
            thinking_mode=resolved.thinking_mode,
            request_timeout=resolved.request_timeout,
            max_validation_repairs=resolved.max_browser_repairs,
            browser_validation=resolved.browser_validation,
            validation_enabled=resolved.validation_enabled,
            layout_budget_validation=resolved.layout_budget_validation,
            validate_dynamic_values=resolved.validate_dynamic_values,
            submit_mode=resolved.submit_mode,
            verbose=resolved.verbose,
            client=client,
        )

    async def generate(self, task_spec: object, size: object) -> BridgeResult:
        """生成 JSX、执行原有校验并返回标准 A2UI 消息。"""
        payload = task_spec_payload(task_spec, size)
        prepared = prepare_task(payload, 1)
        component_name = self._component_name(payload)
        logger.info(f"{_MODULE} agent_start component={component_name} size={size}")

        # trace 收集：agent 执行过程中通过 callback 回传状态
        trace_data: dict[str, Any] = {}

        def trace_callback(update: dict[str, Any]) -> None:
            trace_data.update(update)

        try:
            result = await self.create_agent().render(
                prepared.prompt_task,
                component_name,
                compile_context=prepared.compile_context,
                trace_callback=trace_callback,
            )
        except Exception as exc:
            if self.dump_to_workspace:
                self._merge_exception_trace(trace_data, exc)
                self._dump_trace_to_workspace(
                    component_name,
                    trace_data,
                    {},
                    prepared.prompt_task,
                    prepared.compile_context,
                    error=exc,
                )
            raise exc
        messages = result.get("a2ui")
        if not isinstance(messages, list) or not messages:
            raise RuntimeError("JSX workflow returned no A2UI messages")
        warnings = result.get("warnings")
        normalized_warnings = tuple(item for item in warnings or [] if isinstance(item, dict))

        raw_jsx = str(result.get("jsx") or "")
        raw_source = str(result.get("source") or "")
        raw_a2ui = list(messages)
        raw_a2ui_json = json.dumps(raw_a2ui, ensure_ascii=False, indent=2)
        logger.debug(f"{_MODULE} === RAW JSX === component={component_name}\n{raw_jsx}")
        logger.debug(
            f"{_MODULE} === RAW A2UI ({len(raw_a2ui)} messages) === "
            f"component={component_name}\n{raw_a2ui_json}"
        )

        # 普通请求仍只保留 artifact；仅显式调试或带本地 E2E 标记的请求落盘诊断产物。
        if self.dump_to_workspace:
            self._dump_raw_to_workspace(component_name, raw_source, raw_a2ui)
            self._dump_trace_to_workspace(
                component_name,
                trace_data,
                result,
                prepared.prompt_task,
                prepared.compile_context,
            )

        logger.info(
            f"{_MODULE} agent_done component={component_name} "
            f"turns={result.get('turns')} elapsed={result.get('elapsed_seconds')}s"
        )

        return BridgeResult(
            component_name=component_name,
            jsx=raw_jsx,
            source=raw_source,
            a2ui_messages=tuple(dict(item) for item in messages),
            turns=int(result.get("turns") or 0),
            elapsed_seconds=float(result.get("elapsed_seconds") or 0.0),
            failed_submissions=int(result.get("failed_submissions") or 0),
            repair_calls=int(result.get("repair_calls") or 0),
            warnings=normalized_warnings,
        )

    def _dump_raw_to_workspace(
        self,
        component_name: str,
        raw_source: str,
        raw_a2ui: list[dict[str, Any]],
    ) -> None:
        """把完整 JSX 源码和 A2UI 写到当前请求的诊断目录。"""
        dump_directory = self._dump_directory
        if dump_directory is None:
            return
        try:
            dump_directory.mkdir(parents=True, exist_ok=True)
            jsx_path = dump_directory / f"raw_jsx_{component_name}.jsx"
            a2ui_path = dump_directory / f"raw_a2ui_{component_name}.json"
            jsx_path.write_text(raw_source, encoding="utf-8")
            a2ui_path.write_text(
                json.dumps(raw_a2ui, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info(
                f"{_MODULE} raw_dumped component={component_name} jsx={jsx_path} a2ui={a2ui_path}"
            )
        except Exception as exc:
            logger.warning(f"{_MODULE} raw_dump_failed component={component_name} error={exc}")

    def _dump_trace_to_workspace(
        self,
        component_name: str,
        trace_data: dict[str, Any],
        result: dict[str, Any],
        prompt_task: dict[str, Any],
        compile_context: dict[str, Any] | None,
        *,
        error: Exception | None = None,
    ) -> None:
        """把 trace、rejected JSX 和 context 写到当前请求的诊断目录。"""
        dump_directory = self._dump_directory
        if dump_directory is None:
            return
        try:
            dump_directory.mkdir(parents=True, exist_ok=True)

            # trace.json：agent 执行过程的完整记录
            trace_entry = {
                "component_name": component_name,
                "task": prompt_task,
                "status": "failed" if error is not None else "completed",
                "loaded_resources": trace_data.get("loaded_resources", []),
                "reasoning_trace": trace_data.get("reasoning_trace", []),
                "turn_trace": trace_data.get("turn_trace", []),
                "validation_reports": trace_data.get("validation_reports", []),
                "turns": result.get("turns", 0),
                "elapsed_seconds": result.get("elapsed_seconds", 0.0),
                "coverage": result.get("coverage", []),
                "unmet_requirements": result.get("unmet_requirements", []),
                "semantic_status": result.get(
                    "semantic_status",
                    "unverified" if error is not None else "completed",
                ),
                "failed_submissions": result.get("failed_submissions", 0),
                "repair_calls": result.get("repair_calls", 0),
                "tool_argument_repairs": result.get("tool_argument_repairs", 0),
                "protocol_retries": result.get("protocol_retries", 0),
                "browser_validation": result.get("browser_validation", "unknown"),
                "validation_mode": result.get("validation_mode", "unknown"),
                "layout_budget_validation": result.get(
                    "layout_budget_validation",
                    "unknown",
                ),
                "model": result.get("model", self.model_name),
                "provider": result.get("provider", "deepseek"),
                "thinking_mode": result.get("thinking_mode", self.options.thinking_mode),
            }
            if error is not None:
                trace_entry["error_type"] = type(error).__name__
                trace_entry["error"] = str(error)
            trace_path = dump_directory / f"raw_trace_{component_name}.json"
            trace_path.write_text(
                json.dumps(trace_entry, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            # rejected JSX：校验失败的中间结果
            turn_trace = trace_data.get("turn_trace", [])
            rejected_count = 0
            for turn_record in turn_trace:
                rejected_jsx = turn_record.get("rejected_jsx")
                if not isinstance(rejected_jsx, str):
                    continue
                turn_num = int(turn_record.get("turn", 0))
                rejected_path = (
                    dump_directory / f"raw_rejected_{component_name}_turn{turn_num:02d}.jsx"
                )
                rejected_path.write_text(rejected_jsx, encoding="utf-8")
                rejected_count += 1

            # context.json：编译上下文（数据绑定 + 动作绑定）
            if compile_context and (compile_context.get("data") or compile_context.get("actions")):
                context_path = dump_directory / f"raw_context_{component_name}.json"
                context_path.write_text(
                    json.dumps(compile_context, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

            logger.info(
                f"{_MODULE} trace_dumped component={component_name} "
                f"trace={trace_path} rejected={rejected_count} "
                f"context={'Y' if compile_context else 'N'}"
            )
        except Exception as exc:
            logger.warning(f"{_MODULE} trace_dump_failed component={component_name} error={exc}")

    @staticmethod
    def _merge_exception_trace(trace_data: dict[str, Any], error: Exception) -> None:
        """用异常携带的最终 checkpoint 补齐失败请求 trace。"""
        for key in (
            "turn_trace",
            "loaded_resources",
            "resource_reads",
            "validation_reports",
        ):
            value = getattr(error, key, None)
            if value is not None:
                trace_data[key] = value

    def _resolve_dump_directory(self, dump_to_workspace: bool) -> Path | None:
        """返回当前本地 E2E 请求的隔离采集目录，或显式调试目录。"""
        session_id = self.request_context.session_id
        if _SESSION_ID_PATTERN.fullmatch(session_id) is not None:
            capture_directory = _E2E_CAPTURE_ROOT / session_id
            marker_path = capture_directory / _E2E_CAPTURE_MARKER
            if marker_path.is_file():
                return capture_directory
        if dump_to_workspace or self.settings.LOCAL_FLAG:
            return _WORKSPACE_DIR
        return None

    def _default_request_context(self) -> ModelRequestContext:
        """优先复用平台当前请求的日志上下文，独立运行时再生成稳定兜底。"""
        token = uuid.uuid4().hex
        combined_session = self._context_text(task_logger.get_session_id())
        logger_interaction = self._context_text(task_logger.get_interaction_id())
        session_id, combined_interaction = self._split_request_id(combined_session)
        interaction_id = logger_interaction or combined_interaction or uuid.uuid4().hex
        device_id = self._context_text(task_logger.get_device_id())
        if not device_id:
            trace = self._context_text(task_logger.get_user_device_trace())
            device_id = f"jsx-{trace[:32]}" if trace else f"jsx-{token}"
        country_code = self._context_text(task_logger.get_country_code())
        app_version = self._context_text(task_logger.get_client_version())
        app_name = self._context_text(task_logger.get_package_name())
        return ModelRequestContext(
            session_id=session_id or token,
            interaction_id=interaction_id,
            device_id=device_id,
            country_code=(country_code or self.settings.deepseek_platform_default_country_code),
            app_version=app_version or self.settings.default_prd_version,
            app_name=app_name or self.settings.deepseek_platform_default_app_name,
        )

    @staticmethod
    def _context_text(value: object) -> str:
        if not isinstance(value, str):
            return ""
        normalized = value.strip()
        if not normalized or normalized.casefold() == "none":
            return ""
        return normalized

    @staticmethod
    def _split_request_id(value: str) -> tuple[str, str]:
        if "&" not in value:
            return value, ""
        session_id, interaction_id = value.split("&", 1)
        return session_id.strip(), interaction_id.strip()

    @staticmethod
    def _component_name(payload: dict[str, Any]) -> str:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:12]
        return f"CardGenerated_{digest}"
