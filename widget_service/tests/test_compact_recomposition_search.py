"""2×2重组的候选顺序、搜索预算、回退及异常边界回归。"""

import copy
import json
from collections.abc import Iterator

import pytest

from services import compact_outer_recomposition as recomposition
from services.card_validation import CompactDslValidationError
from services.compact_dsl_a2ui_converter import ComponentRow, DataRow


def _leaves(*, with_action: bool = True) -> list[ComponentRow]:
    rows = [
        ComponentRow("title", "SingleLineTitle", {"title": "天气"}),
        ComponentRow("body", "SecondaryBody", {
            "role": "supporting", "width": "matchParent", "fontSize": 14,
            "items": [{"label": "状态", "value": {"path": "/data/state"}}],
        }),
    ]
    if with_action:
        rows.append(ComponentRow("action", "PillButton", {
            "label": "查看", "onClick": [{"call": "openWeather", "args": {}}],
        }))
    return rows


def _root(leaves: list[ComponentRow]) -> ComponentRow:
    return ComponentRow(
        "root", "Column", {"width": "matchParent", "padding": 12},
        tuple(row.component_id for row in leaves),
    )


def _source(*, with_action: bool = True) -> str:
    leaves = _leaves(with_action=with_action)
    return recomposition._serialize([_root(leaves), *leaves, DataRow("/data/state", "晴")])


def _search(candidates: Iterator[str]) -> recomposition.OuterRecompositionResult:
    task = {"size": "2x2"}
    return recomposition._search_recomposition_candidates(
        "original-source",
        candidates,
        reasons=("height_capacity",),
        validation_context={"task_spec": task, "card_spec": {"suggestSize": "2x2"}},
        compact_plan=None,
        task_spec=task,
    )


@pytest.mark.parametrize("with_action", [False, True])
def test_candidate_order_and_content_preservation(with_action):
    first = _leaves(with_action=with_action)
    second = copy.deepcopy(first)
    second[1].props["items"] = [{"value": "合组正文", "maxLines": 2}]
    variants = [first, second]
    root = _root(first)
    data = [DataRow("/data/state", "晴")]
    used = {"root", "title", "body", "action"}
    before = copy.deepcopy((root, variants, data, used))
    gaps = (6, 4, 2, 0) if with_action else (6,)
    candidates = recomposition._iter_recomposition_candidates(
        root, variants, data, gaps=gaps, pressure_ids=set(), used=used,
    )

    observed = []
    for source in candidates:
        rows = [json.loads(line) for line in source.splitlines()]
        components = {}
        for row in rows:
            if len(row) >= 3:
                components[row[0]] = row
        candidate_root = components.get("root")
        flow = components.get("content_flow")
        body = components.get("body")
        title = components.get("title")
        assert candidate_root is not None
        assert flow is not None
        assert body is not None
        assert title is not None
        observed.append((body[2].get("items"), candidate_root[2].get("itemMargin"),
                         flow[2].get("itemMargin")))
        assert candidate_root[2].get("padding") == 12
        assert title[2] == first[0].props
        assert rows[-1] == ["/data/state", "晴"]
        if with_action:
            action = components.get("action")
            assert action is not None
            assert action[2] == first[-1].props

    expected = []
    for variant in variants:
        for gap in gaps:
            for content_gap in (6, 4, 2, 0):
                expected.append((variant[1].props.get("items"), gap, content_gap))
    assert observed == expected
    assert (root, variants, data, used) == before


def test_unbuildable_candidates_do_not_consume_search_budget(monkeypatch):
    leaves = _leaves()
    candidates = recomposition._iter_recomposition_candidates(
        _root(leaves), [[leaves[0]], leaves], [],
        gaps=(6,), pressure_ids=set(), used={"root", "title", "body", "action"},
    )

    def reject(*_args, **_kwargs):
        raise CompactDslValidationError(["candidate rejected"])

    monkeypatch.setattr(recomposition, "validate_compact_dsl", reject)
    result = _search(candidates)
    assert result.source_dsl == "original-source"
    assert result.candidate_count == 4
    assert result.applied is False


def test_search_stops_at_first_candidate_passing_both_checks(monkeypatch):
    events = []
    generated = []

    def candidates():
        for name in ("invalid", "missing-fact", "accepted", "unused"):
            generated.append(name)
            yield name

    def validate(source, **kwargs):
        assert kwargs.get("enforce_model_component_types") is True
        events.append(("validate", source))
        if source == "invalid":
            raise CompactDslValidationError(["candidate rejected"])

    def coverage(source, _plan, _task):
        events.append(("coverage", source))
        return ["missing fact"] if source == "missing-fact" else []

    monkeypatch.setattr(recomposition, "validate_compact_dsl", validate)
    monkeypatch.setattr(recomposition, "compact_plan_coverage_errors", coverage)
    result = _search(candidates())

    assert result == recomposition.OuterRecompositionResult(
        "accepted", ("height_capacity",), 3, True,
    )
    assert generated == ["invalid", "missing-fact", "accepted"]
    assert events == [
        ("validate", "invalid"), ("validate", "missing-fact"),
        ("coverage", "missing-fact"), ("validate", "accepted"), ("coverage", "accepted"),
    ]


@pytest.mark.parametrize("candidate_count", [0, 3, 32, 40])
@pytest.mark.parametrize("reject_at", ["validation", "coverage"])
def test_search_budget_and_exhausted_result(monkeypatch, candidate_count, reject_at):
    generated = []
    validated = []

    def candidates():
        for index in range(candidate_count):
            generated.append(index)
            yield str(index)

    def validate(source, **_kwargs):
        validated.append(source)
        if reject_at == "validation":
            raise CompactDslValidationError(["candidate rejected"])

    monkeypatch.setattr(recomposition, "validate_compact_dsl", validate)
    monkeypatch.setattr(
        recomposition, "compact_plan_coverage_errors", lambda *_args: ["missing fact"],
    )
    result = _search(candidates())
    expected_count = min(candidate_count, 32)
    assert result == recomposition.OuterRecompositionResult(
        "original-source", ("height_capacity",), expected_count,
    )
    assert len(generated) == expected_count
    assert len(validated) == expected_count


@pytest.mark.parametrize("crash_at", ["generation", "validation", "coverage"])
def test_program_errors_are_not_treated_as_candidate_rejection(monkeypatch, crash_at):
    failure = RuntimeError("implementation failure")

    def candidates():
        if crash_at == "generation":
            raise failure
        yield "candidate"

    def validate(*_args, **_kwargs):
        if crash_at == "validation":
            raise failure

    def coverage(*_args):
        raise failure

    monkeypatch.setattr(recomposition, "validate_compact_dsl", validate)
    monkeypatch.setattr(recomposition, "compact_plan_coverage_errors", coverage)
    with pytest.raises(RuntimeError) as captured:
        _search(candidates())
    assert captured.value is failure


@pytest.mark.parametrize("with_action,expected_count", [(False, 4), (True, 16)])
@pytest.mark.parametrize("accept", [False, True])
def test_public_recomposition_keeps_original_or_first_accepted_candidate(
    monkeypatch, with_action, expected_count, accept,
):
    source = _source(with_action=with_action)
    validations = []

    def validate(candidate, **_kwargs):
        validations.append(candidate)
        if candidate == source or not accept:
            raise CompactDslValidationError(["root: vertical layout requires at least 180vp"])

    monkeypatch.setattr(recomposition, "validate_compact_dsl", validate)
    monkeypatch.setattr(recomposition, "compact_plan_coverage_errors", lambda *_args: [])
    result = recomposition.recompose_small_card(
        source, task_spec={"size": "2x2"}, card_spec={"suggestSize": "2x2"},
        protocol_profile=None, layout_scope="test-layout", compact_plan=None,
    )
    assert validations[0] == source
    assert result.reasons == ("height_capacity",)
    assert result.applied is accept
    assert result.candidate_count == (1 if accept else expected_count)
    if accept:
        assert result.source_dsl == validations[1]
        assert len(validations) == 2
    else:
        assert result.source_dsl == source
        assert len(validations) == expected_count + 1


@pytest.mark.parametrize("case", ["other-size", "no-layout", "invalid-source", "valid", "syntax"])
def test_ineligible_or_unpressured_source_is_preserved(monkeypatch, case):
    source = "invalid" if case == "invalid-source" else _source()

    def validate(*_args, **_kwargs):
        if case == "syntax":
            raise CompactDslValidationError(["component contract failed"])

    def unexpected_candidates(*_args, **_kwargs):
        pytest.fail("ineligible or unpressured source must not enter candidate search")

    monkeypatch.setattr(recomposition, "validate_compact_dsl", validate)
    monkeypatch.setattr(recomposition, "compact_plan_coverage_errors", lambda *_args: [])
    monkeypatch.setattr(recomposition, "_iter_recomposition_candidates", unexpected_candidates)
    result = recomposition.recompose_small_card(
        source, task_spec={"size": "2x2"},
        card_spec={"suggestSize": "2x4" if case == "other-size" else "2x2"},
        protocol_profile=None, layout_scope=None if case == "no-layout" else "test-layout",
        compact_plan=None,
    )
    assert result == recomposition.OuterRecompositionResult(source)
