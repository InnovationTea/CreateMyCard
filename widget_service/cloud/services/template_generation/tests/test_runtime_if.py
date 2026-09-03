"""Provider 运行时 IF 经模板、Compact 公共处理链及 A2UI 校验的回归。"""

from __future__ import annotations

import json
from typing import Any

import pytest

from models.generation import CandidateDataBinding, TaskSpec
from services.a2ui_runtime_if import validate_runtime_if, validate_runtime_if_graph
from services.card_validation import validate_card
from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    convert_compact_dsl_to_a2ui,
)
from services.generation_pipeline import (
    DslProcessingContext,
    DslProcessorKind,
    get_dsl_processor,
)
from services.protocol_registry import A2UIProtocolRegistry
from services.template_generation.engine.advanced.ux_mixed_prompt import build_ux_mixed_prompt
from services.template_generation.engine.cardplan.compiler import (
    _estimate_height,
    _instantiate_blueprint,
    _serialize_node,
    compile_ux_layout_card,
)
from services.template_generation.engine.cardplan.provider_bundle import compile_card_template
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.cardplan.retrieval_index import (
    build_template_variant_search_records,
)
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateRetrievalQuery,
    retrieve_template_variants,
)
from services.template_generation.engine.tersel_converter import (
    Nested2Node,
    TerselConversionError,
    convert_tersel_to_a2ui,
)
from services.template_generation.source_adapter import prepare_template_source_dsl


def _definition(body: str, *, optional: bool = False):
    binding = "$optionalPath" if optional else "$path"
    source = (
        "#Template CalendarConditionFull@1(props: {})\n"
        f'data = {{ eventCont: {binding}("/eventCount") }}\n'
        f"Column({body})\n#End\n"
    )
    return compile_card_template(
        source,
        provider_id="example.calendar",
        business_id="CalendarCondition",
        expected_wire_id="CalendarConditionFull@1",
        expected_capability_id="GetCalendarEvents",
        data_domain="/data/calendar",
        description="日程状态分支",
        supported_card_sizes=("2x2",),
        primary_data=() if optional else ("/eventCount",),
        secondary_data=(),
        optional_data=("/eventCount",) if optional else (),
        output_schema={
            "type": "object",
            "properties": {"eventCount": {"type": "integer"}},
        },
    )


def _task(sample: Any = 0) -> dict[str, Any]:
    return {
        "userQuery": "日程状态",
        "appVersion": "11.7.5.206",
        "size": "2x2",
        "eventCandidates": [],
        "assetCandidates": [],
        "dataModelSchema": {
            "data": {
                "calendar": {"eventCount": {"type": "integer", "sampleValue": sample}},
            },
        },
    }


def _components(a2ui: str) -> list[dict[str, Any]]:
    message = json.loads(a2ui.splitlines()[1])
    update = message.get("updateComponents")
    assert isinstance(update, dict)
    components = update.get("components")
    assert isinstance(components, list)
    return components


def _compile(body: str, sample: Any = 0) -> str:
    definition = _definition(body)
    root = _instantiate_blueprint(
        definition.variants[0].root,
        {},
        {"eventCont": "${data.calendar.eventCount}"},
    )
    return convert_tersel_to_a2ui(
        _serialize_node(root),
        size="2x2",
        protocol_profile=A2UIProtocolRegistry().get_profile(),
        task_spec=_task(sample),
    )


@pytest.mark.parametrize("sample", [0, 1, None, ""])
def test_runtime_if_keeps_both_branches_through_public_processor(sample: Any) -> None:
    profile = A2UIProtocolRegistry().get_profile()
    a2ui = _compile("IF(data.eventCont, Text('true'), Text('false'))", sample)
    components = _components(a2ui)
    condition = components[1]
    assert condition == {
        "id": "root_0",
        "component": "If",
        "condition": "{{ ${/data/calendar/eventCount} }}",
        "childrenIf": ["root_0_0"],
        "childrenElse": ["root_0_1"],
    }
    assert [node.get("content") for node in components[2:]] == ["true", "false"]
    source = prepare_template_source_dsl(
        a2ui,
        processor_kind=DslProcessorKind.DESIGN_COMPACT,
        size="2x2",
        protocol_profile=profile,
    )
    if_row = json.loads(source.splitlines()[1])
    assert len(if_row) == 3
    context = DslProcessingContext(
        size="2x2",
        card_spec={"title": "日程", "description": "日程状态", "suggestSize": "2x2"},
        task_spec=_task(sample),
        protocol_profile=profile,
        design_profile_id="design-compact-dsl",
    )
    result = get_dsl_processor(DslProcessorKind.DESIGN_COMPACT).process(source, context)
    assert not result.errors
    assert _components(result.standard_dsl)[1] == condition
    report = validate_card(dsl_text=result.standard_dsl, cardspec=context.card_spec)
    assert not [item for item in report.diagnostics if item.severity == "error"]


def test_runtime_if_supports_expression_nested_and_omitted_else() -> None:
    a2ui = _compile(
        "IF(Expr(`${data.eventCont} > 0`), "
        "IF(data.eventCont, Text('true')), Column(Text('false')))"
    )
    conditions = [node for node in _components(a2ui) if node.get("component") == "If"]
    assert len(conditions) == 2
    assert conditions[0].get("condition") == "{{ ${/data/calendar/eventCount} > 0 }}"
    assert conditions[1].get("childrenElse") == []


def test_generation_if_still_guards_optional_runtime_binding() -> None:
    body = "\n#if data.eventCont\nIF(data.eventCont, Text('true'), Text('false'))\n#endif\n"
    definition = _definition(body, optional=True)
    blueprint = definition.variants[0].root
    missing = _instantiate_blueprint(blueprint, {}, {})
    assert missing.children == ()
    present = _instantiate_blueprint(blueprint, {}, {"eventCont": "${data.calendar.eventCount}"})
    assert present.children[0].component_type == "If"
    assert len(present.children[0].children) == 2
    with pytest.raises(ValueError, match="optional Bind"):
        _definition("IF(data.eventCont, Text('true'), Text('false'))", optional=True)


@pytest.mark.parametrize(
    "body",
    [
        "IF(data.eventCont)",
        "IF(data.eventCont, Text('a'), Text('b'), Text('c'))",
        "IF(true, Text('a'), Text('b'))",
        "IF(props.eventCont, Text('a'), Text('b'))",
        "IF(data.eventCont, 'not a component', Text('b'))",
        "IF(data.eventCont, children, Text('b'))",
        "IF(data.eventCont, children[0], Text('b'))",
        "IF(data.eventCont, Text('a'), fallback=Text('b'))",
        "IF(data.unknown, Text('a'), Text('b'))",
        "IF(data.eventCont, Text(data.unknown), Text('b'))",
        "IF(data.eventCont, Text('a'), Text(data.unknown))",
    ],
)
def test_runtime_if_rejects_invalid_template_inputs(body: str) -> None:
    with pytest.raises(ValueError):
        _definition(body)


def test_runtime_if_rejects_unknown_expression_paths() -> None:
    with pytest.raises(TerselConversionError, match="outside TaskSpec"):
        convert_tersel_to_a2ui(
            'Column(If("{{ ${/data/unknown} }}",Text("true"),Text("false")))',
            size="2x2",
            protocol_profile=A2UIProtocolRegistry().get_profile(),
            task_spec=_task(),
        )


@pytest.mark.parametrize(
    "props",
    [
        {},
        {"condition": True},
        {"condition": {"path": "/data/calendar/eventCount"}},
        {"condition": "data.eventCont"},
        {"condition": "{{ }}"},
        {"condition": "{{ true }}", "styles": {}},
        {"condition": "{{ true }}", "onClick": []},
        {"condition": "{{ true }}", "accessibility": "label"},
        {"condition": "{{ true }}", "children": []},
        {"condition": "{{ true }}", "childrenIf": None},
        {"condition": "{{ true }}", "childrenIf": "true"},
        {"condition": "{{ true }}", "childrenElse": [1]},
        {"condition": "{{ true }}", "childrenIf": ["{{ true }}"]},
    ],
)
def test_runtime_if_contract_rejects_invalid_properties(props: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        validate_runtime_if(props)
    source = '\n'.join([
        '["root","Column",{},["if"]]',
        json.dumps(["if", "If", props]),
    ])
    with pytest.raises(CompactDslConversionError):
        convert_compact_dsl_to_a2ui(source, size="2x2")


@pytest.mark.parametrize("target", ["missing", "if", "root"])
def test_runtime_if_rejects_missing_and_cyclic_branches(target: str) -> None:
    components = [
        {"id": "root", "component": "Column", "children": ["if"]},
        {"id": "if", "component": "If", "condition": "{{ true }}", "childrenIf": [target]},
    ]
    with pytest.raises(ValueError):
        validate_runtime_if_graph(components)


def test_a2ui_if_references_are_checked_in_false_branch() -> None:
    a2ui = _compile("IF(data.eventCont, Text('true'), Text('false'))")
    rows = [json.loads(line) for line in a2ui.splitlines()]
    update = rows[1].get("updateComponents")
    assert isinstance(update, dict)
    components = update.get("components")
    assert isinstance(components, list)
    components[1]["childrenElse"] = ["missing"]
    report = validate_card(dsl_text="\n".join(json.dumps(row) for row in rows))
    assert any("missing component" in item.message for item in report.diagnostics)


@pytest.mark.parametrize("virtual_root", [False, True])
def test_runtime_if_survives_search_and_second_layer_layout(virtual_root: bool) -> None:
    body = "IF(data.temperature, Text(data.temperature), Text(data.temperature))"
    if not virtual_root:
        body = f"Column({body})"
    source = (
        "#Template WeatherOverviewFull@1(props: {})\n"
        'data = { temperature: $path("/current/temperatureText") }\n'
        f"{body}\n#End\n"
    )
    definition = compile_card_template(
        source,
        provider_id="com.huawei.weather",
        business_id="WeatherOverview",
        expected_wire_id="WeatherOverviewFull@1",
        expected_capability_id="ViewWeather",
        data_domain="/data/weather",
        description="天气条件测试",
        supported_card_sizes=("2x2",),
        primary_data=("/current/temperatureText",),
        secondary_data=(),
        optional_data=(),
        output_schema={
            "type": "object",
            "properties": {
                "current": {
                    "type": "object",
                    "properties": {"temperatureText": {"type": "string"}},
                },
            },
        },
    )
    registry = CardPlanRegistry()
    registry.templates[definition.wire_id] = definition
    registry.template_variant_search_records = build_template_variant_search_records(
        registry.templates
    )
    task = TaskSpec(
        userQuery="显示温度",
        size="2x2",
        dataModelSchema={
            "data": {
                "weather": {
                    "current": {"temperatureText": {"type": "string", "sampleValue": ""}},
                },
            },
        },
    )
    card_spec = {
        "suggestSize": "2x2",
        "dataBindings": [{"capabilityId": "ViewWeather", "writeResultTo": "/data/weather"}],
    }
    query = TemplateRetrievalQuery(
        themeId="family-weather-care-blue",
        requiredOutputFieldsByCapability={"ViewWeather": ("/current/temperatureText",)},
    )
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        writeResultTo="/data/weather",
        candidateOutputFields=["/current/temperatureText"],
    )
    result = retrieve_template_variants(query, task, registry, (binding,), card_spec)
    assert definition.wire_id in result.allowed_template_ids
    projection = build_ux_mixed_prompt(
        task_spec=task,
        card_spec=card_spec,
        scope=result.scope,
        component_candidates=result.component_candidates,
        required_template_groups=result.required_template_groups,
        registry=registry,
    )
    compilation = compile_ux_layout_card(
        'Template("SingleFocusLayout@1",{},Template("WeatherOverviewFull@1",{}));',
        task_spec=task,
        contract=projection.contract,
        protocol_profile=A2UIProtocolRegistry().get_profile(),
        registry=registry,
        card_spec=card_spec,
        enable_data_bindings=True,
    )
    nodes = _components(compilation.a2ui)
    conditions = [node for node in nodes if node.get("component") == "If"]
    assert len(conditions) == 1
    assert "styles" not in conditions[0]
    texts = [node for node in nodes if node.get("component") == "Text"]
    assert len(texts) == 2
    assert texts[0].get("content") == texts[1].get("content")


def test_runtime_if_height_uses_largest_exclusive_branch() -> None:
    first = Nested2Node("Text", ("true", {"height": 24}), ())
    second = Nested2Node("Text", ("false", {"height": 48}), ())
    node = Nested2Node("If", ("{{ ${/data/calendar/eventCount} }}",), (first, second))
    assert _estimate_height(node) == 48
