"""图片业务门禁复用共享归属；这里只维护抽象配色和节假日专属条件。"""

import re

from services.compact_dsl_a2ui_converter import ComponentRow
from services.compact_plan import _VISIBLE_PROP_NAMES, _compact_visible_state
from services.content_business import BusinessContext, VisibleBusinesses
from services.content_business import subtree as subtree
from services.display_text import concatenated_display_text
from services.post_layout_theme_registry import load_theme_registry


def visible_business(rows: list[ComponentRow]) -> str | None:
    return BusinessContext().visible(rows).single


def has_visible_business(rows: list[ComponentRow], business: str) -> bool:
    return business in BusinessContext().visible(rows).data_businesses


def first_visible_business(rows: list[ComponentRow]) -> str | None:
    return BusinessContext().visible(rows).first


def texture_business_reason(
    photo: dict, rows: list[ComponentRow], *, businesses: VisibleBusinesses | None = None,
) -> str | None:
    facts = businesses if businesses is not None else BusinessContext().visible(rows)
    business = facts.first
    mapped_families = set()
    # 停用某颜色的素材不代表删除其业务映射，不能因此改用其它颜色。
    for item in load_theme_registry().get("themes", []):
        if item.get("pool") != "texturePhotos":
            continue
        if business in item.get("contentEligibility", {}).get("businesses", []):
            mapped_families.add(item.get("family"))
    reason: str | None = None
    if mapped_families and photo.get("family") not in mapped_families:
        reason = "抽象图颜色与首个可见业务的配置不匹配"
    return reason


def _holiday_name(text: str) -> bool:
    other_countdown = re.search(
        r"生日|考试|纪念|旅行|出游|婚礼|面试|会议|马拉松|跑步|训练|赛事|比赛|"
        r"\b(?:birthday|exam|anniversary|meeting|wedding|trip|marathon|running|race)\b",
        text, re.I,
    )
    category = re.search(
        r"节|假期|假日|放假|休假|年假|寒假|暑假|调休|元旦|新年|中秋|国庆|"
        r"清明|端午|重阳|除夕|跨年|周末|周日|周天|星期日|星期天|"
        r"holiday|vacation|festival|weekend|sunday|christmas|new year", text, re.I,
    )
    return category is not None and other_countdown is None


def _display_strings(value: object, values: dict) -> list[str]:
    result = []
    if isinstance(value, str):
        resolved = concatenated_display_text(value, values.get)
        if resolved is not None:
            result.append(resolved)
    elif isinstance(value, dict):
        if set(value) == {"path"}:
            bound = values.get(value.get("path"))
            if isinstance(bound, str):
                result.append(bound)
        else:
            for child in value.values():
                result.extend(_display_strings(child, values))
    elif isinstance(value, list):
        for child in value:
            result.extend(_display_strings(child, values))
    return result


def holiday_countdown(
    rows: list[ComponentRow], values: dict, *, businesses: VisibleBusinesses | None = None,
) -> bool:
    """逐个可见倒计时确认节假日；一个节假日不能替其它未知/非节假日对象放行。"""
    facts = businesses if businesses is not None else BusinessContext().visible(rows)
    if facts.single != "countdown":
        return False
    by_id = {row.component_id: row for row in rows}
    names: dict[str, list[str]] = {}
    for path in _compact_visible_state(rows).paths:
        if path.startswith("/data/countdown/") and path.endswith("/countdownDays"):
            names[path.rsplit("/", 1)[0]] = []
    for row in rows:
        scoped = subtree(row.component_id, by_id)
        scoped = [item for item in scoped if not item.component_type.endswith("Button")]
        state = _compact_visible_state(scoped)
        prefixes = set()
        for path in state.paths:
            if path.startswith("/data/countdown/"):
                prefixes.add(path.rsplit("/", 1)[0])
        if len(prefixes) != 1:
            continue
        texts = names.get(next(iter(prefixes)))
        if texts is None:
            continue
        for item in scoped:
            for key, value in item.props.items():
                if key in _VISIBLE_PROP_NAMES:
                    texts.extend(_display_strings(value, values))
    return bool(names) and all(_holiday_name(" ".join(texts)) for texts in names.values())
