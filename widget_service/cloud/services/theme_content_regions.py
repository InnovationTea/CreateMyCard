"""识别完整按钮占用区域；普通非交互容器不占用图片主体空间。"""

from __future__ import annotations


def button_ids(nodes: list[dict]) -> list[str]:
    result = []
    for node in nodes:
        if node.get("component") != "Button" and not node.get("onClick"):
            continue
        identity = node.get("id")
        # 整卡点击是画布事件，不将整个卡片误识别成按钮。
        if isinstance(identity, str) and identity != "root":
            result.append(identity)
    return result
