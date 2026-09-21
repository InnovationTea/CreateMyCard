"""Provider Templates must render with only their required data fields present.

模板预览数据集总是填充全部可选字段，因此无法暴露“可选字段缺失时，仅由条件节点
构成的容器被渲染为空”的缺陷（2026-09-21 线上案例：HeartRateOverviewMinMaxFull@1、
SleepOverviewFull@1、SleepOverviewNapFull@1 在 /updatedAt、/sleepScore 等可选字段
缺失时触发 Expanded container must contain at least one child）。

这里用仅含必需字段（primaryData + secondaryData）的数据模型，经真实引擎链路
（Search -> Planner -> 第二层展开 -> 扩展校验）渲染每个 2x2 Full 模板。
通过 trusted_template_candidate_ids 钉住目标模板，桩模型只回放确定性 Plan 体。
覆盖范围：单绑定 Full 模板（无 Action 布局语法所要求的形态）；Hero/Compact/Support
需要动作与双业务装配，不在本用例内。
"""

from __future__ import annotations

import asyncio
import json

import pytest

from models.generation import CandidateDataBinding, TaskSpec
from services.template_generation.engine.cardplan.preview_dataset import (
    _sample_value,
    _set_path,
)
from services.template_generation.engine.cardplan.provider_bundle import (
    provider_template_layout_kind,
)
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.cardplan.template_retrieval import (
    _TEMPLATE_QUERY_DISCRIMINATORS,
)
from services.template_generation.engine.pipeline import generate_template_a2ui


def _required_only_schema(definition, extra_paths: tuple[str, ...] = ()) -> dict[str, object]:
    schema: dict[str, object] = {"data": {}}
    wanted_full_paths = {
        f"{definition.data_domain.rstrip('/')}{path}"
        for path in (*definition.required_data, *extra_paths)
    }
    for name, binding in definition.bindings.items():
        full_path = f"{definition.data_domain.rstrip('/')}{binding.path}"
        if full_path not in wanted_full_paths:
            continue
        leaf = {
            "type": binding.data_type,
            "description": f"{definition.business_id}.{name} 必需字段渲染数据",
            "sampleValue": _sample_value(definition, name, binding.data_type),
        }
        _set_path(schema, full_path, leaf)
    return schema


def _full_template_ids() -> list[str]:
    registry = get_cardplan_registry()
    # BatteryOverview 依赖专属的 selector/variant 准入机制（电量数值-文本配对），
    # 仅必需字段意图无法表达其真实准入条件，由 battery 专项测试覆盖。
    return sorted(
        wire_id
        for wire_id, definition in registry.templates.items()
        if definition.binding_count == 1
        and provider_template_layout_kind(wire_id) == "Full"
        and not wire_id.startswith("BatteryOverview")
    )


class _DeterministicPlanModel:
    def __init__(self, intent: dict[str, object], body: str) -> None:
        self._intent = intent
        self._body = body

    async def generate_json(self, prompt, *, phase):
        assert phase == "template-retrieval-query", phase
        return json.loads(json.dumps(self._intent))

    async def generate(self, prompt, *_args, **_kwargs):
        return self._body


@pytest.mark.parametrize("template_id", _full_template_ids())
def test_full_template_renders_with_required_fields_only(template_id: str) -> None:
    registry = get_cardplan_registry()
    definition = registry.templates[template_id]
    assert definition.capability_id
    schema = _required_only_schema(
        definition, _TEMPLATE_QUERY_DISCRIMINATORS.get(template_id, ())
    )
    # 查询判别字段（如 WeatherOverviewAlertFull@1 的 /current/alertLevel）是模板
    # 准入条件的一部分，必须与必需字段一起进入意图与候选字段。
    paths = sorted(
        {*definition.required_data, *_TEMPLATE_QUERY_DISCRIMINATORS.get(template_id, ())}
    )
    assert paths, f"{template_id} declares no required data"

    task = TaskSpec(
        userQuery=f"仅必需字段渲染 {template_id}",
        size="2x2",
        appVersion="11.7.7.343",
        dataModelSchema=schema,
    )
    binding = CandidateDataBinding(
        capabilityId=definition.capability_id,
        writeResultTo=definition.data_domain,
        candidateOutputFields=paths,
    )
    card_spec = {
        "suggestSize": "2x2",
        "dataBindings": [
            {
                "capabilityId": definition.capability_id,
                "writeResultTo": definition.data_domain,
            }
        ],
    }
    intent = {
        "requiredOutputFieldsByCapability": {definition.capability_id: paths},
        "primaryOutputFieldByCapability": {},
        "action": [],
    }
    body = f'Template("SingleFocusLayout@1",{{}},Template("{template_id}",{{}}));'

    output = asyncio.run(
        generate_template_a2ui(
            task,
            card_spec,
            (binding,),
            _DeterministicPlanModel(intent, body),
            trusted_template_candidate_ids=(template_id,),
        )
    )

    assert template_id in output.template_ids
    assert output.expanded_component_count > 0
