"""JSONL 解析埋点精简及父阶段计数隔离回归。"""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import copy_context

import pytest
from debug_tools.batch_testing.trace_parser import TraceImporter
from services.compact_dsl_a2ui_converter import _strip_optional_genui_fence
from services.generation_trace_recorder import GenerationTraceRecorder, trace_span

UID = "batch-1234abcd-00001-000"
VALID = '["root","Column",{},[]]'
BROKEN = '["root","Column",{"width":"matchParent" "height":"matchParent"},[]]'


@contextmanager
def _record(root, uid=UID):
    recorder = GenerationTraceRecorder()
    recorder.bind_request(uid, enabled=True, trace_root=root)
    token = recorder.activate()
    try:
        yield recorder
    finally:
        recorder.finalize(status="success")
        recorder.deactivate(token)


def _view(root, uid=UID):
    view = TraceImporter(root).read(uid)
    assert view.get("status") == "complete", view.get("warnings")
    nodes = view.get("nodes")
    assert isinstance(nodes, list)
    return view, nodes


@pytest.mark.parametrize("source,expected", [
    (VALID, VALID), ("\ufeff " + VALID + " ", VALID),
    ("```genui\n" + VALID + "\n```", VALID), ("", ""),
])
def test_noop_repeated_parsing_has_only_parent_summary(tmp_path, source, expected):
    with _record(tmp_path):
        with trace_span("dsl.processing", stage="dsl.processing"):
            for _ in range(5):
                assert _strip_optional_genui_fence(source) == expected
    _, nodes = _view(tmp_path)
    assert len(nodes) == 2
    parent = next(node for node in nodes if node.get("operation") == "dsl.processing")
    assert parent.get("metrics") == {"jsonlParseCalls": 5, "jsonlParseNoop": 5}
    assert "JSONL 解析 5 次，无需修复 5 次" in parent.get("description", "")
    assert parent.get("artifacts") == []
    assert not list(tmp_path.rglob("*.txt"))


def test_real_repairs_remain_separate_with_input_and_output(tmp_path):
    with _record(tmp_path):
        with trace_span("validation.evaluate", stage="validation.evaluate"):
            for _ in range(3):
                repaired = _strip_optional_genui_fence(BROKEN)
                value = json.loads(repaired)
                assert value[2] == {"width": "matchParent", "height": "matchParent"}
            assert _strip_optional_genui_fence(repaired) == repaired
    view, nodes = _view(tmp_path)
    repairs = [node for node in nodes if node.get("operation") == "compact_dsl.jsonl_repair"]
    assert len(repairs) == 3
    for node in repairs:
        assert node.get("durationMs", -1) >= 0.0
        assert node.get("attributes", {}).get("repairedBlockCount") == 1
        refs = node.get("artifacts")
        assert isinstance(refs, list)
        assert {ref.get("role") for ref in refs} == {"input", "output"}
    parent = next(node for node in nodes if node.get("operation") == "validation.evaluate")
    assert parent.get("metrics") == {
        "jsonlParseCalls": 4, "jsonlParseRepaired": 3, "jsonlParseNoop": 1,
    }
    assert view.get("summary", {}).get("retryCounts", {}) == {}


def test_failed_repair_returns_original_and_retains_diagnostics(tmp_path, monkeypatch):
    import json_repair

    def fail(block):
        raise ValueError("无法修复")

    monkeypatch.setattr(json_repair, "loads", fail)
    source = VALID + "\n" + BROKEN
    with _record(tmp_path):
        with trace_span("dsl.processing", stage="dsl.processing"):
            assert _strip_optional_genui_fence(source) == source
    _, nodes = _view(tmp_path)
    failed = next(node for node in nodes if node.get("operation") == "compact_dsl.jsonl_repair")
    assert failed.get("status") == "failed"
    assert failed.get("attributes", {}).get("blockIndex") == 2
    assert failed.get("attributes", {}).get("exceptionType") == "ValueError"
    refs = failed.get("artifacts")
    assert isinstance(refs, list)
    assert len(refs) == 1 and refs[0].get("role") == "input"
    parent = next(node for node in nodes if node.get("operation") == "dsl.processing")
    assert parent.get("metrics") == {"jsonlParseCalls": 1, "jsonlParseFailed": 1}


def test_nested_stage_thread_and_root_counts_are_exclusive(tmp_path):
    with _record(tmp_path):
        _strip_optional_genui_fence(VALID)
        with trace_span("outer", stage="dsl"):
            _strip_optional_genui_fence(VALID)
            with trace_span("inner", stage="validation"):
                with ThreadPoolExecutor(max_workers=4) as executor:
                    futures = []
                    for _ in range(12):
                        context = copy_context()
                        futures.append(executor.submit(
                            context.run, _strip_optional_genui_fence, VALID,
                        ))
                    for future in futures:
                        assert future.result() == VALID
            _strip_optional_genui_fence(VALID)
    _, nodes = _view(tmp_path)
    for operation, calls in (("request", 1), ("outer", 2), ("inner", 12)):
        node = next(item for item in nodes if item.get("operation") == operation)
        assert node.get("metrics") == {"jsonlParseCalls": calls, "jsonlParseNoop": calls}


@pytest.mark.asyncio
async def test_concurrent_requests_do_not_share_counts(tmp_path):
    async def run(uid, count):
        with _record(tmp_path, uid):
            with trace_span("dsl.processing", stage="dsl"):
                for _ in range(count):
                    assert await asyncio.to_thread(_strip_optional_genui_fence, VALID) == VALID

    await asyncio.gather(run(UID, 3), run("batch-abcdef12-00001-000", 7))
    for uid, count in ((UID, 3), ("batch-abcdef12-00001-000", 7)):
        _, nodes = _view(tmp_path, uid)
        node = next(item for item in nodes if item.get("operation") == "dsl.processing")
        assert node.get("metrics") == {"jsonlParseCalls": count, "jsonlParseNoop": count}


def test_legacy_trace_without_counters_has_no_synthetic_summary(tmp_path):
    with _record(tmp_path):
        with trace_span("dsl.processing", stage="dsl.processing"):
            pass
    _, nodes = _view(tmp_path)
    node = next(item for item in nodes if item.get("operation") == "dsl.processing")
    assert node.get("metrics") == {}
    assert node.get("description") == ""


def test_unexpected_parse_exception_is_preserved_and_not_counted_as_noop(tmp_path, monkeypatch):
    def fail(source):
        raise RecursionError("输入嵌套过深")

    with _record(tmp_path):
        with pytest.raises(RecursionError, match="输入嵌套过深"):
            with trace_span("dsl.processing", stage="dsl.processing"):
                with monkeypatch.context() as patch:
                    patch.setattr(json, "loads", fail)
                    _strip_optional_genui_fence(VALID)
    _, nodes = _view(tmp_path)
    parent = next(node for node in nodes if node.get("operation") == "dsl.processing")
    assert parent.get("status") == "failed"
    assert parent.get("metrics") == {"jsonlParseCalls": 1, "jsonlParseFailed": 1}
