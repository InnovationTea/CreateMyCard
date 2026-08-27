# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import json

from models.capability import DataCapability
from models.generation import CandidateDataBinding
from services.card_validation import validate_card
from services.card_validation.display_unit_rules import repair_repeated_display_units
from services.generation_pipeline import DslProcessingContext, StandardA2UIProcessor
from services.task_spec_builder import TaskSpecBuilder


def _capability(unit_included: bool) -> DataCapability:
    return DataCapability(
        id="Battery",
        description="测试电量",
        outputSchema={
            "type": "object",
            "properties": {
                "level": {
                    "type": "string" if unit_included else "integer",
                    "description": "测试电量字段",
                    "sampleValue": "68%" if unit_included else 68,
                    "displayUnits": ["%"],
                    "unitIncluded": unit_included,
                }
            },
        },
    )


def _card_spec() -> dict:
    return {
        "dataBindings": [
            {
                "capabilityId": "Battery",
                "arguments": {},
                "writeResultTo": "/data/battery",
            }
        ]
    }


def _dsl(content: str, *, sibling_units: int = 0) -> str:
    children = ["value", *[f"unit_{index}" for index in range(sibling_units)]]
    components = [
        {"id": "root", "component": "Row", "children": children},
        {"id": "value", "component": "Text", "content": content},
    ]
    components.extend(
        {"id": f"unit_{index}", "component": "Text", "content": "%"}
        for index in range(sibling_units)
    )
    return "\n".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":"))
        for row in [
            {
                "version": "v0.9",
                "createSurface": {
                    "surfaceId": "card",
                    "catalogId": "ohos.a2ui.extended.catalog.form",
                },
            },
            {
                "version": "v0.9",
                "updateComponents": {
                    "surfaceId": "card",
                    "root": "root",
                    "components": components,
                },
            },
            {
                "version": "v0.9",
                "updateDataModel": {
                    "surfaceId": "card",
                    "path": "/",
                    "value": {"data": {"battery": {"level": 68}}},
                },
            },
        ]
    )


def test_task_spec_builder_does_not_project_display_unit_metadata():
    capability = _capability(unit_included=False)
    task_spec = TaskSpecBuilder().build(
        user_query="电量卡片",
        size="2x2",
        effective_bindings=[
            CandidateDataBinding(
                capabilityId="Battery",
                writeResultTo="/data/battery",
                candidateOutputFields=["/level"],
            )
        ],
        effective_data_capabilities=[capability],
        event_candidates=[],
        asset_candidates=[],
    )

    leaf = task_spec.dataModelSchema["data"]["battery"]["level"]
    assert leaf == {
        "type": "integer",
        "description": "测试电量字段",
        "sampleValue": 68,
    }


def test_standard_processor_repairs_repeated_inline_unit():
    source = _dsl("{{ ${/data/battery/level} + '%' }}")
    context = DslProcessingContext(
        size="2x2",
        card_spec=_card_spec(),
        task_spec={"dataModelSchema": {}},
        protocol_profile={},
        data_capabilities=[_capability(unit_included=True)],
    )

    result = StandardA2UIProcessor().process(source, context)

    assert result.source_dsl == source
    assert "{{ ${/data/battery/level} }}" in result.standard_dsl
    assert "+ '%'" not in result.standard_dsl


def test_repair_collapses_repeated_unit_and_keeps_one_for_raw_number():
    repaired = repair_repeated_display_units(
        _dsl("{{ ${/data/battery/level} + '%' + '%' }}"),
        _card_spec(),
        [_capability(unit_included=False)],
    )

    assert "{{ ${/data/battery/level} + '%' }}" in repaired


def test_repair_removes_redundant_sibling_unit_for_formatted_text():
    repaired = repair_repeated_display_units(
        _dsl("{{ ${/data/battery/level} }}", sibling_units=1),
        _card_spec(),
        [_capability(unit_included=True)],
    )
    update = json.loads(repaired.splitlines()[1])["updateComponents"]

    assert update["components"][0]["children"] == ["value"]
    assert {item["id"] for item in update["components"]} == {"root", "value"}


def test_validator_reports_missing_unit_for_raw_number():
    reporter = validate_card(
        artifact={
            "genui": _dsl("{{ ${/data/battery/level} }}"),
            "cardSpec": _card_spec(),
            "effectiveCapabilities": {
                "data": [_capability(unit_included=False).model_dump(mode="json")]
            },
        }
    )

    assert reporter.has_code("DISPLAY_UNIT_MISSING")


def test_validator_reports_duplicate_unit_for_formatted_text():
    reporter = validate_card(
        artifact={
            "genui": _dsl("{{ ${/data/battery/level} + '%' }}"),
            "cardSpec": _card_spec(),
            "effectiveCapabilities": {
                "data": [_capability(unit_included=True).model_dump(mode="json")]
            },
        }
    )

    assert reporter.has_code("DISPLAY_UNIT_DUPLICATED")


def test_validator_accepts_raw_number_with_separate_unit_text():
    reporter = validate_card(
        artifact={
            "genui": _dsl("{{ ${/data/battery/level} }}", sibling_units=1),
            "cardSpec": _card_spec(),
            "effectiveCapabilities": {
                "data": [_capability(unit_included=False).model_dump(mode="json")]
            },
        }
    )

    assert not reporter.has_code("DISPLAY_UNIT_MISSING", "DISPLAY_UNIT_DUPLICATED")
