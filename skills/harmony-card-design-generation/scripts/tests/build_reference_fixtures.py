from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = SKILL_DIR / "scripts"
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from design_system import DesignSystem


def item(item_id: str, role: str, priority: str = "mustKeep", max_chars: int | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {"id": item_id, "role": role, "priority": priority}
    if max_chars is not None:
        value["maxChars"] = max_chars
    return value


def content(feature_id: str, value: Any, binding_kind: str = "static") -> dict[str, Any]:
    return {"featureId": feature_id, "bindingKind": binding_kind, "value": value}


def region(
    region_id: str,
    module_id: str,
    variant_id: str,
    elements: dict[str, str],
    values: dict[str, dict[str, Any]],
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "regionId": region_id,
        "moduleId": module_id,
        "variantId": variant_id,
        "elements": elements,
        "content": values,
    }
    if events:
        result["events"] = events
    return result


def event(target: str, call: str, args: dict[str, Any]) -> dict[str, Any]:
    return {"target": target, "handler": {"call": call, "args": args}}


def make_plan(
    surface_id: str,
    service_object: str,
    primary_question: str,
    size: str,
    visual: str,
    style: str,
    layout_id: str,
    items: list[dict[str, Any]],
    regions: list[dict[str, Any]],
    title: str,
    description: str,
    actions: list[str] | None = None,
    assets: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schemaVersion": "design-plan-v1",
        "surfaceId": surface_id,
        "featureProfile": {
            "schemaVersion": "feature-profile-v1",
            "serviceObject": service_object,
            "primaryQuestion": primary_question,
            "size": size,
            "primaryVisual": visual,
            "contentItems": items,
            "actions": actions or [],
            "dataNeeds": [],
            "assetNeeds": assets or [],
            "styleIntent": style,
        },
        "layoutId": layout_id,
        "styleProfile": style,
        "regions": regions,
        "dataModel": {"state": "ready"},
        "cardSpec": {"title": title, "description": description, "suggestSize": size},
        "degradations": [],
    }


def reference_plans() -> list[dict[str, Any]]:
    battery_event = event(
        "action",
        "clickToIntent",
        {"intentName": "SetSettingSwitch", "params": {"appBundleName": "com.huawei.hmos.settings", "itemName": "battery_saving_mode", "switchFlag": 0}},
    )
    clean_event = event("action", "clickToApi", {"intentName": "CleanRAMMemory", "params": {}})
    usage_event = event(
        "action",
        "clickToDeeplink",
        {"intentName": "Settings", "bundleName": "com.huawei.hmos.settings", "abilityName": "com.huawei.hmos.settings.MainAbility", "uri": "parent_control"},
    )
    calendar_event = event("action", "clickToIntent", {"intentName": "ViewCalendarEvent", "params": {"entityId": ""}})
    weather_event = event(
        "action",
        "clickToDeeplink",
        {"intentName": "Weather_CityCode", "bundleName": "", "abilityName": "", "uri": "hww://www.huawei.com/totemweather?enterType=share&cityCode="},
    )
    settings_battery = event(
        "primaryAction",
        "clickToDeeplink",
        {"intentName": "Settings", "bundleName": "com.huawei.hmos.settings", "abilityName": "com.huawei.hmos.settings.MainAbility", "uri": "battery"},
    )
    settings_health = event(
        "secondaryAction",
        "clickToDeeplink",
        {"intentName": "Settings", "bundleName": "com.huawei.hmos.settings", "abilityName": "com.huawei.hmos.settings.MainAbility", "uri": "smart_charge_battery_health"},
    )
    settings_storage = event(
        "secondaryAction",
        "clickToDeeplink",
        {"intentName": "Settings", "bundleName": "com.huawei.hmos.settings", "abilityName": "com.huawei.hmos.settings.MainAbility", "uri": "storage_settings"},
    )

    plans: list[dict[str, Any]] = []
    plans.append(make_plan(
        "ref-meter-side-action", "手机电池", "还剩多少电并如何省电", "2x2", "progress", "ambient-scene", "header-main-footer",
        [item("object", "object"), item("progress", "metric"), item("primary", "primary"), item("caption", "support"), item("action", "action")],
        [
            region("header", "identity-strip", "compact-136x20", {"title": "text-body-14"}, {"object": content("object", "手机电池")}),
            region("main", "meter-summary", "compact-136x58", {"meter": "progress-ring-50", "value": "text-metric-20", "caption": "text-support-12"}, {"progress": content("progress", 28), "primary": content("primary", "28%"), "caption": content("caption", "电量偏低")}),
            region("footer", "action-strip", "compact-136x26", {"action": "button-136x26"}, {"label": content("action", "开启省电")}, [battery_event]),
        ], "低电模式", "电量与省电入口", ["开启省电"]
    ))
    plans.append(make_plan(
        "ref-multi-meter-action", "系统内存", "当前内存压力如何", "2x2", "status", "dark-focus", "metrics-main-footer",
        [item("metric1", "metric"), item("metric2", "metric"), item("primary", "primary"), item("caption", "support"), item("action", "action")],
        [
            region("metrics", "metric-cluster", "pair-136x28", {"left": "text-body-14", "right": "text-body-14"}, {"metric1": content("metric1", "已用7G"), "metric2": content("metric2", "可用5G")}),
            region("main", "primary-summary", "compact-136x50", {"value": "text-metric-20", "caption": "text-support-12"}, {"primary": content("primary", "60%"), "caption": content("caption", "运行内存占用")}),
            region("footer", "action-strip", "compact-136x26", {"action": "button-136x26"}, {"label": content("action", "立即清理")}, [clean_event]),
        ], "内存状态", "内存占用与清理", ["立即清理"]
    ))
    plans.append(make_plan(
        "ref-bar-dual-metric-action", "应用时长", "今天还可以使用多久", "2x2", "progress", "dark-focus", "header-dashboard-footer",
        [item("object", "object"), item("progress", "metric"), item("metric1", "metric"), item("metric2", "metric"), item("action", "action")],
        [
            region("header", "identity-strip", "compact-136x20", {"title": "text-body-14"}, {"object": content("object", "应用时长")}),
            region("dashboard", "metric-cluster", "dashboard-136x62", {"bar": "progress-bar-136", "left": "text-metric-20", "right": "text-support-12"}, {"progress": content("progress", 65), "metric1": content("metric1", "78分"), "metric2": content("metric2", "剩42分")}),
            region("footer", "action-strip", "compact-136x26", {"action": "button-136x26"}, {"label": content("action", "管理时长")}, [usage_event]),
        ], "应用时长", "今日使用与额度", ["管理时长"]
    ))
    plans.append(make_plan(
        "ref-countdown-panel", "马拉松", "距离比赛还有几天", "2x2", "metric", "ambient-scene", "header-hero-support",
        [item("object", "object"), item("primary", "primary"), item("unit", "support"), item("supportTitle", "support"), item("supportMeta", "support", "shouldKeep")],
        [
            region("header", "identity-strip", "compact-136x18", {"title": "text-body-14"}, {"object": content("object", "马拉松倒计时")}),
            region("hero", "countdown-summary", "compact-136x44", {"value": "text-metric-40", "unit": "text-body-14"}, {"primary": content("primary", "18"), "unit": content("unit", "天")}),
            region("support", "support-panel", "compact-136x42", {"title": "text-body-14", "meta": "text-label-10"}, {"title": content("supportTitle", "下周开始减量训练"), "meta": content("supportMeta", "保持睡眠与补水")}),
        ], "赛事倒计时", "比赛日期与准备"
    ))
    plans.append(make_plan(
        "ref-meeting-action-badge", "产品评审", "下一场会议何时开始", "2x2", "schedule", "neutral-light", "header-main-footer",
        [item("object", "object"), item("title", "primary"), item("time", "primary"), item("action", "action")],
        [
            region("header", "identity-strip", "compact-136x20", {"title": "text-body-14"}, {"object": content("object", "下一场会议")}),
            region("main", "schedule-summary", "compact-136x58", {"title": "text-title-16", "time": "text-metric-20"}, {"title": content("title", "产品方案评审"), "time": content("time", "14:30")}),
            region("footer", "action-strip", "compact-136x26", {"action": "button-136x26"}, {"label": content("action", "查看日程")}, [calendar_event]),
        ], "会议提醒", "下一日程与入口", ["查看日程"]
    ))
    plans.append(make_plan(
        "ref-product-stat-tiles", "蓝牙耳机", "左右耳电量是否充足", "2x2", "media", "media-surface", "full-surface-stack",
        [item("image", "asset"), item("title", "object"), item("metric1", "metric"), item("metric2", "metric")],
        [region("content", "media-summary", "full-136x136", {"image": "icon-48", "title": "text-title-16", "left": "text-metric-20", "right": "text-body-14"}, {"image": content("image", "resources/base/media/icon_earphone.svg"), "title": content("title", "FreeBuds"), "metric1": content("metric1", "86%"), "metric2": content("metric2", "右82%")})],
        "耳机状态", "左右耳电量", assets=["耳机主视觉"]
    ))
    plans.append(make_plan(
        "ref-quadrant-ambient-action", "雨天关怀", "当前天气需要注意什么", "2x2", "status", "ambient-scene", "two-row-grid",
        [item("topLabel", "support"), item("primary", "primary"), item("statusLabel", "support"), item("status", "status"), item("bottomLabel", "support"), item("bottomValue", "support"), item("actionLabel", "support"), item("actionValue", "support")],
        [
            region("top", "featured-pair", "row-136x55", {"primaryLabel": "text-label-10", "primaryValue": "text-metric-20", "statusLabel": "text-label-10", "statusValue": "text-support-12"}, {"primaryLabel": content("topLabel", "天气"), "primaryValue": content("primary", "18℃"), "statusLabel": content("statusLabel", "提醒"), "statusValue": content("status", "带伞")}),
            region("bottom", "paired-grid", "row-136x55", {"leftTitle": "text-label-10", "leftValue": "text-support-12", "rightTitle": "text-label-10", "rightValue": "text-support-12"}, {"leftTitle": content("bottomLabel", "通勤"), "leftValue": content("bottomValue", "提前15分"), "rightTitle": content("actionLabel", "关怀"), "rightValue": content("actionValue", "路上慢行")}),
        ], "雨天关怀", "天气与通勤提醒"
    ))
    plans.append(make_plan(
        "ref-spotlight-context-action", "上海天气", "当前天气和下一安排是什么", "2x2", "status", "ambient-scene", "hero-context-footer",
        [item("icon", "asset"), item("primary", "primary"), item("caption", "support"), item("contextTitle", "support"), item("contextMeta", "support", "shouldKeep"), item("action", "action")],
        [
            region("hero", "primary-summary", "hero-136x42", {"icon": "icon-32", "value": "text-metric-20", "caption": "text-support-12"}, {"icon": content("icon", "resources/base/media/icon_weather1.svg"), "primary": content("primary", "18℃"), "caption": content("caption", "中雨")}),
            region("context", "support-panel", "compact-136x36", {"title": "text-body-14", "meta": "text-support-12"}, {"title": content("contextTitle", "14:30评审"), "meta": content("contextMeta", "线上")}),
            region("footer", "action-strip", "compact-136x26", {"action": "button-136x26"}, {"label": content("action", "打开天气")}, [weather_event]),
        ], "天气日程", "天气与下一安排", ["打开天气"], ["天气图标"]
    ))
    plans.append(make_plan(
        "ref-stacked-schedule-action", "专注日程", "下一项安排是什么", "2x2", "schedule", "ambient-scene", "header-schedule-footer",
        [item("object", "object"), item("title", "primary"), item("time", "primary"), item("meta", "support"), item("action", "action")],
        [
            region("header", "identity-strip", "compact-136x18", {"title": "text-body-14"}, {"object": content("object", "专注日程")}),
            region("schedule", "schedule-summary", "stacked-136x68", {"title": "text-body-14", "time": "text-metric-20", "meta": "text-support-12"}, {"title": content("title", "需求方案整理"), "time": content("time", "15:00-16:00"), "meta": content("meta", "开始前 10 分钟提醒")}),
            region("footer", "action-strip", "compact-136x26", {"action": "button-136x26"}, {"label": content("action", "查看日程")}, [calendar_event]),
        ], "专注日程", "下一安排与提醒", ["查看日程"]
    ))
    plans.append(make_plan(
        "ref-content-action-sidebar", "电池维护", "电池状态需要采取什么操作", "2x4", "status", "neutral-light", "header-content-sidebar",
        [item("object", "object"), item("title", "primary"), item("support", "support"), item("action1", "action"), item("action2", "action")],
        [
            region("header", "identity-strip", "wide-296x24", {"title": "text-title-16"}, {"object": content("object", "电池维护助手")}),
            region("body", "content-sidebar", "wide-296x104", {"title": "text-title-18", "support": "text-body-14", "primaryAction": "button-84x48", "secondaryAction": "button-84x48"}, {"title": content("title", "当前电池状态良好"), "support": content("support", "智能充电可延长寿命"), "primaryAction": content("action1", "电池设置"), "secondaryAction": content("action2", "健康管理")}, [settings_battery, settings_health]),
        ], "电池维护", "状态与维护入口", ["电池设置", "健康管理"]
    ))
    plans.append(make_plan(
        "ref-dual-action-panel", "系统存储", "当前存储状态及可执行操作", "2x4", "metric", "neutral-light", "content-action-stack",
        [item("title", "primary"), item("primary", "primary"), item("support", "support"), item("action1", "action"), item("action2", "action")],
        [
            region("content", "wide-primary", "panel-180x136", {"title": "text-title-16", "value": "text-metric-32", "support": "text-body-14"}, {"title": content("title", "系统存储空间"), "primary": content("primary", "68%"), "support": content("support", "可用 82 GB，状态正常")}),
            region("actions", "action-stack", "wide-104x136", {"primaryAction": "button-104x62", "secondaryAction": "button-104x62"}, {"primaryAction": content("action1", "电池设置"), "secondaryAction": content("action2", "存储管理")}, [settings_battery, settings_storage]),
        ], "系统状态", "存储与快捷操作", ["电池设置", "存储管理"]
    ))
    plans.append(make_plan(
        "ref-hero-context-action", "通勤天气", "天气和今日安排如何", "2x4", "media", "ambient-scene", "hero-context-split",
        [item("visual", "asset"), item("primary", "primary"), item("caption", "support"), item("title", "support"), item("meta", "support"), item("support", "support", "shouldKeep"), item("action", "action")],
        [
            region("hero", "hero-tall", "wide-104x136", {"visual": "icon-48", "value": "text-metric-32", "caption": "text-support-12"}, {"visual": content("visual", "resources/base/media/icon_weather1.svg"), "primary": content("primary", "24℃"), "caption": content("caption", "多云转晴")}),
            region("context", "context-action", "wide-180x136", {"title": "text-body-14", "meta": "text-body-14", "support": "text-support-12", "action": "button-180x32"}, {"title": content("title", "下一场：产品评审"), "meta": content("meta", "14:30 · 线上会议"), "support": content("support", "通勤预计 35 分钟"), "action": content("action", "打开天气")}, [weather_event]),
        ], "通勤助手", "天气日程速览", ["打开天气"], ["天气主视觉"]
    ))
    plans.append(make_plan(
        "ref-metric-dashboard-action", "系统内存", "主指标和支撑指标是否正常", "2x4", "metric", "dark-focus", "metric-dashboard",
        [item("primary", "primary"), item("caption", "support"), item("title", "support"), item("metric1", "metric"), item("metric2", "metric"), item("metric3", "metric", "shouldKeep"), item("action", "action"), item("status", "status", "shouldKeep")],
        [
            region("primary", "primary-summary", "tall-92x136", {"value": "text-metric-40", "caption": "text-support-12"}, {"primary": content("primary", "60%"), "caption": content("caption", "内存占用")}),
            region("metrics", "metric-cluster", "tall-124x136", {"title": "text-body-14", "metric1": "text-body-14", "metric2": "text-body-14", "metric3": "text-body-14"}, {"title": content("title", "系统资源"), "metric1": content("metric1", "已用 7.2 GB"), "metric2": content("metric2", "可用 4.8 GB"), "metric3": content("metric3", "后台 18 个")}),
            region("action", "action-tall", "narrow-64x136", {"action": "button-64x48", "status": "text-support-12"}, {"action": content("action", "清理"), "status": content("status", "释放1.2G")}, [clean_event]),
        ], "内存面板", "主指标与清理", ["清理"]
    ))
    return plans


def main() -> int:
    system = DesignSystem(SKILL_DIR)
    plans = reference_plans()
    golden: dict[str, Any] = {"schemaVersion": "reference-golden-v1", "cards": {}}
    for plan in plans:
        issues = system.validate_plan(plan)
        if issues:
            for issue in issues:
                print(f"{plan['surfaceId']}: {issue.code} {issue.location}: {issue.message}")
            return 1
        dsl, cardspec = system.assemble(plan)
        golden["cards"][plan["surfaceId"]] = {"genui": dsl, "cardspec": cardspec}
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    (FIXTURE_DIR / "reference-plans.json").write_text(
        json.dumps({"schemaVersion": "reference-plans-v1", "plans": plans}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (FIXTURE_DIR / "golden-cards.json").write_text(
        json.dumps(golden, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
