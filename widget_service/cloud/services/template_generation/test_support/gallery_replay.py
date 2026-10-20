"""重建失败画廊的受控输入，保留用例身份、不适用原因和原始业务组合。"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from . import provider_gallery as gallery
from .gallery_case_contracts import (
    REQUIRED_ASSET_IDS,
    THREE_DAY_COUNTDOWN_TEMPLATE,
    THREE_DAY_LAYOUT,
    THREE_DAY_WEATHER_TEMPLATE,
    gallery_display_description,
    three_day_weather_content,
)

_DATE_TITLE = "ScheduleOverviewDateTitleFull@1"
_WEATHER_FULL = "WeatherOverviewFull@1"
_PLAYLIST = "BluetoothDeviceOverviewEarbudsChargingWideFull@1"
_UNREACHABLE_BATTERY = "BatteryOverviewPercentLevelHero@1"


def _object(value: dict[str, Any], name: str) -> dict[str, Any]:
    result = value.get(name)
    if not isinstance(result, dict):
        raise ValueError(f"gallery request requires object: {name}")
    return result


def _arguments(capability_id: str) -> dict[str, Any]:
    value = gallery._CAPABILITY_ARGUMENTS.get(capability_id)
    if value is None:
        raise ValueError(f"gallery arguments missing: {capability_id}")
    return deepcopy(value)


def _template_ids(case: gallery.GalleryInputCase) -> list[str]:
    result = list(case.compositionTemplateIds)
    if not result:
        for template_id in (case.targetTemplateId, case.partnerTemplateId):
            if template_id:
                result.append(template_id)
    return result


def _not_applicable_reason(template_ids: list[str]) -> str:
    reason = ""
    if template_ids == [_UNREACHABLE_BATTERY]:
        reason = "现有电量模板已完整覆盖所需字段，按生产规则不启用旧兜底模板。"
    elif template_ids and all(item.startswith("CurrentTimeOverview") for item in template_ids):
        reason = "当前时间为配对专用；没有其它内容业务，独立操作按钮不构成伙伴业务。"
    return reason


def _calendar_weather(
    case: gallery.GalleryInputCase, content: dict[str, Any],
) -> None:
    content.update(
        size="2x4",
        candidateDataBindings=[
            {
                "capabilityId": "GetCalendarEvents",
                "writeResultTo": "/data/calendar",
                "candidateOutputFields": ["/events/0/title", "/events/0/startDate"],
                "arguments": {"futureDays": 7},
            },
            {
                "capabilityId": "ViewWeather",
                "writeResultTo": "/data/weather",
                "candidateOutputFields": ["/current/temperatureText", "/current/condition"],
                "arguments": _arguments("ViewWeather"),
            },
        ],
        candidateEventCandidates=[],
        userQuery="生成2×4卡片，左侧展示首项日程标题和开始日期，右侧展示当前温度和天气现象，无按钮。",
    )
    case.cardSize = "2x4"
    case.partnerTemplateId = _WEATHER_FULL
    case.compositionTemplateIds = [_DATE_TITLE, _WEATHER_FULL]
    case.expectedLayout = "WideTwoFullLayout"
    case.constrainLayout = True
    case.expectedActionCount = 0
    case.expectsFusionBall = False
    case.scenarioName = "融球 · 日历日期标题 + 天气"


def _normalize_actions(
    template_ids: list[str],
    content: dict[str, Any],
    events: dict[str, dict[str, Any]],
) -> None:
    if not any(item.startswith("ActivityOverview") for item in template_ids):
        return
    candidates = content.get("candidateEventCandidates")
    if not isinstance(candidates, list):
        raise ValueError("gallery event candidates must be a list")
    for index, candidate in enumerate(candidates):
        if candidate.get("capabilityId") != "event.open.health.sportsRecord":
            continue
        candidates[index] = gallery._event_candidate(events, "event.open.health.activityRecord")
        query = content.get("userQuery")
        if not isinstance(query, str):
            raise ValueError("gallery userQuery must be text")
        content["userQuery"] = query.replace("打开锻炼", "打开活动记录")


def normalize_gallery_case(
    original: gallery.GalleryInputCase,
    source: dict[str, Any],
    events: dict[str, dict[str, Any]],
) -> tuple[gallery.GalleryInputCase, dict[str, Any]]:
    """修复测试合同而不放松服务端校验；不改变既定跨垂域随机搭配。"""
    case = original.model_copy(deep=True)
    payload = deepcopy(source)
    content = _object(payload, "content")
    template_ids = _template_ids(case)
    case.notApplicableReason = _not_applicable_reason(template_ids)
    query = content.get("userQuery")
    if not isinstance(query, str):
        raise ValueError("gallery userQuery must be text")
    content["userQuery"] = gallery_display_description(query)
    assets = content.get("candidateAssetIds")
    if not isinstance(assets, list):
        raise ValueError("gallery candidateAssetIds must be a list")
    for template_id in template_ids:
        for asset_id in REQUIRED_ASSET_IDS.get(template_id, ()):
            if asset_id not in assets:
                assets.append(asset_id)
    if "WeatherOverviewFeelsLikeWindSupport@1" in template_ids:
        assets = [item for item in assets if item != "asset.icon_weather_thermometer"]
        if "asset.icon_weather_thermometer_medium" not in assets:
            assets.append("asset.icon_weather_thermometer_medium")
        content["candidateAssetIds"] = assets
    _normalize_actions(template_ids, content, events)
    if case.targetTemplateId == _DATE_TITLE:
        _calendar_weather(case, content)
    elif case.targetTemplateId == THREE_DAY_WEATHER_TEMPLATE:
        content = three_day_weather_content(
            content,
            gallery._event_candidate(events, "event.open.weather"),
            _arguments("GetCountdownDays"),
        )
        # three_day_weather_content also serves fresh base generation.
        bindings = content.get("candidateDataBindings")
        if not isinstance(bindings, list):
            raise ValueError("three-day gallery bindings must be a list")
        content["candidateDataBindings"] = _unique_bindings(bindings)
        case.cardSize = "2x4"
        case.partnerTemplateId = THREE_DAY_COUNTDOWN_TEMPLATE
        case.compositionTemplateIds = [THREE_DAY_WEATHER_TEMPLATE, THREE_DAY_COUNTDOWN_TEMPLATE]
        case.expectedLayout = THREE_DAY_LAYOUT
        case.constrainLayout = True
        case.expectedActionCount = 1
        case.expectsFusionBall = False
        case.scenarioId = "single-one-action"
    elif case.targetTemplateId == _PLAYLIST:
        content["candidateEventCandidates"] = [
            gallery._event_candidate(events, "event.open.music.daily")
        ]
        content["userQuery"] = (
            "生成2×4耳机卡，展示名称、连接状态、左右耳和耳机仓的电量与各自充电状态，"
            "保留内嵌的每日歌单入口。"
        )
        case.expectedActionCount = 1
    payload["content"] = content
    _object(payload, "utterance")["original"] = content.get("userQuery")
    return case, payload


def _unique_bindings(bindings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, Any]] = set()
    result: list[dict[str, Any]] = []
    for binding in bindings:
        key = (binding.get("capabilityId"), binding.get("writeResultTo"))
        if key in seen:
            continue
        seen.add(key)
        result.append(binding)
    return result


def normalize_gallery_inputs(
    source: gallery.GalleryInputManifest,
    input_root: Path,
    events: dict[str, dict[str, Any]],
) -> gallery.GalleryInputManifest:
    manifest = source.model_copy(deep=True)
    sizes: set[str] = set()
    for provider in manifest.providers:
        for index, original in enumerate(provider.cases):
            path = gallery._safe_request_path(input_root, original.requestFile)
            payload = json.loads(path.read_text(encoding="utf-8"))
            case, payload = normalize_gallery_case(original, payload, events)
            provider.cases[index] = case
            sizes.add(case.cardSize)
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
            )
    manifest.cardSize = "mixed" if len(sizes) > 1 else next(iter(sizes), "2x2")
    return manifest


def prepare_failed_replay(input_root: Path, result_root: Path, output_root: Path) -> Path:
    """只重跑原失败条目，四类当前不适用条目由Runner保留状态而不调用模型。"""
    if output_root.exists():
        raise ValueError("replay input directory must be new")
    results = json.loads((result_root / "manifest.json").read_text(encoding="utf-8"))
    failed_ids: set[str] = set()
    coverage_by_id: dict[str, dict[str, Any]] = {}
    for provider in results.get("providers", []):
        for case in provider.get("cases", []):
            if case.get("status") == "failed":
                case_id = case.get("caseId")
                if not isinstance(case_id, str) or not case_id:
                    raise ValueError("failed result requires caseId")
                failed_ids.add(case_id)
                coverage_by_id[case_id] = case
    manifest = gallery.load_gallery_input_manifest(input_root)
    found: set[str] = set()
    selected: list[gallery.GalleryInputProvider] = []
    for provider in manifest.providers:
        cases: list[gallery.GalleryInputCase] = []
        for case in provider.cases:
            if case.caseId not in failed_ids:
                continue
            source = gallery._safe_request_path(input_root, case.requestFile)
            target = gallery._safe_request_path(output_root, case.requestFile)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            coverage = coverage_by_id.get(case.caseId)
            if coverage is None:
                raise ValueError(f"failed result missing: {case.caseId}")
            case_payload = case.model_dump()
            for key in ("compositionTemplateIds", "constrainLayout", "expectedActionCount"):
                if key in coverage:
                    case_payload[key] = coverage.get(key)
            cases.append(gallery.GalleryInputCase.model_validate(case_payload))
            found.add(case.caseId)
        if cases:
            selected.append(provider.model_copy(update={"cases": cases}))
    if found != failed_ids:
        raise ValueError(f"failed cases have no source input: {sorted(failed_ids - found)}")
    manifest.providers = selected
    events = gallery._load_event_capabilities(gallery._CAPABILITY_ROOT)
    manifest = normalize_gallery_inputs(manifest, output_root, events)
    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / "manifest.json"
    path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path
