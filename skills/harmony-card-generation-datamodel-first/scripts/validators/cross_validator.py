from __future__ import annotations

from .base import BaseValidator, is_json_pointer, read_pointer, resolve_dimension, schema_path_exists


class CrossValidator(BaseValidator):
    stage = "semantic"
    name = "cross"

    def validate(self, context, rules, reporter) -> None:
        if not context.dsl_messages or not context.cardspec:
            return
        self._check_size(context, rules, reporter)
        self._check_data_roots(context, rules, reporter)

    def _check_size(self, context, rules, reporter) -> None:
        size = context.cardspec.get("suggestSize")
        if size not in rules.protocol.get("sizes", {}):
            return
        expected = rules.protocol["sizes"][size]
        create = context.create_surface
        width = resolve_dimension(create.get("width"), expected["width"])
        height = resolve_dimension(create.get("height"), expected["height"])
        if width != expected["width"] or height != expected["height"]:
            reporter.add(
                "error",
                "CROSS_SIZE_MISMATCH",
                "semantic",
                "genui",
                line=1,
                json_pointer="/createSurface",
                actual={"width": create.get("width"), "height": create.get("height")},
                expected={"width": expected["width"], "height": expected["height"], "outerFill": "matchParent"},
                message="DSL surface 尺寸必须与 CardSpec suggestSize 一致；外层可使用 matchParent，校验按基准尺寸解析。",
            )

    def _check_data_roots(self, context, rules, reporter) -> None:
        bindings = context.cardspec.get("dataBindings")
        if not isinstance(bindings, list):
            return
        for index, binding in enumerate(bindings):
            if not isinstance(binding, dict):
                continue
            target = binding.get("writeResultTo")
            capability = rules.capabilities.get(binding.get("capabilityId"))
            if not is_json_pointer(target) or capability is None:
                continue
            ok, _ = read_pointer(context.data_model, target)
            if not ok:
                reporter.add(
                    "warning",
                    "CROSS_DATA_PATH_UNCOVERED",
                    "semantic",
                    "cardspec",
                    json_pointer=f"/dataBindings/{index}/writeResultTo",
                    actual=target,
                    message="writeResultTo 对应根结构未在 updateDataModel.value 中初始化。",
                    fix_hint="在 updateDataModel.value 中初始化该 /data/... 根结构和 loading 态。",
                )
            if not schema_path_exists(capability.get("outputSchema", {}), "/"):
                reporter.add(
                    "warning",
                    "CROSS_DATA_PATH_UNCOVERED",
                    "semantic",
                    "cardspec",
                    json_pointer=f"/dataBindings/{index}/capabilityId",
                    actual=binding.get("capabilityId"),
                    message="capability 缺少 outputSchema，无法完整推导 UI 路径。",
                )
