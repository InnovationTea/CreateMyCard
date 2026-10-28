"""验证 Design Compact 修复路由的失败指纹与逐级升级。"""

import pytest

from services.compact_repair_strategy import (
    CompactRepairStrategyTracker,
    compact_capacity_recovery_failure_category,
)


def _issue(message: str, *, code: str = "COMPACT_DSL_VALIDATION_FAILED") -> dict:
    return {
        "stage": "validation",
        "code": code,
        "message": message,
    }


def test_capacity_recovery_keeps_layout_cause_after_display_fact_was_removed() -> None:
    tracker = CompactRepairStrategyTracker()
    tracker.next_directive(
        "dsl-v1",
        [_issue("component body: vertical layout requires at least 142vp within 126vp")],
    )
    errors = [
        _issue(
            "Plan fact is missing from visible DSL: 当前温度 (/data/weather/temp).",
            code="COMPACT_PLAN_COVERAGE_FAILED",
        )
    ]

    category = compact_capacity_recovery_failure_category(
        errors,
        layout_failure_seen=tracker.layout_failure_seen,
    )

    assert category == "layout_capacity"


def test_capacity_recovery_keeps_layout_cause_after_bounded_fallback_omits_fact() -> None:
    errors = [
        _issue(
            "Plan fact was omitted by the bounded fallback: 当前温度。",
            code="COMPACT_PLAN_FACT_OMITTED",
        ),
        _issue(
            "component support: SecondaryBody is auxiliary and cannot be the only "
            "information component in the card.",
        ),
    ]

    category = compact_capacity_recovery_failure_category(
        errors,
        layout_failure_seen=True,
    )

    assert category == "layout_capacity"


def test_text_only_secondary_body_repair_suggests_bounded_table_text() -> None:
    tracker = CompactRepairStrategyTracker()
    source = "\n".join(
        [
            '["root","Layout",{"layout":"W-split-panels"},["left"]]',
            '["left","SecondaryBody",{"items":['
            '{"label":"温度","value":"29℃"},'
            '{"label":"天气","value":"多云"}]}]',
        ]
    )
    errors = [
        _issue(
            "component left: SecondaryBody is auxiliary and cannot be the only "
            "information component in the card."
        )
    ]

    directive = tracker.next_directive(source, errors)

    assert directive.repair_strategy == "component_contract_repair"
    assert "TableText" in directive.instruction
    assert "38vp" in directive.instruction
    assert "52vp" in directive.instruction
    assert "optionalDrop或approvedOmissions" in directive.instruction


def test_height_overflow_diagnostic_code_enters_layout_capacity_repair() -> None:
    tracker = CompactRepairStrategyTracker()
    errors = [
        {
            "stage": "validation",
            "code": "COMPACT_DSL_VALIDATION_FAILED",
            "message": "当前语义分区的完整内容高度超过可用高度。",
            "compactDiagnostics": [
                {
                    "code": "COMPACT_LAYOUT_HEIGHT_OVERFLOW",
                    "componentId": "support",
                }
            ],
        }
    ]

    directive = tracker.next_directive("dsl-v1", errors)

    assert directive.category == "layout_capacity"
    assert directive.repair_strategy == "rebudget"
    assert directive.scope == "sublayout"
    assert "重算受影响信息组的完整高度与间距" in directive.instruction


def test_long_button_label_repair_only_rewrites_visible_wording() -> None:
    tracker = CompactRepairStrategyTracker()
    errors = [
        {
            "stage": "validation",
            "code": "COMPACT_DSL_VALIDATION_FAILED",
            "message": "PillButton.label must contain at most 5 visible characters.",
            "compactDiagnostics": [
                {
                    "code": "COMPACT_DISPLAY_ACTION_LABEL_TOO_LONG",
                    "componentId": "action",
                    "propertyPath": "/label",
                }
            ],
        }
    ]

    directive = tracker.next_directive("dsl-v1", errors)

    assert directive.repair_strategy == "component_contract_repair"
    assert directive.scope == "component"
    assert "label缩短到最多5个字符" in directive.instruction
    assert "一键导航去公司”改为“导航去公司" in directive.instruction
    assert "完整保留onClick的call、args、动作目标" in directive.instruction
    assert "不得复制、删除、改目标或虚构第二个Action" in directive.instruction


@pytest.mark.parametrize(
    ("errors", "layout_failure_seen"),
    [
        (
            [
                _issue(
                    "Plan fact is missing from visible DSL: 当前温度 (/data/weather/temp).",
                    code="COMPACT_PLAN_COVERAGE_FAILED",
                )
            ],
            False,
        ),
        (
            [
                _issue(
                    "Plan action is missing from visible DSL: 打开天气 (open_weather).",
                    code="COMPACT_PLAN_COVERAGE_FAILED",
                )
            ],
            True,
        ),
        (
            [
                _issue(
                    "Plan fact is displayed more than once in visible DSL: 当前温度.",
                    code="COMPACT_PLAN_COVERAGE_FAILED",
                )
            ],
            True,
        ),
    ],
)
def test_capacity_recovery_ignores_unrelated_plan_coverage_failures(
    errors: list[dict],
    layout_failure_seen: bool,
) -> None:
    category = compact_capacity_recovery_failure_category(
        errors,
        layout_failure_seen=layout_failure_seen,
    )

    assert category is None


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


def test_duplicate_plan_fact_stays_in_targeted_deduplication_repair() -> None:
    tracker = CompactRepairStrategyTracker()
    issue = _issue(
        "Plan fact is displayed more than once in visible DSL: 最高心率 "
        "(/data/health/max); expected 1, got 2.",
        code="COMPACT_PLAN_COVERAGE_FAILED",
    )
    issue["duplicateFacts"] = [
        {
            "requirement": "最高心率",
            "dataId": "/data/health/max",
            "expectedVisibleCount": 1,
            "actualVisibleCount": 2,
            "occurrences": [],
        }
    ]

    first = tracker.next_directive("dsl-v1", [issue])
    second = tracker.next_directive("dsl-v2", [issue])
    third = tracker.next_directive("dsl-v3", [issue])

    assert first.repair_strategy == "deduplicate_visible_facts"
    assert first.scope == "information_group"
    assert first.retry_target == "dsl_local_repair"
    assert "每个报错 dataId 最终只在一个可见属性中出现" in first.instruction
    assert "删除数据行" in first.instruction
    assert second.repair_strategy == "deduplicate_visible_facts"
    assert second.scope == "information_group"
    assert second.retry_target == "dsl_local_repair"
    assert "重复超额数量没有减少" in second.instruction
    assert third.repair_strategy == "deduplicate_visible_facts"
    assert third.scope == "information_group"
    assert third.retry_target == "dsl_local_repair"


def test_duplicate_plan_fact_does_not_trigger_prior_layout_recomposition() -> None:
    tracker = CompactRepairStrategyTracker()
    layout_issue = _issue("component body: vertical layout requires at least 142vp within 126vp.")
    duplicate_issue = _issue(
        "Plan fact is displayed more than once in visible DSL: 当前温度 "
        "(/data/weather/current/temperatureText); expected 1, got 2.",
        code="COMPACT_PLAN_COVERAGE_FAILED",
    )
    duplicate_issue["duplicateFacts"] = [{
        "dataId": "/data/weather/current/temperatureText",
        "expectedVisibleCount": 1,
        "actualVisibleCount": 2,
        "occurrences": [],
    }]

    tracker.next_directive("dsl-layout", [layout_issue])
    directive = tracker.next_directive(
        "dsl-duplicate",
        [duplicate_issue],
        compact_plan={},
        task_spec={},
    )

    assert directive.repair_strategy == "deduplicate_visible_facts"
    assert directive.scope == "information_group"
    assert directive.retry_target == "dsl_local_repair"


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
            "SecondaryBody uses fontSize 14 / lineHeight 14 for a single row "
            "and fontSize 12 / lineHeight 12 for multiple rows."
        )
    ]

    directive = tracker.next_directive("dsl-v1", errors)

    assert directive.repair_strategy == "component_contract_repair"
    assert "只把 fontSize 改为错误信息给出的固定 Recipe 值" in directive.instruction
    assert "只有一行且各项 maxLines 都为 1（默认 1）" in directive.instruction
    assert "固定为 14fp/14vp" in directive.instruction
    assert "超过一行或任一项 maxLines 为 2" in directive.instruction
    assert "整组固定为 12fp/12vp，行间距为 2vp" in directive.instruction
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


def test_2x2_pill_capacity_repair_offers_anchor_layout_migration() -> None:
    tracker = CompactRepairStrategyTracker()
    source = "\n".join(
        [
            '["root","Layout",{"layout":"S-title-content-action"},'
            '["title","content","action"]]',
            '["title","SingleLineTitle",{"title":"通勤助手"}]',
            '["content","EmphasisText",{"mainText":"29℃"}]',
            '["action","PillButton",{"label":"导航去公司","icon":'
            '"resources/base/media/icon_car.svg","onClick":[{}]}]',
        ]
    )
    errors = [
        _issue(
            "component root: vertical layout requires at least 142vp within 126vp"
        )
    ]

    directive = tracker.next_directive(
        source,
        errors,
        task_spec={"size": "2x2"},
    )

    assert directive.category == "layout_capacity"
    assert "可把S-title-anchor作为同级合法布局候选" in directive.instruction
    assert "不能只把PillButton改名为CircleButton" in directive.instruction
    assert "按[title, primary, support, action]重排直属children" in directive.instruction
    assert "完整保留原onClick和icon" in directive.instruction
    assert "accessibility.label" in directive.instruction


@pytest.mark.parametrize(
    ("size", "layout"),
    [
        ("2x4", "S-title-content-action"),
        ("2x2", "S-title-content"),
    ],
)
def test_anchor_layout_migration_is_not_offered_outside_relevant_capacity_case(
    size: str,
    layout: str,
) -> None:
    tracker = CompactRepairStrategyTracker()
    action_type = "PillButton" if layout.endswith("action") else "EmphasisText"
    source = "\n".join(
        [
            f'["root","Layout",{{"layout":"{layout}"}},'
            '["title","content","action"]]',
            '["title","SingleLineTitle",{"title":"通勤助手"}]',
            '["content","EmphasisText",{"mainText":"29℃"}]',
            f'["action","{action_type}",{{"label":"导航去公司","onClick":[{{}}]}}]',
        ]
    )

    directive = tracker.next_directive(
        source,
        [_issue("component root: vertical layout requires at least 142vp within 126vp")],
        task_spec={"size": size},
    )

    assert "S-title-anchor作为同级合法布局候选" not in directive.instruction


def test_capacity_recovery_drops_should_only_candidate_on_first_layout_failure() -> None:
    tracker = CompactRepairStrategyTracker(capacity_recovery=True)
    errors = [_issue("component body: vertical layout requires at least 142vp within 126vp")]
    plan = {
        "info_required": [
            {
                "requirement": "补充开始时间",
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
        '["root","Column",{},["main","time"]]\n'
        '["main","EmphasisText",{"mainText":"日程"}]\n'
        '["time","SecondaryBody",{"items":'
        '[{"value":{"path":"/data/calendar/start"}}]}]'
    )

    directive = tracker.next_directive(
        source,
        errors,
        compact_plan=plan,
        task_spec=task_spec,
    )

    assert directive.repair_strategy == "drop_optional_component"
    assert directive.optional_drop is not None
    assert directive.optional_drop.component_id == "time"
    assert directive.optional_drop.contains_must_facts is False


def test_capacity_recovery_uses_must_fact_as_drop_fallback_after_preserving_core() -> None:
    tracker = CompactRepairStrategyTracker(capacity_recovery=True)
    errors = [_issue("component body: vertical layout requires at least 142vp within 126vp")]
    plan = {
        "info_required": [
            {
                "requirement": f"核心状态{index}",
                "priority": "must",
                "dataId": f"/data/device/status{index}",
            }
            for index in range(3)
        ]
    }
    task_spec = {
        "size": "2x2",
        "dataModelSchema": {
            "data": {
                "device": {
                    f"status{index}": {"type": "string"} for index in range(3)
                }
            }
        },
        "eventCandidates": [],
    }
    source = (
        '["root","Column",{},["status"]]\n'
        '["status","TableText",{"items":['
        '{"label":"状态0","value":{"path":"/data/device/status0"}},'
        '{"label":"状态1","value":{"path":"/data/device/status1"}},'
        '{"label":"状态2","value":{"path":"/data/device/status2"}}]}]'
    )

    directive = tracker.next_directive(
        source,
        errors,
        compact_plan=plan,
        task_spec=task_spec,
    )

    assert directive.repair_strategy == "drop_optional_component"
    assert directive.optional_drop is not None
    assert directive.optional_drop.component_id == "status"
    assert directive.optional_drop.partial is True
    assert directive.optional_drop.item_indexes == (2,)
    assert directive.optional_drop.contains_must_facts is True
    assert tracker.allowed_omitted_fact_indexes == (2,)


def test_table_text_over_three_items_drops_one_item_per_repair_immediately() -> None:
    tracker = CompactRepairStrategyTracker(max_repair_attempts=3)
    plan = {
        "info_required": [
            {
                "requirement": f"状态{index}",
                "priority": "must",
                "dataId": f"/data/device/status{index}",
            }
            for index in range(6)
        ]
    }
    task_spec = {
        "size": "2x2",
        "dataModelSchema": {
            "data": {
                "device": {
                    f"status{index}": {"type": "string"} for index in range(6)
                }
            }
        },
        "eventCandidates": [],
    }
    errors = [_issue("status: TableText.items requires 2 to 3 entries.")]

    def source(item_count: int) -> str:
        items = ",".join(
            f'{{"label":"状态{index}",'
            f'"value":{{"path":"/data/device/status{index}"}}}}'
            for index in range(item_count)
        )
        return (
            '["root","Column",{},["status"]]\n'
            f'["status","TableText",{{"items":[{items}]}}]'
        )

    expected_indexes = (5, 4, 3)
    directives = []
    for item_count, expected_index in zip(range(6, 3, -1), expected_indexes, strict=True):
        directive = tracker.next_directive(
            source(item_count),
            errors,
            compact_plan=plan,
            task_spec=task_spec,
        )
        directives.append(directive)
        assert directive.repair_strategy == "drop_optional_component"
        assert directive.optional_drop is not None
        assert directive.optional_drop.item_indexes == (expected_index,)

    assert tracker.allowed_omitted_fact_indexes == (3, 4, 5)
    assert "直接进入程序授权的最小 Drop" in directives[0].instruction
    assert "若删除后仍超过三项" in directives[1].instruction


def test_drop_uses_reachable_auxiliary_candidate_and_requires_core_reattach() -> None:
    tracker = CompactRepairStrategyTracker(max_repair_attempts=6)
    errors = [_issue("Unreachable component(s): core")]
    plan = {
        "info_required": [
            {
                "requirement": "会议标题",
                "priority": "must",
                "dataId": "/data/calendar/title",
            },
            {
                "requirement": "会议地点",
                "priority": "should",
                "dataId": "/data/calendar/location",
            },
        ]
    }
    task_spec = {
        "size": "2x4",
        "dataModelSchema": {
            "data": {
                "calendar": {
                    "title": {"type": "string"},
                    "location": {"type": "string"},
                }
            }
        },
        "eventCandidates": [],
    }
    source = "\n".join(
        [
            '["root","Column",{},["details"]]',
            '["core","EmphasisText",{"mainText":'
            '{"path":"/data/calendar/title"}}]',
            '["details","SecondaryBody",{"items":['
            '{"label":"标题 ","value":{"path":"/data/calendar/title"}},'
            '{"label":"地点 ","value":{"path":"/data/calendar/location"}}]}]',
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
    drop = tracker.next_directive(
        source,
        errors,
        compact_plan=plan,
        task_spec=task_spec,
    )

    assert drop.repair_strategy == "drop_optional_component"
    assert drop.optional_drop is not None
    assert drop.optional_drop.component_id == "details"
    assert drop.optional_drop.fact_indexes == (1,)
    assert drop.optional_drop.requires_core_reattach is True
    payload = drop.to_prompt_payload()["optionalDrop"]
    assert payload["requiresCoreReattach"] is True
    assert payload["protectedCoreComponentIds"] == ["core"]
    assert "至少一个组件重新挂到 root 可达" in drop.instruction

    removed_without_reattach = "\n".join(
        [
            '["root","Column",{},[]]',
            '["core","EmphasisText",{"mainText":'
            '{"path":"/data/calendar/title"}}]',
        ]
    )
    repeated_drop = tracker.next_directive(
        removed_without_reattach,
        errors,
        compact_plan=plan,
        task_spec=task_spec,
    )

    assert repeated_drop.repair_strategy == "drop_optional_component"
    assert repeated_drop.optional_drop == drop.optional_drop


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


def test_missing_semantic_references_receive_executable_repair_guidance() -> None:
    tracker = CompactRepairStrategyTracker()
    source = "\n".join(
        [
            '["root","Layout",{"layout":"W-content-side-slots"},'
            '["content","upper","lower"]]',
            '["content","Region",{"variant":"center"},["status"]]',
            '["status","EmphasisText",{"mainText":"已连接"}]',
            '["daily","CardButton",{"label":"每日推荐","onClick":[{}]}]',
            '["favorite","CardButton",{"label":"收藏歌单","onClick":[{}]}]',
        ]
    )
    errors = [
        _issue(
            "语义布局不符合合同：节点 upper：引用了不存在的组件。"
            "请选择已登记的 Layout、Region 或 Group 变体。"
        )
    ]

    directive = tracker.next_directive(source, errors)

    assert directive.repair_strategy == "parent_layout_recompose"
    assert "root.children[1]=upper" in directive.instruction
    assert "root.children[2]=lower" in directive.instruction
    assert "daily(CardButton)" in directive.instruction
    assert "favorite(CardButton)" in directive.instruction
    assert "不要只修复首个报错引用" in directive.instruction


def test_region_action_conflict_reports_actual_roles_and_parent_recompose() -> None:
    tracker = CompactRepairStrategyTracker()
    source = "\n".join(
        [
            '["root","Layout",{"layout":"W-split-panels"},'
            '["earphone_panel","music_panel"]]',
            '["earphone_panel","Region",{"variant":"center"},["status"]]',
            '["status","EmphasisText",{"mainText":"已连接"}]',
            '["music_panel","Region",{"variant":"title-content-action"},'
            '["music_title","music_favorite","music_daily"]]',
            '["music_title","SingleLineTitle",{"title":"我的音乐"}]',
            '["music_favorite","PillButton",{"label":"收藏歌单","onClick":[{}]}]',
            '["music_daily","PillButton",{"label":"每日推荐","onClick":[{}]}]',
        ]
    )
    errors = [
        _issue(
            "语义布局不符合合同：节点 music_panel：Action 必须放在所选 Region "
            "的底部动作角色中。请选择已登记的 Layout、Region 或 Group 变体。"
        )
    ]
    plan = {
        "info_required": [
            {"actionId": "event.open.music.favorite", "priority": "must"},
            {"actionId": "event.open.music.daily", "priority": "must"},
        ]
    }

    directive = tracker.next_directive(source, errors, compact_plan=plan)

    assert directive.repair_strategy == "semantic_layout_contract_repair"
    assert "1:music_favorite(PillButton Action)" in directive.instruction
    assert "当前检测到 2 个" in directive.instruction
    assert "event.open.music.favorite" in directive.instruction
    assert "当前 Region 无法同时容纳这些 Action" in directive.instruction
    assert "提升到共同父布局" in directive.instruction


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
        '["root","Column",{},["main","time"]]\n'
        '["main","EmphasisText",{"mainText":"日程"}]\n'
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
            '["root","Column",{},["main","time"]]',
            '["main","EmphasisText",{"mainText":"日程"}]',
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
        '["root","Column",{},["main","time"]]\n'
        '["main","EmphasisText",{"mainText":"日程"}]\n'
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
        '["root","Column",{},["main","time"]]\n'
        '["main","EmphasisText",{"mainText":"日程"}]\n'
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
            '["root","Column",{},["main","time","title"]]',
            '["main","EmphasisText",{"mainText":"日程"}]',
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
            '["root","Column",{},["main","title"]]',
            '["main","EmphasisText",{"mainText":"日程"}]',
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
        '["root","Column",{},["main"]]\n'
        '["main","EmphasisText",{"mainText":"日程"}]',
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


def test_bounded_component_overflow_reports_exact_fit_and_overflow_items() -> None:
    tracker = CompactRepairStrategyTracker()
    source = "\n".join(
        [
            '["root","Column",{},["details"]]',
            '["details","SummaryList",{"items":["事项一","事项二",'
            '"事项三","事项四","事项五"]}]',
        ]
    )
    plan = {
        "info_required": [
            {"requirement": f"事项{label}", "priority": "must"}
            for label in ("一", "二", "三", "四", "五")
        ]
    }
    errors = [_issue("details: SummaryList.items requires 2 to 3 entries.")]

    directive = tracker.next_directive(source, errors, compact_plan=plan)
    payload = directive.to_prompt_payload()
    capacity_fit = payload["capacityFits"][0]

    assert directive.category == "layout_capacity"
    assert directive.repair_strategy == "rebudget"
    assert capacity_fit["actualItemCount"] == 5
    assert capacity_fit["allowedItemCount"] == {"min": 2, "max": 3}
    assert [item["value"] for item in capacity_fit["directlyFits"]] == [
        "事项一",
        "事项二",
        "事项三",
    ]
    assert [item["value"] for item in capacity_fit["doesNotFit"]] == [
        "事项四",
        "事项五",
    ]
    assert capacity_fit["doesNotFit"][0]["planFacts"][0]["factIndex"] == 3


def test_secondary_body_height_overflow_reports_item_level_capacity() -> None:
    tracker = CompactRepairStrategyTracker()
    source = "\n".join(
        [
            '["root","Column",{},["main","details"]]',
            '["main","EmphasisText",{"mainText":{"path":"/data/main"}}]',
            '["details","SecondaryBody",{"columns":1,"items":['
            '{"value":{"path":"/data/a"}},'
            '{"value":{"path":"/data/b"}},'
            '{"value":{"path":"/data/c"}}]}]',
        ]
    )
    plan = {
        "info_required": [
            {"requirement": "核心", "priority": "must", "dataId": "/data/main"},
            {"requirement": "信息A", "priority": "must", "dataId": "/data/a"},
            {"requirement": "信息B", "priority": "must", "dataId": "/data/b"},
            {"requirement": "信息C", "priority": "should", "dataId": "/data/c"},
        ]
    }
    errors = [
        {
            **_issue("当前父区域高度不足。"),
            "compactDiagnostics": [
                {
                    "code": "COMPACT_LAYOUT_HEIGHT_OVERFLOW",
                    "actual": {
                        "secondaryBodyFits": [
                            {
                                "componentId": "details",
                                "parentId": "root",
                                "actualRowCount": 3,
                                "maxRetainedRowCount": 2,
                                "effectiveColumnCount": 1,
                                "rowHeights": [12, 12, 12],
                                "rowSpacing": 2,
                                "directlyFitsItemIndexes": [0, 1],
                                "doesNotFitItemIndexes": [2],
                                "parentAvailableHeight": 40,
                            }
                        ]
                    },
                }
            ],
        }
    ]

    directive = tracker.next_directive(source, errors, compact_plan=plan)
    capacity_fit = directive.to_prompt_payload()["capacityFits"][0]

    assert capacity_fit["maxRetainedRowCount"] == 2
    assert capacity_fit["doesNotFit"][0]["itemIndex"] == 2
    assert capacity_fit["doesNotFit"][0]["planFacts"][0]["factIndex"] == 3


def test_capacity_overflow_allows_bounded_drop_after_one_lossless_repair() -> None:
    tracker = CompactRepairStrategyTracker(max_repair_attempts=5)
    plan = {
        "info_required": [
            {
                "requirement": f"事项{index}",
                "priority": "must",
                "dataId": f"/data/items/{index}",
            }
            for index in range(5)
        ]
    }
    task_spec = {
        "size": "2x4",
        "dataModelSchema": {
            "data": {
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                }
            }
        },
        "eventCandidates": [],
    }
    overflow_source = "\n".join(
        [
            '["root","Column",{},["details"]]',
            '["details","SummaryList",{"items":['
            '{"path":"/data/items/0"},{"path":"/data/items/1"},'
            '{"path":"/data/items/2"},{"path":"/data/items/3"},'
            '{"path":"/data/items/4"}]}]',
        ]
    )
    overflow_errors = [_issue("details: SummaryList.items requires 2 to 3 entries.")]
    regrouped_source = "\n".join(
        [
            '["root","Column",{},["main","details"]]',
            '["main","EmphasisText",{"mainText":"事项"}]',
            '["details","SecondaryBody",{"items":['
            '{"value":{"path":"/data/items/3"}},'
            '{"value":{"path":"/data/items/4"}}]}]',
        ]
    )
    regroup_errors = [
        _issue(
            "details: SecondaryBody is auxiliary and cannot be the only "
            "information component."
        )
    ]

    first = tracker.next_directive(
        overflow_source,
        overflow_errors,
        compact_plan=plan,
        task_spec=task_spec,
    )
    drop = tracker.next_directive(
        regrouped_source,
        regroup_errors,
        compact_plan=plan,
        task_spec=task_spec,
    )

    assert first.repair_strategy == "rebudget"
    assert drop.repair_strategy == "drop_optional_component"
    assert drop.optional_drop is not None
    assert drop.optional_drop.component_id == "details"
    assert drop.optional_drop.fact_indexes == (4,)
    assert drop.optional_drop.item_indexes == (1,)
    assert drop.optional_drop.partial is True
    assert "不再等待固定第四轮" in drop.instruction


def test_plan_coverage_does_not_carry_early_drop_into_layout_only_failures() -> None:
    tracker = CompactRepairStrategyTracker(max_repair_attempts=5)
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
        "size": "2x4",
        "dataModelSchema": {
            "data": {"calendar": {"start": {"type": "string"}}}
        },
        "eventCandidates": [],
    }
    source = "\n".join(
        [
            '["root","Column",{},["main","time"]]',
            '["main","EmphasisText",{"mainText":"日程"}]',
            '["time","SecondaryBody",{"items":['
            '{"value":{"path":"/data/calendar/start"}}]}]',
        ]
    )
    coverage_errors = [
        _issue(
            "Plan fact is missing from visible DSL: 补充时间",
            code="COMPACT_PLAN_COVERAGE_FAILED",
        )
    ]
    layout_errors = [
        _issue("component root: vertical layout requires at least 160vp within 126vp")
    ]

    first = tracker.next_directive(
        "dsl-with-missing-fact",
        coverage_errors,
        compact_plan=plan,
        task_spec=task_spec,
    )
    second = tracker.next_directive(
        source,
        layout_errors,
        compact_plan=plan,
        task_spec=task_spec,
    )
    third = tracker.next_directive(
        source,
        layout_errors,
        compact_plan=plan,
        task_spec=task_spec,
    )
    drop = tracker.next_directive(
        source,
        layout_errors,
        compact_plan=plan,
        task_spec=task_spec,
    )

    assert first.repair_strategy == "coverage_restore"
    assert second.repair_strategy != "drop_optional_component"
    assert second.retryable is True
    assert third.repair_strategy != "drop_optional_component"
    assert drop.repair_strategy == "drop_optional_component"
    assert drop.optional_drop is not None
    assert drop.optional_drop.component_id == "time"
    assert "Plan 事实缺失经过两次无损修复" not in drop.instruction


def test_repeated_plan_coverage_failure_gets_two_lossless_repairs_before_drop() -> None:
    tracker = CompactRepairStrategyTracker(max_repair_attempts=5)
    plan = {
        "info_required": [
            {
                "requirement": "会议标题",
                "priority": "must",
                "dataId": "/data/calendar/title",
            },
            {
                "requirement": "补充时间",
                "priority": "should",
                "dataId": "/data/calendar/start",
            }
        ]
    }
    task_spec = {
        "size": "2x2",
        "dataModelSchema": {
            "data": {
                "calendar": {
                    "title": {"type": "string"},
                    "start": {"type": "string"},
                }
            }
        },
        "eventCandidates": [],
    }
    source = "\n".join(
        [
            '["root","Column",{},["main","time"]]',
            '["main","EmphasisText",{"mainText":"日程"}]',
            '["time","SecondaryBody",{"items":['
            '{"value":{"path":"/data/calendar/start"}}]}]',
        ]
    )
    coverage_errors = [
        _issue(
            "Plan fact is missing from visible DSL: 会议标题",
            code="COMPACT_PLAN_COVERAGE_FAILED",
        )
    ]

    first = tracker.next_directive(
        "dsl-with-missing-fact-v1",
        coverage_errors,
        compact_plan=plan,
        task_spec=task_spec,
    )
    second = tracker.next_directive(
        "dsl-with-missing-fact-v2",
        coverage_errors,
        compact_plan=plan,
        task_spec=task_spec,
    )
    drop = tracker.next_directive(
        source,
        coverage_errors,
        compact_plan=plan,
        task_spec=task_spec,
    )

    assert first.repair_strategy == "coverage_restore"
    assert second.repair_strategy != "drop_optional_component"
    assert drop.repair_strategy == "drop_optional_component"
    assert drop.optional_drop is not None
    assert drop.optional_drop.component_id == "time"
    assert drop.optional_drop.fact_indexes == (1,)
    assert "Plan 事实缺失经过两次无损修复" in drop.instruction


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
