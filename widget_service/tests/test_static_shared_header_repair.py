"""失败静态源仅补公共标题后，按候选同源容量继续原有修复，不自动授权省略。"""

import copy
import json
from dataclasses import replace
from types import SimpleNamespace

import httpx
import pytest

from api.schemas import GenerateWidgetCardRequest
from config.config import get_settings
from core.errors import GenerationStatus
from custom.a2ui_model_client import A2UIModelClient
from services.artifact_store import ArtifactStore
from services.card_validation.compact_validation.semantic.static_content import static_group_errors
from services.compact_repair_strategy import CompactRepairStrategyTracker
from services.generation_content_policy import (
    EXISTING_CONTENT_POLICY,
    STATIC_CONTENT_POLICY,
    content_policy_scope,
)
from services.generation_pipeline import (
    DesignCompactProcessor,
    DslProcessingContext,
    DslProcessingResult,
    QualityIssue,
)
from services.protocol_registry import A2UIProtocolRegistry
from services.static_content_presentation import missing_shared_header_candidate
from services.theme_style_roles import layout_phase
from services.widget_generation_service import WidgetGenerationService


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def reject(*_args, **_kwargs):
        raise AssertionError("公共标题交接测试不得访问网络")

    # 底层 socket 由离线运行器管控；不包装 Windows asyncio 的唤醒配对。
    monkeypatch.setattr(httpx.Client, "request", reject)
    monkeypatch.setattr(httpx.AsyncClient, "request", reject)


def encode(rows):
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def fixture_case():
    names = ("春季", "夏季", "冬季")
    details = ("每4至5天一次", "每2至3天一次，早晚向叶面喷雾", "每10至14天一次，水温接近室温")
    facts = []
    groups = []
    items = []
    for index, name in enumerate(names):
        detail = details[index]
        facts.append({"text": f"{name} {detail}", "priority": "must", "displayRole": "value"})
        groups.append({"id": f"season{index}", "kind": "object", "identity": name,
                       "factIndexes": [index]})
        items.append({"primaryText": name, "secondaryText": detail})
    facts.append({"text": "盆土表面下2厘米干透再浇，忌积水", "priority": "must",
                  "displayRole": "body"})
    groups.append({"id": "rule", "kind": "shared", "identity": None, "factIndexes": [3]})
    source = encode([
        ["root", "Layout", {"layout": "S-static-content"}, ["body"]],
        ["body", "TextList", {"items": items}],
        ["/state/ready", True],
    ])
    plan = {"info_required": facts, "contentGroups": groups, "presentationStyle": "records"}
    task = {"size": "2x2", "appVersion": "11.8.8.512", "romVersion": "7.0.0.105",
            "userQuery": "展示绿萝季节浇水频率与共同规则", "dataModelSchema": {"data": {}},
            "eventCandidates": [], "assetCandidates": []}
    profile = A2UIProtocolRegistry("a2ui-form-rom6.0-v1").get_profile()
    context = DslProcessingContext(
        size="2x2", card_spec={"suggestSize": "2x2"}, task_spec=task,
        protocol_profile=profile, design_profile_id="design-compact-dsl",
        layout_scope="S-static-content-guided", compact_plan=plan,
        content_policy=STATIC_CONTENT_POLICY, colorless_layout=True,
    )
    return source, plan, context


def test_real_same_body_source_and_capacity_reach_existing_drop_route():
    source, plan, context = fixture_case()
    processor = DesignCompactProcessor()
    result = processor.process(source, context)
    original_rows = [json.loads(line) for line in source.splitlines()]
    result_rows = [json.loads(line) for line in result.source_dsl.splitlines()]
    assert original_rows[1:] == result_rows[2:]
    shared_title = plan["info_required"][3]["text"]
    assert result_rows[1] == ["header", "SingleLineTitle", {"title": shared_title}]
    assert result.repair_source_dsl == result.source_dsl
    assert not result.standard_dsl
    assert len(result.errors) == 1
    assert "TextList 含标题区时最多两项" in result.errors[0].message
    with content_policy_scope(STATIC_CONTENT_POLICY):
        assert static_group_errors(result.source_dsl, plan) == []
        tracker = CompactRepairStrategyTracker(static_content=True, max_repair_attempts=5)
        issues = [issue.to_prompt_payload() for issue in result.errors]
        first = tracker.next_directive(
            result.source_dsl, issues, compact_plan=plan, task_spec=context.task_spec,
        ).to_prompt_payload()
        # 同候选再次失败的离线路由模拟，不代表真实模型已经执行过一次修复。
        second_result = processor.process(source, context)
        second = tracker.next_directive(
            second_result.source_dsl, issues, compact_plan=plan, task_spec=context.task_spec,
        ).to_prompt_payload()
    assert first.get("optionalDrop") is None
    assert first.get("repairStrategy") == "semantic_layout_contract_repair"
    assert second.get("repairStrategy") == "drop_optional_component"
    assert second.get("optionalDrop", {}).get("allowedOmittedFactIndexes") == [2]


@pytest.mark.parametrize("change", ["existing_header", "object_missing", "unregistered_node",
                                     "unknown_role", "binding", "action", "invalid_index"])
def test_unreliable_or_non_shared_changes_are_not_candidates(change):
    source, plan, _context = fixture_case()
    rows = [json.loads(line) for line in source.splitlines()]
    if change == "existing_header":
        rows[0][3] = ["header", "body"]
        rows.insert(1, ["header", "SingleLineTitle", {"title": "已有标题"}])
    elif change == "object_missing":
        rows[1][2]["items"].pop()
    elif change == "unregistered_node":
        rows.append(["extra", "EmphasisText", {"mainText": "额外正文"}])
    elif change == "unknown_role":
        plan["info_required"][3]["displayRole"] = "value"
    elif change == "binding":
        plan["info_required"][3]["text"] = "{{ ${/data/value} }}"
    elif change == "action":
        plan["info_required"][3]["actionId"] = "action.real"
    else:
        plan["contentGroups"][3]["factIndexes"] = [99]
    with content_policy_scope(STATIC_CONTENT_POLICY):
        assert missing_shared_header_candidate(encode(rows), plan, "2x2") is None


def test_already_approved_shared_omission_is_not_restored():
    source, plan, _context = fixture_case()
    with content_policy_scope(STATIC_CONTENT_POLICY):
        assert missing_shared_header_candidate(source, plan, "2x2", (3,)) is None


def test_original_success_is_identical_and_new_helper_is_not_called(monkeypatch):
    source, plan, context = fixture_case()
    context = replace(context, allowed_omitted_plan_fact_indexes=(3,))
    processor = DesignCompactProcessor()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("成功源不得进入新候选")

    monkeypatch.setattr(processor, "_repair_missing_shared_header", forbidden)
    with content_policy_scope(STATIC_CONTENT_POLICY), layout_phase(True, context.task_spec):
        original = processor._process(source, context)
    result = processor.process(source, context)
    assert result == original
    assert not result.errors
    assert result.repair_source_dsl is None


def test_preexisting_successful_candidate_keeps_priority(monkeypatch):
    source, plan, context = fixture_case()
    plan = copy.deepcopy(plan)
    plan["info_required"] = plan["info_required"][:2]
    plan["contentGroups"] = plan["contentGroups"][:2]
    rows = [json.loads(line) for line in source.splitlines()]
    rows[1][2]["items"] = rows[1][2]["items"][:2]
    rows[0][3] = ["header", "body"]
    rows.insert(1, ["header", "SingleLineTitle", {"title": "绿萝"}])
    frozen = encode(rows)
    plan["staticPresentation"] = frozen
    context = replace(context, compact_plan=plan)
    processor = DesignCompactProcessor()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("既有可成功候选应优先")

    monkeypatch.setattr(processor, "_repair_missing_shared_header", forbidden)
    result = processor.process(source, context)
    assert not result.errors
    assert [json.loads(line) for line in result.source_dsl.splitlines()] == rows
    assert result.repair_source_dsl is None


@pytest.mark.parametrize("message", ["未知转换异常", "COMPACT_STATIC_CORE_MISSING: 仍缺事实"])
def test_candidate_unknown_or_remaining_coverage_error_keeps_original(monkeypatch, message):
    source, _plan, context = fixture_case()
    processor = DesignCompactProcessor()
    original = DslProcessingResult(source, issues=(QualityIssue(
        "validation", "COMPACT_PLAN_COVERAGE_FAILED", "COMPACT_STATIC_CORE_MISSING: 公共说明",
    ),))

    def fail(candidate, _context):
        return DslProcessingResult(candidate, issues=(QualityIssue("validation", "FAIL", message),))

    monkeypatch.setattr(processor, "_process", fail)
    with content_policy_scope(STATIC_CONTENT_POLICY):
        assert processor._repair_missing_shared_header(original, context) is original


def test_other_original_error_is_not_replaced(monkeypatch):
    source, _plan, context = fixture_case()
    processor = DesignCompactProcessor()
    original = DslProcessingResult(source, issues=(QualityIssue(
        "validation", "FAIL", "其他原始协议错误",
    ),))

    def forbidden(*_args, **_kwargs):
        raise AssertionError("非原公共缺失路径不处理")

    monkeypatch.setattr(processor, "_process", forbidden)
    assert processor._repair_missing_shared_header(original, context) is original


def test_non_static_path_does_not_use_shared_header_helper(monkeypatch):
    source, _plan, context = fixture_case()
    processor = DesignCompactProcessor()
    original = DslProcessingResult(source, issues=(QualityIssue("validation", "FAIL", "错误"),))
    monkeypatch.setattr(processor, "_process", lambda *_args: original)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("动态路径不调用静态交接")

    monkeypatch.setattr(processor, "_repair_missing_shared_header", forbidden)
    context = replace(context, content_policy=EXISTING_CONTENT_POLICY)
    assert processor.process(source, context) is original


@pytest.mark.parametrize("mixed", ["unknown_tail", "diagnostic", "second_issue"])
def test_capacity_mixed_with_unknown_errors_is_never_handed_off(monkeypatch, mixed):
    source, plan, context = fixture_case()
    processor = DesignCompactProcessor()
    with content_policy_scope(STATIC_CONTENT_POLICY):
        candidate = missing_shared_header_candidate(source, plan, "2x2")
        assert candidate is not None
        native = processor._process(candidate, context)
    assert len(native.errors) == 1
    issue = native.errors[0]
    if mixed == "unknown_tail":
        changed = replace(issue, message=issue.message + "\n未知组件字段错误")
        altered = replace(native, issues=(changed,))
    elif mixed == "diagnostic":
        context_payload = {"compactDiagnostics": [
            {"code": "COMPACT_STATIC_TEXT_CAPACITY", "message": issue.message,
             "legacyMessage": issue.message},
            {"code": "COMPACT_COMPONENT_INVALID", "message": "其它错误",
             "legacyMessage": "其它错误"},
        ]}
        altered = replace(native, issues=(replace(issue, prompt_context=context_payload),))
    else:
        unknown = QualityIssue("validation", "FAIL", "未知错误")
        altered = replace(native, issues=(*native.issues, unknown))
    original = DslProcessingResult(source, issues=(QualityIssue(
        "validation", "COMPACT_PLAN_COVERAGE_FAILED", "COMPACT_STATIC_CORE_MISSING: 公共说明",
    ),))
    monkeypatch.setattr(processor, "_process", lambda *_args: altered)
    with content_policy_scope(STATIC_CONTENT_POLICY):
        result = processor._repair_missing_shared_header(original, context)
    assert result is original
    assert result.repair_source_dsl is None


@pytest.mark.parametrize("shared_text,expects_failure", [
    ("盆土表面下2厘米干透再浇，忌积水", True),
    ("共同提醒", False),
])
def test_header_width_is_native_capacity_and_success_has_no_repair_marker(
    shared_text, expects_failure,
):
    _source, _plan, context = fixture_case()
    source = encode([
        ["root", "Layout", {"layout": "S-static-content"}, ["body"]],
        ["body", "EmphasisText", {"mainText": "绿萝浇水"}],
        ["/state/ready", True],
    ])
    plan = {"info_required": [
        {"text": "绿萝浇水", "priority": "must", "displayRole": "value"},
        {"text": shared_text, "priority": "must", "displayRole": "body"},
    ], "contentGroups": [
        {"id": "plant", "kind": "object", "identity": None, "factIndexes": [0]},
        {"id": "shared", "kind": "shared", "identity": None, "factIndexes": [1]},
    ]}
    context = replace(context, compact_plan=plan)
    processor = DesignCompactProcessor()
    with content_policy_scope(STATIC_CONTENT_POLICY), layout_phase(True, context.task_spec):
        original = processor._process(source, context)
        assert original.errors
        result = processor._repair_missing_shared_header(original, context)
    assert result.source_dsl != original.source_dsl
    assert bool(result.errors) is expects_failure
    if expects_failure:
        assert result.repair_source_dsl == result.source_dsl
        assert "header.title 完整文字需要 2 行" in result.errors[0].message
    else:
        assert result.repair_source_dsl is None
        assert result.standard_dsl


@pytest.mark.asyncio
async def test_service_repairs_prepared_source_with_matching_capacity_and_keeps_raw_response(
    monkeypatch, isolated_theme_stage,
):
    source, plan, _context = fixture_case()
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    facts[3]["text"] = "忌积水"
    for fact in facts:
        fact_text = fact.get("text")
        assert isinstance(fact_text, str)
        fact.update({"requirement": fact_text, "sourceTexts": [fact_text]})
    plan["omittedContents"] = []
    plan["layoutHints"] = ["S-static-content"]
    query = "；".join(fact.get("text", "") for fact in facts)
    request = GenerateWidgetCardRequest(
        uid="shared-header-handoff", prdVer="11.8.8.512", device={"romVersion": "7.0"},
        userQuery=query, size="2x2", title="浇水频率", description="按季节展示浇水频率",
    )
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_static_content_generation_policy", True)
    monkeypatch.setattr(settings, "enable_a2ui_model_mock", False)
    monkeypatch.setattr(settings, "enable_validation_failure_retry", True)
    monkeypatch.setattr(settings, "validation_failure_max_repair_attempts", 5)
    monkeypatch.setattr(settings, "enable_model_failure_retry", False)
    monkeypatch.setattr(settings, "enable_artifact_validation", True)
    monkeypatch.setattr(settings, "enable_design_compact_runtime_prompt_context", False)
    model_calls = []
    repairs = []
    saved = []
    pending = iter([
        {"name": "submit_card_plan", "arguments": plan},
        {"decision": "keep", "sourceFidelity": "preserved", "findings": []},
    ])

    async def generate(_client, messages, profile=None, **_kwargs):
        kind = (profile or {}).get("format")
        model_calls.append(kind)
        if kind == "raw-json":
            return json.dumps(next(pending), ensure_ascii=False)
        return source

    async def generate_repair(_client, messages, _profile=None, **_kwargs):
        model_calls.append("repair")
        repairs.append(copy.deepcopy(messages))
        current = messages[-2].get("content")
        assert isinstance(current, str)
        payload = json.loads(messages[-1].get("content", ""))
        directive = payload.get("repairStrategy", {})
        if len(repairs) == 1:
            assert directive.get("optionalDrop") is None
            return current
        assert len(repairs) == 2
        assert directive.get("optionalDrop", {}).get("allowedOmittedFactIndexes") == [2]
        rows = [json.loads(line) for line in current.splitlines()]
        body = next(row for row in rows if row[0] == "body")
        items = body[2].get("items")
        assert isinstance(items, list)
        body[2]["items"] = items[:2]
        return encode(rows)

    def save(_store, artifact):
        saved.append(artifact)
        return SimpleNamespace(artifactUrl="https://artifact.test/handoff", artifactDigest="test")

    monkeypatch.setattr(A2UIModelClient, "generate", generate)
    monkeypatch.setattr(A2UIModelClient, "generate_repair", generate_repair)
    monkeypatch.setattr(ArtifactStore, "save", save)
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(request)
    assert response.status == GenerationStatus.DEGRADED
    assert model_calls == ["raw-json", "raw-json", "compact-dsl", "repair", "repair"]
    assert len(saved) == 1
    first = repairs[0]
    raw_responses = []
    for message in first:
        if message.get("role") == "assistant":
            raw_responses.append(message.get("content"))
    assert source in raw_responses
    prepared = first[-2].get("content")
    assert isinstance(prepared, str) and prepared != source
    prepared_rows = [json.loads(line) for line in prepared.splitlines()]
    original_rows = [json.loads(line) for line in source.splitlines()]
    assert prepared_rows[1] == ["header", "SingleLineTitle", {"title": "忌积水"}]
    assert prepared_rows[2:] == original_rows[1:]
    first_errors = json.loads(first[-1].get("content", "")).get("qualityErrors")
    serialized_errors = json.dumps(first_errors, ensure_ascii=False)
    assert "TextList 含标题区时最多两项" in serialized_errors
    assert "COMPACT_STATIC_CORE_MISSING" not in serialized_errors
    assert "忌积水" in saved[0].genui
    assert "冬季" not in saved[0].genui
    assert any("冬季" in text for text in response.omittedRequirements)
