"""真实旧批次的单位对照，以及 1023.2 报告所述标题候选问题的最小复现。"""

import json
from pathlib import Path

import pytest

from services.card_validation import validate_card
from services.card_validation.display_unit_rules import repair_repeated_display_units
from services.compact_plan import parse_compact_plan_call

FIXTURE = Path(__file__).parent / "fixtures/validator_batch_replay/q042_20261012.json"
CAPABILITIES = (
    Path(__file__).parents[1]
    / "cloud/data/capabilities/app-11.7.7.300_rom-7.0/data_capabilities.json"
)


def _batch_case() -> tuple[list[dict], dict, list[dict]]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    genui = payload.get("genui")
    card_spec = payload.get("cardSpec")
    assert isinstance(genui, str)
    assert isinstance(card_spec, dict)
    messages = []
    for line in genui.splitlines():
        if line.strip():
            messages.append(json.loads(line))
    capabilities = json.loads(CAPABILITIES.read_text(encoding="utf-8"))
    return messages, card_spec, capabilities


def _components(messages: list[dict]) -> list[dict]:
    update = messages[1].get("updateComponents")
    assert isinstance(update, dict)
    components = update.get("components")
    assert isinstance(components, list)
    return components


def _component(messages: list[dict], identifier: str) -> dict:
    for component in _components(messages):
        if component.get("id") == identifier:
            return component
    raise AssertionError(f"缺少批跑组件 {identifier}")


def _encode(messages: list[dict]) -> str:
    return "\n".join(json.dumps(message, ensure_ascii=False) for message in messages)


def _unit_errors(source: str, card_spec: dict, capabilities: list[dict]) -> list[str]:
    reporter = validate_card(
        dsl_text=source,
        cardspec=card_spec,
        effective_capabilities={"data": capabilities},
    )
    codes = []
    for diagnostic in reporter.diagnostics:
        if diagnostic.code.startswith("DISPLAY_UNIT_"):
            codes.append(diagnostic.code)
    return codes


def test_original_q042_display_units_are_preserved() -> None:
    messages, card_spec, capabilities = _batch_case()
    source = _encode(messages)
    repaired = repair_repeated_display_units(source, card_spec, capabilities)
    assert _unit_errors(source, card_spec, capabilities) == []
    assert [json.loads(line) for line in repaired.splitlines()] == messages


@pytest.mark.parametrize("sibling_count", [1, 2])
def test_q042_inline_unit_removes_only_redundant_pure_unit_siblings(
    sibling_count: int,
) -> None:
    messages, card_spec, capabilities = _batch_case()
    parent = _component(messages, "countdown")
    children = parent.get("children")
    assert isinstance(children, list)
    for index in range(sibling_count):
        identifier = f"replay_unit_{index}"
        children.append(identifier)
        _components(messages).append({"id": identifier, "component": "Text", "content": "天"})
    # 带业务含义的说明不能被当成可删除的纯单位节点。
    children.append("replay_note")
    note = {"id": "replay_note", "component": "Text", "content": "天后开始"}
    _components(messages).append(note)
    source = _encode(messages)
    assert "DISPLAY_UNIT_DUPLICATED" in _unit_errors(source, card_spec, capabilities)
    repaired = repair_repeated_display_units(source, card_spec, capabilities)
    result = [json.loads(line) for line in repaired.splitlines()]
    assert _component(result, "countdown").get("children") == ["countdown_value", "replay_note"]
    assert _component(result, "replay_note") == note
    assert _component(result, "countdown_value") == _component(messages, "countdown_value")
    assert result[0] == messages[0]
    assert result[2] == messages[2]


def test_q042_duplicate_pure_unit_is_repaired_to_valid_units() -> None:
    messages, card_spec, capabilities = _batch_case()
    parent = _component(messages, "countdown")
    children = parent.get("children")
    assert isinstance(children, list)
    children.append("replay_unit")
    _components(messages).append({"id": "replay_unit", "component": "Text", "content": "天"})
    repaired = repair_repeated_display_units(_encode(messages), card_spec, capabilities)
    assert _unit_errors(repaired, card_spec, capabilities) == []


def test_q042_missing_unit_is_not_silently_filled() -> None:
    messages, card_spec, capabilities = _batch_case()
    _component(messages, "countdown_value")["content"] = "{{ ${/data/countdown/countdownDays} }}"
    source = _encode(messages)
    repaired = repair_repeated_display_units(source, card_spec, capabilities)
    assert _unit_errors(repaired, card_spec, capabilities) == ["DISPLAY_UNIT_MISSING"]
    assert [json.loads(line) for line in repaired.splitlines()] == messages


@pytest.mark.parametrize(
    "content",
    [
        "{{ ${/data/countdown/countdownDays} }}",
        "{{ ${/data/countdown/countdownDays} > 0 ? '天' : '' }}",
        "{{ (${/data/countdown/countdownDays} * 2) + '天' }}",
    ],
)
def test_unit_sibling_is_kept_without_unconditional_inline_unit(content: str) -> None:
    messages, card_spec, capabilities = _batch_case()
    _component(messages, "countdown_value")["content"] = content
    parent = _component(messages, "countdown")
    children = parent.get("children")
    assert isinstance(children, list)
    children.append("replay_unit")
    _components(messages).append({"id": "replay_unit", "component": "Text", "content": "天"})
    repaired = repair_repeated_display_units(_encode(messages), card_spec, capabilities)
    result = [json.loads(line) for line in repaired.splitlines()]
    assert _component(result, "countdown").get("children") == ["countdown_value", "replay_unit"]
    assert _component(result, "countdown_value").get("content") == content


def test_q042_repair_does_not_cross_a_non_text_component() -> None:
    messages, card_spec, capabilities = _batch_case()
    children = _component(messages, "countdown").get("children")
    assert isinstance(children, list)
    children.extend(["replay_barrier", "replay_unit"])
    _components(messages).extend([
        {"id": "replay_barrier", "component": "Divider"},
        {"id": "replay_unit", "component": "Text", "content": "天"},
    ])
    repaired = repair_repeated_display_units(_encode(messages), card_spec, capabilities)
    assert [json.loads(line) for line in repaired.splitlines()] == messages


def test_q042_repair_preserves_unit_node_still_referenced_elsewhere() -> None:
    messages, card_spec, capabilities = _batch_case()
    children = _component(messages, "countdown").get("children")
    assert isinstance(children, list)
    children.append("replay_unit")
    root_children = _component(messages, "root").get("children")
    assert isinstance(root_children, list)
    root_children.append("replay_unit")
    _components(messages).append({"id": "replay_unit", "component": "Text", "content": "天"})
    repaired = repair_repeated_display_units(_encode(messages), card_spec, capabilities)
    result = [json.loads(line) for line in repaired.splitlines()]
    assert _component(result, "countdown").get("children") == ["countdown_value"]
    assert _component(result, "root").get("children") == root_children
    assert _component(result, "replay_unit").get("content") == "天"


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("preferred", ["EmphasisText", "SecondaryBody", "Badge"])
def test_body_preference_is_not_replaced_by_fallback_title(size: str, preferred: str) -> None:
    task = {
        "size": size,
        "userQuery": "显示今天的步数",
        "dataModelSchema": {"data": {"steps": {"type": "integer", "sampleValue": 1000}}},
        "eventCandidates": [],
    }
    raw = json.dumps({"name": "submit_card_plan", "arguments": {"info_required": [{
        "requirement": "今日步数", "dataId": "/data/steps",
        "componentHints": [preferred, "SingleLineTitle"],
    }]}})
    result = parse_compact_plan_call(raw, task)
    facts = result.plan.get("info_required")
    assert isinstance(facts, list)
    assert facts[0].get("componentHints") == [preferred]
    assert facts[0].get("dataId") == "/data/steps"
    assert facts[0].get("priority") == "must"


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_preferred_title_retains_its_exclusive_role(size: str) -> None:
    task = {"size": size, "userQuery": "今日步数", "dataModelSchema": {}, "eventCandidates": []}
    raw = json.dumps({"name": "submit_card_plan", "arguments": {"info_required": [{
        "requirement": "标题", "text": "今日步数",
        "componentHints": ["SingleLineTitle", "SecondaryBody"],
    }]}})
    result = parse_compact_plan_call(raw, task)
    facts = result.plan.get("info_required")
    assert isinstance(facts, list)
    assert facts[0].get("componentHints") == ["SingleLineTitle"]
