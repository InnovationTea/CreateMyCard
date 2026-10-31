"""纯动作布局不补造正文，且展示事实、事件与素材检查仍然生效。"""

import copy
import json

import pytest

from services.card_validation import CompactDslValidationError, validate_card, validate_compact_dsl
from services.compact_composition_planner import feasible_composition_candidates
from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    ComponentRow,
    convert_compact_dsl_to_a2ui,
    expand_compact_semantic_layout,
    parse_compact_dsl_rows,
)
from services.compact_layout_runtime import match_compact_layout
from services.compact_plan import compact_plan_coverage_errors, parse_compact_plan_call


def _task() -> dict:
    events = []
    assets = []
    for name in ("wlan", "bluetooth"):
        events.append({
            "id": name, "description": name, "call": "clickToIntent", "args": {
                "intentName": "SetSettingSwitch", "params": {
                    "appBundleName": "com.huawei.hmos.settings", "itemName": name,
                    "switchFlag": 0,
                },
            },
        })
        assets.append({"id": name, "src": f"resources/base/media/{name}.svg"})
    return {
        "size": "2x2", "appVersion": "99.0", "userQuery": "Wi-Fi 和蓝牙快捷开关",
        "dataModelSchema": {"data": {}}, "eventCandidates": events, "assetCandidates": assets,
    }


def _plan(task: dict) -> dict:
    facts = []
    assignments = []
    for name in ("wlan", "bluetooth"):
        facts.append({"requirement": name, "actionId": name, "priority": "must"})
        assignments.append({"actionId": name, "assetId": name})
    output = {"name": "submit_card_plan", "arguments": {
        "info_required": facts, "layoutHints": ["S-content-dual-action"],
        "assetAssignments": {
            "actions": assignments, "title": {"assetId": None, "reason": "纯动作无标题"},
        },
    }}
    return parse_compact_plan_call(json.dumps(output), task).plan


def _rows(task: dict, variant: str | None = "actions-only") -> list:
    props = {"layout": "S-content-dual-action"}
    if variant is not None:
        props["variant"] = variant
    rows = [["root", "Layout", props, ["wlan", "bluetooth"]]]
    candidates = task.get("eventCandidates")
    assert isinstance(candidates, list)
    for candidate in candidates:
        name = candidate.get("id")
        assert isinstance(name, str)
        args = copy.deepcopy(candidate.get("args"))
        assert isinstance(args, dict)
        params = args.get("params")
        assert isinstance(params, dict)
        params["switchFlag"] = 1
        rows.append([name, "CardButton", {
            "label": "Wi-Fi" if name == "wlan" else "蓝牙",
            "icon": f"resources/base/media/{name}.svg",
            "fillColor": "#FF1F4799",
            "onClick": [{"call": candidate.get("call"), "args": args}],
        }])
    return rows


def _source(rows: list) -> str:
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


@pytest.mark.parametrize("variant", ["actions-only", None])
def test_pure_actions_validate_convert_and_preserve_flag(variant: str | None) -> None:
    task = _task()
    plan = _plan(task)
    source = _source(_rows(task, variant))
    validate_compact_dsl(
        source, task_spec=task, card_spec={"suggestSize": "2x2"}, compact_plan=plan,
    )
    assert not compact_plan_coverage_errors(source, plan, task)
    components = [row for row in parse_compact_dsl_rows(source) if isinstance(row, ComponentRow)]
    assert match_compact_layout(
        components, size="2x2", layout_scope="S-content-dual-action",
    ).layout_id == "S-content-dual-action"
    assert {row.component_id for row in components} == {"root", "wlan", "bluetooth"}
    root = next(row for row in components if row.component_id == "root")
    assert root.props.get("justifyContent") == "center"
    converted = convert_compact_dsl_to_a2ui(source, size="2x2")
    assert '"switchFlag":1' in converted
    report = validate_card(dsl_text=converted, effective_capabilities={
        "data": [], "event": task.get("eventCandidates"), "asset": task.get("assetCandidates"),
    })
    assert not report.has_code("EFFECTIVE_EVENT_NOT_ALLOWED")


def test_pure_actions_still_reject_overlong_button_label() -> None:
    task = _task()
    rows = _rows(task)
    rows[2][2]["label"] = "bluetooth"
    with pytest.raises(CompactDslValidationError, match="at most 6 visible characters"):
        validate_compact_dsl(
            _source(rows), task_spec=task, card_spec={"suggestSize": "2x2"},
            compact_plan=_plan(task),
        )


@pytest.mark.parametrize("case", ["missing_plan", "display_fact", "duplicate_action"])
def test_pure_actions_cannot_bypass_plan_content(case: str) -> None:
    task = _task()
    plan = _plan(task)
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    if case == "display_fact":
        facts.append({"text": "必须保留", "priority": "must", "requirement": "正文"})
    elif case == "duplicate_action":
        facts[1] = copy.deepcopy(facts[0])
    with pytest.raises(CompactDslValidationError, match="exactly two distinct actions"):
        validate_compact_dsl(
            _source(_rows(task)), task_spec=task, card_spec={"suggestSize": "2x2"},
            compact_plan=None if case == "missing_plan" else plan,
        )


@pytest.mark.parametrize("case", ["third_child", "wrong_button", "explicit_standard"])
def test_pure_actions_reject_illegal_shape(case: str) -> None:
    rows = _rows(_task())
    if case == "third_child":
        rows[0][3].append("text")
        rows.append(["text", "EmphasisText", {"mainText": "占位"}])
    elif case == "wrong_button":
        rows[1][1] = "EmphasisText"
    else:
        rows[0][2]["variant"] = "standard"
    with pytest.raises(CompactDslConversionError):
        convert_compact_dsl_to_a2ui(_source(rows), size="2x2")


def test_pure_actions_have_a_complete_composition_candidate() -> None:
    task = _task()
    result = feasible_composition_candidates("2x2", _plan(task), task)
    candidates = result.get("candidates")
    assert isinstance(candidates, list)
    assert any(
        candidate.get("layout") == "S-content-dual-action" and candidate.get("variant") == 2
        for candidate in candidates
    )


def test_legacy_column_cannot_bypass_actions_only_content_guard() -> None:
    task = _task()
    plan = _plan(task)
    facts = plan.get("info_required")
    assert isinstance(facts, list)
    facts.append({"text": "不能遗漏", "priority": "must", "requirement": "正文"})
    expanded, _origins = expand_compact_semantic_layout(_source(_rows(task)), size="2x2")
    with pytest.raises(CompactDslValidationError, match="exactly two distinct actions"):
        validate_compact_dsl(
            expanded, task_spec=task, card_spec={"suggestSize": "2x2"}, compact_plan=plan,
        )


@pytest.mark.asyncio
@pytest.mark.usefixtures("isolated_theme_stage")
async def test_registered_pure_actions_complete_without_quality_repair(monkeypatch) -> None:
    from api.schemas import GenerateWidgetCardRequest
    from config.config import get_settings
    from custom.a2ui_model_client import A2UIModelClient
    from models.service import ArtifactSaveResult
    from services.artifact_store import ArtifactStore
    from services.widget_generation_service import WidgetGenerationService

    task = _task()
    candidates = task.get("eventCandidates")
    assert isinstance(candidates, list)
    selected = []
    facts = []
    selected_names = ("event.setWifiMode", "event.setBluetoothMode")
    for name, event in zip(selected_names, candidates, strict=True):
        selected.append({"capabilityId": name, "action": {
            "call": event.get("call"), "args": event.get("args"),
        }})
        facts.append({"actionId": name, "requirement": name, "priority": "must"})
    rows = _rows(task)
    for row in rows[1:]:
        row[2].pop("icon")
    calls = []

    async def generate(_client, _prompt, profile=None, **_kwargs):
        kind = (profile or {}).get("format")
        calls.append(kind)
        if kind == "raw-json":
            return json.dumps({"name": "submit_card_plan", "arguments": {
                "info_required": facts, "layoutHints": ["S-content-dual-action"],
            }})
        return _source(rows)

    settings = get_settings()
    monkeypatch.setattr(settings, "enable_a2ui_model_mock", False)
    monkeypatch.setattr(settings, "enable_artifact_validation", True)
    monkeypatch.setattr(settings, "enable_design_compact_runtime_prompt_context", False)
    monkeypatch.setattr(A2UIModelClient, "generate", generate)
    monkeypatch.setattr(WidgetGenerationService, "_enable_card_template", lambda _self: False)
    monkeypatch.setattr(WidgetGenerationService, "_enable_jsx_generation", lambda _self: False)
    monkeypatch.setattr(ArtifactStore, "save", lambda *_args: ArtifactSaveResult(
        artifactUrl="https://artifact.test/pure-actions", artifactDigest="sha256:test",
    ))
    request = GenerateWidgetCardRequest(
        uid="pure-actions-test", prdVer="11.7.7.300", device={"romVersion": "7.0"},
        userQuery="Wi-Fi 和蓝牙快捷开关", title="快捷开关", description="两个设置开关",
        size="2x2", candidateEventCandidates=selected,
    )
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(request)
    assert response.status.value == "success"
    assert calls == ["raw-json", "compact-dsl"]
