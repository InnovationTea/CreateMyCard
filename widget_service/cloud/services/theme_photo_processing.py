"""共用图片后处理：样式、背景层、加载兜底及登记地址；不调用模型。"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field

from models.artifact import WidgetArtifact
from services.asset_url_mapper import AssetUrlMapper
from services.fusion_ball_expander import (
    build_fusion_ball_palette,
    expand_fusion_ball_components,
    fusion_ball_enabled,
)
from services.post_layout_theme_registry import (
    load_theme_registry,
    photo_fallback,
    registered_themes,
)
from services.theme_style_roles import COLOR_FIELDS, ROLE_PATTERN, is_role, resolve_role

PREFIX = "__post_theme_"


@dataclass(frozen=True)
class PhotoStyleContext:
    """编译器提供的主题归属，不从已绘制颜色反推显式颜色或图标原色。"""

    roles: dict[str, dict[str, str]] = field(default_factory=dict)
    surfaces: frozenset[str] = frozenset()
    button_ids: frozenset[str] = frozenset()


def photo_background(photo: dict) -> list[dict]:
    return [
        {"id": PREFIX + "background", "component": "Stack", "children": [PREFIX + "base"],
         "styles": {"width": "matchParent", "height": "matchParent", "alignContent": "topStart"}},
        {"id": PREFIX + "base", "component": "Image", "src": photo.get("src"),
         "styles": {"width": "matchParent", "height": "matchParent",
                    "objectFit": "fill" if photo.get("objectFit") == "fill" else "cover"}},
    ]


def has_content_surface(node: dict, legacy_panels: list[str]) -> bool:
    if node.get("component") not in {"Row", "Column", "Stack", "Button"}:
        return False
    background = node.get("styles", {}).get("backgroundColor")
    if is_role(background):
        match = ROLE_PATTERN.fullmatch(background)
        if match is None or float(match[2] or 1) == 0:
            return False
        if match[1] == "panel":
            return True
        return match[1] in {"componentSecondary", "componentTertiary"} and bool(node.get("onClick"))
    if not isinstance(background, str) or not re.fullmatch(r"#[0-9A-Fa-f]{8}", background):
        return False
    if int(background[1:3], 16) == 0:
        return False
    return background in legacy_panels or bool(node.get("onClick"))


def apply_content_palette(
    nodes: list[dict], roles: dict, panel: str, *, surface_style: dict,
    legacy_panels: list[str], ownership: PhotoStyleContext | None = None,
) -> None:
    """融合解析角色值；模板仅更新编译器明确标记为主题所有的属性。"""
    for node in nodes:
        styles = node.setdefault("styles", {})
        if ownership is not None:
            for key, value in ownership.roles.get(node.get("id"), {}).items():
                styles[key] = resolve_role(value, roles, panel)
            if node.get("id") in ownership.surfaces:
                styles["backgroundColor"] = panel
                styles.update(copy.deepcopy(surface_style))
            continue
        content_surface = bool(surface_style) and has_content_surface(node, legacy_panels)
        role_keys = set()
        for key in COLOR_FIELDS:
            if is_role(styles.get(key)):
                styles[key] = resolve_role(styles[key], roles, panel)
                role_keys.add(key)
        for key in ("fontColor", "fillColor", "color", "borderColor"):
            if key in styles and key not in role_keys:
                old = styles.get(key)
                secondary = isinstance(old, str) and old.startswith(("#99", "#66", "#CC"))
                styles[key] = roles.get("secondary") if secondary else roles.get("primary")
        if node.get("component") == "Text":
            styles.setdefault("fontColor", roles.get("primary"))
        if node.get("id") == "root":
            styles.pop("linearGradient", None)
            styles.pop("backgroundColor", None)
            continue
        if "backgroundColor" in styles and "backgroundColor" not in role_keys:
            old = styles.get("backgroundColor")
            if isinstance(old, str) and old.startswith("#00"):
                continue
            styles["backgroundColor"] = panel if old in legacy_panels else roles.get(
                "componentSecondary",
            )
        if content_surface and not styles.get("backgroundColor", "#00").startswith("#00"):
            styles.update(copy.deepcopy(surface_style))


def fusion_background(theme: dict, task: dict, *, enabled: bool | None = None) -> list[dict]:
    if enabled is None:
        enabled = fusion_ball_enabled(task.get("appVersion"))
    if not enabled:
        raise ValueError("Fusion theme is not enabled for this runtime")
    background = theme.get("background", {})
    colors = background.get("ballColors", {})
    palette = build_fusion_ball_palette(
        colors.get("large"), colors.get("medium"), colors.get("small"),
    )
    expanded = expand_fusion_ball_components(
        [{"id": "root", "component": "Column", "children": [], "styles": {}}],
        palette, size=task.get("size"),
    )
    result = []
    for item in expanded:
        identity = item.get("id", "")
        if not identity.startswith("fusionBall"):
            continue
        if identity == "fusionBallGlassLayer":
            styles = item.get("styles", {})
            styles["backgroundColor"] = background.get("glassColor")
            styles["backdropBlur"] = {"radius": background.get("blurRadius")}
        result.append(item)
    return result


def apply_photo_fallback(
    shell: dict, foreground: dict, layers: list[dict], task: dict, primary: str,
    *, foreground_id: str | None = None, enabled: bool | None = None,
) -> None:
    fallback = photo_fallback(primary)
    background = fallback.get("background", {})
    styles = shell.setdefault("styles", {})
    if fallback.get("kind") == "gradient":
        colors = background.get("colors", [])
        styles["backgroundColor"] = colors[-1]
        styles["linearGradient"] = {
            "direction": background.get("direction"), "colors": [[colors[0], 0], [colors[1], 1]],
        }
    else:
        styles["backgroundColor"] = background.get("ballColors", {}).get("large")
        active = fusion_ball_enabled(task.get("appVersion")) if enabled is None else enabled
        if active:
            children = layers[0].get("children")
            if not isinstance(children, list):
                raise ValueError("Photo background requires a child list")
            if foreground_id is not None:
                foreground["id"] = foreground_id
                shell["children"] = [PREFIX + "background", foreground_id]
            children.insert(0, "fusionBallBackground")
            layers.extend(fusion_background(fallback, task, enabled=True))


def deliver_photo_source(source: str, photo: dict) -> str:
    src = photo.get("src")
    address = photo.get("remoteUrl") or src
    if not isinstance(src, str) or not isinstance(address, str):
        raise ValueError("Photo delivery source is missing")
    return AssetUrlMapper({src: address}, {src}).rewrite_standard(source)


def register_photo_asset(artifact: WidgetArtifact) -> WidgetArtifact:
    """按唯一背景 Image 登记受信素材，供两条链路的完整校验与编辑恢复使用。"""
    sources = set()
    for line in artifact.genui.splitlines():
        record = json.loads(line)
        for node in record.get("updateComponents", {}).get("components", []):
            if node.get("id") == PREFIX + "base" and node.get("component") == "Image":
                sources.add(node.get("src"))
    if not sources:
        return artifact
    matches = []
    # 准入始终只选启用图；登记阶段也支持历史产物引用的已停用注册素材。
    for photo in registered_themes(include_disabled=True):
        if photo.get("kind") == "photo":
            if (photo.get("remoteUrl") or photo.get("src")) in sources:
                matches.append(photo)
    if len(sources) != 1 or len(matches) != 1:
        raise ValueError("Photo delivery must reference one registered theme")
    photo = matches[0]
    result = artifact.model_copy(deep=True)
    identity = photo.get("id")
    candidates = result.taskSpec.setdefault("assetCandidates", [])
    if not any(item.get("id") == identity for item in candidates):
        candidates.append({"id": identity, "src": next(iter(sources)), "description": "主题背景"})
    assets = result.effectiveCapabilities.setdefault("asset", [])
    if identity not in assets:
        assets.append(identity)
    return result


def template_foreground(source: str) -> dict:
    """定稿内容签名只忽略允许修改的颜色/背景材质；保留节点、布局和绑定。"""
    records = [json.loads(line) for line in source.splitlines() if line.strip()]
    nodes = []
    data = []
    for record in records:
        if "updateComponents" in record:
            nodes.extend(record.get("updateComponents", {}).get("components", []))
        else:
            data.append(record)
    by_id = {node.get("id"): node for node in nodes}
    if len(by_id) != len(nodes):
        raise ValueError("Template foreground contains duplicate component IDs")

    def visit(identity: str, ancestors: set[str]) -> dict:
        node = by_id.get(identity)
        if node is None or identity in ancestors:
            raise ValueError("Template foreground tree is incomplete")
        value = copy.deepcopy(node)
        for key in COLOR_FIELDS | {"linearGradient", "backdropBlur"}:
            value.get("styles", {}).pop(key, None)
        if "children" in value:
            children = value.get("children", [])
            value["children"] = [visit(child, ancestors | {identity}) for child in children]
        return value

    root = by_id.get("root", {})
    if "template_root" not in root.get("children", []):
        raise ValueError("Template foreground must be a direct child of root")
    shell = copy.deepcopy(root)
    shell["children"] = [child for child in root.get("children", [])
                         if child not in {"fusionBallBackground", PREFIX + "background"}]
    for key in COLOR_FIELDS | {"linearGradient", "backdropBlur"}:
        shell.get("styles", {}).pop(key, None)
    return {"root": shell, "content": visit("template_root", set()), "records": data}


def apply_template_photo(
    source: str, photo: dict, task: dict, ownership: PhotoStyleContext,
) -> str:
    before = template_foreground(source)
    records = [json.loads(line) for line in source.splitlines() if line.strip()]
    update = next(row.get("updateComponents") for row in records if "updateComponents" in row)
    nodes = update.get("components", [])
    if any(str(node.get("id", "")).startswith(PREFIX) for node in nodes):
        raise ValueError("Photo theme must only be applied once")
    root = next(node for node in nodes if node.get("id") == "root")
    if root.get("component") != "Stack":
        raise ValueError("Template photo requires an existing Stack canvas")
    content = photo.get("content", {})
    roles = content.get("roles", {})
    panel = content.get("panelBySize", {}).get(task.get("size"))
    if not roles or not panel:
        raise ValueError("Photo theme is missing complete content colors")
    by_id = {node.get("id"): node for node in nodes}
    removed = set()
    pending = ["fusionBallBackground"]
    while pending:
        identity = pending.pop()
        if identity in removed:
            raise ValueError("Invalid old background tree")
        node = by_id.get(identity)
        if node is not None:
            removed.add(identity)
            pending.extend(node.get("children", []))
    nodes = [node for node in nodes if node.get("id") not in removed]
    root["children"] = [child for child in root.get("children", []) if child not in removed]
    apply_content_palette(
        nodes, roles, panel, surface_style=load_theme_registry().get("photoSurfaceStyle", {}),
        legacy_panels=[], ownership=ownership,
    )
    root.get("styles", {}).pop("linearGradient", None)
    layers = photo_background(photo)
    apply_photo_fallback(root, {}, layers, task, roles.get("primary"))
    root["children"].insert(0, PREFIX + "background")
    update["components"] = [*layers, *nodes]
    result = "\n".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in records
    )
    result = deliver_photo_source(result, photo)
    if template_foreground(result) != before:
        raise ValueError("Photo altered template foreground layout, content or actions")
    return result
