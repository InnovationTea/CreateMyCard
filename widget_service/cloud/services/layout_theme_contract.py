"""布局模型只处理内容与几何；颜色仅在末尾主题阶段展开。"""

from __future__ import annotations

import copy
import json
import re
from typing import Any


def uses_post_layout_theme(
    operation: str, *, template_source: bool = False, jsx_source: bool = False,
) -> bool:
    """共享处理器不代表同一路线；只有融合模型产物允许后置主题。"""
    return operation == "generateWidgetCardCompactDsl" and not (template_source or jsx_source)


COLOR_KEYS = frozenset(
    {
        "fontColor",
        "fillColor",
        "color",
        "backgroundColor",
        "linearGradient",
        "backgroundImage",
        "backgroundImageSizeWithStyle",
        "barColor",
        "trackColor",
        "dividerColor",
        "borderColor",
        "fusionBallColors",
        "baseColor",
    }
)
NEUTRAL_INSTRUCTION = """
# 布局阶段专用合同（优先于历史示例的颜色说明）
本阶段只生成原有通用规范下的内容与布局，不选择主题、不输出任何颜色值、渐变、
背景图或 fusion-ball Design Token。颜色由脚本提供。需要既有内容背板时使用
surfaceRole:"panel"，不能为主题新增背板。按钮底托由组件自动提供。
保留全部事实、动作及原有布局规范；用户颜色要求由末尾主题阶段处理。
不为图片预留空间，不改变常规组件选择。无需输出文字或图标颜色占位。
"""


def without_colors(value: Any) -> Any:
    if isinstance(value, list):
        return [without_colors(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    if "backgroundColor" in value or "linearGradient" in value:
        result["surfaceRole"] = "panel"
    for key, item in value.items():
        if key == "color" and item == "native":
            result[key] = item
            continue
        if key in COLOR_KEYS:
            continue
        if key == "design" and str(item).startswith("fusion-ball-"):
            continue
        result[key] = without_colors(item)
    return result


def strip_source_colors(source: str) -> str:
    from services.compact_dsl_a2ui_converter import parse_compact_dsl_rows
    from services.compact_high_level_components import ComponentRow

    rows = []
    for row in parse_compact_dsl_rows(source, expand_layouts=False):
        if isinstance(row, ComponentRow):
            props = without_colors(row.props)
            if row.component_id == "root":
                props.pop("surfaceRole", None)
            output = [row.component_id, row.component_type, props]
            if row.children:
                output.append(list(row.children))
        else:
            output = [row.path, row.value]
        rows.append(json.dumps(output, ensure_ascii=False, separators=(",", ":")))
    return "\n".join(rows)


def _clean_prompt_text(text: str) -> str:
    # 按已有稳定章节边界去除整块色板，而非删除含颜色的布局规则。
    text = re.sub(r"# 十二、表面与颜色.*?(?=\n# 十[三四]、|\Z)", "", text, flags=re.S)
    lines = []
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            lines.extend(_layout_prose(line))
            continue
        if isinstance(row, list) and len(row) >= 3 and isinstance(row[2], dict):
            row[2] = without_colors(row[2])
            if row[0] == "root":
                row[2].pop("surfaceRole", None)
            line = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
        lines.append(line)
    text = "\n".join(lines)
    # 行内历史示例不携带具体色值；最后的合同明确不输出这些属性。
    return re.sub(r"#[0-9A-Fa-f]{8}\b", "运行时配色", text)


def _layout_prose(line: str) -> list[str]:
    """移除模型颜色合同，保留同一行的尺寸、素材及结构条款。"""
    color_row = (
        r"\|\s*`(?:fontColor|fillColor|backgroundColor|color|barColor|trackColor|dividerColor)`"
    )
    if re.match(color_row, line):
        return []
    if line.startswith("- SVG 默认") or line.startswith("- 默认可染色 SVG"):
        return []
    if line.startswith("- 描述明确包含") or line.startswith("- `ProgressCircle`、带 icon"):
        return []
    if line.startswith("5. 按第十二节") or line.startswith("- 组件不声明文字颜色"):
        return []
    fields = r"`(?:borderColor|backgroundColor|backgroundImage|backgroundImageSizeWithStyle)`、?"
    line = re.sub(fields, "", line)
    clauses = re.split(r"(?<=[；。])", line)
    kept = []
    for clause in clauses:
        if re.search("配色|色板|背景按第十二节|融球是否满足|融球优先级|颜色基准|自由取色", clause):
            continue
        kept.append(clause)
    cleaned = "".join(kept)
    return [cleaned] if cleaned.strip() else []


def _clean_payload(value: Any, key: str = "") -> Any:
    if isinstance(value, dict):
        return {name: _clean_payload(item, name) for name, item in value.items()}
    if isinstance(value, list):
        return [_clean_payload(item, key) for item in value]
    if isinstance(value, str) and key in {"invalidSourceDsl", "sourceDsl", "previousGenui"}:
        try:
            return strip_source_colors(value)
        except ValueError:
            return value
    return value


def layout_only_prompt(
    prompt: list[dict[str, str]],
    *,
    planning: bool = False,
) -> list[dict[str, str]]:
    result = copy.deepcopy(prompt)
    for message in result:
        content = message.get("content", "")
        if message.get("role") == "system":
            instruction = (
                "\n颜色和主题由后置脚本处理，本阶段只规划信息及布局。"
                if planning
                else NEUTRAL_INSTRUCTION
            )
            message["content"] = _clean_prompt_text(content) + instruction
        else:
            try:
                payload = json.loads(content)
            except json.JSONDecodeError:
                continue
            message["content"] = json.dumps(_clean_payload(payload), ensure_ascii=False)
    return result
