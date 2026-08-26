"""模板内部商用契约的回归测试。"""

from __future__ import annotations

import re

import pytest

from models.generation import TaskSpec
from services.template_generation.engine.cardplan.compiler import (
    _instantiate_blueprint,
    _validate_provider_template_layout_action_requirements,
)
from services.template_generation.engine.cardplan.models import (
    TEMPLATE_CHILD_SLOT_COMPONENT,
    SourceSpan,
)
from services.template_generation.engine.cardplan.parser import ParsedCall, parse_hybrid_card
from services.template_generation.engine.cardplan.provider_bundle import compile_card_template
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.pipeline import _task_spec_log_summary
from services.template_generation.engine.terse_dsl_nested2_converter import (
    Nested2Node,
    TerseDslNested2ConversionError,
)
from services.template_generation.model_client import _parse_json_object


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

    with pytest.raises(TerseDslNested2ConversionError, match=r"children\[1\]"):
        _instantiate_blueprint(root, {}, spread_children=(hero,))


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


def test_checked_in_layout_templates_use_concrete_container_blueprints() -> None:
    registry = get_cardplan_registry()
    fixed_slots = {
        "HeroActionLayout@1": 2,
        "HeroSupportLayout@1": 2,
        "HeroSupportActionLayout@1": 3,
    }
    variable_children = {
        "SingleFocusLayout@1",
        "PeerPairLayout@1",
        "SequentialSummaryLayout@1",
        "EqualItemsLayout@1",
        "ListActionLayout@1",
        "ActionMatrixLayout@1",
        "WeatherNowForecastLayout@1",
    }

    for template_id in (*fixed_slots, *variable_children):
        root = registry.require_template(template_id).variants[0].root
        assert root.component in {"Column", "Row", "Stack"}
        assert root.component not in {item.removesuffix("@1") for item in fixed_slots}
        options = root.values[0].properties
        assert options["width"].value == "matchParent"
        assert options["height"].value == "matchParent"

        slot_indexes = [
            child.children[0].values[0].value
            for child in root.children
            if child.children
            and child.children[0].component == TEMPLATE_CHILD_SLOT_COMPONENT
        ]
        if template_id in fixed_slots:
            assert slot_indexes == list(range(fixed_slots[template_id]))
            assert not root.spread_children
        else:
            assert slot_indexes == []
            assert root.spread_children


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
    assert pill.variants[0].root.component == "Stack"
    assert icon.variants[0].root.component == "Stack"


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
        (template("WeatherOverviewCompact@1"),),
        (pill_one, pill_two),
        "2x2",
    )
    _validate_provider_template_layout_action_requirements(
        (template("WeatherOverviewCompact@1"), template("BatteryOverviewNormalCompact@1")),
        (),
        "2x2",
    )
    _validate_provider_template_layout_action_requirements(
        (template("BatteryOverviewNormalHero@1"),),
        (pill_one,),
        "2x2",
    )
    _validate_provider_template_layout_action_requirements(
        (template("WeatherOverviewFull@1"),),
        (icon,),
        "2x2",
    )
    _validate_provider_template_layout_action_requirements(
        (template("AppUsageOverviewWideHero@1"),),
        (pill_one,),
        "2x4",
    )
    _validate_provider_template_layout_action_requirements(
        (template("AppUsageOverviewWideFull@1"),),
        (),
        "2x4",
    )

    with pytest.raises(TerseDslNested2ConversionError, match="Hero.*Action combination"):
        _validate_provider_template_layout_action_requirements(
            (template("BatteryOverviewNormalHero@1"),),
            (),
            "2x2",
        )
    with pytest.raises(TerseDslNested2ConversionError, match="only accepts one IconAction"):
        _validate_provider_template_layout_action_requirements(
            (template("WeatherOverviewFull@1"),),
            (pill_one,),
            "2x2",
        )


def test_parser_rejects_deprecated_three_argument_template_call() -> None:
    source = (
        'Template("card@1",{},Column("section",'
        'Template("Legacy@1","2x2",{})));'
    )

    with pytest.raises(
        TerseDslNested2ConversionError,
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
