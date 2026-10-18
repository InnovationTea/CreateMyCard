"""期望对比的指纹口径：动作按位置识别、尺寸判定与尺寸门槛。"""

import base64
import io
import json

import pytest
from debug_tools.batch_testing.card_size import derive_from_genui, judge
from debug_tools.batch_testing.expect_compare import (
    detect_payload,
    fingerprint,
    _expected_items,
    _actual_items,
    compare,
    compare_live,
    detect_payload,
    expectation_runs,
    fingerprint,
    fingerprint_from_spec,
    match_pair,
)
from debug_tools.batch_testing.quality_import import import_batch
from PIL import Image

SOURCE_TYPE = "external-quality"


def genui(*components: dict) -> str:
    """按 A2UI 三段式拼出 genui 文本。"""
    rows = [
        {"version": "v0.9", "createSurface": {"surfaceId": "s", "catalogId": "c"}},
        {"version": "v0.9", "updateDataModel": {"surfaceId": "s", "path": "/", "value": {}}},
        {"version": "v0.9", "updateComponents": {
            "surfaceId": "s", "root": "root", "components": list(components)}},
    ]
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def png(width: int, height: int) -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


class FakeReader:
    def __init__(self, runs: dict):
        self.runs = runs

    def list_runs(self) -> list:
        return [item["summary"] for item in self.runs.values()]

    def get_run(self, run_id: str) -> dict:
        return self.runs[run_id]["summary"]

    def get_sample(self, run_id: str, sample_id: str) -> dict:
        return self.runs[run_id]["samples"][sample_id]


def import_side(sample_id: str, text: str, size: str, query: str,
                size_source: str = "declared", category: str = "") -> dict:
    row = {"id": sample_id, "title": sample_id, "query": query,
           "size": size, "sizeSource": size_source, "category": category}
    return {
        "summary": {"runId": "imp", "name": "期望批次", "sourceType": SOURCE_TYPE,
                    "samples": [row]},
        "samples": {sample_id: {"summary": {}, "attempts": [{
            "name": "input", "genui": text,
            "input": {**row, "imageFile": "image.png"},
        }]}},
    }


def import_run(entries: list[tuple[str, str, str, str, str]]) -> dict:
    """把多条导入样本拼成同一个期望批次，用于验证多对一配对。"""
    summary_samples = []
    samples = {}
    for sample_id, text, size, query, category in entries:
        side = import_side(sample_id, text, size, query, category=category)
        summary_samples.extend(side["summary"]["samples"])
        samples.update(side["samples"])
    return {
        "summary": {"runId": "imp", "name": "期望批次",
                    "sourceType": SOURCE_TYPE, "samples": summary_samples},
        "samples": samples,
    }


def batch_side(entries: list[tuple[str, str, str, str]], query_map=None) -> dict:
    query_map = query_map or {}
    samples = {}
    meta = []
    for sample_id, text, size, status in entries:
        meta.append({"id": sample_id, "title": sample_id, "query": query_map.get(sample_id, ""),
                     "size": size, "status": status})
        samples[sample_id] = {"summary": {}, "attempts": [
            {"name": "attempt_000", "genui": text}]}
    return {"summary": {"runId": "run1", "name": "批跑", "samples": meta}, "samples": samples}


def test_actions_are_collected_by_position_not_by_shape():
    text = genui(
        {"id": "root", "component": "Column", "layout": "S-title-content",
         "onClick": [{"call": "clickToApi", "args": {
             "intentName": "Weather", "params": {"path": "/data/weather/city"}}}]},
        {"id": "title", "component": "Text",
         "content": {"call": "formatString", "args": {"value": "今日 ${/data/weather/temp}"}}},
        {"id": "cta", "component": "PillButton", "content": "刷新",
         "onClick": {"call": "clickToDeeplink"}},
        {"id": "vip", "component": "Text", "content": "VIP",
         "styles": {"visibility": "{{ $__dataModel.weather.vip ? 'visible' : 'none' }}"}},
    )
    result = fingerprint(text)
    # 属性值位置的 {"call","args"} 是绑定，不是动作；事件槽里的 handler 才是动作。
    assert result["actions"] == ["clickToApi:Weather", "clickToDeeplink"]
    assert "/data/weather/city" in result["data"]
    assert "/data/weather/temp" in result["data"]
    assert "/weather/vip" in result["data"]
    # 指纹只有三个维度；尺寸不进指纹（同一组内容可以落成 2x2 或 2x4）。
    assert set(result) == {"data", "actions", "icons"}


def test_size_is_derived_from_layout_components_and_conflicts():
    def size_of(*components):
        return derive_from_genui(genui(*components))[0]

    assert size_of({"id": "root", "component": "Layout", "layout": "W-four-slots"}) == "2x4"
    assert size_of({"id": "b", "component": "CardButton", "content": "确定"}) == "2x4"
    assert size_of({"id": "root", "component": "Text", "content": "无证据"}) == ""
    conflict = genui(
        {"id": "root", "component": "Column", "layout": "S-center"},
        {"id": "b", "component": "CardButton", "content": "确定"},
    )
    size, reason = derive_from_genui(conflict)
    assert size == "" and "冲突" in reason


def test_declared_size_wins_and_conflict_is_reported_not_corrected():
    text = genui({"id": "root", "component": "Layout", "layout": "W-top-bottom"})
    verdict = judge("2x2", text)
    assert verdict["size"] == "2x2" and verdict["source"] == "declared"
    assert verdict["derived"] == "2x4" and "不一致" in verdict["warning"]
    missing = judge(None, text)
    assert missing["size"] == "2x4" and missing["source"] == "derived"
    unknown = judge(None, genui({"id": "x", "component": "Text", "content": "a"}))
    assert unknown["size"] == "2x2" and unknown["source"] == "fallback"


def test_import_judges_size_from_screenshot_and_rejects_illegal_declared(tmp_path):
    wide = genui({"id": "root", "component": "Text", "content": "横版"})
    imported = import_batch(tmp_path, {"name": "判定", "imageSource": "unknown", "samples": [
        {"id": "A", "query": "横版", "dsl": wide, "imageBase64": png(300, 150)}]})
    row = imported["samples"][0]
    assert row["size"] == "2x4" and row["sizeSource"] == "derived"

    conflict = import_batch(tmp_path, {"name": "冲突", "imageSource": "unknown", "samples": [
        {"id": "B", "query": "横版", "size": "2x2", "dsl": wide,
         "imageBase64": png(300, 150)}]})
    assert conflict["samples"][0]["size"] == "2x2"
    assert conflict["sizeWarnings"] and "不一致" in conflict["sizeWarnings"][0]

    with pytest.raises(ValueError, match="2x2 或 2x4"):
        import_batch(tmp_path, {"name": "非法", "imageSource": "unknown", "samples": [
            {"id": "C", "query": "横版", "size": "4x4", "dsl": wide,
             "imageBase64": png(300, 150)}]})


def test_size_never_changes_the_verdict_and_no_score_is_computed():
    """同一组数据、动作与图标，落成 2x2 或 2x4 都算匹配。"""
    reference = {"data": ["/a"], "actions": ["clickToApi:Go"], "icons": []}
    for size in ("2x2", "2x4", "", None):
        side = {**reference, **({"size": size} if size else {})}
        result = match_pair(reference, side, [], [])
        assert result["tier"] == "matched"
        assert set(result) == {"tier", "missingData", "missingActions", "missingIcons"}
    missing = match_pair(reference, {"data": [], "actions": [], "icons": []}, [], [])
    assert missing["tier"] == "none"


def test_match_pair_requires_every_requirement_in_enabled_dimensions():
    expected = {
        "data": ["/data/weather/condition", "/data/weather/temp"],
        "actions": ["clickToApi:Weather"],
        "icons": ["icons/sunny.png"],
        "size": "2x2",
    }
    complete = {
        "data": ["/data/weather/condition", "/data/weather/temp"],
        "actions": ["clickToApi:Weather"],
        "icons": ["theme/sunny.png"],
        "size": "2x2",
    }
    assert match_pair(expected, complete, [], [])["tier"] == "matched"
    partial = {**complete, "data": ["/data/weather/condition"]}
    result = match_pair(expected, partial, [], [])
    assert result["tier"] == "none"
    assert result["missingData"] == ["/data/weather/temp"]
    assert match_pair(expected, partial, [], [], dimensions=["actions"])["tier"] == "matched"
    missing_icon = {**complete, "icons": []}
    icon_result = match_pair(expected, missing_icon, [], [], dimensions=["icons"])
    assert icon_result["tier"] == "none"
    assert icon_result["missingIcons"] == ["icons/sunny.png"]


def test_compare_prefers_the_candidate_without_missing_items_regardless_of_size():
    """候选排序只认缺失项与同用例程度：尺寸不参与，内容全命中的胜出。"""
    expected_text = genui({"id": "root", "component": "Column", "layout": "S-center",
                           "content": "${/a}"},
                          {"id": "x", "component": "Text", "content": "${/b}"})
    complete = genui({"id": "root", "component": "Column", "layout": "W-top-bottom",
                      "content": "${/a}"},
                     {"id": "x", "component": "Text", "content": "${/b}"})
    partial = genui({"id": "root", "component": "Column", "layout": "S-center",
                     "content": "${/a}"})
    reader = FakeReader({
        "imp": import_side("Q001", expected_text, "2x2", "做个天气卡", size_source="derived"),
        "run1": batch_side(
            [("W24", complete, "2x4", "success"), ("S22", partial, "2x2", "success")],
            query_map={"W24": "做个天气卡", "S22": "做个天气卡"},
        ),
    })
    outcome = compare(reader, "imp", "run1")
    pair = outcome["pairs"][0]
    # 2x4 的那条内容全命中，2x2 那条少一项——尺寸不参与，所以选 2x4。
    assert pair["actual"]["sampleId"] == "W24"
    assert pair["tier"] == "matched"
    assert pair["expected"]["sizeSource"] == "derived"
    assert outcome["summary"]["matched"] == 1
    assert outcome["unmatchedActual"][0]["sampleId"] == "S22"


def test_incomplete_candidate_never_beats_a_complete_one_even_with_the_same_size():
    expected_text = genui({"id": "root", "component": "Column", "layout": "S-center",
                           "content": "${/a}"},
                          {"id": "x", "component": "Text", "content": "${/b}"})
    complete_wide = genui({"id": "root", "component": "Column", "layout": "W-top-bottom",
                           "content": "${/a}"},
                          {"id": "x", "component": "Text", "content": "${/b}"})
    incomplete_square = genui({"id": "root", "component": "Column", "layout": "S-center",
                               "content": "${/a}"})
    reader = FakeReader({
        "imp": import_side("Q001", expected_text, "2x2", "两张数据"),
        "run1": batch_side([
            ("W24", complete_wide, "2x4", "success"),
            ("S22", incomplete_square, "2x2", "success"),
        ], query_map={"W24": "两张数据", "S22": "两张数据"}),
    })
    outcome = compare(reader, "imp", "run1")
    pair = outcome["pairs"][0]
    # 内容完整即命中；尺寸不参与判定，2x4 也是已匹配。
    assert pair["actual"]["sampleId"] == "W24"
    assert pair["tier"] == "matched"
    assert pair["match"]["missingData"] == []
    assert [item["sampleId"] for item in outcome["unmatchedActual"]] == ["S22"]


def card(layout: str, query_identity: str) -> str:
    """同内容、不同布局的卡片，用于验证尺寸门槛与来源无关。"""
    return genui({"id": "root", "component": "Column", "layout": layout,
                  "onClick": [{"call": "clickToApi", "args": {"intentName": query_identity}}],
                  "content": "${/a}"})


def test_compare_live_pairs_session_records_without_a_batch_run():
    reader = FakeReader({"imp": import_side("Q001", card("S-center", "Go"), "2x2", "做个天气卡")})
    outcome = compare_live(reader, "imp", [
        {"id": "call-wide", "query": "做个天气卡", "genui": card("W-top-bottom", "Go")},
        {"id": "call-square", "query": "做个天气卡", "genui": card("S-center", "Go")},
    ])
    assert outcome["actualSource"] == "session"
    assert outcome["runName"] == "本次会话调试记录"
    pair = outcome["pairs"][0]
    # 未跑批也能对比：真实输出由页面提交，尺寸仍按 DSL 证据判定（但不再影响配对优先级）。
    assert pair["actual"]["sampleId"] == "call-wide"
    # 发起这条 2x4 的 DSL：尺寸照旧判定并展示，只是不再影响是否匹配。
    assert pair["actual"]["size"] == "2x4" and pair["actual"]["sizeSource"] == "derived"
    assert pair["tier"] == "matched"
    assert [item["sampleId"] for item in outcome["unmatchedActual"]] == ["call-square"]


def test_compare_live_rejects_unusable_payloads():
    reader = FakeReader({"imp": import_side("Q001", card("S-center", "Go"), "2x2", "做个天气卡")})
    with pytest.raises(ValueError, match="至少勾选"):
        compare_live(reader, "imp", [])
    with pytest.raises(ValueError, match="没有 genui"):
        compare_live(reader, "imp", [{"id": "a", "genui": "  "}])
    with pytest.raises(ValueError, match="标识非法"):
        compare_live(reader, "imp", [{"id": "../secret", "genui": card("S-center", "Go")}])
    with pytest.raises(ValueError, match="2x2 与 2x4"):
        compare_live(reader, "imp", [
            {"id": "a", "size": "4x4", "genui": card("S-center", "Go")}])
    with pytest.raises(ValueError, match="至少启用一个筛选维度"):
        compare_live(reader, "imp", [
            {"id": "a", "genui": card("S-center", "Go")}], options={"dimensions": []})
    with pytest.raises(ValueError, match="只支持数据、动作与图标"):
        compare_live(reader, "imp", [
            {"id": "a", "genui": card("S-center", "Go")}], options={"dimensions": ["size"]})


def test_icons_are_collected_from_image_components_in_both_dsl_shapes():
    text = genui(
        {"id": "root", "component": "Column", "layout": "S-center", "content": "${/a}"},
        {"id": "icon", "component": "Image", "src": "resources/base/media/alarm_fill_1.svg"},
        {"id": "bound", "component": "Image", "src": "${/data/icon}"},
    )
    assert fingerprint(text)["icons"] == ["resources/base/media/alarm_fill_1.svg"]
    compact = "\n".join(json.dumps(row) for row in [
        {"version": "v0.9", "updateComponents": {"components": [
            ["root", "Column", {"layout": "S-center", "content": "${/a}"}],
            ["icon", "Image", {"src": "resources/base/media/alarm_fill_1.svg"}],
            # 没有在素材能力表声明过的外链图片不是我们要识别的素材：忽略。
            ["external", "Image", {"src": "https://cdn.example.com/icons/rain.png?v=2"}],
        ]}},
    ])
    assert fingerprint(compact)["icons"] == ["resources/base/media/alarm_fill_1.svg"]


def test_semantic_icon_props_are_fingerprinted_without_image_rows():
    """正式紧凑 DSL 不写 Image，图标只能从语义属性里取。"""
    compact = "\n".join(json.dumps(row, ensure_ascii=False) for row in [
        ["root", "Layout", {"layout": "S-title-primary-secondary-action"},
         ["header", "count", "note", "cta"]],
        ["header", "SingleLineTitle", {"title": "发布会提醒", "fontSize": 12,
                                      "icon": "resources/base/media/alarm_fill_1.svg"}],
        ["count", "EmphasizedData", {"value": {"path": "/data/countdown/countdownDays"}}],
        ["note", "TableText", {"items": [{"label": "天气", "value": "晴"}], "fontSize": 12}],
        ["cta", "PillButton", {"label": "查看日程", "fontSize": 12,
                              "icon": "resources/base/media/calendar_fill.svg",
                              "onClick": [{"call": "clickToIntent", "args": {
                                  "intentName": "ViewCalendarEvent"}}]}],
        ["/data/countdown/countdownDays", 18],
    ])
    fp = fingerprint(compact)
    assert fp["icons"] == [
        "resources/base/media/alarm_fill_1.svg", "resources/base/media/calendar_fill.svg"]
    assert fp["actions"] == ["clickToIntent:ViewCalendarEvent"]
    result = match_pair(
        {"data": [], "actions": [], "icons": ["asset.calendar_fill", "asset.alarm_fill_1"],
         "size": "2x2"},
        fp, [], [], dimensions=["icons"])
    assert result["tier"] == "matched" and result["missingIcons"] == []


def test_info_block_visual_and_ratio_item_icons_are_collected():
    compact = "\n".join(json.dumps(row, ensure_ascii=False) for row in [
        ["root", "Layout", {"layout": "S-dual-info"}, ["left", "right"]],
        ["left", "InfoBlock", {"primaryText": {"path": "/data/earphone/leftBatteryLevel"},
                               "secondaryText": "充电中", "backgroundColor": "#CCFFFFFF",
                               "visual": {"type": "icon",
                                          "icon": "resources/base/media/icon_left.svg"}}],
        ["right", "InfoBlock", {"primaryText": {"path": "/data/earphone/rightBatteryLevel"},
                                 "secondaryText": "未充电", "backgroundColor": "#CCFFFFFF",
                                 "visual": {"type": "icon",
                                            "icon": "resources/base/media/icon_right.svg"}}],
    ])
    assert fingerprint(compact)["icons"] == [
        "resources/base/media/icon_left.svg", "resources/base/media/icon_right.svg"]


def test_icon_dimension_can_be_toggled_and_uses_the_resource_basename():
    expected = {"data": [], "actions": [], "icons": ["icons/sunny.png"], "size": "2x2"}
    actual = {"data": [], "actions": [], "icons": ["theme/other/sunny.png"], "size": "2x2"}
    enabled = match_pair(expected, actual, [], [], dimensions=["icons"])
    assert enabled["tier"] == "matched" and enabled["missingIcons"] == []
    disabled = match_pair(expected, actual, [], [], dimensions=["data"])
    assert disabled["tier"] == "no-fingerprint"
    missing = match_pair(
        expected, {"data": [], "actions": [], "icons": [], "size": "2x2"},
        [], [], dimensions=["icons"],
    )
    assert missing["tier"] == "none"
    assert missing["missingIcons"] == ["icons/sunny.png"]


def test_partial_requirements_are_not_a_match_in_strict_filtering():
    expected = {"data": ["/a", "/b"], "actions": [], "icons": [], "size": "2x2"}
    actual = {"data": ["/a"], "actions": [], "icons": [], "size": "2x2"}
    result = match_pair(expected, actual, [], [])
    assert result["tier"] == "none" and result["missingData"] == ["/b"]
    full = {"data": ["/a", "/b"], "actions": [], "icons": [], "size": "2x2"}
    assert match_pair(expected, full, [], [])["tier"] == "matched"
    # 其它尺寸只在内容完全命中后才降级为尺寸不一致。
    wide = {**actual, "size": "2x4"}
    assert match_pair(expected, wide, [], [])["tier"] == "none"


def test_cardspec_fingerprint_reads_data_actions_and_assets():
    card_spec = {
        "title": "天气",
        "suggestSize": "2x2",
        "dataBindings": [{
            "capabilityId": "ViewWeather",
            "arguments": {"prefectureName": "杭州市"},
            "writeResultTo": "/data/weather",
        }],
        "events": [{
            "target": "root",
            "handler": {"call": "clickToDeeplink", "args": {"intentName": "Weather_CityCode"}},
        }],
        "candidateAssetIds": ["asset.sun_max", "asset.local_fill"],
    }
    fp = fingerprint_from_spec(card_spec)
    assert fp["data"] == ["/data/weather"]
    assert fp["actions"] == ["clickToDeeplink:Weather_CityCode"]
    assert fp["icons"] == ["local_fill", "sun_max"]

    request = {
        "candidateDataBindings": [{
            "capabilityId": "GetPhoneBatteryInfo",
            "arguments": {},
            "writeResultTo": "/data/phoneBattery",
        }],
        "candidateEventCandidates": [{
            "capabilityId": "event.open.settings",
            "action": {"call": "clickToIntent", "args": {"intentName": "Battery_Settings"}},
        }],
    }
    request_fp = fingerprint_from_spec(request)
    assert request_fp["data"] == ["/data/phoneBattery"]
    assert request_fp["actions"] == ["clickToIntent:Battery_Settings"]
    assert request_fp["icons"] == []


def test_expected_items_prefer_cardspec_and_fall_back_to_dsl_per_dimension():
    text = genui(
        {"id": "root", "component": "Column", "layout": "S-center",
         "content": "${/data/dsl/condition}",
         "onClick": [{"call": "clickToApi", "args": {"intentName": "DslAction"}}]},
        {"id": "icon", "component": "Image", "src": "resources/base/media/icon_left.svg"},
    )
    side = import_side("Q001", text, "2x2", "天气")
    side["samples"]["Q001"]["attempts"][0]["input"]["cardSpec"] = {
        "dataBindings": [{"writeResultTo": "/data/weather"}],
        "events": [{
            "handler": {"call": "clickToDeeplink", "args": {"intentName": "Weather_CityCode"}},
        }],
    }
    expected, _ = _expected_items(FakeReader({"imp": side}), "imp", side["summary"])
    fp = expected[0]["fingerprint"]
    assert fp["data"] == ["/data/weather"]
    assert fp["actions"] == ["clickToDeeplink:Weather_CityCode"]
    # CardSpec 没有图标字段时仍沿用 DSL 的静态资源指纹。
    assert fp["icons"] == ["resources/base/media/icon_left.svg"]


def test_compare_live_groups_multiple_expected_onto_one_actual_with_labels_and_category():
    text = genui(
        {"id": "root", "component": "Column", "layout": "S-center",
         "onClick": [{"call": "clickToDeeplink", "args": {"intentName": "Weather"}}],
         "content": "${/data/weather/current/condition}"},
        {"id": "icon", "component": "Image", "src": "resources/base/media/alarm_fill_1.svg"},
    )
    reader = FakeReader({"imp": import_run([
        # 同一条 Query 的两份期望（不同样本 ID）落在同一张实际卡片上，就是多对一。
        ("Q001", text, "2x2", "天气", "天气"),
        ("Q002", text, "2x2", "天气", "天气"),
    ])})
    outcome = compare_live(reader, "imp", [
        {"id": "call-1", "query": "天气", "genui": text},
    ], options={"dimensions": ["data", "actions", "icons"]})
    assert outcome["options"] == {"dimensions": ["data", "actions", "icons"]}
    assert outcome["categories"] == ["天气"]
    assert [pair["actual"]["sampleId"] for pair in outcome["pairs"]] == ["call-1", "call-1"]
    assert outcome["summary"]["matched"] == 2
    assert "多对一" in outcome["warnings"][0]
    pair = outcome["pairs"][0]
    assert pair["expected"]["category"] == "天气"
    assert pair["expected"]["labels"]["data"]["/data/weather/current/condition"] == "天气状况"
    assert pair["expected"]["labels"]["actions"]["clickToDeeplink:Weather"] == "跳转链接 · 天气"
    assert pair["expected"]["labels"]["icons"][
        "resources/base/media/alarm_fill_1.svg"
    ] == "闹钟单色图标"
    assert pair["actual"]["labels"]["data"]["/data/weather/current/condition"] == "天气状况"


def test_labels_cover_explicit_requirements_and_skip_technical_data_root():
    text = genui({"id": "root", "component": "Column", "layout": "S-center",
                  "onClick": [{"call": "clickToDeeplink",
                               "args": {"intentName": "Battery_Settings"}}],
                  "content": "${/data/battery/level}"})
    side = import_side("Q001", text, "2x2", "电量")
    input_meta = side["samples"]["Q001"]["attempts"][0]["input"]
    input_meta["expectedData"] = ["/data/battery/level"]
    input_meta["expectedActions"] = ["Battery_Settings"]
    outcome = compare_live(FakeReader({"imp": side}), "imp", [
        {"id": "call-1", "query": "电量", "genui": text},
    ])
    expected = outcome["pairs"][0]["expected"]
    assert expected["labels"]["data"]["/data/battery/level"] == "电量 · 电量等级"
    assert expected["labels"]["actions"]["Battery_Settings"] == "电池设置"
    assert expected["labels"]["actions"][
        "clickToDeeplink:Battery_Settings"
    ] == "跳转链接 · 电池设置"


def test_import_persists_batch_and_sample_categories(tmp_path):
    text = genui({"id": "root", "component": "Text", "content": "分类"})
    imported = import_batch(tmp_path, {
        "name": "分类批次", "imageSource": "unknown", "category": "天气",
        "samples": [
            {"id": "A", "query": "天气", "dsl": text, "imageBase64": png(100, 100)},
            {"id": "B", "query": "电量", "category": "电量", "dsl": text,
             "imageBase64": png(100, 100)},
        ],
    })
    rows = {item["id"]: item for item in imported["samples"]}
    assert imported["category"] == "天气"
    assert rows["A"]["category"] == "天气"
    assert rows["B"]["category"] == "电量"
    meta = json.loads(
        (tmp_path / imported["runId"] / "A" / "input" / "input.json").read_text("utf-8")
    )
    assert meta["category"] == "天气"
    with pytest.raises(ValueError, match="数据分类不能为空"):
        import_batch(tmp_path, {
            "name": "空分类", "imageSource": "unknown", "category": "  ",
            "samples": [{"id": "C", "query": "空", "dsl": text,
                         "imageBase64": png(100, 100)}],
        })


def test_explicit_icons_override_the_dsl_fingerprint():
    """期望侧显式写图标时以显式为准：DSL 里出现的图标不再作为需求项。"""
    expected = {"data": [], "actions": [], "icons": ["icons/sunny.png"], "size": "2x2"}
    actual = {"data": [], "actions": [], "icons": ["icons/moon.png"], "size": "2x2"}
    explicit = match_pair(expected, actual, [], [], dimensions=["icons"],
                          explicit_icons=["icons/moon.png"])
    assert explicit["tier"] == "matched" and explicit["missingIcons"] == []
    missing = match_pair(expected, actual, [], [], dimensions=["icons"],
                         explicit_icons=["icons/star.png"])
    assert missing["tier"] == "none" and missing["missingIcons"] == ["icons/star.png"]


def test_import_keeps_explicit_icons_and_uses_them_in_the_comparison(tmp_path):
    """导入时显式图标要落进 input.json，并在对比时按显式需求项判定。"""
    text = genui(
        {"id": "root", "component": "Text", "content": "无图标卡片"},
    )
    imported = import_batch(tmp_path, {
        "name": "显式图标",
        "imageSource": "unknown",
        "samples": [{
            "id": "Q1", "query": "图标", "size": "2x2", "dsl": text,
            "imageBase64": png(100, 100),
            "expectedIcons": ["resources/base/media/bell_fill.svg"],
        }],
    })
    meta = json.loads(
        (tmp_path / imported["runId"] / "Q1" / "input" / "input.json").read_text("utf-8")
    )
    assert meta["expectedIcons"] == ["resources/base/media/bell_fill.svg"]

    actual_text = genui({"id": "root", "component": "Text", "content": "实际卡片"})
    reader = FakeReader({
        imported["runId"]: {
            "summary": {"runId": imported["runId"], "name": "期望批次",
                        "sourceType": SOURCE_TYPE,
                        "samples": [{"id": "Q1", "title": "Q1", "query": "图标",
                                     "size": "2x2", "sizeSource": "declared",
                                     "category": ""}]},
            "samples": {"Q1": {"summary": {}, "attempts": [
                {"name": "input", "genui": text, "input": meta}]}},
        },
        "run-1": {
            "summary": {"runId": "run-1", "name": "实际批跑", "total": 1,
                        "samples": [{"id": "Q1", "status": "success", "size": "2x2"}]},
            "samples": {"Q1": {"summary": {}, "attempts": [
                {"name": "attempt_000", "genui": actual_text}]}},
        },
    })
    result = compare(reader, imported["runId"], "run-1", {"dimensions": ["icons"]})
    pair = result["pairs"][0]
    assert pair["tier"] == "none"
    assert pair["match"]["missingIcons"] == ["resources/base/media/bell_fill.svg"]
    assert pair["expected"]["explicit"]["icons"] == ["resources/base/media/bell_fill.svg"]
    # 标签里也要带上显式图标的中文名，页面才能和原始素材名一起展示。
    assert pair["expected"]["labels"]["icons"]["resources/base/media/bell_fill.svg"]


def test_expectation_runs_keeps_only_import_batches_newest_first():
    reader = FakeReader({
        "old": {"summary": {"runId": "old", "sourceType": SOURCE_TYPE,
                            "startedAt": "2026-01-01T00:00:00"}},
        "new": {"summary": {"runId": "new", "sourceType": SOURCE_TYPE,
                            "startedAt": "2026-02-01T00:00:00"}},
        "batch": {"summary": {"runId": "batch", "startedAt": "2026-03-01T00:00:00"}},
    })
    assert [item["runId"] for item in expectation_runs(reader)] == ["new", "old"]


def import_pool_side(run_id: str, started: str, sample_id: str, data: list, text: str) -> dict:
    """一条导入批次的内存形态：summary 里带 startedAt，样本里带显式期望数据。"""
    row = {"id": sample_id, "title": sample_id, "query": "池", "size": "2x2",
           "sizeSource": "declared", "category": ""}
    return {
        "summary": {"runId": run_id, "name": run_id, "sourceType": SOURCE_TYPE,
                    "startedAt": started, "samples": [row]},
        "samples": {sample_id: {"summary": {}, "attempts": [{
            "name": "input", "genui": text,
            "input": {**row, "imageFile": "image.png", "expectedData": data}}]}},
    }


def test_compare_without_a_batch_pools_imports_and_keeps_the_newest_sample():
    """不挑批次：全部导入批次的期望合成一池，同一个样本 ID 取新批次。"""
    text = genui({"id": "root", "component": "Text", "content": "卡片"})
    actual_text = genui({"id": "root", "component": "Text", "content": "实际"})
    reader = FakeReader({
        "old-batch": import_pool_side("old-batch", "2026-01-01T00:00:00", "Q1", ["/data/old"], text),
        "new-batch": import_pool_side("new-batch", "2026-02-01T00:00:00", "Q1", ["/data/new"], text),
        "run-1": {
            "summary": {"runId": "run-1", "name": "实际批跑", "total": 1,
                        "samples": [{"id": "B1", "status": "success", "size": "2x2"}]},
            "samples": {"B1": {"summary": {}, "attempts": [
                {"name": "attempt_000", "genui": actual_text}]}},
        },
    })
    result = compare(reader, "", "run-1", {"dimensions": ["data"]})
    assert result["importRunId"] == ""
    assert result["importName"] == "已导入的期望输出（1 条 / 2 个批次）"
    assert len(result["pairs"]) == 1
    assert result["pairs"][0]["expected"]["explicit"]["data"] == ["/data/new"]


def test_edited_batch_wins_the_pool_even_if_it_was_imported_first():
    """二次修改要生效：改过的批次（updatedAt 更新）在期望池里优先于更晚导入的旧版本。"""
    text = genui({"id": "root", "component": "Text", "content": "卡片"})
    older = import_pool_side("older", "2026-01-01T00:00:00", "Q1", ["/data/old"], text)
    later = import_pool_side("later", "2026-05-01T00:00:00", "Q1", ["/data/later"], text)
    # 先导入的那批被就地修改过：updatedAt 晚于另一批的导入时间。
    older["summary"]["updatedAt"] = "2026-09-01T00:00:00"
    reader = FakeReader({
        "older": older,
        "later": later,
        "run-1": {
            "summary": {"runId": "run-1", "name": "实际批跑", "total": 1,
                        "samples": [{"id": "Q1", "status": "success", "size": "2x2"}]},
            "samples": {"Q1": {"summary": {}, "attempts": [
                {"name": "attempt_000", "genui": text}]}},
        },
    })
    assert [item["runId"] for item in expectation_runs(reader)][:2] == ["older", "later"]
    result = compare(reader, "", "run-1", {"dimensions": ["data"]})
    assert result["pairs"][0]["expected"]["explicit"]["data"] == ["/data/old"]


def test_import_without_dsl_keeps_its_screenshot_and_explicit_requirements():
    """只导入 ID＋截图时 genui.jsonl 是空的，读取仍要带出 input.json 里的截图与显式期望项。"""
    row = {"id": "S1", "title": "S1", "query": "", "size": "2x2",
           "sizeSource": "derived", "category": ""}
    reader = FakeReader({
        "imp": {
            "summary": {"runId": "imp", "name": "期望批次", "sourceType": SOURCE_TYPE,
                        "samples": [row]},
            "samples": {"S1": {"summary": row, "attempts": [{
                "name": "input", "genui": "",
                "input": {**row, "imageFile": "image.png",
                          "expectedData": ["/data/weather/current/condition"]},
            }]}},
        },
    })
    items, warnings = _expected_items(reader, "imp", reader.get_run("imp"))
    assert warnings == []
    item = items[0]
    assert item["genui"] == ""
    assert item["imageUrl"] == "/debug/expect/runs/imp/samples/S1/input-image"
    assert item["explicit"]["data"] == ["/data/weather/current/condition"]


def test_compare_without_a_batch_reports_when_nothing_is_imported():
    reader = FakeReader({
        "run-1": {"summary": {"runId": "run-1", "samples": []}, "samples": {}},
    })
    with pytest.raises(ValueError, match="还没有导入任何期望输出"):
        compare(reader, "", "run-1", {"dimensions": ["data"]})


def test_strong_binding_pairs_by_category_data_and_actions():
    """ID 只是标识：不同名、不同 Query 时，分类＋数据＋动作全部成立即视为同一条用例。"""
    text = genui({"id": "root", "component": "Column", "layout": "S-center",
                  "content": "${/data/weather/current/condition}",
                  "onClick": [{"call": "clickToDeeplink",
                               "args": {"intentName": "Weather_CityCode"}}]})
    expected_row = {"id": "E1", "title": "E1", "query": "期望的说法", "size": "2x2",
                    "sizeSource": "declared", "category": "天气"}
    actual_row = {"id": "A9", "title": "A9", "query": "完全不同的说法", "size": "2x2",
                  "status": "success", "category": "天气"}

    def build(actual_category: str) -> FakeReader:
        row = {**actual_row, "category": actual_category}
        return FakeReader({
            "imp": {
                "summary": {"runId": "imp", "name": "期望批次", "sourceType": SOURCE_TYPE,
                            "samples": [expected_row]},
                "samples": {"E1": {"summary": expected_row, "attempts": [{
                    "name": "input", "genui": text,
                    "input": {**expected_row,
                              "expectedData": ["/data/weather/current/condition"],
                              "expectedActions": ["clickToDeeplink:Weather_CityCode"]}}]}},
            },
            "run-1": {
                "summary": {"runId": "run-1", "name": "批跑", "total": 1, "samples": [row]},
                "samples": {"A9": {"summary": {}, "attempts": [
                    {"name": "attempt_000", "genui": text}]}},
            },
        })

    paired = compare(build("天气"), "imp", "run-1", {"dimensions": ["data", "actions"]})
    assert paired["pairs"][0]["actual"] is not None
    assert paired["pairs"][0]["actual"]["sampleId"] == "A9"
    assert paired["pairs"][0]["tier"] == "matched"

    # 分类不同 → 强绑定不成立；名字与 Query 也都不同 → 老实报「没有对应的实际输出」。
    unbound = compare(build("日程"), "imp", "run-1", {"dimensions": ["data", "actions"]})
    assert unbound["pairs"][0]["actual"] is None
    assert unbound["pairs"][0]["tier"] == "no-actual"


def test_strong_binding_needs_at_least_one_declared_item():
    """三项全空的期望不能靠强绑定硬配：它仍旧只会和同名或同 Query 的实际输出配对。"""
    static = genui({"id": "root", "component": "Text", "content": "慢慢来，比较快"})
    expected_row = {"id": "E2", "title": "E2", "query": "", "size": "2x2",
                    "sizeSource": "declared", "category": ""}
    actual_row = {"id": "A1", "title": "A1", "query": "", "size": "2x2",
                  "status": "success", "category": ""}
    reader = FakeReader({
        "imp": {"summary": {"runId": "imp", "name": "期望批次", "sourceType": SOURCE_TYPE,
                            "samples": [expected_row]},
                "samples": {"E2": {"summary": expected_row, "attempts": [
                    {"name": "input", "genui": static, "input": {**expected_row}}]}}},
        "run-1": {"summary": {"runId": "run-1", "name": "批跑", "total": 1,
                              "samples": [actual_row]},
                  "samples": {"A1": {"summary": {}, "attempts": [
                      {"name": "attempt_000", "genui": static}]}}},
    })
    outcome = compare(reader, "imp", "run-1", {"dimensions": ["data", "actions"]})
    assert outcome["pairs"][0]["tier"] == "no-actual"


def test_unrelated_actual_is_never_paired_even_without_requirements():
    """没有声明需求项的期望也只和同一条用例比，无关卡片不硬凑。"""
    static = genui({"id": "root", "component": "Text", "content": "慢慢来，比较快"})
    reader = FakeReader({
        "imp": import_side("Q001", static, "2x2", "给卡片放一句话"),
        "run1": batch_side([("W24", static, "2x2", "success")],
                           query_map={"W24": "西湖天气"}),
    })
    outcome = compare(reader, "imp", "run1")
    pair = outcome["pairs"][0]
    assert pair["actual"] is None
    assert pair["tier"] == "no-actual"
    assert "没有同名或同 Query" in "".join(outcome["warnings"])
    assert [item["sampleId"] for item in outcome["unmatchedActual"]] == ["W24"]


def test_same_query_is_enough_to_pair_two_different_sample_ids():
    """同名不是唯一口径：Query 完全相同也算同一条用例，可以比。"""
    static = genui({"id": "root", "component": "Text", "content": "慢慢来，比较快"})
    reader = FakeReader({
        "imp": import_side("Q001", static, "2x2", "西湖天气"),
        "run1": batch_side([("W24", static, "2x2", "success")],
                           query_map={"W24": "西湖天气"}),
    })
    outcome = compare(reader, "imp", "run1")
    pair = outcome["pairs"][0]
    assert pair["actual"]["sampleId"] == "W24"
    assert pair["tier"] == "no-fingerprint"


def imported_actual_side(sample_id: str, text: str, query: str = "") -> dict:
    """导入的「实际输出」批次形态：status 是 imported，genui 在 input 里，截图可以没有。"""
    row = {"id": sample_id, "title": sample_id, "query": query, "size": "2x2",
           "status": "imported", "sourceType": SOURCE_TYPE, "purpose": "actual"}
    return {
        "summary": {"runId": "act", "name": "外部实际输出", "sourceType": SOURCE_TYPE,
                    "purpose": "actual", "startedAt": "2026-03-01T00:00:00",
                    "samples": [row]},
        "samples": {sample_id: {"summary": {}, "attempts": [{
            "name": "input", "genui": text,
            "input": {**row, "imageFile": ""}}]}},
    }


def test_imported_actual_batch_is_a_valid_actual_source():
    """外部产出的真实输出可以按批次导入，再直接与期望配对（没填 Query 时只按样本 ID）。"""
    text = genui({"id": "root", "component": "Text",
                  "content": {"path": "/data/weather/temp"}})
    reader = FakeReader({
        "imp": import_side("Q001", text, "2x2", ""),
        "act": imported_actual_side("Q001", text),
    })
    outcome = compare(reader, "", "act")
    assert outcome["importName"].startswith("已导入的期望输出")
    pair = outcome["pairs"][0]
    assert pair["actual"]["sampleId"] == "Q001"
    assert pair["actual"]["attempt"] == "input"
    assert pair["actual"]["imageUrl"] is None
    assert pair["tier"] in {"matched", "no-fingerprint"}
    assert any("导入批次" in note for note in outcome["warnings"])


def test_actual_purpose_batches_stay_out_of_the_expectation_pool():
    """实际输出批次不能当期望，也不能被画廊/池子收进去，否则会自己和自己配对。"""
    text = genui({"id": "root", "component": "Text", "content": "卡片"})
    reader = FakeReader({
        "act": imported_actual_side("Q001", text),
        "run1": batch_side([("Q001", text, "2x2", "success")]),
    })
    assert expectation_runs(reader) == []
    with pytest.raises(ValueError, match="还没有导入任何期望输出"):
        compare(reader, "", "run1")
    with pytest.raises(ValueError, match="必须是导入的期望输出批次"):
        compare(reader, "act", "run1")


def test_expectation_batch_is_rejected_as_actual_source():
    """左侧的期望批次不能选成实际来源：方向搞反了要报错，而不是静默比出一份假结论。"""
    text = genui({"id": "root", "component": "Text", "content": "卡片"})
    reader = FakeReader({"imp": import_side("Q001", text, "2x2", "显示天气")})
    with pytest.raises(ValueError, match="而不是期望导入批次"):
        compare(reader, "imp", "imp")


def test_detect_payload_routes_cardspec_and_dsl_by_shape():
    """导入识别只看结构：CardSpec 与 genui DSL 都要给出可直接填入需求项的指纹。"""
    spec = {"title": "西湖天气", "suggestSize": "2x4", "dataBindings": [
        {"capabilityId": "ViewWeather", "writeResultTo": "/data/weather"}],
        "candidateAssetIds": ["asset.sun_max"]}
    pretty = json.dumps(spec, ensure_ascii=False, indent=2)
    detected = detect_payload(pretty)
    assert detected["kind"] == "cardspec"
    assert detected["size"] == "2x4"
    assert detected["fingerprint"]["data"] == ["/data/weather"]
    assert detected["fingerprint"]["icons"] == ["sun_max"]

    dsl = genui({"id": "root", "component": "PillButton", "content": "查看",
                 "onClick": [{"call": "clickToIntent", "args": {"intentName": "Demo"}}]})
    detected = detect_payload(dsl)
    assert detected["kind"] == "dsl"
    assert detected["fingerprint"]["actions"] == ["clickToIntent:Demo"]

    assert detect_payload("  \ufeff ")["kind"] == "empty"
    assert detect_payload("这不是 JSON")["kind"] == "unknown"


def test_imported_actual_batch_keeps_its_screenshot_for_reference(tmp_path):
    """带截图导入的实际输出，页面上仍要能翻出参考图；没截图就不给链接。"""
    text = genui({"id": "root", "component": "Text", "content": "卡片"})
    summary = import_batch(tmp_path, {
        "name": "实际批次", "imageSource": "unknown", "purpose": "actual",
        "samples": [{"id": "Q001", "dsl": text, "imageBase64": png(60, 120)}],
    })
    row = summary["samples"][0]
    assert row["purpose"] == "actual"
    stored = json.loads(
        (tmp_path / summary["runId"] / "Q001" / "input" / "input.json")
        .read_text(encoding="utf-8")
    )
    reader = FakeReader({summary["runId"]: {
        "summary": summary,
        "samples": {"Q001": {"summary": {}, "attempts": [{
            "name": "input", "genui": text,
            "input": {**row, "imageFile": stored["imageFile"]}}]}}}})
    items, _ = _actual_items(reader, summary["runId"], summary)
    assert items[0]["imageUrl"] == (
        f"/debug/expect/runs/{summary['runId']}/samples/Q001/input-image"
    )
    # 60x120 的竖图既不是 2x2 也不是 2x4 的比例；这里要的是「截图带回来了」，尺寸沿用导入判定。
    assert items[0]["size"] in {"2x2", "2x4"}
    assert stored["imageFile"]


def test_asset_slots_count_as_icons_not_business_data():
    """模板把素材写成 ``Image.src = {path: "/asset/meetingIcon"}``：归图标，别混进业务数据。"""
    text = "\n".join(json.dumps(row, ensure_ascii=False) for row in [
        {"version": "v0.9", "createSurface": {"surfaceId": "s", "catalogId": "c"}},
        {"version": "v0.9", "updateComponents": {"surfaceId": "s", "root": "root", "components": [
            {"id": "icon", "component": "Image", "src": {"path": "/asset/meetingIcon"}},
            {"id": "title", "component": "Text", "content": {"path": "/meeting/title"}},
        ]}},
        {"version": "v0.9", "updateDataModel": {"surfaceId": "s", "path": "/", "value": {
            "meeting": {"title": "评审会"},
            "asset": {"meetingIcon": "resources/base/media/icon_meeting.svg"},
        }}},
    ])
    fp = fingerprint(text)
    assert fp["data"] == ["/meeting/title"]
    # 资源名才是素材身份：与 CardSpec 的 asset.icon_meeting 归一后同名，也与能力库的中文标签对得上。
    assert fp["icons"] == ["resources/base/media/icon_meeting.svg"]

    # 槽位没有登记资源时既不知道是哪个素材，也不在能力表里：不识别，别造出假需求项。
    unmapped = genui({"id": "icon", "component": "Image", "src": {"path": "/asset/meetingIcon"}})
    assert fingerprint(unmapped) == {"data": [], "actions": [], "icons": []}


def test_pretty_printed_json_array_reads_like_jsonl():
    """模板文件是缩进过的 JSON 数组：识别预览与比对必须给出同一个指纹。"""
    rows = [
        {"version": "v0.9", "updateComponents": {"surfaceId": "s", "root": "root", "components": [
            {"id": "icon", "component": "Image", "src": {"path": "/asset/meetingIcon"}},
            {"id": "title", "component": "Text", "content": {"path": "/meeting/title"}},
        ]}},
        {"version": "v0.9", "updateDataModel": {"surfaceId": "s", "path": "/", "value": {
            "asset": {"meetingIcon": "resources/base/media/icon_meeting.svg"}}}},
    ]
    pretty = json.dumps(rows, ensure_ascii=False, indent=2)
    compact = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    assert fingerprint(pretty) == fingerprint(compact)
    assert fingerprint(pretty) == {
        "data": ["/meeting/title"], "actions": [],
        "icons": ["resources/base/media/icon_meeting.svg"],
    }
    assert detect_payload(pretty)["fingerprint"] == fingerprint(pretty)
