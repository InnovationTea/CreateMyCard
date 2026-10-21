"""结构检索不依赖业务词、测试标签或最终模型答案。"""

import copy
import re
from dataclasses import replace
from pathlib import Path

import pytest

from config.config import get_settings
from models.generation import TaskSpec
from services.compact_prompt_loader import assemble_prompts
from services.compact_structural_fewshots import (
    Features,
    compatible,
    parse_examples,
    query_features,
    score,
    select_structural_fewshots,
)
from services.prompt_builder import PromptBuilder

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source"
)
PROMPTS = assemble_prompts(SOURCE)


def _task(size: str = "2x2") -> dict:
    return {
        "size": size,
        "userQuery": "展示一个设备读数，提供两个独立操作",
        "dataModelSchema": {
            "data": {"device": {"reading": {"type": "string", "sampleValue": "80%"}}},
        },
        "eventCandidates": [],
    }


def _plan(actions: int = 2) -> dict:
    facts = [{"dataId": "/data/device/reading", "componentHints": ["EmphasizedData"]}]
    for number in range(actions):
        facts.append({"actionId": f"action.{number}", "componentHints": ["CardButton"]})
    return {"info_required": facts, "layoutHints": ["S-content-dual-action"]}


def _identifiers(content: str) -> set[str]:
    return set(re.findall(r"(?m)^## (2x[24]-V\d+)", content))


def test_dual_buttons_retrieve_all_three_valid_structures_not_single_buttons() -> None:
    result = select_structural_fewshots(PROMPTS.get("fewshot_2x2", ""), _plan(), _task())
    assert result.identifiers[0] == "2x2-V18"
    assert set(result.identifiers) == {"2x2-V03", "2x2-V17", "2x2-V18"}
    assert _identifiers(result.content) == set(result.identifiers)
    for match in result.matches:
        assert match.example.features.buttons == 2
        assert "CardButton" in match.example.features.components[0]


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_four_unique_read_only_examples_stable_without_domain_words(size: str) -> None:
    task = _task(size)
    plan = _plan(0)
    plan["layoutHints"] = []
    source = PROMPTS.get(f"fewshot_{size}", "")
    result = select_structural_fewshots(source, plan, task)
    assert len(result.matches) == 4
    assert len({match.example.fingerprint for match in result.matches}) == 4
    assert result == select_structural_fewshots(source, plan, task)
    changed = copy.deepcopy(task)
    changed["userQuery"] = "完全无关的业务词"
    changed["dataModelSchema"]["data"]["other"] = changed["dataModelSchema"]["data"].pop("device")
    changed_plan = copy.deepcopy(plan)
    changed_plan["info_required"][0]["dataId"] = "/data/other/reading"
    assert query_features(changed_plan, changed) == query_features(plan, task)
    assert select_structural_fewshots(source, changed_plan, changed) == result


def test_required_actions_not_candidate_event_count_and_duplicate_facts_count_once() -> None:
    plan = _plan()
    task = _task()
    expected = query_features(plan, task)
    task["eventCandidates"] = [{"id": str(index)} for index in range(100)]
    fact = copy.deepcopy(plan["info_required"][0])
    fact.pop("componentHints")
    plan["info_required"].append(fact)
    assert query_features(plan, task) == expected


def test_whole_card_has_no_button_and_only_supporting_layouts() -> None:
    plan = _plan(1)
    plan["wholeCardActionId"] = "action.0"
    query = query_features(plan, _task())
    assert query.buttons == 0
    assert query.action_mode == "whole-card"
    for example in parse_examples(PROMPTS.get("fewshot_2x2", "")):
        assert compatible(query, example) == (
            example.features.layouts[0] in {"S-title-content", "S-title-dual-content"}
        )


def test_missing_hints_and_samples_do_not_count_as_zero_match() -> None:
    query = Features("2x2", 1, 0, "none", None, None)
    example = parse_examples(PROMPTS.get("fewshot_2x2", ""))[0]
    match = score(query, example)
    assert match.dimensions.get("layout") is None
    assert match.dimensions.get("component") is None
    assert match.dimensions.get("density") is not None
    assert 0 <= match.score <= 1


def test_size_and_runtime_action_capacity_are_hard_filters() -> None:
    query = query_features(_plan(), _task())
    for example in parse_examples(PROMPTS.get("fewshot_2x4", "")):
        assert not compatible(query, example)
    wide = replace(query, size="2x4")
    for example in parse_examples(PROMPTS.get("fewshot_2x4", "")):
        if example.features.layouts == ("W-top-bottom",):
            assert not compatible(wide, example)


def test_unmatched_or_empty_library_does_not_invent_references() -> None:
    assert select_structural_fewshots("", _plan(), _task()).identifiers == ()
    plan = _plan(3)
    result = select_structural_fewshots(PROMPTS.get("fewshot_2x2", ""), plan, _task())
    assert result.content == ""
    assert not result.identifiers


def test_retrieval_switch_and_total_switch_are_independent(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_design_compact_few_shots", True)
    task = TaskSpec.model_validate(_task())
    monkeypatch.setattr(settings, "enable_design_compact_few_shot_selection", True)
    selected = PromptBuilder._compact_few_shot_context(task, _plan(), component_source="")
    assert _identifiers(selected) == {"2x2-V03", "2x2-V17", "2x2-V18"}
    monkeypatch.setattr(settings, "enable_design_compact_few_shot_selection", False)
    full = PromptBuilder._compact_few_shot_context(task, _plan(), component_source="")
    assert len(_identifiers(full)) == 19
    assert "2x4-V" not in full
    monkeypatch.setattr(settings, "enable_design_compact_few_shots", False)
    assert PromptBuilder._compact_few_shot_context(task, _plan(), component_source="") == ""


def test_default_configuration_disables_retrieval() -> None:
    from config.config import Settings

    assert Settings.model_fields.get("enable_design_compact_few_shot_selection").default is False
