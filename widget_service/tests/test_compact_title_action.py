import json

import pytest

from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    convert_compact_dsl_to_a2ui,
)
from services.compact_plan import compact_plan_context


def _task() -> dict:
    event = {
        "id": "storage",
        "description": "打开存储设置",
        "call": "clickToIntent",
        "args": {
            "intentName": "OpenSettings",
            "params": {"page": "storage"},
        },
    }
    return {
        "size": "2x2",
        "appVersion": "99.0",
        "userQuery": "打开存储设置",
        "dataModelSchema": {"data": {}},
        "eventCandidates": [event],
        "assetCandidates": [],
    }


def _plan(with_display_fact: bool = False, title_marker: str | None = None) -> dict:
    facts = [{"requirement": "打开存储设置", "actionId": "storage", "priority": "must"}]
    if title_marker is not None:
        title_fact = {"requirement": "存储空间标题", "text": "存储空间", "priority": "must"}
        title_fact[title_marker] = "title" if title_marker == "displayRole" else ["SingleLineTitle"]
        facts.insert(0, title_fact)
    if with_display_fact:
        facts.append({"requirement": "存储状态", "text": "剩余空间", "priority": "must"})
    return {"info_required": facts, "layoutHints": ["S-title-content-action"]}


def _source(variant: str = "title-action") -> str:
    rows = [
        [
            "root",
            "Layout",
            {"layout": "S-title-content-action", "variant": variant},
            ["title", "action"],
        ],
        ["title", "SingleLineTitle", {"title": "存储空间"}],
        [
            "action",
            "PillButton",
            {
                "label": "打开设置",
                "onClick": [{
                    "call": "clickToIntent",
                    "args": {"intentName": "OpenSettings", "params": {"page": "storage"}},
                }],
            },
        ],
    ]
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def test_title_action_validates_and_converts_without_display_fact() -> None:
    source = _source()
    validate_compact_dsl(
        source,
        task_spec=_task(),
        card_spec={"suggestSize": "2x2"},
        compact_plan=_plan(),
    )
    converted = convert_compact_dsl_to_a2ui(source, size="2x2")
    assert '"component":"Button"' in converted


def test_title_action_rejects_plan_with_display_fact() -> None:
    with pytest.raises(CompactDslValidationError, match="title-action requires"):
        validate_compact_dsl(
            _source(),
            task_spec=_task(),
            card_spec={"suggestSize": "2x2"},
            compact_plan=_plan(with_display_fact=True),
        )


@pytest.mark.parametrize("title_marker", ["displayRole", "componentHints"])
def test_title_action_accepts_one_identified_title_fact(title_marker: str) -> None:
    validate_compact_dsl(
        _source(),
        task_spec=_task(),
        card_spec={"suggestSize": "2x2"},
        compact_plan=_plan(title_marker=title_marker),
    )


def test_title_action_requires_explicit_variant() -> None:
    with pytest.raises(CompactDslConversionError):
        convert_compact_dsl_to_a2ui(_source("standard"), size="2x2")


def test_title_action_plan_context_requires_the_explicit_variant() -> None:
    context = compact_plan_context(_plan(), execution_selected=True)
    assert "title-action 变体" in context
    assert "不生成内容槽" in context


def test_title_action_plan_context_accepts_an_identified_title_fact() -> None:
    context = compact_plan_context(_plan(title_marker="displayRole"), execution_selected=True)
    assert "title-action 变体" in context
