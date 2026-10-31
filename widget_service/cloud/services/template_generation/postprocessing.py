"""模板编译结果的资源着色后处理。"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit

from app.logger import logger

_BITMAP_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
# 能力清单尚无结构化染色标志，仅识别正式说明的明确约束，不推断图标配色。
_NATIVE_COLOR_DESCRIPTION = re.compile(
    r"保留原色|禁止染色|不可染色|(?:禁止|不可|不允许)\s*(?:使用\s*)?fillColor",
    re.IGNORECASE,
)


def _native_color_sources(asset_candidates: Sequence[Mapping[str, Any]]) -> set[str]:
    sources: set[str] = set()
    for asset in asset_candidates:
        source = asset.get("src")
        description = asset.get("description")
        if not isinstance(source, str) or not isinstance(description, str):
            continue
        if _NATIVE_COLOR_DESCRIPTION.search(description):
            sources.add(source)
    return sources


def remove_bitmap_fill_colors(a2ui: str) -> str:
    """遍历模板组件，移除 位图 Image 染色；保留 SVG、数据和其它节点属性。"""
    return remove_disallowed_image_fill_colors(a2ui)


def remove_disallowed_image_fill_colors(
    a2ui: str, asset_candidates: Sequence[Mapping[str, Any]] = (),
) -> str:
    """移除位图和素材声明禁染的 Image 颜色；保留数据、绑定及其它样式。"""
    native_sources = _native_color_sources(asset_candidates)
    messages = [json.loads(line) for line in a2ui.splitlines() if line.strip()]
    changed_images = 0
    removed_properties = 0
    for message in messages:
        update = message.get("updateComponents")
        if not isinstance(update, dict):
            continue
        components = update.get("components")
        if not isinstance(components, list):
            continue
        pending: list[Any] = list(components)
        while pending:
            node = pending.pop()
            if isinstance(node, list):
                pending.extend(node)
                continue
            if not isinstance(node, dict):
                continue
            pending.extend(node.values())
            source = node.get("src")
            if node.get("component") != "Image" or not isinstance(source, str):
                continue
            bitmap = urlsplit(source).path.lower().endswith(_BITMAP_SUFFIXES)
            if source not in native_sources and not bitmap:
                continue
            styles = node.get("styles")
            changed = False
            for properties in (node, styles):
                if isinstance(properties, dict) and "fillColor" in properties:
                    properties.pop("fillColor")
                    removed_properties += 1
                    changed = True
            if changed:
                changed_images += 1
    result = a2ui
    if changed_images:
        result = "\n".join(
            json.dumps(message, ensure_ascii=False, separators=(",", ":"))
            for message in messages
        )
    logger.info(
        "[Template Generation] image_fill_colors_postprocessed "
        f"native_source_count={len(native_sources)} changed_image_count={changed_images} "
        f"removed_property_count={removed_properties}"
    )
    return result
