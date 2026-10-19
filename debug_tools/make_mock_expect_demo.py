"""给「期望对比」灌一批受控 mock：期望批次与 mock 实际批跑各 7 条，覆盖全部判定状态。

和 `make_phase_expect_demo.py` 的区别是这里不碰真实 Phase 素材：两侧的卡片都是现搭的，
每条只考察一件事，所以页面上每一种结论都能逐条对照（期望样本 ID 与实际样本 ID 同名，
配对不会被交叉抢走）：

| 样本 | 期望侧 | 实际侧 | 预期结论 |
|---|---|---|---|
| M001 | 数据 alpha/value＋说明＋动作 Demo_One | 完全一致 | 已匹配 |
| M002 | 只绑 beta/main | 多绑一个 beta/extra | 已匹配，实际多出 1 项 |
| M003 | 绑 gamma/main 与 gamma/second | 只有 gamma/main | 未匹配，缺数据 1 |
| M004 | 数据齐全＋按钮 Demo_Four | 数据齐全但没有按钮 | 未匹配，缺动作 1 |
| M005 | 标题图标 bell_fill | 标题图标 bolt_fill | 未匹配，缺图标 1 |
| M006 | 2x4（W-top-bottom＋TextBlock） | 2x2，内容一致 | 已匹配（尺寸不进指纹） |
| M007 | 纯静态卡片，无绑定无事件 | 同为静态卡片 | 无筛选需求（按尺寸对齐） |

mock 实际批跑直接写成 `batch_output/<RUN_ID>` 运行目录，对比页的「实际来源 → 已落盘的批跑运行」
就能选到，不需要真跑模型，也不依赖浏览器会话。重复执行会先删掉同名批次与同名运行目录。
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

DEBUG_TOOLS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = DEBUG_TOOLS_ROOT.parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from debug_tools.make_phase_batch_run import (  # noqa: E402
    bound, header, media, node, pill_button, root,
)
from debug_tools.make_phase_expect_demo import gradient_png, validate  # noqa: E402

BATCH_NAME = "演示 · 期望输出（Mock，可删除）"
RUN_ID = "mock_actual_20261018"
RUN_NAME = "演示 · 实际输出（Mock，可删除）"
API_BASE = "http://127.0.0.1:8888/debug"
RUN_ROOT = DEBUG_TOOLS_ROOT / "batch_output"

C1 = ("#FFA9DCC8", "#FFDDEFC1")
C2 = ("#FFBEE0F5", "#FFDFF0D8")
C3 = ("#FFC7D8FB", "#FFEFE6FB")


def line(*parts) -> str:
    return json.dumps(list(parts), ensure_ascii=False)


def dsl(*lines: str) -> str:
    return "\n".join(lines)


def m001(actual: bool) -> str:
    """数据与动作完全一致：两侧都绑 alpha 的两项并各带同一个按钮。"""
    return dsl(
        root("S-title-primary-secondary-action", ["header", "value", "note", "action"], C1),
        header("header", "M001 一致样例"),
        *bound("value", "EmphasizedData", "value", "/data/demo/alpha/value", 68,
               extra={"unit": "%"}),
        node("note", "SecondaryBody", {"items": [{
            "label": "说明", "value": {"path": "/data/demo/alpha/note"}}], "fontSize": 12}),
        pill_button("action", "查看", {
            "call": "clickToIntent", "args": {"intentName": "Demo_One"}}),
        line("/data/demo/alpha/note", "一致样例"),
    )


def m002(actual: bool) -> str:
    """实际多绑一项：期望只要求 beta/main，实际多了 beta/extra。"""
    items = [{"label": "主值", "value": {"path": "/data/demo/beta/main"}}]
    lines = [
        root("S-title-content", ["header", "body"], C2),
        header("header", "M002 实际多出样例"),
        node("body", "SecondaryBody", {"items": items, "fontSize": 14}),
        line("/data/demo/beta/main", "主值内容"),
    ]
    if actual:
        items.append({"label": "额外", "value": {"path": "/data/demo/beta/extra"}})
        lines.append(line("/data/demo/beta/extra", "实际多绑的项"))
    return dsl(*lines)


def m003(actual: bool) -> str:
    """期望要两项、实际只给一项：未匹配，缺数据 1。"""
    items = [{"label": "主项", "value": {"path": "/data/demo/gamma/main"}}]
    lines = [
        root("S-title-content", ["header", "body"], C3),
        header("header", "M003 缺数据样例"),
        line("/data/demo/gamma/main", "主项内容"),
    ]
    if not actual:
        items.append({"label": "次项", "value": {"path": "/data/demo/gamma/second"}})
        lines.append(line("/data/demo/gamma/second", "期望多要的项"))
    lines.insert(2, node("body", "SecondaryBody", {"items": items, "fontSize": 14}))
    return dsl(*lines)


def m004(actual: bool) -> str:
    """期望带按钮、实际没有：未匹配，缺动作 1（数据仍全覆盖）。"""
    note = node("note", "SecondaryBody", {"items": [{
        "label": "说明", "value": {"path": "/data/demo/delta/note"}}], "fontSize": 12})
    if actual:
        return dsl(
            root("S-title-content", ["header", "body"], C1),
            header("header", "M004 缺动作样例"),
            node("body", "SecondaryBody", {"items": [
                {"label": "次数", "value": {"path": "/data/demo/delta/value"}},
                {"label": "说明", "value": {"path": "/data/demo/delta/note"}},
            ], "columns": 1, "fontSize": 12}),
            line("/data/demo/delta/value", 42),
            line("/data/demo/delta/note", "动作样例"),
        )
    return dsl(
        root("S-title-primary-secondary-action", ["header", "value", "note", "action"], C1),
        header("header", "M004 缺动作样例"),
        *bound("value", "EmphasizedData", "value", "/data/demo/delta/value", 42,
               extra={"unit": "次"}),
        note,
        pill_button("action", "打卡", {
            "call": "clickToIntent", "args": {"intentName": "Demo_Four"}}),
        line("/data/demo/delta/note", "动作样例"),
    )


def m005(actual: bool) -> str:
    """图标不同：期望 bell_fill，实际 bolt_fill，两者都是登记素材。"""
    return dsl(
        root("S-title-content", ["header", "body"], C2),
        header("header", "M005 图标样例", asset=("bolt_fill" if actual else "bell_fill")),
        node("body", "EmphasisText", {
            "mainText": {"path": "/data/demo/epsilon/main"}, "fontSize": 18}),
        line("/data/demo/epsilon/main", "图标样例"),
    )


def m006(actual: bool) -> str:
    """尺寸不进指纹：期望按 2x4 搭、实际是 2x2，同一组内容仍算已匹配。"""
    if actual:
        return dsl(
            root("S-title-content", ["header", "body"], C3),
            header("header", "M006 尺寸样例"),
            node("body", "SecondaryBody", {"items": [
                {"label": "主项", "value": {"path": "/data/demo/zeta/main"}},
                {"label": "次项", "value": {"path": "/data/demo/zeta/second"}},
            ], "columns": 1, "fontSize": 12}),
            line("/data/demo/zeta/main", "主项内容"),
            line("/data/demo/zeta/second", "次项内容"),
        )
    return dsl(
        root("W-top-bottom", ["primary_area", "details"], C3, variant="bottom-details"),
        node("zeta_label", "SecondaryBody", {"items": [{"value": "主项"}], "fontSize": 14}),
        *bound("zeta_value", "EmphasizedData", "value", "/data/demo/zeta/main", 82,
               extra={"unit": "分", "fontSize": 30}),
        node("primary_area", "Group", {"variant": "label-value"},
             ["zeta_label", "zeta_value"]),
        node("details", "TextBlock", {"items": [
            {"label": "主项", "value": {"path": "/data/demo/zeta/main"}},
            {"label": "次项", "value": {"path": "/data/demo/zeta/second"}},
        ]}),
        line("/data/demo/zeta/second", "次项内容"),
    )


def m007(actual: bool) -> str:
    """纯静态卡片：没有绑定也没有事件，期望侧没有筛选需求。"""
    return dsl(
        root("S-center", ["display"], C1),
        node("display", "DataDisplay", {
            "label": "M007 静态样例", "value": "慢慢来，比较快",
            "supportingText": "无绑定、无事件", "fontSize": 18}),
    )


CASES = [
    ("M001", "一致样例", "期望与实际完全一致", m001),
    ("M002", "实际多出样例", "实际多绑一项（beta/extra）", m002),
    ("M003", "缺数据样例", "实际只给一项，缺 gamma/second", m003),
    ("M004", "缺动作样例", "实际没有按钮，缺 clickToIntent:Demo_Four", m004),
    ("M005", "图标样例", "实际用 bolt_fill，缺 bell_fill", m005),
    ("M006", "尺寸样例", "期望 2x4、实际 2x2，内容一致：尺寸不参与判定", m006),
    ("M007", "静态样例", "两侧都没有需求项", m007),
]


def sample_rows() -> list[dict]:
    rows = []
    for sample_id, title, note, builder in CASES:
        size = "2x4" if sample_id == "M006" else "2x2"
        rows.append({
            "id": sample_id, "title": title, "note": note, "size": size,
            # M006 的差异就在尺寸本身：期望 2x4，实际仍是 2x2。
            "actual_size": "2x2" if sample_id == "M006" else size,
            "expected_dsl": builder(False), "actual_dsl": builder(True),
        })
    return rows


def write_run(rows: list[dict]) -> Path:
    run_dir = RUN_ROOT / RUN_ID
    if run_dir.is_dir():
        # 只删自己这一批：路径必须正好是 batch_output 下的 mock 运行目录。
        if run_dir.resolve().parent != RUN_ROOT.resolve() or RUN_ID not in run_dir.name:
            raise SystemExit(f"拒绝删除意外路径：{run_dir}")
        shutil.rmtree(run_dir)
    now = datetime.now(UTC).replace(microsecond=0)
    samples = []
    for row in rows:
        attempt = run_dir / row["id"] / "attempt_000"
        attempt.mkdir(parents=True, exist_ok=True)
        (attempt / "genui.jsonl").write_text(row["actual_dsl"], encoding="utf-8")
        meta = {"id": row["id"], "title": row["title"], "query": f"mock 实际输出 {row['id']}",
                "size": row["actual_size"], "status": "success", "attemptCount": 1,
                "elapsedMs": 1500}
        (run_dir / row["id"] / "result.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        samples.append(meta)
    (run_dir / "summary.json").write_text(json.dumps({
        "runId": RUN_ID, "name": RUN_NAME, "status": "completed",
        # 时间戳格式与批跑产物一致（`+00:00` 而不是 `Z`），否则运行列表里两条时间口径会不同。
        "startedAt": now.isoformat(),
        "finishedAt": now.isoformat(),
        "total": len(samples), "completed": len(samples), "success": len(samples),
        "degraded": 0, "failed": 0, "cancelled": 0, "samples": samples,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return run_dir


def drop_batch(name: str) -> None:
    """同名期望批次先删掉，重复执行不会在画廊里堆出多份。"""
    response = httpx.get(f"{API_BASE}/batch/runs", timeout=30.0)
    response.raise_for_status()
    for item in response.json().get("items") or []:
        if item.get("sourceType") == "external-quality" and item.get("name") == name:
            httpx.delete(f"{API_BASE}/expect/runs/{item['runId']}", timeout=30.0)
            print(f"已删除同名旧演示批次：{item['runId']}")


def import_expectations(rows: list[dict]) -> dict:
    drop_batch(BATCH_NAME)
    # 截图上的项数直接按 DSL 里的绑定/事件数算，避免占位图与指纹口径不一致。
    def count(pattern: str, text: str) -> list[str]:
        return [""] * len(re.findall(pattern, text))

    payload = {"name": BATCH_NAME, "imageSource": "unknown", "samples": [{
        "id": row["id"], "query": f"mock 期望输出 {row['id']}（{row['note']}）",
        "size": row["size"], "dsl": row["expected_dsl"],
        "imageBase64": gradient_png({
            "id": row["id"], "title": row["title"], "size": row["size"],
            "note": row["note"],
            "expectedData": count(r'"path"', row["expected_dsl"]),
            "expectedActions": count(r'"onClick"', row["expected_dsl"]),
        }),
    } for row in rows]}
    response = httpx.post(f"{API_BASE}/expect/import", json=payload, timeout=120.0)
    response.raise_for_status()
    return response.json()


def compare(import_run_id: str) -> dict:
    response = httpx.get(f"{API_BASE}/expect/compare", timeout=120.0, params={
        "importRunId": import_run_id, "runId": RUN_ID,
        "dimensions": "data,actions,icons",
    })
    response.raise_for_status()
    return response.json()


def main() -> None:
    rows = sample_rows()
    for row in rows:
        validate({"dsl": row["expected_dsl"], "size": row["size"]})
        validate({"dsl": row["actual_dsl"], "size": row["actual_size"]})
    print(f"mock 卡片 {len(rows)} 条 ×2 侧全部通过严格转换校验")
    run_dir = write_run(rows)
    print(f"mock 实际批跑：{run_dir}")
    batch = import_expectations(rows)
    print(f"期望批次：{batch['runId']}（{batch['name']}）样本 {batch['imported']} 条")
    result = compare(batch["runId"])
    summary = result["summary"]
    print(f"\n== 判定汇总：期望 {summary['expected']} · 实际 {summary['actual']} · "
          f"已匹配 {summary['matched']} · 未匹配 {summary['none']}（尺寸不进指纹，不参与判定）")
    for pair in result["pairs"]:
        match = pair["match"] or {}
        missing = (match.get("missingData") or []) + (match.get("missingActions") or []) \
            + (match.get("missingIcons") or [])
        extra = (pair.get("diff") or {}).get("data", {}).get("extra") or []
        print(f"   {pair['expected']['sampleId']} → {(pair['actual'] or {}).get('sampleId')}"
              f"  {pair['tier']:<14}{'缺：' + '，'.join(missing) if missing else ''}"
              f"{'；实际多出：' + '，'.join(extra) if extra else ''}")
    for warning in result.get("warnings") or []:
        print(f"   警告：{warning}")
    print(f"\n页面：http://127.0.0.1:8888/debug/expect · 期望批次选 {batch['runId']}，"
          f"实际来源选「已落盘的批跑运行」→ {RUN_NAME}")
    print(f"删除：DELETE {API_BASE}/expect/runs/{batch['runId']}；"
          f"运行目录 {run_dir} 可直接删")


if __name__ == "__main__":
    main()
