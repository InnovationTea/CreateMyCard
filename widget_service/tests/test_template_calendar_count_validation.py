"""日程数量仅按可信来源放行，不改变模板排版及其它语义检查。"""

import json
from pathlib import Path

import pytest

from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.compact_dsl_parse_context import MODEL_PARSE_CONTEXT, TEMPLATE_PARSE_CONTEXT

_CASES = Path(__file__).parent / "compact_dsl_validate/_collect_semantic_text_errors"


def load_case(case_id):
    folder = _CASES / case_id
    source = (folder / "sample_compact.dsl").read_text(encoding="utf-8")
    task = json.loads((folder / "sample_task_spec.json").read_text(encoding="utf-8"))
    card = json.loads((folder / "sample_card_spec.json").read_text(encoding="utf-8"))
    task["size"] = "2x2"
    card["suggestSize"] = "2x2"
    return source, task, card


@pytest.mark.parametrize("context", [None, MODEL_PARSE_CONTEXT, TEMPLATE_PARSE_CONTEXT])
@pytest.mark.parametrize("template_marker", [False, True])
def test_calendar_count_exception_requires_trusted_context(context, template_marker):
    source, task, card = load_case("02")
    if template_marker:
        source = source.replace('"value"', '"template_root"')
    kwargs = {} if context is None else {"parse_context": context}
    if context is TEMPLATE_PARSE_CONTEXT:
        validate_compact_dsl(source, task_spec=task, card_spec=card, **kwargs)
    else:
        with pytest.raises(CompactDslValidationError, match="calendar eventCount"):
            validate_compact_dsl(source, task_spec=task, card_spec=card, **kwargs)


@pytest.mark.parametrize("case_id", ["01", "03", "04"])
def test_template_keeps_other_semantic_errors(case_id):
    source, task, card = load_case(case_id)
    expected = json.loads((_CASES / case_id / "expected.json").read_text(encoding="utf-8"))
    with pytest.raises(CompactDslValidationError) as error:
        validate_compact_dsl(
            source, task_spec=task, card_spec=card, parse_context=TEMPLATE_PARSE_CONTEXT,
        )
    messages = expected.get("expectedErrors")
    assert isinstance(messages, list) and messages
    for message in messages:
        assert message in str(error.value)


def test_template_calendar_count_still_requires_declared_binding():
    source, task, card = load_case("02")
    task["dataModelSchema"] = {"data": {}}
    with pytest.raises(CompactDslValidationError) as error:
        validate_compact_dsl(
            source, task_spec=task, card_spec=card, parse_context=TEMPLATE_PARSE_CONTEXT,
        )
    assert "eventCount" in str(error.value)
    assert "calendar eventCount must not" not in str(error.value)


@pytest.mark.parametrize("context", [MODEL_PARSE_CONTEXT, TEMPLATE_PARSE_CONTEXT])
def test_complete_calendar_count_text_remains_valid(context):
    source, task, card = load_case("02")
    source = source.replace(
        '{"path":"/data/calendar/eventCount"}',
        json.dumps(
            "{{ '未来7天 ' + ${/data/calendar/eventCount} + '项安排' }}", ensure_ascii=False,
        ),
    )
    validate_compact_dsl(source, task_spec=task, card_spec=card, parse_context=context)
