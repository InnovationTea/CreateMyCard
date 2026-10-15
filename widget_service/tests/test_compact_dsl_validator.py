# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.

import json
import re
from pathlib import Path

import pytest

from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.compact_prompt_loader import assemble_prompts
from services.generation_pipeline import (
    DslProcessingContext,
    DslProcessorKind,
    get_dsl_processor,
)

_DESIGN_PROMPT_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "cloud"
    / "data"
    / "protocol_profiles"
    / "design-compact-dsl-fusion"
    / "prompt_source"
)
_DESIGN_PROMPT = assemble_prompts(_DESIGN_PROMPT_SOURCE).get("create")
assert isinstance(_DESIGN_PROMPT, str)

_INVALID_COMPACT_DSL = "\n".join(
    [
        '["root","Column",{"width":160,"height":160},["temperature"]]',
        '["temperature","Text",'
        '{"content":"{{ \'/data/weather/current/temperatureText\' }}"}]',
        '["/data/weather/current/temperatureText","26℃"]',
    ]
)

def _single_line_title_dsl(extra_props: str = "") -> str:
    return "\n".join(
        [
            '["root","Column",{"width":"matchParent","height":"matchParent"},'
            '["header"]]',
            '["header","SingleLineTitle",{"title":"主题","fontColor":"#FF563D99"'
            f'{extra_props}}}]',
        ]
    )


def _progress_circle_dsl(*, width: int, height: int, extra: str = "") -> str:
    return "\n".join(
        [
            '["root","Column",{"width":"matchParent","height":"matchParent"},'
            '["ring"]]',
            '["ring","ProgressCircle",{"externalText":68,'
            '"icon":"resources/battery.svg",'
            '"accessibility":{"label":"电量百分比"},'
            f'"width":{width},"height":{height},'
            '"fontColor":"#FF1F4799","fillColor":"#991F4799",'
            '"color":"#FF1F4799","backgroundColor":"#331F4799"'
            f'{extra}}}]',
        ]
    )


def _progress_circle_task_spec() -> dict:
    return {
        "size": "2x4",
        "eventCandidates": [],
        "dataModelSchema": {"data": {}},
        "assetCandidates": [
            {
                "src": "resources/battery.svg",
                "description": "可染色的电量单色图标",
            }
        ],
    }


def test_rejects_anchor_support_with_only_an_invented_static_label() -> None:
    handler = {
        "call": "clickToDeeplink",
        "args": {"intentName": "Weather", "uri": "hww://weather"},
    }
    compact_dsl = "\n".join(
        [
            '["root","Column",{"width":"matchParent","height":"matchParent",'
            '"padding":12,"itemMargin":6},["title","body"]]',
            '["title","SingleLineTitle",{"title":"西湖天气","fontSize":12,'
            '"width":"matchParent"}]',
            '["body","Column",{"width":"matchParent","itemMargin":8,'
            '"layoutWeight":1},["content","bottom"]]',
            '["content","Column",{"width":"matchParent","layoutWeight":1},'
            '["condition"]]',
            '["condition","EmphasisText",{"mainText":'
            '{"path":"/data/weather/current/condition"},"fontSize":18,'
            '"width":"matchParent"}]',
            '["bottom","Row",{"width":"matchParent","height":40,'
            '"itemMargin":8},["support","action_slot"]]',
            '["support","SecondaryBody",{"role":"metadata","items":['
            '{"value":"当前天气"}],"fontSize":12,"width":78}]',
            '["action_slot","Stack",{"width":40,"height":40,'
            '"alignContent":"center"},["action"]]',
            '["action","CircleButton",{"icon":"resources/base/media/sun_max.svg",'
            '"accessibility":{"label":"查看天气详情"},'
            f'"onClick":[{json.dumps(handler, ensure_ascii=False)}]' + "}]",
            '["/data/weather/current/condition","多云"]',
        ]
    )
    task_spec = {
        "size": "2x2",
        "eventCandidates": [{"id": "event.open.weather", **handler}],
        "dataModelSchema": {
            "data": {
                "weather": {
                    "current": {
                        "condition": {
                            "type": "string",
                            "description": "当前天气现象",
                            "sampleValue": "多云",
                        }
                    }
                }
            }
        },
        "assetCandidates": [
            {
                "src": "resources/base/media/sun_max.svg",
                "description": "晴天或天气详情图标",
            }
        ],
    }
    compact_plan = {
        "info_required": [
            {
                "requirement": "当前天气现象",
                "dataId": "/data/weather/current/condition",
                "componentHints": ["EmphasisText"],
            },
            {
                "requirement": "查看天气详情",
                "actionId": "event.open.weather",
                "componentHints": ["CircleButton", "PillButton"],
            },
        ],
        "layoutHints": ["S-title-anchor", "S-title-content-action"],
    }

    with pytest.raises(
        CompactDslValidationError,
        match="static category label such as '当前天气'",
    ):
        validate_compact_dsl(
            compact_dsl,
            task_spec=task_spec,
            card_spec={"suggestSize": "2x2", "dataBindings": []},
            compact_plan=compact_plan,
        )


def test_model_output_rejects_direct_text_and_isolated_secondary_body() -> None:
    task_spec = {
        "size": "2x2",
        "eventCandidates": [],
        "dataModelSchema": {"data": {}},
        "assetCandidates": [],
    }
    card_spec = {"suggestSize": "2x2", "dataBindings": []}
    direct_text = "\n".join(
        [
            '["root","Column",{},["body"]]',
            '["body","Text",{"content":"普通正文","fontSize":14,'
            '"fontColor":"#FF1F4799"}]',
        ]
    )

    with pytest.raises(CompactDslValidationError, match="converter-internal"):
        validate_compact_dsl(
            direct_text,
            task_spec=task_spec,
            card_spec=card_spec,
            enforce_model_component_types=True,
        )

    semantic_body = "\n".join(
        [
            '["root","Column",{},["body"]]',
            '["body","SecondaryBody",{"items":['
            '{"value":"普通正文","maxLines":1}],"fontColor":"#FF1F4799"}]',
        ]
    )
    with pytest.raises(
        CompactDslValidationError,
        match="SecondaryBody is auxiliary",
    ):
        validate_compact_dsl(
            semantic_body,
            task_spec=task_spec,
            card_spec=card_spec,
            enforce_model_component_types=True,
        )


def test_model_output_accepts_secondary_body_with_core_sibling() -> None:
    compact_dsl = "\n".join(
        [
            '["root","Column",{},["content"]]',
            '["content","Column",{"itemMargin":2},["primary","support"]]',
            '["primary","EmphasisText",{"mainText":"已连接","fontSize":18}]',
            '["support","SecondaryBody",{"items":'
            '[{"value":"更新于 10:00"}],"fontSize":14}]',
        ]
    )
    validate_compact_dsl(
        compact_dsl,
        task_spec={
            "size": "2x2",
            "eventCandidates": [],
            "dataModelSchema": {"data": {}},
            "assetCandidates": [],
        },
        card_spec={"suggestSize": "2x2", "dataBindings": []},
        enforce_model_component_types=True,
    )


def test_model_output_accepts_secondary_body_with_core_in_other_region() -> None:
    compact_dsl = "\n".join(
        [
            '["root","Column",{},["primary","bottom"]]',
            '["primary","Column",{},["wind"]]',
            '["wind","EmphasisText",{"mainText":"东南风 2级","fontSize":18}]',
            '["bottom","Row",{},["detail","support_label"]]',
            '["detail","SecondaryBody",{"items":['
            '{"value":"更新于 09:00"}],"fontSize":14}]',
            '["support_label","SingleLineTitle",{"title":"更新时间",'
            '"fontSize":12}]',
        ]
    )
    validate_compact_dsl(
        compact_dsl,
        task_spec={
            "size": "2x2",
            "eventCandidates": [],
            "dataModelSchema": {"data": {}},
            "assetCandidates": [],
        },
        card_spec={"suggestSize": "2x2", "dataBindings": []},
        enforce_model_component_types=True,
    )


@pytest.mark.parametrize("companion", ["PillButton", "SecondaryBody"])
def test_model_output_rejects_secondary_body_without_core_companion(
    companion: str,
) -> None:
    if companion == "PillButton":
        companion_row = (
            '["companion","PillButton",{"label":"查看",'
            '"onClick":[{"call":"open","args":{}}]}]'
        )
        event_candidates = [{"call": "open", "args": {}}]
    else:
        companion_row = (
            '["companion","SecondaryBody",{"role":"metadata","items":['
            '{"value":"另一条辅助信息"}],"fontSize":12}]'
        )
        event_candidates = []
    compact_dsl = "\n".join(
        [
            '["root","Column",{},["support","companion"]]',
            '["support","SecondaryBody",{"role":"body","items":['
            '{"value":"辅助信息"}],"fontSize":14}]',
            companion_row,
        ]
    )
    with pytest.raises(CompactDslValidationError, match="SecondaryBody is auxiliary"):
        validate_compact_dsl(
            compact_dsl,
            task_spec={
                "size": "2x2",
                "eventCandidates": event_candidates,
                "dataModelSchema": {"data": {}},
                "assetCandidates": [],
            },
            card_spec={"suggestSize": "2x2", "dataBindings": []},
            enforce_model_component_types=True,
        )


def test_accepts_progress_circle_free_box_geometry() -> None:
    validate_compact_dsl(
        _progress_circle_dsl(width=72, height=76),
        task_spec=_progress_circle_task_spec(),
        card_spec={"suggestSize": "2x4", "dataBindings": []},
    )


def test_accepts_bitmap_icon_without_fill_color() -> None:
    source = _progress_circle_dsl(width=72, height=76).replace(
        "resources/battery.svg",
        "resources/battery.png",
    ).replace('"fillColor":"#991F4799",', "")
    task_spec = _progress_circle_task_spec()
    task_spec["assetCandidates"][0]["src"] = "resources/battery.png"

    validate_compact_dsl(
        source,
        task_spec=task_spec,
        card_spec={"suggestSize": "2x4", "dataBindings": []},
    )

def test_accepts_svg_icon_auto_tinted_by_pill_button() -> None:
    handler = {
        "call": "clickToDeeplink",
        "args": {
            "intentName": "Settings",
            "bundleName": "com.huawei.hmos.settings",
            "abilityName": "com.huawei.hmos.settings.MainAbility",
            "uri": "bluetooth_entry",
        },
    }
    source = "\n".join(
        [
            '["root","Column",{},["cta"]]',
            '["cta","PillButton",{"label":"蓝牙设置",'
            '"icon":"resources/settings.svg",'
            f'"onClick":[{json.dumps(handler, ensure_ascii=False)}]' + "}]",
        ]
    )
    task_spec = {
        "size": "2x2",
        "eventCandidates": [handler],
        "dataModelSchema": {"data": {}},
        "assetCandidates": [{"src": "resources/settings.svg"}],
    }

    validate_compact_dsl(
        source,
        task_spec=task_spec,
        card_spec={"suggestSize": "2x2", "dataBindings": []},
    )


def test_accepts_progress_circle_bound_to_complete_percentage_text() -> None:
    source = "\n".join(
        [
            '["root","Column",{},["ring"]]',
            '["ring","ProgressCircle",'
            '{"externalText":{"path":"/data/weather/rainProbability"},'
            '"icon":"resources/battery.svg",'
            '"accessibility":{"label":"降雨概率"},'
            '"width":72,"height":76,"fontColor":"#FF1F4799",'
            '"fillColor":"#991F4799",'
            '"color":"#FF1F4799","backgroundColor":"#331F4799"}]',
            '["/data/weather/rainProbability","20%"]',
        ]
    )
    task_spec = _progress_circle_task_spec()
    task_spec["dataModelSchema"] = {
        "data": {
            "weather": {
                "rainProbability": {
                    "type": "string",
                    "description": "可直接显示的降雨概率百分比",
                    "sampleValue": "20%",
                }
            }
        }
    }

    validate_compact_dsl(
        source,
        task_spec=task_spec,
        card_spec={
            "suggestSize": "2x4",
            "dataBindings": [
                {
                    "capabilityId": "ViewWeather",
                    "arguments": {},
                    "writeResultTo": "/data/weather",
                }
            ],
        },
    )


def test_accepts_progress_circle_percentage_expression() -> None:
    source = "\n".join(
        [
            '["root","Column",{},["ring"]]',
            '["ring","ProgressCircle",'
            '{"externalText":"{{ ${/data/battery/percent} + \'%\' }}",'
            '"icon":"resources/battery.svg",'
            '"accessibility":{"label":"电量百分比"},'
            '"width":72,"height":76,"fontColor":"#FF1F4799",'
            '"fillColor":"#991F4799",'
            '"color":"#FF1F4799","backgroundColor":"#331F4799"}]',
            '["/data/battery/percent",68]',
        ]
    )
    task_spec = _progress_circle_task_spec()
    task_spec["dataModelSchema"] = {
        "data": {
            "battery": {
                "percent": {
                    "type": "number",
                    "description": "0 到 100 的电量百分比",
                    "sampleValue": 68,
                }
            }
        }
    }

    validate_compact_dsl(
        source,
        task_spec=task_spec,
        card_spec={"suggestSize": "2x4", "dataBindings": []},
        enforce_model_component_types=True,
    )


def test_rejects_progress_circle_bound_to_business_copy_with_percentage() -> None:
    source = "\n".join(
        [
            '["root","Column",{},["ring"]]',
            '["ring","ProgressCircle",'
            '{"externalText":{"path":"/data/weather/rainProbability"},'
            '"icon":"resources/battery.svg",'
            '"accessibility":{"label":"降雨概率"},'
            '"width":72,"height":76,"fontColor":"#FF1F4799",'
            '"fillColor":"#991F4799",'
            '"color":"#FF1F4799","backgroundColor":"#331F4799"}]',
            '["/data/weather/rainProbability","降雨概率 20%"]',
        ]
    )
    task_spec = _progress_circle_task_spec()
    task_spec["dataModelSchema"] = {
        "data": {
            "weather": {
                "rainProbability": {
                    "type": "string",
                    "description": "带业务标签的降雨概率文案",
                    "sampleValue": "降雨概率 20%",
                }
            }
        }
    }

    with pytest.raises(
        CompactDslValidationError,
        match="complete numeric percentage",
    ):
        validate_compact_dsl(
            source,
            task_spec=task_spec,
            card_spec={"suggestSize": "2x4", "dataBindings": []},
        )


@pytest.mark.parametrize(
    ("width", "height", "extra", "message"),
    [
        (44, 30, "", "leave less than 40vp for the ring"),
        (44, 60, ',"value":68', "ProgressCircle does not allow value"),
    ],
)
def test_rejects_invalid_progress_circle_contract(
    width: int,
    height: int,
    extra: str,
    message: str,
) -> None:
    with pytest.raises(CompactDslValidationError, match=message):
        validate_compact_dsl(
            _progress_circle_dsl(width=width, height=height, extra=extra),
            task_spec=_progress_circle_task_spec(),
            card_spec={"suggestSize": "2x4", "dataBindings": []},
        )


@pytest.mark.parametrize("component_type", ["Divider", "Image", "Progress"])
def test_rejects_removed_direct_compact_input(component_type: str) -> None:
    with pytest.raises(
        CompactDslValidationError,
        match=rf"unsupported component type {component_type}",
    ):
        validate_compact_dsl(
            '\n'.join(
                [
                    '["root","Column",{},["item"]]',
                    f'["item","{component_type}",{{}}]',
                ]
            ),
            task_spec=_progress_circle_task_spec(),
            card_spec={"suggestSize": "2x4", "dataBindings": []},
        )


@pytest.mark.parametrize(
    "extra_props",
    [
        ',"fillColor":"#FF563D99"',
    ],
)
def test_rejects_single_line_title_visual_props(extra_props: str) -> None:
    with pytest.raises(
        CompactDslValidationError,
        match=r"SingleLineTitle",
    ):
        validate_compact_dsl(
            _single_line_title_dsl(extra_props),
            task_spec={
                "size": "2x4",
                "eventCandidates": [],
                "dataModelSchema": {"data": {}},
                "assetCandidates": [{"src": "resources/heart.svg"}],
            },
            card_spec={"suggestSize": "2x4", "dataBindings": []},
        )


def test_accepts_single_line_title_with_task_spec_icon() -> None:
    validate_compact_dsl(
        _single_line_title_dsl(',"icon":"resources/weather.png"'),
        task_spec={
            "size": "2x4",
            "eventCandidates": [],
            "dataModelSchema": {"data": {}},
            "assetCandidates": [{"src": "resources/weather.png"}],
        },
        card_spec={"suggestSize": "2x4", "dataBindings": []},
    )


def test_accepts_single_line_title_svg_without_authored_fill_color() -> None:
    validate_compact_dsl(
        _single_line_title_dsl(',"icon":"resources/weather.svg"'),
        task_spec={
            "size": "2x4",
            "eventCandidates": [],
            "dataModelSchema": {"data": {}},
            "assetCandidates": [{"src": "resources/weather.svg"}],
        },
        card_spec={"suggestSize": "2x4", "dataBindings": []},
    )


def test_rejects_single_line_title_icon_outside_task_spec_assets() -> None:
    with pytest.raises(CompactDslValidationError, match="asset must use an original src"):
        validate_compact_dsl(
            _single_line_title_dsl(',"icon":"resources/weather.png"'),
            task_spec={
                "size": "2x4",
                "eventCandidates": [],
                "dataModelSchema": {"data": {}},
                "assetCandidates": [],
            },
            card_spec={"suggestSize": "2x4", "dataBindings": []},
        )


@pytest.mark.parametrize("button_type", ["PillButton", "CircleButton"])
def test_rejects_title_and_action_button_reusing_same_icon(button_type: str) -> None:
    compact_dsl = "\n".join(
        [
            '["root","Column",{},["header","action"]]',
            '["header","SingleLineTitle",{"title":"天气",'
            '"icon":"resources/weather.svg","fillColor":"#FF563D99"}]',
            f'["action","{button_type}",{{"icon":"resources/weather.svg"}}]',
        ]
    )

    with pytest.raises(
        CompactDslValidationError,
        match="replace the title icon with another unused matching asset",
    ):
        validate_compact_dsl(
            compact_dsl,
            task_spec={
                "size": "2x2",
                "eventCandidates": [],
                "dataModelSchema": {"data": {}},
                "assetCandidates": [{"src": "resources/weather.svg"}],
            },
            card_spec={"suggestSize": "2x2", "dataBindings": []},
        )


def test_allows_title_and_button_to_use_distinct_icons() -> None:
    handler = {"call": "openWeather", "args": {}}
    compact_dsl = "\n".join(
        [
            '["root","Column",{},["header","action"]]',
            '["header","SingleLineTitle",{"title":"天气",'
            '"icon":"resources/weather.svg","fillColor":"#FF563D99"}]',
            '["action","PillButton",{"label":"打开天气",'
            '"icon":"resources/action.svg",'
            f'"onClick":[{json.dumps(handler, ensure_ascii=False)}]' + "}]",
        ]
    )

    validate_compact_dsl(
        compact_dsl,
        task_spec={
            "size": "2x2",
            "eventCandidates": [handler],
            "dataModelSchema": {"data": {}},
            "assetCandidates": [
                {"src": "resources/weather.svg"},
                {"src": "resources/action.svg"},
            ],
        },
        card_spec={"suggestSize": "2x2", "dataBindings": []},
    )


def test_accepts_icons_matching_plan_asset_assignments() -> None:
    handler = {"call": "openWeather", "args": {}}
    task_spec = {
        "size": "2x2",
        "eventCandidates": [{"id": "event.open.weather", **handler}],
        "dataModelSchema": {"data": {}},
        "assetCandidates": [
            {"id": "asset.weather", "src": "resources/weather.svg"},
            {"id": "asset.action", "src": "resources/action.svg"},
        ],
    }
    compact_plan = {
        "assetAssignments": {
            "actions": [
                {
                    "actionId": "event.open.weather",
                    "assetId": "asset.action",
                }
            ],
            "title": {"assetId": "asset.weather"},
        }
    }
    compact_dsl = "\n".join(
        [
            '["root","Column",{},["header","action"]]',
            '["header","SingleLineTitle",{"title":"天气",'
            '"icon":"resources/weather.svg"}]',
            '["action","PillButton",{"label":"打开天气",'
            '"icon":"resources/action.svg",'
            f'"onClick":[{json.dumps(handler)}]' + "}]",
        ]
    )

    validate_compact_dsl(
        compact_dsl,
        task_spec=task_spec,
        card_spec={"suggestSize": "2x2", "dataBindings": []},
        compact_plan=compact_plan,
    )


def test_allows_plan_title_asset_without_title_when_info_block_is_present() -> None:
    task_spec = {
        "size": "2x2",
        "eventCandidates": [],
        "dataModelSchema": {"data": {}},
        "assetCandidates": [
            {"id": "asset.earphone", "src": "resources/earphone.svg"},
        ],
    }
    compact_plan = {
        "assetAssignments": {
            "actions": [],
            "title": {"assetId": "asset.earphone"},
        }
    }
    compact_dsl = "\n".join(
        [
            '["root","Column",{},["left","right"]]',
            '["left","InfoBlock",{"primaryText":"左耳 80%",'
            '"secondaryText":"未充电","backgroundColor":"#CCFFFFFF"}]',
            '["right","InfoBlock",{"primaryText":"右耳 75%",'
            '"secondaryText":"未充电","backgroundColor":"#CCFFFFFF"}]',
        ]
    )

    validate_compact_dsl(
        compact_dsl,
        task_spec=task_spec,
        card_spec={"suggestSize": "2x2", "dataBindings": []},
        compact_plan=compact_plan,
    )


def test_rejects_plan_title_asset_without_title_or_info_block() -> None:
    task_spec = {
        "size": "2x2",
        "eventCandidates": [],
        "dataModelSchema": {"data": {}},
        "assetCandidates": [
            {"id": "asset.weather", "src": "resources/weather.svg"},
        ],
    }
    compact_plan = {
        "assetAssignments": {
            "actions": [],
            "title": {"assetId": "asset.weather"},
        }
    }
    compact_dsl = "\n".join(
        [
            '["root","Column",{},["weather"]]',
            '["weather","EmphasisText",{"mainText":"晴"}]',
        ]
    )

    with pytest.raises(
        CompactDslValidationError,
        match="assetAssignments.title selected an icon but DSL has no SingleLineTitle",
    ):
        validate_compact_dsl(
            compact_dsl,
            task_spec=task_spec,
            card_spec={"suggestSize": "2x2", "dataBindings": []},
            compact_plan=compact_plan,
        )


@pytest.mark.parametrize(
    ("missing_fragment", "expected_error"),
    [
        (',"icon":"resources/weather.svg"', "primary SingleLineTitle must use"),
        (',"icon":"resources/action.svg"', "button for action 'event.open.weather' must use"),
    ],
)
def test_rejects_missing_plan_asset_assignment(
    missing_fragment: str,
    expected_error: str,
) -> None:
    handler = {"call": "openWeather", "args": {}}
    compact_dsl = "\n".join(
        [
            '["root","Column",{},["header","action"]]',
            '["header","SingleLineTitle",{"title":"天气",'
            '"icon":"resources/weather.svg"}]',
            '["action","PillButton",{"label":"打开天气",'
            '"icon":"resources/action.svg",'
            f'"onClick":[{json.dumps(handler)}]' + "}]",
        ]
    ).replace(missing_fragment, "")
    task_spec = {
        "size": "2x2",
        "eventCandidates": [{"id": "event.open.weather", **handler}],
        "dataModelSchema": {"data": {}},
        "assetCandidates": [
            {"id": "asset.weather", "src": "resources/weather.svg"},
            {"id": "asset.action", "src": "resources/action.svg"},
        ],
    }
    compact_plan = {
        "assetAssignments": {
            "actions": [
                {
                    "actionId": "event.open.weather",
                    "assetId": "asset.action",
                }
            ],
            "title": {"assetId": "asset.weather"},
        }
    }

    with pytest.raises(CompactDslValidationError, match=re.escape(expected_error)):
        validate_compact_dsl(
            compact_dsl,
            task_spec=task_spec,
            card_spec={"suggestSize": "2x2", "dataBindings": []},
            compact_plan=compact_plan,
        )


def test_allows_2x4_title_without_plan_assigned_icon() -> None:
    task_spec = {
        "size": "2x4",
        "eventCandidates": [],
        "dataModelSchema": {"data": {}},
        "assetCandidates": [
            {"id": "asset.weather", "src": "resources/weather.svg"},
        ],
    }
    compact_plan = {
        "assetAssignments": {
            "actions": [],
            "title": {"assetId": "asset.weather"},
        }
    }
    compact_dsl = "\n".join(
        [
            '["root","Column",{},["header"]]',
            '["header","SingleLineTitle",{"title":"天气","fontSize":12}]',
        ]
    )

    validate_compact_dsl(
        compact_dsl,
        task_spec=task_spec,
        card_spec={"suggestSize": "2x4", "dataBindings": []},
        compact_plan=compact_plan,
    )


def test_design_processor_reports_compact_contract_as_validation() -> None:
    context = DslProcessingContext(
        size="2x2",
        card_spec={"dataBindings": []},
        task_spec={
            "userQuery": "生成静态天气入口卡",
            "size": "2x2",
            "eventCandidates": [],
            "dataModelSchema": {"data": {}},
            "assetCandidates": [],
        },
        protocol_profile={"version": "v0.9"},
        design_profile_id="design-compact-dsl",
    )

    result = get_dsl_processor(DslProcessorKind.DESIGN_COMPACT).process(
        _INVALID_COMPACT_DSL,
        context,
    )

    assert result.standard_dsl == ""
    assert len(result.errors) == 1
    assert all(item.stage == "validation" for item in result.errors)
    assert all(
        item.code == "COMPACT_DSL_VALIDATION_FAILED"
        for item in result.errors
    )
    assert "Text is converter-internal" in result.errors[0].message


@pytest.mark.parametrize("component_type", ["Row", "Column", "Stack"])
def test_rejects_empty_container_before_a2ui_conversion(
    component_type: str,
) -> None:
    compact_dsl = "\n".join(
        [
            '["root","Column",{"width":160,"height":160},["empty"]]',
            f'["empty","{component_type}",{{"width":8,"height":8}},[]]',
        ]
    )

    with pytest.raises(
        CompactDslValidationError,
        match=(
            rf"component empty: {component_type}\.children must be non-empty; "
            "use parent itemMargin"
        ),
    ):
        validate_compact_dsl(
            compact_dsl,
            task_spec={
                "dataModelSchema": {"data": {}},
                "assetCandidates": [],
                "eventCandidates": [],
            },
            card_spec={"dataBindings": []},
        )


def _w9_sparse_task_spec() -> dict:
    return {
        "userQuery": "做一张横向状态卡片",
        "size": "2x4",
        "eventCandidates": [],
        "dataModelSchema": {
            "data": {
                "left": {
                    "name": {
                        "type": "string",
                        "description": "左侧对象名称",
                        "sampleValue": "项目",
                    },
                    "status": {
                        "type": "string",
                        "description": "左侧状态",
                        "sampleValue": "进行中",
                    },
                },
                "right": {
                    "name": {
                        "type": "string",
                        "description": "右侧对象名称",
                        "sampleValue": "同步",
                    },
                    "status": {
                        "type": "string",
                        "description": "右侧状态",
                        "sampleValue": "待处理",
                    },
                },
            }
        },
        "assetCandidates": [],
    }


def _w9_sparse_dsl(*, centered: bool) -> str:
    content_props = {
        "width": 116,
        "layoutWeight": 1,
        "itemMargin": 4,
    }
    if centered:
        content_props["justifyContent"] = "center"
    rows = [
        '["root","Row",{"width":"matchParent","height":"matchParent",'
        '"padding":12,"itemMargin":12},["leftZone","rightZone"]]',
        '["leftZone","Column",{"width":132,"height":126,"padding":8},'
        '["leftContent"]]',
        f'["leftContent","Column",{content_props!r}'.replace("'", '"')
        + ',["leftName","leftStatus"]]',
        '["leftName","Text",{"content":{"path":"/data/left/name"},'
        '"width":116,"fontSize":12,"maxLines":1}]',
        '["leftStatus","Text",{"content":{"path":"/data/left/status"},'
        '"width":116,"fontSize":18,"fontWeight":700,"maxLines":1}]',
        '["rightZone","Column",{"width":132,"height":126,"padding":8},'
        '["rightContent"]]',
        f'["rightContent","Column",{content_props!r}'.replace("'", '"')
        + ',["rightName","rightStatus"]]',
        '["rightName","Text",{"content":{"path":"/data/right/name"},'
        '"width":116,"fontSize":12,"maxLines":1}]',
        '["rightStatus","Text",{"content":{"path":"/data/right/status"},'
        '"width":116,"fontSize":18,"fontWeight":700,"maxLines":1}]',
        '["/data/left/name","项目"]',
        '["/data/left/status","进行中"]',
        '["/data/right/name","同步"]',
        '["/data/right/status","待处理"]',
    ]
    return "\n".join(rows)


def test_legacy_sparse_input_does_not_require_removed_w9_business_heuristic() -> None:
    # PR506不再按旧W9业务名推断居中；此处仅验证兼容输入，不代表视觉验收。
    validate_compact_dsl(
        _w9_sparse_dsl(centered=False),
        task_spec=_w9_sparse_task_spec(),
        card_spec={"suggestSize": "2x4", "dataBindings": []},
    )


def test_accepts_sparse_w9_with_vertical_center_and_layout_weight() -> None:
    validate_compact_dsl(
        _w9_sparse_dsl(centered=True),
        task_spec=_w9_sparse_task_spec(),
        card_spec={"suggestSize": "2x4", "dataBindings": []},
    )


def test_legacy_geometry_does_not_require_removed_w9_business_heuristic() -> None:
    legacy = _w9_sparse_dsl(centered=True)
    legacy = legacy.replace(
        '"padding":12,"itemMargin":12',
        '"padding":8,"itemMargin":8',
    )
    legacy = legacy.replace(
        '"width":132,"height":126,"padding":8',
        '"width":138,"height":134,"padding":12',
    )

    validate_compact_dsl(
        legacy,
        task_spec=_w9_sparse_task_spec(),
        card_spec={"suggestSize": "2x4", "dataBindings": []},
    )


def _fusion_overloaded_dsl() -> str:
    return "\n".join(
        [
            '["root","Column",{"width":"matchParent","height":"matchParent",'
            '"padding":12,"design":"fusion-ball-battery-teal"},'
            '["title","main","status1","status2","action"]]',
            '["title","SingleLineTitle",{"title":"手机电池",'
            '"fontColor":"#FF1F4799"}]',
            '["main","ProgressCircle",{"externalText":68,'
            '"icon":"resources/battery.svg",'
            '"accessibility":{"label":"手机电量百分比"},'
            '"width":52,"height":68,"fontColor":"#FF1F4799",'
            '"fillColor":"#FF1F4799","color":"#FF1F4799",'
            '"backgroundColor":"#331F4799"}]',
            '["status1","Text",{"content":"未充电","fontSize":12}]',
            '["status2","Text",{"content":"健康正常","fontSize":12}]',
            '["action","PillButton",{"label":"电池设置",'
            '"onClick":[{"call":"openBattery","args":{}}]}]',
        ]
    )


def test_accepts_registered_progress_circle_in_fusion_composition() -> None:
    validate_compact_dsl(
        _fusion_overloaded_dsl(),
        task_spec={
            "size": "2x2",
            "eventCandidates": [{"call": "openBattery", "args": {}}],
            "dataModelSchema": {"data": {}},
            "assetCandidates": [
                {
                    "src": "resources/battery.svg",
                    "description": "可染色的电量单色图标",
                }
            ],
        },
        card_spec={"suggestSize": "2x2", "dataBindings": []},
    )


@pytest.mark.parametrize("label_component", ["SingleLineTitle", "SecondaryBody"])
def test_accepts_adjacent_semantic_metric_label(label_component: str) -> None:
    label_props = {"fontColor": "#FF563D99"}
    if label_component == "SingleLineTitle":
        label_props["title"] = "睡眠得分"
    else:
        label_props["role"] = "metadata"
        label_props["items"] = [{"value": "睡眠得分"}]
    rows = [
        ["root", "Column", {"width": "matchParent", "height": "matchParent"}, ["label", "value"]],
        ["label", label_component, label_props],
        [
            "value",
            "EmphasizedData",
            {"value": {"path": "/data/sleep/score"}, "unit": "分", "fontColor": "#FF563D99"},
        ],
        ["/data/sleep/score", 82],
    ]
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    validate_compact_dsl(
        source,
        task_spec={
            "size": "2x4",
            "eventCandidates": [],
            "assetCandidates": [],
            "dataModelSchema": {
                "data": {
                    "sleep": {
                        "score": {
                            "type": "integer",
                            "description": "睡眠得分",
                            "sampleValue": 82,
                        }
                    }
                }
            },
        },
        card_spec={"suggestSize": "2x4"},
    )


def test_rejects_ambiguous_index_value_without_metric_label() -> None:
    dsl = "\n".join(
        [
            '["root","Column",{"width":"matchParent","height":"matchParent"},'
            '["value"]]',
            '["value","Text",{"content":{"path":"/data/health/coldIndex"},'
            '"fontSize":18,"maxLines":1}]',
            '["/data/health/coldIndex","中等"]',
        ]
    )
    with pytest.raises(
        CompactDslValidationError,
        match="add a nearby metric label such as 感冒指数",
    ):
        validate_compact_dsl(
            dsl,
            task_spec={
                "size": "2x2",
                "eventCandidates": [],
                "dataModelSchema": {
                    "data": {
                        "health": {
                            "coldIndex": {
                                "type": "string",
                                "description": "感冒指数等级",
                                "sampleValue": "中等",
                            }
                        }
                    }
                },
                "assetCandidates": [],
            },
            card_spec={"suggestSize": "2x2", "dataBindings": []},
        )


def test_accepts_metric_label_embedded_in_expression() -> None:
    dsl = "\n".join(
        [
            '["root","Column",{"width":"matchParent","height":"matchParent",'
            '"padding":12},["metrics"]]',
            '["metrics","Column",{"width":136,"height":64,"itemMargin":2}'
            ',["air","cold"]]',
            '["air","Text",{"content":"{{ \'空气质量 \' + '
            '${/data/weather/airQuality} }}","fontSize":14,"maxLines":1}]',
            '["cold","Text",{"content":"{{ \'感冒指数 \' + '
            '${/data/weather/coldLevel} }}","fontSize":12,"maxLines":1}]',
            '["/data/weather/airQuality","良"]',
            '["/data/weather/coldLevel","低"]',
        ]
    )
    result = validate_compact_dsl(
        dsl,
        task_spec={
            "size": "2x2",
            "eventCandidates": [],
            "dataModelSchema": {
                "data": {
                    "weather": {
                        "airQuality": {
                            "type": "string",
                            "description": "当天空气质量等级。",
                            "sampleValue": "良",
                        },
                        "coldLevel": {
                            "type": "string",
                            "description": "感冒指数。",
                            "sampleValue": "低",
                        },
                    }
                }
            },
            "assetCandidates": [],
        },
        card_spec={"suggestSize": "2x2"},
    )
    assert not result.warnings


def test_rejects_unit_only_expression_for_ambiguous_metric() -> None:
    dsl = "\n".join(
        [
            '["root","Column",{"width":"matchParent","height":"matchParent",'
            '"padding":12},["value"]]',
            "[\"value\",\"Text\",{\"content\":\"{{ ${/data/weather/windLevel} + '级' }}\","
            "\"fontSize\":14,\"maxLines\":1}]",
            '["/data/weather/windLevel",2]',
        ]
    )
    with pytest.raises(
        CompactDslValidationError,
        match="add a nearby metric label such as 感冒指数",
    ):
        validate_compact_dsl(
            dsl,
            task_spec={
                "size": "2x2",
                "eventCandidates": [],
                "dataModelSchema": {
                    "data": {
                        "weather": {
                            "windLevel": {
                                "type": "integer",
                                "description": "当前风力等级的纯整数。",
                                "sampleValue": 2,
                            }
                        }
                    }
                },
                "assetCandidates": [],
            },
            card_spec={"suggestSize": "2x2"},
        )


def test_design_prompt_contains_no_empty_container_examples() -> None:
    prompt = _DESIGN_PROMPT
    empty_container_lines = re.findall(
        r'^\["[^"]+","(?:Row|Column|Stack)",\{.*\},\[\]\]$',
        prompt,
        flags=re.MULTILINE,
    )

    assert empty_container_lines == []


def test_design_prompt_contains_root_height_hard_gate_examples() -> None:
    prompt = _DESIGN_PROMPT

    assert "## 3.1 一级高度算账硬门禁" in prompt
    assert "63 + 8 + 63 = 134vp" in prompt
    assert "59 + 40 + 36 + 8 × 2 = 151vp" in prompt
    assert "itemMargin 不生效" not in prompt
    assert "两种尺寸固定几何均由语义模板决定" in prompt


def _centered_single_value_hero_task_spec(sample_value: int) -> dict:
    return {
        "size": "2x2",
        "eventCandidates": [{"call": "openAlarm", "args": {}}],
        "dataModelSchema": {
            "data": {
                "countdown": {
                    "days": {
                        "type": "integer",
                        "description": "倒计时剩余天数纯整数",
                        "sampleValue": sample_value,
                    }
                }
            }
        },
        "assetCandidates": [],
    }


def _centered_single_value_hero_dsl(
    *,
    value_font: int,
    unit_font: int,
    include_safe_box: bool = True,
    value_height: int | None = None,
) -> str:
    content_children = '["hero_box"]' if include_safe_box else '["value_row"]'
    value_height_property = f',"height":{value_height}' if value_height else ""
    rows = [
        '["root","Column",{"width":"matchParent","height":"matchParent",'
        '"padding":12,"itemMargin":4,"justifyContent":"start",'
        '"alignItems":"center"},["title_area","content_area","action_area"]]',
        '["title_area","SingleLineTitle",{"title":"广州马拉松",'
        '"fontColor":"#FF9A4F19"}]',
        '["content_area","Column",{"width":126,"layoutWeight":1,'
        '"justifyContent":"center","alignItems":"center"},'
        f'{content_children}',
    ]
    if include_safe_box:
        rows.append(
            '["hero_box","Column",{"width":106,"height":58,'
            '"justifyContent":"center","alignItems":"center"},["value_row"]]'
        )
    rows.extend(
        [
            '["value_row","Row",{"width":106,"itemMargin":2,'
            '"justifyContent":"center","alignItems":"bottom"},'
            '["value","unit"]]',
            '["value","Text",{"content":{"path":"/data/countdown/days"},'
            f'"fontSize":{value_font},"fontWeight":700,"maxLines":1'
            f'{value_height_property}}}]',
            '["unit","Text",{"content":"天",'
            f'"fontSize":{unit_font},"fontWeight":400,'
            '"padding":{"bottom":4},"maxLines":1}]',
            '["action_area","Column",{"width":126,"height":36},["action"]]',
            '["action","PillButton",{"label":"打开闹钟",'
            '"onClick":'
            '[{"call":"openAlarm","args":{}}]}]',
            '["/data/countdown/days",30]',
        ]
    )
    return "\n".join(rows)


def test_design_prompt_routes_single_core_value_to_center_layout() -> None:
    prompt = _DESIGN_PROMPT

    assert "## 11.5 2x2 组合落地" in prompt
    assert "| `S-center` | 单一核心内容 |" in prompt
    assert "只承载一个无需标题即可理解的 `DataDisplay`" in prompt
    assert "2x2 单数值 Hero 安全盒前置约束" not in prompt


def test_accepts_centered_single_value_hero_inside_106_by_58_safe_box() -> None:
    result = validate_compact_dsl(
        _centered_single_value_hero_dsl(value_font=38, unit_font=16),
        task_spec=_centered_single_value_hero_task_spec(30),
        card_spec={"suggestSize": "2x2", "dataBindings": []},
    )

    assert not result.warnings


def test_legacy_readout_does_not_require_removed_hero_box_heuristic() -> None:
    validate_compact_dsl(
        _centered_single_value_hero_dsl(
            value_font=38,
            unit_font=16,
            include_safe_box=False,
        ),
        task_spec=_centered_single_value_hero_task_spec(30),
        card_spec={"suggestSize": "2x2", "dataBindings": []},
    )


def test_rejects_centered_single_value_hero_that_exceeds_width_pressure() -> None:
    source = _centered_single_value_hero_dsl(value_font=38, unit_font=16).replace(
        '["value_row","Row",{"width":106',
        '["value_row","Row",{"width":8',
    )
    with pytest.raises(
        CompactDslValidationError,
        match="text width overflow",
    ):
        validate_compact_dsl(
            source,
            task_spec=_centered_single_value_hero_task_spec(1000),
            card_spec={"suggestSize": "2x2", "dataBindings": []},
        )


def test_accepts_centered_single_value_hero_after_font_downgrade() -> None:
    result = validate_compact_dsl(
        _centered_single_value_hero_dsl(value_font=30, unit_font=14),
        task_spec=_centered_single_value_hero_task_spec(1000),
        card_spec={"suggestSize": "2x2", "dataBindings": []},
    )

    assert not result.warnings


def test_rejects_centered_single_value_hero_that_exceeds_height_pressure() -> None:
    with pytest.raises(
        CompactDslValidationError,
        match=r"vertical layout requires at least 64vp within 58vp; it overflows by 6vp",
    ):
        validate_compact_dsl(
            _centered_single_value_hero_dsl(
                value_font=38,
                unit_font=16,
                value_height=64,
            ),
            task_spec=_centered_single_value_hero_task_spec(30),
            card_spec={"suggestSize": "2x2", "dataBindings": []},
        )


def test_legacy_peer_readouts_do_not_use_removed_business_font_heuristic() -> None:
    source = "\n".join(
        [
            '["root","Column",{"width":"matchParent","height":"matchParent",'
            '"padding":12,"itemMargin":4},["value_row","minimum"]]',
            '["value_row","Row",{"width":126,"height":40},["maximum","unit"]]',
            '["maximum","Text",{"content":{"path":"/data/healthSport/max"},'
            '"fontSize":30,"fontWeight":700,"maxLines":1}]',
            '["unit","Text",{"content":"次/分钟","fontSize":12,'
            '"fontWeight":500,"maxLines":1}]',
            '["minimum","Text",{"content":"{{ \'最低 \' + '
            '${/data/healthSport/min} + \'次/分钟\' }}","height":18,'
            '"fontSize":12,"fontWeight":400,"maxLines":1}]',
            '["/data/healthSport/max",168]',
            '["/data/healthSport/min",96]',
        ]
    )
    task_spec = {
        "size": "2x2",
        "dataModelSchema": {
            "data": {
                "healthSport": {
                    "max": {"type": "integer"},
                    "min": {"type": "integer"},
                }
            }
        },
        "assetCandidates": [],
        "eventCandidates": [],
    }

    validate_compact_dsl(
        source,
        task_spec=task_spec,
        card_spec={"suggestSize": "2x2", "dataBindings": []},
    )


def test_accepts_compact_auxiliary_metrics_with_graphical_action() -> None:
    source = "\n".join(
        [
            '["root","Column",{"width":"matchParent","height":"matchParent",'
            '"padding":12,"itemMargin":4},["value_row","metrics","action_area"]]',
            '["value_row","Row",{"width":136,"height":40},["steps","unit"]]',
            '["steps","Text",{"content":{"path":"/data/healthSport/steps"},'
            '"fontSize":30,"fontWeight":700,"maxLines":1}]',
            '["unit","Text",{"content":"步","fontSize":12,'
            '"fontWeight":500,"maxLines":1}]',
            '["metrics","Row",{"width":136,"height":18,"itemMargin":4},'
            '["calorie","separator","heart_rate"]]',
            '["calorie","Text",{"content":{"path":"/data/healthSport/calorieText"},'
            '"fontSize":12,"fontWeight":400,"maxLines":1}]',
            '["separator","Text",{"content":"|","fontSize":12,'
            '"fontWeight":400,"maxLines":1}]',
            '["heart_rate","Text",{"content":{"path":"/data/healthSport/heartRateText"},'
            '"fontSize":12,"fontWeight":400,"maxLines":1}]',
            '["action_area","Column",{"width":136,"height":36,'
            '"alignItems":"center"},["action"]]',
            '["action","PillButton",{"label":"打开歌单",'
            '"icon":"resources/base/media/music_fill.svg",'
            '"onClick":[{"call":"openMusic","args":{}}]}]',
            '["/data/healthSport/steps",2319]',
            '["/data/healthSport/calorieText","260 千卡"]',
            '["/data/healthSport/heartRateText","135次/分钟"]',
        ]
    )
    result = validate_compact_dsl(
        source,
        task_spec={
            "size": "2x2",
            "eventCandidates": [{"call": "openMusic", "args": {}}],
            "dataModelSchema": {
                "data": {
                    "healthSport": {
                        "steps": {"type": "integer"},
                        "calorieText": {"type": "string"},
                        "heartRateText": {"type": "string"},
                    }
                }
            },
            "assetCandidates": [
                {
                    "src": "resources/base/media/music_fill.svg",
                    "description": "音乐入口",
                }
            ],
        },
        card_spec={"suggestSize": "2x2", "dataBindings": []},
    )
    assert not result.warnings
