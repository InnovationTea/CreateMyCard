"""普通创建入口的模板失败必须从 Fusion Plan 重启，不沿用模板修复上下文。"""

import copy
import json
from types import SimpleNamespace

import pytest

from api.schemas import GenerateWidgetCardRequest
from config.config import get_settings
from core.errors import GenerationStatus
from custom.a2ui_model_client import A2UIModelClient, A2UIModelGenerationError
from custom.model_transport import ModelTransportError
from custom.unified_model_client import UnifiedModelClient
from models.generation import ModelRequestContext
from services import widget_generation_service as service_module
from services.artifact_store import ArtifactStore
from services.asset_url_mapper import AssetUrlMapper
from services.generation_pipeline import DslProcessingResult, QualityIssue
from services.template_generation import TemplateSourceGenerator
from services.template_generation.engine.pipeline import TemplateRouteNotApplicable
from services.template_generation.model_client import TemplateModelClient
from services.widget_generation_service import WidgetGenerationService


@pytest.mark.asyncio
@pytest.mark.parametrize("jsx_enabled", [False, True])
@pytest.mark.parametrize("repair_enabled", [False, True])
@pytest.mark.parametrize(
    "failure",
    ["match", "generation", "empty", "conversion", "processor_exception",
     "asset_mapping", "validation", "validator_exception", "success",
     "fusion_repair", "fusion_exhausted"],
)
async def test_template_attempt_falls_back_to_fresh_fusion(
    monkeypatch, failure, repair_enabled, jsx_enabled,
) -> None:
    calls: list[str] = []
    processed: list[tuple[str, bool]] = []
    saved: list[str] = []
    notifications: list[str] = []
    fallback_events: list[dict] = []
    settings = get_settings().model_copy(update={
        "enable_a2ui_model_mock": False,
        "enable_artifact_validation": True,
        "enable_validation_failure_retry": repair_enabled,
        "validation_failure_max_repair_attempts": 1,
        "enable_design_compact_runtime_prompt_context": False,
    })
    monkeypatch.setattr(service_module, "get_settings", lambda: settings)
    monkeypatch.setattr("custom.a2ui_model_client.get_settings", lambda: settings)
    monkeypatch.setattr(WidgetGenerationService, "_enable_card_template", lambda _self: True)
    monkeypatch.setattr(
        WidgetGenerationService, "_enable_jsx_generation", lambda _self: jsx_enabled,
    )

    async def template(generator, task_spec, card_spec, _bindings):
        assert generator.fail_fast
        calls.append("template")
        # 即使失败的模板实现修改输入，Fusion 也必须使用完整的原输入。
        task_spec.userQuery = "discarded-template-query"
        card_spec["title"] = "discarded-template-title"
        if failure == "match":
            raise TemplateRouteNotApplicable("no matching template")
        if failure == "generation":
            raise RuntimeError("template generation failed")
        return "" if failure == "empty" else "template-source"

    async def generate(_client, prompt, profile=None, **_kwargs):
        model_format = (profile or {}).get("format")
        calls.append(model_format)
        prompt_text = json.dumps(prompt, ensure_ascii=False)
        assert "discarded-template" not in prompt_text
        assert "template-source" not in prompt_text
        assert "静态卡片" in prompt_text
        if model_format == "raw-json":
            assert not any(item.get("role") == "assistant" for item in prompt)
            return json.dumps({
                "name": "submit_card_plan",
                "arguments": {
                    "info_required": [{"requirement": "卡片标题", "priority": "must",
                                       "text": "静态卡片", "componentHints": ["EmphasisText"]}],
                    "layoutHints": ["S-center"],
                },
            }, ensure_ascii=False)
        return "fusion-source"

    async def repair(_client, prompt, *_args, **_kwargs):
        assert failure in {"fusion_repair", "fusion_exhausted"}
        calls.append("repair")
        prompt_text = json.dumps(prompt, ensure_ascii=False)
        assert "fusion-source" in prompt_text
        assert "template-source" not in prompt_text
        assert "discarded-template" not in prompt_text
        return "fusion-repaired-source"

    def process(source, context):
        processed.append((source, context.skip_compact_dsl_validation))
        assert context.card_spec.get("title") == "静态卡片"
        if source == "template-source":
            assert context.compact_plan is None
            if failure == "processor_exception":
                raise ValueError("template processing failed")
            if failure in {"conversion", "fusion_repair", "fusion_exhausted"}:
                return DslProcessingResult(source_dsl=source, issues=(
                    QualityIssue(stage="conversion", code="TEST_ERROR", message="invalid template"),
                ))
        else:
            assert source in {"fusion-source", "fusion-repaired-source"}
            assert context.compact_plan is not None
            fusion_invalid = failure == "fusion_exhausted"
            needs_first_repair = failure == "fusion_repair" and source == "fusion-source"
            if fusion_invalid or needs_first_repair:
                return DslProcessingResult(source_dsl=source, issues=(
                    QualityIssue(stage="conversion", code="FUSION_ERROR", message="invalid fusion"),
                ))
        return DslProcessingResult(source_dsl=source, standard_dsl=source)

    def rewrite(_mapper, source):
        if source == "template-source" and failure == "asset_mapping":
            raise ValueError("unknown template asset")
        return source

    def validate(_validator, artifact, _profile):
        if artifact.genui == "template-source":
            if failure == "validator_exception":
                raise ValueError("template validation failed")
            if failure == "validation":
                return ["invalid template binding"]
        return []

    async def save(store, artifact):
        saved.append(artifact.genui)
        assert store.design_token == artifact.genui
        return SimpleNamespace(
            artifactUrl="https://artifact.test/fusion", artifactDigest="sha256:x",
        )

    async def before_model_call(size):
        notifications.append(size)

    def trace_record(event, **kwargs):
        if event == "template.fallback":
            fallback_events.append(copy.deepcopy(kwargs))

    def unexpected_jsx():
        pytest.fail("template failure must bypass JSX")

    monkeypatch.setattr(TemplateSourceGenerator, "__call__", template)
    monkeypatch.setattr(A2UIModelClient, "generate", generate)
    monkeypatch.setattr(A2UIModelClient, "generate_repair", repair)
    monkeypatch.setattr(service_module, "get_dsl_processor", lambda _kind: SimpleNamespace(
        process=process,
    ))
    # 此测试隔离编排，处理器返回的是来源标记而非真实 DSL。
    monkeypatch.setattr(
        service_module, "serialize_compact_dsl_source", lambda source, **_kwargs: source,
    )
    monkeypatch.setattr(AssetUrlMapper, "rewrite_standard", rewrite)
    monkeypatch.setattr(service_module.ArtifactValidator, "validate", validate)
    monkeypatch.setattr(service_module, "JsxA2UIBridge", unexpected_jsx)
    monkeypatch.setattr(service_module, "trace_record", trace_record)
    monkeypatch.setattr(ArtifactStore, "save", save)
    request = GenerateWidgetCardRequest(
        uid="test-user", prdVer="11.7.7.331", device={"romVersion": "7.0"},
        userQuery="生成一个名为静态卡片的卡片", size="2x2", title="静态卡片",
        description="模板失败回退测试",
    )
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(
        request, before_model_call=before_model_call,
    )
    fusion_quality_failure = failure in {"fusion_repair", "fusion_exhausted"}
    terminal_failure = fusion_quality_failure and not repair_enabled
    terminal_failure = terminal_failure or failure == "fusion_exhausted"
    expected_status = GenerationStatus.FAILED if terminal_failure else GenerationStatus.SUCCESS
    assert response.status == expected_status
    assert notifications == ["2x2"]
    if failure == "success":
        assert calls == ["template"]
        assert processed == [("template-source", True)]
        assert saved == ["template-source"]
        assert fallback_events == []
    else:
        expected_calls = ["template", "raw-json", "compact-dsl"]
        final_source = "fusion-source"
        if fusion_quality_failure and repair_enabled:
            expected_calls.append("repair")
            final_source = "fusion-repaired-source"
        assert calls == expected_calls
        assert processed[-1] == (final_source, False)
        assert saved == ([] if terminal_failure else [final_source])
        assert len(fallback_events) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["template-retrieval-query", "advanced-mixed-body"])
@pytest.mark.parametrize("fail_fast", [False, True])
async def test_template_model_retry_policy(monkeypatch, phase, fail_fast) -> None:
    settings = get_settings().model_copy(update={
        "enable_model_failure_retry": True,
        "enable_openai_fallback": True,
    })
    monkeypatch.setattr("services.template_generation.model_client.get_settings", lambda: settings)
    request_context = ModelRequestContext(
        session_id="session", interaction_id="interaction", device_id="device",
        country_code="CN", app_version="11.7.7.331", app_name="CreateMyCard",
    )
    client = TemplateModelClient(object(), request_context, fail_fast=fail_fast)
    attempts: list[str] = []
    delays: list[float] = []

    async def generate(_client, _backend, _prompt, _context, **kwargs):
        attempts.append(kwargs.get("phase"))
        raise ModelTransportError("empty body", code="MODEL_EMPTY_OUTPUT")

    async def sleep(delay):
        delays.append(delay)

    monkeypatch.setattr(UnifiedModelClient, "generate", generate)
    client._sleep = sleep
    with pytest.raises(ModelTransportError, match="empty body"):
        await client.generate([], phase=phase)
    body_retry = phase == "advanced-mixed-body" and not fail_fast
    assert len(attempts) == (2 if body_retry else 1)
    assert len(delays) == (1 if body_retry else 0)
    if fail_fast:
        plans = client._client._provider_plans("openai")
        assert len(plans) == 1
        assert plans[0].max_retry_attempts == 0
    else:
        assert client._client.settings.enable_model_failure_retry


@pytest.mark.asyncio
async def test_fusion_failure_does_not_restart_template(monkeypatch) -> None:
    settings = get_settings().model_copy(update={"enable_a2ui_model_mock": False})
    monkeypatch.setattr(service_module, "get_settings", lambda: settings)
    monkeypatch.setattr("custom.a2ui_model_client.get_settings", lambda: settings)
    monkeypatch.setattr(WidgetGenerationService, "_enable_card_template", lambda _self: True)
    calls: list[str] = []

    async def template(*_args):
        calls.append("template")
        raise RuntimeError("no template")

    async def generate(*_args, **_kwargs):
        calls.append("fusion")
        raise A2UIModelGenerationError("fusion failed")

    monkeypatch.setattr(TemplateSourceGenerator, "__call__", template)
    monkeypatch.setattr(A2UIModelClient, "generate", generate)
    request = GenerateWidgetCardRequest(
        uid="test-user", prdVer="11.7.7.331", device={"romVersion": "7.0"},
        userQuery="静态卡片", size="2x2", title="静态卡片", description="模板回退失败",
    )
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(request)
    assert response.status == GenerationStatus.FAILED
    assert response.artifactUrl == ""
    assert calls == ["template", "fusion"]
