from __future__ import annotations

import json
from typing import Any

from .base import (
    BaseValidator,
    expression_references,
    is_json_pointer,
    is_wrapped_expression,
    static_expression_value,
)


class EffectiveCapabilityValidator(BaseValidator):
    stage = "semantic"
    name = "effective-capability"

    def validate(self, context, rules, reporter) -> None:
        if not getattr(context, "use_effective_capabilities", False):
            return
        self._check_data_capabilities(context, reporter)
        self._check_event_capabilities(context, reporter)
        self._check_asset_capabilities(context, reporter)

    def _check_data_capabilities(self, context, reporter) -> None:
        effective_data = context.effective_capabilities.get("data", [])
        effective_ids = self._effective_ids(effective_data)
        allowed_roots: list[str] = self._effective_data_roots(effective_data)
        bindings = context.cardspec.get("dataBindings")
        if isinstance(bindings, list):
            for index, binding in enumerate(bindings):
                if not isinstance(binding, dict):
                    continue
                capability_id = binding.get("capabilityId")
                root = binding.get("writeResultTo")
                if capability_id not in effective_ids:
                    reporter.add(
                        "error",
                        "EFFECTIVE_DATA_CAPABILITY_NOT_ALLOWED",
                        "semantic",
                        "cardspec",
                        json_pointer=f"/dataBindings/{index}/capabilityId",
                        actual=capability_id,
                        expected=sorted(effective_ids),
                        message=(
                            "CardSpec.dataBindings uses a data capability that is not "
                            "in effectiveCapabilities.data."
                        ),
                        fix_hint=(
                            "Remove this data binding or include it in the filtered "
                            "effective data capabilities."
                        ),
                    )
                    continue
                if is_json_pointer(root):
                    allowed_roots.append(str(root))

        if not context.cardspec_text.strip() and not allowed_roots:
            return

        for pointer, location in self._data_references(context):
            if not pointer.startswith("/data/") and pointer != "/data":
                continue
            if any(self._path_under_root(pointer, root) for root in allowed_roots):
                continue
            reporter.add(
                "error",
                "EFFECTIVE_DATA_PATH_NOT_ALLOWED",
                "semantic",
                "genui",
                line=2,
                json_pointer=location,
                actual=pointer,
                expected=allowed_roots,
                message=(
                    "DSL references a DataModel path that is not backed by an "
                    "effective data capability."
                ),
                fix_hint=(
                    "Bind the DSL to a writeResultTo path from effective CardSpec.dataBindings."
                ),
            )

    def _effective_data_roots(self, items: list[Any]) -> list[str]:
        result: list[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            root = item.get("writeResultTo") or item.get("defaultWriteResultTo")
            if is_json_pointer(root):
                result.append(str(root))
        return result

    def _path_under_root(self, pointer: str, root: str) -> bool:
        root = root.rstrip("/")
        return pointer == root or pointer.startswith(root + "/")

    def _data_references(self, context) -> list[tuple[str, str]]:
        references: list[tuple[str, str]] = []
        for file_kind, pointer, value, _component_id in context.expression_locations:
            if file_kind != "genui" or not isinstance(value, str):
                continue
            for ref in expression_references(value):
                if ref.startswith("/"):
                    references.append((ref, pointer))
        for component in context.components:
            component_id = component.get("id", "<unknown>")
            children = component.get("children")
            if isinstance(children, dict):
                path = children.get("path")
                if isinstance(path, str) and path.startswith("/"):
                    references.append(
                        (
                            path,
                            f"/updateComponents/componentsById/{component_id}/children/path",
                        )
                    )
        return references

    def _check_event_capabilities(self, context, reporter) -> None:
        allowed_actions = self._event_actions(context.effective_capabilities.get("event", []))
        for component in context.components:
            component_id = component.get("id", "<unknown>")
            handlers = component.get("onClick")
            if handlers is None:
                continue
            if not isinstance(handlers, list):
                continue
            for index, handler in enumerate(handlers):
                if not isinstance(handler, dict):
                    continue
                call = handler.get("call")
                args = handler.get("args", {})
                if self._event_allowed(call, args, allowed_actions):
                    continue
                reporter.add(
                    "error",
                    "EFFECTIVE_EVENT_NOT_ALLOWED",
                    "semantic",
                    "genui",
                    line=2,
                    json_pointer=f"/updateComponents/componentsById/{component_id}/onClick/{index}",
                    actual={"call": call, "args": args},
                    expected=allowed_actions,
                    message=(
                        "DSL onClick uses an event action that is not in "
                        "effectiveCapabilities.event."
                    ),
                    fix_hint="Use only event actions that passed cloud-new capability filtering.",
                )

    def _check_asset_capabilities(self, context, reporter) -> None:
        if context.unresolved_effective_asset_ids:
            reporter.add(
                "warning",
                "EFFECTIVE_ASSET_SOURCE_UNRESOLVED",
                "semantic",
                "artifact",
                actual=sorted(context.unresolved_effective_asset_ids),
                message="Some effective asset ids cannot be resolved to resource paths.",
                fix_hint=(
                    "Pass capabilities_dir or include asset src in "
                    "effectiveCapabilities.asset/taskSpec.assetCandidates."
                ),
            )

        for path, location in self._asset_references(context, reporter):
            if path not in context.effective_asset_sources:
                reporter.add(
                    "error",
                    "EFFECTIVE_ASSET_NOT_ALLOWED",
                    "semantic",
                    "genui",
                    line=2,
                    json_pointer=location,
                    actual=path,
                    expected=sorted(context.effective_asset_sources),
                    message=(
                        "DSL references an asset path that is not in effective asset capabilities."
                    ),
                    fix_hint="Use a src from the filtered effective asset capabilities.",
                )

    def _asset_references(self, context, reporter) -> list[tuple[str, str]]:
        references: list[tuple[str, str]] = []
        for component in context.components:
            component_id = component.get("id", "<unknown>")
            if component.get("component") == "Image":
                self._append_asset_reference(
                    component.get("src"),
                    f"/updateComponents/componentsById/{component_id}/src",
                    context,
                    reporter,
                    references,
                )
            styles = component.get("styles", {})
            if isinstance(styles, dict) and "backgroundImage" in styles:
                self._append_asset_reference(
                    styles.get("backgroundImage"),
                    f"/updateComponents/componentsById/{component_id}/styles/backgroundImage",
                    context,
                    reporter,
                    references,
                )
        return references

    def _append_asset_reference(
        self,
        value: Any,
        pointer: str,
        context,
        reporter,
        references: list[tuple[str, str]],
    ) -> None:
        if not isinstance(value, str) or not value:
            return
        if is_wrapped_expression(value):
            resolved = static_expression_value(value, context.data_model)
            if isinstance(resolved, str):
                references.append((resolved, pointer))
            else:
                reporter.add(
                    "warning",
                    "EFFECTIVE_ASSET_DYNAMIC_PATH",
                    "semantic",
                    "genui",
                    line=2,
                    json_pointer=pointer,
                    actual=value,
                    message=(
                        "Dynamic asset expression cannot be resolved statically "
                        "against effective asset capabilities."
                    ),
                    fix_hint=(
                        "Initialize the asset path in updateDataModel.value or use "
                        "a static effective asset src."
                    ),
                )
            return
        references.append((value, pointer))

    def _effective_ids(self, items: list[Any]) -> set[str]:
        result: set[str] = set()
        for item in items:
            if isinstance(item, str):
                result.add(item)
            elif isinstance(item, dict):
                value = item.get("id") or item.get("capabilityId")
                if isinstance(value, str):
                    result.add(value)
        return result

    def _event_actions(self, items: list[Any]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            call = item.get("call")
            if not isinstance(call, str):
                continue
            args = item.get("args", {})
            if not isinstance(args, dict):
                args = {}
            result.append({"call": call, "args": args})
        return result

    def _event_allowed(
        self,
        call: Any,
        args: Any,
        allowed_actions: list[dict[str, Any]],
    ) -> bool:
        if not isinstance(call, str):
            return False
        if not isinstance(args, dict):
            args = {}
        expected = self._stable_json({"call": call, "args": args})
        return any(self._stable_json(item) == expected for item in allowed_actions)

    def _stable_json(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
