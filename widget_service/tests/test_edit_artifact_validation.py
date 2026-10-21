"""编辑引用授权共用产物规则，服务不再追加旧路径子串检查。"""

import asyncio
import copy
import json
from dataclasses import dataclass, field

import pytest

from api.schemas import GenerateWidgetCardRequest
from config.config import get_settings
from core.errors import ErrorCode, GenerationStatus
from custom.a2ui_model_client import A2UIModelClient
from services.card_validation import validate_card
from services.generation_pipeline import DslProcessingResult
from services.single_step_edit import source_digest
from services.source_artifact_repository import SourceArtifactRepository
from services.widget_generation_service import WidgetGenerationService
from utils.upload_file_obs import UploadFileOSMS

OLD_ROOT = "/data/weather"
OLD_REFERENCE = "{{ ${/data/weather/current/condition} }}"
PATH_CODE = "EFFECTIVE_DATA_PATH_NOT_ALLOWED"


def _standard_dsl(content: str, kind: str = "text") -> str:
    text = {
        "id": "value",
        "component": "Text",
        "content": content,
        "styles": {"fontSize": 18, "fontColor": "#FF000000"},
    }
    root = {
        "id": "root",
        "component": "Column",
        "children": ["value"],
        "styles": {
            "width": "matchParent",
            "height": "matchParent",
            "padding": 12,
            "backgroundColor": "#FFFFFFFF",
        },
    }
    if kind == "template":
        root["children"] = {"componentId": "value", "path": OLD_ROOT + "/items"}
    if kind == "event":
        text["content"] = "天气"
        text["onClick"] = [{"call": "test", "args": {"value": content}}]
    if kind == "style":
        text["styles"] = {"fontSize": 18, "fontColor": content}
        text["content"] = "天气"
    # 未移除的首帧值不能让已取消授权的动态路径通过。
    weather = {"current": {"condition": "晴"}, "items": [{"condition": "晴"}]}
    rows = [
        {
            "version": "v0.9",
            "createSurface": {
                "surfaceId": "card",
                "catalogId": "ohos.a2ui.extended.catalog.form",
            },
        },
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": "card", "root": "root", "components": [root, text],
            },
        },
        {
            "version": "v0.9",
            "updateDataModel": {
                "surfaceId": "card",
                "path": "/",
                "value": {
                    "data": {
                        "weather": {**weather, "today": weather},
                        "weatherBackup": weather,
                    },
                },
            },
        },
    ]
    dsl = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    if kind == "escaped":
        dsl = dsl.replace("/", r"\/")
    return dsl


def _binding(root: str) -> dict:
    return {
        "capabilityId": "ViewWeather",
        "arguments": {"prefectureName": "上海市", "forecastDays": 1},
        "writeResultTo": root,
        "candidateOutputFields": ["/current/condition"],
    }


@pytest.mark.parametrize(
    ("content", "root", "kind", "location"),
    [
        pytest.param(OLD_REFERENCE, None, "text", "value/content", id="removed-with-old-data"),
        pytest.param(OLD_ROOT, None, "text", None, id="literal-path"),
        pytest.param(
            "{{ ${/data/weatherBackup/current/condition} }}",
            "/data/weatherBackup", "text", None, id="authorized-sibling",
        ),
        pytest.param(
            "{{ ${/data/weather/today/current/condition} }}",
            "/data/weather/today", "text", None, id="authorized-child",
        ),
        pytest.param(OLD_REFERENCE, None, "escaped", "value/content", id="escaped-slashes"),
        pytest.param("静态卡片", None, "text", None, id="unused-old-data"),
        pytest.param(
            "{{ ${condition} }}", None, "template", "root/children/path", id="relative-template",
        ),
        pytest.param(
            OLD_REFERENCE, None, "event", "value/onClick/0/args/value", id="event-argument",
        ),
        pytest.param(
            OLD_REFERENCE, None, "style", "value/styles/fontColor", id="style-expression",
        ),
        pytest.param(OLD_REFERENCE, OLD_ROOT, "text", None, id="inherited-binding"),
    ],
)
def test_current_binding_authorizes_parsed_references(content, root, kind, location):
    bindings = [] if root is None else [_binding(root)]
    artifact = {
        "genui": _standard_dsl(content, kind),
        "cardSpec": {
            "title": "天气", "description": "当前天气", "suggestSize": "2x2",
            "dataBindings": bindings,
        },
        "effectiveCapabilities": {
            "data": [] if root is None else ["ViewWeather"], "event": [], "asset": [],
        },
    }
    reporter = validate_card(artifact=artifact)
    errors = [item for item in reporter.diagnostics if item.code == PATH_CODE]
    if location is None:
        assert not errors
    else:
        assert len(errors) == 1
        assert errors[0].severity == "error"
        assert errors[0].file_kind == "genui"
        assert errors[0].line == 2
        assert errors[0].json_pointer == "/updateComponents/componentsById/" + location


@dataclass
class GenerationProbe:
    outputs: list[str] = field(default_factory=list)
    prompts: list[list[dict]] = field(default_factory=list)
    metrics: list[dict] = field(default_factory=list)
    evaluations: list[dict] = field(default_factory=list)
    plan_calls: int = 0


@pytest.fixture
def generation_probe(tmp_path, monkeypatch):
    probe = GenerationProbe()
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_semantic_widget_edit", False)
    monkeypatch.setattr(settings, "enable_a2ui_model_mock", False)
    monkeypatch.setattr(settings, "enable_design_compact_runtime_prompt_context", False)
    monkeypatch.setattr(settings, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(settings, "enable_widget_edit", True)
    # 原有整卡编辑与 Compact 修复的契约仍单独验证，不把整卡 mock 当字段补丁。
    monkeypatch.setattr(settings, "enable_single_step_widget_edit", False)
    monkeypatch.setattr(settings, "enable_artifact_download_mock", True)
    monkeypatch.setattr(settings, "enable_artifact_validation", True)
    monkeypatch.setattr(settings, "enable_validation_failure_retry", False)
    monkeypatch.setattr(settings, "asset_src_url_mapping", {})
    monkeypatch.setattr(
        WidgetGenerationService, "_enable_card_template", staticmethod(lambda: False),
    )
    monkeypatch.setattr(
        WidgetGenerationService, "_enable_jsx_generation", staticmethod(lambda: False),
    )
    monkeypatch.setattr(
        "services.artifact_store.file_obs",
        UploadFileOSMS(
            base_url="https://artifact.test", mock_storage_dir=tmp_path / "mock_obs",
        ),
    )

    def generate(_client, prompt, _profile=None, **_kwargs):
        probe.prompts.append(copy.deepcopy(prompt))
        if (_profile or {}).get("id") == "compact-info-plan":
            probe.plan_calls += 1
            return json.dumps({
                "name": "submit_card_plan",
                "arguments": {"info_required": [{
                    "requirement": "天气展示", "text": "天气", "priority": "must",
                    "componentHints": ["EmphasisText"],
                }]},
            }, ensure_ascii=False)
        assert probe.outputs, "发生非预期模型调用"
        return probe.outputs.pop(0)

    def metrics(*, body, **_kwargs):
        probe.metrics.append(body)

    def trace(event, **kwargs):
        if event == "artifact_validation.completed":
            probe.evaluations.append(kwargs)

    monkeypatch.setattr(A2UIModelClient, "generate", generate)
    monkeypatch.setattr("services.widget_generation_service.report_ops_metrics", metrics)
    monkeypatch.setattr("services.widget_generation_service.trace_step", trace)
    return probe


def _request(**updates) -> GenerateWidgetCardRequest:
    values = {
        "uid": "edit-validation-test",
        "device": {"romVersion": "6.0"},
        "prdVer": "11.7.5.205",
        "userQuery": "生成天气卡片",
        "title": "天气",
        "description": "当前天气",
        "size": "2x2",
        "candidateDataBindings": [_binding(OLD_ROOT)],
        "candidateEventCandidates": [],
        "candidateAssetIds": [],
    }
    values.update(updates)
    return GenerateWidgetCardRequest(**values)


def _evaluation_result(evaluation: dict) -> dict:
    artifacts = evaluation.get("json_artifacts")
    assert isinstance(artifacts, dict)
    result = artifacts.get("artifact_validation_result")
    assert isinstance(result, dict)
    return result


@pytest.mark.parametrize(
    ("content", "new_root", "kind", "valid"),
    [
        pytest.param(OLD_ROOT, None, "text", True, id="clear-with-literal"),
        pytest.param("静态卡片", None, "text", True, id="clear-with-unused-data"),
        pytest.param(OLD_REFERENCE, None, "text", False, id="clear-with-reference"),
        pytest.param(OLD_REFERENCE, None, "escaped", False, id="clear-with-escaped-reference"),
        pytest.param(
            "{{ ${/data/weatherBackup/current/condition} }}",
            "/data/weatherBackup", "text", True, id="replace-with-sibling",
        ),
        pytest.param(
            "{{ ${/data/weather/today/current/condition} }}",
            "/data/weather/today", "text", True, id="replace-with-child",
        ),
        pytest.param(OLD_REFERENCE, "/data/weatherBackup", "text", False, id="replace-stale"),
        pytest.param(OLD_REFERENCE, OLD_ROOT, "text", True, id="inherit"),
    ],
)
@pytest.mark.asyncio
async def test_edit_uses_real_artifact_validator(
    generation_probe, content, new_root, kind, valid,
):
    probe = generation_probe
    probe.outputs.extend([_standard_dsl(OLD_REFERENCE), _standard_dsl(content, kind)])
    service = WidgetGenerationService()
    created = await service.generate_widget_card_a2ui_form(_request())
    assert created.status == GenerationStatus.SUCCESS
    source = await asyncio.to_thread(SourceArtifactRepository().load, created.artifactUrl)
    original = source.artifact.model_dump_json()
    updates = {"sourceArtifactUrl": created.artifactUrl, "userQuery": "调整卡片"}
    if new_root != OLD_ROOT:
        updates["candidateDataBindings"] = [] if new_root is None else [_binding(new_root)]
    # 从最小编辑请求开始，省略候选时走真实继承流程。
    edited = await service.generate_widget_card_a2ui_form(
        GenerateWidgetCardRequest(
            uid="edit-validation-test", device={"romVersion": "6.0"},
            prdVer="11.7.5.205", **updates,
        ),
    )
    assert len(probe.prompts) == 2
    assert not probe.outputs
    assert len(probe.evaluations) == 2
    assert _evaluation_result(probe.evaluations[0]).get("errors") == []
    evaluation = probe.evaluations[-1]
    result = _evaluation_result(evaluation)
    errors = result.get("errors")
    contexts = result.get("promptContexts")
    assert isinstance(errors, list)
    assert isinstance(contexts, list)
    failures = [item for item in probe.metrics if "validationScenarioFailure" in item]
    if valid:
        assert edited.status == GenerationStatus.SUCCESS
        assert not errors
        assert not contexts
        assert not failures
        loaded = await asyncio.to_thread(SourceArtifactRepository().load, edited.artifactUrl)
        updated = loaded.artifact
        roots = [item.writeResultTo for item in updated.generationPlan.candidateDataBindings]
        assert roots == ([] if new_root is None else [new_root])
        assert updated.effectiveCapabilities.get("data") == (
            [] if new_root is None else ["ViewWeather"]
        )
        assert edited.artifactUrl != created.artifactUrl
    else:
        # 标准 A2UI 入口原有非阻断策略保持不变，校验仍须报错并准确计数。
        assert edited.status == GenerationStatus.SUCCESS
        assert edited.artifactUrl
        assert evaluation.get("status") == "failed"
        assert len(errors) == len(contexts) == 1
        assert PATH_CODE in errors[0]
        assert contexts[0].get("code") == PATH_CODE
        assert contexts[0].get("fileKind") == "genui"
        assert contexts[0].get("jsonPointer") == (
            "/updateComponents/componentsById/value/content"
        )
        assert failures == [{"validationScenarioFailure": 1}]
    unchanged = await asyncio.to_thread(SourceArtifactRepository().load, created.artifactUrl)
    assert unchanged.artifact.model_dump_json() == original


@pytest.mark.parametrize("remove_binding", [False, True])
@pytest.mark.parametrize("validation_enabled", [False, True])
@pytest.mark.asyncio
async def test_patch_edit_preserves_source_and_runs_real_reference_validation(
    generation_probe, monkeypatch, remove_binding, validation_enabled,
):
    probe = generation_probe
    probe.outputs.append(_standard_dsl(OLD_REFERENCE))
    service = WidgetGenerationService()
    created = await service.generate_widget_card_a2ui_form(_request())
    assert created.status == GenerationStatus.SUCCESS
    source = await asyncio.to_thread(SourceArtifactRepository().load, created.artifactUrl)
    original = source.artifact.model_dump_json()
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_single_step_widget_edit", True)
    monkeypatch.setattr(settings, "enable_artifact_validation", validation_enabled)
    instruction = "仅把value字号改为16fp"
    probe.outputs.append(json.dumps({
        "sourceDigest": source_digest(source.artifact.genui),
        "changes": [{"componentId": "value", "property": "styles.fontSize",
                     "before": {"exists": True, "value": 18}, "value": 16,
                     "requestQuote": instruction}],
    }, ensure_ascii=False))
    updates = {"candidateDataBindings": []} if remove_binding else {}
    edited = await service.generate_widget_card_a2ui_form(GenerateWidgetCardRequest(
        uid="edit-validation-test", device={"romVersion": "6.0"}, prdVer="11.7.5.205",
        sourceArtifactUrl=created.artifactUrl, userQuery=instruction, **updates,
    ))
    assert len(probe.prompts) == 2
    assert len(probe.evaluations) == 2
    errors = _evaluation_result(probe.evaluations[-1]).get("errors")
    assert isinstance(errors, list)
    if remove_binding:
        assert edited.status == GenerationStatus.FAILED
        assert edited.errorCode == ErrorCode.VALIDATION_FAILED.value
        assert any(PATH_CODE in error for error in errors)
        assert not edited.artifactUrl
    else:
        assert edited.status == GenerationStatus.SUCCESS
        assert not errors
        changed = await asyncio.to_thread(SourceArtifactRepository().load, edited.artifactUrl)
        expected = [json.loads(line) for line in source.artifact.genui.splitlines()]
        for row in expected:
            for node in row.get("updateComponents", {}).get("components", []):
                if node.get("id") == "value":
                    styles = node.get("styles")
                    assert isinstance(styles, dict)
                    styles["fontSize"] = 16
        assert [json.loads(line) for line in changed.artifact.genui.splitlines()] == expected
    unchanged = await asyncio.to_thread(SourceArtifactRepository().load, created.artifactUrl)
    assert unchanged.artifact.model_dump_json() == original


def _compact_source(content: str) -> str:
    rows = [
        ["root", "Column", {"width": "matchParent"}, ["value"]],
        ["value", "EmphasisText", {"mainText": content}],
    ]
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


class CompiledLayoutFixture:
    """固定前置编译结果，保留真实服务编排、布局产物校验与修复流程。"""

    def process(self, source_dsl, _context):
        row = json.loads(source_dsl.splitlines()[1])
        props = row[2]
        assert isinstance(props, dict)
        content = props.get("mainText")
        assert isinstance(content, str)
        standard = _standard_dsl(content)
        standard = standard.replace("#FFFFFFFF", "@theme:panel")
        standard = standard.replace("#FF000000", "@theme:primary")
        return DslProcessingResult(source_dsl=source_dsl, standard_dsl=standard)


@pytest.mark.parametrize("repair_content", [None, OLD_ROOT, OLD_REFERENCE])
@pytest.mark.asyncio
async def test_strict_compact_edit_blocks_or_repairs_with_structured_diagnostic(
    generation_probe, monkeypatch, isolated_theme_stage, repair_content,
):
    # 本测试隔离前置编译与最终填色，验证真实 Compact 入口的产物门禁及重试。
    monkeypatch.setattr(
        "services.widget_generation_service.get_dsl_processor",
        lambda _kind: CompiledLayoutFixture(),
    )
    settings = get_settings()
    repair = repair_content is not None
    monkeypatch.setattr(settings, "enable_validation_failure_retry", repair)
    monkeypatch.setattr(settings, "validation_failure_max_repair_attempts", 1)
    probe = generation_probe
    probe.outputs.extend([_compact_source(OLD_REFERENCE), _compact_source(OLD_REFERENCE)])
    if repair:
        probe.outputs.append(_compact_source(repair_content))
    service = WidgetGenerationService()
    created = await service.generate_widget_card_compact_dsl(_request())
    assert created.status == GenerationStatus.SUCCESS
    edited = await service.generate_widget_card_compact_dsl(
        _request(sourceArtifactUrl=created.artifactUrl, candidateDataBindings=[]),
    )
    assert not probe.outputs
    assert probe.plan_calls == 2
    assert len(probe.evaluations) == (3 if repair else 2)
    result = _evaluation_result(probe.evaluations[1])
    errors = result.get("errors")
    contexts = result.get("promptContexts")
    assert isinstance(errors, list)
    assert isinstance(contexts, list)
    assert len(errors) == len(contexts) == 1
    assert contexts[0].get("code") == PATH_CODE
    assert contexts[0].get("jsonPointer") == "/updateComponents/componentsById/value/content"
    failures = [item for item in probe.metrics if "validationScenarioFailure" in item]
    failure_count = 2 if repair_content == OLD_REFERENCE else 1
    assert failures == [{"validationScenarioFailure": 1}] * failure_count
    if repair_content == OLD_ROOT:
        assert edited.status == GenerationStatus.SUCCESS
        assert edited.artifactUrl != created.artifactUrl
        assert _evaluation_result(probe.evaluations[-1]).get("errors") == []
    else:
        assert edited.status == GenerationStatus.FAILED
        assert edited.errorCode == ErrorCode.VALIDATION_FAILED.value
        assert not edited.artifactUrl
    if repair:
        repair_message = probe.prompts[-1][-1].get("content")
        assert isinstance(repair_message, str)
        assert PATH_CODE in repair_message
        assert "/updateComponents/componentsById/value/content" in repair_message


@pytest.mark.asyncio
async def test_disabled_artifact_validation_keeps_existing_edit_skip(generation_probe, monkeypatch):
    probe = generation_probe
    probe.outputs.extend([_standard_dsl(OLD_REFERENCE), _standard_dsl(OLD_REFERENCE)])
    service = WidgetGenerationService()
    created = await service.generate_widget_card_a2ui_form(_request())
    assert created.status == GenerationStatus.SUCCESS
    monkeypatch.setattr(get_settings(), "enable_artifact_validation", False)
    edited = await service.generate_widget_card_a2ui_form(
        _request(sourceArtifactUrl=created.artifactUrl, candidateDataBindings=[]),
    )
    assert edited.status == GenerationStatus.SUCCESS
    assert len(probe.evaluations) == 1
    assert not probe.outputs
    failures = [item for item in probe.metrics if "validationScenarioFailure" in item]
    assert not failures
