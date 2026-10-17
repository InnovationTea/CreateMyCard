"""从现有胶囊展开合同识别主题避让例外，不修改组件结构。"""

from __future__ import annotations

import math


def capsule_ids(nodes: list[dict]) -> list[str]:
    result = []
    for node in nodes:
        if node.get("component") not in {"Button", "Row"} or not node.get("onClick"):
            continue
        styles = node.get("styles", {})
        height, radius = styles.get("height"), styles.get("borderRadius")
        if not isinstance(height, (int, float)) or not isinstance(radius, (int, float)):
            continue
        if not math.isfinite(height) or height <= 0 or not math.isfinite(radius):
            continue
        if radius < height / 2:
            continue
        width = styles.get("width")
        if isinstance(width, (int, float)) and width <= height:
            continue
        identity = node.get("id")
        if isinstance(identity, str):
            result.append(identity)
    return result
