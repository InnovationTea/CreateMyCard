"""用户调整后的 Support 结构、字段降级及原子预览回归。"""

from __future__ import annotations

import pytest

from models.generation import TaskSpec
from services.template_generation.engine.cardplan.compiler import (
    _instantiate_blueprint,
    _serialize_node,
    _validate_provider_template_state,
)
from services.template_generation.engine.cardplan.preview_dataset import (
    build_template_preview_cases,
)
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.tersel_converter import Nested2Node, TerselConversionError

_CALENDAR_SUPPORTS = (
    ("ScheduleOverviewTimeSupport@1", "/events/0/dtStart"),
    ("ScheduleOverviewLocationSupport@1", "/events/0/eventLocation"),
    ("ScheduleOverviewStartTimeSupport@1", "/events/0/dtStart"),
    ("ScheduleOverviewDateSupport@1", "/events/0/startDate"),
)


def _nodes(root: Nested2Node, kind: str) -> list[Nested2Node]:
    result = [root] if root.component_type == kind else []
    for child in root.children:
        result.extend(_nodes(child, kind))
    return result


def _instantiate(
    template_id: str, bindings: dict[str, str], params: dict[str, str] | None = None,
) -> Nested2Node:
    registry = get_cardplan_registry()
    definition = registry.require_template(template_id)
    return _instantiate_blueprint(
        definition.variants[0].root, params or {}, bindings,
        registry.theme_reference_values("2x2-two-support"),
    )


def test_support_inventory_removes_deleted_templates() -> None:
    registry = get_cardplan_registry()
    supports = {key for key in registry.templates if key.endswith("Support@1")}
    assert len(supports) == 17
    assert not supports.intersection({
        "ScheduleOverviewSupport@1", "HeartRateOverviewUpdatedSupport@1",
        "HeartRateOverviewIconSupport@1", "HeartRateOverviewUpdatedIconSupport@1",
    })
    assert "BluetoothDeviceOverviewChargeSupport@1" in supports
    assert "WeatherOverviewTemperaturecoldLevelSupport@1" in supports


@pytest.mark.parametrize(("template_id", "secondary"), _CALENDAR_SUPPORTS)
@pytest.mark.parametrize("with_icon", (False, True))
def test_calendar_support_fields_and_optional_icon(
    template_id: str, secondary: str, with_icon: bool,
) -> None:
    definition = get_cardplan_registry().require_template(template_id)
    assert definition.primary_data == ("/events/0/title",)
    assert definition.secondary_data == (secondary,)
    bindings = {}
    for name, binding in definition.bindings.items():
        if binding.path != "/events/0/dtEnd":
            bindings[name] = "${data.calendar" + binding.path.replace("/", ".") + "}"
    params = {"calendarIcon": "resources/base/media/calendar_fill.svg"} if with_icon else {}
    root = _instantiate(template_id, bindings, params)
    assert len(_nodes(root, "Text")) == 2
    images = _nodes(root, "Image")
    assert len(images) == int(with_icon)
    if images:
        styles = images[0].values[-1]
        assert isinstance(styles, dict)
        assert styles.get("width") == styles.get("height") == 24


@pytest.mark.parametrize("with_end", (False, True))
def test_calendar_time_does_not_leave_separator_without_end(with_end: bool) -> None:
    bindings = {"title": "${data.calendar.title}", "start": "${data.calendar.start}"}
    if with_end:
        bindings["end"] = "${data.calendar.end}"
    root = _instantiate("ScheduleOverviewTimeSupport@1", bindings)
    source = _serialize_node(root)
    assert (" - " in source) == with_end
    assert len(_nodes(root, "Text")) == 2


@pytest.mark.parametrize("percent_fields", ((), ("percentText",), ("percent",), (
    "percent", "percentText",
)))
def test_battery_support_requires_numeric_percent_for_32vp_ring(
    percent_fields: tuple[str, ...],
) -> None:
    bindings = {"charging": "${data.phoneBattery.chargingStatusDesc}"}
    for name in percent_fields:
        bindings[name] = "${data.phoneBattery." + name + "}"
    definition = get_cardplan_registry().require_template("BatteryOverviewSupport@1")
    assert definition.primary_data == ("/batterySOC",)
    assert definition.optional_data == ("/batterySOCText",)
    if "percent" not in percent_fields:
        with pytest.raises(TerselConversionError, match="percent|binding"):
            _instantiate("BatteryOverviewSupport@1", bindings)
        return
    root = _instantiate("BatteryOverviewSupport@1", bindings)
    progresses = _nodes(root, "Progress")
    assert len(progresses) == 1
    assert len(_nodes(root, "Text")) == 2
    assert ("电量信息异常" in _serialize_node(root)) == (not percent_fields)
    if progresses:
        options = progresses[0].values[-1]
        assert isinstance(options, dict)
        assert options.get("width") == options.get("height") == 32
        assert options.get("value") == "${data.phoneBattery.percent}"


@pytest.mark.parametrize("with_action", (False, True))
def test_all_support_actions_are_optional_and_bound_to_root(with_action: bool) -> None:
    registry = get_cardplan_registry()
    for template_id, definition in registry.templates.items():
        if not template_id.endswith("Support@1"):
            continue
        bindings = {}
        for name, binding in definition.bindings.items():
            bindings[name] = "${data.support" + binding.path.replace("/", ".") + "}"
        params = {}
        for name in definition.asset_parameter_semantic_tags:
            params[name] = "resources/base/media/fixture.svg"
        if with_action:
            params["actionId"] = "event.support.test"
        root = _instantiate(template_id, bindings, params)
        options = root.values[0]
        assert isinstance(options, dict)
        # 两个能力尚未注册的历史模板仍使用覆盖层，本轮未改动其样式。
        legacy_overlays = {
            "AppUsageOverviewSupport@1", "ResourceUsageOverviewSupport@1",
            "BluetoothDeviceOverviewEarbudsSupport@1",
        }
        if template_id not in legacy_overlays:
            assert bool(options.get("onClick")) == with_action, template_id
        assert _serialize_node(root).count('"onClick":') == int(with_action), template_id
        assert "onclick" not in options


def test_health_support_coverage_matches_visible_content() -> None:
    registry = get_cardplan_registry()
    sleep = registry.require_template("SleepOverviewSupport@1")
    assert sleep.primary_data == ("/nightSleepDurationText",)
    assert sleep.secondary_data == sleep.optional_data == ()
    root = _instantiate(sleep.wire_id, {"duration": "${data.healthSport.nightSleepDurationText}"})
    assert not _nodes(root, "Progress")
    assert len(_nodes(root, "Text")) == 2
    workout = registry.require_template("WorkoutOverviewSupport@1")
    assert workout.primary_data == ("/exerciseCalorieText",)
    assert workout.secondary_data == ("/exerciseDurationText",)
    assert workout.optional_data == ("/exerciseTypeName",)


def test_two_support_layout_keeps_two_equal_row_slots() -> None:
    root = get_cardplan_registry().require_template("TwoSupportLayout@1").variants[0].root
    assert root.component == "Column"
    assert len(root.children) == 2
    for child in root.children:
        assert child.component == "Row"
        weight = child.values[0].properties.get("layoutWeight")
        assert weight is not None
        assert weight.value == 1


def test_support_preview_assets_preserve_device_and_weather_semantics() -> None:
    expected = {
        "BluetoothDeviceOverviewEarbudsSupport@1": ["icon_earphone.svg"],
        "BluetoothDeviceOverviewChargeSupport@1": ["earphone_case_16644.svg"],
        "HeartRateOverviewSupport@1": ["heart_fill.svg"],
        "WeatherOverviewTemperatureSupport@1": [],
        "WeatherOverviewTemperatureUvSupport@1": [],
        "WeatherOverviewTemperaturecoldLevelSupport@1": [],
        "BatteryOverviewSupport@1": [],
    }
    for case in build_template_preview_cases():
        if case.template_id not in expected:
            continue
        components = case.messages[1].get("updateComponents", {}).get("components", [])
        names = []
        for component in components:
            if component.get("component") == "Image":
                source = component.get("src")
                assert isinstance(source, str)
                names.append(source.rsplit("/", 1)[-1])
        assert names == expected.get(case.template_id), case.template_id


@pytest.mark.parametrize("missing", (None, "batteryLevel", "chargingStatusDesc"))
def test_charge_support_requires_case_battery_and_status(missing: str | None) -> None:
    fields = {
        "batteryLevel": {"type": "integer", "sampleValue": 0},
        "chargingStatusDesc": {"type": "string", "sampleValue": "未充电"},
    }
    if missing is not None:
        fields.pop(missing)
    task = TaskSpec(
        userQuery="耳机盒电量和天气", size="2x2",
        dataModelSchema={"data": {"earphone": fields}},
    )
    if missing is not None:
        with pytest.raises(
            TerselConversionError, match="trusted case status|trusted earphone facts"
        ):
            _validate_provider_template_state(
                "BluetoothDeviceOverviewChargeSupport@1", "default", task,
                business_names={"BluetoothDeviceOverview", "WeatherOverview"},
            )
    else:
        _validate_provider_template_state(
            "BluetoothDeviceOverviewChargeSupport@1", "default", task,
            business_names={"BluetoothDeviceOverview", "WeatherOverview"},
        )
