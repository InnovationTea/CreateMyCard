# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from __future__ import annotations

from .base import BaseValidator, expression_references
from .display_unit_rules import (
    collect_bound_display_unit_rules,
    matching_unit_literal_count,
    static_text_contains_rule,
    unit_rule_for_path,
)


class DisplayUnitValidator(BaseValidator):
    """校验带单位动态字段在 Text 中没有漏写或重复展示单位。"""

    stage = "semantic"
    name = "display_unit"

    def validate(self, context, rules, reporter) -> None:
        del rules
        unit_rules = collect_bound_display_unit_rules(
            context.cardspec,
            context.effective_data_capabilities,
        )
        if not unit_rules:
            return
        parents_by_child = self._parents_by_child(context.components)
        for component in context.components:
            if component.get("component") != "Text":
                continue
            component_id = component.get("id")
            content = component.get("content")
            if not isinstance(component_id, str) or not isinstance(content, str):
                continue
            matched_rules = [
                unit_rule_for_path(path, unit_rules)
                for path in expression_references(content)
            ]
            matched_rules = [rule for rule in matched_rules if rule is not None]
            if len(matched_rules) != 1:
                continue
            rule = matched_rules[0]
            inline_count = matching_unit_literal_count(content, rule)
            sibling_count = self._matching_sibling_count(
                component_id,
                rule,
                parents_by_child,
                context.components_by_id,
            )
            visible_unit_count = inline_count + sibling_count
            pointer = f"/updateComponents/componentsById/{component_id}/content"
            if rule.unit_included and visible_unit_count:
                reporter.add(
                    "error",
                    "DISPLAY_UNIT_DUPLICATED",
                    self.stage,
                    "genui",
                    line=2,
                    json_pointer=pointer,
                    actual=content,
                    expected={"unitIncluded": True, "displayUnits": list(rule.units)},
                    message="动态字段已自带展示单位，不得再次拼接或另行展示相同单位。",
                    fix_hint="删除表达式或相邻 Text 中重复追加的单位，仅保留字段自身内容。",
                )
            elif not rule.unit_included and visible_unit_count == 0:
                reporter.add(
                    "error",
                    "DISPLAY_UNIT_MISSING",
                    self.stage,
                    "genui",
                    line=2,
                    json_pointer=pointer,
                    actual=content,
                    expected={"unitIncluded": False, "displayUnits": list(rule.units)},
                    message="动态数值字段不包含展示单位，当前 Text 未展示其声明的单位。",
                    fix_hint=(
                        f"在数值表达式中追加单位“{rule.units[0]}”，或让紧邻数值后的"
                        f"静态 Text 包含该单位，且整组只展示一次。"
                    ),
                )
            elif not rule.unit_included and visible_unit_count > 1:
                reporter.add(
                    "error",
                    "DISPLAY_UNIT_DUPLICATED",
                    self.stage,
                    "genui",
                    line=2,
                    json_pointer=pointer,
                    actual=content,
                    expected={"unitIncluded": False, "displayUnits": list(rule.units)},
                    message="动态数值字段的展示单位被重复追加。",
                    fix_hint=f"只保留一个单位“{rule.units[0]}”。",
                )

    @staticmethod
    def _parents_by_child(components) -> dict[str, list[dict]]:
        result: dict[str, list[dict]] = {}
        for component in components:
            children = component.get("children")
            if not isinstance(children, list):
                continue
            for child_id in children:
                if isinstance(child_id, str):
                    result.setdefault(child_id, []).append(component)
        return result

    @staticmethod
    def _matching_sibling_count(
        component_id,
        rule,
        parents_by_child,
        components_by_id,
    ) -> int:
        sibling_ids: set[str] = set()
        for parent in parents_by_child.get(component_id, []):
            children = parent.get("children")
            if not isinstance(children, list):
                continue
            value_index = children.index(component_id)
            following_indexes = range(value_index + 1, len(children))
            for child_index in following_indexes:
                child_id = children[child_index]
                if not isinstance(child_id, str):
                    break
                sibling_content = components_by_id.get(child_id, {}).get("content")
                if expression_references(sibling_content):
                    break
                if not static_text_contains_rule(sibling_content, rule):
                    break
                sibling_ids.add(child_id)
        return len(sibling_ids)
