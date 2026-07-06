from __future__ import annotations

from .base import BaseValidator, expression_like, is_empty_required_value, is_json_pointer, pointer_overlaps


class CardSpecValidator(BaseValidator):
    stage = "hard"
    name = "cardspec"

    def validate(self, context, rules, reporter) -> None:
        if not context.cardspec:
            return
        cardspec = context.cardspec
        for field in ("title", "description", "suggestSize"):
            if field not in cardspec or is_empty_required_value(cardspec.get(field)):
                reporter.add(
                    "error",
                    "CARD_REQUIRED_FIELD",
                    "hard",
                    "cardspec",
                    json_pointer=f"/{field}",
                    actual=cardspec.get(field) if field in cardspec else None,
                    message=f"CardSpec.{field} 是必填字段，且不能为空。",
                    fix_hint=f"补齐 CardSpec.{field}。",
                )
        for field, limit in (("title", 8), ("description", 12)):
            value = cardspec.get(field)
            if is_empty_required_value(value):
                continue
            if not isinstance(value, str):
                reporter.add(
                    "error",
                    "CARD_STATIC_FIELD_INVALID",
                    "hard",
                    "cardspec",
                    json_pointer=f"/{field}",
                    actual=value,
                    message=f"CardSpec.{field} 必须是非空静态字符串。",
                )
                continue
            has_binding = expression_like(value) or value.startswith("/")
            if has_binding:
                reporter.add(
                    "error",
                    "CARD_STATIC_FIELD_INVALID",
                    "hard",
                    "cardspec",
                    json_pointer=f"/{field}",
                    actual=value,
                    message=f"CardSpec.{field} 不能写表达式、绑定或 DataModel 路径。",
                    fix_hint="改成用户可见的静态标题/概述。",
                )
            if not has_binding and len(value) > limit:
                reporter.add(
                    "warning",
                    "CARD_STATIC_FIELD_INVALID",
                    "hard",
                    "cardspec",
                    json_pointer=f"/{field}",
                    actual=value,
                    expected=f"不超过 {limit} 个字符",
                    message=f"CardSpec.{field} 建议更短。",
                    fix_hint="压缩成宿主展示用的短标题/短概述。",
                )

        suggest_size = cardspec.get("suggestSize")
        if not is_empty_required_value(suggest_size) and suggest_size not in ("2x2", "2x4"):
            reporter.add(
                "error",
                "CARD_SUGGEST_SIZE_INVALID",
                "hard",
                "cardspec",
                json_pointer="/suggestSize",
                actual=suggest_size,
                expected=["2x2", "2x4"],
                message='suggestSize 只能是 "2x2" 或 "2x4"。',
            )

        extra = sorted(set(cardspec.keys()) - {"title", "description", "suggestSize", "dataBindings"})
        if extra:
            reporter.add(
                "error",
                "CARD_REQUIRED_FIELD",
                "hard",
                "cardspec",
                actual=extra,
                expected=["title", "description", "suggestSize", "dataBindings"],
                message="CardSpec 包含协议外字段。",
                fix_hint="CardSpec 只描述宿主标题、概述、推荐尺寸和数据能力契约，不写 DSL 组件或点击行为。",
            )

        bindings = cardspec.get("dataBindings")
        if bindings is None:
            return
        if not isinstance(bindings, list) or not bindings:
            reporter.add(
                "error",
                "CARD_REQUIRED_FIELD",
                "hard",
                "cardspec",
                json_pointer="/dataBindings",
                actual=bindings,
                message="dataBindings 存在时必须是非空数组。",
            )
            return
        write_targets: list[str] = []
        for index, binding in enumerate(bindings):
            pointer = f"/dataBindings/{index}"
            if not isinstance(binding, dict):
                reporter.add("error", "CARD_REQUIRED_FIELD", "hard", "cardspec", json_pointer=pointer, actual=binding, message="dataBindings[] 必须是 object。")
                continue
            for field in ("capabilityId", "arguments", "writeResultTo"):
                empty_collections = False
                if field not in binding or is_empty_required_value(binding.get(field), empty_collections=empty_collections):
                    reporter.add(
                        "error",
                        "CARD_REQUIRED_FIELD",
                        "hard",
                        "cardspec",
                        json_pointer=f"{pointer}/{field}",
                        actual=binding.get(field) if field in binding else None,
                        message=f"dataBindings[].{field} 是必填字段，且不能为空。",
                        fix_hint=f"补齐 {pointer}/{field}。",
                    )
            target = binding.get("writeResultTo")
            if is_empty_required_value(target):
                continue
            if not is_json_pointer(target) or not str(target).startswith("/data/"):
                reporter.add(
                    "error",
                    "CARD_WRITE_RESULT_PATH_INVALID",
                    "hard",
                    "cardspec",
                    json_pointer=f"{pointer}/writeResultTo",
                    actual=target,
                    expected="/data/...",
                    message="writeResultTo 必须是 /data/... JSON Pointer。",
                )
            else:
                if any(pointer_overlaps(target, existing) for existing in write_targets):
                    reporter.add(
                        "error",
                        "CARD_WRITE_RESULT_PATH_OVERLAP",
                        "hard",
                        "cardspec",
                        json_pointer=f"{pointer}/writeResultTo",
                        actual=target,
                        message="多个 writeResultTo 不得相同、互为父子或互相覆盖。",
                    )
                write_targets.append(target)
