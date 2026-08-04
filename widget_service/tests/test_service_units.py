# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
# ruff: noqa: E402, I001
import asyncio
import base64
import hashlib
import hmac
import json as json_module
import sys
import threading
import time
from pathlib import Path

import httpx
import requests
import pytest
from anyio import to_thread
from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLOUD_ROOT = PROJECT_ROOT / "cloud"
APP_VERSION = ".".join(("11", "7", "5", "205"))
ROM_VERSION_6 = "CLS-AL30 " + ".".join(("6", "0", "0", "328"))
ROM_VERSION_7 = "ALN-AL00 " + ".".join(("7", "1", "0", "100"))
ROM_VERSION_7_WITHOUT_MODEL = ".".join(("7", "1", "0", "100"))
REGISTRY_VERSION_6 = f"app-{APP_VERSION}_rom-6.0"
REGISTRY_VERSION_7 = f"app-{APP_VERSION}_rom-7.1"

if str(CLOUD_ROOT) not in sys.path:
    sys.path.insert(0, str(CLOUD_ROOT))

from core.errors import ErrorCode, GenerationStatus
from api.schemas import (
    CapabilityOverviewRequest,
    DataCapabilitySchemasRequest,
    GenerateWidgetCardRequest,
)
from api.routes import (
    _build_plugin_stream_response,
    _error_details,
    _error_explanation,
    _heartbeat_sender,
    _normalize_payload,
    _pick_device_rom_version,
)
from app.logger import json_for_log
from config.config import Settings, get_settings
from start_websocket_server import configure_anyio_thread_pool
from models.artifact import ArtifactMeta, WidgetArtifact
from models.capability import (
    AssetCapability,
    DataCapability,
    Dependencies,
    EventCapability,
    RemovedCapability,
    RequiredPackage,
)
from models.generation import (
    CandidateDataBinding,
    DeviceContext,
    EventAction,
    GenerationOptions,
    TaskSpec,
)
from models.service import (
    ArtifactSaveResult,
    WidgetWebSocketErrorMessage,
    WidgetWebSocketResultMessage,
)
from services.artifact_store import ArtifactStore
from custom.a2ui_model_client import (
    A2UIModelClient,
    A2UIModelGenerationError,
    _build_design_test_task_spec,
    build_prompt_log_summary,
    require_generated_dsl,
)
from custom.llmclient import LLMClientOptions
from custom.mep_model_transport import MepModelTransport, PredictEventDecoder
from custom.model_transport import ModelTransportError
from custom.model_runtime import ModelExecutionRuntime, _generate_with_llmclient
from services.card_spec_builder import CardSpecBuilder
from services.card_validator import validate_card
from services.card_validation import validate_card as validate_card_api
from services.card_validation.rule_registry import RuleRegistry
from services.capability_registry import CapabilityRegistry
from services.device_capability_resolver import DeviceCapabilityResolver
from services.edit_request_normalizer import EditRequestNormalizer
from services.generation_pipeline import (
    DslProcessingResult,
    DslProcessorKind,
    QualityIssue,
    get_dsl_processor,
)
from services.ids_client import IDSClient, IDSDeviceCapabilityState
from services.prompt_builder import PromptBuilder
from services.protocol_registry import A2UIProtocolRegistry
from services.response_planner import ResponsePlanner
from services.retry_controller import RetryController
from services.task_spec_builder import TaskSpecBuilder
from services.terse_dsl_nested2_converter import (
    TerseDslNested2ConversionError,
    convert_terse_dsl_nested2_to_a2ui,
    parse_terse_dsl_nested2,
)
from services.validator import ArtifactValidator
from services.widget_generation_service import WidgetGenerationService
from utils.base_utils import sts_config
from utils.download_file_from_url import download_file
from utils.file import delete_file, save_txt_file
from utils.upload_file_obs import UploadFileOSMS


def test_terse_dsl_nested2_converts_nested_tree_to_standard_a2ui():
    source = """
Column("card",
  Text("天气速览", "title"),
  Row("between",
    Text("当前温度", "body"),
    Text("26℃", "success")
  ),
  Progress({value: 68, total: 100})
);
"""
    profile = A2UIProtocolRegistry("a2ui-form-rom6.0-v1").get_profile()

    genui = convert_terse_dsl_nested2_to_a2ui(
        source,
        size="2x2",
        protocol_profile=profile,
    )
    messages = [json_module.loads(line) for line in genui.splitlines()]

    assert len(messages) == 3
    assert messages[0]["createSurface"]["width"] == 140
    assert messages[0]["createSurface"]["height"] == 140
    components = messages[1]["updateComponents"]["components"]
    assert [item["id"] for item in components] == [
        "root",
        "root_0",
        "root_1",
        "root_1_0",
        "root_1_1",
        "root_2",
    ]
    assert components[0]["styles"]["width"] == "matchParent"
    assert components[4]["styles"]["fontColor"] == "#FF64BB5C"


@pytest.mark.parametrize(
    "source",
    [
        'Column("card", Text(fetch("x"), "body"));',
        'Column("card", Unknown("x"));',
        'Column("card", Text("x", {constructor: "bad"}));',
        'Row("between", Text("x", "body"));',
    ],
)
def test_terse_dsl_nested2_rejects_executable_or_unsupported_input(source):
    with pytest.raises(TerseDslNested2ConversionError):
        parse_terse_dsl_nested2(source)


@pytest.mark.asyncio
async def test_terse_dsl_nested2_generation_uses_local_prompt_and_converter(monkeypatch):
    source = """
Column("card",
  Text("静态天气", "title"),
  Text("晴 26℃", "success")
);
"""
    prompts: list[list[dict[str, str]]] = []
    saved_genui: list[str] = []
    selected_conversion_profiles: list[str] = []
    original_protocol_reader = A2UIProtocolRegistry.read_design_protocol_profile

    def generate_nested2(_client, prompt, protocol_profile):
        prompts.append(prompt)
        assert protocol_profile["id"] == "terse-dsl-nested-2"
        assert protocol_profile["format"] == "terse-dsl-nested-2"
        return source

    def save_artifact(_store, artifact):
        saved_genui.append(artifact.genui)
        return ArtifactSaveResult(
            artifactUrl="https://artifact.test/nested2",
            artifactDigest="sha256:nested2",
        )

    def read_nested2_protocol(_registry, profile_id, profiles_root=None):
        if profile_id != "terse-dsl-nested-2":
            return original_protocol_reader(profile_id, profiles_root)
        selected_conversion_profiles.append(profile_id)
        return {
            "version": "v0.9",
            "catalogId": "ohos.a2ui.extended.catalog.form",
            "sizes": {
                "2x2": {"width": 138, "height": 138},
                "2x4": {"width": 298, "height": 138},
            },
        }

    monkeypatch.setattr(A2UIModelClient, "generate", generate_nested2)
    monkeypatch.setattr(
        PromptBuilder,
        "build_design_compact",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Nested-2 must not use the Design Compact prompt builder")
        ),
    )
    monkeypatch.setattr(ArtifactValidator, "validate", lambda *_args: [])
    monkeypatch.setattr(ArtifactStore, "save", save_artifact)
    monkeypatch.setattr(
        A2UIProtocolRegistry,
        "read_design_protocol_profile",
        classmethod(read_nested2_protocol),
    )

    response = await WidgetGenerationService().generate_widget_card_terse_dsl_nested2(
        _model_failure_request()
    )

    assert response.status == GenerationStatus.SUCCESS
    assert response.artifactUrl == "https://artifact.test/nested2"
    assert "TerseDSL-Nested-2" in prompts[0][0]["content"]
    assert '"createSurface"' in saved_genui[0]
    assert selected_conversion_profiles == ["terse-dsl-nested-2"]
    create_surface = json_module.loads(saved_genui[0].splitlines()[0])["createSurface"]
    assert create_surface["width"] == 298


def test_terse_dsl_nested2_prompt_builder_uses_terse_system_prompt():
    task_spec = TaskSpec(**_build_design_test_task_spec())
    prompt = PromptBuilder().build_terse_dsl_nested2(
        task_spec,
        "TERSE_NESTED2_SYSTEM_PROMPT",
    )

    assert prompt[0] == {
        "role": "system",
        "content": "TERSE_NESTED2_SYSTEM_PROMPT",
    }
    assert prompt[1]["role"] == "user"
    assert json_module.loads(prompt[1]["content"]) == task_spec.model_dump(
        mode="json",
        exclude_none=True,
    )


@pytest.mark.asyncio
async def test_terse_dsl_nested2_rejects_dynamic_requests():
    dynamic_request = GenerateWidgetCardRequest(
        uid="test-user",
        prdVer=APP_VERSION,
        device={"romVersion": ROM_VERSION_6},
        userQuery="生成动态天气卡片",
        title="天气",
        description="动态天气",
        candidateDataBindings=[
            {
                "capabilityId": "ViewWeather",
                "arguments": {"districtName": "上海"},
                "writeResultTo": "/data/weather",
            }
        ],
    )
    service = WidgetGenerationService()

    dynamic_response = await service.generate_widget_card_terse_dsl_nested2(
        dynamic_request
    )

    assert dynamic_response.status == GenerationStatus.UNSUPPORTED
    assert dynamic_response.errorCode == "PROTOCOL_CAPABILITY_UNSUPPORTED"


def test_websocket_handler_runs_sync_service_in_threadpool():
    """验证 WebSocket async 入口不会直接同步阻塞事件循环。

    入参：无。
    出参：无；通过源码断言防止回退为 `handler(service, request)` 直调。
    """
    routes_source = (CLOUD_ROOT / "api" / "routes.py").read_text(encoding="utf-8")
    assert "from starlette.concurrency import run_in_threadpool" in routes_source
    assert "await run_in_threadpool(handler, service, request)" in routes_source
    assert "result = handler(service, request)" not in routes_source


@pytest.mark.parametrize(
    ("legacy_message", "expected_explanation"),
    [
        (
            WidgetWebSocketResultMessage(
                operation="generateWidgetCard",
                requestId="request-1",
                data={"status": "success"},
            ),
            "",
        ),
        (
            WidgetWebSocketErrorMessage(
                operation="generateWidgetCard",
                requestId="request-1",
                errorCode="FAILED",
                error={"message": "failed"},
            ),
            (
                "工具执行过程中发生未分类的服务异常，本次调用未成功完成，建议稍后重试。"
                "报错信息如下"
            ),
        ),
    ],
)
def test_plugin_final_response_uses_legacy_string_and_empty_items(
    legacy_message,
    expected_explanation,
):
    response = _build_plugin_stream_response(legacy_message)
    expected_prefix = f"{expected_explanation}：" if expected_explanation else ""

    assert response.errorCode == "0"
    assert response.errorMessage == ""
    assert response.reply.streamInfo.streamContent == expected_prefix + str(legacy_message)
    assert response.reply.items == []


@pytest.mark.parametrize(
    ("error_code", "expected_fragment"),
    [
        ("INVALID_ARGUMENTS", "工具参数传入有误"),
        ("UNKNOWN_CAPABILITY", "包含未注册的能力 ID"),
        ("WRITE_RESULT_CONFLICT", "写入路径存在冲突"),
        ("NO_EFFECTIVE_CAPABILITY", "没有可用于生成卡片的有效能力"),
        ("APP_VERSION_UNSUPPORTED", "App 或 ROM 版本不在服务支持范围内"),
        ("PACKAGE_NOT_INSTALLED", "未安装能力依赖的应用"),
        ("A2UI_GENERATION_FAILED", "卡片生成模型调用失败"),
        ("VALIDATION_FAILED", "存在 error 级校验问题"),
        ("ARTIFACT_UPLOAD_FAILED", "产物保存或上传失败"),
        ("WIDGET_EDIT_DISABLED", "没有开启卡片编辑功能"),
        ("SOURCE_ARTIFACT_NOT_FOUND", "没有找到待编辑的来源卡片产物"),
        ("SOURCE_ARTIFACT_DOWNLOAD_FAILED", "来源卡片产物下载失败"),
        ("SOURCE_ARTIFACT_SCHEMA_UNSUPPORTED", "版本或结构不受当前服务支持"),
        ("SOURCE_ARTIFACT_INVALID", "来源卡片产物内容无效或不完整"),
        ("PROTOCOL_CAPABILITY_UNSUPPORTED", "不支持本次请求中的动态能力或编辑模式"),
        ("TIMEOUT", "工具执行超时"),
        ("FAILED", "未分类的服务异常"),
    ],
)
def test_plugin_error_explanation_distinguishes_business_failures(
    error_code,
    expected_fragment,
):
    explanation = _error_explanation(error_code)

    assert expected_fragment in explanation
    assert explanation.endswith("报错信息如下")


def test_anyio_thread_pool_uses_configured_capacity(monkeypatch):
    assert Settings(_env_file=None).anyio_thread_pool_tokens == 80
    assert Settings(_env_file=None).a2ui_form_model_backend == "mep"
    assert Settings(_env_file=None).design_compact_model_backend == "openai"
    assert Settings(_env_file=None).openai_master_client == "deepseek_platform"
    assert Settings(_env_file=None).openai_fallback_client == "llmclient"
    assert Settings(_env_file=None).enable_default_protocol_profile_fallback is True
    assert Settings(_env_file=None).model_max_concurrency == 20
    assert Settings(_env_file=None).model_queue_timeout_seconds == 120.0
    assert Settings(_env_file=None).model_request_timeout_seconds == 120.0
    assert Settings(_env_file=None).model_failure_max_retry_attempts == 1
    assert Settings(_env_file=None).fallback_model_failure_max_retry_attempts == 1
    assert Settings(_env_file=None).model_failure_retry_initial_delay_seconds == 1.0
    assert Settings(_env_file=None).model_failure_retry_max_delay_seconds == 30.0
    assert Settings(_env_file=None).model_failure_retry_backoff_multiplier == 2.0
    assert Settings(_env_file=None).model_failure_retry_jitter_ratio == 0.2
    assert Settings(_env_file=None).model_prompt_log_preview_chars == 30
    assert Settings(_env_file=None).validation_failure_max_repair_attempts == 1
    settings = get_settings()
    monkeypatch.setattr(settings, "anyio_thread_pool_tokens", 80)

    async def configure_and_read_tokens() -> tuple[int, int]:
        configured_tokens = configure_anyio_thread_pool()
        limiter_tokens = to_thread.current_default_thread_limiter().total_tokens
        return configured_tokens, limiter_tokens

    assert asyncio.run(configure_and_read_tokens()) == (80, 80)


def test_llmclient_settings_are_complete_and_keep_previous_defaults():
    settings = Settings(_env_file=None)
    options = LLMClientOptions()

    assert settings.deepseek_api_key == "AccessService"
    assert settings.deepseek_model == "deepseek-ai/DeepSeek-V4-Flash"
    assert settings.deepseek_ws_url.endswith("/llm/websocket/openai/chat/completions")
    assert settings.deepseek_user == "genui_user"
    assert settings.deepseek_request_id == "genui_ui"
    assert settings.deepseek_temperature == 0.7
    assert settings.deepseek_top_p == 0.9
    assert settings.deepseek_top_k == 1
    assert settings.deepseek_max_tokens == 128_000
    assert settings.deepseek_enable_thinking is False
    assert settings.deepseek_include_usage is True
    assert settings.deepseek_debug_usage is True
    assert settings.deepseek_recv_timeout == 120
    assert options.api_key == settings.deepseek_api_key
    assert options.model == settings.deepseek_model
    assert options.ws_url == settings.deepseek_ws_url


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("deepseek_temperature", -0.1),
        ("deepseek_temperature", 2.1),
        ("deepseek_top_p", -0.1),
        ("deepseek_top_p", 1.1),
        ("deepseek_top_k", 0),
        ("deepseek_max_tokens", 0),
        ("deepseek_recv_timeout", 0),
    ],
)
def test_llmclient_numeric_settings_reject_invalid_values(field_name, invalid_value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field_name: invalid_value})


@pytest.mark.parametrize("attempts", [0, 11])
def test_validation_repair_attempt_count_rejects_out_of_range_values(attempts):
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            validation_failure_max_repair_attempts=attempts,
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "model_failure_max_retry_attempts",
        "fallback_model_failure_max_retry_attempts",
    ],
)
@pytest.mark.parametrize("attempts", [0, 11])
def test_model_failure_retry_attempt_count_rejects_out_of_range_values(
    field_name,
    attempts,
):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field_name: attempts})


def test_model_failure_retry_delay_range_rejects_inverted_values():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            model_failure_retry_initial_delay_seconds=10.0,
            model_failure_retry_max_delay_seconds=5.0,
        )


def test_prompt_log_summary_only_keeps_configured_system_prompt_prefix():
    system_prompt = "系统提示词" * 10
    prompt = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "不得出现在日志中的用户内容"},
    ]

    summary = build_prompt_log_summary(prompt, 30)

    assert summary == {
        "messageCount": 2,
        "systemPromptChars": len(system_prompt),
        "systemPromptPreview": system_prompt[:30],
    }
    assert "用户内容" not in json_module.dumps(summary, ensure_ascii=False)
    assert build_prompt_log_summary(prompt, 0)["systemPromptPreview"] == ""


def test_websocket_handler_sets_request_id_to_logger_context():
    """验证三个 WebSocket 接口在进入业务流程前写入 requestId 日志上下文。

    入参：无。
    出参：无；通过源码顺序断言保证首条请求日志及后续线程池日志都携带 requestId。
    """
    routes_source = (CLOUD_ROOT / "api" / "routes.py").read_text(encoding="utf-8")
    set_context_position = routes_source.index(
        'task_logger.set_session_id(request_id or "None")'
    )
    request_log_position = routes_source.index("widget_operation_ws_payload_received")

    assert "from app.logger import json_for_log, logger, task_logger" in routes_source
    assert set_context_position < request_log_position


def test_json_for_log_uses_standard_json_syntax():
    assert json_for_log(
        {
            "name": "运动健康",
            "enabled": True,
            "missing": None,
            "items": ["a"],
        }
    ) == '{"name":"运动健康","enabled":true,"missing":null,"items":["a"]}'


def test_generation_summary_contains_required_observability_fields(monkeypatch):
    messages: list[str] = []
    monkeypatch.setattr(
        "services.widget_generation_service.logger",
        type("CapturedLogger", (), {"info": staticmethod(messages.append)})(),
    )
    request = GenerateWidgetCardRequest(
        uid="uid-must-not-be-logged",
        device={"romVersion": "6.0"},
        userQuery="生成天气卡片",
        title="天气",
        description="当前天气",
    )

    WidgetGenerationService()._log_generation_summary(
        request,
        status=GenerationStatus.SUCCESS,
        error_code="",
        protocol_profile_id="a2ui-form-rom6.0-v1",
        capability_registry_version=REGISTRY_VERSION_6,
        latency_by_stage={"total": 12.3},
        retry_count=0,
        artifact_digest="sha256:test",
    )

    summary = messages[-1]
    for field in (
        "query_hash=",
        "device_id_hash=",
        "skill_version=",
        "protocol_profile_id=",
        "capability_registry_version=",
        "candidate_capabilities=",
        "effective_capabilities=",
        "removed_capabilities=",
        "status=success",
        "error_code=",
        "latency_by_stage=",
        "retry_count=0",
        "artifact_digest=sha256:test",
        "generation_mode=create",
    ):
        assert field in summary
    assert request.uid not in summary


def test_json_for_log_removes_user_uid_recursively():
    logged = json_module.loads(
        json_for_log(
            {
                "uid": "top-secret-user",
                "userId": "outer-secret-user",
                "nested": {
                    "user_id": "nested-secret-user",
                    "items": [
                        {"userUid": "list-secret-user", "value": 1},
                        {
                            "loc": ["uid"],
                            "input": "invalid-secret-user",
                            "message": "invalid uid",
                        },
                    ],
                },
                "callingUid": "decisionhub",
                "odid": "private-device-odid",
                "sourceArtifactUrl": "https://obs.test/private-artifact.md",
                "udid": "device-identifier",
            }
        )
    )

    assert logged == {
        "nested": {
            "items": [
                {"value": 1},
                {"loc": ["uid"], "message": "invalid uid"},
            ]
        },
        "sourceArtifactUrl": "https://obs.test/private-artifact.md",
        "udid": "device-identifier",
    }


def _device() -> DeviceContext:
    """构造测试设备上下文。

    入参：无。
    出参：DeviceContext 测试对象。
    """
    return DeviceContext(
        deviceId="device-001",
        odid="odid-001",
        romVersion="6.0",
    )


def _ids_installed_apps_payload(*bundle_names: str) -> dict:
    return {
        "nameSpaces": [
            {
                "dataType": "t_ids_kv_ohos_installed_apps",
                "values": [
                    {"data": {"bundleName": bundle_name}}
                    for bundle_name in bundle_names
                ],
            }
        ]
    }


def test_ids_mock_is_enabled_by_default():
    settings = Settings()

    assert settings.enable_ids_mock is True
    assert settings.resolved_mock_ids_response_path == (
        CLOUD_ROOT / "data" / "mock" / "ids_res.json"
    )
    payload = json_module.loads(
        settings.resolved_mock_ids_response_path.read_text(encoding="utf-8")
    )
    serialized = json_module.dumps(payload, ensure_ascii=False)
    assert '"uid"' not in serialized.lower()
    assert IDSClient()._parse_ids_payload(payload).installed_apps == {
        "com.android.bluetooth",
        "com.huawei.hmos.weather",
        "com.huawei.hmos.health.core",
    }


def test_validation_failure_retry_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("WIDGET_SERVICE_ENABLE_VALIDATION_FAILURE_RETRY", raising=False)
    settings = Settings(_env_file=None)

    assert settings.enable_validation_failure_retry is False


def test_model_failure_retry_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("WIDGET_SERVICE_ENABLE_MODEL_FAILURE_RETRY", raising=False)

    assert Settings(_env_file=None).enable_model_failure_retry is False


def test_widget_directive_commands_are_disabled_by_default(monkeypatch):
    monkeypatch.delenv("WIDGET_SERVICE_ENABLE_WIDGET_DIRECTIVE_COMMANDS", raising=False)

    assert Settings(_env_file=None).enable_widget_directive_commands is False


def test_model_failure_retry_can_be_enabled_by_environment(monkeypatch):
    monkeypatch.setenv("WIDGET_SERVICE_ENABLE_MODEL_FAILURE_RETRY", "true")

    assert Settings(_env_file=None).enable_model_failure_retry is True


def test_validation_failure_retry_can_be_enabled_by_environment(monkeypatch):
    monkeypatch.setenv("WIDGET_SERVICE_ENABLE_VALIDATION_FAILURE_RETRY", "true")
    settings = Settings(_env_file=None)

    assert settings.enable_validation_failure_retry is True


def test_system_prompts_are_loaded_from_docs_files():
    """验证首次生成和编辑系统提示词均由配置文件读取。"""
    settings = Settings(_env_file=None)

    assert settings.resolved_system_prompt_file == (
        PROJECT_ROOT.parent / "docs" / "system_prompt.txt"
    )
    assert settings.resolved_edit_system_prompt_file == (
        PROJECT_ROOT.parent / "docs" / "edit_system_prompt.txt"
    )
    assert "你是 A2UI 模型" in settings.system_prompt
    assert "编辑模式附加规则" in settings.edit_system_prompt
    assert "{{CREATE_SYSTEM_PROMPT}}" in settings.edit_system_prompt


def test_edit_system_prompt_file_can_be_overridden(tmp_path):
    """验证编辑提示词配置支持绝对文件路径。"""
    prompt_file = tmp_path / "custom_edit_prompt.txt"
    prompt_file.write_text("自定义编辑提示词", encoding="utf-8")

    settings = Settings(
        _env_file=None,
        edit_system_prompt_file=str(prompt_file),
    )

    assert settings.resolved_edit_system_prompt_file == prompt_file
    assert settings.edit_system_prompt == "自定义编辑提示词"


def test_ids_query_builds_structured_request_and_signature(monkeypatch):
    """验证 IDS 查询请求使用实体封装，并生成真实签名。

    入参：无。
    出参：无；通过断言验证 request body、header 和签名符合预期。
    """
    client = IDSClient()
    monkeypatch.setattr(client.settings, "ids_access_key", "access")
    log_messages: list[str] = []
    monkeypatch.setattr(
        "services.ids_client.logger",
        type("CapturedLogger", (), {"info": staticmethod(log_messages.append)})(),
    )
    secret_key = sts_config.get_sts_config("ids.secret.key")
    request = client.build_installed_apps_query(_device(), "ids-unit-1")
    expected_digest = hmac.new(
        secret_key,
        b"access1000",
        hashlib.sha256,
    ).digest()
    expected_sign = base64.b64encode(expected_digest).decode()

    assert request.method == "POST"
    assert request.body.requestId == "ids-unit-1"
    assert request.body.nameSpaces[0].queryRequestData[0].keys.odid == "odid-001"
    assert [item.dataType for item in request.body.nameSpaces] == [
        "t_ids_kv_ohos_installed_apps",
    ]
    assert request.headers.idsSign != "{{idsSign}}"
    assert request.headers.idsSign.startswith("access;")
    assert len(request.headers.idsSign.split(";")) == 3
    assert client.build_ids_sign(timestamp_ms=1000) == f"access;1000;{expected_sign}"
    assert request.headers.model_dump(by_alias=True)["Content-Type"] == "application/json"
    query_log = next(
        message
        for message in log_messages
        if "ids_device_capability_query_built" in message
    )
    assert 'body={"requestId":"ids-unit-1"' in query_log
    assert "callingUid" not in query_log
    assert "odid-001" not in query_log
    assert "body={'" not in query_log


def test_ids_query_uses_default_odid_when_device_odid_missing():
    """验证设备缺少 odid 时 IDS 查询使用固定默认 odid。

    入参：无。
    出参：无；通过断言验证 request body 中的 odid 兜底值。
    """
    client = IDSClient()
    device = DeviceContext(
        deviceId="device-should-not-be-used",
        romVersion="6.0",
    )

    request = client.build_installed_apps_query(device, "ids-default-odid-1")

    assert (
        request.body.nameSpaces[0].queryRequestData[0].keys.odid
        == "790d8366-cd45-c4d5-6784-06727a549e61"
    )


def test_ids_mock_enabled_reads_existing_file_without_remote(tmp_path, monkeypatch):
    mock_path = tmp_path / "ids_mock.json"
    mock_path.write_text(
        json_module.dumps(
            _ids_installed_apps_payload("com.huawei.hmos.health.core")
        ),
        encoding="utf-8",
    )
    client = IDSClient(mock_response_path=mock_path)
    monkeypatch.setattr(client.settings, "enable_ids_mock", True)

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("IDS remote path must not be used while mock is enabled")

    monkeypatch.setattr(client, "build_installed_apps_query", fail_if_called)
    monkeypatch.setattr(client, "_query_remote_ids", fail_if_called)

    state = client.get_device_capability_state(_device(), "ids-mock-unit-1")

    assert state.installed_apps == {"com.huawei.hmos.health.core"}


def test_ids_mock_enabled_returns_empty_state_when_file_missing(tmp_path, monkeypatch):
    client = IDSClient(mock_response_path=tmp_path / "missing_ids_mock.json")
    monkeypatch.setattr(client.settings, "enable_ids_mock", True)

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("IDS remote path must not be used while mock is enabled")

    monkeypatch.setattr(client, "build_installed_apps_query", fail_if_called)
    monkeypatch.setattr(client, "_query_remote_ids", fail_if_called)

    state = client.get_device_capability_state(_device(), "ids-mock-missing-1")

    assert state == IDSDeviceCapabilityState()


def test_ids_mock_enabled_returns_empty_state_for_invalid_json(tmp_path, monkeypatch):
    mock_path = tmp_path / "invalid_ids_mock.json"
    mock_path.write_text("{not-json", encoding="utf-8")
    client = IDSClient(mock_response_path=mock_path)
    monkeypatch.setattr(client.settings, "enable_ids_mock", True)

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("IDS remote path must not be used while mock is enabled")

    monkeypatch.setattr(client, "build_installed_apps_query", fail_if_called)
    monkeypatch.setattr(client, "_query_remote_ids", fail_if_called)

    state = client.get_device_capability_state(_device(), "ids-mock-invalid-1")

    assert state == IDSDeviceCapabilityState()


def test_ids_mock_enabled_returns_empty_state_when_read_fails(tmp_path, monkeypatch):
    mock_path = tmp_path / "unreadable_ids_mock.json"
    mock_path.write_text("{}", encoding="utf-8")
    client = IDSClient(mock_response_path=mock_path)
    monkeypatch.setattr(client.settings, "enable_ids_mock", True)

    def fail_read(_path):
        raise OSError("mock read failed")

    def fail_remote(*_args, **_kwargs):
        raise AssertionError("IDS remote path must not be used while mock is enabled")

    monkeypatch.setattr("services.ids_client.load_json", fail_read)
    monkeypatch.setattr(client, "build_installed_apps_query", fail_remote)
    monkeypatch.setattr(client, "_query_remote_ids", fail_remote)

    state = client.get_device_capability_state(_device(), "ids-mock-read-failed-1")

    assert state == IDSDeviceCapabilityState()


def test_ids_mock_disabled_ignores_existing_file_and_queries_remote(
    tmp_path,
    monkeypatch,
):
    captured_request: dict = {}
    remote_payload = _ids_installed_apps_payload("com.huawei.hmos.weather")
    mock_path = tmp_path / "ids_mock.json"
    mock_path.write_text(
        json_module.dumps(
            _ids_installed_apps_payload("com.huawei.hmos.health.core")
        ),
        encoding="utf-8",
    )

    def fake_request(method, url, headers, json, timeout, stream, verify, allow_redirects):
        """模拟 IDS HTTP 响应。

        入参：真实 requests.request 调用参数。
        出参：requests.Response 测试对象。
        """
        captured_request.update(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
                "stream": stream,
                "verify": verify,
                "allow_redirects": allow_redirects,
            }
        )
        response = requests.Response()
        response.status_code = 200
        response._content = json_module.dumps(remote_payload).encode("utf-8")
        return response

    client = IDSClient(mock_response_path=mock_path)
    monkeypatch.setattr(client.settings, "enable_ids_mock", False)
    monkeypatch.setattr(client.settings, "ids_query_url", "http://ids.local/query")
    monkeypatch.setattr("services.ids_client.requests.request", fake_request)

    state = client.get_device_capability_state(_device(), "ids-remote-unit-1")

    assert captured_request["method"] == "POST"
    assert captured_request["url"] == "http://ids.local/query"
    assert captured_request["headers"]["idsSign"] != "{{idsSign}}"
    assert captured_request["json"]["requestId"] == "ids-remote-unit-1"
    assert captured_request["stream"] is False
    assert captured_request["verify"] is False
    assert captured_request["allow_redirects"] is False
    assert state.installed_apps == {"com.huawei.hmos.weather"}


def test_ids_parser_ignores_provider_intent_and_permission_namespaces():
    state = IDSClient()._parse_ids_payload(
        {
            "nameSpaces": [
                {
                    "dataType": "provider_state",
                    "values": [{"data": {"providerId": "UG.weather.current"}}],
                },
                {
                    "dataType": "intent_state",
                    "values": [{"data": {"intentName": "Weather_CityCode"}}],
                },
                {
                    "dataType": "permission_state",
                    "values": [{"data": {"permission": "LOCATION", "status": "DENIED"}}],
                },
            ]
        }
    )

    assert state.installed_apps == set()
    assert not hasattr(state, "providers")
    assert not hasattr(state, "intent_targets")
    assert not hasattr(state, "permissions")


@pytest.mark.parametrize(
    ("app_version", "rom_version"),
    [
        ("11.7.5.205", "CLS-AL30 6.0.0.328"),
        ("11.8.0.0", "CLS-AL30 6.3.1.20"),
        ("11.9.9.999", "CLS-AL30 6.9.0.1"),
    ],
)
def test_capability_registry_matches_app_rom_interval(app_version, rom_version):
    assert CapabilityRegistry.from_app_rom_versions(app_version, rom_version) == REGISTRY_VERSION_6


@pytest.mark.parametrize(
    ("app_version", "rom_version"),
    [
        ("12.0.0.0", "6.0"),
        ("11.7.5.205", "7.0"),
    ],
)
def test_capability_registry_excludes_maximum_boundaries(app_version, rom_version):
    with pytest.raises(ValueError, match="range not found"):
        CapabilityRegistry.from_app_rom_versions(app_version, rom_version)


def test_capability_registry_extracts_major_minor_from_full_rom_version():
    assert CapabilityRegistry.normalize_rom_version(ROM_VERSION_6) == "6.0"


@pytest.mark.parametrize(
    ("app_version", "rom_version"),
    [
        ("11.7.5.205", "CLS-AL30 6.0.0.328"),
        ("11.8.0.0", "CLS-AL30 6.3.1.20"),
        ("11.9.9.999", "CLS-AL30 6.9.0.1"),
    ],
)
def test_protocol_registry_matches_app_rom_interval(app_version, rom_version):
    selection = A2UIProtocolRegistry.from_app_rom_versions(app_version, rom_version)

    assert selection.protocol_profile_id == "a2ui-form-rom6.0-v1"
    assert selection.design_profile_id == "design-compact-dsl"


@pytest.mark.parametrize(
    ("app_version", "rom_version"),
    [
        ("12.0.0.0", "6.0"),
        ("11.7.5.205", "7.0"),
    ],
)
def test_protocol_registry_excludes_maximum_boundaries(app_version, rom_version):
    with pytest.raises(ValueError, match="range not found"):
        A2UIProtocolRegistry.from_app_rom_versions(app_version, rom_version)


def test_compact_protocol_selection_uses_configured_default_fallback():
    request = GenerateWidgetCardRequest(
        uid="test-user",
        prdVer="12.0.0.0",
        device={"romVersion": "7.0"},
        userQuery="生成静态卡片",
        title="静态卡片",
        description="协议回退测试",
    )

    selection = WidgetGenerationService()._compact_protocol_selection(request)

    assert selection.protocol_profile_id == "a2ui-form-rom6.0-v1"
    assert selection.design_profile_id == "design-compact-dsl"


def _write_registry_ranges(root: Path, ranges: list[dict], directories: list[str]) -> None:
    root.mkdir()
    for directory in directories:
        (root / directory).mkdir()
    payload = {"schemaVersion": "v1", "ranges": ranges}
    (root / "registry_ranges.json").write_text(
        json_module.dumps(payload),
        encoding="utf-8",
    )


def _protocol_range(
    protocol_profile_id: str,
    design_profile_id: str,
    *,
    app_min: str = "11.0",
    app_max: str = "12.0",
    rom_min: str = "6.0",
    rom_max: str = "7.0",
) -> dict:
    return {
        "protocolProfileId": protocol_profile_id,
        "designProfileId": design_profile_id,
        "appVersion": {
            "minInclusive": app_min,
            "maxExclusive": app_max,
        },
        "romVersion": {
            "minInclusive": rom_min,
            "maxExclusive": rom_max,
        },
    }


def _write_protocol_ranges(root: Path, ranges: list[dict]) -> None:
    root.mkdir()
    for item in ranges:
        protocol_dir = root / item["protocolProfileId"]
        protocol_dir.mkdir(exist_ok=True)
        for filename in ("protocol.md", "component-catalog.md", "data-binding.md"):
            (protocol_dir / filename).write_text("profile", encoding="utf-8")
        design_dir = root / item["designProfileId"]
        design_dir.mkdir(exist_ok=True)
        (design_dir / "PROMPT.md").write_text("prompt", encoding="utf-8")
        (design_dir / "protocol.json").write_text(
            json_module.dumps(
                {
                    "version": "v0.9",
                    "catalogId": "ohos.a2ui.extended.catalog.form",
                    "sizes": {
                        "2x2": {"width": 140, "height": 140},
                        "2x4": {"width": 300, "height": 140},
                    },
                }
            ),
            encoding="utf-8",
        )
    (root / "registry_ranges.json").write_text(
        json_module.dumps({"schemaVersion": "v1", "ranges": ranges}),
        encoding="utf-8",
    )


def test_protocol_registry_rejects_overlapping_ranges(tmp_path):
    root = tmp_path / "protocol_profiles"
    ranges = [
        _protocol_range("profile-one", "design-one"),
        _protocol_range("profile-two", "design-two", app_min="11.5", app_max="12.5"),
    ]
    _write_protocol_ranges(root, ranges)

    with pytest.raises(ValueError, match="Overlapping protocol profile ranges"):
        A2UIProtocolRegistry.from_app_rom_versions("11.8", "6.5", root)


def test_protocol_registry_rejects_inverted_interval(tmp_path):
    root = tmp_path / "protocol_profiles"
    ranges = [
        _protocol_range(
            "profile-one",
            "design-one",
            rom_min="7.0",
            rom_max="6.0",
        )
    ]
    _write_protocol_ranges(root, ranges)

    with pytest.raises(ValueError, match="minInclusive must be less"):
        A2UIProtocolRegistry.from_app_rom_versions("11.8", "6.5", root)


def test_protocol_registry_rejects_missing_design_prompt(tmp_path):
    root = tmp_path / "protocol_profiles"
    ranges = [_protocol_range("profile-one", "design-one")]
    _write_protocol_ranges(root, ranges)
    (root / "design-one" / "PROMPT.md").unlink()

    with pytest.raises(ValueError, match="Design Compact prompt not found"):
        A2UIProtocolRegistry.from_app_rom_versions("11.8", "6.5", root)


def test_protocol_registry_rejects_missing_design_protocol_file(tmp_path):
    root = tmp_path / "protocol_profiles"
    ranges = [_protocol_range("profile-one", "design-one")]
    _write_protocol_ranges(root, ranges)
    (root / "design-one" / "protocol.json").unlink()

    with pytest.raises(ValueError, match="Design Compact protocol file not found"):
        A2UIProtocolRegistry.from_app_rom_versions("11.8", "6.5", root)


def test_protocol_registry_rejects_missing_protocol_directory(tmp_path):
    root = tmp_path / "protocol_profiles"
    root.mkdir()
    design_dir = root / "design-one"
    design_dir.mkdir()
    (design_dir / "PROMPT.md").write_text("prompt", encoding="utf-8")
    (design_dir / "protocol.json").write_text("{}", encoding="utf-8")
    ranges = [_protocol_range("missing-profile", "design-one")]
    (root / "registry_ranges.json").write_text(
        json_module.dumps({"schemaVersion": "v1", "ranges": ranges}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Protocol profile not found"):
        A2UIProtocolRegistry.from_app_rom_versions("11.8", "6.5", root)


def _registry_range(
    registry_version: str,
    app_min: str = "11.0",
    app_max: str = "12.0",
    rom_min: str = "6.0",
    rom_max: str = "7.0",
) -> dict:
    return {
        "registryVersion": registry_version,
        "appVersion": {"minInclusive": app_min, "maxExclusive": app_max},
        "romVersion": {"minInclusive": rom_min, "maxExclusive": rom_max},
    }


def test_capability_registry_rejects_overlapping_ranges(tmp_path):
    root = tmp_path / "capabilities"
    ranges = [
        _registry_range("first"),
        _registry_range("second", app_min="11.5", app_max="12.5"),
    ]
    _write_registry_ranges(root, ranges, ["first", "second"])

    with pytest.raises(ValueError, match="Overlapping"):
        CapabilityRegistry.from_app_rom_versions("11.8", "6.5", root)


def test_capability_registry_rejects_inverted_range(tmp_path):
    root = tmp_path / "capabilities"
    ranges = [_registry_range("first", rom_min="7.0", rom_max="6.0")]
    _write_registry_ranges(root, ranges, ["first"])

    with pytest.raises(ValueError, match="minInclusive"):
        CapabilityRegistry.from_app_rom_versions("11.8", "6.5", root)


def test_capability_registry_rejects_missing_registry_directory(tmp_path):
    root = tmp_path / "capabilities"
    _write_registry_ranges(root, [_registry_range("missing")], [])

    with pytest.raises(ValueError, match="version not found"):
        CapabilityRegistry.from_app_rom_versions("11.8", "6.5", root)


def test_capability_registry_uses_rom_version_as_the_only_rom_level():
    registry = CapabilityRegistry(
        app_version=APP_VERSION,
        device_rom_version=ROM_VERSION_6,
    )

    assert registry.version == REGISTRY_VERSION_6


def test_legacy_registry_request_field_is_ignored():
    request = CapabilityOverviewRequest(
        uid="test-user",
        prdVer=APP_VERSION,
        device={"romVersion": ROM_VERSION_6},
        capabilityRegistryVersion="missing-registry",
    )

    registry = WidgetGenerationService()._capability_registry(request)

    assert "capabilityRegistryVersion" not in request.model_dump()
    assert registry.version == REGISTRY_VERSION_6


def test_public_tool_schemas_do_not_expose_version_overrides():
    schema_root = PROJECT_ROOT / "docs" / "schemas"
    schema_names = [
        "getWidgetCapabilityOverview.schema.json",
        "getDataCapabilitySchemas.schema.json",
        "generateWidgetCard.schema.json",
        "generateWidgetCardCompactDsl.schema.json",
        "generateWidgetCardCompactDslWithDirective.schema.json",
        "generateWidgetCardTerseDslNested2.schema.json",
    ]

    for schema_name in schema_names:
        payload = json_module.loads((schema_root / schema_name).read_text(encoding="utf-8"))
        content_properties = payload["messageEnvelope"]["properties"]["content"]["properties"]
        assert "capabilityRegistryVersion" not in content_properties
        assert "protocolProfileId" not in content_properties


def test_generation_tool_schemas_default_to_2x2():
    schema_root = PROJECT_ROOT / "docs" / "schemas"
    schema_names = [
        "generateWidgetCard.schema.json",
        "generateWidgetCardCompactDsl.schema.json",
        "generateWidgetCardCompactDslWithDirective.schema.json",
        "generateWidgetCardTerseDslNested2.schema.json",
    ]

    for schema_name in schema_names:
        payload = json_module.loads((schema_root / schema_name).read_text(encoding="utf-8"))
        content_properties = payload["messageEnvelope"]["properties"]["content"]["properties"]
        assert content_properties["size"]["default"] == "2x2"


def test_create_request_defaults_to_2x2_when_size_is_omitted():
    request = GenerateWidgetCardRequest(
        uid="test-user",
        device={"romVersion": ROM_VERSION_6},
        userQuery="生成一张天气卡片",
        title="天气",
        description="今日天气",
    )

    normalized = EditRequestNormalizer.normalize_create(request)

    assert normalized.size == "2x2"


def _out_of_range_requests():
    common = {
        "uid": "test-user",
        "prdVer": "12.0.0.0",
        "device": {"romVersion": "7.0"},
    }
    return [
        CapabilityOverviewRequest(**common),
        DataCapabilitySchemasRequest(dataCapabilityIds=["ViewWeather"], **common),
        GenerateWidgetCardRequest(
            userQuery="静态卡片",
            title="静态卡片",
            description="区间回退测试",
            **common,
        ),
    ]


@pytest.mark.parametrize("tool_request", _out_of_range_requests())
def test_all_public_request_types_use_default_registry_fallback(tool_request):
    registry = WidgetGenerationService()._capability_registry(tool_request)

    assert registry.version == REGISTRY_VERSION_6


@pytest.mark.parametrize("tool_request", _out_of_range_requests())
def test_all_public_request_types_reject_unmatched_range_when_fallback_is_off(
    tool_request,
    monkeypatch,
):
    monkeypatch.setattr(
        get_settings(),
        "enable_default_capability_registry_fallback",
        False,
    )

    with pytest.raises(ValueError, match="range not found"):
        WidgetGenerationService()._capability_registry(tool_request)


def test_tool_envelope_reads_only_rom_version():
    assert _pick_device_rom_version({"romVersion": ROM_VERSION_6}) == "6.0"
    assert _pick_device_rom_version({"rom_version": ROM_VERSION_7_WITHOUT_MODEL}) == "6.0"


def test_tool_envelope_maps_optional_content_odid_to_device_context():
    request_id, arguments = _normalize_payload(
        {
            "content": {"odid": "content-odid", "dataCapabilityIds": ["ViewWeather"]},
            "deviceInfo": {
                "locale": "zh-CN",
                "prdVer": APP_VERSION,
                "romVersion": ROM_VERSION_6,
                "odid": "ignored-device-info-odid",
            },
            "session": {"sessionId": "session", "interactionId": "interaction"},
            "userAuth": {"user": {"userId": "user"}},
        },
        "getDataCapabilitySchemas",
    )

    assert request_id == "session&interaction"
    assert arguments["device"]["odid"] == "content-odid"
    assert arguments["device"]["romVersion"] == "6.0"
    assert arguments["device"]["_sourceRomVersion"] == ROM_VERSION_6
    assert "odid" not in arguments

    _, arguments_without_odid = _normalize_payload(
        {
            "content": {},
            "deviceInfo": {
                "romVersion": ROM_VERSION_6,
                "odid": "ignored-device-info-only-odid",
            },
            "session": {},
        },
        "getWidgetCapabilityOverview",
    )
    assert arguments_without_odid["device"]["odid"] is None


def test_data_capability_registry_declares_leaf_samples_and_known_package_dependencies():
    registry = CapabilityRegistry(version=REGISTRY_VERSION_6)
    capabilities = registry.list_data_capabilities()
    assert [item.id for item in capabilities] == [
        "ViewWeather",
        "GetCalendarEvents",
        "GetCountdownDays",
        "GetAppUsageDuration",
        "GetEarphoneInfo",
        "GetPhoneBatteryInfo",
        "GetHealthAndSportSummary",
        "GetSystemMemInfo",
    ]
    assert all(
        set(item.dependencies.model_dump()) == {"requiredPackages"}
        for item in capabilities
    )

    weather = registry.get_data_capability("ViewWeather")
    calendar = registry.get_data_capability("GetCalendarEvents")
    health = registry.get_data_capability("GetHealthAndSportSummary")

    assert weather is not None
    assert weather.dependencies.requiredPackages == [
        RequiredPackage(packageName="com.huawei.hmos.weather")
    ]
    assert weather.outputSchema["properties"]["current"]["properties"][
        "temperatureText"
    ]["sampleValue"] == "26℃"

    assert calendar is not None
    assert calendar.dependencies.requiredPackages == [
        RequiredPackage(packageName="com.huawei.hmos.calendar")
    ]
    assert calendar.outputSchema["properties"]["events"]["items"]["properties"]["title"][
        "sampleValue"
    ] == "产品评审"
    assert health is not None
    assert health.dependencies.requiredPackages == [
        RequiredPackage(packageName="com.huawei.hmos.health.core")
    ]
    assert health.outputSchema["properties"]["sleepScore"]["sampleValue"] == 86


def test_data_capability_output_schema_is_self_contained():
    registry = CapabilityRegistry(version=REGISTRY_VERSION_6)
    capabilities = registry.list_data_capabilities()

    def leaf_nodes(schema):
        if schema.get("type") == "object":
            return [
                leaf
                for child in schema.get("properties", {}).values()
                for leaf in leaf_nodes(child)
            ]
        if schema.get("type") == "array":
            return leaf_nodes(schema["items"])
        return [schema]

    assert not (
        CLOUD_ROOT
        / "data"
        / "capabilities"
        / REGISTRY_VERSION_6
        / "data_model_mappings.json"
    ).exists()
    for capability in capabilities:
        leaves = leaf_nodes(capability.outputSchema)
        assert leaves
        assert all(
            {"type", "description", "sampleValue"}.issubset(leaf)
            for leaf in leaves
        )


def test_event_capability_registry_uses_package_dependencies_only():
    registry = CapabilityRegistry(version=REGISTRY_VERSION_6)
    capabilities = registry.list_event_capabilities()

    assert capabilities
    assert all(
        set(item.dependencies.model_dump()) == {"requiredPackages"}
        for item in capabilities
    )
    health_events = {
        item.id: item
        for item in capabilities
        if item.id in {"event.open.health.sport", "event.open.health.sleep"}
    }
    assert set(health_events) == {
        "event.open.health.sport",
        "event.open.health.sleep",
    }
    assert all(
        item.dependencies.requiredPackages
        == [RequiredPackage(packageName="com.huawei.hmos.health.core")]
        for item in health_events.values()
    )


def test_cloud_capability_registries_are_self_contained_and_valid():
    registry_root = CLOUD_ROOT / "data" / "capabilities"
    version_directories = sorted(registry_root.glob("app-*_rom-*"))
    expected_files = {
        "data_capabilities.json",
        "event_capabilities.json",
        "asset_capabilities.json",
    }

    assert version_directories
    for version_directory in version_directories:
        assert {
            path.name for path in version_directory.iterdir() if path.is_file()
        } == expected_files

        registry = CapabilityRegistry(version=version_directory.name)
        data_capabilities = registry.list_data_capabilities()
        event_capabilities = registry.list_event_capabilities()
        asset_capabilities = registry.list_asset_capabilities()
        capability_ids = [
            *(item.id for item in data_capabilities),
            *(item.id for item in event_capabilities),
            *(item.id for item in asset_capabilities),
        ]
        asset_sources = [item.src for item in asset_capabilities]

        assert data_capabilities
        assert event_capabilities
        assert asset_capabilities
        assert len(capability_ids) == len(set(capability_ids))
        assert len(asset_sources) == len(set(asset_sources))


def test_cloud_registry_covers_offline_skill_capability_inventory():
    """防止离线 Skill 新增能力后，云侧版本目录继续使用不完整的旧快照。"""
    repository_root = PROJECT_ROOT.parent
    offline_reference = (
        repository_root
        / "skills"
        / "harmony-card-generation-offline"
        / "reference"
    )
    data_directory = offline_reference / "capability" / "data-capability"
    offline_data_ids = set()
    for path in data_directory.glob("*.md"):
        if path.name == "index.md":
            continue
        manifest_text = path.read_text(encoding="utf-8").split("```json", 1)[1]
        id_line = next(
            line.strip()
            for line in manifest_text.splitlines()
            if line.strip().startswith('"id":')
        )
        offline_data_ids.add(id_line.split('"')[3])

    event_text = (
        offline_reference / "capability" / "event-capability" / "click-event.md"
    ).read_text(encoding="utf-8")
    event_manifest_text = event_text.split("```json", 1)[1].split("```", 1)[0]
    event_manifest = json_module.loads(event_manifest_text)
    offline_events = set()
    for capability in event_manifest["capabilities"]:
        for target in capability["supportedTargets"]:
            descriptions = [
                page["description"] for page in target.get("pages", [target])
            ]
            offline_events.update(
                (
                    capability["functionCall"],
                    target["intentName"],
                    description,
                )
                for description in descriptions
            )

    asset_text = (
        offline_reference / "design" / "asset-library.md"
    ).read_text(encoding="utf-8")
    offline_assets = {}
    for line in asset_text.splitlines():
        if not line.startswith("| `resources/base/media/"):
            continue
        columns = [column.strip() for column in line.strip("|").split("|")]
        offline_assets[columns[0].strip("`")] = columns[1]

    registry = CapabilityRegistry(version=REGISTRY_VERSION_6)
    cloud_data_ids = {item.id for item in registry.list_data_capabilities()}
    cloud_events = {
        (item.call, item.targetScene, item.description)
        for item in registry.list_event_capabilities()
    }
    cloud_assets = {
        item.src: item.description for item in registry.list_asset_capabilities()
    }
    media_directory = repository_root / "resources" / "base" / "media"
    media_sources = {
        path.relative_to(repository_root).as_posix()
        for path in media_directory.iterdir()
        if path.is_file()
    }

    assert cloud_data_ids == offline_data_ids
    assert cloud_events == offline_events
    assert cloud_assets == offline_assets
    assert media_sources == set(offline_assets)


def test_cloud_asset_registry_matches_online_skill_allowlist():
    skill_asset_path = (
        PROJECT_ROOT.parent
        / "skills"
        / "harmony-card-generation-online"
        / "scripts"
        / "rules"
        / "config"
        / "asset.json"
    )
    cloud_asset_rules_path = CLOUD_ROOT / "data" / "validator_rules" / "config" / "asset.json"
    skill_asset_rules = json_module.loads(skill_asset_path.read_text(encoding="utf-8"))
    cloud_asset_rules = json_module.loads(cloud_asset_rules_path.read_text(encoding="utf-8"))
    registry = CapabilityRegistry(version=REGISTRY_VERSION_6)
    registry_sources = {item.src for item in registry.list_asset_capabilities()}
    expected_sources = set(skill_asset_rules["allowlist"])

    assert registry_sources == expected_sources
    assert cloud_asset_rules == skill_asset_rules
    assert {source for source in registry_sources if source.endswith(".png")} == {
        "resources/base/media/icon_tiktok.png"
    }


def test_data_capability_allows_missing_default_path_and_dependencies():
    capability = DataCapability(
        id="optional.registry.metadata",
        description="缺省注册表元数据",
        outputSchema={
            "type": "object",
            "properties": {
                "value": {
                    "type": "string",
                    "description": "展示值",
                    "sampleValue": "示例",
                }
            },
        },
    )

    assert capability.defaultWriteResultTo is None
    assert capability.dependencies == Dependencies()
    payload = capability.model_dump(mode="json", exclude_none=True)
    assert "defaultWriteResultTo" not in payload
    assert payload["dependencies"] == {"requiredPackages": []}


def test_data_capability_allows_missing_leaf_sample_value():
    capability = DataCapability(
        id="missing.sample",
        description="缺少样例",
        outputSchema={
            "type": "object",
            "properties": {
                "value": {"type": "string", "description": "展示值"}
            },
        },
    )

    assert "sampleValue" not in capability.outputSchema["properties"]["value"]


def test_capability_dependencies_ignore_legacy_fields_and_keep_package_names():
    dependencies = Dependencies(
        minRomVersion="7.0.0",
        minAppVersion=APP_VERSION,
        requiredProviders=["UG.weather.current"],
        requiredIntentTargets=["ViewCalendarEvent"],
        requiredPermissions=["calendar.read"],
        requiredPackages=[
            {
                "packageName": "com.example.app",
                "minVersion": "1.0.0",
            }
        ],
    )

    assert dependencies.model_dump() == {
        "requiredPackages": [{"packageName": "com.example.app"}]
    }


def test_event_capability_accepts_legacy_dependency_metadata():
    capability = EventCapability(
        id="event.legacy",
        call="clickToIntent",
        description="旧版事件能力",
        dependencies={
            "minRomVersion": "7.0.0",
            "requiredIntentTargets": ["ViewCalendarEvent"],
            "requiredPackages": [
                {
                    "packageName": "com.huawei.hmos.calendar",
                    "minVersion": "16.0.0",
                }
            ],
        },
    )

    assert capability.dependencies.model_dump() == {
        "requiredPackages": [{"packageName": "com.huawei.hmos.calendar"}]
    }


@pytest.mark.parametrize(
    "output_schema",
    [
        {"type": "object", "properties": {}},
        {"type": "wat", "description": "非法类型", "sampleValue": "x"},
        {
            "type": "object",
            "properties": {"value": {"type": "string"}},
        },
        {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "数量",
                    "sampleValue": "1",
                }
            },
        },
    ],
)
def test_data_capability_rejects_unusable_output_schema(output_schema):
    with pytest.raises(ValidationError):
        DataCapability(
            id="invalid.output",
            description="非法输出",
            defaultWriteResultTo="/data/invalidOutput",
            outputSchema=output_schema,
            dependencies=Dependencies(),
        )


@pytest.mark.parametrize(
    "default_write_result_to",
    ["", "/data//value", "/data/value~2x", "/data/value/", "/other/value"],
)
def test_data_capability_rejects_invalid_default_write_result_to(
    default_write_result_to,
):
    with pytest.raises(ValidationError):
        DataCapability(
            id="invalid.default.path",
            description="非法默认路径",
            defaultWriteResultTo=default_write_result_to,
            outputSchema={
                "type": "object",
                "properties": {
                    "value": {
                        "type": "string",
                        "description": "展示值",
                        "sampleValue": "示例",
                    }
                },
            },
            dependencies=Dependencies(),
        )


def test_validation_error_details_are_json_safe_and_exclude_input():
    with pytest.raises(ValidationError) as exc_info:
        DataCapability(
            id="invalid.sample.type",
            description="非法样例类型",
            outputSchema={
                "type": "object",
                "properties": {
                    "count": {
                        "type": "integer",
                        "description": "数量",
                        "sampleValue": "not-an-integer",
                    }
                },
            },
        )

    details = _error_details(exc_info.value)

    json_module.dumps(details)
    assert isinstance(details, list)
    assert all("ctx" not in item and "input" not in item for item in details)
    assert "sampleValue does not match type integer" in details[0]["msg"]


@pytest.mark.parametrize(
    ("capability_id", "installed_apps", "is_available"),
    [
        ("ViewWeather", set(), True),
        ("GetCalendarEvents", set(), True),
        ("GetHealthAndSportSummary", set(), False),
        ("GetHealthAndSportSummary", {"COM.HUAWEI.HMOS.HEALTH.CORE"}, False),
        ("GetHealthAndSportSummary", {"com.huawei.hmos.health.core"}, True),
    ],
)
def test_ids_installation_filter_only_applies_to_configured_health_package(
    capability_id,
    installed_apps,
    is_available,
):
    registry = CapabilityRegistry(version=REGISTRY_VERSION_6)
    resolver = DeviceCapabilityResolver(registry)
    ids_state = IDSDeviceCapabilityState(installed_apps=installed_apps)
    available, _, _, removed = resolver.resolve_capability_overview(
        DeviceContext(romVersion="1"),
        ids_state,
    )

    if is_available:
        assert capability_id in {item.id for item in available}
        assert capability_id not in {item.id for item in removed}
    else:
        assert capability_id not in {item.id for item in available}
        capability_removal = next(item for item in removed if item.id == capability_id)
        assert capability_removal.reason == ErrorCode.PACKAGE_NOT_INSTALLED.value


def test_package_dependency_filter_ignores_rom_version():
    registry = CapabilityRegistry(version=REGISTRY_VERSION_6)
    resolver = DeviceCapabilityResolver(registry)
    ids_state = IDSDeviceCapabilityState(
        installed_apps={"com.huawei.hmos.health.core"}
    )
    available, _, _, removed = resolver.resolve_capability_overview(
        DeviceContext(romVersion="1"),
        ids_state,
    )

    assert "GetHealthAndSportSummary" in {item.id for item in available}
    assert "GetHealthAndSportSummary" not in {item.id for item in removed}


def test_ids_installation_filter_default_scope_is_health_only():
    settings = Settings()

    assert settings.ids_installation_filter_package_names == (
        "com.huawei.hmos.health.core",
    )


def test_empty_ids_installation_filter_scope_skips_ids_query(monkeypatch):
    monkeypatch.setattr(get_settings(), "ids_installation_filter_package_names", ())
    registry = CapabilityRegistry(version=REGISTRY_VERSION_6)
    resolver = DeviceCapabilityResolver(registry)

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("IDS should not be queried when the filter scope is empty")

    monkeypatch.setattr(
        resolver.ids_client,
        "get_device_capability_state",
        fail_if_called,
    )
    available, events, _, removed = resolver.resolve_capability_overview(_device())

    assert "GetHealthAndSportSummary" in {item.id for item in available}
    assert "event.open.health.sport" in {item.id for item in events}
    assert removed == []


def test_ids_installation_filter_scope_can_be_reconfigured(monkeypatch):
    monkeypatch.setattr(
        get_settings(),
        "ids_installation_filter_package_names",
        ("com.huawei.hmos.calendar",),
    )
    registry = CapabilityRegistry(version=REGISTRY_VERSION_6)
    resolver = DeviceCapabilityResolver(registry)
    available, _, _, removed = resolver.resolve_capability_overview(
        _device(),
        IDSDeviceCapabilityState(),
    )

    assert "GetCalendarEvents" not in {item.id for item in available}
    assert "GetHealthAndSportSummary" in {item.id for item in available}
    assert next(item for item in removed if item.id == "GetCalendarEvents").reason == (
        ErrorCode.PACKAGE_NOT_INSTALLED.value
    )


def test_dependency_filter_logs_one_json_result(monkeypatch):
    log_messages: list[str] = []
    monkeypatch.setattr(
        "services.device_capability_resolver.logger",
        type("CapturedLogger", (), {"info": staticmethod(log_messages.append)})(),
    )
    registry = CapabilityRegistry(version=REGISTRY_VERSION_6)
    resolver = DeviceCapabilityResolver(registry)
    resolver.resolve_capability_overview(_device(), IDSDeviceCapabilityState())

    dependency_logs = [
        message
        for message in log_messages
        if message.startswith("[Device Resolver] capability_package_dependency_checked ")
    ]
    assert len(dependency_logs) == 1
    result = json_module.loads(dependency_logs[0].split("result=", 1)[1])
    assert result["idsSource"] == "provided"
    assert result["idsQueryStatus"] == "provided"
    assert result["filterPackages"] == ["com.huawei.hmos.health.core"]
    assert set(result["checkedCapabilityIds"]) == {
        "GetHealthAndSportSummary",
        "event.open.health.sport",
        "event.open.health.sleep",
    }
    assert result["checkedPackages"] == ["com.huawei.hmos.health.core"]
    assert result["matchedPackages"] == []
    assert result["missingPackages"] == ["com.huawei.hmos.health.core"]
    assert result["installedPackageCount"] == 0
    assert result["availableDataCapabilityCount"] == 7
    assert result["availableEventCapabilityCount"] > 0
    assert result["availableAssetCapabilityCount"] > 0
    assert {
        item["id"] for item in result["removedCapabilities"]
    } == set(result["checkedCapabilityIds"])
    assert {
        (item["type"], item["reason"])
        for item in result["removedCapabilities"]
    } == {
        ("data", ErrorCode.PACKAGE_NOT_INSTALLED.value),
        ("event", ErrorCode.PACKAGE_NOT_INSTALLED.value),
    }
    assert "capability_id=" not in dependency_logs[0]


def test_card_spec_builder_keeps_only_data_bindings():
    """验证 CardSpecBuilder 只生成数据绑定契约。

    入参：无。
    出参：无；通过断言验证事件不会进入 CardSpec。
    """
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        arguments={"districtName": "上海"},
        writeResultTo="/data/weather",
        candidateOutputFields=["/current/temperatureText"],
    )
    card_spec = CardSpecBuilder().build(
        "2x4",
        [binding],
        "天气速览",
        "查看当前天气",
    )

    assert card_spec.title == "天气速览"
    assert card_spec.description == "查看当前天气"
    assert card_spec.suggestSize == "2x4"
    assert card_spec.dataBindings is not None
    assert card_spec.dataBindings[0].model_dump() == {
        "capabilityId": "ViewWeather",
        "arguments": {"districtName": "上海"},
        "writeResultTo": "/data/weather",
    }
    assert "candidateOutputFields" not in card_spec.model_dump()["dataBindings"][0]


def _task_spec_capability(capability_id: str = "ViewWeather") -> DataCapability:
    return DataCapability(
        id=capability_id,
        description="测试能力",
        defaultWriteResultTo="/data/test",
        inputSchema={},
        outputSchema={
            "type": "object",
            "properties": {
                "current": {
                    "type": "object",
                    "properties": {
                        "temperatureText": {
                            "type": "string",
                            "description": "当前温度",
                            "sampleValue": "26℃",
                        },
                        "condition": {
                            "type": "string",
                            "description": "天气现象",
                            "sampleValue": "多云",
                        },
                    },
                },
                "daily": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "condition": {
                                "type": "string",
                                "description": "每日天气",
                                "sampleValue": "小雨",
                            }
                        },
                    },
                },
            },
        },
        dependencies=Dependencies(),
    )


def test_task_spec_builder_synthesizes_missing_sample_values_once_per_capability(
    monkeypatch,
):
    warnings: list[str] = []
    monkeypatch.setattr(
        "services.task_spec_builder.logger",
        type("CapturedLogger", (), {"warning": staticmethod(warnings.append)})(),
    )
    capability = DataCapability(
        id="LegacyOutputSchema",
        description="旧版输出结构",
        outputSchema={
            "type": "object",
            "properties": {
                "label": {"type": "string", "description": "文本"},
                "count": {"type": "integer", "description": "整数"},
                "ratio": {"type": "number", "description": "数值"},
                "enabled": {"type": "boolean", "description": "开关"},
                "empty": {"type": "null", "description": "空值"},
            },
        },
    )
    binding = CandidateDataBinding(
        capabilityId="LegacyOutputSchema",
        writeResultTo="/data/legacy",
        candidateOutputFields=[
            "/label",
            "/count",
            "/ratio",
            "/enabled",
            "/empty",
        ],
    )

    task_spec = TaskSpecBuilder().build(
        user_query="兼容旧能力",
        size="2x2",
        effective_bindings=[binding],
        effective_data_capabilities=[capability],
        event_candidates=[],
        asset_candidates=[],
    )

    legacy_schema = task_spec.dataModelSchema["data"]["legacy"]
    assert legacy_schema["label"]["sampleValue"] == "示例"
    assert legacy_schema["count"]["sampleValue"] == 0
    assert legacy_schema["ratio"]["sampleValue"] == 0
    assert legacy_schema["enabled"]["sampleValue"] is False
    assert legacy_schema["empty"]["sampleValue"] is None
    assert warnings == [
        "[TaskSpec Builder] output_schema_sample_value_fallback "
        "capability_id=LegacyOutputSchema fallback_count=5"
    ]


def test_candidate_data_binding_rejects_legacy_update_model():
    with pytest.raises(ValidationError):
        CandidateDataBinding(
            capabilityId="ViewWeather",
            arguments={},
            writeResultTo="/data/weather",
            updateModel={"current": {}},
        )


def test_generation_options_rejects_inline_artifact_response():
    with pytest.raises(ValidationError):
        GenerationOptions(returnArtifactInline=True)


def test_task_spec_rejects_legacy_top_level_fields():
    with pytest.raises(ValidationError):
        TaskSpec(
            userQuery="天气卡片",
            size="2x4",
            eventCandidates=[],
            dataModelSchema={"data": {}},
            assetCandidates=[],
            title="天气速览",
            description="当前天气",
            dataModel={"value": {}},
        )


def test_task_spec_builder_projects_valid_object_and_array_fields():
    """验证候选字段由注册表还原，并按 writeResultTo 写入 dataModelSchema。

    入参：无。
    出参：无；通过断言验证非法字段被裁剪、对象和数组层级均正确。
    """
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        arguments={"districtName": "上海"},
        writeResultTo="/data/weather",
        candidateOutputFields=[
            "/current/temperatureText",
            "/daily/0/condition",
            "/daily/1/condition",
            "/current/notRegistered",
        ],
    )
    task_spec = TaskSpecBuilder().build(
        user_query="天气卡片",
        size="2x4",
        effective_bindings=[binding],
        effective_data_capabilities=[_task_spec_capability()],
        event_candidates=[EventAction(id="event.open.weather", call="clickToDeeplink", args={})],
        asset_candidates=[
            AssetCapability(
                id="asset.drop_1",
                src="resources/base/media/drop_1.svg",
                description="雨滴",
            )
        ],
    )

    assert task_spec.dataModelSchema["data"]["weather"] == {
        "current": {
            "temperatureText": {
                "type": "string",
                "description": "当前温度",
                "sampleValue": "26℃",
            }
        },
        "daily": [
            {
                "condition": {
                    "type": "string",
                    "description": "每日天气",
                    "sampleValue": "小雨",
                }
            }
        ],
    }
    assert set(task_spec.model_dump()) == {
        "userQuery",
        "size",
        "eventCandidates",
        "dataModelSchema",
        "assetCandidates",
    }
    assert task_spec.assetCandidates[0]["id"] == "asset.drop_1"


@pytest.mark.parametrize(
    "write_result_to",
    ["", "/data//weather", "/data/weather~2x", "/data/weather/", "/other/weather"],
)
def test_generation_binding_rejects_invalid_write_result_json_pointer(
    write_result_to,
):
    registry = CapabilityRegistry(version=REGISTRY_VERSION_6)
    resolver = DeviceCapabilityResolver(registry)
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        arguments={"districtName": "上海"},
        writeResultTo=write_result_to,
        candidateOutputFields=["/current/condition"],
    )

    effective, capabilities, removed = resolver.resolve_generation_data_bindings(
        [binding]
    )

    assert effective == []
    assert capabilities == []
    assert [item.reason for item in removed] == [ErrorCode.INVALID_ARGUMENTS.value]


def test_task_spec_builder_preserves_output_leaf_path():
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        writeResultTo="/data/weather",
        candidateOutputFields=["/current/condition"],
    )

    task_spec = TaskSpecBuilder().build(
        user_query="天气卡片",
        size="2x4",
        effective_bindings=[binding],
        effective_data_capabilities=[_task_spec_capability()],
        event_candidates=[],
        asset_candidates=[],
    )

    weather_schema = task_spec.dataModelSchema["data"]["weather"]
    assert "display" not in weather_schema
    assert weather_schema["current"]["condition"] == {
        "type": "string",
        "description": "天气现象",
        "sampleValue": "多云",
    }


def test_task_spec_builder_preserves_numeric_object_property_name():
    capability = DataCapability(
        id="NumericObjectKey",
        description="数字对象键测试",
        defaultWriteResultTo="/data/numeric",
        outputSchema={
            "type": "object",
            "properties": {
                "metrics": {
                    "type": "object",
                    "properties": {
                        "0": {
                            "type": "string",
                            "description": "编号为零的指标",
                            "sampleValue": "正常",
                        }
                    },
                }
            },
        },
        dependencies=Dependencies(),
    )
    binding = CandidateDataBinding(
        capabilityId="NumericObjectKey",
        writeResultTo="/data/metrics",
        candidateOutputFields=["/metrics/0"],
    )

    task_spec = TaskSpecBuilder().build(
        user_query="指标卡片",
        size="2x2",
        effective_bindings=[binding],
        effective_data_capabilities=[capability],
        event_candidates=[],
        asset_candidates=[],
    )

    assert task_spec.dataModelSchema["data"]["metrics"]["metrics"] == {
        "0": {
            "type": "string",
            "description": "编号为零的指标",
            "sampleValue": "正常",
        }
    }


@pytest.mark.parametrize(
    "candidate_fields",
    [[], ["/notRegistered"]],
)
def test_task_spec_builder_falls_back_to_all_leaf_fields(candidate_fields):
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        arguments={},
        writeResultTo="/data/weather",
        candidateOutputFields=candidate_fields,
    )

    task_spec = TaskSpecBuilder().build(
        user_query="天气卡片",
        size="2x4",
        effective_bindings=[binding],
        effective_data_capabilities=[_task_spec_capability()],
        event_candidates=[],
        asset_candidates=[],
    )

    weather_schema = task_spec.dataModelSchema["data"]["weather"]
    assert set(weather_schema["current"]) == {"temperatureText", "condition"}
    assert weather_schema["daily"][0]["condition"]["sampleValue"] == "小雨"


def test_task_spec_builder_merges_multiple_capabilities():
    calendar = DataCapability(
        id="GetCalendarEvents",
        description="日历",
        defaultWriteResultTo="/data/calendar",
        outputSchema={
            "type": "object",
            "properties": {
                "events": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "日程标题",
                                "sampleValue": "产品评审",
                            }
                        },
                    },
                }
            },
        },
        dependencies=Dependencies(),
    )
    bindings = [
        CandidateDataBinding(
            capabilityId="ViewWeather",
            writeResultTo="/data/weather",
            candidateOutputFields=["/current/condition"],
        ),
        CandidateDataBinding(
            capabilityId="GetCalendarEvents",
            writeResultTo="/data/calendar",
            candidateOutputFields=["/events/0/title"],
        ),
    ]

    task_spec = TaskSpecBuilder().build(
        user_query="通勤卡片",
        size="2x4",
        effective_bindings=bindings,
        effective_data_capabilities=[_task_spec_capability(), calendar],
        event_candidates=[],
        asset_candidates=[],
    )

    assert task_spec.dataModelSchema["data"]["weather"]["current"]["condition"]
    assert task_spec.dataModelSchema["data"]["calendar"]["events"][0]["title"]


def test_prompt_builder_returns_model_messages():
    """验证 PromptBuilder 返回小模型消息列表。

    入参：无。
    出参：无；通过断言验证 system 和 user 消息内容。
    """
    task_spec = TaskSpecBuilder().build(
        user_query="天气卡片",
        size="2x4",
        effective_bindings=[],
        effective_data_capabilities=[],
        event_candidates=[],
        asset_candidates=[],
    )
    messages = PromptBuilder().build(
        task_spec,
        {
            "id": "a2ui-form-rom6.0-v1",
            "version": "v0.9",
            "catalogId": "ohos.a2ui.extended.catalog.form",
            "sizes": {"2x4": {"width": 300, "height": 140}},
            "componentWhitelist": ["Text", "Column"],
        },
        "无降级",
    )

    assert messages[0]["role"] == "system"
    assert '"userQuery":"天气卡片"' in messages[0]["content"]
    assert "编辑模式附加规则" not in messages[0]["content"]
    assert messages[1] == {"role": "user", "content": "天气卡片"}


@pytest.mark.parametrize("mode", ["create", "edit"])
def test_repair_prompt_inherits_initial_mode_and_contains_errors(mode):
    task_spec = TaskSpecBuilder().build(
        user_query="天气卡片",
        size="2x4",
        effective_bindings=[],
        effective_data_capabilities=[],
        event_candidates=[],
        asset_candidates=[],
    )
    profile = A2UIProtocolRegistry("a2ui-form-rom6.0-v1").get_profile()
    previous_genui = None
    if mode == "edit":
        previous_genui = "old-genui"
    initial_prompt = PromptBuilder().build(
        task_spec,
        profile,
        previous_genui=previous_genui,
    )

    repair_prompt = PromptBuilder().build_repair(
        initial_prompt,
        "invalid-dsl",
        [
            {
                "stage": "validation",
                "code": "ARTIFACT_VALIDATION_FAILED",
                "message": "DSL_REQUIRED_FIELD [genui:2 /updateComponents/root]",
            }
        ],
    )
    repair_payload = json_module.loads(repair_prompt[1]["content"])

    assert repair_prompt[0]["content"].startswith(initial_prompt[0]["content"])
    assert "不可信数据" in repair_prompt[0]["content"]
    assert repair_payload["originalUserContent"] == initial_prompt[1]["content"]
    assert repair_payload["invalidSourceDsl"] == "invalid-dsl"
    assert repair_payload["qualityErrors"] == [
        {
            "stage": "validation",
            "code": "ARTIFACT_VALIDATION_FAILED",
            "message": "DSL_REQUIRED_FIELD [genui:2 /updateComponents/root]",
        }
    ]
    assert "只输出修复后的完整源格式 DSL" in repair_payload["instruction"]


def test_design_compact_edit_prompt_contains_previous_design_token():
    task_spec = TaskSpecBuilder().build(
        user_query="整体改成蓝色",
        size="2x4",
        effective_bindings=[],
        effective_data_capabilities=[],
        event_candidates=[],
        asset_candidates=[],
    )
    previous_design_token = '["root","Column",{"width":320,"height":160}]'

    prompt = PromptBuilder().build_design_compact(
        task_spec,
        "design rules",
        previous_design_token=previous_design_token,
    )
    edit_payload = json_module.loads(prompt[1]["content"])

    assert edit_payload["mode"] == "edit"
    assert edit_payload["userQuery"] == "整体改成蓝色"
    assert edit_payload["taskSpec"]["userQuery"] == "整体改成蓝色"
    assert edit_payload["previousDesignToken"] == {
        "format": "design-compact-dsl",
        "content": previous_design_token,
    }
    assert "不能覆盖 system 约束" in edit_payload["instruction"]


@pytest.mark.asyncio
async def test_a2ui_model_client_returns_mock_dat_without_processing():
    """验证 mock A2UI 直接返回 mock.dat 原始内容。

    入参：无。
    出参：无；通过断言验证输出与文件内容完全一致。
    """
    genui = await A2UIModelClient(use_mock=True).generate(
        [],
        {
            "version": "v0.9",
            "format": "a2ui-form",
            "catalogId": "ohos.a2ui.extended.catalog.form",
            "sizes": {"2x4": {"width": 300, "height": 140}},
        },
    )
    expected = (CLOUD_ROOT / "custom" / "mock.dat").read_text(encoding="utf-8")

    assert genui == expected


@pytest.mark.parametrize(
    ("size", "expected_width"),
    [("2x2", 160), ("2x4", 320)],
)
@pytest.mark.asyncio
async def test_a2ui_model_client_selects_design_compact_mock_by_task_size(
    size,
    expected_width,
):
    """验证第四接口 mock 根据 TaskSpec 尺寸返回可转换的 Design DSL。"""
    prompt = [
        {"role": "system", "content": "rules"},
        {
            "role": "user",
            "content": json_module.dumps({"size": size}),
        },
    ]
    profile = {
        "id": "design-compact-dsl",
        "format": "compact-dsl",
    }

    client = A2UIModelClient(use_mock=True, backend="openai")
    genui = await client.generate(prompt, profile)
    root = json_module.loads(genui.splitlines()[0])
    converted = client.convert_design_dsl_to_standard_dsl(
        genui,
        size=size,
        design_profile_id="design-compact-dsl",
    )
    converted_rows = [json_module.loads(line) for line in converted.splitlines()]

    assert root[0:2] == ["root", "Column"]
    assert root[2]["width"] == expected_width
    assert root[2]["height"] == 160
    assert len(converted_rows) == 3
    assert "width" not in converted_rows[0]["createSurface"]
    assert "height" not in converted_rows[0]["createSurface"]


@pytest.mark.asyncio
async def test_a2ui_model_client_real_mode_forwards_messages(monkeypatch):
    """验证关闭 mock 后把消息原样传给真实模型调用入口。

    入参：无。
    出参：无；通过断言验证消息列表不被协议选择逻辑改写。
    """
    messages = [{"role": "user", "content": "帮我做天气卡片"}]

    class FakeTransport:
        @staticmethod
        def generate(value):
            return "forwarded" if value is messages else "changed"

    client = A2UIModelClient(use_mock=False, transport=FakeTransport())
    monkeypatch.setattr(client, "convert_dsl", lambda value: value)

    assert await client.generate(messages) == "forwarded"


@pytest.mark.asyncio
async def test_design_output_uses_non_empty_mep_result_after_abort(monkeypatch):
    """MEP 6241 已产生 Design 输出时继续交给后续严格转换和校验。"""
    design_dsl = '["root","Column",{"width":160,"height":160},[]]'
    warning_logs: list[str] = []

    class AbortedTransport:
        @staticmethod
        def generate(_messages):
            raise ModelTransportError(
                "model returned error: code=6241",
                code="6241",
                partial_output=design_dsl,
            )

    monkeypatch.setattr(
        "custom.a2ui_model_client.logger.warning",
        warning_logs.append,
    )
    client = A2UIModelClient(
        use_mock=False,
        backend="mep",
        transport=AbortedTransport(),
    )
    profile = {"id": "design-compact-dsl", "format": "compact-dsl"}

    assert await client.generate([], profile) == design_dsl
    assert any("mep_design_output_recovered_after_abort" in item for item in warning_logs)


@pytest.mark.parametrize(
    ("profile", "partial_output"),
    [
        ({"id": "design-compact-dsl", "format": "compact-dsl"}, ""),
        ({"id": "a2ui-form-rom6.0-v1", "format": "a2ui-form"}, "partial"),
    ],
)
@pytest.mark.asyncio
async def test_mep_abort_without_usable_design_output_remains_failure(
    profile,
    partial_output,
):
    class AbortedTransport:
        @staticmethod
        def generate(_messages):
            raise ModelTransportError(
                "model returned error: code=6241",
                code="6241",
                partial_output=partial_output,
            )

    client = A2UIModelClient(
        use_mock=False,
        backend="mep",
        transport=AbortedTransport(),
    )

    with pytest.raises(A2UIModelGenerationError, match="model generation failed"):
        await client.generate([], profile)


@pytest.mark.asyncio
async def test_model_runtime_collects_llmclient_stream(monkeypatch):
    """验证 Runtime 内部适配器聚合原有 llmclient Token 流。"""
    captured: dict = {}
    dsl = '{"createSurface":{"surfaceId":"root"}}'

    async def fake_stream(options, messages):
        captured["api_key"] = options.api_key
        captured["messages"] = messages
        yield "```genui\n"
        yield dsl
        yield "\n```"

    messages = [{"role": "user", "content": "weather"}]
    monkeypatch.setattr("custom.model_runtime.stream_genui", fake_stream)

    result = await asyncio.to_thread(_generate_with_llmclient, messages)

    assert result == f"```genui\n{dsl}\n```"
    assert captured == {
        "api_key": "AccessService",
        "messages": messages,
    }


def test_a2ui_model_client_converts_design_dsl_to_standard_dsl(monkeypatch):
    """验证 A2UI 客户端把 Design Compact DSL 转换为三段标准 DSL。"""
    info_logs: list[str] = []
    monkeypatch.setattr("custom.a2ui_model_client.logger.info", info_logs.append)
    design_dsl = "\n".join(
        (
            "```genui",
            '["root","Column",{"width":160,"height":160,"padding":8,'
            '"itemMargin":8},["title"]]',
            '["title","Text",{"content":{"path":"/data/message"},'
            '"design":"title-s"}]',
            '["/data/message","欢迎回来"]',
            "```",
        )
    )
    result = A2UIModelClient(use_mock=True).convert_design_dsl_to_standard_dsl(
        design_dsl,
        size="2x2",
        design_profile_id="design-compact-dsl",
    )
    messages = [json_module.loads(line) for line in result.splitlines()]

    assert len(messages) == 3
    assert "width" not in messages[0]["createSurface"]
    assert "height" not in messages[0]["createSurface"]
    assert messages[1]["updateComponents"]["root"] == "root"
    assert messages[2]["updateDataModel"]["value"]["data"]["message"] == "欢迎回来"
    conversion_logs = [
        message
        for message in info_logs
        if "design_dsl_conversion_completed" in message
    ]
    assert len(conversion_logs) == 1
    assert "converted_dsl=" in conversion_logs[0]
    assert '\\"createSurface\\"' in conversion_logs[0]


def test_design_converter_expands_latest_design_tokens():
    design_dsl = "\n".join(
        (
            '["root","Column",{"width":160,"height":160,"padding":8,'
            '"itemMargin":4},["hero","title","button","progress","small_progress","check"]]',
            '["hero","Image",{"src":"resources/base/media/sun_max.svg",'
            '"design":"icon-lg","fillColor":"icon_fourth"}]',
            '["title","Text",{"content":"电量","design":"display-s",'
            '"fontColor":"font_primary"}]',
            '["progress","Progress",{"value":68,"total":100,'
            '"design":"ring"}]',
            '["small_progress","Progress",{"value":32,"total":100,'
            '"design":"linear-bar-small"}]',
            '["button","Button",{"label":"info","design":"icon-round"}]',
            '["check","Checkbox",{"label":"省电","select":true,'
            '"design":"check"}]',
        )
    )

    result = A2UIModelClient(use_mock=True).convert_design_dsl_to_standard_dsl(
        design_dsl,
        size="2x2",
        design_profile_id="design-compact-dsl",
    )
    components = json_module.loads(result.splitlines()[1])
    component_by_id = {
        component["id"]: component
        for component in components["updateComponents"]["components"]
    }

    assert component_by_id["hero"]["styles"]["width"] == "matchParent"
    assert component_by_id["hero"]["styles"]["fillColor"] == "#33000000"
    assert component_by_id["title"]["styles"]["fontSize"] == 36
    assert component_by_id["button"]["styles"]["width"] == 30
    assert component_by_id["button"]["styles"]["borderRadius"] == 15
    assert component_by_id["progress"]["styles"]["type"] == "ring"
    assert component_by_id["progress"]["styles"]["strokeWidth"] == 6
    assert component_by_id["progress"]["styles"]["color"] == "#FFF9A01E"
    assert component_by_id["small_progress"]["styles"]["height"] == 4
    assert component_by_id["small_progress"]["styles"]["borderRadius"] == 2
    assert component_by_id["check"]["styles"]["shape"] == "rounded_square"
    assert component_by_id["check"]["styles"]["selectedColor"] == "#33FFFFFF"


def test_design_converter_reads_protocol_file_from_selected_design_profile(monkeypatch):
    design_dsl = (CLOUD_ROOT / "custom" / "mock.design-compact-dsl-2x4.dat").read_text(
        encoding="utf-8"
    )
    selected_profiles: list[str] = []

    def read_design_protocol(_registry, profile_id):
        selected_profiles.append(profile_id)
        return {
            "version": "v1.1",
            "catalogId": "ohos.a2ui.extended.catalog.form",
            "sizes": {"2x4": {"width": 288, "height": 136}},
        }

    monkeypatch.setattr(
        A2UIProtocolRegistry,
        "read_design_protocol_profile",
        classmethod(read_design_protocol),
    )

    result = A2UIModelClient(use_mock=True).convert_design_dsl_to_standard_dsl(
        design_dsl,
        size="2x4",
        design_profile_id="design-next",
    )
    create_surface = json_module.loads(result.splitlines()[0])["createSurface"]

    assert selected_profiles == ["design-next"]
    assert "width" not in create_surface
    assert "height" not in create_surface


def test_a2ui_model_client_design_test_task_spec_covers_weather_capabilities():
    """验证临时 main 使用的数据覆盖天气数据、事件和 SVG 素材。"""
    task_spec = _build_design_test_task_spec()
    weather_schema = task_spec["dataModelSchema"]["data"]["weather"]

    assert task_spec["size"] == "2x2"
    assert len(weather_schema["current"]) == 10
    assert len(weather_schema["daily"][0]) == 5
    assert task_spec["eventCandidates"] == [
        {
            "id": "event.open.weather",
            "call": "clickToDeeplink",
            "args": {
                "uri": "hww://www.huawei.com/totemweather?enterType=share&cityCode=",
            },
        }
    ]
    assert [candidate["id"] for candidate in task_spec["assetCandidates"]] == [
        "asset.sun_max",
        "asset.drop_1",
        "asset.thermometer_sun_fill",
    ]
    assert all(
        candidate["src"].endswith(".svg")
        for candidate in task_spec["assetCandidates"]
    )


def test_a2ui_model_client_builds_qwen_chatml_prompt():
    prompt = MepModelTransport.messages_to_qwen_prompt(
        [
            {"role": "system", "content": "rules"},
            {"role": "user", "content": "weather card"},
        ]
    )

    assert prompt == (
        "<|im_start|>system\nrules<|im_end|>\n"
        "<|im_start|>user\nweather card<|im_end|>\n"
        "<|im_start|>assistant\n"
    )


@pytest.mark.asyncio
async def test_a2ui_model_client_reads_predict_stream(monkeypatch):
    dsl = '{"createSurface":{"surfaceId":"root"}}'
    partial = json_module.dumps({"type": "partialText", "text": dsl})
    final = json_module.dumps(
        {
            "type": "finalText",
            "text": "__last_word___",
            "inputTokenNum": 10,
            "generateTokenNum": 5,
        }
    )
    stream = (
        f"$@START_PREFIX@#{partial}$@END_SUFFIX@#"
        f"$@START_PREFIX@#{final}$@END_SUFFIX@#"
    ).encode()
    captured: dict = {}

    class FakeResponse:
        async def __aenter__(self):
            return self

        async def __aexit__(self, _exc_type, _exc, _traceback):
            return False

        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        async def aiter_bytes():
            yield stream[:17]
            yield stream[17:]

    class FakeHttpClient:
        @staticmethod
        def stream(method, url, **kwargs):
            captured["method"] = method
            captured["url"] = url
            captured.update(kwargs)
            return FakeResponse()

    settings = get_settings()
    monkeypatch.setattr(settings, "model_url", "https://model.test/predict")
    monkeypatch.setattr(settings, "model_bid", "bid-1")
    monkeypatch.setattr(settings, "model_flow_id", "flow-1")
    transport = MepModelTransport(settings, http_client=FakeHttpClient())
    monkeypatch.setattr(transport, "calc_sign", lambda **_kwargs: "signature")

    result = await transport.generate([{"role": "user", "content": "weather"}])

    request_payload = json_module.loads(captured["content"].decode())
    assert result == dsl
    assert captured["url"] == "https://model.test/predict?bId=bid-1&flowId=flow-1"
    assert request_payload["data"]["prompt"].endswith("<|im_start|>assistant\n")


def test_mep_event_decoder_accepts_single_byte_chunk_boundaries():
    partial = json_module.dumps(
        {"type": "partialText", "text": "晴天卡片"},
        ensure_ascii=False,
    )
    final = json_module.dumps(
        {"type": "finalText", "text": "__last_word___"},
        ensure_ascii=False,
    )
    stream = (
        f"noise$@START_PREFIX@#{partial}$@END_SUFFIX@#"
        f"$@START_PREFIX@#{final}$@END_SUFFIX@#"
    ).encode()
    decoder = PredictEventDecoder()
    events = []

    for chunk in stream:
        events.extend(decoder.feed(bytes([chunk])))
    events.extend(decoder.feed(b"", final=True))

    assert [item["type"] for item in events] == ["partialText", "finalText"]
    assert events[0]["text"] == "晴天卡片"


@pytest.mark.asyncio
async def test_model_runtime_shares_concurrency_between_mep_and_llmclient():
    settings = Settings(
        model_max_concurrency=1,
        model_queue_timeout_seconds=1.0,
        model_request_timeout_seconds=1.0,
    )
    lock = threading.Lock()
    active_calls = 0
    max_active_calls = 0

    def enter_call() -> None:
        nonlocal active_calls, max_active_calls
        with lock:
            active_calls += 1
            max_active_calls = max(max_active_calls, active_calls)

    def leave_call() -> None:
        nonlocal active_calls
        with lock:
            active_calls -= 1

    class FakeMepTransport:
        @staticmethod
        async def generate(_messages):
            enter_call()
            try:
                await asyncio.sleep(0.03)
                return "mep-result"
            finally:
                leave_call()

        @staticmethod
        async def aclose():
            return None

    class FakeLlmClientTransport:
        @staticmethod
        def generate(_messages):
            enter_call()
            try:
                time.sleep(0.03)
                return "llmclient-result"
            finally:
                leave_call()

    runtime = ModelExecutionRuntime(
        settings,
        mep_transport=FakeMepTransport(),
        llmclient_transport=FakeLlmClientTransport(),
    )
    try:
        results = await asyncio.gather(
            runtime.generate("mep", []),
            runtime.generate("llmclient", []),
        )
    finally:
        await runtime.aclose()

    assert results == ["mep-result", "llmclient-result"]
    assert max_active_calls == 1


@pytest.mark.asyncio
async def test_model_queue_wait_keeps_websocket_heartbeat_running():
    settings = Settings(
        model_max_concurrency=1,
        model_queue_timeout_seconds=1.0,
        model_request_timeout_seconds=1.0,
    )
    release_first = asyncio.Event()
    first_started = asyncio.Event()
    calls = 0

    class QueuedMepTransport:
        @staticmethod
        async def generate(_messages):
            nonlocal calls
            calls += 1
            if calls == 1:
                first_started.set()
                await release_first.wait()
            return f"result-{calls}"

        @staticmethod
        async def aclose():
            return None

    class UnusedLlmClientTransport:
        @staticmethod
        def generate(_messages):
            pytest.fail("llmclient must not be called")

    class RecordingWebSocket:
        def __init__(self):
            self.frames = 0

        async def send_text(self, _payload):
            self.frames += 1

    runtime = ModelExecutionRuntime(
        settings,
        mep_transport=QueuedMepTransport(),
        llmclient_transport=UnusedLlmClientTransport(),
    )
    websocket = RecordingWebSocket()
    first = asyncio.create_task(runtime.generate("mep", []))
    await first_started.wait()
    queued = asyncio.create_task(runtime.generate("mep", []))
    heartbeat = asyncio.create_task(_heartbeat_sender(websocket, "queue", 0.005))
    try:
        await asyncio.sleep(0.02)
        assert queued.done() is False
        assert websocket.frames >= 1
        release_first.set()
        await asyncio.gather(first, queued)
    finally:
        release_first.set()
        await asyncio.gather(first, queued, return_exceptions=True)
        heartbeat.cancel()
        await heartbeat
        await runtime.aclose()


@pytest.mark.asyncio
async def test_heartbeat_disconnect_does_not_cancel_model_generation():
    model_completed = False

    async def run_model() -> str:
        nonlocal model_completed
        await asyncio.sleep(0.03)
        model_completed = True
        return "generated"

    class DisconnectedWebSocket:
        @staticmethod
        async def send_text(_payload):
            raise RuntimeError("websocket disconnected")

    generation = asyncio.create_task(run_model())
    heartbeat = asyncio.create_task(
        _heartbeat_sender(DisconnectedWebSocket(), "disconnected", 0.005)
    )

    await heartbeat
    assert await generation == "generated"
    assert model_completed is True


@pytest.mark.asyncio
async def test_llmclient_timeout_keeps_shared_permit_until_physical_completion():
    settings = Settings(
        model_max_concurrency=1,
        model_queue_timeout_seconds=0.02,
        model_request_timeout_seconds=0.005,
    )
    llm_started = threading.Event()
    allow_llm_finish = threading.Event()
    mep_calls = 0

    class FakeMepTransport:
        @staticmethod
        async def generate(_messages):
            nonlocal mep_calls
            mep_calls += 1
            return "mep-result"

        @staticmethod
        async def aclose():
            return None

    class SlowLlmClientTransport:
        @staticmethod
        def generate(_messages):
            llm_started.set()
            allow_llm_finish.wait(timeout=1.0)
            return "late-result"

    runtime = ModelExecutionRuntime(
        settings,
        mep_transport=FakeMepTransport(),
        llmclient_transport=SlowLlmClientTransport(),
    )
    llm_task = asyncio.create_task(runtime.generate("llmclient", []))
    try:
        started = await asyncio.to_thread(llm_started.wait, 1.0)
        assert started is True
        with pytest.raises(ModelTransportError) as queue_error:
            await runtime.generate("mep", [])
        assert queue_error.value.code == "MODEL_QUEUE_TIMEOUT"
        assert llm_task.done() is False
        allow_llm_finish.set()
        with pytest.raises(ModelTransportError) as request_error:
            await llm_task
        assert request_error.value.code == "MODEL_REQUEST_TIMEOUT"
    finally:
        allow_llm_finish.set()
        await runtime.aclose()

    assert mep_calls == 0


@pytest.mark.asyncio
async def test_model_runtime_cancels_mep_when_execution_timeout_expires():
    settings = Settings(
        model_max_concurrency=1,
        model_queue_timeout_seconds=1.0,
        model_request_timeout_seconds=0.005,
    )
    cancelled = False

    class SlowMepTransport:
        @staticmethod
        async def generate(_messages):
            nonlocal cancelled
            try:
                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                cancelled = True
                raise
            return "late-result"

        @staticmethod
        async def aclose():
            return None

    class UnusedLlmClientTransport:
        @staticmethod
        def generate(_messages):
            pytest.fail("llmclient must not be called")

    runtime = ModelExecutionRuntime(
        settings,
        mep_transport=SlowMepTransport(),
        llmclient_transport=UnusedLlmClientTransport(),
    )
    try:
        with pytest.raises(ModelTransportError) as error_info:
            await runtime.generate("mep", [])
    finally:
        await runtime.aclose()

    assert error_info.value.code == "MODEL_REQUEST_TIMEOUT"
    assert cancelled is True


@pytest.mark.parametrize(
    ("transport_error", "expected_message"),
    [
        (
            httpx.ReadTimeout(
                "read timeout",
                request=httpx.Request("POST", "https://model.test/predict"),
            ),
            "timed out",
        ),
        (
            httpx.ConnectError(
                "connect failed",
                request=httpx.Request("POST", "https://model.test/predict"),
            ),
            "connection failed",
        ),
        (
            httpx.HTTPStatusError(
                "service unavailable",
                request=httpx.Request("POST", "https://model.test/predict"),
                response=httpx.Response(503),
            ),
            "HTTP request failed: 503",
        ),
    ],
)
@pytest.mark.asyncio
async def test_mep_transport_maps_async_request_errors(
    transport_error,
    expected_message,
):
    class RaisingHttpClient:
        @staticmethod
        def stream(*_args, **_kwargs):
            raise transport_error

    transport = MepModelTransport(
        Settings(_env_file=None),
        http_client=RaisingHttpClient(),
    )

    with pytest.raises(ModelTransportError, match=expected_message):
        await transport._request_stream("https://model.test/predict", "{}", {})


def test_mep_transport_preserves_error_code_and_partial_output():
    with pytest.raises(ModelTransportError) as error_info:
        MepModelTransport._raise_for_model_error(
            {
                "errorCode": 6241,
                "errorMsg": "Early stop due to aborted",
            },
            "partial-design-dsl",
        )

    assert error_info.value.code == "6241"
    assert error_info.value.partial_output == "partial-design-dsl"


@pytest.mark.asyncio
async def test_a2ui_model_client_processes_transport_output_by_profile(monkeypatch):
    """模型传输层不感知 DSL 格式，A2UI 客户端根据协议统一执行后处理。"""
    calls: list[object] = []

    class FakeTransport:
        @staticmethod
        def generate(messages):
            calls.append(messages)
            return "raw-dsl"

    messages = [{"role": "user", "content": "weather card"}]
    a2ui_profile = A2UIProtocolRegistry("a2ui-form-rom6.0-v1").get_profile()
    design_profile = {
        "id": "design-compact-dsl",
        "format": "compact-dsl",
    }
    client = A2UIModelClient(use_mock=False, transport=FakeTransport())
    monkeypatch.setattr(client, "convert_dsl", lambda value: f"standard:{value}")

    assert await client.generate(messages, a2ui_profile) == "standard:raw-dsl"
    assert await client.generate(messages, design_profile) == "raw-dsl"
    assert calls == [messages, messages]


@pytest.mark.asyncio
async def test_design_compact_model_client_returns_streamed_ndjson(monkeypatch):
    """Design Compact 输出通过共用 /predict 传输层返回，不经过 A2UI 转换。"""
    dsl = '["root","Column",{"width":"matchParent"},[]]'
    partial = json_module.dumps({"type": "partialText", "text": dsl})
    final = json_module.dumps(
        {
            "type": "finalText",
            "text": "__last_word___",
            "inputTokenNum": 10,
            "generateTokenNum": 5,
        }
    )
    stream = (
        f"$@START_PREFIX@#{partial}$@END_SUFFIX@#"
        f"$@START_PREFIX@#{final}$@END_SUFFIX@#"
    ).encode()

    class FakeResponse:
        async def __aenter__(self):
            return self

        async def __aexit__(self, _exc_type, _exc, _traceback):
            return False

        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        async def aiter_bytes():
            yield stream[:17]
            yield stream[17:]

    class FakeHttpClient:
        @staticmethod
        def stream(_method, _url, **_kwargs):
            return FakeResponse()

    profile = {
        "id": "design-compact-dsl",
        "format": "compact-dsl",
    }
    settings = get_settings()
    monkeypatch.setattr(settings, "model_url", "https://model.test/predict")
    monkeypatch.setattr(settings, "model_bid", "bid-1")
    monkeypatch.setattr(settings, "model_flow_id", "flow-1")
    transport = MepModelTransport(settings, http_client=FakeHttpClient())
    monkeypatch.setattr(transport, "calc_sign", lambda **_kwargs: "signature")
    client = A2UIModelClient(use_mock=False, transport=transport)
    monkeypatch.setattr(
        client,
        "convert_dsl",
        lambda *_args: pytest.fail("Compact output must not use A2UI conversion"),
    )
    result = await client.generate(
        [{"role": "user", "content": "weather"}],
        profile,
    )

    assert result == dsl


def test_compact_model_client_has_no_artificial_completion_limit():
    source = (CLOUD_ROOT / "custom" / "mep_model_transport.py").read_text(
        encoding="utf-8"
    )

    assert "COMPACT_DSL_MAX_TOKENS" not in source
    assert "max_duration" not in source
    assert "stop_when_compact_complete" not in source
    assert "_generate_compact_from_real_model" not in source


@pytest.mark.asyncio
async def test_a2ui_model_client_redacts_repair_prompt_log(tmp_path, monkeypatch):
    mock_path = tmp_path / "repair.dat"
    mock_path.write_text("repaired", encoding="utf-8")
    messages: list[str] = []
    monkeypatch.setattr(
        "custom.a2ui_model_client.logger.info",
        lambda message: messages.append(str(message)),
    )

    result = await A2UIModelClient(
        use_mock=True,
        mock_data_path=mock_path,
    ).generate_repair(
        [{"role": "user", "content": "sensitive-invalid-dsl"}],
    )

    assert result == "repaired"
    assert any("prompt_redacted=true" in message for message in messages)
    assert all("sensitive-invalid-dsl" not in message for message in messages)


@pytest.mark.parametrize(
    "value",
    ["", "   ", "a2ui_model_error: request timed out"],
)
def test_a2ui_model_client_rejects_output_without_dsl(value):
    with pytest.raises(A2UIModelGenerationError):
        require_generated_dsl(value)


@pytest.mark.asyncio
async def test_a2ui_model_client_wraps_transport_exception(monkeypatch):
    class FailingTransport:
        @staticmethod
        def generate(_messages):
            raise requests.exceptions.Timeout("model timeout")

    with pytest.raises(A2UIModelGenerationError, match="model generation failed"):
        await A2UIModelClient(use_mock=False, transport=FailingTransport()).generate([])


def _model_failure_request() -> GenerateWidgetCardRequest:
    return GenerateWidgetCardRequest(
        uid="test-user",
        prdVer=APP_VERSION,
        device={"romVersion": ROM_VERSION_6},
        userQuery="生成一个静态卡片",
        size="2x4",
        title="静态卡片",
        description="模型失败处理测试",
    )


@pytest.mark.parametrize(
    ("generation_method", "setting_name", "backend"),
    [
        ("generate_widget_card_a2ui_form", "a2ui_form_model_backend", "openai"),
        ("generate_widget_card_compact_dsl", "design_compact_model_backend", "mep"),
        (
            "generate_widget_card_terse_dsl_nested2",
            "design_compact_model_backend",
            "mep",
        ),
    ],
)
@pytest.mark.asyncio
async def test_generation_routes_accept_each_configured_model_backend(
    monkeypatch,
    generation_method,
    setting_name,
    backend,
):
    """第三至第五接口都只从各自服务端配置选择模型后端。"""
    settings = get_settings()
    monkeypatch.setattr(settings, setting_name, backend)
    service = WidgetGenerationService()
    captured: dict[str, object] = {}
    sentinel = object()

    async def capture_route(_request, policy):
        captured["model_backend"] = policy.backend
        captured["design_profile_id"] = policy.design_profile_id
        return sentinel

    monkeypatch.setattr(service, "_generate_widget_card_with_policy", capture_route)

    result = await getattr(service, generation_method)(_model_failure_request())

    assert result is sentinel
    assert captured["model_backend"] == backend
    if generation_method == "generate_widget_card_compact_dsl":
        assert captured["design_profile_id"] == "design-compact-dsl"
    if generation_method == "generate_widget_card_terse_dsl_nested2":
        assert captured["design_profile_id"] == "terse-dsl-nested-2"


@pytest.mark.parametrize(
    "generation_method",
    ["generate_widget_card_a2ui_form", "generate_widget_card_compact_dsl"],
)
@pytest.mark.parametrize("failure_kind", ["empty", "exception"])
@pytest.mark.asyncio
async def test_model_failure_skips_validator_and_artifact_store(
    monkeypatch,
    generation_method,
    failure_kind,
):
    settings = get_settings()

    def fail_generate(_client, _prompt, _profile):
        if failure_kind == "exception":
            raise A2UIModelGenerationError("model stream failed")
        return "   "

    def unexpected_validate(*_args, **_kwargs):
        pytest.fail("model failure must not enter the validator")

    def unexpected_save(*_args, **_kwargs):
        pytest.fail("model failure must not save an artifact")

    monkeypatch.setattr(settings, "enable_model_failure_retry", False)
    monkeypatch.setattr(A2UIModelClient, "generate", fail_generate)
    monkeypatch.setattr(ArtifactValidator, "validate", unexpected_validate)
    monkeypatch.setattr(ArtifactStore, "save", unexpected_save)

    service = WidgetGenerationService()
    response = await getattr(service, generation_method)(_model_failure_request())

    assert response.status == GenerationStatus.FAILED
    assert response.errorCode == ErrorCode.A2UI_GENERATION_FAILED.value
    assert response.artifactUrl == ""
    assert response.artifactDigest == ""
    assert response.message == "卡片创建过程遇到问题了，请稍后再试。"


@pytest.mark.asyncio
async def test_repair_model_failure_does_not_validate_or_save_second_result(monkeypatch):
    settings = get_settings()
    model_calls: list[int] = []
    validation_calls: list[str] = []

    def generate_then_fail(_client, _prompt, _profile=None, **_kwargs):
        model_calls.append(len(model_calls) + 1)
        if len(model_calls) == 1:
            return "invalid-but-nonempty-dsl"
        return ""

    def validate_once(_validator, artifact, _profile):
        validation_calls.append(artifact.genui)
        return ["DSL_REQUIRED_FIELD [genui:1 /createSurface]"]

    def unexpected_save(*_args, **_kwargs):
        pytest.fail("repair model failure must not save an artifact")

    monkeypatch.setattr(settings, "enable_artifact_validation", True)
    monkeypatch.setattr(settings, "enable_model_failure_retry", False)
    monkeypatch.setattr(settings, "enable_validation_failure_retry", True)
    monkeypatch.setattr(A2UIModelClient, "generate", generate_then_fail)
    monkeypatch.setattr(ArtifactValidator, "validate", validate_once)
    monkeypatch.setattr(ArtifactStore, "save", unexpected_save)

    response = await WidgetGenerationService().generate_widget_card_a2ui_form(
        _model_failure_request()
    )

    assert model_calls == [1, 2]
    assert validation_calls == ["invalid-but-nonempty-dsl"]
    assert response.status == GenerationStatus.FAILED
    assert response.errorCode == ErrorCode.A2UI_GENERATION_FAILED.value


@pytest.mark.asyncio
async def test_validation_repair_stops_early_after_second_configured_repair(monkeypatch):
    settings = get_settings()
    generated_values = iter(["dsl-first", "dsl-second", "dsl-third"])
    model_calls = 0
    validation_calls: list[str] = []

    def generate_next(_client, _prompt, _profile=None, **_kwargs):
        nonlocal model_calls
        model_calls += 1
        return next(generated_values)

    def validate_until_third(_validator, artifact, _profile):
        validation_calls.append(artifact.genui)
        if artifact.genui == "dsl-third":
            return []
        return [f"invalid {artifact.genui}"]

    monkeypatch.setattr(settings, "enable_artifact_validation", True)
    monkeypatch.setattr(settings, "enable_model_failure_retry", True)
    monkeypatch.setattr(settings, "enable_validation_failure_retry", True)
    monkeypatch.setattr(settings, "validation_failure_max_repair_attempts", 2)
    monkeypatch.setattr(A2UIModelClient, "generate", generate_next)
    monkeypatch.setattr(ArtifactValidator, "validate", validate_until_third)
    monkeypatch.setattr(
        ArtifactStore,
        "save",
        lambda _store, _artifact: ArtifactSaveResult(
            artifactUrl="https://artifact.test/third-validation-result",
            artifactDigest="sha256:third-validation-result",
        ),
    )

    response = await WidgetGenerationService().generate_widget_card_a2ui_form(
        _model_failure_request()
    )

    assert model_calls == 3
    assert validation_calls == ["dsl-first", "dsl-second", "dsl-third"]
    assert response.status == GenerationStatus.SUCCESS


@pytest.mark.asyncio
async def test_design_compact_validation_error_retries_then_does_not_save(monkeypatch):
    settings = get_settings()
    design_dsl = (CLOUD_ROOT / "custom" / "mock.design-compact-dsl-2x4.dat").read_text(
        encoding="utf-8"
    )
    model_prompts: list[list[dict[str, str]]] = []
    validated_genui: list[str] = []

    def generate_design(_client, prompt, _profile=None, **_kwargs):
        model_prompts.append(prompt)
        return design_dsl

    def validate_standard(_validator, artifact, _profile):
        validated_genui.append(artifact.genui)
        return ["DSL_REQUIRED_FIELD [genui:2 /updateComponents/root]"]

    def unexpected_save(*_args, **_kwargs):
        pytest.fail("invalid Design Compact output must not be saved")

    monkeypatch.setattr(settings, "enable_artifact_validation", True)
    monkeypatch.setattr(settings, "enable_validation_failure_retry", True)
    monkeypatch.setattr(A2UIModelClient, "generate", generate_design)
    monkeypatch.setattr(ArtifactValidator, "validate", validate_standard)
    monkeypatch.setattr(ArtifactStore, "save", unexpected_save)

    response = await WidgetGenerationService().generate_widget_card_compact_dsl(
        _model_failure_request()
    )

    assert response.status == GenerationStatus.FAILED
    assert response.errorCode == ErrorCode.VALIDATION_FAILED.value
    assert len(model_prompts) == 2
    assert len(validated_genui) == 2
    assert '"createSurface"' in validated_genui[0]


@pytest.mark.asyncio
async def test_design_compact_skips_validator_when_validation_is_disabled(monkeypatch):
    settings = get_settings()
    validation_calls: list[str] = []

    def validate_design(_validator, artifact, _profile):
        validation_calls.append(artifact.genui)
        return []

    monkeypatch.setattr(settings, "enable_artifact_validation", False)
    monkeypatch.setattr(ArtifactValidator, "validate", validate_design)
    monkeypatch.setattr(
        ArtifactStore,
        "save",
        lambda _store, _artifact: ArtifactSaveResult(
            artifactUrl="https://artifact.test/design-validation-disabled",
            artifactDigest="sha256:design-validation-disabled",
        ),
    )

    response = await WidgetGenerationService().generate_widget_card_compact_dsl(
        _model_failure_request()
    )

    assert response.status == GenerationStatus.SUCCESS
    assert response.artifactUrl == "https://artifact.test/design-validation-disabled"
    assert validation_calls == []


@pytest.mark.asyncio
async def test_design_compact_validation_error_without_repair_fails(monkeypatch):
    settings = get_settings()

    def validation_error(_validator, _artifact, _profile):
        return ["DSL_REQUIRED_FIELD [genui:2 /updateComponents/root]"]

    def unexpected_save(*_args, **_kwargs):
        pytest.fail("invalid Design Compact output must not be saved")

    monkeypatch.setattr(settings, "enable_artifact_validation", True)
    monkeypatch.setattr(settings, "enable_validation_failure_retry", False)
    monkeypatch.setattr(ArtifactValidator, "validate", validation_error)
    monkeypatch.setattr(ArtifactStore, "save", unexpected_save)

    response = await WidgetGenerationService().generate_widget_card_compact_dsl(
        _model_failure_request()
    )

    assert response.status == GenerationStatus.FAILED
    assert response.errorCode == ErrorCode.VALIDATION_FAILED.value


_SOURCE_FORMAT_CASES = [
    (
        "generate_widget_card_compact_dsl",
        (CLOUD_ROOT / "custom" / "mock.design-compact-dsl-2x4.dat").read_text(
            encoding="utf-8"
        ),
        "design-compact-dsl",
    ),
    (
        "generate_widget_card_terse_dsl_nested2",
        'Column("card", Text("静态天气", "title"), Text("晴 26℃", "success"));',
        "terse-dsl-nested-2",
    ),
]


@pytest.mark.parametrize(
    ("generation_method", "valid_source", "source_format"),
    _SOURCE_FORMAT_CASES,
)
@pytest.mark.asyncio
async def test_conversion_failure_repair_uses_latest_source_format(
    monkeypatch,
    generation_method,
    valid_source,
    source_format,
):
    settings = get_settings()
    model_prompts: list[list[dict[str, str]]] = []
    outputs = iter(["invalid-source-dsl", valid_source])

    def generate_source(_client, prompt, _profile=None, **_kwargs):
        model_prompts.append(prompt)
        return next(outputs)

    monkeypatch.setattr(settings, "enable_artifact_validation", False)
    monkeypatch.setattr(settings, "enable_validation_failure_retry", True)
    monkeypatch.setattr(settings, "validation_failure_max_repair_attempts", 2)
    monkeypatch.setattr(A2UIModelClient, "generate", generate_source)
    monkeypatch.setattr(
        ArtifactStore,
        "save",
        lambda _store, _artifact: ArtifactSaveResult(
            artifactUrl="https://artifact.test/conversion-repaired",
            artifactDigest="sha256:conversion-repaired",
        ),
    )

    service = WidgetGenerationService()
    response = await getattr(service, generation_method)(_model_failure_request())
    repair_payload = json_module.loads(model_prompts[1][1]["content"])

    assert response.status == GenerationStatus.SUCCESS
    assert len(model_prompts) == 2
    assert repair_payload["invalidSourceDsl"] == "invalid-source-dsl"
    assert repair_payload["dslFormat"] == source_format
    assert repair_payload["qualityErrors"][0]["stage"] == "conversion"
    assert repair_payload["qualityErrors"][0]["code"].endswith("CONVERSION_FAILED")


@pytest.mark.parametrize(
    ("generation_method", "valid_source", "source_format"),
    _SOURCE_FORMAT_CASES,
)
@pytest.mark.asyncio
async def test_source_format_validation_error_repairs_original_source_dsl(
    monkeypatch,
    generation_method,
    valid_source,
    source_format,
):
    settings = get_settings()
    model_prompts: list[list[dict[str, str]]] = []
    validation_calls = 0

    def generate_source(_client, prompt, _profile=None, **_kwargs):
        model_prompts.append(prompt)
        return valid_source

    def validate_then_succeed(_validator, _artifact, _profile):
        nonlocal validation_calls
        validation_calls += 1
        if validation_calls == 1:
            return ["validator rejected converted DSL"]
        return []

    monkeypatch.setattr(settings, "enable_artifact_validation", True)
    monkeypatch.setattr(settings, "enable_validation_failure_retry", True)
    monkeypatch.setattr(settings, "validation_failure_max_repair_attempts", 1)
    monkeypatch.setattr(A2UIModelClient, "generate", generate_source)
    monkeypatch.setattr(ArtifactValidator, "validate", validate_then_succeed)
    monkeypatch.setattr(
        ArtifactStore,
        "save",
        lambda _store, _artifact: ArtifactSaveResult(
            artifactUrl="https://artifact.test/validation-repaired",
            artifactDigest="sha256:validation-repaired",
        ),
    )

    service = WidgetGenerationService()
    response = await getattr(service, generation_method)(_model_failure_request())
    repair_payload = json_module.loads(model_prompts[1][1]["content"])

    assert response.status == GenerationStatus.SUCCESS
    assert len(model_prompts) == 2
    assert validation_calls == 2
    assert repair_payload["invalidSourceDsl"] == valid_source
    assert repair_payload["dslFormat"] == source_format
    assert repair_payload["qualityErrors"] == [
        {
            "stage": "validation",
            "code": "ARTIFACT_VALIDATION_FAILED",
            "message": "validator rejected converted DSL",
        }
    ]


@pytest.mark.parametrize(
    ("generation_method", "valid_source", "source_format"),
    _SOURCE_FORMAT_CASES,
)
@pytest.mark.asyncio
async def test_quality_repair_can_transition_from_conversion_to_validation(
    monkeypatch,
    generation_method,
    valid_source,
    source_format,
):
    settings = get_settings()
    model_prompts: list[list[dict[str, str]]] = []
    outputs = iter(["invalid-source-dsl", valid_source, valid_source])
    validation_calls = 0

    def generate_source(_client, prompt, _profile=None, **_kwargs):
        model_prompts.append(prompt)
        return next(outputs)

    def validate_then_succeed(_validator, _artifact, _profile):
        nonlocal validation_calls
        validation_calls += 1
        if validation_calls == 1:
            return ["validator rejected converted DSL"]
        return []

    monkeypatch.setattr(settings, "enable_artifact_validation", True)
    monkeypatch.setattr(settings, "enable_validation_failure_retry", True)
    monkeypatch.setattr(settings, "validation_failure_max_repair_attempts", 2)
    monkeypatch.setattr(A2UIModelClient, "generate", generate_source)
    monkeypatch.setattr(ArtifactValidator, "validate", validate_then_succeed)
    monkeypatch.setattr(
        ArtifactStore,
        "save",
        lambda _store, _artifact: ArtifactSaveResult(
            artifactUrl="https://artifact.test/cross-stage-repaired",
            artifactDigest="sha256:cross-stage-repaired",
        ),
    )

    service = WidgetGenerationService()
    response = await getattr(service, generation_method)(_model_failure_request())
    repair_payloads = [
        json_module.loads(model_prompts[index][1]["content"])
        for index in (1, 2)
    ]

    assert response.status == GenerationStatus.SUCCESS
    assert len(model_prompts) == 3
    assert validation_calls == 2
    assert repair_payloads[0]["invalidSourceDsl"] == "invalid-source-dsl"
    assert repair_payloads[0]["qualityErrors"][0]["stage"] == "conversion"
    assert repair_payloads[1]["invalidSourceDsl"] == valid_source
    assert repair_payloads[1]["qualityErrors"][0]["stage"] == "validation"
    assert all(payload["dslFormat"] == source_format for payload in repair_payloads)


@pytest.mark.parametrize(
    ("generation_method", "valid_source", "source_format"),
    _SOURCE_FORMAT_CASES,
)
@pytest.mark.asyncio
async def test_source_format_validation_repair_stops_at_configured_maximum(
    monkeypatch,
    generation_method,
    valid_source,
    source_format,
):
    settings = get_settings()
    model_prompts: list[list[dict[str, str]]] = []
    validation_calls = 0

    def generate_source(_client, prompt, _profile=None, **_kwargs):
        model_prompts.append(prompt)
        return valid_source

    def always_reject(_validator, _artifact, _profile):
        nonlocal validation_calls
        validation_calls += 1
        return ["persistent validator error"]

    def unexpected_save(*_args, **_kwargs):
        pytest.fail("strict source format validation failure must not be saved")

    monkeypatch.setattr(settings, "enable_artifact_validation", True)
    monkeypatch.setattr(settings, "enable_validation_failure_retry", True)
    monkeypatch.setattr(settings, "validation_failure_max_repair_attempts", 2)
    monkeypatch.setattr(A2UIModelClient, "generate", generate_source)
    monkeypatch.setattr(ArtifactValidator, "validate", always_reject)
    monkeypatch.setattr(ArtifactStore, "save", unexpected_save)

    service = WidgetGenerationService()
    response = await getattr(service, generation_method)(_model_failure_request())
    repair_payloads = [
        json_module.loads(model_prompts[index][1]["content"])
        for index in (1, 2)
    ]

    assert response.status == GenerationStatus.FAILED
    assert response.errorCode == ErrorCode.VALIDATION_FAILED.value
    assert response.artifactUrl == ""
    assert len(model_prompts) == 3
    assert validation_calls == 3
    assert all(payload["dslFormat"] == source_format for payload in repair_payloads)
    assert all(
        payload["qualityErrors"][0]["stage"] == "validation"
        for payload in repair_payloads
    )


@pytest.mark.asyncio
async def test_unknown_processor_exception_does_not_trigger_model_repair(monkeypatch):
    settings = get_settings()
    model_calls = 0
    processor = get_dsl_processor(DslProcessorKind.DESIGN_COMPACT)

    def generate_source(_client, _prompt, _profile=None, **_kwargs):
        nonlocal model_calls
        model_calls += 1
        return "source-dsl"

    def raise_internal_error(_source_dsl, _context):
        raise RuntimeError("converter implementation failed")

    monkeypatch.setattr(settings, "enable_validation_failure_retry", True)
    monkeypatch.setattr(settings, "validation_failure_max_repair_attempts", 2)
    monkeypatch.setattr(A2UIModelClient, "generate", generate_source)
    monkeypatch.setattr(processor, "process", raise_internal_error)

    with pytest.raises(RuntimeError, match="converter implementation failed"):
        await WidgetGenerationService().generate_widget_card_compact_dsl(
            _model_failure_request()
        )

    assert model_calls == 1


@pytest.mark.asyncio
async def test_unknown_validator_exception_does_not_trigger_model_repair(monkeypatch):
    settings = get_settings()
    model_calls = 0
    valid_source = _SOURCE_FORMAT_CASES[0][1]

    def generate_source(_client, _prompt, _profile=None, **_kwargs):
        nonlocal model_calls
        model_calls += 1
        return valid_source

    def raise_internal_error(_validator, _artifact, _profile):
        raise RuntimeError("validator implementation failed")

    monkeypatch.setattr(settings, "enable_artifact_validation", True)
    monkeypatch.setattr(settings, "enable_validation_failure_retry", True)
    monkeypatch.setattr(settings, "validation_failure_max_repair_attempts", 2)
    monkeypatch.setattr(A2UIModelClient, "generate", generate_source)
    monkeypatch.setattr(ArtifactValidator, "validate", raise_internal_error)

    with pytest.raises(RuntimeError, match="validator implementation failed"):
        await WidgetGenerationService().generate_widget_card_compact_dsl(
            _model_failure_request()
        )

    assert model_calls == 1


@pytest.mark.parametrize(
    ("generation_method", "processor_kind"),
    [
        ("generate_widget_card_compact_dsl", DslProcessorKind.DESIGN_COMPACT),
        ("generate_widget_card_terse_dsl_nested2", DslProcessorKind.TERSE_NESTED2),
    ],
)
@pytest.mark.asyncio
async def test_source_format_warning_does_not_trigger_repair(
    monkeypatch,
    generation_method,
    processor_kind,
):
    settings = get_settings()
    model_calls = 0
    processor = get_dsl_processor(processor_kind)

    def generate_source(_client, _prompt, _profile=None, **_kwargs):
        nonlocal model_calls
        model_calls += 1
        return "source-dsl-with-warning"

    def process_with_warning(source_dsl, _context):
        issue = QualityIssue(
            stage="conversion",
            code="SOURCE_FORMAT_WARNING",
            message="non-blocking warning",
            severity="warning",
        )
        return DslProcessingResult(
            source_dsl=source_dsl,
            standard_dsl="standard-a2ui-dsl",
            issues=(issue,),
        )

    monkeypatch.setattr(settings, "enable_artifact_validation", False)
    monkeypatch.setattr(settings, "enable_validation_failure_retry", True)
    monkeypatch.setattr(A2UIModelClient, "generate", generate_source)
    monkeypatch.setattr(processor, "process", process_with_warning)
    monkeypatch.setattr(
        ArtifactStore,
        "save",
        lambda _store, _artifact: ArtifactSaveResult(
            artifactUrl="https://artifact.test/warning",
            artifactDigest="sha256:warning",
        ),
    )

    service = WidgetGenerationService()
    response = await getattr(service, generation_method)(_model_failure_request())

    assert response.status == GenerationStatus.SUCCESS
    assert model_calls == 1


@pytest.mark.parametrize(
    "generation_method",
    [
        "generate_widget_card_compact_dsl",
        "generate_widget_card_terse_dsl_nested2",
    ],
)
@pytest.mark.asyncio
async def test_conversion_failure_does_not_repair_when_switch_is_disabled(
    monkeypatch,
    generation_method,
):
    settings = get_settings()
    model_calls = 0

    def generate_invalid(_client, _prompt, _profile=None):
        nonlocal model_calls
        model_calls += 1
        return "invalid-source-dsl"

    def unexpected_save(*_args, **_kwargs):
        pytest.fail("unconverted source DSL must not be saved")

    monkeypatch.setattr(settings, "enable_artifact_validation", False)
    monkeypatch.setattr(settings, "enable_validation_failure_retry", False)
    monkeypatch.setattr(A2UIModelClient, "generate", generate_invalid)
    monkeypatch.setattr(ArtifactStore, "save", unexpected_save)

    service = WidgetGenerationService()
    response = await getattr(service, generation_method)(_model_failure_request())

    assert model_calls == 1
    assert response.status == GenerationStatus.FAILED
    assert response.errorCode == ErrorCode.VALIDATION_FAILED.value
    assert response.artifactUrl == ""


@pytest.mark.parametrize(
    "generation_method",
    [
        "generate_widget_card_compact_dsl",
        "generate_widget_card_terse_dsl_nested2",
    ],
)
@pytest.mark.asyncio
async def test_conversion_repair_stops_at_configured_maximum(
    monkeypatch,
    generation_method,
):
    settings = get_settings()
    model_calls = 0

    def generate_invalid(_client, _prompt, _profile=None, **_kwargs):
        nonlocal model_calls
        model_calls += 1
        return f"invalid-source-dsl-{model_calls}"

    def unexpected_save(*_args, **_kwargs):
        pytest.fail("unconverted source DSL must not be saved")

    monkeypatch.setattr(settings, "enable_artifact_validation", False)
    monkeypatch.setattr(settings, "enable_validation_failure_retry", True)
    monkeypatch.setattr(settings, "validation_failure_max_repair_attempts", 2)
    monkeypatch.setattr(A2UIModelClient, "generate", generate_invalid)
    monkeypatch.setattr(ArtifactStore, "save", unexpected_save)

    service = WidgetGenerationService()
    response = await getattr(service, generation_method)(_model_failure_request())

    assert model_calls == 3
    assert response.status == GenerationStatus.FAILED
    assert response.errorCode == ErrorCode.VALIDATION_FAILED.value


def test_response_planner_returns_structured_status():
    """验证 ResponsePlanner 返回结构化状态对象。

    入参：无。
    出参：无；通过断言验证 success 和 degraded 的状态、话术、错误码。
    """
    success_plan = ResponsePlanner().plan(
        requested_count=1,
        effective_count=1,
        removed=[],
        has_artifact=True,
    )
    degraded_plan = ResponsePlanner().plan(
        requested_count=1,
        effective_count=0,
        removed=[
            RemovedCapability(
                id="Unknown",
                reason=ErrorCode.UNKNOWN_CAPABILITY.value,
                userReadableReason="能力未注册",
            )
        ],
        has_artifact=True,
    )

    assert success_plan.status == GenerationStatus.SUCCESS
    assert success_plan.errorCode == ""
    assert degraded_plan.status == GenerationStatus.DEGRADED
    assert "能力未注册" in degraded_plan.message


@pytest.mark.asyncio
async def test_retry_controller_retries_when_enabled():
    """验证 RetryController 返回结构化重试结果。

    入参：无。
    出参：无；通过断言验证首次失败后最多重试一次。
    """
    repair_calls: list[tuple[str, list[str]]] = []

    def repair(value: str, errors: list[str]) -> str:
        repair_calls.append((value, errors))
        return "second"

    retry_result = await RetryController().run(
        operation=lambda: "first",
        evaluate=lambda value: ["bad"] if value == "first" else [],
        retry_on_quality_failure=True,
        repair=repair,
    )

    assert retry_result.result == "second"
    assert retry_result.retryCount == 1
    assert retry_result.errors == []
    assert retry_result.initialErrors == ["bad"]
    assert retry_result.repairAttempted is True
    assert repair_calls == [("first", ["bad"])]


@pytest.mark.asyncio
async def test_retry_controller_does_not_retry_validation_failure_by_default():
    operation_calls = 0

    def operation() -> str:
        nonlocal operation_calls
        operation_calls += 1
        return "first"

    retry_result = await RetryController().run(
        operation=operation,
        evaluate=lambda _value: ["bad"],
    )

    assert operation_calls == 1
    assert retry_result.result == "first"
    assert retry_result.retryCount == 0
    assert retry_result.errors == ["bad"]
    assert retry_result.repairAttempted is False


@pytest.mark.asyncio
async def test_retry_controller_saves_second_failure_without_third_call():
    operation_calls = 0
    repair_calls = 0

    def operation() -> str:
        nonlocal operation_calls
        operation_calls += 1
        return "first"

    def repair(_value: str, _errors: list[str]) -> str:
        nonlocal repair_calls
        repair_calls += 1
        return "second"

    retry_result = await RetryController().run(
        operation,
        evaluate=lambda value: [f"bad-{value}"],
        retry_on_quality_failure=True,
        repair=repair,
    )

    assert operation_calls == 1
    assert repair_calls == 1
    assert retry_result.result == "second"
    assert retry_result.errors == ["bad-second"]


@pytest.mark.asyncio
async def test_artifact_store_returns_structured_save_result(tmp_path, monkeypatch):
    """验证 ArtifactStore 保存包含标题和说明的 CardSpec。

    入参：
    - tmp_path：pytest 临时目录。
    - monkeypatch：pytest monkeypatch 工具。
    出参：无；通过断言验证上传结果和 CardSpec 内容。
    """
    mock_storage_dir = tmp_path / "mock_obs"
    monkeypatch.setattr(
        "services.artifact_store.file_obs",
        UploadFileOSMS(
            base_url="https://obs.mock.local/widget",
            mock_storage_dir=mock_storage_dir,
        ),
    )
    artifact = WidgetArtifact(
        genui="{}\n{}\n{}",
        cardSpec={
            "title": "天气速览",
            "description": "查看当前天气",
            "suggestSize": "2x4",
        },
        taskSpec={"dataModelSchema": {"data": {}}},
        meta=ArtifactMeta(
            protocolProfileId="a2ui-form-rom6.0-v1",
            capabilityRegistryVersion=REGISTRY_VERSION_6,
            createdAt=1,
        ),
    )
    design_compact_dsl = (
        '["root","Column",{"width":"matchParent","height":140},[]]'
    )
    result = await ArtifactStore(design_token=design_compact_dsl).save(artifact)

    assert result.artifactUrl.endswith(".md")
    assert result.artifactDigest.startswith("sha256:")
    uploaded_file = mock_storage_dir / result.artifactUrl.rsplit("/", 1)[-1]
    uploaded_content = uploaded_file.read_text(encoding="utf-8")
    assert uploaded_content.startswith("```cardspec\n")
    assert uploaded_content.index("```cardspec") < uploaded_content.index("```genui")
    assert uploaded_content.index("```genui") < uploaded_content.index("```schema")
    assert uploaded_content.count("```genui") == 1
    assert uploaded_content.count("```cardspec") == 1
    assert uploaded_content.count("```taskspec") == 1
    assert uploaded_content.count("```effectivecapabilities") == 1
    assert uploaded_content.count("```removedcapabilities") == 1
    assert uploaded_content.count("```generationplan") == 1
    assert uploaded_content.count("```meta") == 1
    assert uploaded_content.count("```schema") == 1
    assert uploaded_content.count("```designcompactdsl") == 1
    assert uploaded_content.index("```meta") < uploaded_content.index(
        "```designcompactdsl"
    )
    assert uploaded_content.endswith(
        "```designcompactdsl\n"
        '["root","Column",{"width":"matchParent","height":140},[]]\n'
        "```\n"
    )
    assert '"title": "天气速览"' in uploaded_content
    assert '"description": "查看当前天气"' in uploaded_content
    assert '"dataModelSchema"' in uploaded_content
    assert '"protocolProfileId": "a2ui-form-rom6.0-v1"' in uploaded_content
def test_file_utils_save_and_delete_utf8_text(tmp_path):
    """验证文本文件工具支持自动建目录、UTF-8 写入和幂等删除。

    入参：
    - tmp_path：pytest 临时目录。
    出参：无；通过断言验证文件工具行为。
    """
    file_path = tmp_path / "nested" / "artifact.md"

    save_txt_file(file_path, "卡片内容")

    assert file_path.read_text(encoding="utf-8") == "卡片内容"
    delete_file(file_path)
    delete_file(file_path)
    assert not file_path.exists()


def test_upload_file_osms_copies_file_and_returns_mock_url(tmp_path):
    """验证 mock OBS 上传保留本地对象并返回访问地址。

    入参：
    - tmp_path：pytest 临时目录。
    出参：无；通过断言验证上传结果和 mock 落盘文件。
    """
    source_path = tmp_path / "source" / "artifact.md"
    mock_storage_dir = tmp_path / "mock_obs"
    save_txt_file(source_path, "artifact")
    uploader = UploadFileOSMS(
        base_url="https://obs.mock.local/widget",
        mock_storage_dir=mock_storage_dir,
    )

    artifact_url = asyncio.run(uploader.upload_file(source_path))

    assert artifact_url == "https://obs.mock.local/widget/artifact.md"
    assert (mock_storage_dir / "artifact.md").read_text(encoding="utf-8") == "artifact"


def test_shared_download_file_uses_remote_http_options(tmp_path, monkeypatch):
    """验证公共下载方法支持来源 artifact 所需的安全参数。"""

    class FakeResponse:
        status_code = 200
        headers = {"Content-Length": "8"}

        def raise_for_status(self):
            return None

        def iter_content(self, chunk_size):
            assert chunk_size == 8192
            yield b"artifact"

    requested: dict = {}

    def fake_get(url, **kwargs):
        requested["url"] = url
        requested.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("utils.download_file_from_url.requests.get", fake_get)
    target_path = tmp_path / "artifact.md"

    downloaded_path = asyncio.run(
        download_file(
            "https://obs.real.example/widget/artifact.md",
            str(target_path),
            max_size_bytes=1024,
            timeout_seconds=2.5,
            allow_redirects=False,
        )
    )

    assert downloaded_path == str(target_path)
    assert target_path.read_bytes() == b"artifact"
    assert requested == {
        "url": "https://obs.real.example/widget/artifact.md",
        "stream": True,
        "allow_redirects": False,
        "timeout": 2.5,
    }


def test_artifact_validator_rejects_legacy_component_shape():
    """验证服务侧 Validator 会拦截旧组件结构。

    入参：无。
    出参：无；通过断言验证旧版 `type/text` 组件结构会被新校验 API 拦截。
    """
    genui = "\n".join(
        [
            (
                '{"version":"v0.9","createSurface":'
                '{"surfaceId":"card","catalogId":"ohos.a2ui.extended.catalog.form",'
                '"width":300,"height":140}}'
            ),
            (
                '{"version":"v0.9","updateComponents":{"surfaceId":"card",'
                '"root":"root","components":[{"id":"root","type":"Column",'
                '"children":["title"]},{"id":"title","type":"Text","text":"天气"}]}}'
            ),
            '{"version":"v0.9","updateDataModel":{"surfaceId":"card","path":"/","value":{}}}',
        ]
    )
    artifact = WidgetArtifact(
        genui=genui,
        cardSpec={"suggestSize": "2x4"},
        taskSpec={"dataModelSchema": {"data": {}}},
        meta=ArtifactMeta(
            protocolProfileId="a2ui-form-rom6.0-v1",
            capabilityRegistryVersion=REGISTRY_VERSION_6,
            createdAt=1,
        ),
    )
    errors = ArtifactValidator().validate(
        artifact,
        {"id": "a2ui-form-rom6.0-v1"},
    )

    assert any("DSL_COMPONENT_REQUIRED_FIELD" in item for item in errors)


def test_card_validation_is_exposed_as_in_process_api():
    reporter = validate_card_api(dsl_text="not-json")
    validator_source = (CLOUD_ROOT / "services" / "validator.py").read_text(
        encoding="utf-8"
    )

    assert reporter.has_code("DSL_JSON_PARSE_FAILED")
    assert "services.card_validation" in validator_source
    assert "subprocess" not in validator_source
    assert "validate_card.py" not in validator_source


def test_card_validation_loads_latest_online_rule_snapshot():
    rules = RuleRegistry(CLOUD_ROOT / "data" / "validator_rules")

    assert set(rules.capabilities) == {
        "GetAppUsageDuration",
        "GetCalendarEvents",
        "GetCountdownDays",
        "GetEarphoneInfo",
        "GetHealthAndSportSummary",
        "GetPhoneBatteryInfo",
        "GetSystemMemInfo",
        "ViewWeather",
    }
    assert rules.expression["maxLength"] == 2048
    assert rules.expression["allowedFunctions"] == ["size"]
    assert rules.protocol["sizes"]["2x4"]["borderRadius"] == 22


def test_card_validation_snapshot_covers_all_online_runtime_files():
    repository_root = PROJECT_ROOT.parent
    skill_scripts = (
        repository_root / "skills" / "harmony-card-generation-online" / "scripts"
    )
    skill_validators = skill_scripts / "validators"
    service_validators = CLOUD_ROOT / "services" / "card_validation"
    skill_rules = skill_scripts / "rules"
    service_rules = CLOUD_ROOT / "data" / "validator_rules"

    skill_validator_names = {
        path.name for path in skill_validators.glob("*.py") if path.is_file()
    }
    service_validator_names = {
        path.name for path in service_validators.glob("*.py") if path.is_file()
    }
    assert service_validator_names == skill_validator_names

    skill_rule_paths = {
        path.relative_to(skill_rules) for path in skill_rules.rglob("*.json")
    }
    service_rule_paths = {
        path.relative_to(service_rules) for path in service_rules.rglob("*.json")
    }
    assert service_rule_paths == skill_rule_paths

    for relative_path in skill_rule_paths:
        skill_rule = json_module.loads(
            (skill_rules / relative_path).read_text(encoding="utf-8")
        )
        service_rule = json_module.loads(
            (service_rules / relative_path).read_text(encoding="utf-8")
        )
        assert service_rule == skill_rule


def _a2ui_genui_with_image(
    source: str,
    background_color: str = "#123456",
) -> str:
    return "\n".join(
        [
            json_module.dumps(
                {
                    "version": "v0.9",
                    "createSurface": {
                        "surfaceId": "card",
                        "catalogId": "ohos.a2ui.extended.catalog.form",
                    },
                },
                separators=(",", ":"),
            ),
            json_module.dumps(
                {
                    "version": "v0.9",
                    "updateComponents": {
                        "surfaceId": "card",
                        "root": "root",
                        "components": [
                            {
                                "id": "root",
                                "component": "Column",
                                "children": ["image"],
                                "styles": {
                                    "width": "matchParent",
                                    "height": "matchParent",
                                    "padding": 12,
                                    "borderRadius": 18,
                                    "clip": True,
                                    "backgroundColor": background_color,
                                },
                            },
                            {
                                "id": "image",
                                "component": "Image",
                                "src": source,
                                "styles": {
                                    "width": 116,
                                    "height": 116,
                                    "objectFit": "contain",
                                },
                            },
                        ],
                    },
                },
                separators=(",", ":"),
            ),
            json_module.dumps(
                {
                    "version": "v0.9",
                    "updateDataModel": {
                        "surfaceId": "card",
                        "path": "/",
                        "value": {"ready": True},
                    },
                },
                separators=(",", ":"),
            ),
        ]
    )


def test_card_validator_uses_effective_asset_candidates_without_external_reads():
    source = "resources/base/media/air_fill.svg"
    validator_source = (
        CLOUD_ROOT / "services" / "card_validator.py"
    ).read_text(encoding="utf-8")

    selected_report = validate_card(
        _a2ui_genui_with_image(source),
        {"title": "天气", "description": "今日天气", "suggestSize": "2x2"},
        allowed_asset_sources={source},
    )
    unselected_report = validate_card(
        _a2ui_genui_with_image(source),
        {"title": "天气", "description": "今日天气", "suggestSize": "2x2"},
        allowed_asset_sources=set(),
    )
    standalone_report = validate_card(
        _a2ui_genui_with_image(source),
        {"title": "天气", "description": "今日天气", "suggestSize": "2x2"},
    )

    assert not any("EFFECTIVE_ASSET_NOT_ALLOWED" in item for item in selected_report.errors)
    assert any("EFFECTIVE_ASSET_NOT_ALLOWED" in item for item in unselected_report.errors)
    assert not any("EFFECTIVE_ASSET_NOT_ALLOWED" in item for item in standalone_report.errors)
    assert "skills" not in validator_source.lower()
    assert "subprocess" not in validator_source


def test_card_validator_does_not_apply_legacy_color_quality_rule():
    valid_report = validate_card(
        _a2ui_genui_with_image("resources/base/media/air_fill.svg"),
        {"title": "天气", "description": "今日天气", "suggestSize": "2x2"},
        allowed_asset_sources={"resources/base/media/air_fill.svg"},
    )
    invalid_report = validate_card(
        _a2ui_genui_with_image(
            "resources/base/media/air_fill.svg",
            background_color="blue",
        ),
        {"title": "天气", "description": "今日天气", "suggestSize": "2x2"},
        allowed_asset_sources={"resources/base/media/air_fill.svg"},
    )

    assert valid_report.errors == []
    assert invalid_report.errors == []
