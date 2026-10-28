"""静态展示文字与对象组的局部覆盖；不复制几何或事件校验。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_DISPLAY_SEPARATORS = str.maketrans({char: " " for char in "，,；;：:。·、|｜"})


def _token_edge(char: str) -> bool:
    return (char.isascii() and char.isalnum()) or char in "._+-−–—"


def _contains_fragment(fragment: str, visible: str) -> bool:
    """字面片段可带字段标签，但不得借用更长ASCII词元或数字的一部分。"""
    start = 0
    while fragment:
        position = visible.find(fragment, start)
        if position < 0:
            break
        end = position + len(fragment)
        left_ok = position == 0 or not (
            _token_edge(fragment[0]) and _token_edge(visible[position - 1])
        )
        right_ok = end == len(visible) or not (
            _token_edge(fragment[-1]) and _token_edge(visible[end])
        )
        if left_ok and right_ok:
            return True
        start = position + 1
    return False


def _joined_fields(parts: list[str]) -> str:
    result = ""
    for part in parts:
        if result and part:
            adjacent_token_edges = _token_edge(result[-1]) and _token_edge(part[0])
            if adjacent_token_edges:
                result += "\x00"  # 不把3、0或数值、单位跨字段拼成新的ASCII词元。
        result += part
    return result


def display_text(value: Any) -> str:
    """仅规范显式换行，保留大小写、标点、空白、单位与否定词。"""
    return value.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "")


def _strings(value: Any) -> list[str]:
    result: list[str] = []
    if isinstance(value, str):
        result.append(value)
    elif isinstance(value, list):
        for child in value:
            result.extend(_strings(child))
    elif isinstance(value, dict):
        for child in value.values():
            result.extend(_strings(child))
    return result


def _covered(text: str, parts: list[str]) -> bool:
    expected = _comparison_text(text)
    if not expected:
        return False
    visible = [_comparison_text(part) for part in parts]
    if any(_contains_fragment(expected, part) for part in visible):
        return True
    if _contains_fragment(expected, _joined_fields(visible)):
        return True
    # 只拆Plan本来就声明的排版分隔，不从原文或query提取语义词。
    fragments = text.translate(_DISPLAY_SEPARATORS).split()
    if len(fragments) < 2:
        return _reordered_fields_covered(expected, visible)
    for fragment in fragments:
        literal = _comparison_text(fragment)
        if not any(_contains_fragment(literal, part) for part in visible):
            return False
    return True



def _reordered_fields_covered(expected: str, visible: list[str]) -> bool:
    """允许完整字段换序，不使用单字、数字碎片或全局字符集合拼凑覆盖。"""
    covered: set[int] = set()
    for part in visible:
        if len(part) < 2:
            continue
        start = 0
        while part:
            position = expected.find(part, start)
            if position < 0:
                break
            end = position + len(part)
            left_ok = position == 0 or not (
                _token_edge(part[0]) and _token_edge(expected[position - 1])
            )
            right_ok = end == len(expected) or not (
                _token_edge(part[-1]) and _token_edge(expected[end])
            )
            if left_ok and right_ok:
                covered.update(range(position, end))
            start = position + 1
    return len(covered) == len(expected)


def _comparison_text(text: str) -> str:
    # 仅规范排版分隔；相邻ASCII词元保留边界，不把独立英文词或读数粘连。
    result = ""
    separated = False
    for character in text:
        if character.isspace() or character in "，,；;：:。·、|｜":
            separated = True
            continue
        if separated and result:
            if _token_edge(result[-1]) and _token_edge(character):
                result += " "
        result += character
        separated = False
    return result



def _identity_covered(identity: str, parts: list[str]) -> bool:
    expected = _comparison_text(identity)
    return any(_contains_fragment(expected, _comparison_text(part)) for part in parts)


def _fact_covered(fact: dict[str, Any], parts: list[str]) -> bool:
    text = fact.get("text")
    if not isinstance(text, str):
        return False
    if fact.get("preserveVerbatim"):
        expected = display_text(text)
        return expected in display_text("".join(parts))
    # 比较已接受的模型展示版本，不从原文识别数字、条件或语义片段。
    # 允许同对象按排版标点拆字段；摘要和省略须在 Plan 中完成。
    return _covered(text, parts)


def _optional(fact: dict[str, Any]) -> bool:
    return fact.get("priority") == "should" and not (
        fact.get("protectedTexts") or fact.get("preserveVerbatim")
    )


@dataclass(frozen=True)
class StaticDisplayGroup:
    component_id: str
    parts: list[str]


@dataclass(frozen=True)
class StaticFactCoverage:
    fact_index: int
    component_id: str | None
    visible: bool



def _attribute_parts(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return []
    return _strings(value.get("label")) + _strings(value.get("value"))


def static_display_groups(
    source: str, *, attribute_objects: bool = False
) -> tuple[list[StaticDisplayGroup], list[StaticDisplayGroup]]:
    """从可达的语义树读取对象顺序；标题和共享说明不计为正文对象。"""
    from services.compact_dsl_a2ui_converter import ComponentRow, parse_compact_dsl_rows

    objects: list[StaticDisplayGroup] = []
    shared: list[StaticDisplayGroup] = []
    for row in parse_compact_dsl_rows(source, expand_layouts=False):
        if not isinstance(row, ComponentRow):
            continue
        if row.component_type == "EmphasisText":
            parts = _strings(row.props.get("mainText")) + _strings(row.props.get("secondaryText"))
            objects.append(StaticDisplayGroup(row.component_id, parts))
        elif row.component_type in {"TextList", "SingleLineList", "ComparisonGroup"}:
            items = row.props.get("items")
            if not isinstance(items, list):
                continue
            keys = ("primaryText", "secondaryText", "value")
            if row.component_type == "ComparisonGroup":
                keys = ("primaryText", "secondaryText", "details")
            elif row.component_type == "SingleLineList":
                keys = ("text", "assist")
            for item in items:
                parts = []
                if isinstance(item, dict):
                    for key in keys:
                        parts.extend(_strings(item.get(key)))
                objects.append(StaticDisplayGroup(row.component_id, parts))
        elif row.component_id in {"header", "note"} or row.component_type in {
            "SingleLineTitle",
            "DoubleLineTitle",
            "SecondaryBody",
        }:
            parts = []
            for key in ("title", "items"):
                parts.extend(_strings(row.props.get(key)))
            shared.append(StaticDisplayGroup(row.component_id, parts))
    return objects, shared


def static_fact_coverage(
    source: str, plan: dict[str, Any], allowed_indexes: tuple[int, ...] = ()
) -> list[StaticFactCoverage]:
    """按组报告事实实际可见性，省略反馈和最小删减共用本规则。"""
    object_count = sum(group.get("kind") == "object" for group in plan.get("contentGroups", []))
    objects, shared = static_display_groups(source, attribute_objects=object_count > 1)
    heading = []
    for display in shared:
        if display.component_id == "header":
            heading.extend(display.parts)
    facts = plan.get("info_required", [])
    result = []
    object_position = 0
    allowed = set(allowed_indexes)
    for group in plan.get("contentGroups", []):
        indexes = group.get("factIndexes", [])
        if indexes and all(index in allowed for index in indexes):
            for index in indexes:
                result.append(StaticFactCoverage(index, None, False))
            continue
        displays = shared
        if group.get("kind") == "object":
            displays = []
            if object_position < len(objects):
                candidate = objects[object_position]
                required = [index for index in indexes if not _optional(facts[index])]
                matched = any(_fact_covered(facts[index], candidate.parts) for index in indexes)
                if required or matched:
                    displays = [candidate]
                    object_position += 1
        for index in indexes:
            fact = facts[index]
            text = fact.get("text")
            match = None
            if isinstance(text, str):
                for display in displays:
                    if _fact_covered(fact, display.parts):
                        match = display
                        break
                    eligible_heading = (
                        fact.get("displayRole") == "title" or text == group.get("identity")
                    )
                    if object_count == 1 and eligible_heading and _fact_covered(fact, heading):
                        match = StaticDisplayGroup("header", heading)
                        break
            result.append(
                StaticFactCoverage(index, match.component_id if match else None, match is not None)
            )
    return result


def static_group_errors(
    source: str, plan: dict[str, Any] | None, allowed_indexes: tuple[int, ...] = ()
) -> list[str]:
    if not isinstance(plan, dict) or not isinstance(plan.get("contentGroups"), list):
        return ["COMPACT_STATIC_CONTEXT_MISSING: 静态内容缺少已接受的来源和分组合同。"]
    facts = plan.get("info_required")
    if not isinstance(facts, list):
        return ["静态展示计划缺少事实。"]
    allowed = set(allowed_indexes)
    for index in allowed:
        if not 0 <= index < len(facts):
            return ["静态省略授权越界。"]
        fact = facts[index]
        protected = fact.get("protectedTexts") or fact.get("preserveVerbatim")
        if protected:
            return ["COMPACT_STATIC_CORE_MISSING: 不能授权省略受保护原文。"]
    object_count = sum(group.get("kind") == "object" for group in plan.get("contentGroups", []))
    objects, shared_groups_display = static_display_groups(
        source, attribute_objects=object_count > 1
    )
    shared = []
    heading = []
    for group_display in shared_groups_display:
        shared.extend(group_display.parts)
        if group_display.component_id == "header":
            heading.extend(group_display.parts)
    object_groups = []
    shared_groups = []
    for group in plan.get("contentGroups", []):
        indexes = group.get("factIndexes", [])
        active = [index for index in indexes if index not in allowed]
        if not active:
            continue
        target = object_groups if group.get("kind") == "object" else shared_groups
        target.append((group.get("id"), active, group.get("identity")))
    errors = []
    required_count = sum(
        any(not _optional(facts[index]) for index in indexes) for _, indexes, _ in object_groups
    )
    if not required_count <= len(objects) <= len(object_groups):
        errors.append(
            "COMPACT_STATIC_GROUP_MISMATCH: "
            f"正文有{len(objects)}个对象，计划含{required_count}个核心组、"
            f"共{len(object_groups)}组；不能删除核心对象或以共享说明代替本条目。"
        )
    position = 0
    for identifier, indexes, identity in object_groups:
        parts = objects[position].parts if position < len(objects) else []
        required = any(not _optional(facts[index]) for index in indexes)
        matched = any(_fact_covered(facts[index], parts) for index in indexes)
        if not required and not matched:
            continue
        identity_parts = parts + heading if object_count == 1 else parts
        if isinstance(identity, str) and not _identity_covered(identity, identity_parts):
            errors.append(
                f"COMPACT_STATIC_CORE_MISSING: 组 {identifier} 缺少对象名称 {identity!r}；"
                "名称必须在本对象内可见，不能只保留无归属数值。"
            )
        for index in indexes:
            fact = facts[index]
            eligible_heading = fact.get("displayRole") == "title" or fact.get("text") == identity
            fact_parts = parts + heading if object_count == 1 and eligible_heading else parts
            errors.extend(_fact_errors(identifier, [index], facts, fact_parts))
        position += 1
    if position < len(objects):
        errors.append("COMPACT_STATIC_GROUP_MISMATCH: 正文存在未匹配计划的额外对象。")
    for identifier, indexes, _identity in shared_groups:
        errors.extend(_fact_errors(identifier, indexes, facts, shared))
    return errors


def collect_static_group_errors(
    source: str, plan: dict[str, Any] | None, errors: Any, allowed_indexes: tuple[int, ...] = ()
) -> None:
    from ..diagnostics import emit_error

    for message in static_group_errors(source, plan, allowed_indexes):
        emit_error(errors, _static_group_diagnostic(message, plan))


def _static_group_diagnostic(message: str, plan: dict[str, Any] | None):
    from ..diagnostics import CompactDiagnostic

    common = {
        "message": message,
        "legacy_message": message,
        "actual": {"contentGroups": (plan or {}).get("contentGroups")},
    }
    if message.startswith("COMPACT_STATIC_CONTEXT_MISSING:"):
        return CompactDiagnostic(
            code="COMPACT_STATIC_CONTEXT_MISSING",
            validation_class="semantic",
            category="cross_file",
            expected={"acceptedStaticContext": True},
            **common,
        )
    if message.startswith("COMPACT_STATIC_CORE_MISSING:"):
        return CompactDiagnostic(
            code="COMPACT_STATIC_CORE_MISSING",
            validation_class="semantic",
            category="display",
            expected={"sameObjectCoverage": True, "coreOmissionAllowed": False},
            **common,
        )
    if message.startswith("COMPACT_STATIC_PROTECTED_TEXT_CHANGED:"):
        return CompactDiagnostic(
            code="COMPACT_STATIC_PROTECTED_TEXT_CHANGED",
            validation_class="semantic",
            category="display",
            expected={"protectedTextUnchanged": True},
            **common,
        )
    return CompactDiagnostic(
        code="COMPACT_STATIC_GROUP_MISMATCH",
        validation_class="semantic",
        category="display",
        expected={"sameObjectCoverage": True, "objectOrderUnchanged": True},
        **common,
    )


def _fact_errors(
    identifier: Any, indexes: list[int], facts: list[dict[str, Any]], parts: list[str]
) -> list[str]:
    errors = []
    for index in indexes:
        fact = facts[index]
        text = fact.get("text")
        if _optional(fact) and not _fact_covered(fact, parts):
            continue
        if isinstance(text, str) and not _fact_covered(fact, parts):
            errors.append(
                f"COMPACT_STATIC_CORE_MISSING: 组 {identifier} 缺少完整展示文字 {text!r}；"
                "须在该对象或条目内恢复，不能从其它栏或note补足。"
            )
        for protected in fact.get("protectedTexts", []):
            if not _covered(protected, parts):
                errors.append(
                    f"COMPACT_STATIC_PROTECTED_TEXT_CHANGED: 组 {identifier} 保护文字改变。"
                )
    return errors
