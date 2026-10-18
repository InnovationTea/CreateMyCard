from __future__ import annotations

from .base import BaseValidator, is_json_pointer, read_pointer, schema_path_exists


class CrossValidator(BaseValidator):
    """Cross-file consistency between DSL and CardSpec.

    Only responsibility left: check that ``CardSpec.dataBindings`` roots are
    initialised in the DSL DataModel and that the referenced data capability
    has an ``outputSchema``. Surface / root dimension checks used to live here
    but were removed: (1) DSL alone has no ``suggestSize`` signal so the size
    budget cannot be derived, (2) the "only root carries matchParent" rule is
    now enforced structurally by ``ProtocolValidator`` (createSurface) and
    ``ComponentValidator`` (root component) at the hard stage, independent of
    CardSpec.
    """

    stage = "semantic"
    name = "cross"

    def validate(self, context, rules, reporter) -> None:
        if not context.dsl_messages or not context.cardspec:
            return
        self._check_data_roots(context, rules, reporter)

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
