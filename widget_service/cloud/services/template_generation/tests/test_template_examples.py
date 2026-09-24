"""模版场景示例页签的输入、事件和批跑回归。

确定性解析契约已固化为场景金样（Layer C，冻结解析结果而非 fixture 本体）：
- template_examples__action_display_label：动作展示文案的缺省回退与显式覆盖；
- template_examples__resolved_requests：8 个示例经正式画廊链路解析出的请求
  逐项冻结（case 元数据、目标模板、场景/布局期望、标题、绑定参数与字段、
  事件动作 call/args、样例覆盖、userQuery、素材清单）；
- template_examples__fixture_pins：示例依赖的日历事实与省电事件注册参数
  （switchFlag=0）等门禁元数据；
- template_examples__weather_hero_optional_fields：WeatherOverviewHero 蓝图
  按可选字段绑定与否的序列化树分支矩阵；
- template_examples__sample_override_invalid_paths：非法数组路径的
  ValueError 报文与原 TaskSpec 不变性。
过程类测试保留为内联：清单追加的幂等与原始请求字节不变、批跑服务交互
（8/8 成功）、未注册事件/素材的 monkeypatch 失败路径、可信样例覆盖不改写
原 TaskSpec 的过程不变量。
"""

import json
import tempfile
from datetime import date
from pathlib import Path

import pytest

from models.generation import EventAction, TaskSpec
from services.template_generation.engine.cardplan.compiler import _instantiate_blueprint
from services.template_generation.engine.cardplan.prompt import action_bindings
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.pipeline import _with_trusted_sample_overrides
from services.template_generation.test_support import provider_gallery as gallery
from services.template_generation.test_support.golden_scenarios import (
    assert_golden_scenario,
    scenario,
)
from services.template_generation.test_support.template_examples import (
    EXAMPLE_PROVIDER_ID,
    append_template_examples,
    load_template_examples,
)
from services.template_generation.tests.test_provider_gallery_batch import _GalleryService


# --------------------------------------------------------------------------
# 场景：动作展示文案
# --------------------------------------------------------------------------


@scenario("template_examples__action_display_label")
def _build_action_display_label() -> dict[str, str]:
    event = EventAction(id="event.open.weather", call="clickToDeeplink", args={})
    task = TaskSpec(userQuery="查看详情", size="2x2", dataModelSchema={}, eventCandidates=[event])
    default_label = action_bindings(task)[0].display_label
    explicit_task = task.model_copy(update={"eventCandidates": [
        event.model_copy(update={"displayLabel": "查看天气"})
    ]})
    return {
        "default": default_label,
        "explicit": action_bindings(explicit_task)[0].display_label,
    }


# --------------------------------------------------------------------------
# 场景：示例请求的解析结果（冻结解析输出，不冻结 fixture 本体）
# --------------------------------------------------------------------------


@scenario("template_examples__resolved_requests")
def _build_resolved_requests() -> dict[str, object]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        gallery.write_gallery_input_dataset(root)
        manifest = append_template_examples(root)
        provider = manifest.providers[-1]
        catalog: dict[str, object] = {
            "providerId": provider.providerId,
            "providerName": provider.providerName,
            "caseCount": len(provider.cases),
            "cases": {},
        }
        cases: dict[str, object] = catalog["cases"]  # type: ignore[assignment]
        for example, case in zip(load_template_examples(), provider.cases):
            envelope = json.loads((root / case.requestFile).read_text(encoding="utf-8"))
            request = gallery._request_from_envelope(envelope)
            bindings = request.candidateDataBindings or []
            binding = bindings[0]
            events = request.candidateEventCandidates or []
            cases[example.id] = {
                "caseId": case.caseId,
                "targetTemplateId": case.targetTemplateId,
                "scenarioId": case.scenarioId,
                "expectedLayout": case.expectedLayout,
                "prdVer": case.prdVer,
                "requestTitle": request.title,
                "bindingCount": len(bindings),
                "writeResultTo": binding.writeResultTo,
                "bindingArguments": binding.arguments,
                "candidateOutputFields": binding.candidateOutputFields,
                "events": [
                    {
                        "capabilityId": event.capabilityId,
                        "call": event.action.call,
                        "args": event.action.args,
                    }
                    for event in events
                ],
                "sampleOverrides": gallery._gallery_sample_overrides_from_envelope(envelope),
                "userQuery": request.userQuery,
                "candidateAssetIds": request.candidateAssetIds,
            }
        return catalog


# --------------------------------------------------------------------------
# 场景：示例依赖的日历事实与注册事件参数
# --------------------------------------------------------------------------


@scenario("template_examples__fixture_pins")
def _build_fixture_pins() -> dict[str, object]:
    registered = gallery._load_event_capabilities(gallery._CAPABILITY_ROOT)
    power = registered.get("event.setPowerSavingMode")
    action = power.get("actionTemplate") if isinstance(power, dict) else None
    args = action.get("args") if isinstance(action, dict) else None
    return {
        "calendarFacts": {
            "friday20260925Weekday": date(2026, 9, 25).weekday(),
            "countdownSpanDays": (date(2026, 12, 13) - date(2026, 9, 9)).days,
        },
        "powerSavingActionArgs": args,
    }


# --------------------------------------------------------------------------
# 场景：WeatherOverviewHero 可选字段绑定分支
# --------------------------------------------------------------------------

_WEATHER_HERO_OPTIONAL_CASES: dict[str, tuple[str, ...]] = {
    "base": (),
    "air_quality": ("airQuality",),
    "cold_level": ("coldLevel",),
    "air_quality_cold_level": ("airQuality", "coldLevel"),
}


@scenario("template_examples__weather_hero_optional_fields")
def _build_weather_hero_optional_fields() -> dict[str, object]:
    definition = get_cardplan_registry().require_template("WeatherOverviewHero@1")
    cases: dict[str, dict[str, bool]] = {}
    for key, extra_fields in _WEATHER_HERO_OPTIONAL_CASES.items():
        bindings = {
            "temperature": "${data.weather.current.temperatureText}",
            "condition": "${data.weather.current.condition}",
        }
        for name in extra_fields:
            bindings[name] = "${data.weather.current." + name + "}"
        root = _instantiate_blueprint(
            definition.variants[0].root, {}, bindings,
            {"primaryColor": "#FF000000", "supportContentColor": "#99000000"},
        )
        serialized = str(root)
        cases[key] = {name: name in serialized for name in ("airQuality", "coldLevel")}
    return {
        "airQualityOptional": "/current/airQuality" in definition.optional_data,
        "cases": cases,
    }


# --------------------------------------------------------------------------
# 场景：非法样例覆盖路径的报错与原对象不变性
# --------------------------------------------------------------------------

_INVALID_OVERRIDE_PATHS = (
    "/data/calendar/events/1/title", "/data/calendar/events/-1/title",
    "/data/calendar/events/01/title", "/data/calendar/events/0/unknown",
    "/data/calendar/events/0", "/outside/calendar/events/0/title",
)


@scenario("template_examples__sample_override_invalid_paths")
def _build_sample_override_invalid_paths() -> dict[str, object]:
    spec = TaskSpec(userQuery="演示", size="2x2", dataModelSchema={
        "data": {"calendar": {"events": [
            {"title": {"type": "string", "sampleValue": "原会议"}},
        ]}},
    })
    original = spec.model_dump_json()
    errors: dict[str, dict[str, str]] = {}
    for path in _INVALID_OVERRIDE_PATHS:
        try:
            _with_trusted_sample_overrides(spec, {path: "替换"})
            errors[path] = {"error": "NO_ERROR"}
        except ValueError as error:
            errors[path] = {"errorType": type(error).__name__, "message": str(error)}
    return {"specUnchanged": spec.model_dump_json() == original, "errors": errors}


# --------------------------------------------------------------------------
# 保留的过程/交互测试
# --------------------------------------------------------------------------


def test_examples_append_idempotently_without_changing_original_requests(tmp_path: Path) -> None:
    before = gallery.write_gallery_input_dataset(tmp_path)
    original = {}
    for provider in before.providers:
        for case in provider.cases:
            original[case.requestFile] = (tmp_path / case.requestFile).read_bytes()
    first = append_template_examples(tmp_path)
    second = append_template_examples(tmp_path)
    assert first == second
    assert second.providers[:-1] == before.providers
    for path, value in original.items():
        assert (tmp_path / path).read_bytes() == value


@pytest.mark.asyncio
async def test_example_runner_uses_public_service_and_keeps_all_eight_cases(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    gallery.write_gallery_input_dataset(inputs)
    append_template_examples(inputs)
    service = _GalleryService()
    summary = await gallery.ProviderGalleryBatchRunner(service).run(
        inputs, tmp_path / "output", provider_ids={EXAMPLE_PROVIDER_ID}
    )
    assert summary.total == 8
    assert summary.success == 8
    assert summary.failed == 0
    assert len(service.requests) == 8
    assert len(list((tmp_path / "output" / "providers").rglob("*.json"))) == 8


def test_example_unknown_event_fails_without_publishing_manifest(
    tmp_path: Path, monkeypatch,
) -> None:
    gallery.write_gallery_input_dataset(tmp_path)
    original = (tmp_path / "manifest.json").read_bytes()
    monkeypatch.setattr(gallery, "_load_event_capabilities", lambda _root: {})
    with pytest.raises(ValueError, match="示例事件未注册"):
        append_template_examples(tmp_path)
    assert (tmp_path / "manifest.json").read_bytes() == original


def test_example_unknown_asset_fails_without_publishing_manifest(
    tmp_path: Path, monkeypatch,
) -> None:
    gallery.write_gallery_input_dataset(tmp_path)
    original = (tmp_path / "manifest.json").read_bytes()
    monkeypatch.setattr(gallery, "_load_asset_capabilities", lambda _root: {})
    with pytest.raises(ValueError, match="示例素材未注册"):
        append_template_examples(tmp_path)
    assert (tmp_path / "manifest.json").read_bytes() == original


def test_sample_overrides_support_array_items_without_mutating_original() -> None:
    spec = TaskSpec(userQuery="演示", size="2x2", dataModelSchema={
        "data": {"calendar": {"events": [
            {"title": {"type": "string", "sampleValue": "原会议"}},
            {"title": {"type": "string", "sampleValue": "另一场会议"}},
        ]}},
    })
    original = spec.model_dump_json()
    changed = _with_trusted_sample_overrides(
        spec, {"/data/calendar/events/0/title": "UI需求评审会"}
    )
    assert spec.model_dump_json() == original
    serialized = changed.model_dump_json()
    assert "UI需求评审会" in serialized
    assert "另一场会议" in serialized
    assert "原会议" not in serialized


# --------------------------------------------------------------------------
# 场景金样断言入口
# --------------------------------------------------------------------------


@pytest.mark.parametrize("scenario_id", [
    "template_examples__action_display_label",
    "template_examples__resolved_requests",
    "template_examples__fixture_pins",
    "template_examples__weather_hero_optional_fields",
    "template_examples__sample_override_invalid_paths",
])
def test_template_examples_golden_scenarios(scenario_id: str) -> None:
    assert_golden_scenario(scenario_id)
