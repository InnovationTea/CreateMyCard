# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from api.schemas import GenerateWidgetCardRequest
from config.config import get_settings
from custom.a2ui_model_client import A2UIModelClient
from models.generation import DeviceContext
from models.service import ArtifactSaveResult
from services.artifact_store import ArtifactStore
from services.compact_dsl_protocol import (
    COMPONENT_WHITELIST,
    build_compact_dsl_system_prompt,
    validate_compact_dsl,
)
from services.widget_generation_service import WidgetGenerationService

APP_VERSION = ".".join(("11", "7", "5", "205"))


def _ndjson(rows: list[list[Any]]) -> str:
    return "\n".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows
    )


def _all_component_rows() -> list[list[Any]]:
    return [
        [
            "root",
            "Column",
            {"width": "matchParent", "space": 8},
            [
                "row",
                "list",
                "stack",
                "grid",
                "text",
                "image",
                "divider",
                "progress",
                "open",
                "input",
                "radio1",
                "radio2",
                "toggle",
                "checkbox",
                "select",
                "web",
                "submit",
            ],
        ],
        ["row", "Row", {"space": 4}, []],
        ["list", "List", {"space": 4}, []],
        ["stack", "Stack", {}, []],
        ["grid", "Grid", {"columnsTemplate": "1fr 1fr"}, []],
        ["text", "Text", {"content": {"path": "/title"}}],
        ["/title", "天气速览"],
        ["image", "Image", {"src": "resources/base/media/weather.png"}],
        ["divider", "Divider", {}],
        ["progress", "Progress", {"value": 50, "total": 100}],
        [
            "open",
            "Button",
            {
                "label": "打开",
                "enabled": True,
                "action": {
                    "functionCall": {
                        "call": "openUrl",
                        "args": {"url": "https://example.com/weather"},
                    }
                },
            },
        ],
        [
            "input",
            "TextInput",
            {
                "text": {"path": "/form/name"},
                "placeholder": "姓名",
                "enabled": True,
                "maxLength": 20,
                "type": "normal",
            },
        ],
        ["/form/name", ""],
        [
            "radio1",
            "Radio",
            {"value": "a", "checked": True, "group": "meal", "indicatorType": "dot"},
        ],
        [
            "radio2",
            "Radio",
            {"value": "b", "checked": False, "group": "meal", "indicatorType": "dot"},
        ],
        ["toggle", "Toggle", {"label": "通知", "isOn": False, "enabled": True}],
        [
            "checkbox",
            "Checkbox",
            {"label": "同意", "group": "terms", "select": False},
        ],
        ["select", "Select", {"options": [{"value": "A"}], "selected": 0, "value": "A"}],
        ["web", "Web", {"url": "https://example.com/embed"}],
        [
            "submit",
            "Button",
            {
                "label": "提交",
                "enabled": True,
                "action": {
                    "event": {
                        "name": "submit_form",
                        "context": {
                            "name": {"path": "/form/name"},
                            "meal": {"call": "getRadioValue", "args": {"group": "meal"}},
                            "terms": {
                                "call": "getCheckboxGroupValues",
                                "args": {"group": "terms"},
                            },
                            "notify": {
                                "call": "getToggleValue",
                                "args": {"componentID": "toggle"},
                            },
                            "choice": {
                                "call": "getSelectValue",
                                "args": {"componentID": "select"},
                            },
                        },
                    }
                },
            },
        ],
    ]


def _component(rows: list[list[Any]], component_id: str) -> list[Any]:
    return next(row for row in rows if row[0] == component_id)


def _errors(rows: list[list[Any]]) -> list[str]:
    return validate_compact_dsl(_ndjson(rows), {"suggestSize": "2x4"}).errors


def _generation_request() -> GenerateWidgetCardRequest:
    return GenerateWidgetCardRequest(
        uid="compact-dsl-model-gate",
        device=DeviceContext(romVersion="6.0"),
        prdVer=APP_VERSION,
        userQuery="weather card",
        size="2x4",
        title="Weather",
        description="Current weather",
    )


def test_all_16_whitelisted_components_pass_together():
    rows = _all_component_rows()

    report = validate_compact_dsl(_ndjson(rows), {"suggestSize": "2x4"})
    types = {row[1] for row in rows if len(row) >= 3 and not row[0].startswith("/")}

    assert report.errors == []
    assert types == set(COMPONENT_WHITELIST)


def test_prompt_contains_runtime_critical_component_and_form_contracts():
    prompt = build_compact_dsl_system_prompt(
        {"componentWhitelist": list(COMPONENT_WHITELIST)}
    )

    assert "Text content:string|path" in prompt
    assert "TextInput text:path" in prompt
    assert "getCheckboxGroupValues(group)" in prompt
    assert "getSelectValue(componentID)" in prompt
    assert "Do not output Markdown fences" in prompt


@pytest.mark.parametrize(
    ("component_id", "prop", "value", "expected"),
    [
        ("row", "space", "4", "Row.space must be a non-negative number"),
        ("progress", "value", True, "Progress.value must be a number"),
        ("progress", "value", 101, "Progress.value must be between 0 and 100"),
        ("input", "text", "literal", "TextInput.text must be a path binding object"),
        ("input", "maxLength", 0, "TextInput.maxLength must be a positive integer"),
        ("input", "type", "phone", "TextInput.type is unsupported"),
        ("radio1", "checked", "true", "Radio.checked must be a boolean"),
        ("radio1", "indicatorType", "circle", "Radio.indicatorType must be tick or dot"),
        ("toggle", "isOn", 1, "Toggle.isOn must be a boolean"),
        ("checkbox", "select", 0, "Checkbox.select must be a boolean"),
        ("select", "options", [], "Select.options must be a non-empty array"),
        ("select", "selected", 1, "Select.selected is outside the options array"),
        ("web", "url", "https://", "Web.url must be a complete http/https URL"),
    ],
)
def test_component_prop_type_and_range_errors_are_rejected(
    component_id: str,
    prop: str,
    value: Any,
    expected: str,
):
    rows = _all_component_rows()
    _component(rows, component_id)[2][prop] = value

    assert any(expected in error for error in _errors(rows))


@pytest.mark.parametrize(
    ("context_key", "expected"),
    [
        ("name", "submit_form context must include path /form/name"),
        ("meal", "getRadioValue"),
        ("terms", "getCheckboxGroupValues"),
        ("notify", "getToggleValue"),
        ("choice", "getSelectValue"),
    ],
)
def test_each_form_control_must_be_submitted(context_key: str, expected: str):
    rows = _all_component_rows()
    context = _component(rows, "submit")[2]["action"]["event"]["context"]
    del context[context_key]

    assert any(expected in error for error in _errors(rows))


def test_radio_group_requires_multiple_options_and_single_checked_item():
    rows = _all_component_rows()
    root_children = _component(rows, "root")[3]
    root_children.remove("radio2")
    rows.remove(_component(rows, "radio2"))

    assert any("at least two Radio" in error for error in _errors(rows))

    rows = _all_component_rows()
    _component(rows, "radio2")[2]["checked"] = True
    assert any("more than one checked" in error for error in _errors(rows))


def test_button_action_requires_one_kind_and_real_open_url():
    rows = _all_component_rows()
    action = _component(rows, "open")[2]["action"]
    action["event"] = {"name": "also_event", "context": {}}
    assert any("exactly one" in error for error in _errors(rows))

    rows = _all_component_rows()
    _component(rows, "open")[2]["action"]["functionCall"]["args"]["url"] = "https://"
    assert any("openUrl args.url" in error for error in _errors(rows))


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        (
            [["root", "Column", {"width": "matchParent", "space": 8}, ["missing"]]],
            "is never created",
        ),
        (
            [
                ["root", "Column", {"width": "matchParent", "space": 8}, ["title"]],
                ["title", "Text", {"content": "x"}, []],
            ],
            "must not have a children array",
        ),
        (
            [
                ["root", "Column", {"width": "matchParent", "space": 8}, ["row"]],
                ["row", "Row", {"space": 4}],
            ],
            "requires a children array",
        ),
        (
            [
                ["root", "Column", {"width": "matchParent", "space": 8}, []],
                ["orphan", "Text", {"content": "x"}],
            ],
            "must first appear in an earlier parent's children",
        ),
        (
            [
                ["root", "Column", {"width": "matchParent", "space": 8}, ["a", "b"]],
                ["a", "Column", {"space": 4}, ["x"]],
                ["b", "Column", {"space": 4}, ["x"]],
                ["x", "Text", {"content": "x"}],
            ],
            "must have exactly one parent",
        ),
    ],
)
def test_invalid_component_trees_are_rejected(rows: list[list[Any]], expected: str):
    assert any(expected in error for error in _errors(rows))


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        (
            [
                ["root", "Column", {"width": "matchParent", "space": 8}, ["title"]],
                ["title", "Text", {"content": {"path": "/title"}}],
            ],
            "has no data line",
        ),
        (
            [
                ["root", "Column", {"width": "matchParent", "space": 8}, ["title"]],
                ["/title", "x"],
                ["title", "Text", {"content": {"path": "/title"}}],
            ],
            "must be initialized after",
        ),
        (
            [
                ["root", "Column", {"width": "matchParent", "space": 8}, ["title"]],
                ["title", "Text", {"content": {"path": "/title"}}],
                ["/title", 42],
            ],
            "must initialize a string value",
        ),
        (
            [
                ["root", "Column", {"width": "matchParent", "space": 8}, ["title"]],
                ["title", "Text", {"content": {"path": "/page.title"}}],
                ["/page.title", "x"],
            ],
            "absolute JSON Pointer",
        ),
    ],
)
def test_binding_order_path_and_semantic_type_are_rejected(
    rows: list[list[Any]], expected: str
):
    assert any(expected in error for error in _errors(rows))


@pytest.mark.parametrize(
    "raw",
    [
        "```genui\n[]\n```",
        '{"createSurface":{}}',
        "null",
        '"text"',
        "[]",
        '["/only-path"]',
        "[",
    ],
)
def test_malformed_or_non_ndjson_input_is_rejected_without_crashing(raw: str):
    report = validate_compact_dsl(raw, {"suggestSize": "2x4"})

    assert report.errors


def test_cardspec_string_is_supported_and_click_behavior_is_rejected():
    rows = [["root", "Column", {"width": "matchParent", "space": 8}, []]]

    valid = validate_compact_dsl(_ndjson(rows), '{"suggestSize":"2x2"}')
    invalid = validate_compact_dsl(
        _ndjson(rows),
        '{"suggestSize":"2x2","onClick":{}}',
    )

    assert valid.errors == []
    assert any("must not contain click behavior" in error for error in invalid.errors)


def test_validator_is_deterministic_and_does_not_mutate_input_rows():
    rows = _all_component_rows()
    original = copy.deepcopy(rows)

    reports = [validate_compact_dsl(_ndjson(rows), {"suggestSize": "2x4"}) for _ in range(50)]

    assert all(report.errors == [] for report in reports)
    assert rows == original


def test_artifact_meta_uses_selected_protocol_profile_version():
    artifact = WidgetGenerationService()._build_artifact(
        genui=_ndjson([["root", "Column", {"width": "matchParent", "space": 8}, []]]),
        card_spec={"suggestSize": "2x4"},
        task_spec={"dataModelSchema": {"data": {}}},
        data_capabilities=[],
        event_candidates=[],
        asset_candidates=[],
        removed=[],
        protocol_profile_id="compact-dsl-v1",
        protocol_profile_version="v1",
        capability_registry_version="app-1.0.0_rom-6.0",
    )

    assert artifact.meta.protocolProfileId == "compact-dsl-v1"
    assert artifact.meta.dslProtocolVersion == "v1"


def test_generation_service_accepts_valid_compact_dsl_model_output(monkeypatch):
    model_output = _ndjson(
        [
            ["root", "Column", {"width": "matchParent", "space": 8}, ["title"]],
            ["title", "Text", {"content": "Weather"}],
        ]
    )
    monkeypatch.setattr(
        A2UIModelClient,
        "generate",
        lambda self, prompt, protocol_profile: model_output,
    )
    saved_artifacts = []

    def capture_artifact(_store, artifact):
        saved_artifacts.append(artifact)
        return ArtifactSaveResult(
            artifactUrl="https://test.invalid/artifact",
            artifactDigest="sha256:test",
        )

    monkeypatch.setattr(ArtifactStore, "save", capture_artifact)

    response = WidgetGenerationService().generate_widget_card_compact_dsl(
        _generation_request()
    )

    assert response.status.value == "success"
    assert "artifact" not in response.model_dump()
    assert len(saved_artifacts) == 1
    assert saved_artifacts[0].genui == model_output
    assert saved_artifacts[0].meta.protocolProfileId == "compact-dsl-v1"
    assert saved_artifacts[0].meta.dslProtocolVersion == "v1"


@pytest.mark.parametrize(
    ("retry_enabled", "expected_generate_calls"),
    [(False, 1), (True, 2)],
)
def test_generation_service_logs_validation_failure_and_continues_save(
    monkeypatch,
    retry_enabled,
    expected_generate_calls,
):
    calls = {"generate": 0, "save": 0}
    saved_artifacts = []
    error_logs: list[str] = []

    def invalid_generate(self, prompt, protocol_profile):
        calls["generate"] += 1
        return "```genui\n[]\n```"

    def capture_save(self, artifact):
        calls["save"] += 1
        saved_artifacts.append(artifact)
        return ArtifactSaveResult(
            artifactUrl="https://test.invalid/non-blocking-validation-artifact",
            artifactDigest="sha256:validation-warning",
        )

    monkeypatch.setattr(A2UIModelClient, "generate", invalid_generate)
    monkeypatch.setattr(ArtifactStore, "save", capture_save)
    monkeypatch.setattr(
        get_settings(),
        "enable_validation_failure_retry",
        retry_enabled,
    )
    monkeypatch.setattr(
        "services.widget_generation_service.logger.error",
        lambda message: error_logs.append(str(message)),
    )

    response = WidgetGenerationService().generate_widget_card_compact_dsl(
        _generation_request()
    )

    assert response.status.value == "success"
    assert response.errorCode == ""
    assert response.artifactUrl == (
        "https://test.invalid/non-blocking-validation-artifact"
    )
    assert "artifact" not in response.model_dump()
    assert calls == {"generate": expected_generate_calls, "save": 1}
    assert len(saved_artifacts) == 1
    assert saved_artifacts[0].genui == "```genui\n[]\n```"
    assert any(
        "a2ui_generation_validation_failed_non_blocking" in message
        and "proceeding_to_artifact_save=true" in message
        for message in error_logs
    )
