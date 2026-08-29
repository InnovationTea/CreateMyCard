# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Fusion-ball version gate, palette, and Compact Design Token tests."""

import json

import pytest

from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.fusion_ball_expander import (
    FUSION_BALL_CONTENT_ID,
    FusionBallExpansionError,
    build_fusion_ball_palette,
    derive_fusion_ball_palette,
    expand_fusion_ball_components,
    fusion_ball_enabled,
)
from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext


@pytest.mark.parametrize(
    ("app_version", "expected"),
    [
        ("11.7.5.206", True),
        ("CreateMyCard/11.7.5.206", True),
        ("11.7.5.205", False),
        ("11.7.5.204", False),
        ("", False),
        (None, False),
        ("invalid", False),
    ],
)
def test_fusion_ball_version_gate_is_strict(app_version, expected) -> None:
    assert fusion_ball_enabled(app_version) is expected


def test_fusion_ball_palette_supports_explicit_and_base_color_inputs() -> None:
    explicit = build_fusion_ball_palette(
        "#ff121259",
        "#ff2b65d9",
        "#ff57aed9",
    )
    derived = derive_fusion_ball_palette("#FF2B65D9")

    assert explicit.large == "#FF121259"
    assert explicit.medium == "#FF2B65D9"
    assert explicit.small == "#FF57AED9"
    assert derived.large == "#FF1E1773"
    assert derived.medium == "#FF2B65D9"
    assert derived.small == "#FF00A3D9"


def test_fusion_ball_palette_rejects_invalid_explicit_color() -> None:
    with pytest.raises(FusionBallExpansionError, match="#AARRGGBB"):
        build_fusion_ball_palette("#121259", "#FF2B65D9", "#FF57AED9")


@pytest.mark.parametrize("root_type", ["Row", "Column", "Stack"])
def test_compact_root_fusion_design_token_expands_and_marks_content(root_type) -> None:
    compact_dsl = "\n".join(
        (
            json.dumps(
                [
                    "root",
                    root_type,
                    {
                        "width": "matchParent",
                        "height": "matchParent",
                        "padding": 12,
                        "borderRadius": 18,
                        "clip": True,
                        "design": "fusion-ball-weather-blue",
                    },
                    ["title"],
                ],
                separators=(",", ":"),
            ),
            '["title","Text",{"content":"天气","fontSize":14}]',
            '["/state/ready",true]',
        )
    )

    a2ui = convert_compact_dsl_to_a2ui(
        compact_dsl,
        size="2x2",
        app_version="11.7.5.206",
    )
    messages = [json.loads(line) for line in a2ui.splitlines()]
    components = {
        item["id"]: item
        for item in messages[1]["updateComponents"]["components"]
    }

    assert components["root"]["component"] == "Stack"
    assert components["root"]["children"] == [
        "fusionBallBackground",
        FUSION_BALL_CONTENT_ID,
    ]
    assert components[FUSION_BALL_CONTENT_ID]["component"] == root_type
    assert components[FUSION_BALL_CONTENT_ID]["children"] == ["title"]
    assert "backgroundColor" not in components[FUSION_BALL_CONTENT_ID]["styles"]
    assert components["fusionBallMedium"]["styles"]["backgroundColor"] == "#FF2B65D9"


@pytest.mark.parametrize("app_version", ["11.7.5.205", "0", "invalid"])
def test_compact_root_fusion_design_token_stays_off_for_unsupported_version(
    app_version,
) -> None:
    compact_dsl = "\n".join(
        (
            '["root","Column",{"width":"matchParent","height":"matchParent",'
            '"design":"fusion-ball-weather-blue"},["title"]]',
            '["title","Text",{"content":"天气","fontSize":14}]',
            '["/state/ready",true]',
        )
    )

    a2ui = convert_compact_dsl_to_a2ui(
        compact_dsl,
        size="2x2",
        app_version=app_version,
    )
    messages = [json.loads(line) for line in a2ui.splitlines()]
    component_ids = {
        item["id"] for item in messages[1]["updateComponents"]["components"]
    }

    assert FUSION_BALL_CONTENT_ID not in component_ids
    assert "fusionBallBackground" not in component_ids


def test_fusion_ball_expansion_rejects_reserved_component_id() -> None:
    components = [
        {
            "id": "root",
            "component": "Column",
            "children": ["fusionBallLarge"],
            "styles": {},
        },
        {
            "id": "fusionBallLarge",
            "component": "Divider",
            "styles": {},
        },
    ]
    palette = derive_fusion_ball_palette("#FF2B65D9")

    with pytest.raises(FusionBallExpansionError, match="already exist"):
        expand_fusion_ball_components(components, palette)


def test_compact_fallback_processor_expands_fusion_design_token() -> None:
    compact_dsl = "\n".join(
        (
            '["root","Column",{"width":"matchParent","height":"matchParent",'
            '"design":"fusion-ball-weather-blue"},["title"]]',
            '["title","Text",{"content":"天气","fontSize":14}]',
            '["/state/ready",true]',
        )
    )
    context = DslProcessingContext(
        size="2x2",
        card_spec={"dataBindings": []},
        task_spec={
            "userQuery": "天气卡片",
            "size": "2x2",
            "appVersion": "11.7.5.206",
            "eventCandidates": [],
            "dataModelSchema": {"data": {}},
            "assetCandidates": [],
        },
        protocol_profile={"version": "v0.9"},
        design_profile_id="design-compact-dsl",
    )

    result = DesignCompactProcessor().process(compact_dsl, context)
    messages = [json.loads(line) for line in result.standard_dsl.splitlines()]
    components = {
        item["id"]: item
        for item in messages[1]["updateComponents"]["components"]
    }

    assert result.errors == ()
    assert components["root"]["children"] == [
        "fusionBallBackground",
        FUSION_BALL_CONTENT_ID,
    ]
    assert components[FUSION_BALL_CONTENT_ID]["component"] == "Column"
