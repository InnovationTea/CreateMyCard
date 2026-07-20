from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class DesignPlanConstraintValidator:
    def __init__(self, plan: dict[str, Any]) -> None:
        self.plan = plan

    def validate(self, context, skill_dir: Path, reporter) -> None:
        from design_system import DesignSystem

        system = DesignSystem(skill_dir)
        issues = system.validate_catalog() + system.validate_plan(self.plan)
        for item in issues:
            reporter.add(
                item.severity,
                item.code,
                "semantic",
                "design-plan",
                actual=item.location,
                message=item.message,
            )
        if issues:
            return
        expected_dsl, expected_cardspec = system.assemble(self.plan)
        expected_messages = [json.loads(line) for line in expected_dsl.splitlines()]
        if context.dsl_messages != expected_messages:
            expected_ids = {
                item.get("id")
                for item in expected_messages[1]["updateComponents"]["components"]
                if isinstance(item, dict)
            }
            actual_ids = set(context.components_by_id)
            if expected_ids != actual_ids:
                reporter.add(
                    "error",
                    "DESIGN_PLAN_COMPONENT_SET_MISMATCH",
                    "semantic",
                    "genui",
                    actual=sorted(actual_ids),
                    expected=sorted(expected_ids),
                    message="DSL 组件集合与 Design Plan 确定性装配结果不一致。",
                )
            else:
                reporter.add(
                    "error",
                    "DESIGN_PLAN_DSL_MISMATCH",
                    "semantic",
                    "genui",
                    message="DSL 属性、层级、元素 token 或内容与 Design Plan 装配结果不一致。",
                )
        if context.cardspec != expected_cardspec:
            reporter.add(
                "error",
                "DESIGN_PLAN_CARDSPEC_MISMATCH",
                "semantic",
                "cardspec",
                actual=context.cardspec,
                expected=expected_cardspec,
                message="CardSpec 与 Design Plan 不一致。",
            )
