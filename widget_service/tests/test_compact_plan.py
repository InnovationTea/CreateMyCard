"""Compact Info Plan 合同、标准化与 DSL 覆盖回归。"""

import json

import pytest

from services.compact_dsl_a2ui_converter import MODEL_COMPACT_INPUT_COMPONENT_TYPES
from services.compact_plan import (
    CompactPlanValidationError,
    build_compact_plan_tool,
    compact_plan_coverage_errors,
    compact_plan_coverage_warnings,
    compact_plan_data_paths,
    compact_plan_omitted_facts,
    compact_plan_optional_drop_candidate,
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


def plan_call_with_composition(*, content_height: int = 34) -> str:
    payload = json.loads(plan_call())
    for fact in payload["arguments"]["info_required"]:
        fact["priority"] = "must"
    payload["arguments"]["composition"] = {
        "layout": "S-title-content-action",
        "variant": 1,
        "regions": [
            {
                "id": "title",
                "path": [0],
                "referenceWidth": 126,
                "referenceHeight": 20,
                "gap": 0,
                "groups": [
                    {
                        "component": "SingleLineTitle",
                        "factIndexes": [],
                        "placements": [],
                        "referenceHeight": 20,
                    }
                ],
            },
            {
                "id": "content",
                "path": [1, 0],
                "referenceWidth": 126,
                "referenceHeight": 64,
                "gap": 0,
                "groups": [
                    {
                        "component": "EventCard",
                        "factIndexes": [0, 1],
                        "placements": ["items[0].title", "items[0].time"],
                        "referenceHeight": content_height,
                    }
                ],
            },
            {
                "id": "action",
                "path": [1, 1],
                "referenceWidth": 126,
                "referenceHeight": 36,
                "gap": 0,
                "groups": [
                    {
                        "component": "PillButton",
                        "factIndexes": [2],
                        "placements": ["onClick"],
                        "referenceHeight": 36,
                    }
                ],
            },
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


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
    assert "ProgressCircle" in fact_properties["componentHints"]["items"]["enum"]
    assert "Progress" not in fact_properties["componentHints"]["items"]["enum"]
    assert "Button" not in fact_properties["componentHints"]["items"]["enum"]
    assert "CardButton" not in fact_properties["componentHints"]["items"]["enum"]
    assert "S-title-content-action" in properties["layoutHints"]["items"]["enum"]
    assert properties["info_required"]["items"]["properties"]["priority"]["enum"] == [
        "must",
        "should",
    ]
    assert "priority" in properties["info_required"]["items"]["required"]
    assert "composition" not in properties
    assert tool["function"]["parameters"]["required"] == ["info_required"]


def test_plan_tool_requires_composition_only_with_runtime_context() -> None:
    tool = build_compact_plan_tool(task_spec(), include_composition=True)
    parameters = tool["function"]["parameters"]

    assert "composition" in parameters["properties"]
    assert parameters["required"] == ["info_required", "composition"]


def test_plan_parser_rejects_composition_when_runtime_context_is_disabled() -> None:
    with pytest.raises(CompactPlanValidationError, match="Unsupported Plan arguments"):
        parse_compact_plan_call(plan_call_with_composition(), task_spec())


def test_plan_parser_requires_valid_composition_when_runtime_context_is_enabled() -> None:
    result = parse_compact_plan_call(
        plan_call_with_composition(),
        task_spec(),
        require_composition=True,
    )

    assert result.plan["composition"]["layout"] == "S-title-content-action"
    assert all(
        region["remainingHeight"] >= 0
        for region in result.plan["composition"]["regions"]
    )


def test_plan_parser_rejects_negative_remaining_height_in_runtime_mode() -> None:
    with pytest.raises(CompactPlanValidationError, match="negative remainingHeight"):
        parse_compact_plan_call(
            plan_call_with_composition(content_height=100),
            task_spec(),
            require_composition=True,
        )


def test_plan_parser_requires_composition_in_runtime_mode() -> None:
    with pytest.raises(CompactPlanValidationError, match="composition is required"):
        parse_compact_plan_call(
            plan_call(),
            task_spec(),
            require_composition=True,
        )


@pytest.mark.parametrize(
    ("size", "expected", "actions"),
    [
        (
            "2x2",
            (
                "SingleLineTitle",
                "DoubleLineTitle",
                "Badge",
                "EmphasizedData",
                "EmphasisText",
                "SecondaryBody",
                "InfoBlock",
                "H_BarChart",
                "NumericRatioStack",
                "ProgressCircleSingle",
                "ProgressCircle",
                "TableText",
                "EventCard",
                "PillButton",
                "DataDisplay",
                "CircleButton",
            ),
            {"PillButton", "CircleButton"},
        ),
        (
            "2x4",
            (
                "SingleLineTitle",
                "DoubleLineTitle",
                "Badge",
                "EmphasizedData",
                "EmphasisText",
                "SecondaryBody",
                "InfoBlock",
                "H_BarChart",
                "NumericRatioStack",
                "ProgressCircleSingle",
                "ProgressCircle",
                "TableText",
                "EventCard",
                "PillButton",
                "ProgressLine2",
                "TextBlock",
                "CardButton",
                "TopTextBottomValue",
                "SummaryList",
            ),
            {"PillButton", "CardButton"},
        ),
    ],
)
def test_plan_component_hints_match_registered_compact_inputs_by_size(
    size: str,
    expected: tuple[str, ...],
    actions: set[str],
) -> None:
    spec = task_spec()
    spec["size"] = size
    tool = build_compact_plan_tool(spec)
    properties = tool["function"]["parameters"]["properties"]
    fact_properties = properties["info_required"]["items"]["properties"]
    candidates = fact_properties["componentHints"]["items"]["enum"]
    candidate_set = set(candidates)

    assert candidates == list(expected)
    assert candidate_set <= MODEL_COMPACT_INPUT_COMPONENT_TYPES
    assert "Text" not in candidate_set
    assert "Button" not in candidate_set
    assert "Image" not in candidate_set
    assert "Divider" not in candidate_set
    assert actions <= candidate_set


@pytest.mark.parametrize(
    ("size", "valid_action"),
    [("2x2", "CircleButton"), ("2x4", "CardButton")],
)
def test_plan_normalization_removes_button_for_each_size(
    size: str,
    valid_action: str,
) -> None:
    spec = task_spec()
    spec["size"] = size
    raw = json.dumps(
        {
            "name": "submit_card_plan",
            "arguments": {
                "info_required": [
                    {
                        "requirement": "打开日历",
                        "actionId": "event.open.calendar",
                        "componentHints": ["Button", valid_action],
                    }
                ]
            },
        },
        ensure_ascii=False,
    )

    result = parse_compact_plan_call(raw, spec)

    assert result.plan["info_required"][0]["componentHints"] == [valid_action]
    assert result.warnings == (
        "info_required[0].componentHints removed unsupported or duplicate values.",
    )


def test_plan_normalization_removes_target_incompatible_component_hints() -> None:
    raw = json.dumps(
        {
            "name": "submit_card_plan",
            "arguments": {
                "info_required": [
                    {
                        "requirement": "会议标题",
                        "dataId": "/data/calendar/events/0/title",
                        "componentHints": ["PillButton", "EventCard"],
                    },
                    {
                        "requirement": "打开日历",
                        "actionId": "event.open.calendar",
                        "componentHints": ["InfoBlock", "PillButton"],
                    },
                ]
            },
        },
        ensure_ascii=False,
    )

    result = parse_compact_plan_call(raw, task_spec())

    facts = result.plan["info_required"]
    assert facts[0]["componentHints"] == ["EventCard"]
    assert facts[1]["componentHints"] == ["PillButton"]
    assert result.warnings == (
        "info_required[0].componentHints removed unsupported, "
        "target-incompatible or duplicate values.",
        "info_required[1].componentHints removed unsupported, "
        "target-incompatible or duplicate values.",
    )


def test_plan_forces_action_priority_to_must() -> None:
    raw = json.dumps(
        {
            "name": "submit_card_plan",
            "arguments": {
                "info_required": [
                    {
                        "requirement": "打开日历",
                        "priority": "should",
                        "actionId": "event.open.calendar",
                        "componentHints": ["PillButton"],
                    }
                ]
            },
        },
        ensure_ascii=False,
    )

    result = parse_compact_plan_call(raw, task_spec())

    assert result.plan["info_required"][0]["priority"] == "must"
    assert result.warnings == (
        "info_required[0].priority was forced to must for an action.",
    )


def test_plan_normalization_makes_single_line_title_an_exclusive_title_hint() -> None:
    raw = json.dumps(
        {
            "name": "submit_card_plan",
            "arguments": {
                "info_required": [
                    {
                        "requirement": "会议标题",
                        "dataId": "/data/calendar/events/0/title",
                        "componentHints": ["Text", "SingleLineTitle", "EventCard"],
                    }
                ]
            },
        },
        ensure_ascii=False,
    )

    result = parse_compact_plan_call(raw, task_spec())

    assert result.plan["info_required"][0]["componentHints"] == ["SingleLineTitle"]
    assert result.warnings == (
        "info_required[0].componentHints removed alternatives because SingleLineTitle "
        "is the exclusive title component.",
    )


def test_plan_keeps_progress_hint_for_complete_percentage_text() -> None:
    spec = task_spec()
    spec["dataModelSchema"]["data"]["weather"] = {
        "rainProbability": {
            "type": "string",
            "description": "可直接显示的降雨概率百分比",
            "sampleValue": "20%",
        },
        "condition": {
            "type": "string",
            "description": "天气现象",
            "sampleValue": "多云",
        },
    }
    raw = json.dumps(
        {
            "name": "submit_card_plan",
            "arguments": {
                "info_required": [
                    {
                        "requirement": "降雨概率",
                        "dataId": "/data/weather/rainProbability",
                        "componentHints": ["ProgressCircleSingle"],
                    },
                    {
                        "requirement": "天气现象",
                        "dataId": "/data/weather/condition",
                        "componentHints": ["ProgressCircleSingle", "SecondaryBody"],
                    },
                ]
            },
        },
        ensure_ascii=False,
    )

    result = parse_compact_plan_call(raw, spec)

    facts = result.plan["info_required"]
    assert facts[0]["componentHints"] == ["ProgressCircleSingle"]
    assert facts[1]["componentHints"] == ["SecondaryBody"]
    assert result.warnings == (
        "info_required[1].componentHints removed unsupported, "
        "type-incompatible or duplicate values.",
    )


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


def test_optional_drop_candidate_prefers_should_only_component() -> None:
    spec = task_spec()
    plan = {
        "info_required": [
            {
                "requirement": "会议标题",
                "priority": "must",
                "dataId": "/data/calendar/events/0/title",
                "componentHints": ["SingleLineTitle"],
            },
            {
                "requirement": "会议开始时间",
                "priority": "should",
                "dataId": "/data/calendar/events/0/start",
                "componentHints": ["SecondaryBody"],
            },
            {
                "requirement": "打开日历",
                "priority": "must",
                "actionId": "event.open.calendar",
                "componentHints": ["PillButton"],
            },
        ]
    }
    source = "\n".join(
        [
            '["root","Column",{},["title","time","action"]]',
            '["title","SingleLineTitle",{"title":{"path":'
            '"/data/calendar/events/0/title"}}]',
            '["time","SecondaryBody",{"role":"metadata","items":'
            '[{"value":{"path":"/data/calendar/events/0/start"}}]}]',
            '["action","PillButton",{"label":"打开日历","onClick":'
            '[{"call":"clickToDeeplink","args":{"uri":"hww://calendar"}}]}]',
        ]
    )

    candidate = compact_plan_optional_drop_candidate(source, plan, spec)

    assert candidate is not None
    assert candidate.component_id == "time"
    assert candidate.fact_indexes == (1,)
    assert candidate.contains_must_facts is False

    without_time = source.replace(',"time"', "").replace(
        '["time","SecondaryBody",{"role":"metadata","items":'
        '[{"value":{"path":"/data/calendar/events/0/start"}}]}]\n',
        "",
    )
    errors = compact_plan_coverage_errors(without_time, plan, spec)
    assert len(errors) == 1
    assert "会议开始时间" in errors[0]
    assert compact_plan_coverage_errors(
        without_time,
        plan,
        spec,
        allowed_omitted_fact_indexes=(1,),
    ) == ()
    omitted = compact_plan_omitted_facts(without_time, plan, spec, (1,))
    assert [fact["requirement"] for fact in omitted] == ["会议开始时间"]


def test_optional_drop_candidate_prefers_the_component_with_fewer_facts() -> None:
    spec = task_spec()
    plan = {
        "info_required": [
            {
                "requirement": "会议标题",
                "priority": "should",
                "dataId": "/data/calendar/events/0/title",
            },
            {
                "requirement": "会议开始时间",
                "priority": "should",
                "dataId": "/data/calendar/events/0/start",
            },
        ]
    }
    source = "\n".join(
        [
            '["root","Column",{},["event","time"]]',
            '["event","EventCard",{"items":[{"title":{"path":'
            '"/data/calendar/events/0/title"},"time":{"path":'
            '"/data/calendar/events/0/start"}}]}]',
            '["time","SecondaryBody",{"role":"metadata","items":'
            '[{"value":{"path":"/data/calendar/events/0/start"}}]}]',
        ]
    )

    candidate = compact_plan_optional_drop_candidate(source, plan, spec)

    assert candidate is not None
    assert candidate.component_id == "time"
    assert candidate.fact_indexes == (1,)


def test_optional_drop_candidate_can_select_component_that_carries_must_fact() -> None:
    spec = task_spec()
    plan = {
        "info_required": [
            {
                "requirement": "会议标题",
                "priority": "must",
                "dataId": "/data/calendar/events/0/title",
            },
            {
                "requirement": "会议开始时间",
                "priority": "should",
                "dataId": "/data/calendar/events/0/start",
            },
        ]
    }
    source = (
        '["root","Column",{},["event"]]\n'
        '["event","EventCard",{"items":[{"title":{"path":'
        '"/data/calendar/events/0/title"},"time":{"path":'
        '"/data/calendar/events/0/start"}}]}]'
    )

    candidate = compact_plan_optional_drop_candidate(source, plan, spec)

    assert candidate is not None
    assert candidate.component_id == "event"
    assert candidate.fact_indexes == (0, 1)
    assert candidate.contains_must_facts is True

    without_event = '["root","Column",{},[]]'
    assert compact_plan_coverage_errors(
        without_event,
        plan,
        spec,
        allowed_omitted_fact_indexes=candidate.fact_indexes,
    ) == ()
    omitted = compact_plan_omitted_facts(
        without_event,
        plan,
        spec,
        candidate.fact_indexes,
    )
    assert [fact["requirement"] for fact in omitted] == ["会议标题", "会议开始时间"]


def test_optional_drop_never_allows_action_fact_to_be_omitted() -> None:
    spec = task_spec()
    plan = {
        "info_required": [
            {
                "requirement": "打开日历",
                "priority": "must",
                "actionId": "event.open.calendar",
            }
        ]
    }
    source = (
        '["root","Column",{},["action"]]\n'
        '["action","PillButton",{"label":"打开日历","onClick":'
        '[{"call":"clickToDeeplink","args":{"uri":"hww://calendar"}}]}]'
    )

    assert compact_plan_optional_drop_candidate(source, plan, spec) is None
    errors = compact_plan_coverage_errors(
        '["root","Column",{},[]]',
        plan,
        spec,
        allowed_omitted_fact_indexes=(0,),
    )
    assert len(errors) == 1
    assert "打开日历" in errors[0]
    assert compact_plan_omitted_facts(
        '["root","Column",{},[]]',
        plan,
        spec,
        (0,),
    ) == ()


def test_single_line_title_plan_fact_cannot_be_covered_by_text() -> None:
    spec = task_spec()
    plan = {
        "info_required": [
            {
                "requirement": "会议标题",
                "dataId": "/data/calendar/events/0/title",
                "componentHints": ["SingleLineTitle"],
            }
        ]
    }
    text_source = "\n".join(
        [
            '["root","Column",{},["title"]]',
            '["title","Text",{"content":{"path":"/data/calendar/events/0/title"}}]',
        ]
    )
    header_source = "\n".join(
        [
            '["root","Column",{},["title"]]',
            '["title","SingleLineTitle",{"title":{"path":'
            '"/data/calendar/events/0/title"},"fontColor":"#FF1F4799"}]',
        ]
    )

    assert compact_plan_coverage_errors(text_source, plan, spec) == (
        "Plan title fact must be visible in a SingleLineTitle.title: "
        "会议标题 (/data/calendar/events/0/title).",
    )
    assert compact_plan_coverage_errors(header_source, plan, spec) == ()


def test_static_title_plan_fact_keeps_hard_title_placement_validation() -> None:
    spec = task_spec()
    plan = {
        "info_required": [
            {
                "requirement": "卡片标题",
                "text": "设计评审",
                "componentHints": ["SingleLineTitle"],
            }
        ]
    }
    source = "\n".join(
        [
            '["root","Column",{},["title"]]',
            '["title","SecondaryBody",{"role":"body","items":'
            '[{"value":"设计评审"}],"fontSize":14}]',
        ]
    )

    assert compact_plan_coverage_errors(source, plan, spec) == (
        "Plan title fact must be visible in a SingleLineTitle.title: 卡片标题.",
    )
    assert compact_plan_coverage_warnings(source, plan, spec) == ()


def test_progress_circle_external_text_covers_numeric_plan_fact() -> None:
    spec = {
        "size": "2x2",
        "dataModelSchema": {
            "data": {
                "device": {
                    "battery": {
                        "type": "integer",
                        "description": "设备电量百分比0到100",
                    }
                }
            }
        },
        "eventCandidates": [],
    }
    plan = {
        "info_required": [
            {
                "requirement": "设备电量",
                "dataId": "/data/device/battery",
                "componentHints": ["ProgressCircle"],
            }
        ]
    }
    source = "\n".join(
        [
            '["root","Column",{},["battery"]]',
            '["battery","ProgressCircle",'
            '{"externalText":{"path":"/data/device/battery"},'
            '"icon":"resources/battery.svg",'
            '"accessibility":{"label":"设备电量百分比"},'
            '"width":52,"height":68,"fontColor":"#FF1F4799",'
            '"color":"#FF1F4799","backgroundColor":"#331F4799"}]',
        ]
    )

    assert compact_plan_coverage_errors(source, plan, spec) == ()


def test_processor_reports_missing_static_plan_text_as_warning() -> None:
    plan = {
        "info_required": [
            {
                "requirement": "卡片标题",
                "text": "静态卡片",
                "componentHints": ["SecondaryBody"],
            }
        ]
    }
    spec = task_spec()
    spec["appVersion"] = "12.0.0.1"
    context = DslProcessingContext(
        size="2x2",
        card_spec={},
        task_spec=spec,
        protocol_profile={},
        compact_plan=plan,
    )
    result = DesignCompactProcessor().process(
        '["root","Column",{},["title"]]\n'
        '["title","SecondaryBody",{"role":"metadata",'
        '"items":[{"value":"其他文字"}]}]',
        context,
    )

    assert result.standard_dsl
    assert result.errors == ()
    warnings = tuple(issue for issue in result.issues if issue.severity == "warning")
    assert len(warnings) == 1
    assert warnings[0].code == "COMPACT_PLAN_COVERAGE_WARNING"
    assert "卡片标题" in warnings[0].message


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
    warnings = compact_plan_coverage_warnings(source, plan, task_spec())

    assert errors == ()
    assert warnings == ("Plan static text is not fully visible in DSL: 卡片标题.",)


def test_shortened_static_plan_text_is_warning_only() -> None:
    plan = {
        "info_required": [
            {
                "requirement": "展示提醒文字“每天带孩子出去运动两次”",
                "text": "每天带孩子出去运动两次",
                "componentHints": ["SecondaryBody"],
            }
        ]
    }
    source = "\n".join(
        [
            '["root","Column",{},["reminder"]]',
            '["reminder","SecondaryBody",{"role":"body","items":'
            '[{"value":"每天带孩子运动","maxLines":1}],"fontSize":14}]',
        ]
    )

    assert compact_plan_coverage_errors(source, plan, task_spec()) == ()
    assert compact_plan_coverage_warnings(source, plan, task_spec()) == (
        "Plan static text is not fully visible in DSL: "
        "展示提醒文字“每天带孩子出去运动两次”.",
    )
