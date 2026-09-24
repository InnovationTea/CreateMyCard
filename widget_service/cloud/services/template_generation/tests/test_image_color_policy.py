"""Image 显式着色、原色保护及真实双业务编译回归。

双 Support 2x2 的真实编译产物已固化为场景金样（Layer C）：
BatteryOverviewSupport + WeatherOverviewTemperatureSupport 挂
event.open.weather deeplink，按 conditionIcon 资产 × feels-like 字段有无
参数化为 8 个场景，完整 A2UI 消息（含 Image 的 fillColor 与尺寸）由快照
整体冻结。per-option fillColor 矩阵（主题着色 4 例 + 动作内着色 3 例，
``image_color__option_matrix``）与 legacy 天气入口按资产着色的 3 例
（``image_color__legacy_entry``）同样固化为按 case 键分组的场景金样；
原色保护与 fillColor 并存的报错路径仍为内联 pytest.raises 精度断言，
保持不变。引擎改动后按 golden 工作流 `check --diff` / `bless --declared`
复核。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from models.generation import EventAction, TaskSpec
from services.protocol_registry import A2UI_FORM_PROTOCOL_PROFILE_ID, A2UIProtocolRegistry
from services.template_generation.engine.advanced.ux_mixed_prompt import build_ux_mixed_prompt
from services.template_generation.engine.cardplan.compiler import (
    _apply_theme_content_color,
    _expand_weather_overview_call,
    _lower_action_template_tree,
    _strip_advanced_component_markers,
    compile_ux_layout_card,
)
from services.template_generation.engine.cardplan.models import HybridBodyContract, SourceSpan
from services.template_generation.engine.cardplan.parser import ParsedCall
from services.template_generation.engine.cardplan.preview_dataset import _build_data_schema
from services.template_generation.engine.cardplan.provider_bundle import compile_card_template
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.cardplan.template_plan_planner import (
    plan_template_candidates,
    planner_component_candidates,
    planner_required_template_groups,
    planner_scope,
)
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateBusinessCandidates,
    TemplateSearchCandidate,
    TemplateSearchIntent,
    TemplateSearchResult,
)
from services.template_generation.engine.tersel_converter import Nested2Node, TerselConversionError
from services.template_generation.test_support.golden_scenarios import (
    assert_golden_scenario,
    scenario,
)

_EXPLICIT = "#FF123456"
_ROOT = Path(__file__).resolve().parents[1]
_ASSETS = _ROOT.parents[1] / "data/capabilities/app-11.7.5.205_rom-6.0/asset_capabilities.json"


def _template_source(options: str) -> str:
    return (
        '#Template ImagePolicy@1(props: {})\ndata = {}\n'
        'Column(Image("resources/base/media/icon_weather_thermometer.svg", {'
        + options + '}))\n#End\n'
    )


_FEELS_LIKE_STATES: tuple[tuple[str, bool], ...] = (("present", True), ("absent", False))
_CONDITION_ICON_ASSETS: tuple[tuple[str, str], ...] = (
    ("icon_weather_thermometer", "icon_weather_thermometer.svg"),
    ("icon_weather_thermometer_medium", "icon_weather_thermometer_medium.svg"),
    ("sun_max", "sun_max.svg"),
    ("icon_weather_wind", "icon_weather_wind.svg"),
)


def _render_two_support_a2ui(filename: str, has_feels_like: bool) -> dict[str, Any]:
    registry = get_cardplan_registry()
    catalog = json.loads(_ASSETS.read_text(encoding="utf-8"))
    source = "resources/base/media/" + filename
    asset = next(item for item in catalog if item.get("src") == source)
    data: dict[str, Any] = {}
    bindings: list[dict[str, str]] = []
    groups: list[TemplateBusinessCandidates] = []
    required: dict[str, tuple[str, ...]] = {}
    for template_id in ("BatteryOverviewSupport@1", "WeatherOverviewTemperatureSupport@1"):
        definition = registry.require_template(template_id)
        sample = _build_data_schema(definition).get("data")
        assert isinstance(sample, dict)
        data.update(sample)
        capability_id = definition.capability_id
        business_id = definition.business_id
        domain = definition.data_domain
        assert capability_id is not None
        assert business_id is not None
        assert domain is not None
        bindings.append({"capabilityId": capability_id, "writeResultTo": domain})
        required[capability_id] = definition.required_data
        groups.append(TemplateBusinessCandidates(
            capabilityId=capability_id, businessId=business_id,
            explicitFields=definition.required_data,
            candidates=(TemplateSearchCandidate(
                templateId=template_id, coveredExplicitFields=definition.required_data,
            ),),
        ))
    weather = data.get("weather")
    assert isinstance(weather, dict)
    location = weather.get("location")
    current = weather.get("current")
    assert isinstance(location, dict)
    assert isinstance(current, dict)
    location["cityCode"] = {"type": "string", "sampleValue": "021"}
    if not has_feels_like:
        current.pop("feelsLikeC", None)
    task = TaskSpec(
        userQuery="展示手机电量与天气", size="2x2", dataModelSchema={"data": data},
        assetCandidates=[asset],
        eventCandidates=[EventAction(
            id="event.open.weather", call="clickToDeeplink",
            args={"uri": (
                "{{ 'hww://www.huawei.com/totemweather?enterType=share&cityCode=' "
                "+ ${/data/weather/location/cityCode} }}"
            )},
        )],
    )
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability=required,
        action_ids=("event.open.weather",),
    )
    search = TemplateSearchResult(cardSize="2x2", businessCandidates=tuple(groups))
    plans = plan_template_candidates(intent, search, task, registry)
    assert plans
    card_spec = {
        "title": "电量与天气", "description": "Image 着色回归",
        "suggestSize": "2x2", "dataBindings": bindings,
    }
    projection = build_ux_mixed_prompt(
        task_spec=task, card_spec=card_spec, scope=planner_scope(plans),
        component_candidates=planner_component_candidates(plans),
        required_template_groups=planner_required_template_groups(plans),
        template_plans=plans, registry=registry,
    )
    children: list[str] = []
    for slot in plans[0].business_slots:
        params = (
            {"conditionIcon": source, "actionId": "event.open.weather"}
            if slot.business_id == "WeatherOverview" else {}
        )
        children.append(f'Template("{slot.template_id}",{json.dumps(params)})')
    composition = 'Template("TwoSupportLayout@1",{},' + ",".join(children) + ");"
    result = compile_ux_layout_card(
        composition, task_spec=task, contract=projection.contract,
        protocol_profile=A2UIProtocolRegistry(A2UI_FORM_PROTOCOL_PROFILE_ID).get_profile(),
        registry=registry, card_spec=card_spec, enable_data_bindings=True,
    )
    return {
        "a2ui": [
            json.loads(line) for line in result.a2ui.splitlines() if line.strip()
        ],
    }


def _register_two_support_scenarios() -> None:
    for icon_slug, filename in _CONDITION_ICON_ASSETS:
        for feels_like_slug, has_feels_like in _FEELS_LIKE_STATES:
            def _build(
                filename: str = filename, has_feels_like: bool = has_feels_like,
            ) -> dict[str, Any]:
                return _render_two_support_a2ui(filename, has_feels_like)

            scenario(f"image_color__{icon_slug}__feelslike_{feels_like_slug}")(_build)


_register_two_support_scenarios()


_IMAGE_OPTION_CASES: tuple[tuple[str, str, dict[str, Any]], ...] = (
    ("theme_default", "theme", {}),
    ("theme_explicit_fill", "theme", {"fillColor": _EXPLICIT}),
    ("theme_explicit_fill_preserve_false", "theme",
     {"_preserveOriginalColor": False, "fillColor": _EXPLICIT}),
    ("theme_preserve_original", "theme", {"_preserveOriginalColor": True}),
    ("action_theme_default", "action", {}),
    ("action_explicit_fill", "action", {"fillColor": _EXPLICIT}),
    ("action_preserve_original", "action", {"_preserveOriginalColor": True}),
)


def _resolved_image_fill_color(family: str, options: dict[str, Any]) -> dict[str, Any]:
    """按着色选项解析 Image 最终 fillColor；options 为编译前的独立副本。"""
    if family == "theme":
        node = Nested2Node(
            "Image", ("resources/base/media/icon_weather1.svg", dict(options)), (),
        )
        contract = HybridBodyContract.model_construct(theme_profile_id="2x2-two-support")
        styled = _apply_theme_content_color(node, contract, get_cardplan_registry())
        cleaned = _strip_advanced_component_markers(styled)
        final_options = cleaned.values[-1]
    else:
        image = Nested2Node("Image", ("resources/base/media/icon_phone.svg", dict(options)), ())
        root = Nested2Node("IconAction", (), (
            Nested2Node("Stack", ({"onClick": [{"call": "open"}]},), (image,)),
        ))
        styled = _lower_action_template_tree(
            root, background="#FFFFFFFF", foreground="#FFABCDEF",
        )
        final_options = styled.children[0].values[-1]
    assert isinstance(final_options, dict)
    return {"options": options, "finalOptions": final_options}


@scenario("image_color__option_matrix")
def _build_option_matrix() -> dict[str, Any]:
    return {
        key: _resolved_image_fill_color(family, options)
        for key, family, options in _IMAGE_OPTION_CASES
    }


_LEGACY_ENTRY_ASSETS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("icon_weather_thermometer.svg", ("temperature",)),
    ("sun_max.svg", ("sun", "sunny")),
    ("rain.svg", ("cloud", "rain")),
)


def _legacy_weather_entry_final_options(
    filename: str, tags: tuple[str, ...],
) -> dict[str, Any]:
    registry = get_cardplan_registry()
    source = "resources/base/media/" + filename
    contract = HybridBodyContract.model_construct(
        theme_profile_id="2x2-two-support",
        allowed_business_component_ids=("WeatherOverview",),
        asset_semantic_tags_by_source={source: tags},
    )
    samples = {
        "city": "深圳", "temperature": "29°C", "condition": "多云",
        "airQuality": "良", "coldLevel": "低", "temperatureRange": "25° / 32°",
    }
    schema = {key: {"type": "string", "sampleValue": value} for key, value in samples.items()}
    task = TaskSpec(userQuery="天气", size="2x2", dataModelSchema=schema)
    call = ParsedCall(
        kind="component", name="WeatherOverview",
        values=({"role": "support", "conditionIcon": source},), children=(),
        span=SourceSpan(start=0, end=1),
    )
    root = _expand_weather_overview_call(
        call, task_spec=task, contract=contract, registry=registry, layout_id=None,
    )
    styled = _apply_theme_content_color(root, contract, registry)
    pending = [styled]
    images: list[Nested2Node] = []
    while pending:
        node = pending.pop()
        if node.component_type == "Image":
            images.append(node)
        pending.extend(node.children)
    assert len(images) == 1
    options = images[0].values[-1]
    assert isinstance(options, dict)
    return {"finalOptions": options}


@scenario("image_color__legacy_entry")
def _build_legacy_entry() -> dict[str, Any]:
    return {
        filename: _legacy_weather_entry_final_options(filename, tags)
        for filename, tags in _LEGACY_ENTRY_ASSETS
    }


@pytest.mark.parametrize("color", ('"#FF123456"', "$theme('supportContentColor')"))
@pytest.mark.parametrize("inherited", (False, True))
def test_template_rejects_original_color_and_explicit_fill(color: str, inherited: bool) -> None:
    source = _template_source('"_preserveOriginalColor": true, "fillColor": ' + color)
    if inherited:
        source = _template_source('"fillColor": ' + color).replace(
            "Column(", 'Column({"_preserveOriginalColor": true},',
        )
    with pytest.raises(ValueError, match="_preserveOriginalColor.*fillColor"):
        compile_card_template(
            source, provider_id="example.image", business_id=None,
            expected_wire_id="ImagePolicy@1", expected_capability_id=None,
            data_domain=None, description="Image 着色冲突", supported_card_sizes=("2x2",),
            primary_data=(), secondary_data=(), optional_data=(),
            output_schema={"type": "object", "properties": {}},
        )


@pytest.mark.parametrize("inherited", (False, True))
def test_runtime_rejects_conflicting_image_color_even_in_action(inherited: bool) -> None:
    image_options: dict[str, Any] = {"fillColor": _EXPLICIT}
    parent_options: dict[str, Any] = {"_boundTemplateAction": "event.open"}
    if inherited:
        parent_options["_preserveOriginalColor"] = True
    else:
        image_options["_preserveOriginalColor"] = True
    root = Nested2Node("Row", (parent_options,), (
        Nested2Node("Image", ("resources/base/media/icon_phone.svg", image_options), ()),
    ))
    contract = HybridBodyContract.model_construct(theme_profile_id="2x2-two-support")
    with pytest.raises(TerselConversionError, match="_preserveOriginalColor.*fillColor"):
        _apply_theme_content_color(root, contract, get_cardplan_registry())


@pytest.mark.parametrize("conflict", (False, True))
def test_action_image_inherits_original_color_protection(conflict: bool) -> None:
    options = {"fillColor": _EXPLICIT} if conflict else {}
    image = Nested2Node("Image", ("resources/base/media/icon_phone.svg", options), ())
    action_options = {"onClick": [{"call": "open"}], "_preserveOriginalColor": True}
    root = Nested2Node("IconAction", (), (Nested2Node("Stack", (action_options,), (image,)),))
    if conflict:
        with pytest.raises(TerselConversionError, match="_preserveOriginalColor.*fillColor"):
            _lower_action_template_tree(root, background="#FFFFFFFF", foreground="#FFABCDEF")
    else:
        styled = _lower_action_template_tree(
            root, background="#FFFFFFFF", foreground="#FFABCDEF",
        )
        final_options = styled.children[0].values[-1]
        assert isinstance(final_options, dict)
        assert "fillColor" not in final_options


def test_image_color_option_matrices_match_golden_scenarios() -> None:
    assert_golden_scenario("image_color__option_matrix")
    assert_golden_scenario("image_color__legacy_entry")


@pytest.mark.parametrize(("icon_slug", "filename"), _CONDITION_ICON_ASSETS)
@pytest.mark.parametrize(("feels_like_slug", "has_feels_like"), _FEELS_LIKE_STATES)
def test_two_support_final_a2ui_preserves_weather_template_fill(
    icon_slug: str, filename: str, feels_like_slug: str, has_feels_like: bool,
) -> None:
    assert_golden_scenario(f"image_color__{icon_slug}__feelslike_{feels_like_slug}")
