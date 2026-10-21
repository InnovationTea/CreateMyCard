"""Compact Info Plan 合同、标准化与 DSL 覆盖回归。"""

import json

import pytest

from services.compact_dsl_a2ui_converter import MODEL_COMPACT_INPUT_COMPONENT_TYPES
from services.compact_plan import (
    CompactPlanValidationError,
    _secondary_body_composition_errors,
    build_compact_plan_tool,
    compact_plan_asset_ids,
    compact_plan_coverage_errors,
    compact_plan_coverage_warnings,
    compact_plan_data_paths,
    compact_plan_omitted_facts,
    compact_plan_optional_drop_candidate,
    evaluate_compact_plan_coverage,
    parse_compact_plan_call,
)
from services.compact_repair_strategy import CompactRepairStrategyTracker
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


def dual_action_task_spec() -> dict:
    return {
        "userQuery": "显示剩余电量，并打开省电模式和导航回家",
        "size": "2x2",
        "dataModelSchema": {
            "data": {
                "phoneBattery": {
                    "soc": {
                        "type": "integer",
                        "description": "剩余电量",
                        "sampleValue": 68,
                    },
                    "status": {
                        "type": "string",
                        "description": "充电状态",
                        "sampleValue": "未充电",
                    },
                }
            }
        },
        "eventCandidates": [
            {
                "id": "event.setPowerSavingMode",
                "description": "打开省电模式",
                "call": "clickToIntent",
                "args": {
                    "intentName": "SetSettingSwitch",
                    "params": {
                        "appBundleName": "com.huawei.hmos.settings",
                        "itemName": "battery_saving_mode",
                        "switchFlag": 0,
                    },
                },
            },
            {
                "id": "event.startNavigate",
                "description": "导航回家",
                "call": "startNavigate",
                "args": {"destination": "home"},
            },
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


def freshness_task_spec(user_query: str = "显示天气预警") -> dict:
    return {
        "userQuery": user_query,
        "size": "2x2",
        "dataModelSchema": {
            "data": {
                "weather": {
                    "current": {
                        "alertLevel": {
                            "type": "string",
                            "description": "天气预警等级",
                            "sampleValue": "大风蓝色预警",
                        },
                        "condition": {
                            "type": "string",
                            "description": "当前天气状态",
                            "sampleValue": "多云",
                        },
                    },
                    "updatedAt": {
                        "type": "string",
                        "description": "数据更新时间",
                        "sampleValue": "2026-08-06 09:00",
                    },
                }
            }
        },
        "eventCandidates": [],
    }


def freshness_plan_call(
    *,
    include_condition: bool = False,
    freshness_component: str = "EmphasisText",
    freshness_priority: str = "should",
    composition_groups: list[dict] | None = None,
) -> str:
    facts = [
        {
            "requirement": "天气预警等级",
            "priority": "must",
            "dataId": "/data/weather/current/alertLevel",
            "componentHints": ["EmphasisText"],
        }
    ]
    if include_condition:
        facts.append(
            {
                "requirement": "当前天气状态",
                "priority": "should",
                "dataId": "/data/weather/current/condition",
                "componentHints": ["EmphasisText"],
            }
        )
    facts.append(
        {
            "requirement": "数据更新时间",
            "priority": freshness_priority,
            "dataId": "/data/weather/updatedAt",
            "componentHints": [freshness_component],
        }
    )
    arguments: dict = {
        "info_required": facts,
        "layoutHints": ["S-title-content"],
    }
    if composition_groups is not None:
        arguments["composition"] = {
            "layout": "S-title-content",
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
                    "path": [1],
                    "referenceWidth": 126,
                    "referenceHeight": 108,
                    "gap": 2,
                    "groups": composition_groups,
                },
            ],
        }
    return json.dumps(
        {"name": "submit_card_plan", "arguments": arguments},
        ensure_ascii=False,
    )


def test_unrequested_freshness_metadata_is_rejected_for_non_sparse_card() -> None:
    with pytest.raises(
        CompactPlanValidationError,
        match="Freshness metadata is not a normal display fact",
    ):
        parse_compact_plan_call(
            freshness_plan_call(include_condition=True),
            freshness_task_spec(),
        )


def test_sparse_card_accepts_freshness_as_optional_emphasis_support() -> None:
    result = parse_compact_plan_call(
        freshness_plan_call(),
        freshness_task_spec(),
    )

    facts = result.plan.get("info_required")
    assert isinstance(facts, list)
    assert facts[1].get("priority") == "should"
    assert facts[1].get("componentHints") == ["EmphasisText"]


def test_sparse_card_rejects_standalone_secondary_body_freshness() -> None:
    with pytest.raises(
        CompactPlanValidationError,
        match="must be grouped into the single short text core",
    ):
        parse_compact_plan_call(
            freshness_plan_call(freshness_component="SecondaryBody"),
            freshness_task_spec(),
        )


def test_sparse_card_rejects_required_freshness_filler() -> None:
    with pytest.raises(
        CompactPlanValidationError,
        match="must use priority should",
    ):
        parse_compact_plan_call(
            freshness_plan_call(freshness_priority="must"),
            freshness_task_spec(),
        )


def test_explicit_freshness_request_allows_rich_card() -> None:
    result = parse_compact_plan_call(
        freshness_plan_call(
            include_condition=True,
            freshness_component="SecondaryBody",
            freshness_priority="must",
        ),
        freshness_task_spec("显示天气预警、当前天气和更新时间"),
    )

    facts = result.plan.get("info_required")
    assert isinstance(facts, list)
    assert len(facts) == 3


def test_sparse_card_composition_groups_freshness_with_core() -> None:
    result = parse_compact_plan_call(
        freshness_plan_call(
            composition_groups=[
                {
                    "component": "EmphasisText",
                    "factIndexes": [0, 1],
                    "placements": ["mainText", "secondaryText"],
                    "referenceHeight": 42,
                }
            ]
        ),
        freshness_task_spec(),
        require_composition=True,
    )

    assert result.plan.get("composition") is not None


def test_composition_rejects_duplicate_fact_placements() -> None:
    with pytest.raises(
        CompactPlanValidationError,
        match="duplicates an info_required data fact across visible placements",
    ):
        parse_compact_plan_call(
            freshness_plan_call(
                composition_groups=[
                    {
                        "component": "EmphasisText",
                        "factIndexes": [0, 0, 1],
                        "placements": [
                            "mainText",
                            "secondaryText",
                            "supportingText",
                        ],
                        "referenceHeight": 58,
                    }
                ]
            ),
            freshness_task_spec(),
            require_composition=True,
        )


def test_sparse_card_composition_rejects_separate_freshness_group() -> None:
    with pytest.raises(
        CompactPlanValidationError,
        match="must share one EmphasisText group",
    ):
        parse_compact_plan_call(
            freshness_plan_call(
                composition_groups=[
                    {
                        "component": "EmphasisText",
                        "factIndexes": [0],
                        "placements": ["mainText"],
                        "referenceHeight": 24,
                    },
                    {
                        "component": "EmphasisText",
                        "factIndexes": [1],
                        "placements": ["secondaryText"],
                        "referenceHeight": 24,
                    },
                ]
            ),
            freshness_task_spec(),
            require_composition=True,
        )


def test_anchor_hint_rejects_title_plus_single_body_fact() -> None:
    payload = json.loads(plan_call())
    payload["arguments"]["info_required"][0]["componentHints"] = ["SingleLineTitle"]
    payload["arguments"]["info_required"][1]["componentHints"] = ["EmphasisText"]
    payload["arguments"]["info_required"][2]["componentHints"] = [
        "CircleButton",
        "PillButton",
    ]
    payload["arguments"]["layoutHints"] = [
        "S-title-anchor",
        "S-title-content-action",
    ]

    with pytest.raises(
        CompactPlanValidationError,
        match="at least one independent support fact",
    ):
        parse_compact_plan_call(
            json.dumps(payload, ensure_ascii=False),
            task_spec(),
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


def test_plan_composition_rejects_secondary_body_when_card_has_no_core() -> None:
    payload = json.loads(plan_call_with_composition())
    arguments = payload.get("arguments")
    assert isinstance(arguments, dict)
    composition = arguments.get("composition")
    assert isinstance(composition, dict)
    regions = composition.get("regions")
    assert isinstance(regions, list)
    content = regions[1]
    assert isinstance(content, dict)
    content["groups"] = [
        {
            "component": "SecondaryBody",
            "factIndexes": [0, 1],
            "placements": ["items[0].value", "items[1].value"],
            "referenceHeight": 38,
        }
    ]

    with pytest.raises(
        CompactPlanValidationError,
        match="SecondaryBody without a core information component",
    ):
        parse_compact_plan_call(
            json.dumps(payload, ensure_ascii=False),
            task_spec(),
            require_composition=True,
        )


def test_plan_composition_accepts_secondary_body_with_core_group() -> None:
    payload = json.loads(plan_call_with_composition())
    arguments = payload.get("arguments")
    assert isinstance(arguments, dict)
    composition = arguments.get("composition")
    assert isinstance(composition, dict)
    regions = composition.get("regions")
    assert isinstance(regions, list)
    content = regions[1]
    assert isinstance(content, dict)
    content["gap"] = 2
    content["groups"] = [
        {
            "component": "EmphasisText",
            "factIndexes": [0],
            "placements": ["mainText"],
            "referenceHeight": 24,
        },
        {
            "component": "SecondaryBody",
            "factIndexes": [1],
            "placements": ["items[0].value"],
            "referenceHeight": 18,
        },
    ]

    result = parse_compact_plan_call(
        json.dumps(payload, ensure_ascii=False),
        task_spec(),
        require_composition=True,
    )

    normalized_composition = result.plan.get("composition")
    assert isinstance(normalized_composition, dict)
    normalized_regions = normalized_composition.get("regions")
    assert isinstance(normalized_regions, list)
    normalized_content = normalized_regions[1]
    assert isinstance(normalized_content, dict)
    groups = normalized_content.get("groups")
    assert isinstance(groups, list)
    secondary = groups[1]
    assert isinstance(secondary, dict)
    assert secondary.get("component") == "SecondaryBody"


def test_plan_composition_accepts_secondary_body_with_core_in_other_region() -> None:
    composition = {
        "regions": [
            {
                "id": "primary",
                "groups": [{"component": "EmphasisText"}],
            },
            {
                "id": "support",
                "groups": [{"component": "SecondaryBody"}],
            },
        ]
    }

    assert _secondary_body_composition_errors(composition) == []


def asset_task_spec() -> dict:
    spec = task_spec()
    spec["assetCandidates"] = [
        {
            "id": "asset.calendar_fill",
            "src": "resources/base/media/calendar_fill.svg",
            "description": "打开日历的日历图标",
        },
        {
            "id": "asset.icon_meeting",
            "src": "resources/base/media/icon_meeting.svg",
            "description": "会议主题图标",
        },
    ]
    return spec


def asset_plan_call() -> str:
    payload = json.loads(plan_call())
    payload["arguments"]["assetAssignments"] = {
        "actions": [
            {
                "actionId": "event.open.calendar",
                "assetId": "asset.calendar_fill",
            }
        ],
        "title": {"assetId": "asset.icon_meeting"},
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


@pytest.mark.parametrize(("size", "max_must_facts"), [("2x2", 6), ("2x4", 10)])
def test_plan_tool_explains_must_fact_guidance_by_card_size(
    size: str,
    max_must_facts: int,
) -> None:
    spec = task_spec()
    spec["size"] = size

    tool = build_compact_plan_tool(spec)
    priority = tool["function"]["parameters"]["properties"]["info_required"]["items"]
    priority = priority["properties"]["priority"]
    assert f"最多可提交 {max_must_facts} 条 must 信息" in priority["description"]


def _must_fact_limit_payload(fact_count: int, *, size: str) -> tuple[dict, dict]:
    schema_fields = {}
    facts = []
    for index in range(fact_count):
        field_name = f"metric{index}"
        schema_fields[field_name] = {
            "type": "string",
            "description": f"指标 {index}",
            "sampleValue": f"值 {index}",
        }
        facts.append(
            {
                "requirement": f"展示指标 {index}",
                "priority": "must",
                "dataId": f"/data/metrics/{field_name}",
                "componentHints": ["SecondaryBody"],
            }
        )
    spec = {
        "userQuery": "展示全部指标",
        "size": size,
        "dataModelSchema": {"data": {"metrics": schema_fields}},
        "eventCandidates": [],
    }
    payload = {
        "name": "submit_card_plan",
        "arguments": {"info_required": facts},
    }
    return spec, payload


@pytest.mark.parametrize(("size", "fact_count"), [("2x2", 7), ("2x4", 11)])
def test_plan_must_fact_limit_is_guidance_only(size: str, fact_count: int) -> None:
    spec, payload = _must_fact_limit_payload(fact_count, size=size)

    result = parse_compact_plan_call(json.dumps(payload), spec)

    assert len(result.plan["info_required"]) == fact_count


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_plan_tool_explains_registered_layout_names_without_new_fields(size: str) -> None:
    spec = task_spec()
    spec["size"] = size
    tool = build_compact_plan_tool(spec)
    function = tool.get("function")
    assert isinstance(function, dict)
    description = function.get("description")
    assert isinstance(description, str)
    assert "不得自行缩写、拼接或增删后缀" in description
    assert "全部必要事实与动作都有合法落点" in description
    assert ("children 为 [title, hero, support]" in description) == (size == "2x4")
    if size == "2x4":
        assert "Region 的 title-hero-support" in description
        assert "Group 的 hero-support 只有 [hero, support]" in description
        assert "第四项 PillButton" in description
    parameters = function.get("parameters")
    assert isinstance(parameters, dict)
    properties = parameters.get("properties")
    assert isinstance(properties, dict)
    assert set(properties) == {"info_required", "layoutHints"}
    layout_hints = properties.get("layoutHints")
    assert isinstance(layout_hints, dict)
    assert "不填写 Region/Group 变体，不使用简称" in layout_hints.get("description", "")


def test_dual_action_plan_tool_only_offers_the_unique_layout() -> None:
    spec = dual_action_task_spec()
    spec["assetCandidates"] = [
        {"id": "asset.power", "src": "resources/power.svg"},
        {"id": "asset.home", "src": "resources/home.svg"},
        {"id": "asset.location", "src": "resources/location.svg"},
    ]
    tool = build_compact_plan_tool(
        spec,
        include_composition=True,
        layout_scope="S-content-dual-action",
    )
    properties = tool["function"]["parameters"]["properties"]
    layout_hints = properties["layoutHints"]

    assert layout_hints["items"]["enum"] == ["S-content-dual-action"]
    assert layout_hints["maxItems"] == 1
    assert properties["composition"]["properties"]["layout"]["enum"] == [
        "S-content-dual-action"
    ]
    title_assignment = properties["assetAssignments"]["properties"]["title"]
    assert title_assignment["properties"]["assetId"] == {
        "type": "null",
        "enum": [None],
        "description": "固定双动作布局没有标题槽，必须为 null。",
    }


def test_dual_action_plan_preserves_content_hints_and_normalizes_buttons() -> None:
    payload = {
        "name": "submit_card_plan",
        "arguments": {
            "info_required": [
                {
                    "requirement": "剩余电量",
                    "priority": "must",
                    "dataId": "/data/phoneBattery/soc",
                    "componentHints": ["ProgressCircleSingle", "EmphasizedData"],
                },
                {
                    "requirement": "充电状态",
                    "priority": "should",
                    "dataId": "/data/phoneBattery/status",
                    "componentHints": ["SecondaryBody", "TableText"],
                },
                {
                    "requirement": "打开省电模式",
                    "priority": "must",
                    "actionId": "event.setPowerSavingMode",
                    "componentHints": ["CircleButton"],
                },
                {
                    "requirement": "导航回家",
                    "priority": "must",
                    "actionId": "event.startNavigate",
                    "componentHints": ["PillButton"],
                },
            ],
            "layoutHints": ["S-title-content-action", "S-content-dual-action"],
        },
    }

    result = parse_compact_plan_call(
        json.dumps(payload, ensure_ascii=False),
        dual_action_task_spec(),
    )

    assert result.plan.get("layoutHints") == ["S-content-dual-action"]
    facts = result.plan.get("info_required")
    assert isinstance(facts, list)
    assert facts[0].get("componentHints") == ["ProgressCircleSingle", "EmphasizedData"]
    assert facts[1].get("componentHints") == ["SecondaryBody", "TableText"]
    assert facts[2].get("componentHints") == ["PillButton"]
    assert facts[3].get("componentHints") == ["PillButton"]


def test_dual_action_plan_discards_title_asset_without_a_title_slot() -> None:
    spec = dual_action_task_spec()
    spec["assetCandidates"] = [
        {"id": "asset.power", "src": "resources/power.svg"},
        {"id": "asset.home", "src": "resources/home.svg"},
        {"id": "asset.location", "src": "resources/location.svg"},
    ]
    payload = {
        "name": "submit_card_plan",
        "arguments": {
            "info_required": [
                {
                    "requirement": "剩余电量",
                    "priority": "must",
                    "dataId": "/data/phoneBattery/soc",
                    "componentHints": ["EmphasisText"],
                },
                {
                    "requirement": "打开省电模式",
                    "priority": "must",
                    "actionId": "event.setPowerSavingMode",
                    "componentHints": ["PillButton"],
                },
                {
                    "requirement": "导航回家",
                    "priority": "must",
                    "actionId": "event.startNavigate",
                    "componentHints": ["PillButton"],
                },
            ],
            "layoutHints": ["S-content-dual-action"],
            "assetAssignments": {
                "actions": [
                    {
                        "actionId": "event.setPowerSavingMode",
                        "assetId": "asset.power",
                    },
                    {
                        "actionId": "event.startNavigate",
                        "assetId": "asset.home",
                    },
                ],
                "title": {"assetId": "asset.location"},
            },
        },
    }

    result = parse_compact_plan_call(json.dumps(payload), spec)

    assert result.plan["assetAssignments"]["title"] == {
        "assetId": None,
        "reason": "S-content-dual-action has no title slot.",
    }


def test_action_coverage_accepts_equivalent_switch_flag() -> None:
    spec = dual_action_task_spec()
    plan = {
        "info_required": [
            {
                "requirement": "打开省电模式",
                "priority": "must",
                "actionId": "event.setPowerSavingMode",
                "componentHints": ["PillButton"],
            }
        ]
    }
    source = "\n".join(
        [
            '["root","Column",{},["power"]]',
            '["power","PillButton",{"label":"打开省电模式","onClick":'
            '[{"call":"clickToIntent","args":{"intentName":"SetSettingSwitch",'
            '"params":{"appBundleName":"com.huawei.hmos.settings",'
            '"itemName":"battery_saving_mode","switchFlag":1}}}]}]',
        ]
    )

    errors = compact_plan_coverage_errors(source, plan, spec)

    assert not errors


def test_plan_tool_requires_explicit_asset_assignments_for_candidates() -> None:
    spec = asset_task_spec()
    tool = build_compact_plan_tool(spec)
    parameters = tool["function"]["parameters"]
    assignments = parameters["properties"]["assetAssignments"]

    assert compact_plan_asset_ids(spec) == (
        "asset.calendar_fill",
        "asset.icon_meeting",
    )
    assert parameters["required"] == ["info_required", "assetAssignments"]
    assert assignments["required"] == ["actions", "title"]


def test_plan_parser_preserves_button_first_asset_assignments() -> None:
    result = parse_compact_plan_call(asset_plan_call(), asset_task_spec())

    assert result.plan["assetAssignments"] == {
        "actions": [
            {
                "actionId": "event.open.calendar",
                "assetId": "asset.calendar_fill",
            }
        ],
        "title": {"assetId": "asset.icon_meeting"},
    }


def test_plan_parser_rejects_missing_asset_assignments() -> None:
    with pytest.raises(CompactPlanValidationError, match="assetAssignments is required"):
        parse_compact_plan_call(plan_call(), asset_task_spec())


def test_plan_parser_rejects_asset_reuse_between_button_and_title() -> None:
    payload = json.loads(asset_plan_call())
    payload["arguments"]["assetAssignments"]["title"] = {
        "assetId": "asset.calendar_fill"
    }

    with pytest.raises(CompactPlanValidationError, match="reuses an already assigned asset"):
        parse_compact_plan_call(json.dumps(payload), asset_task_spec())


def test_plan_parser_requires_reason_for_unassigned_icon() -> None:
    payload = json.loads(asset_plan_call())
    payload["arguments"]["assetAssignments"]["title"] = {"assetId": None}

    with pytest.raises(CompactPlanValidationError, match="reason is required"):
        parse_compact_plan_call(json.dumps(payload), asset_task_spec())


def test_plan_parser_accepts_card_button_without_an_assigned_action_icon() -> None:
    spec = asset_task_spec()
    spec["size"] = "2x4"
    payload = json.loads(asset_plan_call())
    action_fact = payload["arguments"]["info_required"][2]
    action_fact["componentHints"] = ["CardButton"]
    payload["arguments"]["assetAssignments"]["actions"] = [
        {
            "actionId": "event.open.calendar",
            "assetId": None,
            "reason": "没有语义匹配的候选素材",
        }
    ]

    result = parse_compact_plan_call(json.dumps(payload), spec)

    action_fact = result.plan["info_required"][2]
    assert action_fact["componentHints"] == ["CardButton"]
    assert result.plan["assetAssignments"]["actions"][0]["assetId"] is None


def test_plan_parser_accepts_pill_button_when_action_icon_is_unassigned() -> None:
    spec = asset_task_spec()
    spec["size"] = "2x4"
    payload = json.loads(asset_plan_call())
    payload["arguments"]["assetAssignments"]["actions"] = [
        {
            "actionId": "event.open.calendar",
            "assetId": None,
            "reason": "没有语义匹配的候选素材",
        }
    ]

    result = parse_compact_plan_call(json.dumps(payload), spec)

    action_fact = result.plan["info_required"][2]
    assert action_fact["componentHints"] == ["PillButton"]
    assert result.plan["assetAssignments"]["actions"][0]["assetId"] is None


def test_plan_tool_requires_composition_only_with_runtime_context() -> None:
    tool = build_compact_plan_tool(task_spec(), include_composition=True)
    parameters = tool["function"]["parameters"]

    assert "composition" in parameters["properties"]
    assert parameters["required"] == ["info_required", "composition"]
    groups = parameters["properties"]["composition"]["properties"]["regions"]
    component_enum = groups["items"]["properties"]["groups"]["items"]
    component_enum = component_enum["properties"]["component"]["enum"]
    assert "CardButton" not in component_enum


def test_two_by_four_plan_tool_offers_card_button_without_asset_candidates() -> None:
    spec = task_spec()
    spec["size"] = "2x4"

    tool = build_compact_plan_tool(spec, include_composition=True)
    parameters = tool["function"]["parameters"]
    fact_properties = parameters["properties"]["info_required"]["items"]["properties"]
    assert "CardButton" in fact_properties["componentHints"]["items"]["enum"]
    groups = parameters["properties"]["composition"]["properties"]["regions"]
    component_enum = groups["items"]["properties"]["groups"]["items"]
    assert "CardButton" in component_enum["properties"]["component"]["enum"]
    assert "assetAssignments" not in parameters["properties"]


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
    arguments = {
        "info_required": [
            {
                "requirement": "打开日历",
                "actionId": "event.open.calendar",
                "componentHints": ["Button", valid_action],
            }
        ]
    }
    raw = json.dumps(
        {
            "name": "submit_card_plan",
            "arguments": arguments,
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


def test_two_by_four_action_plan_removes_top_bottom_layout_hint() -> None:
    spec = task_spec()
    spec["size"] = "2x4"
    payload = json.loads(plan_call())
    arguments = payload.get("arguments")
    assert isinstance(arguments, dict)
    arguments["layoutHints"] = ["W-top-bottom", "W-content-side-slots"]

    result = parse_compact_plan_call(json.dumps(payload, ensure_ascii=False), spec)

    assert result.plan.get("layoutHints") == ["W-content-side-slots"]
    assert result.warnings[-1] == (
        "W-top-bottom was removed from layoutHints because the 2x4 Plan contains "
        "an Action and this layout has no legal action slot."
    )


def test_two_by_four_action_plan_does_not_invent_replacement_layout_hint() -> None:
    spec = task_spec()
    spec["size"] = "2x4"
    payload = json.loads(plan_call())
    arguments = payload.get("arguments")
    assert isinstance(arguments, dict)
    arguments["layoutHints"] = ["W-top-bottom"]

    result = parse_compact_plan_call(json.dumps(payload, ensure_ascii=False), spec)

    assert "layoutHints" not in result.plan
    assert result.warnings[-1] == (
        "W-top-bottom was removed from layoutHints because the 2x4 Plan contains "
        "an Action and this layout has no legal action slot."
    )


def test_two_by_four_plan_without_action_keeps_top_bottom_layout_hint() -> None:
    spec = task_spec()
    spec["size"] = "2x4"
    payload = json.loads(plan_call())
    arguments = payload.get("arguments")
    assert isinstance(arguments, dict)
    facts = arguments.get("info_required")
    assert isinstance(facts, list)
    arguments["info_required"] = [fact for fact in facts if "actionId" not in fact]
    arguments["layoutHints"] = ["W-top-bottom"]

    result = parse_compact_plan_call(json.dumps(payload, ensure_ascii=False), spec)

    assert result.plan.get("layoutHints") == ["W-top-bottom"]
    assert not any("W-top-bottom was removed" in warning for warning in result.warnings)


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


@pytest.mark.parametrize("component_type", ["SecondaryBody", "TextBlock"])
def test_static_plan_fact_can_span_label_and_value_in_same_item(
    component_type: str,
) -> None:
    plan = {
        "info_required": [
            {
                "requirement": "Day1 09:00-11:30 灵隐寺祈福",
                "text": "09:00-11:30 灵隐寺祈福",
                "priority": "must",
            }
        ]
    }
    source = "\n".join(
        [
            '["root","Column",{},["details"]]',
            f'["details","{component_type}",{{"items":['
            '{"label":"Day1 09:00-11:30 ","value":"灵隐寺祈福"}]}}]',
        ]
    )

    result = evaluate_compact_plan_coverage(source, plan, task_spec())

    assert result.errors == ()


def test_static_plan_fact_cannot_span_different_structured_items() -> None:
    plan = {
        "info_required": [
            {
                "requirement": "Day1 09:00-11:30 灵隐寺祈福",
                "text": "09:00-11:30 灵隐寺祈福",
                "priority": "must",
            }
        ]
    }
    source = "\n".join(
        [
            '["root","Column",{},["details"]]',
            '["details","SecondaryBody",{"items":['
            '{"label":"Day1 09:00-11:30 ","value":"其他景点"},'
            '{"label":"Day1 13:30-16:30 ","value":"灵隐寺祈福"}]}}]',
        ]
    )

    result = evaluate_compact_plan_coverage(source, plan, task_spec())

    assert result.errors == (
        "Plan static text is not fully visible in DSL: Day1 09:00-11:30 灵隐寺祈福.",
    )


@pytest.mark.parametrize(
    "plan_text",
    ["09:00-11:30 灵隐寺祈福", "灵隐寺祈福 09:00-11:30"],
)
def test_static_plan_fact_can_span_event_card_time_and_title_in_same_item(
    plan_text: str,
) -> None:
    plan = {
        "info_required": [
            {
                "requirement": "Day1 09:00-11:30 灵隐寺祈福",
                "text": plan_text,
                "priority": "must",
            }
        ]
    }
    source = "\n".join(
        [
            '["root","Column",{},["events"]]',
            '["events","EventCard",{"items":['
            '{"title":"灵隐寺祈福","time":"09:00-11:30"}]}]',
        ]
    )

    result = evaluate_compact_plan_coverage(source, plan, task_spec())

    assert result.errors == ()


def test_static_plan_fact_cannot_span_different_event_card_items() -> None:
    plan = {
        "info_required": [
            {
                "requirement": "Day1 09:00-11:30 灵隐寺祈福",
                "text": "09:00-11:30 灵隐寺祈福",
                "priority": "must",
            }
        ]
    }
    source = "\n".join(
        [
            '["root","Column",{},["events"]]',
            '["events","EventCard",{"items":['
            '{"title":"其他景点","time":"09:00-11:30"},'
            '{"title":"灵隐寺祈福","time":"13:30-16:30"}]}]',
        ]
    )

    result = evaluate_compact_plan_coverage(source, plan, task_spec())

    assert result.errors == (
        "Plan static text is not fully visible in DSL: Day1 09:00-11:30 灵隐寺祈福.",
    )


def test_static_plan_fact_requires_complete_event_card_item_text() -> None:
    plan = {
        "info_required": [
            {
                "requirement": "Day1 09:00-11:30 灵隐寺祈福",
                "text": "09:00-11:30 灵隐寺祈福",
                "priority": "must",
            }
        ]
    }
    source = "\n".join(
        [
            '["root","Column",{},["events"]]',
            '["events","EventCard",{"items":['
            '{"title":"灵隐寺祈福","time":"09:00"}]}]',
        ]
    )

    result = evaluate_compact_plan_coverage(source, plan, task_spec())

    assert result.errors == (
        "Plan static text is not fully visible in DSL: Day1 09:00-11:30 灵隐寺祈福.",
    )


def test_compact_dsl_rejects_duplicate_visible_plan_data() -> None:
    plan = {
        "info_required": [
            {
                "requirement": "会议标题",
                "dataId": "/data/calendar/events/0/title",
                "componentHints": ["EmphasisText", "SecondaryBody"],
            }
        ]
    }
    source = "\n".join(
        [
            '["root","Column",{},["primary","support"]]',
            '["primary","EmphasisText",'
            '{"mainText":{"path":"/data/calendar/events/0/title"}}]',
            '["support","SecondaryBody",{"items":['
            '{"label":"会议 ","value":"{{ ${/data/calendar/events/0/title} }}"}]}]',
            '["/data/calendar/events/0/title","设计评审"]',
        ]
    )

    result = evaluate_compact_plan_coverage(source, plan, task_spec())

    assert len(result.errors) == 1
    assert "displayed more than once" in result.errors[0]
    assert "primary (EmphasisText).mainText" in result.errors[0]
    assert "support (SecondaryBody).items[0].value" in result.errors[0]
    assert result.duplicate_facts == (
        {
            "requirement": "会议标题",
            "dataId": "/data/calendar/events/0/title",
            "expectedVisibleCount": 1,
            "actualVisibleCount": 2,
            "occurrences": [
                {
                    "componentId": "primary",
                    "componentType": "EmphasisText",
                    "property": "mainText",
                },
                {
                    "componentId": "support",
                    "componentType": "SecondaryBody",
                    "property": "items[0].value",
                },
            ],
        },
    )


def test_duplicate_plan_data_remains_blocking_when_missing_data_is_warning() -> None:
    plan = {
        "info_required": [
            {
                "requirement": "会议标题",
                "dataId": "/data/calendar/events/0/title",
            }
        ]
    }
    source = "\n".join(
        [
            '["root","Column",{},["first","second"]]',
            '["first","Text",{"content":{"path":"/data/calendar/events/0/title"}}]',
            '["second","Text",{"content":{"path":"/data/calendar/events/0/title"}}]',
            '["/data/calendar/events/0/title","设计评审"]',
        ]
    )

    result = evaluate_compact_plan_coverage(
        source,
        plan,
        task_spec(),
        information_errors_as_warnings=True,
    )

    assert len(result.errors) == 1
    assert result.warnings == ()


def test_anchor_composition_cannot_be_replaced_by_text_action_layout() -> None:
    spec = task_spec()
    plan = {
        "info_required": [
            {
                "requirement": "会议标题",
                "dataId": "/data/calendar/events/0/title",
                "componentHints": ["SecondaryBody"],
            },
            {
                "requirement": "打开日历",
                "actionId": "event.open.calendar",
                "componentHints": ["CircleButton", "PillButton"],
            },
        ],
        "layoutHints": ["S-title-anchor", "S-title-content-action"],
        "composition": {
            "layout": "S-title-anchor",
            "variant": 1,
            "regions": [],
        },
    }
    source = "\n".join(
        [
            '["root","Column",{},["title","content","action"]]',
            '["title","SingleLineTitle",{"title":"会议"}]',
            '["content","SecondaryBody",{"role":"body","items":'
            '[{"value":{"path":"/data/calendar/events/0/title"}}]}]',
            '["action","PillButton",{"label":"打开日历","onClick":'
            '[{"call":"clickToDeeplink","args":{"uri":"hww://calendar"}}]}]',
        ]
    )

    errors = compact_plan_coverage_errors(source, plan, spec)

    assert errors == (
        "Accepted Compact Plan selected S-title-anchor as its executable composition; "
        "keep the CircleButton anchor layout instead of replacing it with a text-action "
        "layout that compresses the required content.",
    )


def test_single_focus_data_display_route_cannot_be_downgraded_during_repair() -> None:
    spec = task_spec()
    plan = {
        "info_required": [
            {
                "requirement": "会议标题",
                "priority": "must",
                "dataId": "/data/calendar/events/0/title",
                "componentHints": ["DataDisplay", "EmphasisText"],
            }
        ],
        "layoutHints": ["S-center"],
    }
    downgraded = "\n".join(
        [
            '["root","Layout",{"layout":"S-title-content"},["header","display"]]',
            '["header","SingleLineTitle",{"title":"会议"}]',
            '["display","EmphasisText",{"mainText":'
            '{"path":"/data/calendar/events/0/title"}}]',
        ]
    )
    preserved = "\n".join(
        [
            '["root","Layout",{"layout":"S-center"},["display"]]',
            '["display","DataDisplay",{"label":"会议","value":'
            '{"path":"/data/calendar/events/0/title"},"supportingText":"今日"}]',
        ]
    )

    errors = compact_plan_coverage_errors(downgraded, plan, spec)

    assert errors == (
        "已接受 Plan 选择了 2x2 单焦点 S-center + DataDisplay；修复时必须保留"
        "该布局与组件，不得降级为 SingleLineTitle + EmphasisText 或 EmphasizedData。",
    )
    assert compact_plan_coverage_errors(preserved, plan, spec) == ()

    long_value_spec = task_spec()
    schema = long_value_spec.get("dataModelSchema")
    assert isinstance(schema, dict)
    data = schema.get("data")
    assert isinstance(data, dict)
    calendar = data.get("calendar")
    assert isinstance(calendar, dict)
    events = calendar.get("events")
    assert isinstance(events, list)
    assert events
    first_event = events[0]
    assert isinstance(first_event, dict)
    title = first_event.get("title")
    assert isinstance(title, dict)
    title["sampleValue"] = "这是明确超过八个字的文本结论"
    assert compact_plan_coverage_errors(downgraded, plan, long_value_spec) == ()


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

    assert compact_plan_optional_drop_candidate(
        source,
        plan,
        spec,
        allow_must_fallback=False,
    ) is None

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

def test_single_line_title_plan_hint_can_be_covered_by_body_component() -> None:
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
    body_source = "\n".join(
        [
            '["root","Column",{},["title"]]',
            '["title","TextBlock",{"items":[{"label":"会议",'
            '"value":{"path":"/data/calendar/events/0/title"}}]}]',
        ]
    )
    header_source = "\n".join(
        [
            '["root","Column",{},["title"]]',
            '["title","SingleLineTitle",{"title":{"path":'
            '"/data/calendar/events/0/title"},"fontColor":"#FF1F4799"}]',
        ]
    )

    assert compact_plan_coverage_errors(body_source, plan, spec) == ()
    assert compact_plan_coverage_errors(header_source, plan, spec) == ()


def test_static_title_plan_hint_can_be_covered_by_body_component() -> None:
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

    assert compact_plan_coverage_errors(source, plan, spec) == ()
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


def test_progress_driver_and_readout_count_as_one_visible_fact() -> None:
    spec = {
        "size": "2x4",
        "dataModelSchema": {
            "data": {
                "health": {
                    "score": {
                        "type": "integer",
                        "description": "睡眠得分",
                    }
                }
            }
        },
        "eventCandidates": [],
    }
    plan = {
        "info_required": [
            {
                "requirement": "睡眠得分",
                "dataId": "/data/health/score",
                "componentHints": ["ProgressLine2"],
            }
        ]
    }
    source = "\n".join(
        [
            '["root","Column",{},["score"]]',
            '["score","ProgressLine2",'
            '{"value":{"path":"/data/health/score"},"total":100,'
            '"displayValue":{"path":"/data/health/score"},'
            '"color":"#FF563D99","backgroundColor":"#33563D99"}]',
        ]
    )

    assert compact_plan_coverage_errors(source, plan, spec) == ()


@pytest.mark.parametrize("validate_drop_facts", [False, True])
@pytest.mark.parametrize("drop_entered", [False, True])
@pytest.mark.parametrize("missing_action", [False, True])
def test_drop_fact_validation_switch_keeps_normal_coverage_and_action_checks(
    validate_drop_facts: bool, drop_entered: bool, missing_action: bool,
) -> None:
    spec = task_spec()
    spec["size"] = "2x4"
    spec["appVersion"] = "12.0.0.1"
    plan = {
        "info_required": [
            {"requirement": "会议标题", "dataId": "/data/calendar/events/0/title",
             "priority": "must"},
            {"requirement": "会议时间", "dataId": "/data/calendar/events/0/start",
             "priority": "should"},
            {"requirement": "打开日历", "actionId": "event.open.calendar", "priority": "must"},
        ]
    }
    source_rows = [
        ["root", "Layout", {"layout": "W-split-panels"}, ["left", "right"]],
        ["left", "Region", {"variant": "center"}, ["main"]],
        ["main", "EmphasisText", {"mainText": {"path": "/data/calendar/events/0/title"}}],
        ["right", "Region", {"variant": "title-content-action"}, ["title", "extra", "action"]],
        ["title", "SingleLineTitle", {"title": "打开日历"}],
        ["extra", "SecondaryBody", {"items": [
            {"label": "时间", "value": {"path": "/data/calendar/events/0/start"}},
        ]}],
        ["action", "PillButton", {"label": "打开日历", "onClick": [
            {"call": "clickToDeeplink", "args": {"uri": "hww://calendar"}},
        ]}],
    ]
    original = "\n".join(json.dumps(row, ensure_ascii=False) for row in source_rows)
    tracker = CompactRepairStrategyTracker()
    if drop_entered:
        errors = [{
            "code": "COMPACT_DSL_VALIDATION_FAILED", "stage": "validation",
            "message": "component right: vertical layout requires at least 140vp within 110vp",
        }]
        for _ in range(4):
            directive = tracker.next_directive(original, errors, compact_plan=plan, task_spec=spec)
        assert directive.repair_strategy == "drop_optional_component"
        assert tracker.allowed_omitted_fact_indexes == (1,)
    allowed = tracker.validation_omitted_fact_indexes(
        plan, validate_drop_plan_facts=validate_drop_facts,
    )
    source_rows[2] = ["main", "EmphasisText", {"mainText": "日程概览"}]
    source_rows[5] = ["guide", "EmphasisText", {"mainText": "日程信息"}]
    source_rows[3][3] = ["title", "guide", "action"]
    if missing_action:
        source_rows[3][2] = {"variant": "title-content"}
        source_rows[3][3] = ["title", "guide"]
        source_rows.pop()
    source_rows.append(["/state/ready", True])
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in source_rows)
    result = DesignCompactProcessor().process(source, DslProcessingContext(
        size="2x4", card_spec={"suggestSize": "2x4"}, task_spec=spec,
        protocol_profile={}, compact_plan=plan, allowed_omitted_plan_fact_indexes=allowed,
    ))
    messages = [issue.message for issue in result.errors]
    expect_missing_facts = not drop_entered or validate_drop_facts
    assert any("Plan fact is missing" in message for message in messages) == expect_missing_facts
    assert any("Plan action is missing" in message for message in messages) == missing_action
    if not expect_missing_facts and not missing_action:
        assert result.errors == ()
        assert result.standard_dsl
    omitted = compact_plan_omitted_facts(source, plan, spec, allowed)
    expected_omitted = 0 if not drop_entered else 1 if validate_drop_facts else 2
    assert len(omitted) == expected_omitted
    assert all("actionId" not in fact for fact in omitted)


def test_processor_reports_missing_static_plan_text_as_initial_error() -> None:
    plan = {
        "info_required": [
            {
                "requirement": "卡片标题",
                "priority": "must",
                "text": "静态卡片",
                "componentHints": ["EmphasisText"],
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
        '["title","EmphasisText",{"mainText":"其他文字","fontSize":18}]',
        context,
    )

    assert result.standard_dsl == ""
    assert len(result.errors) == 1
    assert result.errors[0].code == "COMPACT_PLAN_COVERAGE_FAILED"
    assert "卡片标题" in result.errors[0].message
    warnings = tuple(issue for issue in result.issues if issue.severity == "warning")
    assert warnings == ()


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_repair_coverage_downgrades_information_but_not_action(size: str) -> None:
    handler = {"call": "openSettings", "args": {"target": "device"}}
    spec = {
        "size": size,
        "dataModelSchema": {
            "data": {
                "device": {
                    "status": {
                        "type": "string",
                        "description": "设备状态",
                        "sampleValue": "在线",
                    }
                }
            }
        },
        "eventCandidates": [{"id": "event.open.settings", **handler}],
        "assetCandidates": [],
    }
    plan = {
        "info_required": [
            {
                "requirement": "展示设备状态",
                "dataId": "/data/device/status",
                "priority": "must",
            },
            {
                "requirement": "展示静态说明",
                "text": "必须保留的静态说明",
                "priority": "must",
            },
            {
                "requirement": "打开设备设置",
                "actionId": "event.open.settings",
                "priority": "must",
            },
        ]
    }
    source = '\n'.join(
        [
            '["root","Column",{},["summary"]]',
            '["summary","EmphasisText",{"mainText":"设备概览","fontSize":18}]',
        ]
    )

    strict = evaluate_compact_plan_coverage(source, plan, spec)
    assert len(strict.errors) == 3
    assert strict.warnings == ()

    repaired = evaluate_compact_plan_coverage(
        source,
        plan,
        spec,
        information_errors_as_warnings=True,
    )
    assert len(repaired.errors) == 1
    assert "Plan action is missing" in repaired.errors[0]
    assert len(repaired.warnings) == 2
    assert any("Plan fact is missing" in warning for warning in repaired.warnings)
    assert any("Plan static text" in warning for warning in repaired.warnings)


def test_static_fact_is_not_satisfied_by_visual_style_props() -> None:
    plan = {
        "info_required": [
            {
                "requirement": "卡片标题",
                "priority": "must",
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

    assert errors == ("Plan static text is not fully visible in DSL: 卡片标题.",)
    assert warnings == ()


def test_shortened_static_plan_text_is_initial_error() -> None:
    plan = {
        "info_required": [
            {
                "requirement": "展示提醒文字“每天带孩子出去运动两次”",
                "priority": "must",
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

    assert compact_plan_coverage_errors(source, plan, task_spec()) == (
        "Plan static text is not fully visible in DSL: "
        "展示提醒文字“每天带孩子出去运动两次”.",
    )
    assert compact_plan_coverage_warnings(source, plan, task_spec()) == ()
