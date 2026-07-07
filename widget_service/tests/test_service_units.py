# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
# ruff: noqa: E402, I001
import base64
import hashlib
import hmac
import json as json_module
import sys
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLOUD_ROOT = PROJECT_ROOT / "cloud"

if str(CLOUD_ROOT) not in sys.path:
    sys.path.insert(0, str(CLOUD_ROOT))

from core.errors import ErrorCode, GenerationStatus
from core.logger import DesensitizedErrorTool
from models.artifact import ArtifactMeta, WidgetArtifact
from models.capability import AssetCapability, DataCapability, RemovedCapability
from models.generation import CandidateDataBinding, DeviceContext, EventAction
from services.artifact_store import ArtifactStore
from services.card_spec_builder import CardSpecBuilder
from services.capability_registry import CapabilityRegistry
from services.ids_client import IDSClient
from services.prompt_builder import PromptBuilder
from services.response_planner import ResponsePlanner
from services.retry_controller import RetryController
from services.task_spec_builder import TaskSpecBuilder
from services.validator import ArtifactValidator


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
    monkeypatch.setattr(client.settings, "ids_secret_key", base64.b64encode(b"secret").decode())
    request = client.build_installed_apps_query(_device(), "ids-unit-1")
    expected_digest = hmac.new(
        b"secret",
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


def test_desensitized_error_tool_masks_common_sensitive_fields():
    """验证脱敏 error 工具类能处理常见敏感字段。

    入参：无。
    出参：无；通过断言验证 sign、accessKey、token 等敏感值被替换。
    """
    message = "idsSign=abc accessKey=foo token=bar custom=secret-value"

    sanitized = DesensitizedErrorTool.sanitize(message, ["secret-value"])

    assert "abc" not in sanitized
    assert "foo" not in sanitized
    assert "bar" not in sanitized
    assert "secret-value" not in sanitized
    assert "custom=***" in sanitized


def test_capability_registry_version_is_derived_from_device_versions():
    """验证能力版本目录由 ohosApiVersion 和 romVersion 推导。

    入参：无。
    出参：无；通过断言验证版本文件夹名符合约定。
    """
    version = CapabilityRegistry.from_app_rom_versions("36", "ALN-AL00 7.0.0.36")

    assert version == "ohos-36_rom-7.0.0"


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
    card_spec = CardSpecBuilder().build("2x4", [binding])

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
    assert task_spec.assetCandidates[0]["id"] == "asset.drop_1"


def test_prompt_builder_returns_entity_payload():
    """验证 PromptBuilder 返回结构化 prompt 实体。

    入参：无。
    出参：无；通过断言验证模型输入不再是裸 dict 拼装。
    """
    task_spec = TaskSpecBuilder().build(
        user_query="天气卡片",
        size="2x4",
        effective_bindings=[],
        effective_data_capabilities=[],
        event_candidates=[],
        asset_candidates=[],
    )
    payload = PromptBuilder().build(
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

    assert payload.user.protocolProfile.version == "v0.9"
    assert payload.user.degradationContext == "无降级"


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


def test_artifact_store_returns_structured_save_result():
    """验证 ArtifactStore 返回结构化保存结果。

    入参：无。
    出参：无；通过断言验证 artifactUrl 和 artifactDigest 字段可直接使用。
    """
    artifact = WidgetArtifact(
        genui="{}\n{}\n{}",
        cardSpec={"suggestSize": "2x4"},
        taskSpec={"dataModel": {"value": {}}},
        meta=ArtifactMeta(
            protocolProfileId="a2ui-form-rom7-v1",
            capabilityRegistryVersion="ohos-36_rom-7.0.0",
            createdAt=1,
        ),
    )
    result = ArtifactStore().save(artifact)

    assert result.artifactUrl.endswith(".json")
    assert result.artifactDigest.startswith("sha256:")


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
            capabilityRegistryVersion="ohos-36_rom-7.0.0",
            createdAt=1,
        ),
    )
    errors = ArtifactValidator().validate(
        artifact,
        {"id": "a2ui-form-rom7-v1"},
    )

    assert any("unsupported component" in item for item in errors)
