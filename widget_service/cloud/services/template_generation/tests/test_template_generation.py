"""模板路由独立模块的关键边界和天气 POC。"""

from __future__ import annotations

import inspect
import json
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from api.schemas import GenerateWidgetCardRequest
from config.config import get_settings
from core.errors import GenerationStatus
from models.generation import (
    CandidateDataBinding,
    EventAction,
    ModelRequestContext,
    TaskSpec,
)
from models.service import ArtifactSaveResult
from services import widget_generation_service as widget_generation_service_module
from services.artifact_store import ArtifactStore
from services.card_validation import validate_card
from services.fusion_ball_expander import (
    FUSION_BALL_MIN_PRD_VERSION_CONFIG,
)
from services.generation_pipeline import (
    DslProcessingResult,
    DslProcessorKind,
    GenerationRoutePolicy,
    QualityIssue,
)
from services.protocol_registry import (
    A2UI_FORM_PROTOCOL_PROFILE_ID,
    A2UIProtocolRegistry,
)
from services.template_generation import (
    TemplateSourceGenerator,
    facade,
)
from services.template_generation import source_generator as template_source_generator_module
from services.template_generation.binding_dependencies import enrich_template_bindings
from services.template_generation.controls import TemplateControls, load_template_controls
from services.template_generation.engine import pipeline as template_pipeline_module
from services.template_generation.engine.advanced.content_selectors import (
    app_usage_overview_is_eligible,
    app_usage_overview_query_is_supported,
    apply_content_selectors,
    bluetooth_device_overview_is_eligible,
    extract_battery_overview_facts,
    extract_bluetooth_device_overview_facts,
    extract_schedule_overview_facts,
    extract_schedule_timezone_facts,
    extract_workout_latest_facts,
    schedule_overview_is_eligible,
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
    plan_advanced_scope_with_llm,
    resolve_scope_layout_ids,
    scope_template_ids,
    validate_template_request_coverage,
)
from services.template_generation.engine.advanced.ux_mixed_framer import (
    frame_ux_layout_root_children,
)
from services.template_generation.engine.cardplan import registry as cardplan_registry_module
from services.template_generation.engine.cardplan.compiler import (
    _apply_template_background,
    _apply_theme_content_color,
    _compile_ux_layout_shell,
    _inject_resource_battery_title,
    _instantiate_blueprint,
    _lower_action_template_tree,
    _normalize_weather_condition_icons,
    _provider_layout_action_background,
    _validate_provider_template_state,
)
from services.template_generation.engine.cardplan.fusion_ball_background import (
    FusionBallPalette,
    apply_fusion_ball_background,
    build_fusion_ball_background,
)
from services.template_generation.engine.cardplan.models import (
    ActionBinding,
    HybridBodyContract,
    HybridLimits,
)
from services.template_generation.engine.cardplan.prompt import _ux_layout_action_rule
from services.template_generation.engine.cardplan.provider_bundle import (
    _parse_component_body,
    load_provider_bundle,
    provider_template_family_identity,
    provider_template_layout_kind,
)
from services.template_generation.engine.cardplan.registry import (
    CardPlanRegistry,
    get_cardplan_registry,
)
from services.template_generation.engine.pipeline import (
    TemplateGenerationError,
    generate_template_a2ui,
)
from services.template_generation.engine.tersel_converter import (
    Nested2Node,
    TerselConversionError,
    convert_tersel_to_a2ui,
)
from services.template_generation.profile import read_tersel_protocol_profile
from services.widget_generation_service import WidgetGenerationService

_WEATHER_BODY = (
    'Template("SingleFocusLayout@1",{},Template("WeatherOverviewFull@1",'
    '{"conditionIcon":"resources/base/media/icon_weather1.svg"}));'
)


def test_ux_mixed_framer_quotes_unquoted_template_ids_only_in_calls() -> None:
    source = (
        'Template(CompactTwoActionLayout@1, {}, '
        'Template(HeartRateOverviewUpdatedIconHero@1, '
        '{"sourceIcon":"resources/base/media/heart_fill.svg"}), '
        'Template(PillAction@1, {"actionId":"event.open.health.sport", '
        '"label":"Template(Fake@1, label)"}), '
        'Template(PillAction@1, {"actionId":"event.open.settings.dnd", '
        '"label":"免打扰"}));'
    )

    framed, repaired = frame_ux_layout_root_children(
        source,
        size="2x2",
        registry=get_cardplan_registry(enable_fusion_ball=True),
        allowed_layout_ids=("CompactTwoActionLayout@1",),
    )

    assert repaired
    assert 'Template("CompactTwoActionLayout@1",' in framed
    assert 'Template("HeartRateOverviewUpdatedIconHero@1",' in framed
    assert '"label":"Template(Fake@1, label)"' in framed
_WEATHER_TEMPLATE_FIELDS = (
    "/location/districtName",
    "/current/temperatureText",
    "/current/condition",
    "/current/airQuality",
    "/current/coldLevel",
    "/daily/0/temperatureRangeText",
)
_WEATHER_PALETTE = ("#FF121259", "#FF2B65D9", "#FF57AED9")
_SPORT_PALETTE = ("#FFB33024", "#FFFF8833", "#FFE68073")
_TEST_APP_VERSION = ".".join(("11", "7", "5", "205"))


def test_weather_single_color_template_icon_uses_provided_fill_color() -> None:
    contract = HybridBodyContract.model_construct(asset_semantic_tags_by_source={})
    source = "resources/base/media/icon_high_temperature.svg"
    root = Nested2Node(
        "Row",
        ({"_advancedComponent": "WeatherOverview"},),
        (
            Nested2Node(
                "Image",
                (
                    source,
                    {
                        "width": 20,
                        "height": 20,
                        "fillColor": "#FF1F4594",
                        "_preserveOriginalColor": True,
                    },
                ),
                (),
            ),
        ),
    )

    normalized = _normalize_weather_condition_icons(root, contract)

    icon_options = normalized.children[0].values[1]
    assert icon_options["fillColor"] == "#FF1F4594"
    assert "_preserveOriginalColor" not in icon_options


def test_weather_multicolor_template_icon_preserves_original_color() -> None:
    contract = HybridBodyContract.model_construct(asset_semantic_tags_by_source={})
    source = "resources/base/media/icon_weather1.svg"
    root = Nested2Node(
        "Row",
        ({"_advancedComponent": "WeatherOverview"},),
        (
            Nested2Node(
                "Image",
                (
                    source,
                    {
                        "width": 20,
                        "height": 20,
                        "fillColor": "#FF1F4594",
                    },
                ),
                (),
            ),
        ),
    )

    normalized = _normalize_weather_condition_icons(root, contract)

    icon_options = normalized.children[0].values[1]
    assert icon_options["_preserveOriginalColor"] is True
    assert "fillColor" not in icon_options


def test_template_facade_requires_explicit_fusion_feature_switch() -> None:
    parameter = inspect.signature(facade.request_template_source_dsl).parameters[
        "enable_fusion_ball"
    ]

    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is inspect.Parameter.empty


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

    assert len(registry.provider_template_ids) == 83
    assert {
        "ActivityOverviewFull@1",
        "AppUsageOverviewFull@1",
        "BatteryOverviewFull@1",
        "BatteryOverviewHero@1",
        "BatteryOverviewChargingProgressHero@1",
        "BatteryOverviewChargingProgressFull@1",
        "BatteryOverviewChargingDiagnosticsHero@1",
        "BatteryOverviewChargingRingHero@1",
        "BatteryOverviewHealthLevelHero@1",
        "BluetoothDeviceOverviewEarbudPairFull@1",
        "BluetoothDeviceOverviewHero@1",
        "CountdownOverviewFull@1",
        "CountdownOverviewHero@1",
        "HeartRateOverviewFull@1",
        "ResourceUsageOverviewFull@1",
        "ScheduleOverviewDatedMeetingHero@1",
        "ScheduleOverviewDateFull@1",
        "ScheduleOverviewNextEventHero@1",
        "ScheduleOverviewReminderHero@1",
        "ScheduleOverviewTimezoneFull@1",
        "SleepOverviewCompact@1",
        "SleepOverviewFull@1",
        "SleepOverviewHero@1",
        "WeatherOverviewAirQualityHero@1",
        "WeatherOverviewFull@1",
        "WeatherOverviewHero@1",
        "WeatherOverviewHumidityFull@1",
        "WeatherOverviewUvFull@1",
        "WorkoutOverviewFull@1",
        "SingleFocusLayout@1",
        "CompactTwoActionLayout@1",
        "WideSingleFocusLayout@1",
    }.issubset(registry.provider_template_ids)
    assert provider_directories == {
        "action",
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
    assert all("IfPresent" not in source for source in provider_source_texts)
    assert all("IfAbsent" not in source for source in provider_source_texts)
    assert any("#if" in source for source in provider_source_texts)
    assert any("#else" in source for source in provider_source_texts)
    assert any("#endif" in source for source in provider_source_texts)
    assert any("#Expr" in source for source in provider_source_texts)
    assert all(
        definition.variants[0].size == "default"
        for template_id in registry.provider_template_ids
        for definition in (registry.require_template(template_id),)
    )


def test_business_template_suffix_drives_size_and_provider_data_tiers():
    registry = get_cardplan_registry()
    layout_kinds = {
        "HeroTitle",
        "HeroContent",
        "Support",
        "Compact",
        "Hero",
        "Full",
        "WideHero",
        "WideFull",
    }

    for template_id in registry.provider_template_ids:
        definition = registry.require_template(template_id)
        if definition.capability_id is None:
            continue
        layout_kind = provider_template_layout_kind(template_id)
        expected_sizes = ("2x4",) if layout_kind in {"WideHero", "WideFull"} else ("2x2",)
        serialized = definition.model_dump(mode="json", by_alias=True)

        assert layout_kind in layout_kinds
        assert definition.variants[0].supported_card_sizes == expected_sizes
        assert "requiredData" not in serialized
        assert "requiredDataFields" not in serialized
        assert set(definition.primary_data).isdisjoint(definition.secondary_data)
        assert set(definition.primary_data).isdisjoint(definition.optional_data)
        assert set(definition.secondary_data).isdisjoint(definition.optional_data)
        assert definition.required_data == (*definition.primary_data, *definition.secondary_data)


def test_app_usage_compact_data_contract_matches_visible_content() -> None:
    definition = get_cardplan_registry().require_template("AppUsageOverviewCompact@1")

    assert definition.primary_data == (
        "/appUsage/appName",
        "/appUsage/durationText",
    )
    assert definition.secondary_data == ()
    assert definition.optional_data == ()


def test_weather_location_compile_time_conditional_has_optional_sources() -> None:
    definition = get_cardplan_registry().require_template("WeatherOverviewCompact@1")
    variant = definition.variants[0]

    assert definition.primary_data == ("/current/temperatureText",)
    assert definition.secondary_data == ("/current/condition",)
    assert definition.optional_data == (
        "/location/prefectureName",
        "/location/districtName",
        "/current/coldLevel",
    )
    assert variant.required_bindings == ("temperature", "condition")
    assert variant.optional_bindings == ("city", "district", "coldLevel")


@pytest.mark.parametrize(
    "template_id",
    [
        "WeatherOverviewHumidityFull@1",
        "WeatherOverviewUvFull@1",
        "WeatherOverviewAirQualityHero@1",
    ],
)
def test_specialized_weather_location_uses_optional_compile_time_sources(
    template_id: str,
) -> None:
    definition = get_cardplan_registry().require_template(template_id)
    variant = definition.variants[0]
    required_props = variant.parameters_schema.get("required", [])
    properties = variant.parameters_schema.get("properties", {})
    bindings = {
        name: f"${{data.weather.{name}}}" for name in variant.required_bindings
    }
    bindings["city"] = "${data.weather.location.prefectureName}"

    root = _instantiate_blueprint(
        variant.root,
        {},
        bindings,
        {
            "primaryColor": "#FF000000",
            "supportContentColor": "#99000000",
        },
    )

    assert "location" in properties
    assert "location" not in required_props
    assert definition.optional_data[:2] == (
        "/location/prefectureName",
        "/location/districtName",
    )
    assert {"city", "district"}.issubset(variant.optional_bindings)
    assert "${data.weather.location.prefectureName}" in repr(root)
    assert "?" not in repr(root)


@pytest.mark.parametrize(
    ("location_bindings", "params", "expected"),
    [
        (
            {
                "city": "${data.weather.location.prefectureName}",
                "district": "${data.weather.location.districtName}",
            },
            {"location": "二层城市"},
            "${data.weather.location.prefectureName}",
        ),
        (
            {"district": "${data.weather.location.districtName}"},
            {"location": "二层城市"},
            "${data.weather.location.districtName}",
        ),
        ({}, {"location": "二层城市"}, "二层城市"),
        ({}, {}, "当前城市"),
    ],
)
def test_weather_location_compile_time_conditional_selects_available_reference(
    location_bindings: dict[str, str],
    params: dict[str, str],
    expected: str,
) -> None:
    definition = get_cardplan_registry().require_template("WeatherOverviewCompact@1")
    bindings = {
        "temperature": "${data.weather.current.temperatureText}",
        "condition": "${data.weather.current.condition}",
        **location_bindings,
    }
    root = _instantiate_blueprint(
        definition.variants[0].root,
        params,
        bindings,
        {
            "primaryColor": "#FF000000",
            "supportContentColor": "#99000000",
        },
    )
    location_text = root.children[0].children[0].children[0]

    assert location_text.component_type == "Text"
    assert location_text.values[0] == expected
    assert "?" not in repr(root)
    assert "{{" not in str(location_text.values[0])


def test_compile_time_conditional_requires_explicit_expr() -> None:
    with pytest.raises(ValueError, match="must use #Expr"):
        _parse_component_body('Text((data.city ? data.city : "当前城市"), {})')

    root = _parse_component_body(
        'Text(#Expr(data.city ? data.city : '
        '(props.location ? props.location : "当前城市")), {})'
    )

    assert root.values[0].kind == "compile-time-conditional"
    assert root.values[0].items[2].kind == "compile-time-conditional"


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("#else", "has no matching #if"),
        ("#if data.city", "missing #endif"),
        ("#if data.city.value\n#endif", "#if target is invalid"),
        ("Text(#Expr(data.city), {})", "requires one ternary expression"),
    ],
)
def test_provider_compile_directives_reject_invalid_syntax(
    source: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        _parse_component_body(source)


def test_provider_compiler_rejects_legacy_presence_calls() -> None:
    with pytest.raises(ValueError, match="unsupported Provider Template component"):
        _parse_component_body('Column({}, IfPresent(data.city, Text(data.city, {})))')


def test_provider_structure_directive_selects_compile_time_branch() -> None:
    root = _parse_component_body(
        """Column({},
#if data.city
  Text(data.city, {}),
  Text("已定位", {})
#else
  Text("当前城市", {})
#endif
)"""
    )

    present = _instantiate_blueprint(root, {}, {"city": "${data.weather.city}"})
    missing = _instantiate_blueprint(root, {}, {})

    assert present.children[0].values[0] == "${data.weather.city}"
    assert present.children[1].values[0] == "已定位"
    assert missing.children[0].values[0] == "当前城市"
    assert "IfBind" not in repr(present)
    assert "IfMissingBind" not in repr(missing)


def test_layout_template_wide_marker_drives_exclusive_card_size() -> None:
    registry = get_cardplan_registry()
    expected_sizes = {
        "SingleFocusLayout": ("2x2",),
        "HeroActionLayout": ("2x2",),
        "FullIconActionLayout": ("2x2",),
        "CompactTwoActionLayout": ("2x2",),
        "HeroTitleContentActionLayout": ("2x2",),
        "TwoSupportLayout": ("2x2",),
        "WideSingleFocusLayout": ("2x4",),
    }

    assert set(registry.ux_layout_components) == set(expected_sizes)
    for layout_id, sizes in expected_sizes.items():
        layout = registry.require_ux_layout_component(layout_id)
        assert layout.supported_card_sizes == sizes
        assert set(layout.max_children_by_size) == set(sizes)
        assert set(layout.min_action_children_by_size) == set(sizes)
        assert set(layout.max_action_children_by_size) == set(sizes)
        assert set(layout.lowering_by_size) == set(sizes)
        assert layout_id.startswith("Wide") == (sizes == ("2x4",))


def test_cardplan_registry_does_not_require_source_hashes(tmp_path):
    source_root = tmp_path / "source"
    bundled_source_root = get_cardplan_registry().source_root
    shutil.copytree(bundled_source_root, source_root)
    rule_path = source_root / "themes/digital-wellbeing-neutral-dark/first-layer.md"
    rule_path.write_text(
        rule_path.read_text(encoding="utf-8") + "\n<!-- local update -->\n",
        encoding="utf-8",
    )

    registry = CardPlanRegistry(source_root=source_root)

    assert registry.require_theme("digital-wellbeing-neutral-dark") is not None
    assert "files" not in registry.manifest
    assert "promptSha256" not in registry.manifest


def test_business_groups_are_derived_from_provider_templates() -> None:
    registry = get_cardplan_registry()
    theme_base = json.loads(
        (registry.source_root / "themes/base/theme-base.json").read_text(encoding="utf-8")
    )
    provider_business_groups = {
        component.name
        for bundle in registry.provider_bundles.values()
        for component in bundle.business_groups
    }
    provider_layout_components = {
        component.name
        for bundle in registry.provider_bundles.values()
        for component in bundle.manifest.layout_components
    }

    assert theme_base["themeBaseVersion"] == "theme-base/2"
    assert "businessComponents" not in theme_base
    assert "layoutComponents" not in theme_base
    assert provider_business_groups == set(registry.ux_business_components)
    assert provider_layout_components == set(registry.ux_layout_components)
    assert len(registry.ux_business_component_provider_ids) == 11
    calendar = registry.require_ux_business_component("CalendarOverview")
    assert len(calendar.local_template_ids) == 9
    assert "ScheduleOverviewDateFull@1" in calendar.local_template_ids
    assert not any(
        template_id.startswith("DateOverview")
        for template_id in calendar.local_template_ids
    )
    assert len(registry.ux_layout_component_provider_ids) == 7
    for bundle in registry.provider_bundles.values():
        payload = json.loads(
            (registry.source_root / "providers" / bundle.manifest.provider_id.removeprefix(
                "com.huawei."
            ).removesuffix(".cli") / "provider.json").read_text(encoding="utf-8")
        )
        assert "businessComponents" not in payload
        assert all("digest" not in template for template in payload.get("templates", []))


def test_registry_uses_only_distributed_provider_and_theme_sources() -> None:
    registry = get_cardplan_registry(True)
    central_sources = {
        "advanced-component-registry.json",
        "advanced-component-ux-registry.json",
        "template-registry.json",
        "theme-profiles.json",
    }

    assert all(not (registry.source_root / name).exists() for name in central_sources)
    assert set(registry.templates) == set(registry.provider_template_ids)
    assert set(registry.themes) == {
        "audio-product-neutral-violet",
        "2x2-two-support",
        "device-clean-blue-teal",
        "digital-wellbeing-neutral-dark",
        "family-weather-care-blue",
        "fusion-battery-teal",
        "fusion-schedule-cool",
        "fusion-sleep-violet",
        "fusion-sport-orange",
        "fusion-weather-blue",
        "meeting-paper-neutral",
        "race-night-violet",
        "race-sunrise-action",
        "sleep-night-violet",
    }
    assert all(
        (registry.source_root / "themes" / theme_id / "theme.json").is_file()
        for theme_id in registry.themes
    )


def test_two_support_layout_theme_is_deterministic_and_exposes_slot_styles() -> None:
    registry = get_cardplan_registry()
    theme = registry.require_theme("2x2-two-support")
    support_capabilities: set[str] = set()
    for template_id, definition in registry.templates.items():
        capability_id = definition.capability_id
        if capability_id is None:
            continue
        if template_id.rpartition("@")[0].endswith("Support"):
            support_capabilities.add(capability_id)

    assert theme.supported_layout_ids == ("TwoSupportLayout",)
    assert set(theme.supported_capability_ids) == support_capabilities
    assert registry.layout_theme_ids(
        "TwoSupportLayout",
        ("ViewWeather", "GetAppUsageDuration"),
    ) == ("2x2-two-support",)
    assert registry.require_layout_theme(
        "TwoSupportLayout",
        ("GetHealthAndSportSummary",),
    ) == "2x2-two-support"
    assert registry.theme_reference_values("2x2-two-support") == {
        "primaryColor": "#FF1F4595",
        "supportContentColor": "#991F4595",
        "progressColor": "#FF1F4595",
        "progressBackgroundColor": "#330A59F7",
        "actionStyle.backgroundColor": "#330A59F7",
        "actionStyle.contentColor": "#FF1F4799",
        "supportContentStyle.backgroundColor": "#1A2E529E",
        "supportContentStyle.borderRadius": 16,
    }


def test_two_support_layout_rejects_business_without_support_template() -> None:
    scope = AdvancedScopeBrief(
        themeId="family-weather-care-blue",
        advancedComponentIds=("WeatherOverview", "CalendarOverview"),
    )

    layout_ids = resolve_scope_layout_ids(
        scope,
        TaskSpec(userQuery="显示天气和日程", size="2x2", dataModelSchema={}),
        get_cardplan_registry(),
    )

    assert "TwoSupportLayout" not in layout_ids


def test_registry_hides_fusion_themes_by_default() -> None:
    default_registry = get_cardplan_registry()
    enabled_registry = get_cardplan_registry(True)

    assert all(
        theme.fusion_ball_style is None for theme in default_registry.themes.values()
    )
    assert any(
        theme.fusion_ball_style is not None for theme in enabled_registry.themes.values()
    )


def test_battery_fusion_theme_covers_phone_and_earphone_businesses() -> None:
    registry = get_cardplan_registry(True)
    theme = registry.require_theme("fusion-battery-teal")
    fusion_style = theme.fusion_ball_style

    assert set(theme.supported_capability_ids) == {
        "GetPhoneBatteryInfo",
        "GetEarphoneInfo",
    }
    assert fusion_style is not None
    assert set(fusion_style.business_ids) == {
        "BatteryOverview",
        "BluetoothDeviceOverview",
    }
    assert registry.first_layer_theme_ids(("BatteryOverview",)) == (
        "fusion-battery-teal",
    )
    assert registry.first_layer_theme_ids(("BluetoothDeviceOverview",)) == (
        "fusion-battery-teal",
    )


def test_sport_fusion_theme_covers_countdown_business() -> None:
    registry = get_cardplan_registry(True)
    theme = registry.require_theme("fusion-sport-orange")
    fusion_style = theme.fusion_ball_style

    assert "GetCountdownDays" in theme.supported_capability_ids
    assert fusion_style is not None
    assert "CountdownOverview" in fusion_style.business_ids
    assert "fusion-sport-orange" in registry.first_layer_theme_ids(
        ("CountdownOverview",)
    )


def test_search_layout_action_rule_omits_legacy_two_support_instruction() -> None:
    action = ActionBinding(
        action_id="action-0",
        event_id="event.open.weather",
        display_label="天气详情",
        call="clickToDeeplink",
        args={},
    )
    contract = HybridBodyContract.model_construct(
        action_bindings=(action,),
        content_action_ids=("action-0",),
        allowed_layout_component_ids=("HeroActionLayout",),
    )

    search_rule = _ux_layout_action_rule(contract)
    compatibility_rule = _ux_layout_action_rule(
        contract.model_copy(
            update={"allowed_layout_component_ids": ("TwoSupportLayout",)}
        )
    )

    assert "layoutActionCandidates" in search_rule
    assert "TwoSupportLayout" not in search_rule
    assert "Support Template" not in search_rule
    assert "TwoSupportLayout" in compatibility_rule
    assert "Support Template" in compatibility_rule


def test_theme_styles_have_distinct_root_content_and_action_scopes() -> None:
    registry = get_cardplan_registry()
    contract = HybridBodyContract.model_construct(
        theme_profile_id="digital-wellbeing-neutral-dark",
        allowed_layout_component_ids=("SingleFocusLayout",),
    )
    action = Nested2Node(
        "Stack",
        (
            {
                "_boundTemplateAction": "event.open",
                "onClick": [{"call": "open"}],
                "height": 36,
                "borderRadius": 18,
            },
        ),
        (
            Nested2Node(
                "Text",
                ("打开", {"fontSize": 14, "fontWeight": 500}),
                (),
            ),
        ),
    )
    content = Nested2Node(
        "Column",
        (),
        (
            Nested2Node("Text", ("默认内容色",), ()),
            Nested2Node("Text", ("显式内容色", {"fontColor": "#FF123456"}), ()),
            Nested2Node("Image", ("icon.svg", {"fillColor": "#FF654321"}), ()),
            Nested2Node("Progress", ({"color": "#FFABCDEF", "value": 50},), ()),
            Nested2Node(
                "Button",
                (
                    {
                        "backgroundColor": "#FFFFFFFF",
                        "onClick": [{"call": "ordinaryButton"}],
                    },
                ),
                (),
            ),
            action,
        ),
    )

    styled = _apply_theme_content_color(content, contract, registry)
    root = _compile_ux_layout_shell(styled, contract, registry)
    root_options = root.values[-1]
    default_text, explicit_text, image, progress, button, styled_action = styled.children

    assert root_options["backgroundColor"] == "#FFFFFFFF"
    assert root_options["padding"] == 12
    template_root = root.children[0]
    assert template_root.component_type == styled.component_type
    assert template_root.children == styled.children
    assert template_root.values[-1]["_id"] == "template_root"
    assert default_text.values[-1]["fontColor"] == "#E6000000"
    assert explicit_text.values[-1]["fontColor"] == "#FF123456"
    assert image.values[-1]["fillColor"] == "#FF654321"
    assert progress.values[-1]["color"] == "#FFABCDEF"
    assert button.values[-1]["fontColor"] == "#E6000000"
    assert "fontColor" not in styled_action.children[0].values[-1]

    action_style = registry.require_theme("digital-wellbeing-neutral-dark").action_style
    assert action_style is not None
    action_template = Nested2Node("PillAction", (), (action,))
    lowered_action = _lower_action_template_tree(
        action_template,
        background=action_style.background_color,
        foreground=action_style.content_color,
    )
    assert lowered_action.values[-1]["backgroundColor"] == action_style.background_color
    assert lowered_action.values[-1]["height"] == 36
    assert lowered_action.values[-1]["borderRadius"] == 18
    assert lowered_action.children[0].values[-1]["fontColor"] == action_style.content_color
    assert lowered_action.children[0].values[-1]["fontSize"] == 14
    assert lowered_action.children[0].values[-1]["fontWeight"] == 500


def test_all_themes_use_fixed_root_inset_and_color_only_action_style() -> None:
    registry = get_cardplan_registry()

    for theme in registry.themes.values():
        assert theme.root_style["padding"] == 12
        assert set(theme.action_style.model_dump(by_alias=True)) == {
            "backgroundColor",
            "contentColor",
        }


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


def test_earphone_hero_covers_connection_and_pair_battery_data() -> None:
    registry = get_cardplan_registry()
    provider_root = registry.source_root / "providers/earphone"
    manifest = json.loads((provider_root / "provider.json").read_text(encoding="utf-8"))
    descriptions = {
        item["templateId"]: item["description"]
        for item in manifest["templates"]
    }
    hero_description = descriptions["BluetoothDeviceOverviewHero@1"]
    rule_text = (provider_root / "layer-docs/second-layer.md").read_text(encoding="utf-8")

    assert "连接状态" in hero_description
    assert "左右耳电量" in hero_description
    assert "BluetoothDeviceOverviewHero@1" in rule_text
    assert "HeroActionLayout@1" in rule_text


def test_nested2_full_document_converts_component_binding_and_data_model():
    profile = read_tersel_protocol_profile()
    task_spec = {
        "dataModelSchema": {
            "data": {
                "weather": {
                    "current": {
                        "temperature": _provider_field("38℃", "string"),
                    }
                }
            }
        }
    }
    source = (
        'Column("card",Text("${data.weather.current.temperature}","body"));\n'
        'data = {"weather":{"current":{"temperature":"38℃"}}}'
    )

    a2ui = convert_tersel_to_a2ui(
        source,
        size="2x2",
        protocol_profile=profile,
        task_spec=task_spec,
    )
    messages = [json.loads(line) for line in a2ui.splitlines()]
    text_component = messages[1]["updateComponents"]["components"][1]
    assert text_component["content"] == (
        "{{ ${/data/weather/current/temperature} }}"
    )
    assert messages[2]["updateDataModel"]["value"] == {
        "data": {"weather": {"current": {"temperature": "38℃"}}}
    }


def test_nested2_full_document_rejects_internal_projection_data():
    profile = read_tersel_protocol_profile()
    source = 'Column("card",Text("天气","body")); data={"_templateProjection":{}}'

    with pytest.raises(TerselConversionError, match="internal projection"):
        convert_tersel_to_a2ui(
            source,
            size="2x2",
            protocol_profile=profile,
        )


def test_nested2_full_document_requires_data_for_every_component_binding():
    profile = read_tersel_protocol_profile()
    task_spec = {
        "dataModelSchema": {
            "data": {"weather": {"temperature": _provider_field("38℃", "string")}}
        }
    }
    source = 'Column("card",Text("${data.weather.temperature}","body")); data={}'

    with pytest.raises(TerselConversionError, match="missing component binding"):
        convert_tersel_to_a2ui(
            source,
            size="2x2",
            protocol_profile=profile,
            task_spec=task_spec,
        )


@pytest.mark.parametrize(
    ("theme_profile_id", "expected_scene", "expected_palette"),
    [
        (
            "fusion-weather-blue",
            "weather",
            FusionBallPalette(*_WEATHER_PALETTE),
        ),
        (
            "fusion-sleep-violet",
            "sleep",
            FusionBallPalette("#FF2B2459", "#FF572BD9", "#FFB398D9"),
        ),
        (
            "fusion-sport-orange",
            "health-sport",
            FusionBallPalette(*_SPORT_PALETTE),
        ),
        (
            "fusion-battery-teal",
            "battery",
            FusionBallPalette("#FF17734C", "#FF26BFA6", "#FF60BF98"),
        ),
        (
            "fusion-schedule-cool",
            "schedule-cool",
            FusionBallPalette("#FF121E59", "#FF2BA2D9", "#FF52CCCC"),
        ),
        ("digital-wellbeing-neutral-dark", None, None),
    ],
)
def test_fusion_ball_palette_is_gated_by_selected_theme(
    theme_profile_id: str,
    expected_scene: str | None,
    expected_palette: FusionBallPalette | None,
):
    theme = get_cardplan_registry(True).require_theme(theme_profile_id)

    fusion_style = theme.fusion_ball_style
    assert (fusion_style.scene if fusion_style else None) == expected_scene
    actual_palette = (
        FusionBallPalette(
            fusion_style.large_color,
            fusion_style.medium_color,
            fusion_style.small_color,
        )
        if fusion_style
        else None
    )
    assert actual_palette == expected_palette


@pytest.mark.parametrize(
    ("theme_id", "primary", "support"),
    [
        ("fusion-weather-blue", "#FFCCDDFF", "#99CCDDFF"),
        ("fusion-sleep-violet", "#FFD9CCFF", "#99D9CCFF"),
        ("fusion-sport-orange", "#FFFFFFFF", "#99FFFFFF"),
        ("fusion-battery-teal", "#FFCCFFF6", "#99CCFFF6"),
        ("fusion-schedule-cool", "#FFCCEEFF", "#B3CCEEFF"),
    ],
)
def test_fusion_theme_content_and_action_colors_are_exact(
    theme_id: str,
    primary: str,
    support: str,
) -> None:
    theme = get_cardplan_registry(True).require_theme(theme_id)

    assert theme.primary_color == primary
    assert theme.support_content_color == support
    assert theme.action_style.content_color == primary
    expected_action_background = (
        "#33CCEEFF" if theme_id == "fusion-schedule-cool" else "#33FFFFFF"
    )
    assert theme.action_style.background_color == expected_action_background


def test_app_usage_theme_uses_the_reviewed_content_and_action_colors() -> None:
    theme = get_cardplan_registry().require_theme("digital-wellbeing-neutral-dark")

    assert theme.primary_color == "#E6000000"
    assert theme.support_content_color == "#99000000"
    assert theme.root_style["backgroundColor"] == "#FFFFFFFF"
    assert theme.root_style["linearGradient"]["colors"] == [
        ["#1A000000", 0],
        ["#00FFFFFF", 1],
    ]
    assert theme.action_style.content_color == "#FF0A59F7"
    assert theme.action_style.background_color == "#1A0A59F7"


def test_non_fusion_weather_theme_uses_the_reviewed_solid_palette() -> None:
    theme = get_cardplan_registry().require_theme("family-weather-care-blue")

    assert theme.primary_color == "#FF1F4799"
    assert theme.support_content_color == "#991F4799"
    assert theme.root_style["backgroundColor"] == "#FFE5EDFE"
    assert "linearGradient" not in theme.root_style
    assert theme.action_style.content_color == "#FF1F4799"
    assert theme.action_style.background_color == "#330A59F7"


def test_non_fusion_sleep_theme_uses_the_reviewed_solid_palette() -> None:
    theme = get_cardplan_registry().require_theme("sleep-night-violet")

    assert theme.primary_color == "#FF401F99"
    assert theme.support_content_color == "#991F4799"
    assert theme.root_style["backgroundColor"] == "#FFEDE6FF"
    assert "linearGradient" not in theme.root_style
    assert theme.action_style.content_color == "#FF401F99"
    assert theme.action_style.background_color == "#33564AF7"


def test_non_fusion_sport_theme_uses_the_reviewed_solid_palette() -> None:
    theme = get_cardplan_registry().require_theme("race-sunrise-action")

    assert theme.primary_color == "#FF99521F"
    assert theme.support_content_color == "#9999521F"
    assert theme.progress_color == "#FF99521F"
    assert theme.progress_background_color == "#3399521F"
    assert theme.root_style.get("backgroundColor") == "#FFFFF0E6"
    assert "linearGradient" not in theme.root_style
    assert theme.action_style.content_color == "#FF99521F"
    assert theme.action_style.background_color == "#3399521F"


def test_non_fusion_earphone_theme_uses_the_reviewed_solid_palette() -> None:
    theme = get_cardplan_registry().require_theme("audio-product-neutral-violet")

    assert theme.primary_color == "#FF52991F"
    assert theme.support_content_color == "#9952991F"
    assert theme.root_style["backgroundColor"] == "#FFF0FFE6"
    assert "linearGradient" not in theme.root_style
    assert theme.action_style.content_color == "#FF52991F"
    assert theme.action_style.background_color == "#3364BB5C"


def test_non_fusion_schedule_theme_uses_the_reviewed_solid_palette() -> None:
    theme = get_cardplan_registry().require_theme("meeting-paper-neutral")

    assert theme.primary_color == "#FF1F4799"
    assert theme.support_content_color == "#991F4799"
    assert theme.progress_color == "#991F4799"
    assert theme.root_style["backgroundColor"] == "#FFE5EDFE"
    assert "linearGradient" not in theme.root_style
    assert theme.action_style.content_color == "#FF1F4799"
    assert theme.action_style.background_color == "#331F4799"


def test_non_fusion_event_countdown_theme_uses_the_reviewed_solid_palette() -> None:
    registry = get_cardplan_registry()
    theme = registry.require_theme("race-night-violet")
    sport_theme = registry.require_theme("race-sunrise-action")

    assert theme.supported_capability_ids == ("GetCountdownDays",)
    assert sport_theme.supported_capability_ids == ("GetHealthAndSportSummary",)
    assert theme.primary_color == "#FF99521F"
    assert theme.support_content_color == "#9999521F"
    assert theme.root_style.get("backgroundColor") == "#FFFFF0E6"
    assert "linearGradient" not in theme.root_style
    assert theme.action_style.content_color == "#FF99521F"
    assert theme.action_style.background_color == "#3399521F"


def test_non_fusion_device_theme_uses_the_reviewed_resource_palette() -> None:
    theme = get_cardplan_registry().require_theme("device-clean-blue-teal")

    assert theme.supported_capability_ids == (
        "GetPhoneBatteryInfo",
        "GetSystemMemInfo",
    )
    assert theme.primary_color == "#E6000000"
    assert theme.support_content_color == "#99000000"
    assert theme.progress_color == "#FFF9A01E"
    assert theme.root_style["backgroundColor"] == "#FFFFFFFF"
    assert theme.root_style["linearGradient"]["colors"] == [
        ["#1AF9A01E", 0],
        ["#00FFFFFF", 1],
    ]
    assert theme.action_style.content_color == "#FF0A59F7"
    assert theme.action_style.background_color == "#1A0A59F7"


def test_disabled_fusion_feature_removes_themes_from_server_registry_view() -> None:
    enabled_registry = get_cardplan_registry(True)
    disabled_registry = get_cardplan_registry(False)
    fusion_theme_ids = {
        theme_id
        for theme_id, theme in enabled_registry.themes.items()
        if theme.fusion_ball_style is not None
    }

    assert fusion_theme_ids
    assert fusion_theme_ids.isdisjoint(disabled_registry.themes)
    assert set(disabled_registry.themes) == {
        "2x2-two-support",
        "audio-product-neutral-violet",
        "device-clean-blue-teal",
        "digital-wellbeing-neutral-dark",
        "family-weather-care-blue",
        "meeting-paper-neutral",
        "race-night-violet",
        "race-sunrise-action",
        "sleep-night-violet",
    }
    assert fusion_theme_ids.isdisjoint(disabled_registry.theme_first_layer_rules)
    assert all(
        fusion_theme_ids.isdisjoint(theme_ids)
        for theme_ids in disabled_registry.palette_scene_theme_ids.values()
    )
    for theme_id in fusion_theme_ids:
        with pytest.raises(ValueError, match="unknown CardPlan theme"):
            disabled_registry.require_theme(theme_id)


def test_fusion_ball_background_expands_to_standard_tersel_components():
    palette = FusionBallPalette(*_WEATHER_PALETTE)
    background = build_fusion_ball_background(palette)

    assert background.component_type == "Stack"
    assert background.values[-1]["_id"] == "fusionBallBackground"
    assert [child.values[-1]["_id"] for child in background.children] == [
        "fusionBallLargeSlot",
        "fusionBallMediumSlot",
        "fusionBallSmallSlot",
        "fusionBallGlassLayer",
    ]
    ball_colors = tuple(
        child.children[0].values[-1]["backgroundColor"]
        for child in background.children[:3]
    )
    assert ball_colors == _WEATHER_PALETTE
    expected_dimensions = {
        "fusionBallBackground": ("100%", "100%"),
        "fusionBallLargeSlot": ("112.5%", "27.5%"),
        "fusionBallLarge": ("116.666667%", "477.272727%"),
        "fusionBallMediumSlot": ("50%", "137.5%"),
        "fusionBallMedium": ("200%", "72.727273%"),
        "fusionBallSmallSlot": ("121.875%", "118.75%"),
        "fusionBallSmall": ("51.282051%", "52.631579%"),
        "fusionBallGlassLayer": ("100%", "100%"),
    }
    background_nodes = [background, *background.children]
    background_nodes.extend(child.children[0] for child in background.children[:3])
    for node in background_nodes:
        component_id = node.values[-1]["_id"]
        width, height = expected_dimensions.get(component_id, (0, 0))
        assert node.values[-1]["width"] == width
        assert node.values[-1]["height"] == height


@pytest.mark.parametrize(
    ("slot_id", "ball_id", "diameter"),
    [
        ("fusionBallLargeSlot", "fusionBallLarge", 210),
        ("fusionBallMediumSlot", "fusionBallMedium", 160),
        ("fusionBallSmallSlot", "fusionBallSmall", 100),
    ],
)
def test_fusion_ball_child_percentages_resolve_against_the_direct_slot(
    slot_id: str,
    ball_id: str,
    diameter: int,
) -> None:
    background = build_fusion_ball_background(FusionBallPalette(*_WEATHER_PALETTE))
    nodes = {node.values[-1]["_id"]: node for node in background.children}
    nodes.update({
        child.children[0].values[-1]["_id"]: child.children[0]
        for child in background.children[:3]
    })
    slot_styles = nodes[slot_id].values[-1]
    ball_styles = nodes[ball_id].values[-1]
    slot_width_ratio = float(slot_styles["width"].removesuffix("%")) / 100
    slot_height_ratio = float(slot_styles["height"].removesuffix("%")) / 100
    ball_width_ratio = float(ball_styles["width"].removesuffix("%")) / 100
    ball_height_ratio = float(ball_styles["height"].removesuffix("%")) / 100

    assert 160 * slot_width_ratio * ball_width_ratio == pytest.approx(diameter)
    assert 160 * slot_height_ratio * ball_height_ratio == pytest.approx(diameter)


def test_fusion_ball_wraps_only_2x2_with_expanded_tersel_background():
    card = Nested2Node(
        "Column",
        (
            "card",
            {
                "_id": "root",
                "padding": 12,
                "backgroundColor": "#FF008FBF",
                "linearGradient": {
                    "direction": "Bottom",
                    "colors": [["#FF008FBF", 0], ["#FF46B1E3", 1]],
                },
                "clip": True,
            },
        ),
        (
            Nested2Node(
                "Column",
                (
                    "compact",
                    {
                        "width": "100%",
                        "height": "100%",
                    },
                ),
                (
                    Nested2Node("Text", ("天气卡片", "compact-title"), ()),
                    Nested2Node("Text", ("天气", "body"), ()),
                    Nested2Node(
                        "Image",
                        (
                            "resources/base/media/icon_weather1.svg",
                            {"fillColor": "#FF000000"},
                        ),
                        (),
                    ),
                    Nested2Node(
                        "Stack",
                        ("action", {"onClick": [{"call": "openWeather"}]}),
                        (
                            Nested2Node(
                                "Image",
                                (
                                    "resources/base/media/phone_fill.svg",
                                    {"fillColor": "#FF64BB5C"},
                                ),
                                (),
                            ),
                            Nested2Node(
                                "Text",
                                ("详情", {"fontColor": "#FF64BB5C"}),
                                (),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )

    palette = FusionBallPalette(*_WEATHER_PALETTE)
    wrapped = apply_fusion_ball_background(
        card,
        size="2x2",
        palette=palette,
    )
    foreground_options = wrapped.children[1].values[-1]

    assert wrapped.component_type == "Stack"
    assert wrapped.values[0] == "card"
    assert wrapped.values[-1]["_id"] == "root"
    assert wrapped.values[-1]["backgroundColor"] == "#00000000"
    assert wrapped.children[0].component_type == "Stack"
    assert wrapped.children[0].values[-1]["_id"] == "fusionBallBackground"
    assert wrapped.children[1].component_type == "Stack"
    assert foreground_options["_id"] == "template_root"
    assert foreground_options["padding"] == 12
    overflow_content = wrapped.children[1].children[0]
    assert overflow_content.component_type == "Stack"
    assert overflow_content.values[-1]["_id"] == (
        "__genui_render_component__template_root"
    )
    assert overflow_content.values[-1]["width"] == "matchParent"
    assert overflow_content.values[-1]["height"] == "matchParent"
    skeleton = overflow_content.children[0]
    assert skeleton.values[-1]["_id"] == "root_1"
    title_text = skeleton.children[0]
    content_text = skeleton.children[1]
    content_icon = skeleton.children[2]
    action_icon = skeleton.children[3].children[0]
    action_text = skeleton.children[3].children[1]
    assert title_text.values == ("天气卡片", "compact-title")
    assert content_text.values == ("天气", "body")
    assert content_icon.values[0] == "resources/base/media/icon_weather1.svg"
    assert content_icon.values[-1]["fillColor"] == "#FF000000"
    assert action_icon.values[-1]["fillColor"] == "#FF64BB5C"
    assert action_text.values[-1]["fontColor"] == "#FF64BB5C"

    assert apply_fusion_ball_background(
        card,
        size="2x4",
        palette=palette,
    ) is card
    assert apply_fusion_ball_background(
        card,
        size="2x2",
        palette=None,
    ) is card


def test_template_compiler_keeps_non_fusion_2x2_theme_background():
    card = Nested2Node(
        "Column",
        (
            "card",
            {
                "_id": "root",
                "backgroundColor": "#FFFFFFFF",
                "linearGradient": {
                    "direction": "Bottom",
                    "colors": [["#1A000000", 0], ["#00FFFFFF", 1]],
                },
            },
        ),
        (Nested2Node("Text", ("会议", "body"), ()),),
    )
    contract = HybridBodyContract.model_construct(
        theme_profile_id="digital-wellbeing-neutral-dark"
    )

    decorated = _apply_template_background(
        card,
        "2x2",
        contract,
        get_cardplan_registry(),
    )

    assert decorated is card
    assert decorated.values[-1]["backgroundColor"] == "#FFFFFFFF"
    assert "linearGradient" in decorated.values[-1]


@pytest.mark.parametrize(
    ("theme_id", "selected_template_ids", "expect_fusion"),
    [
        ("fusion-weather-blue", ("WeatherOverviewFull@1",), True),
        ("fusion-weather-blue", ("WeatherOverviewHero@1",), True),
        ("fusion-weather-blue", ("WeatherOverviewCompact@1",), True),
        (
            "fusion-weather-blue",
            (
                "WeatherOverviewHero@1",
                "PillAction@1",
                "HeroActionLayout@1",
            ),
            True,
        ),
        (
            "fusion-weather-blue",
            (
                "WeatherOverviewCompact@1",
                "PillAction@1",
                "CompactTwoActionLayout@1",
            ),
            True,
        ),
        ("fusion-weather-blue", ("ScheduleOverviewDateFull@1",), False),
        (
            "fusion-weather-blue",
            (
                "WeatherOverviewFull@1",
                "ScheduleOverviewDateFull@1",
            ),
            False,
        ),
        ("fusion-sleep-violet", ("SleepOverviewFull@1",), True),
        ("fusion-sleep-violet", ("ActivityOverviewFull@1",), False),
        ("fusion-sport-orange", ("CountdownOverviewFull@1",), True),
        ("fusion-sleep-violet", ("CountdownOverviewFull@1",), False),
        (
            "fusion-schedule-cool",
            (
                "HeroTitleContentActionLayout@1",
                "WeatherOverviewHeroTitle@1",
                "ScheduleOverviewHeroContent@1",
                "PillAction@1",
            ),
            True,
        ),
        (
            "fusion-weather-blue",
            ("WeatherOverviewHeroTitle@1", "ScheduleOverviewHeroContent@1"),
            False,
        ),
        (
            "meeting-paper-neutral",
            ("WeatherOverviewHeroTitle@1", "ScheduleOverviewHeroContent@1"),
            False,
        ),
        ("fusion-schedule-cool", ("ScheduleOverviewHeroContent@1",), False),
        (
            "fusion-schedule-cool",
            ("WeatherOverviewHeroTitle@1", "ScheduleOverviewDateFull@1"),
            False,
        ),
        (
            "fusion-sport-orange",
            ("CountdownOverviewFull@1", "ActivityOverviewFull@1"),
            False,
        ),
    ],
)
def test_fusion_theme_requires_matching_primary_business(
    theme_id: str,
    selected_template_ids: tuple[str, ...],
    expect_fusion: bool,
) -> None:
    card = Nested2Node(
        "Column",
        ("card", {"_id": "root", "backgroundColor": "#FF121259"}),
        (
            Nested2Node(
                "Column",
                ("compact",),
                (Nested2Node("Text", ("内容", {"fontColor": "#FFCCDDFF"}), ()),),
            ),
        ),
    )
    contract = HybridBodyContract.model_construct(theme_profile_id=theme_id)

    decorated = _apply_template_background(
        card,
        "2x2",
        contract,
        get_cardplan_registry(True),
        selected_template_ids,
    )

    assert (decorated is not card) is expect_fusion
    if expect_fusion:
        assert decorated.children[0].component_type == "Stack"
        assert decorated.children[0].values[-1]["_id"] == "fusionBallBackground"
        assert decorated.children[1].values[-1]["_id"] == "template_root"
        overflow_content = decorated.children[1].children[0]
        assert overflow_content.values[-1]["_id"] == (
            "__genui_render_component__template_root"
        )
        assert decorated.values[-1]["_id"] == "root"
        content = overflow_content.children[0]
        assert content.values[-1]["_id"] == "root_1"
        assert content.children[0].values[-1]["fontColor"] == "#FFCCDDFF"


def test_form_validator_allows_empty_stack_children_but_rejects_empty_column_children():
    profile = A2UIProtocolRegistry(A2UI_FORM_PROTOCOL_PROFILE_ID).get_profile()
    reports = {}
    for component_type in ("Stack", "Column"):
        source = f'{component_type}("card",{{"backgroundColor":"#FF008FBF"}});'
        dsl = convert_tersel_to_a2ui(
            source,
            size="2x2",
            protocol_profile=profile,
        )
        reports[component_type] = validate_card(dsl_text=dsl)

    stack_report = reports.get("Stack")
    column_report = reports.get("Column")
    assert stack_report is not None
    assert column_report is not None
    stack_children_errors = []
    for diagnostic in stack_report.diagnostics:
        is_required_field = diagnostic.code == "DSL_COMPONENT_REQUIRED_FIELD"
        is_children_field = diagnostic.json_pointer.endswith("/children")
        if is_required_field and is_children_field:
            stack_children_errors.append(diagnostic)
    column_children_errors = []
    for diagnostic in column_report.diagnostics:
        is_required_field = diagnostic.code == "DSL_COMPONENT_REQUIRED_FIELD"
        is_children_field = diagnostic.json_pointer.endswith("/children")
        if is_required_field and is_children_field:
            column_children_errors.append(diagnostic)
    assert stack_children_errors == []
    assert len(column_children_errors) == 1


def test_app_usage_template_sizes_separate_compact_and_wide_variants():
    registry = get_cardplan_registry()
    compact_ids = (
        "AppUsageOverviewFull@1",
        "AppUsageOverviewHero@1",
    )
    wide_ids = (
        "AppUsageOverviewWideFull@1",
        "AppUsageOverviewWideHero@1",
    )

    for template_id in compact_ids:
        assert registry.require_template(template_id).variants[0].supported_card_sizes == (
            "2x2",
        )
    for template_id in wide_ids:
        assert registry.require_template(template_id).variants[0].supported_card_sizes == (
            "2x4",
        )


def test_app_usage_templates_use_compact_duration_and_labeled_update_time():
    registry = get_cardplan_registry()
    expected_typography = {
        "AppUsageOverviewFull@1": (24, 10),
        "AppUsageOverviewHero@1": (24, 10),
        "AppUsageOverviewWideFull@1": (30, 12),
        "AppUsageOverviewWideHero@1": (30, 12),
    }

    for template_id, (duration_size, update_size) in expected_typography.items():
        root = registry.require_variant(template_id, "default").root
        text_nodes = _template_nodes(root, "Text")
        duration = None
        update_time = None
        for node in text_nodes:
            value = node.values[0]
            if value.kind == "binding" and value.name == "duration":
                duration = node
            if value.kind != "interpolation":
                continue
            has_updated_at = any(item.name == "updatedAt" for item in value.items)
            if has_updated_at:
                update_time = node
        assert duration is not None
        duration_options = _template_node_options(duration)
        assert duration_options["fontSize"] == duration_size
        assert "minFontSize" not in duration_options

        assert update_time is not None
        assert tuple(
            (item.kind, item.value, item.name) for item in update_time.values[0].items
        ) == (
            ("literal", "更新于 ", None),
            ("binding", None, "updatedAt"),
        )
        update_options = _template_node_options(update_time)
        assert update_options["fontSize"] == update_size
        assert "minFontSize" not in update_options


def test_activity_daily_summary_stacks_supporting_metrics():
    registry = get_cardplan_registry()
    root = registry.require_variant("ActivityOverviewFull@1", "default").root
    supporting_metrics = next(
        node
        for node in reversed(_template_nodes(root, "Column"))
        if len(node.children) == 2 and all(child.component == "Row" for child in node.children)
    )

    assert supporting_metrics.component == "Column"
    supporting_options = _template_node_options(supporting_metrics)
    assert supporting_options["justifyContent"] == "start"
    assert supporting_options.get("alignItems", "start") == "start"
    assert len(supporting_metrics.children) == 2
    assert all(child.component == "Row" for child in supporting_metrics.children)
    assert all(
        _template_node_options(child)["alignItems"] == "center"
        for child in supporting_metrics.children
    )


def test_workout_template_requires_one_complete_training_session():
    registry = get_cardplan_registry()
    definition = registry.require_template("WorkoutOverviewFull@1")

    assert definition.primary_data == ("/exerciseTypeName", "/exerciseDurationText")
    assert definition.secondary_data == ("/exerciseCalorieText", "/exerciseEndTimeText")
    assert definition.optional_data == ()
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
        item for item in workout["templates"] if item["templateId"] == "WorkoutOverviewFull@1"
    )
    assert template["requiredTaskSpecPaths"] == [
        "/data/healthSport/exerciseTypeName",
        "/data/healthSport/exerciseDurationText",
        "/data/healthSport/exerciseCalorieText",
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
    assert "WeatherOverviewFull@1" in weather_candidate["availableTemplateIds"]
    weather_templates = weather_candidate["templates"]
    assert any(
        item["templateId"] == "WeatherOverviewFull@1"
        and "/data/weather/current/temperatureText" in item["requiredTaskSpecPaths"]
        for item in weather_templates
    )
    provider_rules = json.dumps(payload["providerFirstLayerRules"], ensure_ascii=False)
    theme_rules = json.dumps(payload["themeFirstLayerRules"], ensure_ascii=False)
    assert "天气高级组件首层规则" in provider_rules
    assert "手机电量高级组件首层规则" not in provider_rules
    assert "family-weather-care-blue" in theme_rules
    assert "fusion-weather-blue" not in theme_rules


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
    disabled_template_id = "WeatherOverviewFull@1"
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
    assert "WeatherOverviewCompact@1" in first_layer_content
    assert "WeatherOverviewCompact@1" in second_layer_rules


def test_provider_second_layer_guidance_omits_the_full_template_catalog() -> None:
    registry = get_cardplan_registry()

    guidance = registry.provider_second_layer_guidance(("WeatherOverview",))
    serialized = json.dumps(guidance, ensure_ascii=False)

    assert "第二层业务模板使用规则" in serialized
    assert "conditionIcon" in serialized
    assert "- 可用模板：" not in serialized
    assert "WeatherOverviewFull@1" not in serialized
    assert "WeatherOverviewCompact@1" not in serialized


def test_disabled_template_cannot_be_restored_by_first_layer_output():
    registry = CardPlanRegistry(
        disabled_template_ids=("WeatherOverviewFull@1",),
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
            availableTemplateIds=("WeatherOverviewFull@1",),
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


def test_checked_in_template_controls_enable_calendar_and_earphone():
    controls = load_template_controls()
    registry = CardPlanRegistry(
        disabled_provider_ids=controls.disabled_provider_ids,
        disabled_template_ids=controls.disabled_template_ids,
    )

    assert controls.disabled_provider_ids == ()
    assert controls.disabled_template_ids == ()
    assert registry.template_is_enabled("ScheduleOverviewDateFull@1")
    assert registry.template_is_enabled("ScheduleOverviewNextEventHero@1")
    assert registry.template_is_enabled("BluetoothDeviceOverviewEarbudPairFull@1")
    assert registry.template_is_enabled("BluetoothDeviceOverviewHero@1")
    assert registry.template_is_enabled("WeatherOverviewFull@1")


def test_invalid_first_layer_component_selector_fails_closed():
    with pytest.raises(ValueError, match="firstLayerComponentSelector"):
        TemplateControls(
            schemaVersion="template-controls/1",
            firstLayerComponentSelector="invalid",
        )


def test_first_layer_decision_contract_carries_component_template_candidates():
    payload = {
        "theme": "fusion-weather-blue",
        "componentCandidates": [
            {
                "componentId": "WeatherOverview",
                "availableTemplateIds": [
                    "WeatherOverviewFull@1",
                    "WeatherOverviewCompact@1",
                ],
            },
            {
                "componentId": "CalendarOverview",
                "availableTemplateIds": [
                    "ScheduleOverviewDateFull@1",
                    "ScheduleOverviewNextEventLocationFull@1",
                ],
            },
        ],
        "action": ["event.open.weather"],
    }

    decision = TemplateRouteDecision.model_validate(payload)

    assert decision.component_ids == ("WeatherOverview", "CalendarOverview")
    assert decision.model_dump(mode="json", by_alias=True) == payload


def test_template_route_candidate_limit_matches_retrieval_limit() -> None:
    template_ids = tuple(f"HeartRateOverviewCandidate{index}@1" for index in range(24))
    candidate = TemplateComponentCandidate(
        componentId="HeartRateOverview",
        availableTemplateIds=template_ids,
    )

    decision = TemplateRouteDecision(
        theme="fusion-health-blue",
        componentCandidates=(candidate,),
    )

    assert decision.component_candidates[0].available_template_ids == template_ids
    with pytest.raises(ValueError, match="at most 24 Templates"):
        TemplateRouteDecision(
            theme="fusion-health-blue",
            componentCandidates=(
                candidate.model_copy(
                    update={"available_template_ids": template_ids[:13]},
                ),
                TemplateComponentCandidate(
                    componentId="ActivityOverview",
                    availableTemplateIds=template_ids[11:],
                ),
            ),
        )


def test_phone_battery_binding_does_not_auto_include_numeric_soc():
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


def test_sleep_templates_bind_progress_color_to_theme_progress_token() -> None:
    registry = get_cardplan_registry()

    for template_id in (
        "SleepOverviewFull@1",
        "SleepOverviewHero@1",
    ):
        root = registry.require_variant(template_id, "default").root
        progress = _template_nodes(root, "Progress")
        assert len(progress) == 1
        options = progress[0].values[-1]
        assert options.kind == "object"
        color = options.properties.get("color")
        assert color is not None
        assert color.kind == "theme"
        assert color.name == "progressColor"


def test_sleep_hero_requires_both_time_bindings_for_the_fallback_row() -> None:
    registry = get_cardplan_registry()
    root = registry.require_variant("SleepOverviewHero@1", "default").root
    grouped_guards = _template_nodes(root, "IfAllBind")

    assert len(grouped_guards) == 1
    guard_value = grouped_guards[0].values[0]
    assert guard_value.kind == "array"
    assert tuple(item.value for item in guard_value.items) == (
        "startTime",
        "endTime",
    )

    theme_values = {
        "primaryColor": "#FF401F99",
        "supportContentColor": "#991F4799",
        "progressColor": "#991F4799",
        "progressBackgroundColor": "#33564AF7",
    }
    binding_paths = {
        "duration": "${data.healthSport.nightSleepDurationText}",
        "score": "${data.healthSport.sleepScore}",
        "status": "${data.healthSport.sleepStatus}",
        "startTime": "${data.healthSport.fallAsleepTimeText}",
        "endTime": "${data.healthSport.wakeupTimeText}",
    }

    def instantiate(*names: str) -> Nested2Node:
        bindings: dict[str, str] = {}
        for name in names:
            path = binding_paths.get(name)
            assert path is not None
            bindings[name] = path
        return _instantiate_blueprint(root, {}, bindings, theme_values)

    def walk(node: Nested2Node) -> list[Nested2Node]:
        nodes = [node]
        for child in node.children:
            nodes.extend(walk(child))
        return nodes

    def text_values(node: Nested2Node) -> tuple[str, ...]:
        values: list[str] = []
        for item in walk(node):
            if item.component_type != "Text" or not item.values:
                continue
            value = item.values[0]
            if isinstance(value, str):
                values.append(value)
        return tuple(values)

    score = instantiate("duration", "score", "status", "startTime", "endTime")
    assert any(item.component_type == "Progress" for item in walk(score))
    score_text = text_values(score)
    assert not any("状况" in value or "fallAsleepTimeText" in value for value in score_text)

    status = instantiate("duration", "status", "startTime", "endTime")
    assert not any(item.component_type == "Progress" for item in walk(status))
    assert any("状况" in value for value in text_values(status))
    assert not any("fallAsleepTimeText" in value for value in text_values(status))

    complete_time = instantiate("duration", "startTime", "endTime")
    complete_time_text = text_values(complete_time)
    assert any("fallAsleepTimeText" in value for value in complete_time_text)
    assert any("wakeupTimeText" in value for value in complete_time_text)

    partial_time = instantiate("duration", "startTime")
    partial_time_text = text_values(partial_time)
    assert not any("fallAsleepTimeText" in value for value in partial_time_text)
    assert not any("wakeupTimeText" in value for value in partial_time_text)


def test_sport_templates_bind_progress_color_to_theme_progress_token() -> None:
    registry = get_cardplan_registry()

    for template_id, expected_count in (
        ("ActivityOverviewHero@1", 1),
        ("ActivityOverviewFull@1", 1),
        ("WorkoutOverviewFull@1", 0),
    ):
        root = registry.require_variant(template_id, "default").root
        progress = _template_nodes(root, "Progress")
        assert len(progress) == expected_count, template_id
        for node in progress:
            options = node.values[-1]
            assert options.kind == "object"
            color = options.properties.get("color")
            assert color is not None
            assert color.kind == "theme"
            assert color.name == "progressColor"


def test_health_sport_templates_follow_latest_display_contract() -> None:
    registry = get_cardplan_registry()
    expected_descriptions = {
        "ActivityOverviewCompact@1": (
            "每日步数紧凑摘要，展示步数，可使用步数图标。 组件形态：compact。"
        ),
        "ActivityOverviewHero@1": (
            "今日活动步数主视觉，展示步数和固定万步基准进度，可使用步数图标。 "
            "组件形态：hero。"
        ),
        "ActivityOverviewFull@1": (
            "今日活动完整摘要，展示步数、固定万步基准进度、消耗热量和运动距离，"
            "可使用步数图标。 组件形态：full。"
        ),
        "SleepOverviewFull@1": (
            "睡眠情况完整摘要，展示时长和状态，"
            "可选展示得分进度或完整睡眠时段，可使用睡眠图标。 "
            "组件形态：full。"
        ),
        "SleepOverviewHero@1": (
            "睡眠情况主视觉，展示时长，"
            "可选展示得分进度、睡眠状态或完整睡眠时段，可使用睡眠图标。 "
            "组件形态：hero。"
        ),
        "SleepOverviewCompact@1": (
            "睡眠情况紧凑摘要，展示睡眠时长，可使用睡眠图标。 组件形态：compact。"
        ),
    }

    rule_keys = ("ActivityOverview", "SleepOverview")
    rules_list = []
    for item in registry.provider_second_layer_rules(rule_keys):
        rules_list.append(item["content"])
    provider_rules = "\n".join(rules_list)

    for template_id, description in expected_descriptions.items():
        definition = registry.require_template(template_id)
        assert definition.description == description
        assert description in provider_rules

    for template_id in (
        "ActivityOverviewCompact@1",
        "ActivityOverviewHero@1",
        "ActivityOverviewFull@1",
    ):
        definition = registry.require_template(template_id)
        assert set(definition.variants[0].parameters_schema["properties"]) == {
            "stepsIcon"
        }

    for template_id in ("ActivityOverviewHero@1", "ActivityOverviewFull@1"):
        root = registry.require_variant(template_id, "default").root
        progress_options = _template_nodes(root, "Progress")[0].values[-1]
        assert progress_options.properties["total"].value == 10000

    sleep_labels = {
        "SleepOverviewFull@1": {"睡眠情况", "睡眠情况评分"},
        "SleepOverviewHero@1": {"睡眠情况"},
        "SleepOverviewCompact@1": {"睡眠情况时长"},
    }
    for template_id, expected_labels in sleep_labels.items():
        root = registry.require_variant(template_id, "default").root
        literal_labels = {
            node.values[0].value
            for node in _template_nodes(root, "Text")
            if node.values[0].kind == "literal"
        }
        assert expected_labels <= literal_labels

    for template_id in ("SleepOverviewFull@1", "SleepOverviewHero@1"):
        root = registry.require_variant(template_id, "default").root
        progress_options = _template_nodes(root, "Progress")[0].values[-1]
        background_color = progress_options.properties.get("backgroundColor")
        assert background_color is not None
        assert background_color.kind == "theme"
        assert background_color.name == "progressBackgroundColor"


def test_earphone_templates_bind_progress_color_to_theme_support_content() -> None:
    registry = get_cardplan_registry()
    progress_count = 0

    for template_id, definition in registry.templates.items():
        if definition.business_id != "BluetoothDeviceOverview":
            continue
        root = registry.require_variant(template_id, "default").root
        for progress in _template_nodes(root, "Progress"):
            progress_count += 1
            options = progress.values[-1]
            assert options.kind == "object"
            color = options.properties["color"]
            assert color.kind == "theme"
            assert color.name == "supportContentColor"

    assert progress_count == 10


def test_business_artwork_and_monochrome_icons_keep_explicit_color_policies() -> None:
    registry = get_cardplan_registry()
    original_color_props = {
        "AppUsageOverview": {"appIcon"},
        "BluetoothDeviceOverview": {
            "sourceIcon",
            "leftEarIcon",
            "rightEarIcon",
            "deviceIcon",
            "caseIcon",
        },
        "HeartRateOverview": {"sourceIcon"},
        "SleepOverview": {"sourceIcon"},
        "WorkoutOverview": {"sourceIcon"},
    }
    preserved_assets: list[tuple[str, str]] = []
    expected_themed_assets = {
        ("BluetoothDeviceOverviewHero@1", "leftEarIcon"),
        ("BluetoothDeviceOverviewHero@1", "rightEarIcon"),
        ("BluetoothDeviceOverviewEarbudsSupport@1", "deviceIcon"),
        ("BluetoothDeviceOverviewEarbudPairFull@1", "leftEarIcon"),
        ("BluetoothDeviceOverviewEarbudPairFull@1", "rightEarIcon"),
        ("BluetoothDeviceOverviewEarbudPairFull@1", "caseIcon"),
        ("BluetoothDeviceOverviewEarbudPairCompact@1", "leftEarIcon"),
        ("BluetoothDeviceOverviewEarbudPairCompact@1", "rightEarIcon"),
        ("HeartRateOverviewIconCompact@1", "sourceIcon"),
        ("HeartRateOverviewIconHero@1", "sourceIcon"),
        ("HeartRateOverviewUpdatedIconHero@1", "sourceIcon"),
        ("HeartRateOverviewIconSupport@1", "sourceIcon"),
        ("HeartRateOverviewUpdatedIconSupport@1", "sourceIcon"),
        ("SleepOverviewFull@1", "sourceIcon"),
        ("SleepOverviewHero@1", "sourceIcon"),
        ("SleepOverviewCompact@1", "sourceIcon"),
        ("SleepOverviewSupport@1", "sourceIcon"),
    }
    expected_inherited_assets = {
        ("WorkoutOverviewFull@1", "sourceIcon"),
        ("WorkoutOverviewCompact@1", "sourceIcon"),
        ("WorkoutOverviewHero@1", "sourceIcon"),
        ("WorkoutOverviewSupport@1", "sourceIcon"),
    }
    themed_assets: set[tuple[str, str]] = set()
    inherited_assets: set[tuple[str, str]] = set()

    for template_id, definition in registry.templates.items():
        asset_props = original_color_props.get(definition.business_id or "")
        if asset_props is None:
            continue
        root = registry.require_variant(template_id, "default").root
        for image in _template_nodes(root, "Image"):
            source = image.values[0]
            if source.kind != "parameter" or source.name not in asset_props:
                continue
            options = image.values[-1]
            assert options.kind == "object"
            asset_key = (template_id, source.name)
            if asset_key in expected_themed_assets:
                color = options.properties.get("fillColor")
                assert color is not None
                assert color.kind == "theme"
                assert color.name == "supportContentColor"
                assert "_preserveOriginalColor" not in options.properties
                themed_assets.add(asset_key)
                continue
            assert "fillColor" not in options.properties
            if asset_key in expected_inherited_assets:
                assert "_preserveOriginalColor" not in options.properties
                icon = Nested2Node(
                    "Image", ("resources/workout.svg", _template_node_options(image)), (),
                )
                contract = HybridBodyContract.model_construct(
                    theme_profile_id="race-sunrise-action"
                )
                styled = _apply_theme_content_color(icon, contract, registry)
                styled_options = styled.values[-1]
                assert isinstance(styled_options, dict)
                assert styled_options.get("fillColor") == "#FF99521F"
                inherited_assets.add(asset_key)
                continue
            preserve_original = options.properties.get("_preserveOriginalColor")
            assert preserve_original is not None, asset_key
            assert preserve_original.kind == "literal"
            assert preserve_original.value is True
            preserved_assets.append((template_id, source.name))

    assert len(preserved_assets) == 18
    assert themed_assets == expected_themed_assets
    assert inherited_assets == expected_inherited_assets


def test_calendar_monochrome_source_icons_use_the_theme_primary_color() -> None:
    registry = get_cardplan_registry()
    themed_source_icons: list[str] = []

    for template_id, definition in registry.templates.items():
        if definition.business_id != "CalendarOverview":
            continue
        root = registry.require_variant(template_id, "default").root
        for image in _template_nodes(root, "Image"):
            source = image.values[0]
            if source.kind != "parameter" or source.name != "sourceIcon":
                continue
            options = image.values[-1]
            assert options.kind == "object"
            fill_color = options.properties["fillColor"]
            assert fill_color.kind == "theme"
            assert fill_color.name == "primaryColor"
            assert "_preserveOriginalColor" not in options.properties
            themed_source_icons.append(template_id)

    assert len(themed_source_icons) == 1


def test_device_ring_progress_and_icons_bind_to_distinct_theme_colors() -> None:
    providers_root = (
        Path(__file__).resolve().parents[1] / "resources" / "source" / "providers"
    )
    progress_count = 0
    ring_icon_count = 0

    for provider_name in ("battery", "system-memory"):
        bundle = load_provider_bundle(providers_root / provider_name)
        for definition in bundle.templates:
            root = definition.variants[0].root
            progresses = _template_nodes(root, "Progress")
            if not progresses:
                continue
            for progress in progresses:
                progress_count += 1
                color = progress.values[-1].properties["color"]
                assert color.kind == "theme"
                assert color.name == "progressColor"
            for icon in _template_nodes(root, "Image"):
                ring_icon_count += 1
                fill_color = icon.values[-1].properties["fillColor"]
                assert fill_color.kind == "theme"
                assert fill_color.name == "supportContentColor"

    assert progress_count == 10
    assert ring_icon_count == 9


def test_battery_ring_progress_uses_dedicated_track_theme_color() -> None:
    providers_root = (
        Path(__file__).resolve().parents[1] / "resources" / "source" / "providers"
    )
    bundle = load_provider_bundle(providers_root / "battery")
    ring_template_ids = {
        "BatteryOverviewFull@1",
        "BatteryOverviewHero@1",
        "BatteryOverviewWideFull@1",
        "BatteryOverviewCompact@1",
        "BatteryOverviewChargingProgressFull@1",
        "BatteryOverviewPercentRingHero@1",
        "BatteryOverviewChargingRingHero@1",
    }

    for definition in bundle.templates:
        if definition.wire_id not in ring_template_ids:
            continue
        progress = _template_nodes(definition.variants[0].root, "Progress")[0]
        background = progress.values[-1].properties["backgroundColor"]
        assert background.kind == "theme"
        assert background.name == "progressBackgroundColor"


def test_earphone_action_background_is_owned_by_the_theme():
    registry = get_cardplan_registry()
    definition = registry.require_template("BluetoothDeviceOverviewEarbudPairFull@1")
    assert definition.layout_action_style is None
    contract = HybridBodyContract(
        theme_profile_id="audio-product-neutral-violet",
        allowed_components=(),
        allowed_design_tokens=(),
        allowed_layout_tokens=(),
        allowed_template_ids=("BluetoothDeviceOverviewEarbudPairFull@1",),
        required_template_groups=(("BluetoothDeviceOverviewEarbudPairFull@1",),),
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
        foreground="#FF52991F",
        default="#3364BB5C",
    ) == "#3364BB5C"


def test_pr7_visual_fixes_are_encoded_in_provider_cardtpl_variants():
    registry = get_cardplan_registry()

    countdown = registry.require_variant("CountdownOverviewFull@1", "default").root
    assert _template_node_options(countdown)["justifyContent"] == "center"
    countdown_value_row = countdown.children[2]
    assert countdown_value_row.component == "Row"
    assert _template_node_options(countdown_value_row)["justifyContent"] == "center"
    assert len(countdown_value_row.children) == 2
    countdown_value, transparent_unit = countdown_value_row.children
    assert countdown_value.component == "Text"
    assert countdown_value.values[0].kind == "binding"
    assert countdown_value.values[0].name == "days"
    assert transparent_unit.component == "Text"
    assert transparent_unit.values[0].value == "天"
    assert _template_node_options(transparent_unit)["fontSize"] == 1
    assert _template_node_options(transparent_unit)["fontColor"] == "#00000000"
    visible_unit = countdown.children[3]
    assert visible_unit.component == "Text"
    assert visible_unit.values[0].value == "天"
    assert _template_node_options(visible_unit)["fontSize"] == 16
    visible_unit_color = visible_unit.values[-1].properties["fontColor"]
    assert visible_unit_color.kind == "theme"
    assert visible_unit_color.name == "supportContentColor"

    app_usage = registry.require_variant("AppUsageOverviewFull@1", "default").root
    assert _template_node_options(app_usage)["justifyContent"] == "start"
    updated_at_branch = app_usage.children[1]
    assert updated_at_branch.component == "IfBind"
    updated_at_region = updated_at_branch.children[0]
    assert _template_node_options(updated_at_region)["justifyContent"] == "end"
    assert _template_node_options(updated_at_region)["itemMargin"] == 4

    battery = registry.require_variant("BatteryOverviewFull@1", "default").root
    battery_support_color = battery.children[1].values[-1].properties["fontColor"]
    assert battery_support_color.kind == "theme"
    assert battery_support_color.name == "supportContentColor"
    battery_hero = registry.require_variant("BatteryOverviewHero@1", "default").root
    battery_wide = registry.require_variant("BatteryOverviewWideFull@1", "default").root
    assert _template_node_options(battery_hero)["justifyContent"] == "start"
    assert _template_node_options(battery_wide)["justifyContent"] == "start"
    assert battery_hero.children[0].component == "Column"
    assert battery_wide.children[1].component == "Row"
    assert _template_node_options(battery_wide.children[1])["layoutWeight"] == 1
    assert _template_node_options(_template_nodes(battery_hero, "Progress")[0])["width"] == 52
    battery_peer = registry.require_variant(
        "BatteryOverviewCompact@1",
        "default",
    ).root
    assert _template_node_options(battery_peer)["justifyContent"] == "start"
    assert len(_template_nodes(battery_peer, "Image")) == 1
    compact_content_row = battery_peer.children[0]
    assert [child.component for child in compact_content_row.children] == [
        "Stack",
        "Column",
    ]

    resource_peer = registry.require_variant(
        "ResourceUsageOverviewCompact@1",
        "default",
    ).root
    assert _template_node_options(resource_peer)["justifyContent"] == "end"
    assert _template_node_options(_template_nodes(resource_peer, "Image")[0])["width"] == 20
    percent_row = resource_peer.children[1]
    assert _template_node_options(percent_row.children[0])["fontWeight"] == 700
    assert not _template_nodes(resource_peer.children[0], "Text")

    activity = registry.require_variant("ActivityOverviewFull@1", "default").root
    activity_text_options = [
        _template_node_options(node) for node in _template_nodes(activity, "Text")
    ]
    assert all(options.get("fontColor") != "#E6000000" for options in activity_text_options)
    assert sum(options.get("minFontSize") == 10 for options in activity_text_options) == 2


def test_calendar_templates_follow_latest_schedule_contract() -> None:
    registry = get_cardplan_registry()
    calendar = registry.require_ux_business_component("CalendarOverview")

    assert len(calendar.local_template_ids) == 9
    assert "ScheduleOverviewHeroContent@1" in calendar.local_template_ids
    assert "ScheduleOverviewDateFull@1" in calendar.local_template_ids
    assert not any(
        template_id.endswith(("Support@1", "Compact@1"))
        for template_id in calendar.local_template_ids
    )

    date_full = registry.require_template("ScheduleOverviewDateFull@1")
    assert date_full.primary_data == (
        "/events/0/startDate",
        "/events/0/title",
    )
    assert date_full.secondary_data == (
        "/events/0/dtStart",
        "/events/0/dtEnd",
        "/events/0/eventLocation",
    )
    expected_props = {
        "ScheduleOverviewTimezoneFull@1": {"headerLabel"},
        "ScheduleOverviewDateFull@1": {"headerLabel"},
        "ScheduleOverviewNextEventLocationFull@1": {
            "calendarIcon",
            "headerLabel",
        },
    }
    for template_id, prop_names in expected_props.items():
        definition = registry.require_template(template_id)
        properties = definition.variants[0].parameters_schema["properties"]
        assert set(properties) == prop_names
    support_content_text_count = 0
    for template_id in calendar.local_template_ids:
        root = registry.require_variant(template_id, "default").root
        for text_node in _template_nodes(root, "Text"):
            options = text_node.values[-1]
            assert options.kind == "object"
            font_color = options.properties.get("fontColor")
            if font_color is None:
                continue
            if font_color.kind == "theme":
                if font_color.name == "supportContentColor":
                    support_content_text_count += 1
                continue
            assert font_color.value != "#991F4799"
    assert support_content_text_count > 0

    second_layer_rules = registry.provider_second_layer_rules(("CalendarOverview",))
    assert len(second_layer_rules) == 1
    rule_content = second_layer_rules[0].get("content")
    assert isinstance(rule_content, str)
    assert "ScheduleOverviewDateFull@1" in rule_content
    assert "Support" in rule_content


def test_battery_templates_follow_consolidated_state_contract() -> None:
    registry = get_cardplan_registry()
    battery = registry.require_ux_business_component("BatteryOverview")
    expected_template_ids = {
        "BatteryOverviewFull@1",
        "BatteryOverviewHero@1",
        "BatteryOverviewWideFull@1",
        "BatteryOverviewCompact@1",
        "BatteryOverviewHealthLevelHero@1",
        "BatteryOverviewChargingProgressHero@1",
        "BatteryOverviewChargingProgressFull@1",
        "BatteryOverviewChargingDiagnosticsHero@1",
        "BatteryOverviewChargingRingHero@1",
        "BatteryOverviewPercentRingHero@1",
        "BatteryOverviewTemperatureFull@1",
    }

    assert set(battery.local_template_ids) == expected_template_ids
    assert not any(template_id.endswith("Support@1") for template_id in expected_template_ids)
    compact = registry.require_template("BatteryOverviewCompact@1")
    assert compact.primary_data == ("/batterySOC",)
    assert compact.secondary_data == ("/chargingStatusDesc",)
    assert compact.optional_data == ()


def test_genui_rsi_battery_and_countdown_templates_keep_expected_geometry() -> None:
    registry = get_cardplan_registry(True)

    temperature = registry.require_variant(
        "BatteryOverviewTemperatureFull@1",
        "default",
    ).root
    temperature_text_options = [
        _template_node_options(node) for node in _template_nodes(temperature, "Text")
    ]
    assert _template_node_options(temperature)["justifyContent"] == "spaceBetween"
    assert [options["fontSize"] for options in temperature_text_options] == [
        12,
        20,
        12,
        10,
        10,
    ]

    charging_ring = registry.require_variant(
        "BatteryOverviewChargingRingHero@1",
        "default",
    ).root
    assert [child.component for child in charging_ring.children] == ["Stack", "Text"]
    ring_progress = _template_nodes(charging_ring, "Progress")[0]
    assert _template_node_options(ring_progress)["strokeWidth"] == 6

    charging_full = registry.require_variant(
        "BatteryOverviewChargingProgressFull@1",
        "default",
    ).root
    charging_full_progress = _template_nodes(charging_full, "Progress")[0]
    assert _template_node_options(charging_full_progress)["type"] == "ring"
    assert _template_node_options(charging_full_progress)["strokeWidth"] == 6
    assert len(_template_nodes(charging_full, "Row")) == 4

    diagnostics = registry.require_variant(
        "BatteryOverviewChargingDiagnosticsHero@1",
        "default",
    ).root
    assert len(_template_nodes(diagnostics, "Row")) == 4
    assert len(_template_nodes(diagnostics, "Column")) == 3

    compact = registry.require_variant("BatteryOverviewCompact@1", "default").root
    compact_progress = _template_nodes(compact, "Progress")[0]
    assert _template_node_options(compact_progress)["type"] == "ring"
    assert _template_node_options(compact_progress)["strokeWidth"] == 6

    countdown = registry.require_variant("CountdownOverviewHero@1", "default").root
    value_row = countdown.children[2]
    value, unit = value_row.children
    assert _template_node_options(value)["height"] == 48
    assert unit.values[0].value == "天"
    assert _template_node_options(unit)["height"] == 16
    unit_margin = unit.values[-1].properties["margin"]
    assert unit_margin.kind == "object"
    assert unit_margin.properties["bottom"].value == 8


@pytest.mark.asyncio
async def test_calendar_dnd_action_restores_label_icon_and_scene_header():
    task = TaskSpec(
        userQuery="显示下一场会议的完整信息，点击进入免打扰设置",
        size="2x2",
        eventCandidates=[
            EventAction(
                id="event.open.settings.dnd",
                call="clickToDeeplink",
                args={
                    "intentName": "Settings",
                    "bundleName": "com.huawei.hmos.settings",
                    "abilityName": "com.huawei.hmos.settings.MainAbility",
                    "uri": "intelligent_scene_entry",
                },
            )
        ],
        assetCandidates=[
            {
                "src": "resources/base/media/icon_schedule.svg",
                "description": "日历日程图标",
                "sceneTags": ["calendar", "schedule"],
            },
            {
                "src": "resources/base/media/icon_focus.svg",
                "description": "免打扰和专注模式的月亮图标",
                "sceneTags": ["focus"],
            },
        ],
        dataModelSchema={
            "data": {
                "calendar": {
                    "eventCount": _provider_field(1, "integer"),
                    "events": [
                        {
                            "title": _provider_field("项目例会", "string"),
                            "description": _provider_field("评审本周进度", "string"),
                            "dtStart": _provider_field("14:00", "string"),
                            "dtEnd": _provider_field("15:00", "string"),
                            "eventLocation": _provider_field("会议室 A", "string"),
                        }
                    ]
                }
            }
        },
    )
    binding = CandidateDataBinding(
        capabilityId="GetCalendarEvents",
        writeResultTo="/data/calendar",
        candidateOutputFields=[
            "/eventCount",
            "/events/0/title",
            "/events/0/description",
            "/events/0/dtStart",
            "/events/0/dtEnd",
            "/events/0/eventLocation",
        ],
    )
    card_spec = {
        "title": "下一场日程",
        "description": "会议详情和免打扰设置",
        "suggestSize": "2x2",
        "dataBindings": [
            {
                "capabilityId": "GetCalendarEvents",
                "writeResultTo": "/data/calendar",
            }
        ],
    }
    model = _FixedTemplateModel(
        theme_id="meeting-paper-neutral",
        component_id="CalendarOverview",
        available_template_ids=("ScheduleOverviewNextEventHero@1",),
        capability_id="GetCalendarEvents",
        required_fields=("/events/0/title", "/events/0/dtStart"),
        action_id="event.open.settings.dnd",
        body=(
            'Template("HeroActionLayout@1",{},'
            'Template("ScheduleOverviewNextEventHero@1",'
            '{"headerLabel":"下一场日程"}),'
            'Template("PillAction@1",{"actionId":"event.open.settings.dnd",'
            '"label":"免打扰","icon":"resources/base/media/icon_focus.svg"}));'
        ),
    )

    output = await generate_template_a2ui(task, card_spec, (binding,), model)

    assert "下一场日程" in output.a2ui
    assert "下一个日程" not in output.a2ui
    assert "events/0/eventLocation" in output.a2ui
    assert "免打扰" in output.a2ui
    assert "专注模式" not in output.a2ui
    assert "resources/base/media/icon_focus.svg" in output.a2ui
    assert "resources/base/media/icon_schedule.svg" not in output.a2ui
    messages = [json.loads(line) for line in output.a2ui.splitlines()]
    components = messages[1]["updateComponents"]["components"]
    assert components[0]["styles"]["backgroundColor"] == "#FFE5EDFE"
    assert "linearGradient" not in components[0]["styles"]
    header_label = next(
        component for component in components if component.get("content") == "下一场日程"
    )
    header_row = next(
        component
        for component in components
        if header_label["id"] in component.get("children", ())
    )
    hero_content = next(
        component
        for component in components
        if header_row["id"] in component.get("children", ())
    )
    header_styles = header_row.get("styles")
    assert isinstance(header_styles, dict)
    assert header_styles.get("alignItems") == "top"
    assert hero_content.get("itemMargin") == 2
    action = next(component for component in components if component.get("onClick"))
    assert action["styles"]["backgroundColor"] == "#331F4799"
    focus_icon = next(
        component
        for component in components
        if component.get("src") == "resources/base/media/icon_focus.svg"
    )
    assert focus_icon["styles"]["fillColor"] == "#FF1F4799"
    assert model.second_layer_prompt is not None
    second_layer_rule = model.second_layer_prompt[1]["content"]
    assert "HeroActionLayout@1" in second_layer_rule
    assert "headerLabel" in second_layer_rule
    assert "免打扰" in second_layer_rule
    assert "Action 图标必须与动作语义一致" in second_layer_rule


@pytest.mark.asyncio
async def test_calendar_reminder_hero_keeps_start_and_advance_notice():
    task = TaskSpec(
        userQuery="明天上午10点去医院复查，显示时间和提前提醒，点击进入闹钟",
        size="2x2",
        eventCandidates=[
            EventAction(
                id="event.open.clock.alarm",
                call="clickToDeeplink",
                args={
                    "intentName": "Clock",
                    "bundleName": "com.huawei.hmos.clock",
                    "abilityName": "com.huawei.hmos.clock.phone",
                    "uri": "",
                },
            )
        ],
        assetCandidates=[
            {
                "src": "resources/base/media/icon_schedule.svg",
                "description": "日历日程图标",
                "sceneTags": ["calendar", "schedule"],
            },
            {
                "src": "resources/base/media/alarm_fill_1.svg",
                "description": "闹钟和定时提醒图标",
                "sceneTags": ["alarm", "reminder"],
            },
        ],
        dataModelSchema={
            "data": {
                "calendar": {
                    "events": [
                        {
                            "title": _provider_field("医院复查", "string"),
                            "dtStart": _provider_field("10:00", "string"),
                            "remindTime": [_provider_field("15", "string")],
                        }
                    ]
                }
            }
        },
    )
    fields = (
        "/events/0/title",
        "/events/0/dtStart",
        "/events/0/remindTime/0",
    )
    binding = CandidateDataBinding(
        capabilityId="GetCalendarEvents",
        writeResultTo="/data/calendar",
        candidateOutputFields=list(fields),
    )
    card_spec = {
        "title": "明天提醒",
        "description": "日程时间和提前提醒",
        "suggestSize": "2x2",
        "dataBindings": [
            {
                "capabilityId": "GetCalendarEvents",
                "writeResultTo": "/data/calendar",
            }
        ],
    }
    model = _FixedTemplateModel(
        theme_id="meeting-paper-neutral",
        component_id="CalendarOverview",
        available_template_ids=("ScheduleOverviewReminderHero@1",),
        capability_id="GetCalendarEvents",
        required_fields=fields,
        action_id="event.open.clock.alarm",
        body=(
            'Template("HeroActionLayout@1",{},'
            'Template("ScheduleOverviewReminderHero@1",'
            '{"headerLabel":"明天提醒"}),'
            'Template("PillAction@1",{"actionId":"event.open.clock.alarm",'
            '"label":"设置闹钟",'
            '"icon":"resources/base/media/alarm_fill_1.svg"}));'
        ),
    )

    output = await generate_template_a2ui(task, card_spec, (binding,), model)

    assert output.template_ids == (
        "ScheduleOverviewReminderHero@1",
        "PillAction@1",
        "HeroActionLayout@1",
    )
    assert "明天提醒" in output.a2ui
    assert "events/0/title" in output.a2ui
    assert "events/0/dtStart" in output.a2ui
    assert "events/0/remindTime/0" in output.a2ui
    assert "提前" in output.a2ui
    assert "分钟提醒" in output.a2ui
    assert "设置闹钟" in output.a2ui
    assert "resources/base/media/alarm_fill_1.svg" in output.a2ui
    assert "resources/base/media/icon_schedule.svg" not in output.a2ui
    messages = [json.loads(line) for line in output.a2ui.splitlines()]
    components = messages[1]["updateComponents"]["components"]
    timeline_dot = None
    for component in components:
        if component.get("component") == "Stack" and component.get("styles", {}).get("width") == 8:
            if component.get("styles", {}).get("height") == 8:
                timeline_dot = component
                break
    event_title = next(
        component
        for component in components
        if "events/0/title" in str(component.get("content", ""))
    )
    timeline_column = next(
        component
        for component in components
        if timeline_dot["id"] in component.get("children", ())
    )
    assert timeline_column["styles"]["padding"] == {
        "left": 0,
        "top": 4,
        "right": 0,
        "bottom": 2,
    }
    assert timeline_column["itemMargin"] == 4
    assert timeline_dot["styles"]["borderWidth"] == 1.5
    assert timeline_dot["styles"]["borderColor"] == event_title["styles"]["fontColor"]
    assert timeline_dot["styles"]["backgroundColor"] == "#00FFFFFF"
    definition = get_cardplan_registry().require_template(
        "ScheduleOverviewReminderHero@1"
    )
    assert definition.primary_data == ("/events/0/title",)
    assert definition.secondary_data == (
        "/events/0/dtStart",
        "/events/0/remindTime/0",
    )
    assert model.second_layer_prompt is not None
    second_layer_rule = model.second_layer_prompt[1]["content"]
    assert "ScheduleOverviewReminderHero@1" in second_layer_rule
    assert "设置闹钟" in second_layer_rule
    assert "Action 图标必须与动作语义一致" in second_layer_rule
    assert "PillAction@1` 没有匹配素材时省略 `icon`" in second_layer_rule


def test_calendar_timezone_full_keeps_reference_geometry():
    registry = get_cardplan_registry()
    definition = registry.require_template("ScheduleOverviewTimezoneFull@1")
    timezone = registry.require_variant(
        "ScheduleOverviewTimezoneFull@1",
        "default",
    ).root
    timezone_text_options = _template_node_options(timezone.children[1])
    timezone_timeline = timezone.children[2]
    timezone_dot_column = timezone_timeline.children[0]
    timezone_dot = timezone_dot_column.children[0]
    timezone_divider = timezone_dot_column.children[1]

    assert timezone_text_options["height"] == 44
    assert timezone_text_options["fontSize"] == 16
    assert timezone_text_options["maxLines"] == 1
    dot_padding = timezone_dot_column.values[-1].properties["padding"].properties
    timeline_height = timezone_timeline.values[-1].properties.get("height")
    assert timeline_height is not None
    assert timeline_height.kind == "expression"
    height_bindings = tuple(item.name for item in timeline_height.items if item.kind == "binding")
    assert height_bindings == ("start",)
    assert "padding" not in _template_node_options(timezone_timeline)
    assert dot_padding["top"].value == 4
    assert dot_padding["bottom"].value == 2
    assert _template_node_options(timezone_divider)["layoutWeight"] == 1
    assert _template_node_options(timezone_dot)["borderWidth"] == 1.5
    assert _template_node_options(timezone_dot)["backgroundColor"] == "#00FFFFFF"
    assert definition.primary_data == (
        "/events/0/timeZone",
        "/events/0/title",
    )
    assert definition.secondary_data == (
        "/events/0/dtStart",
        "/events/0/dtEnd",
        "/events/0/eventLocation",
    )


def test_calendar_templates_use_explicit_required_data_contracts():
    registry = get_cardplan_registry()
    full = registry.require_template("ScheduleOverviewDateFull@1")
    hero = registry.require_template("ScheduleOverviewNextEventHero@1")

    assert full.primary_data == (
        "/events/0/startDate",
        "/events/0/title",
    )
    assert full.secondary_data == (
        "/events/0/dtStart",
        "/events/0/dtEnd",
        "/events/0/eventLocation",
    )
    assert hero.secondary_data == (
        "/events/0/dtStart",
        "/events/0/dtEnd",
        "/events/0/eventLocation",
    )
    assert full.optional_data == ()
    assert hero.optional_data == ()


def test_calendar_timezone_has_dedicated_facts_without_becoming_time_text():
    task = TaskSpec(
        userQuery="展示跨区会议的标题、时区、全天状态和地点",
        size="2x2",
        eventCandidates=[],
        dataModelSchema={
            "data": {
                "calendar": {
                    "events": [
                        {
                            "title": _provider_field("跨区视频会议", "string"),
                            "timeZone": _provider_field(
                                "America/Los_Angeles", "string"
                            ),
                            "isAllDay": _provider_field(False, "boolean"),
                            "eventLocation": _provider_field("线上会议室", "string"),
                        }
                    ]
                }
            }
        },
    )

    assert extract_schedule_overview_facts(task.dataModelSchema) is None
    timezone_facts = extract_schedule_timezone_facts(task.dataModelSchema)
    assert timezone_facts is not None
    assert timezone_facts.time_zone == "America/Los_Angeles"
    assert schedule_overview_is_eligible(task, {"GetCalendarEvents"})

    selected = apply_content_selectors(task, {"GetCalendarEvents"})
    data = selected.dataModelSchema.get("data")
    assert isinstance(data, dict)
    selectors = data.get("_advancedSelectors")
    assert isinstance(selectors, dict)
    schedule = selectors.get("schedule")
    assert isinstance(schedule, dict)
    assert "timeText" not in schedule
    time_zone = schedule.get("timeZone")
    is_all_day = schedule.get("isAllDay")
    assert isinstance(time_zone, dict)
    assert isinstance(is_all_day, dict)
    assert time_zone.get("sampleValue") == "America/Los_Angeles"
    assert is_all_day.get("sampleValue") is False


@pytest.mark.asyncio
async def test_calendar_timezone_full_requires_time_range() -> None:
    definition = get_cardplan_registry().require_template(
        "ScheduleOverviewTimezoneFull@1"
    )

    assert definition.primary_data == (
        "/events/0/timeZone",
        "/events/0/title",
    )
    assert definition.secondary_data == (
        "/events/0/dtStart",
        "/events/0/dtEnd",
        "/events/0/eventLocation",
    )
    assert "/events/0/isAllDay" not in (
        *definition.primary_data,
        *definition.secondary_data,
        *definition.optional_data,
    )


@pytest.mark.asyncio
async def test_calendar_event_count_template_is_not_advertised() -> None:
    registry = get_cardplan_registry()
    calendar = registry.require_ux_business_component("CalendarOverview")
    rule = registry.provider_second_layer_rules(("CalendarOverview",))[0]["content"]

    assert "ScheduleOverviewEventCountHero@1" not in calendar.local_template_ids
    assert "ScheduleOverviewEventCountHero@1" not in rule
    assert all(
        "/eventCount"
        not in (
            *definition.primary_data,
            *definition.secondary_data,
            *definition.optional_data,
        )
        for template_id in calendar.local_template_ids
        for definition in (registry.require_template(template_id),)
    )


def test_pr7_resource_battery_outer_title_keeps_the_reviewed_subtext_style():
    registry = get_cardplan_registry()
    contract = HybridBodyContract(
        theme_profile_id="fusion-battery-teal",
        allowed_components=(),
        allowed_design_tokens=(),
        allowed_layout_tokens=(),
        allowed_template_ids=(
            "BatteryOverviewCompact@1",
            "ResourceUsageOverviewCompact@1",
        ),
        required_template_groups=(
            ("BatteryOverviewCompact@1",),
            ("ResourceUsageOverviewCompact@1",),
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
                "themeId": "digital-wellbeing-neutral-dark",
                "requiredOutputFieldsByCapability": {
                    "GetAppUsageDuration": [
                        "/appUsage/appName",
                        "/appUsage/durationText",
                    ]
                },
                "action": None,
            }

        async def generate(self, *_args: Any, **_kwargs: Any) -> str:
            return (
                'Template("SingleFocusLayout@1",{},'
                'Template("AppUsageOverviewFull@1",{}));'
            )

    output = await generate_template_a2ui(
        task_spec,
        card_spec,
        (binding,),
        AppUsageTemplateModel(),
    )
    projected_data = output.projected_task_spec.dataModelSchema["data"]
    assert "AppUsageOverview" not in projected_data
    assert "_templateProjection" not in output.tersel
    assert "_advancedSelectors" not in output.tersel
    assert projected_data["appUsageStats"]["appUsage"]["durationText"]["sampleValue"] == (
        "1小时20分钟"
    )
    assert "data = " in output.tersel
    messages = [json.loads(line) for line in output.a2ui.splitlines()]
    components = messages[1]["updateComponents"]["components"]
    component_source = json.dumps(components, ensure_ascii=False)
    duration_path = "/data/appUsageStats/appUsage/durationText"
    assert f"${{{duration_path}}}" in component_source
    assert "_templateProjection" not in component_source
    runtime_data = {
        "data": {
            "appUsageStats": {
                "appUsage": {
                    "appName": "示例应用",
                    "durationText": "2小时5分钟",
                }
            }
        }
    }
    runtime_value: Any = runtime_data
    for part in duration_path.removeprefix("/").split("/"):
        runtime_value = runtime_value[part]
    assert runtime_value == "2小时5分钟"
    assert "/updatedAt" not in output.a2ui


@pytest.mark.asyncio
async def test_optional_empty_template_asset_is_omitted_before_expansion():
    binding = CandidateDataBinding(
        capabilityId="GetAppUsageDuration",
        writeResultTo="/data/appUsageStats",
        candidateOutputFields=[
            "/appUsage/appName",
            "/appUsage/durationText",
        ],
    )

    class EmptyOptionalAssetModel:
        async def generate_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return {
                "themeId": "digital-wellbeing-neutral-dark",
                "requiredOutputFieldsByCapability": {
                    "GetAppUsageDuration": [
                        "/appUsage/appName",
                        "/appUsage/durationText",
                    ]
                },
                "action": None,
            }

        async def generate(self, *_args: Any, **_kwargs: Any) -> str:
            return (
                'Template("SingleFocusLayout@1",{},'
                'Template("AppUsageOverviewFull@1",{"appIcon":""}));'
            )

    output = await generate_template_a2ui(
        _app_usage_task_spec(),
        _app_usage_card_spec(),
        (binding,),
        EmptyOptionalAssetModel(),
    )

    assert '"src":""' not in output.a2ui.replace(" ", "")


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
async def test_advanced_scope_normalizes_two_support_to_layout_theme() -> None:
    task_spec = TaskSpec(
        userQuery="显示昨晚睡眠时长、睡眠得分和今天步数",
        size="2x2",
        dataModelSchema={
            "data": {
                "healthSport": {
                    "sleepScore": _provider_field(82, "integer"),
                    "nightSleepDurationText": _provider_field("7小时1分", "string"),
                    "dailySteps": _provider_field(6200, "integer"),
                }
            }
        },
    )

    async def generate_json(
        prompt: list[dict[str, str]],
        phase: str,
    ) -> dict[str, Any]:
        assert phase == "advanced-component-scope"
        payload = json.loads(prompt[1]["content"])
        assert "2x2-two-support" not in {
            theme["id"] for theme in payload["themes"]
        }
        return {
            "themeId": "race-sunrise-action",
            "advancedComponentIds": ["SleepOverview", "ActivityOverview"],
        }

    scope = await plan_advanced_scope_with_llm(
        task_spec,
        extract_data_shape(task_spec),
        generate_json,
        get_cardplan_registry(),
        ("GetHealthAndSportSummary",),
    )

    assert scope.advanced_component_ids == ("SleepOverview", "ActivityOverview")
    assert scope.theme_id == "2x2-two-support"


@pytest.mark.asyncio
async def test_q094_multi_business_search_is_rejected_before_second_layer():
    task_spec = TaskSpec(
        userQuery="刚睡醒，看看昨晚睡了多久、睡眠得分和今天走了多少步",
        size="2x2",
        eventCandidates=[
            EventAction(
                id="event.open.sleep.details",
                displayLabel="睡眠详情",
                call="clickToIntent",
                args={"intentName": "event.open.sleep.details"},
            ),
            EventAction(
                id="event.open.activity.details",
                displayLabel="活动详情",
                call="clickToIntent",
                args={"intentName": "event.open.activity.details"},
            ),
        ],
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
                "themeId": "race-sunrise-action",
                "requiredOutputFieldsByCapability": {
                    "GetHealthAndSportSummary": [
                        "/sleepScore",
                        "/nightSleepDurationText",
                        "/dailySteps",
                    ]
                },
                "action": [
                    "event.open.sleep.details",
                    "event.open.activity.details",
                ],
            }

        async def generate(
            self,
            prompt: list[dict[str, str]],
            *_args: Any,
            **_kwargs: Any,
        ) -> str:
            self.second_layer_prompt = prompt
            pytest.fail("multi-business Search must not call the second-layer model")

    model = Q094TemplateModel()
    with pytest.raises(TemplateRouteNotApplicable, match="multiple data businesses"):
        await generate_template_a2ui(
            task_spec,
            card_spec,
            (binding,),
            model,
            trusted_template_candidate_ids=(
                "SleepOverviewSupport@1",
                "ActivityOverviewSupport@1",
            ),
        )

    assert model.first_layer_prompt is not None
    first_layer_payload = json.loads(model.first_layer_prompt[1]["content"])
    assert first_layer_payload["candidateOutputFieldsByCapability"] == {
        "GetHealthAndSportSummary": [
            "/sleepScore",
            "/nightSleepDurationText",
            "/dailySteps",
        ]
    }
    assert first_layer_payload["providerFirstLayerRules"]
    assert model.second_layer_prompt is None


class _FixedTemplateModel:
    def __init__(
        self,
        *,
        theme_id: str,
        component_id: str,
        available_template_ids: tuple[str, ...],
        capability_id: str,
        required_fields: tuple[str, ...],
        body: str,
        action_id: str | tuple[str, ...] | None = None,
    ) -> None:
        self.theme_id = theme_id
        self.component_id = component_id
        self.available_template_ids = available_template_ids
        self.capability_id = capability_id
        self.required_fields = required_fields
        self.action_id = action_id
        self.body = body
        self.second_layer_prompt: list[dict[str, str]] | None = None

    async def generate_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {
            "themeId": self.theme_id,
            "requiredOutputFieldsByCapability": {
                self.capability_id: list(self.required_fields)
            },
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


@pytest.mark.asyncio
async def test_q001_sleep_assistant_generates_hero_without_sleep_score() -> None:
    task_spec = TaskSpec(
        userQuery="显示今日睡眠时长，点击可打开闹钟快速设置提醒",
        size="2x2",
        eventCandidates=[
            EventAction(
                id="event.open.clock.alarm",
                call="clickToDeeplink",
                args={
                    "intentName": "Clock",
                    "bundleName": "com.huawei.hmos.clock",
                    "abilityName": "com.huawei.hmos.clock.phone",
                    "uri": "",
                },
            )
        ],
        dataModelSchema={
            "data": {
                "healthSport": {
                    "nightSleepDurationText": _provider_field("7小时1分", "string"),
                    "sleepStatus": _provider_field("良好", "string"),
                    "fallAsleepTimeText": _provider_field("23:15", "string"),
                    "wakeupTimeText": _provider_field("07:30", "string"),
                }
            }
        },
    )
    binding = CandidateDataBinding(
        capabilityId="GetHealthAndSportSummary",
        writeResultTo="/data/healthSport",
        candidateOutputFields=[
            "/nightSleepDurationText",
            "/sleepStatus",
            "/fallAsleepTimeText",
            "/wakeupTimeText",
        ],
    )
    card_spec = {
        "title": "睡眠助手",
        "description": "今日睡眠时长与闹钟入口",
        "suggestSize": "2x2",
        "dataBindings": [
            {
                "capabilityId": "GetHealthAndSportSummary",
                "writeResultTo": "/data/healthSport",
            }
        ],
    }
    model = _FixedTemplateModel(
        theme_id="sleep-night-violet",
        component_id="SleepOverview",
        available_template_ids=("SleepOverviewHero@1",),
        capability_id="GetHealthAndSportSummary",
        required_fields=("/nightSleepDurationText",),
        action_id="event.open.clock.alarm",
        body=(
            'Template("HeroActionLayout@1",{},'
            'Template("SleepOverviewHero@1",{}),'
            'Template("PillAction@1",{"actionId":"event.open.clock.alarm",'
            '"label":"设置闹钟"}));'
        ),
    )

    output = await generate_template_a2ui(task_spec, card_spec, (binding,), model)

    messages = [json.loads(line) for line in output.a2ui.splitlines()]
    assert len(messages) >= 2
    update_components = messages[1].get("updateComponents")
    assert isinstance(update_components, dict)
    components = update_components.get("components")
    assert isinstance(components, list)
    component_payload = json.dumps(components, ensure_ascii=False)
    assert "nightSleepDurationText" in component_payload
    assert "sleepStatus" in component_payload
    assert "设置闹钟" in component_payload
    assert "sleepScore" not in component_payload
    assert "fallAsleepTimeText" not in component_payload
    assert "IfAllBind" not in component_payload


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


def _bluetooth_case_status_task(
    device_icon: str = "resources/base/media/earphone_case_16644.svg",
) -> TaskSpec:
    icon_description = (
        "耳机收纳盒实心图标"
        if device_icon.endswith("earphone_case_16644.svg")
        else "整副蓝牙耳机图标"
    )
    return TaskSpec(
        userQuery=(
            "睡前想听半小时歌又怕睡过头，帮我做个卡片，卡片上需要有耳机盒"
            "充没充、电量够不够，能进歌单和闹钟。"
        ),
        size="2x2",
        eventCandidates=[
            EventAction(
                id="event.open.music.daily",
                call="clickToDeeplink",
                args={
                    "intentName": "Music",
                    "bundleName": "",
                    "abilityName": "",
                    "uri": "hwmusic://daily",
                },
            ),
            EventAction(
                id="event.open.clock.alarm",
                call="clickToDeeplink",
                args={
                    "intentName": "Clock",
                    "bundleName": "com.huawei.hmos.clock",
                    "abilityName": "com.huawei.hmos.clock.phone",
                    "uri": "",
                },
            ),
        ],
        assetCandidates=[
            {
                "src": device_icon,
                "description": icon_description,
                "sceneTags": ["device", "audio"],
            },
            {
                "src": "resources/base/media/music_fill.svg",
                "description": "每日歌单音乐图标",
                "sceneTags": ["music", "media"],
            },
            {
                "src": "resources/base/media/alarm_fill_1.svg",
                "description": "闹钟图标",
                "sceneTags": ["alarm", "reminder"],
            },
        ],
        dataModelSchema={
            "data": {
                "earphone": {
                    "batteryLevel": _provider_field(80, "integer"),
                    "chargingStatusDesc": _provider_field("充电中", "string"),
                    "leftChargingStatusDesc": _provider_field("未充电", "string"),
                    "rightChargingStatusDesc": _provider_field("充电中", "string"),
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


@pytest.mark.parametrize(
    ("fields", "expected_percent", "expected_text"),
    [
        ({"batterySOC": _provider_field(68, "integer")}, 68, "68%"),
        ({"batterySOCText": _provider_field("15%", "string")}, 15, "15%"),
    ],
)
def test_battery_facts_accept_numeric_or_text_soc(
    fields: dict[str, Any],
    expected_percent: int,
    expected_text: str,
) -> None:
    facts = extract_battery_overview_facts({"data": {"phoneBattery": fields}})

    assert facts is not None
    assert facts.level_percent == expected_percent
    assert facts.level_text == expected_text


def test_state_independent_battery_compact_accepts_normal_battery_facts() -> None:
    _validate_provider_template_state(
        "BatteryOverviewCompact@1",
        "default",
        _battery_task(),
        business_names={"BatteryOverview"},
    )


def test_support_provider_family_identity_preserves_support_shape() -> None:
    assert provider_template_family_identity(
        "BluetoothDeviceOverviewEarbudsSupport@1"
    ) == (
        "BluetoothDeviceOverview@1",
        "earbudsSupport",
    )


@pytest.mark.parametrize(
    "template_id",
    (
        "BatteryOverviewCompact@1",
        "BatteryOverviewChargingProgressFull@1",
        "BatteryOverviewChargingRingHero@1",
        "BatteryOverviewFull@1",
        "BatteryOverviewHero@1",
        "BatteryOverviewTemperatureFull@1",
        "BatteryOverviewWideFull@1",
    ),
)
def test_generic_battery_templates_accept_trusted_battery_state(
    template_id: str,
) -> None:
    for battery_level, charging_status in (
        (15, "未充电"),
        (68, "正在充电"),
    ):
        task = _battery_task()
        task.dataModelSchema["data"]["phoneBattery"]["batterySOC"] = _provider_field(
            battery_level,
            "integer",
        )
        task.dataModelSchema["data"]["phoneBattery"]["batterySOCText"] = _provider_field(
            f"{battery_level}%",
            "string",
        )
        task.dataModelSchema["data"]["phoneBattery"]["chargingStatusDesc"] = (
            _provider_field(charging_status, "string")
        )
        _validate_provider_template_state(
            template_id,
            "default",
            task,
            business_names={"BatteryOverview"},
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
            "看一下耳机的连接状态、名称和完整电量",
            (
                "/isConnected",
                "/earphoneName",
                "/batteryLevel",
                "/leftBatteryLevel",
                "/rightBatteryLevel",
            ),
            "full",
            "isConnected",
        ),
        (
            "看看我的蓝牙耳机连上没有，用电量环显示耳机盒还剩多少电",
            (
                "/isConnected",
                "/earphoneName",
                "/batteryLevel",
                "/leftBatteryLevel",
                "/rightBatteryLevel",
            ),
            "full",
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
    template_ids = {
        "full": "BluetoothDeviceOverviewEarbudPairFull@1",
    }
    template_id = template_ids.get(variant)
    assert template_id is not None
    binding = CandidateDataBinding(
        capabilityId="GetEarphoneInfo",
        writeResultTo="/data/earphone",
        candidateOutputFields=list(required_fields),
    )
    body = (
        'Template("SingleFocusLayout@1",{},Template('
        f'"{template_id}",{{}}));'
    )
    model = _FixedTemplateModel(
        theme_id="audio-product-neutral-violet",
        component_id="BluetoothDeviceOverview",
        available_template_ids=(template_id,),
        capability_id="GetEarphoneInfo",
        required_fields=required_fields,
        body=body,
    )

    output = await generate_template_a2ui(
        _bluetooth_task(query),
        _bluetooth_card_spec(),
        (binding,),
        model,
    )

    assert output.template_ids == (template_id, "SingleFocusLayout@1")
    assert "isConnected" in output.a2ui
    assert expected_path in output.a2ui
    assert "已连接" in output.a2ui and "未连接" in output.a2ui


def test_bluetooth_case_status_facts_do_not_require_device_identity() -> None:
    task_spec = _bluetooth_case_status_task()

    facts = extract_bluetooth_device_overview_facts(task_spec.dataModelSchema)

    assert facts is not None
    assert facts.is_connected is None
    assert facts.earphone_name is None
    assert facts.case_battery_level == 80
    assert facts.case_charging_status == "充电中"
    assert bluetooth_device_overview_is_eligible(task_spec, {"GetEarphoneInfo"})


@pytest.mark.asyncio
async def test_bluetooth_hero_supports_connection_action() -> None:
    binding = CandidateDataBinding(
        capabilityId="GetEarphoneInfo",
        writeResultTo="/data/earphone",
        candidateOutputFields=[
            "/isConnected",
            "/earphoneName",
            "/leftBatteryLevel",
            "/rightBatteryLevel",
        ],
    )
    task_spec = _bluetooth_task("看看耳机是否连接，并打开蓝牙设置").model_copy(
        update={
            "eventCandidates": [
                EventAction(
                    id="event.open.settings.bluetooth",
                    displayLabel="蓝牙设置",
                    call="clickToIntent",
                    args={"intentName": "event.open.settings.bluetooth"},
                )
            ],
            "assetCandidates": [
                {
                    "src": "resources/base/media/icon_earphone.svg",
                    "description": "整副蓝牙耳机图标",
                    "sceneTags": ["audio", "earphone", "product"],
                }
            ],
        }
    )
    model = _FixedTemplateModel(
        theme_id="audio-product-neutral-violet",
        component_id="BluetoothDeviceOverview",
        available_template_ids=("BluetoothDeviceOverviewHero@1",),
        capability_id="GetEarphoneInfo",
        required_fields=(
            "/isConnected",
            "/earphoneName",
            "/leftBatteryLevel",
            "/rightBatteryLevel",
        ),
        action_id="event.open.settings.bluetooth",
        body=(
            'Template("HeroActionLayout@1",{},'
            'Template("BluetoothDeviceOverviewHero@1",{}),'
            'Template("PillAction@1",{"actionId":"event.open.settings.bluetooth",'
            '"label":"蓝牙设置"}));'
        ),
    )

    output = await generate_template_a2ui(
        task_spec,
        _bluetooth_card_spec(),
        (binding,),
        model,
    )

    assert output.template_ids == (
        "BluetoothDeviceOverviewHero@1",
        "PillAction@1",
        "HeroActionLayout@1",
    )
    assert "isConnected" in output.a2ui
    assert "earphoneName" in output.a2ui
    assert "leftBatteryLevel" in output.a2ui
    assert "rightBatteryLevel" in output.a2ui
    messages = [json.loads(line) for line in output.a2ui.splitlines()]
    components = {
        item["id"]: item for item in messages[1]["updateComponents"]["components"]
    }
    battery_pair: dict[str, Any] | None = None
    for item in components.values():
        if item.get("component") != "Row":
            continue
        styles = item.get("styles", {})
        if styles.get("width") != 100:
            continue
        if styles.get("height") != 16:
            continue
        if item.get("itemMargin") != 0:
            continue
        if styles.get("justifyContent") != "spaceBetween":
            continue
        battery_pair = item
        break
    assert battery_pair is not None
    ear_rows = [components[child_id] for child_id in battery_pair["children"]]
    assert len(ear_rows) == 2
    assert all(row["component"] == "Row" for row in ear_rows)
    assert all(row["itemMargin"] == 2 for row in ear_rows)
    assert all(row["styles"]["justifyContent"] == "start" for row in ear_rows)


@pytest.mark.asyncio
async def test_bluetooth_music_action_can_use_full_with_icon_action():
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
            ],
            "assetCandidates": [
                {
                    "src": "resources/base/media/icon_music.svg",
                    "description": "音乐动作图标",
                    "sceneTags": ["action", "music"],
                }
            ],
        }
    )
    model = _FixedTemplateModel(
        theme_id="audio-product-neutral-violet",
        component_id="BluetoothDeviceOverview",
        available_template_ids=("BluetoothDeviceOverviewEarbudPairFull@1",),
        capability_id="GetEarphoneInfo",
        required_fields=(
            "/isConnected",
            "/earphoneName",
            "/batteryLevel",
            "/leftBatteryLevel",
            "/rightBatteryLevel",
        ),
        action_id="event.open.music.daily",
        body=(
            'Template("FullIconActionLayout@1",{},'
            'Template("BluetoothDeviceOverviewEarbudPairFull@1",{}),'
            'Template("IconAction@1",{"actionId":"event.open.music.daily",'
            '"icon":"resources/base/media/icon_music.svg"}));'
        ),
    )

    output = await generate_template_a2ui(
        task_spec,
        _bluetooth_card_spec(),
        (binding,),
        model,
    )

    assert output.template_ids == (
        "BluetoothDeviceOverviewEarbudPairFull@1",
        "IconAction@1",
        "FullIconActionLayout@1",
    )
    assert "event.open.music.daily" in output.a2ui
    assert "resources/base/media/icon_music.svg" in output.a2ui


def test_bluetooth_identity_without_battery_is_a_complete_provider_fact():
    facts = extract_bluetooth_device_overview_facts(
        {
            "data": {
                "earphone": {
                    "isConnected": _provider_field(True, "boolean"),
                    "earphoneName": _provider_field("FreeBuds Pro", "string"),
                }
            }
        }
    )

    assert facts is not None
    assert facts.is_connected is True
    assert facts.earphone_name == "FreeBuds Pro"
    assert facts.battery_part_count == 0


@pytest.mark.asyncio
async def test_bluetooth_music_action_uses_hero_pair_data():
    binding = CandidateDataBinding(
        capabilityId="GetEarphoneInfo",
        writeResultTo="/data/earphone",
        candidateOutputFields=[
            "/isConnected",
            "/earphoneName",
            "/leftBatteryLevel",
            "/rightBatteryLevel",
        ],
    )
    task_spec = _bluetooth_task(
        "看看耳机连上没、叫什么名字，并打开每日推荐",
    ).model_copy(
        update={
            "eventCandidates": [
                EventAction(
                    id="event.open.music.daily",
                    displayLabel="每日推荐",
                    call="clickToIntent",
                    args={"intentName": "event.open.music.daily"},
                )
            ],
            "dataModelSchema": {
                "data": {
                    "earphone": {
                        "isConnected": _provider_field(True, "boolean"),
                        "earphoneName": _provider_field("FreeBuds Pro", "string"),
                        "leftBatteryLevel": _provider_field(76, "integer"),
                        "rightBatteryLevel": _provider_field(78, "integer"),
                    }
                }
            },
        }
    )
    model = _FixedTemplateModel(
        theme_id="audio-product-neutral-violet",
        component_id="BluetoothDeviceOverview",
        available_template_ids=("BluetoothDeviceOverviewHero@1",),
        capability_id="GetEarphoneInfo",
        required_fields=(
            "/isConnected",
            "/earphoneName",
            "/leftBatteryLevel",
            "/rightBatteryLevel",
        ),
        action_id="event.open.music.daily",
        body=(
            'Template("HeroActionLayout@1",{},'
            'Template("BluetoothDeviceOverviewHero@1",{}),'
            'Template("PillAction@1",{"actionId":"event.open.music.daily",'
            '"label":"每日推荐"}));'
        ),
    )
    card_spec = _bluetooth_card_spec() | {"title": "耳机听歌入口"}

    output = await generate_template_a2ui(task_spec, card_spec, (binding,), model)

    assert output.template_ids == (
        "BluetoothDeviceOverviewHero@1",
        "PillAction@1",
        "HeroActionLayout@1",
    )
    assert "FreeBuds Pro" in output.a2ui
    assert "isConnected" in output.a2ui
    assert "earphoneName" in output.a2ui
    messages = [json.loads(line) for line in output.a2ui.splitlines()]
    update_components = messages[1]["updateComponents"]
    component_ids = {
        component["id"] for component in update_components["components"]
    }
    assert update_components["root"] == "root"
    assert "root" in component_ids
    assert "template_root" in component_ids
    assert "fusionBallBackground" not in component_ids
    root = next(
        component
        for component in update_components["components"]
        if component["id"] == "root"
    )
    assert "template_root" in root["children"]
    assert model.second_layer_prompt is not None
    second_layer_user = model.second_layer_prompt[1]["content"]
    contracts_line = next(
        line
        for line in second_layer_user.splitlines()
        if line.startswith("templateContracts=")
    )
    contracts = json.loads(contracts_line.removeprefix("templateContracts="))
    hero_contract = next(
        item
        for item in contracts
        if item["templateId"] == "BluetoothDeviceOverviewHero@1"
    )
    assert set(hero_contract["propsSchema"]["properties"]) == {
        "leftEarIcon",
        "rightEarIcon",
    }


@pytest.mark.asyncio
async def test_2x2_battery_pill_action_uses_generic_hero_template():
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
        theme_id="fusion-battery-teal",
        component_id="BatteryOverview",
        available_template_ids=("BatteryOverviewHero@1",),
        capability_id="GetPhoneBatteryInfo",
        required_fields=("/batterySOC", "/batteryCapacityLevelDesc"),
        action_id="event.setPowerSavingMode",
        body=(
            'Template("HeroActionLayout@1",{},'
            'Template("BatteryOverviewHero@1",'
            '{"batteryIcon":"resources/base/media/battery_leaf_fill.svg"}),'
            'Template("PillAction@1",{"actionId":"event.setPowerSavingMode",'
            '"label":"省电模式"}));'
        ),
    )

    output = await generate_template_a2ui(
        _battery_task(),
        _battery_card_spec(),
        (binding,),
        model,
        enable_fusion_ball=True,
    )

    assert output.template_ids == (
        "BatteryOverviewHero@1",
        "PillAction@1",
        "HeroActionLayout@1",
    )
    assert model.second_layer_prompt is not None
    second_layer_system = model.second_layer_prompt[0]["content"]
    second_layer_user = model.second_layer_prompt[1]["content"]
    assert "类 Tersel 调用树" in second_layer_system
    assert "完整签名" in second_layer_system
    action_contract_line = next(
        line for line in second_layer_user.splitlines() if line.startswith("actionContracts=")
    )
    action_contracts = json.loads(action_contract_line.removeprefix("actionContracts="))
    assert action_contracts[0]["templateId"] == "PillAction@1"
    assert action_contracts[0]["callSyntax"] == (
        'Template("PillAction@1", <props matching propsSchema>)'
    )
    assert action_contracts[0]["propsSchema"]["required"] == ["actionId", "label"]
    assert action_contracts[0]["propsSchema"]["additionalProperties"] is False
    action_candidate_line = next(
        line
        for line in second_layer_user.splitlines()
        if line.startswith("selectedActionCandidates=")
    )
    action_candidates = json.loads(
        action_candidate_line.removeprefix("selectedActionCandidates=")
    )
    assert action_candidates[0]["actionId"] == "event.setPowerSavingMode"
    assert action_candidates[0]["label"] == "省电模式"
    layout_contract_line = next(
        line for line in second_layer_user.splitlines() if line.startswith("layoutContracts=")
    )
    layout_contracts = json.loads(layout_contract_line.removeprefix("layoutContracts="))
    assert layout_contracts[0]["templateId"] == "HeroActionLayout@1"
    template_contract_line = next(
        line for line in second_layer_user.splitlines() if line.startswith("templateContracts=")
    )
    template_contracts = json.loads(
        template_contract_line.removeprefix("templateContracts=")
    )
    hero_contract = next(
        contract
        for contract in template_contracts
        if contract["templateId"] == "BatteryOverviewHero@1"
    )
    assert hero_contract["callSyntax"] == (
        'Template("BatteryOverviewHero@1", <props matching propsSchema>)'
    )
    assert hero_contract["propsSchema"]["additionalProperties"] is False
    assert '"height":36' in output.a2ui
    assert "省电模式" in output.a2ui
    assert "batterySOC" in output.a2ui
    assert "batteryCapacityLevelDesc" in output.a2ui
    messages = [json.loads(line) for line in output.a2ui.splitlines()]
    components = {
        item["id"]: item for item in messages[1]["updateComponents"]["components"]
    }
    assert messages[1]["updateComponents"]["root"] == "root"
    assert components["root"]["children"] == [
        "fusionBallBackground",
        "template_root",
    ]
    content = components["template_root"]
    assert content["styles"] == {
        "width": "matchParent",
        "height": "matchParent",
        "padding": 12,
    }
    assert content["children"] == ["__genui_render_component__template_root"]
    overflow_content = components["__genui_render_component__template_root"]
    assert overflow_content["component"] == "Stack"
    assert overflow_content["children"] == ["root_1"]
    assert overflow_content["styles"] == {
        "width": "matchParent",
        "height": "matchParent",
    }
    assert components["fusionBallLarge"]["styles"]["width"] == "116.666667%"
    assert components["fusionBallLarge"]["styles"]["height"] == "477.272727%"
    assert components["fusionBallMedium"]["styles"]["width"] == "200%"
    assert components["fusionBallMedium"]["styles"]["height"] == "72.727273%"
    assert components["fusionBallSmall"]["styles"]["width"] == "51.282051%"
    assert components["fusionBallSmall"]["styles"]["height"] == "52.631579%"
    layout = components["root_1"]
    assert layout["component"] == "Column"
    assert layout["itemMargin"] == 8
    assert layout["styles"] == {
        "width": "matchParent",
        "height": "matchParent",
        "justifyContent": "start",
        "alignItems": "center",
    }
    hero_slot, action_slot = (components[child_id] for child_id in layout["children"])
    assert hero_slot["styles"] == {"width": "matchParent", "layoutWeight": 1}
    assert action_slot["styles"] == {"width": "matchParent", "height": 36}
    action = components[action_slot["children"][0]]
    assert action["component"] == "Stack"
    assert action["onClick"] == [
        {
            "call": "clickToIntent",
            "args": {
                "intentName": "SetSettingSwitch",
                "params": {
                    "appBundleName": "com.huawei.hmos.settings",
                    "itemName": "battery_saving_mode",
                    "switchFlag": 0,
                },
            },
        }
    ]
    assert "_boundTemplateAction" not in output.a2ui


@pytest.mark.asyncio
async def test_pill_action_template_rejects_mismatched_label_props():
    binding = CandidateDataBinding(
        capabilityId="GetPhoneBatteryInfo",
        writeResultTo="/data/phoneBattery",
        candidateOutputFields=["/batterySOC", "/chargingStatusDesc"],
    )
    model = _FixedTemplateModel(
        theme_id="fusion-battery-teal",
        component_id="BatteryOverview",
        available_template_ids=("BatteryOverviewHero@1",),
        capability_id="GetPhoneBatteryInfo",
        required_fields=("/batterySOC",),
        action_id="event.setPowerSavingMode",
        body=(
            'Template("HeroActionLayout@1",{},'
            'Template("BatteryOverviewHero@1",{}),'
            'Template("PillAction@1",{"actionId":"event.setPowerSavingMode",'
            '"label":"天气详情"}));'
        ),
    )

    with pytest.raises(TemplateGenerationError, match="template body validation failed"):
        await generate_template_a2ui(
            _battery_task(),
            _battery_card_spec(),
            (binding,),
            model,
            enable_fusion_ball=True,
        )


@pytest.mark.asyncio
async def test_2x2_battery_percent_ring_hero_does_not_require_capacity_level():
    binding = CandidateDataBinding(
        capabilityId="GetPhoneBatteryInfo",
        writeResultTo="/data/phoneBattery",
        candidateOutputFields=[
            "/batterySOC",
            "/batterySOCText",
            "/chargingStatusDesc",
        ],
    )
    task_spec = _battery_task()
    phone_battery = task_spec.dataModelSchema["data"]["phoneBattery"]
    del phone_battery["batteryCapacityLevelDesc"]
    model = _FixedTemplateModel(
        theme_id="fusion-battery-teal",
        component_id="BatteryOverview",
        available_template_ids=("BatteryOverviewPercentRingHero@1",),
        capability_id="GetPhoneBatteryInfo",
        required_fields=("/batterySOC",),
        action_id="event.setPowerSavingMode",
        body=(
            'Template("HeroActionLayout@1",{},'
            'Template("BatteryOverviewPercentRingHero@1",'
            '{"batteryIcon":"resources/base/media/battery_leaf_fill.svg"}),'
            'Template("PillAction@1",{"actionId":"event.setPowerSavingMode",'
            '"label":"省电模式"}));'
        ),
    )

    output = await generate_template_a2ui(
        task_spec,
        _battery_card_spec(),
        (binding,),
        model,
        enable_fusion_ball=True,
    )

    assert output.template_ids == (
        "BatteryOverviewPercentRingHero@1",
        "PillAction@1",
        "HeroActionLayout@1",
    )
    assert "batterySOC" in output.a2ui
    assert "batterySOCText" not in output.a2ui
    assert "batteryCapacityLevelDesc" not in output.a2ui
    assert "省电模式" in output.a2ui


@pytest.mark.asyncio
async def test_2x2_battery_charging_progress_hero_uses_status_fields():
    binding = CandidateDataBinding(
        capabilityId="GetPhoneBatteryInfo",
        writeResultTo="/data/phoneBattery",
        candidateOutputFields=[
            "/batterySOCText",
            "/chargingStatusDesc",
            "/healthStatusDesc",
        ],
    )
    task_spec = _battery_task()
    task_spec.userQuery = "睡前想把手机充满，看看剩余电量、充上没和电池健康咋样。"
    data = task_spec.dataModelSchema.get("data")
    assert isinstance(data, dict)
    phone_battery = data.get("phoneBattery")
    assert isinstance(phone_battery, dict)
    phone_battery.pop("batterySOC")
    phone_battery.pop("batteryCapacityLevelDesc")
    phone_battery["healthStatusDesc"] = _provider_field("正常", "string")
    model = _FixedTemplateModel(
        theme_id="fusion-battery-teal",
        component_id="BatteryOverview",
        available_template_ids=("BatteryOverviewChargingProgressHero@1",),
        capability_id="GetPhoneBatteryInfo",
        required_fields=(
            "/batterySOCText",
            "/chargingStatusDesc",
            "/healthStatusDesc",
        ),
        action_id="event.setPowerSavingMode",
        body=(
            'Template("HeroActionLayout@1",{},'
            'Template("BatteryOverviewChargingProgressHero@1",{}),'
            'Template("PillAction@1",{"actionId":"event.setPowerSavingMode",'
            '"label":"省电模式"}));'
        ),
    )

    output = await generate_template_a2ui(
        task_spec,
        _battery_card_spec(),
        (binding,),
        model,
        enable_fusion_ball=True,
    )

    assert output.template_ids == (
        "BatteryOverviewChargingProgressHero@1",
        "PillAction@1",
        "HeroActionLayout@1",
    )
    assert "batterySOC" in output.a2ui
    assert "chargingStatusDesc" in output.a2ui
    assert "healthStatusDesc" in output.a2ui
    assert "pluggedTypeDesc" not in output.a2ui
    assert '"component": "Progress"' not in output.a2ui


@pytest.mark.asyncio
async def test_2x2_battery_health_level_hero_uses_health_fields():
    binding = CandidateDataBinding(
        capabilityId="GetPhoneBatteryInfo",
        writeResultTo="/data/phoneBattery",
        candidateOutputFields=[
            "/healthStatusDesc",
            "/batteryCapacityLevelDesc",
        ],
    )
    task_spec = _battery_task()
    task_spec.userQuery = "手机用了两年，想确认电池健康和当前电量等级，点击查看电池健康设置。"
    task_spec.dataModelSchema["data"]["phoneBattery"] = {
        "healthStatusDesc": _provider_field("电池健康 正常", "string"),
        "batteryCapacityLevelDesc": _provider_field("正常电量", "string"),
    }
    model = _FixedTemplateModel(
        theme_id="fusion-battery-teal",
        component_id="BatteryOverview",
        available_template_ids=("BatteryOverviewHealthLevelHero@1",),
        capability_id="GetPhoneBatteryInfo",
        required_fields=(
            "/healthStatusDesc",
            "/batteryCapacityLevelDesc",
        ),
        action_id="event.setPowerSavingMode",
        body=(
            'Template("HeroActionLayout@1",{},'
            'Template("BatteryOverviewHealthLevelHero@1",{}),'
            'Template("PillAction@1",{"actionId":"event.setPowerSavingMode",'
            '"label":"省电模式"}));'
        ),
    )

    output = await generate_template_a2ui(
        task_spec,
        _battery_card_spec(),
        (binding,),
        model,
        enable_fusion_ball=True,
    )

    assert output.template_ids == (
        "BatteryOverviewHealthLevelHero@1",
        "PillAction@1",
        "HeroActionLayout@1",
    )
    assert "healthStatusDesc" in output.a2ui
    assert "batteryCapacityLevelDesc" in output.a2ui
    assert "batterySOC" not in output.a2ui


@pytest.mark.asyncio
async def test_2x2_battery_generic_compact_accepts_two_pill_actions():
    action_ids = ("event.setPowerSavingMode", "event.startNavigate")

    class TwoActionBatteryModel:
        second_layer_prompt: list[dict[str, str]] | None = None

        async def generate_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return {
                "themeId": "fusion-battery-teal",
                "requiredOutputFieldsByCapability": {
                    "GetPhoneBatteryInfo": [
                        "/batterySOC",
                        "/chargingStatusDesc",
                    ]
                },
                "action": list(action_ids),
            }

        async def generate(
            self,
            prompt: list[dict[str, str]],
            *_args: Any,
            **_kwargs: Any,
        ) -> str:
            self.second_layer_prompt = prompt
            return (
                'Template("CompactTwoActionLayout@1",{},'
                'Template("BatteryOverviewCompact@1",'
                '{"batteryIcon":"resources/base/media/battery_leaf_fill.svg"}),'
                'Template("PillAction@1",{"actionId":"event.setPowerSavingMode",'
                '"label":"省电模式"}),'
                'Template("PillAction@1",{"actionId":"event.startNavigate",'
                '"label":"开始导航"}));'
            )

    binding = CandidateDataBinding(
        capabilityId="GetPhoneBatteryInfo",
        writeResultTo="/data/phoneBattery",
        candidateOutputFields=[
            "/batterySOC",
            "/batterySOCText",
            "/chargingStatusDesc",
            "/batteryCapacityLevelDesc",
            "/batteryTemperatureText",
        ],
    )
    task_spec = _battery_task().model_copy(
        update={
            "userQuery": "下班要开车回家，显示手机电量和状态，不够开省电，能导航回家。",
            "eventCandidates": [
                EventAction(
                    id="event.setPowerSavingMode",
                    displayLabel="省电模式",
                    call="clickToIntent",
                    args={"intentName": "SetSettingSwitch"},
                ),
                EventAction(
                    id="event.startNavigate",
                    displayLabel="导航回家",
                    call="clickToIntent",
                    args={"intentName": "StartNavigate"},
                ),
            ],
        }
    )
    model = TwoActionBatteryModel()

    output = await generate_template_a2ui(
        task_spec,
        _battery_card_spec(),
        (binding,),
        model,
        enable_fusion_ball=True,
    )

    assert output.template_ids == (
        "BatteryOverviewCompact@1",
        "PillAction@1",
        "CompactTwoActionLayout@1",
    )
    assert model.second_layer_prompt is not None
    second_layer_user = model.second_layer_prompt[1]["content"]
    assert "BatteryOverviewCompact@1" in second_layer_user
    assert "CompactTwoActionLayout@1" in output.template_ids
    assert output.a2ui.count('"call":"clickToIntent"') == 2
    assert "batterySOC" in output.a2ui
    assert "chargingStatusDesc" in output.a2ui
    assert "batterySOCText" not in output.a2ui
    assert "batteryCapacityLevelDesc" not in output.a2ui
    assert "省电模式" in output.a2ui and "开始导航" in output.a2ui
    messages = [json.loads(line) for line in output.a2ui.splitlines()]
    components = {
        item["id"]: item for item in messages[1]["updateComponents"]["components"]
    }
    assert messages[1]["updateComponents"]["root"] == "root"
    assert components["root"]["children"] == [
        "fusionBallBackground",
        "template_root",
    ]
    assert components["fusionBallLarge"]["styles"]["backgroundColor"] == "#FF17734C"
    assert components["fusionBallMedium"]["styles"]["backgroundColor"] == "#FF26BFA6"
    assert components["fusionBallSmall"]["styles"]["backgroundColor"] == "#FF60BF98"
    assert components["template_root"]["children"] == [
        "__genui_render_component__template_root"
    ]
    assert components["__genui_render_component__template_root"]["children"] == [
        "root_1"
    ]


def test_battery_generic_hero_requires_a_selected_layout_action():
    registry = get_cardplan_registry(True)
    definition = registry.require_template("BatteryOverviewHero@1")
    scope = AdvancedScopeBrief(
        themeId="fusion-battery-teal",
        advancedComponentIds=["BatteryOverview"],
    )
    no_action_task = _battery_task().model_copy(update={"eventCandidates": []})

    assert definition.requires_layout_action is True
    assert "BatteryOverviewHero@1" not in scope_template_ids(
        scope,
        registry,
        no_action_task,
    )
    assert "BatteryOverviewFull@1" in scope_template_ids(scope, registry, no_action_task)
    assert "BatteryOverviewHero@1" in scope_template_ids(
        scope,
        registry,
        _battery_task(),
    )


@pytest.mark.asyncio
async def test_battery_hero_without_pill_action_is_repaired_to_full_template():
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

    class RepairingBatteryModel(_FixedTemplateModel):
        def __init__(self) -> None:
            super().__init__(
                theme_id="fusion-battery-teal",
                component_id="BatteryOverview",
                available_template_ids=(
                    "BatteryOverviewFull@1",
                    "BatteryOverviewHero@1",
                ),
                capability_id="GetPhoneBatteryInfo",
                required_fields=("/batterySOC", "/chargingStatusDesc"),
                action_id=None,
                body="",
            )
            self.body_calls = 0

        async def generate(
            self,
            prompt: list[dict[str, str]],
            *_args: Any,
            **_kwargs: Any,
        ) -> str:
            self.second_layer_prompt = prompt
            self.body_calls += 1
            layout = 'Template("SingleFocusLayout@1",{},'
            if self.body_calls == 1:
                return layout + 'Template("BatteryOverviewHero@1",{}));'
            return layout + 'Template("BatteryOverviewFull@1",{}));'

    model = RepairingBatteryModel()
    output = await generate_template_a2ui(
        _battery_task(),
        _battery_card_spec(),
        (binding,),
        model,
        enable_fusion_ball=True,
    )

    assert model.body_calls == 2
    assert output.template_ids == ("BatteryOverviewFull@1", "SingleFocusLayout@1")
    assert model.second_layer_prompt is not None
    candidate_line = next(
        line
        for line in model.second_layer_prompt[1]["content"].splitlines()
        if line.startswith("componentCandidates=")
    )
    candidates = json.loads(candidate_line.removeprefix("componentCandidates="))
    assert len(candidates) == 1
    assert candidates[0]["componentId"] == "BatteryOverview"
    assert "BatteryOverviewFull@1" in candidates[0]["availableTemplateIds"]
    assert "BatteryOverviewHero@1" not in candidates[0]["availableTemplateIds"]
    assert "PillAction" not in output.tersel


@pytest.mark.asyncio
async def test_second_layer_invalid_direct_calls_are_retried_exactly_twice() -> None:
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

    class InvalidDirectCallModel(_FixedTemplateModel):
        def __init__(self) -> None:
            super().__init__(
                theme_id="device-clean-blue-teal",
                component_id="BatteryOverview",
                available_template_ids=("BatteryOverviewFull@1",),
                capability_id="GetPhoneBatteryInfo",
                required_fields=(
                    "/batterySOC",
                    "/batterySOCText",
                    "/batteryCapacityLevelDesc",
                    "/chargingStatusDesc",
                ),
                action_id=None,
                body="",
            )
            self.body_calls = 0

        async def generate(
            self,
            prompt: list[dict[str, str]],
            *_args: Any,
            **_kwargs: Any,
        ) -> str:
            self.second_layer_prompt = prompt
            self.body_calls += 1
            return (
                'Template(layout="SingleFocusLayout@1", props={}, '
                'children=[Template("BatteryOverviewFull@1", {})]);'
            )

    model = InvalidDirectCallModel()

    with pytest.raises(TemplateGenerationError, match="template body validation failed"):
        await generate_template_a2ui(
            _battery_task(),
            _battery_card_spec(),
            (binding,),
            model,
        )

    assert model.body_calls == 3
    assert model.second_layer_prompt is not None
    assert len(model.second_layer_prompt) == 4
    retry_instruction = model.second_layer_prompt[-1]["content"]
    assert "不含关键字参数的直接位置调用" in retry_instruction
    assert "props=" in retry_instruction
    assert "只输出类 Tersel 调用树" in retry_instruction


def test_first_layer_action_candidate_exposes_only_event_identity():
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

    payload = json.loads(messages[1]["content"])
    assert payload["action"] == [
        {
            "eventId": "event.open.weather",
            "call": "clickToDeeplink",
        }
    ]


@pytest.mark.parametrize(
    ("enable_fusion_ball", "expected_theme_id"),
    [(False, "race-night-violet"), (True, "fusion-sport-orange")],
)
def test_countdown_theme_candidates_follow_fusion_gate(
    enable_fusion_ball: bool,
    expected_theme_id: str,
) -> None:
    registry = get_cardplan_registry(enable_fusion_ball)

    assert registry.first_layer_theme_ids(("CountdownOverview",)) == (expected_theme_id,)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("enable_fusion_ball", "theme_id"),
    [(False, "race-night-violet"), (True, "fusion-sport-orange")],
)
async def test_generic_countdown_query_uses_countdown_overview_without_workout_semantics(
    enable_fusion_ball: bool,
    theme_id: str,
) -> None:
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
        theme_id=theme_id,
        component_id="CountdownOverview",
        available_template_ids=("CountdownOverviewFull@1",),
        capability_id="GetCountdownDays",
        required_fields=("/countdownDays",),
        body='Template("SingleFocusLayout@1",{},Template("CountdownOverviewFull@1",{}));',
    )

    output = await generate_template_a2ui(
        task_spec,
        card_spec,
        (binding,),
        model,
        enable_fusion_ball=enable_fusion_ball,
    )

    assert output.template_ids == ("CountdownOverviewFull@1", "SingleFocusLayout@1")
    assert "countdownDays" in output.a2ui
    assert "倒计时" in output.a2ui
    assert "运动倒计时" not in output.a2ui
    messages = [json.loads(line) for line in output.a2ui.splitlines()]
    update = messages[1].get("updateComponents")
    assert isinstance(update, dict)
    components = update.get("components")
    assert isinstance(components, list)
    components_by_id: dict[str, dict[str, Any]] = {}
    for component in components:
        component_id = component.get("id")
        assert isinstance(component_id, str)
        components_by_id[component_id] = component
    root = components_by_id.get("root")
    assert isinstance(root, dict)
    if enable_fusion_ball:
        assert root.get("component") == "Stack"
        assert root.get("children") == ["fusionBallBackground", "template_root"]
    else:
        assert root.get("component") == "Column"
        assert "fusionBallBackground" not in components_by_id
        root_styles = root.get("styles")
        assert isinstance(root_styles, dict)
        assert root_styles.get("backgroundColor") == "#FFFFF0E6"
    expected_ball_colors = {
        "fusionBallLarge": "#FFB33024",
        "fusionBallMedium": "#FFFF8833",
        "fusionBallSmall": "#FFE68073",
    }
    for ball_id, expected_color in expected_ball_colors.items():
        if not enable_fusion_ball:
            assert ball_id not in components_by_id
            continue
        ball = components_by_id.get(ball_id)
        assert isinstance(ball, dict)
        assert ball.get("component") == "Divider"
        ball_styles = ball.get("styles")
        assert isinstance(ball_styles, dict)
        assert ball_styles.get("backgroundColor") == expected_color
    reporter = validate_card(
        artifact={
            "genui": output.a2ui,
            "cardSpec": card_spec,
            "effectiveCapabilities": {
                "data": [
                    {
                        "id": "GetCountdownDays",
                        "type": "data",
                        "outputSchema": {
                            "type": "object",
                            "properties": {
                                "countdownDays": {
                                    "type": "integer",
                                    "displayUnits": ["天"],
                                    "unitIncluded": False,
                                }
                            },
                        },
                    }
                ]
            },
        }
    )
    assert not reporter.has_code("DISPLAY_UNIT_MISSING", "DISPLAY_UNIT_DUPLICATED")


class WeatherTemplateModel:
    def __init__(
        self,
        *,
        route_usable: bool = True,
        action_id: str | None = None,
        theme_id: str = "family-weather-care-blue",
        body: str = _WEATHER_BODY,
        available_template_ids: tuple[str, ...] = ("WeatherOverviewFull@1",),
    ) -> None:
        self.body_called = False
        self.route_usable = route_usable
        self.action_id = action_id
        self.theme_id = theme_id
        self.body = body
        self.available_template_ids = available_template_ids
        self.first_layer_prompt: list[dict[str, str]] | None = None
        self.second_layer_prompt: list[dict[str, str]] | None = None

    async def generate_json(self, prompt: list[dict[str, str]], **_kwargs: Any) -> dict[str, Any]:
        self.first_layer_prompt = prompt
        payload = json.loads(prompt[1]["content"])
        candidate_fields = payload["candidateOutputFieldsByCapability"].get(
            "ViewWeather",
            [],
        )
        required_fields = [
            field
            for field in ("/current/temperatureText", "/current/condition")
            if field in candidate_fields
        ]
        return {
            "themeId": self.theme_id,
            "requiredOutputFieldsByCapability": (
                {"ViewWeather": required_fields}
                if self.route_usable
                else {}
            ),
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


@pytest.mark.asyncio
@pytest.mark.parametrize("selector", ["search", "llm"])
async def test_disabled_fusion_feature_hides_themes_from_first_layer_prompt(
    monkeypatch,
    selector: str,
) -> None:
    class FusionDisabledModel:
        first_layer_payload: dict[str, Any] | None = None
        second_layer_prompt: list[dict[str, str]] | None = None

        async def generate_json(
            self,
            prompt: list[dict[str, str]],
            *,
            phase: str,
        ) -> dict[str, Any]:
            self.first_layer_payload = json.loads(prompt[1]["content"])
            if selector == "llm":
                assert phase == "template-route-decision"
                return {
                    "theme": "digital-wellbeing-neutral-dark",
                    "componentCandidates": [
                        {
                            "componentId": "AppUsageOverview",
                            "availableTemplateIds": ["AppUsageOverviewFull@1"],
                        }
                    ],
                    "action": [],
                }
            assert phase == "template-retrieval-query"
            return {
                "themeId": "digital-wellbeing-neutral-dark",
                "requiredOutputFieldsByCapability": {
                    "GetAppUsageDuration": [
                        "/appUsage/appName",
                        "/appUsage/durationText",
                    ]
                },
                "action": [],
            }

        async def generate(
            self,
            prompt: list[dict[str, str]],
            *_args: Any,
            **_kwargs: Any,
        ) -> str:
            self.second_layer_prompt = prompt
            return (
                'Template("SingleFocusLayout@1",{},'
                'Template("AppUsageOverviewFull@1",{}));'
            )

    controls = TemplateControls(
        schemaVersion="template-controls/1",
        firstLayerComponentSelector=selector,
    )
    monkeypatch.setattr(template_pipeline_module, "load_template_controls", lambda: controls)
    binding = CandidateDataBinding(
        capabilityId="GetAppUsageDuration",
        writeResultTo="/data/appUsageStats",
        candidateOutputFields=[
            "/appUsage/appName",
            "/appUsage/durationText",
        ],
    )
    model = FusionDisabledModel()

    output = await generate_template_a2ui(
        _app_usage_task_spec(),
        _app_usage_card_spec(),
        (binding,),
        model,
        enable_fusion_ball=False,
    )

    assert model.first_layer_payload is not None
    fusion_theme_ids = {
        theme_id
        for theme_id, theme in get_cardplan_registry(True).themes.items()
        if theme.fusion_ball_style is not None
    }
    serialized_prompt_payload = json.dumps(model.first_layer_payload, ensure_ascii=False)
    assert all(theme_id not in serialized_prompt_payload for theme_id in fusion_theme_ids)
    assert model.second_layer_prompt is not None
    serialized_second_layer_prompt = json.dumps(model.second_layer_prompt, ensure_ascii=False)
    assert all(theme_id not in serialized_second_layer_prompt for theme_id in fusion_theme_ids)
    assert "FusionBall" not in output.tersel


@pytest.mark.asyncio
async def test_disabled_fusion_feature_rejects_forged_fusion_theme() -> None:
    model = WeatherTemplateModel(theme_id="fusion-weather-blue")
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        writeResultTo="/data/weather",
        candidateOutputFields=["/current/temperatureText", "/current/condition"],
    )

    with pytest.raises(TemplateRouteNotApplicable, match="first-layer decision failed"):
        await generate_template_a2ui(
            _weather_task_spec(),
            _weather_card_spec(),
            (binding,),
            model,
            enable_fusion_ball=False,
        )

    assert model.body_called is False


@pytest.mark.asyncio
async def test_template_pipeline_rejects_2x4_before_any_model_call() -> None:
    class NoModelCall:
        async def generate_json(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            pytest.fail("2x4 template Search must not call the model")

        async def generate(self, *_args: Any, **_kwargs: Any) -> str:
            pytest.fail("2x4 template Search must not call the model")

    task_spec = _weather_task_spec().model_copy(update={"size": "2x4"})
    card_spec = _weather_card_spec() | {"suggestSize": "2x4"}
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        writeResultTo="/data/weather",
        candidateOutputFields=["/current/temperatureText", "/current/condition"],
    )

    with pytest.raises(TemplateRouteNotApplicable, match="does not support 2x4"):
        await generate_template_a2ui(
            task_spec,
            card_spec,
            (binding,),
            NoModelCall(),
            enable_fusion_ball=True,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("selector", "expected_phase"),
    [
        ("search", "template-retrieval-query"),
        ("llm", "template-route-decision"),
    ],
)
async def test_first_layer_selector_routes_and_preserves_action(
    monkeypatch,
    selector: str,
    expected_phase: str,
):
    class SelectorModel:
        phases: list[str] = []

        async def generate_json(
            self,
            _prompt: list[dict[str, str]],
            *,
            phase: str,
        ) -> dict[str, Any]:
            self.phases.append(phase)
            if selector == "llm":
                return {
                    "theme": "family-weather-care-blue",
                    "componentCandidates": [
                        {
                            "componentId": "WeatherOverview",
                            "availableTemplateIds": ["WeatherOverviewHero@1"],
                        }
                    ],
                    "action": ["event.open.weather"],
                }
            return {
                "themeId": "family-weather-care-blue",
                "requiredOutputFieldsByCapability": {
                    "ViewWeather": ["/current/condition"]
                },
                "action": "event.open.weather",
            }

        async def generate(self, *_args: Any, **_kwargs: Any) -> str:
            return (
                'Template("HeroActionLayout@1",{},'
                'Template("WeatherOverviewHero@1",{}),'
                'Template("PillAction@1",{"actionId":"event.open.weather",'
                '"label":"天气详情"}));'
            )

    controls = TemplateControls(
        schemaVersion="template-controls/1",
        firstLayerComponentSelector=selector,
    )
    monkeypatch.setattr(template_pipeline_module, "load_template_controls", lambda: controls)
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
    model = SelectorModel()

    output = await generate_template_a2ui(
        task_spec,
        _weather_card_spec(),
        (binding,),
        model,
    )

    assert model.phases == [expected_phase]
    assert '"call":"clickToDeeplink"' in output.a2ui


@pytest.mark.asyncio
async def test_compact_template_accepts_two_independently_selected_pill_actions():
    action_ids = ("event.open.weather", "event.open.music.daily")

    class TwoActionModel:
        async def generate_json(
            self,
            _prompt: list[dict[str, str]],
            *,
            phase: str,
        ) -> dict[str, Any]:
            assert phase == "template-retrieval-query"
            return {
                "themeId": "family-weather-care-blue",
                "requiredOutputFieldsByCapability": {
                    "ViewWeather": ["/current/condition"]
                },
                "action": list(action_ids),
            }

        async def generate(self, *_args: Any, **_kwargs: Any) -> str:
            return (
                'Template("CompactTwoActionLayout@1",{},'
                'Template("WeatherOverviewCompact@1",{}),'
                'Template("PillAction@1",{"actionId":"event.open.weather",'
                '"label":"天气详情"}),'
                'Template("PillAction@1",{"actionId":"event.open.music.daily",'
                '"label":"每日推荐"}));'
            )

    task_spec = _weather_task_spec().model_copy(
        update={
            "eventCandidates": [
                EventAction(
                    id=action_id,
                    displayLabel=label,
                    call="clickToIntent",
                    args={"intentName": action_id},
                )
                for action_id, label in zip(action_ids, ("详情", "刷新"), strict=True)
            ]
        }
    )
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        writeResultTo="/data/weather",
        candidateOutputFields=["/current/condition"],
    )

    output = await generate_template_a2ui(
        task_spec,
        _weather_card_spec(),
        (binding,),
        TwoActionModel(),
    )

    assert output.a2ui.count('"call":"clickToIntent"') == 2
    assert "天气详情" in output.a2ui and "每日推荐" in output.a2ui
    assert output.template_ids == (
        "WeatherOverviewCompact@1",
        "PillAction@1",
        "CompactTwoActionLayout@1",
    )


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
        processor_kind=DslProcessorKind.DESIGN_COMPACT,
        source_format="design-compact-dsl",
        model_profile_id="design-compact-dsl",
        model_format="compact-dsl",
        design_profile_id="design-compact-dsl",
        supports_dynamic_capabilities=True,
        validation_failure_blocking=True,
        stores_design_token=True,
    )


def _weather_request() -> GenerateWidgetCardRequest:
    return GenerateWidgetCardRequest(
        uid="template-test",
        prdVer=_TEST_APP_VERSION,
        device={"romVersion": "6.0"},
        userQuery="做一个天气卡片，显示城市、温度、天气、空气质量和感冒指数",
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
                    "/current/coldLevel",
                ],
            }
        ],
        candidateAssetIds=["asset.icon_weather_temperature1"],
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
                        "coldLevel": field("低"),
                    },
                    "daily": [{"temperatureRangeText": field("25° / 32°")}],
                }
            }
        },
    )


def _app_usage_task_spec() -> TaskSpec:
    def field(value: str) -> dict[str, Any]:
        return {
            "type": "string",
            "description": "trusted app usage field",
            "sampleValue": value,
        }

    return TaskSpec(
        userQuery="查看应用今日使用时长",
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


def _app_usage_card_spec() -> dict[str, Any]:
    return {
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


def _minimal_template_a2ui() -> str:
    messages = [
        {
            "version": "v0.9",
            "createSurface": {
                "surfaceId": "surface_card",
                "catalogId": "ohos.a2ui.extended.catalog.form",
            },
        },
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": "surface_card",
                "root": "root",
                "components": [
                    {
                        "id": "root",
                        "component": "Column",
                        "children": [],
                        "styles": {
                            "backgroundColor": "#FF317AF7",
                            "linearGradient": {
                                "direction": "Bottom",
                                "colors": [
                                    ["#FF317AF7", 0],
                                    ["#FF46B1E3", 1],
                                ],
                            },
                        },
                    }
                ],
            },
        },
        {
            "version": "v0.9",
            "updateDataModel": {
                "surfaceId": "surface_card",
                "path": "/",
                "value": {"data": {}},
            },
        },
    ]
    return "\n".join(
        json.dumps(item, ensure_ascii=False, separators=(",", ":"))
        for item in messages
    )


@pytest.mark.asyncio
async def test_template_facade_returns_only_compact_source_dsl_string(monkeypatch):
    class Output:
        a2ui = _minimal_template_a2ui()
        template_ids = ("WeatherOverviewFull@1",)
        expanded_component_count = 3

    observed_feature_flags: list[bool] = []

    async def generate(
        *_args: Any,
        enable_fusion_ball: bool,
    ) -> Output:
        observed_feature_flags.append(enable_fusion_ball)
        return Output()

    monkeypatch.setattr(facade, "create_template_model_client", lambda *_args: object())
    monkeypatch.setattr(facade, "generate_template_engine_a2ui", generate)
    result = await facade.request_template_source_dsl(
        _weather_task_spec(),
        _weather_card_spec(),
        (),
        processor_kind=DslProcessorKind.DESIGN_COMPACT,
        protocol_profile=A2UIProtocolRegistry(
            A2UI_FORM_PROTOCOL_PROFILE_ID
        ).get_profile(),
        model_runtime=object(),
        model_request_context=ModelRequestContext(
            session_id="session",
            interaction_id="interaction",
            device_id="device",
            country_code="CN",
            app_version=_TEST_APP_VERSION,
            app_name="CreateMyCard",
        ),
        enable_fusion_ball=False,
    )

    assert isinstance(result, str)
    rows = [json.loads(line) for line in result.splitlines()]
    assert rows[0][0:2] == ["root", "Column"]
    assert rows[0][2]["backgroundColor"] == "#FF317AF7"
    assert rows[0][2]["linearGradient"]["colors"] == [
        ["#FF317AF7", 0],
        ["#FF46B1E3", 1],
    ]
    assert rows[-1] == ["/", {"data": {}}]
    assert observed_feature_flags == [False]


@pytest.mark.asyncio
async def test_template_facade_preserves_effective_bindings(monkeypatch):
    observed_fields: list[str] = []

    class Output:
        a2ui = _minimal_template_a2ui()
        template_ids = ("DeviceStatusBattery@1",)
        expanded_component_count = 2

    async def generate(
        _task_spec: TaskSpec,
        _card_spec: dict,
        bindings: tuple[CandidateDataBinding, ...],
        _model_client: Any,
        *,
        enable_fusion_ball: bool,
    ) -> Output:
        assert enable_fusion_ball is True
        observed_fields.extend(bindings[0].candidateOutputFields)
        return Output()

    binding = CandidateDataBinding(
        capabilityId="GetPhoneBatteryInfo",
        arguments={},
        writeResultTo="/data/phoneBattery",
        candidateOutputFields=["/batterySOCText", "/chargingStatusDesc"],
    )
    monkeypatch.setattr(facade, "create_template_model_client", lambda *_args: object())
    monkeypatch.setattr(facade, "generate_template_engine_a2ui", generate)

    await facade.request_template_source_dsl(
        _weather_task_spec(),
        _weather_card_spec(),
        (binding,),
        processor_kind=DslProcessorKind.DESIGN_COMPACT,
        protocol_profile=A2UIProtocolRegistry(
            A2UI_FORM_PROTOCOL_PROFILE_ID
        ).get_profile(),
        model_runtime=object(),
        model_request_context=ModelRequestContext(
            session_id="session",
            interaction_id="interaction",
            device_id="device",
            country_code="CN",
            app_version=_TEST_APP_VERSION,
            app_name="CreateMyCard",
        ),
        enable_fusion_ball=True,
    )

    assert observed_fields == [
        "/batterySOCText",
        "/chargingStatusDesc",
    ]
    assert binding.candidateOutputFields == [
        "/batterySOCText",
        "/chargingStatusDesc",
    ]


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
async def test_weather_template_defaults_to_non_fusion_a2ui_and_compact_artifact(monkeypatch):
    monkeypatch.setattr(WidgetGenerationService, "_enable_card_template", lambda _self: True)
    model = WeatherTemplateModel(
        body=(
            'Template("SingleFocusLayout@1",{},Template("WeatherOverviewFull@1",'
            '{"conditionIcon":"resources/base/media/icon_weather_temperature1.svg"}));'
        )
    )
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
    weather_full_candidates = ["WeatherOverviewFull@1"]
    assert json.loads(candidate_line.removeprefix("componentCandidates=")) == [
        {
            "componentId": "WeatherOverview",
            "availableTemplateIds": weather_full_candidates,
        }
    ]
    required_group_line = next(
        line
        for line in second_layer_user.splitlines()
        if line.startswith("requiredLocalTemplateGroups=")
    )
    assert json.loads(required_group_line.removeprefix("requiredLocalTemplateGroups=")) == [
        weather_full_candidates,
        weather_full_candidates,
    ]
    assert "selectedActionEventIds=[]" in second_layer_user
    template_contract_line = next(
        line
        for line in second_layer_user.splitlines()
        if line.startswith("templateContracts=")
    )
    template_contracts = json.loads(
        template_contract_line.removeprefix("templateContracts=")
    )
    assert template_contracts[0]["templateId"] == "WeatherOverviewFull@1"
    assert template_contracts[0]["callSyntax"] == (
        'Template("WeatherOverviewFull@1", <props matching propsSchema>)'
    )
    assert template_contracts[0]["propsSchema"] == {
        "type": "object",
        "properties": {
            "location": {"type": "string"},
            "conditionIcon": {"type": "string"},
        },
        "required": [],
        "additionalProperties": False,
    }
    assert template_contracts[0]["parameterSources"]["conditionIcon"] == {
        "valueKind": "asset-source",
        "allowedSources": ["resources/base/media/icon_weather_temperature1.svg"],
    }
    assert "layoutContracts=" in second_layer_user
    assert "actionContracts=[]" in second_layer_user
    assert "第二层业务模板使用规则" in second_layer_user
    assert "手机电量高级组件二层规则" not in second_layer_user
    assert "- 可用模板：" not in second_layer_user
    assert "WeatherOverviewCompact@1" not in second_layer_user
    assert sum(len(item["content"]) for item in model.second_layer_prompt) < 8_000
    assert "标准组件投影" not in model.second_layer_prompt[0]["content"]
    assert captured["compact"]
    assert "{{ ${/data/weather/current/condition}" in captured["compact"]
    assert "{{ ${/data/weather/location/districtName} }}" in captured["artifact"].genui
    assert '"content":"青浦区"' not in captured["artifact"].genui
    messages = [json.loads(line) for line in captured["artifact"].genui.splitlines()]
    protocol_profile = A2UIProtocolRegistry(A2UI_FORM_PROTOCOL_PROFILE_ID).get_profile()
    assert messages[0]["createSurface"]["catalogId"] == protocol_profile["catalogId"]
    assert messages[1]["updateComponents"]["root"] == "root"
    root = next(
        item
        for item in messages[1]["updateComponents"]["components"]
        if item["id"] == "root"
    )
    component_ids = {
        item["id"] for item in messages[1]["updateComponents"]["components"]
    }
    assert root["component"] == "Column"
    assert root["styles"]["borderRadius"] == 18
    assert root["styles"]["backgroundColor"] == "#FFE5EDFE"
    assert "linearGradient" not in root["styles"]
    assert "template_root" in root["children"]
    assert "fusionBallBackground" not in component_ids
    assert all(not component_id.startswith("fusionBall") for component_id in component_ids)
    assert captured["artifact"].effectiveCapabilities["data"] == ["ViewWeather"]


@pytest.mark.asyncio
async def test_terse_entry_uses_compact_template_source_with_fusion_ball_theme(monkeypatch):
    model = WeatherTemplateModel(
        theme_id="fusion-weather-blue",
        body=(
            'Template("SingleFocusLayout@1",{},'
            'Template("WeatherOverviewFull@1",{}));'
        ),
    )
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        get_settings(),
        "CONFIG",
        {FUSION_BALL_MIN_PRD_VERSION_CONFIG: "11.7.5.206"},
    )

    monkeypatch.setattr(
        facade,
        "create_template_model_client",
        lambda _runtime, _context: model,
    )
    enabled_registry = get_cardplan_registry(True)
    monkeypatch.setattr(
        template_pipeline_module,
        "get_cardplan_registry",
        lambda _enable_fusion_ball=False: enabled_registry,
    )

    async def save(store: ArtifactStore, artifact: Any) -> ArtifactSaveResult:
        captured["artifact"] = artifact
        captured["compact"] = store.design_token
        return ArtifactSaveResult(
            artifactUrl="https://artifact.test/weather-template-terse",
            artifactDigest="sha256:weather-template-terse",
        )

    monkeypatch.setattr(ArtifactStore, "save", save)
    response = await WidgetGenerationService(
        model_runtime=object(),
    ).generate_widget_card_terse_dsl_nested2(
        _weather_request().model_copy(update={"prdVer": "11.7.5.206"}),
    )

    assert response.status == GenerationStatus.SUCCESS
    assert response.artifactUrl == "https://artifact.test/weather-template-terse"
    assert "prdVer" not in captured["artifact"].taskSpec
    assert captured["artifact"].taskSpec["appVersion"] == "11.7.5.206"
    assert model.first_layer_prompt is not None
    first_layer_payload = json.loads(model.first_layer_prompt[1]["content"])
    assert "prdVer" not in first_layer_payload["taskSpec"]
    assert first_layer_payload["taskSpec"]["appVersion"] == "11.7.5.206"
    compact_rows = [json.loads(line) for line in captured["compact"].splitlines()]
    compact_components = {
        row[0]: row for row in compact_rows if len(row) >= 3 and isinstance(row[0], str)
    }
    assert all(row[1] != "FusionBall" for row in compact_rows if len(row) >= 2)
    root_id = "root"
    assert compact_rows[0][0:2] == [root_id, "Stack"]
    foreground_id = "template_root"
    overflow_content_id = "__genui_render_component__template_root"
    content_id = "root_1"
    assert compact_components[root_id][3] == ["fusionBallBackground", foreground_id]
    assert compact_components[foreground_id][2]["padding"] == 12
    assert compact_components[foreground_id][3] == [overflow_content_id]
    assert compact_components[overflow_content_id][3] == [content_id]
    assert compact_components[root_id][2]["backgroundColor"] == "#00000000"
    assert "linearGradient" not in compact_components[root_id][2]
    assert compact_components["fusionBallLarge"][2]["backgroundColor"] == (
        _WEATHER_PALETTE[0]
    )
    assert compact_components["fusionBallMedium"][2]["backgroundColor"] == (
        _WEATHER_PALETTE[1]
    )
    assert compact_components["fusionBallSmall"][2]["backgroundColor"] == (
        _WEATHER_PALETTE[2]
    )
    assert "linearGradient" not in compact_components[content_id][2]
    messages = [json.loads(line) for line in captured["artifact"].genui.splitlines()]
    protocol_profile = A2UIProtocolRegistry(A2UI_FORM_PROTOCOL_PROFILE_ID).get_profile()
    assert messages[0]["createSurface"]["catalogId"] == protocol_profile["catalogId"]
    assert messages[1]["updateComponents"]["root"] == root_id
    components = {item["id"]: item for item in messages[1]["updateComponents"]["components"]}
    assert components[root_id]["component"] == "Stack"
    assert components[root_id]["children"] == [
        "fusionBallBackground",
        foreground_id,
    ]
    assert components[foreground_id]["styles"]["padding"] == 12
    assert components[foreground_id]["children"] == [overflow_content_id]
    assert components[overflow_content_id]["children"] == [content_id]
    assert components[root_id]["styles"]["backgroundColor"] == "#00000000"
    assert components["fusionBallLarge"]["component"] == "Divider"
    assert components["fusionBallMedium"]["component"] == "Divider"
    assert components["fusionBallSmall"]["component"] == "Divider"
    assert components["fusionBallGlassLayer"]["component"] == "Divider"

    target_ids = (
        "fusionBallLarge",
        "fusionBallMedium",
        "fusionBallSmall",
        "fusionBallGlassLayer",
    )
    assert all(
        "children" not in components[component_id]
        for component_id in target_ids
    )

    assert components["fusionBallGlassLayer"]["styles"]["backdropBlur"] == {
        "radius": 120
    }
    assert components["fusionBallMedium"]["styles"]["backgroundColor"] == _WEATHER_PALETTE[1]
    assert "linearGradient" not in components[content_id]["styles"]
    text_components = [
        item for item in components.values() if item.get("component") == "Text"
    ]
    assert text_components
    text_colors = {item["styles"]["fontColor"] for item in text_components}
    assert text_colors == {"#FFCCDDFF", "#99CCDDFF"}
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

    with pytest.raises(TemplateRouteNotApplicable, match="no requested capability"):
        await generate_template_a2ui(
            _weather_task_spec(),
            _weather_card_spec(),
            (binding,),
            model,
        )

    assert model.body_called is False


@pytest.mark.asyncio
async def test_search_candidates_are_derived_from_registry_not_model_template_ids():
    model = WeatherTemplateModel(available_template_ids=("ScheduleOverviewDateFull@1",))
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        writeResultTo="/data/weather",
        candidateOutputFields=list(_WEATHER_TEMPLATE_FIELDS),
    )

    output = await generate_template_a2ui(
        _weather_task_spec(),
        _weather_card_spec(),
        (binding,),
        model,
    )

    assert model.body_called is True
    assert "ScheduleOverviewDateFull@1" not in output.template_ids


@pytest.mark.asyncio
async def test_second_layer_rejects_provider_template_outside_first_layer_candidates():
    model = WeatherTemplateModel(
        body=(
            'Template("SingleFocusLayout@1",{},'
            'Template("ScheduleOverviewDateFull@1",{}));'
        )
    )
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

    assert output.template_ids == ("WeatherOverviewFull@1", "SingleFocusLayout@1")
    assert model.body_called is True


@pytest.mark.asyncio
async def test_first_layer_action_is_independent_from_selected_components():
    model = WeatherTemplateModel(
        action_id="event.open.weather",
        body=(
            'Template("HeroActionLayout@1",{},Template("WeatherOverviewHero@1",{}),'
            'Template("PillAction@1",{"actionId":"event.open.weather",'
            '"label":"天气详情"}));'
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
    assert model.second_layer_prompt is not None
    second_layer_prompt = json.dumps(model.second_layer_prompt, ensure_ascii=False)
    assert "dataFacts=" not in second_layer_prompt
    assert "mustKeep=" not in second_layer_prompt
    assert "60814" not in second_layer_prompt
    candidate_line = next(
        line
        for line in model.second_layer_prompt[1]["content"].splitlines()
        if line.startswith("componentCandidates=")
    )
    candidates = json.loads(candidate_line.removeprefix("componentCandidates="))
    assert set(candidates[0]["availableTemplateIds"]) == {
        "WeatherOverviewHero@1",
        "WeatherOverviewAirQualityHero@1",
    }
    messages = [json.loads(line) for line in output.a2ui.splitlines()]
    visible_text = {
        component.get("content")
        for component in messages[1]["updateComponents"]["components"]
        if component.get("component") == "Text"
    }
    assert "60814" not in visible_text


@pytest.mark.asyncio
async def test_calendar_event_entity_id_stays_out_of_second_layer_and_visible_text():
    task_spec = TaskSpec(
        userQuery="显示下一场日程并支持点击查看",
        size="2x2",
        eventCandidates=[
            EventAction(
                id="event.viewCalendarEvent",
                displayLabel="查看日程",
                call="clickToIntent",
                args={
                    "intentName": "ViewCalendarEvent",
                    "params": {
                        "entityId": "{{ ${/data/calendar/events/0/entityId} }}",
                    },
                },
            )
        ],
        dataModelSchema={
            "data": {
                "calendar": {
                    "events": [
                        {
                            "title": _provider_field("项目例会", "string"),
                            "dtStart": _provider_field("14:00", "string"),
                            "dtEnd": _provider_field("15:00", "string"),
                            "eventLocation": _provider_field("A1 会议室", "string"),
                            "entityId": _provider_field("example-event-001", "string"),
                        }
                    ]
                }
            }
        },
    )
    binding = CandidateDataBinding(
        capabilityId="GetCalendarEvents",
        writeResultTo="/data/calendar",
        candidateOutputFields=[
            "/events/0/title",
            "/events/0/dtStart",
            "/events/0/dtEnd",
            "/events/0/eventLocation",
        ],
    )
    card_spec = {
        "title": "下一场日程",
        "description": "日程速览",
        "suggestSize": "2x2",
        "dataBindings": [
            {
                "capabilityId": "GetCalendarEvents",
                "writeResultTo": "/data/calendar",
            }
        ],
    }
    model = _FixedTemplateModel(
        theme_id="meeting-paper-neutral",
        component_id="CalendarOverview",
        available_template_ids=("ScheduleOverviewNextEventHero@1",),
        capability_id="GetCalendarEvents",
        required_fields=(
            "/events/0/title",
            "/events/0/dtStart",
            "/events/0/dtEnd",
            "/events/0/eventLocation",
        ),
        action_id="event.viewCalendarEvent",
        body=(
            'Template("HeroActionLayout@1",{},'
            'Template("ScheduleOverviewNextEventHero@1",{}),'
            'Template("PillAction@1",{"actionId":"event.viewCalendarEvent",'
            '"label":"查看日程"}));'
        ),
    )

    output = await generate_template_a2ui(task_spec, card_spec, (binding,), model)

    assert model.second_layer_prompt is not None
    second_layer_prompt = json.dumps(model.second_layer_prompt, ensure_ascii=False)
    assert "example-event-001" not in second_layer_prompt
    second_layer_user = model.second_layer_prompt[1]["content"]
    action_contract_line = next(
        line
        for line in second_layer_user.splitlines()
        if line.startswith("actionContracts=")
    )
    action_contracts = json.loads(action_contract_line.removeprefix("actionContracts="))
    assert action_contracts[0]["templateId"] == "PillAction@1"
    assert action_contracts[0]["callSyntax"] == (
        'Template("PillAction@1", <props matching propsSchema>)'
    )
    assert action_contracts[0]["propsSchema"]["required"] == ["actionId", "label"]
    assert set(action_contracts[0]["propsSchema"]["properties"]) == {
        "actionId",
        "label",
        "icon",
    }
    assert len(action_contracts) == 1
    messages = [json.loads(line) for line in output.a2ui.splitlines()]
    visible_text = {
        component.get("content")
        for component in messages[1]["updateComponents"]["components"]
        if component.get("component") == "Text"
    }
    assert "example-event-001" not in visible_text
    assert messages[2]["updateDataModel"]["value"]["data"]["calendar"]["events"][0][
        "entityId"
    ] == "example-event-001"


@pytest.mark.asyncio
async def test_duplicate_weather_pill_actions_keep_independent_event_bindings():
    event_id = "event.open.weather"
    event_actions = []
    for index in range(2):
        event_actions.append(
            EventAction(
                id=event_id,
                displayLabel="查看天气",
                call="clickToIntent",
                args={
                    "intentName": "OpenWeather",
                    "params": {
                        "target": (
                            "{{ ${/data/weather/location/districtName} }}"
                            if index == 0
                            else "{{ ${/data/weather/current/condition} }}"
                        ),
                    },
                },
            )
        )
    task_spec = _weather_task_spec().model_copy(
        update={
            "userQuery": "显示天气，并支持分别打开地区和天气详情",
            "eventCandidates": event_actions,
        }
    )
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        writeResultTo="/data/weather",
        candidateOutputFields=[
            "/location/districtName",
            "/current/temperatureText",
            "/current/condition",
            "/current/coldLevel",
        ],
    )
    model = _FixedTemplateModel(
        theme_id="family-weather-care-blue",
        component_id="WeatherOverview",
        available_template_ids=("WeatherOverviewCompact@1",),
        capability_id="ViewWeather",
        required_fields=(
            "/location/districtName",
            "/current/temperatureText",
            "/current/condition",
            "/current/coldLevel",
        ),
        action_id=event_id,
        body=(
                'Template("CompactTwoActionLayout@1",{},'
                'Template("WeatherOverviewCompact@1",{}),'
                'Template("PillAction@1",{"actionId":"event.open.weather#1",'
                '"label":"天气详情"}),'
                'Template("PillAction@1",{"actionId":"event.open.weather#2",'
                '"label":"天气详情"}));'
        ),
    )

    output = await generate_template_a2ui(
        task_spec,
        _weather_card_spec(),
        (binding,),
        model,
    )

    assert model.second_layer_prompt is not None
    second_layer_prompt = json.dumps(model.second_layer_prompt, ensure_ascii=False)
    assert "event.open.weather#1" in second_layer_prompt
    assert "event.open.weather#2" in second_layer_prompt
    messages = [json.loads(line) for line in output.a2ui.splitlines()]
    components = messages[1]["updateComponents"]["components"]
    action_components = []
    for component in components:
        if component.get("onClick"):
            action_components.append(component)
    bound_targets = set()
    for component in action_components:
        target = component["onClick"][0]["args"]["params"]["target"]
        bound_targets.add(target)
    assert bound_targets == {
        "{{ ${/data/weather/location/districtName} }}",
        "{{ ${/data/weather/current/condition} }}",
    }
    assert "event.open.weather#" not in output.a2ui


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action_call",
    [
        'IconAction({"actionId":"event.open.weather"})',
        (
            'IconAction({"actionId":"event.open.weather",'
            '"icon":"resources/base/media/icon_weather1.svg"})'
        ),
        'ActionTile({"actionId":"event.open.weather"})',
        'PillAction({"actionId":"event.open.weather"})',
        (
            'PillAction({"actionId":"event.open.weather",'
            '"icon":"resources/base/media/icon_weather1.svg"})'
        ),
    ],
)
async def test_second_layer_rejects_direct_action_components(action_call: str):
    model = WeatherTemplateModel(
        action_id="event.open.weather",
        body=(
            'Template("SingleFocusLayout@1",{},Template("WeatherOverviewFull@1",'
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
@pytest.mark.parametrize(
    ("entry_name", "template_failure_is_terminal"),
    [
        ("generate_widget_card_compact_dsl", False),
        ("generate_widget_card_terse_dsl_nested2", True),
    ],
)
@pytest.mark.parametrize(
    "template_error",
    [
        RuntimeError("selected route failed"),
        TemplateRouteNotApplicable("LLM rejected template route"),
    ],
    ids=["generation-error", "route-not-applicable"],
)
async def test_template_exception_obeys_route_failure_policy(
    monkeypatch,
    entry_name: str,
    template_failure_is_terminal: bool,
    template_error: Exception,
):
    generated_sources: list[str] = []
    model_generate_calls = 0
    template_processors: list[DslProcessorKind] = []
    callback_sizes: list[str] = []

    class ModelClient:
        model_failure_retry_count = 0

        async def generate(self, *_args: Any, **_kwargs: Any) -> str:
            nonlocal model_generate_calls
            model_generate_calls += 1
            return "generic-source"

        async def generate_repair(self, *_args: Any, **_kwargs: Any) -> str:
            pytest.fail("template exception fallback must not enter repair")

        @staticmethod
        def extract_genui_payload(source_dsl: str) -> str:
            return source_dsl

    class Processor:
        def process(self, source_dsl: str, _context: Any) -> DslProcessingResult:
            generated_sources.append(source_dsl)
            return DslProcessingResult(
                source_dsl=source_dsl,
                standard_dsl="valid-a2ui",
            )

    async def failed_template(
        _task_spec: TaskSpec,
        *_args: Any,
        processor_kind: DslProcessorKind,
        **_kwargs: Any,
    ) -> str:
        template_processors.append(processor_kind)
        raise template_error

    async def save(_store: ArtifactStore, _artifact: Any) -> ArtifactSaveResult:
        return ArtifactSaveResult(
            artifactUrl="https://artifact.test/template-fallback",
            artifactDigest="sha256:template-fallback",
        )

    async def before_model_call(size: str) -> None:
        callback_sizes.append(size)

    monkeypatch.setattr(
        template_source_generator_module,
        "request_template_source_dsl",
        failed_template,
    )
    monkeypatch.setattr(
        widget_generation_service_module,
        "A2UIModelClient",
        lambda **_kwargs: ModelClient(),
    )
    monkeypatch.setattr(
        widget_generation_service_module,
        "get_dsl_processor",
        lambda _kind: Processor(),
    )
    monkeypatch.setattr(
        widget_generation_service_module.ArtifactValidator,
        "validate",
        lambda _self, _artifact, _profile: [],
    )
    monkeypatch.setattr(ArtifactStore, "save", save)
    settings = widget_generation_service_module.get_settings().model_copy(
        update={"CONFIG": {"enable_card_template": "true"}}
    )
    monkeypatch.setattr(
        widget_generation_service_module,
        "get_settings",
        lambda: settings,
    )

    service = WidgetGenerationService()
    entry = getattr(service, entry_name)
    response = await entry(
        _weather_request(),
        before_model_call=before_model_call,
    )

    if template_failure_is_terminal:
        assert response.status == GenerationStatus.FAILED
        assert response.errorCode == "A2UI_GENERATION_FAILED"
        assert response.artifactUrl == ""
        assert model_generate_calls == 0
        assert generated_sources == []
    else:
        assert response.status == GenerationStatus.SUCCESS
        assert response.artifactUrl == "https://artifact.test/template-fallback"
        assert model_generate_calls == 1
        assert generated_sources == ["generic-source"]
    assert template_processors == [DslProcessorKind.DESIGN_COMPACT]
    assert callback_sizes == ["2x2"]


@pytest.mark.asyncio
@pytest.mark.parametrize("policy_factory", [_policy, _terse_policy], ids=["compact", "terse"])
async def test_template_source_has_priority_over_jsx_and_uses_common_repair_once(
    monkeypatch,
    policy_factory,
):
    processed_sources: list[str] = []
    processor_kinds: list[DslProcessorKind] = []
    template_call_count = 0
    model_generate_calls = 0
    model_repair_calls = 0
    saved_design_tokens: list[str | None] = []

    class ModelClient:
        model_failure_retry_count = 0

        async def generate(self, *_args: Any, **_kwargs: Any) -> str:
            nonlocal model_generate_calls
            model_generate_calls += 1
            return "generic-initial-source"

        async def generate_repair(self, *_args: Any, **_kwargs: Any) -> str:
            nonlocal model_repair_calls
            model_repair_calls += 1
            return "generic-repaired-source"

        @staticmethod
        def extract_genui_payload(source_dsl: str) -> str:
            return source_dsl

    class Processor:
        def process(self, source_dsl: str, _context: Any) -> DslProcessingResult:
            processed_sources.append(source_dsl)
            if source_dsl == "template-invalid-source":
                return DslProcessingResult(
                    source_dsl=source_dsl,
                    issues=(
                        QualityIssue(
                            stage="conversion",
                            code="TEST_TEMPLATE_SOURCE_INVALID",
                            message="template source is invalid",
                        ),
                    ),
                )
            return DslProcessingResult(
                source_dsl=source_dsl,
                standard_dsl="valid-a2ui",
            )

    async def template_source_generator(*_args: Any, **_kwargs: Any) -> str:
        nonlocal template_call_count
        template_call_count += 1
        return "template-invalid-source"

    class RejectedJsxBridge:
        def __init__(self) -> None:
            pytest.fail("template source must take priority over JSX generation")

    async def save(store: ArtifactStore, _artifact: Any) -> ArtifactSaveResult:
        saved_design_tokens.append(store.design_token)
        return ArtifactSaveResult(
            artifactUrl="https://artifact.test/template-repaired",
            artifactDigest="sha256:template-repaired",
        )

    settings = widget_generation_service_module.get_settings().model_copy(
        update={
            "enable_validation_failure_retry": True,
            "validation_failure_max_repair_attempts": 1,
        }
    )
    monkeypatch.setattr(
        widget_generation_service_module,
        "get_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        widget_generation_service_module,
        "A2UIModelClient",
        lambda **_kwargs: ModelClient(),
    )
    monkeypatch.setattr(
        widget_generation_service_module,
        "JsxA2UIBridge",
        RejectedJsxBridge,
    )
    monkeypatch.setattr(
        widget_generation_service_module,
        "get_dsl_processor",
        lambda kind: processor_kinds.append(kind) or Processor(),
    )
    monkeypatch.setattr(
        widget_generation_service_module.ArtifactValidator,
        "validate",
        lambda _self, _artifact, _profile: [],
    )
    monkeypatch.setattr(ArtifactStore, "save", save)

    response = await WidgetGenerationService().generate_widget_card(
        _weather_request(),
        policy=policy_factory(),
        try_jsx=True,
        template_source_generator=template_source_generator,
    )

    assert response.status == GenerationStatus.SUCCESS
    assert template_call_count == 1
    assert model_generate_calls == 0
    assert model_repair_calls == 1
    assert processed_sources == [
        "template-invalid-source",
        "generic-repaired-source",
    ]
    assert processor_kinds == [DslProcessorKind.DESIGN_COMPACT]
    assert saved_design_tokens == ["generic-repaired-source"]


@pytest.mark.asyncio
async def test_terse_edit_is_rejected_before_template_source_request(monkeypatch):
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
        template_source_generator_module,
        "request_template_source_dsl",
        rejected_template,
    )
    monkeypatch.setattr(service, "generate_widget_card", original_generation)
    response = await service.generate_widget_card_terse_dsl_nested2(request)

    assert response.status == GenerationStatus.FAILED
    assert response.errorCode == "A2UI_GENERATION_FAILED"
    assert template_called is False


@pytest.mark.asyncio
async def test_terse_entry_forwards_gallery_template_overrides(monkeypatch):
    expected = object()
    observed: dict[str, Any] = {}

    async def capture_generation(
        _request: Any,
        _policy: Any,
        **options: Any,
    ) -> Any:
        observed.update(options)
        return expected

    service = WidgetGenerationService()
    monkeypatch.setattr(service, "_generate_widget_card_with_policy", capture_generation)
    response = await service.generate_widget_card_terse_dsl_nested2(
        _weather_request(),
        trusted_template_candidate_ids=("WeatherOverviewCompact@1",),
        trusted_template_action_ids=("event.open.weather",),
        trusted_template_sample_overrides={"/data/weather/current/condition": "晴"},
    )

    assert response is expected
    generator = observed["template_source_generator"]
    assert isinstance(generator, TemplateSourceGenerator)
    assert generator.trusted_template_candidate_ids == (
        "WeatherOverviewCompact@1",
    )
    assert generator.trusted_template_action_ids == ("event.open.weather",)
    assert generator.trusted_template_sample_overrides == {
        "/data/weather/current/condition": "晴"
    }
    assert generator.processor_kind is None
    assert generator.protocol_profile is None


@pytest.mark.asyncio
async def test_policy_layer_configures_template_source_generator(monkeypatch):
    expected = object()
    captured: dict[str, Any] = {}

    async def capture_generation(
        _request: Any,
        **options: Any,
    ) -> Any:
        captured.update(options)
        return expected

    service = WidgetGenerationService(model_runtime=object())
    monkeypatch.setattr(service, "generate_widget_card", capture_generation)
    generator = TemplateSourceGenerator(
        trusted_template_candidate_ids=("WeatherOverviewCompact@1",),
    )
    response = await service._generate_widget_card_with_policy(
        _weather_request(),
        _terse_policy(),
        template_source_generator=generator,
        need_fallback=False,
    )

    assert response is expected
    assert captured["template_source_generator"] is generator
    assert captured["need_fallback"] is False
    assert generator.processor_kind == DslProcessorKind.DESIGN_COMPACT
    assert generator.protocol_profile is not None
    assert generator.protocol_profile["id"] == A2UI_FORM_PROTOCOL_PROFILE_ID
    assert generator.model_runtime is service.model_runtime
    assert isinstance(generator.model_request_context, ModelRequestContext)
    assert "enable_fusion_ball" not in captured


@pytest.mark.asyncio
async def test_template_source_generator_uses_task_spec_app_version_gate(monkeypatch):
    observed_flags: list[bool] = []

    monkeypatch.setattr(
        get_settings(),
        "CONFIG",
        {FUSION_BALL_MIN_PRD_VERSION_CONFIG: "11.7.5.206"},
    )

    async def capture_source(
        *_args: Any,
        enable_fusion_ball: bool,
        **_kwargs: Any,
    ) -> str:
        observed_flags.append(enable_fusion_ball)
        return "template-source"

    monkeypatch.setattr(
        "services.template_generation.source_generator.request_template_source_dsl",
        capture_source,
    )
    generator = TemplateSourceGenerator()
    generator.processor_kind = DslProcessorKind.DESIGN_COMPACT
    generator.protocol_profile = {"id": A2UI_FORM_PROTOCOL_PROFILE_ID}
    generator.model_request_context = ModelRequestContext(
        session_id="session",
        interaction_id="interaction",
        device_id="device",
        country_code="CN",
        app_version=_TEST_APP_VERSION,
        app_name="CreateMyCard",
    )

    disabled_task_spec = _weather_task_spec().model_copy(
        update={"appVersion": "11.7.5.205"},
    )
    enabled_task_spec = _weather_task_spec().model_copy(
        update={"appVersion": "11.7.5.206"},
    )
    assert (
        await generator(disabled_task_spec, _weather_card_spec(), ())
        == "template-source"
    )
    assert (
        await generator(enabled_task_spec, _weather_card_spec(), ())
        == "template-source"
    )
    assert observed_flags == [False, True]
