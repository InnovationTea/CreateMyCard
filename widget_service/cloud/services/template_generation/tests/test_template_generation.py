"""模板路由独立模块的关键边界和天气 POC。"""

from __future__ import annotations

import ast
import json
import re
import runpy
import shutil
from pathlib import Path
from typing import Any

import pytest

from api.schemas import GenerateWidgetCardRequest
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
from services.generation_pipeline import (
    DslProcessingResult,
    DslProcessorKind,
    GenerationRoutePolicy,
    QualityIssue,
)
from services.protocol_registry import (
    A2UI_FORM_PROTOCOL_PROFILE_ID,
    TERSE_DSL_NESTED2_PROFILE_ID,
    A2UIProtocolRegistry,
)
from services.template_generation import (
    FusionBallA2UIConversionError,
    convert_a2ui_with_fusion_ball,
    facade,
    route_legacy_python_terse_generation,
)
from services.template_generation.binding_dependencies import enrich_template_bindings
from services.template_generation.controls import TemplateControls, load_template_controls
from services.template_generation.engine import pipeline as template_pipeline_module
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
    scope_template_ids,
    validate_template_request_coverage,
)
from services.template_generation.engine.cardplan import registry as cardplan_registry_module
from services.template_generation.engine.cardplan.compiler import (
    _apply_template_background,
    _apply_theme_content_color,
    _compile_ux_layout_shell,
    _inject_resource_battery_title,
    _lower_action_template_tree,
    _provider_layout_action_background,
)
from services.template_generation.engine.cardplan.fusion_ball_background import (
    FusionBallPalette,
    apply_fusion_ball_background,
    build_fusion_ball_background,
)
from services.template_generation.engine.cardplan.models import HybridBodyContract, HybridLimits
from services.template_generation.engine.cardplan.provider_bundle import (
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
from services.template_generation.engine.terse_dsl_nested2_converter import (
    Nested2Node,
    TerseDslNested2ConversionError,
    convert_terse_dsl_nested2_to_a2ui,
)
from services.widget_generation_service import WidgetGenerationService

_WEATHER_BODY = (
    'Template("SingleFocusLayout@1",{},Template("WeatherOverviewIconFull@1",'
    '{"conditionIcon":"resources/base/media/icon_weather1.svg"}));'
)
_WEATHER_TEMPLATE_FIELDS = (
    "/location/districtName",
    "/current/temperatureText",
    "/current/condition",
    "/current/airQuality",
    "/current/coldLevel",
    "/daily/0/temperatureRangeText",
)
_WEATHER_PALETTE = ("#FF121259", "#FF2B65D9", "#FF57AED9")
_SPORT_PALETTE = ("#FFB33C24", "#FFFF8833", "#FFFAA89E")
_TEST_APP_VERSION = ".".join(("11", "7", "5", "205"))


def _complete_stack_a2ui(root_styles: dict[str, Any]) -> str:
    messages = [
        {
            "version": "v0.9",
            "createSurface": {
                "surfaceId": "weather-card",
                "catalogId": "ohos.a2ui.extended.catalog.form",
            },
        },
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": "weather-card",
                "root": "root",
                "components": [
                    {
                        "id": "root",
                        "component": "Stack",
                        "children": ["weatherTitle"],
                        "styles": {
                            "width": "matchParent",
                            "height": "matchParent",
                            "padding": 12,
                            "borderRadius": 18,
                            "alignContent": "center",
                            "clip": True,
                            **root_styles,
                        },
                    },
                    {
                        "id": "weatherTitle",
                        "component": "Text",
                        "content": "{{ ${/data/weather/title} }}",
                        "styles": {"fontSize": 16, "fontColor": "#FFFFFFFF"},
                    },
                ],
            },
        },
        {
            "version": "v0.9",
            "updateDataModel": {
                "surfaceId": "weather-card",
                "path": "/",
                "value": {"data": {"weather": {"title": "深圳 25℃"}}},
            },
        },
    ]
    return "\n".join(json.dumps(message, ensure_ascii=False) for message in messages)


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

    assert len(registry.provider_template_ids) == 87
    assert {
        "ActivityOverviewFull@1",
        "AppUsageOverviewFull@1",
        "BatteryOverviewNormalFull@1",
        "BatteryOverviewNormalHero@1",
        "BluetoothDeviceOverviewCaseFull@1",
        "CountdownOverviewFull@1",
        "DateOverviewFull@1",
        "HeartRateOverviewFull@1",
        "ResourceUsageOverviewFull@1",
        "ScheduleOverviewNextEventFull@1",
        "SleepOverviewCompact@1",
        "SleepOverviewFull@1",
        "SleepOverviewHero@1",
        "WeatherOverviewAirQualityHero@1",
        "WeatherOverviewConditionFull@1",
        "WeatherOverviewFull@1",
        "WeatherOverviewHero@1",
        "WeatherOverviewHumidityFull@1",
        "WeatherOverviewUvFull@1",
        "WorkoutOverviewFull@1",
        "SingleFocusLayout@1",
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
    assert any("IfPresent" in source for source in provider_source_texts)
    assert any("IfAbsent" in source for source in provider_source_texts)
    assert all(
        definition.variants[0].size == "default"
        for template_id in registry.provider_template_ids
        for definition in (registry.require_template(template_id),)
    )


def test_business_template_suffix_drives_size_and_provider_data_tiers():
    registry = get_cardplan_registry()
    layout_kinds = {"Compact", "Hero", "Full", "WideHero", "WideFull"}

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


def test_cardplan_registry_does_not_require_source_hashes(tmp_path):
    source_root = tmp_path / "source"
    bundled_source_root = get_cardplan_registry().source_root
    shutil.copytree(bundled_source_root, source_root)
    rule_path = source_root / "themes/family-weather-care-blue/first-layer.md"
    rule_path.write_text(
        rule_path.read_text(encoding="utf-8") + "\n<!-- local update -->\n",
        encoding="utf-8",
    )

    registry = CardPlanRegistry(source_root=source_root)

    assert registry.require_theme("family-weather-care-blue") is not None
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
    assert len(calendar.local_template_ids) == 10
    assert set(calendar.local_template_ids) >= {
        "DateOverviewCompact@1",
        "ScheduleOverviewMeetingCompact@1",
    }
    assert len(registry.ux_layout_component_provider_ids) == 10
    for bundle in registry.provider_bundles.values():
        payload = json.loads(
            (registry.source_root / "providers" / bundle.manifest.provider_id.removeprefix(
                "com.huawei."
            ).removesuffix(".cli") / "provider.json").read_text(encoding="utf-8")
        )
        assert "businessComponents" not in payload
        assert all("digest" not in template for template in payload.get("templates", []))


def test_registry_uses_only_distributed_provider_and_theme_sources() -> None:
    registry = get_cardplan_registry()
    central_sources = {
        "advanced-component-registry.json",
        "advanced-component-ux-registry.json",
        "template-registry.json",
        "theme-profiles.json",
    }

    assert all(not (registry.source_root / name).exists() for name in central_sources)
    assert set(registry.templates) == set(registry.provider_template_ids)
    assert len(registry.themes) == 17
    assert all(
        (registry.source_root / "themes" / theme_id / "theme.json").is_file()
        for theme_id in registry.themes
    )


def test_theme_styles_have_distinct_root_content_and_action_scopes() -> None:
    registry = get_cardplan_registry()
    contract = HybridBodyContract.model_construct(
        theme_profile_id="device-clean-blue-teal",
        allowed_layout_component_ids=("SingleFocusLayout",),
    )
    action = Nested2Node(
        "Stack",
        (
            {
                "_boundTemplateAction": "event.open",
                "onClick": [{"call": "open"}],
            },
        ),
        (Nested2Node("Text", ("打开",), ()),),
    )
    content = Nested2Node(
        "Column",
        (),
        (
            Nested2Node("Text", ("默认内容色",), ()),
            Nested2Node("Text", ("显式内容色", {"fontColor": "#FF123456"}), ()),
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
    default_text, explicit_text, button, styled_action = styled.children

    assert root_options["backgroundColor"] == "#FFFFFFFF"
    assert root_options["padding"] == 11
    assert default_text.values[-1]["fontColor"] == "#FF0A59F7"
    assert explicit_text.values[-1]["fontColor"] == "#FF123456"
    assert button.values[-1]["fontColor"] == "#FF0A59F7"
    assert len(styled_action.children[0].values) == 1

    action_style = registry.require_theme("device-clean-blue-teal").action_style
    assert action_style is not None
    action_template = Nested2Node("PillAction", (), (action,))
    lowered_action = _lower_action_template_tree(
        action_template,
        background=action_style.background_color,
        foreground=action_style.content_color,
        action_style=action_style,
    )
    assert lowered_action.values[-1]["backgroundColor"] == action_style.background_color
    assert lowered_action.values[-1]["height"] == action_style.height
    assert lowered_action.children[0].values[-1]["fontColor"] == action_style.content_color


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


def test_nested2_full_document_converts_component_binding_and_data_model():
    profile = A2UIProtocolRegistry.read_design_protocol_profile(
        TERSE_DSL_NESTED2_PROFILE_ID
    )
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

    a2ui = convert_terse_dsl_nested2_to_a2ui(
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
    profile = A2UIProtocolRegistry.read_design_protocol_profile(
        TERSE_DSL_NESTED2_PROFILE_ID
    )
    source = 'Column("card",Text("天气","body")); data={"_templateProjection":{}}'

    with pytest.raises(TerseDslNested2ConversionError, match="internal projection"):
        convert_terse_dsl_nested2_to_a2ui(
            source,
            size="2x2",
            protocol_profile=profile,
        )


def test_nested2_full_document_requires_data_for_every_component_binding():
    profile = A2UIProtocolRegistry.read_design_protocol_profile(
        TERSE_DSL_NESTED2_PROFILE_ID
    )
    task_spec = {
        "dataModelSchema": {
            "data": {"weather": {"temperature": _provider_field("38℃", "string")}}
        }
    }
    source = 'Column("card",Text("${data.weather.temperature}","body")); data={}'

    with pytest.raises(TerseDslNested2ConversionError, match="missing component binding"):
        convert_terse_dsl_nested2_to_a2ui(
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
            "fusion-schedule-warm",
            "schedule-warm",
            FusionBallPalette("#FF731D28", "#FFFF5533", "#FFE68A2E"),
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
        ("meeting-paper-neutral", None, None),
    ],
)
def test_fusion_ball_palette_is_gated_by_selected_theme(
    theme_profile_id: str,
    expected_scene: str | None,
    expected_palette: FusionBallPalette | None,
):
    theme = get_cardplan_registry().require_theme(theme_profile_id)

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
        ("fusion-sport-orange", "#FFFFE1CC", "#99FFE1CC"),
        ("fusion-schedule-warm", "#FFFFEFE6", "#99FFEFE6"),
        ("fusion-battery-teal", "#FFCCFFF6", "#99CCFFF6"),
        ("fusion-schedule-cool", "#FFCCEEFF", "#99CCEEFF"),
    ],
)
def test_fusion_theme_content_and_action_colors_are_exact(
    theme_id: str,
    primary: str,
    support: str,
) -> None:
    theme = get_cardplan_registry().require_theme(theme_id)

    assert theme.primary_color == primary
    assert theme.support_content_color == support
    assert theme.action_style.content_color == primary
    assert theme.action_style.background_color == "#33FFFFFF"


def test_non_fusion_themes_use_one_color_for_primary_and_support_content() -> None:
    themes = get_cardplan_registry().themes.values()

    assert all(
        theme.primary_color == theme.support_content_color
        for theme in themes
        if theme.fusion_ball_style is None
    )


def test_fusion_ball_background_builds_the_supported_160vp_terse_tree():
    palette = FusionBallPalette(*_WEATHER_PALETTE)
    background = build_fusion_ball_background(palette)
    background_options = background.values[-1]
    slots = background.children[0:3]
    glass = background.children[3]

    assert background.component_type == "Stack"
    assert background_options["_id"] == "fusionBallBackground"
    assert background_options["width"] == 160
    assert background_options["height"] == 160
    assert "backgroundColor" not in background_options
    assert [slot.values[-1]["alignContent"] for slot in slots] == [
        "center",
        "bottom",
        "bottomEnd",
    ]
    assert [
        (slot.values[-1]["width"], slot.values[-1]["height"]) for slot in slots
    ] == [(180, 44), (80, 220), (195, 190)]
    assert [slot.children[0].values[-1]["backgroundColor"] for slot in slots] == [
        *_WEATHER_PALETTE,
    ]
    assert [slot.children[0].values[-1]["width"] for slot in slots] == [210, 160, 100]
    assert [slot.children[0].component_type for slot in slots] == ["Stack"] * 3
    assert [slot.children[0].children for slot in slots] == [()] * 3
    assert glass.component_type == "Stack"
    assert glass.children == ()
    assert glass.values[-1]["backgroundColor"] == "#0DFFFFFF"
    assert glass.values[-1]["backdropBlur"] == {"radius": 120}


def test_fusion_ball_wraps_only_2x2_and_replaces_the_card_gradient():
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
    assert [child.values[-1]["_id"] for child in wrapped.children] == [
        "fusionBallBackground",
        "cardContent",
    ]
    assert "backgroundColor" not in foreground_options
    assert "linearGradient" not in foreground_options
    assert "backgroundColor" not in wrapped.values[-1]
    assert foreground_options["width"] == 160
    assert foreground_options["height"] == 160
    content_icon = wrapped.children[1].children[1]
    action_icon = wrapped.children[1].children[2].children[0]
    action_text = wrapped.children[1].children[2].children[1]
    content_text = wrapped.children[1].children[0]
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
                    "colors": [["#1AE84026", 0], ["#00FFFFFF", 1]],
                },
            },
        ),
        (Nested2Node("Text", ("会议", "body"), ()),),
    )
    contract = HybridBodyContract.model_construct(theme_profile_id="meeting-paper-neutral")

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
        ("fusion-weather-blue", ("WeatherOverviewCompact@1",), False),
        ("fusion-weather-blue", ("ScheduleOverviewNextEventFull@1",), False),
        (
            "fusion-weather-blue",
            (
                "WeatherOverviewFull@1",
                "ScheduleOverviewNextEventFull@1",
            ),
            False,
        ),
        ("fusion-sleep-violet", ("SleepOverviewFull@1",), True),
        ("fusion-sleep-violet", ("ActivityOverviewFull@1",), False),
    ],
)
def test_fusion_theme_requires_one_matching_full_or_hero_business(
    theme_id: str,
    selected_template_ids: tuple[str, ...],
    expect_fusion: bool,
) -> None:
    card = Nested2Node(
        "Column",
        ("card", {"_id": "root", "backgroundColor": "#FF121259"}),
        (Nested2Node("Text", ("内容", {"fontColor": "#FFCCDDFF"}), ()),),
    )
    contract = HybridBodyContract.model_construct(theme_profile_id=theme_id)

    decorated = _apply_template_background(
        card,
        "2x2",
        contract,
        get_cardplan_registry(),
        selected_template_ids,
    )

    assert (decorated is not card) is expect_fusion
    if expect_fusion:
        assert decorated.children[0].values[-1]["_id"] == "fusionBallBackground"
        assert decorated.children[1].children[0].values[-1]["fontColor"] == "#FFCCDDFF"


@pytest.mark.parametrize(
    "root_background",
    [
        {"backgroundColor": "#FF123456"},
        {
            "backgroundColor": "#FF112233",
            "linearGradient": {
                "direction": "Bottom",
                "colors": [["#FFFF0000", 0], ["#FF00FF00", 1]],
            },
        },
    ],
)
def test_complete_a2ui_converter_replaces_stack_background_with_fusion_balls(
    root_background: dict[str, Any],
):
    source = _complete_stack_a2ui(root_background)
    source_messages = [json.loads(line) for line in source.splitlines()]

    converted = convert_a2ui_with_fusion_ball(source, palette=_WEATHER_PALETTE)
    messages = [json.loads(line) for line in converted.splitlines()]
    update = messages[1]["updateComponents"]
    components = {component["id"]: component for component in update["components"]}
    root = components["root"]
    content_id = "cardContent"
    content = components[content_id]

    assert len(messages) == 3
    assert messages[0] == source_messages[0]
    assert messages[2] == source_messages[2]
    assert update["root"] == "root"
    assert root["component"] == "Stack"
    assert root["children"] == ["fusionBallBackground", content_id]
    assert root["styles"]["padding"] == 0
    assert root["styles"]["alignContent"] == "topStart"
    assert "backgroundColor" not in root["styles"]
    assert "linearGradient" not in root["styles"]
    assert content["component"] == "Stack"
    assert content["children"] == ["weatherTitle"]
    assert content["styles"]["padding"] == 12
    assert content["styles"]["alignContent"] == "center"
    assert "backgroundColor" not in content["styles"]
    assert "linearGradient" not in content["styles"]
    assert components["fusionBallLarge"]["styles"]["backgroundColor"] == _WEATHER_PALETTE[0]
    assert components["fusionBallMedium"]["styles"]["backgroundColor"] == _WEATHER_PALETTE[1]
    assert components["fusionBallSmall"]["styles"]["backgroundColor"] == _WEATHER_PALETTE[2]
    assert "backgroundColor" not in components["fusionBallBackground"]["styles"]
    assert not components["fusionBallBackground"]["id"].startswith(
        "__genui_render_component__"
    )
    assert components["fusionBallGlassLayer"]["children"] == []
    assert components["fusionBallGlassLayer"]["styles"]["backdropBlur"] == {
        "radius": 120
    }
    assert components["weatherTitle"]["styles"]["fontColor"] == "#FFFFFFFF"
    assert validate_card(dsl_text=converted).diagnostics == []
    assert convert_a2ui_with_fusion_ball(converted, palette=_WEATHER_PALETTE) == converted


def test_complete_a2ui_converter_removes_legacy_fusion_content_marker():
    source = _complete_stack_a2ui({"backgroundColor": "#FF008FBF"})
    converted = convert_a2ui_with_fusion_ball(source, palette=_WEATHER_PALETTE)
    legacy_content_id = "__genui_render_component__cardContent"
    legacy = converted.replace("cardContent", legacy_content_id)

    upgraded = convert_a2ui_with_fusion_ball(legacy, palette=_WEATHER_PALETTE)
    update = json.loads(upgraded.splitlines()[1])["updateComponents"]
    component_ids = {component["id"] for component in update["components"]}

    assert update["components"][0]["children"] == [
        "fusionBallBackground",
        "cardContent",
    ]
    assert "cardContent" in component_ids
    assert legacy_content_id not in component_ids


def test_complete_a2ui_converter_preserves_provider_content_and_actions():
    messages = [
        json.loads(line)
        for line in _complete_stack_a2ui({"backgroundColor": "#FF008FBF"}).splitlines()
    ]
    update = messages[1]["updateComponents"]
    update["components"][0]["children"].extend(["weatherIcon", "pillAction"])
    update["components"].extend(
        [
            {
                "id": "weatherIcon",
                "component": "Image",
                "src": "resources/base/media/icon_weather1.svg",
                "styles": {"width": 20, "height": 20, "fillColor": "#FF000000"},
            },
            {
                "id": "pillAction",
                "component": "Stack",
                "children": ["pillActionIcon", "pillActionLabel"],
                "onClick": [{"call": "openWeather"}],
                "styles": {"backgroundColor": "#FFFFFFFF"},
            },
            {
                "id": "pillActionIcon",
                "component": "Image",
                "src": "resources/base/media/phone_fill.svg",
                "styles": {"fillColor": "#FF64BB5C"},
            },
            {
                "id": "pillActionLabel",
                "component": "Text",
                "content": "详情",
                "styles": {"fontColor": "#FF64BB5C"},
            },
        ]
    )
    source = "\n".join(
        json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        for message in messages
    )

    converted = convert_a2ui_with_fusion_ball(source, palette=_WEATHER_PALETTE)
    converted_update = json.loads(converted.splitlines()[1])["updateComponents"]
    components = {
        component["id"]: component for component in converted_update["components"]
    }

    assert components["weatherTitle"]["styles"]["fontColor"] == "#FFFFFFFF"
    assert components["weatherIcon"]["src"] == "resources/base/media/icon_weather1.svg"
    assert components["weatherIcon"]["styles"]["fillColor"] == "#FF000000"
    assert components["pillActionIcon"]["styles"]["fillColor"] == "#FF64BB5C"
    assert components["pillActionLabel"]["styles"]["fontColor"] == "#FF64BB5C"

def test_complete_a2ui_converter_rejects_invalid_theme_palette():
    source = _complete_stack_a2ui({"backgroundColor": "#FF008FBF"})

    with pytest.raises(FusionBallA2UIConversionError, match="three Theme colors"):
        convert_a2ui_with_fusion_ball(source, ("#FF121259",))
    with pytest.raises(FusionBallA2UIConversionError, match="#AARRGGBB"):
        convert_a2ui_with_fusion_ball(source, ("#121259", "#FF2B65D9", "#FF57AED9"))


@pytest.mark.parametrize(
    "expected_colors",
    [
        _WEATHER_PALETTE,
        _SPORT_PALETTE,
        ("#FF2B2459", "#FF572BD9", "#FFB398D9"),
    ],
)
def test_complete_a2ui_converter_uses_theme_palette(
    expected_colors: tuple[str, str, str],
):
    source = _complete_stack_a2ui({"backgroundColor": "#FF123456"})
    converted = convert_a2ui_with_fusion_ball(source, expected_colors)
    components = {
        component["id"]: component
        for component in json.loads(converted.splitlines()[1])["updateComponents"][
            "components"
        ]
    }

    actual_colors = tuple(
        components[component_id]["styles"]["backgroundColor"]
        for component_id in ("fusionBallLarge", "fusionBallMedium", "fusionBallSmall")
    )
    assert actual_colors == expected_colors


def test_complete_a2ui_converter_file_is_self_contained(tmp_path):
    source_path = Path(convert_a2ui_with_fusion_ball.__code__.co_filename)
    module = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_roots = {
        imported_root
        for node in ast.walk(module)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for imported_root in (
            [alias.name.split(".", 1)[0] for alias in node.names]
            if isinstance(node, ast.Import)
            else [(node.module or "").split(".", 1)[0]]
        )
    }

    assert imported_roots <= {"__future__", "colorsys", "copy", "json", "re", "typing"}
    copied_path = tmp_path / "fusion_ball_a2ui_converter.py"
    shutil.copyfile(source_path, copied_path)
    copied_module = runpy.run_path(str(copied_path))
    source = _complete_stack_a2ui({"backgroundColor": "#FF123456"})
    converted = copied_module["convert_a2ui_with_fusion_ball"](source, _WEATHER_PALETTE)
    components = {
        component["id"]: component
        for component in json.loads(converted.splitlines()[1])["updateComponents"][
            "components"
        ]
    }

    assert components["fusionBallMedium"]["styles"]["backgroundColor"] == _WEATHER_PALETTE[1]


@pytest.mark.parametrize(
    ("root_update", "error"),
    [
        ({"component": "Column"}, "root component must be Stack"),
        ({"styles": {}}, "must contain backgroundColor or linearGradient"),
        (
            {
                "styles": {
                    "backgroundColor": "#FF008FBF",
                    "backgroundImage": "resources/base/media/weather.png",
                }
            },
            "does not replace a backgroundImage",
        ),
    ],
)
def test_complete_a2ui_converter_rejects_unsupported_root_backgrounds(
    root_update: dict[str, Any],
    error: str,
):
    source_messages = [
        json.loads(line)
        for line in _complete_stack_a2ui({"backgroundColor": "#FF008FBF"}).splitlines()
    ]
    root = source_messages[1]["updateComponents"]["components"][0]
    root.update(root_update)
    source = "\n".join(json.dumps(message) for message in source_messages)

    with pytest.raises(FusionBallA2UIConversionError, match=error):
        convert_a2ui_with_fusion_ball(source, palette=_WEATHER_PALETTE)


def test_form_validator_allows_empty_stack_children_but_rejects_empty_column_children():
    profile = A2UIProtocolRegistry(A2UI_FORM_PROTOCOL_PROFILE_ID).get_profile()
    reports = {}
    for component_type in ("Stack", "Column"):
        source = f'{component_type}("card",{{"backgroundColor":"#FF008FBF"}});'
        dsl = convert_terse_dsl_nested2_to_a2ui(
            source,
            size="2x2",
            protocol_profile=profile,
        )
        reports[component_type] = validate_card(dsl_text=dsl)

    stack_children_errors = [
        diagnostic
        for diagnostic in reports["Stack"].diagnostics
        if diagnostic.code == "DSL_COMPONENT_REQUIRED_FIELD"
        and diagnostic.json_pointer.endswith("/children")
    ]
    column_children_errors = [
        diagnostic
        for diagnostic in reports["Column"].diagnostics
        if diagnostic.code == "DSL_COMPONENT_REQUIRED_FIELD"
        and diagnostic.json_pointer.endswith("/children")
    ]
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
        "AppUsageOverviewFull@1": (18, 10),
        "AppUsageOverviewHero@1": (18, 10),
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
    assert "WeatherOverviewIconFull@1" in first_layer_content
    assert "WeatherOverviewIconFull@1" in second_layer_rules


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
    assert not registry.template_is_enabled("ScheduleOverviewNextEventFull@1")
    assert not registry.template_is_enabled("BluetoothDeviceOverviewCaseFull@1")
    assert registry.template_is_enabled("WeatherOverviewFull@1")


def test_invalid_first_layer_component_selector_fails_closed():
    with pytest.raises(ValueError, match="firstLayerComponentSelector"):
        TemplateControls(
            schemaVersion="template-controls/1",
            firstLayerComponentSelector="invalid",
        )


def test_first_layer_decision_contract_carries_component_template_candidates():
    payload = {
        "theme": "family-weather-care-blue",
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
                    "ScheduleOverviewNextEventFull@1",
                    "ScheduleOverviewNextEventLocationFull@1",
                ],
            },
        ],
        "action": ["event.open.weather"],
    }

    decision = TemplateRouteDecision.model_validate(payload)

    assert decision.component_ids == ("WeatherOverview", "CalendarOverview")
    assert decision.model_dump(mode="json", by_alias=True) == payload


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


def test_pr6_bluetooth_action_background_is_owned_by_cardtpl_metadata():
    registry = get_cardplan_registry()
    definition = registry.require_template("BluetoothDeviceOverviewCaseFull@1")
    assert definition.layout_action_style is not None
    assert definition.layout_action_style.background_opacity == 0.1
    contract = HybridBodyContract(
        theme_profile_id="audio-product-neutral-violet",
        allowed_components=(),
        allowed_design_tokens=(),
        allowed_layout_tokens=(),
        allowed_template_ids=("BluetoothDeviceOverviewCaseFull@1",),
        required_template_groups=(("BluetoothDeviceOverviewCaseFull@1",),),
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

    countdown = registry.require_variant("CountdownOverviewFull@1", "default").root
    assert _template_node_options(countdown)["justifyContent"] == "start"
    assert _template_node_options(countdown.children[1])["justifyContent"] == "center"
    assert _template_node_options(countdown.children[1].children[0])["justifyContent"] == "center"

    app_usage = registry.require_variant("AppUsageOverviewFull@1", "default").root
    assert _template_node_options(app_usage)["justifyContent"] == "start"
    duration_region = app_usage.children[1]
    assert _template_node_options(duration_region)["justifyContent"] == "end"
    assert _template_node_options(duration_region)["itemMargin"] == 4

    battery = registry.require_variant("BatteryOverviewNormalFull@1", "default").root
    battery_support_color = battery.children[1].values[-1].properties["fontColor"]
    assert battery_support_color.kind == "theme"
    assert battery_support_color.name == "supportContentColor"
    battery_hero = registry.require_variant("BatteryOverviewNormalHero@1", "default").root
    battery_wide = registry.require_variant("BatteryOverviewNormalWideFull@1", "default").root
    assert _template_node_options(battery_hero)["justifyContent"] == "start"
    assert _template_node_options(battery_wide)["justifyContent"] == "start"
    assert battery_hero.children[0].component == "Column"
    assert battery_wide.children[1].component == "Row"
    assert _template_node_options(battery_wide.children[1])["layoutWeight"] == 1
    assert _template_node_options(_template_nodes(battery_hero, "Progress")[0])["width"] == 52
    battery_peer = registry.require_variant("BatteryOverviewNormalCompact@1", "default").root
    assert _template_node_options(battery_peer)["justifyContent"] == "end"
    assert _template_node_options(_template_nodes(battery_peer, "Image")[0])["width"] == 20

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


def test_calendar_templates_follow_latest_date_schedule_ux_geometry():
    registry = get_cardplan_registry()

    date_compact = registry.require_variant("DateOverviewCompact@1", "default").root
    assert date_compact.component == "Column"
    assert _template_node_options(date_compact)["height"] == "100%"
    assert _template_node_options(date_compact.children[0])["height"] == 12
    compact_date_options = _template_node_options(date_compact.children[1])
    assert compact_date_options["height"] == 44
    assert compact_date_options["fontSize"] == 38

    date_full = registry.require_variant("DateOverviewFull@1", "default").root
    assert _template_node_options(date_full)["justifyContent"] == "spaceBetween"
    assert _template_node_options(date_full.children[0])["height"] == 64
    assert _template_node_options(date_full.children[1])["height"] == 40

    schedule = registry.require_variant(
        "ScheduleOverviewMeetingLocationCompact@1",
        "default",
    ).root
    timeline = schedule.children[0]
    assert _template_node_options(timeline.children[0])["width"] == 8
    assert _template_node_options(timeline.children[1])["height"] == 36
    text_options = [_template_node_options(node) for node in _template_nodes(schedule, "Text")]
    assert text_options[0]["height"] == 20
    assert all(options["height"] == 14 for options in text_options[1:])


@pytest.mark.asyncio
async def test_calendar_date_and_schedule_compacts_generate_one_vertical_card():
    class CalendarTemplateModel:
        async def generate_json(
            self,
            _prompt: list[dict[str, str]],
            **_kwargs: Any,
        ) -> dict[str, Any]:
            return {
                "themeId": "meeting-paper-neutral",
                "requiredOutputFieldsByCapability": {
                    "GetCalendarEvents": [
                        "/events/0/startDate",
                        "/events/0/title",
                        "/events/0/dtStart",
                    ]
                },
                "action": [],
            }

        async def generate(
            self,
            _prompt: list[dict[str, str]],
            *_args: Any,
            **_kwargs: Any,
        ) -> str:
            return (
                'Template("PeerPairLayout@1",{},'
                'Template("DateOverviewCompact@1",{}),'
                'Template("ScheduleOverviewMeetingCompact@1",{}));'
            )

    task = TaskSpec(
        userQuery="显示日期和下一场会议的标题、时间",
        size="2x2",
        dataModelSchema={
            "data": {
                "calendar": {
                    "events": [
                        {
                            "startDate": _provider_field("2026-08-19", "string"),
                            "title": _provider_field("UI需求评审会", "string"),
                            "dtStart": _provider_field("14:00", "string"),
                            "dtEnd": _provider_field("15:30", "string"),
                        }
                    ],
                    "updatedAt": _provider_field("2026-08-19 09:00", "string"),
                }
            }
        },
    )
    fields = [
        "/events/0/startDate",
        "/events/0/title",
        "/events/0/dtStart",
        "/events/0/dtEnd",
        "/updatedAt",
    ]
    binding = CandidateDataBinding(
        capabilityId="GetCalendarEvents",
        writeResultTo="/data/calendar",
        candidateOutputFields=fields,
    )
    card_spec = {
        "suggestSize": "2x2",
        "dataBindings": [
            {
                "capabilityId": "GetCalendarEvents",
                "writeResultTo": "/data/calendar",
            }
        ],
    }

    output = await generate_template_a2ui(
        task,
        card_spec,
        (binding,),
        CalendarTemplateModel(),
    )

    assert output.template_ids == (
        "DateOverviewCompact@1",
        "ScheduleOverviewMeetingCompact@1",
        "PeerPairLayout@1",
    )
    assert "UI需求评审会" in output.a2ui
    assert "2026-08-19" in output.a2ui


def test_pr7_resource_battery_outer_title_keeps_the_reviewed_subtext_style():
    registry = get_cardplan_registry()
    contract = HybridBodyContract(
        theme_profile_id="device-clean-blue-teal",
        allowed_components=(),
        allowed_design_tokens=(),
        allowed_layout_tokens=(),
        allowed_template_ids=(
            "BatteryOverviewNormalCompact@1",
            "ResourceUsageOverviewCompact@1",
        ),
        required_template_groups=(
            ("BatteryOverviewNormalCompact@1",),
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
    assert "_templateProjection" not in output.terse_dsl_nested2
    assert "_advancedSelectors" not in output.terse_dsl_nested2
    assert projected_data["appUsageStats"]["appUsage"]["durationText"]["sampleValue"] == (
        "1小时20分钟"
    )
    assert "data = " in output.terse_dsl_nested2
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
async def test_q094_multi_business_fields_reject_template_search():
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
                "themeId": "race-sunrise-action",
                "requiredOutputFieldsByCapability": {
                    "GetHealthAndSportSummary": [
                        "/sleepScore",
                        "/nightSleepDurationText",
                        "/dailySteps",
                    ]
                },
                "action": None,
            }

        async def generate(
            self,
            prompt: list[dict[str, str]],
            *_args: Any,
            **_kwargs: Any,
        ) -> str:
            self.second_layer_prompt = prompt
            raise AssertionError("multi-business Search miss must skip the second layer")

    model = Q094TemplateModel()
    with pytest.raises(TemplateRouteNotApplicable, match="one business component"):
        await generate_template_a2ui(task_spec, card_spec, (binding,), model)

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
        action_id: str | None = None,
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
    template_ids = {
        "connection": "BluetoothDeviceOverviewConnectionFull@1",
        "earbuds": "BluetoothDeviceOverviewCaseFull@1",
    }
    template_id = template_ids[variant]
    binding = CandidateDataBinding(
        capabilityId="GetEarphoneInfo",
        writeResultTo="/data/earphone",
        candidateOutputFields=list(required_fields),
    )
    model = _FixedTemplateModel(
        theme_id="audio-product-neutral-violet",
        component_id="BluetoothDeviceOverview",
        available_template_ids=(template_id,),
        capability_id="GetEarphoneInfo",
        required_fields=required_fields,
        body=(
            'Template("SingleFocusLayout@1",{},Template('
            f'"{template_id}",{{}}));'
        ),
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
        available_template_ids=("BluetoothDeviceOverviewCaseFull@1",),
        capability_id="GetEarphoneInfo",
        required_fields=("/isConnected", "/batteryLevel"),
        action_id="event.open.music.daily",
        body=(
            'Template("SingleFocusLayout@1",{},'
            'Template("BluetoothDeviceOverviewCaseFull@1",{}),'
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
        capability_id="GetPhoneBatteryInfo",
        required_fields=("/batterySOC", "/chargingStatusDesc"),
        action_id="event.setPowerSavingMode",
        body=(
            'Template("HeroActionLayout@1",{},'
            'Template("BatteryOverviewNormalHero@1",'
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
    )

    assert output.template_ids == (
        "BatteryOverviewNormalHero@1",
        "PillAction@1",
        "HeroActionLayout@1",
    )
    assert model.second_layer_prompt is not None
    second_layer_system = model.second_layer_prompt[0]["content"]
    second_layer_user = model.second_layer_prompt[1]["content"]
    assert "Template('PillAction@1', props)" in second_layer_system
    assert '"actionId": "event.setPowerSavingMode"' in second_layer_system
    assert '"label": "省电模式"' in second_layer_system
    assert "约 2x1.7；用于 2x2 主内容加一个 PillAction" in second_layer_user
    assert "业务模板本身不得携带按钮" in second_layer_user
    assert "PillAction@1" in second_layer_user
    assert '"height":36' in output.a2ui
    assert "省电模式" in output.a2ui
    assert "batterySOC" in output.a2ui
    assert "chargingStatusDesc" in output.a2ui
    messages = [json.loads(line) for line in output.a2ui.splitlines()]
    components = {
        item["id"]: item for item in messages[1]["updateComponents"]["components"]
    }
    layout = components[components["root"]["children"][0]]
    assert layout["component"] == "Column"
    assert layout["itemMargin"] == 8
    assert layout["styles"] == {"width": "matchParent", "height": "matchParent"}
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
        theme_id="system-low-power-blue",
        component_id="BatteryOverview",
        available_template_ids=("BatteryOverviewNormalHero@1",),
        capability_id="GetPhoneBatteryInfo",
        required_fields=("/batterySOC", "/chargingStatusDesc"),
        action_id="event.setPowerSavingMode",
        body=(
            'Template("HeroActionLayout@1",{},'
            'Template("BatteryOverviewNormalHero@1",{}),'
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
        theme_id="system-low-power-blue",
        component_id="BatteryOverview",
        available_template_ids=("BatteryOverviewPercentRingHero@1",),
        capability_id="GetPhoneBatteryInfo",
        required_fields=("/batterySOC", "/batterySOCText"),
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
    )

    assert output.template_ids == (
        "BatteryOverviewPercentRingHero@1",
        "PillAction@1",
        "HeroActionLayout@1",
    )
    assert "batterySOC" in output.a2ui
    assert "batterySOCText" in output.a2ui
    assert "batteryCapacityLevelDesc" not in output.a2ui
    assert "省电模式" in output.a2ui


def test_battery_normal_hero_requires_a_selected_layout_action():
    registry = get_cardplan_registry()
    definition = registry.require_template("BatteryOverviewNormalHero@1")
    scope = AdvancedScopeBrief(
        themeId="system-low-power-blue",
        advancedComponentIds=["BatteryOverview"],
    )
    no_action_task = _battery_task().model_copy(update={"eventCandidates": []})

    assert definition.requires_layout_action is True
    assert "BatteryOverviewNormalHero@1" not in scope_template_ids(
        scope,
        registry,
        no_action_task,
    )
    assert "BatteryOverviewNormalFull@1" in scope_template_ids(scope, registry, no_action_task)
    assert "BatteryOverviewNormalHero@1" in scope_template_ids(
        scope,
        registry,
        _battery_task(),
    )


@pytest.mark.asyncio
async def test_battery_normal_hero_without_pill_action_is_repaired_to_normal_template():
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
                theme_id="system-low-power-blue",
                component_id="BatteryOverview",
                available_template_ids=(
                    "BatteryOverviewNormalFull@1",
                    "BatteryOverviewNormalHero@1",
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
                return layout + 'Template("BatteryOverviewNormalHero@1",{}));'
            return layout + 'Template("BatteryOverviewNormalFull@1",{}));'

    model = RepairingBatteryModel()
    output = await generate_template_a2ui(
        _battery_task(),
        _battery_card_spec(),
        (binding,),
        model,
    )

    assert model.body_calls == 2
    assert output.template_ids == ("BatteryOverviewNormalFull@1", "SingleFocusLayout@1")
    assert model.second_layer_prompt is not None
    candidate_line = next(
        line
        for line in model.second_layer_prompt[1]["content"].splitlines()
        if line.startswith("componentCandidates=")
    )
    candidates = json.loads(candidate_line.removeprefix("componentCandidates="))
    assert len(candidates) == 1
    assert candidates[0]["componentId"] == "BatteryOverview"
    assert "BatteryOverviewNormalFull@1" in candidates[0]["availableTemplateIds"]
    assert "BatteryOverviewNormalHero@1" not in candidates[0]["availableTemplateIds"]
    assert "PillAction" not in output.terse_dsl_nested2


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
        available_template_ids=("CountdownOverviewFull@1",),
        capability_id="GetCountdownDays",
        required_fields=("/countdownDays",),
        body='Template("SingleFocusLayout@1",{},Template("CountdownOverviewFull@1",{}));',
    )

    output = await generate_template_a2ui(task_spec, card_spec, (binding,), model)

    assert output.template_ids == ("CountdownOverviewFull@1", "SingleFocusLayout@1")
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
            "WeatherOverviewFull@1",
            "WeatherOverviewIconFull@1",
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
            "themeId": "fusion-weather-blue",
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
                            "availableTemplateIds": ["WeatherOverviewIconFull@1"],
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
                    'Template("SingleFocusLayout@1",{},'
                    'Template("WeatherOverviewIconFull@1",'
                    '{"conditionIcon":"resources/base/media/icon_weather1.svg"}),'
                    'Template("IconAction@1",{"actionId":"event.open.weather",'
                    '"icon":"resources/base/media/icon_weather1.svg"}));'
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
                'Template("ActionMatrixLayout@1",{},'
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
        "ActionMatrixLayout@1",
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


def _legacy_terse_policy() -> GenerationRoutePolicy:
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
                        "coldLevel": field("低"),
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

    async def generate(*_args: Any) -> Output:
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
    ) -> Output:
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
                "WeatherOverviewCompact@1",
                "WeatherOverviewConditionFull@1",
                "WeatherOverviewFull@1",
                "WeatherOverviewIconCompact@1",
                "WeatherOverviewIconFull@1",
            ],
        }
    ]
    required_group_line = next(
        line
        for line in second_layer_user.splitlines()
        if line.startswith("requiredLocalTemplateGroups=")
    )
    assert json.loads(required_group_line.removeprefix("requiredLocalTemplateGroups=")) == [
        [
            "WeatherOverviewCompact@1",
            "WeatherOverviewConditionFull@1",
            "WeatherOverviewFull@1",
            "WeatherOverviewIconCompact@1",
            "WeatherOverviewIconFull@1",
        ],
        [
            "WeatherOverviewCompact@1",
            "WeatherOverviewConditionFull@1",
            "WeatherOverviewFull@1",
            "WeatherOverviewIconCompact@1",
            "WeatherOverviewIconFull@1",
        ],
    ]
    assert "selectedActionEventIds=[]" in second_layer_user
    assert "只能按业务模板布局后缀选择 PillAction@1 或 IconAction@1" in second_layer_user
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
    medium_ball = next(
        item
        for item in messages[1]["updateComponents"]["components"]
        if item["id"] == "fusionBallMedium"
    )
    glass_layer = next(
        item
        for item in messages[1]["updateComponents"]["components"]
        if item["id"] == "fusionBallGlassLayer"
    )
    assert root["component"] == "Stack"
    assert root["children"] == [
        "fusionBallBackground",
        "cardContent",
    ]
    assert root["styles"]["borderRadius"] == 18
    assert "backgroundColor" not in root["styles"]
    assert "linearGradient" not in root["styles"]
    assert medium_ball["children"] == []
    assert medium_ball["styles"]["backgroundColor"] == _WEATHER_PALETTE[1]
    assert glass_layer["styles"]["backdropBlur"] == {"radius": 120}
    assert captured["artifact"].effectiveCapabilities["data"] == ["ViewWeather"]


@pytest.mark.asyncio
async def test_terse_entry_uses_compact_template_source_with_fusion_ball_theme(monkeypatch):
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
            artifactUrl="https://artifact.test/weather-template-terse",
            artifactDigest="sha256:weather-template-terse",
        )

    monkeypatch.setattr(ArtifactStore, "save", save)
    response = await WidgetGenerationService(
        model_runtime=object(),
    ).generate_widget_card_terse_dsl_nested2(_weather_request())

    assert response.status == GenerationStatus.SUCCESS
    assert response.artifactUrl == "https://artifact.test/weather-template-terse"
    compact_rows = [json.loads(line) for line in captured["compact"].splitlines()]
    compact_components = {
        row[0]: row for row in compact_rows if len(row) >= 3 and isinstance(row[0], str)
    }
    assert compact_rows[0][0:2] == ["root", "Stack"]
    content_id = "cardContent"
    assert compact_rows[0][3] == ["fusionBallBackground", content_id]
    assert "backgroundColor" not in compact_rows[0][2]
    assert "linearGradient" not in compact_rows[0][2]
    assert compact_components["fusionBallLarge"][2]["backgroundColor"] == _WEATHER_PALETTE[0]
    assert compact_components["fusionBallMedium"][2]["backgroundColor"] == _WEATHER_PALETTE[1]
    assert compact_components["fusionBallSmall"][2]["backgroundColor"] == _WEATHER_PALETTE[2]
    assert "linearGradient" not in compact_components[content_id][2]
    messages = [json.loads(line) for line in captured["artifact"].genui.splitlines()]
    protocol_profile = A2UIProtocolRegistry(A2UI_FORM_PROTOCOL_PROFILE_ID).get_profile()
    assert messages[0]["createSurface"]["catalogId"] == protocol_profile["catalogId"]
    components = {item["id"]: item for item in messages[1]["updateComponents"]["components"]}
    assert components["root"]["component"] == "Stack"
    assert components["root"]["children"] == ["fusionBallBackground", content_id]
    assert "backgroundColor" not in components["root"]["styles"]
    assert components["fusionBallLarge"]["children"] == []
    assert components["fusionBallMedium"]["children"] == []
    assert components["fusionBallSmall"]["children"] == []
    assert components["fusionBallGlassLayer"]["children"] == []
    assert components["fusionBallGlassLayer"]["styles"]["backdropBlur"] == {
        "radius": 120
    }
    assert components["fusionBallMedium"]["styles"]["backgroundColor"] == _WEATHER_PALETTE[1]
    assert "linearGradient" not in components[content_id]["styles"]
    weather_icons = [
        item
        for item in components.values()
        if item.get("component") == "Image"
        and item.get("src") == "resources/base/media/icon_weather1.svg"
    ]
    assert len(weather_icons) == 1
    assert weather_icons[0]["styles"].get("fillColor") != "#FFFFFFFF"
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
    model = WeatherTemplateModel(available_template_ids=("ScheduleOverviewNextEventFull@1",))
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
    assert "ScheduleOverviewNextEventFull@1" not in output.template_ids


@pytest.mark.asyncio
async def test_second_layer_rejects_provider_template_outside_first_layer_candidates():
    model = WeatherTemplateModel(
        body=(
            'Template("SingleFocusLayout@1",{},'
            'Template("ScheduleOverviewNextEventFull@1",{}));'
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

    assert output.template_ids == ("WeatherOverviewIconFull@1", "SingleFocusLayout@1")
    assert model.body_called is True


@pytest.mark.asyncio
async def test_first_layer_action_is_independent_from_selected_components():
    model = WeatherTemplateModel(
        action_id="event.open.weather",
        body=(
            'Template("SingleFocusLayout@1",{},Template("WeatherOverviewIconFull@1",'
            '{"conditionIcon":"resources/base/media/icon_weather1.svg"}),'
            'Template("IconAction@1",{"actionId":"event.open.weather",'
            '"icon":"resources/base/media/icon_weather1.svg"}));'
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
    assert "resources/base/media/icon_weather1.svg" in output.a2ui
    assert "cityCode" in output.projected_task_spec.dataModelSchema["data"]["weather"]["location"]


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
            'Template("SingleFocusLayout@1",{},Template("WeatherOverviewIconFull@1",'
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
        widget_generation_service_module,
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
async def test_template_source_quality_failure_uses_common_compact_repair_once(
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
        widget_generation_service_module,
        "request_template_source_dsl",
        rejected_template,
    )
    monkeypatch.setattr(service, "generate_widget_card", original_generation)
    response = await service.generate_widget_card_terse_dsl_nested2(request)

    assert response.status == GenerationStatus.FAILED
    assert response.errorCode == "A2UI_GENERATION_FAILED"
    assert template_called is False


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
        _legacy_terse_policy(),
        before_model_call=notify,
    )

    assert response is expected
    assert observed_callback is notify
