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
from services.validation_execution import ValidationExecutionContext
from services.widget_generation_service import WidgetGenerationService


@pytest.mark.asyncio
@pytest.mark.parametrize("jsx_enabled", [False, True])
@pytest.mark.parametrize("repair_enabled", [False, True])
@pytest.mark.parametrize(
    "failure",
    ["match", "generation", "empty", "conversion", "processor_exception",
     "asset_mapping", "validation", "validator_exception", "success",
     "fusion_repair", "fusion_exhausted", "empty_recovers", "empty_exhausted"],
)
async def test_template_attempt_falls_back_to_fresh_fusion(
    monkeypatch, failure, repair_enabled, jsx_enabled,
) -> None:
    calls: list[str] = []
    processed: list[tuple[str, bool]] = []
    saved: list[str] = []
    themed: list[str] = []
    notifications: list[str] = []
    fallback_events: list[dict] = []
    body_attempts: list[list[dict[str, str]]] = []
    theme_validation_contexts: list[ValidationExecutionContext | None] = []
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
        calls.append("template")
        if failure in {"empty_recovers", "empty_exhausted"}:
            client = TemplateModelClient(object(), ModelRequestContext(
                session_id="session", interaction_id="interaction", device_id="device",
                country_code="CN", app_version="11.7.7.331", app_name="CreateMyCard",
            ))
            client._sleep = skip_sleep
            return await client.generate([{"role": "user", "content": task_spec.userQuery}])
        # 即使失败的模板实现修改输入，Fusion 也必须使用完整的原输入。
        task_spec.userQuery = "discarded-template-query"
        card_spec["title"] = "discarded-template-title"
        if failure == "match":
            raise TemplateRouteNotApplicable("no matching template")
        if failure == "generation":
            raise RuntimeError("template generation failed")
        return "" if failure == "empty" else "template-source"

    async def generate_body(_client, _backend, prompt, _context, **_kwargs):
        body_attempts.append(copy.deepcopy(prompt))
        if failure == "empty_recovers" and len(body_attempts) == 2:
            return "template-source"
        raise ModelTransportError("empty body", code="MODEL_EMPTY_OUTPUT")

    async def skip_sleep(_delay):
        return None

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
        validation_context = context.validation_execution_context
        assert validation_context is not None
        assert validation_context.operation == "generateWidgetCardCompactDsl"
        assert validation_context.generation_mode == "create"
        assert context.colorless_layout == (source != "template-source")
        assert context.card_spec.get("title") == "静态卡片"
        if source == "template-source":
            assert validation_context.purpose == "template_candidate"
            assert (validation_context.phase, validation_context.attempt) == ("initial", 1)
            assert context.compact_plan is None
            if failure == "processor_exception":
                raise ValueError("template processing failed")
            if failure in {"conversion", "fusion_repair", "fusion_exhausted"}:
                return DslProcessingResult(source_dsl=source, issues=(
                    QualityIssue(stage="conversion", code="TEST_ERROR", message="invalid template"),
                ))
        else:
            assert source in {"fusion-source", "fusion-repaired-source"}
            assert validation_context.purpose == "delivery_candidate"
            expected_phase = "repair" if source == "fusion-repaired-source" else "initial"
            expected_attempt = 2 if source == "fusion-repaired-source" else 1
            assert (validation_context.phase, validation_context.attempt) == (
                expected_phase,
                expected_attempt,
            )
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

    def validate(_validator, artifact, _profile, *, execution_context=None):
        if artifact.genui == "template-source":
            if failure == "validator_exception":
                raise ValueError("template validation failed")
            if failure == "validation":
                return ["invalid template binding"]
        return []

    async def theme(artifact, *_args, **_kwargs):
        themed.append(artifact.genui)
        theme_validation_contexts.append(_kwargs.get("validation_execution_context"))
        return artifact

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
    monkeypatch.setattr(UnifiedModelClient, "generate", generate_body)
    monkeypatch.setattr(A2UIModelClient, "generate", generate)
    monkeypatch.setattr(A2UIModelClient, "generate_repair", repair)
    monkeypatch.setattr(service_module, "get_dsl_processor", lambda _kind: SimpleNamespace(
        process=process,
    ))
    monkeypatch.setattr(AssetUrlMapper, "rewrite_standard", rewrite)
    monkeypatch.setattr(service_module.ArtifactValidator, "validate", validate)
    monkeypatch.setattr(service_module.ArtifactValidator, "validate_layout", validate)
    monkeypatch.setattr("services.post_layout_theme.theme_artifact", theme)
    monkeypatch.setattr(service_module, "JsxA2UIBridge", unexpected_jsx)
    monkeypatch.setattr(service_module, "trace_record", trace_record)
    monkeypatch.setattr(ArtifactStore, "save", save)
    # 本测试使用占位 DSL，序列化由独立测试覆盖，这里只验证路线和上下文隔离。
    monkeypatch.setattr(
        service_module, "serialize_compact_dsl_source", lambda source, **_kw: source,
    )
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
    if failure in {"empty_recovers", "empty_exhausted"}:
        assert len(body_attempts) == 2
        assert body_attempts[0] == body_attempts[1]
    if failure in {"success", "empty_recovers"}:
        assert calls == ["template"]
        assert processed == [("template-source", True)]
        assert saved == ["template-source"]
        assert fallback_events == []
        assert themed == []
    else:
        expected_calls = ["template", "raw-json", "compact-dsl"]
        final_source = "fusion-source"
        if fusion_quality_failure and repair_enabled:
            expected_calls.append("repair")
            final_source = "fusion-repaired-source"
        assert calls == expected_calls
        assert processed[-1] == (final_source, False)
        assert saved == ([] if terminal_failure else [final_source])
        assert themed == ([] if terminal_failure else [final_source])
        assert len(fallback_events) == 1
    if themed:
        assert len(theme_validation_contexts) == 1
        theme_context = theme_validation_contexts[0]
        assert theme_context is not None
        assert (
            theme_context.operation,
            theme_context.generation_mode,
            theme_context.phase,
            theme_context.attempt,
            theme_context.purpose,
        ) == (
            "generateWidgetCardCompactDsl",
            "create",
            "theme",
            1,
            "theme_candidate",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "phase", ["template-retrieval-query", "advanced-mixed-body", "advanced-mixed-body-repair"],
)
@pytest.mark.parametrize("model_retry_enabled", [False, True])
@pytest.mark.parametrize("error_code", ["MODEL_EMPTY_OUTPUT", "MODEL_OUTPUT_TRUNCATED"])
@pytest.mark.parametrize("recovers", [False, True])
async def test_template_model_retry_policy(
    monkeypatch, phase, model_retry_enabled, error_code, recovers,
) -> None:
    settings = get_settings().model_copy(update={
        "enable_model_failure_retry": model_retry_enabled,
        "enable_openai_fallback": True,
    })
    monkeypatch.setattr("services.template_generation.model_client.get_settings", lambda: settings)
    request_context = ModelRequestContext(
        session_id="session", interaction_id="interaction", device_id="device",
        country_code="CN", app_version="11.7.7.331", app_name="CreateMyCard",
    )
    client = TemplateModelClient(object(), request_context)
    attempts: list[str] = []
    delays: list[float] = []
    prompt = [{"role": "user", "content": "原始模板填充输入"}]

    async def generate(_client, _backend, _prompt, _context, **kwargs):
        attempts.append(kwargs.get("phase"))
        assert _prompt == prompt
        if recovers and len(attempts) == 2:
            return "template-source"
        raise ModelTransportError("model failed", code=error_code)

    async def sleep(delay):
        delays.append(delay)

    monkeypatch.setattr(UnifiedModelClient, "generate", generate)
    client._sleep = sleep
    body_retry = phase != "template-retrieval-query" and error_code == "MODEL_EMPTY_OUTPUT"
    if body_retry and recovers:
        assert await client.generate(prompt, phase=phase) == "template-source"
    else:
        with pytest.raises(ModelTransportError, match="model failed"):
            await client.generate(prompt, phase=phase)
    assert len(attempts) == (2 if body_retry else 1)
    assert len(delays) == (1 if body_retry else 0)
    body_plans = client._body_client._provider_plans("openai")
    assert len(body_plans) == 1
    assert body_plans[0].max_retry_attempts == 0
    assert client._client.settings is settings
    assert client._client.settings.enable_model_failure_retry is model_retry_enabled
    assert client._client.settings.enable_openai_fallback


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
