# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import asyncio
import inspect
import json
import sys
import traceback
import uuid
from pathlib import Path

import json_repair

if __name__ == "__main__" and __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.logger import json_for_log, logger
from config.config import get_settings
from custom.model_runtime import ModelExecutionRuntime
from custom.model_transport import (
    ModelBackend,
    ModelTransport,
    ModelTransportError,
)
from custom.unified_model_client import UnifiedModelClient
from models.generation import ModelRequestContext
from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    ThemeMode,
    convert_compact_dsl_to_a2ui,
)
from services.protocol_registry import (
    DESIGN_COMPACT_PROFILE_ID,
    A2UIProtocolRegistry,
)

_MODULE = "[A2UI Model]"


class A2UIModelGenerationError(RuntimeError):
    """小模型未能产出可交给校验器的非空 DSL。"""


def require_generated_dsl(value: object) -> str:
    """拒绝空输出和历史错误字符串，保证下游只接收 DSL 候选。"""
    if not isinstance(value, str) or not value.strip():
        raise A2UIModelGenerationError("model returned empty DSL")
    if value.lstrip().startswith("a2ui_model_error:"):
        raise A2UIModelGenerationError("model returned an error instead of DSL")
    return value


def build_prompt_log_summary(
    prompt: list[dict[str, str]],
    preview_chars: int,
) -> dict[str, int | str]:
    """构造不包含完整消息正文的提示词日志摘要。"""
    system_prompt = ""
    for message in prompt:
        if message.get("role") != "system":
            continue
        content = message.get("content", "")
        system_prompt = content if isinstance(content, str) else str(content)
        break
    return {
        "messageCount": len(prompt),
        "systemPromptChars": len(system_prompt),
        "systemPromptPreview": system_prompt[:preview_chars],
    }


class A2UIModelClient:
    """A2UI 模型调用客户端。

    mock 开关打开时按协议 profile 返回对应 mock 文件的原始内容；
    关闭时调用真实小模型接口。
    """

    def __init__(
        self,
        use_mock: bool | None = None,
        mock_data_path: str | Path | None = None,
        backend: ModelBackend = "mep",
        transport: ModelTransport | None = None,
        runtime: ModelExecutionRuntime | None = None,
        request_context: ModelRequestContext | None = None,
        operation_name: str = "a2ui-model",
    ) -> None:
        """初始化 A2UI 模型客户端。

        入参：
        - use_mock：是否使用 mock 数据；不传时读取全局配置。
        - mock_data_path：可选 mock 文件路径；不传时按协议选择同目录 mock 文件。
        - backend：由生成路由配置选择的模型传输后端。
        - transport：测试或扩展场景可注入的模型传输实现。
        出参：无。
        """
        if backend not in {"mep", "openai"}:
            raise ValueError(f"Unsupported A2UI model backend: {backend}")
        settings = get_settings()
        self.settings = settings
        self.use_mock = (
            settings.enable_a2ui_model_mock if use_mock is None else use_mock
        )
        self.backend = backend
        self.transport = transport
        self.mock_data_path = Path(mock_data_path) if mock_data_path else None
        self.request_context = request_context or self._default_request_context()
        needs_runtime = not self.use_mock and transport is None
        self._owns_runtime = needs_runtime and runtime is None
        self.runtime = runtime or (ModelExecutionRuntime(settings) if needs_runtime else None)
        self.unified_client = None
        if needs_runtime and self.runtime is not None:
            self.unified_client = UnifiedModelClient(
                settings,
                self.runtime,
                operation_name=operation_name,
            )

    @property
    def model_failure_retry_count(self) -> int:
        """返回当前生成请求累计发生的模型额外调用次数。"""
        if self.unified_client is None:
            return 0
        return self.unified_client.retry_count

    async def aclose(self) -> None:
        """关闭当前客户端自行创建的模型运行时。"""
        if self._owns_runtime and self.runtime is not None:
            await self.runtime.aclose()

    async def generate(
        self,
        prompt: list[dict[str, str]],
        protocol_profile: dict | None = None,
        *,
        suppress_prompt_log: bool = False,
        phase: str = "initial",
    ) -> str:
        """生成 A2UI genui JSONL。

        入参：
        - prompt：PromptBuilder 生成的模型输入。
        - protocol_profile：用于选择协议对应的 mock；真实模型直接消费 prompt。
        出参：A2UI genui JSONL 字符串。
        """
        if suppress_prompt_log:
            logger.info(
                f"{_MODULE} generate_started use_mock={json_for_log(self.use_mock)} "
                f"backend={self.backend} "
                "prompt_redacted=true"
            )
        else:
            prompt_summary = build_prompt_log_summary(
                prompt,
                self.settings.model_prompt_log_preview_chars,
            )
            logger.info(
                f"{_MODULE} generate_started use_mock={json_for_log(self.use_mock)} "
                f"backend={self.backend} "
                f"prompt_summary={json_for_log(prompt_summary)}"
            )

        try:
            if self.use_mock:
                result = self._load_mock_data(protocol_profile, prompt)
            else:
                profile = protocol_profile or {}
                raw_output = await self._call_transport(
                    prompt,
                    profile,
                    phase=phase,
                )
                result = self._process_model_output(raw_output, profile)
            return require_generated_dsl(result)
        except A2UIModelGenerationError:
            raise
        except Exception as exc:
            logger.error(
                f"{_MODULE} generation_failed exception_type={type(exc).__name__} "
                f"exception={exc!r} traceback={traceback.format_exc()}"
            )
            raise A2UIModelGenerationError("model generation failed") from exc

    async def generate_repair(
        self,
        prompt: list[dict[str, str]],
        protocol_profile: dict | None = None,
    ) -> str:
        """调用同一模型入口，但不把修复载荷写入日志。"""
        result = self.generate(
            prompt,
            protocol_profile,
            suppress_prompt_log=True,
            phase="repair",
        )
        if inspect.isawaitable(result):
            return await result
        return result

    async def _call_transport(
        self,
        prompt: list[dict[str, str]],
        protocol_profile: dict,
        *,
        phase: str,
    ) -> str:
        """调用注入的测试 Transport 或应用级共享模型 Runtime。"""
        if self.transport is not None:
            try:
                generate = self.transport.generate
                if inspect.iscoroutinefunction(generate):
                    return await generate(prompt)
                result = await asyncio.to_thread(generate, prompt)
                if inspect.isawaitable(result):
                    return await result
                return result
            except ModelTransportError as exc:
                return self._recover_design_output_after_abort(
                    exc,
                    protocol_profile,
                )
        if self.unified_client is None:
            raise A2UIModelGenerationError("model runtime is not initialized")
        allow_partial_abort = (
            protocol_profile.get("id") == DESIGN_COMPACT_PROFILE_ID
        )
        return await self.unified_client.generate(
            self.backend,
            prompt,
            self.request_context,
            phase=phase,
            allow_mep_partial_abort=allow_partial_abort,
        )

    def _default_request_context(self) -> ModelRequestContext:
        """为本地直调和单元测试生成不含硬编码会话 ID 的上下文。"""
        return ModelRequestContext(
            session_id=uuid.uuid4().hex,
            interaction_id=uuid.uuid4().hex,
            device_id=f"aiwidget-{uuid.uuid4().hex}",
            country_code=self.settings.deepseek_platform_default_country_code,
            app_version=self.settings.default_prd_version,
            app_name=self.settings.deepseek_platform_default_app_name,
        )

    def _process_model_output(
        self,
        raw_output: str,
        protocol_profile: dict,
    ) -> str:
        """按目标 DSL 格式统一处理各模型后端的原始输出。"""
        dsl_text = self.extract_genui_payload(raw_output)
        is_design_compact = (
            protocol_profile.get("id") == DESIGN_COMPACT_PROFILE_ID
        )
        if not is_design_compact:
            dsl_text = self.convert_dsl(dsl_text)
        logger.info(
            f"{_MODULE} dsl_processed backend={self.backend} "
            f"dsl_content={json_for_log(dsl_text)}"
        )
        return dsl_text

    @staticmethod
    def _recover_design_output_after_abort(
        exc: ModelTransportError,
        protocol_profile: dict,
    ) -> str:
        """MEP 中止但已返回 Design 候选时交给严格转换器继续判定。"""
        is_design_output = protocol_profile.get("id") == DESIGN_COMPACT_PROFILE_ID
        has_partial_output = bool(exc.partial_output.strip())
        can_recover = exc.code == "6241" and is_design_output
        if not can_recover or not has_partial_output:
            raise exc
        logger.warning(
            f"{_MODULE} mep_design_output_recovered_after_abort "
            f"error_code={exc.code} partial_length={len(exc.partial_output)}"
        )
        return exc.partial_output

    def _load_mock_data(
        self,
        protocol_profile: dict | None = None,
        prompt: list[dict[str, str]] | None = None,
    ) -> str:
        """直接读取当前协议对应的 mock 原始内容。

        入参：协议 profile 和模型提示词；Design Compact mock 会从 TaskSpec 选择尺寸文件。
        出参：mock 文件的完整 UTF-8 文本，不做替换或结构调整。
        """
        mock_data_path = self.mock_data_path
        if mock_data_path is None:
            filename = self._mock_filename(protocol_profile or {}, prompt or [])
            mock_data_path = Path(__file__).with_name(filename)
        if not mock_data_path.is_file():
            raise FileNotFoundError(f"A2UI mock 数据文件不存在: {mock_data_path}")

        mock_data = mock_data_path.read_text(encoding="utf-8")
        logger.info(
            f"{_MODULE} generate_completed mode=mock path={mock_data_path}"
        )
        return mock_data

    @staticmethod
    def _mock_filename(
        protocol_profile: dict,
        prompt: list[dict[str, str]],
    ) -> str:
        if protocol_profile.get("id") == DESIGN_COMPACT_PROFILE_ID:
            size = A2UIModelClient._task_size_from_prompt(prompt)
            return f"mock.design-compact-dsl-{size}.dat"
        return "mock.dat"

    @staticmethod
    def _task_size_from_prompt(prompt: list[dict[str, str]]) -> str:
        if not prompt:
            return "2x2"
        user_content = prompt[-1].get("content", "")
        try:
            payload = json.loads(user_content)
        except json.JSONDecodeError as exc:
            logger.warning(
                f"{_MODULE} mock_task_spec_parse_failed "
                f"exception_type={type(exc).__name__} exception={exc!r}"
            )
            return "2x2"
        size = payload.get("size") if isinstance(payload, dict) else None
        task_spec = payload.get("taskSpec") if isinstance(payload, dict) else None
        if size is None and isinstance(task_spec, dict):
            size = task_spec.get("size")
        return size if size in {"2x2", "2x4"} else "2x2"

    def extract_genui_payload(self, text):
        """
        如果响应以'''genui 开头，则剔除前后标记，返回中间的JSON字符串
        否则原样返回。
        """
        text = text.strip()
        if text.startswith('```genui'):
            content = text[len('```genui'):].strip()
            if content.endswith('```'):
                content = content[:-3].strip()
            return content
        else:
            return text

    def convert_design_dsl_to_standard_dsl(
        self,
        design_dsl: str,
        *,
        size: str,
        design_profile_id: str = DESIGN_COMPACT_PROFILE_ID,
        theme: ThemeMode = "light",
        surface_id: str = "surface_card",
    ) -> str:
        """使用 Design profile 自带的协议文件把 Design Compact DSL 转为标准 A2UI。"""
        compact_dsl = self.extract_genui_payload(design_dsl)
        try:
            protocol_profile = A2UIProtocolRegistry.read_design_protocol_profile(
                design_profile_id
            )
            converted_dsl = convert_compact_dsl_to_a2ui(
                compact_dsl,
                size=size,
                protocol_profile=protocol_profile,
                theme=theme,
                surface_id=surface_id,
            )
            logger.info(
                f"{_MODULE} design_dsl_conversion_completed "
                f"converted_dsl={json_for_log(converted_dsl)}"
            )
            return converted_dsl
        except CompactDslConversionError as exc:
            logger.error(
                f"{_MODULE} design_dsl_conversion_failed "
                f"exception_type={type(exc).__name__} exception={exc!r}"
            )
            raise A2UIModelGenerationError("design DSL conversion failed") from exc

    def process_line(self, line):
        """
        处理单行 JSON 字符串，返回解析后的数据或 None
        """
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            logger.error(f"{_MODULE} json_parse_failed line={json_for_log(line)}")
            try:
                return json_repair.loads(line)
            except Exception as e:
                logger.error(
                    f"{_MODULE} json_repair_failed exception_type={type(e).__name__} "
                    f"exception={e!r} traceback={traceback.format_exc()}"
                )
                return None

    def convert_dsl(self, dsl_text: str) -> str:
        """
        dsl 文本处理函数
        """
        output_lines = []

        for line in dsl_text.splitlines():
            line = line.strip()
            if not line:
                continue

            data = self.process_line(line)
            if not data:
                logger.error(f"{_MODULE} dsl_line_parse_failed line={json_for_log(line)}")
                return dsl_text

            # 修改 createSurface.catalogId
            create_surface = data.get("createSurface")
            if create_surface:
                create_surface["catalogId"] = "ohos.a2ui.extended.catalog.form"

            # 修改 root 的宽高
            update_components = data.get("updateComponents")
            if update_components:
                for component in update_components.get("components", []):
                    if component.get("id") == "root":
                        styles = component.setdefault("styles", {})
                        styles["width"] = "matchParent"
                        styles["height"] = "matchParent"
                        break

            output_lines.append(
                json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            )

        return "\n".join(output_lines)


def _build_design_test_task_spec() -> dict:
    """构造覆盖数据、事件和素材能力的 Design Compact DSL 本地测试任务。"""
    return {
        "userQuery": (
            "生成杭州滨江区天气卡片，展示当前温度、天气状况、体感温度、湿度、空气质量、"
            "风向风力、生活指数和未来3天天气预报，并支持打开天气详情"
        ),
        "size": "2x2",
        "eventCandidates": [
            {
                "id": "event.open.weather",
                "call": "clickToDeeplink",
                "args": {
                    "uri": "hww://www.huawei.com/totemweather?enterType=share&cityCode=",
                },
            }
        ],
        "dataModelSchema": {
            "data": {
                "weather": {
                    "current": {
                        "temperatureText": {
                            "type": "string",
                            "description": "适合直接显示的温度文本",
                            "sampleValue": "26℃",
                        },
                        "condition": {
                            "type": "string",
                            "description": "当前天气现象",
                            "sampleValue": "多云",
                        },
                        "feelsLikeC": {
                            "type": "number",
                            "description": "当前体感摄氏温度",
                            "sampleValue": 27,
                        },
                        "humidityPercent": {
                            "type": "number",
                            "description": "当前相对湿度百分比",
                            "sampleValue": 68,
                        },
                        "airQuality": {
                            "type": "string",
                            "description": "当前空气质量等级",
                            "sampleValue": "优",
                        },
                        "windDirection": {
                            "type": "string",
                            "description": "当前风向",
                            "sampleValue": "东南风",
                        },
                        "windLevel": {
                            "type": "integer",
                            "description": "当前风力等级",
                            "sampleValue": 2,
                        },
                        "uvIndex": {
                            "type": "string",
                            "description": "当前紫外线等级",
                            "sampleValue": "中等",
                        },
                        "coldLevel": {
                            "type": "string",
                            "description": "当前感冒指数",
                            "sampleValue": "较低",
                        },
                        "alertLevel": {
                            "type": "string",
                            "description": "当前天气预警信息",
                            "sampleValue": "无预警",
                        },
                    },
                    "daily": [
                        {
                            "date": {
                                "type": "string",
                                "description": "预报日期",
                                "sampleValue": "2026-07-15",
                            },
                            "weekday": {
                                "type": "string",
                                "description": "星期文本",
                                "sampleValue": "星期三",
                            },
                            "condition": {
                                "type": "string",
                                "description": "白天天气现象",
                                "sampleValue": "多云",
                            },
                            "temperatureRangeText": {
                                "type": "string",
                                "description": "适合直接显示的温度范围",
                                "sampleValue": "24℃ / 31℃",
                            },
                            "rainProbabilityPercent": {
                                "type": "string",
                                "description": "白天降雨概率百分比",
                                "sampleValue": "20%",
                            },
                        }
                    ],
                }
            }
        },
        "assetCandidates": [
            {
                "id": "asset.sun_max",
                "src": "resources/base/media/sun_max.svg",
                "description": "天气晴朗和亮度信息使用的太阳图标",
            },
            {
                "id": "asset.drop_1",
                "src": "resources/base/media/drop_1.svg",
                "description": "湿度和降雨信息使用的水滴图标",
            },
            {
                "id": "asset.thermometer_sun_fill",
                "src": "resources/base/media/thermometer_sun_fill.svg",
                "description": "温度和体感信息使用的温度计太阳图标",
            },
        ],
    }



async def _run_main() -> int:
    """临时验证 Design Compact DSL 生成及标准 A2UI DSL 转换链路。"""
    system_prompt = A2UIProtocolRegistry.read_design_prompt(
        DESIGN_COMPACT_PROFILE_ID
    )
    task_spec = _build_design_test_task_spec()
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": json.dumps(task_spec, ensure_ascii=False),
        },
    ]
    client = A2UIModelClient(
        use_mock=False,
        backend=get_settings().design_compact_model_backend,
    )
    design_profile = {
        "id": DESIGN_COMPACT_PROFILE_ID,
        "format": "design-compact-dsl",
    }
    try:
        design_dsl = await client.generate(messages, design_profile)
        final_dsl = client.convert_design_dsl_to_standard_dsl(
            design_dsl,
            size=task_spec["size"],
            design_profile_id=DESIGN_COMPACT_PROFILE_ID,
        )
        print("\n=== Final A2UI DSL ===")
        print(final_dsl)
        return 0
    finally:
        await client.aclose()


def main() -> int:
    """运行临时 Design Compact DSL 端到端测试。"""
    return asyncio.run(_run_main())


if __name__ == "__main__":
    raise SystemExit(main())
