from __future__ import annotations

from .base import BaseValidator, expression_like, is_empty_required_value, is_json_pointer


class ProtocolValidator(BaseValidator):
    stage = "hard"
    name = "protocol"

    def validate(self, context, rules, reporter) -> None:
        if not context.dsl_messages:
            return
        order = rules.protocol.get(
            "messageOrder", ["createSurface", "updateComponents", "updateDataModel"]
        )
        payload_ready = True
        for index, expected in enumerate(order):
            if index >= len(context.dsl_messages):
                continue
            message = context.dsl_messages[index]
            line = index + 1
            if message.get("version") != rules.protocol.get("version", "v0.9"):
                reporter.add(
                    "error",
                    "DSL_VERSION_INVALID",
                    "hard",
                    "genui",
                    line=line,
                    json_pointer="/version",
                    actual=message.get("version"),
                    expected=rules.protocol.get("version", "v0.9"),
                    message="genui 每行 version 必须固定。",
                    fix_hint='把 version 改为 "v0.9"。',
                )
            payload_keys = [key for key in message.keys() if key != "version"]
            if expected not in message or len(payload_keys) != 1:
                payload_ready = False
                reporter.add(
                    "error",
                    "DSL_MESSAGE_ORDER",
                    "hard",
                    "genui",
                    line=line,
                    actual=payload_keys,
                    expected=[expected],
                    message=f"genui 第 {line} 行必须只包含 {expected}。",
                    fix_hint=(
                        "按 createSurface -> updateComponents -> updateDataModel "
                        "的顺序输出三行 JSONL。"
                    ),
                )
            elif not isinstance(message.get(expected), dict):
                payload_ready = False
                reporter.add(
                    "error",
                    "DSL_REQUIRED_FIELD",
                    "hard",
                    "genui",
                    line=line,
                    json_pointer=f"/{expected}",
                    actual=message.get(expected),
                    message=f"{expected} 必须是非空 object。",
                    fix_hint=f"补齐 {expected} 对象及其必填字段。",
                )

        create = context.create_surface
        update = context.update_components
        data = context.update_data_model
        invalid_conditions = (
            not payload_ready,
            not isinstance(create, dict),
            not isinstance(update, dict),
            not isinstance(data, dict),
        )
        if any(invalid_conditions):
            return

        required_by_message = rules.protocol.get("messageRequiredFields", {})
        non_empty_by_message = rules.protocol.get("messageNonEmptyFields", {})
        for line, message_name, payload in (
            (1, "createSurface", create),
            (2, "updateComponents", update),
            (3, "updateDataModel", data),
        ):
            required = required_by_message.get(message_name, [])
            non_empty = set(non_empty_by_message.get(message_name, []))
            for field in required:
                if field not in payload or is_empty_required_value(
                    payload.get(field), empty_collections=field in non_empty
                ):
                    reporter.add(
                        "error",
                        "DSL_REQUIRED_FIELD",
                        "hard",
                        "genui",
                        line=line,
                        json_pointer=f"/{message_name}/{field}",
                        actual=payload.get(field) if field in payload else None,
                        message=f"{message_name}.{field} 是必填字段，且不能为空。",
                        fix_hint=f"补齐 {message_name}.{field}。",
                    )

        catalog_id = create.get("catalogId")
        if not is_empty_required_value(catalog_id) and catalog_id not in set(
            rules.protocol.get("catalogIds", [])
        ):
            reporter.add(
                "error",
                "DSL_CATALOG_ID_INVALID",
                "hard",
                "genui",
                line=1,
                json_pointer="/createSurface/catalogId",
                actual=catalog_id,
                expected=rules.protocol.get("catalogIds", []),
                message="createSurface.catalogId 不在允许列表中。",
                fix_hint="使用协议声明的 Form catalogId。",
            )

        surface_ids = [create.get("surfaceId"), update.get("surfaceId"), data.get("surfaceId")]
        if (
            all(not is_empty_required_value(surface_id) for surface_id in surface_ids)
            and len(set(surface_ids)) != 1
        ):
            reporter.add(
                "error",
                "DSL_SURFACE_ID_MISMATCH",
                "hard",
                "genui",
                actual=surface_ids,
                message="三行 JSONL 的 surfaceId 必须一致。",
                fix_hint=(
                    "把 createSurface、updateComponents、updateDataModel "
                    "的 surfaceId 改成同一个值。"
                ),
            )

        data_path = data.get("path")
        if not is_empty_required_value(data_path) and (
            expression_like(data_path) or not is_json_pointer(data_path)
        ):
            reporter.add(
                "error",
                "EXPR_FORBIDDEN_FIELD",
                "hard",
                "genui",
                line=3,
                json_pointer="/updateDataModel/path",
                actual=data_path,
                expected='"/"',
                message="updateDataModel.path 必须是结构 JSON Pointer，不能是表达式。",
                fix_hint='新卡片默认使用 "path": "/"。',
            )

        styles = create.get("styles")
        if isinstance(styles, dict):
            allowed = set(rules.style.get("createSurfaceAllowedStyles", []))
            extra = sorted(set(styles.keys()) - allowed)
            if extra:
                reporter.add(
                    "error",
                    "STYLE_BACKGROUND_WRONG_PLACE",
                    "hard",
                    "genui",
                    line=1,
                    json_pointer="/createSurface/styles",
                    actual=extra,
                    expected=sorted(allowed),
                    message="createSurface.styles 只允许外层形状/裁切字段。",
                    fix_hint=(
                        "把 backgroundColor、linearGradient、backgroundImage "
                        "等背景样式放到 root.styles。"
                    ),
                )

        # createSurface.width/height 是可选字段：不写才是标准写法，实际尺寸预算由
        # root.styles 承担。写了本身不会破坏渲染（只要值是 matchParent），但也没有
        # 意义，因此按 warning 提示删除；ComponentValidator 会对 root.styles.width/
        # height 是否为 matchParent 做 hard 校验。
        for field_name in ("width", "height"):
            if field_name not in create:
                continue
            reporter.add(
                "warning",
                "STYLE_SURFACE_DIMENSION_REDUNDANT",
                "hard",
                "genui",
                line=1,
                json_pointer=f"/createSurface/{field_name}",
                actual=create.get(field_name),
                message=f"createSurface.{field_name} 无需声明，实际尺寸预算由 root.styles 承担。",
                fix_hint=f"删除 createSurface.{field_name}。",
            )
