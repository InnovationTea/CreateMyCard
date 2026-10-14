# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import asyncio

import pytest
from pydantic import ValidationError

from api.schemas import GenerateWidgetCardRequest, GenerateWidgetCardResponse
from config.config import Settings, get_settings
from core.errors import ErrorCode, GenerationStatus
from custom.a2ui_model_client import A2UIModelGenerationError
from models.artifact import ArtifactMeta, WidgetArtifact
from models.generation import ModelRequestContext
from services import artifact_store
from services.artifact_store import ArtifactStore, ArtifactUploadError
from services.compact_dsl_interface_retry import run_compact_dsl_with_retry


def make_request(**overrides) -> GenerateWidgetCardRequest:
    return GenerateWidgetCardRequest(
        uid="test-user",
        prdVer="11.7.7.332",
        device={"romVersion": "7.0"},
        userQuery="生成天气卡片",
        title="天气",
        description="天气速览",
        **overrides,
    )


def make_response(
    status: GenerationStatus = GenerationStatus.SUCCESS,
    error_code: str = "",
) -> GenerateWidgetCardResponse:
    artifact_url = ""
    if status in {GenerationStatus.SUCCESS, GenerationStatus.DEGRADED}:
        artifact_url = "https://test.invalid/widget/final.md"
    return GenerateWidgetCardResponse(
        status=status,
        errorCode=error_code,
        suggestSize="2x2",
        message="测试",
        artifactUrl=artifact_url,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("enabled", "retry_count", "expected_calls"),
    [(False, 0, 1), (False, 1, 1), (False, 2, 1), (True, 0, 1), (True, 1, 2), (True, 2, 3)],
)
async def test_retry_count_is_extra_attempts(enabled, retry_count, expected_calls):
    calls = []
    failure = make_response(GenerationStatus.FAILED, ErrorCode.VALIDATION_FAILED)

    async def generate(request):
        calls.append(request)
        return failure

    result = await run_compact_dsl_with_retry(
        generate, make_request(), enabled=enabled, retry_count=retry_count, request_id="count"
    )
    assert len(calls) == expected_calls
    assert result is failure


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "code",
    [
        ErrorCode.A2UI_GENERATION_FAILED,
        ErrorCode.VALIDATION_FAILED,
        ErrorCode.ARTIFACT_UPLOAD_FAILED,
        ErrorCode.TIMEOUT,
    ],
)
async def test_retryable_result_stops_on_success(code):
    calls = []
    success = make_response()

    async def generate(request):
        calls.append(request)
        if len(calls) == 1:
            return make_response(GenerationStatus.FAILED, code)
        return success

    result = await run_compact_dsl_with_retry(
        generate, make_request(), enabled=True, retry_count=3, request_id=None
    )
    assert result is success
    assert len(calls) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "code"),
    [
        (GenerationStatus.SUCCESS, ""),
        (GenerationStatus.DEGRADED, ErrorCode.VALIDATION_FAILED),
        (GenerationStatus.UNSUPPORTED, ErrorCode.APP_VERSION_UNSUPPORTED),
        (GenerationStatus.FAILED, ErrorCode.INVALID_ARGUMENTS),
        (GenerationStatus.FAILED, ErrorCode.SOURCE_ARTIFACT_INVALID),
        (GenerationStatus.FAILED, ErrorCode.SOURCE_ARTIFACT_DOWNLOAD_FAILED),
        (GenerationStatus.FAILED, "UNKNOWN_ERROR"),
    ],
)
async def test_non_retryable_results_preserved(status, code):
    calls = []
    response = make_response(status, code)

    async def generate(request):
        calls.append(request)
        return response

    result = await run_compact_dsl_with_retry(
        generate, make_request(), enabled=True, retry_count=2, request_id="stop"
    )
    assert result is response
    assert len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_type", [A2UIModelGenerationError, ArtifactUploadError, TimeoutError, ConnectionError]
)
@pytest.mark.parametrize("recovers", [True, False])
async def test_retryable_exceptions_recover_or_preserve_last_exception(error_type, recovers):
    calls = []
    failure = error_type("temporary failure")

    async def generate(request):
        calls.append(request)
        if recovers and len(calls) == 2:
            return make_response()
        raise failure

    task = run_compact_dsl_with_retry(
        generate, make_request(), enabled=True, retry_count=1, request_id="exception"
    )
    if recovers:
        result = await task
        assert result.status == GenerationStatus.SUCCESS
    else:
        with pytest.raises(error_type) as raised:
            await task
        assert raised.value is failure
    assert len(calls) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_type", [ValueError, RuntimeError, KeyError, FileNotFoundError, asyncio.CancelledError]
)
async def test_non_retryable_exceptions_and_cancellation_propagate(error_type):
    calls = []
    failure = error_type("permanent failure")

    async def generate(request):
        calls.append(request)
        raise failure

    with pytest.raises(error_type) as raised:
        await run_compact_dsl_with_retry(
            generate, make_request(), enabled=True, retry_count=2, request_id="no-retry"
        )
    assert raised.value is failure
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_each_attempt_preserves_original_request_fields_and_private_context():
    request = make_request(sourceArtifactUrl="https://test.invalid/widget/source.md")
    request._raw_request_body = '{"content":{"title":"天气"}}'
    request.device._source_rom_version = "VYG-AL00 7.0.0.105"
    request._model_request_context = ModelRequestContext(
        session_id="session",
        interaction_id="1",
        device_id="device",
        country_code="CN",
        app_version=request.prdVer,
        app_name="app",
    )
    calls = []

    async def generate(attempt_request):
        assert attempt_request is not request
        assert attempt_request.title == "天气"
        assert "size" not in attempt_request.model_fields_set
        assert attempt_request._raw_request_body == request._raw_request_body
        assert attempt_request._model_request_context == request._model_request_context
        assert attempt_request.device._source_rom_version == request.device._source_rom_version
        calls.append(attempt_request)
        attempt_request.title = "被修改"
        attempt_request.size = "2x4"
        attempt_request.device.romVersion = "6.0"
        attempt_request.device._source_rom_version = None
        if len(calls) == 1:
            return make_response(GenerationStatus.FAILED, ErrorCode.VALIDATION_FAILED)
        return make_response()

    await run_compact_dsl_with_retry(
        generate, request, enabled=True, retry_count=1, request_id="snapshot"
    )
    assert len(calls) == 2
    assert calls[0] is not calls[1]
    assert request.title == "天气"
    assert request.device.romVersion == "7.0"
    assert "size" not in request.model_fields_set


@pytest.mark.parametrize("value", [-1, 1.5, 1.0, True, "bad", "1.5", None])
def test_invalid_retry_count_config_is_rejected(value):
    with pytest.raises(ValidationError, match="compact_dsl_interface_retry_count"):
        Settings(compact_dsl_interface_retry_count=value)


@pytest.mark.parametrize("value", [0, 1, 2, "0", "1", "2"])
def test_valid_retry_count_config(value):
    settings = Settings(compact_dsl_interface_retry_count=value)
    assert settings.compact_dsl_interface_retry_count == int(value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("upload_error", "expected_type"),
    [
        (None, ArtifactUploadError),
        (TimeoutError("timeout"), ArtifactUploadError),
        (ConnectionError("connection lost"), ArtifactUploadError),
        (FileNotFoundError("missing"), FileNotFoundError),
        (PermissionError("denied"), PermissionError),
        (RuntimeError("unknown"), RuntimeError),
    ],
)
async def test_upload_errors_are_classified_only_at_upload_boundary(
    monkeypatch, tmp_path, upload_error, expected_type
):
    monkeypatch.setattr(get_settings(), "WORKSPACE_ROOT", tmp_path)

    async def upload(_path):
        if upload_error is not None:
            raise upload_error
        return ""

    monkeypatch.setattr(artifact_store.file_obs, "upload_file", upload)
    artifact = WidgetArtifact(
        genui="{}\n{}\n{}",
        cardSpec={"title": "天气", "description": "天气速览", "suggestSize": "2x2"},
        taskSpec={"dataModelSchema": {"data": {}}},
        meta=ArtifactMeta(
            protocolProfileId="a2ui-form-rom6.0-v1",
            capabilityRegistryVersion="app-11.7.5.205_rom-6.0",
            createdAt=1,
        ),
    )
    with pytest.raises(expected_type) as raised:
        await ArtifactStore().save(artifact)
    if upload_error is not None:
        if isinstance(raised.value, ArtifactUploadError):
            assert raised.value.__cause__ is upload_error
        else:
            assert raised.value is upload_error
