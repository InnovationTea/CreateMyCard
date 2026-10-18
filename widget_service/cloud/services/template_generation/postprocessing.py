"""模板编译结果的资源着色后处理。"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlsplit

_BITMAP_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")


def remove_bitmap_fill_colors(a2ui: str) -> str:
    """遍历模板组件，移除 位图 Image 染色；保留 SVG、数据和其它节点属性。"""
    messages = [json.loads(line) for line in a2ui.splitlines() if line.strip()]
    changed = False
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
            if not urlsplit(source).path.lower().endswith(_BITMAP_SUFFIXES):
                continue
            styles = node.get("styles")
            for properties in (node, styles):
                if isinstance(properties, dict) and "fillColor" in properties:
                    properties.pop("fillColor")
                    changed = True
    result = a2ui
    if changed:
        result = "\n".join(json.dumps(message, ensure_ascii=False) for message in messages)
    return result
