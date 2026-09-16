# -*- coding: utf-8 -*-
"""Layer A 模板金样回归：确定性生成结果必须与已固化的金样集一致。

失败处理约定：任何差异（含已申报但未固化的）都让本测试失败——固化
（``golden accept``）是 PR 的一部分，评审者据此看到「哪些模板 UI 变了」。
"""

import pytest

from services.template_generation.test_support import golden as golden_tool


def test_template_golden_set_is_blessed_and_matches_generation() -> None:
    if not golden_tool.TEMPLATES_DIR.is_dir():
        pytest.fail(
            "Template golden set is missing. Bootstrap it with:\n"
            "  python3 -m services.template_generation.test_support.golden accept",
            pytrace=False,
        )
    generated = golden_tool.build_snapshots()
    blessed = golden_tool.load_blessed()
    comparison = golden_tool.compare(generated, blessed)
    report = golden_tool.render_check_report(
        [golden_tool.CheckLayer(label="Templates", comparison=comparison)]
    )
    if report.has_divergence:
        pytest.fail(report.text, pytrace=False)


def test_preview_snapshot_generation_is_deterministic() -> None:
    first = golden_tool.build_snapshots()
    second = golden_tool.build_snapshots()
    assert {key: value.text for key, value in first.items()} == {
        key: value.text for key, value in second.items()
    }
