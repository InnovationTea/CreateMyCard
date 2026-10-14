"""模板语义、布局、PNG 和空日期业务的公共链路回归；仅使用标准示例数据。"""

import json
from pathlib import Path
from typing import Any

import pytest

from models.generation import CandidateDataBinding, TaskSpec
from services.generation_pipeline import (
    DesignCompactProcessor,
    DslProcessingContext,
    DslProcessorKind,
)
from services.protocol_registry import A2UIProtocolRegistry
from services.template_generation.engine.pipeline import generate_template_a2ui
from services.template_generation.source_adapter import prepare_template_source_dsl

_FIXTURES = Path(__file__).parent / "fixtures/template_validation_recovery.json"
_CASES = json.loads(_FIXTURES.read_text(encoding="utf-8"))


@pytest.mark.asyncio
@pytest.mark.parametrize("fusion", [False, True])
@pytest.mark.parametrize("case", _CASES, ids=lambda case: case.get("name"))
async def test_template_output_passes_public_validation(case: dict, fusion: bool) -> None:
    task = TaskSpec.model_validate(case.get("task"))
    card = case.get("card")
    assert isinstance(card, dict)
    bindings = tuple(CandidateDataBinding.model_validate(item) for item in case.get("bindings", []))

    class Model:
        async def generate_json(self, _prompt: Any, *, phase: str) -> dict:
            intent = case.get("intent")
            assert isinstance(intent, dict)
            return intent

        async def generate(self, *_args: Any, **_kwargs: Any) -> str:
            body = case.get("body")
            assert isinstance(body, str)
            return body

    output = await generate_template_a2ui(
        task, card, bindings, Model(), enable_fusion_ball=fusion,
    )
    profile = A2UIProtocolRegistry("a2ui-form-rom6.0-v1").get_profile()
    source = prepare_template_source_dsl(
        output.a2ui, processor_kind=DslProcessorKind.DESIGN_COMPACT,
        size=task.size, protocol_profile=profile,
    )
    result = DesignCompactProcessor().process(
        source,
        DslProcessingContext(
            size=task.size, task_spec=task.model_dump(mode="json"), card_spec=card,
            protocol_profile=profile, design_profile_id="design-compact-dsl",
            skip_compact_dsl_validation=True,
        ),
    )
    assert not result.errors, result.errors
    assert result.standard_dsl
