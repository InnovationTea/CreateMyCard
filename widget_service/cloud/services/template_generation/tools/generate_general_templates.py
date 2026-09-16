"""生成按业务视觉基线设计的 Number、Text、Pair 通用模板。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PROVIDERS = Path(__file__).resolve().parents[1] / "resources" / "source" / "providers"
SHAPES = ("Full", "Hero", "Compact", "Support")
KINDS = ("Text", "Number", "Pair")
# 字号、对齐、图标位置和参考模板均逐业务指定，来源为现有正式 cardtpl。
STYLES = {
    "WeatherOverview": {
        "icon": "conditionIcon",
        "tag": "weather",
        "number": 32,
        "text": 20,
        "align": "start",
        "iconPosition": "trailing",
        "footerRows": False,
        "references": ["WeatherOverviewFull@1", "WeatherOverviewUvFull@1"],
    },
    "ActivityOverview": {
        "icon": "stepsIcon",
        "tag": "sport",
        "number": 38,
        "text": 18,
        "align": "start",
        "iconPosition": "trailing",
        "footerRows": True,
        "references": ["ActivityOverviewFull@1", "ActivityOverviewWideFull@1"],
    },
    "AppUsageOverview": {
        "icon": "appIcon",
        "tag": "app",
        "number": 24,
        "text": 24,
        "align": "start",
        "iconPosition": "trailing",
        "footerRows": True,
        "references": ["AppUsageOverviewFull@1", "AppUsageOverviewHero@1"],
    },
    "BatteryOverview": {
        "icon": "batteryIcon",
        "tag": "battery",
        "number": 30,
        "text": 20,
        "align": "center",
        "iconPosition": "leading",
        "footerRows": False,
        "meter": "ring",
        "references": ["BatteryOverviewFull@1", "BatteryOverviewHealthLevelHero@1"],
    },
    "BluetoothDeviceOverview": {
        "icon": "deviceIcon",
        "tag": "earphone",
        "number": 20,
        "text": 20,
        "align": "center",
        "iconPosition": "leading",
        "footerRows": True,
        "references": ["BluetoothDeviceOverviewHero@1", "BluetoothDeviceOverviewEarbudPairFull@1"],
    },
    "CalendarOverview": {
        "icon": "calendarIcon",
        "tag": "calendar",
        "number": 38,
        "text": 20,
        "align": "start",
        "iconPosition": "leading",
        "footerRows": True,
        "references": ["ScheduleOverviewDateFull@1", "ScheduleOverviewTitleHero@1"],
    },
    "CountdownOverview": {
        "icon": "timerIcon",
        "tag": "timer",
        "number": 40,
        "text": 20,
        "align": "center",
        "iconPosition": "trailing",
        "footerRows": False,
        "references": ["CountdownOverviewFull@1", "CountdownOverviewHero@1"],
    },
    "HeartRateOverview": {
        "icon": "heartIcon",
        "tag": "heart",
        "number": 38,
        "text": 20,
        "align": "center",
        "iconPosition": "leading",
        "footerRows": False,
        "references": ["HeartRateOverviewFull@1", "HeartRateOverviewMinMaxFull@1"],
    },
    "ResourceUsageOverview": {
        "icon": "icon",
        "tag": "memory",
        "number": 24,
        "text": 18,
        "align": "center",
        "iconPosition": "leading",
        "footerRows": True,
        "meter": "ring",
        "references": ["ResourceUsageOverviewFull@1", "ResourceUsageOverviewSupport@1"],
    },
    "SleepOverview": {
        "icon": "sourceIcon",
        "tag": "sleep",
        "number": 20,
        "text": 20,
        "align": "start",
        "iconPosition": "trailing",
        "footerRows": True,
        "meter": "linear",
        "references": ["SleepOverviewFull@1", "SleepOverviewNapFull@1"],
    },
    "WorkoutOverview": {
        "icon": "sourceIcon",
        "tag": "sport",
        "number": 24,
        "text": 24,
        "align": "start",
        "iconPosition": "leading",
        "footerRows": True,
        "references": ["WorkoutOverviewFull@1", "WorkoutOverviewHero@1"],
    },
}
HEALTH_FIELDS = {
    "ActivityOverview": ("dailySteps", "dailyTotalCaloriesText", "dailyDistanceText"),
    "SleepOverview": (
        "sleepScore",
        "sleepStatus",
        "sleepTypeDesc",
        "nightSleepDurationText",
        "deepSleepDurationText",
        "totalNapDurationText",
        "fallAsleepTimeText",
        "wakeupTimeText",
    ),
    "WorkoutOverview": (
        "exerciseTypeName",
        "exerciseStartTimeText",
        "exerciseEndTimeText",
        "exerciseDurationText",
        "exerciseCalorieText",
        "exerciseHeartRateAvg",
        "exerciseHeartRateMax",
        "exerciseHeartRateMin",
    ),
    "HeartRateOverview": (
        "exerciseTypeName",
        "exerciseStartTimeText",
        "exerciseEndTimeText",
        "exerciseHeartRateAvg",
        "exerciseHeartRateMax",
        "exerciseHeartRateMin",
    ),
}
ORIGINAL_COLOR = {"appIcon", "deviceIcon", "heartIcon", "sourceIcon"}


def _text(
    value: str,
    size: int,
    height: int,
    *,
    primary: bool = True,
    lines: int = 1,
    align: str = "left",
    weight: int | None = None,
) -> str:
    color = "primaryColor" if primary else "supportContentColor"
    actual_weight = weight if weight is not None else (700 if primary else 400)
    return (
        f'Text({value}, {{"width": "matchParent", "height": {height}, "fontSize": {size}, '
        f'"fontWeight": {actual_weight}, "fontColor": $theme(\'{color}\'), '
        f'"maxLines": {lines}, "textOverflow": "ellipsis", "textAlign": "{align}", '
        '"constraintSize": {"minWidth": 0, "minHeight": 0}})'
    )


def _column(children: str, *, align: str = "start", weight: bool = False) -> str:
    layout = ', "layoutWeight": 1' if weight else ', "width": "matchParent"'
    return (
        'Column({"itemMargin": 0, "justifyContent": "center", '
        f'"alignItems": "{align}", "clip": true{layout}, '
        '"constraintSize": {"minWidth": 0, "minHeight": 0}},\n' + children + "\n)"
    )


def _icon(style: dict[str, Any], shape: str) -> str:
    name = style.get("icon")
    size = 24 if shape == "Support" else 20
    color = (
        '"_preserveOriginalColor": true'
        if name in ORIGINAL_COLOR
        else ("\"fillColor\": $theme('supportContentColor')")
    )
    return (
        f'#if props.{name}\nImage(props.{name}, {{"width": {size}, "height": {size}, '
        f'"objectFit": "contain", "flexShrink": 0, {color}}})\n#endif'
    )


def _footer(style: dict[str, Any], shape: str) -> str:
    row_height = 12 if shape == "Compact" else 16
    first = _text("data.supportValues[0]", 12, row_height, primary=False)
    second = _text("data.supportValues[1]", 12, row_height, primary=False)
    pair = _text(
        "`${data.supportValues[0]} | ${data.supportValues[1]}`", 12, row_height, primary=False
    )
    if shape == "Full" and style.get("footerRows"):
        pair = first + ",\n" + second
    return (
        f"#if data.supportValues.size == 1\n{first}\n"
        f"#elseif data.supportValues.size == 2\n{pair}\n#endif"
    )


def _pair_body(style: dict[str, Any], shape: str) -> str:
    small = shape in {"Compact", "Support"}
    size = 14 if small else min(int(style.get("number", 20)), 24)
    cells = []
    for prefix in ("first", "second"):
        label = _text(f"data.{prefix}Label", 12, 12 if small else 16, primary=False)
        value = _text(f"data.{prefix}Value", size, 16 if small else 32)
        cells.append(_column(label + ",\n" + value, weight=True))
    return (
        'Row({"layoutWeight": 1, "itemMargin": 8, "alignItems": "center", '
        '"constraintSize": {"minWidth": 0, "minHeight": 0}},\n' + ",\n".join(cells) + ")"
    )


def _single_body(style: dict[str, Any], shape: str, kind: str) -> str:
    value_name = "mainNumberValue" if kind == "Number" else "mainTextValue"
    size = int(style.get("number" if kind == "Number" else "text", 20))
    size = min(size, 32) if shape == "Hero" else size
    align = "center" if style.get("align") == "center" else "left"
    lines = 2 if kind == "Text" and shape == "Full" and size <= 20 else 1
    value = _text(f"data.{value_name}", size, (size + 8) * lines, lines=lines, align=align)
    label = _text("data.mainLabel", 12, 16, primary=False, align=align)
    if kind == "Number" and style.get("meter"):
        meter = style.get("meter")
        if meter == "ring":
            height = 52 if shape == "Full" else 44
            ring_text = _text(f"data.{value_name}", 16, 24, align="center")
            chart = (
                f'Stack({{"width": "matchParent", "height": {height}, "alignContent": "center"}},\n'
                'Progress({"value": data.progressValue, "total": 100, "type": "ring", '
                f'"width": {height}, "height": {height}, "strokeWidth": 4, '
                "\"color\": $theme('progressColor'), "
                "\"backgroundColor\": $theme('progressBackgroundColor')}),\n" + ring_text + ")"
            )
            value = f"#if data.progressValue\n{chart}\n#else\n{value}\n#endif"
        else:
            value += (
                ",\n#if data.progressValue\n"
                'Progress({"value": data.progressValue, "total": 100, "height": 12, '
                '"width": "matchParent", "strokeWidth": 8, "color": $theme(\'progressColor\'), '
                "\"backgroundColor\": $theme('progressBackgroundColor')})\n#endif"
            )
    return _column(
        value + ",\n#if data.mainLabel\n" + label + "\n#endif",
        align=str(style.get("align", "start")),
    )


def template_source(business: str, shape: str, kind: str) -> str:
    style = STYLES.get(business)
    if style is None:
        raise ValueError(f"Missing business visual baseline: {business}")
    title = "location" if business == "WeatherOverview" else "title"
    family = "ScheduleOverview" if business == "CalendarOverview" else business
    small = shape in {"Compact", "Support"}
    title_size = 14 if shape == "Support" else (12 if not small or kind == "Pair" else 16)
    title_text = _text(f"data.{title}", title_size, 20, primary=small)
    fields = "firstLabel: string, firstValue: string, secondLabel: string, secondValue: string"
    if kind != "Pair":
        value_name = "mainNumberValue" if kind == "Number" else "mainTextValue"
        fields = f"{value_name}: string, mainLabel?: string"
        if small:
            label_title = _text(f"`${{data.{title}}} ${{data.mainLabel}}`", title_size, 20)
            title_text = f"#if data.mainLabel\n{label_title}\n#else\n{title_text}\n#endif"
        elif kind == "Number" and style.get("meter"):
            fields += ", progressValue?: number"
    icon = _icon(style, shape)
    header_items = [_column(title_text, weight=True), icon]
    if style.get("iconPosition") == "leading":
        header_items.reverse()
    if small:
        if kind == "Pair":
            body = _pair_body(style, shape)
        else:
            size = 14 if shape == "Support" else 16
            body = _column(_text(f"data.{value_name}", size, 20), weight=True)
        header_items = [_column(title_text, weight=True), body, icon]
    header = (
        'Row({"width": "matchParent", "itemMargin": 4, "alignItems": "center", '
        '"constraintSize": {"minWidth": 0, "minHeight": 0}},\n' + ",\n".join(header_items) + "\n)"
    )
    main = ""
    if not small:
        body = _pair_body(style, shape) if kind == "Pair" else _single_body(style, shape, kind)
        main = body + ",\n"
    action = ", actionId?: string" if shape == "Support" else ""
    on_click = ', "onClick": EventAction(props?.actionId)' if shape == "Support" else ""
    padding = ', "padding": {"left": 8, "right": 8}' if shape == "Support" else ""
    justify = "spaceBetween" if shape == "Full" else "start"
    return (
        f"#Template {family}General{kind}{shape}@1(data: {{ {title}: string, {fields}, "
        f"...supportValues: string[] }}, props: {{ {style.get('icon')}?: asset{action} }})\n"
        f'Column({{"_advancedComponent": "{family}", "width": "matchParent", '
        f'"height": "matchParent", "itemMargin": 4, "justifyContent": "{justify}", '
        f'"alignItems": "{style.get("align")}", "clip": true, '
        f'"constraintSize": {{"minWidth": 0, "minHeight": 0}}{padding}{on_click}}},\n'
        + header
        + ",\n"
        + main
        + _footer(style, shape)
        + "\n)\n#End\n"
    )


def generated_files() -> dict[Path, str]:
    files: dict[Path, str] = {}
    for manifest_path in sorted(PROVIDERS.glob("*/provider.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = manifest.get("templates")
        if not isinstance(entries, list):
            raise ValueError(f"Missing Provider templates: {manifest_path}")
        originals = [entry for entry in entries if not entry.get("fallbackOnly")]
        businesses: dict[str, str] = {}
        event_ids: dict[str, list[str]] = {}
        for entry in originals:
            business, capability = entry.get("businessId"), entry.get("capabilityId")
            if not isinstance(business, str) or not isinstance(capability, str):
                continue
            previous = businesses.get(business)
            if previous is not None and previous != capability:
                raise ValueError(f"Business has multiple capabilities: {business}")
            businesses[business] = capability
            events = event_ids.setdefault(business, [])
            for event in entry.get("supportedEventIds", ()):
                if event not in events:
                    events.append(event)
        if not businesses:
            continue
        sources: dict[str, list[str]] = {kind: [] for kind in KINDS}
        general_entries: list[dict[str, object]] = []
        for business, capability in businesses.items():
            family = "ScheduleOverview" if business == "CalendarOverview" else business
            style = STYLES.get(business)
            if style is None:
                raise ValueError(f"Missing business visual baseline: {business}")
            for kind in KINDS:
                if business == "CountdownOverview" and kind == "Pair":
                    # 当前能力只声明 countdownDays，没有可组成 Pair 的第二个输出字段。
                    continue
                for shape in SHAPES:
                    sources[kind].append(
                        template_source(business, shape, kind).replace("#endif,", "#endif")
                    )
                    entry = {
                        "templateId": f"{family}General{kind}{shape}@1",
                        "businessId": business,
                        "capabilityId": capability,
                        "description": (
                            f"{business} 通用 {kind} {shape}；仅无专用候选时使用；"
                            "按本业务的数值、文字或并列指标样式展示。"
                        ),
                        "fallbackOnly": True,
                        "generalContentKind": kind.lower(),
                        "entry": f"templates/general-{kind.lower()}.cardtpl",
                        "assetParameterSemanticTags": {style.get("icon"): [style.get("tag")]},
                    }
                    health_fields = HEALTH_FIELDS.get(business)
                    if health_fields is not None:
                        entry["generalDataPaths"] = [
                            "/" + field for field in (*health_fields, "targetDateText", "updatedAt")
                        ]
                    if shape == "Support":
                        entry["supportedEventIds"] = event_ids.get(business, [])
                    general_entries.append(entry)
        manifest["templates"] = [*originals, *general_entries]
        files[manifest_path] = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
        for kind, blocks in sources.items():
            if not blocks:
                continue
            files[manifest_path.parent / "templates" / f"general-{kind.lower()}.cardtpl"] = (
                "\n".join(blocks)
            )
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    mismatches: list[str] = []
    for path, source in generated_files().items():
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != source:
                mismatches.append(str(path))
        else:
            path.write_text(source, encoding="utf-8")
    if mismatches:
        print("Generated general templates are stale:\n" + "\n".join(mismatches))
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
