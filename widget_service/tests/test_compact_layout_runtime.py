"""验证版本化布局契约与正式 Few-shot 保持一致。"""

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.compact_dsl_a2ui_converter import ComponentRow, parse_compact_dsl_rows
from services.compact_layout_runtime import (
    LAYOUT_CONTRACT_VERSION,
    CompactLayoutRuntimeError,
    layout_ids_for_size,
    load_layout_contract,
    match_compact_layout,
)
from services.compact_prompt_loader import assemble_prompts
from services.prompt_builder import PromptBuilder

PROMPT_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source"
)
PROMPTS = assemble_prompts(PROMPT_SOURCE)
def _few_shots() -> list[tuple[str, str, str, str]]:
    examples: list[tuple[str, str, str, str]] = []
    for size in ("2x2", "2x4"):
        document = PROMPTS[f"fewshot_{size}"]
        for section in re.split(r"(?m)^## ", document)[1:]:
            identifier = re.search(rf"({size}-V\d\d)", section)
            task = re.search(r"### user\s*\n```json\s*\n(.*?)\n```", section, re.S)
            source = re.search(r"```genui\s*\n(.*?)\n```", section, re.S)
            assert identifier is not None
            assert task is not None
            assert source is not None
            task_spec = SimpleNamespace(**json.loads(task.group(1)))
            layout_scope = PromptBuilder._layout_scope(task_spec)
            examples.append((identifier.group(1), size, layout_scope, source.group(1)))
    return examples


def _components(source: str) -> list[ComponentRow]:
    return [
        row
        for row in parse_compact_dsl_rows(source)
        if isinstance(row, ComponentRow)
    ]


def _layout_pseudocodes() -> list[tuple[str, str, str]]:
    pseudocodes: list[tuple[str, str, str]] = []
    for size in ("2x2", "2x4"):
        document = (PROMPT_SOURCE / f"layouts/{size}.md").read_text(encoding="utf-8")
        for section in re.split(r"(?m)^### `", document)[1:]:
            layout_id = section.split("`", 1)[0]
            source = re.search(r"```genui\s*\n(.*?)\n```", section, re.S)
            if layout_id.startswith(("S-", "W-")):
                assert source is not None, layout_id
                pseudocodes.append((layout_id, size, source.group(1)))
    return pseudocodes


def _layout_fixture(layout_id: str) -> str:
    fixture_ids = {
        "S-dual-info": "2x2-V07",
        "W-content-side-slots": "2x4-V04",
    }
    fixture_id = fixture_ids.get(layout_id)
    assert fixture_id is not None, layout_id
    for identifier, _, _, source in _few_shots():
        if identifier == fixture_id:
            return source
    raise AssertionError(f"Missing layout fixture: {layout_id}")


def _mutate_rows(source: str, mutator) -> str:
    output: list[str] = []
    for line in source.splitlines():
        row = json.loads(line)
        mutator(row)
        output.append(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
    return "\n".join(output)


def _task_spec_for_source(source: str, *, size: str) -> dict:
    event_candidates: list[dict] = []
    for line in source.splitlines():
        row = json.loads(line)
        if len(row) < 3:
            continue
        event_candidates.extend(row[2].get("onClick", []))
    return {
        "userQuery": "布局契约测试",
        "size": size,
        "eventCandidates": event_candidates,
        "assetCandidates": [],
        "dataModelSchema": {"data": {}},
    }


def test_layout_contract_registers_the_documented_layouts() -> None:
    contract = load_layout_contract()
    assert contract.get("version") == LAYOUT_CONTRACT_VERSION
    assert layout_ids_for_size("2x2") == (
        "S-center",
        "S-title-content",
        "S-title-dual-content",
        "S-quad-content",
        "S-title-content-action",
        "S-title-primary-secondary-action",
        "S-title-dual-column-action",
        "S-title-anchor",
        "S-content-dual-action",
        "S-dual-info",
    )
    assert layout_ids_for_size("2x4") == (
        "W-top-bottom",
        "W-split-panels",
        "W-content-side-slots",
        "W-four-slots",
    )


@pytest.mark.parametrize(
    "identifier,size,layout_scope,source",
    _few_shots(),
    ids=[item[0] for item in _few_shots()],
)
def test_formal_few_shot_matches_its_layout(
    identifier: str,
    size: str,
    layout_scope: str,
    source: str,
) -> None:
    result = match_compact_layout(
        _components(source),
        size=size,
        layout_scope=layout_scope,
    )
    assert result.layout_id in load_layout_contract()["scopes"].get(
        layout_scope,
        [layout_scope],
    )


@pytest.mark.parametrize(
    "layout_id,size,source",
    _layout_pseudocodes(),
    ids=[item[0] for item in _layout_pseudocodes()],
)
def test_documented_layout_uses_abstract_genui_pseudocode(
    layout_id: str,
    size: str,
    source: str,
) -> None:
    del layout_id, size
    rows = [json.loads(line) for line in source.splitlines()]
    assert rows[0][0] == "root"
    assert any(
        isinstance(row[1], str) and row[1].startswith("<")
        for row in rows
        if len(row) >= 3
    )


def test_layout_scope_rejects_wrong_geometry_before_expansion() -> None:
    source = '\n'.join(
        (
            '["root","Column",{"padding":8,"alignItems":"center",'
            '"justifyContent":"center"},["value"]]',
            '["value","Text",{"content":"42","fontSize":30}]',
        )
    )
    with pytest.raises(CompactDslValidationError, match="S-center"):
        validate_compact_dsl(
            source,
            task_spec={"size": "2x2"},
            card_spec={"suggestSize": "2x2"},
            layout_scope="S-center",
        )


def test_unknown_layout_scope_is_rejected() -> None:
    _, _, _, source = _few_shots()[0]
    with pytest.raises(CompactLayoutRuntimeError, match="Unknown Compact layout scope"):
        match_compact_layout(
            _components(source),
            size="2x2",
            layout_scope="S-unknown",
        )


def test_s_dual_info_rejects_non_contract_slot_heights() -> None:
    source = _layout_fixture("S-dual-info")

    def mutate(row: list) -> None:
        if row[0] == "shanghai":
            row[2]["height"] = 55
        if row[0] == "beijing":
            row[2]["height"] = 71

    with pytest.raises(CompactLayoutRuntimeError, match="height"):
        match_compact_layout(
            _components(_mutate_rows(source, mutate)),
            size="2x2",
            layout_scope="S-dual-info",
        )


def test_w_content_side_slots_rejects_non_contract_slot_heights() -> None:
    source = _layout_fixture("W-content-side-slots")

    def mutate(row: list) -> None:
        if row[0] == "info_slot":
            row[2]["height"] = 50
        if row[0] == "action_slot":
            row[2]["height"] = 64

    invalid_source = _mutate_rows(source, mutate)
    with pytest.raises(CompactDslValidationError, match="height"):
        validate_compact_dsl(
            invalid_source,
            task_spec=_task_spec_for_source(invalid_source, size="2x4"),
            card_spec={"suggestSize": "2x4", "dataBindings": []},
            layout_scope="W-content-side-slots",
        )


def test_w_content_side_slots_rejects_action_then_information() -> None:
    source = _layout_fixture("W-content-side-slots")

    def mutate(row: list) -> None:
        if row[0] == "info_slot":
            row[1] = "CardButton"
            row[2]["onClick"] = [
                {"call": "clickToDeeplink", "args": {"intentName": "Settings"}}
            ]
        if row[0] == "action_slot":
            row[1] = "InfoBlock"
            row[2].pop("onClick", None)

    with pytest.raises(CompactLayoutRuntimeError, match="W-content-side-slots"):
        match_compact_layout(
            _components(_mutate_rows(source, mutate)),
            size="2x4",
            layout_scope="W-content-side-slots",
        )


def test_w_content_side_slots_rejects_event_on_information_slot() -> None:
    source = _layout_fixture("W-content-side-slots")
    action: list[dict] = []
    for line in source.splitlines():
        row = json.loads(line)
        if row[0] == "action_slot":
            action = row[2]["onClick"]

    def mutate(row: list) -> None:
        if row[0] == "info_slot":
            row[2]["onClick"] = action
        if row[0] == "action_slot":
            row[2].pop("onClick", None)

    invalid_source = _mutate_rows(source, mutate)
    with pytest.raises(CompactDslValidationError, match="event"):
        validate_compact_dsl(
            invalid_source,
            task_spec=_task_spec_for_source(invalid_source, size="2x4"),
            card_spec={"suggestSize": "2x4", "dataBindings": []},
            layout_scope="W-content-side-slots",
        )
