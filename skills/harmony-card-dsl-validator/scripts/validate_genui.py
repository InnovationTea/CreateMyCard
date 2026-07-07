#!/usr/bin/env python3
"""Static checker for HarmonyOS A2UI Form genui JSONL and CardSpec."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from typing import Any


ALLOWED_COMPONENTS = {
    "Text", "Image", "Divider", "Progress", "Button",
    "Checkbox", "Row", "Column", "List", "Stack",
}
PROHIBITED_COMPONENTS = {
    "TextInput", "Toggle", "Radio", "CheckboxGroup", "Select",
    "NavContainer", "Tabs", "TabContent", "Web", "Grid", "If",
}
TEMPLATE_CONTAINERS = {"Row", "Column", "List"}
KNOWN_EVENT_CALLS = {"clickToCallPhone", "clickToDeeplink", "clickToIntent"}
KNOWN_DATA_CAPABILITIES = {"weather.overview.get", "calendar.events.search"}
EVENT_NAMES = {"onClick", "onAppear", "onChange", "onSelect", "onReachStart", "onReachEnd"}
NETWORK_RE = re.compile(r"^(https?:)?//|^(https?:)|example\.com|placeholder\.com|picsum\.photos", re.I)
EXPR_RE = re.compile(r"\{\{.*?\}\}")
IDENT_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


@dataclass
class Issue:
    severity: str
    location: str
    message: str
    suggestion: str = ""

    def line(self) -> str:
        suffix = f" 建议：{self.suggestion}" if self.suggestion else ""
        return f"- [{self.severity}] {self.location}: {self.message}{suffix}"


def read_input(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def fenced_blocks(text: str) -> list[tuple[str, str]]:
    pattern = re.compile(r"```([A-Za-z0-9_-]*)\s*\n(.*?)```", re.S)
    return [(m.group(1).lower(), m.group(2).strip()) for m in pattern.finditer(text)]


def split_payload(text: str) -> tuple[str, str | None]:
    blocks = fenced_blocks(text)
    if not blocks:
        return text.strip(), None
    genui_parts: list[str] = []
    cardspec: str | None = None
    for lang, body in blocks:
        if lang == "genui":
            genui_parts.append(body)
        elif lang == "cardspec":
            cardspec = body
        elif lang in {"json", ""}:
            try:
                obj = json.loads(body)
                if isinstance(obj, dict) and "suggestSize" in obj:
                    cardspec = body
                else:
                    genui_parts.append(body)
            except Exception:
                genui_parts.append(body)
    return "\n".join(genui_parts).strip(), cardspec


def parse_jsonl(text: str) -> tuple[list[tuple[int, dict[str, Any]]], list[Issue]]:
    issues: list[Issue] = []
    messages: list[tuple[int, dict[str, Any]]] = []
    if not text:
        return messages, [Issue("P0", "输入", "没有找到 genui JSONL 内容")]
    for idx, line in enumerate([ln for ln in text.splitlines() if ln.strip()], 1):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            issues.append(Issue("P0", f"第 {idx} 行", f"JSON 解析失败：{exc.msg}", "JSONL 每行只能有一个完整 JSON object"))
            continue
        if not isinstance(obj, dict):
            issues.append(Issue("P0", f"第 {idx} 行", "消息不是 object"))
            continue
        messages.append((idx, obj))
    return messages, issues


def walk(value: Any, path: str = "$"):
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            yield from walk(child, f"{path}[{idx}]")


def check_expression(value: str, location: str, issues: list[Issue]) -> None:
    if "{{" not in value and "}}" not in value:
        return
    if value.count("{{") != value.count("}}"):
        issues.append(Issue("P1", location, "表达式括号不配对", "使用完整的 `{{ ... }}` 表达式"))
    matches = EXPR_RE.findall(value)
    if len(matches) > 1:
        issues.append(Issue("P1", location, "一个字符串中包含多个独立表达式", "改成单个表达式，例如 `{{ $a + ' ' + $b }}`"))
    if matches and value.strip() != matches[0]:
        issues.append(Issue("P1", location, "表达式外混有普通文本", "拼接请放入表达式内部"))
    if len(value) > 2048:
        issues.append(Issue("P1", location, "表达式字符串超过 2048 字符"))
    if "$__widthBreakpoint" in value or "$__colorMode" in value:
        issues.append(Issue("P0", location, "Form 排除 `$__widthBreakpoint` 和 `$__colorMode`"))
    issues.append(Issue("P3", location, "检测到表达式；完整 A2UI Form 协议允许，但当前生成 skill 默认禁用表达式", "若目标是验证生成 skill，优先改为 `{path}`、`formatString` 或预计算展示字段"))


def check_media_value(value: Any, location: str, issues: list[Issue]) -> None:
    if isinstance(value, str):
        if NETWORK_RE.search(value):
            issues.append(Issue("P0", location, "媒体路径使用了网络/占位 URL", "改用用户提供或素材库声明的本地/资源路径"))
        if value.lower().endswith(".svg") or value.lower().startswith("data:image/svg"):
            issues.append(Issue("P0", location, "Form Image/backgroundImage 不支持 SVG"))


def check_messages(messages: list[tuple[int, dict[str, Any]]]) -> tuple[list[Issue], dict[str, Any]]:
    issues: list[Issue] = []
    create_lines: list[int] = []
    update_component_lines: list[int] = []
    surface_ids: list[tuple[str, str]] = []
    components: list[dict[str, Any]] = []

    for line_no, msg in messages:
        if msg.get("version") != "v0.9":
            issues.append(Issue("P0", f"第 {line_no} 行", "`version` 不是 `v0.9`"))
        message_keys = [key for key in ("createSurface", "updateComponents", "updateDataModel", "deleteSurface") if key in msg]
        if len(message_keys) != 1:
            issues.append(Issue("P0", f"第 {line_no} 行", "消息必须且只能包含一个 create/update/delete payload"))
            continue
        kind = message_keys[0]
        payload = msg[kind]
        if not isinstance(payload, dict):
            issues.append(Issue("P0", f"第 {line_no} 行 `{kind}`", "payload 必须是 object"))
            continue
        sid = payload.get("surfaceId")
        if not isinstance(sid, str) or not sid:
            issues.append(Issue("P0", f"第 {line_no} 行 `{kind}.surfaceId`", "缺少有效 surfaceId"))
        else:
            surface_ids.append((f"第 {line_no} 行", sid))

        if kind == "createSurface":
            create_lines.append(line_no)
            if payload.get("catalogId") != "ohos.a2ui.extended.catalog":
                issues.append(Issue("P0", f"第 {line_no} 行 `createSurface.catalogId`", "必须是 `ohos.a2ui.extended.catalog`"))
            if "theme" in payload:
                issues.append(Issue("P0", f"第 {line_no} 行 `createSurface.theme`", "Form createSurface 不支持 theme 字段"))
        elif kind == "updateComponents":
            update_component_lines.append(line_no)
            arr = payload.get("components")
            if not isinstance(arr, list):
                issues.append(Issue("P0", f"第 {line_no} 行 `updateComponents.components`", "components 必须是数组"))
            else:
                components.extend([item for item in arr if isinstance(item, dict)])
                if any(not isinstance(item, dict) for item in arr):
                    issues.append(Issue("P0", f"第 {line_no} 行 `components`", "每个组件必须是 object"))
        elif kind == "updateDataModel":
            path = payload.get("path", "/")
            if not isinstance(path, str) or (path and not path.startswith("/")):
                issues.append(Issue("P1", f"第 {line_no} 行 `updateDataModel.path`", "path 应为 JSON Pointer，通常以 `/` 开头"))
        elif kind == "deleteSurface":
            issues.append(Issue("P2", f"第 {line_no} 行 `deleteSurface`", "最终卡片产物通常不应包含 deleteSurface，除非正在校验生命周期消息"))

        for path, value in walk(payload, f"第 {line_no} 行 `{kind}`"):
            if isinstance(value, str):
                check_expression(value, path, issues)
            if path.endswith(".src") or path.endswith(".backgroundImage"):
                check_media_value(value, path, issues)
            if isinstance(value, dict) and set(value.keys()) == {"path"} and isinstance(value.get("path"), str):
                binding_path = value["path"]
                if binding_path.startswith("/") and "." in binding_path:
                    issues.append(Issue("P2", path, "JSON Pointer 中疑似使用点路径", "例如 `/meeting/title`，不要写 `/meeting.title`"))

    if not create_lines:
        issues.append(Issue("P0", "消息流", "缺少 createSurface"))
    if len(create_lines) > 1:
        issues.append(Issue("P0", "消息流", "存在多个 createSurface"))
    if not update_component_lines:
        issues.append(Issue("P0", "消息流", "缺少 updateComponents"))
    if len(update_component_lines) > 1:
        issues.append(Issue("P0", "消息流", "同一 Form surface 不应有多次 updateComponents"))
    if create_lines and update_component_lines and min(update_component_lines) < min(create_lines):
        issues.append(Issue("P0", "消息顺序", "updateComponents 出现在 createSurface 之前"))
    if surface_ids and len({sid for _, sid in surface_ids}) > 1:
        detail = ", ".join([f"{loc}={sid}" for loc, sid in surface_ids])
        issues.append(Issue("P0", "surfaceId", f"消息流 surfaceId 不一致：{detail}"))

    component_info = check_components(components)
    issues.extend(component_info["issues"])
    return issues, {"root_size": component_info.get("root_size")}


def check_components(components: list[dict[str, Any]]) -> dict[str, Any]:
    issues: list[Issue] = []
    ids: dict[str, dict[str, Any]] = {}
    root_size = None
    for idx, comp in enumerate(components):
        cid = comp.get("id")
        ctype = comp.get("component")
        loc = f"组件[{idx}]"
        if not isinstance(cid, str) or not cid:
            issues.append(Issue("P0", loc, "组件缺少有效 id"))
            continue
        if cid in ids:
            issues.append(Issue("P0", f"组件 `{cid}`", "组件 id 重复"))
        ids[cid] = comp
        loc = f"组件 `{cid}`"
        if not isinstance(ctype, str) or not ctype:
            issues.append(Issue("P0", loc, "组件缺少 component"))
            continue
        if ctype in PROHIBITED_COMPONENTS:
            issues.append(Issue("P0", loc, f"Form 不支持组件 `{ctype}`"))
        elif ctype not in ALLOWED_COMPONENTS:
            issues.append(Issue("P1", loc, f"未知或自定义组件 `{ctype}`", "只有宿主 catalog 明确注册时才可使用"))

        if ctype == "Text":
            if "content" not in comp:
                issues.append(Issue("P0", loc, "Text 缺少 `content`"))
            if "text" in comp:
                issues.append(Issue("P0", loc, "Text 使用了标准属性 `text`", "改用 extended 属性 `content`"))
        if ctype == "Image":
            if "src" not in comp:
                issues.append(Issue("P0", loc, "Image 缺少 `src`"))
            if "url" in comp:
                issues.append(Issue("P0", loc, "Image 使用了 `url`", "改用 `src`"))
            check_media_value(comp.get("src"), f"{loc}.src", issues)
        if ctype == "Button":
            if "label" not in comp:
                issues.append(Issue("P0", loc, "Button 缺少 `label`"))
            if "child" in comp:
                issues.append(Issue("P0", loc, "Button 使用了 `child`", "改用 `label`"))
            if "action" in comp:
                issues.append(Issue("P0", loc, "Form Button 不使用 `action`", "把点击行为写到 `onClick` EventHandler 数组"))
        if ctype == "Progress" and "total" not in comp:
            issues.append(Issue("P0", loc, "Progress 缺少 `total`"))

        styles = comp.get("styles")
        if isinstance(styles, dict):
            for key, value in styles.items():
                if "-" in key:
                    issues.append(Issue("P0", f"{loc}.styles.{key}", "样式键使用了 CSS kebab-case", "改用 camelCase，例如 `fontSize`"))
                if key == "backgroundImage":
                    check_media_value(value, f"{loc}.styles.backgroundImage", issues)
        elif styles is not None:
            issues.append(Issue("P0", f"{loc}.styles", "styles 必须是 object"))

        for event in EVENT_NAMES:
            if event in comp:
                if event != "onClick":
                    issues.append(Issue("P0", f"{loc}.{event}", "Form 只支持 onClick 通用事件"))
                check_event(comp[event], f"{loc}.{event}", issues)

        if cid == "root":
            styles = comp.get("styles", {})
            if isinstance(styles, dict):
                root_size = (styles.get("width"), styles.get("height"))

    if "root" not in ids and components:
        issues.append(Issue("P0", "组件树", "缺少 `root` 组件"))

    for cid, comp in ids.items():
        ctype = comp.get("component")
        children = comp.get("children")
        if children is None:
            continue
        loc = f"组件 `{cid}`.children"
        if isinstance(children, list):
            for i, child in enumerate(children):
                if isinstance(child, str):
                    if child not in ids:
                        issues.append(Issue("P0", f"{loc}[{i}]", f"child 引用 `{child}` 不存在"))
                elif isinstance(child, dict):
                    issues.append(Issue("P0", f"{loc}[{i}]", "children 不能内联组件 object", "改为扁平 components 邻接表，用 id 引用"))
                else:
                    issues.append(Issue("P0", f"{loc}[{i}]", "children 数组项必须是组件 id 字符串"))
        elif isinstance(children, dict):
            if ctype not in TEMPLATE_CONTAINERS:
                issues.append(Issue("P0", loc, f"`{ctype}` 不支持模板 children 对象"))
            allowed = {"path", "componentId", "itemVar", "indexVar"}
            extra = set(children) - allowed
            if extra:
                issues.append(Issue("P1", loc, f"模板 children 出现未知字段：{sorted(extra)}"))
            path = children.get("path")
            template_id = children.get("componentId")
            if not isinstance(path, str) or not path:
                issues.append(Issue("P0", loc, "模板 children 缺少有效 `path`"))
            if not isinstance(template_id, str) or template_id not in ids:
                issues.append(Issue("P0", loc, "模板 children 的 `componentId` 不存在"))
            for name_key in ("itemVar", "indexVar"):
                if name_key in children:
                    val = children[name_key]
                    if not isinstance(val, str) or not IDENT_RE.match(val) or val.startswith("$"):
                        issues.append(Issue("P1", f"{loc}.{name_key}", "变量名不合法", "不带 `$`，并匹配 `^[a-zA-Z_][a-zA-Z0-9_]*$`"))
        else:
            issues.append(Issue("P0", loc, "children 必须是字符串数组或模板对象"))

    return {"issues": issues, "root_size": root_size}


def check_event(value: Any, location: str, issues: list[Issue]) -> None:
    if not isinstance(value, list) or not value:
        issues.append(Issue("P0", location, "事件值必须是非空 EventHandler 数组"))
        return
    for i, handler in enumerate(value):
        loc = f"{location}[{i}]"
        if not isinstance(handler, dict):
            issues.append(Issue("P0", loc, "EventHandler 必须是 object"))
            continue
        call = handler.get("call")
        if not isinstance(call, str) or not call:
            issues.append(Issue("P0", f"{loc}.call", "EventHandler 缺少有效 call"))
        elif "{{" in call:
            issues.append(Issue("P0", f"{loc}.call", "call 不支持表达式"))
        elif call not in KNOWN_EVENT_CALLS:
            issues.append(Issue("P1", f"{loc}.call", f"`{call}` 不在当前 click-event manifest 中", "若为宿主自定义函数，需要明确 catalog 已注册"))
        if "as" in handler:
            as_name = handler["as"]
            if not isinstance(as_name, str) or not IDENT_RE.match(as_name) or as_name.startswith("$"):
                issues.append(Issue("P1", f"{loc}.as", "as 变量名不合法或错误携带 `$` 前缀"))
        if "condition" in handler:
            cond = handler["condition"]
            if not isinstance(cond, str) or "{{" not in cond:
                issues.append(Issue("P1", f"{loc}.condition", "condition 应为表达式字符串"))


def parse_cardspec(text: str | None) -> tuple[dict[str, Any] | None, list[Issue]]:
    if not text:
        return None, []
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, [Issue("P0", "cardspec", f"JSON 解析失败：{exc.msg}")]
    if not isinstance(obj, dict):
        return None, [Issue("P0", "cardspec", "CardSpec 必须是 JSON object")]
    return obj, []


def check_cardspec(cardspec: dict[str, Any] | None, root_size: tuple[Any, Any] | None) -> list[Issue]:
    issues: list[Issue] = []
    if cardspec is None:
        issues.append(Issue("P1", "cardspec", "未提供 CardSpec；若这是完整卡片结果，应补充 cardspec 代码块"))
        return issues
    size = cardspec.get("suggestSize")
    if size not in {"2x2", "2x4"}:
        issues.append(Issue("P0", "cardspec.suggestSize", "必须是 `2x2` 或 `2x4`"))
    if root_size:
        width, height = root_size
        inferred = "2x2" if (width, height) == (160, 160) else "2x4" if (width, height) == (320, 160) else None
        if inferred and size and inferred != size:
            issues.append(Issue("P0", "cardspec.suggestSize", f"与 root 尺寸 {width}x{height} 不一致", f"改为 `{inferred}` 或调整 DSL root 尺寸"))
    bindings = cardspec.get("dataBindings")
    if bindings is None:
        return issues
    if not isinstance(bindings, list):
        issues.append(Issue("P0", "cardspec.dataBindings", "必须是数组"))
        return issues
    seen_write: list[str] = []
    for i, binding in enumerate(bindings):
        loc = f"cardspec.dataBindings[{i}]"
        if not isinstance(binding, dict):
            issues.append(Issue("P0", loc, "binding 必须是 object"))
            continue
        cap = binding.get("capabilityId")
        if cap not in KNOWN_DATA_CAPABILITIES:
            issues.append(Issue("P1", f"{loc}.capabilityId", f"`{cap}` 不在当前 data-capability manifest 中", "补充 capability manifest 或改为静态降级"))
        args = binding.get("arguments")
        if args is not None and not isinstance(args, dict):
            issues.append(Issue("P0", f"{loc}.arguments", "arguments 必须是 object"))
        write_to = binding.get("writeResultTo")
        if not isinstance(write_to, str) or not write_to.startswith("/data/"):
            issues.append(Issue("P0", f"{loc}.writeResultTo", "必须是 `/data/...` JSON Pointer"))
        else:
            for prev in seen_write:
                if write_to == prev or write_to.startswith(prev + "/") or prev.startswith(write_to + "/"):
                    issues.append(Issue("P0", f"{loc}.writeResultTo", f"与 `{prev}` 重复或互为父子路径"))
            seen_write.append(write_to)
        for forbidden in ("functionCall", "supportedTargets", "onClick"):
            if forbidden in binding:
                issues.append(Issue("P0", f"{loc}.{forbidden}", "CardSpec 不应包含点击事件能力"))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Input file path, or '-' for stdin")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    args = parser.parse_args()

    text = read_input(args.input)
    genui_text, cardspec_text = split_payload(text)
    messages, issues = parse_jsonl(genui_text)
    context = {"root_size": None}
    if messages:
        more, context = check_messages(messages)
        issues.extend(more)
    cardspec, cs_issues = parse_cardspec(cardspec_text)
    issues.extend(cs_issues)
    issues.extend(check_cardspec(cardspec, context.get("root_size")))

    order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    issues.sort(key=lambda item: (order.get(item.severity, 9), item.location))
    if args.json:
        print(json.dumps([issue.__dict__ for issue in issues], ensure_ascii=False, indent=2))
    else:
        if not issues:
            print("未发现结构性问题。仍需按 skill 进行视觉、布局、能力 manifest 和业务语义复核。")
        else:
            print(f"发现 {len(issues)} 个问题：")
            for issue in issues:
                print(issue.line())
    return 1 if any(issue.severity == "P0" for issue in issues) else 0


if __name__ == "__main__":
    raise SystemExit(main())
