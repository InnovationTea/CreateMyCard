"""静态内容的共享参考文字度量；不测量或猜测真实宿主尺寸。"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

_CONTRACT_PATH = (
    Path(__file__).resolve().parents[1]
    / "data/protocol_profiles/design-compact-dsl-fusion/runtime/static-content-v1.json"
)
_DATE = (
    r"\d{4}年\d{1,2}月(?:\d{1,2}日)?|\d{1,2}月\d{1,2}日|"
    r"\d{1,2}时\d{1,2}分(?:\d{1,2}秒)?|\d+分\d+秒"
)
_NUMBER = rf"(?:{_DATE}|\d+(?:[.,:/]\d+)*(?:年|月|日|号|时|分|秒)?)"
_UNIT = (
    r"(?:元(?:/[年月日人次])?|[%％℃]|°C|公里|千米|米|公斤|千克|毫升|分钟|小时|天|次|"
    r"[A-Za-z]+(?:/[A-Za-z]+)?)"
)
_TEXT_TOKEN = re.compile(
    r"[A-Za-z]+[A-Za-z0-9]*(?:\.[A-Za-z0-9]+)*(?:['’][A-Za-z]+)*"
    rf"|[$¥￥€]?[+-]?{_NUMBER}(?:[–—~至-]{_NUMBER})?(?:[ \t]?{_UNIT})?|.",
)


def critical_readings(text: str) -> tuple[str, ...]:
    """返回换行用的数值词元；不参与来源核验或重要性判断。"""
    values = []
    for match in _TEXT_TOKEN.finditer(text):
        token = match.group()
        if any(character.isdigit() for character in token):
            values.append(token)
    return tuple(values)


@lru_cache(maxsize=1)
def _contract() -> dict[str, Any]:
    payload = json.loads(_CONTRACT_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("version") != "static-content-v1":
        raise ValueError("静态内容合同版本无效。")
    for key in ("layout", "text", "components", "measurement", "typography", "lineBreak"):
        if not isinstance(payload.get(key), dict):
            raise ValueError(f"静态内容合同缺少 {key}。")
    _validate_contract_fields(payload)
    _validate_typography(payload)
    for name in ("noLineStart", "noLineEnd"):
        value = payload.get("lineBreak", {}).get(name)
        if not isinstance(value, str) or not value:
            raise ValueError("静态断行禁则必须为非空字符集。")
    return payload


def _validate_contract_fields(payload: dict[str, Any]) -> None:
    for name in (
        "header", "emphasis", "emphasisSecondary", "listPrimary", "listSecondary",
        "listValue", "singleText", "singleAssist", "comparisonPrimary", "comparisonSecondary",
        "detail", "singlePanelAssist", "listBadge",
    ):
        text_fields = payload.get("text", {}).get(name)
        if not isinstance(text_fields, dict):
            raise ValueError(f"静态文字规格缺少 {name}。")
        for key in ("fontSize", "lineHeight", "maxLines", "fontWeight"):
            if number(text_fields, key) <= 0:
                raise ValueError(f"静态文字规格 {name}.{key} 必须为正数。")
        if not number(text_fields, "maxLines").is_integer():
            raise ValueError(f"静态文字规格 {name}.maxLines 必须为整数。")
        if name in {"listPrimary", "listSecondary"}:
            if text_fields.get("textOverflow") != "ellipsis":
                raise ValueError(f"静态文字规格 {name}.textOverflow 必须为 ellipsis。")
        if name == "emphasisSecondary":
            if number(text_fields, "maxLines") != 3:
                raise ValueError("静态文字规格 emphasisSecondary.maxLines 必须为 3。")
            if text_fields.get("textOverflow") != "ellipsis":
                raise ValueError(
                    "静态文字规格 emphasisSecondary.textOverflow 必须为 ellipsis。"
                )
        if name == "comparisonSecondary":
            if text_fields.get("textOverflow") != "ellipsis":
                raise ValueError(
                    "静态文字规格 comparisonSecondary.textOverflow 必须为 ellipsis。"
                )
    required = {
        "StaticHeader": ("iconSize", "iconGap"),
        "EmphasisText": ("gap", "minimumSupportGap"),
        "SingleLineList": (
            "gap", "sideGap", "panelHeight", "panelPadding", "panelRadius", "wideInset",
        ),
        "TextList": ("innerGap", "sideGap", "twoItemGap", "threeItemGap",
                     "dividerWidth", "dividerAlpha", "badgePadding", "badgeGap", "badgeRadius",
                     "badgeAlpha"),
        "ComparisonGroup": (
            "minimumItems", "maximumItems", "gap", "padding", "innerGap",
            "fourItemGap", "fourItemHeight", "fourItemInnerGap", "radius",
        ),
    }
    for name, keys in required.items():
        component_fields = payload.get("components", {}).get(name)
        if not isinstance(component_fields, dict):
            raise ValueError(f"静态组件规格缺少 {name}。")
        for key in keys:
            number(component_fields, key)
        if name == "ComparisonGroup":
            if component_fields.get("fourItemTextOverflow") != "ellipsis":
                raise ValueError(
                    "静态组件规格 ComparisonGroup.fourItemTextOverflow 必须为 ellipsis。"
                )
    for key in ("padding", "gap", "radius"):
        number(payload.get("layout", {}), key)
    for key in ("asciiEm", "wideAsciiEm", "digitEm", "narrowAsciiEm", "wideEm", "safetyFactor"):
        if number(payload.get("measurement", {}), key) <= 0:
            raise ValueError(f"静态文字度量 {key} 必须为正数。")



def _validate_typography(payload: dict[str, Any]) -> None:
    typography = payload.get("typography", {})
    if typography:
        raise ValueError("静态字号由组件语义角色固定，不登记自由缩字档位。")



def static_content_contract() -> dict[str, Any]:
    return deepcopy(_contract())


def contract_section(name: str) -> dict[str, Any]:
    section = _contract().get(name)
    if not isinstance(section, dict):
        raise ValueError(f"静态内容合同缺少 {name}。")
    return deepcopy(section)


def text_spec(name: str, font_size: int = 12) -> dict[str, Any]:
    if isinstance(font_size, bool) or font_size != 12:
        raise ValueError("静态文字规格由组件角色固定，不接受自由字号档位。")
    spec = contract_section("text").get(name)
    if not isinstance(spec, dict):
        raise ValueError(f"静态文字规格未登记：{name}。")
    return spec


def component_spec(name: str) -> dict[str, Any]:
    spec = contract_section("components").get(name)
    if not isinstance(spec, dict):
        raise ValueError(f"静态组件规格未登记：{name}。")
    return spec


def number(spec: dict[str, Any], name: str) -> float:
    value = spec.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"静态合同 {name} 必须是数值。")
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"静态合同 {name} 必须是非负有限数值。")
    return float(value)


@dataclass(frozen=True)
class TextCapacity:
    lines: int
    height: float
    maximum_lines: int
    width: float
    wrapped_lines: tuple[str, ...]

    @property
    def fits(self) -> bool:
        return self.lines <= self.maximum_lines


def character_width(character: str, font: float) -> float:
    if unicodedata.combining(character):
        return 0.0
    metrics = _contract().get("measurement")
    if not isinstance(metrics, dict):
        raise ValueError("静态文字度量合同缺失。")
    metric = "wideEm"
    if character.isascii():
        metric = "asciiEm"
        if character in "MWmw@#%&":
            metric = "wideAsciiEm"
        elif character.isdigit():
            metric = "digitEm"
        elif character in " .,:;!/|ilI'`":
            metric = "narrowAsciiEm"
    em = number(metrics, metric)
    return font * em * number(metrics, "safetyFactor")


def text_width(text: str, font: float) -> float:
    maximum = 0.0
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        maximum = max(maximum, sum(character_width(character, font) for character in line))
    return maximum


def measure_text(text: str, width: float, spec: dict[str, Any]) -> TextCapacity:
    """按可读片段换行，关键读数不从中间拆开；超长英文按字符保留。"""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("静态文字必须为非空字符串。")
    if not math.isfinite(width) or width <= 0:
        raise ValueError("静态文字参考宽度未知或不足。")
    font = number(spec, "fontSize")
    maximum = int(number(spec, "maxLines"))
    line_height = number(spec, "lineHeight")
    wrapped: list[str] = []
    for paragraph in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        wrapped.extend(_wrap_paragraph(paragraph, width, font))
    lines = len(wrapped)
    return TextCapacity(lines, lines * line_height, maximum, width, tuple(wrapped))



def _protect_line_start(tokens: list[str], forbidden: str) -> list[str]:
    result: list[str] = []
    for token in tokens:
        if token and token[0] in forbidden and result:
            suffix = token
            while result and result[-1].isspace():
                suffix = result.pop() + suffix
            if result:
                result[-1] += suffix
            else:
                result.append(suffix)
        else:
            result.append(token)
    return result


def _wrap_paragraph(paragraph: str, width: float, font: float) -> list[str]:
    lines: list[str] = []
    current = ""
    occupied = 0.0
    rules = contract_section("lineBreak")
    tokens = [match.group() for match in _TEXT_TOKEN.finditer(paragraph)]
    tokens = _protect_line_start(tokens, rules.get("noLineStart", ""))
    no_line_end = rules.get("noLineEnd", "") + "-~～至–—"
    for token in tokens:
        extent = text_width(token, font)
        if extent > width + 1e-7:
            if any(character.isdigit() for character in token):
                raise ValueError(
                    f"COMPACT_STATIC_TEXT_CAPACITY: 关键读数 {token!r} 超过 {width:g}vp；"
                    "保持数值、日期时间和单位完整，改用更宽正文或列表，不能拆数字或缩字。"
                )
            pieces = _protect_line_start(list(token), rules.get("noLineStart", ""))
        else:
            pieces = [token]
        for piece in pieces:
            extent = text_width(piece, font)
            if extent > width + 1e-7:
                raise ValueError("COMPACT_STATIC_TEXT_CAPACITY: 静态文字单个字符超过参考文字区。")
            if occupied + extent > width + 1e-7:
                carry = ""
                if len(current) > 1 and current[-1] in no_line_end:
                    carry = current[-1]
                    current = current[:-1]
                lines.append(current)
                current = carry
                occupied = text_width(carry, font)
                if occupied + extent > width + 1e-7:
                    raise ValueError(
                        "COMPACT_STATIC_TEXT_CAPACITY: 完整片段与分隔符超宽，请改用更宽正文。"
                    )
            current += piece
            occupied += extent
    lines.append(current)
    return lines


def static_capacity_prompt(size: str) -> str:
    """Plan 首次提交前给出与 Runtime 一致的组件容量预算。"""
    comparison = (
        "ComparisonGroup仅2x4可用：带标题2–3项，四个对象改选可带标题的合法结构。"
        if size == "2x4"
        else "ComparisonGroup在2x2不可用。"
    )
    return (
        "# 首次Plan组件容量预算\n"
        f"当前尺寸 {size}。提交Plan前先按信息形态选组件，再核对标题和正文项数；"
        "不得用“最多5个object组”代替具体组件容量。\n"
        "只有三条TextList可以无标题；其它正文形态均须有简短主题标题，不为标题删减必要记录。\n"
        "- TextList/records：带标题只能2项，无标题只能3项；适合对象名加说明、状态或多个限定。\n"
        "- SingleLineList/rows：必须带标题，正文1–5行；仅适合可完整单行读取的短标签加短值。\n"
        f"- {comparison}\n"
        "- EmphasisText/content：必须带标题，只承载1个核心对象或结论；mainText最多2行，"
        "secondaryText与bottomText各最多3行，并共同满足剩余高度。\n"
        "shared/title使用标题区；shared/body虽不计入object组数，仍必须放入所选正文组件的合法字段与高度。"
        "如果实际占用超出上限，首次Plan即先不选should，必要时省略完整低优先级对象并记录omittedContents。"
        "字体、行高及间距由Runtime固定，文字宽度和完整性校验仍作为后续安全兜底。\n"
    )
