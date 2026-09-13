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
    ("ScheduleOverviewTimeSupport@1", "/events/0/dtStart", ()),
    ("ScheduleOverviewLocationSupport@1", "/events/0/title", ("/events/0/eventLocation",)),
    ("ScheduleOverviewStartTimeSupport@1", "/events/0/title", ("/events/0/dtStart",)),
    ("ScheduleOverviewDateSupport@1", "/events/0/title", ("/events/0/startDate",)),
)

# 主数值与同排单位都属于主文本；应用时长模板保留原有的辅助信息在上布局。
_SUPPORT_PRIMARY_TEXT_INDEXES = {
    "ActivityOverviewSupport@1": (0,),
    "AppUsageOverviewSupport@1": (1,),
    "BatteryOverviewSupport@1": (0,),
    "BatteryOverviewStatusSupport@1": (0,),
    "BluetoothDeviceOverviewEarbudsSupport@1": (0,),
    "BluetoothDeviceOverviewChargeSupport@1": (0,),
    "BluetoothDeviceOverviewConnectionSupport@1": (0,),
    "CountdownOverviewSupport@1": (0,),
    "CountdownOverviewTravelSupport@1": (0,),
    "HeartRateOverviewSupport@1": (0,),
    "ResourceUsageOverviewSupport@1": (0, 1),
    "ScheduleOverviewTimeSupport@1": (0,),
    "ScheduleOverviewLocationSupport@1": (0,),
    "ScheduleOverviewStartTimeSupport@1": (0,),
    "ScheduleOverviewDateSupport@1": (0,),
    "SleepOverviewSupport@1": (0,),
    "WeatherOverviewTemperatureSupport@1": (0, 1),
    "WeatherOverviewTemperatureUvSupport@1": (0, 1),
    "WeatherOverviewTemperaturecoldLevelSupport@1": (0, 1),
    "WeatherOverviewDaily2TravelSupport@1": (0,),
    "WeatherOverviewTravelSupport@1": (0,),
    "WorkoutOverviewSupport@1": (0,),
}

# 电量缺失时只保留一行主文本的 Support：不要求存在辅助文本行。
_SUPPORT_OPTIONAL_SECONDARY_TEXT_TEMPLATES = {
    "BatteryOverviewSupport@1",
    "BluetoothDeviceOverviewChargeSupport@1",
    "BluetoothDeviceOverviewConnectionSupport@1",
}

# 温度文本改为可选绑定的温度 Support：无可选数据时主行仅剩城市文本。
_SUPPORT_OPTIONAL_TEMPERATURE_TEXT_TEMPLATES = {
    "WeatherOverviewTemperatureSupport@1",
}


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


def _support_ux_root(
    template_id: str, with_optional: bool, with_action: bool,
) -> Nested2Node:
    definition = get_cardplan_registry().require_template(template_id)
    variant = definition.variants[0]
    bindings: dict[str, str] = {}
    for name in definition.bindings:
        if not with_optional and name in variant.optional_bindings:
            continue
        bindings[name] = "${data.support." + name + "}"
    required_parameters = variant.parameters_schema.get("required", [])
    params: dict[str, str] = {}
    for name in definition.asset_parameter_semantic_tags:
        if with_optional or name in required_parameters:
            params[name] = "resources/base/media/fixture.svg"
    properties = variant.parameters_schema.get("properties", {})
    if with_optional:
        for name in ("title", "location"):
            if name in properties:
                params[name] = "测试内容"
    if with_action:
        params["actionId"] = "event.support.test"
    return _instantiate(template_id, bindings, params)


def _standalone_images(root: Nested2Node) -> list[Nested2Node]:
    # 环内小图标不是独立右侧图标，不将其放大到 24vp。
    if any(child.component_type == "Progress" for child in root.children):
        return []
    images = [root] if root.component_type == "Image" else []
    for child in root.children:
        images.extend(_standalone_images(child))
    return images


@pytest.mark.parametrize("template_id", tuple(_SUPPORT_PRIMARY_TEXT_INDEXES))
@pytest.mark.parametrize("with_optional", (False, True))
@pytest.mark.parametrize("with_action", (False, True))
def test_support_ux_spacing_typography_and_right_icon(
    template_id: str, with_optional: bool, with_action: bool,
) -> None:
    root = _support_ux_root(template_id, with_optional, with_action)
    options = root.values[0]
    assert isinstance(options, dict)
    padding = options.get("padding")
    assert isinstance(padding, dict)
    assert padding.get("left") == padding.get("right") == 8

    # 旧覆盖层中的空 Text 仅提供点击命中区域，不属于主辅信息。
    texts = [node for node in _nodes(root, "Text") if node.values[0] != ""]
    primary_indexes = _SUPPORT_PRIMARY_TEXT_INDEXES.get(template_id)
    assert primary_indexes is not None
    if not with_optional and template_id in _SUPPORT_OPTIONAL_TEMPERATURE_TEXT_TEMPLATES:
        primary_indexes = (0,)
    fallback_only = template_id == "WeatherOverviewTravelSupport@1" and not with_optional
    if fallback_only:
        assert len(texts) == 1
        fallback_styles = texts[0].values[-1]
        assert isinstance(fallback_styles, dict)
        assert fallback_styles.get("fontSize") == 14
    elif template_id not in _SUPPORT_OPTIONAL_SECONDARY_TEXT_TEMPLATES:
        assert len(texts) > len(primary_indexes)
    for index, node in enumerate(texts):
        if fallback_only:
            continue
        styles = node.values[-1]
        assert isinstance(styles, dict)
        primary = index in primary_indexes
        subtitle_size = 10 if template_id in {
            "CountdownOverviewSupport@1",
            "CountdownOverviewTravelSupport@1",
            "WeatherOverviewDaily2TravelSupport@1",
            "WeatherOverviewTravelSupport@1",
        } else 12
        font_size = 14 if primary else subtitle_size
        assert styles.get("fontSize") == font_size
        if primary:
            assert styles.get("fontWeight") == 700
        else:
            # 电量/天气升级模板的辅助行已改为 500 中等字重。
            assert styles.get("fontWeight") in (400, 500)
        assert styles.get("minFontSize", font_size) == font_size

    for node in _standalone_images(root):
        styles = node.values[-1]
        assert isinstance(styles, dict)
        assert styles.get("width") == styles.get("height") == 24
        assert styles.get("flexShrink") == 0
    assert _serialize_node(root).count('"onClick":') == int(with_action)


def test_support_ux_contract_covers_every_registered_support() -> None:
    supports = {
        name for name in get_cardplan_registry().templates if name.endswith("Support@1")
    }
    assert supports == set(_SUPPORT_PRIMARY_TEXT_INDEXES)


@pytest.mark.parametrize(("template_id", "binding", "unit", "caption"), (
    ("ActivityOverviewSupport@1", "steps", "步", "每日步数"),
    ("HeartRateOverviewSupport@1", "average", "次/分钟", "运动平均心率"),
))
def test_health_support_combines_numeric_value_and_unit_with_runtime_binding(
    template_id: str, binding: str, unit: str, caption: str,
) -> None:
    root = _support_ux_root(template_id, with_optional=True, with_action=False)
    texts = _nodes(root, "Text")
    assert len(texts) == 2
    assert texts[0].values[0] == "{{ ${/data/support/" + binding + "} + '" + unit + "' }}"
    assert texts[1].values[0] == caption


@pytest.mark.parametrize("title", (None, "运动会倒计时", "倒计时与天气"))
def test_countdown_support_prioritizes_remaining_days(title: str | None) -> None:
    params = {"title": title} if title is not None else {}
    root = _instantiate("CountdownOverviewSupport@1", {"days": "${data.countdown.days}"}, params)
    texts = _nodes(root, "Text")
    assert len(texts) == 2
    assert texts[0].values[0] == "{{ '剩余' + ${/data/countdown/days} + '天' }}"
    assert texts[1].values[0] == (title if title is not None else "倒计时")
    # 显式主行容器隔离下一行标题，避免其中的“天”被误识别为数值单位。
    assert root.children[0].children[0].component_type == "Row"
    assert len(root.children[0].children[0].children) == 1


@pytest.mark.parametrize("template_id", (
    "BatteryOverviewSupport@1", "BluetoothDeviceOverviewChargeSupport@1",
))
def test_battery_support_places_progress_to_the_right_of_text(template_id: str) -> None:
    root = _support_ux_root(template_id, with_optional=True, with_action=False)
    content = root.children[0]
    assert [node.component_type for node in content.children] == ["Column", "Stack"]
    styles = content.values[0]
    assert isinstance(styles, dict)
    assert styles.get("justifyContent") == "spaceBetween"


def test_heart_rate_support_keeps_two_direct_text_lines_without_forced_width() -> None:
    root = _support_ux_root("HeartRateOverviewSupport@1", with_optional=True, with_action=False)
    content = root.children[0]
    assert content.component_type == "Column"
    assert [node.component_type for node in content.children] == ["Text", "Text"]
    for node in content.children:
        styles = node.values[-1]
        assert isinstance(styles, dict)
        assert styles.get("width") is None
        assert styles.get("maxLines") == 1
        assert styles.get("textOverflow") == "ellipsis"
        assert styles.get("constraintSize") == {"minWidth": 0, "minHeight": 0}


@pytest.mark.parametrize(("template_id", "ring_size", "icon_size"), (
    ("BatteryOverviewSupport@1", 40, 16),
    ("BluetoothDeviceOverviewChargeSupport@1", 40, 16),
    ("BluetoothDeviceOverviewConnectionSupport@1", 40, 16),
    ("ResourceUsageOverviewSupport@1", 44, 20),
))
def test_support_ux_preserves_progress_and_inner_icon_sizes(
    template_id: str, ring_size: int, icon_size: int,
) -> None:
    root = _support_ux_root(template_id, with_optional=True, with_action=False)
    progress = _nodes(root, "Progress")
    images = _nodes(root, "Image")
    assert len(progress) == len(images) == 1
    progress_styles = progress[0].values[-1]
    icon_styles = images[0].values[-1]
    assert isinstance(progress_styles, dict)
    assert isinstance(icon_styles, dict)
    assert progress_styles.get("width") == progress_styles.get("height") == ring_size
    assert icon_styles.get("width") == icon_styles.get("height") == icon_size


def test_support_inventory_removes_deleted_templates() -> None:
    registry = get_cardplan_registry()
    supports = {key for key in registry.templates if key.endswith("Support@1")}
    assert len(supports) == 22
    assert not supports.intersection({
        "ScheduleOverviewSupport@1", "HeartRateOverviewUpdatedSupport@1",
        "HeartRateOverviewIconSupport@1", "HeartRateOverviewUpdatedIconSupport@1",
    })
    assert "BluetoothDeviceOverviewChargeSupport@1" in supports
    assert "WeatherOverviewTemperaturecoldLevelSupport@1" in supports


@pytest.mark.parametrize(("template_id", "primary", "secondary"), _CALENDAR_SUPPORTS)
@pytest.mark.parametrize("with_icon", (False, True))
def test_calendar_support_fields_and_optional_icon(
    template_id: str, primary: str, secondary: tuple[str, ...], with_icon: bool,
) -> None:
    definition = get_cardplan_registry().require_template(template_id)
    assert definition.primary_data == (primary,)
    assert definition.secondary_data == secondary
    bindings = {}
    for name, binding in definition.bindings.items():
        if binding.path != "/events/0/dtEnd":
            bindings[name] = "${data.calendar" + binding.path.replace("/", ".") + "}"
    params: dict[str, str] = {}
    if with_icon:
        # 时间 Support 的图标仅在绑定事件时显示。
        params["actionId"] = "event.support.test"
        params["calendarIcon"] = "resources/base/media/calendar_fill.svg"
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
def test_battery_support_requires_numeric_percent_for_40vp_ring(
    percent_fields: tuple[str, ...],
) -> None:
    bindings = {"charging": "${data.phoneBattery.chargingStatusDesc}"}
    for name in percent_fields:
        bindings[name] = "${data.phoneBattery." + name + "}"
    definition = get_cardplan_registry().require_template("BatteryOverviewSupport@1")
    assert definition.primary_data == ("/batterySOC",)
    # 充电状态与电池温度降为可选：缺失时模板只保留电量行，电量环仍由数值电量驱动。
    assert definition.secondary_data == ()
    assert definition.optional_data == (
        "/chargingStatusDesc", "/batterySOCText", "/batteryTemperatureText",
    )
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
        assert options.get("width") == options.get("height") == 40
        assert options.get("value") == "${data.phoneBattery.percent}"


@pytest.mark.parametrize("with_charging", (False, True))
def test_battery_support_aux_line_prefers_charging_over_temperature(
    with_charging: bool,
) -> None:
    bindings = {
        "percent": "${data.phoneBattery.percent}",
        "temperature": "${data.phoneBattery.temperature}",
    }
    if with_charging:
        bindings["charging"] = "${data.phoneBattery.chargingStatusDesc}"
    root = _instantiate("BatteryOverviewSupport@1", bindings)
    texts = _nodes(root, "Text")
    assert len(texts) == 2
    # 辅行为编译期分支：充电状态存在时优先展示，温度只在充电状态缺失时回退展示。
    assert texts[1].values[0] == (
        "${data.phoneBattery.chargingStatusDesc}" if with_charging
        else "{{ '电池 ' + ${/data/phoneBattery/temperature} }}"
    )


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
        "BluetoothDeviceOverviewConnectionSupport@1": ["icon_earphone.svg"],
        "HeartRateOverviewSupport@1": ["heart_fill.svg"],
        "WeatherOverviewTemperatureSupport@1": [],
        "WeatherOverviewTemperatureUvSupport@1": [],
        "WeatherOverviewTemperaturecoldLevelSupport@1": [],
        "BatteryOverviewSupport@1": ["icon_phone.svg"],
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


@pytest.mark.parametrize(
    ("missing", "expect_error"),
    (
        (None, False),
        ("batteryLevel", False),
        ("chargingStatusDesc", True),
    ),
)
def test_charge_support_requires_trusted_case_status_only(
    missing: str | None, expect_error: bool,
) -> None:
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
    if expect_error:
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


def test_battery_status_support_state_is_independent_of_soc_facts() -> None:
    task = TaskSpec(
        userQuery="手机和耳机充电状态", size="2x2",
        dataModelSchema={"data": {"phoneBattery": {
            "chargingStatusDesc": {"type": "string", "sampleValue": "未充电"},
            "pluggedTypeDesc": {"type": "string", "sampleValue": "未连接充电器"},
        }}},
    )
    _validate_provider_template_state(
        "BatteryOverviewStatusSupport@1", "default", task,
        business_names={"BatteryOverview", "BluetoothDeviceOverview"},
    )
