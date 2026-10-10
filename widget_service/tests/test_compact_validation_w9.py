"""W9 跨类别检查的交错顺序、门禁与诊断事实回归。"""

from services.card_validation.compact_validation.diagnostics import (
    CompactDiagnostic,
    DiagnosticCollector,
)
from services.card_validation.compact_validation.flows.w9 import (
    _collect_two_by_four_w9_content_errors,
    _collect_two_by_four_w9_weather_triplet_errors,
)
from services.compact_dsl_a2ui_converter import ComponentRow


def _text(identifier: str, content: str, size: int = 12) -> ComponentRow:
    return ComponentRow(
        identifier,
        "Text",
        {
            "content": content,
            "fontSize": size,
            "fontWeight": 400,
        },
    )


def _diagnostics(errors: DiagnosticCollector) -> list[CompactDiagnostic]:
    result = []
    for item in errors.records:
        assert isinstance(item, CompactDiagnostic)
        result.append(item)
    return result


def test_weather_triplet_preserves_interleaved_errors_and_skips_duplicate_field() -> None:
    zone = ComponentRow("weather", "Column", {})
    texts = [
        _text("temperature", "温度"),
        _text("duplicate_temperature", "温度", 20),
        _text("rain", "值", 14),
        _text("air", "空气"),
    ]
    paths = {
        "temperature": ["/data/weather/temperatureRangeText"],
        "duplicate_temperature": ["/data/weather/temperatureRangeText"],
        "rain": ["/data/weather/rainProbabilityPercent", "/data/weather/humidity"],
        "air": ["/data/weather/airQuality"],
    }
    errors = DiagnosticCollector()
    _collect_two_by_four_w9_weather_triplet_errors(
        zone, texts, [*texts, ComponentRow("icon", "Image", {})], paths, errors
    )
    items = _diagnostics(errors)
    assert [item.code for item in items] == [
        "COMPACT_LAYOUT_W9_WEATHER_DECORATION",
        "COMPACT_DISPLAY_W9_WEATHER_FIELD_COUNT",
        "COMPACT_LAYOUT_W9_WEATHER_FACT_ROWS",
        "COMPACT_LAYOUT_W9_WEATHER_TRIPLET_TYPOGRAPHY",
        "COMPACT_DISPLAY_W9_WEATHER_METRIC_LABEL",
    ]
    assert items[1].actual == {"occurrences": 2}
    assert items[1].expected == {"field": "temperature", "occurrences": 1}
    assert items[-1].expected == {"requiredLabel": "降雨"}
    assert items[-1].component_id == "rain"
    assert list(errors) == [item.legacy_message for item in items]


def test_weather_triplet_valid_and_incomplete_summaries_preserve_gate() -> None:
    zone = ComponentRow("weather", "Column", {})
    texts = [_text("temperature", "温度"), _text("rain", "降雨"), _text("air", "空气")]
    paths = {
        "temperature": ["/data/weather/temperatureRangeText"],
        "rain": ["/data/weather/rainProbabilityPercent"],
        "air": ["/data/weather/airQuality"],
    }
    errors = DiagnosticCollector()
    _collect_two_by_four_w9_weather_triplet_errors(zone, texts, texts, paths, errors)
    assert errors.records == []

    # 未包含空气字段时，原三项摘要规则整组不适用，即使另有装饰图标。
    partial = texts[:2]
    _collect_two_by_four_w9_weather_triplet_errors(
        zone, partial, [*partial, ComponentRow("icon", "Image", {})], paths, errors
    )
    assert errors.records == []


def test_business_action_ownership_and_count_remain_separate_display_checks() -> None:
    root = ComponentRow("root", "Row", {}, ("zone",))
    zone = ComponentRow("zone", "Column", {}, ("content", "action"))
    content = ComponentRow(
        "content", "Column", {"layoutWeight": 1, "justifyContent": "center"}, ("one", "two")
    )
    one = _text("one", "{{ ${/data/weather/temperature} }}")
    two = _text("two", "{{ ${/data/calendar/eventCount} }}")
    action = ComponentRow(
        "action",
        "Button",
        {
            "onClick": [{"call": "open", "args": {"id": {"path": "/data/other/id"}}}],
        },
    )
    components = {item.component_id: item for item in (root, zone, content, one, two, action)}
    errors = DiagnosticCollector()
    _collect_two_by_four_w9_content_errors(root, components, {}, errors)
    items = _diagnostics(errors)
    assert [item.code for item in items] == [
        "COMPACT_DISPLAY_W9_BUSINESS_ROOTS",
        "COMPACT_DISPLAY_W9_ACTION_OWNERSHIP",
        "COMPACT_DISPLAY_W9_ACTION_COUNT",
    ]
    assert all(item.category == "display" for item in items)
    assert items[1].actual == {
        "actionRoots": ["other"],
        "contentRoots": ["calendar", "weather"],
        "backboardId": "zone",
    }
    assert items[2].actual == {"visibleActions": 1}
    assert items[2].expected.get("maximumVisibleActions") == 0
