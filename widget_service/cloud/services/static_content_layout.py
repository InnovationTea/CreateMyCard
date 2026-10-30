"""静态正文的固定外框策略；模型字段不包含样式和几何。"""

from typing import Any

from services.static_text_capacity import component_spec, contract_section, number


def has_single_line_panels(kind: str, props: dict[str, Any]) -> bool:
    items = props.get("items")
    return kind == "SingleLineList" and isinstance(items, list) and 1 <= len(items) <= 3


def stretches_static_body(kind: str, props: dict[str, Any]) -> bool:
    if kind == "EmphasisText":
        return True
    items = props.get("items")
    return has_single_line_panels(kind, props) and len(items) == 3


def static_body_inset(kind: str, props: dict[str, Any], size: str) -> float:
    if size == "2x4" and has_single_line_panels(kind, props):
        return number(component_spec("SingleLineList"), "wideInset")
    return number(contract_section("layout"), "padding")
