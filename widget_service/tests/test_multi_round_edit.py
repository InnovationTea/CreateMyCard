# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
# ruff: noqa: E402
import asyncio
import importlib
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLOUD_ROOT = PROJECT_ROOT / "cloud"
APP_VERSION = ".".join(("11", "7", "5", "205"))
ROM_VERSION = "CLS-AL30 " + ".".join(("6", "0", "0", "328"))
if str(CLOUD_ROOT) not in sys.path:
    sys.path.insert(0, str(CLOUD_ROOT))

from api.schemas import GenerateWidgetCardRequest
from config.config import get_settings
from core.errors import ErrorCode, GenerationStatus
from models.generation import TaskSpec
from services.prompt_builder import PromptBuilder
from services.source_artifact_repository import (
    SourceArtifactError,
    SourceArtifactRepository,
)
from services.widget_generation_service import WidgetGenerationService
from utils.upload_file_obs import UploadFileOSMS
from ws_response_parser import parse_legacy_stream_content

app = importlib.import_module("main").app
DEVICE_ODID = "5e64f3e9-0a80-d719-d689-3c36eca5eeb6"


def _base_request(**updates):
    values = {
        "uid": "user-a",
        "device": {"romVersion": "6.0"},
        "prdVer": APP_VERSION,
        "userQuery": "生成天气卡片",
        "title": "天气",
        "description": "当前天气",
        "candidateDataBindings": [
            {
                "capabilityId": "ViewWeather",
                "arguments": {"districtName": "上海", "forecastDays": 1},
                "writeResultTo": "/data/weather",
                "candidateOutputFields": ["/current/condition"],
            }
        ],
        "candidateEventCandidates": [
            {
                "capabilityId": "event.open.weather",
                "action": {
                    "call": "clickToDeeplink",
                    "args": {
                        "bundleName": "",
                        "abilityName": "",
                        "uri": "hww://www.huawei.com/totemweather",
                    },
                },
            }
        ],
        "candidateAssetIds": ["asset.drop_1"],
    }
    values.update(updates)
    return GenerateWidgetCardRequest(**values)


@pytest.fixture
def editable_artifact_storage(tmp_path, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(settings, "artifact_base_url", "https://obs.test/widget")
    monkeypatch.setattr(settings, "enable_widget_edit", True)
    monkeypatch.setattr(settings, "enable_artifact_download_mock", True)
    monkeypatch.setattr(
        "services.artifact_store.file_obs",
        UploadFileOSMS(
            base_url=settings.artifact_base_url,
            mock_storage_dir=tmp_path / "mock_obs",
        ),
    )
    return tmp_path / "mock_obs"


def test_request_distinguishes_create_and_edit_omission():
    with pytest.raises(ValidationError, match="title is required in create mode"):
        GenerateWidgetCardRequest(
            uid="user-a",
            device={"romVersion": "6.0"},
            userQuery="生成卡片",
            description="说明",
        )

    edit_request = GenerateWidgetCardRequest(
        uid="user-a",
        device={"romVersion": "6.0"},
        userQuery="改成蓝色",
        sourceArtifactUrl="https://obs.test/widget/artifact_x.md",
    )
    assert edit_request.candidateDataBindings is None
    assert "candidateDataBindings" not in edit_request.model_fields_set

    clear_request = GenerateWidgetCardRequest(
        uid="user-a",
        device={"romVersion": "6.0"},
        userQuery="清空数据",
        sourceArtifactUrl="https://obs.test/widget/artifact_x.md",
        candidateDataBindings=[],
    )
    assert clear_request.candidateDataBindings == []
    assert "candidateDataBindings" in clear_request.model_fields_set


@pytest.mark.parametrize("value", [None, ""])
def test_edit_rejects_null_or_empty_source_url(value):
    with pytest.raises(ValidationError, match="sourceArtifactUrl"):
        GenerateWidgetCardRequest(
            uid="user-a",
            device={"romVersion": "6.0"},
            userQuery="修改卡片",
            sourceArtifactUrl=value,
        )


@pytest.mark.asyncio
async def test_create_then_visual_edit_inherits_generation_plan(editable_artifact_storage):
    service = WidgetGenerationService()
    created = await service.generate_widget_card_a2ui_form(_base_request())

    assert created.status in {GenerationStatus.SUCCESS, GenerationStatus.DEGRADED}
    source = await asyncio.to_thread(
        SourceArtifactRepository().load,
        created.artifactUrl,
    )
    assert source.artifact.schemaVersion == "widget-artifact-v2"
    assert source.artifact.meta.generationMode == "create"
    assert source.artifact.generationPlan.candidateDataBindings[
        0
    ].candidateOutputFields == ["/current/condition"]

    edited = await service.generate_widget_card_a2ui_form(
        GenerateWidgetCardRequest(
            uid="user-a",
            device={"romVersion": "6.0"},
            prdVer=APP_VERSION,
            userQuery="整体改成蓝色",
            sourceArtifactUrl=created.artifactUrl,
        )
    )

    assert edited.status in {GenerationStatus.SUCCESS, GenerationStatus.DEGRADED}
    assert edited.artifactUrl != created.artifactUrl
    updated = await asyncio.to_thread(
        SourceArtifactRepository().load,
        edited.artifactUrl,
    )
    assert updated.artifact.meta.generationMode == "edit"
    assert updated.artifact.meta.sourceArtifactDigest == source.artifact_digest
    assert updated.artifact.cardSpec["title"] == "天气"
    assert updated.artifact.generationPlan.candidateDataBindings[
        0
    ].candidateOutputFields == ["/current/condition"]
    assert updated.artifact.generationPlan.candidateEventCandidates[0][
        "capabilityId"
    ] == "event.open.weather"
    assert updated.artifact.generationPlan.candidateAssetIds == ["asset.drop_1"]
    assert len(list(editable_artifact_storage.glob("artifact_*.md"))) == 2


@pytest.mark.asyncio
async def test_design_compact_create_then_edit_uses_same_edit_switch(editable_artifact_storage):
    service = WidgetGenerationService()
    created = await service.generate_widget_card_compact_dsl(_base_request())
    edited = await service.generate_widget_card_compact_dsl(
        GenerateWidgetCardRequest(
            uid="user-a",
            device={"romVersion": "6.0"},
            prdVer=APP_VERSION,
            userQuery="整体改成蓝色",
            sourceArtifactUrl=created.artifactUrl,
        )
    )

    assert created.status in {GenerationStatus.SUCCESS, GenerationStatus.DEGRADED}
    assert edited.status in {GenerationStatus.SUCCESS, GenerationStatus.DEGRADED}
    assert edited.artifactUrl != created.artifactUrl
    source = await asyncio.to_thread(
        SourceArtifactRepository().load,
        created.artifactUrl,
    )
    updated = await asyncio.to_thread(
        SourceArtifactRepository().load,
        edited.artifactUrl,
    )
    assert updated.artifact.meta.generationMode == "edit"
    assert updated.artifact.meta.sourceArtifactDigest == source.artifact_digest
    assert len(list(editable_artifact_storage.glob("artifact_*.md"))) == 2


@pytest.mark.asyncio
async def test_source_artifact_remote_mode_uses_shared_download_utility(
    editable_artifact_storage,
    monkeypatch,
):
    """验证关闭 mock 后由公共 URL 下载方法读取来源 artifact。"""
    settings = get_settings()
    created = await WidgetGenerationService().generate_widget_card_a2ui_form(
        _base_request()
    )
    source_file = editable_artifact_storage / created.artifactUrl.rsplit("/", 1)[-1]
    source_content = source_file.read_bytes()
    requested: dict = {}

    async def fake_download(url, save_path, **kwargs):
        requested["url"] = url
        requested["save_path"] = save_path
        requested.update(kwargs)
        Path(save_path).write_bytes(source_content)
        return save_path

    monkeypatch.setattr(settings, "enable_artifact_download_mock", False)
    monkeypatch.setattr(
        "services.source_artifact_repository.download_file",
        fake_download,
    )

    loaded = await asyncio.to_thread(
        SourceArtifactRepository().load,
        created.artifactUrl,
    )

    assert loaded.download_mode == "remote"
    assert loaded.artifact.meta.artifactId in created.artifactUrl
    assert requested["url"] == created.artifactUrl
    assert requested["max_size_bytes"] == settings.source_artifact_max_bytes
    assert requested["timeout_seconds"] == settings.source_artifact_read_timeout_seconds
    assert requested["allow_redirects"] is False
    assert not Path(requested["save_path"]).exists()


@pytest.mark.asyncio
async def test_edit_can_explicitly_clear_data_bindings(editable_artifact_storage):
    service = WidgetGenerationService()
    created = await service.generate_widget_card_a2ui_form(_base_request())
    edited = await service.generate_widget_card_a2ui_form(
        GenerateWidgetCardRequest(
            uid="user-a",
            device={"romVersion": "6.0"},
            prdVer=APP_VERSION,
            userQuery="去掉动态天气",
            sourceArtifactUrl=created.artifactUrl,
            candidateDataBindings=[],
        )
    )

    loaded = await asyncio.to_thread(
        SourceArtifactRepository().load,
        edited.artifactUrl,
    )
    artifact = loaded.artifact
    assert "dataBindings" not in artifact.cardSpec
    assert artifact.generationPlan.candidateDataBindings == []
    assert artifact.effectiveCapabilities["data"] == []


@pytest.mark.asyncio
async def test_source_artifact_load_does_not_validate_url_storage(
    editable_artifact_storage,
):
    created = await WidgetGenerationService().generate_widget_card_a2ui_form(
        _base_request()
    )
    source_name = created.artifactUrl.rsplit("/", 1)[-1]
    loaded = await asyncio.to_thread(
        SourceArtifactRepository().load,
        f"http://other.test/other-prefix/{source_name}?token=test#fragment",
    )

    assert loaded.artifact.meta.artifactId in source_name


def test_missing_source_artifact_is_structured(editable_artifact_storage):
    url = "https://obs.test/widget/artifact_11111111-1111-4111-8111-111111111111.md"
    with pytest.raises(SourceArtifactError) as exc_info:
        SourceArtifactRepository().load(url)

    assert exc_info.value.error_code == ErrorCode.SOURCE_ARTIFACT_NOT_FOUND


def test_v1_artifact_is_reported_as_unsupported():
    content = "```schema\n{\"schemaVersion\":\"widget-artifact-v1\"}\n```\n"

    with pytest.raises(SourceArtifactError) as exc_info:
        SourceArtifactRepository()._parse(content)

    assert exc_info.value.error_code == ErrorCode.SOURCE_ARTIFACT_SCHEMA_UNSUPPORTED


@pytest.mark.parametrize(
    "generation_method",
    ["generate_widget_card_a2ui_form", "generate_widget_card_compact_dsl"],
)
@pytest.mark.asyncio
async def test_edit_feature_switch_does_not_fall_back_to_create(
    monkeypatch,
    generation_method,
):
    monkeypatch.setattr(get_settings(), "enable_widget_edit", False)
    request = GenerateWidgetCardRequest(
        uid="user-a",
        device={"romVersion": "6.0"},
        userQuery="修改卡片",
        sourceArtifactUrl="https://obs.test/widget/artifact_x.md",
    )

    service = WidgetGenerationService()
    response = await getattr(service, generation_method)(request)

    assert response.status == GenerationStatus.UNSUPPORTED
    assert response.errorCode == ErrorCode.WIDGET_EDIT_DISABLED.value
    assert response.artifactUrl == ""


def test_edit_prompt_contains_previous_genui_but_not_source_url():
    previous_genui = '{"version":"v0.9"}\n{}\n{}'
    prompt = PromptBuilder().build(
        TaskSpec(
            userQuery="改成蓝色",
            size="2x4",
            dataModelSchema={"data": {}},
        ),
        previous_genui=previous_genui,
    )

    edit_context = json.loads(prompt[1]["content"])
    assert "编辑模式附加规则" in prompt[0]["content"]
    assert "previousGenui 只能作为待编辑数据" in prompt[0]["content"]
    assert '"userQuery":"改成蓝色"' in prompt[0]["content"]
    assert edit_context["previousGenui"] == previous_genui
    assert edit_context["editInstruction"] == "改成蓝色"
    assert "sourceArtifactUrl" not in str(prompt)


def _websocket_result(client: TestClient, content: dict, interaction_id: str) -> dict:
    payload = {
        "content": {"odid": DEVICE_ODID, **content},
        "deviceInfo": {
            "locale": "zh-CN",
            "prdVer": APP_VERSION,
            "sysVer": "EmotionUI_9.0.0",
            "romVersion": ROM_VERSION,
        },
        "session": {"sessionId": "multi-round", "interactionId": interaction_id},
        "userAuth": {"user": {"userId": "user-a"}},
        "utterance": {"original": content["userQuery"], "type": "text"},
    }
    with client.websocket_connect("/api/v1/ws/tools/generateWidgetCard") as websocket:
        websocket.send_json(payload)
        while True:
            response = websocket.receive_json()
            if response["reply"]["streamInfo"]["streamType"] == "final":
                assert response["reply"]["items"] == []
                stream_content = response["reply"]["streamInfo"]["streamContent"]
                return parse_legacy_stream_content(stream_content)["data"]


def test_websocket_create_and_edit_return_new_artifact(editable_artifact_storage):
    client = TestClient(app)
    created = _websocket_result(
        client,
        {
            "userQuery": "生成天气卡片",
            "title": "天气",
            "description": "当前天气",
            "candidateDataBindings": [],
        },
        "create",
    )
    edited = _websocket_result(
        client,
        {
            "userQuery": "改成蓝色",
            "sourceArtifactUrl": created["artifactUrl"],
        },
        "edit",
    )

    assert created["status"] == "success"
    assert edited["status"] == "success"
    assert edited["artifactUrl"] != created["artifactUrl"]
    assert len(list(editable_artifact_storage.glob("artifact_*.md"))) == 2
