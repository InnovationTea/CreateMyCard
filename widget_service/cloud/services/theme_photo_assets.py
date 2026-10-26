"""按定稿前景实际使用的资源执行统一图片排除，不读取素材候选或猜测图标名称。"""

from services.card_validation.base import read_pointer
from services.display_text import current_display_text


def excluded_foreground_assets(
    nodes: list[dict], excluded: list[str], url_mapping: dict, data_model: dict | None,
) -> list[dict]:
    """识别root可达Image；资源键与已配置交付URL视为同一资源。"""
    sources = {asset: asset for asset in excluded}
    for asset in excluded:
        url = url_mapping.get(asset)
        if isinstance(url, str) and url:
            sources[url] = asset
    if not sources:
        return []
    by_id = {node.get("id"): node for node in nodes}
    pending = ["root"]
    visited = set()
    matches = []

    def lookup(path: str):
        _, value = read_pointer(data_model, path)
        return value

    while pending:
        identity = pending.pop()
        if identity in visited:
            continue
        visited.add(identity)
        node = by_id.get(identity, {})
        children = node.get("children", [])
        if isinstance(children, list):
            pending.extend(child for child in reversed(children) if isinstance(child, str))
        if node.get("component") != "Image":
            continue
        value = node.get("src")
        if isinstance(value, dict):
            value = lookup(value.get("path"))
        src = current_display_text(value, lookup)
        asset = sources.get(src)
        if asset:
            matches.append({"componentId": identity, "asset": asset})
    return matches
