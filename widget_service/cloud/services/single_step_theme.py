"""250新建展开结果到公共主题的交接；不参与编辑或融合布局。"""

import copy
import json

from services.fusion_ball_expander import (
    build_fusion_ball_content_id,
    expand_fusion_ball_components,
    fusion_ball_palette_for_root,
)
from services.post_layout_theme import FUSION_IDS, components, decode, encode
from services.theme_content_regions import capsule_ids
from services.theme_style_roles import (
    COLOR_FIELDS,
    layout_phase,
    native_asset,
    property_role,
    role,
)

_BACKGROUND_KEYS = {"linearGradient", "backgroundImage", "backgroundImageSizeWithStyle"}
_WHITE_PANELS = {"#CCFFFFFF", "#99FFFFFF", "#33FFFFFF"}


def _remove_generated_background(nodes: list[dict], source: str, task: dict) -> None:
    """仅移除原转换器按有效根Design Token生成、与标准展开逐项相同的背景。"""
    roots = []
    for line in source.splitlines():
        row = json.loads(line)
        if isinstance(row, list) and len(row) >= 3 and row[0] == "root":
            roots.append({"component_id": "root", "component_type": row[1], "props": row[2]})
    palette = fusion_ball_palette_for_root(
        roots, size=task.get("size"), app_version=task.get("appVersion"),
    )
    if palette is None:
        return
    expected = expand_fusion_ball_components(
        [{"id": "root", "component": "Column", "children": [], "styles": {}}],
        palette, size=task.get("size"),
    )
    removable = FUSION_IDS | {"root"}
    generated = [node for node in nodes if node.get("id") in removable]
    expected_generated = [node for node in expected if node.get("id") in removable]
    if generated != expected_generated:
        raise ValueError("250 generated background does not match its registered expansion")
    content_id = build_fusion_ball_content_id("root")
    foreground = [node for node in nodes if node.get("id") == content_id]
    if len(foreground) != 1:
        raise ValueError("250 generated background requires exactly one foreground")
    retained = [node for node in nodes if node.get("id") not in removable]
    for node in retained:
        if any(child in removable for child in node.get("children", [])):
            raise ValueError("250 foreground must not reference generated background nodes")
    foreground[0]["id"] = "root"
    nodes[:] = retained


def prepare_single_step_theme(standard: str, source: str, task: dict) -> str:
    """保留250已展开的前景结构、字号、绑定和动作，只交接颜色及已知背景。"""
    records = decode(standard)
    nodes = components(records)
    _remove_generated_background(nodes, source, task)
    capsules = set(capsule_ids(nodes))
    with layout_phase(task=task):
        for node in nodes:
            styles = node.get("styles")
            if not isinstance(styles, dict):
                continue
            original = copy.deepcopy(styles)
            is_root = node.get("id") == "root"
            for key, value in original.items():
                if key in _BACKGROUND_KEYS:
                    if not is_root and key == "backgroundImage":
                        raise ValueError("250 non-root background image needs a theme role")
                    styles.pop(key, None)
                    if not is_root and key == "linearGradient":
                        styles["backgroundColor"] = role("componentSecondary")
                    continue
                if key not in COLOR_FIELDS:
                    continue
                if is_root and key == "backgroundColor":
                    styles.pop(key, None)
                elif key == "fillColor" and native_asset(node.get("src")):
                    styles.pop(key, None)
                elif key == "backgroundColor" and isinstance(value, str) and value in _WHITE_PANELS:
                    is_panel = node.get("id") not in capsules and node.get("component") != "Button"
                    styles[key] = role("panel" if is_panel else "componentSecondary")
                else:
                    styles[key] = property_role(key, value)
    return encode(records)
