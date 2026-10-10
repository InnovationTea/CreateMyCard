# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import asyncio
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from api.schemas import GenerateWidgetCardRequest
from config.config import get_settings
from core.errors import GenerationStatus
from custom.a2ui_model_client import A2UIModelClient
from services import widget_generation_service
from services.artifact_store import ArtifactStore
from services.asset_url_mapper import AssetUrlMapper
from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.multi_step_generation.core.bridge import JsxA2UIBridge
from services.source_artifact_repository import SourceArtifactRepository
from services.template_generation import TemplateSourceGenerator
from services.validator import ArtifactValidator
from services.widget_generation_service import WidgetGenerationService
from test_asset_url_mapper import SRC, URL, components
from utils.upload_file_obs import UploadFileOSMS


def design_source():
    return "\n".join(
        json.dumps(row, ensure_ascii=False)
        for row in [
            ["root", "Column", {"width": 320, "height": 160, "padding": 12}, ["title", "image"]],
            ["title", "Text", {"content": "天气", "fontSize": 16}],
            ["image", "Image", {"src": SRC, "width": 20, "height": 20, "fillColor": "#FF1F4799"}],
            ["/ui/state", "ready"],
        ]
    )


def json_rows(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def request(**updates):
    values = {
        "uid": "test-user",
        "device": {"romVersion": "7.0"},
        "prdVer": "11.7.7.331",
        "userQuery": "生成天气卡片",
        "title": "天气",
        "description": "天气图标",
        "size": "2x4",
        "candidateAssetIds": ["asset.drop_1"],
    }
    values.update(updates)
    return GenerateWidgetCardRequest(**values)


@pytest.fixture
def storage(tmp_path, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(settings, "enable_widget_edit", True)
    monkeypatch.setattr(settings, "enable_artifact_download_mock", True)
    monkeypatch.setattr(settings, "enable_validation_failure_retry", False)
    monkeypatch.setattr(settings, "asset_src_url_mapping", {SRC: URL})
    monkeypatch.setattr(
        WidgetGenerationService, "_enable_card_template", staticmethod(lambda: False)
    )
    monkeypatch.setattr(
        WidgetGenerationService, "_enable_jsx_generation", staticmethod(lambda: False)
    )
    monkeypatch.setattr(
        "services.artifact_store.file_obs",
        UploadFileOSMS(base_url="https://artifact.test", mock_storage_dir=tmp_path / "mock_obs"),
    )
    return tmp_path / "mock_obs"


@pytest.mark.parametrize("kind", ["compact_dsl", "a2ui_form"])
@pytest.mark.parametrize("validation_enabled", [True, False])
@pytest.mark.parametrize("mapping_hit", [True, False])
@pytest.mark.asyncio
async def test_jsx_only_maps_resources_without_engine_quality_flow(
    storage, monkeypatch, kind, validation_enabled, mapping_hit
):
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_artifact_validation", validation_enabled)
    monkeypatch.setattr(settings, "enable_validation_failure_retry", True)
    if not mapping_hit:
        monkeypatch.setattr(settings, "asset_src_url_mapping", {})
    standard = convert_compact_dsl_to_a2ui(design_source(), size="2x4")
    jsx_calls = []

    def forbidden(*_args, **_kwargs):
        pytest.fail("JSX must not enter engineering processor, validator or model repair")

    async def jsx(_bridge, task, _size):
        jsx_calls.append(task)
        return SimpleNamespace(
            a2ui_messages=json_rows(standard),
            component_name="Test", turns=1, elapsed_seconds=0.0,
        )

    monkeypatch.setattr(
        WidgetGenerationService, "_enable_jsx_generation", staticmethod(lambda: True)
    )
    monkeypatch.setattr(JsxA2UIBridge, "generate", jsx)
    monkeypatch.setattr(
        widget_generation_service, "get_dsl_processor",
        lambda _kind: SimpleNamespace(process=forbidden),
    )
    monkeypatch.setattr(ArtifactValidator, "validate", forbidden)
    monkeypatch.setattr(A2UIModelClient, "generate", forbidden)
    result = await getattr(WidgetGenerationService(), f"generate_widget_card_{kind}")(request())
    assert result.status == GenerationStatus.SUCCESS
    assert len(jsx_calls) == 1
    source = await asyncio.to_thread(SourceArtifactRepository().load, result.artifactUrl)
    images = [
        item for item in components(source.artifact.genui) if item.get("component") == "Image"
    ]
    assert images
    for image in images:
        assert image.get("src") == (URL if mapping_hit else SRC)


@pytest.mark.parametrize("kind", ["compact_dsl", "a2ui_form"])
@pytest.mark.asyncio
async def test_jsx_mapping_failure_does_not_trigger_engine_repair_or_save(
    storage, monkeypatch, kind
):
    monkeypatch.setattr(get_settings(), "enable_artifact_validation", True)
    monkeypatch.setattr(get_settings(), "enable_validation_failure_retry", True)
    standard = convert_compact_dsl_to_a2ui(design_source(), size="2x4")
    mapping_error = ValueError("resource mapping failed")
    jsx_calls = []

    def forbidden(*_args, **_kwargs):
        pytest.fail("JSX resource mapping failure must not trigger engineering repair or save")

    def mapping_failed(*_args, **_kwargs):
        raise mapping_error

    async def jsx(_bridge, _task, _size):
        jsx_calls.append(True)
        return SimpleNamespace(
            a2ui_messages=json_rows(standard),
            component_name="Test", turns=1, elapsed_seconds=0.0,
        )

    monkeypatch.setattr(
        WidgetGenerationService, "_enable_jsx_generation", staticmethod(lambda: True)
    )
    monkeypatch.setattr(JsxA2UIBridge, "generate", jsx)
    monkeypatch.setattr(AssetUrlMapper, "rewrite_standard", mapping_failed)
    monkeypatch.setattr(
        widget_generation_service, "get_dsl_processor",
        lambda _kind: SimpleNamespace(process=forbidden),
    )
    monkeypatch.setattr(ArtifactValidator, "validate", forbidden)
    monkeypatch.setattr(A2UIModelClient, "generate", forbidden)
    monkeypatch.setattr(ArtifactStore, "save", forbidden)
    with pytest.raises(ValueError) as raised:
        await getattr(WidgetGenerationService(), f"generate_widget_card_{kind}")(request())
    assert raised.value is mapping_error
    assert len(jsx_calls) == 1


@pytest.mark.parametrize(
    "kind,backend",
    [
        ("compact_dsl", "model"),
        ("a2ui_form", "model"),
        ("compact_dsl", "template"),
        ("compact_dsl", "jsx"),
        ("a2ui_form", "jsx"),
    ],
)
@pytest.mark.parametrize("validation_enabled", [True, False])
@pytest.mark.asyncio
async def test_generation_maps_before_validation_and_saves_separate_sources(
    storage,
    monkeypatch,
    kind,
    backend,
    validation_enabled,
):
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_artifact_validation", validation_enabled)
    token = design_source()
    standard = convert_compact_dsl_to_a2ui(token, size="2x4")
    inputs = []
    validated = []

    def generate(_client, prompt, _profile, **_kwargs):
        inputs.append(json.dumps(prompt, ensure_ascii=False))
        # 生成期间配置变化，不应改变本次请求的映射快照。
        monkeypatch.setattr(settings, "asset_src_url_mapping", {SRC: URL + "changed"})
        return token if kind == "compact_dsl" else standard

    async def template(_generator, task, *_args):
        inputs.append(task.model_dump_json())
        return token

    async def jsx(_bridge, task, _size):
        inputs.append(task.model_dump_json())
        return SimpleNamespace(
            a2ui_messages=[json.loads(line) for line in standard.splitlines()],
            component_name="Test",
            turns=1,
            elapsed_seconds=0.0,
        )

    def validate(validator, artifact, _profile):
        validated.append(artifact.genui)
        assert validator.asset_src_url_mapping == {SRC: URL}
        return []

    monkeypatch.setattr(A2UIModelClient, "generate", generate)
    monkeypatch.setattr(TemplateSourceGenerator, "__call__", template)
    monkeypatch.setattr(JsxA2UIBridge, "generate", jsx)
    monkeypatch.setattr(ArtifactValidator, "validate", validate)
    monkeypatch.setattr(
        WidgetGenerationService,
        "_enable_card_template",
        staticmethod(lambda: backend == "template"),
    )
    monkeypatch.setattr(
        WidgetGenerationService,
        "_enable_jsx_generation",
        staticmethod(lambda: backend == "jsx"),
    )

    result = await getattr(WidgetGenerationService(), f"generate_widget_card_{kind}")(request())
    assert result.status == GenerationStatus.SUCCESS
    source = await asyncio.to_thread(SourceArtifactRepository().load, result.artifactUrl)
    assert inputs
    for model_input in inputs:
        assert SRC in model_input
        assert URL not in model_input
    images = [
        item for item in components(source.artifact.genui) if item.get("component") == "Image"
    ]
    assert images
    for item in images:
        assert item.get("src") == URL
    if backend != "jsx" and validation_enabled:
        assert len(validated) == 1
        assert json_rows(validated[0]) == json_rows(source.artifact.genui)
    else:
        assert not validated
    if kind == "compact_dsl" and backend != "jsx":
        assert source.design_token is not None
        assert SRC in source.design_token
        assert URL not in source.design_token
    task = source.artifact.taskSpec
    assert URL not in json.dumps(task)
    md = (storage / result.artifactUrl.rsplit("/", 1)[-1]).read_text(encoding="utf-8")
    genui_block = md.split("```genui\n", 1)[1].split("\n```", 1)[0]
    assert json_rows(genui_block) == json_rows(source.artifact.genui)


@pytest.mark.asyncio
async def test_edit_and_legacy_url_migration_preserve_source_artifact(storage, monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_artifact_validation", False)
    prompts = []

    def generate(_client, prompt, _profile, **_kwargs):
        prompts.append(json.dumps(prompt, ensure_ascii=False))
        return design_source()

    monkeypatch.setattr(A2UIModelClient, "generate", generate)
    service = WidgetGenerationService()
    created = await service.generate_widget_card_compact_dsl(request())
    assert created.status == GenerationStatus.SUCCESS
    source = await asyncio.to_thread(SourceArtifactRepository().load, created.artifactUrl)
    source_path = storage / created.artifactUrl.rsplit("/", 1)[-1]
    original_bytes = source_path.read_bytes()
    assert source.design_token is not None

    legacy_artifact = source.artifact.model_copy(deep=True)
    candidates = legacy_artifact.taskSpec.get("assetCandidates")
    assert isinstance(candidates, list)
    candidates[0]["src"] = URL
    legacy = replace(
        source,
        artifact=legacy_artifact,
        design_token=source.design_token.replace(SRC, URL),
    )
    restored = SourceArtifactRepository.restore_asset_paths(legacy, {}, restore_genui=True)
    assert restored.artifact_digest == legacy.artifact_digest
    assert restored.design_token is not None
    assert URL not in restored.design_token
    assert URL not in restored.artifact.genui
    assert candidates[0].get("src") == URL
    assert legacy.design_token is not None and URL in legacy.design_token

    for _ in range(2):
        edited = await service.generate_widget_card_compact_dsl(
            request(
                sourceArtifactUrl=created.artifactUrl,
                userQuery="调整背景颜色",
            )
        )
        assert edited.status == GenerationStatus.SUCCESS
        assert edited.artifactUrl != created.artifactUrl
        created = edited
    assert source_path.read_bytes() == original_bytes
    for prompt in prompts:
        assert URL not in prompt


@pytest.mark.asyncio
async def test_repair_uses_original_paths_and_remaps_final_output(storage, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_artifact_validation", True)
    monkeypatch.setattr(settings, "enable_validation_failure_retry", True)
    monkeypatch.setattr(settings, "validation_failure_max_repair_attempts", 1)
    prompts = []
    validated = []

    def generate(_client, prompt, _profile, **_kwargs):
        prompts.append(json.dumps(prompt, ensure_ascii=False))
        return design_source()

    def validate(validator, artifact, _profile):
        validated.append(artifact.genui)
        if len(validated) == 1:
            validator.error_prompt_contexts = [{"actual": URL, "expected": [URL]}]
            return ["test layout issue"]
        return []

    monkeypatch.setattr(A2UIModelClient, "generate", generate)
    monkeypatch.setattr(ArtifactValidator, "validate", validate)
    result = await WidgetGenerationService().generate_widget_card_compact_dsl(request())
    assert result.status == GenerationStatus.SUCCESS
    assert len(prompts) == 2
    assert len(validated) == 2
    for prompt in prompts:
        assert URL not in prompt
        assert SRC in prompt
    for dsl in validated:
        assert URL in dsl
    saved = await asyncio.to_thread(SourceArtifactRepository().load, result.artifactUrl)
    assert json_rows(saved.artifact.genui) == json_rows(validated[-1])
    assert saved.design_token is not None and URL not in saved.design_token


@pytest.mark.asyncio
async def test_standard_edit_restores_paths_before_model_call(storage, monkeypatch):
    monkeypatch.setattr(get_settings(), "enable_artifact_validation", False)
    prompts = []
    standard = convert_compact_dsl_to_a2ui(design_source(), size="2x4")

    def generate(_client, prompt, _profile, **_kwargs):
        prompts.append(json.dumps(prompt, ensure_ascii=False))
        return standard

    monkeypatch.setattr(A2UIModelClient, "generate", generate)
    service = WidgetGenerationService()
    created = await service.generate_widget_card_a2ui_form(request())
    assert created.status == GenerationStatus.SUCCESS
    edited = await service.generate_widget_card_a2ui_form(request(
        sourceArtifactUrl=created.artifactUrl, userQuery="调整背景",
    ))
    assert edited.status == GenerationStatus.SUCCESS
    assert len(prompts) == 2
    assert "previousGenui" in prompts[1]
    assert URL not in prompts[1]
    assert SRC in prompts[1]
    source = await asyncio.to_thread(SourceArtifactRepository().load, edited.artifactUrl)
    assert URL in source.artifact.genui
