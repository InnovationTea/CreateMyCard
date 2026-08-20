"""模板路由独立模块的关键边界和天气 POC。"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from api.schemas import GenerateWidgetCardRequest
from core.errors import GenerationStatus
from models.generation import CandidateDataBinding, EventAction, TaskSpec
from models.service import ArtifactSaveResult
from services import widget_generation_service as widget_generation_service_module
from services.artifact_store import ArtifactStore
from services.generation_pipeline import (
    DslProcessorKind,
    GenerationRoutePolicy,
)
from services.protocol_registry import (
    A2UI_FORM_PROTOCOL_PROFILE_ID,
    TERSE_DSL_NESTED2_PROFILE_ID,
    A2UIProtocolRegistry,
)
from services.template_generation import (
    facade,
    route_legacy_python_terse_generation,
)
from services.template_generation.binding_dependencies import enrich_template_bindings
from services.template_generation.controls import TemplateControls, load_template_controls
from services.template_generation.engine.advanced.content_selectors import (
    app_usage_overview_is_eligible,
    app_usage_overview_query_is_supported,
    apply_content_selectors,
    extract_workout_latest_facts,
)
from services.template_generation.engine.advanced.data_shape import extract_data_shape
from services.template_generation.engine.advanced.models import (
    AdvancedScopeBrief,
    TemplateComponentCandidate,
    TemplateRouteDecision,
)
from services.template_generation.engine.advanced.scope_planner import (
    TemplateRouteNotApplicable,
    build_advanced_scope_prompt,
    validate_template_request_coverage,
)
from services.template_generation.engine.cardplan import registry as cardplan_registry_module
from services.template_generation.engine.cardplan.compiler import (
    _inject_resource_battery_title,
    _provider_layout_action_background,
)
from services.template_generation.engine.cardplan.models import HybridBodyContract, HybridLimits
from services.template_generation.engine.cardplan.registry import (
    CardPlanRegistry,
    get_cardplan_registry,
)
from services.template_generation.engine.pipeline import (
    TemplateGenerationError,
    generate_template_a2ui,
)
from services.template_generation.engine.terse_dsl_nested2_converter import Nested2Node
from services.widget_generation_service import WidgetGenerationService

_WEATHER_BODY = (
    'Template("SingleFocusLayout@1",{},Template("WeatherOverviewHeroIcon@1",'
    '{"conditionIcon":"resources/base/media/icon_weather1.svg"}));'
)
_WEATHER_TEMPLATE_FIELDS = (
    "/location/districtName",
    "/current/temperatureText",
    "/current/condition",
    "/current/airQuality",
    "/daily/0/temperatureRangeText",
)


@pytest.fixture(autouse=True)
def enable_all_templates_for_isolated_unit_tests(monkeypatch):
    """Keep capability tests independent from the checked-in operational denylist."""
    controls = TemplateControls(schemaVersion="template-controls/1")
    monkeypatch.setattr(
        cardplan_registry_module,
        "load_template_controls",
        lambda: controls,
    )
    get_cardplan_registry.cache_clear()
    yield
    get_cardplan_registry.cache_clear()


def test_all_provider_templates_are_loaded_from_the_isolated_directory():
    registry = get_cardplan_registry()
    provider_directories = {
        path.name
        for path in (registry.source_root / "providers").iterdir()
        if path.is_dir()
    }

    assert len(registry.provider_template_ids) == 86
    assert {
        "ActivityOverviewSteps@1",
        "AppUsageOverviewSingleApp@1",
        "BatteryOverviewNormal@1",
        "BatteryOverviewNormalHero@1",
        "BluetoothDeviceOverviewEarbuds@1",
        "CountdownOverview@1",
        "DateOverviewDateHero@1",
        "HeartRateOverviewHero@1",
        "ResourceUsageOverviewMemory@1",
        "ScheduleOverviewNextEvent@1",
        "SleepOverviewDuration@1",
        "SleepOverviewDurationScore@1",
        "WeatherOverviewHero@1",
        "WorkoutOverview@1",
        "SingleFocusLayout@1",
    }.issubset(registry.provider_template_ids)
    assert provider_directories == {
        "app-usage",
        "battery",
        "calendar",
        "countdown",
        "earphone",
        "health-sport",
        "layout",
        "system-memory",
        "weather",
    }
    provider_sources = tuple((registry.source_root / "providers").glob("*/templates/*.cardtpl"))
    assert provider_sources
    provider_source_texts = tuple(path.read_text(encoding="utf-8") for path in provider_sources)
    assert all("#Variant" not in source for source in provider_source_texts)
    assert all("IfParam" not in source for source in provider_source_texts)
    assert all("IfMissingParam" not in source for source in provider_source_texts)
    assert any("IfPresent" in source for source in provider_source_texts)
    assert any("IfAbsent" in source for source in provider_source_texts)
    assert all(
        definition.variants[0].size == "default"
        for template_id in registry.provider_template_ids
        for definition in (registry.require_template(template_id),)
    )


def test_every_provider_asset_prop_has_second_layer_semantic_description():
    registry = get_cardplan_registry()
    providers_root = registry.source_root / "providers"
    for provider_root in sorted(path for path in providers_root.iterdir() if path.is_dir()):
        manifest = json.loads((provider_root / "provider.json").read_text(encoding="utf-8"))
        rule = manifest.get("secondLayerRule")
        if not isinstance(rule, dict):
            continue
        rule_text = (provider_root / rule["path"]).read_text(encoding="utf-8")
        template_paths = {
            item["entry"]
            for item in manifest["templates"]
            if isinstance(item.get("entry"), str)
        }
        source = "\n".join(
            (provider_root / path).read_text(encoding="utf-8")
            for path in sorted(template_paths)
        )
        asset_props = set(
            re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\??\s*:\s*asset", source)
        )
        missing = sorted(name for name in asset_props if name not in rule_text)
        assert not missing, f"{provider_root.name} asset props lack descriptions: {missing}"


def test_workout_template_requires_one_complete_training_session():
    registry = get_cardplan_registry()
    definition = registry.require_template("WorkoutOverview@1")

    assert definition.required_data == (
        "/exerciseTypeName",
        "/exerciseCalorieText",
        "/exerciseDurationText",
        "/exerciseEndTimeText",
    )
    assert set(definition.variants[0].parameters_schema["properties"]) == {"sourceIcon"}

    session = {
        "exerciseTypeName": {
            "type": "string",
            "description": "最近运动类型",
            "sampleValue": "户外跑步",
        },
        "exerciseCalorieText": {
            "type": "string",
            "description": "最近运动热量",
            "sampleValue": "260 千卡",
        },
        "exerciseDurationText": {
            "type": "string",
            "description": "最近运动时长",
            "sampleValue": "40分",
        },
        "exerciseEndTimeText": {
            "type": "string",
            "description": "最近运动结束时间",
            "sampleValue": "19:10",
        },
    }
    facts = extract_workout_latest_facts({"data": {"healthSport": session}})
    assert facts is not None
    assert facts.end_time_text == "19:10"

    incomplete = {key: value for key, value in session.items() if key != "exerciseEndTimeText"}
    assert extract_workout_latest_facts({"data": {"healthSport": incomplete}}) is None


def test_first_layer_receives_workout_session_routing_rules_and_four_required_paths():
    session = {
        "exerciseTypeName": {
            "type": "string",
            "description": "最近运动类型",
            "sampleValue": "户外跑步",
        },
        "exerciseCalorieText": {
            "type": "string",
            "description": "最近运动热量",
            "sampleValue": "260 千卡",
        },
        "exerciseDurationText": {
            "type": "string",
            "description": "最近运动时长",
            "sampleValue": "40分",
        },
        "exerciseEndTimeText": {
            "type": "string",
            "description": "最近运动结束时间",
            "sampleValue": "19:10",
        },
    }
    task_spec = TaskSpec(
        userQuery="查看最近一次户外跑步的时长和热量",
        size="2x2",
        eventCandidates=[],
        assetCandidates=[],
        dataModelSchema={"data": {"healthSport": session}},
    )
    binding = CandidateDataBinding(
        capabilityId="GetHealthAndSportSummary",
        writeResultTo="/data/healthSport",
        candidateOutputFields=[f"/{name}" for name in session],
    )

    messages = build_advanced_scope_prompt(
        task_spec,
        extract_data_shape(task_spec),
        get_cardplan_registry(),
        ("GetHealthAndSportSummary",),
        template_route_decision=True,
        coverage_bindings=(binding,),
        card_spec={
            "title": "最近运动",
            "suggestSize": "2x2",
            "dataBindings": [
                {
                    "capabilityId": "GetHealthAndSportSummary",
                    "writeResultTo": "/data/healthSport",
                }
            ],
        },
    )

    payload = json.loads(messages[1]["content"])
    workout = next(
        item
        for item in payload["componentCatalog"]
        if item["componentId"] == "WorkoutOverview"
    )
    template = next(
        item for item in workout["templates"] if item["templateId"] == "WorkoutOverview@1"
    )
    assert template["requiredTaskSpecPaths"] == [
        "/data/healthSport/exerciseTypeName",
        "/data/healthSport/exerciseCalorieText",
        "/data/healthSport/exerciseDurationText",
        "/data/healthSport/exerciseEndTimeText",
    ]
    provider_rules = json.dumps(payload["providerFirstLayerRules"], ensure_ascii=False)
    assert "最近一次特定运动训练会话" in provider_rules
    assert "ActivityOverview` 默认互斥" in provider_rules


def test_first_layer_uses_candidate_provider_and_theme_documents_with_task_spec_paths():
    registry = get_cardplan_registry()
    task_spec = _weather_task_spec().model_copy(
        update={
            "eventCandidates": [
                EventAction(
                    id="event.open.weather",
                    call="clickToDeeplink",
                    args={
                        "intentName": "Weather_CityCode",
                        "uri": (
                            "{{ 'hww://www.huawei.com/totemweather?enterType=share&cityCode=' "
                            "+ ${/data/weather/location/cityCode} }}"
                        ),
                    },
                )
            ]
        }
    )
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        writeResultTo="/data/weather",
        candidateOutputFields=list(_WEATHER_TEMPLATE_FIELDS),
    )

    messages = build_advanced_scope_prompt(
        task_spec,
        extract_data_shape(task_spec),
        registry,
        ("ViewWeather",),
        template_route_decision=True,
        coverage_bindings=(binding,),
        card_spec=_weather_card_spec(),
    )

    system = messages[0]["content"]
    payload = json.loads(messages[1]["content"])
    assert set(json.loads(system.splitlines()[-1])["properties"]) == {
        "theme",
        "componentCandidates",
        "action",
    }
    assert "Action 是点击或跳转动作，不是数据项" in system
    assert "requiredOutputFieldsByCapability" not in system
    assert "不得判断 Action 属于哪个 component" in system
    assert "明确要求交互但 action 候选中没有语义匹配的 eventId" in system
    assert '"componentCandidates":[]' in system
    assert '"theme":null' not in system
    assert payload["action"] == [
        {"eventId": "event.open.weather", "call": "clickToDeeplink"}
    ]
    assert (
        "/data/weather/current/temperatureText"
        in payload["componentCatalog"][0]["supportedTaskSpecPaths"]
    )
    weather_candidate = payload["componentCatalog"][0]
    assert weather_candidate["componentId"] == "WeatherOverview"
    assert "WeatherOverviewHero@1" in weather_candidate["availableTemplateIds"]
    weather_templates = weather_candidate["templates"]
    assert any(
        item["templateId"] == "WeatherOverviewHero@1"
        and "/data/weather/current/temperatureText" in item["requiredTaskSpecPaths"]
        for item in weather_templates
    )
    provider_rules = json.dumps(payload["providerFirstLayerRules"], ensure_ascii=False)
    theme_rules = json.dumps(payload["themeFirstLayerRules"], ensure_ascii=False)
    assert "天气高级组件首层规则" in provider_rules
    assert "手机电量高级组件首层规则" not in provider_rules
    assert "family-weather-care-blue" in theme_rules
    assert "system-low-power-blue" not in theme_rules


def test_disabled_weather_provider_is_not_exposed_to_first_layer():
    registry = CardPlanRegistry(
        disabled_provider_ids=("com.huawei.weather.cli",),
    )
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        writeResultTo="/data/weather",
        candidateOutputFields=list(_WEATHER_TEMPLATE_FIELDS),
    )

    with pytest.raises(ValueError, match="no provider-backed UX Business Component candidate"):
        build_advanced_scope_prompt(
            _weather_task_spec(),
            extract_data_shape(_weather_task_spec()),
            registry,
            ("ViewWeather",),
            template_route_decision=True,
            coverage_bindings=(binding,),
            card_spec=_weather_card_spec(),
        )


def test_disabled_weather_template_is_hidden_from_both_llm_layers():
    disabled_template_id = "WeatherOverviewHero@1"
    registry = CardPlanRegistry(
        disabled_template_ids=(disabled_template_id,),
    )
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        writeResultTo="/data/weather",
        candidateOutputFields=list(_WEATHER_TEMPLATE_FIELDS),
    )
    messages = build_advanced_scope_prompt(
        _weather_task_spec(),
        extract_data_shape(_weather_task_spec()),
        registry,
        ("ViewWeather",),
        template_route_decision=True,
        coverage_bindings=(binding,),
        card_spec=_weather_card_spec(),
    )
    first_layer_content = json.dumps(messages, ensure_ascii=False)
    second_layer_rules = json.dumps(
        registry.provider_second_layer_rules(("WeatherOverview",)),
        ensure_ascii=False,
    )

    assert disabled_template_id not in first_layer_content
    assert disabled_template_id not in second_layer_rules
    assert "WeatherOverviewHeroIcon@1" in first_layer_content
    assert "WeatherOverviewHeroIcon@1" in second_layer_rules


def test_disabled_template_cannot_be_restored_by_first_layer_output():
    registry = CardPlanRegistry(
        disabled_template_ids=("WeatherOverviewHero@1",),
    )
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        writeResultTo="/data/weather",
        candidateOutputFields=list(_WEATHER_TEMPLATE_FIELDS),
    )
    scope = AdvancedScopeBrief(
        themeId="family-weather-care-blue",
        advancedComponentIds=("WeatherOverview",),
    )
    component_candidates = (
        TemplateComponentCandidate(
            componentId="WeatherOverview",
            availableTemplateIds=("WeatherOverviewHero@1",),
        ),
    )

    with pytest.raises(ValueError, match="selected an unavailable Provider Template"):
        validate_template_request_coverage(
            scope,
            _weather_task_spec(),
            registry,
            (binding,),
            _weather_card_spec(),
            component_candidates,
        )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            {"disabled_provider_ids": ("com.huawei.unknown.cli",)},
            "disabled Template Provider IDs are unknown",
        ),
        (
            {"disabled_template_ids": ("UnknownTemplate@1",)},
            "disabled Template IDs are unknown",
        ),
    ],
)
def test_unknown_template_controls_fail_closed(kwargs, message):
    with pytest.raises(ValueError, match=message):
        CardPlanRegistry(**kwargs)


def test_checked_in_template_controls_disable_calendar_and_earphone():
    controls = load_template_controls()
    registry = CardPlanRegistry(
        disabled_provider_ids=controls.disabled_provider_ids,
        disabled_template_ids=controls.disabled_template_ids,
    )

    assert controls.disabled_provider_ids == (
        "com.huawei.calendar.cli",
        "com.huawei.earphone.cli",
    )
    assert controls.disabled_template_ids == ()
    assert not registry.template_is_enabled("ScheduleOverviewNextEvent@1")
    assert not registry.template_is_enabled("BluetoothDeviceOverviewEarbuds@1")
    assert registry.template_is_enabled("WeatherOverviewHero@1")


def test_first_layer_decision_contract_carries_component_template_candidates():
    payload = {
        "theme": "family-weather-care-blue",
        "componentCandidates": [
            {
                "componentId": "WeatherOverview",
                "availableTemplateIds": [
                    "WeatherOverviewHero@1",
                    "WeatherOverviewCompact@1",
                ],
            },
            {
                "componentId": "ScheduleOverview",
                "availableTemplateIds": [
                    "ScheduleOverviewNextEvent@1",
                    "ScheduleOverviewNextEventLocation@1",
                ],
            },
        ],
        "action": "event.open.weather",
    }

    decision = TemplateRouteDecision.model_validate(payload)

    assert decision.component_ids == ("WeatherOverview", "ScheduleOverview")
    assert decision.model_dump(mode="json", by_alias=True) == payload


def test_phone_battery_binding_auto_includes_numeric_soc_for_template_rendering():
    binding = CandidateDataBinding(
        capabilityId="GetPhoneBatteryInfo",
        arguments={},
        writeResultTo="/data/phoneBattery",
        candidateOutputFields=["/batterySOCText", "/chargingStatusDesc"],
    )

    effective = enrich_template_bindings([binding])

    assert effective[0].candidateOutputFields == [
        "/batterySOCText",
        "/chargingStatusDesc",
        "/batterySOC",
    ]


def test_provider_data_domain_must_match_card_spec_write_root():
    registry = get_cardplan_registry()
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        writeResultTo="/data/customWeather",
        candidateOutputFields=list(_WEATHER_TEMPLATE_FIELDS),
    )
    card_spec = _weather_card_spec()
    card_spec["dataBindings"][0]["writeResultTo"] = "/data/customWeather"
    scope = AdvancedScopeBrief(
        themeId="family-weather-care-blue",
        advancedComponentIds=["WeatherOverview"],
    )

    with pytest.raises(ValueError, match="no applicable Provider Template"):
        validate_template_request_coverage(
            scope,
            _weather_task_spec(),
            registry,
            (binding,),
            card_spec,
        )


def _template_node_options(node: Any) -> dict[str, Any]:
    value = node.values[-1]
    assert value.kind == "object"
    return {
        key: item.value
        for key, item in value.properties.items()
        if item.kind == "literal"
    }


def _template_nodes(node: Any, component: str) -> list[Any]:
    matches = [node] if node.component == component else []
    for child in node.children:
        matches.extend(_template_nodes(child, component))
    return matches


def test_pr6_bluetooth_action_background_is_owned_by_cardtpl_metadata():
    registry = get_cardplan_registry()
    definition = registry.require_template("BluetoothDeviceOverviewEarbuds@1")
    assert definition.layout_action_style is not None
    assert definition.layout_action_style.background_opacity == 0.1
    contract = HybridBodyContract(
        theme_profile_id="audio-product-neutral-violet",
        allowed_components=(),
        allowed_design_tokens=(),
        allowed_layout_tokens=(),
        allowed_template_ids=("BluetoothDeviceOverviewEarbuds@1",),
        required_template_groups=(("BluetoothDeviceOverviewEarbuds@1",),),
        allowed_asset_sources=(),
        trusted_literals=(),
        trusted_numbers=(),
        required_literals=(),
        protected_literals=(),
        limits=HybridLimits(
            max_raw_components=8,
            max_expanded_components=64,
            max_nesting_depth=8,
            vertical_budget_vp=128,
        ),
    )

    assert _provider_layout_action_background(
        contract,
        registry,
        foreground="#FF64BB5C",
        default="#FFFFFFFF",
    ) == "#1964BB5C"


def test_pr7_visual_fixes_are_encoded_in_provider_cardtpl_variants():
    registry = get_cardplan_registry()

    countdown = registry.require_variant("CountdownOverview@1", "default").root
    assert _template_node_options(countdown)["justifyContent"] == "start"
    assert _template_node_options(countdown.children[1])["justifyContent"] == "center"
    assert _template_node_options(countdown.children[1].children[0])["justifyContent"] == "center"

    app_usage = registry.require_variant("AppUsageOverviewSingleApp@1", "default").root
    assert _template_node_options(app_usage)["justifyContent"] == "start"
    duration_region = app_usage.children[1]
    assert _template_node_options(duration_region)["justifyContent"] == "end"
    assert "itemMargin" not in _template_node_options(duration_region)

    battery = registry.require_variant("BatteryOverviewNormal@1", "default").root
    assert _template_node_options(battery.children[1])["fontColor"] == "#99000000"
    battery_hero = registry.require_variant("BatteryOverviewNormalHero@1", "default").root
    battery_wide = registry.require_variant("BatteryOverviewNormalWide@1", "default").root
    assert battery_hero == battery_wide
    assert _template_node_options(battery_hero)["justifyContent"] == "start"
    assert battery_hero.children[1].component == "Row"
    assert _template_node_options(battery_hero.children[1])["layoutWeight"] == 1
    assert _template_node_options(_template_nodes(battery_hero, "Progress")[0])["width"] == 52
    battery_peer = registry.require_variant("BatteryOverviewNormalPeer@1", "default").root
    assert _template_node_options(battery_peer)["justifyContent"] == "end"
    assert _template_node_options(_template_nodes(battery_peer, "Image")[0])["width"] == 20

    resource_peer = registry.require_variant(
        "ResourceUsageOverviewMemoryPeer@1",
        "default",
    ).root
    assert _template_node_options(resource_peer)["justifyContent"] == "end"
    assert _template_node_options(_template_nodes(resource_peer, "Image")[0])["width"] == 20
    percent_row = resource_peer.children[1]
    assert _template_node_options(percent_row.children[0])["fontWeight"] == 700
    assert not _template_nodes(resource_peer.children[0], "Text")

    activity = registry.require_variant("ActivityOverviewDailySummary@1", "default").root
    activity_text_options = [
        _template_node_options(node) for node in _template_nodes(activity, "Text")
    ]
    assert all(options["fontColor"] != "#E6000000" for options in activity_text_options)
    assert sum(options.get("minFontSize") == 10 for options in activity_text_options) == 2


def test_pr7_resource_battery_outer_title_keeps_the_reviewed_subtext_style():
    registry = get_cardplan_registry()
    contract = HybridBodyContract(
        theme_profile_id="device-clean-blue-teal",
        allowed_components=(),
        allowed_design_tokens=(),
        allowed_layout_tokens=(),
        allowed_template_ids=(
            "BatteryOverviewNormalPeer@1",
            "ResourceUsageOverviewMemoryPeer@1",
        ),
        required_template_groups=(
            ("BatteryOverviewNormalPeer@1",),
            ("ResourceUsageOverviewMemoryPeer@1",),
        ),
        allowed_asset_sources=(),
        trusted_literals=("设备资源",),
        trusted_numbers=(),
        required_literals=(),
        protected_literals=(),
        limits=HybridLimits(
            max_raw_components=8,
            max_expanded_components=64,
            max_nesting_depth=8,
            vertical_budget_vp=128,
        ),
    )
    result = _inject_resource_battery_title(
        Nested2Node("Row", ("between", {}), ()),
        "设备资源",
        contract,
        registry,
        size="2x2",
    )

    title_options = result.children[0].values[2]
    assert title_options["fontWeight"] == 400
    assert title_options["fontColor"] == "#99182431"


@pytest.mark.asyncio
async def test_derived_parameter_source_field_is_counted_as_template_coverage():
    def field(value: str) -> dict[str, Any]:
        return {
            "type": "string",
            "description": "trusted app usage field",
            "sampleValue": value,
        }

    registry = get_cardplan_registry()
    task_spec = TaskSpec(
        userQuery="帮我做个应用时长卡片，可以查看抖音应用用了多久",
        size="2x2",
        eventCandidates=[],
        assetCandidates=[],
        dataModelSchema={
            "data": {
                "appUsageStats": {
                    "appUsage": {
                        "appName": field("示例应用"),
                        "durationText": field("1小时20分钟"),
                    }
                }
            }
        },
    )
    task_spec = apply_content_selectors(task_spec, {"GetAppUsageDuration"})
    assert app_usage_overview_is_eligible(task_spec, {"GetAppUsageDuration"})
    for query in (
        "帮我做个防沉迷卡片，看看抖音应用今天用了多久",
        "帮我做个应用时长卡片，可以查看抖音应用用了多久",
        "帮我做个应用时长卡片，可以查看抖音今天用了多久",
    ):
        assert app_usage_overview_is_eligible(
            task_spec.model_copy(update={"userQuery": query}),
            {"GetAppUsageDuration"},
        )
    binding = CandidateDataBinding(
        capabilityId="GetAppUsageDuration",
        writeResultTo="/data/appUsageStats",
        candidateOutputFields=[
            "/appUsage/appName",
            "/appUsage/durationText",
        ],
    )
    scope = AdvancedScopeBrief(
        themeId="digital-wellbeing-neutral-dark",
        advancedComponentIds=["AppUsageOverview"],
    )
    card_spec = {
        "title": "应用时长",
        "description": "今日使用情况",
        "suggestSize": "2x2",
        "dataBindings": [
            {
                "capabilityId": "GetAppUsageDuration",
                "arguments": {},
                "writeResultTo": "/data/appUsageStats",
            }
        ],
    }

    validate_template_request_coverage(
        scope,
        task_spec,
        registry,
        (binding,),
        card_spec,
    )

    class AppUsageTemplateModel:
        async def generate_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return {
                "theme": "digital-wellbeing-neutral-dark",
                "componentCandidates": [
                    {
                        "componentId": "AppUsageOverview",
                        "availableTemplateIds": ["AppUsageOverviewSingleApp@1"],
                    }
                ],
                "action": None,
            }

        async def generate(self, *_args: Any, **_kwargs: Any) -> str:
            return (
                'Template("SingleFocusLayout@1",{},'
                'Template("AppUsageOverviewSingleApp@1",{}));'
            )

    output = await generate_template_a2ui(
        task_spec,
        card_spec,
        (binding,),
        AppUsageTemplateModel(),
    )
    projected_data = output.projected_task_spec.dataModelSchema["data"]
    assert "AppUsageOverview" not in projected_data
    assert (
        projected_data["appUsageStats"]["_templateProjection"]["AppUsageOverview"]
        ["durationPrimaryValueText"]["sampleValue"]
        == "1"
    )
    assert "/updatedAt" not in output.a2ui


def test_placeholder_app_name_still_rejects_an_obvious_multi_app_query():
    assert not app_usage_overview_query_is_supported(
        "看看抖音和微信今天用了多久",
        "示例应用",
    )


def _provider_field(value: Any, field_type: str) -> dict[str, Any]:
    return {
        "type": field_type,
        "description": "trusted provider field",
        "sampleValue": value,
    }


@pytest.mark.asyncio
async def test_q094_sleep_duration_score_and_steps_are_all_preserved():
    task_spec = TaskSpec(
        userQuery="刚睡醒，看看昨晚睡了多久、睡眠得分和今天走了多少步",
        size="2x2",
        eventCandidates=[],
        assetCandidates=[
            {
                "src": "resources/base/media/moon_z_fill_1.svg",
                "description": "睡眠和夜间月亮图标",
                "sceneTags": ["sleep", "night"],
            },
            {
                "src": "resources/base/media/figure_run.svg",
                "description": "跑步、步数和日常活动图标",
                "sceneTags": ["health", "sport"],
            },
        ],
        dataModelSchema={
            "data": {
                "healthSport": {
                    "sleepScore": _provider_field(82, "integer"),
                    "nightSleepDurationText": _provider_field("7小时1分", "string"),
                    "dailySteps": _provider_field(6200, "integer"),
                    "dailyTotalCaloriesText": _provider_field("420 千卡", "string"),
                    "dailyDistanceText": _provider_field("4.60 公里", "string"),
                }
            }
        },
    )
    binding = CandidateDataBinding(
        capabilityId="GetHealthAndSportSummary",
        writeResultTo="/data/healthSport",
        candidateOutputFields=[
            "/sleepScore",
            "/nightSleepDurationText",
            "/dailySteps",
        ],
    )
    card_spec = {
        "title": "晨间健康",
        "description": "睡眠健康速览",
        "suggestSize": "2x2",
        "dataBindings": [
            {
                "capabilityId": "GetHealthAndSportSummary",
                "arguments": {"targetDayOffset": 0},
                "writeResultTo": "/data/healthSport",
            }
        ],
    }

    class Q094TemplateModel:
        first_layer_prompt: list[dict[str, str]] | None = None
        second_layer_prompt: list[dict[str, str]] | None = None

        async def generate_json(
            self,
            prompt: list[dict[str, str]],
            **_kwargs: Any,
        ) -> dict[str, Any]:
            self.first_layer_prompt = prompt
            return {
                "theme": "race-sunrise-action",
                "componentCandidates": [
                    {
                        "componentId": "ActivityOverview",
                        "availableTemplateIds": ["ActivityOverviewSteps@1"],
                    },
                    {
                        "componentId": "SleepOverview",
                        "availableTemplateIds": ["SleepOverviewDurationScoreSupport@1"],
                    },
                ],
                "action": None,
            }

        async def generate(
            self,
            prompt: list[dict[str, str]],
            *_args: Any,
            **_kwargs: Any,
        ) -> str:
            self.second_layer_prompt = prompt
            return (
                'Template("HeroSupportLayout@1",{},'
                'Template("ActivityOverviewSteps@1",'
                '{"stepsIcon":"resources/base/media/figure_run.svg"}),'
                'Template("SleepOverviewDurationScoreSupport@1",{}));'
            )

    model = Q094TemplateModel()
    output = await generate_template_a2ui(task_spec, card_spec, (binding,), model)

    assert output.template_ids == (
        "ActivityOverviewSteps@1",
        "SleepOverviewDurationScoreSupport@1",
        "HeroSupportLayout@1",
    )
    assert all(
        field in output.a2ui
        for field in ("dailySteps", "nightSleepDurationText", "sleepScore")
    )
    assert "#FFED6F21" in output.a2ui
    assert model.first_layer_prompt is not None
    first_layer_payload = json.loads(model.first_layer_prompt[1]["content"])
    sleep_component = next(
        item
        for item in first_layer_payload["componentCatalog"]
        if item["componentId"] == "SleepOverview"
    )
    assert "/data/healthSport/sleepScore" in sleep_component["supportedTaskSpecPaths"]
    assert model.second_layer_prompt is not None
    second_layer_user = model.second_layer_prompt[1]["content"]
    assert "没有合适候选时省略可选参数" in second_layer_user
    assert "caloriesIcon" in second_layer_user and "distanceIcon" in second_layer_user


class _FixedTemplateModel:
    def __init__(
        self,
        *,
        theme_id: str,
        component_id: str,
        available_template_ids: tuple[str, ...],
        body: str,
        action_id: str | None = None,
    ) -> None:
        self.theme_id = theme_id
        self.component_id = component_id
        self.available_template_ids = available_template_ids
        self.action_id = action_id
        self.body = body
        self.second_layer_prompt: list[dict[str, str]] | None = None

    async def generate_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {
            "theme": self.theme_id,
            "componentCandidates": [
                {
                    "componentId": self.component_id,
                    "availableTemplateIds": self.available_template_ids,
                }
            ],
            "action": self.action_id,
        }

    async def generate(
        self,
        prompt: list[dict[str, str]],
        *_args: Any,
        **_kwargs: Any,
    ) -> str:
        self.second_layer_prompt = prompt
        return self.body


def _bluetooth_task(query: str) -> TaskSpec:
    return TaskSpec(
        userQuery=query,
        size="2x2",
        eventCandidates=[],
        assetCandidates=[],
        dataModelSchema={
            "data": {
                "earphone": {
                    "isConnected": _provider_field(True, "boolean"),
                    "earphoneName": _provider_field("示例耳机", "string"),
                    "batteryLevel": _provider_field(80, "integer"),
                    "leftBatteryLevel": _provider_field(76, "integer"),
                    "rightBatteryLevel": _provider_field(78, "integer"),
                }
            }
        },
    )


def _bluetooth_card_spec() -> dict[str, Any]:
    return {
        "title": "耳机",
        "description": "耳机连接与电量",
        "suggestSize": "2x2",
        "dataBindings": [
            {
                "capabilityId": "GetEarphoneInfo",
                "arguments": {},
                "writeResultTo": "/data/earphone",
            }
        ],
    }


def _battery_task() -> TaskSpec:
    return TaskSpec(
        userQuery="显示设备电量、正常电量和充电状态，支持开启省电模式",
        size="2x2",
        eventCandidates=[
            EventAction(
                id="event.setPowerSavingMode",
                call="clickToIntent",
                args={
                    "intentName": "SetSettingSwitch",
                    "params": {
                        "appBundleName": "com.huawei.hmos.settings",
                        "itemName": "battery_saving_mode",
                        "switchFlag": 0,
                    },
                },
            )
        ],
        assetCandidates=[
            {
                "src": "resources/base/media/battery_leaf_fill.svg",
                "description": "省电模式电池图标",
                "sceneTags": ["battery", "power-saving"],
            }
        ],
        dataModelSchema={
            "data": {
                "phoneBattery": {
                    "batterySOC": _provider_field(68, "integer"),
                    "batterySOCText": _provider_field("68%", "string"),
                    "batteryCapacityLevelDesc": _provider_field("正常电量", "string"),
                    "chargingStatusDesc": _provider_field("未充电", "string"),
                }
            }
        },
    )


def _battery_card_spec() -> dict[str, Any]:
    return {
        "title": "设备电量",
        "description": "设备电量与省电模式",
        "suggestSize": "2x2",
        "dataBindings": [
            {
                "capabilityId": "GetPhoneBatteryInfo",
                "arguments": {},
                "writeResultTo": "/data/phoneBattery",
            }
        ],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "required_fields", "variant", "expected_path"),
    [
        (
            "看一下耳机的连接状态是否为已连接",
            ("/isConnected",),
            "connection",
            "isConnected",
        ),
        (
            "看看我的蓝牙耳机连上没有，用电量环显示耳机盒还剩多少电",
            ("/isConnected", "/batteryLevel"),
            "earbuds",
            "batteryLevel",
        ),
    ],
)
async def test_bluetooth_connection_and_case_queries_have_honest_template_coverage(
    query: str,
    required_fields: tuple[str, ...],
    variant: str,
    expected_path: str,
):
    binding = CandidateDataBinding(
        capabilityId="GetEarphoneInfo",
        writeResultTo="/data/earphone",
        candidateOutputFields=list(required_fields),
    )
    model = _FixedTemplateModel(
        theme_id="audio-product-neutral-violet",
        component_id="BluetoothDeviceOverview",
        available_template_ids=(
            f"BluetoothDeviceOverview{variant[:1].upper() + variant[1:]}@1",
        ),
        body=(
            'Template("SingleFocusLayout@1",{},Template('
            f'"BluetoothDeviceOverview{variant[:1].upper() + variant[1:]}@1",{{}}));'
        ),
    )

    output = await generate_template_a2ui(
        _bluetooth_task(query),
        _bluetooth_card_spec(),
        (binding,),
        model,
    )

    expected_template = f"BluetoothDeviceOverview{variant[:1].upper() + variant[1:]}@1"
    assert output.template_ids == (expected_template, "SingleFocusLayout@1")
    assert "isConnected" in output.a2ui
    assert expected_path in output.a2ui
    assert "已连接" in output.a2ui and "未连接" in output.a2ui


@pytest.mark.asyncio
async def test_bluetooth_layout_action_uses_cardtpl_foreground_opacity():
    binding = CandidateDataBinding(
        capabilityId="GetEarphoneInfo",
        writeResultTo="/data/earphone",
        candidateOutputFields=[
            "/isConnected",
            "/earphoneName",
            "/batteryLevel",
            "/leftBatteryLevel",
            "/rightBatteryLevel",
        ],
    )
    task_spec = _bluetooth_task(
        "看看蓝牙耳机充电盒电量并打开每日推荐",
    ).model_copy(
        update={
            "eventCandidates": [
                EventAction(
                    id="event.open.music.daily",
                    displayLabel="每日推荐",
                    call="clickToIntent",
                    args={"intentName": "event.open.music.daily"},
                )
            ]
        }
    )
    model = _FixedTemplateModel(
        theme_id="audio-product-neutral-violet",
        component_id="BluetoothDeviceOverview",
        available_template_ids=("BluetoothDeviceOverviewEarbuds@1",),
        action_id="event.open.music.daily",
        body=(
            'Template("HeroActionLayout@1",{},'
            'Template("BluetoothDeviceOverviewEarbuds@1",{}),'
            'PillAction({"actionId":"event.open.music.daily"}));'
        ),
    )

    output = await generate_template_a2ui(
        task_spec,
        _bluetooth_card_spec(),
        (binding,),
        model,
    )

    assert "#1964BB5C" in output.a2ui


@pytest.mark.asyncio
async def test_2x2_battery_pill_action_uses_normal_hero_template():
    binding = CandidateDataBinding(
        capabilityId="GetPhoneBatteryInfo",
        writeResultTo="/data/phoneBattery",
        candidateOutputFields=[
            "/batterySOC",
            "/batterySOCText",
            "/batteryCapacityLevelDesc",
            "/chargingStatusDesc",
        ],
    )
    model = _FixedTemplateModel(
        theme_id="system-low-power-blue",
        component_id="BatteryOverview",
        available_template_ids=("BatteryOverviewNormalHero@1",),
        action_id="event.setPowerSavingMode",
        body=(
            'Template("HeroActionLayout@1",{},'
            'Template("BatteryOverviewNormalHero@1",'
            '{"batteryIcon":"resources/base/media/battery_leaf_fill.svg"}),'
            'PillAction({"actionId":"event.setPowerSavingMode"}));'
        ),
    )

    output = await generate_template_a2ui(
        _battery_task(),
        _battery_card_spec(),
        (binding,),
        model,
    )

    assert output.template_ids == ("BatteryOverviewNormalHero@1", "HeroActionLayout@1")
    assert model.second_layer_prompt is not None
    second_layer_user = model.second_layer_prompt[1]["content"]
    assert "2x2 手机电量摘要，为底部 PillAction 预留空间" in second_layer_user
    assert "selectedActionEventId` 非空且电量状态为 normal" in second_layer_user
    assert '"height":36' in output.a2ui
    assert "省电模式" in output.a2ui
    assert "batterySOC" in output.a2ui
    assert "chargingStatusDesc" in output.a2ui


def test_first_layer_action_candidate_exposes_only_event_identity():
    registry = get_cardplan_registry()
    task_spec = _bluetooth_task(
        "看看蓝牙耳机充电盒电量并打开每日推荐",
    ).model_copy(
        update={
            "eventCandidates": [
                EventAction(
                    id="event.open.music.daily",
                    call="clickToIntent",
                    args={"intentName": "event.open.music.daily"},
                )
            ]
        }
    )
    binding = CandidateDataBinding(
        capabilityId="GetEarphoneInfo",
        writeResultTo="/data/earphone",
        candidateOutputFields=["/isConnected", "/batteryLevel"],
    )

    messages = build_advanced_scope_prompt(
        task_spec,
        extract_data_shape(task_spec),
        registry,
        ("GetEarphoneInfo",),
        template_route_decision=True,
        coverage_bindings=(binding,),
        card_spec=_bluetooth_card_spec(),
    )

    payload = json.loads(messages[1]["content"])
    assert payload["action"] == [
        {
            "eventId": "event.open.music.daily",
            "call": "clickToIntent",
        }
    ]


@pytest.mark.asyncio
async def test_generic_countdown_query_uses_countdown_overview_without_workout_semantics():
    task_spec = TaskSpec(
        userQuery="做一张日程倒数卡片，我想看看高考还剩下多少天",
        size="2x2",
        eventCandidates=[],
        assetCandidates=[],
        dataModelSchema={
            "data": {
                "countdown": {
                    "countdownDays": _provider_field(294, "integer"),
                }
            }
        },
    )
    card_spec = {
        "title": "高考倒计时",
        "description": "高考剩余天数",
        "suggestSize": "2x2",
        "dataBindings": [
            {
                "capabilityId": "GetCountdownDays",
                "arguments": {"targetDate": "2027-06-07"},
                "writeResultTo": "/data/countdown",
            }
        ],
    }
    binding = CandidateDataBinding(
        capabilityId="GetCountdownDays",
        arguments={"targetDate": "2027-06-07"},
        writeResultTo="/data/countdown",
        candidateOutputFields=["/countdownDays"],
    )
    model = _FixedTemplateModel(
        theme_id="meeting-paper-neutral",
        component_id="CountdownOverview",
        available_template_ids=("CountdownOverview@1",),
        body='Template("SingleFocusLayout@1",{},Template("CountdownOverview@1",{}));',
    )

    output = await generate_template_a2ui(task_spec, card_spec, (binding,), model)

    assert output.template_ids == ("CountdownOverview@1", "SingleFocusLayout@1")
    assert "countdownDays" in output.a2ui
    assert "倒计时" in output.a2ui
    assert "运动倒计时" not in output.a2ui


class WeatherTemplateModel:
    def __init__(
        self,
        *,
        route_usable: bool = True,
        action_id: str | None = None,
        body: str = _WEATHER_BODY,
        available_template_ids: tuple[str, ...] = (
            "WeatherOverviewHero@1",
            "WeatherOverviewHeroIcon@1",
        ),
    ) -> None:
        self.body_called = False
        self.route_usable = route_usable
        self.action_id = action_id
        self.body = body
        self.available_template_ids = available_template_ids
        self.first_layer_prompt: list[dict[str, str]] | None = None
        self.second_layer_prompt: list[dict[str, str]] | None = None

    async def generate_json(self, prompt: list[dict[str, str]], **_kwargs: Any) -> dict[str, Any]:
        self.first_layer_prompt = prompt
        return {
            "theme": "family-weather-care-blue",
            "componentCandidates": [
                {
                    "componentId": "WeatherOverview",
                    "availableTemplateIds": self.available_template_ids,
                }
            ]
            if self.route_usable
            else [],
            "action": self.action_id if self.route_usable else None,
        }

    async def generate(
        self,
        prompt: list[dict[str, str]],
        *_args: Any,
        **_kwargs: Any,
    ) -> str:
        self.body_called = True
        self.second_layer_prompt = prompt
        return self.body


def _policy() -> GenerationRoutePolicy:
    return GenerationRoutePolicy(
        operation="generateWidgetCardCompactDsl",
        protocol_profile_id=A2UI_FORM_PROTOCOL_PROFILE_ID,
        backend="openai",
        processor_kind=DslProcessorKind.DESIGN_COMPACT,
        source_format="design-compact-dsl",
        model_profile_id="design-compact-dsl",
        model_format="compact-dsl",
        design_profile_id="design-compact-dsl",
        validation_failure_blocking=True,
        stores_design_token=True,
    )


def _terse_policy() -> GenerationRoutePolicy:
    return GenerationRoutePolicy(
        operation="generateWidgetCardTerseDslNested2",
        protocol_profile_id=A2UI_FORM_PROTOCOL_PROFILE_ID,
        backend="openai",
        processor_kind=DslProcessorKind.TERSE_NESTED2,
        source_format=TERSE_DSL_NESTED2_PROFILE_ID,
        model_profile_id=TERSE_DSL_NESTED2_PROFILE_ID,
        model_format=TERSE_DSL_NESTED2_PROFILE_ID,
        design_profile_id=TERSE_DSL_NESTED2_PROFILE_ID,
        supports_dynamic_capabilities=True,
        validation_failure_blocking=True,
        stores_design_token=True,
    )


def _weather_request() -> GenerateWidgetCardRequest:
    return GenerateWidgetCardRequest(
        uid="template-test",
        prdVer="11.7.5.205",
        device={"romVersion": "6.0"},
        userQuery="做一个天气卡片，显示城市、温度、天气、空气质量和温度范围",
        size="2x2",
        title="今日天气",
        description="天气概览",
        candidateDataBindings=[
            {
                "capabilityId": "ViewWeather",
                "arguments": {
                    "districtName": "青浦区",
                    "prefectureName": "上海市",
                    "forecastDays": 1,
                },
                "writeResultTo": "/data/weather",
                "candidateOutputFields": [
                    "/location/districtName",
                    "/current/temperatureText",
                    "/current/condition",
                    "/current/airQuality",
                    "/daily/0/temperatureRangeText",
                ],
            }
        ],
        candidateAssetIds=["asset.icon_weather1"],
    )


def _weather_task_spec() -> TaskSpec:
    def field(value: str) -> dict[str, Any]:
        return {
            "type": "string",
            "description": "weather field",
            "sampleValue": value,
        }

    return TaskSpec(
        userQuery="天气",
        size="2x2",
        eventCandidates=[],
        assetCandidates=[
            {
                "src": "resources/base/media/icon_weather1.svg",
                "description": "天气状态图标",
                "sceneTags": ["condition", "weather"],
            }
        ],
        dataModelSchema={
            "data": {
                "weather": {
                    "location": {"districtName": field("青浦区")},
                    "current": {
                        "temperatureText": field("29°C"),
                        "condition": field("多云"),
                        "airQuality": field("良"),
                    },
                    "daily": [{"temperatureRangeText": field("25° / 32°")}],
                }
            }
        },
    )


def _weather_card_spec() -> dict[str, Any]:
    return {
        "title": "今日天气",
        "description": "天气概览",
        "suggestSize": "2x2",
        "dataBindings": [
            {
                "capabilityId": "ViewWeather",
                "arguments": {
                    "districtName": "青浦区",
                    "prefectureName": "上海市",
                    "forecastDays": 1,
                },
                "writeResultTo": "/data/weather",
            }
        ],
    }


def test_template_route_prompt_exposes_exact_task_spec_paths_from_bindings():
    task_spec = apply_content_selectors(
        _weather_task_spec().model_copy(
            update={"userQuery": "看看是否下雨、现在多少度"}
        ),
        {"ViewWeather"},
    )
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        writeResultTo="/data/weather",
        candidateOutputFields=list(_WEATHER_TEMPLATE_FIELDS),
    )
    prompt = build_advanced_scope_prompt(
        task_spec,
        extract_data_shape(task_spec),
        get_cardplan_registry(),
        ("ViewWeather",),
        template_route_decision=True,
        coverage_bindings=(binding,),
        card_spec=_weather_card_spec(),
    )

    payload = json.loads(prompt[1]["content"])
    weather = next(
        item
        for item in payload["componentCatalog"]
        if item["componentId"] == "WeatherOverview"
    )
    assert "/data/weather/current/condition" in weather["supportedTaskSpecPaths"]
    assert "/data/weather/current/temperatureText" in weather["supportedTaskSpecPaths"]
    assert all("/_advancedSelectors/" not in path for path in weather["supportedTaskSpecPaths"])
    assert "candidateOutputFieldsByCapability" not in payload


@pytest.mark.asyncio
async def test_weather_template_generates_a2ui_and_compact_artifact(monkeypatch):
    model = WeatherTemplateModel()
    captured: dict[str, Any] = {}

    monkeypatch.setattr(
        facade,
        "create_template_model_client",
        lambda _runtime, _context: model,
    )

    async def save(store: ArtifactStore, artifact: Any) -> ArtifactSaveResult:
        captured["artifact"] = artifact
        captured["compact"] = store.design_token
        return ArtifactSaveResult(
            artifactUrl="https://artifact.test/weather-template",
            artifactDigest="sha256:weather-template",
        )

    monkeypatch.setattr(ArtifactStore, "save", save)
    starts: list[str] = []

    async def before_model_call(size: str) -> None:
        starts.append(size)

    response = await WidgetGenerationService(
        model_runtime=object(),
    ).generate_widget_card_compact_dsl(
        _weather_request(),
        before_model_call=before_model_call,
    )

    assert response.status == GenerationStatus.SUCCESS
    assert response.artifactUrl == "https://artifact.test/weather-template"
    assert starts == ["2x2"]
    assert model.body_called is True
    assert model.first_layer_prompt is not None
    assert model.second_layer_prompt is not None
    second_layer_user = model.second_layer_prompt[1]["content"]
    assert "providerSecondLayerRules=" in second_layer_user
    candidate_line = next(
        line for line in second_layer_user.splitlines() if line.startswith("componentCandidates=")
    )
    assert json.loads(candidate_line.removeprefix("componentCandidates=")) == [
        {
            "componentId": "WeatherOverview",
            "availableTemplateIds": [
                "WeatherOverviewHero@1",
                "WeatherOverviewHeroIcon@1",
            ],
        }
    ]
    required_group_line = next(
        line
        for line in second_layer_user.splitlines()
        if line.startswith("requiredLocalTemplateGroups=")
    )
    assert json.loads(required_group_line.removeprefix("requiredLocalTemplateGroups=")) == [
        ["WeatherOverviewHero@1", "WeatherOverviewHeroIcon@1"]
    ]
    assert "selectedActionEventId=null" in second_layer_user
    assert 'PillAction({"actionId":"<selectedActionEventId>"})' in second_layer_user
    assert "第二层业务模板使用规则" in second_layer_user
    assert "手机电量高级组件二层规则" not in second_layer_user
    assert captured["compact"]
    assert "{{ ${/data/weather/current/condition}" in captured["compact"]
    messages = [json.loads(line) for line in captured["artifact"].genui.splitlines()]
    protocol_profile = A2UIProtocolRegistry(A2UI_FORM_PROTOCOL_PROFILE_ID).get_profile()
    assert messages[0]["createSurface"]["catalogId"] == protocol_profile["catalogId"]
    root = next(
        item
        for item in messages[1]["updateComponents"]["components"]
        if item["id"] == "root"
    )
    assert root["styles"]["borderRadius"] == 18
    assert captured["artifact"].effectiveCapabilities["data"] == ["ViewWeather"]


@pytest.mark.asyncio
async def test_weather_template_generates_a2ui_and_terse_artifact(monkeypatch):
    model = WeatherTemplateModel()
    captured: dict[str, Any] = {}

    monkeypatch.setattr(
        facade,
        "create_template_model_client",
        lambda _runtime, _context: model,
    )

    async def save(store: ArtifactStore, artifact: Any) -> ArtifactSaveResult:
        captured["artifact"] = artifact
        captured["terse"] = store.design_token
        return ArtifactSaveResult(
            artifactUrl="https://artifact.test/weather-template-terse",
            artifactDigest="sha256:weather-template-terse",
        )

    monkeypatch.setattr(ArtifactStore, "save", save)
    response = await WidgetGenerationService(
        model_runtime=object(),
    ).generate_widget_card_terse_dsl_nested2(_weather_request())

    assert response.status == GenerationStatus.SUCCESS
    assert response.artifactUrl == "https://artifact.test/weather-template-terse"
    assert captured["terse"]
    assert "Column(" in captured["terse"]
    assert "Template(" not in captured["terse"]
    messages = [json.loads(line) for line in captured["artifact"].genui.splitlines()]
    protocol_profile = A2UIProtocolRegistry(A2UI_FORM_PROTOCOL_PROFILE_ID).get_profile()
    assert messages[0]["createSurface"]["catalogId"] == protocol_profile["catalogId"]
    assert captured["artifact"].effectiveCapabilities["data"] == ["ViewWeather"]


@pytest.mark.asyncio
async def test_first_layer_no_match_rejects_template_before_body_generation():
    model = WeatherTemplateModel(route_usable=False)
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        arguments={"districtName": "青浦区", "prefectureName": "上海市"},
        writeResultTo="/data/weather",
        candidateOutputFields=[
            "/current/condition",
            "/current/humidityPercent",
        ],
    )

    with pytest.raises(TemplateRouteNotApplicable, match="first-layer decision rejected"):
        await generate_template_a2ui(
            _weather_task_spec(),
            _weather_card_spec(),
            (binding,),
            model,
        )

    assert model.body_called is False


@pytest.mark.asyncio
async def test_first_layer_rejects_template_candidate_outside_component_catalog():
    model = WeatherTemplateModel(available_template_ids=("ScheduleOverviewNextEvent@1",))
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        writeResultTo="/data/weather",
        candidateOutputFields=list(_WEATHER_TEMPLATE_FIELDS),
    )

    with pytest.raises(TemplateRouteNotApplicable, match="unavailable Provider Template"):
        await generate_template_a2ui(
            _weather_task_spec(),
            _weather_card_spec(),
            (binding,),
            model,
        )

    assert model.body_called is False


@pytest.mark.asyncio
async def test_second_layer_rejects_provider_template_outside_first_layer_candidates():
    model = WeatherTemplateModel(available_template_ids=("WeatherOverviewHero@1",))
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        writeResultTo="/data/weather",
        candidateOutputFields=list(_WEATHER_TEMPLATE_FIELDS),
    )

    with pytest.raises(TemplateGenerationError, match="template body validation failed"):
        await generate_template_a2ui(
            _weather_task_spec(),
            _weather_card_spec(),
            (binding,),
            model,
        )

    assert model.body_called is True


@pytest.mark.asyncio
async def test_unused_candidate_fields_do_not_block_query_required_weather_fields():
    model = WeatherTemplateModel()
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        arguments={"districtName": "青浦区", "prefectureName": "上海市"},
        writeResultTo="/data/weather",
        candidateOutputFields=[
            *_WEATHER_TEMPLATE_FIELDS,
            "/current/humidityPercent",
            "/current/windDirection",
            "/current/uvIndex",
        ],
    )

    output = await generate_template_a2ui(
        _weather_task_spec(),
        _weather_card_spec(),
        (binding,),
        model,
    )

    assert output.template_ids == ("WeatherOverviewHeroIcon@1", "SingleFocusLayout@1")
    assert model.body_called is True


@pytest.mark.asyncio
async def test_first_layer_action_is_independent_from_selected_components():
    model = WeatherTemplateModel(
        action_id="event.open.weather",
        body=(
            'Template("SingleFocusLayout@1",{},Template("WeatherOverviewHeroIcon@1",'
            '{"conditionIcon":"resources/base/media/icon_weather1.svg"}),'
            'PillAction({"actionId":"event.open.weather"}));'
        ),
    )
    task_spec = _weather_task_spec()
    task_spec.dataModelSchema["data"]["weather"]["location"]["cityCode"] = {
        "type": "string",
        "description": "weather city code",
        "sampleValue": "60814",
    }
    task_spec = task_spec.model_copy(
        update={
            "eventCandidates": [
                EventAction(
                    id="event.open.weather",
                    call="clickToDeeplink",
                    args={
                        "intentName": "Weather_CityCode",
                        "uri": (
                            "{{ 'hww://www.huawei.com/totemweather?enterType=share&cityCode=' "
                            "+ ${/data/weather/location/cityCode} }}"
                        ),
                    },
                )
            ]
        }
    )
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        arguments={"districtName": "青浦区", "prefectureName": "上海市"},
        writeResultTo="/data/weather",
        candidateOutputFields=["/current/condition"],
    )

    output = await generate_template_a2ui(
        task_spec,
        _weather_card_spec(),
        (binding,),
        model,
    )

    assert model.body_called is True
    assert '"call":"clickToDeeplink"' in output.a2ui
    assert "天气详情" in output.a2ui
    assert "cityCode" in output.projected_task_spec.dataModelSchema["data"]["weather"]["location"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action_call",
    [
        'IconAction({"actionId":"event.open.weather"})',
        'ActionTile({"actionId":"event.open.weather"})',
        (
            'PillAction({"actionId":"event.open.weather",'
            '"icon":"resources/base/media/icon_weather1.svg"})'
        ),
    ],
)
async def test_second_layer_rejects_non_pill_or_decorated_actions(action_call: str):
    model = WeatherTemplateModel(
        action_id="event.open.weather",
        body=(
            'Template("SingleFocusLayout@1",{},Template("WeatherOverviewHeroIcon@1",'
            '{"conditionIcon":"resources/base/media/icon_weather1.svg"}),' + action_call + ");"
        ),
    )
    task_spec = _weather_task_spec().model_copy(
        update={
            "eventCandidates": [
                EventAction(
                    id="event.open.weather",
                    call="clickToDeeplink",
                    args={"intentName": "Weather_CityCode"},
                )
            ]
        }
    )
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        writeResultTo="/data/weather",
        candidateOutputFields=["/current/condition"],
    )

    with pytest.raises(TemplateGenerationError, match="template body validation failed"):
        await generate_template_a2ui(
            task_spec,
            _weather_card_spec(),
            (binding,),
            model,
        )


@pytest.mark.asyncio
async def test_first_layer_action_must_be_a_task_spec_event_id():
    model = WeatherTemplateModel(action_id="event.unknown")
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        arguments={"districtName": "青浦区", "prefectureName": "上海市"},
        writeResultTo="/data/weather",
        candidateOutputFields=["/current/condition"],
    )

    with pytest.raises(TemplateRouteNotApplicable, match="outside TaskSpec.eventCandidates"):
        await generate_template_a2ui(
            _weather_task_spec(),
            _weather_card_spec(),
            (binding,),
            model,
        )

    assert model.body_called is False


@pytest.mark.asyncio
async def test_compact_edit_rejection_uses_original_flow(monkeypatch):
    request = _weather_request().model_copy(
        update={"sourceArtifactUrl": "https://artifact.test/source.md"}
    )
    request.model_fields_set.add("sourceArtifactUrl")
    original_response = object()

    async def original_generation(*_args: Any, **_kwargs: Any) -> Any:
        return original_response

    service = WidgetGenerationService()
    monkeypatch.setattr(
        service,
        "_generate_widget_card_with_policy",
        original_generation,
    )
    response = await service.generate_widget_card_compact_dsl(request)

    assert response is original_response


@pytest.mark.asyncio
async def test_selected_template_failure_falls_back_to_original_at_entry(monkeypatch):
    original_called = False
    original_response = object()

    async def original_generation(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal original_called
        original_called = True
        return original_response

    async def selected_failure(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("selected route failed")

    service = WidgetGenerationService()
    monkeypatch.setattr(
        widget_generation_service_module,
        "generate_template_artifact",
        selected_failure,
    )
    monkeypatch.setattr(
        service,
        "_generate_widget_card_with_policy",
        original_generation,
    )
    response = await service.generate_widget_card_compact_dsl(_weather_request())

    assert response is original_response
    assert original_called is True


@pytest.mark.asyncio
async def test_first_layer_rejection_falls_back_to_original(monkeypatch):
    async def original_generation(*_args: Any, **_kwargs: Any) -> str:
        return "original"

    async def rejected(
        _request: Any,
        _policy_value: Any,
        **_kwargs: Any,
    ) -> Any:
        raise TemplateRouteNotApplicable("LLM rejected template route")

    service = WidgetGenerationService()
    monkeypatch.setattr(
        widget_generation_service_module,
        "generate_template_artifact",
        rejected,
    )
    monkeypatch.setattr(
        service,
        "_generate_widget_card_with_policy",
        original_generation,
    )
    response = await service.generate_widget_card_compact_dsl(_weather_request())

    assert response == "original"


@pytest.mark.asyncio
async def test_terse_template_mismatch_returns_failed_without_original_flow(monkeypatch):
    original_called = False

    async def original_generation(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal original_called
        original_called = True
        return object()

    async def rejected(*_args: Any, **_kwargs: Any) -> Any:
        raise TemplateRouteNotApplicable("LLM rejected template route")

    service = WidgetGenerationService()
    monkeypatch.setattr(
        widget_generation_service_module,
        "generate_template_artifact",
        rejected,
    )
    monkeypatch.setattr(
        service,
        "_generate_widget_card_with_policy",
        original_generation,
    )
    response = await service.generate_widget_card_terse_dsl_nested2(_weather_request())

    assert response.status == GenerationStatus.FAILED
    assert response.errorCode == "A2UI_GENERATION_FAILED"
    assert original_called is False


@pytest.mark.asyncio
async def test_terse_selected_template_failure_returns_failed_without_original_flow(
    monkeypatch,
):
    original_called = False

    async def original_generation(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal original_called
        original_called = True
        return object()

    async def failed(*_args: Any, **_kwargs: Any) -> Any:
        raise TemplateGenerationError("template body validation failed")

    service = WidgetGenerationService()
    monkeypatch.setattr(
        widget_generation_service_module,
        "generate_template_artifact",
        failed,
    )
    monkeypatch.setattr(
        service,
        "_generate_widget_card_with_policy",
        original_generation,
    )
    response = await service.generate_widget_card_terse_dsl_nested2(_weather_request())

    assert response.status == GenerationStatus.FAILED
    assert response.errorCode == "A2UI_GENERATION_FAILED"
    assert original_called is False


@pytest.mark.asyncio
async def test_terse_edit_uses_shared_template_entry_then_returns_failed(monkeypatch):
    request = _weather_request().model_copy(
        update={"sourceArtifactUrl": "https://artifact.test/source.md"}
    )
    request.model_fields_set.add("sourceArtifactUrl")
    template_called = False

    async def original_generation(*_args: Any, **_kwargs: Any) -> Any:
        pytest.fail("Terse edit must not enter the original flow")

    async def rejected_template(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal template_called
        template_called = True
        raise TemplateRouteNotApplicable("template generation does not support edit mode")

    service = WidgetGenerationService()
    monkeypatch.setattr(
        widget_generation_service_module,
        "generate_template_artifact",
        rejected_template,
    )
    monkeypatch.setattr(
        service,
        "_generate_widget_card_with_policy",
        original_generation,
    )
    response = await service.generate_widget_card_terse_dsl_nested2(request)

    assert response.status == GenerationStatus.FAILED
    assert response.errorCode == "A2UI_GENERATION_FAILED"
    assert template_called is True


@pytest.mark.asyncio
async def test_legacy_python_terse_entry_is_explicit_and_delegates_to_original():
    expected = object()
    observed_callback: Any = None

    class Host:
        async def _generate_widget_card_with_policy(
            self,
            _request: Any,
            _policy_value: Any,
            *,
            before_model_call: Any,
        ) -> Any:
            nonlocal observed_callback
            observed_callback = before_model_call
            return expected

    async def notify(_size: str) -> None:
        return None

    response = await route_legacy_python_terse_generation(
        Host(),
        _weather_request(),
        _terse_policy(),
        before_model_call=notify,
    )

    assert response is expected
    assert observed_callback is notify
