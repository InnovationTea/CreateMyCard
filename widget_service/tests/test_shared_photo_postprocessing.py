"""公共图集新增即生效，模板不重编译/调用模型，且与融合共用准入和绘制。"""

import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config.config import get_settings
from models.generation import TaskSpec
from services import post_layout_theme as themes
from services import post_layout_theme_registry as registry
from services.protocol_registry import A2UIProtocolRegistry
from services.template_generation.engine.cardplan.compiler import (
    HybridCompilation,
    _lower_action_template_tree,
    compile_ux_layout_card,
)
from services.template_generation.engine.cardplan.models import (
    ExpansionStats,
    HybridBodyContract,
    HybridLimits,
)
from services.template_generation.engine.cardplan.photo_facts import template_photo_facts
from services.template_generation.engine.cardplan.photo_selection import finalize_template_photo
from services.template_generation.engine.cardplan.photo_theme import collect_photo_style_context
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.tersel_converter import Nested2Node
from services.theme_photo_eligibility import fusion_photo_facts
from services.theme_photo_matching import eligible_photos, photo_reason
from services.theme_photo_processing import (
    PhotoStyleContext,
    apply_content_palette,
    apply_template_photo,
    register_photo_asset,
    template_foreground,
)
from services.theme_style_roles import is_role
from services.validator import ArtifactValidator
from test_holiday_weather_panel_photos import panels
from test_photo_asset_delivery import artifact
from test_uniform_photo_eligibility import PATHS, evidence, sample
from test_wide_photo_focus import focus_sample


def template_source(saved):
    records = themes.decode(saved.source)
    nodes = themes.components(records)
    roles = {}
    surfaces = set()
    for node in nodes:
        owned = {}
        for key, value in node.get("styles", {}).items():
            if is_role(value):
                owned[key] = value
        if owned:
            roles[node.get("id")] = owned
        if owned.get("backgroundColor") == "@theme:panel/1":
            surfaces.add(node.get("id"))
    base = next(item for item in registry.registered_themes("standard")
                if item.get("id") == "gradient-blue")
    content = base.get("content", {})
    apply_content_palette(
        nodes, content.get("roles", {}), content.get("panelBySize", {}).get(saved.task.get("size")),
        surface_style={}, legacy_panels=[],
    )
    root = next(node for node in nodes if node.get("id") == "root")
    root["id"] = "template_root"
    if "root" in roles:
        roles["template_root"] = roles.pop("root")
    nodes.insert(0, {"id": "root", "component": "Stack", "children": ["template_root"],
                     "styles": {"width": "matchParent", "height": "matchParent",
                                "backgroundColor": "#FFFFFFFF", "padding": 0}})
    return themes.encode(records), PhotoStyleContext(roles, frozenset(surfaces))


def finalize(saved, *, budget=256, source=None, ownership=None):
    converted, context = template_source(saved)
    original = HybridCompilation(
        "unchanged template source", "unchanged expanded source", source or converted,
        ExpansionStats(), photo_style_context=ownership or context,
    )
    contract = SimpleNamespace(
        theme_profile_id="original-theme", allowed_template_plans=(),
        limits=HybridLimits(max_raw_components=64, max_expanded_components=budget,
                            max_nesting_depth=32, vertical_budget_vp=1000),
    )
    # 没有映射、没有已登记 photo_themes，也不提供任何模型客户端。
    result, identity = finalize_template_photo(
        original, task_spec=TaskSpec.model_validate(saved.task), contract=contract,
        registry=SimpleNamespace(photo_themes={}), compile_options={"business_title": "状态"},
    )
    return original, result, identity


def only_photo(monkeypatch, identity, *, new_id=None):
    config = registry.load_theme_registry()
    selected = next(item for item in config.get("themes", []) if item.get("id") == identity)
    if new_id:
        selected = copy.deepcopy(selected)
        selected["id"] = new_id
        selected["name"] = "公共图集新增素材"
        selected["background"]["src"] = "resources/base/media/bg_new_shared_photo.jpg"
        selected["background"]["remoteUrl"] = (
            "https://lfcontentcenterdev.hwcloudtest.cn/new-shared-photo.jpg"
        )
    for item in config.get("themes", []):
        if item.get("kind") == "photo":
            item["enabled"] = False
    selected["enabled"] = True
    if new_id:
        config["themes"].append(selected)
    registry.validate_registry(config)
    monkeypatch.setattr(registry, "load_theme_registry", lambda: copy.deepcopy(config))
    monkeypatch.setattr(get_settings(), "enable_photo_background_theme", True)
    return next(item for item in registry.registered_themes()
                if item.get("id") == selected.get("id"))


def test_adding_one_public_photo_config_works_for_both_routes_without_template_mapping(monkeypatch):
    photo = only_photo(monkeypatch, "photo-ux-wave-square", new_id="photo-new-shared-weather")
    saved = sample(PATHS.get("weather"), 3, button=False)
    original, delivered, identity = finalize(saved)
    facts = fusion_photo_facts(saved.task, evidence(saved), saved.compact)
    candidates, _ = eligible_photos(facts)
    assert [item.get("id") for item in candidates] == [photo.get("id")]
    assert identity == photo.get("id")
    assert template_foreground(delivered.a2ui) == template_foreground(original.a2ui)
    assert delivered.raw_output == original.raw_output
    assert delivered.effective_output == original.effective_output
    image = next(node for node in themes.components(themes.decode(delivered.a2ui))
                 if node.get("id") == "__post_theme_base")
    assert image.get("src") == photo.get("remoteUrl")
    assert not original.a2ui == delivered.a2ui
    assert "_templateTheme" not in delivered.a2ui
    document = artifact()
    document.genui = delivered.a2ui
    registered = register_photo_asset(document)
    candidates = registered.taskSpec.get("assetCandidates", [])
    assert any(item.get("id") == identity for item in candidates)
    assert identity in registered.effectiveCapabilities.get("asset", [])


@pytest.mark.parametrize("business", ["weather", "sleep", "sport", "battery", "calendar"])
@pytest.mark.parametrize("lines", [2, 3, 4])
def test_both_adapters_enforce_the_same_square_business_and_line_rules(business, lines):
    saved = sample(PATHS.get(business), lines, button=False)
    source, _ = template_source(saved)
    template_facts = template_photo_facts(source, saved.task, "状态")
    fusion_facts = fusion_photo_facts(saved.task, evidence(saved), saved.compact)
    for photo in registry.registered_themes("photos"):
        if photo.get("size") != "2x2":
            continue
        assert (photo_reason(photo, template_facts) is None) == (
            photo_reason(photo, fusion_facts) is None
        ), photo.get("id")


@pytest.mark.parametrize("state", ["disabled", "no-photos", "over-budget", "missing-binding"])
def test_template_fallback_retains_the_original_document(monkeypatch, state):
    only_photo(monkeypatch, "photo-ux-wave-square")
    saved = sample(PATHS.get("weather"), 3, button=False)
    source, ownership = template_source(saved)
    budget = 1 if state == "over-budget" else 256
    if state == "disabled":
        monkeypatch.setattr(get_settings(), "enable_photo_background_theme", False)
    elif state == "no-photos":
        saved = sample(PATHS.get("weather"), 4, button=False)
        source, ownership = template_source(saved)
    elif state == "missing-binding":
        records = themes.decode(source)
        records[-1]["updateDataModel"]["value"] = {}
        source = themes.encode(records)
    original, result, identity = finalize(saved, budget=budget, source=source, ownership=ownership)
    assert result is original
    assert result.a2ui == source
    assert identity == "original-theme"


@pytest.mark.parametrize("icon", ["resources/base/media/ic_weather_color.svg",
                                  "https://assets.example.test/color-cloud.svg"])
def test_visible_excluded_icon_blocks_every_template_photo_pool(monkeypatch, icon):
    only_photo(monkeypatch, "photo-ux-wave-square")
    monkeypatch.setattr(get_settings(), "asset_src_url_mapping", {
        "resources/base/media/ic_weather_color.svg": "https://assets.example.test/color-cloud.svg",
    })
    saved = sample(PATHS.get("weather"), 2, button=False)
    source, ownership = template_source(saved)
    records = themes.decode(source)
    nodes = themes.components(records)
    next(node for node in nodes if node.get("id") == "template_root")["children"].append("cloud")
    nodes.append({"id": "cloud", "component": "Image", "src": icon,
                  "styles": {"width": 20, "height": 20}})
    source = themes.encode(records)
    original, result, _ = finalize(saved, source=source, ownership=ownership)
    assert result is original


@pytest.mark.parametrize("photo_id", ["photo-ux-wave-square", "photo-ux-meeting-room-square"])
def test_shared_application_keeps_explicit_icon_color_and_root_while_using_registered_ink(photo_id):
    saved = sample(PATHS.get("weather"), 2, button=False)
    source, ownership = template_source(saved)
    records = themes.decode(source)
    nodes = themes.components(records)
    next(node for node in nodes if node.get("id") == "template_root")["children"].append("art")
    nodes.append({"id": "art", "component": "Image", "src": "resources/base/media/art.svg",
                  "styles": {"fillColor": "#FF123456", "width": 20, "height": 20}})
    source = themes.encode(records)
    photo = next(item for item in registry.registered_themes(include_disabled=True)
                 if item.get("id") == photo_id)
    result = apply_template_photo(source, photo, saved.task, ownership)
    after = themes.components(themes.decode(result))
    art = next(node for node in after if node.get("id") == "art")
    assert art.get("styles", {}).get("fillColor") == "#FF123456"
    reading = next(node for node in after if node.get("id") == "reading")
    primary = photo.get("content", {}).get("roles", {}).get("primary")
    assert reading.get("styles", {}).get("fontColor") == primary
    root = next(node for node in after if node.get("id") == "root")
    assert "template_root" in root.get("children", [])
    assert template_foreground(source) == template_foreground(result)


@pytest.mark.parametrize("layout", ["left", "right"])
@pytest.mark.parametrize("business", ["weather", "sleep", "calendar", "countdown"])
@pytest.mark.parametrize("lines", [2, 4, 5])
def test_wide_focus_adapters_share_business_direction_and_line_gates(layout, business, lines):
    saved = focus_sample(business, lines, layout)
    source, _ = template_source(saved)
    actual = template_photo_facts(source, saved.task, "状态")
    expected = fusion_photo_facts(saved.task, evidence(saved), saved.compact)
    for photo in registry.registered_themes("photos"):
        if photo.get("size") == "2x4":
            assert (photo_reason(photo, actual) is None) == (
                photo_reason(photo, expected) is None
            ), (photo.get("id"), photo_reason(photo, actual), photo_reason(photo, expected))


@pytest.mark.parametrize("layout", ["W-split-panels", "W-four-slots"])
def test_shared_special_weather_panel_rule_is_not_filtered_out_by_template_kind(layout):
    saved = panels(layout)
    source, _ = template_source(saved)
    actual = template_photo_facts(source, saved.task)
    expected = fusion_photo_facts(saved.task, evidence(saved), saved.compact)
    photo = next(item for item in registry.registered_themes()
                 if item.get("id") == "photo-ux-ice-wide")
    assert photo_reason(photo, expected) is None
    assert photo_reason(photo, actual) is None


def test_real_template_uses_new_public_photo_without_mapping_or_theme_model(monkeypatch):
    original_registry = get_cardplan_registry()
    assert original_registry.photo_themes == {}
    photo = only_photo(monkeypatch, "photo-ux-wave-square", new_id="photo-new-real-template")
    model = AsyncMock(side_effect=AssertionError("模板图片不应调用融合主题模型"))
    monkeypatch.setattr(themes, "select_theme", model)
    schema = {"data": {"weather": {"current": {
        "condition": {"type": "string", "sampleValue": "多云"},
    }}}}
    task = TaskSpec(userQuery="显示天气", size="2x2", appVersion="11.7.7.331",
                    dataModelSchema=schema)
    contract = HybridBodyContract(
        theme_profile_id="family-weather-care-blue", allowed_components=(
            "Column", "Row", "Stack", "Text", "Image", "Button", "Progress", "Divider", "Checkbox",
        ), allowed_design_tokens=(),
        allowed_layout_tokens=(), allowed_template_ids=(
            "SingleFocusLayout@1", "WeatherOverviewConditionFeelsLikeAlertFull@1",
        ), allowed_asset_sources=(), trusted_literals=("天气",), trusted_numbers=(),
        required_literals=(), protected_literals=(),
        allowed_layout_component_ids=("SingleFocusLayout",),
        allowed_business_component_ids=("WeatherOverview",),
        limits=HybridLimits(max_raw_components=64, max_expanded_components=256,
                            max_nesting_depth=16, vertical_budget_vp=140),
    )
    card = {"title": "天气", "description": "天气", "suggestSize": "2x2", "dataBindings": [
        {"capabilityId": "ViewWeather", "writeResultTo": "/data/weather",
         "arguments": {"city": "南京"}},
    ]}
    profile = A2UIProtocolRegistry("a2ui-form-rom6.0-v1").get_profile()
    compiled = compile_ux_layout_card(
        'Template("SingleFocusLayout@1", {}, '
        'Template("WeatherOverviewConditionFeelsLikeAlertFull@1", {}));',
        task_spec=task, contract=contract, registry=original_registry, protocol_profile=profile,
        business_title="天气", card_spec=card, enable_data_bindings=True,
    )
    result, identity = finalize_template_photo(
        compiled, task_spec=task, contract=contract, registry=original_registry,
        compile_options={"business_title": "天气"},
    )
    assert identity == photo.get("id")
    assert result is not compiled
    model.assert_not_awaited()
    assert template_foreground(result.a2ui) == template_foreground(compiled.a2ui)
    assert compiled.photo_style_context is not None
    before = {node.get("id"): node for node in themes.components(themes.decode(compiled.a2ui))}
    after = {node.get("id"): node for node in themes.components(themes.decode(result.a2ui))}
    for identity, owned in compiled.photo_style_context.roles.items():
        if "fontColor" in owned:
            node = after.get(identity)
            assert node is not None
            assert node.get("styles", {}).get("fontColor", "")[3:] == "FFFFFF"
    for node in after.values():
        if node.get("component") == "Text":
            assert node.get("styles", {}).get("fontColor", "")[3:] == "FFFFFF", node
    assert "_templateTheme" not in result.a2ui
    assert set(before).issubset(after)
    document = artifact()
    document.genui = result.a2ui
    document.cardSpec = card
    document.taskSpec = task.model_dump(mode="json")
    document.effectiveCapabilities["data"] = ["ViewWeather"]
    document = register_photo_asset(document)
    assert ArtifactValidator({}).validate(document, profile) == []


@pytest.mark.parametrize("business,photo_id", [
    ("weather", "photo-ux-mountain-sunset-lake-wide"), ("calendar", "photo-ux-digital-wave-wide"),
    ("countdown", "photo-ux-gradient-wide"),
])
@pytest.mark.parametrize("lines", [2, 4, 5])
def test_template_top_bottom_main_focus_keeps_shared_line_gate(business, photo_id, lines):
    saved = focus_sample(business, lines, "left")
    source, _ = template_source(saved)
    records = themes.decode(source)
    nodes = themes.components(records)
    root = next(node for node in nodes if node.get("id") == "template_root")
    root["component"] = "Column"
    root_children = root.get("children", [])
    assert len(root_children) == 2
    support = next(node for node in nodes if node.get("id") == root_children[1])
    support["component"] = "Row"
    facts = template_photo_facts(themes.encode(records), saved.task, "状态")
    photo = next(item for item in registry.registered_themes(include_disabled=True)
                 if item.get("id") == photo_id)
    assert (photo_reason(photo, facts) is None) is (lines <= 4)
    assert "side-focus" not in facts.scopes
    assert "left-main-dual" not in facts.scopes


@pytest.mark.parametrize("kind,alignment,full_width,left,top", [
    ("Stack", {"alignContent": "topStart"}, False, True, True),
    ("Stack", {"alignContent": "center"}, False, False, False),
    ("Stack", {"alignContent": "bottomEnd"}, False, False, False),
    ("Stack", {"alignContent": "center"}, True, True, False),
    ("Column", {"alignItems": "end"}, False, False, True),
    ("Column", {"justifyContent": "center"}, False, True, False),
    ("Row", {"justifyContent": "end", "alignItems": "top"}, False, False, True),
])
def test_outer_alignment_remains_part_of_template_photo_facts(
    kind, alignment, full_width, left, top,
):
    saved = sample(PATHS.get("weather"), 1, button=False)
    source, _ = template_source(saved)
    records = themes.decode(source)
    nodes = themes.components(records)
    content = next(node for node in nodes if node.get("id") == "template_root")
    content["id"] = "weather_content"
    content["styles"].pop("width", None)
    content["styles"].pop("height", None)
    if full_width:
        content["styles"]["width"] = "matchParent"
    nodes.append({"id": "template_root", "component": kind, "children": ["weather_content"],
                  "styles": {"width": "matchParent", "height": "matchParent", **alignment}})
    facts = template_photo_facts(themes.encode(records), saved.task, "状态")
    card = facts.scopes.get("card")
    assert card is not None
    assert card.body_flow.get("leftAligned") is left
    assert facts.top_content.get("topOnly") is top
    photo = next(item for item in registry.registered_themes(include_disabled=True)
                 if item.get("id") == "photo-ux-clouds-weather-square")
    assert (photo_reason(photo, facts) is None) is (left and top)


@pytest.mark.parametrize("business,photo_id", [
    ("weather", "photo-ux-mountain-sunset-lake-wide"), ("calendar", "photo-ux-digital-wave-wide"),
    ("countdown", "photo-ux-gradient-wide"),
])
@pytest.mark.parametrize("variant", ["continuous", "bottom-details", "equal"])
@pytest.mark.parametrize("title", [False, True])
@pytest.mark.parametrize("lines", [2, 4, 5])
def test_compiled_top_bottom_layout_matches_fusion_main_scope(
    business, photo_id, variant, title, lines,
):
    saved = focus_sample(business, lines, "top", variant, title)
    source, _ = template_source(saved)
    facts = template_photo_facts(source, saved.task, "顶部标题")
    expected = fusion_photo_facts(saved.task, evidence(saved), saved.compact)
    photo = next(item for item in registry.registered_themes(include_disabled=True)
                 if item.get("id") == photo_id)
    assert photo_reason(photo, facts) == photo_reason(photo, expected)
    assert "main-focus" in facts.scopes
    assert "side-focus" not in facts.scopes
    assert "left-main-dual" not in facts.scopes


@pytest.mark.parametrize("support_panels", [False, True])
def test_top_bottom_main_focus_does_not_require_two_auxiliary_panels(support_panels):
    saved = focus_sample("weather", 2, "left")
    source, _ = template_source(saved)
    records = themes.decode(source)
    nodes = themes.components(records)
    root = next(node for node in nodes if node.get("id") == "template_root")
    root["component"] = "Column"
    children = root.get("children", [])
    assert len(children) == 2
    support = next(node for node in nodes if node.get("id") == children[1])
    support["component"] = "Row"
    if not support_panels:
        for node in nodes:
            node.get("styles", {}).pop("backgroundColor", None)
    facts = template_photo_facts(themes.encode(records), saved.task, "状态")
    assert "main-focus" in facts.scopes
    assert "side-focus" not in facts.scopes


@pytest.mark.parametrize("alignment", ["center", "bottomEnd"])
def test_full_size_child_keeps_equivalent_outer_alignment(alignment):
    saved = sample(PATHS.get("weather"), 1, button=False)
    source, _ = template_source(saved)
    records = themes.decode(source)
    nodes = themes.components(records)
    content = next(node for node in nodes if node.get("id") == "template_root")
    content["id"] = "weather_content"
    nodes.append({"id": "template_root", "component": "Stack", "children": ["weather_content"],
                  "styles": {"width": "matchParent", "height": "matchParent",
                             "alignContent": alignment}})
    facts = template_photo_facts(themes.encode(records), saved.task, "状态")
    card = facts.scopes.get("card")
    assert card is not None
    assert card.body_flow.get("leftAligned") is True
    assert facts.top_content.get("topOnly") is True


@pytest.mark.parametrize("layout", ["side-without-panels", "ambiguous-top-bottom"])
def test_main_scope_keeps_side_panel_and_unambiguous_focus_requirements(layout):
    saved = focus_sample("weather", 2, "left")
    source, _ = template_source(saved)
    records = themes.decode(source)
    nodes = themes.components(records)
    root = next(node for node in nodes if node.get("id") == "template_root")
    children = root.get("children", [])
    assert len(children) == 2
    support = next(node for node in nodes if node.get("id") == children[1])
    for node in nodes:
        node.get("styles", {}).pop("backgroundColor", None)
    if layout == "ambiguous-top-bottom":
        root["component"] = "Column"
        support["component"] = "Row"
        main = next(node for node in nodes if node.get("id") == children[0])
        main["component"] = "Row"
    facts = template_photo_facts(themes.encode(records), saved.task, "状态")
    assert "main-focus" not in facts.scopes
    assert "side-focus" not in facts.scopes
    assert "left-main-dual" not in facts.scopes


@pytest.mark.parametrize("explicit", [None, "#FF123456"])
def test_compiler_records_auto_action_icon_ink_but_protects_explicit_ink(explicit):
    options = {} if explicit is None else {"fillColor": explicit}
    image = Nested2Node("Image", ("resources/base/media/clock.svg", options), ())
    content = Nested2Node("Stack", ({"onClick": [{"call": "open"}]},), (image,))
    action = Nested2Node("IconAction", (), (content,))
    lowered = _lower_action_template_tree(
        action, background="#FFFFFFFF", foreground="#FF123456",
    )
    shell = Nested2Node("Column", ({},), (lowered,))
    context = collect_photo_style_context(shell)
    assert context.button_ids == frozenset({"__genui_render_component__root_1"})
    owned = context.roles.get("root_1_0", {})
    assert (owned.get("fillColor") == "@theme:primary/1") is (explicit is None)
