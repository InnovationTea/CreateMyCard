"""模板内部商用契约的回归测试。"""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

from models.generation import TaskSpec
from services.template_generation.engine.advanced.ux_mixed_prompt import (
    _weather_builtin_assets_for_components,
)
from services.template_generation.engine.cardplan.compiler import (
    _instantiate_blueprint,
    _validate_provider_template_layout_action_requirements,
)
from services.template_generation.engine.cardplan.models import (
    TEMPLATE_CHILD_SLOT_COMPONENT,
    SourceSpan,
    TemplateNode,
)
from services.template_generation.engine.cardplan.parser import ParsedCall, parse_hybrid_card
from services.template_generation.engine.cardplan.provider_bundle import compile_card_template
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.pipeline import (
    _prompt_size_summary,
    _task_spec_log_summary,
)
from services.template_generation.engine.tersel_converter import (
    Nested2Node,
    TerselConversionError,
)
from services.template_generation.model_client import _parse_json_object


def test_weather_builtin_assets_are_scoped_to_direct_weather_components() -> None:
    template_weather = SimpleNamespace(
        name="WeatherOverview",
        implementation="template",
    )
    direct_weather = SimpleNamespace(
        name="WeatherOverview",
        implementation="terse-dsl",
    )

    assert _weather_builtin_assets_for_components((template_weather,)) == ()
    assert _weather_builtin_assets_for_components((direct_weather,)) == (
        "resources/base/media/icon_weather1.svg",
        "resources/base/media/sun_max.svg",
        "resources/base/media/cold.svg",
    )


def test_second_layer_prompt_size_summary_does_not_log_prompt_content() -> None:
    messages = [
        {"role": "system", "content": "system-contract"},
        {"role": "user", "content": "private-dynamic-contract"},
    ]

    summary = _prompt_size_summary(messages)

    assert summary == {
        "messageCount": 2,
        "systemPromptChars": len("system-contract"),
        "userPromptChars": len("private-dynamic-contract"),
        "totalPromptChars": len("system-contractprivate-dynamic-contract"),
    }
    assert "private-dynamic-contract" not in str(summary)


def test_provider_compiler_rejects_deprecated_variant_syntax() -> None:
    legacy_source = """#Template(\"Legacy@1\", {\"capability\": \"LegacyCapability\"})
#Variant(\"2x2\", {})
Column(\"section\")
#EndVariant
#EndTemplate
"""

    with pytest.raises(ValueError, match="must use the cardtpl/1 UI syntax"):
        compile_card_template(
            legacy_source,
            provider_id="example.provider",
            business_id="Legacy",
            expected_wire_id="Legacy@1",
            expected_capability_id="LegacyCapability",
            data_domain="/data/legacy",
            description="legacy syntax must be rejected",
            supported_card_sizes=("2x2",),
            primary_data=(),
            secondary_data=(),
            optional_data=(),
            output_schema={"type": "object", "properties": {}},
        )


def test_provider_cardtpl_theme_references_are_resolved_deterministically() -> None:
    source = """#Template ThemeReference@1(props: {})
data = {
}

Column(
  {"backgroundColor": $theme('actionStyle.backgroundColor')},
  Text("主内容", {"fontColor": $theme('primaryColor')}),
  Text("辅助内容", {"fontColor": $theme('supportContentColor')}),
  Progress({"value": 50, "total": 100, "color": $theme('progressColor')})
)
#End
"""
    definition = compile_card_template(
        source,
        provider_id="example.theme",
        business_id=None,
        expected_wire_id="ThemeReference@1",
        expected_capability_id=None,
        data_domain=None,
        description="theme references",
        supported_card_sizes=(),
        primary_data=(),
        secondary_data=(),
        optional_data=(),
        output_schema={"type": "object", "properties": {}},
    )
    values = {
        "primaryColor": "#FFCCDDFF",
        "supportContentColor": "#99CCDDFF",
        "progressColor": "#FF445566",
        "actionStyle.backgroundColor": "#33FFFFFF",
        "actionStyle.contentColor": "#FFCCDDFF",
    }

    root = _instantiate_blueprint(
        definition.variants[0].root,
        {},
        theme_values=values,
    )

    assert root.values[-1]["backgroundColor"] == "#33FFFFFF"
    assert root.children[0].values[-1]["fontColor"] == "#FFCCDDFF"
    assert root.children[1].values[-1]["fontColor"] == "#99CCDDFF"
    assert root.children[2].values[-1]["color"] == "#FF445566"


def test_provider_cardtpl_rejects_unknown_theme_reference() -> None:
    source = """#Template InvalidThemeReference@1(props: {})
data = {
}
Column({"backgroundColor": $theme('unknownColor')})
#End
"""

    with pytest.raises(ValueError, match="approved Theme path"):
        compile_card_template(
            source,
            provider_id="example.theme",
            business_id=None,
            expected_wire_id="InvalidThemeReference@1",
            expected_capability_id=None,
            data_domain=None,
            description="invalid theme reference",
            supported_card_sizes=(),
            primary_data=(),
            secondary_data=(),
            optional_data=(),
            output_schema={"type": "object", "properties": {}},
        )


def test_provider_compiler_preserves_indexed_child_slots() -> None:
    source = """#Template HeroActionLayout@1(props: {}, ...children)
data = {
}

Column({
  "width": "matchParent",
  "height": "matchParent",
  "itemMargin": 8
},
  Column({
    "width": "matchParent",
    "layoutWeight": 1
  }, children[0]),
  Column({
    "width": "matchParent",
    "height": 36
  }, children[1])
)
#End
"""
    definition = compile_card_template(
        source,
        provider_id="example.layout",
        business_id=None,
        expected_wire_id="HeroActionLayout@1",
        expected_capability_id=None,
        data_domain=None,
        description="indexed child slots",
        supported_card_sizes=(),
        primary_data=(),
        secondary_data=(),
        optional_data=(),
        output_schema={"type": "object", "properties": {}},
    )
    root = definition.variants[0].root

    assert root.component == "Column"
    assert root.values[0].properties["itemMargin"].value == 8
    assert [child.children[0].component for child in root.children] == [
        TEMPLATE_CHILD_SLOT_COMPONENT,
        TEMPLATE_CHILD_SLOT_COMPONENT,
    ]

    hero = Nested2Node("Text", ("hero",), ())
    action = Nested2Node("Text", ("action",), ())
    instantiated = _instantiate_blueprint(
        root,
        {},
        spread_children=(hero, action),
    )
    assert instantiated.children[0].children == (hero,)
    assert instantiated.children[1].children == (action,)

    with pytest.raises(TerselConversionError, match=r"children\[1\]"):
        _instantiate_blueprint(root, {}, spread_children=(hero,))


def test_provider_cardtpl_sources_use_inline_styles_without_design_tokens() -> None:
    registry = get_cardplan_registry()

    def assert_inline_only(node: TemplateNode) -> None:
        component = node.component
        values = node.values
        if component in {"Column", "Row", "List", "Stack"}:
            has_design_token = (
                bool(values)
                and values[0].kind == "literal"
                and isinstance(values[0].value, str)
            )
            assert not has_design_token, component
        if component in {"Text", "Image", "Button"}:
            has_design_token = (
                len(values) > 1
                and values[1].kind == "literal"
                and isinstance(values[1].value, str)
            )
            assert not has_design_token, component
        for child in node.children:
            assert_inline_only(child)

    for definition in registry.templates.values():
        for variant in definition.variants:
            assert_inline_only(variant.root)


@pytest.mark.parametrize(
    ("body", "message"),
    (
        ("Column(children[0], children[0])", "indexes must be unique"),
        ("Column(children[1])", "indexes must be contiguous from zero"),
        ("Column(children, children[0])", "cannot mix children and children[index]"),
    ),
)
def test_provider_compiler_rejects_invalid_indexed_child_slots(
    body: str,
    message: str,
) -> None:
    source = f"""#Template HeroActionLayout@1(props: {{}}, ...children)
data = {{
}}

{body}
#End
"""
    with pytest.raises(ValueError, match=re.escape(message)):
        compile_card_template(
            source,
            provider_id="example.layout",
            business_id=None,
            expected_wire_id="HeroActionLayout@1",
            expected_capability_id=None,
            data_domain=None,
            description="invalid indexed child slots",
            supported_card_sizes=(),
            primary_data=(),
            secondary_data=(),
            optional_data=(),
            output_schema={"type": "object", "properties": {}},
        )


def _layout_child_slot_indexes(root: TemplateNode) -> list[int]:
    slot_indexes: list[int] = []
    pending = [root]
    while pending:
        node = pending.pop()
        if node.component == TEMPLATE_CHILD_SLOT_COMPONENT:
            slot_index = node.values[0].value
            assert isinstance(slot_index, int)
            slot_indexes.append(slot_index)
        pending.extend(reversed(node.children))
    return slot_indexes


def test_checked_in_layout_templates_use_concrete_container_blueprints() -> None:
    registry = get_cardplan_registry()
    fixed_slots = {
        "HeroActionLayout@1": 2,
        "FullIconActionLayout@1": 2,
        "CompactTwoActionLayout@1": 3,
        "TwoSupportLayout@1": 2,
    }
    variable_children = {
        "SingleFocusLayout@1",
        "WideSingleFocusLayout@1",
    }

    for template_id in (*fixed_slots, *variable_children):
        root = registry.require_template(template_id).variants[0].root
        assert root.component in {"Column", "Row", "Stack"}
        assert root.component not in {item.removesuffix("@1") for item in fixed_slots}
        options = root.values[0].properties
        assert options["width"].value == "matchParent"
        assert options["height"].value == "matchParent"

        slot_indexes = _layout_child_slot_indexes(root)
        if template_id in fixed_slots:
            assert slot_indexes == list(range(fixed_slots[template_id]))
            assert not root.spread_children
        else:
            assert slot_indexes == []
            assert root.spread_children


def test_fusion_theme_rules_cover_compact_eligible_businesses() -> None:
    registry = get_cardplan_registry(enable_fusion_ball=True)
    compact_business_ids: set[str] = set()
    for template_id, definition in registry.templates.items():
        if not template_id.endswith("Compact@1"):
            continue
        if not registry.template_is_enabled(template_id):
            continue
        business_id = definition.business_id
        if business_id is not None:
            compact_business_ids.add(business_id)

    for theme_id, theme in registry.themes.items():
        fusion_style = theme.fusion_ball_style
        if fusion_style is None:
            continue
        has_compact_business = bool(
            compact_business_ids.intersection(fusion_style.business_ids)
        )
        if not has_compact_business:
            continue
        first_layer_rule = registry.theme_first_layer_rules.get(theme_id)
        assert first_layer_rule is not None
        assert "Compact" in first_layer_rule, theme_id


def test_checked_in_action_templates_expose_second_layer_props() -> None:
    registry = get_cardplan_registry()
    pill = registry.require_template("PillAction@1")
    icon = registry.require_template("IconAction@1")

    pill_schema = pill.variants[0].parameters_schema
    icon_schema = icon.variants[0].parameters_schema
    assert pill.provider_id == "com.huawei.action.cli"
    assert pill_schema["required"] == ["actionId", "label"]
    assert set(pill_schema["properties"]) == {"actionId", "label", "icon"}
    assert icon_schema["required"] == ["actionId", "icon"]
    assert set(icon_schema["properties"]) == {"actionId", "icon"}
    for definition in (pill, icon):
        root = definition.variants[0].root
        assert root.component == "Stack"
        options = root.values[0].properties
        assert options["onClick"].kind == "event-action"
        assert options["onClick"].items[0].kind == "parameter"
        assert options["onClick"].items[0].name == "actionId"
        assert "_actionId" not in options


def test_support_template_exposes_optional_internal_action_prop() -> None:
    support = get_cardplan_registry().require_template(
        "WeatherOverviewTemperatureSupport@1"
    )
    variant = support.variants[0]
    schema = variant.parameters_schema

    assert schema["properties"]["actionId"]["type"] == "string"
    assert "actionId" not in schema["required"]
    action_options = variant.root.values[0].properties
    assert action_options["onClick"].kind == "event-action"
    assert action_options["onClick"].items[0].kind == "optional-parameter"
    assert action_options["onClick"].items[0].name == "actionId"


@pytest.mark.parametrize(
    ("params", "expected_event_name"),
    (
        ({"actionId": "event.open.weather"}, "event.open.weather"),
        ({}, None),
        ({"actionId": None}, None),
    ),
)
def test_optional_event_action_omits_on_click_without_action_id(
    params: dict[str, object],
    expected_event_name: str | None,
) -> None:
    source = """#Template OptionalAction@1(props: { actionId?: string })
data = {
}

Stack({
  "width": "matchParent",
  "onClick": EventAction(props?.actionId)
}, Text("动作", "body"))
#End
"""
    definition = compile_card_template(
        source,
        provider_id="example.action",
        business_id=None,
        expected_wire_id="OptionalAction@1",
        expected_capability_id=None,
        data_domain=None,
        description="optional EventAction",
        supported_card_sizes=(),
        primary_data=(),
        secondary_data=(),
        optional_data=(),
        output_schema={"type": "object", "properties": {}},
    )
    blueprint = definition.variants[0].root
    action_value = blueprint.values[0].properties["onClick"]

    assert action_value.kind == "event-action"
    assert action_value.items[0].kind == "optional-parameter"
    root = _instantiate_blueprint(blueprint, params)
    options = root.values[0]
    if expected_event_name is None:
        assert "onClick" not in options
    else:
        assert options["onClick"] == [
            {
                "call": "sendToAssistant",
                "args": {"eventName": expected_event_name},
            }
        ]


def test_optional_event_action_rejects_required_prop() -> None:
    source = """#Template InvalidOptionalAction@1(props: { actionId: string })
data = {
}

Stack({
  "onClick": EventAction(props?.actionId)
}, Text("动作", "body"))
#End
"""

    with pytest.raises(ValueError, match="requires an optional prop: actionId"):
        compile_card_template(
            source,
            provider_id="example.action",
            business_id=None,
            expected_wire_id="InvalidOptionalAction@1",
            expected_capability_id=None,
            data_domain=None,
            description="invalid optional EventAction",
            supported_card_sizes=(),
            primary_data=(),
            secondary_data=(),
            optional_data=(),
            output_schema={"type": "object", "properties": {}},
        )


@pytest.mark.parametrize(
    ("event_value", "message"),
    (
        ('EventAction("event.open.weather")', "requires one props parameter"),
        ("EventAction(props.actionId)", "must be the direct onClick option"),
    ),
)
def test_provider_compiler_rejects_invalid_event_action_usage(
    event_value: str,
    message: str,
) -> None:
    option_name = "onClick" if event_value.startswith('EventAction("') else "width"
    source = f"""#Template InvalidAction@1(props: {{ actionId: string }})
data = {{
}}

Stack({{
  "{option_name}": {event_value}
}}, Text("动作", "body"))
#End
"""
    with pytest.raises(ValueError, match=message):
        compile_card_template(
            source,
            provider_id="example.action",
            business_id=None,
            expected_wire_id="InvalidAction@1",
            expected_capability_id=None,
            data_domain=None,
            description="invalid EventAction",
            supported_card_sizes=(),
            primary_data=(),
            secondary_data=(),
            optional_data=(),
            output_schema={"type": "object", "properties": {}},
        )


def test_provider_template_layout_suffix_combinations_are_enforced() -> None:
    span = SourceSpan(start=0, end=1)

    def template(template_id: str) -> ParsedCall:
        return ParsedCall("template", template_id, ({},), (), span)

    def action(template_id: str, action_id: str) -> ParsedCall:
        return ParsedCall("template", template_id, ({"actionId": action_id},), (), span)

    pill_one = action("PillAction@1", "event.one")
    pill_two = action("PillAction@1", "event.two")
    icon = action("IconAction@1", "event.icon")

    _validate_provider_template_layout_action_requirements(
        "CompactTwoActionLayout",
        (template("WeatherOverviewCompact@1"),),
        (pill_one, pill_two),
        "2x2",
    )
    _validate_provider_template_layout_action_requirements(
        "TwoSupportLayout",
        (
            template("WeatherOverviewTemperatureSupport@1"),
            template("ResourceUsageOverviewSupport@1"),
        ),
        (),
        "2x2",
    )
    with pytest.raises(TerselConversionError, match="layout combination is invalid"):
        _validate_provider_template_layout_action_requirements(
            "TwoSupportLayout",
            (
                template("WeatherOverviewCompact@1"),
                template("BatteryOverviewCompact@1"),
            ),
            (),
            "2x2",
        )
    _validate_provider_template_layout_action_requirements(
        "HeroActionLayout",
        (template("BatteryOverviewHero@1"),),
        (pill_one,),
        "2x2",
    )
    _validate_provider_template_layout_action_requirements(
        "SingleFocusLayout",
        (template("WeatherOverviewFull@1"),),
        (),
        "2x2",
    )
    _validate_provider_template_layout_action_requirements(
        "FullIconActionLayout",
        (template("WeatherOverviewFull@1"),),
        (icon,),
        "2x2",
    )
    _validate_provider_template_layout_action_requirements(
        "WideSingleFocusLayout",
        (template("AppUsageOverviewWideHero@1"),),
        (pill_one,),
        "2x4",
    )
    _validate_provider_template_layout_action_requirements(
        "WideSingleFocusLayout",
        (template("AppUsageOverviewWideFull@1"),),
        (),
        "2x4",
    )

    with pytest.raises(TerselConversionError, match="Hero.*Action combination"):
        _validate_provider_template_layout_action_requirements(
            "HeroActionLayout",
            (template("BatteryOverviewHero@1"),),
            (),
            "2x2",
        )
    with pytest.raises(TerselConversionError, match="Full.*Action combination"):
        _validate_provider_template_layout_action_requirements(
            "SingleFocusLayout",
            (template("WeatherOverviewFull@1"),),
            (icon,),
            "2x2",
        )
    with pytest.raises(TerselConversionError, match="Wide marker"):
        _validate_provider_template_layout_action_requirements(
            "SingleFocusLayout",
            (template("AppUsageOverviewWideFull@1"),),
            (),
            "2x4",
        )
    with pytest.raises(TerselConversionError, match="suffix mismatches"):
        _validate_provider_template_layout_action_requirements(
            "WideSingleFocusLayout",
            (template("AppUsageOverviewFull@1"),),
            (),
            "2x4",
        )
    with pytest.raises(TerselConversionError, match="requires HeroActionLayout"):
        _validate_provider_template_layout_action_requirements(
            "SingleFocusLayout",
            (template("BatteryOverviewHero@1"),),
            (pill_one,),
            "2x2",
        )


def test_parser_rejects_deprecated_three_argument_template_call() -> None:
    source = (
        'Template("card@1",{},Column("section",'
        'Template("Legacy@1","2x2",{})));'
    )

    with pytest.raises(
        TerselConversionError,
        match="requires a versioned ID, one props object and optional children",
    ):
        parse_hybrid_card(source)


def test_task_spec_log_summary_omits_user_content_and_schema_details() -> None:
    task_spec = TaskSpec(
        userQuery="不应进入日志的用户原始请求",
        size="2x2",
        dataModelSchema={"privateDomain": {"secretField": "secretValue"}},
        eventCandidates=[],
        assetCandidates=[],
    )

    summary = _task_spec_log_summary(task_spec)

    assert summary == {
        "size": "2x2",
        "dataModelRootKeys": ["privateDomain"],
        "eventCandidateCount": 0,
        "assetCandidateCount": 0,
    }
    assert "用户原始请求" not in repr(summary)
    assert "secretField" not in repr(summary)
    assert "secretValue" not in repr(summary)


def test_model_response_json_extraction_uses_complete_outer_object() -> None:
    assert _parse_json_object('说明：{"decision":"use {trusted}"}。') == {
        "decision": "use {trusted}"
    }
