# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Semantic Compact component binding-contract regression tests."""

from __future__ import annotations

import json

import pytest

from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.compact_component_bindings import (
    COMPACT_COMPONENT_BINDING_CONTRACTS,
    collect_compact_component_binding_errors,
)
from services.compact_dsl_a2ui_converter import (
    MODEL_COMPACT_INPUT_COMPONENT_TYPES,
    CompactDslConversionError,
    convert_compact_dsl_to_a2ui,
    repair_compact_dsl_binding_paths,
)
from services.multi_step_generation.jsx_to_a2ui.catalog.bindings import (
    BINDABLE_PROP_TYPES,
)
from services.multi_step_generation.jsx_to_a2ui.catalog.contracts import (
    collect_jsx_component_errors,
)
from services.multi_step_generation.jsx_to_a2ui.parser.jsx_ast import JSXElement


def _serialize(rows: list[list[object]]) -> str:
    values: list[str] = []
    for row in rows:
        values.append(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
    return "\n".join(values)


def test_binding_registry_covers_every_model_semantic_component() -> None:
    semantic_components = MODEL_COMPACT_INPUT_COMPONENT_TYPES - {
        "Row",
        "Column",
        "Stack",
        "Layout",
        "Region",
        "Group",
    }

    assert semantic_components == set(COMPACT_COMPONENT_BINDING_CONTRACTS)


@pytest.mark.parametrize(
    ("component_type", "props"),
    [
        (
            "EmphasizedData",
            {"unit": {"path": "/data/metric/unit"}},
        ),
        (
            "TableText",
            {"items": [{"label": {"path": "/data/items/0/name"}, "value": "1"}]},
        ),
        (
            "TextBlock",
            {"items": [{"label": {"path": "/data/items/0/name"}, "value": "1"}]},
        ),
        (
            "ProgressCircleSingle",
            {"label": {"path": "/data/device/name"}},
        ),
        (
            "EventCard",
            {"items": [{"title": {"path": "/data/events/0/title"}}]},
        ),
    ],
)
def test_allows_registered_nested_path_bindings(
    component_type: str,
    props: dict[str, object],
) -> None:
    errors = collect_compact_component_binding_errors(
        "subject",
        component_type,
        props,
    )

    assert errors == []


def test_text_block_label_accepts_path_binding_and_expression() -> None:
    compact_dsl = _serialize(
        [
            ["root", "Column", {}, ["details"]],
            [
                "details",
                "TextBlock",
                {
                    "items": [
                        {
                            "label": {"path": "/data/items/0/name"},
                            "value": {"path": "/data/items/0/value"},
                        },
                        {
                            "label": "{{ '项目 ' + ${/data/items/1/name} }}",
                            "value": {"path": "/data/items/1/value"},
                        },
                    ]
                },
            ],
            ["/data/items/0/name", "照明"],
            ["/data/items/0/value", "18千瓦时"],
            ["/data/items/1/name", "空调"],
            ["/data/items/1/value", "34千瓦时"],
        ]
    )

    converted = convert_compact_dsl_to_a2ui(compact_dsl, size="2x4")
    update = json.loads(converted.splitlines()[1])["updateComponents"]
    components = {item["id"]: item for item in update["components"]}

    assert components["details_item0_label"]["content"] == (
        "{{ ${/data/items/0/name} }}"
    )
    assert components["details_item1_label"]["content"] == (
        "{{ '项目 ' + ${/data/items/1/name} }}"
    )


def test_emphasis_text_secondary_accepts_ordered_path_bindings() -> None:
    secondary_text = [
        {"path": "/data/weather/location/prefectureName"},
        {"path": "/data/weather/location/districtName"},
    ]
    errors = collect_compact_component_binding_errors(
        "weather",
        "EmphasisText",
        {"secondaryText": secondary_text},
    )

    assert errors == []

    compact_dsl = _serialize(
        [
            ["root", "Column", {}, ["weather"]],
            [
                "weather",
                "EmphasisText",
                {
                    "mainText": {"path": "/data/weather/current/condition"},
                    "secondaryText": secondary_text,
                },
            ],
            ["/data/weather/current/condition", "多云"],
            ["/data/weather/location/prefectureName", "上海市"],
            ["/data/weather/location/districtName", "青浦区"],
        ]
    )
    converted = convert_compact_dsl_to_a2ui(compact_dsl, size="2x2")
    update = json.loads(converted.splitlines()[1])["updateComponents"]
    components = {item["id"]: item for item in update["components"]}

    assert components["weather_secondary"]["content"] == (
        "{{ ${/data/weather/location/prefectureName} + ' | ' + "
        "${/data/weather/location/districtName} }}"
    )


@pytest.mark.parametrize(
    "secondary_text",
    [
        [{"path": "/data/only"}],
        [{"path": "/data/left"}, "静态值"],
    ],
)
def test_emphasis_text_secondary_rejects_invalid_binding_arrays(
    secondary_text: list[object],
) -> None:
    compact_dsl = _serialize(
        [
            ["root", "Column", {}, ["status"]],
            [
                "status",
                "EmphasisText",
                {"mainText": "状态", "secondaryText": secondary_text},
            ],
        ]
    )

    with pytest.raises(CompactDslConversionError, match="EmphasisText.secondaryText"):
        convert_compact_dsl_to_a2ui(compact_dsl, size="2x2")


@pytest.mark.parametrize(
    ("component_type", "props", "prop_path"),
    [
        (
            "DataDisplay",
            {"label": "{{ ${/data/name} }}"},
            "label",
        ),
        (
            "SecondaryBody",
            {"items": [{"label": {"path": "/data/label"}, "value": "内容"}]},
            "items[].label",
        ),
        (
            "H_BarChart",
            {"items": [{"label": "{{ ${/data/name} }}", "valueUnit": "1"}]},
            "items[].label",
        ),
        (
            "TopTextBottomValue",
            {"items": [{"label": {"path": "/data/name"}, "value": 1}]},
            "items[].label",
        ),
        (
            "NumericRatioStack",
            {"items": [{"value": 68, "unit": {"path": "/data/metric/unit"}}]},
            "items[].unit",
        ),
        (
            "PillButton",
            {"label": "{{ ${/data/actionName} }}"},
            "label",
        ),
    ],
)
def test_rejects_bindings_on_static_semantic_props(
    component_type: str,
    props: dict[str, object],
    prop_path: str,
) -> None:
    errors = collect_compact_component_binding_errors(
        "subject",
        component_type,
        props,
    )

    assert errors == [
        f"component subject.props.{prop_path}: "
        f"{component_type}.{prop_path} only accepts a static value."
    ]


def test_rejects_direct_boolean_path_but_allows_boolean_expression() -> None:
    schema_types = {"/data/device/connected": "boolean"}

    direct_errors = collect_compact_component_binding_errors(
        "title",
        "SingleLineTitle",
        {"title": {"path": "/data/device/connected"}},
        schema_type_resolver=schema_types.get,
    )
    expression_errors = collect_compact_component_binding_errors(
        "title",
        "SingleLineTitle",
        {"title": "{{ ${/data/device/connected} ? '已连接' : '未连接' }}"},
        schema_type_resolver=schema_types.get,
    )

    assert "schema type boolean" in direct_errors[0]
    assert expression_errors == []


def test_progress_circle_driver_accepts_path_and_expression() -> None:
    path_errors = collect_compact_component_binding_errors(
        "progress",
        "ProgressCircle",
        {"externalText": {"path": "/data/battery/percent"}},
    )
    expression_errors = collect_compact_component_binding_errors(
        "progress",
        "ProgressCircle",
        {"externalText": "{{ ${/data/current} / ${/data/total} * 100 }}"},
    )
    line_errors = collect_compact_component_binding_errors(
        "line",
        "ProgressLine2",
        {"value": "{{ ${/data/current} / ${/data/total} * 100 }}"},
    )

    assert path_errors == []
    assert expression_errors == []
    assert "does not accept expression bindings" in line_errors[0]


def test_data_display_supporting_text_accepts_dynamic_binding() -> None:
    path_errors = collect_compact_component_binding_errors(
        "display",
        "DataDisplay",
        {"supportingText": {"path": "/data/weather/updatedAt"}},
    )
    expression_errors = collect_compact_component_binding_errors(
        "display",
        "DataDisplay",
        {
            "supportingText": (
                "{{ '更新 ' + ${/data/weather/updatedAt} }}"
            )
        },
    )

    assert path_errors == []
    assert expression_errors == []
    assert "supportingText" in BINDABLE_PROP_TYPES["DataDisplay"]

    jsx_errors = collect_jsx_component_errors(
        JSXElement(
            "DataDisplay",
            {
                "label": "天气预警",
                "value": "大风蓝色预警",
                "supportingText": "10:30 更新",
                "variant": "textConclusion",
            },
        )
    )
    assert jsx_errors == []


def test_data_display_ignores_legacy_font_size_and_uses_text_recipe() -> None:
    compact_dsl = _serialize(
        [
            ["root", "Column", {}, ["display"]],
            [
                "display",
                "DataDisplay",
                {
                    "icon": "resources/base/media/air_fill.svg",
                    "value": {"path": "/data/weather/alert"},
                    "supportingText": (
                        "{{ '更新 ' + ${/data/weather/updatedAt} }}"
                    ),
                    "fontSize": 48,
                    "fontColor": "#FF1F4799",
                },
            ],
            ["/data/weather/alert", "大风蓝色预警"],
            ["/data/weather/updatedAt", "10:30"],
        ]
    )

    converted = convert_compact_dsl_to_a2ui(compact_dsl, size="2x2")
    update_components = json.loads(converted.splitlines()[1])["updateComponents"]
    components = {
        component["id"]: component
        for component in update_components["components"]
    }

    assert components["display_value"]["content"] == (
        "{{ ${/data/weather/alert} }}"
    )
    assert components["display"]["children"] == [
        "display_icon",
        "display_value_area",
        "display_supporting",
    ]
    assert components["display_icon"]["component"] == "Image"
    assert components["display_icon"]["src"] == "resources/base/media/air_fill.svg"
    assert components["display_icon"]["styles"]["width"] == 18
    assert components["display_icon"]["styles"]["height"] == 18
    assert components["display"]["styles"]["height"] == 122
    assert components["display_value"]["styles"]["fontSize"] == 24
    assert components["display_value_area"]["component"] == "Column"
    assert components["display_value_area"]["children"] == ["display_value"]
    assert components["display_value_area"]["styles"]["height"] == 60
    assert components["display_value_area"]["styles"]["justifyContent"] == "center"
    assert "height" not in components["display_value"]["styles"]
    assert components["display_value"]["styles"]["lineHeight"] == 1.25
    assert components["display_value"]["styles"]["maxLines"] == 2
    assert components["display_supporting"]["content"] == (
        "{{ '更新 ' + ${/data/weather/updatedAt} }}"
    )
    assert components["display_supporting"]["styles"]["margin"]["top"] == 8
    assert components["display_supporting"]["styles"]["flexShrink"] == 0


def test_data_display_accepts_one_character_path_bound_text() -> None:
    compact_dsl = _serialize(
        [
            ["root", "Column", {}, ["display"]],
            [
                "display",
                "DataDisplay",
                {
                    "label": "结论",
                    "value": {"path": "/data/status"},
                    "supportingText": "当前状态",
                    "fontColor": "#FF1F4799",
                },
            ],
            ["/data/status", "优"],
        ]
    )

    convert_compact_dsl_to_a2ui(compact_dsl, size="2x2")


def test_data_display_rejects_text_over_eight_characters() -> None:
    value = "这是超过八个字的文本结论"
    compact_dsl = _serialize(
        [
            ["root", "Column", {}, ["display"]],
            [
                "display",
                "DataDisplay",
                {
                    "label": "结论",
                    "value": value,
                    "supportingText": "当前状态",
                    "fontColor": "#FF1F4799",
                },
            ],
        ]
    )

    with pytest.raises(CompactDslConversionError, match="requires 1 to 8 characters"):
        convert_compact_dsl_to_a2ui(compact_dsl, size="2x2")


def test_validator_checks_semantic_prop_binding_before_expansion() -> None:
    compact_dsl = _serialize(
        [
            ["root", "Column", {}, ["display"]],
            [
                "display",
                "DataDisplay",
                {
                    "label": "{{ ${/data/name} }}",
                    "value": 3,
                    "supportingText": "天",
                    "fontColor": "#FF1F4799",
                },
            ],
            ["/data/name", "运动会"],
        ]
    )

    with pytest.raises(CompactDslValidationError, match="DataDisplay.label only accepts"):
        validate_compact_dsl(
            compact_dsl,
            task_spec={
                "size": "2x2",
                "dataModelSchema": {"data": {"name": {"type": "string"}}},
                "assetCandidates": [],
                "eventCandidates": [],
            },
            card_spec={"suggestSize": "2x2", "dataBindings": []},
            enforce_model_component_types=True,
        )


def test_validator_rejects_boolean_path_for_visible_text_prop() -> None:
    compact_dsl = _serialize(
        [
            ["root", "Column", {}, ["title"]],
            [
                "title",
                "SingleLineTitle",
                {
                    "title": {"path": "/data/device/connected"},
                    "fontColor": "#FF1F4799",
                },
            ],
            ["/data/device/connected", True],
        ]
    )

    with pytest.raises(CompactDslValidationError, match="schema type boolean"):
        validate_compact_dsl(
            compact_dsl,
            task_spec={
                "size": "2x2",
                "dataModelSchema": {
                    "data": {
                        "device": {
                            "connected": {"type": "boolean"},
                        }
                    }
                },
                "assetCandidates": [],
                "eventCandidates": [],
            },
            card_spec={"suggestSize": "2x2", "dataBindings": []},
            enforce_model_component_types=True,
        )


def test_converter_preserves_dynamic_unit_and_table_label_bindings() -> None:
    compact_dsl = _serialize(
        [
            ["root", "Column", {}, ["metric", "details"]],
            [
                "metric",
                "EmphasizedData",
                {
                    "value": {"path": "/data/metric/value"},
                    "unit": {"path": "/data/metric/unit"},
                    "fontColor": "#FF1F4799",
                },
            ],
            [
                "details",
                "TableText",
                {
                    "items": [
                        {
                            "label": {"path": "/data/items/0/name"},
                            "value": {"path": "/data/items/0/value"},
                        },
                        {"label": "次项", "value": "2"},
                    ],
                    "fontColor": "#FF1F4799",
                },
            ],
            ["/data/metric/value", 68],
            ["/data/metric/unit", "%"],
            ["/data/items/0/name", "主项"],
            ["/data/items/0/value", "1"],
        ]
    )

    converted = convert_compact_dsl_to_a2ui(compact_dsl, size="2x4")
    update_components = json.loads(converted.splitlines()[1])["updateComponents"]
    components = {
        component["id"]: component
        for component in update_components["components"]
    }

    assert components["metric_unit"]["content"] == "{{ ${/data/metric/unit} }}"
    assert components["details_row0_label"]["content"] == (
        "{{ ${/data/items/0/name} }}"
    )


def test_converter_rejects_non_string_unit() -> None:
    compact_dsl = _serialize(
        [
            ["root", "Column", {}, ["metric"]],
            [
                "metric",
                "EmphasizedData",
                {"value": 68, "unit": 100, "fontColor": "#FF1F4799"},
            ],
        ]
    )

    with pytest.raises(
        CompactDslConversionError,
        match="unit must be string display text",
    ):
        convert_compact_dsl_to_a2ui(compact_dsl, size="2x4")


def test_repairs_paths_in_conditional_expression() -> None:
    compact_dsl = _serialize(
        [
            ["root", "Column", {}, ["title"]],
            [
                "title",
                "SingleLineTitle",
                {
                    "title": "{{ ${/data/current/connected} ? '已连接' : '未连接' }}",
                    "fontColor": "#FF1F4799",
                },
            ],
            ["/data/current/connected", True],
        ]
    )
    task_spec = {
        "dataModelSchema": {
            "data": {
                "device": {
                    "current": {
                        "connected": {"type": "boolean"},
                    }
                }
            }
        }
    }
    card_spec = {"dataBindings": [{"writeResultTo": "/data/device"}]}

    repaired = repair_compact_dsl_binding_paths(
        compact_dsl,
        task_spec=task_spec,
        card_spec=card_spec,
    )
    rows = [json.loads(line) for line in repaired.splitlines()]

    assert rows[1][2]["title"] == (
        "{{ ${/data/device/current/connected} ? '已连接' : '未连接' }}"
    )
    assert rows[2][0] == "/data/device/current/connected"
