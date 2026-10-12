# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import json

import pytest
from pydantic import ValidationError

from config.config import Settings
from models.generation import CardSpec
from services.card_spec_builder import CardSpecBuilder
from services.card_validation import validate_card
from services.compact_dsl_a2ui_converter import (
    convert_compact_dsl_to_a2ui,
    strip_compact_card_background,
)
from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext


def _components(dsl: str) -> dict[str, dict]:
    update_message = json.loads(dsl.splitlines()[1])
    rows = update_message.get("updateComponents", {}).get("components")
    assert isinstance(rows, list)
    return {row.get("id"): row for row in rows}


def test_new_material_setting_defaults_off_and_supports_environment(monkeypatch):
    variable = "WIDGET_SERVICE_ENABLE_NEW_MATERIAL"
    monkeypatch.delenv(variable, raising=False)
    assert Settings(_env_file=None).enable_new_material is False

    monkeypatch.setenv(variable, "true")
    assert Settings(_env_file=None).enable_new_material is True

    monkeypatch.setenv(variable, "invalid")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_card_spec_builder_only_emits_requested_material():
    legacy = CardSpecBuilder().build(
        "2x2",
        [],
        "静态卡片",
        "旧材质",
    )
    material = CardSpecBuilder().build(
        "2x2",
        [],
        "静态卡片",
        "新材质",
        "thick",
    )
    thin_material = CardSpecBuilder().build(
        "2x2",
        [],
        "静态卡片",
        "薄材质",
        "thin",
    )

    assert "materialType" not in legacy.model_dump(exclude_none=True)
    assert material.materialType == "thick"
    assert thin_material.materialType == "thin"
    with pytest.raises(ValidationError):
        CardSpec(
            title="静态卡片",
            description="非法材质",
            suggestSize="2x2",
            materialType="medium",
        )


def test_cardspec_validator_accepts_supported_material_types():
    thick = validate_card(
        cardspec={
            "title": "静态卡片",
            "description": "新材质",
            "suggestSize": "2x2",
            "materialType": "thick",
        }
    )
    thin = validate_card(
        cardspec={
            "title": "静态卡片",
            "description": "薄材质",
            "suggestSize": "2x2",
            "materialType": "thin",
        }
    )
    invalid = validate_card(
        cardspec={
            "title": "静态卡片",
            "description": "非法材质",
            "suggestSize": "2x2",
            "materialType": "medium",
        }
    )

    assert not thick.has_code("CARD_MATERIAL_TYPE_INVALID")
    assert not thin.has_code("CARD_MATERIAL_TYPE_INVALID")
    assert invalid.has_code("CARD_MATERIAL_TYPE_INVALID")


@pytest.mark.parametrize("material_type", ["thick", "thin"])
def test_new_material_strips_only_card_background_and_disables_fusion_ball(material_type):
    source = "\n".join(
        [
            '["root","Column",{"backgroundColor":"#FFFFFFFF",'
            '"backgroundImage":"resources/card.png",'
            '"backgroundImageSizeWithStyle":"cover",'
            '"linearGradient":{"colors":[["#FFFFFFFF",0],["#FF000000",1]]},'
            '"design":"fusion-ball-sport-orange"},["content"]]',
            '["content","Column",{"backgroundColor":"#33FFFFFF"},["text"]]',
            '["text","Text",{"content":"测试","fontColor":"#FF000000"}]',
            '["/state","ready"]',
        ]
    )

    processed = strip_compact_card_background(source)
    root = json.loads(processed.splitlines()[0])
    child = json.loads(processed.splitlines()[1])
    converted = convert_compact_dsl_to_a2ui(
        source,
        size="2x2",
        material_type=material_type,
    )
    converted_components = _components(converted)
    converted_root_styles = converted_components.get("root", {}).get("styles", {})

    for field in (
        "backgroundColor",
        "backgroundImage",
        "backgroundImageSizeWithStyle",
        "linearGradient",
        "design",
    ):
        assert field not in root[2]
    assert child[2].get("backgroundColor") == "#33FFFFFF"
    assert "backgroundColor" not in converted_root_styles
    assert "linearGradient" not in converted_root_styles
    assert "backgroundImage" not in converted_root_styles
    assert "fusionBallBackground" not in converted_components
    assert converted_components.get("content", {}).get("styles", {}).get(
        "backgroundColor"
    ) == "#33FFFFFF"


def test_design_compact_processor_strips_background_for_thin_material():
    source = "\n".join(
        [
            '["root","Column",{"backgroundColor":"#FFFFFFFF"},["content"]]',
            '["content","Column",{"backgroundColor":"#33FFFFFF"},["text"]]',
            '["text","Text",{"content":"测试","fontColor":"#FF000000"}]',
        ]
    )
    context = DslProcessingContext(
        size="2x2",
        card_spec={"materialType": "thin"},
        task_spec={"appVersion": "11.9.9.342"},
        protocol_profile={"version": "v0.9"},
        skip_compact_dsl_validation=True,
    )

    result = DesignCompactProcessor().process(source, context)
    processed_root = json.loads(result.source_dsl.splitlines()[0])
    processed_child = json.loads(result.source_dsl.splitlines()[1])
    converted_components = _components(result.standard_dsl)

    assert not result.errors
    assert "backgroundColor" not in processed_root[2]
    assert processed_child[2].get("backgroundColor") == "#33FFFFFF"
    assert "backgroundColor" not in converted_components.get("root", {}).get("styles", {})


def test_legacy_conversion_still_adds_default_root_background():
    source = "\n".join(
        [
            '["root","Column",{},["text"]]',
            '["text","Text",{"content":"测试","fontColor":"#FF000000"}]',
        ]
    )

    converted = convert_compact_dsl_to_a2ui(source, size="2x2")

    assert _components(converted).get("root", {}).get("styles", {}).get(
        "backgroundColor"
    ) == "#FFE5EDFE"
