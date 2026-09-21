# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import json
from types import SimpleNamespace

import pytest

from config.config import get_settings
from models.capability import AssetCapability
from services.asset_url_mapper import AssetUrlMapper
from services.card_validation import ValidationOptions, validate_card
from services.card_validation.compact_dsl_validator import (
    CompactDslValidationError,
    validate_compact_dsl,
)
from services.card_validation.effective_loader import attach_effective_capabilities
from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.task_spec_builder import TaskSpecBuilder

SRC = "resources/base/media/drop_1.svg"
LOCAL = "resources/base/media/air_fill.svg"
URL = "https://hagres-drcn.dbankcdn.com/assets/drop_1.svg?version=1"


def standard_dsl(src=SRC):
    return json.dumps(
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": "test",
                "root": "root",
                "components": [
                    {"id": "image", "component": "Image", "src": src},
                    {"id": "local", "component": "Image", "src": LOCAL},
                    {"id": "text", "component": "Text", "text": SRC},
                    {"id": "root", "component": "Column", "styles": {"backgroundImage": SRC}},
                    {
                        "id": "button",
                        "component": "Button",
                        "onClick": [
                            {"call": "test", "args": {"src": SRC}},
                        ],
                    },
                ],
            },
        },
        ensure_ascii=False,
    )


def components(dsl):
    result = []
    for line in dsl.splitlines():
        row = json.loads(line)
        update = row.get("updateComponents")
        if isinstance(update, dict):
            result.extend(update.get("components", []))
    return result


def test_maps_only_declared_static_asset_properties():
    mapper = AssetUrlMapper({SRC: URL, LOCAL: URL}, {SRC})
    result = components(mapper.rewrite_standard(standard_dsl()))
    assert result[0].get("src") == URL
    assert result[1].get("src") == LOCAL
    assert result[2].get("text") == SRC
    assert result[3].get("styles") == {"backgroundImage": URL}
    assert result[4].get("onClick") == [{"call": "test", "args": {"src": SRC}}]


@pytest.mark.parametrize("mapping", [{}, {LOCAL: URL}])
def test_no_mapping_preserves_original_bytes(mapping):
    text = standard_dsl() + "\r\n"
    assert AssetUrlMapper(mapping, {SRC}).rewrite_standard(text) == text


@pytest.mark.parametrize(
    "value",
    [
        {"path": "/ui/image"},
        "{{ ${/ui/image} }}",
        "{{ 'resources/base/media/drop_1.svg' }}",
        SRC + ".backup",
    ],
)
def test_dynamic_bindings_and_partial_matches_are_unchanged(value):
    mapper = AssetUrlMapper({SRC: URL}, {SRC})
    result = components(mapper.rewrite_standard(standard_dsl(value)))
    assert result[0].get("src") == value


def test_mapping_is_idempotent_and_does_not_modify_data_model():
    mapper = AssetUrlMapper({SRC: URL}, {SRC})
    text = standard_dsl() + "\n" + json.dumps({"updateDataModel": {"value": {"src": SRC}}})
    once = mapper.rewrite_standard(text)
    assert mapper.rewrite_standard(once) == once
    assert json.loads(once.splitlines()[-1]) == {"updateDataModel": {"value": {"src": SRC}}}


def test_task_spec_keeps_original_assets_with_configured_mapping(monkeypatch):
    monkeypatch.setattr(get_settings(), "asset_src_url_mapping", {SRC: URL})
    task = TaskSpecBuilder().build(
        "天气",
        "2x2",
        [],
        [],
        [],
        [AssetCapability(id="asset.drop_1", src=SRC, description="雨伞")],
    )
    assert task.assetCandidates == [{"id": "asset.drop_1", "src": SRC, "description": "雨伞"}]


def test_mapping_covers_expanded_header_and_action_icons():
    token = "\n".join(
        json.dumps(row)
        for row in [
            [
                "root",
                "Column",
                {"width": 160, "height": 160, "padding": 12, "justifyContent": "start"},
                ["header", "action"],
            ],
            [
                "header",
                "CardHeader",
                {"title": "天气", "icon": SRC, "fontColor": "#FF000000", "fillColor": "#FF000000"},
            ],
            [
                "action",
                "ActionUnit",
                {
                    "state": "capsule",
                    "label": "查看",
                    "icon": SRC,
                    "onClick": [{"call": "test", "args": {}}],
                },
            ],
            ["/ui/state", "ready"],
        ]
    )
    dsl = convert_compact_dsl_to_a2ui(token, size="2x2")
    result = AssetUrlMapper({SRC: URL}, {SRC}).rewrite_standard(dsl)
    images = [item for item in components(result) if item.get("component") == "Image"]
    assert len(images) == 2
    for item in images:
        assert item.get("src") == URL


def test_effective_sources_accept_only_declared_mapping_targets():
    context = SimpleNamespace()
    attach_effective_capabilities(
        context,
        {"asset": [{"src": SRC}]},
        {},
        None,
        {SRC: URL, LOCAL: "https://other"},
    )
    assert context.effective_asset_sources == {SRC, URL}


@pytest.mark.parametrize("src,allowed", [(SRC, True), (URL, True), (URL + "-other", False)])
def test_final_validator_recognizes_exact_mapped_asset(src, allowed):
    token = "\n".join(
        json.dumps(row)
        for row in [
            ["root", "Column", {"width": 320, "height": 160}, ["image"]],
            ["image", "Image", {"src": src, "width": 20, "height": 20}],
            ["/ui/state", "ready"],
        ]
    )
    reporter = validate_card(
        dsl_text=convert_compact_dsl_to_a2ui(token, size="2x4"),
        effective_capabilities={"asset": [{"src": SRC}, {"src": LOCAL}]},
        options=ValidationOptions(asset_src_url_mapping={SRC: URL}),
    )
    asset_errors = []
    for diagnostic in reporter.diagnostics:
        if diagnostic.json_pointer != "/updateComponents/componentsById/image/src":
            continue
        if diagnostic.code in {"EFFECTIVE_ASSET_NOT_ALLOWED", "ASSET_REMOTE_URL_FORBIDDEN"}:
            asset_errors.append(diagnostic)
    assert bool(asset_errors) is not allowed


def test_restore_old_token_only_changes_asset_properties():
    mapper = AssetUrlMapper({SRC: URL}, {SRC})
    token = "\n".join(
        json.dumps(row)
        for row in [
            ["root", "Column", {}, ["img", "text"]],
            ["img", "Image", {"src": URL}],
            ["text", "Text", {"content": URL}],
            ["/ui/address", URL],
        ]
    )
    rows = [json.loads(line) for line in mapper.restore_design_token(token).splitlines()]
    assert rows[1][2].get("src") == SRC
    assert rows[2][2].get("content") == URL
    assert rows[3] == ["/ui/address", URL]


def test_restore_ambiguous_or_unknown_url_fails_without_guessing():
    mapper = AssetUrlMapper({SRC: URL, LOCAL: URL}, {SRC, LOCAL})
    with pytest.raises(ValueError, match="multiple"):
        mapper.rewrite_standard(standard_dsl(URL), restore=True)
    with pytest.raises(ValueError, match="cannot be restored"):
        mapper.rewrite_standard(standard_dsl(URL + "unknown"), restore=True)


def test_repair_diagnostics_use_original_asset_paths():
    mapper = AssetUrlMapper({SRC: URL}, {SRC})
    original = {"actual": URL, "expected": [URL], "code": "TEST"}
    assert mapper.restore_diagnostic_values(original) == {
        "actual": SRC,
        "expected": [SRC],
        "code": "TEST",
    }
    assert original.get("actual") == URL


@pytest.mark.parametrize("src", [URL, LOCAL])
def test_compact_validation_rejects_non_candidate_source_before_conversion(src):
    token = "\n".join(json.dumps(row) for row in [
        ["root", "Column", {"width": 320, "height": 160}, ["image"]],
        ["image", "Image", {"src": src, "width": 20, "height": 20}],
        ["/ui/state", "ready"],
    ])
    with pytest.raises(CompactDslValidationError, match="original src"):
        validate_compact_dsl(
            token, task_spec={"assetCandidates": [{"src": SRC}]}, card_spec={},
        )
