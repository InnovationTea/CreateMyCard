"""应用时长下线后，其它业务模板仍可加载和检索。"""

from __future__ import annotations

import json

import pytest

from config.config import get_settings
from models.generation import CandidateDataBinding, TaskSpec
from services.template_generation.engine.cardplan.preview_dataset import (
    _build_data_schema,
    _preview_theme_values,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.cardplan.template_retrieval import (
    TemplateRetrievalQuery,
    retrieve_template_variants,
)


@pytest.mark.parametrize(
    "version", ("app-11.7.5.205_rom-6.0", "app-11.7.7.300_rom-7.0")
)
def test_app_usage_is_absent_from_runtime_capability_snapshots(version: str) -> None:
    path = get_settings().data_root / "capabilities" / version / "data_capabilities.json"
    capabilities = json.loads(path.read_text(encoding="utf-8"))

    assert all(item.get("id") != "GetAppUsageDuration" for item in capabilities)


@pytest.mark.parametrize("enable_fusion_ball", (False, True))
def test_retired_app_usage_does_not_block_weather_search(enable_fusion_ball: bool) -> None:
    registry = CardPlanRegistry(enable_fusion_ball=enable_fusion_ball)
    assert "com.huawei.app-usage.cli" not in registry.provider_bundles
    assert "AppUsageOverview" not in registry.ux_business_components
    assert "digital-wellbeing-neutral-dark" not in registry.themes
    assert not any(name.startswith("AppUsageOverview") for name in registry.templates)
    for theme in registry.themes.values():
        assert "GetAppUsageDuration" not in theme.supported_capability_ids

    definition = registry.require_template("WeatherOverviewFull@1")
    task = TaskSpec(
        userQuery="显示温度和天气情况",
        size="2x2",
        dataModelSchema=_build_data_schema(definition),
    )
    fields = ("/current/temperatureText", "/current/condition")
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        writeResultTo="/data/weather",
        candidateOutputFields=list(fields),
    )
    query = TemplateRetrievalQuery(
        themeId="family-weather-care-blue",
        requiredOutputFieldsByCapability={"ViewWeather": fields},
    )
    selection = retrieve_template_variants(
        query,
        task,
        registry,
        (binding,),
        {"suggestSize": "2x2", "dataBindings": [binding.model_dump(mode="json")]},
    )

    assert any(
        "WeatherOverviewFull@1" in candidate.available_template_ids
        for candidate in selection.component_candidates
    )


def test_preview_without_compatible_theme_reports_the_template(monkeypatch) -> None:
    registry = CardPlanRegistry()
    definition = registry.require_template("WeatherOverviewFull@1")
    monkeypatch.setattr(registry, "themes", {})

    with pytest.raises(ValueError, match="No compatible preview theme: WeatherOverviewFull@1"):
        _preview_theme_values(definition, registry)
