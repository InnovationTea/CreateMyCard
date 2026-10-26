"""布局与主题共用业务证据，实际展示优先；视觉偏好仍由一次主题调用处理。"""

import asyncio
import copy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config.config import get_settings
from models.generation import TaskSpec
from services import content_business as business
from services import post_layout_theme as themes
from services import theme_selection_policy as policy
from services.compact_dsl_a2ui_converter import ComponentRow
from services.prompt_builder import PromptBuilder
from test_compact_plan_generation import (
    test_real_compact_route_runs_plan_before_dsl_without_plan_fewshots as run_plan_flow,
)
from test_navigation_settings_photo import NAVIGATION, SETTINGS, action
from test_post_layout_sleep_theme import sleep_layout, sleep_task
from test_texture_mixed_business import mixed_sample, split_sample
from test_uniform_photo_eligibility import PATHS, evidence, photo, sample
from test_wide_photo_focus import focus_sample
from theme_preference_samples import preference, reply


@pytest.mark.parametrize("path,expected", [
    ("/data/healthSport/nightSleepDurationText", "sleep"),
    ("/data/healthSport/dailySteps", "sport"),
    ("/data/healthSport/unknownMetric", None),
    ("/data/currentTime/currentDate", "calendar"),
    ("/data/currentTime/updatedAt", None),
    ("/data/weather/current/temperature", "weather"),
    ("/data/custom/mostUsedApps/4/totalDuration", "app-usage"),
    ("/data/custom/appName", None),
    ("/data/earphone/battery", "earphone"),
    ("/data/phoneBattery/level", "battery"),
])
def test_registered_binding_semantics_ignore_query_words(path, expected):
    catalog = business.BusinessContext.from_task({
        "userQuery": "天气会议运动睡眠紫色深色背景",
        "dataModelSchema": {},
    })
    rows = [ComponentRow("text", "Text", {"content": {"path": path}})]
    facts = catalog.visible(rows)
    assert facts.single == expected
    assert facts.first == expected


@pytest.mark.parametrize("event_id,expected", [(NAVIGATION, "navigation"), (SETTINGS, "settings")])
def test_plan_and_final_action_share_catalog_entry(monkeypatch, event_id, expected):
    handler = action(event_id)
    task = {"eventCandidates": [{"id": event_id, "description": "候选", **handler}]}
    catalog = business.BusinessContext.from_task(task)
    assert catalog.candidate_payload().get("actions", {}).get(event_id) == expected

    def unexpected(_action):
        raise AssertionError("Already classified action must be reused")

    monkeypatch.setattr(business, "_action_business", unexpected)
    rows = [ComponentRow("button", "CardButton", {"onClick": [handler], "label": "打开"})]
    assert catalog.visible(rows).single == expected


def test_plan_contains_business_metadata_but_not_visual_preferences():
    raw = sleep_task("展示昨夜数据，深色背景")
    before = copy.deepcopy(raw)
    typed = TaskSpec.model_validate(raw)
    catalog = PromptBuilder.business_context(typed)
    prompt = PromptBuilder().build_compact_plan(
        typed, "布局合同", "原始请求", business_context=catalog,
    )
    stage = prompt[-1].get("content", "")
    payload = json.loads(stage.split("<business_context>", 1)[1].split("</business_context>")[0])
    assert payload.get("data", {}).get("/data/healthSport/sleepScore") == "sleep"
    assert "preferences" not in payload
    assert "backgroundTone" not in payload
    assert "深色" not in json.dumps(payload, ensure_ascii=False)
    assert "仅帮助理解已登记候选" in stage
    assert raw == before
    assert "businessContext" not in typed.model_dump()
    assert PromptBuilder._visual_route(typed)[0] == catalog.layout_route


@pytest.mark.parametrize("layout", ["left", "right", "top"])
def test_main_and_auxiliary_businesses_come_from_final_regions(layout):
    saved = focus_sample("weather", lines=1, layout=layout)
    catalog = business.BusinessContext.from_task(sleep_task())
    finalized = business.FinalBusinessContext.from_layout(saved.compact, catalog)
    primary = "primary" if layout == "top" else "main"
    assert finalized.scope(primary).single == "weather"
    assert finalized.payload().get("primaryBusiness") == "weather"
    assert finalized.payload().get("primaryRegionId") == primary
    assert themes.photo_reason(
        photo("photo-ux-wave-wide"), saved.task, evidence(saved),
        final_layout=saved.compact, business_context=finalized,
    ) is None
    assert finalized.scope(primary).single != "sleep"


def test_split_panels_have_no_primary_business():
    saved = split_sample()
    context = business.FinalBusinessContext.from_layout(
        saved.compact, business.BusinessContext.from_task(saved.task),
    )
    assert context.payload().get("primaryRegionId") is None
    assert context.payload().get("primaryBusiness") is None
    assert context.scope().single is None
    assert context.scope().data_businesses == {"weather", "battery"}


@pytest.mark.parametrize("first,second", [("unknown", "sleep"), ("battery", "weather")])
def test_first_business_is_not_replaced_by_later_or_candidate_business(first, second):
    saved = mixed_sample(first, second)
    context = business.FinalBusinessContext.from_layout(
        saved.compact, business.BusinessContext.from_task(sleep_task()),
    )
    assert context.scope().first == (None if first == "unknown" else first)
    assert context.scope().single is None


def test_unused_candidates_do_not_count():
    saved = sample(PATHS.get("weather"), 1, button=False)
    context = business.FinalBusinessContext.from_layout(
        saved.compact, business.BusinessContext.from_task(sleep_task()),
    )
    assert context.scope().ordered == ("weather",)
    assert context.scope().single == "weather"


@pytest.mark.parametrize("invalid", [
    None, "invalid-json",
    '["root","Column",{},["missing"]]',
    '["root","Column",{},["root"]]',
])
def test_unavailable_or_incomplete_final_layout_has_no_business(invalid):
    context = business.FinalBusinessContext.from_layout(
        invalid, business.BusinessContext.from_task(sleep_task()),
    )
    assert context.scope().single is None
    assert context.payload().get("complete") is False


def test_theme_reuses_prepared_catalog_and_classifies_each_scope_once(monkeypatch):
    saved = sample(PATHS.get("sleep"), 1)
    saved.task = sleep_task("展示昨夜数据")
    catalog = PromptBuilder.business_context(TaskSpec.model_validate(saved.task))

    def unexpected(*_args):
        raise AssertionError("Theme must reuse the prepared business context")

    monkeypatch.setattr(business, "_path_business", unexpected)
    monkeypatch.setattr(themes, "prepare_business_context", unexpected)
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", True)
    client = SimpleNamespace(generate=AsyncMock(return_value=reply([])))
    before = copy.deepcopy(saved)
    result, audit = asyncio.run(themes.select_theme(
        saved.source, saved.task, client, final_layout=saved.compact, business_context=catalog,
    ))
    client.generate.assert_awaited_once()
    payload = json.loads(client.generate.call_args.args[0][1].get("content"))
    assert payload.get("layoutSummary", {}).get("businessSummary") == audit.get("businessSummary")
    assert audit.get("businessSummary", {}).get("singleBusiness") == "sleep"
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)
    assert saved == before


@pytest.mark.parametrize("wide", [False, True])
def test_visual_preferences_remain_in_theme_call(monkeypatch, wide):
    saved = sample(PATHS.get("weather"), 2, wide=wide)
    saved.task["userQuery"] = "天气，底色压暗一些"
    catalog = policy.prepare_business_context(saved.task)
    items = [preference("backgroundTone", "dark", "底色压暗一些")]
    client = SimpleNamespace(generate=AsyncMock(return_value=reply(items)))
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", True)
    result, audit = asyncio.run(themes.select_theme(
        saved.source, saved.task, client, final_layout=saved.compact, business_context=catalog,
    ))
    client.generate.assert_awaited_once()
    assert audit.get("userPreferences") == items
    assert audit.get("userColors", {}).get("background", {}).get("tone") == "dark"
    assert audit.get("businessSummary", {}).get("firstBusiness") == "weather"
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


@pytest.mark.parametrize("query", ["看看昨夜的数据", "运动后的昨夜数据", "会议提醒之后的监测"])
def test_sleep_fusion_uses_final_business_instead_of_request_keywords(query):
    task = sleep_task(query)
    context = PromptBuilder.business_context(TaskSpec.model_validate(task))
    gate = policy.fusion_candidate_gate(task, sleep_layout(), context)
    assert gate.get("allowedTokens") == ["fusion-ball-sleep-violet"]


def test_heart_rate_metadata_does_not_enable_sport_fusion():
    context = business.BusinessContext(layout_route="health-readout")
    facts = context.visible([
        ComponentRow("value", "Text", {"content": {"path": "/data/healthSport/heartRate"}}),
        ComponentRow("time", "Text", {"content": {"path": "/data/healthSport/updatedAt"}}),
    ])
    task = TaskSpec(
        size="2x2", userQuery="显示运动心率", dataModelSchema={"data": {"healthSport": {}}},
    )
    assert policy._business_token(task, facts, context) is None


def test_existing_calendar_countdown_route_keeps_countdown_fusion():
    task = TaskSpec(
        size="2x2", userQuery="距离国庆还有几天",
        dataModelSchema={"data": {"calendar": {
            "countdownDays": {"type": "integer", "sampleValue": 12},
        }}},
    )
    context = PromptBuilder.business_context(task)
    assert context.layout_route == "countdown"
    facts = context.visible([
        ComponentRow("value", "Text", {"content": {"path": "/data/calendar/countdownDays"}}),
    ])
    assert policy._business_token(task, facts, context) == "fusion-ball-sport-orange"


@pytest.mark.asyncio
@pytest.mark.parametrize("plan_format", ["plain", "invalid_then_json"])
async def test_generation_passes_same_context_to_plan_and_theme(
    monkeypatch, isolated_theme_stage, plan_format,
):
    seen = {}
    original = PromptBuilder.build_compact_plan

    def plan(self, *args, **kwargs):
        seen["plan"] = kwargs.get("business_context")
        return original(self, *args, **kwargs)

    async def theme(artifact, *_args, **kwargs):
        seen["theme"] = kwargs.get("business_context")
        assert "businessContext" not in artifact.taskSpec
        return artifact

    monkeypatch.setattr(PromptBuilder, "build_compact_plan", plan)
    monkeypatch.setattr(themes, "theme_artifact", theme)
    await run_plan_flow(monkeypatch, plan_format)
    assert isinstance(seen.get("plan"), business.BusinessContext)
    assert seen.get("plan") is seen.get("theme")

