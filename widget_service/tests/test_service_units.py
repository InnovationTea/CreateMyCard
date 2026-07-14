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

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLOUD_ROOT = PROJECT_ROOT / "cloud"

if str(CLOUD_ROOT) not in sys.path:
    sys.path.insert(0, str(CLOUD_ROOT))

from core.errors import ErrorCode, GenerationStatus
from models.artifact import ArtifactMeta, WidgetArtifact
from models.capability import AssetCapability, DataCapability, RemovedCapability
from models.generation import CandidateDataBinding, DeviceContext, EventAction
from services.artifact_store import ArtifactStore
from custom.a2ui_model_client import A2UIModelClient
from services.card_spec_builder import CardSpecBuilder
from services.capability_registry import CapabilityRegistry
from services.ids_client import IDSClient
from services.prompt_builder import PromptBuilder
from services.protocol_registry import A2UIProtocolRegistry
from services.response_planner import ResponsePlanner
from services.retry_controller import RetryController
from services.task_spec_builder import TaskSpecBuilder
from services.validator import ArtifactValidator
from utils.base_utils import sts_config
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

    assert "from app.logger import logger, task_logger" in routes_source
    assert set_context_position < request_log_position


def _device() -> DeviceContext:
    """构造测试设备上下文。

    入参：无。
    出参：DeviceContext 测试对象。
    """
    return DeviceContext(
        deviceId="device-001",
        odid="odid-001",
        romVersion="ALN-AL00 7.0.0.36",
        ohosApiVersion=36,
    )


def test_ids_query_builds_structured_request_and_signature(monkeypatch):
    """验证 IDS 查询请求使用实体封装，并生成真实签名。

    入参：无。
    出参：无；通过断言验证 request body、header 和签名符合预期。
    """
    client = IDSClient()
    monkeypatch.setattr(client.settings, "ids_access_key", "access")
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
    assert request.headers.idsSign != "{{idsSign}}"
    assert request.headers.idsSign.startswith("access;")
    assert len(request.headers.idsSign.split(";")) == 3
    assert client.build_ids_sign(timestamp_ms=1000) == f"access;1000;{expected_sign}"
    assert request.headers.model_dump(by_alias=True)["Content-Type"] == "application/json"


def test_ids_query_uses_default_odid_when_device_odid_missing():
    """验证设备缺少 odid 时 IDS 查询使用固定默认 odid。

    入参：无。
    出参：无；通过断言验证 request body 中的 odid 兜底值。
    """
    client = IDSClient()
    device = DeviceContext(
        deviceId="device-should-not-be-used",
        romVersion="ALN-AL00 7.0.0.36",
        ohosApiVersion=36,
    )

    request = client.build_installed_apps_query(device, "ids-default-odid-1")

    assert (
        request.body.nameSpaces[0].queryRequestData[0].keys.odid
        == "790d8366-cd45-c4d5-6784-06727a549e61"
    )


def test_ids_client_queries_remote_when_mock_file_missing(tmp_path, monkeypatch):
    """验证 mock 文件不存在时 IDSClient 会真实发起 HTTP 查询。

    入参：
    - tmp_path：pytest 临时目录。
    - monkeypatch：pytest monkeypatch 工具。
    出参：无；通过断言验证远程响应会被解析成设备能力状态。
    """
    captured_request: dict = {}
    ids_payload = {
        "nameSpaces": [
            {
                "dataType": "t_ids_kv_ohos_installed_apps",
                "values": [
                    {
                        "data": {
                            "bundleName": "com.huawei.hmos.weather",
                            "versionName": "7.0.0",
                        }
                    }
                ],
            },
            {
                "dataType": "provider_state",
                "values": [{"data": {"providerId": "UG.weather.current"}}],
            },
        ]
    }

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
        response._content = json_module.dumps(ids_payload).encode("utf-8")
        return response

    client = IDSClient(mock_response_path=tmp_path / "missing_ids_response.json")
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
    assert state.installed_apps["com.huawei.hmos.weather"] == "7.0.0"
    assert "UG.weather.current" in state.providers


def test_capability_registry_version_is_derived_from_prd_and_rom_versions():
    """验证能力版本目录由 prdVer 和 romVersion 推导。

    入参：无。
    出参：无；通过随机版本参数断言版本文件夹名符合约定。
    """
    random_patch = uuid.uuid4().int % 100000
    prd_ver = f"88.7.{random_patch}"
    rom_ver = f"36.{random_patch}"

    version = CapabilityRegistry.from_app_rom_versions(prd_ver, rom_ver)

    assert version == f"app-{prd_ver}_rom-{rom_ver}"


def test_card_spec_builder_keeps_only_data_bindings():
    """验证 CardSpecBuilder 只生成数据绑定契约。

    入参：无。
    出参：无；通过断言验证事件不会进入 CardSpec。
    """
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        arguments={"districtName": "上海"},
        writeResultTo="/data/weather",
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
    assert card_spec.dataBindings == [binding]


def test_task_spec_builder_writes_update_model_to_data_model_path():
    """验证 updateModel 会按 writeResultTo 写入 DataModel。

    入参：无。
    出参：无；通过断言验证输出层级保留主 Agent 选择的字段结构。
    """
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        arguments={"districtName": "上海"},
        writeResultTo="/data/weather",
        updateModel={"current": {"temperatureText": ""}},
    )
    capability = DataCapability(
        id="ViewWeather",
        description="天气",
        inputSchema={},
        outputSchema={},
    )
    task_spec = TaskSpecBuilder().build(
        user_query="天气卡片",
        size="2x4",
        title="天气速览",
        description="查看当前天气",
        effective_bindings=[binding],
        effective_data_capabilities=[capability],
        event_candidates=[EventAction(id="event.open.weather", call="clickToDeeplink", args={})],
        asset_candidates=[
            AssetCapability(
                id="asset.drop_1",
                src="resources/base/media/drop_1.svg",
                description="雨滴",
            )
        ],
    )

    assert task_spec.dataModel["value"]["data"]["weather"] == {
        "current": {"temperatureText": ""}
    }
    assert task_spec.title == "天气速览"
    assert task_spec.description == "查看当前天气"
    assert task_spec.assetCandidates[0]["id"] == "asset.drop_1"


def test_prompt_builder_returns_model_messages():
    """验证 PromptBuilder 返回小模型消息列表。

    入参：无。
    出参：无；通过断言验证 system 和 user 消息内容。
    """
    task_spec = TaskSpecBuilder().build(
        user_query="天气卡片",
        size="2x4",
        title="天气速览",
        description="查看当前天气",
        effective_bindings=[],
        effective_data_capabilities=[],
        event_candidates=[],
        asset_candidates=[],
    )
    messages = PromptBuilder().build(
        task_spec,
        {
            "id": "a2ui-form-rom7-v1",
            "version": "v0.9",
            "catalogId": "ohos.a2ui.extended.catalog",
            "sizes": {"2x4": {"width": 300, "height": 140}},
            "componentWhitelist": ["Text", "Column"],
        },
        "无降级",
    )

    assert messages[0]["role"] == "system"
    assert '"userQuery":"天气卡片"' in messages[0]["content"]
    assert messages[1] == {"role": "user", "content": "天气卡片"}


def test_compact_dsl_profile_builds_isolated_prompt():
    """验证极简协议 profile 和 Prompt 不依赖旧 A2UI 消息结构。"""
    profile = A2UIProtocolRegistry("compact-dsl-v1").get_profile()
    task_spec = TaskSpecBuilder().build(
        user_query="天气卡片",
        size="2x4",
        title="天气速览",
        description="查看当前天气",
        effective_bindings=[],
        effective_data_capabilities=[],
        event_candidates=[],
        asset_candidates=[],
    )

    messages = PromptBuilder().build(task_spec, profile)
    system_prompt = messages[0]["content"]

    assert profile["format"] == "compact-dsl"
    assert A2UIProtocolRegistry("a2ui-form-rom7-v1").get_profile()["format"] == "a2ui-form"
    assert len(profile["componentWhitelist"]) == 16
    assert set(profile["componentWhitelist"]) == {
        "Row",
        "Column",
        "List",
        "Stack",
        "Grid",
        "Text",
        "Image",
        "Divider",
        "Progress",
        "Button",
        "TextInput",
        "Radio",
        "Toggle",
        "Checkbox",
        "Select",
        "Web",
    }
    assert "raw NDJSON only" in system_prompt
    assert "Do not output Markdown fences" in system_prompt
    assert "Use Grid only for an explicit grid" in system_prompt
    assert '"protocolProfile":{"id":"compact-dsl-v1"' in system_prompt


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
            "catalogId": "ohos.a2ui.extended.catalog",
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


def test_retry_controller_returns_retry_result():
    """验证 RetryController 返回结构化重试结果。

    入参：无。
    出参：无；通过断言验证首次失败后最多重试一次。
    """
    results = iter(["first", "second"])

    retry_result = RetryController().run(
        operation=lambda: next(results),
        validate=lambda value: ["bad"] if value == "first" else [],
    )

    assert retry_result.result == "second"
    assert retry_result.retryCount == 1
    assert retry_result.errors == []


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
        taskSpec={"dataModel": {"value": {}}},
        meta=ArtifactMeta(
            protocolProfileId="a2ui-form-rom7-v1",
            capabilityRegistryVersion="app-11.7.5.205_rom-36",
            createdAt=1,
        ),
    )
    result = ArtifactStore().save(artifact)

    assert result.artifactUrl.endswith(".md")
    assert result.artifactDigest.startswith("sha256:")
    uploaded_file = mock_storage_dir / result.artifactUrl.rsplit("/", 1)[-1]
    uploaded_content = uploaded_file.read_text(encoding="utf-8")
    assert '"title": "天气速览"' in uploaded_content
    assert '"description": "查看当前天气"' in uploaded_content


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
    """验证 mock OBS 上传会保留文件副本并返回访问地址。

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


def test_artifact_validator_reuses_datamodel_first_validator():
    """验证服务侧 Validator 复用 datamodel-first 校验脚本。

    入参：无。
    出参：无；通过断言验证旧版 `type/text` 组件结构会被新校验脚本拦截。
    """
    genui = "\n".join(
        [
            (
                '{"version":"v0.9","createSurface":'
                '{"surfaceId":"card","catalogId":"ohos.a2ui.extended.catalog",'
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
        taskSpec={"dataModel": {"value": {}}},
        meta=ArtifactMeta(
            protocolProfileId="a2ui-form-rom7-v1",
            capabilityRegistryVersion="app-11.7.5.205_rom-36",
            createdAt=1,
        ),
    )
    errors = ArtifactValidator().validate(
        artifact,
        {"id": "a2ui-form-rom7-v1"},
    )

    assert any("unsupported component" in item for item in errors)


def test_artifact_validator_accepts_compact_dsl_ndjson():
    """验证极简协议允许字符串属性通过 path 数据行取值。"""
    profile = A2UIProtocolRegistry("compact-dsl-v1").get_profile()
    artifact = WidgetArtifact(
        genui=(CLOUD_ROOT / "custom" / "mock.compact-dsl.dat").read_text(
            encoding="utf-8"
        ),
        cardSpec={"suggestSize": "2x4"},
        taskSpec={"dataModel": {"value": {}}},
        meta=ArtifactMeta(
            protocolProfileId="compact-dsl-v1",
            capabilityRegistryVersion="app-11.7.5.205_rom-36",
            createdAt=1,
        ),
    )

    errors = ArtifactValidator().validate(artifact, profile)

    assert errors == []


@pytest.mark.parametrize(
    ("data_line", "expected_error"),
    [
        (None, "has no data line"),
        ('["/title",42]', "must initialize a string value"),
    ],
)
def test_artifact_validator_rejects_invalid_binding_data(data_line, expected_error):
    """验证 Text.content 绑定必须存在数据行并初始化为 string。"""
    profile = A2UIProtocolRegistry("compact-dsl-v1").get_profile()
    lines = [
        '["root","Column",{"width":"matchParent","space":8},["title"]]',
        '["title","Text",{"content":{"path":"/title"}}]',
    ]
    if data_line:
        lines.append(data_line)
    artifact = WidgetArtifact(
        genui="\n".join(lines),
        cardSpec={"suggestSize": "2x4"},
        taskSpec={"dataModel": {"value": {}}},
        meta=ArtifactMeta(
            protocolProfileId="compact-dsl-v1",
            capabilityRegistryVersion="app-11.7.5.205_rom-36",
            createdAt=1,
        ),
    )

    errors = ArtifactValidator().validate(artifact, profile)

    assert any(expected_error in item for item in errors)
