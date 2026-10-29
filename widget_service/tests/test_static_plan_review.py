"""静态 Plan 在既有两次预算内复核，身份确认和错误回退均可审计。"""

import copy
import json
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator, ValidationError

from api.schemas import GenerateWidgetCardRequest
from config.config import get_settings
from core.errors import GenerationStatus
from custom.a2ui_model_client import A2UIModelClient, A2UIModelGenerationError
from models.generation import CompactDslRecoveryFact, CompactDslRetryContext, TaskSpec
from services.artifact_store import ArtifactStore
from services.compact_plan import (
    CompactPlanValidationError,
    parse_compact_plan_call,
    static_fact_source,
)
from services.generation_content_policy import (
    EXISTING_CONTENT_POLICY,
    STATIC_CONTENT_POLICY,
    content_policy_scope,
)
from services.prompt_builder import PromptBuilder
from services.static_plan_review import StaticPlanReviewError, parse_static_plan_review
from services.widget_generation_service import WidgetGenerationService


@pytest.fixture(autouse=True)
def isolated_models(monkeypatch, isolated_theme_stage):
    """模型、主题与保存均由本文件假实现；外网隔离由统一测试入口提供。"""
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_static_content_generation_policy", True)
    monkeypatch.setattr(settings, "enable_a2ui_model_mock", False)
    monkeypatch.setattr(settings, "enable_artifact_validation", True)
    monkeypatch.setattr(settings, "enable_validation_failure_retry", False)
    monkeypatch.setattr(settings, "enable_model_failure_retry", False)
    monkeypatch.setattr(settings, "enable_design_compact_runtime_prompt_context", False)


def _plan(text="带证件", source=None):
    return {
        "info_required": [{
            "text": text, "requirement": source or text, "sourceTexts": [source or text],
            "priority": "must", "componentHints": ["EmphasisText"],
            "protectedTexts": [], "preserveVerbatim": False, "displayRole": "body",
        }],
        "contentGroups": [{
            "id": "one", "kind": "object", "identity": None, "factIndexes": [0],
        }],
        "layoutHints": ["S-static-content"], "omittedContents": [],
    }


def _call(plan):
    return {"name": "submit_card_plan", "arguments": plan}


def _keep():
    return {"decision": "keep", "sourceFidelity": "preserved", "findings": []}


def _correct(plan, findings=None):
    return {
        "decision": "correct",
        "sourceFidelity": "needs_correction" if findings else "preserved",
        "findings": findings or [], "correctedPlan": _call(plan),
    }


def _finding(source="带证件", indexes=None):
    return {"sourceText": source, "factIndexes": [0] if indexes is None else indexes,
            "issue": "最终展示遗漏原文的必要限定"}


def _parse(payload, source="带证件"):
    return parse_static_plan_review(json.dumps(payload), source=source, fact_count=1)


def _request(query="制作静态卡片：带证件", size="2x2"):
    return GenerateWidgetCardRequest(
        uid="static-review", prdVer="11.7.7.331", device={"romVersion": "7.0"},
        userQuery=query, size=size, title="复核", description="静态复核专项",
    )


def _dsl(text):
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in [
        ["root", "Layout", {"layout": "S-static-content"}, ["body"]],
        ["body", "EmphasisText", {"mainText": text}], ["/state/ready", True],
    ])


def _accepted_plan(messages):
    for message in messages:
        try:
            payload = json.loads(message.get("content", ""))
        except ValueError:
            continue
        if isinstance(payload, dict):
            accepted = payload.get("toolResult", {}).get("acceptedPlan")
            if accepted is not None:
                return accepted
    raise AssertionError("DSL 阶段没有收到接受的 Plan")


def _service(monkeypatch, outputs, display="带证件", dsl_source=None):
    calls = []
    saved = []
    pending = iter(outputs)

    async def generate(_client, messages, profile=None, **kwargs):
        calls.append({"format": (profile or {}).get("format"), "messages": copy.deepcopy(messages),
                      "phase": kwargs.get("phase")})
        if (profile or {}).get("format") != "raw-json":
            return _dsl(display) if dsl_source is None else dsl_source
        value = next(pending)
        if isinstance(value, Exception):
            raise value
        return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)

    def save(_store, artifact):
        saved.append(artifact)
        return SimpleNamespace(artifactUrl="https://artifact.test/review", artifactDigest="test")

    monkeypatch.setattr(A2UIModelClient, "generate", generate)
    monkeypatch.setattr(ArtifactStore, "save", save)
    return WidgetGenerationService(), calls, saved


def test_keep_has_no_rewritten_plan():
    result = _parse(_keep())
    assert result.decision == "keep"
    assert result.corrected_source is None


def test_correct_preserves_original_plan_envelope_for_existing_validator():
    plan = _plan()
    result = _parse(_correct(plan, [_finding()]))
    assert json.loads(result.corrected_source or "null") == _call(plan)


def test_string_corrected_plan_is_still_rejected_without_implicit_decoding():
    payload = _correct(_plan())
    payload["correctedPlan"] = json.dumps(_call(_plan()), ensure_ascii=False)
    with pytest.raises(StaticPlanReviewError, match="完整 correctedPlan 对象"):
        _parse(payload)


@pytest.mark.parametrize("indexes", [[], [0]])
def test_source_evidence_allows_completely_missing_fact(indexes):
    result = _parse(_correct(_plan(), [_finding(indexes=indexes)]))
    assert result.findings[0].get("factIndexes") == indexes


@pytest.mark.parametrize("change", [
    {"decision": "unknown"}, {"decision": True}, {"sourceFidelity": "unknown"},
    {"findings": None}, {"findings": {}}, {"extra": True},
    {"correctedPlan": _call(_plan())}, {"sourceFidelity": "needs_correction"},
    {"findings": [_finding()]},
])
def test_invalid_keep_is_never_treated_as_confirmation(change):
    with pytest.raises(StaticPlanReviewError):
        _parse({**_keep(), **change})


@pytest.mark.parametrize("finding", [
    {**_finding(), "sourceText": "编造原文"},
    {**_finding(), "sourceText": ""}, {**_finding(), "issue": ""},
    {**_finding(), "factIndexes": [True]}, {**_finding(), "factIndexes": [-1]},
    {**_finding(), "factIndexes": [1]}, {**_finding(), "factIndexes": [0, 0]},
    {**_finding(), "extra": True}, None,
])
def test_invalid_evidence_is_rejected(finding):
    with pytest.raises(StaticPlanReviewError):
        _parse(_correct(_plan(), [finding]))


@pytest.mark.parametrize("raw", [
    '[]', 'null', '{}', '```json\n{}\n```',
    '{"decision":"keep","decision":"correct","sourceFidelity":"preserved","findings":[]}',
    '{"decision":"keep","sourceFidelity":"preserved","findings":[]}{}',
])
def test_invalid_transport_is_rejected(raw):
    with pytest.raises(StaticPlanReviewError):
        parse_static_plan_review(raw, source="带证件", fact_count=1)


@pytest.mark.parametrize("payload", [_keep(), _correct(_plan(), [_finding()])])
def test_only_missing_outer_review_brace_is_restored_without_changing_values(payload):
    complete = json.dumps(payload, ensure_ascii=False)
    result = parse_static_plan_review(complete[:-1], source="带证件", fact_count=1)
    expected = parse_static_plan_review(complete, source="带证件", fact_count=1)
    assert result.decision == expected.decision
    assert result.source_fidelity == expected.source_fidelity
    assert result.findings == expected.findings
    assert result.corrected_source == expected.corrected_source
    assert len(result.warnings) == 1
    assert expected.warnings == ()


@pytest.mark.parametrize("raw", [
    '{"decision":"keep","sourceFidelity":"preserved","findings":[',
    '{"decision":"keep","sourceFidelity":"preserved","findings":',
    '{"decision":"keep","sourceFidelity":"preserved","findings":[],',
    '{"decision":"keep","decision":"correct","sourceFidelity":"preserved","findings":[]',
    '{"decision":"correct","sourceFidelity":"needs_correction","findings":[]',
    '{"decision":"correct","sourceFidelity":"preserved","findings":[]',
    '{"decision":"keep","sourceFidelity":"preserved","findings":[]}{}',
])
def test_review_closure_recovery_never_invents_content_or_bypasses_contract(raw):
    with pytest.raises(StaticPlanReviewError):
        parse_static_plan_review(raw, source="带证件", fact_count=1)


def test_explicit_fact_source_does_not_admit_user_expectation_as_evidence():
    query = "想去北京；本轮卡片静态内容（用作展示的外部事实）：上海体育场"
    source, explicit = static_fact_source(query)
    assert explicit and source == "上海体育场"
    with pytest.raises(StaticPlanReviewError, match="有效事实源"):
        _parse(_correct(_plan(), [_finding("想去北京")]), source)


def test_prompt_reviews_visible_group_with_original_source_without_dsl_blueprint():
    query = "甲活动在上海体育场"
    plan = _plan("甲活动", query)
    plan["staticPresentation"] = "forbidden-dsl-blueprint"
    plan["staticPresentationFeedback"] = ["需要调整容量"]
    messages = [{"role": "system", "content": "原合同"}, {"role": "user", "content": query}]
    original = copy.deepcopy(messages)
    original_submission = json.dumps(_call(_plan("甲活动", query)), ensure_ascii=False)
    reviewed = PromptBuilder.build_static_plan_review(
        messages, plan, query, original_submission=original_submission,
    )
    payload = json.loads(reviewed[-1].get("content", ""))
    data = payload.get("staticPlanReview", {})
    assert data.get("originalFactSource") == query
    assert data.get("capacityReference") == ["需要调整容量"]
    assert data.get("originalSubmission") == original_submission
    assert "forbidden-dsl-blueprint" not in json.dumps(reviewed)
    assert "requirement/sourceTexts/selectionNotes" in payload.get("instruction", "")
    assert messages == original


def _review_payload(plan, query):
    messages = [{"role": "system", "content": "原合同"}]
    reviewed = PromptBuilder.build_static_plan_review(
        messages, plan, query, original_submission=json.dumps(_call(plan), ensure_ascii=False),
    )
    return json.loads(reviewed[-1].get("content", ""))


def test_review_output_is_a_typed_schema_not_string_placeholder_examples():
    payload = _review_payload(_plan(), "带证件")
    schema = payload.get("reviewOutput")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    validator.validate(_keep())
    validator.validate(_correct(_plan(), [_finding()]))
    string_plan = _correct(_plan())
    string_plan["correctedPlan"] = json.dumps(_call(_plan()))
    with pytest.raises(ValidationError):
        validator.validate(string_plan)
    string_indexes = _correct(_plan(), [{**_finding(), "factIndexes": "[0]"}])
    with pytest.raises(ValidationError):
        validator.validate(string_indexes)


def test_review_allows_shared_units_and_visible_identity_without_new_plan_gate():
    source = "甲套餐价格分380元、680元两档"
    plan = _plan("380/680元", source)
    groups = plan.get("contentGroups")
    assert isinstance(groups, list) and groups
    groups[0]["identity"] = "甲套餐"
    with content_policy_scope(STATIC_CONTENT_POLICY):
        parsed = parse_compact_plan_call(json.dumps(_call(plan)), {
            "userQuery": source, "size": "2x2",
        }).plan
    assert parsed.get("info_required", [])[0].get("text") == "380/680元"
    assert parsed.get("contentGroups", [])[0].get("identity") == "甲套餐"
    instruction = _review_payload(parsed, source).get("instruction", "")
    assert "identity标签、同组text及确实共同适用的shared内容可共同表达" in instruction
    assert "跨不同对象不能借值" in instruction
    assert "没有逐项重复单位、年份或原文数量用语" in instruction
    assert "必要场景或限定改成更宽泛的结论" in instruction
    assert "排版偏好、措辞美化、重复标注不构成语义纠错" in instruction


@pytest.mark.asyncio
async def test_keep_uses_two_plan_calls_then_existing_dsl_and_exact_candidate(monkeypatch):
    plan = _plan()
    with content_policy_scope(STATIC_CONTENT_POLICY):
        accepted = parse_compact_plan_call(json.dumps(_call(plan)), {
            "userQuery": "制作静态卡片：带证件", "size": "2x2",
        }).plan
    service, calls, saved = _service(monkeypatch, [_call(plan), _keep()])
    response = await service.generate_widget_card_compact_dsl(_request())
    assert response.status == GenerationStatus.SUCCESS
    assert len(saved) == 1
    assert [call.get("phase") for call in calls] == ["plan", "plan", None]
    assert [call.get("format") for call in calls] == ["raw-json", "raw-json", "compact-dsl"]
    final_prompt = json.dumps(calls[-1].get("messages"), ensure_ascii=False)
    assert "staticPlanReview" not in final_prompt
    assert "reviewOutput" not in final_prompt
    assert calls[-1].get("messages", [])[0] == calls[0].get("messages", [])[0]
    assert accepted.get("staticPresentation")
    assert _accepted_plan(calls[-1].get("messages", [])) == accepted
    assert saved[0].genui


@pytest.mark.asyncio
async def test_q19_style_omission_is_corrected_before_dsl(monkeypatch):
    source = "甲活动在上海体育场"
    fixed = "甲活动 上海体育场"
    original = _plan("甲活动", source)
    corrected = _plan(fixed, source)
    service, calls, saved = _service(monkeypatch, [
        _call(original), _correct(corrected, [_finding(source)]),
    ], display=fixed)
    response = await service.generate_widget_card_compact_dsl(_request(source))
    assert response.status == GenerationStatus.SUCCESS
    assert len(calls) == 3 and len(saved) == 1
    components = []
    for line in saved[0].genui.splitlines():
        components.extend(json.loads(line).get("updateComponents", {}).get("components", []))
    texts = []
    for node in components:
        if node.get("component") == "Text":
            texts.append(node.get("content", ""))
    assert "上海体育场" in "".join("".join(texts).split())
    final_prompt = json.dumps(calls[-1].get("messages"), ensure_ascii=False)
    assert "staticPlanReview" not in final_prompt and "reviewOutput" not in final_prompt
    assert calls[-1].get("messages", [])[0] == calls[0].get("messages", [])[0]
    accepted = _accepted_plan(calls[-1].get("messages", []))
    assert accepted.get("info_required", [])[0].get("text") == fixed


@pytest.mark.asyncio
@pytest.mark.parametrize("review", [
    {"decision": "unknown"}, "not-json", TimeoutError("offline timeout"),
])
async def test_invalid_review_or_timeout_never_saves_original(monkeypatch, review):
    service, calls, saved = _service(monkeypatch, [_call(_plan()), review])
    try:
        response = await service.generate_widget_card_compact_dsl(_request())
    except (A2UIModelGenerationError, TimeoutError):
        response = None
    assert response is None or response.status != GenerationStatus.SUCCESS
    assert len(calls) == 2
    assert not saved


@pytest.mark.asyncio
@pytest.mark.parametrize("semantic_issue", [False, True])
async def test_only_semantically_confirmed_original_can_survive_bad_optimization(
    monkeypatch, semantic_issue,
):
    findings = [_finding()] if semantic_issue else []
    service, calls, saved = _service(monkeypatch, [
        _call(_plan()), _correct({"info_required": []}, findings),
    ])
    response = await service.generate_widget_card_compact_dsl(_request())
    if semantic_issue:
        assert response.status != GenerationStatus.SUCCESS
        assert len(calls) == 2 and not saved
    else:
        assert response.status == GenerationStatus.SUCCESS
        assert len(calls) == 3 and len(saved) == 1


@pytest.mark.asyncio
async def test_confirmed_original_survives_optimization_without_feasible_candidate(monkeypatch):
    source = "完整说明" * 70
    original = _plan("完整说明", source)
    corrected = _plan(source, source)
    with content_policy_scope(STATIC_CONTENT_POLICY):
        parsed = parse_compact_plan_call(json.dumps(_call(corrected)), {
            "userQuery": source, "size": "2x2",
        }).plan
    assert not parsed.get("staticPresentation")
    service, calls, saved = _service(monkeypatch, [
        _call(original), _correct(corrected),
    ], display="完整说明")
    response = await service.generate_widget_card_compact_dsl(_request(source))
    assert response.status == GenerationStatus.SUCCESS
    assert len(calls) == 3 and len(saved) == 1
    accepted = _accepted_plan(calls[-1].get("messages", []))
    assert accepted.get("info_required", [])[0].get("text") == "完整说明"


def _no_candidate_case():
    title = "流程安排"
    facts = [{"requirement": title, "text": title, "sourceTexts": [title],
              "priority": "must", "displayRole": "title",
              "componentHints": ["SingleLineTitle"]}]
    groups = [{"id": "title", "kind": "shared", "identity": None, "factIndexes": [0]}]
    items = []
    for index in range(1, 6):
        identity = f"阶段{index}"
        detail = "核对原始记录后逐项登记处理结果并保留完整资料" * 3
        text = f"{identity} {detail}"
        facts.append({"requirement": text, "text": text, "sourceTexts": [text],
                      "priority": "must", "displayRole": "body",
                      "componentHints": ["SingleLineList"]})
        groups.append({"id": f"step{index}", "kind": "object", "identity": identity,
                       "factIndexes": [index]})
        items.append({"text": identity, "assist": detail})
    plan = {"info_required": facts, "contentGroups": groups,
            "layoutHints": ["W-static-content"], "presentationStyle": "rows",
            "omittedContents": []}
    query = "；".join(fact.get("text", "") for fact in facts)
    dsl = "\n".join(json.dumps(row, ensure_ascii=False) for row in [
        ["root", "Layout", {"layout": "W-static-content"}, ["header", "body"]],
        ["header", "SingleLineTitle", {"title": title}],
        ["body", "SingleLineList", {"items": items}], ["/state/ready", True],
    ])
    return plan, query, dsl


def _parse_no_candidate(plan, query):
    with content_policy_scope(STATIC_CONTENT_POLICY):
        accepted = parse_compact_plan_call(json.dumps(_call(plan)), {
            "userQuery": query, "size": "2x4", "dataModelSchema": {"data": {}},
            "assetCandidates": [], "eventCandidates": [],
        }).plan
    assert not accepted.get("staticPresentation")
    assert accepted.get("staticPresentationFeedback")
    return accepted


@pytest.mark.asyncio
@pytest.mark.parametrize("violation", ["record_count", "note_length"])
async def test_confirmed_no_candidate_plan_reaches_dsl_after_invalid_optimization(
    monkeypatch, violation,
):
    original, query, dsl = _no_candidate_case()
    accepted = _parse_no_candidate(original, query)
    corrected = copy.deepcopy(original)
    if violation == "record_count":
        corrected["presentationStyle"] = "records"
        expected_error = "TextList"
    else:
        corrected["selectionNotes"] = ["说明" * 101]
        expected_error = "取舍说明最多200字符"
    with pytest.raises(CompactPlanValidationError, match=expected_error):
        _parse_no_candidate(corrected, query)
    trace_events = []

    def record(event, **kwargs):
        trace_events.append((event, kwargs))

    monkeypatch.setattr("services.widget_generation_service.trace_record", record)
    service, calls, saved = _service(monkeypatch, [
        _call(original), _correct(corrected),
    ], dsl_source=dsl)
    response = await service.generate_widget_card_compact_dsl(_request(query, "2x4"))
    assert [call.get("format") for call in calls] == ["raw-json", "raw-json", "compact-dsl"]
    assert _accepted_plan(calls[-1].get("messages", [])) == accepted
    assert response.status != GenerationStatus.SUCCESS
    assert response.errorCode == "VALIDATION_FAILED"
    assert not saved
    fallback = [payload for name, payload in trace_events
                if name == "static_content.plan.review.fallback"]
    assert len(fallback) == 1
    details = fallback[0].get("details", {})
    assert details.get("hasFeasibleCandidate") is False
    assert "不代表容量已通过" in details.get("reason", "")


@pytest.mark.asyncio
async def test_two_structurally_valid_plans_without_candidate_keep_the_new_plan(monkeypatch):
    original, query, dsl = _no_candidate_case()
    _parse_no_candidate(original, query)
    corrected = copy.deepcopy(original)
    corrected["selectionNotes"] = ["继续按原完整内容尝试排版"]
    accepted = _parse_no_candidate(corrected, query)
    service, calls, saved = _service(monkeypatch, [
        _call(original), _correct(corrected),
    ], dsl_source=dsl)
    response = await service.generate_widget_card_compact_dsl(_request(query, "2x4"))
    assert len(calls) == 3
    assert _accepted_plan(calls[-1].get("messages", [])) == accepted
    assert response.status != GenerationStatus.SUCCESS and not saved


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["needs_correction", "invalid_review", "timeout"])
async def test_no_candidate_does_not_bypass_semantic_or_review_failures(monkeypatch, failure):
    original, query, dsl = _no_candidate_case()
    _parse_no_candidate(original, query)
    if failure == "needs_correction":
        review = _correct({"info_required": []}, [_finding("流程安排", [0])])
    elif failure == "invalid_review":
        review = {"decision": "correct", "sourceFidelity": "preserved", "findings": []}
    else:
        review = TimeoutError("offline timeout")
    service, calls, saved = _service(monkeypatch, [_call(original), review], dsl_source=dsl)
    try:
        response = await service.generate_widget_card_compact_dsl(_request(query, "2x4"))
    except (A2UIModelGenerationError, TimeoutError):
        response = None
    assert response is None or response.status != GenerationStatus.SUCCESS
    assert len(calls) == 2 and not saved


@pytest.mark.asyncio
async def test_existing_capacity_refinement_and_source_review_share_second_call(monkeypatch):
    source = "完整说明" * 70
    original = _plan(source, source)
    corrected = _plan("完整说明", source)
    service, calls, saved = _service(monkeypatch, [
        _call(original), _correct(corrected),
    ], display="完整说明")
    response = await service.generate_widget_card_compact_dsl(_request(source))
    assert response.status == GenerationStatus.SUCCESS
    assert len(calls) == 3 and len(saved) == 1
    messages = calls[1].get("messages", [])
    review = json.loads(messages[-1].get("content", ""))
    assert review.get("staticPlanReview", {}).get("capacityReference")
    assert "reviewOutput" not in json.dumps(calls[-1].get("messages"))


@pytest.mark.asyncio
async def test_first_contract_error_uses_second_contract_repair_without_third_call(monkeypatch):
    service, calls, saved = _service(monkeypatch, [_call({}), _call(_plan())])
    response = await service.generate_widget_card_compact_dsl(_request())
    assert response.status == GenerationStatus.SUCCESS
    assert len(calls) == 3 and len(saved) == 1
    repair_prompt = json.dumps(calls[1].get("messages"), ensure_ascii=False)
    assert "同一对象组的最终text与identity" in repair_prompt
    assert "原始需求的主体、年份和作用范围即使放在header也不是装饰" in repair_prompt
    assert "来源引用错误先核对并修正引用" in repair_prompt
    assert "staticPlanReview" not in repair_prompt


@pytest.mark.asyncio
async def test_capacity_recovery_does_not_review_or_rewrite_frozen_facts(monkeypatch):
    request = _request()
    request._compact_dsl_retry_context = CompactDslRetryContext(
        failure_category="layout_capacity", capacity_recovery=True,
        retained_facts=(CompactDslRecoveryFact("text", "带证件", "带证件", "must"),),
        omitted_facts=(CompactDslRecoveryFact("text", "带雨伞", "带雨伞", "must"),),
    )
    service, calls, saved = _service(monkeypatch, [_call(_plan())])
    response = await service.generate_widget_card_compact_dsl(request)
    assert response.status == GenerationStatus.SUCCESS
    assert len(saved) == 1 and len(calls) == 2
    assert [call.get("format") for call in calls] == ["raw-json", "compact-dsl"]
    messages = json.dumps(calls[0].get("messages"), ensure_ascii=False)
    assert "recovery_fact_scope" in messages
    assert "staticPlanReview" not in messages


def test_normal_plan_and_frozen_recovery_keep_their_original_output_contract():
    task = TaskSpec(userQuery="带证件", size="2x2", dataModelSchema={"data": {}})
    retry = CompactDslRetryContext(
        failure_category="layout_capacity", capacity_recovery=True,
        retained_facts=(CompactDslRecoveryFact("text", "带证件", "带证件", "must"),),
    )
    for policy in (STATIC_CONTENT_POLICY, EXISTING_CONTENT_POLICY):
        with content_policy_scope(policy):
            original = PromptBuilder().build_compact_plan(task, "合同", "需求")
            recovery = PromptBuilder().build_compact_plan(
                task, "合同", "需求", retry_context=retry,
            )
        assert "staticPlanReview" not in json.dumps(original)
        assert "staticPlanReview" not in json.dumps(recovery)
        assert "reviewOutput" not in json.dumps(recovery)
