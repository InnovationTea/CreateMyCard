"""双输入复用评分：真实导入/宿主链路、安全边界、证据失效和单卡配对。"""

import base64
import hashlib
import importlib.util
import io
import json
from pathlib import Path

import pytest
from debug_tools.batch_testing.api import register_batch_routes
from debug_tools.batch_testing.postprocess import PostprocessManager
from debug_tools.batch_testing.quality import compare
from debug_tools.batch_testing.quality_import import (
    import_batch,
    update_run_category,
    update_sample,
)
from debug_tools.batch_testing.task_manager import BatchTaskManager
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from test_debug_quality_workflow import PLUGINS, save_scores


def module(name):
    spec = importlib.util.spec_from_file_location(name, PLUGINS / "quality-score" / (name + ".py"))
    assert spec is not None and spec.loader is not None
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def payload(dsl=None):
    buffer = io.BytesIO()
    Image.new("RGB", (80, 80), "white").save(buffer, format="PNG")
    actions = [
        {"version": "v0.9", "createSurface": {"surfaceId": "card"}},
        {"version": "v0.9", "updateComponents": {"root": "root", "components": [
            {"id": "root", "component": "Text", "content": "显示天气"},
        ]}},
        {"version": "v0.9", "updateDataModel": {"path": "/", "value": {}}},
    ]
    return {"name": "导入测试", "imageSource": "native", "samples": [{
        "id": "Q001", "query": "显示天气", "size": "2x2",
        "dsl": json.dumps(actions, ensure_ascii=False) if dsl is None else dsl,
        "imageBase64": base64.b64encode(buffer.getvalue()).decode(),
    }]}


def context(root, value):
    summary = import_batch(root, value)
    run = root / summary.get("runId")
    output = run / "test-output"
    output.mkdir()
    return {"sample": summary.get("samples")[0], "runDir": str(run),
            "sampleDir": str(run / "Q001"), "outputDir": str(output)}


def test_import_http_is_explicit_and_keeps_history(tmp_path):
    manager = BatchTaskManager(tmp_path / "datasets", tmp_path / "output",
                               tmp_path / "traces", tmp_path / "cloud")
    app = FastAPI()
    register_batch_routes(app, task_manager=manager)
    client = TestClient(app)
    run_ids = []
    for _ in range(2):
        response = client.post("/debug/batch/quality/import", json=payload())
        assert response.status_code == 200
        run_id = response.json().get("runId")
        run_ids.append(run_id)
        detail = client.get(f"/debug/batch/runs/{run_id}").json()
        assert detail.get("sourceType") == "external-quality"
        assert detail.get("samples")[0].get("status") == "imported"
        assert detail.get("success") == 0
    assert run_ids[0] != run_ids[1]
    assert len(client.get("/debug/batch/runs").json().get("items")) == 2
    assert manager.postprocess_manager.queue.empty()


@pytest.mark.parametrize("image_kind", ["PNG", "JPEG", "PNG_BAD_CRC"])
def test_import_http_validates_image_and_publishes_atomically(tmp_path, image_kind):
    output = tmp_path / "output"
    manager = BatchTaskManager(
        tmp_path / "datasets", output, tmp_path / "traces", tmp_path / "cloud",
    )
    app = FastAPI()
    register_batch_routes(app, task_manager=manager)
    client = TestClient(app, raise_server_exceptions=False)
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), "white").save(
        buffer, format="JPEG" if image_kind == "JPEG" else "PNG",
    )
    raw = bytearray(buffer.getvalue())
    if image_kind == "PNG_BAD_CRC":
        offset = 8
        while offset < len(raw):
            length = int.from_bytes(raw[offset:offset + 4], "big")
            if raw[offset + 4:offset + 8] == b"IDAT":
                raw[offset + 8 + length] ^= 1
                break
            offset += length + 12
        else:
            pytest.fail("测试 PNG 缺少 IDAT")
    value = payload()
    samples = value.get("samples")
    assert samples
    sample = {**samples[0], "id": "Q002", "imageBase64": base64.b64encode(raw).decode()}
    # 第二张损坏时，第一张已写入临时目录；整个批次仍应清理且不发布。
    samples.append(sample)
    response = client.post("/debug/batch/quality/import", json=value)
    if image_kind == "PNG_BAD_CRC":
        assert response.status_code == 422
        assert response.json().get("detail") == "截图损坏或像素过大"
        assert client.get("/debug/batch/runs").json().get("items") == []
        assert list(output.iterdir()) == []
    else:
        assert response.status_code == 200
        run_id = response.json().get("runId")
        assert run_id
        extension = ".jpg" if image_kind == "JPEG" else ".png"
        stored = output / run_id / "Q002/input" / ("image" + extension)
        assert stored.read_bytes() == raw


@pytest.mark.parametrize(
    "bad", ["path", "reserved", "image", "sha", "purpose", "image_sha"],
)
def test_bad_import_is_atomic(tmp_path, bad):
    value = payload()
    sample = value.get("samples")[0]
    if bad == "path":
        sample["id"] = "../escape"
    elif bad == "reserved":
        sample["id"] = "CON.json"
    elif bad == "image":
        sample["imageBase64"] = base64.b64encode(b"not an image").decode()
    elif bad == "sha":
        sample["sourceSha256"] = "0" * 64
    elif bad == "purpose":
        value["purpose"] = "expected"
    elif bad == "image_sha":
        # 清单声明了截图摘要却没带截图：不能静默按「无截图」导入。
        del sample["imageBase64"]
        sample["imageSha256"] = "0" * 64
    else:
        sample["query"] = " "
    with pytest.raises(ValueError):
        import_batch(tmp_path, value)
    assert not list(tmp_path.iterdir())


def test_query_and_screenshot_are_optional(tmp_path):
    """真实输出常常只有 DSL：Query 与截图留空仍要能导入，配对退化成按样本 ID。"""
    value = payload()
    value["purpose"] = "actual"
    sample = value.get("samples")[0]
    del sample["query"]
    del sample["imageBase64"]
    summary = import_batch(tmp_path, value)
    row = summary.get("samples")[0]
    assert row.get("query") == ""
    assert row.get("size") == "2x2"
    assert summary.get("purpose") == "actual"
    input_dir = tmp_path / summary["runId"] / "Q001" / "input"
    metadata = json.loads((input_dir / "input.json").read_text(encoding="utf-8"))
    assert metadata.get("imageFile") == ""
    assert metadata.get("purpose") == "actual"
    assert not (input_dir / "image.png").exists()
    assert (input_dir / "genui.jsonl").read_text(encoding="utf-8").strip()


def test_only_id_and_screenshot_are_required(tmp_path):
    """导入只强制样本 ID 与截图：DSL、Query、尺寸、三类期望项都能留空。"""
    value = payload()
    sample = value.get("samples")[0]
    del sample["dsl"]
    del sample["query"]
    del sample["size"]
    summary = import_batch(tmp_path, value)
    row = summary["samples"][0]
    assert row["id"] == "Q001"
    assert row["query"] == ""
    # 没有 DSL 是合法输入：尺寸改由截图宽高比判定（80×80 方图 → 2x2），不是错误。
    assert row["size"] == "2x2" and row["sizeSource"] == "derived"
    assert summary["sizeWarnings"] == []
    input_dir = tmp_path / summary["runId"] / "Q001" / "input"
    assert (input_dir / "genui.jsonl").read_text(encoding="utf-8") == ""
    assert (input_dir / "image.png").is_file()
    metadata = json.loads((input_dir / "input.json").read_text(encoding="utf-8"))
    assert metadata["sourceSha256"] == hashlib.sha256(b"").hexdigest()


def test_blank_ids_are_generated_and_duplicates_are_rejected(tmp_path):
    """ID 依旧唯一：留空按内容哈希生成（同批同内容加后缀），人工写重名直接拒绝。"""
    value = payload()
    value["samples"][0]["id"] = ""
    value["samples"].append({**value["samples"][0], "id": ""})
    summary = import_batch(tmp_path, value)
    ids = [item["id"] for item in summary["samples"]]
    assert ids[0].startswith("H-") and len(ids[0]) == 14, "留空时按哈希生成"
    assert ids[1] == f"{ids[0]}-2", "同批同内容撞车时加后缀，保证唯一"
    assert len({item.casefold() for item in ids}) == 2
    assert any("同批重名，已改名" in note for note in summary["sizeWarnings"])

    # 人工写重名不再静默改名：直接拒绝并提示可以留空。
    dupe = tmp_path / "dupe"
    dupe.mkdir()
    clash = payload()
    clash["samples"].append({**clash["samples"][0], "id": "q001"})
    with pytest.raises(ValueError, match="样本 ID 重复"):
        import_batch(dupe, clash)
    assert not list(dupe.iterdir()), "拒绝时不留半个批次"


def test_update_sample_changes_only_the_named_one(tmp_path):
    """二次修改只覆盖指定样本：同批其它样本与批次身份都不变。"""
    value = payload()
    value["samples"].append({**value["samples"][0], "id": "Q002"})
    summary = import_batch(tmp_path, value)
    run_id = summary["runId"]
    before = {item["id"]: item for item in summary["samples"]}

    updated = update_sample(tmp_path, run_id, "Q002", {
        "query": "改成新的说法",
        "size": "2x4",
        "dsl": "",
        "imageBase64": value["samples"][0]["imageBase64"],
        "expectedData": ["/data/weather/current/condition"],
        "expectedActions": ["clickToDeeplink:Weather_CityCode"],
    })
    assert updated["id"] == "Q002" and updated["query"] == "改成新的说法"
    assert updated["updatedAt"]

    after = json.loads((tmp_path / run_id / "summary.json").read_text(encoding="utf-8"))
    ids = [item["id"] for item in after["samples"]]
    assert ids == ["Q001", "Q002"], "顺序保持，不能把被改的样本挪到末尾"
    rows = {item["id"]: item for item in after["samples"]}
    assert rows["Q001"] == before["Q001"], "同批其它样本不该被改动"
    assert after["updatedAt"]
    metadata = json.loads(
        (tmp_path / run_id / "Q002" / "input" / "input.json").read_text(encoding="utf-8")
    )
    assert metadata["query"] == "改成新的说法"
    assert metadata["expectedData"] == ["/data/weather/current/condition"]
    assert metadata["expectedActions"] == ["clickToDeeplink:Weather_CityCode"]
    # 不传截图按保留处理：页面无法回填 file 输入框，改文字不该丢原截图。
    kept = json.loads(
        (tmp_path / run_id / "Q002" / "input" / "input.json").read_text(encoding="utf-8")
    )
    assert kept["imageFile"] == "image.png"
    update_sample(tmp_path, run_id, "Q002", {"dsl": "", "query": "只改文字"})
    again = json.loads(
        (tmp_path / run_id / "Q002" / "input" / "input.json").read_text(encoding="utf-8")
    )
    assert again["query"] == "只改文字"
    assert again["imageFile"] == "image.png", "没传截图时原截图必须保留"
    assert (tmp_path / run_id / "Q002" / "input" / "image.png").is_file()

    # 请求体里的 id 会被忽略：身份以路径为准，改内容不会改 ID。
    ignored = update_sample(tmp_path, run_id, "Q002", {
        "id": "Q999", "dsl": "", "imageBase64": value["samples"][0]["imageBase64"],
    })
    assert ignored["id"] == "Q002"
    assert [item["id"] for item in json.loads(
        (tmp_path / run_id / "summary.json").read_text(encoding="utf-8"))["samples"]
    ] == ["Q001", "Q002"]


def test_generated_id_follows_content_not_query(tmp_path):
    """ID 只做标识：同样 Query 但内容不同会得到不同 ID，同内容才是同一个 ID。"""
    first_dir = tmp_path / "a"
    second_dir = tmp_path / "b"
    first_dir.mkdir()
    second_dir.mkdir()
    value = payload()
    value["samples"][0]["id"] = ""
    same = import_batch(first_dir, value)["samples"][0]["id"]
    again = import_batch(second_dir, payload())["samples"][0]["id"]
    assert again != same, "第一个用例的 ID 由内容决定，另一次导入 id 非空"

    # 同 Query、不同 DSL → 不同 ID（ID 不做 Query 绑定）。
    third_dir = tmp_path / "c"
    third_dir.mkdir()
    changed = payload(dsl='["root","Layout",{"layout":"S-center"},["display"]]')
    changed["samples"][0]["id"] = ""
    changed_id = import_batch(third_dir, changed)["samples"][0]["id"]
    assert changed_id.startswith("H-") and changed_id != same


def test_partial_update_keeps_untouched_fields_and_accepts_a_custom_category(tmp_path):
    """只改分类这种局部修改不能把 Query／DSL／期望项清掉，自定义分类名也要能存。"""
    value = payload()
    summary = import_batch(tmp_path, value)
    run_id = summary["runId"]
    row = update_sample(tmp_path, run_id, "Q001", {"category": "通勤"})
    assert row["category"] == "通勤"
    input_dir = tmp_path / run_id / "Q001" / "input"
    meta = json.loads((input_dir / "input.json").read_text(encoding="utf-8"))
    assert meta["category"] == "通勤"
    assert meta["query"] == "显示天气", "没传的字段必须保持原值"
    assert (input_dir / "genui.jsonl").read_text(encoding="utf-8").strip(), "DSL 不能被清空"
    assert (input_dir / "image.png").is_file(), "截图不能被清空"

    # 显式清空：传 null / 空列表才算真的清。
    cleared = update_sample(tmp_path, run_id, "Q001", {"category": None, "expectedData": []})
    assert cleared["category"] == ""


def test_run_category_sets_every_image_in_the_batch(tmp_path):
    """画廊整批改分类：一次改掉这批所有图片的分类，不动 DSL、截图与期望项。"""
    value = payload()
    value["samples"].append({**value["samples"][0], "id": "Q002"})
    summary = import_batch(tmp_path, value)
    run_id = summary["runId"]
    result = update_run_category(tmp_path, run_id, {"category": "通勤"})
    assert result == {"runId": run_id, "category": "通勤", "sampleCount": 2}
    after = json.loads((tmp_path / run_id / "summary.json").read_text(encoding="utf-8"))
    assert after["category"] == "通勤"
    assert [row["category"] for row in after["samples"]] == ["通勤", "通勤"]
    for sample_id in ("Q001", "Q002"):
        meta = json.loads(
            (tmp_path / run_id / sample_id / "input" / "input.json").read_text(encoding="utf-8")
        )
        assert meta["category"] == "通勤"
        assert meta["query"] == "显示天气", "整批改分类不能动内容"
    assert (tmp_path / run_id / "Q001" / "input" / "image.png").is_file()

    # 传 null 表示清回未分类；自定义名字允许，超长拒绝。
    assert update_run_category(tmp_path, run_id, {"category": None})["category"] == ""
    assert update_run_category(tmp_path, run_id, {"category": "自定-义 分类"})["category"] == "自定-义 分类"
    with pytest.raises(ValueError, match="40"):
        update_run_category(tmp_path, run_id, {"category": "x" * 41})


def test_update_sample_rejects_unknown_or_non_import_batches(tmp_path):
    value = payload()
    summary = import_batch(tmp_path, value)
    run_id = summary["runId"]
    with pytest.raises(KeyError):
        update_sample(tmp_path, run_id, "Q404", {"dsl": "", "imageBase64": value["samples"][0]["imageBase64"]})
    with pytest.raises(KeyError):
        update_sample(tmp_path, "batch_missing", "Q001", {"dsl": ""})
    # 普通批跑运行不能当导入样本改。
    plain = tmp_path / "run_plain"
    plain.mkdir()
    (plain / "summary.json").write_text(
        json.dumps({"runId": "run_plain", "samples": [{"id": "Q001"}]}), encoding="utf-8"
    )
    with pytest.raises(ValueError):
        update_sample(tmp_path, "run_plain", "Q001", {"dsl": ""})


def test_cardspec_user_query_fills_an_empty_query(tmp_path):
    """CardSpec 顶层的 userQuery 是用户原话：Query 留空时补上，显式填写的仍然优先。"""
    value = payload()
    del value["samples"][0]["query"]
    value["samples"][0]["cardSpec"] = {"userQuery": " 帮我做个西湖天气卡片 ", "size": "2x2"}
    summary = import_batch(tmp_path, value)
    assert summary["samples"][0]["query"] == "帮我做个西湖天气卡片"
    metadata = json.loads(
        (tmp_path / summary["runId"] / "Q001" / "input" / "input.json").read_text(encoding="utf-8")
    )
    assert metadata["query"] == "帮我做个西湖天气卡片"

    # 显式填写的 Query 优先，不被 CardSpec 覆盖。
    explicit = tmp_path / "explicit"
    explicit.mkdir()
    again = payload()
    again["samples"][0]["cardSpec"] = {"userQuery": "CardSpec 里的旧话术"}
    assert import_batch(explicit, again)["samples"][0]["query"] == "显示天气"

    # CardSpec 没有 userQuery 或它不是字符串时保持空 Query，不编造。
    for index, card_spec in enumerate(({}, {"userQuery": 42})):
        spare = tmp_path / ("spare%d" % index)
        spare.mkdir()
        without = payload()
        del without["samples"][0]["query"]
        without["samples"][0]["cardSpec"] = card_spec
        assert import_batch(spare, without)["samples"][0]["query"] == ""


def test_offline_ocr_clue_and_unavailable_share_model(tmp_path, monkeypatch):
    checker, plugin = module("external"), module("plugin")
    ctx = context(tmp_path, payload())
    monkeypatch.setattr(checker.core, "check_ocr", lambda *_: ["[待复核·文字缺失]天气"])
    findings, evidence, picture, boundary = checker.inspect(ctx)
    result = plugin._score_result(ctx, findings, evidence, picture, boundary)
    assert result.get("facts", {}).get("score") == 100
    assert result.get("facts", {}).get("scoreLow") == 85
    monkeypatch.setattr(checker.core, "check_ocr", lambda *_: ["[检测失败·OCR]ImportError"])
    result = plugin._score_result(ctx, *checker.inspect(ctx))
    assert result.get("facts", {}).get("score") is None
    assert result.get("facts", {}).get("verdict") == "待评"
    (Path(ctx.get("sampleDir")) / "input/genui.jsonl").write_text("changed")
    with pytest.raises(ValueError, match="已变化"):
        checker.inspect(ctx)


@pytest.mark.parametrize("dsl", ['[["root", "Text", {}]]', '[{"version":"v1.0"}]'])
def test_unsupported_protocol_is_pending_not_rejected(tmp_path, dsl):
    result = module("plugin").process_sample(context(tmp_path, payload(dsl)))
    assert result.get("facts", {}).get("score") is None
    assert result.get("facts", {}).get("verdict") == "待评"


@pytest.mark.asyncio
async def test_import_worker_skips_browser_gallery_and_serves_image(tmp_path):
    summary = import_batch(tmp_path, payload("{invalid-json"))
    run_id = summary.get("runId")
    manager = PostprocessManager(tmp_path, PLUGINS)
    await manager.start()
    try:
        execution = manager.enqueue(run_id, ["quality-score"])
        await manager.queue.join()
        execution_id = execution.get("executionId")
        stages = manager.executions(run_id)[0].get("plugins")
        assert [stage.get("id") for stage in stages] == ["quality-score"]
        result = manager.sample_result(run_id, execution_id, "quality-score", "Q001")
        assert result.get("facts", {}).get("score") == 0
        assert result.get("facts", {}).get("verdict") == "输入硬错误淘汰"
        captures = [item for item in result.get("artifacts", []) if item.get("key") == "capture"]
        assert len(captures) == 1
        assert captures[0].get("url", "").startswith("/debug/batch/runs/")
        api_manager = BatchTaskManager(tmp_path / "datasets", tmp_path,
                                       tmp_path / "traces", tmp_path / "cloud")
        app = FastAPI()
        register_batch_routes(app, task_manager=api_manager)
        image = TestClient(app).get(captures[0].get("url"))
        assert image.status_code == 200
        assert image.content.startswith(b"\x89PNG")
        result = compare(manager, run_id, run_id, left_sample_id="Q001", right_sample_id="Q001")
        assert result.get("rows")[0].get("left", {}).get("imageUrl") == captures[0].get("url")
    finally:
        await manager.close()


@pytest.mark.parametrize("mismatch", ["comparisonScope", "appVersion"])
def test_single_different_ids_and_scope_mismatch(tmp_path, mismatch):
    manager = PostprocessManager(tmp_path, PLUGINS)
    save_scores(manager, "before", {"a": 85, "b": 100})
    save_scores(manager, "after", {"c": 100})
    result = compare(manager, "before", "after", left_sample_id="a", right_sample_id="c")
    row = result.get("rows")[0]
    assert row.get("left", {}).get("sampleId") == "a"
    assert row.get("right", {}).get("sampleId") == "c"
    assert row.get("scoreDelta") == row.get("scoreLowDelta") == 15
    assert result.get("left", {}).get("total") == 1
    with pytest.raises(ValueError, match="同时指定"):
        compare(manager, "before", "after", left_sample_id="a")
    with pytest.raises(ValueError, match="对应样本"):
        compare(manager, "before", "after", left_sample_id="missing", right_sample_id="c")
    path = tmp_path / "after/postprocess/exec_1/plugins/quality-score/samples/c/result.json"
    stored = json.loads(path.read_text(encoding="utf-8"))
    for item in stored.get("artifacts", []):
        if item.get("key") == "detail":
            evidence = item.get("data", {}).get("evidence", {})
            if mismatch == "comparisonScope":
                evidence["comparisonScope"] = {"imageSource": "native"}
            else:
                evidence.setdefault("renderContext", {})["appVersion"] = "11.7.7.300"
    path.write_text(json.dumps(stored), encoding="utf-8")
    result = compare(manager, "before", "after", left_sample_id="a", right_sample_id="c")
    assert result.get("rows")[0].get("scoreDelta") is None
    assert result.get("rows")[0].get("alignment") == "evidence-mismatch"


def test_real_ocr_when_local_dependency_and_chinese_font_available(tmp_path):
    """可选的真实 OCR 联调；没有依赖/字库时明确跳过，其余测试不依赖 OCR。"""
    pytest.importorskip("rapidocr_onnxruntime")
    try:
        font = ImageFont.truetype("msyh.ttc", 40)
    except OSError:
        pytest.skip("本机无中文测试字库")
    picture = Image.new("RGB", (500, 160), "white")
    ImageDraw.Draw(picture).text((25, 45), "显示天气", fill="black", font=font)
    buffer = io.BytesIO()
    picture.save(buffer, format="PNG")
    value = payload()
    sample = value.get("samples")[0]
    sample["imageBase64"] = base64.b64encode(buffer.getvalue()).decode()
    sample["expectedIntents"] = []  # 该测试 Query 只有文本展示，无交互需求。
    result = module("plugin").process_sample(context(tmp_path, value))
    assert result.get("facts", {}).get("score") == 100
    assert result.get("facts", {}).get("scoreLow") == 100
    assert result.get("facts", {}).get("verdict") == "范围内未扣分"
