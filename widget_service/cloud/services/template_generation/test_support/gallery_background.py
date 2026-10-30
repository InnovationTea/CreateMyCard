"""画廊主题验收：区分普通融球与已登记图片下的加载兜底。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.fusion_ball_expander import fusion_ball_enabled
from services.post_layout_theme_registry import photo_fallback, registered_themes


@dataclass(frozen=True)
class GalleryBackgroundCheck:
    error: str
    fusion_rendered: bool
    kind: str


def _components(messages: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for message in messages:
        update = message.get("updateComponents")
        if not isinstance(update, dict):
            continue
        for node in update.get("components", []):
            if not isinstance(node, dict):
                continue
            identity = node.get("id")
            if isinstance(identity, str):
                result[identity] = node
    return result


def _photo_error(nodes: dict[str, dict[str, Any]], app_version: str) -> str:
    image = nodes.get("__post_theme_base", {})
    styles = image.get("styles", {})
    if image.get("component") != "Image":
        return "图片背景缺少 Image"
    if styles.get("width") != "matchParent" or styles.get("height") != "matchParent":
        return "图片背景不是全幅图片"
    source = image.get("src")
    theme: dict[str, Any] | None = None
    for candidate in registered_themes():
        if candidate.get("kind") != "photo":
            continue
        address = candidate.get("remoteUrl") or candidate.get("src")
        if isinstance(address, str) and source == address:
            theme = candidate
            break
    if theme is None:
        return "图片背景未登记或已停用"
    root = nodes.get("root", {})
    children = root.get("children", [])
    if not children or children[0] != "__post_theme_background":
        return "图片背景未置于根节点前景下方"
    if "template_root" not in children:
        return "图片背景缺少原模板前景"
    primary = theme.get("content", {}).get("roles", {}).get("primary")
    if not isinstance(primary, str):
        return "图片主题缺少主文字颜色"
    fallback = photo_fallback(primary)
    background = fallback.get("background", {})
    root_styles = root.get("styles", {})
    fusion_expected = False
    if fallback.get("kind") == "gradient":
        colors = background.get("colors", [])
        if len(colors) != 2:
            return "图片渐变兜底配置无效"
        expected_gradient = {
            "direction": background.get("direction"),
            "colors": [[colors[0], 0], [colors[1], 1]],
        }
        if root_styles.get("linearGradient") != expected_gradient:
            return "黑字图片缺少配置的渐变兜底"
        expected_color = colors[-1]
    else:
        fusion_expected = fusion_ball_enabled(app_version)
        expected_color = background.get("ballColors", {}).get("large")
        if root_styles.get("linearGradient") is not None:
            return "白字图片不应保留渐变兜底"
    if root_styles.get("backgroundColor") != expected_color:
        return "图片兜底底色与主题配置不符"
    expected_children = ["__post_theme_base"]
    if fusion_expected:
        expected_children.insert(0, "fusionBallBackground")
    layer = nodes.get("__post_theme_background", {})
    if layer.get("component") != "Stack" or layer.get("children") != expected_children:
        return "图片兜底层次与文字颜色或版本门禁不符"
    if ("fusionBallBackground" in nodes) != fusion_expected:
        return "图片融球兜底与文字颜色或版本门禁不符"
    return ""


def check_gallery_background(
    messages: list[dict[str, Any]], *, expected_fusion: bool, app_version: str,
) -> GalleryBackgroundCheck:
    """图片使用登记主题的兜底合同；普通背景继续使用场景原有融球断言。"""
    nodes = _components(messages)
    fusion_rendered = "fusionBallBackground" in nodes
    has_photo_marker = any(identity.startswith("__post_theme_") for identity in nodes)
    error = ""
    kind = "fusion" if fusion_rendered else "ordinary"
    if has_photo_marker:
        kind = "photo"
        error = _photo_error(nodes, app_version)
    elif fusion_rendered != expected_fusion:
        error = f"融球版本校验失败：期望 {expected_fusion}，实际 {fusion_rendered}"
    elif fusion_rendered and not fusion_ball_enabled(app_version):
        error = "当前版本不支持融球背景"
    return GalleryBackgroundCheck(error, fusion_rendered, kind)
