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
    item_index: int | None = None
    property_parts: tuple[tuple[str, tuple[str, ...]], ...] = ()


@dataclass(frozen=True)
class StaticFactCoverage:
    """归组覆盖与保守存在性分开；text_present仅用于阻止恢复阶段误排除。"""

    fact_index: int
    component_id: str | None
    visible: bool
    text_present: bool = False


@dataclass(frozen=True)
class StaticDisplayMapping:
    objects: dict[int, list[StaticDisplayGroup]]
    shared: list[StaticDisplayGroup]
    heading: list[str]
    unmatched: list[StaticDisplayGroup]


def _group_facts(group: dict[str, Any], facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for index in group.get("factIndexes", []):
        if not isinstance(index, int) or isinstance(index, bool):
            raise ValueError("已接受的静态分组包含无效事实索引。")
        if not 0 <= index < len(facts):
            raise ValueError("已接受的静态分组包含无效事实索引。")
        result.append(facts[index])
    return result


def _shared_only(
    display: StaticDisplayGroup, shared_facts: list[dict[str, Any]],
    object_facts: list[dict[str, Any]],
) -> bool:
    if any(_fact_covered(fact, display.parts) for fact in object_facts):
        return False
    if not any(_fact_covered(fact, display.parts) for fact in shared_facts):
        return False
    # 整条说明必须可由已声明的公共事实解释，不能吞掉带未知正文的额外条目。
    return _parts_explained(display, shared_facts)


def _parts_explained(
    display: StaticDisplayGroup, facts: list[dict[str, Any]], identity: str | None = None,
) -> bool:
    texts = []
    for fact in facts:
        text = fact.get("text")
        if isinstance(text, str) and _fact_covered(fact, display.parts):
            texts.append(_comparison_text(text))
    if isinstance(identity, str):
        texts.append(_comparison_text(identity))
    for part in display.parts:
        expected = _comparison_text(part)
        if any(_contains_fragment(expected, text) for text in texts):
            continue
        if not _reordered_fields_covered(expected, texts):
            return False
    return bool(display.parts)


def _extends_object(
    current: list[StaticDisplayGroup], display: StaticDisplayGroup,
    own_facts: list[dict[str, Any]], shared_facts: list[dict[str, Any]], identity: str | None,
) -> bool:
    if not any(_matching_display(fact, current) for fact in own_facts):
        return False
    if not _parts_explained(display, own_facts + shared_facts, identity):
        return False
    for fact in own_facts:
        if not _matching_display(fact, current) and _fact_covered(fact, display.parts):
            return True
    return False


def _display_mapping(
    source: str, plan: dict[str, Any], allowed: set[int],
) -> StaticDisplayMapping:
    """同一份顺序映射供核心校验和省略账本使用，不改动语义树。"""
    facts = plan.get("info_required", [])
    groups = []
    object_facts = []
    shared_facts = []
    for group in plan.get("contentGroups", []):
        active = dict(group)
        indexes = group.get("factIndexes", [])
        active["factIndexes"] = [index for index in indexes if index not in allowed]
        groups.append(active)
        target = object_facts if group.get("kind") == "object" else shared_facts
        target.extend(_group_facts(group, facts))
    displays, shared = static_display_groups(source)
    heading = []
    for display in shared:
        if display.component_id == "header":
            heading.extend(display.parts)
    objects = []
    for display in displays:
        if not _shared_only(display, shared_facts, object_facts):
            objects.append(display)
    object_count = sum(group.get("kind") == "object" for group in groups)
    mapped = {}
    position = 0
    for group_index, group in enumerate(groups):
        if group.get("kind") != "object":
            continue
        if position >= len(objects):
            break
        candidate = objects[position]
        if not group.get("factIndexes"):
            original = plan.get("contentGroups", [])[group_index]
            original_facts = _group_facts(original, facts)
            identity = original.get("identity")
            identity_matches = not isinstance(identity, str) or _identity_covered(
                identity, candidate.parts,
            )
            if identity_matches and _parts_explained(candidate, original_facts, identity):
                mapped[group_index] = [candidate]
                position += 1
            continue
        own_facts = _group_facts(group, facts)
        required = any(not _optional(fact) for fact in own_facts)
        matched = any(_fact_covered(fact, candidate.parts) for fact in own_facts)
        if not required and not matched:
            continue
        identity = group.get("identity")
        current = [candidate]
        position += 1
        while object_count == 1 and position < len(objects):
            following = objects[position]
            if not _extends_object(current, following, own_facts, shared_facts, identity):
                break
            current.append(following)
            position += 1
        mapped[group_index] = current
    # 公共说明逐条核对，不把不同对象的零散字段拼成新的公共事实。
    return StaticDisplayMapping(mapped, shared + displays, heading, objects[position:])


def _matching_display(
    fact: dict[str, Any], displays: list[StaticDisplayGroup],
) -> StaticDisplayGroup | None:
    return next((display for display in displays if _fact_covered(fact, display.parts)), None)



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
            properties = tuple(
                (key, tuple(_strings(row.props.get(key))))
                for key in ("mainText", "secondaryText")
            )
            objects.append(StaticDisplayGroup(row.component_id, parts, property_parts=properties))
        elif row.component_type in {"TextList", "SingleLineList", "ComparisonGroup"}:
            items = row.props.get("items")
            if not isinstance(items, list):
                continue
            keys = ("primaryText", "secondaryText", "value")
            if row.component_type == "ComparisonGroup":
                keys = ("primaryText", "secondaryText", "details")
            elif row.component_type == "SingleLineList":
                keys = ("text", "assist")
            for item_index, item in enumerate(items):
                parts = []
                properties = []
                if isinstance(item, dict):
                    for key in keys:
                        values = _strings(item.get(key))
                        parts.extend(values)
                        properties.append((key, tuple(values)))
                objects.append(
                    StaticDisplayGroup(row.component_id, parts, item_index, tuple(properties))
                )
        elif row.component_id in {"header", "note"} or row.component_type in {
            "SingleLineTitle",
            "DoubleLineTitle",
            "SecondaryBody",
        }:
            parts = []
            for key in ("title", "items"):
                parts.extend(_strings(row.props.get(key)))
            properties = tuple(
                (key, tuple(_strings(row.props.get(key)))) for key in ("title", "items")
            )
            shared.append(StaticDisplayGroup(row.component_id, parts, property_parts=properties))
    return objects, shared


def static_fact_coverage(
    source: str, plan: dict[str, Any], allowed_indexes: tuple[int, ...] = ()
) -> list[StaticFactCoverage]:
    """按组报告事实实际可见性，省略反馈和最小删减共用本规则。"""
    object_count = sum(group.get("kind") == "object" for group in plan.get("contentGroups", []))
    mapping = _display_mapping(source, plan, set(allowed_indexes))
    heading = mapping.heading
    facts = plan.get("info_required", [])
    result = []
    for group_index, group in enumerate(plan.get("contentGroups", [])):
        indexes = group.get("factIndexes", [])
        displays = mapping.shared
        if group.get("kind") == "object":
            displays = mapping.objects.get(group_index, [])
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
            text_present = match is not None or _matching_display(fact, mapping.shared) is not None
            result.append(
                StaticFactCoverage(
                    index, match.component_id if match else None, match is not None,
                    text_present=text_present,
                )
            )
    return result


def static_capacity_fact_indexes(
    source: str, plan: dict[str, Any], component_id: str, item_index: int | None,
    property_name: str | None, allowed_indexes: tuple[int, ...] = (),
) -> tuple[int, ...]:
    """把当前容量字段映射到所属组的完整事实，不跨对象搜词或推断语义。"""
    mapping = _display_mapping(source, plan, set(allowed_indexes))
    facts = plan.get("info_required", [])
    matches: list[int] = []
    owners = 0
    for group_index, group in enumerate(plan.get("contentGroups", [])):
        displays = mapping.shared
        if group.get("kind") == "object":
            displays = mapping.objects.get(group_index, [])
        targets = []
        for display in displays:
            if display.component_id == component_id and display.item_index == item_index:
                targets.append(display)
        if len(targets) != 1:
            continue
        target = targets[0]
        identity = group.get("identity")
        if isinstance(identity, str) and not _identity_covered(identity, target.parts):
            continue
        values = target.parts
        if property_name is not None:
            values = []
            for key, parts in target.property_parts:
                if key == property_name:
                    values.extend(parts)
        own_indexes = []
        for index in group.get("factIndexes", []):
            if index not in allowed_indexes:
                own_indexes.append(index)
        current = []
        for index in own_indexes:
            fact = facts[index]
            if not _fact_covered(fact, target.parts):
                continue
            complete_field = _fact_covered(fact, values)
            unique_whole_fact = len(own_indexes) == 1 and _parts_explained(target, [fact], identity)
            if values and (complete_field or unique_whole_fact):
                current.append(index)
        if current:
            owners += 1
            matches.extend(current)
    return tuple(matches) if owners == 1 else ()


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
    mapping = _display_mapping(source, plan, allowed)
    heading = mapping.heading
    object_groups = []
    shared_groups = []
    for group_index, group in enumerate(plan.get("contentGroups", [])):
        indexes = group.get("factIndexes", [])
        active = [index for index in indexes if index not in allowed]
        if not active:
            continue
        target = object_groups if group.get("kind") == "object" else shared_groups
        target.append((group_index, group.get("id"), active, group.get("identity")))
    errors = []
    required_count = sum(
        any(not _optional(facts[index]) for index in indexes) for _, _, indexes, _ in object_groups
    )
    active_group_indexes = {index for index, _identifier, _facts, _identity in object_groups}
    display_count = sum(index in active_group_indexes for index in mapping.objects)
    display_count += len(mapping.unmatched)
    if not required_count <= display_count <= len(object_groups):
        errors.append(
            "COMPACT_STATIC_GROUP_MISMATCH: "
            f"正文有{display_count}个对象，计划含{required_count}个核心组、"
            f"共{len(object_groups)}组；不能删除核心对象或以共享说明代替本条目。"
        )
    for group_index, identifier, indexes, identity in object_groups:
        displays = mapping.objects.get(group_index, [])
        parts = []
        for display in displays:
            parts.extend(display.parts)
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
            display = _matching_display(fact, displays)
            fact_parts = display.parts if display else []
            if object_count == 1 and eligible_heading:
                if _fact_covered(fact, heading):
                    fact_parts = heading
            errors.extend(_fact_errors(identifier, [index], facts, fact_parts))
    if mapping.unmatched:
        errors.append("COMPACT_STATIC_GROUP_MISMATCH: 正文存在未匹配计划的额外对象。")
    for _group_index, identifier, indexes, _identity in shared_groups:
        for index in indexes:
            display = _matching_display(facts[index], mapping.shared)
            parts = display.parts if display else []
            errors.extend(_fact_errors(identifier, [index], facts, parts, shared=True))
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
    identifier: Any, indexes: list[int], facts: list[dict[str, Any]], parts: list[str],
    *, shared: bool = False,
) -> list[str]:
    errors = []
    location = "须在该对象或条目内恢复，不能从其它栏或note补足。"
    if shared:
        location = "须在合法且可达的标题或正文条目内完整展示，不跨不同对象拼接说明。"
    for index in indexes:
        fact = facts[index]
        text = fact.get("text")
        if _optional(fact) and not _fact_covered(fact, parts):
            continue
        if isinstance(text, str) and not _fact_covered(fact, parts):
            errors.append(
                f"COMPACT_STATIC_CORE_MISSING: 组 {identifier} 缺少完整展示文字 {text!r}；"
                + location
            )
        for protected in fact.get("protectedTexts", []):
            if not _covered(protected, parts):
                errors.append(
                    f"COMPACT_STATIC_PROTECTED_TEXT_CHANGED: 组 {identifier} 保护文字改变。"
                )
    return errors
