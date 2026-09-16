"""通用模板兜底、数据授权、类型、数组分支与真实 A2UI 编译回归。"""

from __future__ import annotations

import json
import re

import pytest

from models.generation import CandidateDataBinding, EventAction, TaskSpec
from services.template_generation.engine.advanced.ux_mixed_prompt import build_ux_mixed_prompt
from services.template_generation.engine.cardplan.business_actions import supports_business_action
from services.template_generation.engine.cardplan.compiler import compile_ux_layout_card
from services.template_generation.engine.cardplan.data_parameters import (
    DataExpressionArgument,
    DataPathArgument,
    resolve_data_arguments,
    split_data_signature,
)
from services.template_generation.engine.cardplan.models import ActionBinding, TemplatePlan
from services.template_generation.engine.cardplan.parser import parse_ux_layout_card
from services.template_generation.engine.cardplan.provider_bundle import compile_card_template
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.cardplan.template_plan_planner import (
    plan_template_candidates,
    planner_component_candidates,
    planner_required_template_groups,
    planner_scope,
)
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateRetrievalMiss,
    TemplateSearchIntent,
    search_template_variants,
)
from services.template_generation.engine.tersel_converter import TerselConversionError
from services.template_generation.profile import read_tersel_protocol_profile

FIELDS = (
    "/location/prefectureName",
    "/current/coldLevel",
    "/current/humidityPercent",
    "/current/uvIndex",
)


@pytest.fixture(scope="module")
def registry() -> CardPlanRegistry:
    return CardPlanRegistry()


def _task(action_count: int = 0) -> TaskSpec:
    events = [
        EventAction(id="event.viewWeather", call="clickToWeather", args={}),
        EventAction(id="event.createAlarm", call="clickToIntent", args={}),
    ]
    return TaskSpec(
        userQuery="显示杭州的感冒风险、湿度和紫外线",
        size="2x2",
        dataModelSchema={
            "data": {
                "weather": {
                    "location": {"prefectureName": {"type": "string", "sampleValue": "杭州"}},
                    "current": {
                        "coldLevel": {"type": "string", "sampleValue": "低"},
                        "humidityPercent": {"type": "number", "sampleValue": 68.0},
                        "uvIndex": {"type": "string", "sampleValue": "中等"},
                        "temperatureText": {"type": "string", "sampleValue": "29℃"},
                        "condition": {"type": "string", "sampleValue": "多云"},
                    },
                }
            }
        },
        eventCandidates=events[:action_count],
    )


def _card() -> dict[str, object]:
    return {
        "title": "天气",
        "description": "感冒风险、湿度和紫外线",
        "suggestSize": "2x2",
        "dataBindings": [{"capabilityId": "ViewWeather", "writeResultTo": "/data/weather"}],
    }


def _search(registry: CardPlanRegistry, task: TaskSpec, fields: tuple[str, ...] = FIELDS):
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={"ViewWeather": fields},
        action=[event.id for event in task.eventCandidates],
    )
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        writeResultTo="/data/weather",
        candidateOutputFields=fields,
    )
    return intent, search_template_variants(intent, task, registry, (binding,), _card())


def _projection(registry: CardPlanRegistry, task: TaskSpec, plans: tuple[TemplatePlan, ...]):
    return build_ux_mixed_prompt(
        task_spec=task,
        card_spec=_card(),
        scope=planner_scope(plans),
        component_candidates=planner_component_candidates(plans),
        required_template_groups=planner_required_template_groups(plans),
        template_plans=plans,
        registry=registry,
    )


def _source(plan: TemplatePlan, data: str) -> str:
    slot = plan.business_slots[0]
    children = [f'Template("{slot.template_id}", {{data: {data}}})']
    for assignment in plan.action_assignments:
        children.append(
            f'Template("{assignment.action_template_id}", '
            f'{{actionId: "{assignment.action_id}", label: "查看"}})'
        )
    return f'Template("{plan.layout_template_id}", {{}}, ' + ", ".join(children) + ");"


DATA = """{
  location: $path("/location/prefectureName"),
  mainTextValue: Expr("感冒风险" + data.coldLevel),
  supportValues: [Expr("湿度" + data.humidityPercent + "%"), Expr("紫外线" + data.uvIndex)]
}"""


def test_all_current_businesses_have_four_fallback_shapes(registry: CardPlanRegistry) -> None:
    groups: dict[str, set[str]] = {}
    for definition in registry.templates.values():
        if definition.fallback_only:
            assert definition.data_parameters_schema
            assert definition.business_id is not None
            shapes = groups.setdefault(definition.business_id, set())
            shapes.add(re.split(r"General(?:Number|Text|Pair)", definition.template_id)[1])
    assert set(groups) == set(registry.ux_business_components)
    assert all(shapes == {"Full", "Hero", "Compact", "Support"} for shapes in groups.values())


def test_specialized_candidates_exclude_general(registry: CardPlanRegistry) -> None:
    intent, result = _search(registry, _task(), ("/current/temperatureText",))
    assert result.business_candidates
    for group in result.business_candidates:
        assert all(
            not registry.require_template(item.template_id).fallback_only
            for item in group.candidates
        )
    assert plan_template_candidates(intent, result, _task(), registry)


@pytest.mark.parametrize(("action_count", "shape"), [(0, "Full"), (1, "Hero"), (2, "Compact")])
def test_existing_planner_selects_general_shapes(
    registry: CardPlanRegistry,
    action_count: int,
    shape: str,
) -> None:
    task = _task(action_count)
    intent, result = _search(registry, task)
    for group in result.business_candidates:
        assert all(
            registry.require_template(item.template_id).fallback_only for item in group.candidates
        )
    plans = plan_template_candidates(intent, result, task, registry)
    assert all(plan.business_slots[0].template_id.endswith(shape + "@1") for plan in plans)


def test_dynamic_data_reaches_real_a2ui_without_sample_substitution(
    registry: CardPlanRegistry,
) -> None:
    task = _task()
    intent, search = _search(registry, task)
    plans = plan_template_candidates(intent, search, task, registry)
    projection = _projection(registry, task, plans)
    result = compile_ux_layout_card(
        _source(plans[0], DATA),
        task_spec=task,
        card_spec=_card(),
        contract=projection.contract,
        registry=registry,
        protocol_profile=read_tersel_protocol_profile(),
        enable_data_bindings=True,
    )
    for path in FIELDS:
        assert "/data/weather" + path in result.a2ui
    assert "感冒风险" in result.a2ui
    assert "IfDataSize" not in result.a2ui
    assert "_advancedComponent" not in result.a2ui
    assert result.stats.matched_plan_id == plans[0].plan_id
    messages = [json.loads(line) for line in result.a2ui.splitlines()]
    assert len(messages) == 3


def test_missing_dynamic_display_field_is_rejected(registry: CardPlanRegistry) -> None:
    task = _task()
    intent, result = _search(registry, task)
    plans = plan_template_candidates(intent, result, task, registry)
    projection = _projection(registry, task, plans)
    missing = DATA.replace('Expr("感冒风险" + data.coldLevel)', '"低风险"')
    with pytest.raises(TerselConversionError, match="omits explicit"):
        compile_ux_layout_card(
            _source(plans[0], missing),
            task_spec=task,
            card_spec=_card(),
            contract=projection.contract,
            registry=registry,
            protocol_profile=read_tersel_protocol_profile(),
            enable_data_bindings=True,
        )


@pytest.mark.parametrize("general_battery", [False, True])
def test_two_support_layout_compiles_per_business_fallback(
    registry: CardPlanRegistry, general_battery: bool,
) -> None:
    task = _task()
    task_data = task.dataModelSchema.get("data")
    assert isinstance(task_data, dict)
    battery_fields = ("/chargingStatusDesc", "/pluggedTypeDesc")
    if general_battery:
        battery_fields = (
            "/healthStatusDesc", "/batterySOCText", "/chargingStatusDesc",
            "/batteryCapacityLevelDesc",
        )
    task_data["phoneBattery"] = {
        field.removeprefix("/"): {"type": "string"} for field in battery_fields
    }
    fields_by_capability = {"ViewWeather": FIELDS, "GetPhoneBatteryInfo": battery_fields}
    bindings = [
        CandidateDataBinding(
            capabilityId=capability, writeResultTo=root, candidateOutputFields=fields,
        )
        for capability, root, fields in (
            ("ViewWeather", "/data/weather", FIELDS),
            ("GetPhoneBatteryInfo", "/data/phoneBattery", battery_fields),
        )
    ]
    card = _card()
    card["dataBindings"] = [
        {"capabilityId": binding.capabilityId, "writeResultTo": binding.writeResultTo}
        for binding in bindings
    ]
    intent = TemplateSearchIntent(requiredOutputFieldsByCapability=fields_by_capability)
    search = search_template_variants(intent, task, registry, tuple(bindings), card)
    for group in search.business_candidates:
        expected_general = group.capability_id == "ViewWeather" or general_battery
        assert all(
            registry.require_template(item.template_id).fallback_only == expected_general
            for item in group.candidates
        )
    plans = plan_template_candidates(intent, search, task, registry)
    assert plans and all(plan.layout_template_id == "TwoSupportLayout@1" for plan in plans)
    projection = build_ux_mixed_prompt(
        task_spec=task, card_spec=card, scope=planner_scope(plans),
        component_candidates=planner_component_candidates(plans),
        required_template_groups=planner_required_template_groups(plans),
        template_plans=plans, registry=registry,
    )
    children: list[str] = []
    for slot in plans[0].business_slots:
        params = "{}"
        if slot.capability_id == "ViewWeather":
            params = "{data: " + DATA + "}"
        elif general_battery:
            params = """{data: {
                title: "电池", mainTextValue: $path("/healthStatusDesc"),
                supportValues: [$path("/batterySOCText"),
                    Expr(data.chargingStatusDesc + " " + data.batteryCapacityLevelDesc)]
            }}"""
        children.append(f'Template("{slot.template_id}", {params})')
    source = 'Template("TwoSupportLayout@1", {}, ' + ", ".join(children) + ");"
    result = compile_ux_layout_card(
        source, task_spec=task, card_spec=card, contract=projection.contract,
        registry=registry, protocol_profile=read_tersel_protocol_profile(),
        enable_data_bindings=True,
    )
    assert result.stats.matched_plan_id == plans[0].plan_id
    for binding in bindings:
        for field in binding.candidateOutputFields:
            assert binding.writeResultTo + field in result.a2ui


@pytest.mark.parametrize(
    "source",
    [
        '{data: {value: $path("/value")}}',
        '{data: {value: Expr("风险" + data.value)}}',
    ],
)
def test_parser_keeps_data_arguments_symbolic(source: str) -> None:
    parsed = parse_ux_layout_card(f'Template("SingleFocusLayout@1", {source});')
    params = parsed.values[0]
    data = params.get("data")
    assert isinstance(data, dict)
    value = data.get("value")
    assert isinstance(value, (DataPathArgument, DataExpressionArgument))


@pytest.mark.parametrize(
    "argument",
    [
        DataPathArgument("/other/value"),
        DataPathArgument("/data/weather/value"),
        DataPathArgument("/items/2/value"),
        DataExpressionArgument("data.unknown"),
        DataExpressionArgument("data.other.value"),
        DataExpressionArgument("__import__('os')"),
        DataExpressionArgument("data.value.constructor"),
        "${data.weather.value}",
        "{{ ${/data/weather/value} }}",
        0,
        False,
        None,
    ],
)
def test_data_authorization_and_types_reject_invalid_arguments(argument: object) -> None:
    schema, _ = split_data_signature("data: {value: string}, props: {}")
    with pytest.raises(ValueError):
        resolve_data_arguments(schema, {"value": argument}, {"/value": "string"}, "/data/weather")


@pytest.mark.parametrize("count", [0, 1, 2])
def test_array_parameter_keeps_order_empty_strings_and_zero(count: int) -> None:
    schema, _ = split_data_signature("data: {value: integer, ...items: string[]}, props: {}")
    arguments = {"value": 0, "items": ["", "第二项"][:count]}
    values = resolve_data_arguments(schema, arguments, {}, "/data/weather")
    assert values.get("value") == 0
    assert type(values.get("value")) is int
    assert list(values) == ["value", *(f"items[{index}]" for index in range(count))]


def test_array_parameter_overflow_is_rejected() -> None:
    schema, _ = split_data_signature("data: {...items: string[]}, props: {}")
    with pytest.raises(TerselConversionError, match="budget"):
        resolve_data_arguments(schema, {"items": ["a", "b", "c"]}, {}, "/data/weather")


def test_array_reference_must_be_valid_in_every_length_branch() -> None:
    source = """#Template ExampleFull@1(data: {items: string[]}, props: {})
Column(Text(data.items[0]))
#End"""
    with pytest.raises(ValueError, match="out of range"):
        compile_card_template(
            source,
            provider_id="example.general",
            business_id="Example",
            expected_wire_id="ExampleFull@1",
            expected_capability_id="ViewWeather",
            data_domain="/data/weather",
            description="通用测试",
            supported_card_sizes=("2x2",),
            primary_data=(),
            secondary_data=(),
            optional_data=(),
            output_schema={},
        )


def test_general_requires_one_approved_root(registry: CardPlanRegistry) -> None:
    task = _task()
    intent = TemplateSearchIntent(requiredOutputFieldsByCapability={"ViewWeather": FIELDS})
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        writeResultTo="/data/wrong",
        candidateOutputFields=FIELDS,
    )
    card = {"dataBindings": [{"capabilityId": "ViewWeather", "writeResultTo": "/data/wrong"}]}
    with pytest.raises(TemplateRetrievalMiss):
        search_template_variants(intent, task, registry, (binding,), card)


def test_specialized_candidate_still_blocks_general_when_planner_cannot_form_layout(
    registry: CardPlanRegistry,
) -> None:
    disabled: list[str] = []
    for definition in registry.templates.values():
        if definition.capability_id != "ViewWeather" or definition.fallback_only:
            continue
        if definition.wire_id != "WeatherOverviewHeroTitle@1":
            disabled.append(definition.wire_id)
    limited = CardPlanRegistry(disabled_template_ids=tuple(disabled))
    intent, result = _search(limited, _task(), ("/location/prefectureName",))
    candidates = result.business_candidates[0].candidates
    assert tuple(item.template_id for item in candidates) == ("WeatherOverviewHeroTitle@1",)
    with pytest.raises(TemplateRetrievalMiss, match="atomic plan"):
        plan_template_candidates(intent, result, _task(), limited)


@pytest.mark.parametrize("expression", [
    "data.number", "data.number + 1", "data.number > 1",
    'data.number > 1 ? "大" : 0', 'size(data.text)',
])
def test_string_expression_rejects_non_string_result_branches(expression: str) -> None:
    schema, _ = split_data_signature("data: {value: string}, props: {}")
    with pytest.raises(TerselConversionError, match="declared string type"):
        resolve_data_arguments(
            schema, {"value": DataExpressionArgument(expression)},
            {"/number": "number", "/text": "string"}, "/data/weather",
        )


@pytest.mark.parametrize("expression", [
    '"数值" + data.number', 'data.number > 1 ? "大" : "小"',
    'data.number > 1 ? data.text : (data.number == 0 ? "零" : "小")',
    'data.text', '"长度" + size(data.text)',
])
def test_string_expression_preserves_text_result(expression: str) -> None:
    schema, _ = split_data_signature("data: {value: string}, props: {}")
    values = resolve_data_arguments(
        schema, {"value": DataExpressionArgument(expression)},
        {"/number": "number", "/text": "string"}, "/data/weather",
    )
    value = values.get("value")
    assert isinstance(value, str) and value.startswith("{{")


def test_second_layer_receives_selected_field_metadata_without_samples(
    registry: CardPlanRegistry,
) -> None:
    task = _task()
    intent, result = _search(registry, task)
    plans = plan_template_candidates(intent, result, task, registry)
    projection = _projection(registry, task, plans)
    messages = json.dumps(projection.messages, ensure_ascii=False)
    assert "dataSchema" in messages
    assert "displayUnits" in messages
    assert "sampleValue" not in messages
    assert "/current/temperatureText" not in messages


@pytest.mark.parametrize(("display_paths", "accepted"), [
    (("/events/0/title",), True),
    (("/events/1/title",), False),
    (("/events/0/title", "/events/1/title"), False),
    ((), False),
])
def test_general_calendar_support_action_matches_displayed_event(
    registry: CardPlanRegistry, display_paths: tuple[str, ...], accepted: bool,
) -> None:
    definition = registry.require_template("ScheduleOverviewGeneralNumberSupport@1")
    action = ActionBinding(
        action_id="event.viewCalendarEvent", event_id="event.viewCalendarEvent",
        display_label="查看日程", call="clickToIntent",
        args={"params": {"entityId": {"path": "/data/calendar/events/0/entityId"}}},
    )
    assert supports_business_action(
        definition, action, "2x2", display_paths=display_paths,
    ) is accepted
