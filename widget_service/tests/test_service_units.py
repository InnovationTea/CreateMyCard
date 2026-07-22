# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
# ruff: noqa: E402, I001
import asyncio
import base64
import hashlib
import hmac
import json as json_module
import sys
import uuid
from pathlib import Path

import requests
import pytest
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
from api.schemas import GenerateWidgetCardRequest
from api.routes import _error_details, _normalize_payload, _pick_device_rom_version
from app.logger import json_for_log
from config.config import Settings, get_settings
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
from services.artifact_store import ArtifactStore
from custom.a2ui_model_client import A2UIModelClient
from services.card_spec_builder import CardSpecBuilder
from services.card_validator import validate_card
from services.card_validation import validate_card as validate_card_api
from services.card_validation.rule_registry import RuleRegistry
from services.capability_registry import CapabilityRegistry
from services.device_capability_resolver import DeviceCapabilityResolver
from services.ids_client import IDSClient, IDSDeviceCapabilityState
from services.prompt_builder import PromptBuilder
from services.protocol_registry import A2UIProtocolRegistry
from services.response_planner import ResponsePlanner
from services.retry_controller import RetryController
from services.task_spec_builder import TaskSpecBuilder
from services.validator import ArtifactValidator
from services.widget_generation_service import WidgetGenerationService
from utils.base_utils import sts_config
from utils.download_file_from_url import download_file
from utils.file import delete_file, save_txt_file
from utils.upload_file_obs import UploadFileOSMS


def test_websocket_handler_runs_sync_service_in_threadpool():
    """验证 WebSocket async 入口不会直接同步阻塞事件循环。

    入参：无。
    出参：无；通过源码断言防止回退为 `handler(service, request)` 直调。
    """
    routes_source = (CLOUD_ROOT / "api" / "routes.py").read_text(encoding="utf-8")
    assert "from starlette.concurrency import run_in_threadpool" in routes_source
    assert "await run_in_threadpool(handler, service, request)" in routes_source
    assert "result = handler(service, request)" not in routes_source


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


def test_capability_registry_version_is_derived_from_prd_and_rom_versions():
    """验证能力版本目录由 prdVer 和 romVersion 推导。

    入参：无。
    出参：无；通过随机版本参数断言版本文件夹名符合约定。
    """
    random_patch = uuid.uuid4().int % 100000
    prd_ver = f"88.7.{random_patch}"
    rom_ver = ROM_VERSION_6

    version = CapabilityRegistry.from_app_rom_versions(prd_ver, rom_ver)

    assert version == f"app-{prd_ver}_rom-6.0"


def test_capability_registry_extracts_major_minor_from_full_rom_version():
    version = CapabilityRegistry.from_app_rom_versions(
        APP_VERSION,
        ROM_VERSION_6,
    )

    assert version == REGISTRY_VERSION_6
    assert CapabilityRegistry.from_app_rom_versions(
        APP_VERSION,
        ROM_VERSION_7,
    ) == REGISTRY_VERSION_7


def test_capability_registry_uses_rom_version_as_the_only_rom_level():
    registry = CapabilityRegistry(
        app_version=APP_VERSION,
        device_rom_version=ROM_VERSION_6,
    )

    assert registry.version == REGISTRY_VERSION_6


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
        "GetAppUsageDurationAndPower",
        "GetBluetoothEarphoneStatus",
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
        if message.startswith("capability_package_dependency_checked ")
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
    assert result["availableDataCapabilityCount"] == 5
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
        "output_schema_sample_value_fallback "
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


def test_compact_dsl_profile_builds_isolated_prompt():
    """验证极简协议 profile 和 Prompt 不依赖旧 A2UI 消息结构。"""
    profile = A2UIProtocolRegistry("compact-dsl-v1").get_profile()
    task_spec = TaskSpecBuilder().build(
        user_query="天气卡片",
        size="2x4",
        effective_bindings=[],
        effective_data_capabilities=[],
        event_candidates=[],
        asset_candidates=[],
    )

    messages = PromptBuilder().build(task_spec, profile)
    system_prompt = messages[0]["content"]

    assert profile["format"] == "compact-dsl"
    assert A2UIProtocolRegistry("a2ui-form-rom6.0-v1").get_profile()["format"] == "a2ui-form"
    a2ui_profile = A2UIProtocolRegistry("a2ui-form-rom6.0-v1").get_profile()
    assert profile["componentWhitelist"] == a2ui_profile["componentWhitelist"]
    assert len(profile["componentWhitelist"]) == 10
    assert "只输出裸 NDJSON" in system_prompt
    assert "不输出 Markdown 围栏" in system_prompt
    assert "Grid" not in profile["componentWhitelist"]
    assert "Generation context JSON:" in system_prompt


def test_a2ui_model_client_returns_mock_dat_without_processing():
    """验证 mock A2UI 直接返回 mock.dat 原始内容。

    入参：无。
    出参：无；通过断言验证输出与文件内容完全一致。
    """
    genui = A2UIModelClient(use_mock=True).generate(
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


def test_a2ui_model_client_selects_compact_dsl_mock_by_profile():
    """验证 mock 客户端只在极简 profile 下切换为 tuple NDJSON。"""
    profile = A2UIProtocolRegistry("compact-dsl-v1").get_profile()

    genui = A2UIModelClient(use_mock=True).generate([], profile)
    expected = (CLOUD_ROOT / "custom" / "mock.compact-dsl.dat").read_text(
        encoding="utf-8"
    )

    assert genui == expected
    assert all(
        isinstance(json_module.loads(line), list)
        for line in genui.splitlines()
        if line.strip()
    )


def test_a2ui_model_client_real_mode_forwards_messages(monkeypatch):
    """验证关闭 mock 后把消息原样传给真实模型调用入口。

    入参：无。
    出参：无；通过断言验证消息列表不被协议选择逻辑改写。
    """
    messages = [{"role": "user", "content": "帮我做天气卡片"}]
    monkeypatch.setattr(
        A2UIModelClient,
        "_generate_from_real_model",
        lambda self, value: "forwarded" if value is messages else "changed",
    )

    assert A2UIModelClient(use_mock=False).generate(messages) == "forwarded"


def test_a2ui_model_client_isolates_compact_and_a2ui_generators(monkeypatch):
    """Tool 4 uses direct Compact output while Tool 3 keeps the A2UI path."""
    calls: list[tuple[str, object]] = []

    def generate_a2ui(_client, messages):
        calls.append(("a2ui", messages))
        return "a2ui-output"

    def generate_compact(_client, messages):
        calls.append(("compact", messages))
        return "compact-output"

    monkeypatch.setattr(
        A2UIModelClient,
        "_generate_from_real_model",
        generate_a2ui,
    )
    monkeypatch.setattr(
        A2UIModelClient,
        "_generate_compact_from_real_model",
        generate_compact,
    )
    messages = [{"role": "user", "content": "weather card"}]
    a2ui_profile = A2UIProtocolRegistry("a2ui-form-rom6.0-v1").get_profile()
    compact_profile = A2UIProtocolRegistry("compact-dsl-v1").get_profile()
    client = A2UIModelClient(use_mock=False)

    assert client.generate(messages, a2ui_profile) == "a2ui-output"
    assert client.generate(messages, compact_profile) == "compact-output"
    assert calls == [
        ("a2ui", messages),
        ("compact", messages),
    ]


def test_compact_model_client_returns_streamed_ndjson(monkeypatch):
    """Compact model output is returned directly without A2UI conversion."""
    dsl = '["root","Column",{"width":"matchParent"},[]]'

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _traceback):
            return False

        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def iter_lines(decode_unicode=True):
            assert decode_unicode is True
            content_chunk = {"choices": [{"delta": {"content": dsl}}]}
            yield f"data: {json_module.dumps(content_chunk)}"
            yield 'data: {"choices":[],"usage":{"total_tokens":120}}'
            yield "data: [DONE]"

    client = A2UIModelClient(use_mock=False)
    monkeypatch.setattr(client, "calc_sign", lambda _payload: "signature")
    monkeypatch.setattr(
        client,
        "convert_dsl",
        lambda *_args: pytest.fail("Compact output must not use A2UI conversion"),
    )
    monkeypatch.setattr(
        "custom.a2ui_model_client.requests.post",
        lambda *_args, **_kwargs: FakeResponse(),
    )

    result = client._generate_compact_from_real_model(
        [{"role": "user", "content": "weather"}],
    )

    assert result == dsl


def test_compact_model_client_has_no_artificial_completion_limit():
    source = (
        CLOUD_ROOT / "custom" / "a2ui_model_client.py"
    ).read_text(encoding="utf-8")

    assert "COMPACT_DSL_MAX_TOKENS" not in source
    assert "max_duration" not in source
    assert "stop_when_compact_complete" not in source


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


def test_retry_controller_retries_when_enabled():
    """验证 RetryController 返回结构化重试结果。

    入参：无。
    出参：无；通过断言验证首次失败后最多重试一次。
    """
    results = iter(["first", "second"])

    retry_result = RetryController().run(
        operation=lambda: next(results),
        validate=lambda value: ["bad"] if value == "first" else [],
        retry_on_validation_failure=True,
    )

    assert retry_result.result == "second"
    assert retry_result.retryCount == 1
    assert retry_result.errors == []


def test_retry_controller_does_not_retry_validation_failure_by_default():
    operation_calls = 0

    def operation() -> str:
        nonlocal operation_calls
        operation_calls += 1
        return "first"

    retry_result = RetryController().run(
        operation=operation,
        validate=lambda _value: ["bad"],
    )

    assert operation_calls == 1
    assert retry_result.result == "first"
    assert retry_result.retryCount == 0
    assert retry_result.errors == ["bad"]


def test_artifact_store_returns_structured_save_result(tmp_path, monkeypatch):
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
    result = ArtifactStore().save(artifact)

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


def test_artifact_validator_accepts_compact_dsl_ndjson():
    """验证极简协议允许字符串属性通过 path 数据行取值。"""
    profile = A2UIProtocolRegistry("compact-dsl-v1").get_profile()
    artifact = WidgetArtifact(
        genui=(CLOUD_ROOT / "custom" / "mock.compact-dsl.dat").read_text(
            encoding="utf-8"
        ),
        cardSpec={"suggestSize": "2x2"},
        taskSpec={"dataModelSchema": {"data": {}}},
        meta=ArtifactMeta(
            protocolProfileId="compact-dsl-v1",
            capabilityRegistryVersion=REGISTRY_VERSION_6,
            createdAt=1,
        ),
    )

    errors = ArtifactValidator().validate(artifact, profile)

    assert errors == []


@pytest.mark.parametrize(
    ("data_line", "expected_error"),
    [
        (None, "has no data line"),
        ('["/title",true]', "must initialize a string value"),
    ],
)
def test_artifact_validator_rejects_invalid_binding_data(data_line, expected_error):
    """验证 Text.content 绑定有数据行，且预览值类型可被文本展示。"""
    profile = A2UIProtocolRegistry("compact-dsl-v1").get_profile()
    lines = [
        '["root","Stack",{"width":"matchParent","height":140,"padding":12,'
        '"borderRadius":18,"clip":true,"backgroundColor":"#FFFFFFFF"},["title"]]',
        '["title","Text",{"width":100,"height":20,'
        '"content":{"path":"/title"},"fontSize":14}]',
    ]
    if data_line:
        lines.append(data_line)
    artifact = WidgetArtifact(
        genui="\n".join(lines),
        cardSpec={"suggestSize": "2x2"},
        taskSpec={"dataModelSchema": {"data": {}}},
        meta=ArtifactMeta(
            protocolProfileId="compact-dsl-v1",
            capabilityRegistryVersion=REGISTRY_VERSION_6,
            createdAt=1,
        ),
    )

    errors = ArtifactValidator().validate(artifact, profile)

    assert any(expected_error in item for item in errors)
