"""模板内部图片交付；复用地址映射器，只读共享主题配置。"""

from services.post_layout_theme_registry import load_theme_registry, registered_themes
from services.theme_photo_processing import deliver_photo_source as deliver_registered_photo
from services.theme_photo_processing import register_photo_asset as register_photo_asset

PHOTO_BACKGROUND_ID = "__post_theme_base"


def photo_surface_style() -> dict:
    return load_theme_registry().get("photoSurfaceStyle", {})


def deliver_photo_source(source: str, theme_id: str) -> str:
    """编译完成后、返回源 DSL 前替换图片；失败由模板选择层恢复原主题。"""
    photo = next((item for item in registered_themes() if item.get("id") == theme_id), None)
    if photo is None:
        raise ValueError("Template photo theme is unavailable")
    return deliver_registered_photo(source, photo)


def is_delivered_photo_source(component_id: str, source: str) -> bool:
    """仅模板背景节点可使用当前已启用主题的精确交付地址。"""
    if component_id != PHOTO_BACKGROUND_ID:
        return False
    return any(source == item.get("remoteUrl") for item in registered_themes())
