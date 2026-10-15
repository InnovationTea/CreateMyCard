"""线上单轮回放：真实处理器、产物校验与两种调试部署模式。"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from debug_tools.end_to_end_debug.backend.debug_agent.config import DebugSettings
from debug_tools.end_to_end_debug.backend.server import create_app
from debug_tools.static_site import create_frontend_app
from fastapi.testclient import TestClient

from models.artifact import WidgetArtifact
from services.capability_registry import CapabilityRegistry
from services.card_validation.diagnostics import Diagnostic
from services.validator import ArtifactValidator

EXAMPLE = Path(__file__).resolve().parents[2] / "debug_tools/card_renderer/validation-example.json"


@pytest.fixture(params=["frontend", "full"])
def client(request):
    app = create_frontend_app()
    if request.param == "full":
        app = create_app(DebugSettings(), production_settings=SimpleNamespace())
    return TestClient(app)


@pytest.fixture
def payload():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def context_of(payload):
    context = payload.get("context")
    assert isinstance(context, dict)
    return context


def artifact_of(payload):
    artifact = context_of(payload).get("artifact")
    assert isinstance(artifact, dict)
    return artifact


def check(client, payload):
    response = client.post("/debug/renderer/validate", json=payload)
    assert response.status_code == 200
    return response.json()


def test_full_model_chain_passes_and_keeps_source_views(client, payload):
    result = check(client, payload)
    assert result.get("valid") is True
    assert result.get("complete") is True
    assert result.get("genui") == artifact_of(payload).get("genui")
    assert result.get("diagnostics") == []
    sources = result.get("sources")
    assert isinstance(sources, dict)
    assert sources.get("original") == payload.get("source")
    assert sources.get("genui") == result.get("genui")
    assert result.get("validationScope") == "layout"
    stages = result.get("stages", [])
    assert any(stage.get("name") == "布局产物校验" for stage in stages)
    assert stages[-1].get("status") == "skipped"
    assert "@theme:" in result.get("genui", "")


@pytest.mark.parametrize(
    "missing",
    [
        "context",
        "artifact",
        "compactPlan",
        "sourceKind",
        "enableArtifactValidation",
        "planInformationCoverageAsWarning",
        "assetMapping",
        "layoutScope",
        "allowedOmittedPlanFactIndexes",
        "designProfileId",
    ],
)
def test_no_guessed_context_or_switches(client, payload, missing):
    target = payload if missing == "context" else context_of(payload)
    target.pop(missing)
    result = check(client, payload)
    assert result.get("status") == "context_required"
    assert result.get("valid") is False
    assert result.get("genui") is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("enableArtifactValidation", "true"),
        ("planInformationCoverageAsWarning", "false"),
        ("allowedOmittedPlanFactIndexes", [True]),
        ("allowedOmittedPlanFactIndexes", [-1]),
        ("designProfileId", "../design-compact-dsl"),
        ("designProfileId", "missing-profile"),
    ],
)
def test_invalid_replay_configuration_is_blocked(client, payload, field, value):
    context_of(payload)[field] = value
    assert check(client, payload).get("status") == "context_required"


def test_missing_original_client_version_is_not_defaulted(client, payload):
    task = artifact_of(payload).get("taskSpec")
    assert isinstance(task, dict)
    task.pop("appVersion")
    assert check(client, payload).get("status") == "context_required"


def test_model_component_rules_are_enabled_and_failure_stops_pipeline(client, payload):
    payload["source"] = '["root","Text",{"content":"你好，卡片"}]'
    result = check(client, payload)
    assert result.get("valid") is False
    assert result.get("genui") is None
    assert any(stage.get("status") == "skipped" for stage in result.get("stages", []))


def test_template_source_preserves_online_compact_skip(client, payload):
    payload["source"] = '["root","Text",{"content":"你好，卡片","fontSize":14}]'
    context_of(payload)["sourceKind"] = "template"
    result = check(client, payload)
    assert result.get("complete") is True
    assert isinstance(result.get("genui"), str)
    assert any(stage.get("name") == "Compact 专项校验" for stage in result.get("stages", []))


@pytest.mark.parametrize("coverage_warning", [False, True])
def test_plan_coverage_respects_online_warning_switch(client, payload, coverage_warning):
    context_of(payload)["planInformationCoverageAsWarning"] = coverage_warning
    context_of(payload)["compactPlan"] = {
        "info_required": [
            {
                "requirement": "动态状态",
                "dataId": "/data/status",
                "priority": "must",
                "componentHints": ["EmphasisText"],
            }
        ],
        "layoutHints": ["S-center"],
    }
    result = check(client, payload)
    assert result.get("valid") is coverage_warning
    assert isinstance(result.get("genui"), str) is coverage_warning
    code = "COMPACT_PLAN_COVERAGE_WARNING" if coverage_warning else "COMPACT_PLAN_COVERAGE_FAILED"
    diagnostic = next(item for item in result.get("diagnostics", []) if item.get("code") == code)
    assert diagnostic.get("severity") == ("warning" if coverage_warning else "error")


def test_artifact_only_error_uses_cardspec_source_and_preserves_preview(client, payload):
    card = artifact_of(payload).get("cardSpec")
    assert isinstance(card, dict)
    card["dataBindings"] = []
    result = check(client, payload)
    assert result.get("valid") is False
    assert result.get("complete") is True
    assert isinstance(result.get("genui"), str)
    diagnostic = next(
        item for item in result.get("diagnostics", []) if item.get("code") == "CARD_REQUIRED_FIELD"
    )
    assert diagnostic.get("sourceKind") == "cardspec"
    assert diagnostic.get("propertyPath") == "/dataBindings"
    # 与线上包装器直接校验同一候选产物的结果保持一致。
    artifact = WidgetArtifact.model_validate(artifact_of(payload))
    artifact.genui = result.get("genui")
    errors = ArtifactValidator({}).validate_layout(
        artifact, {"id": artifact.meta.protocolProfileId},
    )
    assert any("CARD_REQUIRED_FIELD" in error for error in errors)


def test_disabled_artifact_validation_is_never_full_pass(client, payload):
    context_of(payload)["enableArtifactValidation"] = False
    result = check(client, payload)
    assert result.get("status") == "skipped"
    assert result.get("valid") is False
    assert result.get("complete") is False
    assert isinstance(result.get("genui"), str)


def test_compact_diagnostic_locates_colorless_input_without_using_original_line(client, payload):
    source = payload.get("source")
    assert isinstance(source, str)
    source = source.replace('"clip":true', '"clip":true,"accessibilityText":"{{/missing}}"')
    payload["source"] = "\n```genui\n" + source + "\n```"
    result = check(client, payload)
    diagnostic = next(
        item
        for item in result.get("diagnostics", [])
        if item.get("code") == "COMPACT_EXPRESSION_REFERENCE_MISSING"
    )
    assert diagnostic.get("sourceKind") == "layoutInput"
    assert diagnostic.get("sourceLine") == 1
    sources = result.get("sources")
    assert isinstance(sources, dict)
    assert sources.get("original") == payload.get("source")
    assert "{{/missing}}" in sources.get("layoutInput", "").splitlines()[0]


def test_expanded_component_diagnostic_does_not_guess_original_location(client, payload):
    source = payload.get("source")
    assert isinstance(source, str)
    payload["source"] = source.replace("你好，卡片", "{{/missing}}")
    result = check(client, payload)
    diagnostic = next(
        item
        for item in result.get("diagnostics", [])
        if item.get("code") == "COMPACT_EXPRESSION_REFERENCE_MISSING"
    )
    assert diagnostic.get("sourceLine") is None


def test_edit_uses_current_snapshot_without_original_artifact(client, payload):
    meta = artifact_of(payload).get("meta")
    assert isinstance(meta, dict)
    meta["generationMode"] = "edit"
    result = check(client, payload)
    assert result.get("valid") is True
    assert result.get("complete") is True


def test_artifact_diagnostics_preserve_zero_false_warning_and_location(
    client, payload, monkeypatch
):
    diagnostics = [
        Diagnostic(
            "warning",
            "TEST_WARNING",
            "quality",
            "genui",
            "warning",
            line=2,
            actual=0,
            expected=False,
        )
    ]
    monkeypatch.setattr(
        "services.validator.validate_card", lambda **_: SimpleNamespace(diagnostics=diagnostics)
    )
    result = check(client, payload)
    assert result.get("valid") is True
    warning = next(iter(result.get("diagnostics", [])))
    assert warning.get("actual") == 0
    assert warning.get("expected") is False
    assert warning.get("sourceKind") == "genui"
    assert warning.get("sourceLine") == 2


def test_effective_asset_mapping_reaches_preview_and_artifact(client, payload):
    registry = CapabilityRegistry(version="app-11.7.7.300_rom-7.0")
    asset = registry.get_asset_capability("asset.drop_1")
    assert asset is not None
    context = context_of(payload)
    context["sourceKind"] = "template"
    context["compactPlan"] = None
    context["assetMapping"] = {asset.src: "https://assets.example.test/drop.svg"}
    effective = artifact_of(payload).get("effectiveCapabilities")
    assert isinstance(effective, dict)
    effective["asset"] = [asset.id]
    payload["source"] = json.dumps(
        [
            "root",
            "Column",
            {"backgroundImage": asset.src, "width": "matchParent", "height": "matchParent"},
        ],
        ensure_ascii=False,
    )
    result = check(client, payload)
    assert result.get("complete") is True
    assert "https://assets.example.test/drop.svg" in result.get("genui", "")


def test_mapping_failure_stops_before_artifact(client, payload, monkeypatch):
    def fail_mapping(_self, _source):
        raise ValueError("mapping failed")

    monkeypatch.setattr("services.asset_url_mapper.AssetUrlMapper.rewrite_standard", fail_mapping)
    result = check(client, payload)
    assert result.get("genui") is None
    assert result.get("complete") is False
    assert any(item.get("code") == "ASSET_MAPPING_FAILED" for item in result.get("diagnostics", []))


@pytest.mark.parametrize(
    "content,root,escaped,valid",
    [
        ("/data/weather", None, False, True),
        ("静态卡片", None, False, True),
        ("{{ ${/data/weather/current/condition} }}", None, False, False),
        ("{{ ${/data/weather/current/condition} }}", None, True, False),
        (
            "{{ ${/data/weatherBackup/current/condition} }}",
            "/data/weatherBackup", False, True,
        ),
        (
            "{{ ${/data/weather/today/current/condition} }}",
            "/data/weather/today", False, True,
        ),
    ],
)
def test_edit_replay_matches_online_artifact_validator(
    client, payload, content, root, escaped, valid,
):
    context = context_of(payload)
    context["sourceKind"] = "template"
    context["compactPlan"] = None
    candidate = artifact_of(payload)
    meta = candidate.get("meta")
    assert isinstance(meta, dict)
    meta["generationMode"] = "edit"
    card = candidate.get("cardSpec")
    effective = candidate.get("effectiveCapabilities")
    plan = candidate.get("generationPlan")
    assert isinstance(card, dict)
    assert isinstance(effective, dict)
    assert isinstance(plan, dict)
    if root is not None:
        binding = {
            "capabilityId": "ViewWeather",
            "arguments": {"prefectureName": "上海市", "forecastDays": 1},
            "writeResultTo": root,
        }
        card["dataBindings"] = [binding]
        plan["candidateDataBindings"] = [binding]
        effective["data"] = ["ViewWeather"]
    weather = {"current": {"condition": "晴"}}
    rows = [
        ["root", "Column", {
            "width": "matchParent", "height": "matchParent", "padding": 12,
            "backgroundColor": "#FFFFFFFF",
        }, ["value"]],
        ["value", "Text", {"content": content, "fontSize": 18, "fontColor": "#FF000000"}],
        ["/data", {"weather": {**weather, "today": weather}, "weatherBackup": weather}],
    ]
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    payload["source"] = source.replace("/", r"\/") if escaped else source
    result = check(client, payload)
    assert result.get("valid") is valid
    assert result.get("complete") is True
    artifact = WidgetArtifact.model_validate(candidate)
    artifact.genui = result.get("genui")
    validator = ArtifactValidator({})
    errors = validator.validate(artifact, {"id": artifact.meta.protocolProfileId})
    assert (not errors) is valid
    replay_errors = [
        item for item in result.get("diagnostics", []) if item.get("severity") == "error"
    ]
    assert len(replay_errors) == len(errors)
    if not valid:
        assert len(replay_errors) == 1
        assert replay_errors[0].get("code") == "EFFECTIVE_DATA_PATH_NOT_ALLOWED"
        assert replay_errors[0].get("sourceKind") == "genui"
        assert replay_errors[0].get("propertyPath") == (
            "/updateComponents/componentsById/value/content"
        )
    assert all(item.get("stage") != "edit" for item in result.get("diagnostics", []))


def test_raw_json_notes_do_not_override_online_recovery(client, payload):
    source = payload.get("source")
    assert isinstance(source, str)
    payload["source"] = source + "\nnon-json commentary"
    result = check(client, payload)
    notes = result.get("inputNotes")
    assert isinstance(notes, list)
    assert any(item.get("sourceLine") == 3 for item in notes)
    # 当前线上解析器忽略非 JSON 的说明行，回放必须保持相同结论。
    assert result.get("valid") is True
