"""在修复请求边界组织 Compact 说明，不改写质量问题和修复记录。"""

from __future__ import annotations

import json
import math
import re
from typing import Any

from app.logger import logger

_TOP_BOTTOM_DETAILS_TRANSLATION = (
    "details 槽必须使用 TextBlock、TopTextBottomValue、SummaryList 或 EventCard"
)
_SEMANTIC_DETAIL_TRANSLATIONS = {
    "cyclic component reference": "组件引用形成循环",
    "component has multiple parents": "组件被多个父节点同时引用",
    "semantic tree nesting exceeds safe depth": "语义组件树嵌套超过安全深度",
    "missing component reference": "引用了不存在的组件",
    "generated component id collision": "生成的组件 ID 发生冲突",
    "title slot requires a title component or title-count Group": (
        "标题槽必须使用标题组件或 title-count Group"
    ),
    "content slot requires a business component or controlled Group": (
        "内容槽必须使用业务组件或受控 Group"
    ),
    "business component cannot have children": "业务组件不能声明 children",
    "unknown Group.variant": "Group.variant 未登记",
    "action fixed slot requires one complete CardButton": (
        "动作固定槽必须使用一个完整的 CardButton"
    ),
    "title-count starts with SingleLineTitle": (
        "title-count 的第一个子组件必须是 SingleLineTitle"
    ),
    "title-count ends with Badge": "title-count 的最后一个子组件必须是 Badge",
    "parent content area requires Region": "父级内容区必须使用 Region",
    "bottom action requires PillButton": "底部动作槽必须使用 PillButton",
    "optional bottom action requires PillButton": "可选底部动作槽必须使用 PillButton",
    "Action must occupy the selected Region bottom-action role": (
        "Action 必须放在所选 Region 的底部动作角色中"
    ),
    "InfoBlock belongs only in fixed slots, not Region or its Groups": (
        "InfoBlock 只能放在固定槽，不能进入 Region 或其 Group"
    ),
    "InfoBlock belongs only in fixed slots": "InfoBlock 只能放在固定槽",
    "ratio slot requires ProgressCircle": "比例槽必须使用 ProgressCircle",
    "DoubleLineTitle recipe has unknown reference height": (
        "DoubleLineTitle Recipe 缺少可确定的参考高度"
    ),
    "ratio slot has unknown reference dimensions": "比例槽缺少可确定的参考尺寸",
    "ratio slot has no positive reference capacity": "比例槽没有有效的正数容量",
    "unknown W-top-bottom variant": "W-top-bottom.variant 未登记",
    "W-top-bottom does not have shared button roles": "W-top-bottom 不提供共享按钮角色",
    "details slot requires TextBlock/TopTextBottomValue/SummaryList": (
        _TOP_BOTTOM_DETAILS_TRANSLATION
    ),
    "details slot requires TextBlock/TopTextBottomValue/SummaryList/EventCard": (
        _TOP_BOTTOM_DETAILS_TRANSLATION
    ),
    "fixed slot requires InfoBlock/CardButton or registered slot Group": (
        "固定槽必须使用 InfoBlock、CardButton 或已登记的槽位 Group"
    ),
    "semantic tree must start with Layout": "语义组件树的根节点必须是 Layout",
    "unknown Layout.layout": "Layout.layout 未登记",
    "unknown orientation": "orientation 未登记",
    "mixed fixed slots require InfoBlock above CardButton": (
        "混合固定槽必须将 InfoBlock 放在 CardButton 上方"
    ),
    "small title slot requires SingleLineTitle": "小卡标题槽必须使用 SingleLineTitle",
    "missing compiled slot": "缺少已展开的槽位",
    "small Group.variant must be a registered string": (
        "小卡 Group.variant 必须是已登记的字符串"
    ),
    "unknown small Group.variant": "小卡 Group.variant 未登记",
    "small Group contains only same-region read-only content": (
        "小卡 Group 只能包含同一区域内的只读内容"
    ),
    "choose a registered S-series Layout for size 2x2": (
        "2x2 必须选择已登记的 S 系列 Layout"
    ),
    "Actions must occupy the selected small layout action roles": (
        "Action 必须放在所选小卡布局的动作角色中"
    ),
    "InfoBlock requires a registered small fixed slot": (
        "InfoBlock 必须放在已登记的小卡固定槽"
    ),
    "S-center requires one complete DataDisplay": (
        "S-center 必须使用一个完整的 DataDisplay"
    ),
    "stacked-info requires two InfoBlock without visual": (
        "stacked-info 必须使用两个不含 visual 的 InfoBlock"
    ),
    "stacked-info requires InfoBlock.variant='stacked'": (
        "stacked-info 要求 InfoBlock.variant='stacked'"
    ),
    "two InfoBlock require stacked-info variant": (
        "两个 InfoBlock 必须使用 stacked-info 变体"
    ),
    "S-dual-info requires two InfoBlock": "S-dual-info 必须使用两个 InfoBlock",
}


def _localize_semantic_detail(detail: str) -> str:
    translated = _SEMANTIC_DETAIL_TRANSLATIONS.get(detail)
    if translated is not None:
        return translated
    variant_match = re.fullmatch(
        r"Region\.variant is not supported in this parent area \(got (.+)\); "
        r"(compact|wide) Region variants: (.+)",
        detail,
    )
    if variant_match is not None:
        area = "紧凑版" if variant_match.group(2) == "compact" else "宽版"
        return (
            f"当前父区域不支持 Region.variant（实际为 {variant_match.group(1)}）；"
            f"{area} Region 允许的变体：{variant_match.group(3)}"
        )
    count_match = re.fullmatch(
        r"expected child count (\[[^]]+\]), got (\d+)(?:; (.+) requires children (.+))?",
        detail,
    )
    if count_match is not None:
        message = (
            f"子组件数量应为 {count_match.group(1)}，实际为 {count_match.group(2)}"
        )
        if count_match.group(3) is not None:
            message += (
                f"；{count_match.group(3)} 要求的 children 角色为 {count_match.group(4)}"
            )
        return message
    role_count_match = re.fullmatch(
        r"expected child count (\[[^]]+\]); requires children (.+)",
        detail,
    )
    if role_count_match is not None:
        return (
            f"子组件数量应为 {role_count_match.group(1)}；"
            f"要求的 children 角色为 {role_count_match.group(2)}"
        )
    action_match = re.fullmatch(r"action role requires (.+) with onClick", detail)
    if action_match is not None:
        return f"动作角色必须使用带 onClick 的 {action_match.group(1)}"
    variants_match = re.fullmatch(r"allowed small variants: (.+)", detail)
    if variants_match is not None:
        return f"小卡允许的 variant：{variants_match.group(1)}"
    missing_match = re.fullmatch(r"uncompiled component\(s\): (.+)", detail)
    if missing_match is not None:
        return f"以下组件未接入已展开的组件树：{missing_match.group(1)}"
    size_match = re.fullmatch(
        r"layout is available only for size (.+), not (.+)", detail
    )
    if size_match is not None:
        return (
            f"该布局仅适用于尺寸 {size_match.group(1)}，不能用于 {size_match.group(2)}"
        )
    logger.warning("Untranslated semantic layout feedback: {}", detail)
    return "语义布局的组件角色或树结构不符合已登记合同"


def _localize_semantic_layout_message(message: str) -> str:
    layout_match = re.fullmatch(
        r"layout does not match semantic contract: ([^:]+): (.+)\. "
        r"Choose a registered Layout/Region/Group variant; do not edit expanded geometry\.",
        message,
    )
    if layout_match is not None:
        detail = _localize_semantic_detail(layout_match.group(2))
        return (
            f"语义布局不符合合同：节点 {layout_match.group(1)}：{detail}。"
            "请选择已登记的 Layout、Region 或 Group 变体，不要修改展开后的几何。"
        )
    props_match = re.fullmatch(
        r"component ([^:]+): invalid semantic props: (.+)\. "
        r"Fix only the reported properties; preserve the current layout, facts and Actions\.",
        message,
    )
    if props_match is None:
        return message
    detail = props_match.group(2)
    if detail.startswith("unsupported semantic properties "):
        detail = "不支持以下语义属性：" + detail.removeprefix(
            "unsupported semantic properties "
        )
    elif detail.startswith("business geometry is template-owned: "):
        detail = "以下业务几何由模板负责，模型不能声明：" + detail.removeprefix(
            "business geometry is template-owned: "
        )
    else:
        logger.warning("Untranslated semantic props feedback: {}", detail)
        detail = "语义属性不符合已登记合同"
    return (
        f"组件 {props_match.group(1)} 的语义属性无效：{detail}。"
        "只修复已报告的属性，并保留当前布局、事实和 Action。"
    )


def _required_text(value: dict[str, Any], key: str) -> str:
    text = value.get(key)
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"Compact diagnostic requires non-empty {key}")
    return text


def _format_location(diagnostic: dict[str, Any]) -> str | None:
    parts: list[str] = []
    line = diagnostic.get("sourceLine")
    if isinstance(line, int) and not isinstance(line, bool) and line > 0:
        parts.append(f"原文第 {line} 行")
    component_id = diagnostic.get("componentId")
    if isinstance(component_id, str) and component_id:
        parts.append(f"组件 {component_id}")
        path = diagnostic.get("propertyPath")
        if isinstance(path, str) and path:
            parts.append(f"属性 {path}")
    result: str | None = None
    if parts:
        result = "位置：" + "；".join(parts)
    return result


def _json_fact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _format_diagnostic(diagnostic: dict[str, Any]) -> str:
    code = _required_text(diagnostic, "code")
    validation_class = _required_text(diagnostic, "validationClass")
    category = _required_text(diagnostic, "category")
    message = _required_text(diagnostic, "message")
    if diagnostic.get("severity") != "error":
        raise ValueError("Only Compact errors belong in repair feedback")
    if "expected" not in diagnostic:
        raise ValueError("Compact diagnostic requires its hard constraints")
    lines = [f"错误码：{code}", f"分类：{validation_class} / {category}"]
    location = _format_location(diagnostic)
    if location is not None:
        lines.append(location)
    lines.append(f"问题：{message}")
    if "actual" in diagnostic:
        source_names = {
            "original": "本轮原始文本",
            "validation": "本轮校验文本",
            "expanded": "高阶组件展开结果",
        }
        source = source_names.get(diagnostic.get("evidenceSource"))
        if source is None:
            raise ValueError("Compact diagnostic actual requires evidenceSource")
        lines.append(f"实际值（来源：{source}）：{_json_fact(diagnostic.get('actual'))}")
    lines.append(f"约束：{_json_fact(diagnostic.get('expected'))}")
    hint = diagnostic.get("fixHint")
    if hint is not None:
        lines.append("修改建议：" + _required_text(diagnostic, "fixHint"))
    return "\n".join(lines)


def format_compact_issue_for_model(payload: dict[str, Any]) -> str:
    """读取完整迁移的一组诊断，按原顺序逐条呈现。"""
    diagnostics = payload.get("compactDiagnostics")
    if not isinstance(diagnostics, list) or not diagnostics:
        raise ValueError("Compact feedback requires a complete non-empty diagnostic group")
    paragraphs: list[str] = []
    for index, diagnostic in enumerate(diagnostics, 1):
        if not isinstance(diagnostic, dict):
            raise TypeError("Compact diagnostic must be an object")
        paragraph = _format_diagnostic(diagnostic)
        if len(diagnostics) > 1:
            paragraph = f"关联问题 {index}\n{paragraph}"
        paragraphs.append(paragraph)
    return "\n\n".join(paragraphs)


def compact_issue_for_model(payload: dict[str, Any]) -> dict[str, Any]:
    """只修改新建的外层对象；诊断嵌套值只读，不被文字说明覆盖。"""
    result = dict(payload)
    is_compact = (
        payload.get("stage") == "validation"
        and payload.get("code") == "COMPACT_DSL_VALIDATION_FAILED"
    )
    if not is_compact:
        return result
    if "compactDiagnostics" not in payload:
        message = result.get("message")
        if isinstance(message, str):
            result["message"] = _localize_semantic_layout_message(message)
        return result
    result.pop("compactDiagnostics", None)
    try:
        result["message"] = format_compact_issue_for_model(payload)
    except Exception as exc:
        logger.warning("Compact feedback formatting failed: {}: {}", type(exc).__name__, exc)
    return result


def _height_overflow_diagnostic(payload: dict[str, Any]) -> dict[str, Any] | None:
    diagnostics = payload.get("compactDiagnostics")
    if not isinstance(diagnostics, list) or len(diagnostics) != 1:
        return None
    diagnostic = diagnostics[0]
    if not isinstance(diagnostic, dict):
        return None
    if diagnostic.get("code") != "COMPACT_LAYOUT_HEIGHT_OVERFLOW":
        return None
    try:
        _format_diagnostic(diagnostic)
    except (TypeError, ValueError):
        return None
    actual = diagnostic.get("actual")
    expected = diagnostic.get("expected")
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return None
    numeric_values = (
        actual.get("minimumRequiredHeight"),
        actual.get("overflow"),
        expected.get("maximumHeight"),
    )
    for value in numeric_values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        if not math.isfinite(float(value)):
            return None
    return diagnostic


def _height_group_key(diagnostic: dict[str, Any]) -> tuple[str, int | None] | None:
    component_id = diagnostic.get("componentId")
    source_line = diagnostic.get("sourceLine")
    if not isinstance(source_line, int) or isinstance(source_line, bool):
        source_line = None
    group_key: tuple[str, int | None] | None = None
    if isinstance(component_id, str) and component_id:
        group_key = component_id, source_line
    else:
        actual = diagnostic.get("actual")
        occupancy = actual.get("occupancy") if isinstance(actual, dict) else None
        if isinstance(occupancy, str):
            item_match = re.match(r"^([A-Za-z0-9_-]+)_item\d+_", occupancy)
            if item_match is not None:
                group_key = f"{item_match.group(1)}_items", source_line
    return group_key


def _compact_number(value: Any) -> str:
    return f"{float(value):g}"


def _height_group_summary(
    payload: dict[str, Any],
    diagnostics: list[dict[str, Any]],
    group_key: tuple[str, int | None],
) -> dict[str, Any]:
    result = dict(payload)
    result.pop("compactDiagnostics", None)
    representative = diagnostics[0]
    representative_expected = representative.get("expected")
    maximum_height = float(representative_expected.get("maximumHeight"))
    for diagnostic in diagnostics[1:]:
        candidate_expected = diagnostic.get("expected")
        candidate_height = float(candidate_expected.get("maximumHeight"))
        if candidate_height > maximum_height:
            representative = diagnostic
            maximum_height = candidate_height
    component_id = str(representative.get("componentId") or group_key[0])
    source_line = representative.get("sourceLine")
    actual = representative.get("actual")
    expected = representative.get("expected")
    actual = actual if isinstance(actual, dict) else {}
    expected = expected if isinstance(expected, dict) else {}
    required = actual.get("minimumRequiredHeight")
    maximum = expected.get("maximumHeight")
    overflow = actual.get("overflow")
    location = f"组件 {component_id}"
    if isinstance(source_line, int) and not isinstance(source_line, bool):
        location = f"原文第 {source_line} 行；{location}"
    lines = [
        "错误码：COMPACT_LAYOUT_HEIGHT_OVERFLOW",
        f"位置：{location}",
        "问题：该语义分区完整内容至少需要 "
        f"{_compact_number(required)}vp，可用 {_compact_number(maximum)}vp，"
        f"超出 {_compact_number(overflow)}vp。",
    ]
    occupancies: list[str] = []
    for diagnostic in diagnostics:
        item_actual = diagnostic.get("actual")
        if not isinstance(item_actual, dict):
            continue
        occupancy = item_actual.get("occupancy")
        if not isinstance(occupancy, str) or not occupancy:
            continue
        is_wrapper = occupancy.startswith("__layout__") and occupancy.count(",") == 1
        if is_wrapper or occupancy in occupancies:
            continue
        occupancies.append(occupancy)
    if occupancies:
        lines.append("关键占用：")
        for occupancy in occupancies[:3]:
            lines.append(f"- {occupancy}")
    title_icon_candidate = None
    for diagnostic in diagnostics:
        item_actual = diagnostic.get("actual")
        if not isinstance(item_actual, dict):
            continue
        candidate = item_actual.get("removableTitleIcon")
        if isinstance(candidate, dict):
            title_icon_candidate = candidate
            break
    if title_icon_candidate is not None:
        title_id = title_icon_candidate.get("componentId")
        height_saving = title_icon_candidate.get("heightSaving")
        if isinstance(title_id, str) and isinstance(height_saving, (int, float)):
            lines.append(
                f"优先修复：删除 SingleLineTitle 组件 {title_id} 的 icon 属性可释放 "
                f"{_compact_number(height_saving)}vp，足以消除当前高度超限；"
                "保留 title、全部事实、Action 和当前布局。"
            )
    lines.append(
        "修复要求：按完整事实重新选择组件组合或当前尺寸合法布局；"
        "保留必要事实、Action、固定字号和设计尺寸，不使用裁剪、缩字、权重或 flexShrink 规避。"
    )
    result["message"] = "\n".join(lines)
    return result


def compact_issues_for_model(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """合并同一语义分区的展开高度错误，仅精简发送给 Repair 模型的反馈。"""
    groups: dict[tuple[str, int | None], list[dict[str, Any]]] = {}
    ordered: list[tuple[str, Any]] = []
    first_payloads: dict[tuple[str, int | None], dict[str, Any]] = {}
    for payload in payloads:
        diagnostic = _height_overflow_diagnostic(payload)
        key = _height_group_key(diagnostic) if diagnostic is not None else None
        if diagnostic is None or key is None:
            ordered.append(("issue", payload))
            continue
        group = groups.get(key)
        if group is None:
            group = []
            groups[key] = group
            first_payloads[key] = payload
            ordered.append(("height", key))
        group.append(diagnostic)

    results: list[dict[str, Any]] = []
    for kind, value in ordered:
        if kind == "issue":
            results.append(compact_issue_for_model(value))
            continue
        if not isinstance(value, tuple):
            raise TypeError("Compact height feedback group key must be a tuple")
        group = groups.get(value)
        first_payload = first_payloads.get(value)
        if group is None or first_payload is None:
            raise RuntimeError("Compact height feedback group is incomplete")
        results.append(_height_group_summary(first_payload, group, value))
    return results
