from __future__ import annotations

from typing import Any

from services.template_generation.tests.eval_fixture_migration import migrate_case


def _case(case_id: str, capability_id: str, root: str) -> dict[str, Any]:
    return {
        "id": case_id,
        "expectedMatched": True,
        "candidateDataBindings": [
            {
                "capabilityId": capability_id,
                "writeResultTo": root,
                "candidateOutputFields": ["/exerciseTypeName"],
            }
        ],
        "taskSpecFieldTypesByCapability": {capability_id: {"/exerciseTypeName": "string"}},
    }


def test_migration_updates_current_provider_data_roots() -> None:
    for old, expected in (
        ("/data/appUsage", "/data/appUsageStats"),
        ("/data/battery", "/data/phoneBattery"),
        ("/data/health", "/data/healthSport"),
    ):
        migrated = migrate_case(_case("TRE-001", "GetHealthAndSportSummary", old))
        assert migrated["candidateDataBindings"][0]["writeResultTo"] == expected
        assert migrated["expectedPipelineStage"] == "retrieval"


def test_migration_adds_new_workout_required_field() -> None:
    migrated = migrate_case(_case("TRE-066", "GetHealthAndSportSummary", "/data/health"))

    binding = migrated["candidateDataBindings"][0]
    assert binding["writeResultTo"] == "/data/healthSport"
    assert "/exerciseEndTimeText" in binding["candidateOutputFields"]
    assert (
        migrated["taskSpecFieldTypesByCapability"]["GetHealthAndSportSummary"][
            "/exerciseEndTimeText"
        ]
        == "string"
    )


def test_migration_marks_non_retrieval_cases_explicitly() -> None:
    rejected = migrate_case(_case("TRE-026", "GetCalendarEvents", "/data/calendar"))
    unsupported = migrate_case(_case("TRE-081", "GetSystemMemInfo", "/data/systemMem"))

    assert rejected["expectedPipelineStage"] == "preflight_reject"
    assert unsupported["expectedPipelineStage"] == "unsupported_capability"
    assert unsupported["expectedMatched"] is False


def test_migration_translates_legacy_template_variant_to_current_template_id() -> None:
    case = _case("TRE-001", "ViewWeather", "/data/weather")
    case.update({"expectedTemplateId": "WeatherOverview@1", "expectedVariantName": "hero"})

    migrated = migrate_case(case)

    assert migrated["expectedTemplateId"] == "WeatherOverviewFull@1"
    assert migrated["expectedVariantName"] == "default"
