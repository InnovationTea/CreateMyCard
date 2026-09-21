# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.

import re
from pathlib import Path

import pytest

from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.generation_pipeline import (
    DslProcessingContext,
    DslProcessorKind,
    get_dsl_processor,
)

_DESIGN_PROMPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "cloud"
    / "data"
    / "protocol_profiles"
    / "design-compact-dsl"
    / "PROMPT.md"
)

_INVALID_COMPACT_DSL = "\n".join(
    [
        '["root","Column",{"width":160,"height":160},["temperature"]]',
        '["temperature","Text",'
        '{"content":"{{ \'/data/weather/current/temperatureText\' }}"}]',
        '["/data/weather/current/temperatureText","26℃"]',
    ]
)

_NARROW_GRAPHICAL_ACTION_DSL = "\n".join(
    [
        '["root","Column",{"width":"matchParent","height":"matchParent"},["action_area"]]',
        '["action_area","Column",{"width":136,"height":36},["action"]]',
        '["action","Row",{"width":96,"height":36,"padding":8,"borderRadius":18,'
        '"itemMargin":8,"justifyContent":"center","alignItems":"center",'
        '"onClick":[{"call":"clickToIntent","args":{"intentName":"Open"}}]},'
        '["icon","label"]]',
        '["icon","Image",{"src":"resources/icon.svg","width":20,"height":20,'
        '"objectFit":"contain"}]',
        '["label","Text",{"content":"打开","fontSize":14,"maxLines":1}]',
    ]
)


def _narrow_graphical_action_task_spec() -> dict:
    return {
        "size": "2x2",
        "eventCandidates": [
            {
                "call": "clickToIntent",
                "args": {"intentName": "Open"},
            }
        ],
        "dataModelSchema": {"data": {}},
        "assetCandidates": [{"src": "resources/icon.svg"}],
    }


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
    assert len(result.errors) == 2
    assert all(item.stage == "validation" for item in result.errors)
    assert all(
        item.code == "COMPACT_DSL_VALIDATION_FAILED"
        for item in result.errors
    )


@pytest.mark.parametrize("component_type", ["Row", "Column", "List", "Stack"])
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


def test_rejects_narrow_2x2_graphical_action_without_parent_centering() -> None:
    with pytest.raises(
        CompactDslValidationError,
        match=(
            r"2x2 narrow graphical action Row action must be centered by parent "
            r"Column action_area"
        ),
    ):
        validate_compact_dsl(
            _NARROW_GRAPHICAL_ACTION_DSL,
            task_spec=_narrow_graphical_action_task_spec(),
            card_spec={"dataBindings": []},
        )


def test_accepts_narrow_2x2_graphical_action_with_parent_centering() -> None:
    dsl = _NARROW_GRAPHICAL_ACTION_DSL.replace(
        '"width":136,"height":36',
        '"width":136,"height":36,"alignItems":"center"',
        1,
    )

    validate_compact_dsl(
        dsl,
        task_spec=_narrow_graphical_action_task_spec(),
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
        "width": 114,
        "layoutWeight": 1,
        "itemMargin": 4,
    }
    if centered:
        content_props["justifyContent"] = "center"
    rows = [
        '["root","Row",{"width":"matchParent","height":"matchParent",'
        '"padding":8,"itemMargin":8},["leftZone","rightZone"]]',
        '["leftZone","Column",{"width":138,"height":134,"padding":12},'
        '["leftContent"]]',
        f'["leftContent","Column",{content_props!r}'.replace("'", '"')
        + ',["leftName","leftStatus"]]',
        '["leftName","Text",{"content":{"path":"/data/left/name"},'
        '"width":120,"fontSize":12,"maxLines":1}]',
        '["leftStatus","Text",{"content":{"path":"/data/left/status"},'
        '"width":120,"fontSize":18,"fontWeight":700,"maxLines":1}]',
        '["rightZone","Column",{"width":138,"height":134,"padding":12},'
        '["rightContent"]]',
        f'["rightContent","Column",{content_props!r}'.replace("'", '"')
        + ',["rightName","rightStatus"]]',
        '["rightName","Text",{"content":{"path":"/data/right/name"},'
        '"width":120,"fontSize":12,"maxLines":1}]',
        '["rightStatus","Text",{"content":{"path":"/data/right/status"},'
        '"width":120,"fontSize":18,"fontWeight":700,"maxLines":1}]',
        '["/data/left/name","项目"]',
        '["/data/left/status","进行中"]',
        '["/data/right/name","同步"]',
        '["/data/right/status","待处理"]',
    ]
    return "\n".join(rows)


def test_rejects_sparse_w9_without_vertical_center_and_layout_weight() -> None:
    with pytest.raises(
        CompactDslValidationError,
        match=(
            r"2x4 W9 sparse backboard leftZone.*layoutWeight 1.*"
            r"justifyContent center"
        ),
    ):
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


def _fusion_overloaded_dsl() -> str:
    return "\n".join(
        [
            '["root","Column",{"width":"matchParent","height":"matchParent",'
            '"padding":12,"design":"fusion-ball-battery-teal"},'
            '["title","main","status1","status2","action"]]',
            '["title","Row",{"width":136,"height":20},["titleText","titleIcon"]]',
            '["titleText","Text",{"content":"手机电池","fontSize":12}]',
            '["titleIcon","Image",{"src":"resources/battery.svg",'
            '"width":20,"height":20,"objectFit":"contain"}]',
            '["main","Stack",{"width":52,"height":52},["ring"]]',
            '["ring","Progress",{"type":"ring","width":52,"height":52,'
            '"value":68,"total":100}]',
            '["status1","Text",{"content":"未充电","fontSize":12}]',
            '["status2","Text",{"content":"健康正常","fontSize":12}]',
            '["action","Button",{"label":"电池设置","width":120,"height":36,',
            '"onClick":[{"call":"openBattery","args":{}}]}]',
        ]
    )


def test_rejects_overloaded_fusion_composition() -> None:
    with pytest.raises(
        CompactDslValidationError,
        match="must not combine a title/auxiliary icon",
    ):
        validate_compact_dsl(
            _fusion_overloaded_dsl(),
            task_spec={
                "size": "2x2",
                "eventCandidates":[{"call":"openBattery","args":{}}],
                "dataModelSchema": {"data": {}},
                "assetCandidates": [{"src": "resources/battery.svg"}],
            },
            card_spec={"suggestSize": "2x2", "dataBindings": []},
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


def test_design_prompt_contains_no_empty_container_examples() -> None:
    prompt = _DESIGN_PROMPT_PATH.read_text(encoding="utf-8")
    empty_container_lines = re.findall(
        r'^\["[^"]+","(?:Row|Column|List|Stack)",\{.*\},\[\]\]$',
        prompt,
        flags=re.MULTILINE,
    )

    assert empty_container_lines == []


def test_design_prompt_contains_root_height_hard_gate_examples() -> None:
    prompt = _DESIGN_PROMPT_PATH.read_text(encoding="utf-8")

    assert "## 3.1 一级高度算账硬门禁" in prompt
    assert "20 + 59 + 59 + 8 × 2 = 154 > 134" in prompt
    assert "20 + 66 + 36 + 36 = 158 > 126" in prompt
    assert "itemMargin 不生效" not in prompt
    assert "两者可以同时设置" in prompt


def test_rejects_large_hero_for_peer_metrics_on_150vp_card() -> None:
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

    with pytest.raises(
        CompactDslValidationError,
        match="multiple peer quantitative fields",
    ):
        validate_compact_dsl(
            source,
            task_spec=task_spec,
            card_spec={"suggestSize": "2x2", "dataBindings": []},
        )
