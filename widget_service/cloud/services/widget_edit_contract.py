"""语义编辑的意图合同与原卡差异检查，不参与首次生成。"""

from __future__ import annotations

import copy
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from models.generation import WidgetSize
from services.single_step_edit import _components, _load_json, _messages, _same, source_digest

EditDimension = Literal["palette", "typography", "spacing", "shape", "layout", "text"]
_STYLE_GROUPS = {
    "palette": {"fontColor", "fillColor", "color", "backgroundColor", "linearGradient",
                "borderColor", "selectedColor"},
    "typography": {"fontSize", "fontWeight", "minFontSize", "maxFontSize", "textAlign",
                   "maxLines", "textOverflow"},
    "spacing": {"margin", "padding", "itemMargin", "justifyContent", "alignItems",
                "alignContent", "alignSelf"},
    "shape": {"borderRadius", "borderWidth", "shadow", "clip", "strokeWidth", "type"},
    "layout": {"width", "height", "aspectRatio", "constraintSize", "layoutWeight",
               "flexShrink", "wrap", "listDirection"},
}
_CONTAINERS = {"Row", "Column", "Stack"}
_TOP_LAYOUT_FIELDS = {"itemMargin", "space", "wrap"}
_STYLE_PATH = Path(__file__).resolve().parents[1] / "data/validator_rules/config/style.json"


class TextChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    componentId: str
    before: str
    after: str = Field(min_length=1)


class EditIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: Literal["ready", "needs_clarification", "unchanged", "unsupported"] = "ready"
    explanation: str = Field(min_length=1)
    mode: Literal["patch", "layout"] = "patch"
    targetSize: WidgetSize
    dimensions: list[EditDimension] = Field(default_factory=list)
    targets: list[str] = Field(default_factory=list)
    linkedTargets: list[str] = Field(default_factory=list)
    protectedTargets: list[str] = Field(default_factory=list)
    backgroundTargets: list[str] = Field(default_factory=list)
    textChanges: list[TextChange] = Field(default_factory=list)


def dump_rows(rows: list[dict]) -> str:
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def _tree(source: str) -> tuple[list[dict], dict[str, dict]]:
    rows = _messages(source)
    if len(rows) != 3:
        raise ValueError("编辑源和结果必须是三条标准 A2UI 消息")
    keys = ("createSurface", "updateComponents", "updateDataModel")
    for row, key in zip(rows, keys, strict=True):
        if not isinstance(row.get(key), dict):
            raise ValueError(f"标准 A2UI 消息缺少 {key}")
    return rows, _components(rows)


def descendants(nodes: dict[str, dict], roots: list[str]) -> set[str]:
    result: set[str] = set()
    pending = list(roots)
    while pending:
        identity = pending.pop()
        if identity in result:
            continue
        node = nodes.get(identity)
        if node is None:
            raise ValueError(f"编辑范围引用不存在的组件：{identity}")
        result.add(identity)
        children = node.get("children")
        if isinstance(children, list):
            pending.extend(children)
        elif isinstance(children, dict):
            child = children.get("componentId")
            if isinstance(child, str):
                pending.append(child)
    return result


def scope_ids(intent: EditIntent, nodes: dict[str, dict]) -> set[str]:
    allowed = descendants(nodes, intent.targets)
    for identity in intent.linkedTargets:
        if identity not in nodes:
            raise ValueError(f"联动目标不存在：{identity}")
        allowed.add(identity)
    protected = descendants(nodes, intent.protectedTargets)
    return allowed - protected


def _dynamic(value: Any) -> bool:
    found = False
    if isinstance(value, str):
        found = "{{" in value or "${" in value
    elif isinstance(value, dict):
        found = "path" in value or any(_dynamic(item) for item in value.values())
    elif isinstance(value, list):
        found = any(_dynamic(item) for item in value)
    return found


def validate_intent(
    intent: EditIntent, original: str, source_size: str, explicit_size: str | None,
) -> None:
    _, nodes = _tree(original)
    if intent.outcome != "ready":
        if intent.outcome == "unchanged" and explicit_size is not None:
            if explicit_size != source_size:
                raise ValueError("显式请求变更规格时不能返回无需修改")
        return
    allowed = scope_ids(intent, nodes)
    if not allowed or not intent.dimensions:
        raise ValueError("编辑计划必须列出明确的目标和视觉维度")
    if explicit_size is not None and intent.targetSize != explicit_size:
        raise ValueError("编辑目标规格必须与请求显式尺寸一致")
    if intent.targetSize != source_size:
        if intent.mode != "layout" or "layout" not in intent.dimensions:
            raise ValueError("变更卡片规格必须执行布局编辑，不能只更新尺寸元信息")
    if intent.mode == "layout" and "layout" not in intent.dimensions:
        raise ValueError("布局编辑必须声明 layout 维度")
    seen_text: set[str] = set()
    for change in intent.textChanges:
        if change.componentId in seen_text:
            raise ValueError("同一组件不能存在相互冲突的文案修改")
        seen_text.add(change.componentId)
        node = nodes.get(change.componentId)
        if node is None or change.componentId not in allowed:
            raise ValueError("文案修改超出已接受范围")
        if "text" not in intent.dimensions or node.get("component") != "Text":
            raise ValueError("只有明确的文字编辑可以修改静态 Text 内容")
        if node.get("content") != change.before:
            raise ValueError("文字修改原值与原卡不一致")
        if _dynamic(change.before) or _dynamic(change.after):
            raise ValueError("文案编辑不得静态化或引入动态表达式")
    for identity in intent.backgroundTargets:
        node = nodes.get(identity)
        if node is None or identity not in allowed or "palette" not in intent.dimensions:
            raise ValueError("背景联动目标必须位于配色编辑范围")
        if node.get("onClick") or _dynamic(node):
            raise ValueError("背景联动不得删除动作或动态内容")
        if node.get("component") == "Image":
            styles = node.get("styles", {})
            if styles.get("width") not in {"matchParent", "100%"}:
                raise ValueError("不能把业务图标当成背景移除")
            if styles.get("height") not in {"matchParent", "100%"}:
                raise ValueError("背景图必须为填满承载区的图片")


def _allowed_styles(intent: EditIntent) -> set[str]:
    allowed: set[str] = set()
    for dimension in intent.dimensions:
        allowed.update(_STYLE_GROUPS.get(dimension, set()))
    if intent.mode == "layout":
        allowed.update(_STYLE_GROUPS.get("spacing", set()))
        allowed.update(_STYLE_GROUPS.get("layout", set()))
    return allowed


def _style_value(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("样式数值必须有限")
    if _dynamic(value):
        raise ValueError("视觉编辑不能引入新的动态样式或资源引用")
    if isinstance(value, dict):
        for child in value.values():
            _style_value(child)
    elif isinstance(value, list):
        for child in value:
            _style_value(child)


def _apply_patch(original: str, patch: dict, intent: EditIntent) -> str:
    rows, nodes = _tree(original)
    changes = patch.get("changes")
    if not isinstance(changes, list) or not 1 <= len(changes) <= 256:
        raise ValueError("ready 编辑必须包含 1..256 项修改；无需修改应在意图阶段说明")
    seen: set[tuple[str, str]] = set()
    for change in changes:
        if not isinstance(change, dict):
            raise ValueError("补丁项必须为对象")
        identity, prop = change.get("componentId"), change.get("property")
        if not isinstance(identity, str) or not isinstance(prop, str):
            raise ValueError("补丁目标和字段必须为字符串")
        node = nodes.get(identity)
        if node is None or (identity, prop) in seen:
            raise ValueError("补丁目标不存在或字段重复")
        seen.add((identity, prop))
        if prop == "content" or prop in _TOP_LAYOUT_FIELDS:
            target, key = node, prop
        elif prop.startswith("styles."):
            target, key = node.setdefault("styles", {}), prop.removeprefix("styles.")
            if "." in key or not key:
                raise ValueError("样式补丁只接受单个协议属性")
        else:
            raise ValueError("属性补丁不得修改结构、绑定或动作")
        if not isinstance(target, dict):
            raise ValueError("组件样式必须是对象")
        before = {"exists": key in target}
        if key in target:
            before["value"] = target.get(key)
        if not _same(change.get("before"), before):
            raise ValueError("补丁原值与不可变原卡不一致")
        operation = change.get("operation", "set")
        if operation == "remove":
            if key not in target:
                raise ValueError("不能删除原本不存在的字段")
            target.pop(key)
        elif operation == "set" and "value" in change:
            target[key] = copy.deepcopy(change.get("value"))
        else:
            raise ValueError("补丁只能设置 value 或移除明确的原字段")
    result = dump_rows(rows)
    validate_edit_diff(original, result, intent)
    return result


def apply_edit_output(original: str, raw: str, intent: EditIntent) -> str:
    payload = _load_json(raw)
    if not isinstance(payload, dict) or payload.get("sourceDigest") != source_digest(original):
        raise ValueError("编辑结果必须携带不可变原卡摘要")
    if intent.mode == "patch":
        if set(payload) != {"sourceDigest", "changes"}:
            raise ValueError("属性编辑只接受 sourceDigest 与 changes")
        result = _apply_patch(original, payload, intent)
    else:
        if set(payload) != {"sourceDigest", "genui"}:
            raise ValueError("布局编辑只接受 sourceDigest 与三条标准 genui 消息")
        rows = payload.get("genui")
        if not isinstance(rows, list):
            raise ValueError("布局编辑的 genui 必须是标准消息数组")
        result = dump_rows(rows)
        validate_edit_diff(original, result, intent)
    if _same(_messages(original), _messages(result)):
        raise ValueError("编辑结果没有实际变化，不能声称完成修改")
    return result


def _reachable(nodes: dict[str, dict], root: str) -> set[str]:
    return descendants(nodes, [root])


def _node_changes(before: dict, after: dict) -> set[str]:
    changed: set[str] = set()
    for key in set(before) | set(after):
        if key not in before or key not in after:
            changed.add(key)
        elif not _same(before.get(key), after.get(key)):
            changed.add(key)
    return changed


def validate_edit_diff(original: str, candidate: str, intent: EditIntent) -> None:
    before_rows, before_nodes = _tree(original)
    after_rows, after_nodes = _tree(candidate)
    if not _same(before_rows[0], after_rows[0]) or not _same(before_rows[2], after_rows[2]):
        raise ValueError("视觉编辑不得修改 surface、首帧数据或协议头")
    before_update = before_rows[1].get("updateComponents", {})
    after_update = after_rows[1].get("updateComponents", {})
    before_header = {key: value for key, value in before_update.items() if key != "components"}
    after_header = {key: value for key, value in after_update.items() if key != "components"}
    if not _same(before_header, after_header):
        raise ValueError("编辑不得更换根节点或 surface")
    root = before_update.get("root")
    if not isinstance(root, str):
        raise ValueError("原卡缺少根节点")
    reachable = _reachable(after_nodes, root)
    _check_tree(after_nodes, root)
    source_reachable = _reachable(before_nodes, root)
    allowed = scope_ids(intent, before_nodes)
    style_fields = _allowed_styles(intent)
    texts = {change.componentId: change for change in intent.textChanges}
    style_rules = json.loads(_STYLE_PATH.read_text(encoding="utf-8"))
    for identity, before in before_nodes.items():
        after = after_nodes.get(identity)
        if after is None:
            if identity in intent.backgroundTargets and before.get("component") == "Image":
                continue
            raise ValueError(f"编辑不得删除原有内容或组件：{identity}")
        changes = _node_changes(before, after)
        if changes and identity not in allowed:
            raise ValueError(f"修改超出已接受目标范围：{identity}")
        _validate_node(identity, before, after, changes, intent, texts)
        _validate_styles(identity, before, after, style_fields, intent, style_rules)
        if identity in source_reachable and identity not in reachable:
            raise ValueError(f"原卡展示内容不能移到不可达区域：{identity}")
    for identity, node in after_nodes.items():
        if identity in before_nodes:
            continue
        if intent.mode != "layout" or node.get("component") not in _CONTAINERS:
            raise ValueError("布局编辑只能新增组织容器，不能新增业务内容或素材")
        if set(node) - {"id", "component", "styles", "children"}:
            raise ValueError("新增容器不能承载额外数据或动作")
        _validate_styles(identity, {}, node, style_fields, intent, style_rules)
    _preserve_occurrences(before_nodes, after_nodes)


def _validate_node(identity: str, before: dict, after: dict, changes: set[str],
                   intent: EditIntent, texts: dict[str, TextChange]) -> None:
    allowed_fields = {"styles"}
    if "spacing" in intent.dimensions or "layout" in intent.dimensions:
        allowed_fields.update(_TOP_LAYOUT_FIELDS)
        for key in changes & _TOP_LAYOUT_FIELDS:
            if key not in after:
                continue
            value = after.get(key)
            _style_value(value)
            if key == "wrap":
                if value not in {"noWrap", "wrap"}:
                    raise ValueError("wrap 必须使用合法的换行枚举")
            elif isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("布局间距必须为有限数值")
            elif value < 0:
                raise ValueError("布局间距不能为负数")
    if intent.mode == "layout":
        allowed_fields.add("children")
        old_children, new_children = before.get("children"), after.get("children")
        if isinstance(old_children, dict) or isinstance(new_children, dict):
            if not _same(old_children, new_children):
                raise ValueError("布局调整不得改写列表模板的数据绑定与上下文")
        if before.get("component") in _CONTAINERS:
            allowed_fields.add("component")
            if after.get("component") not in _CONTAINERS:
                raise ValueError("布局容器只能转换为 Row、Column 或 Stack")
    text = texts.get(identity)
    if text is not None:
        allowed_fields.add("content")
        if after.get("content") != text.after:
            raise ValueError("文案结果与接受的静态文字修改不一致")
    if changes - allowed_fields:
        raise ValueError(f"不得修改组件业务字段、动作或资源：{identity}")


def _validate_styles(identity: str, before: dict, after: dict, allowed: set[str],
                     intent: EditIntent, rules: dict) -> None:
    old_styles, new_styles = before.get("styles", {}), after.get("styles", {})
    if not isinstance(old_styles, dict) or not isinstance(new_styles, dict):
        raise ValueError("原卡及编辑样式必须为对象")
    legal = set(rules.get("commonStyleFields", []))
    legal.update(rules.get("componentStyleFields", {}).get(after.get("component"), []))
    for key in _node_changes(old_styles, new_styles):
        background_removal = identity in intent.backgroundTargets and key == "backgroundImage"
        if background_removal and key not in new_styles:
            continue
        if key not in allowed or key not in legal:
            raise ValueError(f"样式不在已接受维度或协议范围：{identity}.{key}")
        value = new_styles.get(key)
        _style_value(value)
        if key in new_styles:
            _validate_style_type(key, value, after.get("component"), rules)
        if key in {"width", "height", "fontSize"} and isinstance(value, (int, float)):
            if isinstance(value, bool) or value <= 0:
                raise ValueError("字号与固定宽高必须为正数")


def _validate_style_type(key: str, value: Any, kind: str, rules: dict) -> None:
    numeric_fields = {"fontSize", "fontWeight", "minFontSize", "maxFontSize", "maxLines",
                      "layoutWeight", "flexShrink", "borderWidth", "strokeWidth", "aspectRatio"}
    if key in numeric_fields:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{key} 必须为有限数值")
        if value < 0:
            raise ValueError(f"{key} 不得为负数")
    color_fields = {"fontColor", "fillColor", "color", "backgroundColor", "borderColor",
                    "selectedColor"}
    if key in color_fields:
        if not isinstance(value, str) or not value.startswith("#"):
            raise ValueError(f"{key} 必须为 #RRGGBB 或 #AARRGGBB")
        if len(value) not in {7, 9}:
            raise ValueError(f"{key} 色值长度非法")
        digits = value.removeprefix("#")
        if any(character not in "0123456789abcdefABCDEF" for character in digits):
            raise ValueError(f"{key} 必须只包含十六进制颜色字符")
        if key == "fontColor" and len(value) == 9 and int(value[1:3], 16) == 0:
            raise ValueError("不能通过透明文字隐藏原卡事实")
    enum_values = rules.get("enumValues", {})
    allowed = enum_values.get(f"{kind}.{key}", enum_values.get(key))
    if allowed is not None and value not in allowed:
        raise ValueError(f"{kind}.{key} 必须使用端侧协议枚举")
    if key in {"width", "height"}:
        _validate_dimension(value)
    if key == "linearGradient":
        _validate_gradient(value, kind, rules)
    if key in {"padding", "margin", "borderRadius"}:
        _validate_edges(value)


def _validate_edges(value: Any) -> None:
    if isinstance(value, bool):
        raise ValueError("边距和圆角必须使用数值")
    if isinstance(value, (int, float)):
        return
    values: list[Any] = []
    if isinstance(value, dict):
        values = list(value.values())
    elif isinstance(value, list):
        values = value
    if not values:
        raise ValueError("边距和圆角必须使用数值或非空数值集合")
    for item in values:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError("边距和圆角集合必须只包含数值")


def _validate_gradient(value: Any, kind: str, rules: dict) -> None:
    if not isinstance(value, dict):
        raise ValueError("渐变必须为协议对象")
    colors = value.get("colors")
    if not isinstance(colors, list) or len(colors) < 2:
        raise ValueError("渐变至少需要两个颜色位置")
    previous = -1.0
    for stop in colors:
        if not isinstance(stop, list) or len(stop) != 2:
            raise ValueError("渐变颜色位置必须为 [色值, 位置]")
        color, offset = stop
        _validate_style_type("backgroundColor", color, kind, rules)
        if isinstance(offset, bool) or not isinstance(offset, (int, float)):
            raise ValueError("渐变位置必须为数值")
        if not 0 <= offset <= 1 or offset < previous:
            raise ValueError("渐变位置必须在 0..1 中递增")
        previous = float(offset)


def _validate_dimension(value: Any) -> None:
    if isinstance(value, bool):
        raise ValueError("宽高不能是布尔值")
    if isinstance(value, (int, float)):
        if value <= 0:
            raise ValueError("宽高必须为正数")
        return
    if isinstance(value, str):
        if value == "matchParent":
            return
        if value.endswith("%"):
            number = float(value.removesuffix("%"))
            if math.isfinite(number) and number > 0:
                return
    raise ValueError("宽高必须是正数、正百分比或 matchParent")


def _check_tree(nodes: dict[str, dict], root: str) -> None:
    """拒绝可达树中的环；共享叶节点另由挂载次数保护。"""
    visiting: set[str] = set()
    visited: set[str] = set()
    pending = [(root, False)]
    while pending:
        identity, leaving = pending.pop()
        if leaving:
            visiting.remove(identity)
            visited.add(identity)
            continue
        if identity in visiting:
            raise ValueError("组件树不能形成循环引用")
        if identity in visited:
            continue
        node = nodes.get(identity)
        if node is None:
            raise ValueError("组件树引用了不存在的目标")
        visiting.add(identity)
        pending.append((identity, True))
        children = node.get("children", [])
        if isinstance(children, dict):
            children = [children.get("componentId")]
        if not isinstance(children, list):
            raise ValueError("children 必须为引用数组或合法模板引用")
        for child in reversed(children):
            if not isinstance(child, str):
                raise ValueError("children 只能引用组件 ID")
            pending.append((child, False))


def has_layout_change(original: str, candidate: str) -> bool:
    before_nodes, after_nodes = _components(_messages(original)), _components(_messages(candidate))
    changed = set(before_nodes) != set(after_nodes)
    for identity, before in before_nodes.items():
        after = after_nodes.get(identity)
        if after is None:
            continue
        if not _same(before.get("children"), after.get("children")):
            changed = True
        if before.get("component") != after.get("component"):
            changed = True
        old_styles, new_styles = before.get("styles", {}), after.get("styles", {})
        for key in _STYLE_GROUPS.get("layout", set()):
            if not _same(old_styles.get(key), new_styles.get(key)):
                changed = True
    return changed


def _preserve_occurrences(before: dict[str, dict], after: dict[str, dict]) -> None:
    """不允许把同一业务组件挂载多次来改变事实/动作次数。"""
    old_count: Counter[str] = Counter()
    new_count: Counter[str] = Counter()
    for nodes, counts in ((before, old_count), (after, new_count)):
        for node in nodes.values():
            children = node.get("children")
            if isinstance(children, list):
                counts.update(children)
    for identity, node in before.items():
        if node.get("component") in _CONTAINERS:
            continue
        if identity in after and old_count.get(identity, 0) != new_count.get(identity, 0):
            raise ValueError(f"不能改变业务组件的挂载次数：{identity}")
