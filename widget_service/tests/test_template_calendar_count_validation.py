"""模板入口的显式跳过标记控制 Compact 校验；解析权限保持独立。"""

import json
from pathlib import Path

import pytest

from services import generation_pipeline
from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.compact_dsl_parse_context import MODEL_PARSE_CONTEXT, TEMPLATE_PARSE_CONTEXT
from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext

_CASE = Path(__file__).parent / "compact_dsl_validate/_collect_semantic_text_errors/02"


def load_case():
    source = (_CASE / "sample_compact.dsl").read_text(encoding="utf-8")
    task = json.loads((_CASE / "sample_task_spec.json").read_text(encoding="utf-8"))
    card = json.loads((_CASE / "sample_card_spec.json").read_text(encoding="utf-8"))
    task.update(size="2x4", appVersion="11.7.7.300")
    card["suggestSize"] = "2x4"
    return source, task, card


@pytest.mark.parametrize("parse_context", [MODEL_PARSE_CONTEXT, TEMPLATE_PARSE_CONTEXT])
@pytest.mark.parametrize("skip", [False, True])
@pytest.mark.parametrize("template_marker", [False, True])
def test_only_explicit_flag_skips_compact_validation(
    monkeypatch, parse_context, skip, template_marker,
):
    source, task, card = load_case()
    if template_marker:
        source = source.replace('"value"', '"template_root"')
    calls = []

    def record_validation(*args, **kwargs):
        calls.append(True)
        return validate_compact_dsl(*args, **kwargs)

    monkeypatch.setattr(generation_pipeline, "validate_compact_dsl", record_validation)
    result = DesignCompactProcessor().process(source, DslProcessingContext(
        size="2x4", task_spec=task, card_spec=card, protocol_profile={"version": "v0.9"},
        skip_compact_dsl_validation=skip, parse_context=parse_context,
    ))
    assert calls == ([] if skip else [True])
    if skip:
        assert not result.errors
        assert result.standard_dsl
    else:
        assert result.errors


@pytest.mark.parametrize("parse_context", [MODEL_PARSE_CONTEXT, TEMPLATE_PARSE_CONTEXT])
def test_direct_calendar_validator_keeps_rule_for_all_sources(parse_context):
    source, task, card = load_case()
    with pytest.raises(CompactDslValidationError, match="calendar eventCount"):
        validate_compact_dsl(
            source, task_spec=task, card_spec=card, parse_context=parse_context,
        )


def test_skip_flag_does_not_bypass_public_bitmap_conversion():
    source = '\n'.join([
        '["root","Column",{},["icon"]]',
        '["icon","Image",{"src":"resources/icon.jpg","fillColor":"#FF123456"}]',
    ])
    _, task, card = load_case()
    result = DesignCompactProcessor().process(source, DslProcessingContext(
        size="2x4", task_spec=task, card_spec=card, protocol_profile={"version": "v0.9"},
        skip_compact_dsl_validation=True, parse_context=TEMPLATE_PARSE_CONTEXT,
    ))
    assert result.errors
    assert any("must not set fillColor" in issue.message for issue in result.errors)
