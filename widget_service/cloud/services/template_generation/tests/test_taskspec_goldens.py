# -*- coding: utf-8 -*-
"""Layer B taskspec 金样回归：回放录制响应后整链路结果必须与金样一致。

用例尚未录制（需要真实 LLM 额度）时跳过；录制后任何差异（含未重新
固化的已申报差异）都让本测试失败——固化是 PR 的一部分。
"""

import asyncio
import json

import pytest

from services.template_generation.test_support import golden as golden_tool
from services.template_generation.test_support import golden_taskspecs

_SELF_TEST_PAYLOAD = {
    "content": {
        "userQuery": "金样链路自检",
        "size": "2x2",
        "title": "自检",
        "description": "链路自检",
        "candidateDataBindings": [],
        "candidateAssetIds": [],
    },
    "deviceInfo": {"prdVer": "11.7.5.208", "locale": "zh-CN"},
    "session": {"sessionId": "golden-selftest", "interactionId": "001", "isNew": True},
    "userAuth": {"user": {"userId": ""}},
    "utterance": {"original": "金样链路自检", "type": "text"},
}


def test_taskspec_goldens_replay_matches_generation() -> None:
    case_ids = golden_taskspecs.blessed_case_ids()
    if not case_ids:
        pytest.skip(
            "No recorded taskspec goldens. Record with:\n"
            "  python3 -m services.template_generation.test_support.golden_taskspecs "
            "record --corpus-dir <widget_batch_cases 目录>",
        )
    generated = {}
    blessed = {}
    missed = []
    for case_id in case_ids:
        text, is_missed = asyncio.run(golden_taskspecs.replay_case_text(case_id))
        generated[case_id] = golden_tool.TemplateGolden(
            template_id=case_id,
            meta={},
            text=text,
        )
        blessed[case_id] = (
            golden_taskspecs.GOLDEN_ROOT / case_id / "golden.json"
        ).read_text(encoding="utf-8")
        if is_missed:
            missed.append(case_id)
    comparison = golden_tool.compare(generated, blessed)
    report = golden_tool.render_check_report(
        [
            golden_tool.CheckLayer(
                label="Taskspecs",
                comparison=comparison,
                extra_failed=tuple(missed),
            )
        ]
    )
    if report.has_divergence:
        pytest.fail(report.text, pytrace=False)


def test_taskspec_record_replay_roundtrip_is_deterministic() -> None:
    """无 LLM 的链路自检：空回放表下两次执行结果必须逐字节一致。"""
    payload = json.loads(json.dumps(_SELF_TEST_PAYLOAD))
    first, _ = asyncio.run(
        golden_taskspecs.execute_case("SELFTEST", payload, golden_taskspecs.ReplayingTransport({}))
    )
    second, _ = asyncio.run(
        golden_taskspecs.execute_case("SELFTEST", payload, golden_taskspecs.ReplayingTransport({}))
    )
    assert golden_tool.canonicalize(first) == golden_tool.canonicalize(second)
