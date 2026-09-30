# -*- coding: utf-8 -*-
"""统一金样门禁（general golden pytest）：三层金样一次全量比对。

模板（Layer A）、taskspec（Layer B）、场景（Layer C）的金样集必须与当前
生成完全一致；已申报但未固化的差异同样失败——固化（``golden_cli bless``）
是 PR 的一部分，评审者据此看到「哪些生成 UI 变了」。比较逻辑直接复用
``golden_cli`` 的分层实现，保证与 ``golden_cli check`` 的判定逐字节一致。
Layer B 未录制任何用例时跳过该层。
"""

import pytest

from services.template_generation.test_support import golden as golden_layer
from services.template_generation.test_support import golden_cli

_LAYER_LABELS = ("Templates", "Taskspecs", "Scenarios")


def test_golden_workflow_all_layers_match_blessed_set() -> None:
    layer_states = golden_cli._check_layers(frozenset(), False)
    check_layers = []
    for state, label in zip(layer_states, _LAYER_LABELS):
        if state.skipped:
            continue
        check_layers.append(
            golden_layer.CheckLayer(
                label=label,
                comparison=state.comparison,
                extra_failed=state.replay_missed,
            )
        )
    report = golden_layer.render_check_report(check_layers)
    if report.has_divergence:
        pytest.fail(report.text, pytrace=False)


def test_preview_snapshot_generation_is_deterministic() -> None:
    first = golden_layer.build_snapshots()
    second = golden_layer.build_snapshots()
    assert {key: value.text for key, value in first.items()} == {
        key: value.text for key, value in second.items()
    }
