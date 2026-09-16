"""按真实能力叶字段逐项走 Search、Planner、数据填充及 A2UI 编译。"""

from __future__ import annotations

import json
from typing import Any

import pytest

from models.generation import CandidateDataBinding, TaskSpec
from services.template_generation.engine.advanced.ux_mixed_prompt import build_ux_mixed_prompt
from services.template_generation.engine.cardplan.compiler import compile_ux_layout_card
from services.template_generation.engine.cardplan.general_semantics import (
    field_presentation,
    general_field_is_allowed,
    general_preview_data,
    validate_general_focus,
    validate_general_main_value,
)
from services.template_generation.engine.cardplan.models import TemplateDefinition
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
from services.template_generation.tools.audit_general_template_coverage import (
    CAPABILITIES,
    build_audit,
    schema_leaves,
)

_CAPABILITIES = json.loads(CAPABILITIES.read_text())
_DISPLAY_FIELDS: list[tuple[dict[str, Any], str, dict[str, Any]]] = []
for _capability in _CAPABILITIES:
    for _path, _field in schema_leaves(_capability.get("outputSchema", {})):
        if field_presentation(_path, _field) != "internal":
            _DISPLAY_FIELDS.append((_capability, _path, _field))


@pytest.fixture(scope="module")
def registry() -> CardPlanRegistry:
    return CardPlanRegistry()


@pytest.fixture(scope="module")
def general_registry(registry: CardPlanRegistry) -> CardPlanRegistry:
    disabled = []
    for definition in registry.templates.values():
        if definition.business_id is not None and not definition.fallback_only:
            disabled.append(definition.wire_id)
    return CardPlanRegistry(disabled_template_ids=tuple(disabled))


def _task_schema(schema: dict[str, Any]) -> Any:
    result: Any
    if schema.get("type") == "object":
        result = {name: _task_schema(value) for name, value in schema.get("properties", {}).items()}
    elif schema.get("type") == "array":
        result = [_task_schema(schema.get("items", {}))]
    else:
        result = {"type": schema.get("type")}
    return result


def _main_argument(path: str, field: dict[str, Any]) -> str:
    reference = "data." + path.removeprefix("/").replace("/", ".")
    argument: str
    if field.get("type") == "boolean":
        argument = f'Expr({reference} ? "是" : "否")'
    elif field.get("type") in {"number", "integer"}:
        units = field.get("displayUnits", [""])
        argument = f"Expr({reference} + {json.dumps(units[0], ensure_ascii=False)})"
    else:
        argument = f'$path("{path}")'
    return argument


@pytest.mark.parametrize(
    ("capability", "pattern", "field"),
    _DISPLAY_FIELDS,
    ids=[item[0].get("id", "") + item[1] for item in _DISPLAY_FIELDS],
)
def test_each_display_field_reaches_real_a2ui(
    general_registry: CardPlanRegistry,
    capability: dict[str, Any],
    pattern: str,
    field: dict[str, Any],
) -> None:
    capability_id = capability.get("id")
    root = capability.get("defaultWriteResultTo")
    assert isinstance(capability_id, str) and isinstance(root, str)
    path = pattern.replace("*", "0")
    schema: dict[str, Any] = _task_schema(capability.get("outputSchema", {}))
    for part in reversed(root.removeprefix("/").split("/")):
        schema = {part: schema}
    task = TaskSpec(userQuery="展示本字段", size="2x2", dataModelSchema=schema)
    card = {"dataBindings": [{"capabilityId": capability_id, "writeResultTo": root}]}
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={capability_id: (path,)},
        primaryOutputFieldByCapability={capability_id: path},
    )
    binding = CandidateDataBinding(
        capabilityId=capability_id,
        writeResultTo=root,
        candidateOutputFields=(path,),
    )
    search = search_template_variants(intent, task, general_registry, (binding,), card)
    plans = plan_template_candidates(intent, search, task, general_registry)
    definition = general_registry.require_template(plans[0].business_slots[0].template_id)
    expected = "number" if field_presentation(pattern, field) == "number" else "text"
    assert definition.general_content_kind == expected
    projection = build_ux_mixed_prompt(
        task_spec=task,
        card_spec=card,
        scope=planner_scope(plans),
        component_candidates=planner_component_candidates(plans),
        required_template_groups=planner_required_template_groups(plans),
        template_plans=plans,
        registry=general_registry,
    )
    title = "location" if definition.business_id == "WeatherOverview" else "title"
    main = "mainNumberValue" if expected == "number" else "mainTextValue"
    progress = ""
    if path in {"/batterySOC", "/sleepScore"}:
        progress = f', progressValue: $path("{path}")'
    source = (
        f'Template("{plans[0].layout_template_id}", {{}}, '
        f'Template("{definition.wire_id}", {{data: {{ {title}: "字段概览", '
        f"{main}: {_main_argument(path, field)}, supportValues: []{progress} }} }}));"
    )
    result = compile_ux_layout_card(
        source,
        task_spec=task,
        card_spec=card,
        contract=projection.contract,
        registry=general_registry,
        protocol_profile=read_tersel_protocol_profile(),
        enable_data_bindings=True,
    )
    assert root + path in result.a2ui
    assert len(result.a2ui.splitlines()) == 3


def test_audit_counts_fields_not_template_inventory(registry: CardPlanRegistry) -> None:
    audit = build_audit(registry, _CAPABILITIES)
    assert audit.get("leafPatterns") == 87
    assert audit.get("roles") == {"internal": 7, "context": 23, "number": 30, "text": 27}
    assert audit.get("coveredLeafPatterns") == 80
    assert len(_DISPLAY_FIELDS) == 80


@pytest.mark.parametrize(
    ("business", "allowed", "denied"),
    [
        ("SleepOverview", "/sleepScore", "/dailySteps"),
        ("ActivityOverview", "/dailySteps", "/sleepScore"),
        ("HeartRateOverview", "/exerciseHeartRateAvg", "/sleepStatus"),
        ("WorkoutOverview", "/exerciseDurationText", "/nightSleepDurationText"),
    ],
)
def test_health_businesses_do_not_borrow_other_business_fields(
    registry: CardPlanRegistry,
    business: str,
    allowed: str,
    denied: str,
) -> None:
    definition = registry.require_template(business + "GeneralNumberFull@1")
    assert general_field_is_allowed(definition, allowed)
    assert not general_field_is_allowed(definition, denied)


@pytest.mark.parametrize(
    "value",
    [
        "感冒风险低",
        "正常",
        "${data.weather.current.coldLevel}",
        "{{ '感冒风险' + ${/data/weather/current/humidityPercent} + '%' }}",
        "{{ ${/data/weather/current/coldLevel} }}",
    ],
)
def test_number_main_rejects_status_and_label_sentences(
    registry: CardPlanRegistry,
    value: str,
) -> None:
    definition = registry.require_template("WeatherOverviewGeneralNumberFull@1")
    with pytest.raises(TerselConversionError, match="Number main"):
        validate_general_main_value(
            definition,
            {"mainNumberValue": value},
            {
                "/current/humidityPercent": "number",
                "/current/coldLevel": "string",
            },
        )


@pytest.mark.parametrize(
    "value",
    [
        "68%",
        "68",
        "${data.weather.current.temperatureText}",
        "{{ ${/data/weather/current/humidityPercent} + '%' }}",
    ],
)
def test_number_main_accepts_numeric_display(registry: CardPlanRegistry, value: str) -> None:
    definition = registry.require_template("WeatherOverviewGeneralNumberFull@1")
    validate_general_main_value(
        definition,
        {"mainNumberValue": value},
        {
            "/current/humidityPercent": "number",
            "/current/temperatureText": "string",
        },
    )


def _nodes(root):
    yield root
    for child in root.children:
        yield from _nodes(child)


def _main_font(definition: TemplateDefinition, name: str) -> int:
    for node in _nodes(definition.variants[0].root):
        if node.component == "Text" and node.values[0].name == name:
            option = node.values[-1].properties.get("fontSize")
            assert option is not None
            return option.value
    raise AssertionError("Main Text missing")


def test_businesses_keep_distinct_visual_baselines(registry: CardPlanRegistry) -> None:
    expected = {
        "WeatherOverview": 32,
        "AppUsageOverview": 24,
        "ActivityOverview": 38,
        "CountdownOverview": 40,
        "HeartRateOverview": 38,
        "SleepOverview": 20,
        "WorkoutOverview": 24,
        "BluetoothDeviceOverview": 20,
    }
    for business, size in expected.items():
        definition = registry.require_template(business + "GeneralNumberFull@1")
        assert _main_font(definition, "mainNumberValue") == size
    for business in ("BatteryOverview", "ResourceUsageOverview", "SleepOverview"):
        definition = registry.require_template(business + "GeneralNumberFull@1")
        assert any(node.component == "Progress" for node in _nodes(definition.variants[0].root))
    assert (
        _main_font(registry.require_template("WeatherOverviewGeneralTextFull@1"), "mainTextValue")
        == 20
    )


def test_primary_field_cannot_be_hidden_in_support_values(registry: CardPlanRegistry) -> None:
    definition = registry.require_template("WeatherOverviewGeneralTextFull@1")
    values = {
        "mainTextValue": "${data.weather.current.airQuality}",
        "supportValues[0]": "${data.weather.current.coldLevel}",
    }
    with pytest.raises(TerselConversionError, match="primary field"):
        validate_general_focus(definition, values, {"/current/coldLevel"})


def _minimum_height(node) -> float:
    options = node.values[-1] if node.values and isinstance(node.values[-1], dict) else {}
    heights = [_minimum_height(child) for child in node.children]
    height = options.get("height", 0)
    fixed = float(height) if isinstance(height, (int, float)) else 0.0
    intrinsic = max(heights, default=0.0)
    if node.component_type in {"Column", "List"}:
        intrinsic = sum(heights) + max(len(heights) - 1, 0) * options.get("itemMargin", 0)
    padding = options.get("padding", {})
    if isinstance(padding, dict):
        intrinsic += padding.get("top", 0) + padding.get("bottom", 0)
    return max(fixed, intrinsic)


@pytest.mark.parametrize("count", [0, 1, 2])
def test_all_general_shapes_fit_existing_height_budgets(
    registry: CardPlanRegistry, count: int,
) -> None:
    from services.template_generation.engine.cardplan.compiler import _instantiate_blueprint
    from services.template_generation.engine.cardplan.data_parameters import (
        materialize_data_root,
        resolve_data_arguments,
        select_data_size,
    )
    from services.template_generation.engine.cardplan.preview_dataset import (
        _CONTENT_HEIGHT_BY_LAYOUT,
    )
    from services.template_generation.engine.cardplan.provider_bundle import (
        provider_template_layout_kind,
    )

    for definition in registry.templates.values():
        if not definition.fallback_only:
            continue
        arguments = general_preview_data(definition)
        arguments["supportValues"] = ["辅助内容"] * count
        schema = definition.data_parameters_schema
        if "progressValue" in schema.get("properties", {}):
            arguments["progressValue"] = 0
        values = resolve_data_arguments(schema, arguments, {}, definition.data_domain or "")
        selected = select_data_size(definition.variants[0].root, schema, count)
        root = materialize_data_root(selected, values)
        params = {name: "resources/icon.svg" for name in definition.asset_parameter_semantic_tags}
        expanded = _instantiate_blueprint(
            root, params, {}, registry.theme_reference_values("2x2-two-support"),
        )
        shape = provider_template_layout_kind(definition.wire_id)
        budget = _CONTENT_HEIGHT_BY_LAYOUT.get(shape)
        assert budget is not None
        assert _minimum_height(expanded) <= budget, definition.wire_id


@pytest.mark.parametrize("progress", [-1, 101, "${data.healthSport.nightSleepDurationText}"])
def test_progress_rejects_non_percentage_values(
    registry: CardPlanRegistry, progress: object,
) -> None:
    definition = registry.require_template("SleepOverviewGeneralNumberFull@1")
    with pytest.raises(TerselConversionError, match="progress"):
        validate_general_main_value(
            definition, {"mainNumberValue": "68", "progressValue": progress},
            {"/sleepScore": "integer"},
        )


_PAIR_SCENARIOS = (
    ("ViewWeather", ("/current/coldLevel", "/current/uvIndex", "/current/humidityPercent")),
    ("GetCalendarEvents", ("/events/0/title", "/events/0/dtStart", "/events/0/eventLocation")),
    ("GetAppUsageDuration", ("/appUsage/appName", "/appUsage/durationText", "/updatedAt")),
    ("GetEarphoneInfo", ("/leftBatteryLevel", "/rightBatteryLevel", "/isConnected")),
    ("GetPhoneBatteryInfo", ("/batterySOCText", "/healthStatusDesc", "/chargingStatusDesc")),
    ("GetHealthAndSportSummary", ("/sleepScore", "/sleepStatus", "/nightSleepDurationText")),
    ("GetHealthAndSportSummary", ("/dailySteps", "/dailyDistanceText", "/dailyTotalCaloriesText")),
    ("GetHealthAndSportSummary", (
        "/exerciseHeartRateAvg", "/exerciseHeartRateMax", "/exerciseHeartRateMin",
    )),
    ("GetHealthAndSportSummary", (
        "/exerciseDurationText", "/exerciseCalorieText", "/exerciseTypeName",
    )),
)


@pytest.mark.parametrize(("capability_id", "paths"), _PAIR_SCENARIOS)
def test_pair_compiles_representative_business_field_combinations(
    general_registry: CardPlanRegistry, capability_id: str, paths: tuple[str, ...],
) -> None:
    from services.template_generation.engine.cardplan.provider_bundle import _schema_leaf

    capability = next(item for item in _CAPABILITIES if item.get("id") == capability_id)
    root = capability.get("defaultWriteResultTo")
    assert isinstance(root, str)
    schema = _task_schema(capability.get("outputSchema", {}))
    for part in reversed(root.removeprefix("/").split("/")):
        schema = {part: schema}
    task = TaskSpec(userQuery="比较两项并显示辅助信息", size="2x2", dataModelSchema=schema)
    card = {"dataBindings": [{"capabilityId": capability_id, "writeResultTo": root}]}
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={capability_id: paths},
        primaryOutputFieldByCapability={capability_id: paths[0]},
    )
    binding = CandidateDataBinding(
        capabilityId=capability_id, writeResultTo=root, candidateOutputFields=paths,
    )
    search = search_template_variants(intent, task, general_registry, (binding,), card)
    plans = plan_template_candidates(intent, search, task, general_registry)
    pairs = []
    for plan in plans:
        definition = general_registry.require_template(plan.business_slots[0].template_id)
        if definition.general_content_kind == "pair":
            pairs.append(plan)
    assert pairs
    selected = pairs[0]
    definition = general_registry.require_template(selected.business_slots[0].template_id)
    arguments = []
    for path in paths:
        field = _schema_leaf(capability.get("outputSchema", {}), path)
        assert field is not None
        arguments.append(_main_argument(path, field))
    title = "location" if definition.business_id == "WeatherOverview" else "title"
    data = (
        f'{{{title}: "指标对照", firstLabel: "主指标", firstValue: {arguments[0]}, '
        f'secondLabel: "对照指标", secondValue: {arguments[1]}, '
        f'supportValues: [{arguments[2]}]}}'
    )
    source = (
        f'Template("{selected.layout_template_id}", {{}}, '
        f'Template("{definition.wire_id}", {{data: {data}}}));'
    )
    projection = build_ux_mixed_prompt(
        task_spec=task, card_spec=card, scope=planner_scope(plans),
        component_candidates=planner_component_candidates(plans),
        required_template_groups=planner_required_template_groups(plans),
        template_plans=plans, registry=general_registry,
    )
    result = compile_ux_layout_card(
        source, task_spec=task, card_spec=card, contract=projection.contract,
        registry=general_registry, protocol_profile=read_tersel_protocol_profile(),
        enable_data_bindings=True,
    )
    for path in paths:
        assert root + path in result.a2ui


def test_template_families_follow_current_data_fields(registry: CardPlanRegistry) -> None:
    from collections import Counter

    counts: Counter[str] = Counter()
    for definition in registry.templates.values():
        if definition.fallback_only:
            counts[definition.general_content_kind or "unknown"] += 1
    assert counts == {"number": 44, "text": 44, "pair": 40}
    assert "CountdownOverviewGeneralPairFull@1" not in registry.templates


def test_cross_health_business_combination_is_not_claimed_as_covered(
    general_registry: CardPlanRegistry,
) -> None:
    capability = "GetHealthAndSportSummary"
    root = "/data/healthSport"
    fields = ("/dailySteps", "/sleepScore")
    task = TaskSpec(userQuery="步数与睡眠评分", size="2x2", dataModelSchema={
        "data": {"healthSport": {
            "dailySteps": {"type": "integer"}, "sleepScore": {"type": "integer"},
        }},
    })
    intent = TemplateSearchIntent(requiredOutputFieldsByCapability={capability: fields})
    binding = CandidateDataBinding(
        capabilityId=capability, writeResultTo=root, candidateOutputFields=fields,
    )
    card = {"dataBindings": [{"capabilityId": capability, "writeResultTo": root}]}
    with pytest.raises(TemplateRetrievalMiss, match="no provider template covers"):
        search_template_variants(intent, task, general_registry, (binding,), card)


@pytest.mark.parametrize("value", ["7小时1分", "0分", "1小时21分30秒"])
def test_compound_duration_literal_uses_business_numeric_style(
    registry: CardPlanRegistry, value: str,
) -> None:
    definition = registry.require_template("AppUsageOverviewGeneralNumberFull@1")
    validate_general_main_value(
        definition, {"mainNumberValue": value}, {"/appUsage/durationText": "string"},
    )
