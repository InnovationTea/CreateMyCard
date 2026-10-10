"""固定模型返回序列，核对两条真实修复入口的兼容边界。"""

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from api.schemas import GenerateWidgetCardRequest
from config.config import get_settings
from core.errors import GenerationStatus
from custom.a2ui_model_client import A2UIModelClient
from models.artifact import ArtifactMeta, WidgetArtifact
from models.generation import TaskSpec
from models.service import ArtifactSaveResult
from repair_compact_dsl import (
    CompactDslArtifactSource,
    CompactDslRepairError,
    _repair_compact_dsl_source,
)
from services import widget_generation_service
from services.artifact_store import ArtifactStore, RepairArtifactRecord
from services.asset_url_mapper import AssetUrlMapper
from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext
from services.validator import ArtifactValidator
from services.widget_generation_service import WidgetGenerationService

INVALID = "\n".join(
    [
        '["root","Column",{"width":320,"height":160},["cta"]]',
        '["cta","ActionUnit",{"state":"capsule","label":"设置"}]',
        '["/state/ready",true]',
    ]
)
VALID = (Path(__file__).parents[1] / "cloud/custom/mock.design-compact-dsl-2x4.dat").read_text(
    encoding="utf-8"
)
LEGACY = "component cta: ActionUnit.onClick is required."
PREFIX = "[stage=validation code=COMPACT_DSL_VALIDATION_FAILED] "
SRC = "resources/base/media/drop_1.svg"
URL = "https://example.test/drop_1.svg"


def _source() -> CompactDslArtifactSource:
    task = TaskSpec(userQuery="静态卡片", size="2x4", dataModelSchema={"data": {}})
    artifact = WidgetArtifact(
        genui="",
        cardSpec={"title": "静态卡片", "description": "修复验证", "suggestSize": "2x4"},
        taskSpec=task.model_dump(mode="json"),
        meta=ArtifactMeta(
            protocolProfileId="a2ui-form-rom6.0-v1",
            capabilityRegistryVersion="app-11.7.5.205_rom-6.0",
            createdAt=0,
        ),
    )
    return CompactDslArtifactSource(artifact, task, INVALID)


def _quality_errors(prompt: list[dict[str, str]]) -> list[dict[str, Any]]:
    content = prompt[1].get("content")
    assert isinstance(content, str)
    payload = json.loads(content)
    assert payload.get("invalidSourceDsl") == INVALID
    errors = payload.get("qualityErrors")
    assert isinstance(errors, list)
    assert len(errors) == 1
    issue = errors[0]
    assert issue.get("stage") == "validation"
    assert issue.get("code") == "COMPACT_DSL_VALIDATION_FAILED"
    assert "compactDiagnostics" not in issue
    message = issue.get("message")
    assert isinstance(message, str)
    assert "COMPACT_ACTION_CLICK_REQUIRED" in message
    assert "原文第 2 行" in message
    assert "约束：" in message
    return errors


@pytest.mark.asyncio
@pytest.mark.parametrize("succeeds", [True, False])
async def test_standalone_fixed_rounds_preserve_result_and_exception(
    monkeypatch: pytest.MonkeyPatch, succeeds: bool
) -> None:
    prompts: list[list[dict[str, str]]] = []
    outputs = iter([INVALID, VALID if succeeds else INVALID])
    closed: list[bool] = []

    async def generate(_client: Any, prompt: list[dict[str, str]], _profile: Any) -> str:
        prompts.append(prompt)
        return next(outputs)

    async def close(_client: Any) -> None:
        closed.append(True)

    def forbidden_restore(*_args: Any, **_kwargs: Any) -> Any:
        pytest.fail("独立入口不应引入在线素材还原")

    monkeypatch.setattr(A2UIModelClient, "generate_repair", generate)
    monkeypatch.setattr(A2UIModelClient, "aclose", close)
    monkeypatch.setattr(AssetUrlMapper, "restore_diagnostic_values", forbidden_restore)
    # 完整产物规则保持既有职责，本用例隔离其结果，实际执行 Compact 解析、校验、转换。
    monkeypatch.setattr(ArtifactValidator, "validate", lambda *_args: [])
    if succeeds:
        result = await _repair_compact_dsl_source(_source(), max_repair_attempts=2)
        assert result.compact_dsl == VALID
        assert '"createSurface"' in result.dsl
        assert result.repair_count == 2
        assert result.initial_errors == (PREFIX + LEGACY,)
    else:
        with pytest.raises(CompactDslRepairError) as captured:
            await _repair_compact_dsl_source(_source(), max_repair_attempts=2)
        error = captured.value
        assert error.errors == (PREFIX + LEGACY,)
        assert str(error) == PREFIX + LEGACY
        assert error.args == (PREFIX + LEGACY,)
        assert error.__cause__ is None
    assert len(prompts) == 2
    assert closed == [True]
    for prompt in prompts:
        _quality_errors(prompt)


@pytest.mark.asyncio
async def test_online_restores_nested_facts_before_formatting_and_preserves_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_artifact_validation", False)
    monkeypatch.setattr(settings, "enable_validation_failure_retry", True)
    monkeypatch.setattr(settings, "validation_failure_max_repair_attempts", 2)
    monkeypatch.setattr(
        WidgetGenerationService, "_enable_card_template", staticmethod(lambda: False)
    )
    monkeypatch.setattr(
        WidgetGenerationService, "_enable_jsx_generation", staticmethod(lambda: False)
    )
    # 注入已映射事实，验证真实在线入口的还原/格式化先后顺序；校验仍执行真实规则。
    mapper = AssetUrlMapper({SRC: URL}, {SRC})
    monkeypatch.setattr(widget_generation_service, "AssetUrlMapper", lambda *_args: mapper)
    original_process = DesignCompactProcessor.process
    internal_payloads: list[list[dict[str, Any]]] = []

    def process(
        processor: DesignCompactProcessor, source: str, context: DslProcessingContext
    ) -> Any:
        result = original_process(processor, source, context)
        for issue in result.errors:
            diagnostics = issue.prompt_context.get("compactDiagnostics")
            assert isinstance(diagnostics, list)
            diagnostics[0]["actual"] = {"asset": URL, "nested": [URL]}
        internal_payloads.append([issue.to_prompt_payload() for issue in result.errors])
        return result

    monkeypatch.setattr(DesignCompactProcessor, "process", process)
    outputs = iter([INVALID, INVALID, VALID])
    prompts: list[list[dict[str, str]]] = []
    saved_records: list[RepairArtifactRecord] = []

    def generate(_client: Any, prompt: list[dict[str, str]], *_args: Any, **_kw: Any) -> str:
        prompts.append(prompt)
        return next(outputs)

    def save(store: ArtifactStore, _artifact: WidgetArtifact) -> ArtifactSaveResult:
        saved_records.extend(store.repair_records)
        return ArtifactSaveResult(
            artifactUrl="https://artifact.test/result", artifactDigest="sha256:x"
        )

    monkeypatch.setattr(A2UIModelClient, "generate", generate)
    monkeypatch.setattr(ArtifactStore, "save", save)
    request = GenerateWidgetCardRequest(
        uid="test-user",
        prdVer="11.7.5.205",
        device={"romVersion": "6.0"},
        userQuery="静态卡片",
        size="2x4",
        title="静态卡片",
        description="修复验证",
    )
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(request)
    assert response.status == GenerationStatus.SUCCESS
    assert len(prompts) == 3
    for prompt in prompts[1:]:
        errors = _quality_errors(prompt)
        message = errors[0].get("message")
        assert isinstance(message, str)
        assert SRC in message
        assert URL not in message
    assert len(saved_records) == 2
    failed_record = saved_records[0]
    assert failed_record.model_generated_compact_dsl == INVALID
    assert failed_record.validation_errors == tuple(internal_payloads[1])
    record_payload = failed_record.to_payload()
    before = deepcopy(record_payload)
    encoded = json.dumps(record_payload, ensure_ascii=False)
    assert URL in encoded
    assert LEGACY in encoded
    assert "compactDiagnostics" in encoded
    assert record_payload == before
    assert saved_records[1].validation_errors == ()
    assert internal_payloads[0] == internal_payloads[1]
