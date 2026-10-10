"""Half/Compact selection must preserve complete business candidates."""

from types import SimpleNamespace

import pytest

from services.template_generation.engine.advanced.models import TemplateComponentCandidate
from services.template_generation.engine.cardplan import compiler
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.cardplan.template_retrieval import (
    _prefer_eligible_template,
    _prefer_half_compact_pair,
)


@pytest.mark.parametrize("reverse", [False, True])
def test_half_compact_pair_is_ordered_without_mixing_businesses(reverse):
    half = TemplateComponentCandidate(
        componentId="BluetoothDeviceOverview",
        availableTemplateIds=("BluetoothDeviceOverviewTripleBatteryWideHalf@1",),
    )
    compact = TemplateComponentCandidate(
        componentId="BatteryOverview",
        availableTemplateIds=("BatteryOverviewPhoneTextCompact@1", "BatteryOverviewHero@1"),
    )
    source = (compact, half) if reverse else (half, compact)
    selected = _prefer_half_compact_pair(source)
    assert selected[0].component_id == "BluetoothDeviceOverview"
    assert selected[1].available_template_ids == ("BatteryOverviewPhoneTextCompact@1",)
    assert len(compact.available_template_ids) == 2


def test_existing_hero_pair_is_unchanged():
    source = (
        TemplateComponentCandidate(
            componentId="BatteryOverview", availableTemplateIds=("BatteryOverviewHero@1",)
        ),
        TemplateComponentCandidate(
            componentId="BluetoothDeviceOverview",
            availableTemplateIds=("BluetoothDeviceOverviewHero@1",),
        ),
    )
    assert _prefer_half_compact_pair(source) is source


def test_q079_declarations_match_original_inputs():
    registry = CardPlanRegistry()
    phone = registry.require_template("BatteryOverviewPhoneTextCompact@1")
    assert phone.primary_data == ("/batterySOCText",)
    assert phone.secondary_data == ()
    assert phone.optional_data == ()
    half = registry.require_template("BluetoothDeviceOverviewTripleBatteryWideHalf@1")
    assert "/isConnected" in half.optional_data
    assert set(half.primary_data) == {"/batteryLevel", "/leftBatteryLevel", "/rightBatteryLevel"}


def test_workout_type_duration_compact_does_not_require_calories():
    registry = CardPlanRegistry()
    template = registry.require_template("WorkoutOverviewTypeDurationCompact@1")
    assert set(template.primary_data) == {"/exerciseTypeName", "/exerciseDurationText"}
    assert template.secondary_data == ()
    assert template.optional_data == ()
    assert template.asset_parameter_semantic_tags.get("sourceIcon") is not None


def test_meeting_entry_only_prefers_an_eligible_candidate():
    template = "ScheduleOverviewMeetingEntryHero@1"
    calendar = TemplateComponentCandidate(
        componentId="CalendarOverview",
        availableTemplateIds=(template, "ScheduleOverviewLocationHero@1"),
    )
    other = TemplateComponentCandidate(
        componentId="BluetoothDeviceOverview",
        availableTemplateIds=("BluetoothDeviceOverviewCaseConnectionHero@1",),
    )
    selected = _prefer_eligible_template((calendar, other), template)
    assert selected[0].available_template_ids == (template,)
    assert selected[1] is other
    assert _prefer_eligible_template((other,), template) == (other,)


def test_case_settings_preference_preserves_phone_candidate():
    template = "BluetoothDeviceOverviewCaseSettingsHero@1"
    earphone = TemplateComponentCandidate(
        componentId="BluetoothDeviceOverview",
        availableTemplateIds=(template, "BluetoothDeviceOverviewStatusHero@1"),
    )
    phone = TemplateComponentCandidate(
        componentId="BatteryOverview",
        availableTemplateIds=("BatteryOverviewHero@1",),
    )
    selected = _prefer_eligible_template((earphone, phone), template)
    assert selected[0].available_template_ids == (template,)
    assert selected[1] is phone


@pytest.mark.parametrize("status", ["未充电", None])
def test_case_settings_requires_only_case_charging_status(monkeypatch, status):
    monkeypatch.setattr(
        compiler,
        "extract_bluetooth_device_overview_facts",
        lambda _schema: SimpleNamespace(case_charging_status=status),
    )
    task = SimpleNamespace(dataModelSchema={})
    if status is None:
        with pytest.raises(compiler.TerselConversionError, match="trusted case status"):
            compiler._validate_provider_template_state(
                "BluetoothDeviceOverviewCaseSettingsHero@1",
                "caseSettingsHero",
                task,
                business_names={"BluetoothDeviceOverview", "BatteryOverview"},
            )
    else:
        compiler._validate_provider_template_state(
            "BluetoothDeviceOverviewCaseSettingsHero@1",
            "caseSettingsHero",
            task,
            business_names={"BluetoothDeviceOverview", "BatteryOverview"},
        )
