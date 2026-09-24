"""应用时长（GetAppUsageDuration）下线后的残留清零与检索不受阻（场景金样化）。

三类确定性契约已固化为场景金样（Layer C）：

- ``retired_app_usage__capability_absence``：ROM 6.0 / ROM 7.0 两份运行时
  data_capabilities.json 快照里 GetAppUsageDuration 出现的 id 列表（应为空）；
- ``retired_app_usage__weather_search``：fusion 球开/关两个注册表实例下的
  残留集合（provider bundle、业务组件、主题、模板名、主题能力引用，均应
  为空）+ 天气检索解析出的每个组件候选及其可用模板列表（含
  WeatherOverviewFull@1）；
- ``retired_app_usage__preview_theme_error``：注册表无兼容主题时
  _preview_theme_values 的精确错误类型与消息（无错误则以
  ``{"error": "NO_ERROR"}`` 呈现）。

原有内联断言全部迁入金样，本文件仅保留注册与金样比对入口；能力快照、
模板清单或检索策略改动后按 golden 工作流 `check --diff` /
`bless --declared` 复核。
"""

from __future__ import annotations

import json
from typing import Any

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
from services.template_generation.test_support.golden_scenarios import (
    assert_golden_scenario,
    scenario,
)

_CAPABILITY_VERSIONS = ("app-11.7.5.205_rom-6.0", "app-11.7.7.300_rom-7.0")
_RETIRED_CAPABILITY_ID = "GetAppUsageDuration"
_RETIRED_PROVIDER_ID = "com.huawei.app-usage.cli"
_RETIRED_BUSINESS_ID = "AppUsageOverview"
_RETIRED_THEME_ID = "digital-wellbeing-neutral-dark"


@scenario("retired_app_usage__capability_absence")
def _build_capability_absence() -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for version in _CAPABILITY_VERSIONS:
        path = get_settings().data_root / "capabilities" / version / "data_capabilities.json"
        capabilities = json.loads(path.read_text(encoding="utf-8"))
        payload[version] = {
            "retiredCapabilityIds": [
                item.get("id")
                for item in capabilities
                if item.get("id") == _RETIRED_CAPABILITY_ID
            ],
        }
    return payload


def _retired_residue_and_weather_search(enable_fusion_ball: bool) -> dict[str, Any]:
    registry = CardPlanRegistry(enable_fusion_ball=enable_fusion_ball)
    residue = {
        "providerIds": sorted(
            provider_id
            for provider_id in registry.provider_bundles
            if provider_id == _RETIRED_PROVIDER_ID
        ),
        "businessComponentIds": sorted(
            component_id
            for component_id in registry.ux_business_components
            if component_id == _RETIRED_BUSINESS_ID
        ),
        "themeIds": sorted(
            theme_id
            for theme_id in registry.themes
            if theme_id == _RETIRED_THEME_ID
        ),
        "templateIds": sorted(
            template_id
            for template_id in registry.templates
            if template_id.startswith(_RETIRED_BUSINESS_ID)
        ),
        "themesWithRetiredCapability": sorted(
            theme_id
            for theme_id, theme in registry.themes.items()
            if _RETIRED_CAPABILITY_ID in theme.supported_capability_ids
        ),
    }
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
    return {
        "retiredResidue": residue,
        "componentCandidates": {
            candidate.component_id: list(candidate.available_template_ids)
            for candidate in selection.component_candidates
        },
    }


@scenario("retired_app_usage__weather_search")
def _build_weather_search() -> dict[str, Any]:
    return {
        "fusion_off": _retired_residue_and_weather_search(False),
        "fusion_on": _retired_residue_and_weather_search(True),
    }


@scenario("retired_app_usage__preview_theme_error")
def _build_preview_theme_error() -> dict[str, Any]:
    registry = CardPlanRegistry()
    definition = registry.require_template("WeatherOverviewFull@1")
    registry.themes = {}
    try:
        _preview_theme_values(definition, registry)
    except Exception as exc:  # 场景契约即错误类型+消息，捕获后冻结
        return {"errorType": type(exc).__name__, "message": str(exc)}
    return {"error": "NO_ERROR"}


def test_retired_app_usage_scenarios_match_goldens() -> None:
    assert_golden_scenario("retired_app_usage__capability_absence")
    assert_golden_scenario("retired_app_usage__weather_search")
    assert_golden_scenario("retired_app_usage__preview_theme_error")
