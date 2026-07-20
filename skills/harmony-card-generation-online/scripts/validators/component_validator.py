from __future__ import annotations

from .base import BaseValidator, expression_like, is_empty_required_value, is_json_pointer


class ComponentValidator(BaseValidator):
    stage = "hard"
    name = "component"

    def validate(self, context, rules, reporter) -> None:
        if not context.update_components:
            return
        components_value = context.update_components.get("components")
        if not isinstance(components_value, list):
            reporter.add(
                "error",
                "DSL_COMPONENT_REQUIRED_FIELD",
                "hard",
                "genui",
                line=2,
                json_pointer="/updateComponents/components",
                actual=components_value,
                message="updateComponents.components 必须是数组。",
            )
            return
        if context.duplicate_component_ids:
            reporter.add(
                "error",
                "DSL_COMPONENT_ID_DUPLICATED",
                "hard",
                "genui",
                line=2,
                actual=sorted(context.duplicate_component_ids),
                message="components[].id 必须唯一。",
            )
        if isinstance(context.root_id, str) and context.root_id and context.root_id not in context.components_by_id:
            reporter.add(
                "error",
                "DSL_ROOT_NOT_FOUND",
                "hard",
                "genui",
                line=2,
                json_pointer="/updateComponents/root",
                actual=context.root_id,
                message="updateComponents.root 必须引用 components 中存在的 id。",
            )

        common_top = set(rules.protocol.get("commonTopLevelFields", []))
        common_required = rules.protocol.get("componentCommonRequiredFields", ["id", "component"])
        top_fields = rules.protocol.get("componentTopLevelFields", {})
        required_fields = rules.protocol.get("componentRequiredFields", {})
        non_empty_required = set(rules.protocol.get("componentNonEmptyRequiredFields", []))
        forbidden_global = set(rules.protocol.get("forbiddenComponentFields", {}).get("*", []))
        forbidden_by_component = rules.protocol.get("forbiddenComponentFields", {})
        template_components = set(rules.protocol.get("templateComponents", []))
        template_children_rules = rules.protocol.get("templateChildren", {})
        allowed_template_keys = set(template_children_rules.get(
            "allowedKeys", ["componentId", "path", "itemVar", "indexVar"]
        ))
        required_template_keys = set(template_children_rules.get(
            "requiredKeys", ["componentId", "path"]
        ))
        event_handler_forbidden = set(rules.protocol.get(
            "eventHandlerForbiddenFields", ["condition", "as"]
        ))

        for index, component in enumerate(context.components):
            pointer = f"/updateComponents/components/{index}"
            component_id = component.get("id")
            component_type = component.get("component")
            missing_common = False
            for field in common_required:
                if field not in component or is_empty_required_value(
                    component.get(field),
                    empty_strings=field in non_empty_required,
                    empty_collections=field in non_empty_required,
                ):
                    missing_common = True
                    reporter.add(
                        "error",
                        "DSL_COMPONENT_REQUIRED_FIELD",
                        "hard",
                        "genui",
                        line=2,
                        json_pointer=f"{pointer}/{field}",
                        actual=component.get(field) if field in component else None,
                        message=f"组件缺少必填顶层字段 {field}，或该字段为空。",
                        fix_hint=f"补齐 components[{index}].{field}。",
                    )
            if missing_common:
                continue
            if component_type not in rules.allowed_components:
                reporter.add(
                    "error",
                    "DSL_COMPONENT_UNKNOWN",
                    "hard",
                    "genui",
                    line=2,
                    json_pointer=f"{pointer}/component",
                    actual=component_type,
                    expected=sorted(rules.allowed_components),
                    message="组件类型不在 Form 允许组件列表中。",
                )
                continue
            allowed = common_top | set(top_fields.get(component_type, []))
            extra = sorted(set(component.keys()) - allowed)
            if extra:
                reporter.add(
                    "error",
                    "DSL_FIELD_FORBIDDEN",
                    "hard",
                    "genui",
                    line=2,
                    json_pointer=pointer,
                    actual=extra,
                    expected=sorted(allowed),
                    message=f"{component_type} 包含协议外顶层字段。",
                    fix_hint="按 component-catalog.md 把视觉字段放入 styles，删除协议外字段。",
                )
            forbidden = sorted((forbidden_global | set(forbidden_by_component.get(component_type, []))) & set(component.keys()))
            if forbidden:
                reporter.add("error", "DSL_FIELD_FORBIDDEN", "hard", "genui", line=2, json_pointer=pointer, actual=forbidden, message="组件包含禁用字段。")
            handlers = component.get("onClick")
            if isinstance(handlers, list):
                if len(handlers) > 1:
                    reporter.add(
                        "error",
                        "EVENT_ARGUMENT_INVALID",
                        "hard",
                        "genui",
                        line=2,
                        json_pointer=f"{pointer}/onClick",
                        actual=len(handlers),
                        expected=1,
                        message="Form 协议每个事件仅支持 1 个 EventHandler。",
                    )
                for handler_index, handler in enumerate(handlers):
                    if isinstance(handler, dict):
                        forbidden_handler = sorted(set(handler.keys()) & event_handler_forbidden)
                        if forbidden_handler:
                            reporter.add(
                                "error",
                                "DSL_FIELD_FORBIDDEN",
                                "hard",
                                "genui",
                                line=2,
                                json_pointer=f"{pointer}/onClick/{handler_index}",
                                actual=forbidden_handler,
                                message="Form EventHandler 不支持 condition/as。",
                            )
            for field in required_fields.get(component_type, []):
                if field not in component or is_empty_required_value(
                    component.get(field),
                    empty_strings=field in non_empty_required,
                    empty_collections=field in non_empty_required,
                ):
                    reporter.add(
                        "error",
                        "DSL_COMPONENT_REQUIRED_FIELD",
                        "hard",
                        "genui",
                        line=2,
                        json_pointer=f"{pointer}/{field}",
                        actual=component.get(field) if field in component else None,
                        message=f"{component_type} 缺少必填顶层字段 {field}，或该字段为空。",
                        fix_hint=f"补齐 {component_type}.{field}。",
                    )

            styles = component.get("styles")
            if styles is not None and not isinstance(styles, dict):
                reporter.add("error", "DSL_COMPONENT_REQUIRED_FIELD", "hard", "genui", line=2, json_pointer=f"{pointer}/styles", actual=styles, message="styles 必须是 object。")

            # root 组件是唯一卡片 shell：宽高必须写 "matchParent"，实际预算由内部组件承担。
            # 其它组件继续按数值 / 可静态推导的约束保持数值宽高。
            if isinstance(styles, dict) and component_id is not None and component_id == context.root_id:
                for style_field in ("width", "height"):
                    if style_field not in styles:
                        continue
                    raw = styles.get(style_field)
                    if isinstance(raw, str) and raw.strip() == "matchParent":
                        continue
                    reporter.add(
                        "error",
                        "STYLE_ROOT_DIMENSION_INVALID",
                        "hard",
                        "genui",
                        line=2,
                        json_pointer=f"{pointer}/styles/{style_field}",
                        actual=raw,
                        expected="matchParent",
                        message="root 组件的 styles.width/height 必须写 \"matchParent\"，实际尺寸预算由内部组件数值承担。",
                        fix_hint=f'把 root.styles.{style_field} 设为 "matchParent"，删除具体数值。',
                    )

            children = component.get("children")
            if children is not None:
                if isinstance(children, list):
                    for child_index, child in enumerate(children):
                        if not isinstance(child, str):
                            reporter.add("error", "DSL_TEMPLATE_CHILDREN_INVALID", "hard", "genui", line=2, json_pointer=f"{pointer}/children/{child_index}", actual=child, message="普通 children 只能包含组件 id 字符串。")
                        elif child not in context.components_by_id:
                            reporter.add("error", "DSL_CHILD_REF_NOT_FOUND", "hard", "genui", line=2, json_pointer=f"{pointer}/children/{child_index}", actual=child, message="children 引用了不存在的组件 id。", fix_hint="新增该 id 的组件，或删除/改正 children 引用。")
                elif isinstance(children, dict):
                    if component_type not in template_components:
                        reporter.add("error", "DSL_TEMPLATE_CHILDREN_INVALID", "hard", "genui", line=2, json_pointer=f"{pointer}/children", message=f"{component_type}.children 不支持模板循环对象。")
                    if not required_template_keys <= set(children.keys()) or set(children.keys()) - allowed_template_keys:
                        reporter.add("error", "DSL_TEMPLATE_CHILDREN_INVALID", "hard", "genui", line=2, json_pointer=f"{pointer}/children", actual=children, expected={"componentId": "...", "path": "/items", "itemVar": "item", "indexVar": "index"}, message="模板 children 必须包含 componentId/path，可选 itemVar/indexVar。")
                    child_id = children.get("componentId")
                    child_path = children.get("path")
                    if child_id not in context.components_by_id:
                        reporter.add("error", "DSL_CHILD_REF_NOT_FOUND", "hard", "genui", line=2, json_pointer=f"{pointer}/children/componentId", actual=child_id, message="模板 componentId 引用了不存在的组件 id。")
                    if expression_like(child_path) or not is_json_pointer(child_path):
                        reporter.add("error", "EXPR_FORBIDDEN_FIELD", "hard", "genui", line=2, json_pointer=f"{pointer}/children/path", actual=child_path, message="模板 children.path 必须是结构 JSON Pointer，不能是表达式。")
                    for var_field in ("itemVar", "indexVar"):
                        var_name = children.get(var_field)
                        if var_name is not None and (not isinstance(var_name, str) or not var_name or var_name.startswith("$")):
                            reporter.add("error", "DSL_TEMPLATE_CHILDREN_INVALID", "hard", "genui", line=2, json_pointer=f"{pointer}/children/{var_field}", actual=var_name, message=f"{var_field} 必须是不带 $ 前缀的非空变量名。")
                else:
                    reporter.add("error", "DSL_TEMPLATE_CHILDREN_INVALID", "hard", "genui", line=2, json_pointer=f"{pointer}/children", actual=children, message="children 必须是组件 id 数组或模板循环对象。")
