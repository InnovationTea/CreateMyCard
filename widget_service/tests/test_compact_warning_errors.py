"""只升级新增几何警告，保留原有警告的非阻断和不重试语义。"""

import json
from dataclasses import replace

import pytest

from services.card_validation.compact_dsl_validator import (
    validate_compact_dsl,
)
from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext
from services.prompt_builder import PromptBuilder
from services.retry_controller import RetryController


def _source(*, clipped: bool = False) -> str:
    rows = [
        ["root", "Column", {}, ["slot"]],
        ["slot", "Row", {"width": 100, "height": 20, "clip": True}, ["label"]],
        ["label", "Text", {"width": 80, "height": 40 if clipped else 20, "content": "内容"}],
    ]
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def _context() -> DslProcessingContext:
    return DslProcessingContext(
        size="2x4",
        task_spec={
            "size": "2x4",
            "appVersion": "12.0.0.1",
            "dataModelSchema": {},
            "assetCandidates": [],
        },
        card_spec={"suggestSize": "2x4", "dataBindings": []},
        protocol_profile={"sizes": {"2x4": {"width": 300, "height": 150}}},
    )


@pytest.mark.parametrize("fixed", [False, True])
@pytest.mark.asyncio
async def test_clipping_warning_enters_repair_and_rechecks(fixed: bool) -> None:
    processor = DesignCompactProcessor()
    context = _context()
    prompts: list[str] = []

    def evaluate(source: str) -> list[str]:
        return [issue.repair_message() for issue in processor.process(source, context).errors]

    def repair(source: str, errors: list[str]) -> str:
        assert any("COMPACT_LAYOUT_CLIPPED" in error for error in errors)
        messages = PromptBuilder().build_repair(
            [{"role": "system", "content": "生成卡片"}, {"role": "user", "content": "内容"}],
            source,
            [{"message": error} for error in errors],
            dsl_format="design-compact-dsl",
        )
        content = messages[1].get("content")
        assert isinstance(content, str)
        prompts.append(content)
        return _source(clipped=not fixed)

    result = await RetryController().run(
        lambda: _source(clipped=True),
        evaluate,
        retry_on_quality_failure=True,
        max_repair_attempts=2,
        repair=repair,
    )
    assert result.retryCount == (1 if fixed else 2)
    assert bool(result.errors) is not fixed
    assert all("COMPACT_LAYOUT_CLIPPED" in prompt for prompt in prompts)


def test_only_geometry_warnings_merge_with_existing_errors() -> None:
    context = replace(
        _context(),
        card_spec={
            "suggestSize": "2x4",
            "dataBindings": [{"writeResultTo": "/data/weather"}],
        },
    )
    source = "\n".join(
        [
            '["root","Column",{},["image","label"]]',
            '["image","Image",{}]',
            '["label","Text",{"content":{"path":"/data/missing"}}]',
        ]
    )
    result = DesignCompactProcessor().process(source, context)
    messages = "\n".join(issue.message for issue in result.errors)
    assert "/data/missing" in messages
    assert "declared data capability is not used" not in messages
    assert "COMPACT_LAYOUT_UNVERIFIED" in messages
    assert all(issue.severity == "error" for issue in result.issues)


def test_success_keeps_result_shape_and_empty_warnings() -> None:
    result = validate_compact_dsl(
        _source(),
        task_spec=_context().task_spec,
        card_spec=_context().card_spec,
    )
    assert result.warnings == ()


def test_unused_data_remains_warning() -> None:
    result = validate_compact_dsl(
        _source(),
        task_spec=_context().task_spec,
        card_spec={"suggestSize": "2x4", "dataBindings": [{"writeResultTo": "/data/weather"}]},
    )
    assert result.warnings == (
        "/data/weather: declared data capability is not used by any component.",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("clipped", [False, True])
async def test_existing_warning_does_not_trigger_or_extend_repair(clipped: bool) -> None:
    context = replace(
        _context(),
        card_spec={"suggestSize": "2x4", "dataBindings": [{"writeResultTo": "/data/weather"}]},
    )
    processor = DesignCompactProcessor()

    def evaluate(source: str) -> list[str]:
        return [issue.repair_message() for issue in processor.process(source, context).errors]

    def repair(_source_dsl: str, errors: list[str]) -> str:
        assert clipped
        assert any("COMPACT_LAYOUT_CLIPPED" in error for error in errors)
        assert all("declared data capability is not used" not in error for error in errors)
        return _source()

    result = await RetryController().run(
        lambda: _source(clipped=clipped),
        evaluate,
        retry_on_quality_failure=True,
        max_repair_attempts=2,
        repair=repair,
    )
    assert result.errors == []
    assert result.retryCount == (1 if clipped else 0)
    final = processor.process(result.result, context)
    assert not final.errors
    assert any("declared data capability is not used" in issue.message for issue in final.issues)
    assert all(issue.severity == "warning" for issue in final.issues)
