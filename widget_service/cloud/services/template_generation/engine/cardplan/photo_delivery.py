"""模板内部图片交付；复用地址映射器，只读共享主题配置。"""

import json

from models.artifact import WidgetArtifact
from services.asset_url_mapper import AssetUrlMapper
from services.post_layout_theme_registry import load_theme_registry, registered_themes

PHOTO_BACKGROUND_ID = "__post_theme_base"


def photo_surface_style() -> dict:
    return load_theme_registry().get("photoSurfaceStyle", {})


def deliver_photo_source(source: str, theme_id: str) -> str:
    """编译完成后、返回源 DSL 前替换图片；失败由模板选择层恢复原主题。"""
    photo = next((item for item in registered_themes() if item.get("id") == theme_id), None)
    if photo is None:
        raise ValueError("Template photo theme is unavailable")
    src = photo.get("src")
    address = photo.get("remoteUrl") or src
    if not isinstance(src, str) or not isinstance(address, str):
        raise ValueError("Template photo delivery source is missing")
    return AssetUrlMapper({src: address}, {src}).rewrite_standard(source)


def register_photo_asset(artifact: WidgetArtifact) -> WidgetArtifact:
    """为已交付的模板图片登记编辑恢复信息；不转换图片或改变原始产物。"""
    if PHOTO_BACKGROUND_ID not in artifact.genui:
        return artifact
    sources = set()
    for line in artifact.genui.splitlines():
        record = json.loads(line)
        for node in record.get("updateComponents", {}).get("components", []):
            if node.get("id") == PHOTO_BACKGROUND_ID and node.get("component") == "Image":
                sources.add(node.get("src"))
    if not sources:
        return artifact
    matches = []
    for photo in registered_themes():
        if photo.get("remoteUrl", photo.get("src")) in sources:
            matches.append(photo)
    if len(sources) != 1 or len(matches) != 1:
        raise ValueError("Template photo delivery must reference one registered theme")
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


def is_delivered_photo_source(component_id: str, source: str) -> bool:
    """仅模板背景节点可使用当前已启用主题的精确交付地址。"""
    if component_id != PHOTO_BACKGROUND_ID:
        return False
    return any(source == item.get("remoteUrl") for item in registered_themes())
