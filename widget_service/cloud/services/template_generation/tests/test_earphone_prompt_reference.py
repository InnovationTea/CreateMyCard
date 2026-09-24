"""耳机提示词模板事实与作用域回归。

本文件整体保留为普通测试（不转场景金样）：断言对象是检索提示词里的
``earphoneTemplateReference`` 字节内容——Full 模板的 ``missingInputFields``
覆盖语义、``roles``，以及其他业务不得收到耳机动作引用。提示词字节契约
门禁 Layer B 录制重放的有效性（提示词漂移 = 显式重放未命中），按策略
不做快照化。
"""

import json

import pytest

from models.generation import CandidateDataBinding
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.cardplan.template_retrieval import (
    _earphone_template_reference,
    build_template_retrieval_prompt,
)
from services.template_generation.tests.test_template_retrieval import _binding, _task


def _earphone_binding(fields: list[str]) -> CandidateDataBinding:
    return CandidateDataBinding(
        capabilityId="GetEarphoneInfo",
        writeResultTo="/data/earphone",
        candidateOutputFields=fields,
    )


@pytest.mark.parametrize(
    ("fields", "expected_missing"),
    [
        (["/earphoneName", "/batteryLevel"],
         ["/isConnected", "/leftBatteryLevel", "/rightBatteryLevel"]),
        (["/earphoneName", "/batteryLevel", "/isConnected",
          "/leftBatteryLevel", "/rightBatteryLevel"], []),
    ],
)
def test_full_reference_distinguishes_coverage_from_required_inputs(
    fields: list[str], expected_missing: list[str],
) -> None:
    references = _earphone_template_reference(
        get_cardplan_registry(), (_earphone_binding(fields),),
    )
    full = next(
        item for item in references
        if item.get("templateId") == "BluetoothDeviceOverviewEarbudPairFull@1"
    )
    assert full.get("missingInputFields") == expected_missing
    assert full.get("roles") == ["Full"]


@pytest.mark.parametrize("mixed", [False, True])
def test_other_businesses_do_not_receive_earphone_action_reference(mixed: bool) -> None:
    bindings = (_binding(),)
    if mixed:
        bindings += (_earphone_binding(["/earphoneName", "/batteryLevel"]),)
    messages = build_template_retrieval_prompt(_task(), get_cardplan_registry(), bindings)
    content = messages[1].get("content")
    assert isinstance(content, str)
    assert "earphoneTemplateReference" not in json.loads(content)
