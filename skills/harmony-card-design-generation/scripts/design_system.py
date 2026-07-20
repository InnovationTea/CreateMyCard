from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover - optional in bundled runtimes
    Draft202012Validator = None


CATALOG_ID = "ohos.a2ui.extended.catalog.form"
STYLE_PROFILES = {"neutral-light", "dark-focus", "ambient-scene", "media-surface"}
ALLOWED_CONTAINER_COMPONENTS = {"Row", "Column", "Stack"}
ALLOWED_ELEMENT_COMPONENTS = {"Text", "Image", "Progress", "Button", "Divider"}
ALLOWED_FONT_SIZES = {10, 12, 14, 16, 18, 20, 32, 40}


@dataclass(frozen=True)
class DesignIssue:
    severity: str
    code: str
    location: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "code": self.code,
            "location": self.location,
            "message": self.message,
        }


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


class DesignSystem:
    def __init__(self, skill_dir: Path) -> None:
        self.skill_dir = skill_dir
        self.templates_dir = skill_dir / "assets" / "templates"
        self.index = read_json(self.templates_dir / "index.json")
        catalogs = self.index.get("catalogs", {})
        self.layouts_catalog = read_json(self.templates_dir / catalogs["layouts"])
        self.modules_catalog = read_json(self.templates_dir / catalogs["modules"])
        self.elements_catalog = read_json(self.templates_dir / catalogs["elements"])
        self.cardspec_base = read_json(self.templates_dir / catalogs["cardSpecBase"])
        self.layouts = self._by_id(self.layouts_catalog.get("layouts", []))
        self.modules = self._by_id(self.modules_catalog.get("modules", []))
        self.elements = self._by_id(self.elements_catalog.get("elements", []))
        self.styles = self.index.get("styleProfiles", {})
        self.limits = self.index.get("limits", {})
        asset_doc = skill_dir / "references" / "design" / "asset-library.md"
        asset_text = asset_doc.read_text(encoding="utf-8") if asset_doc.exists() else ""
        self.asset_allowlist = set(re.findall(r"`(resources/base/media/[^`]+)`", asset_text))

    @staticmethod
    def _by_id(items: Any) -> dict[str, dict[str, Any]]:
        if not isinstance(items, list):
            return {}
        return {
            item["id"]: item
            for item in items
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }

    def validate_catalog(self) -> list[DesignIssue]:
        issues: list[DesignIssue] = []
        if self.index.get("schemaVersion") != "design-system-v1":
            issues.append(self._issue("DESIGN_SYSTEM_VERSION_INVALID", "index/schemaVersion", "设计系统版本必须是 design-system-v1。"))
        if self.index.get("catalogId") != CATALOG_ID:
            issues.append(self._issue("DESIGN_SYSTEM_CATALOG_INVALID", "index/catalogId", f"catalogId 必须是 {CATALOG_ID}。"))
        if set(self.styles) != STYLE_PROFILES:
            issues.append(self._issue("DESIGN_SYSTEM_STYLE_SET_INVALID", "index/styleProfiles", "必须完整声明四套受控风格。"))
        issues.extend(self._validate_schemas())
        issues.extend(self._validate_layouts())
        issues.extend(self._validate_elements())
        issues.extend(self._validate_modules())
        issues.extend(self._validate_compatibility())
        return issues

    def validate_plan(self, plan: dict[str, Any]) -> list[DesignIssue]:
        issues = self._validate_plan_shape(plan)
        issues.extend(self._validate_value_against_schema(plan, "designPlan", "plan"))
        feature = plan.get("featureProfile") if isinstance(plan.get("featureProfile"), dict) else {}
        issues.extend(self._validate_value_against_schema(feature, "featureProfile", "plan/featureProfile"))
        if issues:
            return issues

        layout_id = plan.get("layoutId")
        layout = self.layouts.get(layout_id)
        if layout is None:
            return [self._issue("DESIGN_PLAN_LAYOUT_UNKNOWN", "plan/layoutId", f"未声明布局 {layout_id}。")]
        size = feature.get("size")
        if size not in self.limits:
            return [self._issue("DESIGN_PLAN_SIZE_INVALID", "plan/featureProfile/size", "尺寸只能是 2x2 或 2x4。")]
        if layout.get("size") != size or plan.get("cardSpec", {}).get("suggestSize") != size:
            issues.append(self._issue("DESIGN_PLAN_SIZE_MISMATCH", "plan", "Feature Profile、布局和 CardSpec 尺寸必须一致。"))
        if plan.get("styleProfile") not in self.styles:
            issues.append(self._issue("DESIGN_PLAN_STYLE_UNKNOWN", "plan/styleProfile", "风格档案未在设计系统中声明。"))
        if feature.get("styleIntent") != plan.get("styleProfile"):
            issues.append(self._issue("DESIGN_PLAN_STYLE_MISMATCH", "plan/styleProfile", "Feature Profile 风格意图必须与 Design Plan 风格一致。"))

        feature_items = {
            item.get("id"): item
            for item in feature.get("contentItems", [])
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        mapped_features: dict[str, int] = {}
        region_plans = plan.get("regions", [])
        regions_by_id = {
            region.get("regionId"): region
            for region in region_plans
            if isinstance(region, dict) and isinstance(region.get("regionId"), str)
        }
        if len(regions_by_id) != len(region_plans):
            issues.append(self._issue("DESIGN_PLAN_REGION_DUPLICATE", "plan/regions", "regionId 必须唯一。"))
        layout_regions = {item["id"]: item for item in layout.get("regions", [])}
        extra_regions = sorted(set(regions_by_id) - set(layout_regions))
        if extra_regions:
            issues.append(self._issue("DESIGN_PLAN_REGION_UNKNOWN", "plan/regions", f"布局中不存在 region：{extra_regions}。"))
        for region_id, region in layout_regions.items():
            if region.get("required") and region_id not in regions_by_id:
                issues.append(self._issue("DESIGN_PLAN_REQUIRED_REGION_MISSING", f"plan/regions/{region_id}", "必选布局区域未分配模块。"))
        size_limit = self.limits.get(size, {})
        if len(region_plans) > size_limit.get("maxModules", 0):
            issues.append(self._issue("DESIGN_PLAN_MODULE_LIMIT_EXCEEDED", "plan/regions", "顶层模块数超过尺寸上限。"))

        for region_id, region_plan in regions_by_id.items():
            region = layout_regions.get(region_id)
            if region is None:
                continue
            issues.extend(self._validate_region_plan(region, region_plan, feature_items, mapped_features))

        degradation_text = " ".join(item for item in plan.get("degradations", []) if isinstance(item, str))
        for feature_id, item in feature_items.items():
            count = mapped_features.get(feature_id, 0)
            if item.get("priority") == "mustKeep" and count != 1:
                issues.append(self._issue("DESIGN_PLAN_MUST_KEEP_MAPPING_INVALID", f"plan/featureProfile/contentItems/{feature_id}", "mustKeep 内容必须恰好映射一次。"))
            if item.get("priority") == "shouldKeep" and count > 1:
                issues.append(self._issue("DESIGN_PLAN_FEATURE_DUPLICATED", f"plan/featureProfile/contentItems/{feature_id}", "shouldKeep 内容最多映射一次。"))
            if item.get("priority") == "shouldKeep" and count == 0 and feature_id not in degradation_text:
                issues.append(self._issue("DESIGN_PLAN_DEGRADATION_UNRECORDED", f"plan/degradations/{feature_id}", "删除 shouldKeep 内容时必须记录 feature ID 和原因。"))

        bindings = plan.get("cardSpec", {}).get("dataBindings", [])
        if not isinstance(bindings, list):
            bindings = []
        if len(bindings) > size_limit.get("maxDataBindings", 0):
            issues.append(self._issue("DESIGN_PLAN_CAPABILITY_LIMIT_EXCEEDED", "plan/cardSpec/dataBindings", "数据能力数量超过尺寸上限。"))
        if len(feature.get("dataNeeds", [])) < len(bindings):
            issues.append(self._issue("DESIGN_PLAN_CAPABILITY_NOT_REQUESTED", "plan/cardSpec/dataBindings", "CardSpec 包含 Feature Profile 未声明的数据需求。"))
        if len(feature.get("dataNeeds", [])) > size_limit.get("maxDataBindings", 0):
            issues.append(self._issue("DESIGN_PLAN_CAPABILITY_LIMIT_EXCEEDED", "plan/featureProfile/dataNeeds", "Feature Profile 数据需求数量超过尺寸上限。"))
        action_limit = 1 if size == "2x2" else 2
        actions = feature.get("actions", [])
        if len(actions) > action_limit:
            issues.append(self._issue("DESIGN_PLAN_ACTION_LIMIT_EXCEEDED", "plan/featureProfile/actions", "动作数量超过尺寸上限。"))
        event_count = sum(len(region.get("events", [])) for region in region_plans if isinstance(region, dict) and isinstance(region.get("events", []), list))
        if event_count > len(actions):
            issues.append(self._issue("DESIGN_PLAN_EVENT_NOT_REQUESTED", "plan/regions/events", "Design Plan 事件数量超过 Feature Profile 动作数量。"))
        if not isinstance(plan.get("dataModel"), dict):
            issues.append(self._issue("DESIGN_PLAN_DATA_MODEL_INVALID", "plan/dataModel", "dataModel 必须是 object。"))
        return issues

    def _validate_plan_shape(self, plan: dict[str, Any]) -> list[DesignIssue]:
        issues: list[DesignIssue] = []
        required = {"schemaVersion", "surfaceId", "featureProfile", "layoutId", "styleProfile", "regions", "dataModel", "cardSpec", "degradations"}
        missing = sorted(required - set(plan))
        if missing:
            issues.append(self._issue("DESIGN_PLAN_FIELDS_MISSING", "plan", f"缺少字段：{missing}。"))
            return issues
        if plan.get("schemaVersion") != "design-plan-v1":
            issues.append(self._issue("DESIGN_PLAN_VERSION_INVALID", "plan/schemaVersion", "schemaVersion 必须是 design-plan-v1。"))
        surface_id = plan.get("surfaceId")
        if not isinstance(surface_id, str) or re.fullmatch(r"[a-z][a-z0-9-]*", surface_id) is None:
            issues.append(self._issue("DESIGN_PLAN_SURFACE_ID_INVALID", "plan/surfaceId", "surfaceId 必须是小写稳定标识。"))
        feature = plan.get("featureProfile")
        if not isinstance(feature, dict):
            issues.append(self._issue("FEATURE_PROFILE_INVALID", "plan/featureProfile", "featureProfile 必须是 object。"))
            return issues
        feature_required = {"schemaVersion", "serviceObject", "primaryQuestion", "size", "primaryVisual", "contentItems", "actions", "dataNeeds", "assetNeeds", "styleIntent"}
        feature_missing = sorted(feature_required - set(feature))
        if feature_missing:
            issues.append(self._issue("FEATURE_PROFILE_FIELDS_MISSING", "plan/featureProfile", f"缺少字段：{feature_missing}。"))
            return issues
        if feature.get("schemaVersion") != "feature-profile-v1":
            issues.append(self._issue("FEATURE_PROFILE_VERSION_INVALID", "plan/featureProfile/schemaVersion", "schemaVersion 必须是 feature-profile-v1。"))
        for field in ("serviceObject", "primaryQuestion"):
            if not isinstance(feature.get(field), str) or not feature[field].strip():
                issues.append(self._issue("FEATURE_PROFILE_TEXT_INVALID", f"plan/featureProfile/{field}", f"{field} 必须是非空字符串。"))
        if feature.get("primaryVisual") not in {"text", "metric", "progress", "media", "schedule", "status"}:
            issues.append(self._issue("FEATURE_PROFILE_VISUAL_INVALID", "plan/featureProfile/primaryVisual", "primaryVisual 未声明。"))
        content_items = feature.get("contentItems")
        if not isinstance(content_items, list) or not content_items:
            issues.append(self._issue("FEATURE_PROFILE_CONTENT_INVALID", "plan/featureProfile/contentItems", "contentItems 必须是非空数组。"))
        else:
            ids = [item.get("id") for item in content_items if isinstance(item, dict)]
            if len(ids) != len(content_items) or len(ids) != len(set(ids)):
                issues.append(self._issue("FEATURE_PROFILE_CONTENT_ID_INVALID", "plan/featureProfile/contentItems", "每个内容项必须有唯一 ID。"))
            for index, item in enumerate(content_items):
                if not isinstance(item, dict) or item.get("role") not in {"object", "primary", "support", "metric", "status", "badge", "action", "asset"}:
                    issues.append(self._issue("FEATURE_PROFILE_CONTENT_ROLE_INVALID", f"plan/featureProfile/contentItems/{index}", "内容角色无效。"))
                if not isinstance(item, dict) or item.get("priority") not in {"mustKeep", "shouldKeep"}:
                    issues.append(self._issue("FEATURE_PROFILE_PRIORITY_INVALID", f"plan/featureProfile/contentItems/{index}", "内容优先级无效。"))
        for field in ("actions", "dataNeeds", "assetNeeds", "regions", "degradations"):
            owner = feature if field in {"actions", "dataNeeds", "assetNeeds"} else plan
            if not isinstance(owner.get(field), list):
                issues.append(self._issue("DESIGN_PLAN_ARRAY_REQUIRED", f"plan/{'featureProfile/' if owner is feature else ''}{field}", f"{field} 必须是数组。"))
        card_spec = plan.get("cardSpec")
        if not isinstance(card_spec, dict):
            issues.append(self._issue("DESIGN_PLAN_CARDSPEC_INVALID", "plan/cardSpec", "cardSpec 必须是 object。"))
        else:
            for field, limit in (("title", 8), ("description", 12)):
                value = card_spec.get(field)
                if not isinstance(value, str) or not value or len(value) > limit:
                    issues.append(self._issue("DESIGN_PLAN_CARDSPEC_TEXT_INVALID", f"plan/cardSpec/{field}", f"{field} 必须是长度不超过 {limit} 的静态字符串。"))
            if card_spec.get("suggestSize") not in {"2x2", "2x4"}:
                issues.append(self._issue("DESIGN_PLAN_CARDSPEC_SIZE_INVALID", "plan/cardSpec/suggestSize", "suggestSize 只能是 2x2 或 2x4。"))
        return issues

    def assemble(self, plan: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        issues = self.validate_plan(plan)
        if issues:
            rendered = "; ".join(f"{item.code}@{item.location}: {item.message}" for item in issues)
            raise ValueError(rendered)
        layout = self.layouts[plan["layoutId"]]
        size = layout["size"]
        limit = self.limits[size]
        style = self.styles[plan["styleProfile"]]
        regions_by_id = {item["regionId"]: item for item in plan["regions"]}
        components: list[dict[str, Any]] = []
        root_children: list[str] = []
        for region in layout["regions"]:
            region_plan = regions_by_id.get(region["id"])
            if region_plan is None:
                continue
            expanded = self._expand_region(region, region_plan, style.get("colors", {}))
            components.extend(expanded)
            root_children.append(region["id"])

        root_styles = {
            "width": "matchParent",
            "height": "matchParent",
            "padding": limit["padding"],
            "borderRadius": limit["borderRadius"],
            "clip": True,
        }
        root_styles.update(copy.deepcopy(layout["root"].get("styles", {})))
        root_styles.update(copy.deepcopy(style.get("root", {})))
        root: dict[str, Any] = {
            "id": "root",
            "component": layout["root"]["component"],
            "children": root_children,
            "styles": root_styles,
        }
        if layout["root"].get("itemMargin"):
            root["itemMargin"] = layout["root"]["itemMargin"]
        components.insert(0, root)

        surface_id = plan["surfaceId"]
        messages = [
            {"version": "v0.9", "createSurface": {"surfaceId": surface_id, "catalogId": CATALOG_ID, "width": "matchParent", "height": "matchParent"}},
            {"version": "v0.9", "updateComponents": {"surfaceId": surface_id, "root": "root", "components": components}},
            {"version": "v0.9", "updateDataModel": {"surfaceId": surface_id, "path": "/", "value": copy.deepcopy(plan["dataModel"])}},
        ]
        dsl = "\n".join(json.dumps(item, ensure_ascii=False, separators=(",", ":")) for item in messages)
        cardspec = copy.deepcopy(plan["cardSpec"])
        return dsl, cardspec

    def _validate_schemas(self) -> list[DesignIssue]:
        issues: list[DesignIssue] = []
        for schema_name, relative in self.index.get("schemas", {}).items():
            path = self.templates_dir / relative
            try:
                schema = read_json(path)
                if Draft202012Validator is not None:
                    Draft202012Validator.check_schema(schema)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                issues.append(self._issue("DESIGN_SYSTEM_SCHEMA_INVALID", f"schemas/{schema_name}", str(exc)))
        return issues

    def _validate_layouts(self) -> list[DesignIssue]:
        issues = self._validate_value_against_schema(self.layouts_catalog, "layoutCatalog", "layouts")
        if len(self.layouts) != 12:
            issues.append(self._issue("DESIGN_SYSTEM_LAYOUT_COUNT_INVALID", "layouts", f"首版必须包含 12 个布局，当前为 {len(self.layouts)}。"))
        for layout_id, layout in self.layouts.items():
            size = layout.get("size")
            limit = self.limits.get(size, {})
            root = layout.get("root", {})
            regions = layout.get("regions", [])
            if root.get("component") not in {"Row", "Column"}:
                issues.append(self._issue("LAYOUT_ROOT_COMPONENT_INVALID", f"layouts/{layout_id}/root", "root 只能是 Row 或 Column。"))
                continue
            if len(regions) > limit.get("maxModules", 0):
                issues.append(self._issue("LAYOUT_MODULE_LIMIT_EXCEEDED", f"layouts/{layout_id}/regions", "布局顶层 region 数超过尺寸上限。"))
            axis = "width" if root.get("component") == "Row" else "height"
            content_budget = limit.get(axis, 0) - 2 * limit.get("padding", 0)
            total = sum(item.get(axis, 0) for item in regions)
            total += max(0, len(regions) - 1) * root.get("itemMargin", 0)
            if total > content_budget:
                issues.append(self._issue("LAYOUT_GEOMETRY_OVERFLOW", f"layouts/{layout_id}", f"{axis} 预算 {total} 超过 {content_budget}。"))
            ids = [item.get("id") for item in regions]
            if len(ids) != len(set(ids)):
                issues.append(self._issue("LAYOUT_REGION_DUPLICATE", f"layouts/{layout_id}/regions", "region ID 必须唯一。"))
        return issues

    def _validate_elements(self) -> list[DesignIssue]:
        issues = self._validate_value_against_schema(self.elements_catalog, "elementCatalog", "elements")
        for element_id, element in self.elements.items():
            if element.get("component") not in ALLOWED_ELEMENT_COMPONENTS:
                issues.append(self._issue("ELEMENT_COMPONENT_INVALID", f"elements/{element_id}", "元素使用了未允许组件。"))
            font_size = element.get("styles", {}).get("fontSize")
            if font_size is not None and font_size not in ALLOWED_FONT_SIZES:
                issues.append(self._issue("ELEMENT_FONT_SIZE_INVALID", f"elements/{element_id}/styles/fontSize", "字号不在批准阶梯中。"))
        return issues

    def _validate_modules(self) -> list[DesignIssue]:
        issues = self._validate_value_against_schema(self.modules_catalog, "moduleCatalog", "modules")
        for module_id, module in self.modules.items():
            for variant in module.get("variants", []):
                variant_id = variant.get("id")
                location = f"modules/{module_id}/{variant_id}"
                footprint = variant.get("footprint", {})
                nodes = variant.get("nodes", [])
                by_id = {node.get("id"): node for node in nodes if isinstance(node, dict)}
                if len(by_id) != len(nodes):
                    issues.append(self._issue("MODULE_NODE_DUPLICATE", f"{location}/nodes", "模块本地组件 ID 必须唯一。"))
                root = by_id.get(variant.get("rootLocalId"))
                if root is None:
                    issues.append(self._issue("MODULE_ROOT_MISSING", location, "模块变体缺少 rootLocalId 对应节点。"))
                else:
                    root_tokens = root.get("allowedTokens", [])
                    if root_tokens:
                        root_styles = []
                        for token_id in root_tokens:
                            token = self.elements.get(token_id, {})
                            styles = copy.deepcopy(token.get("styles", {}))
                            styles.update(root.get("styles", {}))
                            root_styles.append(styles)
                    else:
                        root_styles = [root.get("styles", {})]
                    if any(
                        styles.get("width") != footprint.get("width")
                        or styles.get("height") != footprint.get("height")
                        for styles in root_styles
                    ):
                        issues.append(self._issue("MODULE_FOOTPRINT_MISMATCH", location, "模块根节点宽高必须等于 footprint。"))
                for node_id, node in by_id.items():
                    component = node.get("component")
                    if component is not None and component not in ALLOWED_CONTAINER_COMPONENTS:
                        issues.append(self._issue("MODULE_CONTAINER_INVALID", f"{location}/nodes/{node_id}", "模块容器只能使用 Row、Column 或 Stack。"))
                    tokens = node.get("allowedTokens")
                    if tokens is not None:
                        if not isinstance(tokens, list) or not tokens or any(token not in self.elements for token in tokens):
                            issues.append(self._issue("MODULE_ELEMENT_TOKEN_INVALID", f"{location}/nodes/{node_id}", "模块引用了不存在的 element token。"))
                    children = node.get("children", [])
                    if any(child not in by_id for child in children):
                        issues.append(self._issue("MODULE_CHILD_UNKNOWN", f"{location}/nodes/{node_id}/children", "模块 children 引用了不存在节点。"))
                for slot_id, slot in variant.get("slots", {}).items():
                    if slot.get("node") not in by_id:
                        issues.append(self._issue("MODULE_SLOT_NODE_UNKNOWN", f"{location}/slots/{slot_id}", "内容槽位引用了不存在节点。"))
        return issues

    def _validate_compatibility(self) -> list[DesignIssue]:
        issues: list[DesignIssue] = []
        variants: list[tuple[str, str, str, dict[str, Any]]] = []
        for module_id, module in self.modules.items():
            for variant in module.get("variants", []):
                variants.append((module_id, module.get("role", ""), variant.get("id", ""), variant.get("footprint", {})))
        for layout_id, layout in self.layouts.items():
            for region in layout.get("regions", []):
                matches = [
                    item
                    for item in variants
                    if item[1] in region.get("allowedModuleRoles", [])
                    and item[3].get("width") == region.get("width")
                    and item[3].get("height") == region.get("height")
                ]
                if not matches:
                    issues.append(self._issue("LAYOUT_REGION_HAS_NO_MODULE", f"layouts/{layout_id}/regions/{region.get('id')}", "region 没有任何精确 footprint 的兼容模块。"))
        return issues

    def _validate_region_plan(
        self,
        region: dict[str, Any],
        region_plan: dict[str, Any],
        feature_items: dict[str, dict[str, Any]],
        mapped_features: dict[str, int],
    ) -> list[DesignIssue]:
        issues: list[DesignIssue] = []
        region_id = region["id"]
        module_id = region_plan.get("moduleId")
        module = self.modules.get(module_id)
        if module is None:
            return [self._issue("DESIGN_PLAN_MODULE_UNKNOWN", f"plan/regions/{region_id}/moduleId", f"未声明模块 {module_id}。")]
        if module.get("role") not in region.get("allowedModuleRoles", []):
            issues.append(self._issue("DESIGN_PLAN_MODULE_ROLE_INVALID", f"plan/regions/{region_id}", "模块角色与 region 不兼容。"))
        variant = self._variant(module, region_plan.get("variantId"))
        if variant is None:
            return issues + [self._issue("DESIGN_PLAN_VARIANT_UNKNOWN", f"plan/regions/{region_id}/variantId", "模块变体不存在。")]
        footprint = variant.get("footprint", {})
        if footprint.get("width") != region.get("width") or footprint.get("height") != region.get("height"):
            issues.append(self._issue("DESIGN_PLAN_FOOTPRINT_MISMATCH", f"plan/regions/{region_id}", "模块 footprint 必须与 region 完全相等。"))

        content = region_plan.get("content", {})
        slots = variant.get("slots", {})
        extra_slots = sorted(set(content) - set(slots))
        if extra_slots:
            issues.append(self._issue("DESIGN_PLAN_SLOT_UNKNOWN", f"plan/regions/{region_id}/content", f"模块不存在槽位：{extra_slots}。"))
        for slot_id, slot in slots.items():
            item = content.get(slot_id)
            if slot.get("required") and not isinstance(item, dict):
                issues.append(self._issue("DESIGN_PLAN_REQUIRED_SLOT_MISSING", f"plan/regions/{region_id}/content/{slot_id}", "必选内容槽位未填充。"))
                continue
            if not isinstance(item, dict):
                continue
            feature_id = item.get("featureId")
            if feature_id not in feature_items:
                issues.append(self._issue("DESIGN_PLAN_FEATURE_UNKNOWN", f"plan/regions/{region_id}/content/{slot_id}/featureId", "内容映射引用了未知 feature。"))
            else:
                mapped_features[feature_id] = mapped_features.get(feature_id, 0) + 1
                if feature_items[feature_id].get("role") != slot.get("role"):
                    issues.append(self._issue("DESIGN_PLAN_CONTENT_ROLE_MISMATCH", f"plan/regions/{region_id}/content/{slot_id}/featureId", "Feature 内容角色与模块槽位角色不一致。"))
            if item.get("bindingKind") not in slot.get("bindingKinds", []):
                issues.append(self._issue("DESIGN_PLAN_BINDING_KIND_INVALID", f"plan/regions/{region_id}/content/{slot_id}", "绑定方式不属于槽位允许集合。"))
            value = item.get("value")
            if item.get("bindingKind") == "expression" and (not isinstance(value, str) or not value.startswith("{{") or not value.endswith("}}")):
                issues.append(self._issue("DESIGN_PLAN_EXPRESSION_INVALID", f"plan/regions/{region_id}/content/{slot_id}/value", "expression 必须是完整 {{ ... }} 字符串。"))
            if item.get("bindingKind") == "path" and (not isinstance(value, str) or not value.startswith("/")):
                issues.append(self._issue("DESIGN_PLAN_PATH_INVALID", f"plan/regions/{region_id}/content/{slot_id}/value", "path 必须是绝对 JSON Pointer。"))
            limit = slot.get("maxChars")
            if item.get("bindingKind") == "static" and isinstance(value, str) and isinstance(limit, int) and len(value) > limit:
                issues.append(self._issue("DESIGN_PLAN_TEXT_OVERFLOW", f"plan/regions/{region_id}/content/{slot_id}", "静态文本超过模块字符预算。"))
            if slot.get("role") == "asset" and item.get("bindingKind") == "static":
                if not isinstance(value, str) or value not in self.asset_allowlist:
                    issues.append(self._issue("DESIGN_PLAN_ASSET_NOT_DECLARED", f"plan/regions/{region_id}/content/{slot_id}", "静态素材路径未在素材库声明。"))

        nodes = {node["id"]: node for node in variant.get("nodes", [])}
        elements = region_plan.get("elements", {})
        extra_elements = sorted(set(elements) - set(nodes))
        if extra_elements:
            issues.append(self._issue("DESIGN_PLAN_ELEMENT_NODE_UNKNOWN", f"plan/regions/{region_id}/elements", f"元素选择引用了未知节点：{extra_elements}。"))
        for node_id, node in nodes.items():
            allowed = node.get("allowedTokens")
            if not allowed:
                continue
            omitted = self._node_is_omitted(node_id, node, slots, content)
            token = elements.get(node_id)
            if omitted and token is None:
                continue
            if token not in allowed:
                issues.append(self._issue("DESIGN_PLAN_ELEMENT_TOKEN_INVALID", f"plan/regions/{region_id}/elements/{node_id}", "元素 token 不在模块节点允许集合中。"))

        events = region_plan.get("events", [])
        if not isinstance(events, list):
            events = []
        for index, event in enumerate(events):
            target = event.get("target") if isinstance(event, dict) else None
            handler = event.get("handler") if isinstance(event, dict) else None
            if target not in variant.get("eventTargets", []):
                issues.append(self._issue("DESIGN_PLAN_EVENT_TARGET_INVALID", f"plan/regions/{region_id}/events/{index}", "事件目标未由模块声明。"))
            if not isinstance(handler, dict) or not isinstance(handler.get("call"), str):
                issues.append(self._issue("DESIGN_PLAN_EVENT_HANDLER_INVALID", f"plan/regions/{region_id}/events/{index}", "事件必须包含合法 call。"))
            elif any(key in handler for key in ("condition", "as", "$context")):
                issues.append(self._issue("DESIGN_PLAN_EVENT_HANDLER_INVALID", f"plan/regions/{region_id}/events/{index}", "Form 事件不支持 condition、as 或 $context。"))
        event_targets = {event.get("target") for event in events if isinstance(event, dict)}
        action_nodes = {
            slot.get("node")
            for slot_id, slot in slots.items()
            if slot.get("role") == "action" and slot_id in content
        }
        for node_id in action_nodes:
            if node_id in variant.get("eventTargets", []) and node_id not in event_targets:
                issues.append(self._issue("DESIGN_PLAN_ACTION_EVENT_MISSING", f"plan/regions/{region_id}/events", "动作内容必须绑定模块声明的合法事件；没有事件时删除动作模块。"))
        return issues

    def _expand_region(self, region: dict[str, Any], region_plan: dict[str, Any], colors: dict[str, str]) -> list[dict[str, Any]]:
        module = self.modules[region_plan["moduleId"]]
        variant = self._variant(module, region_plan["variantId"])
        assert variant is not None
        nodes = variant["nodes"]
        slots = variant.get("slots", {})
        content = region_plan.get("content", {})
        omitted = {
            node["id"]
            for node in nodes
            if self._node_is_omitted(node["id"], node, slots, content)
        }
        id_map = {
            node["id"]: region["id"]
            if node["id"] == variant["rootLocalId"]
            else f"{region['id']}__{module['id']}__{node['id']}"
            for node in nodes
            if node["id"] not in omitted
        }
        selected_tokens = region_plan.get("elements", {})
        expanded: dict[str, dict[str, Any]] = {}
        for node in nodes:
            local_id = node["id"]
            if local_id in omitted:
                continue
            component: dict[str, Any] = {"id": id_map[local_id]}
            token_id = selected_tokens.get(local_id)
            if token_id:
                token = copy.deepcopy(self.elements[token_id])
                component["component"] = token["component"]
                component.update(copy.deepcopy(token.get("properties", {})))
                styles = copy.deepcopy(token.get("styles", {}))
            else:
                component["component"] = node["component"]
                styles = {}
            for key in ("itemMargin", "space"):
                if key in node:
                    component[key] = node[key]
            children = [id_map[child] for child in node.get("children", []) if child in id_map]
            if "children" in node:
                component["children"] = children
            styles.update(copy.deepcopy(node.get("styles", {})))
            if styles:
                component["styles"] = self._resolve_colors(styles, colors)
            expanded[local_id] = component

        for slot_id, slot in slots.items():
            item = content.get(slot_id)
            node_id = slot.get("node")
            if not isinstance(item, dict) or node_id not in expanded:
                continue
            value = item.get("value")
            if item.get("bindingKind") == "path":
                value = {"path": value}
            expanded[node_id][slot["property"]] = value

        for event in region_plan.get("events", []):
            target = event.get("target")
            if target in expanded:
                expanded[target]["onClick"] = [copy.deepcopy(event["handler"])]
        return [expanded[node["id"]] for node in nodes if node["id"] in expanded]

    def _validate_value_against_schema(self, value: dict[str, Any], schema_key: str, location: str) -> list[DesignIssue]:
        if Draft202012Validator is None:
            return []
        relative = self.index.get("schemas", {}).get(schema_key)
        if not isinstance(relative, str):
            return [self._issue("DESIGN_SYSTEM_SCHEMA_MISSING", location, f"缺少 {schema_key} schema。")]
        schema = read_json(self.templates_dir / relative)
        validator = Draft202012Validator(schema)
        issues: list[DesignIssue] = []
        for error in sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path)):
            suffix = "/".join(str(item) for item in error.absolute_path)
            pointer = f"{location}/{suffix}" if suffix else location
            issues.append(self._issue("DESIGN_SYSTEM_SCHEMA_VALIDATION_FAILED", pointer, error.message))
        return issues

    @staticmethod
    def _variant(module: dict[str, Any], variant_id: Any) -> dict[str, Any] | None:
        return next(
            (item for item in module.get("variants", []) if isinstance(item, dict) and item.get("id") == variant_id),
            None,
        )

    @staticmethod
    def _node_is_omitted(node_id: str, node: dict[str, Any], slots: dict[str, Any], content: dict[str, Any]) -> bool:
        if not node.get("optional"):
            return False
        node_slots = [slot_id for slot_id, slot in slots.items() if slot.get("node") == node_id]
        return bool(node_slots) and not any(slot_id in content for slot_id in node_slots)

    @staticmethod
    def _resolve_colors(value: Any, colors: dict[str, str]) -> Any:
        if isinstance(value, dict):
            return {key: DesignSystem._resolve_colors(item, colors) for key, item in value.items()}
        if isinstance(value, list):
            return [DesignSystem._resolve_colors(item, colors) for item in value]
        if isinstance(value, str) and value.startswith("@color."):
            return colors.get(value.removeprefix("@color."), value)
        return value

    @staticmethod
    def _issue(code: str, location: str, message: str, severity: str = "error") -> DesignIssue:
        return DesignIssue(severity=severity, code=code, location=location, message=message)


def load_design_plan(path: Path) -> dict[str, Any]:
    return read_json(path)
