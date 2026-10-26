"""整卡详情的接受、精确覆盖、发布校验和回退边界；不调用线上模型。"""

import copy
import json
from types import SimpleNamespace

import pytest

from api.schemas import GenerateWidgetCardRequest
from config.config import get_settings
from core.errors import GenerationStatus
from custom.a2ui_model_client import A2UIModelClient
from models.generation import CardSpec, TaskSpec
from services.artifact_store import ArtifactStore
from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.compact_plan import (
    CompactPlanValidationError,
    compact_plan_context,
    parse_compact_plan_call,
)
from services.compact_repair_context import joint_repair_contract
from services.compact_whole_card_click import accepted_whole_card_click, select_whole_card_click
from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext
from services.generation_preflight import GenerationPreflight
from services.widget_generation_service import WidgetGenerationService

# 本组验证既有创建、回退或路由合同，静态策略由专项测试覆盖。
pytestmark = pytest.mark.usefixtures("existing_generation_policy")


def _task(business: str = "weather") -> dict:
    weather = {
        "current": {"condition": {"type": "string", "sampleValue": "晴"}},
        "location": {"cityCode": {"type": "string", "sampleValue": "101010100"}},
    }
    calendar = {"events": [{
        "title": {"type": "string", "sampleValue": "设计评审"},
        "entityId": {"type": "string", "sampleValue": "event-1"},
    }]}
    event = {
        "id": "event.open.weather",
        "call": "clickToDeeplink",
        "args": {
            "intentName": "Weather_CityCode", "bundleName": "", "abilityName": "",
            "uri": "{{ 'hww://www.huawei.com/totemweather?enterType=share&cityCode=' "
                   "+ ${/data/weather/location/cityCode} }}",
        },
    }
    if business == "calendar":
        event = {
            "id": "event.viewCalendarEvent", "call": "clickToIntent",
            "args": {
                "intentName": "ViewCalendarEvent",
                "params": {"entityId": "{{ ${/data/calendar/events/0/entityId} }}"},
            },
        }
    return {
        "appVersion": "11.7.8.340", "size": "2x2",
        "userQuery": "显示天气，点一下查看天气详情" if business == "weather"
                     else "显示下一场日程标题，点一下查看日程详情",
        "dataModelSchema": {"data": {business: weather if business == "weather" else calendar}},
        "eventCandidates": [event], "assetCandidates": [],
    }


def _candidate(task: dict) -> dict:
    candidates = task.get("eventCandidates")
    assert isinstance(candidates, list)
    candidate = candidates[0]
    assert isinstance(candidate, dict)
    return candidate


def _facts(task: dict, business: str = "weather") -> list[dict]:
    return [
        {
            "requirement": "用户要求的动态正文", "priority": "must",
            "dataId": "/data/weather/current/condition" if business == "weather"
                      else "/data/calendar/events/0/title",
            "componentHints": ["EmphasisText"],
        },
        {
            "requirement": "点按查看详情", "priority": "must",
            "actionId": _candidate(task).get("id"), "componentHints": ["PillButton"],
        },
    ]


def _accept(task: dict, business: str = "weather", *, facts: list | None = None) -> dict:
    arguments = {
        "info_required": _facts(task, business) if facts is None else facts,
        "layoutHints": ["S-title-content-action"],
    }
    if task.get("assetCandidates"):
        arguments["assetAssignments"] = {
            "actions": [{"actionId": _candidate(task).get("id"), "assetId": "asset.detail"}],
            "title": {"assetId": "asset.detail"},
        }
    output = json.dumps({"name": "submit_card_plan", "arguments": arguments}, ensure_ascii=False)
    return parse_compact_plan_call(output, task).plan


def _source_rows(task: dict, business: str = "weather") -> list[list]:
    event = _candidate(task)
    handler = {"call": event.get("call"), "args": copy.deepcopy(event.get("args"))}
    facts = _facts(task, business)
    data = {"current": {"condition": "晴"}, "location": {"cityCode": "101010100"}}
    if business == "calendar":
        data = {"events": [{"title": "设计评审", "entityId": "event-1"}]}
    return [
        ["root", "Layout", {"layout": "S-title-content", "onClick": [handler]},
         ["title", "content"]],
        ["title", "SingleLineTitle", {"title": "信息概览", "fontSize": 12}],
        ["content", "EmphasisText", {"mainText": {"path": facts[0].get("dataId")}, "fontSize": 18}],
        [f"/data/{business}", data],
    ]


def _validate(
    task: dict, plan: dict | None, rows: list[list], *, layout_scope: str = "S-title-content",
) -> None:
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    validate_compact_dsl(
        source, task_spec=task, card_spec={"suggestSize": task.get("size")}, compact_plan=plan,
        layout_scope=layout_scope, enforce_model_component_types=True,
    )


@pytest.mark.parametrize("business", ["weather", "calendar"])
def test_whole_card_accepts_and_compiles_exact_read_only_handler(business: str) -> None:
    task = _task(business)
    before = copy.deepcopy(task)
    facts = _facts(task, business)
    plan = _accept(task, business)
    selected = accepted_whole_card_click(task, plan)
    assert selected is not None
    assert selected.action_id == _candidate(task).get("id")
    accepted = plan.get("info_required")
    assert isinstance(accepted, list)
    assert accepted[0] == facts[0]
    assert accepted[1].get("actionId") == facts[1].get("actionId")
    assert accepted[1].get("priority") == "must"
    assert "componentHints" not in accepted[1]
    assert "不能删动作" in compact_plan_context(plan)
    rows = _source_rows(task, business)
    _validate(task, plan, rows)
    context = DslProcessingContext(
        size="2x2", card_spec={"suggestSize": "2x2"}, task_spec=task, protocol_profile={},
        compact_plan=plan, layout_scope="S-title-content", colorless_layout=True,
    )
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    result = DesignCompactProcessor().process(source, context)
    assert not result.errors
    assert result.standard_dsl
    messages = [json.loads(line) for line in result.standard_dsl.splitlines()]
    handlers = []

    def collect(value):
        if isinstance(value, dict):
            if "onClick" in value:
                handlers.append(value.get("onClick"))
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(messages)
    assert handlers == [[selected.handler]]
    assert task == before


@pytest.mark.parametrize("query", ["天气详情按钮", "显示按钮文案：查看天气", "weather button"])
def test_explicit_button_requests_keep_button_path(query: str) -> None:
    task = _task()
    task["userQuery"] = query
    plan = _accept(task)
    assert "wholeCardActionId" not in plan
    assert plan.get("layoutHints") == ["S-title-content-action"]
    with pytest.raises(CompactDslValidationError):
        _validate(task, plan, _source_rows(task))


@pytest.mark.parametrize("query", [
    "显示天气，不需要按钮，点击查看天气详情", "不显示按钮，整卡查看天气",
    "无需按钮，点天气看详情", "去掉按钮，整卡打开天气", "no button, open weather details",
])
def test_negative_button_mentions_do_not_create_a_button_requirement(query: str) -> None:
    task = _task()
    task["userQuery"] = query
    assert _accept(task).get("wholeCardActionId") == "event.open.weather"


@pytest.mark.parametrize("action", [
    "event.call.phone", "event.startNavigate", "event.enter.meeting",
    "event.setPowerSavingMode", "event.open.health.sleep",
])
def test_other_actions_and_unregistered_details_keep_buttons(action: str) -> None:
    task = _task()
    _candidate(task)["id"] = action
    plan = _accept(task)
    assert "wholeCardActionId" not in plan
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    assert facts[-1].get("componentHints") == ["PillButton"]


@pytest.mark.parametrize("case", ["wide", "multi_business", "duplicate_target", "two_actions",
                                "wrong_call", "wrong_intent", "wrong_city", "wrong_bundle",
                                "pure_display"])
def test_ambiguous_or_unsupported_requests_do_not_get_root_authorization(case: str) -> None:
    task = _task()
    facts = _facts(task)
    candidate = _candidate(task)
    args = candidate.get("args")
    assert isinstance(args, dict)
    if case == "wide":
        task["size"] = "2x4"
    elif case == "multi_business":
        schema = task.get("dataModelSchema")
        assert isinstance(schema, dict)
        schema["data"] = {"weather": {}, "calendar": {}}
    elif case == "duplicate_target":
        task["eventCandidates"] = [candidate, copy.deepcopy(candidate)]
    elif case == "two_actions":
        extra = {**copy.deepcopy(candidate), "id": "event.call.phone"}
        task["eventCandidates"] = [candidate, extra]
        facts.append({"requirement": "拨号", "priority": "must", "actionId": extra.get("id")})
    elif case == "wrong_call":
        candidate["call"] = "clickToIntent"
    elif case == "wrong_intent":
        args["intentName"] = "StartNavigate"
    elif case == "wrong_city":
        args["uri"] = "hww://unknown"
    elif case == "wrong_bundle":
        args["bundleName"] = "other.app"
    elif case == "pure_display":
        task["userQuery"] = "天气纯展示，不要点击"
    assert select_whole_card_click(task, facts) is None


@pytest.mark.parametrize("case", ["different_event", "list_count", "static_target"])
def test_calendar_details_must_match_one_displayed_event(case: str) -> None:
    task = _task("calendar")
    facts = _facts(task, "calendar")
    if case == "different_event":
        facts[0]["dataId"] = "/data/calendar/events/1/title"
    elif case == "list_count":
        facts.append({"requirement": "总数", "dataId": "/data/calendar/count", "priority": "must"})
    else:
        args = _candidate(task).get("args")
        assert isinstance(args, dict)
        args["params"] = {"entityId": "event-1"}
    assert select_whole_card_click(task, facts) is None


def test_whole_card_action_does_not_consume_title_asset() -> None:
    task = _task()
    task["assetCandidates"] = [{"id": "asset.detail", "src": "resources/detail.svg"}]
    plan = _accept(task)
    assignments = plan.get("assetAssignments")
    assert isinstance(assignments, dict)
    assert assignments.get("title") == {"assetId": "asset.detail"}
    actions = assignments.get("actions")
    assert isinstance(actions, list)
    assert actions[0].get("assetId") is None
    rows = _source_rows(task)
    rows[1][2]["icon"] = "resources/detail.svg"
    _validate(task, plan, rows)


@pytest.mark.parametrize("case", ["missing", "changed_args", "child_click", "duplicate_click",
                                "button", "forged_marker"])
def test_whole_card_action_cannot_be_dropped_moved_duplicated_or_forged(case: str) -> None:
    task = _task()
    plan = _accept(task)
    rows = _source_rows(task)
    root_props = rows[0][2]
    if case == "missing":
        root_props.pop("onClick")
    elif case == "changed_args":
        handlers = root_props.get("onClick")
        assert isinstance(handlers, list)
        args = handlers[0].get("args")
        assert isinstance(args, dict)
        args["uri"] = "changed"
    elif case == "child_click":
        rows[2][2]["onClick"] = root_props.pop("onClick")
    elif case == "duplicate_click":
        rows[2][2]["onClick"] = copy.deepcopy(root_props.get("onClick"))
    elif case == "button":
        rows[0][3].append("button")
        rows.insert(3, ["button", "PillButton", {
            "label": "查看详情", "onClick": copy.deepcopy(root_props.get("onClick")),
        }])
    else:
        plan["wholeCardActionId"] = "event.startNavigate"
    with pytest.raises(CompactDslValidationError):
        _validate(task, plan, rows)


def test_root_count_exception_is_not_enabled_without_accepted_plan() -> None:
    task = _task()
    with pytest.raises(CompactDslValidationError, match="at most 0 actions"):
        _validate(task, None, _source_rows(task))


def test_joint_repair_keeps_whole_card_action_and_complete_parameters() -> None:
    task = _task()
    plan = _accept(task)
    contract = joint_repair_contract(plan, task, [])
    assert contract.get("wholeCardActionId") == _candidate(task).get("id")
    assert contract.get("actions") == task.get("eventCandidates")
    assert "不补回按钮" in contract.get("instruction", "")


def test_calendar_entity_path_binding_is_preserved() -> None:
    task = _task("calendar")
    args = _candidate(task).get("args")
    assert isinstance(args, dict)
    args["params"] = {"entityId": {"path": "/data/calendar/events/0/entityId"}}
    plan = _accept(task, "calendar")
    selected = accepted_whole_card_click(task, plan)
    assert selected is not None
    assert selected.handler.get("args") == args
    _validate(task, plan, _source_rows(task, "calendar"))


@pytest.mark.parametrize("priority", ["must", "should"])
def test_whole_card_keeps_all_primary_and_supporting_facts(priority: str) -> None:
    task = _task()
    schema = task.get("dataModelSchema")
    assert isinstance(schema, dict)
    data = schema.get("data")
    assert isinstance(data, dict)
    weather = data.get("weather")
    assert isinstance(weather, dict)
    current = weather.get("current")
    assert isinstance(current, dict)
    current["humidity"] = {"type": "string", "sampleValue": "45%"}
    facts = _facts(task)
    support = {
        "requirement": "湿度", "priority": priority, "dataId": "/data/weather/current/humidity",
        "componentHints": ["SecondaryBody"],
    }
    facts.insert(1, support)
    plan = _accept(task, facts=facts)
    accepted = plan.get("info_required")
    assert isinstance(accepted, list)
    assert accepted[:2] == facts[:2]
    rows = _source_rows(task)
    rows[0][2]["layout"] = "S-title-dual-content"
    rows[0][3].append("support")
    rows.insert(3, ["support", "SecondaryBody", {
        "items": [{"label": "湿度", "value": {"path": support.get("dataId")}}], "fontSize": 14,
    }])
    data_row = rows[-1][1]
    assert isinstance(data_row, dict)
    current_value = data_row.get("current")
    assert isinstance(current_value, dict)
    current_value["humidity"] = "45%"
    _validate(task, plan, rows, layout_scope="S-title-dual-content")


def test_model_cannot_self_authorize_whole_card_metadata() -> None:
    task = _task()
    output = json.dumps({"name": "submit_card_plan", "arguments": {
        "info_required": _facts(task), "wholeCardActionId": "event.open.weather",
    }}, ensure_ascii=False)
    with pytest.raises(CompactPlanValidationError, match="Unsupported Plan arguments"):
        parse_compact_plan_call(output, task)


@pytest.mark.asyncio
@pytest.mark.usefixtures("isolated_theme_stage")
@pytest.mark.parametrize("mode", ["whole_card", "implicit_detail", "explicit_button", "repair"])
async def test_real_plan_dsl_pipeline_keeps_call_budget_and_click_presentation(
    monkeypatch, mode: str,
) -> None:
    task = _task()
    if mode == "explicit_button":
        task["userQuery"] = "显示天气并提供查看详情按钮"
    elif mode == "implicit_detail":
        task["userQuery"] = "做一张天气卡片"
    task_model = TaskSpec.model_validate(task)
    preflight = SimpleNamespace(
        blocking_issues=(), warnings=(), effective_bindings=(), effective_data_capabilities=(),
        effective_events=tuple(task_model.eventCandidates), effective_assets=(),
        removed_capabilities=(), task_spec=task_model,
        card_spec=CardSpec(title="天气", description="天气详情", suggestSize="2x2"),
    )
    monkeypatch.setattr(GenerationPreflight, "run", lambda _self, _request: preflight)
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_a2ui_model_mock", False)
    monkeypatch.setattr(settings, "enable_artifact_validation", False)
    monkeypatch.setattr(settings, "enable_design_compact_runtime_prompt_context", False)
    monkeypatch.setattr(settings, "enable_validation_failure_retry", True)
    monkeypatch.setattr(
        WidgetGenerationService, "_enable_card_template", staticmethod(lambda: False),
    )
    monkeypatch.setattr(
        WidgetGenerationService, "_enable_jsx_generation", staticmethod(lambda: False),
    )
    monkeypatch.setattr(ArtifactStore, "save", lambda _self, _artifact: SimpleNamespace(
        artifactUrl="https://artifact.test/whole-card", artifactDigest="sha256:whole-card",
    ))
    formats = []
    dsl_messages = []

    async def generate(_self, prompt, profile=None, **_kwargs):
        model_format = (profile or {}).get("format")
        formats.append(model_format)
        if model_format == "raw-json":
            return json.dumps({"name": "submit_card_plan", "arguments": {
                "info_required": _facts(task), "layoutHints": ["S-title-content-action"],
            }}, ensure_ascii=False)
        dsl_messages.append(copy.deepcopy(prompt))
        rows = _source_rows(task)
        if mode == "explicit_button":
            root_props = rows[0][2]
            handlers = root_props.pop("onClick")
            root_props["layout"] = "S-title-content-action"
            rows[0][3].append("button")
            rows.insert(3, ["button", "PillButton", {"label": "查看天气", "onClick": handlers}])
        elif mode == "repair" and len(dsl_messages) == 1:
            rows[0][2].pop("onClick")
        return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)

    monkeypatch.setattr(A2UIModelClient, "generate", generate)
    request = GenerateWidgetCardRequest(
        uid="test-user", prdVer="11.7.8.340", device={"romVersion": "7.0"},
        userQuery=task_model.userQuery, title="天气", description="天气详情", size="2x2",
    )
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(request)
    assert response.status == GenerationStatus.SUCCESS
    expected = ["raw-json", "compact-dsl"]
    if mode == "repair":
        expected.append("compact-dsl")
    assert formats == expected
    for messages in dsl_messages:
        context = "\n".join(message.get("content", "") for message in messages)
        if mode != "explicit_button":
            assert '"wholeCardActionId":"event.open.weather"' in context
            assert "不能删动作、改为子节点点击或因修复补回按钮" in context
        else:
            assert '"wholeCardActionId":"event.open.weather"' not in context
