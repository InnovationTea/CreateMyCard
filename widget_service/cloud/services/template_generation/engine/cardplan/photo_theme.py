"""从图片 JSON 匹配模板主题，并编译背景、底板材质和交付素材。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.logger import logger
from config.config import get_settings
from models.generation import TaskSpec
from services.post_layout_theme_registry import load_theme_registry, registered_themes
from services.template_generation.engine.tersel_converter import Nested2Node

from .models import (
    PhotoBackgroundStyle,
    TemplateDefinition,
    TemplateNode,
    TemplatePlan,
    ThemeDefinition,
)
from .photo_delivery import photo_surface_style
from .photo_preference import photo_preference_reason

if TYPE_CHECKING:
    from .registry import CardPlanRegistry

PHOTO_BACKGROUND_ID = "__post_theme_base"
SURFACE_MARKER = "_templateThemeSurface"
_SURFACE_REFERENCES = {"actionStyle.backgroundColor", "supportContentStyle.backgroundColor"}


def load_template_photo_themes(
    templates: dict[str, TemplateDefinition],
    mapping_path: Path,
) -> dict[str, ThemeDefinition]:
    """映射只引用主题与主模板 ID；未配置或过期条目不影响普通模板。"""
    mappings = _load_mappings(mapping_path)
    config = load_theme_registry()
    fallback = config.get("photoFallbacks", {}).get("color")
    result: dict[str, ThemeDefinition] = {}
    for photo in registered_themes():
        if photo.get("kind") != "photo":
            continue
        template_ids = []
        capability_ids: list[str] = []
        mapping = mappings.get(photo.get("id"), {})
        for template_id in mapping.get("templateIds", ()):
            definition = templates.get(template_id)
            if definition is None or definition.business_id is None:
                continue
            template_ids.append(template_id)
            capability_id = definition.capability_id
            if capability_id is not None and capability_id not in capability_ids:
                capability_ids.append(capability_id)
        if not template_ids:
            continue
        size = photo.get("size")
        content = photo.get("content", {})
        roles = content.get("roles", {})
        panel = content.get("panelBySize", {}).get(size)
        theme = ThemeDefinition.model_validate({
            "themeFormat": "card-theme/2",
            "themeProfileId": photo.get("id"),
            "description": photo.get("description"),
            "supportedCapabilityIds": capability_ids,
            "primaryColor": roles.get("primary"),
            "supportContentColor": roles.get("secondary"),
            "progressColor": roles.get("graphicPrimary"),
            "progressBackgroundColor": roles.get("componentSecondary"),
            "rootStyle": {
                "backgroundColor": fallback, "borderRadius": 20, "padding": 12, "clip": True,
            },
            "actionStyle": {"backgroundColor": panel, "contentColor": roles.get("primary")},
            "allowTemplateActionBackgroundOverride": False,
            "supportContentStyle": {"backgroundColor": panel, "borderRadius": 12},
            "firstLayerRule": {"path": "post_layout_themes.json"},
            "photo_background_style": {
                "src": photo.get("src"), "object_fit": photo.get("objectFit"), "size": size,
                "template_ids": template_ids, "pool": photo.get("pool"),
                "layout_template_ids": mapping.get("layoutTemplateIds"),
            },
        })
        result[theme.theme_profile_id] = theme
    return result


def _load_mappings(path: Path) -> dict[str, dict[str, tuple[str, ...]]]:
    result: dict[str, dict[str, tuple[str, ...]]] = {}
    if not path.exists():
        return result
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(config, dict) or config.get("version") != 1:
            raise ValueError("Unsupported photo template mapping version")
        mappings = config.get("mappings")
        if not isinstance(mappings, list):
            raise ValueError("Photo template mappings must be an array")
        for mapping in mappings:
            if not isinstance(mapping, dict):
                raise ValueError("Photo template mapping must be an object")
            identity = mapping.get("themeId")
            ids = mapping.get("templateIds")
            if not isinstance(identity, str) or not isinstance(ids, list):
                raise ValueError("Photo mapping requires themeId and templateIds")
            if not ids or any(not isinstance(item, str) for item in ids):
                raise ValueError("Photo templateIds must be a nonempty string array")
            layouts = mapping.get("layoutTemplateIds")
            if not isinstance(layouts, list) or not layouts:
                raise ValueError("Photo mapping requires layoutTemplateIds")
            if any(not isinstance(item, str) or not item for item in layouts):
                raise ValueError("Photo layoutTemplateIds must contain nonempty strings")
            if identity in result:
                raise ValueError("Duplicate photo theme mapping")
            result[identity] = {
                "templateIds": tuple(dict.fromkeys(ids)),
                "layoutTemplateIds": tuple(dict.fromkeys(layouts)),
            }
    except (OSError, ValueError) as exc:
        logger.warning(f"template_photo_mapping_unavailable path={path} detail={exc}")
        result = {}
    return result


def select_template_photo_theme(
    plans: tuple[TemplatePlan, ...], task: TaskSpec, registry: CardPlanRegistry,
) -> tuple[TemplatePlan, ...]:
    """逐计划记录候选，保持原主题与候选排序；定稿内容检查后才切换。"""
    enabled = get_settings().enable_photo_background_theme
    if not enabled or photo_preference_reason(task.userQuery):
        return tuple(plan.model_copy(update={"photo_theme_ids": ()}) for plan in plans)
    selected = []
    for plan in plans:
        candidates = []
        for theme in registry.photo_themes.values():
            photo = theme.photo_background_style
            if photo is None or photo.size != task.size:
                continue
            if _matches_plan(plan, photo, registry):
                candidates.append(theme.theme_profile_id)
        selected.append(plan.model_copy(update={"photo_theme_ids": tuple(candidates)}))
    return tuple(selected)


def _matches_plan(
    plan: TemplatePlan, photo: PhotoBackgroundStyle, registry: CardPlanRegistry,
) -> bool:
    if plan.layout_template_id not in photo.layout_template_ids or not plan.business_slots:
        return False
    main = min(plan.business_slots, key=lambda slot: slot.position)
    if main.position != 0 or main.template_id not in photo.template_ids:
        return False
    for slot in plan.business_slots:
        definition = registry.require_template(slot.template_id)
        if definition.compatible_theme_profile_ids:
            return False
    return True


def mark_theme_surfaces(node: TemplateNode, values: list[Any]) -> None:
    """标记受信蓝图中的主题底板，避免按颜色猜测而模糊图形或业务内容。"""
    if node.component not in {"Button", "Row", "Column", "Stack"}:
        return
    for blueprint, value in zip(node.values, values, strict=True):
        if not isinstance(value, dict):
            continue
        background = blueprint.properties.get("backgroundColor")
        if background is None or background.kind != "theme":
            continue
        if background.name in _SURFACE_REFERENCES:
            value[SURFACE_MARKER] = True


def normalize_photo_styles(styles: dict) -> dict:
    """模板旧左对齐写法适配到交付枚举，不改动几何和业务内容。"""
    result = dict(styles)
    if result.get("textAlign") == "left":
        result["textAlign"] = "start"
    return result


def apply_photo_surfaces(node: Nested2Node, theme: ThemeDefinition) -> Nested2Node:
    photo = theme.photo_background_style
    if photo is None:
        return node
    values: list[Any] = []
    for value in node.values:
        if isinstance(value, dict):
            value = normalize_photo_styles(value)
            marked = value.pop(SURFACE_MARKER, False)
            if marked and value.get("backgroundColor"):
                value.update(photo_surface_style())
        values.append(value)
    children = tuple(apply_photo_surfaces(child, theme) for child in node.children)
    return Nested2Node(node.component_type, tuple(values), children)


def apply_photo_background(card: Nested2Node, theme: ThemeDefinition) -> Nested2Node:
    """背景单独成层，不经过内容补色；复用现有内容安全边距。"""
    photo = theme.photo_background_style
    if photo is None:
        return card
    if card.component_type != "Stack":
        raise ValueError("Photo template requires one content skeleton")
    foreground = []
    template_roots = 0
    for child in card.children:
        child_id: Any = None
        for value in child.values:
            if isinstance(value, dict) and "_id" in value:
                child_id = value.get("_id")
        if child_id == "template_root":
            template_roots += 1
        if child_id != "fusionBallBackground":
            foreground.append(child)
    if template_roots != 1:
        raise ValueError("Photo template requires one direct template_root")
    from services.post_layout_theme import photo_background

    registered = next(
        item for item in registered_themes() if item.get("id") == theme.theme_profile_id
    )
    layers = photo_background(registered)
    by_id = {item.get("id"): item for item in layers}

    def build(identity: str) -> Nested2Node:
        item = by_id.get(identity)
        if item is None:
            raise ValueError("Photo background layer is missing")
        options = {"_id": identity, **item.get("styles", {})}
        component = item.get("component")
        children = tuple(build(child) for child in item.get("children", []))
        values: tuple[Any, ...] = (options,)
        if component == "Image":
            values = (item.get("src"), options)
        return Nested2Node(component, values, children)

    background = build("__post_theme_background")
    # 保留 root 对 template_root 的直接引用，沿用公共校验的模板豁免。
    return Nested2Node(card.component_type, card.values, (background, *foreground))
