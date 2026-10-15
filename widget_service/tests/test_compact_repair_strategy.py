"""验证 Design Compact 修复路由的失败指纹与逐级升级。"""

import pytest

from services.compact_repair_strategy import CompactRepairStrategyTracker


def _issue(message: str, *, code: str = "COMPACT_DSL_VALIDATION_FAILED") -> dict:
    return {
        "stage": "validation",
        "code": code,
        "message": message,
    }


def test_component_contract_migrates_without_stopping_before_global_limit() -> None:
    tracker = CompactRepairStrategyTracker(max_repair_attempts=4)
    errors = [_issue("component metric: unsupported prop unitText")]

    first = tracker.next_directive("dsl-v1", errors)
    second = tracker.next_directive("dsl-v2", errors)
    resumed_targeted = tracker.next_directive("dsl-v2", errors)

    assert first.repair_strategy == "component_contract_repair"
    assert first.scope == "component"
    assert first.retry_target == "dsl_local_repair"
    assert "容量修复的受控选型例外" not in first.instruction
    assert second.repair_strategy == "plan_guided_recompose"
    assert second.scope == "full_dsl"
    assert second.retry_target == "dsl_recompose"
    assert resumed_targeted.repair_strategy == "component_contract_repair"
    assert resumed_targeted.retry_target == "dsl_local_repair"
    assert resumed_targeted.retryable is True


def test_info_block_progress_value_error_gets_precise_non_degrading_repair() -> None:
    tracker = CompactRepairStrategyTracker()
    errors = [
        _issue(
            "battery: InfoBlock.primaryText must be a finite number or "
            "complete numeric percentage."
        )
    ]

    directive = tracker.next_directive("dsl-v1", errors)

    assert directive.repair_strategy == "component_contract_repair"
    assert directive.scope == "component"
    assert "保留 visual、icon、fillColor" in directive.instruction
    assert 'unit:"%"' in directive.instruction
    assert "不得删除 visual" in directive.instruction


@pytest.mark.parametrize("count", [0, 7])
def test_secondary_body_item_overflow_guides_optional_removal_without_dropping_plan(
    count: int,
) -> None:
    tracker = CompactRepairStrategyTracker()
    directive = tracker.next_directive("dsl-v1", [
        _issue(f"details: SecondaryBody.items requires 1 to 6 entries (got {count})."),
    ])
    assert directive.repair_strategy == "component_contract_repair"
    if count == 0:
        assert "优先删除" not in directive.instruction
    else:
        assert "优先删除重复、与需求无关或已接受Plan未要求的可选补充项" in directive.instruction
        assert "整理为1–6项" in directive.instruction
        assert "不得按数组顺序直接截掉末尾项" in directive.instruction
        assert "删除Plan要求的must/should事实" in directive.instruction
        assert "仍需现有Drop授权" in directive.instruction
        assert "不为6项放宽布局预算" in directive.instruction


@pytest.mark.parametrize("font_size", [14, 12])
def test_secondary_body_font_size_error_gets_recipe_aware_repair(font_size: int) -> None:
    tracker = CompactRepairStrategyTracker()
    errors = [
        _issue(
            f"weather_line: SecondaryBody.fontSize must be the fixed Recipe value {font_size}. "
            "SecondaryBody uses fontSize 14 / lineHeight 19 for a single row "
            "and fontSize 12 / lineHeight 16 for multiple rows."
        )
    ]

    directive = tracker.next_directive("dsl-v1", errors)

    assert directive.repair_strategy == "component_contract_repair"
    assert "只把 fontSize 改为错误信息给出的固定 Recipe 值" in directive.instruction
    assert "只有一行且各项 maxLines 都为 1（默认 1）" in directive.instruction
    assert "固定为 14fp/19vp" in directive.instruction
    assert "超过一行或任一项 maxLines 为 2" in directive.instruction
    assert "整组固定为 12fp/16vp，行间距为 2vp" in directive.instruction
    assert "两项同行用 14；两项 columns:1 分行用 12" in directive.instruction
    assert "按最终行布局重新核算字号与高度" in directive.instruction
    assert "不得仅为缩小字号拆散信息组或删除事实" in directive.instruction
    for obsolete in ("role", "body", "metadata", "supporting"):
        assert obsolete not in directive.instruction


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
    transition = tracker.next_directive("dsl-v6", second_errors)

    assert first.category == "layout_capacity"
    assert first.repair_strategy == "rebudget"
    assert first.scope == "sublayout"
    assert second.repair_strategy == "parent_layout_recompose"
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
    for directive in (first, second, third, fallback_first, fallback_second):
        assert "容量修复的受控选型例外" not in directive.instruction
    assert transition.repair_strategy == "plan_guided_recompose"
    assert transition.fallback_attempt == 2
    assert transition.fallback_remaining_attempts == 0
    assert transition.retryable is True


def test_multi_region_overflow_with_missing_fact_recomposes_parent_immediately() -> None:
    tracker = CompactRepairStrategyTracker()
    errors = [
        _issue(
            "Plan fact is missing from visible DSL: 天气预警。",
            code="COMPACT_PLAN_COVERAGE_FAILED",
        ),
        {
            "stage": "validation",
            "code": "COMPACT_DSL_VALIDATION_FAILED",
            "message": (
                "component meeting_panel: vertical layout requires at least "
                "114vp within 110vp"
            ),
            "compactDiagnostics": [
                {
                    "code": "COMPACT_LAYOUT_HEIGHT_OVERFLOW",
                    "componentId": "meeting_panel",
                }
            ],
        },
        {
            "stage": "validation",
            "code": "COMPACT_DSL_VALIDATION_FAILED",
            "message": (
                "component weather_panel: vertical layout requires at least "
                "124vp within 110vp"
            ),
            "compactDiagnostics": [
                {
                    "code": "COMPACT_LAYOUT_HEIGHT_OVERFLOW",
                    "componentId": "weather_panel",
                }
            ],
        },
    ]

    directive = tracker.next_directive("dsl-v1", errors)

    assert directive.category == "layout_capacity"
    assert directive.repair_strategy == "parent_layout_recompose"
    assert directive.scope == "parent_layout"
    assert "多个语义分区同时容量超限" in directive.instruction
    assert "先恢复缺失事实" in directive.instruction


def test_capacity_text_compaction_exception_is_sent_only_when_relevant() -> None:
    tracker = CompactRepairStrategyTracker()
    source = "\n".join(
        [
            '["value","EmphasizedData",{"value":96}]',
            '["details","TextBlock",{"items":[]}]',
        ]
    )
    directive = tracker.next_directive(
        source,
        [_issue("component body: vertical layout requires at least 142vp within 126vp")],
    )

    assert "容量修复的受控选型例外" in directive.instruction
    assert "一个SecondaryBody.items" in directive.instruction


def test_fixed_side_slot_primary_text_overflow_prefers_split_panels() -> None:
    tracker = CompactRepairStrategyTracker()
    source = "\n".join(
        [
            '["root","Layout",{"layout":"W-content-side-slots"},'
            '["content","exercise_slot","action_slot"]]',
            '["content","Region",{"variant":"center"},["summary"]]',
            '["summary","EmphasisText",{"mainText":"运动复盘"}]',
            '["exercise_slot","InfoBlock",{"variant":"slot",'
            '"primaryText":"户外跑步","secondaryText":"完整运动明细"}]',
            '["action_slot","CardButton",{"label":"打开锻炼页","onClick":[]}]',
        ]
    )
    errors = [
        _issue(
            "component exercise_slot_primary: text width overflow; complete text "
            "needs about 294vp in one line, but its allocated text area is 116vp."
        )
    ]

    directive = tracker.next_directive(source, errors)

    assert directive.category == "layout_capacity"
    assert directive.repair_strategy == "parent_layout_recompose"
    assert directive.scope == "parent_layout"
    assert "优先比较并改用 W-split-panels" in directive.instruction
    assert "保留全部事实和 Action" in directive.instruction


def test_root_layout_mismatch_takes_priority_over_capacity_error() -> None:
    tracker = CompactRepairStrategyTracker()
    errors = [
        _issue(
            "component root: vertical layout requires at least 174vp within 126vp; "
            "it overflows by 48vp."
        ),
        _issue(
            "Compact layout does not match scope W-plan-guided: "
            "slot root must have 2 children, got 3."
        ),
    ]

    directive = tracker.next_directive("dsl-v1", errors)

    assert directive.category == "layout_structure"
    assert directive.repair_strategy == "parent_layout_recompose"
    assert directive.scope == "parent_layout"


def test_chinese_semantic_layout_error_uses_structure_route() -> None:
    tracker = CompactRepairStrategyTracker()
    errors = [
        _issue(
            "语义布局不符合合同：节点 today：当前父区域不支持 Region.variant；"
            "请选择已登记的 Layout、Region 或 Group 变体。"
        )
    ]

    directive = tracker.next_directive("dsl-v1", errors)

    assert directive.category == "layout_structure"
    assert directive.repair_strategy == "semantic_layout_contract_repair"
    assert directive.scope == "parent_layout"
    assert directive.retry_target == "dsl_local_repair"


def test_semantic_layout_contract_repair_escalates_in_bounded_steps() -> None:
    tracker = CompactRepairStrategyTracker()
    errors = [
        _issue(
            "语义布局不符合合同：节点 right：子组件数量应为 [3]，实际为 2；"
            "Region.variant='title-content-action' 要求 [title, content, PillButton]。"
        )
    ]

    first = tracker.next_directive("dsl-v1", errors)
    repeated = tracker.next_directive("dsl-v1", errors)
    parent = tracker.next_directive("dsl-v1", errors)
    full = tracker.next_directive("dsl-v1", errors)

    assert first.repair_strategy == "semantic_layout_contract_repair"
    assert first.retry_target == "dsl_local_repair"
    assert "直属 children" in first.instruction
    assert "title-count 只占标题角色" in first.instruction
    assert "title-content-action 的动作角色必须使用 PillButton" in first.instruction
    assert repeated.repair_strategy == "semantic_layout_contract_repair"
    assert repeated.no_progress is True
    assert "不得原样返回上一轮 DSL" in repeated.instruction
    assert parent.repair_strategy == "parent_layout_recompose"
    assert parent.scope == "parent_layout"
    assert "本轮仍不重写整份 DSL" in parent.instruction
    assert full.repair_strategy == "plan_guided_recompose"
    assert full.scope == "full_dsl"


def test_compact_fallback_bridges_contract_repair_then_resumes_drop() -> None:
    tracker = CompactRepairStrategyTracker()
    layout_errors = [
        _issue("component body: vertical layout requires at least 142vp within 126vp")
    ]
    contract_errors = [
        _issue(
            "component day0.props.items[].label: SecondaryBody.items[].label "
            "only accepts a static value."
        )
    ]
    plan = {
        "info_required": [
            {
                "requirement": "补充时间",
                "priority": "should",
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

    tracker.next_directive("dsl-v1", layout_errors)
    tracker.next_directive("dsl-v2", layout_errors)
    first_fallback = tracker.next_directive("dsl-v3", layout_errors)
    second_fallback = tracker.next_directive("dsl-v4", layout_errors)
    component_repair = tracker.next_directive("dsl-v5", contract_errors)
    resumed_drop = tracker.next_directive(
        source,
        layout_errors,
        compact_plan=plan,
        task_spec=task_spec,
    )

    assert first_fallback.repair_strategy == "compact_component"
    assert second_fallback.repair_strategy == "compact_component"
    assert second_fallback.fallback_attempt == 1
    assert component_repair.category == "component_contract"
    assert component_repair.repair_strategy == "component_contract_repair"
    assert component_repair.scope == "component"
    assert component_repair.retry_target == "dsl_local_repair"
    assert component_repair.retryable is True
    assert "动态 label" in component_repair.instruction
    assert "items[].value Expression" in component_repair.instruction
    assert resumed_drop.repair_strategy == "drop_optional_component"
    assert resumed_drop.optional_drop is not None
    assert resumed_drop.optional_drop.component_id == "time"


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize(
    ("max_attempts", "fourth_is_layout"), [(5, True), (3, True), (5, False)],
)
def test_fourth_repair_can_drop_should_component_only_with_layout_error_and_budget(
    size: str, max_attempts: int, fourth_is_layout: bool,
) -> None:
    tracker = CompactRepairStrategyTracker(max_repair_attempts=max_attempts)
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
        "size": size,
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

    for _ in range(3):
        directive = tracker.next_directive(
            source,
            errors,
            compact_plan=plan,
            task_spec=task_spec,
        )
        assert directive.repair_strategy != "drop_optional_component"
        assert tracker.allowed_omitted_fact_indexes == ()

    fourth_errors = errors if fourth_is_layout else [_issue("time: unsupported prop unitText")]
    drop = tracker.next_directive(
        source, fourth_errors, compact_plan=plan, task_spec=task_spec,
    )
    if max_attempts == 3:
        assert drop.repair_strategy == "exhausted"
        assert tracker.allowed_omitted_fact_indexes == ()
        return
    if not fourth_is_layout:
        assert drop.repair_strategy == "component_contract_repair"
        assert tracker.allowed_omitted_fact_indexes == ()
        return
    assert drop.repair_strategy == "drop_optional_component"
    assert drop.fallback_stage == "drop_optional_component"
    assert drop.fallback_attempt == 0
    assert drop.fallback_remaining_attempts == 2
    assert "已进入有界删除兜底" in drop.instruction
    assert "上一轮没有执行 Drop" not in drop.instruction
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


def test_drop_no_progress_counts_toward_global_limit_without_early_stop() -> None:
    tracker = CompactRepairStrategyTracker(max_repair_attempts=10)
    contract_errors = [_issue("component battery: unsupported prop unitText")]
    layout_errors = [_issue("component body: vertical layout requires at least 142vp within 126vp")]
    plan = {
        "info_required": [
            {
                "requirement": "补充时间",
                "priority": "should",
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

    tracker.next_directive("dsl-contract", contract_errors)
    tracker.next_directive("dsl-layout-1", layout_errors)
    tracker.next_directive("dsl-layout-2", layout_errors)
    tracker.next_directive("dsl-layout-3", layout_errors)
    tracker.next_directive("dsl-layout-4", layout_errors)

    drop_directives = []
    for _ in range(5):
        drop_directives.append(
            tracker.next_directive(
                source,
                layout_errors,
                compact_plan=plan,
                task_spec=task_spec,
            )
        )
    exhausted = tracker.next_directive(
        source,
        layout_errors,
        compact_plan=plan,
        task_spec=task_spec,
    )

    assert [item.repair_strategy for item in drop_directives] == [
        "drop_optional_component"
    ] * 5
    assert [item.fallback_attempt for item in drop_directives] == [0, 1, 2, 3, 4]
    assert [item.fallback_attempt_limit for item in drop_directives] == [5] * 5
    assert [item.fallback_remaining_attempts for item in drop_directives] == [
        5,
        4,
        3,
        2,
        1,
    ]
    assert drop_directives[0].no_progress is False
    assert drop_directives[1].no_progress is True
    assert "上一轮没有执行 Drop" in drop_directives[1].instruction
    assert "从直接父组件 children 中移除该 ID" in drop_directives[1].instruction
    assert "禁止原样返回上一轮 Compact DSL" in drop_directives[1].instruction
    assert exhausted.repair_strategy == "exhausted"
    assert exhausted.retryable is False
    assert exhausted.no_progress is True
    assert exhausted.fallback_attempt == 5
    assert exhausted.fallback_attempt_limit == 5
    assert exhausted.to_prompt_payload()["stopReason"] == "global_attempt_limit"


def test_drop_selects_next_candidate_after_previous_candidate_is_removed() -> None:
    tracker = CompactRepairStrategyTracker(max_repair_attempts=10)
    errors = [_issue("component body: vertical layout requires at least 142vp within 126vp")]
    plan = {
        "info_required": [
            {
                "requirement": "补充时间",
                "priority": "should",
                "dataId": "/data/calendar/start",
            },
            {
                "requirement": "补充标题",
                "priority": "should",
                "dataId": "/data/calendar/title",
            },
        ]
    }
    task_spec = {
        "size": "2x2",
        "dataModelSchema": {
            "data": {
                "calendar": {
                    "start": {"type": "string"},
                    "title": {"type": "string"},
                }
            }
        },
        "eventCandidates": [],
    }
    source = "\n".join(
        [
            '["root","Column",{},["time","title"]]',
            '["time","SecondaryBody",{"role":"metadata","items":'
            '[{"value":{"path":"/data/calendar/start"}}]}]',
            '["title","SingleLineTitle",{"title":{"path":"/data/calendar/title"}}]',
        ]
    )

    first_drop = None
    for attempt in range(1, 7):
        first_drop = tracker.next_directive(
            source if attempt >= 5 else f"dsl-v{attempt}",
            errors,
            compact_plan=plan,
            task_spec=task_spec,
        )
        if first_drop.repair_strategy == "drop_optional_component":
            break

    assert first_drop is not None
    assert first_drop.optional_drop is not None
    assert first_drop.optional_drop.component_id == "time"

    source_after_first_drop = "\n".join(
        [
            '["root","Column",{},["title"]]',
            '["title","SingleLineTitle",{"title":{"path":"/data/calendar/title"}}]',
        ]
    )
    second_drop = tracker.next_directive(
        source_after_first_drop,
        errors,
        compact_plan=plan,
        task_spec=task_spec,
    )

    assert second_drop.repair_strategy == "drop_optional_component"
    assert second_drop.optional_drop is not None
    assert second_drop.optional_drop.component_id == "title"
    assert tracker.allowed_omitted_fact_indexes == (0, 1)
    assert second_drop.to_prompt_payload()["approvedOmittedFactIndexes"] == [0, 1]

    transition = tracker.next_directive(
        '["root","Column",{},[]]',
        errors,
        compact_plan=plan,
        task_spec=task_spec,
    )

    assert transition.repair_strategy == "plan_guided_recompose"
    assert transition.retryable is True
    assert tracker.allowed_omitted_fact_indexes == (0, 1)


def test_compact_component_plan_coverage_bridge_does_not_stop_early() -> None:
    tracker = CompactRepairStrategyTracker(max_repair_attempts=10)
    layout_errors = [
        _issue("component body: vertical layout requires at least 142vp within 126vp")
    ]
    coverage_errors = [
        _issue(
            "Plan fact is missing from visible DSL: /data/healthSport/heartRate",
            code="COMPACT_PLAN_COVERAGE_FAILED",
        )
    ]

    assert tracker.next_directive("dsl-v1", layout_errors).repair_strategy == "rebudget"
    assert (
        tracker.next_directive("dsl-v2", layout_errors).repair_strategy
        == "plan_guided_recompose"
    )
    assert (
        tracker.next_directive("dsl-v3", layout_errors).repair_strategy
        == "compact_component"
    )
    assert (
        tracker.next_directive("dsl-v4", coverage_errors).repair_strategy
        == "coverage_restore"
    )
    assert (
        tracker.next_directive("dsl-v5", layout_errors).repair_strategy
        == "compact_component"
    )

    second_coverage_restore = tracker.next_directive("dsl-v6", coverage_errors)

    assert second_coverage_restore.repair_strategy == "coverage_restore"
    assert second_coverage_restore.retry_target == "dsl_local_repair"
    assert second_coverage_restore.retryable is True


def test_global_limit_is_the_only_exhausted_route() -> None:
    tracker = CompactRepairStrategyTracker(max_repair_attempts=2)
    errors = [_issue("component metric: unsupported prop unitText")]

    assert tracker.next_directive("dsl-v1", errors).retryable is True
    assert tracker.next_directive("dsl-v2", errors).retryable is True

    exhausted = tracker.next_directive("dsl-v3", errors)

    assert exhausted.repair_strategy == "exhausted"
    assert exhausted.retry_target == "stop"
    assert exhausted.retryable is False
    assert exhausted.to_prompt_payload()["stopReason"] == "global_attempt_limit"


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
    assert directive.repair_strategy == "parent_layout_recompose"
    assert directive.scope == "parent_layout"
