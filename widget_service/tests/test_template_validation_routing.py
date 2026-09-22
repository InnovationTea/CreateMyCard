"""模板专项校验边界、可信来源、修复与编辑回归。"""

import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest

from api.schemas import GenerateWidgetCardRequest
from config.config import get_settings
from core.errors import GenerationStatus
from custom.a2ui_model_client import A2UIModelClient
from services import generation_pipeline
from services.card_validation import CompactDslValidationError
from services.compact_dsl_a2ui_converter import CompactDslConversionError
from services.generation_pipeline import (
    DslProcessingContext,
    DslProcessorKind,
    GenerationOrigin,
    GenerationRoutePolicy,
    get_dsl_processor,
)
from services.source_artifact_repository import SourceArtifactRepository
from services.validator import ArtifactValidator
from services.widget_generation_service import WidgetGenerationService
from utils.upload_file_obs import UploadFileOSMS

APP_VERSION = "11.7.5.205"
COMPACT = "\n".join(
    [
        '["root","Column",{"width":"matchParent","height":"matchParent"},["body"]]',
        '["body","Text",{"content":"测试卡片","fontSize":14}]',
    ]
)


def context(origin: GenerationOrigin) -> DslProcessingContext:
    return DslProcessingContext(
        size="2x2",
        card_spec={"suggestSize": "2x2", "dataBindings": []},
        task_spec={"appVersion": APP_VERSION, "dataModelSchema": {}, "eventCandidates": []},
        protocol_profile={},
        source_origin=origin,
    )


def reject_compact(*_args, **_kwargs):
    raise CompactDslValidationError(["test compact rule rejected output"])


@pytest.mark.parametrize("origin", list(GenerationOrigin))
def test_only_template_skips_compact_rules(monkeypatch, origin):
    monkeypatch.setattr(generation_pipeline, "validate_compact_dsl", reject_compact)
    processor = get_dsl_processor(DslProcessorKind.DESIGN_COMPACT)
    result = processor.process(COMPACT, context(origin))
    assert bool(result.errors) is (origin != GenerationOrigin.TEMPLATE)
    if origin == GenerationOrigin.TEMPLATE:
        assert "updateComponents" in result.standard_dsl


def test_shared_processor_does_not_share_validation_strategy(monkeypatch):
    monkeypatch.setattr(generation_pipeline, "validate_compact_dsl", reject_compact)
    processor = get_dsl_processor(DslProcessorKind.DESIGN_COMPACT)
    origins = [GenerationOrigin.TEMPLATE, GenerationOrigin.MODEL] * 8

    def process(origin):
        return bool(processor.process(COMPACT, context(origin)).errors)

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(process, origins))
    assert results == [False, True] * 8


def test_template_still_rejects_unparseable_source():
    processor = get_dsl_processor(DslProcessorKind.DESIGN_COMPACT)
    result = processor.process("not-json", context(GenerationOrigin.TEMPLATE))
    assert result.errors
    assert not result.standard_dsl


def test_template_conversion_failure_is_reported(monkeypatch):
    def fail_conversion(*_args, **_kwargs):
        raise CompactDslConversionError("conversion failed")

    monkeypatch.setattr(generation_pipeline, "convert_compact_dsl_to_a2ui", fail_conversion)
    processor = get_dsl_processor(DslProcessorKind.DESIGN_COMPACT)
    result = processor.process(COMPACT, context(GenerationOrigin.TEMPLATE))
    assert len(result.errors) == 1
    assert result.errors[0].code == "DESIGN_CONVERSION_FAILED"
    assert not result.standard_dsl


def test_template_root_marker_does_not_grant_provenance(monkeypatch):
    monkeypatch.setattr(generation_pipeline, "validate_compact_dsl", reject_compact)
    source = COMPACT.replace('"body"', '"template_root"')
    processor = get_dsl_processor(DslProcessorKind.DESIGN_COMPACT)
    assert processor.process(source, context(GenerationOrigin.UNKNOWN)).errors


@pytest.fixture
def storage(tmp_path, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(settings, "enable_artifact_download_mock", True)
    monkeypatch.setattr(settings, "enable_artifact_validation", True)
    monkeypatch.setattr(settings, "enable_validation_failure_retry", False)
    monkeypatch.setattr(settings, "enable_widget_edit", True)
    monkeypatch.setattr(
        "services.artifact_store.file_obs",
        UploadFileOSMS(base_url="https://obs.test/widget", mock_storage_dir=tmp_path / "mock_obs"),
    )
    return tmp_path


def policy() -> GenerationRoutePolicy:
    return GenerationRoutePolicy(
        operation="generateWidgetCardCompactDsl",
        protocol_profile_id="a2ui-form-rom6.0-v1",
        backend="openai",
        processor_kind=DslProcessorKind.DESIGN_COMPACT,
        source_format="design-compact-dsl",
        model_profile_id="design-compact-dsl",
        model_format="compact-dsl",
        validation_failure_blocking=True,
        stores_design_token=True,
    )


def request(**updates) -> GenerateWidgetCardRequest:
    values = {
        "uid": "test-user",
        "prdVer": APP_VERSION,
        "device": {"romVersion": "6.0"},
        "userQuery": "制作静态卡片",
        "title": "测试",
        "description": "测试卡片",
        "candidateDataBindings": [],
        "candidateEventCandidates": [],
        "candidateAssetIds": [],
    }
    values.update(updates)
    return GenerateWidgetCardRequest(**values)


async def template_source(*_args):
    return COMPACT


@pytest.mark.asyncio
async def test_template_uses_artifact_validation_without_source_storage(storage, monkeypatch):
    monkeypatch.setattr(generation_pipeline, "validate_compact_dsl", reject_compact)
    original_validate = ArtifactValidator.validate
    calls = []

    def validate(self, value, profile):
        calls.append(value)
        return original_validate(self, value, profile)

    monkeypatch.setattr(ArtifactValidator, "validate", validate)
    result = await WidgetGenerationService().generate_widget_card(
        request(),
        policy=policy(),
        template_source_generator=template_source,
    )
    assert result.status == GenerationStatus.SUCCESS
    assert len(calls) == 1
    loaded = await asyncio.to_thread(SourceArtifactRepository().load, result.artifactUrl)
    assert not hasattr(loaded, "source_origin")
    assert not (storage / "generation_provenance").exists()
    assert loaded.design_token is not None


@pytest.mark.asyncio
async def test_template_artifact_error_is_not_swallowed(storage, monkeypatch):
    monkeypatch.setattr(generation_pipeline, "validate_compact_dsl", reject_compact)
    monkeypatch.setattr(ArtifactValidator, "validate", lambda *_args: ["artifact rejected"])
    result = await WidgetGenerationService().generate_widget_card(
        request(),
        policy=policy(),
        template_source_generator=template_source,
    )
    assert result.status == GenerationStatus.FAILED
    assert not result.artifactUrl
    assert not (storage / "generation_provenance").exists()


@pytest.mark.asyncio
async def test_template_fallback_restores_compact_validation(storage, monkeypatch):
    async def rejected_template(*_args):
        raise ValueError("template not applicable")

    monkeypatch.setattr(A2UIModelClient, "generate", lambda *_args: COMPACT)
    monkeypatch.setattr(generation_pipeline, "validate_compact_dsl", reject_compact)
    result = await WidgetGenerationService().generate_widget_card(
        request(),
        policy=policy(),
        template_source_generator=rejected_template,
    )
    assert result.status == GenerationStatus.FAILED
    assert not result.artifactUrl


@pytest.mark.asyncio
@pytest.mark.parametrize("repair_valid", [True, False])
async def test_outer_repair_restores_compact_rules(
    storage,
    monkeypatch,
    repair_valid,
):
    monkeypatch.setattr(get_settings(), "enable_validation_failure_retry", True)
    monkeypatch.setattr(get_settings(), "validation_failure_max_repair_attempts", 1)
    artifact_calls = []
    compact_calls = []
    original_compact = generation_pipeline.validate_compact_dsl

    def validate_compact(*args, **kwargs):
        compact_calls.append(args)
        if not repair_valid:
            reject_compact()
        return original_compact(*args, **kwargs)

    def validate_artifact(*_args):
        artifact_calls.append(True)
        return ["repair required"] if len(artifact_calls) == 1 else []

    monkeypatch.setattr(generation_pipeline, "validate_compact_dsl", validate_compact)
    monkeypatch.setattr(ArtifactValidator, "validate", validate_artifact)
    monkeypatch.setattr(A2UIModelClient, "generate_repair", lambda *_args: COMPACT)
    result = await WidgetGenerationService().generate_widget_card(
        request(),
        policy=policy(),
        template_source_generator=template_source,
    )
    assert len(compact_calls) == 1
    if not repair_valid:
        assert result.status == GenerationStatus.FAILED
        assert len(artifact_calls) == 1
        assert not result.artifactUrl
        return
    assert result.status == GenerationStatus.SUCCESS
    assert len(artifact_calls) == 2
    loaded = await asyncio.to_thread(SourceArtifactRepository().load, result.artifactUrl)
    assert loaded.design_token is not None
    assert not hasattr(loaded, "source_origin")


@pytest.mark.asyncio
@pytest.mark.parametrize("history_valid", [True, False])
async def test_template_history_and_edit_output_use_full_rules(storage, monkeypatch, history_valid):
    original_compact = generation_pipeline.validate_compact_dsl
    monkeypatch.setattr(generation_pipeline, "validate_compact_dsl", reject_compact)
    service = WidgetGenerationService()
    created = await service.generate_widget_card(
        request(),
        policy=policy(),
        template_source_generator=template_source,
    )
    assert created.status == GenerationStatus.SUCCESS
    compact_calls = []
    model_calls = []

    def validate_compact(*args, **kwargs):
        compact_calls.append(args)
        if not history_valid:
            reject_compact()
        return original_compact(*args, **kwargs)

    def generate(*_args):
        model_calls.append(True)
        return COMPACT

    monkeypatch.setattr(generation_pipeline, "validate_compact_dsl", validate_compact)
    monkeypatch.setattr(A2UIModelClient, "generate", generate)
    edited = await service.generate_widget_card(
        request(sourceArtifactUrl=created.artifactUrl),
        policy=policy(),
    )
    if history_valid:
        assert len(compact_calls) == 2
        assert len(model_calls) == 1
        assert edited.status == GenerationStatus.SUCCESS
    else:
        assert len(compact_calls) == 1
        assert not model_calls
        assert edited.status == GenerationStatus.FAILED
        assert not edited.artifactUrl
    assert not (storage / "generation_provenance").exists()
