"""Migrate the legacy retrieval evaluation fixture to the current contracts.

This is intentionally test-only: provider manifests and device capability data
remain owned by the target branch.  It lets an external legacy JSONL fixture be
updated reproducibly before it is used for an end-to-end evaluation.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

_DATA_ROOTS = {
    "/data/appUsage": "/data/appUsageStats",
    "/data/battery": "/data/phoneBattery",
    "/data/health": "/data/healthSport",
}
_PREFLIGHT_REJECT_CASE_IDS = frozenset(
    {
        "TRE-026",
        "TRE-027",
        "TRE-036",
        "TRE-037",
        "TRE-042",
        "TRE-052",
        "TRE-059",
        "TRE-060",
        "TRE-074",
        "TRE-075",
    }
)
_UNSUPPORTED_CAPABILITY_CASE_IDS = frozenset({"TRE-081", "TRE-082", "TRE-086"})
_WORKOUT_END_TIME_CASE_IDS = frozenset({"TRE-066", "TRE-079"})
_WORKOUT_END_TIME = "/exerciseEndTimeText"
_REMOVED_TEMPLATE_VARIANTS = frozenset(
    {
        ("DateOverview@1", "dateHero"),
        ("BluetoothDeviceOverview@1", "connection"),
        ("BluetoothDeviceOverview@1", "earbuds"),
    }
)
_TEMPLATE_IDS = {
    ("WeatherOverview@1", "hero"): "WeatherOverviewFull@1",
    ("ScheduleOverview@1", "nextEvent"): "ScheduleOverviewNextEventLocationFull@1",
    ("ScheduleOverview@1", "nextEventLocation"): "ScheduleOverviewNextEventLocationFull@1",
    ("BluetoothDeviceOverview@1", "earbudPair"): "BluetoothDeviceOverviewEarbudPairFull@1",
    ("BluetoothDeviceOverview@1", "earbudsFullWide"): "BluetoothDeviceOverviewCompleteWideFull@1",
    ("BatteryOverview@1", "chargingPhone"): "BatteryOverviewCompact@1",
    ("BatteryOverview@1", "charging"): "BatteryOverviewFull@1",
    ("BatteryOverview@1", "chargingWide"): "BatteryOverviewWideFull@1",
    ("CountdownOverviewFull@1", "countdown"): "CountdownOverviewFull@1",
    ("AppUsageOverview@1", "singleApp"): "AppUsageOverviewFull@1",
    ("AppUsageOverview@1", "singleAppWide"): "AppUsageOverviewWideFull@1",
    ("ActivityOverview@1", "steps"): "ActivityOverviewStepsFull@1",
    ("ActivityOverview@1", "dailySummary"): "ActivityOverviewDailySummaryFull@1",
    ("ActivityOverview@1", "dailySummaryWide"): "ActivityOverviewDailySummaryWideFull@1",
    ("WorkoutOverviewFull@1", "latest"): "WorkoutOverviewFull@1",
    ("HeartRateOverview@1", "hero"): "HeartRateOverviewFull@1",
    ("HeartRateOverview@1", "heroUpdated"): "HeartRateOverviewUpdatedFull@1",
    ("SleepOverview@1", "duration"): "SleepOverviewDurationFull@1",
    ("SleepOverview@1", "insufficient"): "SleepOverviewInsufficientFull@1",
    ("SleepOverview@1", "schedule"): "SleepOverviewScheduleWideFull@1",
}


def migrate_case(case: dict[str, Any]) -> dict[str, Any]:
    """Return one current-contract evaluation case without mutating input."""
    migrated = copy.deepcopy(case)
    case_id = str(migrated["id"])
    for binding in migrated["candidateDataBindings"]:
        old_root = binding.get("writeResultTo")
        if old_root in _DATA_ROOTS:
            binding["writeResultTo"] = _DATA_ROOTS[old_root]

    if case_id in _WORKOUT_END_TIME_CASE_IDS:
        binding = migrated["candidateDataBindings"][0]
        fields = binding["candidateOutputFields"]
        if _WORKOUT_END_TIME not in fields:
            fields.append(_WORKOUT_END_TIME)
        types = migrated["taskSpecFieldTypesByCapability"]["GetHealthAndSportSummary"]
        types[_WORKOUT_END_TIME] = "string"

    if case_id in _PREFLIGHT_REJECT_CASE_IDS:
        migrated["expectedPipelineStage"] = "preflight_reject"
    elif case_id in _UNSUPPORTED_CAPABILITY_CASE_IDS:
        migrated["expectedPipelineStage"] = "unsupported_capability"
        migrated["expectedMatched"] = False
        migrated["expectedTemplateId"] = None
        migrated["expectedVariantName"] = None
    else:
        migrated["expectedPipelineStage"] = "retrieval"
        legacy_template_id = migrated.get("expectedTemplateId")
        legacy_variant_name = migrated.get("expectedVariantName")
        legacy_template_variant: tuple[str, str] | None = None
        if isinstance(legacy_template_id, str) and isinstance(legacy_variant_name, str):
            legacy_template_variant = (legacy_template_id, legacy_variant_name)
        if legacy_template_variant in _REMOVED_TEMPLATE_VARIANTS:
            migrated["expectedMatched"] = False
            migrated["expectedTemplateId"] = None
            migrated["expectedVariantName"] = None
            return migrated
        template_id = _TEMPLATE_IDS.get(legacy_template_variant)
        if template_id is not None:
            migrated["expectedTemplateId"] = template_id
            migrated["expectedVariantName"] = "default"
    return migrated


def migrate_jsonl(source: Path, destination: Path) -> None:
    """Read legacy JSONL and write the migrated current-contract JSONL."""
    cases = [
        migrate_case(json.loads(line))
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    destination.write_text(
        "".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases),
        encoding="utf-8",
    )
