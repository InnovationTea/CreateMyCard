"""真实批跑失败夹具回归；固定源及 Plan，隔离原有自动重组，不请求模型。"""

import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest

from compact_script_helpers import options
from models.artifact import ArtifactMeta, WidgetArtifact
from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.compact_contract_repair import CONTRACT_RULES, contract_candidates
from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    ComponentRow,
    convert_compact_dsl_to_a2ui,
    parse_compact_dsl_rows,
)
from services.compact_plan import evaluate_compact_plan_coverage
from services.compact_script_repair import ScriptRepairBudget, _improved, repair_static_errors
from services.generation_pipeline import (
    DesignCompactProcessor,
    DslProcessingContext,
    DslProcessingResult,
    QualityIssue,
)
from services.protocol_registry import A2UIProtocolRegistry
from services.theme_style_roles import layout_phase
from services.validator import ArtifactValidator

_FIXTURES = json.loads(
    (Path(__file__).parent / "fixtures/compact_script_real_cases.json").read_text(encoding="utf-8")
)


def case(identifier):
    cases = _FIXTURES.get("cases")
    assert isinstance(cases, list)
    original = next(item for item in cases if item.get("id") == identifier)
    source = original.get("source")
    data = copy.deepcopy(original.get("context"))
    task, card = data.get("task"), data.get("card")
    assert isinstance(source, str) and isinstance(task, dict) and isinstance(card, dict)
    context = DslProcessingContext(
        size=task.get("size"),
        task_spec=task,
        card_spec=card,
        protocol_profile=A2UIProtocolRegistry(data.get("standardProfile")).get_profile(),
        design_profile_id=data.get("designProfile"),
        layout_scope=data.get("layoutScope"),
        compact_plan=data.get("plan"),
        colorless_layout=True,
    )
    return source, context


def evaluate(source, context):
    design = A2UIProtocolRegistry.read_design_protocol_profile(context.design_profile_id)
    design["appVersion"] = context.task_spec.get("appVersion")
    with layout_phase(True, context.task_spec):
        try:
            coverage = evaluate_compact_plan_coverage(
                source,
                context.compact_plan,
                context.task_spec,
            )
            issues = tuple(
                QualityIssue("validation", "COMPACT_PLAN_COVERAGE_FAILED", message)
                for message in coverage.errors
            )
            try:
                validate_compact_dsl(
                    source,
                    task_spec=context.task_spec,
                    card_spec=context.card_spec,
                    compact_plan=context.compact_plan,
                    protocol_profile=design,
                    layout_scope=context.layout_scope,
                    enforce_model_component_types=True,
                )
            except CompactDslValidationError as exc:
                failed = DesignCompactProcessor._validation_failure(
                    source,
                    exc.errors,
                    groups=exc.groups,
                )
                return replace(failed, issues=(*issues, *failed.issues))
            if issues:
                return DslProcessingResult(source, issues=issues)
            standard = convert_compact_dsl_to_a2ui(
                source,
                size=context.size,
                protocol_profile=design,
            )
            data_ids = []
            for binding in context.card_spec.get("dataBindings", []):
                data_ids.append(binding.get("capabilityId"))
            assets = [asset.get("id") for asset in context.task_spec.get("assetCandidates", [])]
            artifact = WidgetArtifact(
                genui=standard,
                cardSpec=context.card_spec,
                taskSpec=context.task_spec,
                effectiveCapabilities={
                    "data": data_ids,
                    "event": context.task_spec.get("eventCandidates", []),
                    "asset": assets,
                },
                meta=ArtifactMeta(
                    protocolProfileId=context.protocol_profile.get("id"),
                    capabilityRegistryVersion="app-11.7.7.300_rom-7.0",
                    createdAt=0,
                ),
            )
            errors = ArtifactValidator().validate_layout(artifact, context.protocol_profile)
            issues = tuple(QualityIssue("validation", "ARTIFACT", error) for error in errors)
            return DslProcessingResult(source, standard, issues)
        except CompactDslConversionError as exc:
            return DesignCompactProcessor._validation_failure(source, (str(exc),))


@pytest.mark.parametrize("identifier", ["Q017", "Q037"])
@pytest.mark.asyncio
async def test_real_contract_failures_pass_complete_validation_without_original_repair(identifier):
    source, context = case(identifier)
    frozen = copy.deepcopy(context)
    before = evaluate(source, context)
    assert before.errors
    candidates = []

    async def check(candidate):
        value = evaluate(candidate, context)
        candidates.append(value)
        return value

    budget = ScriptRepairBudget(12)
    final = await repair_static_errors(
        before,
        settings=options(),
        evaluate=check,
        budget=budget,
        context=context,
    )
    assert not final.errors and final.standard_dsl
    assert context == frozen and budget.candidates_used <= 12
    assert not evaluate(final.source_dsl, context).errors
    old_rows = parse_compact_dsl_rows(source, expand_layouts=False)
    new_rows = parse_compact_dsl_rows(final.source_dsl, expand_layouts=False)
    assert [row for row in old_rows if not isinstance(row, ComponentRow)] == [
        row for row in new_rows if not isinstance(row, ComponentRow)
    ]
    if identifier == "Q037":
        assert not _improved(before, candidates[0])
        assert len(candidates) == 2
        assert "'是' : '否'" in final.source_dsl
    else:
        assert '"TableText"' in final.source_dsl


@pytest.mark.parametrize("identifier", ["Q059", "Q105", "Q031"])
@pytest.mark.asyncio
async def test_unresolved_real_cases_do_not_commit_intermediate_source(identifier):
    source, context = case(identifier)
    before = evaluate(source, context)
    budget = ScriptRepairBudget(12)

    async def check(candidate):
        return evaluate(candidate, context)

    final = await repair_static_errors(
        before,
        settings=options(),
        evaluate=check,
        budget=budget,
        context=context,
    )
    assert final is before and final.errors
    assert budget.candidates_used <= 12


@pytest.mark.parametrize("rule", list(CONTRACT_RULES))
def test_contract_switch_disables_its_candidates(rule):
    source, context = case("Q059")
    raw = [json.loads(line) for line in source.splitlines()]
    for row in raw:
        if len(row) == 3 and row[1] == "ContentBlock":
            row[1:3] = ["EmphasisText", {"mainText": row[2].get("body")}]
    if rule in {"primary-content", "fixed-slot", "plan-fact"}:
        identifier = "Q017" if rule == "primary-content" else "Q037"
        source, context = case(identifier)
        if rule == "plan-fact":
            before = evaluate(source, context)
            fixed = next(
                s for r, s in contract_candidates(before, options(), context) if r == "fixed-slot"
            )
            source = fixed
    elif rule != "known-component":
        source = "\n".join(json.dumps(row, ensure_ascii=False) for row in raw)
    if rule == "numeric-label":
        source, context = case("Q105")
        raw = [json.loads(line) for line in source.splitlines()]
        for row in raw:
            if len(row) == 3 and row[1] == "DataDisplay":
                row[2].pop("icon", None)
        source = "\n".join(json.dumps(row, ensure_ascii=False) for row in raw)
    if rule == "event-target":
        source, context = case("Q031")
        task = copy.deepcopy(context.task_spec)
        task["eventCandidates"] = task.get("eventCandidates", [])[:1]
        context = replace(context, task_spec=task)
        source = source.replace("events/0/entityId", "events/2/entityId", 1)
    before = evaluate(source, context)
    enabled_candidates = list(contract_candidates(before, options(), context))
    assert any(name == rule for name, _source in enabled_candidates)
    disabled = options(**{f"enable_compact_{rule.replace('-', '_')}_repair": False})
    generated = list(contract_candidates(before, disabled, context))
    assert all(name != rule for name, _source in generated)


def test_event_target_candidate_is_exact_and_duplicate_ids_cannot_be_guessed():
    source, original = case("Q031")
    assert not any(
        name == "event-target"
        for name, _s in contract_candidates(
            evaluate(source, original),
            options(),
            original,
        )
    )
    task = copy.deepcopy(original.task_spec)
    events = task.get("eventCandidates")
    assert isinstance(events, list)
    task["eventCandidates"] = events[:1]
    context = replace(original, task_spec=task)
    source = source.replace("events/0/entityId", "events/2/entityId", 1)
    before = evaluate(source, context)

    candidates = list(contract_candidates(before, options(), context))
    candidate = next(text for name, text in candidates if name == "event-target")
    assert '"entityId":"{{ ${/data/calendar/events/0/entityId} }}"' in candidate
    checked = evaluate(candidate, context)
    assert not any("Plan action is missing" in issue.message for issue in checked.errors)
    assert not any("no matching button" in issue.message for issue in checked.errors)


def test_missing_fact_requires_real_initialized_path():
    source, context = case("Q037")
    before = evaluate(source, context)
    fixed = next(s for r, s in contract_candidates(before, options(), context) if r == "fixed-slot")
    kept = []
    for line in fixed.splitlines():
        if json.loads(line)[0] != "/data/earphone/isConnected":
            kept.append(line)
    fixed = "\n".join(kept)
    generated = contract_candidates(evaluate(fixed, context), options(), context)
    assert not any(rule == "plan-fact" for rule, _source in generated)


def test_numeric_label_does_not_drop_the_only_icon():
    source, context = case("Q105")
    generated = contract_candidates(evaluate(source, context), options(), context)
    assert not any(rule == "numeric-label" for rule, _source in generated)


@pytest.mark.asyncio
async def test_lookahead_budget_cannot_commit_new_errors():
    source, context = case("Q037")
    before = evaluate(source, context)

    async def check(candidate):
        return evaluate(candidate, context)

    budget = ScriptRepairBudget(1)
    final = await repair_static_errors(
        before,
        settings=options(),
        evaluate=check,
        budget=budget,
        context=context,
    )
    assert final is before
    assert budget.candidates_used == 1
