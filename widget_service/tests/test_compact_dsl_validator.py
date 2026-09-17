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
    assert "20 + 64 + 64 + 8 × 2 = 164 > 136" in prompt
    assert "64 + 40 + 36 + 8 × 2 = 156 > 136" in prompt
    assert "itemMargin 不生效" not in prompt
    assert "两者可以同时设置" in prompt


def _dual_action_task_spec() -> dict:
    return {
        "userQuery": "查看电量，并提供省电和回家两个入口",
        "size": "2x2",
        "eventCandidates": [
            {"call": "clickToIntent", "args": {"intentName": "PowerSaving"}},
            {"call": "clickToIntent", "args": {"intentName": "NavigateHome"}},
        ],
        "dataModelSchema": {
            "data": {
                "phoneBattery": {
                    "batterySOC": {"type": "integer"},
                    "chargingStatusDesc": {"type": "string"},
                }
            }
        },
        "assetCandidates": [],
    }


def _dual_action_s3_source(*, summary_font_size: int = 12) -> str:
    return "\n".join(
        [
            '["root","Column",{"width":160,"height":160,"padding":12,'
            '"itemMargin":8},["header_area","action_area"]]',
            '["header_area","Column",{"width":136,"height":48},'
            '["business_title","data_summary"]]',
            '["business_title","Text",{"content":"剩余电量","fontSize":14,'
            '"fontWeight":700,"maxLines":1}]',
            '["data_summary","Text",{"content":"68% | 未充电","fontSize":'
            f'{summary_font_size},"fontWeight":400,"maxLines":1}}]',
            '["action_area","Column",{"width":136,"itemMargin":8},'
            '["cta_save","cta_home"]]',
            '["cta_save","ActionUnit",{"state":"capsule","label":"省电模式",'
            '"onClick":[{"call":"clickToIntent","args":'
            '{"intentName":"PowerSaving"}}]}]',
            '["cta_home","ActionUnit",{"state":"capsule","label":"导航回家",'
            '"onClick":[{"call":"clickToIntent","args":'
            '{"intentName":"NavigateHome"}}]}]',
        ]
    )


def test_accepts_compact_s3_single_business_dual_action_layout() -> None:
    result = validate_compact_dsl(
        _dual_action_s3_source(),
        task_spec=_dual_action_task_spec(),
        card_spec={"suggestSize": "2x2", "dataBindings": []},
    )

    assert result.warnings == ()


def test_rejects_large_data_text_in_s3_dual_action_layout() -> None:
    with pytest.raises(
        CompactDslValidationError,
        match="one 12fp/400 merged data summary",
    ):
        validate_compact_dsl(
            _dual_action_s3_source(summary_font_size=38),
            task_spec=_dual_action_task_spec(),
            card_spec={"suggestSize": "2x2", "dataBindings": []},
        )
