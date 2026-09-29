"""Compact Info Plan 合同、标准化与 DSL 覆盖回归。"""

import json

import pytest

from services.compact_plan import (
    CompactPlanValidationError,
    build_compact_plan_tool,
    compact_plan_coverage_errors,
    compact_plan_data_paths,
    parse_compact_plan_call,
)
from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext


def task_spec() -> dict:
    return {
        "userQuery": "制作会议卡片，显示设计评审、开始时间，并提供打开日历按钮",
        "size": "2x2",
        "dataModelSchema": {
            "data": {
                "calendar": {
                    "events": [
                        {
                            "title": {
                                "type": "string",
                                "description": "会议标题",
                                "sampleValue": "设计评审",
                            },
                            "start": {
                                "type": "string",
                                "description": "开始时间",
                                "sampleValue": "10:00",
                            },
                        }
                    ]
                }
            }
        },
        "eventCandidates": [
            {
                "id": "event.open.calendar",
                "description": "打开日历",
                "call": "clickToDeeplink",
                "args": {"uri": "hww://calendar"},
            }
        ],
    }


def plan_call() -> str:
    return json.dumps(
        {
            "name": "submit_card_plan",
            "arguments": {
                "info_required": [
                    {
                        "requirement": "会议标题",
                        "dataId": "/data/calendar/events/0/title",
                        "componentHints": ["EventCard"],
                    },
                    {
                        "requirement": "会议开始时间",
                        "dataId": "/data/calendar/events/0/start",
                        "componentHints": ["EventCard", "Unknown", "EventCard"],
                    },
                    {
                        "requirement": "打开日历",
                        "actionId": "event.open.calendar",
                        "componentHints": ["PillButton"],
                    },
                ],
                "layoutHints": ["S-title-content-action"],
            },
        },
        ensure_ascii=False,
    )


def test_plan_tool_uses_task_paths_actions_and_size_contracts() -> None:
    spec = task_spec()
    assert compact_plan_data_paths(spec) == (
        "/data/calendar/events/0/title",
        "/data/calendar/events/0/start",
    )
    tool = build_compact_plan_tool(spec)
    properties = tool["function"]["parameters"]["properties"]
    fact_properties = properties["info_required"]["items"]["properties"]
    assert fact_properties["dataId"]["enum"] == list(compact_plan_data_paths(spec))
    assert fact_properties["actionId"]["enum"] == ["event.open.calendar"]
    assert "EventCard" in fact_properties["componentHints"]["items"]["enum"]
    assert "CardButton" not in fact_properties["componentHints"]["items"]["enum"]
    assert "S-title-content-action" in properties["layoutHints"]["items"]["enum"]


def test_plan_call_is_normalized_without_freezing_components() -> None:
    result = parse_compact_plan_call(plan_call(), task_spec())
    facts = result.plan["info_required"]
    assert len(facts) == 3
    assert facts[1]["componentHints"] == ["EventCard"]
    assert result.plan["layoutHints"] == ["S-title-content-action"]
    assert result.warnings == (
        "info_required[1].componentHints removed unsupported or duplicate values.",
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("dataId", "/data/calendar/events/0/missing", "not present in TaskSpec"),
        ("actionId", "event.missing", "not present in TaskSpec"),
        ("text", "模型自行增加的文案", "must be copied from userQuery"),
    ],
)
def test_plan_rejects_invented_targets(field: str, value: str, message: str) -> None:
    raw = json.dumps(
        {
            "name": "submit_card_plan",
            "arguments": {
                "info_required": [
                    {"requirement": "非法事实", field: value},
                ]
            },
        },
        ensure_ascii=False,
    )
    with pytest.raises(CompactPlanValidationError, match=message):
        parse_compact_plan_call(raw, task_spec())


def test_compact_dsl_must_cover_plan_data_and_action() -> None:
    plan = parse_compact_plan_call(plan_call(), task_spec()).plan
    complete = "\n".join(
        [
            '["root","Column",{},["title","start","button"]]',
            '["title","Text",{"content":{"path":"/data/calendar/events/0/title"}}]',
            '["start","Text",{"content":"{{ ${/data/calendar/events/0/start} }}"}]',
            '["button","PillButton",{"label":"打开日历","onClick":'
            '[{"call":"clickToDeeplink","args":{"uri":"hww://calendar"}}]}]',
            '["/data/calendar/events/0/title","设计评审"]',
            '["/data/calendar/events/0/start","10:00"]',
        ]
    )
    assert compact_plan_coverage_errors(complete, plan, task_spec()) == ()

    incomplete = complete.replace(
        '{"path":"/data/calendar/events/0/title"}',
        '"会议"',
    ).replace(
        '[{"call":"clickToDeeplink","args":{"uri":"hww://calendar"}}]',
        "[]",
    )
    errors = compact_plan_coverage_errors(incomplete, plan, task_spec())
    assert any("会议标题" in item for item in errors)
    assert any("打开日历" in item for item in errors)


def test_processor_reports_missing_plan_fact_with_dedicated_code() -> None:
    plan = {
        "info_required": [
            {
                "requirement": "卡片标题",
                "text": "静态卡片",
                "componentHints": ["Text"],
            }
        ]
    }
    context = DslProcessingContext(
        size="2x2",
        card_spec={},
        task_spec=task_spec(),
        protocol_profile={},
        compact_plan=plan,
    )
    result = DesignCompactProcessor().process(
        '["root","Column",{},["title"]]\n'
        '["title","Text",{"content":"其他文字"}]',
        context,
    )

    assert result.standard_dsl == ""
    assert len(result.errors) == 1
    assert result.errors[0].code == "COMPACT_PLAN_COVERAGE_FAILED"
    assert "卡片标题" in result.errors[0].message


def test_static_fact_is_not_satisfied_by_visual_style_props() -> None:
    plan = {
        "info_required": [
            {
                "requirement": "卡片标题",
                "text": "center",
            }
        ]
    }
    source = "\n".join(
        [
            '["root","Column",{"justifyContent":"center"},["title"]]',
            '["title","Text",{"content":"其他文字"}]',
        ]
    )

    errors = compact_plan_coverage_errors(source, plan, task_spec())

    assert errors == ("Plan static text is missing from visible DSL: 卡片标题.",)
