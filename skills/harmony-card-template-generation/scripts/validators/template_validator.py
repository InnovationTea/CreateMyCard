from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ALLOWED_COMPONENTS = {
    "Text",
    "Image",
    "Divider",
    "Progress",
    "Button",
    "Checkbox",
    "Row",
    "Column",
    "List",
    "Stack",
}


class TemplateConstraintValidator:
    def __init__(self, template_id: str) -> None:
        self.template_id = template_id

    def validate(self, context, skill_dir: Path, reporter) -> None:
        template_dir = skill_dir / "assets" / "templates" / self.template_id
        manifest_path = template_dir / "manifest.json"
        skeleton_path = template_dir / "template.genui.jsonl"
        manifest = self._read_json(manifest_path, reporter)
        if not manifest:
            return

        if manifest.get("id") != self.template_id:
            reporter.add(
                "error",
                "TEMPLATE_ID_MISMATCH",
                "semantic",
                "manifest",
                actual=manifest.get("id"),
                expected=self.template_id,
                message="模板目录名、manifest.id 与 --template-id 必须一致。",
            )

        expected_size = manifest.get("size")
        if context.cardspec and context.cardspec.get("suggestSize") != expected_size:
            reporter.add(
                "error",
                "TEMPLATE_SIZE_MISMATCH",
                "semantic",
                "cardspec",
                json_pointer="/suggestSize",
                actual=context.cardspec.get("suggestSize"),
                expected=expected_size,
                message="CardSpec 尺寸与所选模板不一致。",
            )

        skeleton_ids = self._skeleton_component_ids(skeleton_path, reporter)
        current_ids = set(context.components_by_id)
        extra_ids = sorted(current_ids - skeleton_ids)
        if extra_ids:
            reporter.add(
                "error",
                "TEMPLATE_COMPONENT_ID_ADDED",
                "semantic",
                "genui",
                actual=extra_ids,
                expected=sorted(skeleton_ids),
                message="生成结果新增了模板骨架之外的组件 ID。",
                fix_hint="只在现有 region 内使用 manifest 声明的组件变体，并复用模板 ID。",
            )

        regions = manifest.get("layout", {}).get("regions", [])
        variants = manifest.get("componentVariants", {})
        region_ids = {
            item.get("id")
            for item in regions
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        for region in regions if isinstance(regions, list) else []:
            if not isinstance(region, dict):
                continue
            region_id = region.get("id")
            if not isinstance(region_id, str):
                continue
            component = context.components_by_id.get(region_id)
            if component is None:
                if region.get("required"):
                    reporter.add(
                        "error",
                        "TEMPLATE_REQUIRED_REGION_MISSING",
                        "semantic",
                        "genui",
                        actual=region_id,
                        message="必选模板 region 被删除。",
                    )
                continue

            allowed_roots = {
                item.get("rootComponent")
                for item in variants.get(region_id, [])
                if isinstance(item, dict)
            }
            if component.get("component") not in allowed_roots:
                reporter.add(
                    "error",
                    "TEMPLATE_REGION_COMPONENT_INVALID",
                    "semantic",
                    "genui",
                    json_pointer=f"/updateComponents/componentsById/{region_id}/component",
                    actual=component.get("component"),
                    expected=sorted(value for value in allowed_roots if isinstance(value, str)),
                    message="region 根组件不属于 manifest 声明的变体。",
                )

            region_component_ids = self._region_component_ids(
                region_id,
                context.components_by_id,
                region_ids,
            )
            region_component_types = {
                context.components_by_id[component_id].get("component")
                for component_id in region_component_ids
            }
            matching_variants = [
                item
                for item in variants.get(region_id, [])
                if isinstance(item, dict)
                and item.get("rootComponent") == component.get("component")
                and region_component_types.issubset(set(item.get("allowedComponents", [])))
            ]
            if not matching_variants:
                reporter.add(
                    "error",
                    "TEMPLATE_REGION_VARIANT_INVALID",
                    "semantic",
                    "genui",
                    actual=sorted(value for value in region_component_types if isinstance(value, str)),
                    message="region 组件树不匹配任何 manifest 组件变体。",
                )

            children = self._child_ids(component)
            max_children = region.get("maxChildren")
            if isinstance(max_children, int) and len(children) > max_children:
                reporter.add(
                    "error",
                    "TEMPLATE_REGION_CHILD_LIMIT_EXCEEDED",
                    "semantic",
                    "genui",
                    actual=len(children),
                    expected=max_children,
                    message="region 子项数量超过 manifest 上限。",
                )

            styles = component.get("styles") if isinstance(component.get("styles"), dict) else {}
            for dimension in ("width", "height"):
                expected = region.get(dimension)
                actual = styles.get(dimension)
                if isinstance(expected, (int, float)) and actual != expected:
                    reporter.add(
                        "error",
                        "TEMPLATE_REGION_SIZE_CHANGED",
                        "semantic",
                        "genui",
                        json_pointer=f"/updateComponents/componentsById/{region_id}/styles/{dimension}",
                        actual=actual,
                        expected=expected,
                        message="region 固定尺寸被修改或缺失。",
                    )

            allowed = set(region.get("allowedComponents", []))
            if not allowed.issubset(ALLOWED_COMPONENTS):
                reporter.add(
                    "error",
                    "TEMPLATE_COMPONENT_ALLOWLIST_INVALID",
                    "semantic",
                    "manifest",
                    actual=sorted(allowed - ALLOWED_COMPONENTS),
                    message="manifest 声明了 Form 子集外组件。",
                )

        slots = manifest.get("slots", {})
        if isinstance(slots, dict):
            for name, slot in slots.items():
                if not isinstance(slot, dict):
                    continue
                component_id = slot.get("component")
                if slot.get("required") and isinstance(component_id, str) and component_id not in current_ids:
                    reporter.add(
                        "error",
                        "TEMPLATE_REQUIRED_SLOT_MISSING",
                        "semantic",
                        "genui",
                        actual={"slot": name, "component": component_id},
                        message="必选模板槽位对应组件被删除。",
                    )
                region_id = slot.get("region")
                if isinstance(component_id, str) and component_id in current_ids and isinstance(region_id, str):
                    in_region = self._region_component_ids(
                        region_id,
                        context.components_by_id,
                        region_ids,
                    )
                    if component_id not in in_region:
                        reporter.add(
                            "error",
                            "TEMPLATE_SLOT_COMPONENT_OUTSIDE_REGION",
                            "semantic",
                            "genui",
                            actual={"slot": name, "component": component_id, "region": region_id},
                            message="槽位组件不在 manifest 指定 region 内。",
                        )

                path = slot.get("path")
                value, found = self._json_pointer_value(context.data_model, path)
                if slot.get("required") and not found:
                    reporter.add(
                        "error",
                        "TEMPLATE_REQUIRED_SLOT_DATA_MISSING",
                        "semantic",
                        "genui",
                        actual={"slot": name, "path": path},
                        message="必选槽位在初始 DataModel 中没有对应路径。",
                    )
                limit = slot.get("maxCharsCn") or slot.get("maxChars")
                if found and isinstance(value, str) and isinstance(limit, int) and len(value) > limit:
                    reporter.add(
                        "error",
                        "TEMPLATE_SLOT_TEXT_OVERFLOW",
                        "semantic",
                        "genui",
                        actual={"slot": name, "length": len(value), "value": value},
                        expected=limit,
                        message="槽位文本超过 manifest 字符预算。",
                    )

        bindings = context.cardspec.get("dataBindings", []) if context.cardspec else []
        binding_count = len(bindings) if isinstance(bindings, list) else 0
        limit = 1 if expected_size == "2x2" else 2
        if binding_count > limit:
            reporter.add(
                "error",
                "TEMPLATE_CAPABILITY_LIMIT_EXCEEDED",
                "semantic",
                "cardspec",
                json_pointer="/dataBindings",
                actual=binding_count,
                expected=limit,
                message="数据能力数量超过模板尺寸上限。",
            )

    def _read_json(self, path: Path, reporter) -> dict[str, Any]:
        if not path.exists():
            reporter.add(
                "error",
                "TEMPLATE_MANIFEST_MISSING",
                "hard",
                "manifest",
                actual=str(path),
                message="找不到所选模板 manifest。",
            )
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            reporter.add(
                "error",
                "TEMPLATE_MANIFEST_INVALID",
                "hard",
                "manifest",
                actual=str(exc),
                message="模板 manifest 不是合法 JSON。",
            )
            return {}
        return value if isinstance(value, dict) else {}

    def _skeleton_component_ids(self, path: Path, reporter) -> set[str]:
        if not path.exists():
            reporter.add(
                "error",
                "TEMPLATE_SKELETON_MISSING",
                "hard",
                "manifest",
                actual=str(path),
                message="找不到所选模板 genui 骨架。",
            )
            return set()
        try:
            lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            message = json.loads(lines[1])
            components = message["updateComponents"]["components"]
        except (OSError, IndexError, KeyError, TypeError, json.JSONDecodeError) as exc:
            reporter.add(
                "error",
                "TEMPLATE_SKELETON_INVALID",
                "hard",
                "manifest",
                actual=str(exc),
                message="模板 genui 骨架无法解析组件列表。",
            )
            return set()
        return {
            item["id"]
            for item in components
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }

    @staticmethod
    def _child_ids(component: dict[str, Any]) -> list[str]:
        children = component.get("children", [])
        if not isinstance(children, list):
            return []
        return [child for child in children if isinstance(child, str)]

    def _region_component_ids(
        self,
        region_id: str,
        components: dict[str, dict[str, Any]],
        region_ids: set[str],
    ) -> set[str]:
        result: set[str] = set()
        pending = [region_id]
        while pending:
            current = pending.pop()
            if current in result or current not in components:
                continue
            result.add(current)
            for child in self._child_ids(components[current]):
                if child not in region_ids or child == region_id:
                    pending.append(child)
        return result

    @staticmethod
    def _json_pointer_value(value: Any, pointer: Any) -> tuple[Any, bool]:
        if not isinstance(pointer, str) or not pointer.startswith("/"):
            return None, False
        current = value
        for raw_part in pointer.split("/")[1:]:
            part = raw_part.replace("~1", "/").replace("~0", "~")
            if isinstance(current, dict) and part in current:
                current = current[part]
            elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
                current = current[int(part)]
            else:
                return None, False
        return current, True
