"""给「期望对比」灌一批看得见的演示数据：真实 Phase 入参当期望，批跑结果当实际。

左侧（期望批次）取 `taskspec/Phase/Q001..Q010` 的真实入参：Query、候选数据字段、
候选事件与声明尺寸原样使用，DSL 用同目录批跑产物里的模型 DSL，再按需要改出几种
**故意不命中**的形态，让匹配层级、缺项与同内容跨尺寸仍算匹配都能在页面上看出来：

* Q001 / Q001B：两份完全相同的期望 → 多对一（同一张实际卡片承接两条期望）
* Q002 / Q004 / Q005 / Q007 / Q008 / Q010：期望需求项与实际完全一致 → 已匹配
* Q003：期望动作写成 `ViewCalendarEventX`（实际是 `ViewCalendarEvent`）→ 未匹配（动作缺 1）
* Q009：期望左耳分区用候选素材 `bolt_fill`，实际用的是 `icon_left` → 未匹配（图标缺 1）
* Q006：期望按 2x4 搭（`W-top-bottom`＋`TextBlock` 明细），实际是 2x2 → 仍算已匹配（尺寸不进指纹）

右侧（实际）直接用已落盘的批跑运行 `phase_q001_q010_model`，不需要浏览器里先有调试记录；
脚本同时用同目录 `session/records.json` 走一遍会话来源，确认两条来源口径一致。

所有期望样本的 DSL 都先过 `convert_compact_dsl_to_a2ui`，过不了直接报错，避免演示数据
在页面上渲染失败。产物落在调试平台里，随时可在「期望数据画廊」删除整批。
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont

DEBUG_TOOLS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = DEBUG_TOOLS_ROOT.parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from debug_tools.make_phase_batch_run import MEDIA_ROOT, THEMES  # noqa: E402

PHASE_SOURCE = REPOSITORY_ROOT.parent / "taskspec" / "Phase"
MODEL_RUN = DEBUG_TOOLS_ROOT / "Datasets" / "phase_Q001_Q010_model_run" / "output"
RUN_ID = "phase_q001_q010_model"
API_BASE = "http://127.0.0.1:8888/debug"
BATCH_NAME = "Demo 期望_Phase Q001–Q010（含未命中样例）"

FONT_PATH = (REPOSITORY_ROOT / "render" / "genui-sdk" / "HarmonyOS-Sans" / "HarmonyOS Sans"
             / "HarmonyOS_Sans_SC" / "HarmonyOS_Sans_SC_Medium.ttf")

CATEGORY = {
    "Q001": "天气", "Q001B": "天气", "Q002": "天气", "Q004": "天气", "Q005": "天气",
    "Q010": "天气", "Q003": "日程", "Q006": "日程", "Q007": "日程", "Q009": "设备",
    "Q008": "出行",
}

# 样本级差异：这里只写"和真实入参不同的那一处"，其余全部沿用入参。
VARIANTS: dict[str, dict[str, object]] = {
    "Q003": {"actions": ["ViewCalendarEventX"],
             "note": "期望动作写成 ViewCalendarEventX（实际是 ViewCalendarEvent）"},
    "Q009": {"info_block_icon": {"node": "left", "asset": "bolt_fill"},
             "note": "期望左耳分区用候选素材 bolt_fill，实际用的是 icon_left"},
    "Q006": {"size": "2x4",
             "note": "期望按 2x4 搭、实际是 2x2：同一组内容仍算已匹配"},
}

SAMPLE_IDS = [f"Q{index:03d}" for index in range(1, 11)] + ["Q001B"]


def media_uri(asset: str) -> str:
    """图标必须真实存在于渲染资源目录，扩展名按磁盘上的实际文件写。"""
    name = asset.removeprefix("asset.")
    for suffix in (".svg", ".png", ".jpg", ".jpeg"):
        if (MEDIA_ROOT / f"{name}{suffix}").is_file():
            return f"resources/base/media/{name}{suffix}"
    raise FileNotFoundError(f"渲染资源目录缺少素材：{name}")


def q006_two_by_four() -> list[list]:
    """Q006 的 2x4 期望卡片：按 layouts/2x4.md 的 W-top-bottom 合法组合搭。

    主体只能用 Group(label-value)，明细槽只接受 TextBlock／TopTextBottomValue／SummaryList；
    TextBlock 要求 2~4 项，正好承接两场会议的标题与开始时间。
    """
    gradient = {"direction": "RightBottom",
                "colors": [[THEMES["Q006"][0], 0], [THEMES["Q006"][1], 1]]}
    return [
        ["root", "Layout", {"layout": "W-top-bottom", "variant": "bottom-details",
                            "linearGradient": gradient}, ["primary_area", "details"]],
        ["meeting_title", "SecondaryBody", {"items": [{"value": "下一场会议"}], "fontSize": 14}],
        ["meeting_slot", "EmphasizedData", {
            "value": {"path": "/data/calendar/events/0/title"}, "fontSize": 30}],
        ["primary_area", "Group", {"variant": "label-value"},
         ["meeting_title", "meeting_slot"]],
        ["details", "TextBlock", {"items": [{
            "label": "产品立项会",
            "value": {"path": "/data/calendar/events/0/dtStart"}},
            {"label": "客户交流会",
             "value": {"path": "/data/calendar/events/1/dtStart"}}]}],
        ["/data/calendar/events/0/title", "产品立项会"],
        ["/data/calendar/events/0/dtStart", "09:00"],
        ["/data/calendar/events/1/dtStart", "15:00"],
    ]


def phase_payload(sample_id: str) -> dict:
    source = "Q001" if sample_id == "Q001B" else sample_id
    return json.loads((PHASE_SOURCE / f"{source}.json").read_text(encoding="utf-8"))


def model_dsl(sample_id: str) -> str:
    source = "Q001" if sample_id == "Q001B" else sample_id
    return (MODEL_RUN / f"{source}.genui.jsonl").read_text(encoding="utf-8")


def expectation(sample_id: str) -> dict:
    """把真实入参整理成一条期望样本：候选字段/事件成为显式需求项。"""
    payload = phase_payload(sample_id)
    content = payload.get("content") or {}
    variant = VARIANTS.get(sample_id, {})
    fields = [
        f"{binding.get('writeResultTo', '')}{field}"
        for binding in content.get("candidateDataBindings") or []
        for field in binding.get("candidateOutputFields") or []
    ]
    actions = variant.get("actions") or [
        (candidate.get("action") or {}).get("args", {}).get("intentName")
        for candidate in content.get("candidateEventCandidates") or []
    ]
    actions = [item for item in actions if item]
    lines = ([json.loads(line) for line in model_dsl(sample_id).splitlines() if line.strip()]
             if variant.get("size") != "2x4" else q006_two_by_four())
    for line in lines:
        # 图标只出现在标题、按钮、进度环心与 S-dual-info 分区主视觉上，改动必须落在这些合法位置。
        swap = variant.get("info_block_icon")
        if (isinstance(swap, dict) and len(line) > 2 and line[1] == "InfoBlock"
                and line[0] == swap["node"]):
            line[2]["visual"] = {"type": "icon", "icon": media_uri(str(swap["asset"]))}
    return {
        "id": sample_id,
        "query": content.get("userQuery") or payload.get("userQuery") or sample_id,
        "title": content.get("title") or sample_id,
        "size": str(variant.get("size") or content.get("size") or ""),
        "dsl": "\n".join(json.dumps(line, ensure_ascii=False) for line in lines),
        "expectedData": fields,
        "expectedActions": actions,
        "category": CATEGORY.get(sample_id, ""),
        "note": str(variant.get("note") or "期望与实际一致（候选字段与事件全部命中）"),
    }


def gradient_png(sample: dict) -> str:
    """按该条的卡片主题色画一张占位截图，尺寸比例与声明尺寸一致。"""
    width, height = (600, 300) if sample["size"] == "2x4" else (400, 400)
    colors = THEMES.get("Q001" if sample["id"] == "Q001B" else sample["id"],
                        ("#FFDCE6F2", "#FFEAF3E0"))

    def rgb(value: str) -> tuple[int, int, int]:
        text = value.lstrip("#")[2:]
        return tuple(int(text[index:index + 2], 16) for index in (0, 2, 4))

    start, end = rgb(colors[0]), rgb(colors[1])
    picture = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(picture)
    for y in range(height):
        ratio = y / max(height - 1, 1)
        draw.line([(0, y), (width, y)],
                  fill=tuple(round(a + (b - a) * ratio) for a, b in zip(start, end)))
    title_font = ImageFont.truetype(str(FONT_PATH), 34)
    body_font = ImageFont.truetype(str(FONT_PATH), 19)
    draw.text((28, 26), f"{sample['id']} · {sample['title']}", font=title_font, fill="#12305c")
    draw.text((28, 78), f"期望样例 · {sample['size']}", font=body_font, fill="#33507a")
    for index, text in enumerate([f"数据 {len(sample['expectedData'])} 项",
                                  f"动作 {len(sample['expectedActions'])} 项"]):
        draw.text((28, 112 + index * 26), text, font=body_font, fill="#33507a")
    note = sample["note"]
    draw.text((28, height - 62), note[:26], font=body_font, fill="#7a4a12")
    if len(note) > 26:
        draw.text((28, height - 36), note[26:52], font=body_font, fill="#7a4a12")
    buffer = io.BytesIO()
    picture.save(buffer, format="PNG")
    import base64
    return base64.b64encode(buffer.getvalue()).decode()


def validate(sample: dict) -> None:
    """与卡片渲染页同一入口：期望 DSL 过不了严格转换就不要灌进平台。"""
    import os
    os.environ.setdefault("WIDGET_CLOUD_ROOT", str(REPOSITORY_ROOT))
    cloud = REPOSITORY_ROOT / "widget_service" / "cloud"
    sys.path.insert(0, str(cloud))
    os.chdir(cloud)
    from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
    convert_compact_dsl_to_a2ui(
        sample["dsl"], size=sample["size"] or "2x2", protocol_profile={"version": "v0.9"},
    )


def build_samples() -> list[dict]:
    samples = [expectation(sample_id) for sample_id in SAMPLE_IDS]
    for sample in samples:
        validate(sample)
    return samples


def import_batch(samples: list[dict]) -> dict:
    drop_previous()
    payload = {
        "name": BATCH_NAME,
        "imageSource": "web",
        "samples": [{
            "id": sample["id"], "query": sample["query"], "size": sample["size"] or None,
            "dsl": sample["dsl"], "imageBase64": gradient_png(sample),
            "expectedData": sample["expectedData"], "expectedActions": sample["expectedActions"],
            "category": sample["category"] or None,
        } for sample in samples],
    }
    response = httpx.post(f"{API_BASE}/expect/import", json=payload, timeout=120.0)
    response.raise_for_status()
    return response.json()


def drop_previous() -> None:
    """同名演示批次先删掉，重复执行不会在画廊里堆出多份。"""
    response = httpx.get(f"{API_BASE}/batch/runs", timeout=30.0)
    response.raise_for_status()
    for item in response.json().get("items") or []:
        if item.get("sourceType") == "external-quality" and item.get("name") == BATCH_NAME:
            httpx.delete(f"{API_BASE}/expect/runs/{item['runId']}", timeout=30.0)
            print(f"已删除同名旧演示批次：{item['runId']}")


def compare_by_batch(import_run_id: str) -> dict:
    response = httpx.get(f"{API_BASE}/expect/compare", timeout=120.0, params={
        "importRunId": import_run_id, "runId": RUN_ID,
        "dimensions": "data,actions,icons",
    })
    response.raise_for_status()
    return response.json()


def compare_by_session(import_run_id: str) -> dict:
    records = json.loads((DEBUG_TOOLS_ROOT / "Datasets" / "phase_Q001_Q010_model_run"
                          / "session" / "records.json").read_text(encoding="utf-8"))
    actuals = [{
        "id": record["id"],
        "query": (record.get("request") or {}).get("userQuery") or "",
        "genui": ((record.get("response") or {}).get("data") or {}).get("genui") or "",
        "size": (record.get("request") or {}).get("size") or "",
        "title": (record.get("response") or {}).get("data", {}).get("title") or record["id"],
    } for record in records]
    response = httpx.post(f"{API_BASE}/expect/compare-live", timeout=120.0, json={
        "importRunId": import_run_id, "actuals": actuals,
        "dimensions": ["data", "actions", "icons"],
    })
    response.raise_for_status()
    return response.json()


def report(title: str, comparison: dict) -> None:
    summary = comparison["summary"]
    print(f"\n== {title}")
    print(f"   期望 {summary['expected']} 条 · 实际 {summary['actual']} 条 · "
          f"已匹配 {summary['matched']} · 未匹配 {summary['none']}（尺寸不进指纹，不参与判定）")
    for pair in comparison["pairs"]:
        match = pair.get("match") or {}
        actual = pair.get("actual") or {}
        missing = (match.get("missingData") or []) + (match.get("missingActions") or []) \
            + (match.get("missingIcons") or [])
        print(f"   {pair['expected']['sampleId']:<6} → "
              f"{(actual.get('sampleId') or '无'):<10} {pair['tier']:<14}"
              f"{'缺：' + '，'.join(missing) if missing else ''}")
    for warning in comparison.get("warnings") or []:
        print(f"   警告：{warning}")


def main() -> None:
    samples = build_samples()
    print(f"期望样本 {len(samples)} 条，全部通过严格转换校验")
    run = import_batch(samples)
    print(f"导入批次：{run['runId']}（{run['name']}）样本 {run['imported']} 条"
          f"{'，尺寸提示：' + str(run['sizeWarnings']) if run.get('sizeWarnings') else ''}")
    report("实际来源＝批跑运行 " + RUN_ID, compare_by_batch(run["runId"]))
    report("实际来源＝本次会话记录", compare_by_session(run["runId"]))
    print(f"\n页面：http://127.0.0.1:8888/debug/expect · 期望批次选 {run['runId']}；"
          f"删除整批：DELETE {API_BASE}/expect/runs/{run['runId']}")


if __name__ == "__main__":
    main()
