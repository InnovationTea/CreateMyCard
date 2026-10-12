"""验证 Design Compact 修复路由的失败指纹与逐级升级。"""

from services.compact_repair_strategy import CompactRepairStrategyTracker


def _issue(message: str, *, code: str = "COMPACT_DSL_VALIDATION_FAILED") -> dict:
    return {
        "stage": "validation",
        "code": code,
        "message": message,
    }


def test_component_contract_gets_only_one_targeted_attempt() -> None:
    tracker = CompactRepairStrategyTracker()
    errors = [_issue("component metric: unsupported prop unitText")]

    first = tracker.next_directive("dsl-v1", errors)
    second = tracker.next_directive("dsl-v2", errors)
    exhausted = tracker.next_directive("dsl-v2", errors)

    assert first.repair_strategy == "targeted"
    assert first.scope == "component"
    assert first.retry_target == "dsl_local_repair"
    assert second.repair_strategy == "plan_guided_recompose"
    assert second.scope == "full_dsl"
    assert second.retry_target == "dsl_recompose"
    assert exhausted.repair_strategy == "exhausted"
    assert exhausted.retry_target == "stop"
    assert exhausted.retryable is False


def test_layout_capacity_escalates_from_rebudget_to_full_recomposition() -> None:
    tracker = CompactRepairStrategyTracker()
    first_errors = [
        _issue(
            "component body: vertical layout requires at least 142vp within 126vp; "
            "it overflows by 16vp. Occupancy: title=12vp, body=122vp."
        )
    ]
    second_errors = [
        _issue(
            "component replacement: vertical layout requires at least 138vp within 126vp; "
            "it overflows by 12vp. Occupancy: summary=42vp, details=88vp."
        )
    ]

    first = tracker.next_directive("dsl-v1", first_errors)
    second = tracker.next_directive("dsl-v2", second_errors)
    third = tracker.next_directive("dsl-v3", second_errors)
    fallback_first = tracker.next_directive("dsl-v4", second_errors)
    fallback_second = tracker.next_directive("dsl-v5", second_errors)
    exhausted = tracker.next_directive("dsl-v6", second_errors)

    assert first.category == "layout_capacity"
    assert first.repair_strategy == "rebudget"
    assert first.scope == "sublayout"
    assert second.repair_strategy == "structural"
    assert second.scope == "parent_layout"
    assert second.consecutive_failures == 1
    assert third.repair_strategy == "plan_guided_recompose"
    assert third.scope == "full_dsl"
    assert third.consecutive_failures == 2
    assert fallback_first.repair_strategy == "compact_component"
    assert fallback_first.fallback_stage == "compact_component"
    assert fallback_first.fallback_attempt == 0
    assert fallback_first.fallback_attempt_limit == 2
    assert fallback_first.fallback_remaining_attempts == 2
    assert fallback_second.repair_strategy == "compact_component"
    assert fallback_second.fallback_attempt == 1
    assert fallback_second.fallback_remaining_attempts == 1
    assert exhausted.repair_strategy == "exhausted"
    assert exhausted.fallback_attempt == 2
    assert exhausted.fallback_remaining_attempts == 0
    assert exhausted.retryable is False


def test_compact_component_fallback_stays_active_for_non_layout_regression() -> None:
    tracker = CompactRepairStrategyTracker()
    layout_errors = [
        _issue("component body: vertical layout requires at least 142vp within 126vp")
    ]
    contract_errors = [_issue("component summary: unsupported prop density")]

    tracker.next_directive("dsl-v1", layout_errors)
    tracker.next_directive("dsl-v2", layout_errors)
    first_fallback = tracker.next_directive("dsl-v3", layout_errors)
    second_fallback = tracker.next_directive("dsl-v4", contract_errors)

    assert first_fallback.repair_strategy == "compact_component"
    assert second_fallback.repair_strategy == "compact_component"
    assert second_fallback.fallback_attempt == 1


def test_compact_fallback_can_drop_one_program_selected_should_component() -> None:
    tracker = CompactRepairStrategyTracker()
    errors = [
        _issue("component body: vertical layout requires at least 142vp within 126vp")
    ]
    plan = {
        "info_required": [
            {
                "requirement": "补充时间",
                "priority": "should",
                "dataId": "/data/calendar/start",
                "componentHints": ["SecondaryBody"],
            }
        ]
    }
    task_spec = {
        "size": "2x2",
        "dataModelSchema": {
            "data": {
                "calendar": {
                    "start": {"type": "string", "sampleValue": "10:00"},
                }
            }
        },
        "eventCandidates": [],
    }
    source = "\n".join(
        [
            '["root","Column",{},["time"]]',
            '["time","SecondaryBody",{"role":"metadata","items":'
            '[{"value":{"path":"/data/calendar/start"}}]}]',
        ]
    )

    drop = None
    for attempt in range(1, 7):
        drop = tracker.next_directive(
            source if attempt >= 5 else f"dsl-v{attempt}",
            errors,
            compact_plan=plan,
            task_spec=task_spec,
        )
        if drop.repair_strategy == "drop_optional_component":
            break

    assert drop is not None
    assert drop.repair_strategy == "drop_optional_component"
    assert drop.fallback_stage == "drop_optional_component"
    assert drop.optional_drop is not None
    assert drop.optional_drop.component_id == "time"
    assert drop.optional_drop.contains_must_facts is False
    assert tracker.allowed_omitted_fact_indexes == (0,)
    assert drop.to_prompt_payload()["optionalDrop"]["allowedOmittedFactIndexes"] == [0]


def test_compact_fallback_can_drop_one_program_selected_must_component() -> None:
    tracker = CompactRepairStrategyTracker()
    errors = [
        _issue("component body: vertical layout requires at least 142vp within 126vp")
    ]
    plan = {
        "info_required": [
            {
                "requirement": "核心时间",
                "priority": "must",
                "dataId": "/data/calendar/start",
            }
        ]
    }
    task_spec = {
        "size": "2x2",
        "dataModelSchema": {"data": {"calendar": {"start": {"type": "string"}}}},
        "eventCandidates": [],
    }
    source = (
        '["root","Column",{},["time"]]\n'
        '["time","SecondaryBody",{"role":"metadata","items":'
        '[{"value":{"path":"/data/calendar/start"}}]}]'
    )

    drop = None
    for attempt in range(1, 7):
        drop = tracker.next_directive(
            source if attempt >= 5 else f"dsl-v{attempt}",
            errors,
            compact_plan=plan,
            task_spec=task_spec,
        )
        if drop.repair_strategy == "drop_optional_component":
            break

    assert drop is not None
    assert drop.repair_strategy == "drop_optional_component"
    assert drop.optional_drop is not None
    assert drop.optional_drop.component_id == "time"
    assert drop.optional_drop.contains_must_facts is True
    assert tracker.allowed_omitted_fact_indexes == (0,)
    assert drop.to_prompt_payload()["optionalDrop"]["containsMustFacts"] is True


def test_unchanged_dsl_is_reported_as_no_progress_and_escalated() -> None:
    tracker = CompactRepairStrategyTracker()
    errors = [_issue("component metric: unsupported prop unitText")]

    tracker.next_directive("same-dsl", errors)
    repeated = tracker.next_directive("same-dsl", errors)

    assert repeated.no_progress is True
    assert repeated.repair_strategy == "plan_guided_recompose"
    assert repeated.retry_target == "dsl_recompose"


def test_plan_coverage_has_a_dedicated_first_repair_route() -> None:
    tracker = CompactRepairStrategyTracker()
    errors = [
        _issue(
            "Plan fact is missing from visible DSL: /data/calendar/title",
            code="COMPACT_PLAN_COVERAGE_FAILED",
        )
    ]

    directive = tracker.next_directive("dsl-v1", errors)

    assert directive.category == "plan_coverage"
    assert directive.repair_strategy == "coverage_restore"
    assert directive.scope == "information_group"
    assert directive.retry_target == "dsl_local_repair"


def test_layout_structure_starts_at_parent_layout_scope() -> None:
    tracker = CompactRepairStrategyTracker()
    errors = [
        _issue(
            "Compact layout does not match scope W-plan-guided: "
            "slot root/1 must have 2 children, got 4."
        )
    ]

    directive = tracker.next_directive("dsl-v1", errors)

    assert directive.category == "layout_structure"
    assert directive.repair_strategy == "structural"
    assert directive.scope == "parent_layout"
