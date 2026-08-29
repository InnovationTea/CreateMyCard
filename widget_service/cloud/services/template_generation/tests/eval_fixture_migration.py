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
_TEMPLATE_IDS = {
    ("WeatherOverview@1", "hero"): "WeatherOverviewHero@1",
    ("ScheduleOverview@1", "nextEvent"): "ScheduleOverviewNextEvent@1",
    ("ScheduleOverview@1", "nextEventLocation"): "ScheduleOverviewNextEventLocation@1",
    ("DateOverview@1", "dateHero"): "DateOverviewDateHero@1",
    ("BluetoothDeviceOverview@1", "connection"): "BluetoothDeviceOverviewConnection@1",
    ("BluetoothDeviceOverview@1", "earbuds"): "BluetoothDeviceOverviewEarbuds@1",
    ("BluetoothDeviceOverview@1", "earbudPair"): "BluetoothDeviceOverviewEarbudPair@1",
    ("BluetoothDeviceOverview@1", "earbudsFullWide"): "BluetoothDeviceOverviewEarbudsFullWide@1",
    ("BatteryOverview@1", "chargingPhone"): "BatteryOverviewChargingPhone@1",
    ("BatteryOverview@1", "charging"): "BatteryOverviewCharging@1",
    ("BatteryOverview@1", "chargingWide"): "BatteryOverviewChargingWide@1",
    ("CountdownOverview@1", "countdown"): "CountdownOverview@1",
    ("AppUsageOverview@1", "singleApp"): "AppUsageOverviewSingleApp@1",
    ("AppUsageOverview@1", "singleAppWide"): "AppUsageOverviewSingleAppWide@1",
    ("ActivityOverview@1", "steps"): "ActivityOverviewSteps@1",
    ("ActivityOverview@1", "dailySummary"): "ActivityOverviewDailySummary@1",
    ("ActivityOverview@1", "dailySummaryWide"): "ActivityOverviewDailySummaryWide@1",
    ("WorkoutOverview@1", "latest"): "WorkoutOverview@1",
    ("HeartRateOverview@1", "hero"): "HeartRateOverviewHero@1",
    ("HeartRateOverview@1", "heroUpdated"): "HeartRateOverviewHeroUpdated@1",
    ("SleepOverview@1", "duration"): "SleepOverviewDuration@1",
    ("SleepOverview@1", "insufficient"): "SleepOverviewInsufficient@1",
    ("SleepOverview@1", "schedule"): "SleepOverviewSchedule@1",
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
        template_id = (
            _TEMPLATE_IDS.get((legacy_template_id, legacy_variant_name))
            if isinstance(legacy_template_id, str) and isinstance(legacy_variant_name, str)
            else None
        )
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
