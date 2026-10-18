"""生成期望对比的演示数据：一批导入期望输出（含尺寸判定）＋一批实际批跑。

仅用于本地看效果，产物都落在 debug_tools/batch_output（已 gitignore），可随时删除。
"""

import base64
import io
import json
from pathlib import Path

import httpx
from PIL import Image

ROOT = Path(__file__).resolve().parent / "batch_output"
BASE = "http://127.0.0.1:8888/debug"
RUN_ID = "demo_size_20261017"


def png(width: int, height: int) -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (238, 244, 252)).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


WEATHER_2X2 = "\n".join([
    json.dumps(["root", "Column", {"width": "matchParent", "height": 150, "padding": 12,
                                   "space": 6}, ["title", "value", "action"]], ensure_ascii=False),
    json.dumps(["title", "Text", {"content": "西湖天气", "fontSize": 16, "fontWeight": 700}],
               ensure_ascii=False),
    json.dumps(["value", "Text", {"content": {"path": "/data/weather/current/condition"},
                                  "fontSize": 32, "fontWeight": 700}], ensure_ascii=False),
    json.dumps(["/data/weather/current/condition", "晴"], ensure_ascii=False),
    json.dumps(["action", "PillButton", {"label": "查看详情", "onClick": [
        {"call": "clickToDeeplink", "args": {"intentName": "Weather_CityCode"}}]}],
        ensure_ascii=False),
])
BATTERY_FULL = "\n".join([
    json.dumps(["root", "Column", {"width": "matchParent", "height": 150, "padding": 12,
                                   "space": 8}, ["title", "value", "action"]], ensure_ascii=False),
    json.dumps(["title", "Text", {"content": "剩余电量", "fontSize": 14}], ensure_ascii=False),
    json.dumps(["value", "Text", {"content": {"path": "/data/battery/level"},
                                  "fontSize": 32, "fontWeight": 700}], ensure_ascii=False),
    json.dumps(["/data/battery/level", "68%"], ensure_ascii=False),
    json.dumps(["action", "PillButton", {"label": "电池设置", "onClick": [
        {"call": "clickToIntent", "args": {"intentName": "Battery_Settings"}}]}],
        ensure_ascii=False),
])
# 实际侧的天气卡：只有数据没有动作（2x2），以及数据动作齐全的另一张（2x4）。
WEATHER_PARTIAL_2X2 = "\n".join([
    json.dumps(["root", "Column", {"width": "matchParent", "height": 150, "padding": 12,
                                   "space": 6}, ["title", "value"]], ensure_ascii=False),
    json.dumps(["title", "Text", {"content": "西湖天气", "fontSize": 16, "fontWeight": 700}],
               ensure_ascii=False),
    json.dumps(["value", "Text", {"content": {"path": "/data/weather/current/condition"},
                                  "fontSize": 32, "fontWeight": 700}], ensure_ascii=False),
])
WEATHER_FULL_2X4 = "\n".join([
    json.dumps(["root", "Row", {"width": "matchParent", "height": 150, "padding": 12,
                               "space": 8}, ["title", "value", "action"]], ensure_ascii=False),
    json.dumps(["title", "Text", {"content": "西湖天气", "fontSize": 16, "fontWeight": 700}],
               ensure_ascii=False),
    json.dumps(["value", "Text", {"content": {"path": "/data/weather/current/condition"},
                                  "fontSize": 32, "fontWeight": 700}], ensure_ascii=False),
    json.dumps(["action", "PillButton", {"label": "查看详情", "onClick": [
        {"call": "clickToDeeplink", "args": {"intentName": "Weather_CityCode"}}]}],
        ensure_ascii=False),
])

ACTUAL = [
    ("X001", WEATHER_PARTIAL_2X2, "2x2", "帮我做个卡片看天气，点击查看详情"),
    ("X002", WEATHER_FULL_2X4, "2x4", "天气详情横版"),
    ("X003", BATTERY_FULL, "2x4", "电量与设置"),
]

IMPORT_SAMPLES = [
    {"id": "Q001", "query": "做个天气卡片，点击跳转到天气详情", "dsl": WEATHER_2X2,
     "imageBase64": png(300, 300)},
    {"id": "Q002", "query": "剩余电量大字，带电池设置入口", "dsl": BATTERY_FULL,
     "imageBase64": png(600, 300)},
    {"id": "Q003", "query": "方版电量卡片", "dsl": BATTERY_FULL, "size": "2x2",
     "imageBase64": png(300, 300)},
]


def write_actual_run() -> None:
    run_dir = ROOT / RUN_ID
    samples = []
    for sample_id, text, size, query in ACTUAL:
        attempt = run_dir / sample_id / "attempt_000"
        attempt.mkdir(parents=True, exist_ok=True)
        (attempt / "genui.jsonl").write_text(text, encoding="utf-8")
        row = {"id": sample_id, "title": sample_id, "query": query, "size": size,
               "status": "success", "attemptCount": 1, "elapsedMs": 1200}
        (run_dir / sample_id / "result.json").write_text(
            json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
        samples.append(row)
    (run_dir / "summary.json").write_text(json.dumps({
        "runId": RUN_ID, "name": "演示 · 尺寸指纹批跑（可删除）", "status": "completed",
        "startedAt": "2026-10-17T09:00:00Z", "finishedAt": "2026-10-17T09:05:00Z",
        "total": len(samples), "completed": len(samples), "success": len(samples),
        "failed": 0, "samples": samples,
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    write_actual_run()
    response = httpx.post(f"{BASE}/expect/import", json={
        "name": "演示 · 期望输出（尺寸自动判定）", "imageSource": "unknown",
        "samples": IMPORT_SAMPLES,
    }, timeout=60)
    response.raise_for_status()
    body = response.json()
    print("importRunId =", body["runId"])
    print("sizeWarnings =", json.dumps(body.get("sizeWarnings"), ensure_ascii=False))
    for row in body["samples"]:
        print(f"  {row['id']} size={row['size']} source={row['sizeSource']}")
    compare = httpx.get(f"{BASE}/expect/compare",
                        params={"importRunId": body["runId"], "runId": RUN_ID}, timeout=60)
    compare.raise_for_status()
    result = compare.json()
    print("summary =", json.dumps(result["summary"], ensure_ascii=False))
    print("warnings =", json.dumps(result["warnings"], ensure_ascii=False))
    for pair in result["pairs"]:
        match = pair["match"] or {}
        print(f"  {pair['expected']['sampleId']}({pair['expected']['size']}) → "
              f"{(pair['actual'] or {}).get('sampleId')}({(pair['actual'] or {}).get('size')}) "
              f"tier={pair['tier']} score={match.get('score')} "
              f"tier={pair['tier']} "
              f"actions={pair['expected']['fingerprint']['actions']}")
    print("unmatched =", [item["sampleId"] for item in result["unmatchedActual"]])


if __name__ == "__main__":
    main()
