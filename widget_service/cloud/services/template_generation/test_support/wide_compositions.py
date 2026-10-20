"""按主垂域补充可重放的 2×4 骨架组合输入，不合成生成结果。"""

from __future__ import annotations

import json
import random
from dataclasses import replace
from itertools import product
from pathlib import Path
from typing import Any

from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.cardplan.wide_template_planner import (
    _WIDE_LAYOUTS,
    WideLayoutOption,
    _template_intrinsic_height,
)
from services.template_generation.test_support import provider_gallery as gallery
from services.template_generation.test_support.template_examples import _object_field

DEFAULT_SEED = 20261014
# 选取字段明确、无强制内嵌动作的代表模板；其余垂域按骨架角色随机搭配。
_POOL = {
    "current-time": {
        "Full": ("CurrentTimeOverviewDateFull@1",),
        "Support": ("CurrentTimeOverviewSupport@1",),
    },
    "battery": {
        "Support": ("BatteryOverviewPhoneTextSupport@1",),
        "Full": ("BatteryOverviewPercentTextFull@1",),
        "Hero": ("BatteryOverviewStatusRingHero@1", "BatteryOverviewTemperatureRingHero@1"),
        "Compact": ("BatteryOverviewPercentRingCompact@1",),
    },
    "calendar": {
        "Support": ("ScheduleOverviewStartTimeSupport@1",),
        "Full": ("ScheduleOverviewTitleTimeFull@1",),
        "Hero": ("ScheduleOverviewTitleHero@1",),
        "Compact": ("ScheduleOverviewReminderCompact@1",),
    },
    "countdown": {
        "Full": ("CountdownOverviewTargetDetailFull@1",),
        "Hero": ("CountdownOverviewEventHero@1",),
        "Compact": ("CountdownOverviewTargetCompact@1",),
        "WideHalf": ("CountdownOverviewWideHalf@1",),
    },
    "earphone": {
        "Support": ("BluetoothDeviceOverviewNameAndConnectionSupport@1",),
        "Full": ("BluetoothDeviceOverviewEarphonePercentTextFull@1",),
        "Hero": ("BluetoothDeviceOverviewEarbudPairHero@1",),
        "Compact": ("BluetoothDeviceOverviewEarphoneCaseCompact@1",),
        "WideHalf": ("BluetoothDeviceOverviewTripleBatteryWideHalf@1",),
    },
    "health-sport": {
        "Support": ("ActivityOverviewSupport@1",),
        "Full": ("ActivityOverviewFull@1", "HeartRateOverviewFull@1"),
        "Hero": ("ActivityOverviewHero@1", "HeartRateOverviewHero@1"),
        "Compact": ("ActivityOverviewCompact@1", "SleepOverviewCompact@1"),
    },
    "weather": {
        "Support": ("WeatherOverviewFeelsLikeWindSupport@1",),
        "Full": ("WeatherOverviewFull@1",),
        "Hero": ("WeatherOverviewFeelsLikeHero@1",),
        "Compact": ("WeatherOverviewCompact@1",),
        "WideHalf": ("WeatherOverviewWideHalf@1",),
    },
}
_ACTIONS = {
    "BatteryOverview": ("event.open.settings.battery", "event.open.settings.batteryHealth"),
    "CalendarOverview": ("event.viewCalendarEvent", "event.enter.meeting"),
    "CountdownOverview": ("event.open.clock.alarmTab",),
    "BluetoothDeviceOverview": ("event.open.settings.bluetooth", "event.open.music.daily"),
    "ActivityOverview": ("event.open.health.activityRecord",),
    "HeartRateOverview": ("event.open.health.sport",),
    "SleepOverview": ("event.open.health.sleep",),
    "WeatherOverview": ("event.open.weather",),
}
_SHARED_ACTIONS = (
    "event.open.settings.battery",
    "event.open.music.daily",
    "event.open.health.sport",
    "event.open.clock.alarmTab",
)
_ACTION_LABELS = {
    "event.open.settings.battery": "打开电池设置",
    "event.open.settings.batteryHealth": "打开电池健康",
    "event.viewCalendarEvent": "查看第一个日程详情",
    "event.enter.meeting": "进入第一个日程的会议",
    "event.open.clock.alarmTab": "打开闹钟",
    "event.open.settings.bluetooth": "打开蓝牙设置",
    "event.open.music.daily": "打开每日音乐",
    "event.open.health.sport": "打开锻炼",
    "event.open.health.activityRecord": "打开活动记录",
    "event.open.health.sleep": "打开睡眠详情",
    "event.open.weather": "打开当前城市天气",
}


def _selections() -> dict[str, gallery.GalleryTemplateSelection]:
    result = {}
    for business in gallery._load_business_definitions(gallery._PROVIDER_ROOT):
        for template in business.templates:
            result[template.template_id] = gallery.GalleryTemplateSelection(business, template)
    return result


def composition_layouts() -> tuple[WideLayoutOption, ...]:
    """每种多槽宽卡骨架一项；保留正式角色顺序及动作归属。"""
    results = []
    seen = {"WideSingleFocusLayout", "WideFullOnlyLayout"}
    for layout in _WIDE_LAYOUTS:
        if layout.layout_id in seen:
            continue
        seen.add(layout.layout_id)
        results.append(layout)
    return tuple(results)


def _action_ids(
    layout: WideLayoutOption, selections: tuple[gallery.GalleryTemplateSelection, ...]
) -> tuple[str, ...]:
    ids = []
    for owner in layout.action_owners:
        options = (
            _SHARED_ACTIONS
            if owner is None
            else _ACTIONS.get(selections[owner].business.business_id, ())
        )
        available = [event for event in options if event not in ids]
        if not available:
            return ()
        ids.append(available[0])
    return tuple(ids)


def _choose(
    domain: str,
    layout: WideLayoutOption,
    rng: random.Random,
    selections: dict[str, gallery.GalleryTemplateSelection],
) -> tuple[gallery.GalleryTemplateSelection, ...]:
    registry = get_cardplan_registry(True)
    options = []
    for position, role in enumerate(layout.roles):
        eligible = []
        for slug, roles in _POOL.items():
            if (position == 0) != (slug == domain):
                continue
            for template_id in roles.get(role, ()):
                budget = (
                    layout.slot_height_budgets[position] if layout.slot_height_budgets else None
                )
                if (
                    budget is not None
                    and _template_intrinsic_height(template_id, registry) > budget
                ):
                    continue
                selection = selections.get(template_id)
                if selection is None:
                    raise ValueError(f"组合模板未注册：{template_id}")
                eligible.append(selection)
        options.append(eligible)
    valid = []
    for combination in product(*options):
        domains = {item.business.provider_slug for item in combination}
        if domains == {"current-time"}:
            continue
        if len(domains) != len(combination):
            continue
        if len(_action_ids(layout, combination)) != len(layout.action_templates):
            continue
        valid.append(combination)
    return rng.choice(valid) if valid else ()


def _request(
    chosen: tuple[gallery.GalleryTemplateSelection, ...],
    layout: WideLayoutOption,
    case_id: str,
    events: dict[str, dict[str, Any]],
    assets: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    first = chosen[0]
    payload = gallery._request_envelope(
        first.business,
        first.template,
        "single-content",
        gallery._GALLERY_APPEARANCES[0],
        events,
        assets,
    )
    bindings = []
    asset_ids = []
    samples = {}
    descriptions = []
    for selected in chosen:
        template = selected.template
        definition = get_cardplan_registry(True).require_template(template.template_id)
        fields = gallery._ordered_unique(
            [*definition.primary_data, *definition.secondary_data, *definition.required_data]
        )
        binding = gallery._data_binding(selected.business, replace(template, fields=fields))
        # 组合只要求模板承载字段；禁止把电量单业务兜底事实带入其他槽位。
        binding["candidateOutputFields"] = list(fields)
        bindings.append(binding)
        asset_ids.extend(gallery._candidate_asset_ids(template, assets))
        for pointer, value in gallery._gallery_sample_overrides(template).items():
            if pointer.removeprefix(selected.business.data_domain) in fields:
                samples[pointer] = value
        descriptions.append(gallery.gallery_display_description(template.description))
    actions = _action_ids(layout, chosen)
    if any(
        name in {"LargeIconAction", "CompactSubtitleAction"} for name in layout.action_templates
    ):
        action_assets = (
            "asset.battery_leaf_fill", "asset.music_fill", "asset.alarm_fill_1", "asset.heart_fill",
        )
        for asset_id in action_assets:
            if asset_id not in assets:
                raise ValueError(f"组合动作素材未注册：{asset_id}")
            asset_ids.append(asset_id)
    query = "生成一个2×4卡片，组合以下内容，每块内容独立显示：" + "；".join(descriptions)
    query += (
        "。倒计时目标为2027年1月1日元旦。"
        if any(item.business.provider_slug == "countdown" for item in chosen)
        else "。"
    )
    labels = []
    for event in actions:
        label = _ACTION_LABELS.get(event)
        if label is None:
            raise ValueError(f"组合动作缺少说明：{event}")
        labels.append(label)
    query += "提供独立操作按钮：" + "、".join(labels) + "。" if actions else "不显示操作按钮。"
    _object_field(payload, "content").update(
        title=first.business.business_name + "组合",
        description="2×4跨垂域骨架组合，演示数据",
        size="2x4",
        userQuery=query,
        candidateDataBindings=bindings,
        candidateAssetIds=list(dict.fromkeys(asset_ids)),
        candidateEventCandidates=[gallery._event_candidate(events, event) for event in actions],
    )
    _object_field(payload, "utterance")["original"] = query
    _object_field(payload, "session")["sessionId"] = case_id
    payload["galleryTest"] = {"sampleOverrides": samples}
    return payload


def append_wide_compositions(
    input_root: Path, seed: int = DEFAULT_SEED
) -> gallery.GalleryInputManifest:
    """保留已有各垂域，只替换该垂域内本生成器管理的骨架组合。"""
    manifest = gallery.load_gallery_input_manifest(input_root)
    selections = _selections()
    events = gallery._load_event_capabilities(gallery._CAPABILITY_ROOT)
    assets = gallery._load_asset_capabilities(gallery._CAPABILITY_ROOT)
    rng = random.Random(seed)
    excluded = []
    for provider in manifest.providers:
        domain = provider.providerSlug
        if domain not in _POOL:
            continue
        provider.cases = [
            case for case in provider.cases if not case.caseId.startswith("wide-composition-")
        ]
        for layout in composition_layouts():
            chosen = _choose(domain, layout, rng, selections)
            if not chosen:
                excluded.append(
                    {
                        "domain": domain,
                        "layout": layout.layout_id,
                        "reason": "主槽角色或高度/动作要求无兼容模板",
                    }
                )
                continue
            layout_slug = gallery._kebab_case(layout.layout_id)
            case_id = f"wide-composition-{domain}-{layout_slug}"
            request_file = f"providers/{domain}/wide-compositions/{layout_slug}.json"
            payload = _request(chosen, layout, case_id, events, assets)
            path = input_root / request_file
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            template_ids = [item.template.template_id for item in chosen]
            names = [item.business.business_name for item in chosen]
            provider.cases.append(
                gallery.GalleryInputCase(
                    caseId=case_id,
                    cardSize="2x4",
                    providerId=provider.providerId,
                    providerName=provider.providerName,
                    providerSlug=domain,
                    businessId=chosen[0].business.business_id,
                    businessName=" + ".join(names),
                    scenarioId=layout_slug,
                    scenarioName="骨架组合 · " + " + ".join(names),
                    appearanceId="fusion",
                    appearanceName="融球",
                    prdVer=gallery.FUSION_PRD_VERSION,
                    expectsFusionBall=len(chosen) == 1 and layout.roles == ("Full",),
                    expectedLayout=layout.layout_id,
                    expectedTemplateSuffix=layout.roles[0],
                    targetTemplateId=template_ids[0],
                    partnerTemplateId=template_ids[1] if len(template_ids) > 1 else "",
                    compositionTemplateIds=template_ids,
                    constrainLayout=True,
                    expectedActionCount=len(layout.action_templates),
                    requestFile=request_file,
                )
            )
    manifest.cardSize = "mixed"
    (input_root / "manifest.json").write_text(
        manifest.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    audit = {
        "seed": seed,
        "excluded": excluded,
        "layouts": [item.layout_id for item in composition_layouts()],
    }
    (input_root / "wide-composition-selection.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest
