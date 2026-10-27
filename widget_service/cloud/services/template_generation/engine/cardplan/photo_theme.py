"""模板主题样式归属；旧绘制入口保留兼容，正式选图走公共后处理。"""

from __future__ import annotations

from typing import Any

from services.fusion_ball_expander import build_fusion_ball_content_id
from services.post_layout_theme_registry import registered_themes
from services.template_generation.engine.tersel_converter import Nested2Node
from services.theme_photo_processing import PhotoStyleContext
from services.theme_style_roles import role

from .models import (
    TemplateNode,
    ThemeDefinition,
)
from .photo_delivery import photo_surface_style

PHOTO_BACKGROUND_ID = "__post_theme_base"
SURFACE_MARKER = "_templateThemeSurface"
STYLE_MARKER = "_templateThemeRoles"
ACTION_MARKER = "_templatePhotoAction"
PRESERVE_MARKER = "_templatePhotoPreserve"
_PHOTO_STYLE_ROLES = {
    "primaryColor": "primary", "supportContentColor": "secondary",
    "progressColor": "graphicPrimary", "progressBackgroundColor": "componentSecondary",
    "actionStyle.backgroundColor": "panel", "actionStyle.contentColor": "primary",
    "supportContentStyle.backgroundColor": "panel",
}
_SURFACE_REFERENCES = {"actionStyle.backgroundColor", "supportContentStyle.backgroundColor"}


def mark_theme_surfaces(node: TemplateNode, values: list[Any]) -> None:
    """标记受信蓝图中的主题底板，避免按颜色猜测而模糊图形或业务内容。"""
    for blueprint, value in zip(node.values, values, strict=True):
        if not isinstance(value, dict):
            continue
        style_roles = {}
        for key, attribute in blueprint.properties.items():
            semantic = _PHOTO_STYLE_ROLES.get(attribute.name) if attribute.kind == "theme" else None
            if semantic is not None:
                style_roles[key] = role(semantic)
        if style_roles:
            value[STYLE_MARKER] = style_roles
        background = blueprint.properties.get("backgroundColor")
        if background is None or background.kind != "theme":
            continue
        if background.name in _SURFACE_REFERENCES:
            value[SURFACE_MARKER] = True


def collect_photo_style_context(root: Nested2Node) -> PhotoStyleContext:
    """按转换器相同编号规则记录侧车数据；标记不进入 A2UI，也不改动任何节点 ID。"""
    roles = {}
    surfaces = set()
    buttons = set()

    def visit(node: Nested2Node, identity: str, preserved: bool, action: bool) -> None:
        options = next((item for item in node.values if isinstance(item, dict)), {})
        preserved = preserved or options.get("_preserveOriginalColor") is True
        preserved = preserved or options.get(PRESERVE_MARKER) is True
        if options.get(ACTION_MARKER):
            buttons.add(identity)
        action = action or options.get(ACTION_MARKER) is True
        if not preserved:
            owned = dict(options.get(STYLE_MARKER, {}))
            if action:
                if "fontColor" in options:
                    owned.setdefault("fontColor", role("primary"))
                if options.get("backgroundColor") not in {None, "#00000000", "transparent"}:
                    owned.setdefault("backgroundColor", role("panel"))
                    surfaces.add(identity)
            if owned:
                roles[identity] = owned
            if options.get(SURFACE_MARKER):
                surfaces.add(identity)
        base = identity.removeprefix("__genui_render_component__")
        for index, child in enumerate(node.children):
            child_options = next((item for item in child.values if isinstance(item, dict)), {})
            child_id = child_options.get("_id") or f"{base}_{index}"
            visit(child, child_id, preserved, action)

    if len(root.children) == 1:
        visit(root.children[0], build_fusion_ball_content_id("root_1"), False, False)
    return PhotoStyleContext(roles, frozenset(surfaces), frozenset(buttons))


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
