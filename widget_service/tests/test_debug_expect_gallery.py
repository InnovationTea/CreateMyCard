"""期望数据画廊：聚合导入批次、筛选与删除。"""

import base64
import io
import json

import pytest
from debug_tools.batch_testing.expect_gallery import (
    delete_run,
    delete_sample,
    gallery,
)
from debug_tools.batch_testing.expect_gallery import sample_ids
from debug_tools.batch_testing.quality_import import import_batch
from debug_tools.batch_testing.runner import BatchRunManager
from PIL import Image


def png() -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (100, 100), "white").save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def genui(text: str) -> str:
    rows = [
        {"version": "v0.9", "createSurface": {"surfaceId": "s", "catalogId": "c"}},
        {"version": "v0.9", "updateComponents": {
            "surfaceId": "s", "root": "root", "components": [
                {"id": "root", "component": "Column", "layout": "S-center",
                 "onClick": [{"call": "clickToDeeplink",
                              "args": {"intentName": "Weather"}}],
                 "content": "${/data/weather/current/condition}"},
                {"id": "title", "component": "Text", "content": text},
            ]}},
    ]
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def make_manager(tmp_path) -> BatchRunManager:
    return BatchRunManager(
        tmp_path / "datasets",
        tmp_path / "output",
        tmp_path / "trace",
        tmp_path / "cloud",
    )


def sample(sample_id: str, query: str, category: str | None = None) -> dict:
    row = {"id": sample_id, "query": query, "dsl": genui(query), "imageBase64": png()}
    if category is not None:
        row["category"] = category
    return row


def test_gallery_lists_imported_samples_with_labels_and_filters(tmp_path):
    manager = make_manager(tmp_path)
    first = import_batch(manager.output_root, {
        "name": "天气批次", "imageSource": "unknown", "category": "天气",
        "samples": [sample("Q001", "今日天气"), sample("Q002", "明日天气", "电量")],
    })
    second = import_batch(manager.output_root, {
        "name": "日程批次", "imageSource": "unknown",
        "samples": [sample("Q003", "今天日程", "日程")],
    })

    result = gallery(manager)
    assert result["total"] == 3
    assert set(result["categories"]) == {"天气", "电量", "日程"}
    assert {item["runId"] for item in result["items"]} == {
        first["runId"], second["runId"],
    }
    item = next(item for item in result["items"] if item["sampleId"] == "Q001")
    assert item["runName"] == "天气批次"
    assert item["category"] == "天气" and item["size"] == "2x2"
    assert item["labels"]["data"]["/data/weather/current/condition"] == "天气状况"
    assert item["labels"]["actions"]["clickToDeeplink:Weather"] == "跳转链接 · 天气"
    assert item["fingerprint"] == {
        "data": ["/data/weather/current/condition"],
        "actions": ["clickToDeeplink:Weather"],
        "icons": [],
    }
    assert item["imageUrl"].endswith("/input-image")

    by_category = gallery(manager, category="电量")
    assert [item["sampleId"] for item in by_category["items"]] == ["Q002"]
    # 分类下拉仍返回全部分类，便于切换。
    assert set(by_category["categories"]) == {"天气", "电量", "日程"}

    by_query = gallery(manager, query="天气")
    assert {item["sampleId"] for item in by_query["items"]} == {"Q001", "Q002"}
    # 批次名也参与关键词匹配。
    assert [item["sampleId"] for item in gallery(manager, query="日程批次")["items"]] == [
        "Q003",
    ]


def test_gallery_exposes_cardspec_fingerprint_for_filtering(tmp_path):
    manager = make_manager(tmp_path)
    row = sample("Q001", "电量卡片")
    row["cardSpec"] = {
        "dataBindings": [{"writeResultTo": "/data/phoneBattery"}],
        "events": [{
            "handler": {"call": "clickToIntent", "args": {"intentName": "Battery_Settings"}},
        }],
    }
    import_batch(manager.output_root, {
        "name": "规格批次", "imageSource": "unknown", "samples": [row],
    })
    item = gallery(manager)["items"][0]
    assert item["fingerprint"]["data"] == ["/data/phoneBattery"]
    assert item["fingerprint"]["actions"] == ["clickToIntent:Battery_Settings"]


def test_gallery_ignores_regular_batch_runs(tmp_path):
    manager = make_manager(tmp_path)
    run_dir = manager.output_root / "batch_regular"
    run_dir.mkdir(parents=True)
    (run_dir / "summary.json").write_text(json.dumps({
        "runId": "batch_regular",
        "name": "普通批跑",
        "sourceType": "generation",
        "samples": [{"id": "S1", "query": "天气", "status": "success"}],
    }), encoding="utf-8")
    assert gallery(manager)["items"] == []


def test_delete_sample_updates_summary_and_removes_empty_batch(tmp_path):
    manager = make_manager(tmp_path)
    imported = import_batch(manager.output_root, {
        "name": "待删除", "imageSource": "unknown", "category": "天气",
        "samples": [sample("Q001", "今日天气"), sample("Q002", "明日天气")],
    })
    run_id = imported["runId"]
    run_dir = manager.output_root / run_id
    assert (run_dir / "Q001").is_dir()

    outcome = delete_sample(manager, run_id, "Q001")
    assert outcome["deleted"] == "sample"
    assert not (run_dir / "Q001").exists()
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["total"] == 1 and summary["completed"] == 1
    assert [item["id"] for item in summary["samples"]] == ["Q002"]
    assert gallery(manager)["total"] == 1

    outcome = delete_sample(manager, run_id, "Q002")
    assert outcome["deleted"] == "run"
    assert not run_dir.exists()
    assert gallery(manager)["items"] == []

    with pytest.raises(KeyError):
        delete_sample(manager, run_id, "Q002")


def test_delete_rejects_regular_runs_unsafe_ids_and_active_batches(tmp_path):
    manager = make_manager(tmp_path)
    imported = import_batch(manager.output_root, {
        "name": "保护", "imageSource": "unknown",
        "samples": [sample("Q001", "今日天气")],
    })
    run_id = imported["runId"]
    with pytest.raises(KeyError):
        delete_sample(manager, "../escape", "Q001")
    with pytest.raises(KeyError):
        delete_sample(manager, run_id, "../escape")
    with pytest.raises(KeyError):
        delete_run(manager, "batch_missing")

    class FakeState:
        status = "running"

        def __init__(self) -> None:
            # get_run 会用 state.output_dir 做指标补全，这里补上运行目录。
            self.output_dir = manager.output_root / run_id

        @staticmethod
        def public_dict() -> dict:
            return {"runId": run_id, "name": "保护", "sourceType": "external-quality"}

    manager.runs[run_id] = FakeState()
    with pytest.raises(ValueError, match="仍在运行"):
        delete_run(manager, run_id)
    manager.runs.pop(run_id)

    regular = manager.output_root / "batch_regular"
    regular.mkdir(parents=True)
    (regular / "summary.json").write_text(json.dumps({
        "runId": "batch_regular", "name": "普通", "sourceType": "generation",
    }), encoding="utf-8")
    # 导入批次分期望／实际两种用途，删除守卫只认 sourceType，文案要同时覆盖两种用途。
    with pytest.raises(ValueError) as info:
        delete_sample(manager, "batch_regular", "Q001")
    assert "只有导入批次" in str(info.value)
    assert "期望" in str(info.value) and "实际" in str(info.value)


def test_delete_run_only_accepts_import_batches(tmp_path):
    manager = make_manager(tmp_path)
    regular = manager.output_root / "batch_regular"
    regular.mkdir(parents=True)
    (regular / "summary.json").write_text(json.dumps({
        "runId": "batch_regular", "name": "普通", "sourceType": "generation",
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="只有导入批次"):
        delete_run(manager, "batch_regular")
    assert regular.is_dir()


def test_sample_ids_lists_one_side_without_dsl_or_screenshots(tmp_path):
    """导入页查重只要 ID：索引不带 DSL／截图，并按用途分侧。"""
    manager = make_manager(tmp_path)
    import_batch(manager.output_root, {
        "name": "期望批次", "imageSource": "unknown",
        "samples": [sample("Q001", "今日天气")],
    })
    import_batch(manager.output_root, {
        "name": "实际批次", "imageSource": "unknown", "purpose": "actual",
        "samples": [sample("Q001", "今日天气")],
    })
    both = sample_ids(manager)
    assert sorted(item["id"] for item in both["items"]) == ["Q001", "Q001"]
    assert both["total"] == 2

    expect_only = sample_ids(manager, "expect")
    assert [item["id"] for item in expect_only["items"]] == ["Q001"]
    assert expect_only["items"][0]["runName"] == "期望批次"
    assert "genui" not in json.dumps(expect_only, ensure_ascii=False)
    assert "image" not in json.dumps(expect_only, ensure_ascii=False)

    actual_only = sample_ids(manager, "actual")
    assert [item["id"] for item in actual_only["items"]] == ["Q001"]
    assert actual_only["items"][0]["runName"] == "实际批次"
