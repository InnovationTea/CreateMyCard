"""模板路由独立模块的关键边界和天气 POC。"""

from __future__ import annotations

import json
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
from services.template_generation.engine.advanced.content_selectors import (
    app_usage_overview_is_eligible,
    app_usage_overview_query_is_supported,
    apply_content_selectors,
)
from services.template_generation.engine.advanced.data_shape import extract_data_shape
from services.template_generation.engine.advanced.models import AdvancedScopeBrief
from services.template_generation.engine.advanced.scope_planner import (
    TemplateRouteNotApplicable,
    build_advanced_scope_prompt,
    validate_template_request_coverage,
)
from services.template_generation.engine.cardplan.compiler import (
    _inject_resource_battery_title,
    _provider_layout_action_background,
)
from services.template_generation.engine.cardplan.models import HybridBodyContract, HybridLimits
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.pipeline import generate_template_a2ui
from services.template_generation.engine.terse_dsl_nested2_converter import Nested2Node
from services.widget_generation_service import WidgetGenerationService

_WEATHER_BODY = (
    'SingleFocusLayout(Template("WeatherOverview@1","heroIcon",'
    '{"conditionIcon":"resources/base/media/icon_weather1.svg"}));'
)
_WEATHER_TEMPLATE_FIELDS = (
    "/location/districtName",
    "/current/temperatureText",
    "/current/condition",
    "/current/airQuality",
    "/daily/0/temperatureRangeText",
)


def test_all_provider_templates_are_loaded_from_the_isolated_directory():
    registry = get_cardplan_registry()
    provider_directories = {
        path.name
        for path in (registry.source_root / "providers").iterdir()
        if path.is_dir()
    }

    assert set(registry.provider_template_ids) == {
        "ActivityOverview@1",
        "AppUsageOverview@1",
        "BatteryOverview@1",
        "BluetoothDeviceOverview@1",
        "CountdownOverview@1",
        "DateOverview@1",
        "HeartRateOverview@1",
        "ResourceUsageOverview@1",
        "ScheduleOverview@1",
        "SleepOverview@1",
        "WeatherOverview@1",
        "WorkoutOverview@1",
    }
    assert provider_directories == {
        "app-usage",
        "battery",
        "calendar",
        "countdown",
        "earphone",
        "health-sport",
        "system-memory",
        "weather",
    }


def test_first_layer_uses_candidate_provider_and_theme_documents_with_task_spec_paths():
    registry = get_cardplan_registry()
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
        "component",
        "action",
    }
    assert "Action 是点击或跳转动作，不是数据项" in system
    assert "requiredOutputFieldsByCapability" not in system
    assert "action.supportedComponent" in system
    assert payload["action"] == []
    assert (
        "/data/weather/current/temperatureText" in payload["component"][0]["supportedTaskSpecPaths"]
    )
    provider_rules = json.dumps(payload["providerFirstLayerRules"], ensure_ascii=False)
    theme_rules = json.dumps(payload["themeFirstLayerRules"], ensure_ascii=False)
    assert "天气高级组件首层规则" in provider_rules
    assert "手机电量高级组件首层规则" not in provider_rules
    assert "family-weather-care-blue" in theme_rules
    assert "system-low-power-blue" not in theme_rules


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
    definition = registry.require_template("BluetoothDeviceOverview@1")
    assert definition.layout_action_style is not None
    assert definition.layout_action_style.background_opacity == 0.1
    contract = HybridBodyContract(
        theme_profile_id="audio-product-neutral-violet",
        allowed_components=(),
        allowed_design_tokens=(),
        allowed_layout_tokens=(),
        allowed_template_ids=("BluetoothDeviceOverview@1",),
        required_template_groups=(("BluetoothDeviceOverview@1",),),
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

    countdown = registry.require_variant("CountdownOverview@1", "countdown").root
    assert _template_node_options(countdown)["justifyContent"] == "start"
    assert _template_node_options(countdown.children[1])["justifyContent"] == "center"
    assert _template_node_options(countdown.children[1].children[0])["justifyContent"] == "center"

    app_usage = registry.require_variant("AppUsageOverview@1", "singleApp").root
    assert _template_node_options(app_usage)["justifyContent"] == "start"
    duration_region = app_usage.children[1]
    assert _template_node_options(duration_region)["justifyContent"] == "end"
    assert "itemMargin" not in _template_node_options(duration_region)

    battery = registry.require_variant("BatteryOverview@1", "normal").root
    assert _template_node_options(battery.children[1])["fontColor"] == "#99000000"
    battery_peer = registry.require_variant("BatteryOverview@1", "normalPeer").root
    assert _template_node_options(battery_peer)["justifyContent"] == "end"
    assert _template_node_options(_template_nodes(battery_peer, "Image")[0])["width"] == 20

    resource_peer = registry.require_variant(
        "ResourceUsageOverview@1",
        "memoryPeer",
    ).root
    assert _template_node_options(resource_peer)["justifyContent"] == "end"
    assert _template_node_options(_template_nodes(resource_peer, "Image")[0])["width"] == 20
    percent_row = resource_peer.children[1]
    assert _template_node_options(percent_row.children[0])["fontWeight"] == 700
    assert not _template_nodes(resource_peer.children[0], "Text")


def test_pr7_resource_battery_outer_title_keeps_the_reviewed_subtext_style():
    registry = get_cardplan_registry()
    contract = HybridBodyContract(
        theme_profile_id="device-clean-blue-teal",
        allowed_components=(),
        allowed_design_tokens=(),
        allowed_layout_tokens=(),
        allowed_template_ids=("BatteryOverview@1", "ResourceUsageOverview@1"),
        required_template_groups=(
            ("BatteryOverview@1",),
            ("ResourceUsageOverview@1",),
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
                "component": ["AppUsageOverview"],
                "action": [],
            }

        async def generate(self, *_args: Any, **_kwargs: Any) -> str:
            return 'SingleFocusLayout(Template("AppUsageOverview@1","singleApp",{}));'

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


class _FixedTemplateModel:
    def __init__(
        self,
        *,
        theme_id: str,
        component_id: str,
        body: str,
        action_ids: tuple[str, ...] = (),
    ) -> None:
        self.theme_id = theme_id
        self.component_id = component_id
        self.action_ids = action_ids
        self.body = body

    async def generate_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {
            "theme": self.theme_id,
            "component": [self.component_id],
            "action": list(self.action_ids),
        }

    async def generate(self, *_args: Any, **_kwargs: Any) -> str:
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
        body=(
            'SingleFocusLayout(Template("BluetoothDeviceOverview@1","'
            + variant
            + '",{}));'
        ),
    )

    output = await generate_template_a2ui(
        _bluetooth_task(query),
        _bluetooth_card_spec(),
        (binding,),
        model,
    )

    assert output.template_ids == ("BluetoothDeviceOverview@1",)
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
        action_ids=("event.open.music.daily",),
        body=(
            'HeroActionLayout(Template("BluetoothDeviceOverview@1","earbuds",{}),'
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


def test_first_layer_action_candidate_declares_supported_component():
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
            "id": "event.open.music.daily",
            "call": "clickToIntent",
            "supportedComponent": ["BluetoothDeviceOverview"],
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
        body='SingleFocusLayout(Template("CountdownOverview@1","countdown",{}));',
    )

    output = await generate_template_a2ui(task_spec, card_spec, (binding,), model)

    assert output.template_ids == ("CountdownOverview@1",)
    assert "countdownDays" in output.a2ui
    assert "倒计时" in output.a2ui
    assert "运动倒计时" not in output.a2ui


class WeatherTemplateModel:
    def __init__(
        self,
        *,
        route_usable: bool = True,
        action_ids: tuple[str, ...] = (),
    ) -> None:
        self.body_called = False
        self.route_usable = route_usable
        self.action_ids = action_ids
        self.first_layer_prompt: list[dict[str, str]] | None = None
        self.second_layer_prompt: list[dict[str, str]] | None = None

    async def generate_json(self, prompt: list[dict[str, str]], **_kwargs: Any) -> dict[str, Any]:
        self.first_layer_prompt = prompt
        return {
            "theme": "family-weather-care-blue" if self.route_usable else None,
            "component": ["WeatherOverview"] if self.route_usable else [],
            "action": list(self.action_ids) if self.route_usable else [],
        }

    async def generate(
        self,
        prompt: list[dict[str, str]],
        *_args: Any,
        **_kwargs: Any,
    ) -> str:
        self.body_called = True
        self.second_layer_prompt = prompt
        return _WEATHER_BODY


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


def test_template_route_prompt_requires_exact_candidate_output_paths():
    task_spec = apply_content_selectors(
        _weather_task_spec().model_copy(
            update={"userQuery": "看看是否下雨、现在多少度"}
        ),
        {"ViewWeather"},
    )
    prompt = build_advanced_scope_prompt(
        task_spec,
        extract_data_shape(task_spec),
        get_cardplan_registry(),
        ("ViewWeather",),
        template_route_decision=True,
        candidate_output_fields={"ViewWeather": _WEATHER_TEMPLATE_FIELDS},
        card_spec=_weather_card_spec(),
    )

    system_prompt = prompt[0]["content"]
    assert (
        "必须从同一 capability 的 candidateOutputFieldsByCapability 数组中逐字复制"
        in system_prompt
    )
    assert "禁止输出 /_advancedSelectors" in system_prompt
    assert "/current/condition 和 /current/temperatureText" in system_prompt
    payload = json.loads(prompt[1]["content"])
    assert payload["candidateOutputFieldsByCapability"]["ViewWeather"] == list(
        _WEATHER_TEMPLATE_FIELDS
    )
    assert "LocationOverview" not in {
        item["id"] for item in payload["advancedComponents"]
    }


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
    assert "天气高级组件二层规则" in second_layer_user
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

    with pytest.raises(TemplateRouteNotApplicable, match="first-layer LLM rejected"):
        await generate_template_a2ui(
            _weather_task_spec(),
            _weather_card_spec(),
            (binding,),
            model,
        )

    assert model.body_called is False


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

    assert output.template_ids == ("WeatherOverview@1",)
    assert model.body_called is True


@pytest.mark.asyncio
async def test_first_layer_action_must_be_supported_by_selected_components():
    model = WeatherTemplateModel(action_ids=("event.open.weather",))
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
        arguments={"districtName": "青浦区", "prefectureName": "上海市"},
        writeResultTo="/data/weather",
        candidateOutputFields=["/current/condition"],
    )

    with pytest.raises(TemplateRouteNotApplicable, match="unsupported by the component scope"):
        await generate_template_a2ui(
            task_spec,
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
async def test_terse_template_mismatch_falls_back_to_original_at_entry(monkeypatch):
    original_called = False
    original_response = object()

    async def original_generation(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal original_called
        original_called = True
        return original_response

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

    assert response is original_response
    assert original_called is True


@pytest.mark.asyncio
async def test_terse_edit_rejection_uses_original_flow(monkeypatch):
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
    response = await service.generate_widget_card_terse_dsl_nested2(request)

    assert response is original_response


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
