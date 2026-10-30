"""开域静态增量合同、来源分组、容量与请求隔离回归。"""

import asyncio
import copy
import json
import re
import shutil
from pathlib import Path

import pytest

from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.card_validation.compact_validation.semantic.static_content import static_group_errors
from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    convert_compact_dsl_to_a2ui,
)
from services.compact_layout_runtime import allowed_layout_ids
from services.compact_plan import CompactPlanValidationError, parse_compact_plan_call
from services.generation_content_policy import (
    EXISTING_CONTENT_POLICY,
    STATIC_CONTENT_POLICY,
    content_policy_scope,
    current_content_policy,
    effective_layout_scope,
    isolated_content_request,
    resolve_content_policy,
)
from services.static_content_context import final_static_display_errors
from services.static_text_capacity import measure_text, text_spec

SOURCE_ROOT = (
    Path(__file__).resolve().parents[1]
    / "cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/static_content"
)


def source(body: str, props: dict, size: str = "2x2", extra: list | None = None) -> str:
    prefix = "S" if size == "2x2" else "W"
    rows = [
        ["root", "Layout", {"layout": f"{prefix}-static-content"}, ["body"]],
        ["body", body, props],
        ["/state/ready", True],
    ]
    rows.extend(extra or [])
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def task(query: str = "制作备忘卡：带证件", size: str = "2x2") -> dict:
    return {
        "userQuery": query,
        "size": size,
        "dataModelSchema": {"data": {}},
        "eventCandidates": [],
        "assetCandidates": [],
    }


def fact(text: str, **extras) -> dict:
    result = {
        "requirement": text,
        "text": text,
        "sourceTexts": [text],
        "priority": "must",
        "componentHints": ["EmphasisText"],
    }
    result.update(extras)
    return result


def plan(facts: list[dict], groups: list[dict] | None = None) -> dict:
    if groups is None:
        groups = [{"id": "object1", "kind": "object", "factIndexes": list(range(len(facts)))}]
    return {"info_required": facts, "contentGroups": groups, "layoutHints": ["S-static-content"]}



def model_plan(value: dict) -> dict:
    result = copy.deepcopy(value)
    for group in result.get("contentGroups", []):
        group.setdefault("identity", None)
    declarations = []
    for entry in result.get("omittedContents", []):
        if isinstance(entry, str):
            entry = {"description": entry, "factIndexes": []}
        declarations.append(entry)
    result["omittedContents"] = declarations
    return result


def accept(value: dict, query: str, size: str = "2x2") -> dict:
    raw = json.dumps({"name": "submit_card_plan", "arguments": value}, ensure_ascii=False)
    return parse_compact_plan_call(raw, task(query, size)).plan


def capacity_issue(dsl: str, size: str = "2x2") -> dict:
    with pytest.raises(CompactDslConversionError) as caught:
        convert_compact_dsl_to_a2ui(dsl, size=size)
    return {
        "stage": "conversion", "code": "COMPACT_DSL_CONVERSION_FAILED",
        "message": str(caught.value),
    }


def review_response(messages) -> str | None:
    try:
        payload = json.loads(messages[-1].get("content", ""))
    except (ValueError, TypeError):
        return None
    if isinstance(payload, dict) and "staticPlanReview" in payload:
        return json.dumps({"decision": "keep", "sourceFidelity": "preserved", "findings": []})
    return None


@pytest.fixture
def static_policy():
    with content_policy_scope(STATIC_CONTENT_POLICY):
        yield


@pytest.mark.parametrize(
    "change",
    [
        {"enabled": False},
        {"is_edit": True},
        {"requested_data": True},
        {"effective_data": True},
        {"requested_events": True},
        {"effective_events": True},
        {"single_step": True},
        {"operation": "generateWidgetCard"},
    ],
)
def test_policy_only_enables_eligible_create(change: dict) -> None:
    arguments = {
        "operation": "generateWidgetCardCompactDsl",
        "enabled": True,
        "is_edit": False,
        "requested_data": False,
        "effective_data": False,
        "requested_events": False,
        "effective_events": False,
    }
    assert resolve_content_policy(**arguments).is_static
    arguments.update(change)
    assert resolve_content_policy(**arguments) == EXISTING_CONTENT_POLICY


@pytest.mark.asyncio
async def test_concurrent_request_policies_reset_on_success_and_failure() -> None:
    @isolated_content_request
    async def run(policy, fail):
        assert not current_content_policy().is_static
        with content_policy_scope(policy):
            await asyncio.sleep(0)
            assert current_content_policy() == policy
            if fail:
                raise ValueError("测试异常")
        return current_content_policy()

    results = await asyncio.gather(
        run(STATIC_CONTENT_POLICY, True),
        run(EXISTING_CONTENT_POLICY, False),
        return_exceptions=True,
    )
    assert isinstance(results[0], ValueError)
    assert results[1] == EXISTING_CONTENT_POLICY
    assert current_content_policy() == EXISTING_CONTENT_POLICY


def test_default_registry_and_parser_do_not_admit_static_contract() -> None:
    assert "S-static-content" not in allowed_layout_ids("2x2", "S-plan-guided")
    with pytest.raises(CompactDslConversionError):
        convert_compact_dsl_to_a2ui(source("EmphasisText", {"mainText": "带证件"}), size="2x2")


@pytest.mark.usefixtures("static_policy")
def test_static_scope_does_not_extend_existing_scope() -> None:
    assert "S-static-content" in allowed_layout_ids("2x2", effective_layout_scope("2x2"))
    assert "S-static-content" not in allowed_layout_ids("2x2", "S-plan-guided")


@pytest.mark.usefixtures("static_policy")
def test_source_extract_and_duplicate_index_remap_preserve_different_objects() -> None:
    value = plan(
        [fact("免费"), fact("免费"), fact("免费")],
        [
            {"id": "first", "kind": "object", "factIndexes": [0, 1]},
            {"id": "second", "kind": "object", "factIndexes": [2]},
        ],
    )
    accepted = accept(value, "公园免费；展馆免费")
    facts = accepted.get("info_required")
    groups = accepted.get("contentGroups")
    assert isinstance(facts, list) and len(facts) == 2
    assert groups == [
        {"id": "first", "kind": "object", "factIndexes": [0]},
        {"id": "second", "kind": "object", "factIndexes": [1]},
    ]


@pytest.mark.usefixtures("static_policy")
@pytest.mark.parametrize(
    "value",
    [
        fact("预计周六", protectedTexts=["预计"], sourceTexts=["不存在的句子"]),
        fact("周六", preserveVerbatim=True, sourceTexts=["预计周六"]),
        fact("周六", protectedTexts=["预计"], sourceTexts=["预计周六"]),
    ],
)
def test_reject_invalid_source_or_explicit_verbatim_violation(value: dict) -> None:
    with pytest.raises(CompactPlanValidationError):
        accept(plan([value]), "尚未开放，每月128元，预计周六")


@pytest.mark.usefixtures("static_policy")
def test_extract_preserves_numbers_units_and_qualifiers() -> None:
    value = fact(
        "预计周六19:30", sourceTexts=["活动预计周六19:30开始"], protectedTexts=["预计", "19:30"]
    )
    accepted = accept(plan([value]), "活动预计周六19:30开始")
    assert accepted.get("info_required") == [value]


@pytest.mark.usefixtures("static_policy")
def test_missing_source_texts_is_warning_for_unprotected_static_text() -> None:
    value = plan([fact("通勤助手")])
    facts = value.get("info_required")
    assert isinstance(facts, list)
    facts[0].pop("sourceTexts")
    raw = json.dumps({"name": "submit_card_plan", "arguments": value}, ensure_ascii=False)

    result = parse_compact_plan_call(raw, task("创建一张通勤助手小卡片"))

    assert result.plan.get("info_required", [])[0].get("text") == "通勤助手"
    assert any("缺少 sourceTexts" in warning for warning in result.warnings)


@pytest.mark.usefixtures("static_policy")
def test_explicit_static_fact_section_rejects_requested_device_status_as_source() -> None:
    query = (
        "展示今天是否下雨、耳机是否连接和耳机仓电量，点击打开歌单。\n\n"
        "本轮卡片静态内容（用作展示的外部事实）：\n"
        "上海天气：多云，29°C。"
    )
    weather = fact(
        "上海多云，29°C", sourceTexts=["上海天气：多云，29°C。"],
        componentHints=["EmphasisText"],
    )
    accepted = accept(plan([weather]), query)

    assert accepted.get("info_required") == [weather]

    unsupported_status = fact("耳机已连接", sourceTexts=["耳机是否连接"])
    with pytest.raises(CompactPlanValidationError, match="来源引用不在本轮有效输入中"):
        accept(plan([weather, unsupported_status]), query)

    missing_source = fact("耳机仓电量充足")
    missing_source.pop("sourceTexts")
    with pytest.raises(CompactPlanValidationError, match="必须引用该段中的非空 sourceTexts"):
        accept(plan([weather, missing_source]), query)

    unregistered_action = {
        "requirement": "打开歌单",
        "priority": "must",
        "actionId": "event.openPlaylist",
        "componentHints": [],
    }
    with pytest.raises(CompactPlanValidationError, match="actionId is not present in TaskSpec"):
        accept(plan([weather, unregistered_action]), query)


@pytest.mark.usefixtures("static_policy")
def test_registered_action_group_cannot_enter_static_only_plan() -> None:
    value = plan(
        [
            fact("通勤助手"),
            {
                "requirement": "一键导航到公司",
                "priority": "must",
                "componentHints": [],
                "actionId": "event.startNavigate",
            },
        ],
        [
            {"id": "title", "kind": "shared", "factIndexes": [0]},
            {"id": "action", "kind": "object", "factIndexes": [1]},
        ],
    )
    current_task = task("创建一张通勤助手小卡片，支持一键导航到公司")
    current_task["eventCandidates"] = [{"id": "event.startNavigate"}]
    raw = json.dumps({"name": "submit_card_plan", "arguments": value}, ensure_ascii=False)

    before = copy.deepcopy(value)
    with pytest.raises(CompactPlanValidationError, match="不支持Action"):
        parse_compact_plan_call(raw, current_task)
    assert value == before


@pytest.mark.usefixtures("static_policy")
def test_action_text_collision_does_not_turn_registered_action_into_static_text() -> None:
    action_id = "event.startNavigate"
    value = plan(
        [
            {
                "requirement": "从家到公司的导航入口",
                "priority": "must",
                "componentHints": [],
                "text": "去公司导航",
                "actionId": action_id,
                "displayRole": "title",
            },
        ],
        [{"id": "route", "kind": "object", "factIndexes": [0]}],
    )
    current_task = task("生成从家里导航到公司的卡片，点击一键导航去公司")
    current_task["eventCandidates"] = [{"id": action_id}]
    raw = json.dumps({"name": "submit_card_plan", "arguments": value}, ensure_ascii=False)

    before = copy.deepcopy(value)
    with pytest.raises(CompactPlanValidationError, match="不支持Action"):
        parse_compact_plan_call(raw, current_task)
    assert value == before


@pytest.mark.usefixtures("static_policy")
@pytest.mark.parametrize(
    "display,reference",
    [
        ("128元/月", "每月128元"),
        ("周末须提前预约", "周六、周日参观前均需要完成预约"),
        ("10月1–3日为天文大潮期", "10月1日至3日为天文大潮期"),
        ("03:00至07:00、21:00至23:00", "窗口为03:00至07:00与21:00至23:00"),
        ("晴天出发，遇雨取消", "天气晴朗时可以出发；如果下雨则取消出行"),
    ],
)
def test_model_summary_does_not_need_original_substrings(display, reference) -> None:
    accepted = accept(plan([fact(display, sourceTexts=[reference])]), reference)
    assert accepted.get("info_required", [])[0].get("text") == display


@pytest.mark.usefixtures("static_policy")
@pytest.mark.parametrize(
    "items",
    [
        [{"text": "甲", "assist": "免费"}, {"text": "乙", "assist": "20元"}],
        [{"text": "甲", "assist": "20元"}],
    ],
)
def test_objects_cannot_borrow_facts_from_another_item(items: list[dict]) -> None:
    accepted = plan(
        [fact("甲"), fact("20元"), fact("乙"), fact("免费")],
        [
            {"id": "a", "kind": "object", "factIndexes": [0, 1]},
            {"id": "b", "kind": "object", "factIndexes": [2, 3]},
        ],
    )
    errors = static_group_errors(source("SingleLineList", {"items": items}), accepted)
    assert errors and any("COMPACT_STATIC_CORE_MISSING" in error for error in errors)


@pytest.mark.usefixtures("static_policy")
def test_plan_should_authorizes_omission_without_waiting_for_repair() -> None:
    accepted = plan([fact("带证件"), fact("带雨伞", priority="should")])
    value = source("EmphasisText", {"mainText": "带证件"})
    assert not static_group_errors(value, accepted)
    assert not static_group_errors(value, accepted, (1,))
    assert static_group_errors(value, accepted, (0,))
    protected_plan = copy.deepcopy(accepted)
    facts = protected_plan.get("info_required")
    assert isinstance(facts, list)
    facts[1]["protectedTexts"] = ["带雨伞"]
    assert static_group_errors(value, protected_plan, (1,))


@pytest.mark.parametrize(
    "text,width",
    [("连续中文" * 20, 126.0), ("https://example.test/" * 15, 70.0), ("甲\n乙\n丙\n丁\n戊", 126.0)],
)
def test_complete_text_capacity_rejects_overflow(text: str, width: float) -> None:
    assert not measure_text(text, width, text_spec("emphasisSecondary")).fits


@pytest.mark.usefixtures("static_policy")
@pytest.mark.parametrize(
    "component,props,size",
    [
        ("EmphasisText", {"mainText": "长" * 100}, "2x2"),
        ("EmphasisText", {"mainText": "内容", "onClick": []}, "2x2"),
        ("SingleLineList", {"items": [{"text": "记录", "assist": "长" * 30}]}, "2x2"),
        ("ComparisonGroup", {"items": [{"primaryText": "甲"}, {"primaryText": "乙"}]}, "2x2"),
        ("ComparisonGroup", {"items": [{"primaryText": "长" * 30}, {"primaryText": "乙"}]}, "2x4"),
    ],
)
def test_invalid_static_components_fail_without_truncation(component, props, size) -> None:
    with pytest.raises(CompactDslConversionError):
        convert_compact_dsl_to_a2ui(source(component, props, size), size=size)


def fewshot_cases() -> list[tuple[str, str, dict]]:
    cases = []
    for size in ("2x2", "2x4"):
        text = (SOURCE_ROOT / "fewshots" / f"{size}.md").read_text(encoding="utf-8")
        pairs = re.findall(r"```json\n(.*?)\n```\s+```genui\n(.*?)\n```", text, re.S)
        for query, dsl in pairs:
            cases.append((size, dsl, json.loads(query)))
    return cases


@pytest.mark.usefixtures("static_policy")
@pytest.mark.parametrize("size,dsl,task_spec", fewshot_cases())
def test_all_static_fewshots_convert_validate_and_keep_theme_geometry(size, dsl, task_spec) -> None:
    facts = []
    groups = []
    for line in dsl.splitlines():
        row = json.loads(line)
        if len(row) < 3:
            continue
        identifier, component, props = row[:3]
        objects = []
        kind = "object"
        if component == "EmphasisText":
            objects = [[props.get("mainText"), props.get("secondaryText")]]
        elif component in {"TextList", "SingleLineList", "ComparisonGroup"}:
            for item in props.get("items", []):
                parts = []
                for key in ("primaryText", "secondaryText", "text", "assist", "value"):
                    if isinstance(item.get(key), str):
                        parts.append(item.get(key))
                parts.extend(item.get("details", []))
                objects.append(parts)
        elif component == "SingleLineTitle":
            kind = "shared"
            objects = [[props.get("title")]]
        for parts in objects:
            indexes = []
            for part in parts:
                if isinstance(part, str) and part:
                    indexes.append(len(facts))
                    facts.append(fact(part))
            groups.append({"id": str(len(groups)), "kind": kind, "factIndexes": indexes})
    accepted = plan(facts, groups)
    validate_compact_dsl(
        dsl,
        task_spec=task_spec,
        card_spec={"suggestSize": size},
        compact_plan=accepted,
        layout_scope=effective_layout_scope(size),
        enforce_model_component_types=True,
    )
    converted = convert_compact_dsl_to_a2ui(dsl, size=size)
    assert not final_static_display_errors(converted, converted)
    from services.static_content_context import standard_components

    for identifier, node in standard_components(converted).items():
        if "__static_" in identifier and node.get("component") == "Text":
            assert node.get("styles", {}).get("wordBreak") == "normal"


@pytest.mark.asyncio
@pytest.mark.usefixtures("isolated_theme_stage")
@pytest.mark.parametrize(
    "component,props,size,repair",
    [
        ("EmphasisText", {"mainText": "出发前检查", "secondaryText": "带证件"}, "2x2", False),
        ("SingleLineList", {"items": [
            {"text": "出发前", "assist": "带证件"},
            {"text": "遇雨", "assist": "带雨伞"},
        ]}, "2x2", False),
        (
            "ComparisonGroup",
            {"items": [{"primaryText": "128元/月"}, {"primaryText": "159元/月"}]},
            "2x4",
            False,
        ),
        ("EmphasisText", {"mainText": "出发前检查", "secondaryText": "带证件"}, "2x2", True),
    ],
)
async def test_formal_service_uses_static_plan_and_real_processor(
    monkeypatch,
    component,
    props,
    size,
    repair,
) -> None:
    from types import SimpleNamespace

    from api.schemas import GenerateWidgetCardRequest
    from config.config import get_settings
    from core.errors import GenerationStatus
    from custom.a2ui_model_client import A2UIModelClient
    from services.artifact_store import ArtifactStore
    from services.widget_generation_service import WidgetGenerationService

    text_values = []
    groups = []
    objects = props.get("items", [props])
    for item in objects:
        indexes = []
        for key in ("mainText", "secondaryText", "text", "assist", "primaryText"):
            text = item.get(key)
            if text is not None:
                indexes.append(len(text_values))
                text_values.append(text)
        groups.append({"id": str(len(groups)), "kind": "object", "factIndexes": indexes})
    accepted = plan([fact(text) for text in text_values], groups)
    prefix = "S" if size == "2x2" else "W"
    accepted["layoutHints"] = [f"{prefix}-static-content"]
    query = "制作静态卡片：" + "；".join(text_values)
    calls = []
    saved = []

    async def generate(_client, prompt, profile=None, **_kwargs):
        model_format = (profile or {}).get("format")
        calls.append((model_format, copy.deepcopy(prompt)))
        if model_format == "raw-json":
            review = review_response(prompt)
            if review is not None:
                return review
            return json.dumps(
                {"name": "submit_card_plan", "arguments": model_plan(accepted)}, ensure_ascii=False
            )
        dsl_calls = sum(item[0] == "compact-dsl" for item in calls)
        value = props
        if repair and dsl_calls == 1:
            value = {"mainText": "出发前检查"}
        return source(component, value, size)

    def save(_store, artifact):
        saved.append(artifact)
        return SimpleNamespace(
            artifactUrl="https://artifact.test/static", artifactDigest="sha256:static"
        )

    settings = get_settings()
    monkeypatch.setattr(settings, "enable_static_content_generation_policy", True)
    monkeypatch.setattr(settings, "enable_a2ui_model_mock", False)
    monkeypatch.setattr(settings, "enable_artifact_validation", True)
    monkeypatch.setattr(settings, "enable_validation_failure_retry", True)
    monkeypatch.setattr(A2UIModelClient, "generate", generate)
    monkeypatch.setattr(ArtifactStore, "save", save)
    request = GenerateWidgetCardRequest(
        uid="static-test",
        prdVer="11.7.7.331",
        device={"romVersion": "7.0"},
        userQuery=query,
        size=size,
        title="静态内容",
        description="静态专项回归",
    )
    result = await WidgetGenerationService().generate_widget_card_compact_dsl(request)
    assert result.status == GenerationStatus.SUCCESS, result
    assert len(saved) == 1
    expected = ["raw-json", "raw-json", "compact-dsl"]
    assert [call[0] for call in calls] == expected
    for text in text_values:
        assert text in saved[0].genui
    assert not current_content_policy().is_static
    assert "contentGroups" in calls[0][1][0].get("content", "")
    assert "FEWSHOT" not in calls[0][1][0].get("content", "")
    assert calls[-1][1][0].get("content", "").startswith(calls[0][1][0].get("content", ""))
    assert sum(message.get("role") == "system" for message in calls[-1][1]) == 1


def test_existing_action_layout_accepts_static_body_and_preserves_action() -> None:
    handler = {"call": "clickToDeeplink", "args": {"uri": "hww://calendar"}}
    rows = [
        ["root", "Layout", {"layout": "S-title-content-action"}, ["title", "content", "action"]],
        ["title", "SingleLineTitle", {"title": "出发", "fontSize": 12}],
        ["content", "EmphasisText", {"mainText": "带证件"}],
        ["action", "PillButton", {"label": "打开日历", "onClick": [handler]}],
        ["/state/ready", True],
    ]
    dsl = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    value = plan(
        [
            fact("出发"),
            fact("带证件"),
            {"requirement": "打开日历", "priority": "must", "actionId": "open"},
        ],
        [
            {"id": "title", "kind": "shared", "factIndexes": [0]},
            {"id": "body", "kind": "object", "factIndexes": [1]},
        ],
    )
    current_task = task("出发带证件，打开日历")
    current_task["eventCandidates"] = [{"id": "open", **handler}]
    validate_compact_dsl(
        dsl,
        task_spec=current_task,
        card_spec={"suggestSize": "2x2"},
        compact_plan=value,
        layout_scope=effective_layout_scope("2x2"),
        enforce_model_component_types=True,
    )
    from services.compact_plan import compact_plan_coverage_errors

    assert not compact_plan_coverage_errors(dsl, value, current_task)
    without_action = dsl.replace(json.dumps(handler, ensure_ascii=False), "{}")
    assert compact_plan_coverage_errors(without_action, value, current_task)


@pytest.mark.usefixtures("static_policy")
def test_minimal_should_drop_keeps_must_in_same_component() -> None:
    from services.compact_plan import (
        compact_plan_omitted_facts,
        compact_plan_optional_drop_candidate,
    )
    from services.compact_repair_strategy import CompactRepairStrategyTracker

    optional = "完整雨具使用说明" * 30
    accepted = plan([fact("带证件"), fact(optional, priority="should")])
    dsl = source("EmphasisText", {"mainText": optional, "secondaryText": "带证件"})
    candidate = compact_plan_optional_drop_candidate(dsl, accepted, task())
    assert candidate is not None and candidate.partial
    assert candidate.fact_indexes == (1,)
    tracker = CompactRepairStrategyTracker(static_content=True, capacity_recovery=True)
    issue = capacity_issue(dsl)
    first = tracker.next_directive(dsl, [issue], compact_plan=accepted, task_spec=task())
    assert first.optional_drop is None
    directive = tracker.next_directive(dsl, [issue], compact_plan=accepted, task_spec=task())
    assert directive.category == "layout_capacity"
    assert directive.optional_drop == candidate
    assert "由程序批准的should文字" in directive.instruction
    assert tracker.validation_omitted_fact_indexes(accepted, validate_drop_plan_facts=False) == (1,)
    repaired = source("EmphasisText", {"mainText": "带证件"})
    assert not static_group_errors(repaired, accepted, (1,))
    assert len(compact_plan_omitted_facts(repaired, accepted, task(), (1,))) == 1


@pytest.mark.usefixtures("static_policy")
@pytest.mark.parametrize(
    "extras",
    [
        {"priority": "should", "protectedTexts": ["带证件"]},
        {"priority": "should", "preserveVerbatim": True},
        {"priority": "must", "protectedTexts": ["带证件"]},
    ],
)
def test_static_drop_never_authorizes_protected_or_verbatim(extras) -> None:
    from services.compact_plan import compact_plan_optional_drop_candidate

    assert (
        compact_plan_optional_drop_candidate(
            source("EmphasisText", {"mainText": "带证件"}),
            plan([fact("带证件", **extras)]),
            task(),
            allow_must_fallback=True,
        )
        is None
    )


@pytest.mark.usefixtures("static_policy")
def test_static_drop_uses_lowest_must_after_should_candidates_are_exhausted() -> None:
    from services.compact_plan import (
        compact_plan_omitted_facts,
        compact_plan_optional_drop_candidate,
    )
    from services.compact_repair_strategy import CompactRepairStrategyTracker

    extra = "乙场完整入场说明" * 30
    facts = [fact("甲场周六19:30"), fact(extra)]
    groups = [
        {"id": "event0", "kind": "object", "factIndexes": [0]},
        {"id": "event1", "kind": "object", "factIndexes": [1]},
    ]
    accepted = plan(facts, groups)
    dsl = source(
        "SingleLineList",
        {
            "items": [
                {"text": "甲场", "assist": "周六19:30"},
                {"text": "乙场", "assist": extra.removeprefix("乙场")},
            ]
        },
    )
    assert (
        compact_plan_optional_drop_candidate(
            dsl,
            accepted,
            task(),
            allow_must_fallback=False,
        )
        is None
    )
    tracker = CompactRepairStrategyTracker(static_content=True, capacity_recovery=True)
    issue = capacity_issue(dsl)
    first = tracker.next_directive(dsl, [issue], compact_plan=accepted, task_spec=task())
    assert first.optional_drop is None
    directive = tracker.next_directive(dsl, [issue], compact_plan=accepted, task_spec=task())
    candidate = directive.optional_drop
    assert candidate is not None
    assert candidate.fact_indexes == (1,)
    assert candidate.contains_must_facts is True
    assert "由程序批准的must文字" in directive.instruction
    repaired = source("SingleLineList", {"items": [{"text": "甲场", "assist": "周六19:30"}]})
    assert not static_group_errors(repaired, accepted, (1,))
    omitted = compact_plan_omitted_facts(repaired, accepted, task(), (1,))
    assert omitted[0].get("omissionReason") == "bounded_drop"


@pytest.mark.usefixtures("static_policy")
def test_static_drop_keeps_the_last_object() -> None:
    from services.compact_plan import compact_plan_optional_drop_candidate

    accepted = plan([fact("甲场周六19:30")])
    dsl = source("SingleLineList", {"items": [{"text": "甲场", "assist": "周六19:30"}]})
    assert (
        compact_plan_optional_drop_candidate(
            dsl,
            accepted,
            task(),
            allow_must_fallback=True,
        )
        is None
    )


@pytest.mark.usefixtures("static_policy")
@pytest.mark.parametrize("mutation", ["drop", "move", "hide", "font", "ancestor"])
def test_final_theme_audit_rejects_changed_or_hidden_content(mutation) -> None:
    original = convert_compact_dsl_to_a2ui(
        source("EmphasisText", {"mainText": "带证件"}), size="2x2",
    )
    records = [json.loads(line) for line in original.splitlines()]
    nodes = []
    for record in records:
        update = record.get("updateComponents")
        if update is not None:
            nodes = update.get("components", [])
    text = next(node for node in nodes if node.get("component") == "Text")
    parent = next(node for node in nodes if text.get("id") in node.get("children", []))
    if mutation == "drop":
        text["content"] = "带雨伞"
    elif mutation == "move":
        parent["children"] = []
    elif mutation == "hide":
        parent.setdefault("styles", {})["opacity"] = 0
    elif mutation == "font":
        text.setdefault("styles", {})["fontSize"] = 8
    else:
        parent.setdefault("styles", {})["height"] = 1
    changed = "\n".join(json.dumps(record, ensure_ascii=False) for record in records)
    assert final_static_display_errors(original, changed)


@pytest.mark.usefixtures("static_policy")
@pytest.mark.parametrize("family", ["blue", "purple", "warm"])
def test_real_gradient_theme_keeps_complete_static_content(family) -> None:
    from services.post_layout_theme import apply_theme
    from services.post_layout_theme_registry import fallback_theme
    from services.theme_selection_policy import fusion_candidate_gate
    from services.theme_style_roles import layout_phase

    dsl = source("SingleLineList", {"items": [
        {"text": "出发前", "assist": "带证件"}, {"text": "遇雨", "assist": "带雨伞"},
    ]})
    with layout_phase(task=task()):
        original = convert_compact_dsl_to_a2ui(dsl, size="2x2")
    themed = apply_theme(original, fallback_theme(family), task(), {})
    assert not final_static_display_errors(original, themed)
    assert fusion_candidate_gate(task(), dsl).get("allowedTokens") == []


@pytest.mark.usefixtures("static_policy")
@pytest.mark.parametrize(
    "change",
    [
        {"mainText": {"path": "/data/fake"}},
        {"mainText": "${fake}"},
        {"mainText": "{{fake}}"},
        {"variant": []},
        {"attributes": []},
        {"width": 10},
        {"fontSize": 8},
    ],
)
def test_static_component_shape_does_not_allow_dynamic_or_free_geometry(change) -> None:
    props = {"mainText": "带证件", **change}
    with pytest.raises(CompactDslConversionError):
        convert_compact_dsl_to_a2ui(source("EmphasisText", props), size="2x2")


@pytest.mark.usefixtures("static_policy")
def test_missing_static_plan_context_cannot_skip_required_validation() -> None:
    from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext

    context = DslProcessingContext(
        size="2x2",
        task_spec=task(),
        card_spec={"suggestSize": "2x2"},
        protocol_profile=None,
        content_policy=STATIC_CONTENT_POLICY,
        layout_scope=effective_layout_scope("2x2"),
        skip_compact_dsl_validation=True,
    )
    result = DesignCompactProcessor().process(
        source("EmphasisText", {"mainText": "带证件"}), context,
    )
    assert result.issues
    assert not result.standard_dsl


@pytest.mark.usefixtures("static_policy")
def test_crlf_quotes_keep_offsets_into_original_source() -> None:
    from services.static_content_context import StaticContentContext

    original = "说明\r\n活动\r\n预计周六"
    accepted = accept(plan([fact("活动\n预计周六", preserveVerbatim=True)]), original)
    context = StaticContentContext.from_plan(original, accepted)
    assert context.source_positions[0].get("positions") == [{"start": 4, "end": 12}]


@pytest.mark.usefixtures("static_policy")
def test_ambiguous_source_positions_are_bounded(monkeypatch) -> None:
    from config.config import get_settings

    monkeypatch.setattr(get_settings(), "static_content_max_source_positions", 2)
    with pytest.raises(CompactPlanValidationError, match="来源位置数量超过预算"):
        accept(plan([fact("免费")]), "免费免费免费")


@pytest.mark.usefixtures("static_policy")
@pytest.mark.parametrize(
    "body",
    [
        "完整正文需要多行展示但每个字都应保留所以使用受控换行而不是省略号",
        "https://example.test/very-long-path-to-remember",
        "WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWW",
    ],
)
def test_complete_multiline_text_fits_without_changing_content(body) -> None:
    dsl = source("EmphasisText", {"mainText": "正文", "secondaryText": body}, "2x4")
    accepted = plan([fact("正文"), fact(body)])
    validate_compact_dsl(
        dsl,
        task_spec=task(body, "2x4"),
        card_spec={"suggestSize": "2x4"},
        compact_plan=accepted,
        layout_scope=effective_layout_scope("2x4"),
        enforce_model_component_types=True,
    )
    from services.static_content_context import standard_components

    converted = convert_compact_dsl_to_a2ui(dsl, size="2x4")
    texts = [
        node for node in standard_components(converted).values() if node.get("component") == "Text"
    ]
    rendered = next(node for node in texts if node.get("content") == body)
    assert measure_text(body, 276, text_spec("emphasisSecondary")).fits
    assert rendered.get("styles", {}).get("maxLines") == 3
    assert rendered.get("styles", {}).get("fontSize") == 12


@pytest.mark.usefixtures("static_policy")
def test_single_line_list_accepts_five_individually_valid_fields() -> None:
    items = [{"text": str(index), "assist": "完整值"} for index in range(5)]
    dsl = source("SingleLineList", {"items": items})
    facts = [fact(item.get("text") + "完整值") for item in items]
    groups = [{"id": str(index), "kind": "object", "factIndexes": [index]} for index in range(5)]
    validate_compact_dsl(
        dsl,
        task_spec=task("信息卡"),
        card_spec={"suggestSize": "2x2"},
        compact_plan=plan(facts, groups),
        layout_scope=effective_layout_scope("2x2"),
    )


@pytest.mark.usefixtures("static_policy")
def test_static_capacity_error_keeps_structured_diagnostic_and_guidance() -> None:
    body = "完整文字" * 30
    with pytest.raises(CompactDslValidationError) as caught:
        validate_compact_dsl(
            source("EmphasisText", {"mainText": body}),
            task_spec=task(body),
            card_spec={"suggestSize": "2x2"},
            compact_plan=plan([fact(body)]),
            layout_scope=effective_layout_scope("2x2"),
        )
    diagnostic = next(
        item for item in caught.value.diagnostics if item.code == "COMPACT_STATIC_TEXT_CAPACITY"
    )
    assert diagnostic.fix_hint and "固定文字规格" in diagnostic.fix_hint
    assert "不修改字体" in diagnostic.fix_hint


@pytest.mark.parametrize(
    "section,key",
    [("text", "header"), ("components", "ComparisonGroup"), ("measurement", "safetyFactor")],
)
def test_incomplete_static_recipe_is_rejected_before_enabling(
    monkeypatch, tmp_path, section, key
) -> None:
    from services import static_text_capacity as capacity

    value = capacity.static_content_contract()
    fields = value.get(section)
    assert isinstance(fields, dict)
    fields.pop(key)
    resource = tmp_path / "incomplete.json"
    resource.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    capacity._contract.cache_clear()
    monkeypatch.setattr(capacity, "_CONTRACT_PATH", resource)
    try:
        with pytest.raises(ValueError):
            capacity.static_content_contract()
    finally:
        capacity._contract.cache_clear()


def test_empty_static_prompt_does_not_fall_back_to_dynamic_prompt(tmp_path) -> None:
    from services.compact_prompt_loader import read_static_prompt

    root = tmp_path / "source"
    shutil.copytree(SOURCE_ROOT.parent, root)
    (root / "static_content/plan.md").write_text(" ", encoding="utf-8")
    with pytest.raises(ValueError, match="静态提示词资源为空"):
        read_static_prompt(root, "plan", "2x2")


@pytest.mark.usefixtures("static_policy")
@pytest.mark.parametrize(
    "component",
    [
        "EventCard",
        "TextBlock",
        "SummaryList",
        "InfoBlock",
        "TableText",
        "DataDisplay",
    ],
)
def test_old_body_components_cannot_bypass_static_validation(component) -> None:
    with pytest.raises(CompactDslValidationError, match="开域正文不允许") as caught:
        validate_compact_dsl(
            source(component, {}),
            task_spec=task(),
            card_spec={"suggestSize": "2x2"},
            compact_plan=plan([fact("带证件")]),
            enforce_model_component_types=False,
        )
    assert caught.value.diagnostics[0].code == "COMPACT_MODEL_COMPONENT_FORBIDDEN"


@pytest.mark.usefixtures("static_policy")
@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_static_plan_and_runtime_share_restricted_candidates(size) -> None:
    from services.compact_plan import build_compact_plan_tool
    from services.generation_content_policy import static_layout_ids, static_model_components

    tool = build_compact_plan_tool(task(size=size))
    function = tool.get("function")
    assert function is not None
    properties = function.get("parameters", {}).get("properties", {})
    groups = properties.get("contentGroups", {}).get("items", {}).get("properties", {})
    hints = groups.get("facts", {}).get("items", {}).get("properties", {})
    assert set(hints.get("componentHints", {}).get("items", {}).get("enum", [])) == set(
        static_model_components(size)
    )
    assert tuple(
        properties.get("layoutHints", {}).get("items", {}).get("enum", [])
    ) == static_layout_ids(size)
    assert allowed_layout_ids(size, effective_layout_scope(size)) == static_layout_ids(size)


@pytest.mark.usefixtures("static_policy")
def test_static_plan_rejects_old_component_hint() -> None:
    with pytest.raises(CompactPlanValidationError, match="静态计划仅允许"):
        accept(plan([fact("带证件", componentHints=["ContentBlock"])]), "带证件")


@pytest.mark.usefixtures("static_policy")
@pytest.mark.parametrize("count", [4, 5])
def test_plan_accepts_up_to_five_complete_objects(count) -> None:
    facts = []
    groups = []
    for index in range(count):
        facts.append(fact(f"演出{index}周六19:30"))
        groups.append({"id": f"concert{index}", "kind": "object", "factIndexes": [index]})
    query = "完整展示：" + "；".join(item.get("text") for item in facts)
    accepted = accept(plan(facts, groups), query, "2x4")
    assert len(accepted.get("contentGroups", [])) == count


@pytest.mark.usefixtures("static_policy")
@pytest.mark.parametrize("count", [6, 8])
def test_plan_rejects_more_than_five_complete_objects(count) -> None:
    facts = []
    groups = []
    for index in range(count):
        facts.append(fact(f"演出{index}周六19:30"))
        groups.append({"id": f"concert{index}", "kind": "object", "factIndexes": [index]})
    query = "完整展示：" + "；".join(item.get("text") for item in facts)
    with pytest.raises(CompactPlanValidationError, match="最多五条完整对象信息"):
        accept(plan(facts, groups), query, "2x4")


@pytest.mark.usefixtures("static_policy")
@pytest.mark.parametrize("records_style", [False, True])
def test_record_list_plan_rejects_more_than_three_objects(records_style: bool) -> None:
    facts = [fact("杭州周末活动汇总")]
    groups = [
        {
            "id": "summary",
            "kind": "shared",
            "factIndexes": [0],
        }
    ]
    for index in range(4):
        text = f"演出{index}周六19:30"
        hints = ["EmphasisText"] if records_style else ["TextList"]
        facts.append(fact(text, componentHints=hints))
        groups.append(
            {
                "id": f"concert{index}",
                "kind": "object",
                "factIndexes": [index + 1],
            }
        )
    value = plan(facts, groups)
    if records_style:
        value["presentationStyle"] = "records"
    query = "；".join(item.get("text") for item in facts)

    with pytest.raises(CompactPlanValidationError, match="TextList"):
        accept(value, query, "2x2")


@pytest.mark.usefixtures("static_policy")
def test_record_list_plan_accepts_three_objects() -> None:
    facts = []
    groups = []
    for index in range(3):
        text = f"演出{index}周六19:30"
        facts.append(fact(text, componentHints=["TextList"]))
        groups.append(
            {
                "id": f"concert{index}",
                "kind": "object",
                "factIndexes": [index],
            }
        )
    value = plan(facts, groups)
    value["presentationStyle"] = "records"
    query = "活动汇总：" + "；".join(item.get("text") for item in facts)

    accepted = accept(value, query, "2x2")
    assert len(accepted.get("contentGroups", [])) == 3


@pytest.mark.usefixtures("static_policy")
def test_plan_defers_height_to_selected_component_but_rejects_actual_overflow() -> None:
    body = "完整信息" * 120
    accepted = accept(plan([fact(body)]), body)
    with pytest.raises(CompactDslValidationError, match="COMPACT_STATIC_TEXT_CAPACITY"):
        validate_compact_dsl(
            source("EmphasisText", {"mainText": body}),
            task_spec=task(body),
            card_spec={"suggestSize": "2x2"},
            compact_plan=accepted,
        )
    value = plan([fact("音乐会"), fact("音乐会周六19:30")])
    assert accept(value, "音乐会周六19:30")


@pytest.mark.parametrize(
    "text,fragment,width",
    [
        ("甲方案 128元/月", "128元/月", 72.0),
        ("演出时间19:30–21:00", "19:30–21:00", 105.0),
        ("演出日期2026年10月3日19:30", "2026年10月3日", 110.0),
        ("温度预计-5℃", "-5℃", 42.0),
        ("预计升值0.72%", "0.72%", 48.0),
    ],
)
def test_readable_wrap_keeps_critical_numeric_fragments(text, fragment, width) -> None:
    measured = measure_text(text, width, text_spec("emphasisSecondary"))
    assert "".join(measured.wrapped_lines) == text
    assert any(fragment in line for line in measured.wrapped_lines)


def test_critical_fragment_too_wide_requires_wider_structure() -> None:
    with pytest.raises(ValueError, match="关键读数"):
        measure_text("128元/月", 24.0, text_spec("comparisonPrimary"))


@pytest.mark.usefixtures("static_policy")
def test_comparison_expands_price_as_complete_rendered_line() -> None:
    from services.static_content_context import standard_components

    items = [
        {"primaryText": "甲方案 128元/月"},
        {"primaryText": "乙方案 159元/月"},
        {"primaryText": "丙方案 199元/月"},
    ]
    converted = convert_compact_dsl_to_a2ui(
        source("ComparisonGroup", {"items": items}, "2x4"), size="2x4"
    )
    contents = []
    for node in standard_components(converted).values():
        if node.get("component") == "Text":
            contents.append(node.get("content"))
    assert "128元/月" in contents
    assert "159元/月" in contents
    assert "199元/月" in contents


@pytest.mark.usefixtures("static_policy")
def test_shared_note_cannot_hide_long_text_or_replace_body_object() -> None:
    dsl = source("EmphasisText", {"mainText": "带证件", "secondaryText": "完整说明" * 30})
    value = plan(
        [fact("带证件"), fact("完整说明" * 30)],
        [
            {"id": "object", "kind": "object", "factIndexes": [0]},
            {"id": "shared", "kind": "shared", "factIndexes": [1]},
        ],
    )
    from services.static_content_components import complete_static_text_trial

    with complete_static_text_trial(), pytest.raises(
        CompactDslValidationError, match="COMPACT_STATIC_TEXT_CAPACITY",
    ):
        validate_compact_dsl(
            dsl,
            task_spec=task(),
            card_spec={"suggestSize": "2x2"},
            compact_plan=value,
        )


@pytest.mark.usefixtures("static_policy")
@pytest.mark.parametrize(
    "display,reference",
    [
        ("每月128元", "128元/月"),
        ("预计周六晚七点半", "预计周六19:30"),
        ("期限不超过五年", "5年以下含5年"),
    ],
)
def test_model_owns_semantic_equivalence_without_numeric_token_gate(display, reference):
    assert accept(plan([fact(display, sourceTexts=[reference])]), reference)


@pytest.mark.usefixtures("static_policy")
def test_source_key_reading_can_be_split_across_facts_in_same_object() -> None:
    value = plan(
        [
            fact("128", sourceTexts=["128元/月"]),
            fact("元/月", sourceTexts=["128元/月"]),
        ]
    )
    assert accept(value, "128元/月")


@pytest.mark.asyncio
@pytest.mark.usefixtures("isolated_theme_stage")
async def test_four_short_objects_deliver_as_comparison_without_plan_rejection(monkeypatch):
    from types import SimpleNamespace

    from api.schemas import GenerateWidgetCardRequest
    from config.config import get_settings
    from custom.a2ui_model_client import A2UIModelClient
    from services.artifact_store import ArtifactStore
    from services.widget_generation_service import WidgetGenerationService

    names = ["甲演出", "乙演出", "丙演出", "丁演出"]
    facts = [fact(name + "周六") for name in names]
    groups = []
    for index in range(4):
        groups.append({"id": f"item{index}", "kind": "object", "factIndexes": [index]})
    value = plan(facts, groups)
    value["layoutHints"] = ["W-static-content"]
    calls = []
    saved = []

    async def generate(_client, _prompt, profile=None, **_kwargs):
        model_format = (profile or {}).get("format")
        calls.append(model_format)
        if model_format == "raw-json":
            review = review_response(_prompt)
            if review is not None:
                return review
            return json.dumps(
                {"name": "submit_card_plan", "arguments": model_plan(value)}, ensure_ascii=False,
            )
        items = [{"primaryText": name, "secondaryText": "周六"} for name in names]
        return source("ComparisonGroup", {"items": items}, "2x4")

    def save(_store, artifact):
        saved.append(artifact)
        return SimpleNamespace(artifactUrl="https://artifact.test/attributes", artifactDigest="qa")

    settings = get_settings()
    monkeypatch.setattr(settings, "enable_static_content_generation_policy", True)
    monkeypatch.setattr(settings, "enable_a2ui_model_mock", False)
    monkeypatch.setattr(A2UIModelClient, "generate", generate)
    monkeypatch.setattr(ArtifactStore, "save", save)
    request = GenerateWidgetCardRequest(
        uid="static-capacity-test",
        prdVer="11.7.7.331",
        device={"romVersion": "7.0"},
        userQuery="完整展示：" + "；".join(item.get("text") for item in facts),
        size="2x4",
        title="演出",
        description="完整属性表容量回归",
    )
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(request)
    assert response.status.value == "success", response
    assert len(saved) == 1
    assert calls == ["raw-json", "raw-json", "compact-dsl"]


@pytest.mark.usefixtures("static_policy")
def test_quote_context_does_not_force_unselected_conflicting_dates_into_venue():
    query = "虹口足球场，主办方10月31日，票务11月1日"
    value = plan([fact("虹口足球场", sourceTexts=[query])])
    assert accept(value, query).get("info_required")[0].get("text") == "虹口足球场"


@pytest.mark.usefixtures("static_policy")
@pytest.mark.parametrize(
    "display,reference",
    [
        ("周深巡演", "周深后面时间的演唱会巡演安排"),
        ("开演时间19:00", "开演时间均为19:00"),
    ],
)
def test_bounded_short_labels_can_remove_background(display, reference):
    assert accept(plan([fact(display, sourceTexts=[reference])]), reference)


@pytest.mark.usefixtures("static_policy")
def test_shared_note_split_accepts_punctuation_change_without_losing_date():
    text = "来源：示例条目，检索日期2026年9月21日"
    value = plan(
        [fact("博物馆"), fact(text)],
        [
            {"id": "object", "kind": "object", "factIndexes": [0]},
            {"id": "note", "kind": "shared", "factIndexes": [1]},
        ],
    )
    dsl = source("EmphasisText", {
        "mainText": "博物馆", "secondaryText": "来源：示例条目；检索日期2026年9月21日",
    })
    assert not static_group_errors(dsl, value)


@pytest.mark.usefixtures("static_policy")
@pytest.mark.parametrize("changed", [False, True])
def test_single_line_items_match_per_row_and_cannot_swap_values(changed):
    value = plan(
        [fact("米饭35至40分钟"), fact("干面条4至6分钟")],
        [
            {"id": "rice", "kind": "object", "factIndexes": [0]},
            {"id": "noodles", "kind": "object", "factIndexes": [1]},
        ],
    )
    values = ["35至40分钟", "4至6分钟"]
    if changed:
        values.reverse()
    dsl = source(
        "SingleLineList",
        {
            "items": [
                {"text": "米饭", "assist": values[0]},
                {"text": "干面条", "assist": values[1]},
            ]
        },
        "2x4",
    )
    assert bool(static_group_errors(dsl, value)) is changed


@pytest.mark.usefixtures("static_policy")
def test_price_labels_and_values_can_be_layered_without_rewriting_readings():
    value = plan([fact("票价三档"), fact("380元、680元、980元")])
    dsl = source("EmphasisText", {
        "mainText": "380元、680元、980元", "secondaryText": "票价三档",
    }, "2x4")
    assert not static_group_errors(dsl, value)


@pytest.mark.usefixtures("static_policy")
def test_optional_object_between_core_groups_can_be_omitted_and_reported():
    from services.compact_plan import compact_plan_omitted_facts

    value = plan(
        [fact("甲场19:30"), fact("乙场20:00", priority="should"), fact("丙场21:00")],
        [
            {"id": "a", "kind": "object", "factIndexes": [0]},
            {"id": "b", "kind": "object", "factIndexes": [1]},
            {"id": "c", "kind": "object", "factIndexes": [2]},
        ],
    )
    dsl = source("SingleLineList", {"items": [
        {"text": "甲场", "assist": "19:30"}, {"text": "丙场", "assist": "21:00"},
    ]})
    assert not static_group_errors(dsl, value)
    omitted = compact_plan_omitted_facts(dsl, value, task(), ())
    assert len(omitted) == 1
    assert omitted[0].get("text") == "乙场20:00"


@pytest.mark.usefixtures("static_policy")
@pytest.mark.parametrize(
    "text,visible,extras,valid",
    [
        ("周末带证件出门顺便去公园散步", "周末带证件出门顺便…", {}, False),
        ("周末带证件出门顺便去公园散步", "周末带证件出门顺便…", {"preserveVerbatim": True}, False),
        (
            "周末带证件出门顺便去公园散步",
            "周末带证件出门顺便…",
            {"protectedTexts": ["公园"]},
            False,
        ),
        ("演出19:30开始地点在示例剧场请提前准备", "演出19:30开始地点在示例…", {}, False),
        ("周末带证件出门顺便去公园门票20元", "周末带证件出门顺便…", {}, False),
        ("周末带证件出门顺便去公园需预约", "周末带证件出门顺便…", {}, False),
        ("周末带证件出门顺便去公园散步", "周末…", {}, False),
    ],
)
def test_dsl_cannot_truncate_accepted_core_even_without_keyword_match(text, visible, extras, valid):
    value = plan([fact(text, **extras)])
    dsl = source("EmphasisText", {"mainText": visible})
    assert bool(static_group_errors(dsl, value)) is not valid


@pytest.mark.usefixtures("static_policy")
@pytest.mark.parametrize("notes", [["仅展示最相关的两场演出"], []])
def test_plan_selection_notes_survive_and_feed_delivery_feedback(notes):
    from services.compact_plan import compact_plan_omitted_facts

    value = plan([fact("带证件")])
    value["selectionNotes"] = notes
    accepted = accept(value, "带证件")
    omitted = compact_plan_omitted_facts(
        source("EmphasisText", {"mainText": "带证件"}), accepted, task(), ()
    )
    assert accepted.get("selectionNotes") == notes
    assert not omitted


@pytest.mark.usefixtures("static_policy")
def test_comparison_detail_keeps_complete_text_with_registered_multiline_layout():
    from services.static_content_context import standard_components

    trailing = "成人票20元儿童需由成人陪同"
    dsl = source("ComparisonGroup", {"items": [
        {"primaryText": "动物园", "details": [trailing]}, {"primaryText": "展馆"},
    ]}, "2x4")
    converted = convert_compact_dsl_to_a2ui(dsl, size="2x4")
    contents = []
    for node in standard_components(converted).values():
        if node.get("component") == "Text":
            contents.append(node.get("content"))
    assert trailing == "".join(contents).removeprefix("动物园").removesuffix("展馆")


@pytest.mark.asyncio
@pytest.mark.usefixtures("static_policy")
async def test_static_theme_rejects_texture_and_uses_light_background():
    from services.post_layout_theme import select_theme

    seen = []

    class Client:
        async def generate(self, prompt, *_args, **_kwargs):
            payload = json.loads(prompt[1].get("content"))
            seen.extend(payload.get("candidates", []))
            return json.dumps({"themeId": seen[0].get("themeId")})

    dsl = source("EmphasisText", {"mainText": "带证件"})
    standard = convert_compact_dsl_to_a2ui(dsl, size="2x2")
    await select_theme(standard, task(), Client(), final_layout=dsl)
    assert seen
    assert all(candidate.get("type") in {"gradient", "solid"} for candidate in seen)


@pytest.mark.asyncio
@pytest.mark.usefixtures("isolated_theme_stage")
@pytest.mark.parametrize("mode", [
    "planning", "summary", "selection", "should", "ellipsis",
    "referenced_kept", "referenced_dropped",
])
async def test_static_content_reduction_is_delivered_as_degraded(monkeypatch, mode):
    from types import SimpleNamespace

    from api.schemas import GenerateWidgetCardRequest
    from config.config import get_settings
    from custom.a2ui_model_client import A2UIModelClient
    from services.artifact_store import ArtifactStore
    from services.widget_generation_service import WidgetGenerationService

    text = "周末带证件出门顺便去公园散步"
    value = plan([fact(text)])
    if mode == "planning":
        value["selectionNotes"] = ["全部内容保留，使用正文排版，无素材"]
    if mode == "selection":
        value["selectionNotes"] = ["只保留备忘核心，省略背景"]
        value["omittedContents"] = ["其余非必要背景"]
    if mode in {"should", "referenced_kept", "referenced_dropped"}:
        value = plan([fact(text), fact("带雨伞", priority="should")])
    if mode in {"referenced_kept", "referenced_dropped"}:
        value["omittedContents"] = [{"description": "可选补充", "factIndexes": [1]}]
    visible = "周末带证件出门顺便…" if mode == "ellipsis" else text
    if mode == "referenced_kept":
        visible += "；带雨伞"
    if mode == "summary":
        visible = "周末携证件，到公园走走"
        value = plan([fact(visible, sourceTexts=[text])])
    if mode == "ellipsis":
        value = plan([fact(visible, sourceTexts=[text])])
        value["omittedContents"] = ["公园散步安排"]
    value["layoutHints"] = ["W-static-content"]
    calls = []

    async def generate(_client, _prompt, profile=None, **_kwargs):
        calls.append((profile or {}).get("format"))
        if calls[-1] == "raw-json":
            review = review_response(_prompt)
            if review is not None:
                return review
            return json.dumps(
                {"name": "submit_card_plan", "arguments": model_plan(value)}, ensure_ascii=False,
            )
        return source("EmphasisText", {"mainText": visible}, "2x4")

    settings = get_settings()
    monkeypatch.setattr(settings, "enable_static_content_generation_policy", True)
    monkeypatch.setattr(settings, "enable_a2ui_model_mock", False)
    monkeypatch.setattr(A2UIModelClient, "generate", generate)
    monkeypatch.setattr(
        ArtifactStore,
        "save",
        lambda *_args: SimpleNamespace(
            artifactUrl="https://artifact.test/reduced", artifactDigest="qa"
        ),
    )
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(
        GenerateWidgetCardRequest(
            uid="static-reduction-test",
            prdVer="11.7.7.331",
            device={"romVersion": "7.0"},
            userQuery=text + "；带雨伞",
            size="2x4",
            title="备忘",
            description="精简反馈回归",
        )
    )
    expected = "success" if mode in {"planning", "summary", "referenced_kept"} else "degraded"
    assert response.status.value == expected, response
    if expected == "degraded":
        assert response.omittedRequirements
    else:
        assert "omittedRequirements" not in response.model_dump(mode="json")
    assert response.artifactUrl
    if expected == "degraded":
        assert "空间限制" in response.message
    assert calls == ["raw-json", "raw-json", "compact-dsl"]


@pytest.mark.usefixtures("static_policy")
def test_capacity_trial_never_selects_or_rewrites_model_facts():
    from services.static_content_planning import select_static_plan_content

    names = ["甲演唱会长名称", "乙演唱会长名称", "丙演唱会长名称", "丁演唱会长名称"]
    facts = [fact(name + "周六19:30示例体育场") for name in names]
    groups = []
    for index in range(len(facts)):
        groups.append({"id": str(index), "kind": "object", "factIndexes": [index]})
    original = copy.deepcopy(facts)
    selected = select_static_plan_content(facts, groups, "展示演唱会安排", "2x2")
    assert selected.facts == original
    assert selected.groups == groups
    assert not selected.notes
    assert not selected.omitted_contents
    assert selected.presentation is None
    assert selected.trial_errors
    assert "不代表所有合法排版均不可行" in selected.trial_errors[0]
    assert facts == original
    complete = select_static_plan_content(facts, groups, "完整展示演唱会安排", "2x2")
    assert complete.facts == original
    assert not complete.notes


@pytest.mark.usefixtures("static_policy")
@pytest.mark.parametrize("extra", [{}, {"onClick": [{}]}, {"variant": "unknown"}])
def test_record_table_normalization_preserves_all_text_and_does_not_hide_invalid_props(extra):
    from services.static_content_planning import normalize_static_record_table

    items = []
    for name in ("甲", "乙", "丙", "丁"):
        items.append({"title": name, "description": "周六19:30", "trailing": "免费"})
    dsl = source("RecordList", {"items": items, **extra}, "2x4")
    changed = normalize_static_record_table(dsl)
    assert changed == dsl
    for name in ("甲", "乙", "丙", "丁"):
        assert name in changed
    assert changed.count("周六19:30") == 4
    assert changed.count("免费") == 4
    with pytest.raises(CompactDslConversionError, match="unsupported component type RecordList"):
        convert_compact_dsl_to_a2ui(changed, size="2x4")


@pytest.mark.usefixtures("static_policy")
def test_pre_accept_title_compaction_keeps_protected_and_verbatim_exceptions():
    from services.static_content_planning import select_static_plan_content

    text = "Charlie Puth Whatever's Clever世界巡演上海站长标题"
    groups = [{"id": "main", "kind": "object", "factIndexes": [0]}]
    heading = fact(text, requirement="演出名称与艺人")
    selected = select_static_plan_content([heading], groups, "展示巡演信息", "2x2")
    assert selected.facts[0].get("text") == text
    assert not selected.notes
    protected = fact(text, requirement="演出名称与艺人", protectedTexts=[text])
    assert select_static_plan_content([protected], groups, "展示巡演信息", "2x2").facts == [
        protected
    ]
    assert select_static_plan_content([heading], groups, "原文展示巡演信息", "2x2").facts == [
        heading
    ]


@pytest.mark.parametrize(
    "text,expected",
    [
        ("含5年2.35%", ("5年", "2.35%")),
        ("含5年2.775%", ("5年", "2.775%")),
        ("F1", ("F1",)),
        ("PM2.5", ("PM2.5",)),
        ("IMAX 3D", ("3D",)),
        ("2026年10月3日19:30", ("2026年10月3日", "19:30")),
        ("10月3日至5日55至78", ("10月3日至5日", "55至78")),
        ("-5℃", ("-5℃",)),
    ],
)
def test_critical_readings_preserve_identifiers_and_do_not_join_term_with_rate(text, expected):
    from services.static_text_capacity import critical_readings

    assert critical_readings(text) == expected


@pytest.mark.usefixtures("static_policy")
@pytest.mark.parametrize("text", ["《F1：狂飙飞车》", "首要污染物前期为臭氧、后期转为PM2.5"])
def test_exact_source_with_mixed_identifier_is_always_supported(text):
    assert accept(plan([fact(text)]), text)


@pytest.mark.usefixtures("static_policy")
def test_movie_name_can_drop_parentheses_but_keep_whole_identifiers():
    text = "《沙丘3》（DUNE: PART THREE）IMAX 3D 原版字幕，19:30首都电影院"
    value = fact("《沙丘3》DUNE: PART THREE", sourceTexts=[text])
    assert accept(plan([value]), text)


@pytest.mark.usefixtures("static_policy")
def test_explicit_protection_is_not_silently_reassigned_by_program():
    value = plan(
        [
            fact("电影", protectedTexts=["19:30"], sourceTexts=["电影19:30"]),
            fact("19:30", sourceTexts=["电影19:30"]),
        ]
    )
    with pytest.raises(CompactPlanValidationError, match="保护片段"):
        accept(value, "电影19:30")
    value["contentGroups"] = [
        {"id": "a", "kind": "object", "factIndexes": [0]},
        {"id": "b", "kind": "object", "factIndexes": [1]},
    ]
    with pytest.raises(CompactPlanValidationError, match="保护片段"):
        accept(value, "电影19:30")


@pytest.mark.usefixtures("static_policy")
def test_term_and_decimal_rate_can_be_split_into_attribute_label_and_value():
    text = "首套住房5年以下含5年2.35%"
    accepted = plan([fact(text, protectedTexts=["含5年", "2.35%"])])
    dsl = source(
        "SingleLineList", {"items": [{"text": "首套住房5年以下含5年", "assist": "2.35%"}]}, "2x4"
    )
    validate_compact_dsl(
        dsl, task_spec=task(text, "2x4"), card_spec={"suggestSize": "2x4"}, compact_plan=accepted
    )


@pytest.mark.usefixtures("static_policy")
def test_literal_source_ellipsis_is_not_an_actual_reduction():
    from services.compact_plan import compact_plan_omitted_facts

    text = "备忘：看看下一步…"
    value = plan([fact(text)])
    dsl = source("EmphasisText", {"mainText": text})
    assert not compact_plan_omitted_facts(dsl, value, task(text), ())


@pytest.mark.parametrize(
    "query,texts",
    [
        ("日期存在冲突", ["演出", "主办方10月31日", "票务平台11月1日", "未标注改期"]),
        ("限行规则", ["工作日7:00至20:00限行", "纯电动出租车不受限行"]),
        ("保险分类", ["交强险是法定强制保险", "车船税属于税费不是保险"]),
    ],
)
def test_related_claims_and_exceptions_are_selected_together(query, texts):
    from services.static_content_planning import select_static_plan_content

    facts = [fact(text) for text in texts]
    groups = []
    for index in range(len(facts)):
        groups.append({"id": str(index), "kind": "object", "factIndexes": [index]})
    with content_policy_scope(STATIC_CONTENT_POLICY):
        selected = select_static_plan_content(facts, groups, query, "2x2")
    assert selected.facts == facts
    assert selected.groups == groups
    assert not selected.omitted_contents


@pytest.mark.usefixtures("static_policy")
def test_unenumerated_commute_table_preserves_all_facts_and_reports_capacity_feedback():
    from services.static_content_presentation import trial_static_presentation

    value = plan(
        [fact("地铁：含步行换乘42分钟，最稳"), fact("驾车：约15.3公里，平峰28分钟，早高峰55分钟")],
        [
            {"id": "subway", "kind": "object", "factIndexes": [0]},
            {"id": "drive", "kind": "object", "factIndexes": [1]},
        ],
    )
    before = copy.deepcopy(value)
    trial = trial_static_presentation(value, "展示通勤耗时", "2x2")
    assert trial.source is None
    assert trial.errors
    assert value == before
    assert "不代表所有合法排版均不可行" in trial.errors[0]


@pytest.mark.usefixtures("static_policy")
def test_static_repeated_failure_has_switch_instruction_then_stops_within_budget():
    from services.compact_repair_strategy import CompactRepairStrategyTracker

    tracker = CompactRepairStrategyTracker(static_content=True)
    value = plan([fact("带证件")])
    dsl = source("EmphasisText", {"mainText": "带证件"})
    issue = {"stage": "validation", "code": "COMPACT_STATIC_TEXT_CAPACITY", "message": "文字超限"}
    directives = []
    for _ in range(3):
        directives.append(
            tracker.next_directive(dsl, [issue], compact_plan=value, task_spec=task())
        )
    assert "切换组件形态" in directives[1].instruction
    assert not directives[2].retryable


@pytest.mark.usefixtures("static_policy")
def test_same_group_source_can_support_short_label_but_not_another_objects_claim():
    query = "交强险是法定强制保险，依据机动车交通事故责任强制保险条例（国务院令第462号）"
    facts = [
        fact("交强险：法定强制保险", sourceTexts=["交强险是法定强制保险"]),
        fact(
            "交强险条例（国务院令第462号）",
            sourceTexts=["依据机动车交通事故责任强制保险条例（国务院令第462号）"],
        ),
    ]
    accepted = accept(plan(facts), query)
    assert accepted.get("staticPresentation")
    split = [
        {"id": "a", "kind": "object", "factIndexes": [0]},
        {"id": "b", "kind": "object", "factIndexes": [1]},
    ]
    assert accept(plan(facts, split), query)


@pytest.mark.usefixtures("static_policy")
def test_program_does_not_select_optional_background_on_behalf_of_model():
    from services.static_content_planning import select_static_plan_content

    texts = ["交强险：法定强制保险", "背景资料" * 40, "车船税：属于税费，不是保险"]
    facts = [fact(texts[0]), fact(texts[1], priority="should"), fact(texts[2])]
    groups = [
        {"id": "insurance", "kind": "object", "factIndexes": [0, 1]},
        {"id": "tax", "kind": "object", "factIndexes": [2]},
    ]
    selected = select_static_plan_content(facts, groups, "展示保险分类", "2x2")
    assert selected.facts == facts
    assert not selected.omitted_contents
    assert selected.trial_errors
    assert "不代表所有合法排版均不可行" in selected.trial_errors[0]


@pytest.mark.usefixtures("static_policy")
def test_explicit_horizontal_comparison_is_not_changed_into_a_list():
    from services.static_content_presentation import static_presentation_candidates

    value = plan(
        [fact("甲：20元"), fact("乙：30元")],
        [
            {"id": "a", "kind": "object", "factIndexes": [0]},
            {"id": "b", "kind": "object", "factIndexes": [1]},
        ],
    )
    value["presentationStyle"] = "comparison"
    candidates = static_presentation_candidates(value, "2x4")
    assert candidates
    assert len(candidates) == len(set(candidates))
    assert all("ComparisonGroup" in candidate for candidate in candidates)


@pytest.mark.parametrize("exception", ["区域B不适用", "赠品不是主套餐", "访客除外", "仅限成年人"])
def test_relation_detection_is_independent_of_business_names(exception):
    from services.static_content_planning import select_static_plan_content

    facts = [fact("主要对象与规则"), fact(exception)]
    groups = [
        {"id": "main", "kind": "object", "factIndexes": [0]},
        {"id": "exception", "kind": "object", "factIndexes": [1]},
    ]
    with content_policy_scope(STATIC_CONTENT_POLICY):
        selected = select_static_plan_content(facts, groups, "展示信息", "2x2")
    assert selected.facts == facts
    assert selected.groups == groups


@pytest.mark.usefixtures("static_policy")
@pytest.mark.parametrize("invalid", [None, 0, {}, []])
def test_source_normalization_preserves_validation_exception_for_non_text(invalid):
    invalid_fact = fact("备忘")
    invalid_fact["text"] = invalid
    value = plan([invalid_fact])
    with pytest.raises(CompactPlanValidationError):
        accept(value, "备忘")


@pytest.mark.usefixtures("static_policy")
def test_no_candidate_is_not_a_plan_rejection(monkeypatch):
    from services.static_content_presentation import StaticPresentationTrial

    monkeypatch.setattr(
        "services.static_content_presentation.trial_static_presentation",
        lambda *_args: StaticPresentationTrial(None, 3, ("候选字段超限",)),
    )
    value = plan([fact("核心结论与必要条件")])
    accepted = accept(value, "核心结论与必要条件")
    assert accepted.get("info_required") == value.get("info_required")
    assert "staticPresentation" not in accepted


@pytest.mark.usefixtures("static_policy")
def test_summary_instructions_reuse_existing_stages_and_keep_semantic_responsibility():
    from services.compact_prompt_loader import read_static_prompt

    plan_prompt = read_static_prompt(SOURCE_ROOT.parent, "plan", "2x2")
    dsl_prompt = read_static_prompt(SOURCE_ROOT.parent, "dsl", "2x2")
    create_prompt = read_static_prompt(SOURCE_ROOT.parent, "create", "2x2")
    assert "不必逐字提取" in plan_prompt
    assert "或/且" in create_prompt
    assert "omittedContents" in plan_prompt
    assert "原始输入" in dsl_prompt
    assert "静态" in create_prompt
    assert "不补造事实" in create_prompt
    assert "title-action" not in dsl_prompt
    assert "不新增模型阶段" in plan_prompt


@pytest.mark.usefixtures("static_policy")
def test_equal_meaning_summary_does_not_trigger_omission_by_source_string_comparison():
    from services.compact_plan import compact_plan_omitted_facts

    reference = "活动安排在周六晚上七点半开始，参加前需要预约"
    text = "周六19:30开始，须预约"
    accepted = accept(plan([fact(text, sourceTexts=[reference])]), reference)
    assert not compact_plan_omitted_facts(
        source("EmphasisText", {"mainText": text}), accepted, task(reference), ()
    )


@pytest.mark.usefixtures("static_policy")
@pytest.mark.parametrize("part", ["128元/月", "至少2天", "国内流量", "或等效组合"])
def test_dsl_cannot_drop_any_accepted_core_by_missing_program_keyword(part):
    text = "主体" + part
    value = plan([fact(text)])
    assert static_group_errors(source("EmphasisText", {"mainText": "主体"}), value)


def test_closed_plan_keeps_paraphrased_text_with_warning():
    with content_policy_scope(EXISTING_CONTENT_POLICY):
        value = {"info_required": [{"requirement": "说明", "priority": "must", "text": "携证出行"}]}
        raw = json.dumps({"name": "submit_card_plan", "arguments": value}, ensure_ascii=False)

        result = parse_compact_plan_call(raw, task("带证件出门"))

        assert result.plan.get("info_required", [])[0].get("text") == "携证出行"
        assert any("must be copied from userQuery" in warning for warning in result.warnings)


@pytest.mark.usefixtures("static_policy")
def test_plan_text_can_be_distributed_in_reordered_display_fields_without_semantic_tokens():
    value = plan([fact("示例对象128元/月"), fact("国内范围")])
    dsl = source(
        "ComparisonGroup",
        {
            "items": [
                {"primaryText": "128元/月", "secondaryText": "示例对象", "details": ["国内范围"]},
                {"primaryText": "另一对象"},
            ]
        },
        "2x4",
    )
    value["info_required"].append(fact("另一对象"))
    value["contentGroups"].append({"id": "other", "kind": "object", "factIndexes": [2]})
    assert not static_group_errors(dsl, value)
    changed = dsl.replace("128元/月", "129元/月")
    assert static_group_errors(changed, value)


@pytest.mark.usefixtures("static_policy")
def test_plan_budget_is_loaded_from_shared_contract():
    from services.compact_prompt_loader import read_static_prompt
    from services.static_text_capacity import static_capacity_prompt, static_content_contract

    prompt = read_static_prompt(SOURCE_ROOT.parent, "plan", "2x2")
    budget = json.loads(prompt.splitlines()[-1])
    contract = static_content_contract()
    assert budget.get("referenceOnly") is True
    assert budget.get("width") == 150
    assert budget.get("height") == 150
    assert "text" not in budget
    initial_budget = static_capacity_prompt("2x2")
    assert "# 首次Plan组件容量预算" in initial_budget
    assert "字体、行高及间距由Runtime固定" in initial_budget
    assert "TextList/records：带标题只能2项，无标题只能3项" in initial_budget
    assert "SingleLineList/rows：必须带标题，正文1–5行" in initial_budget
    assert "ComparisonGroup在2x2不可用" in initial_budget
    assert "shared/body虽不计入object组数" in initial_budget
    assert "omittedContents" in initial_budget
    assert "TextList" in contract.get("components", {})
    assert contract.get("text", {}).get("emphasis", {}).get("fontSize") == 18

    wide_budget = static_capacity_prompt("2x4")
    assert "ComparisonGroup仅2x4可用：带标题2–3项，无标题4项" in wide_budget
