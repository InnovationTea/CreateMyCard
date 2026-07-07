#!/usr/bin/env python3
"""Validate Harmony A2UI Form card drafts.

The validator catches deterministic protocol errors and common layout risks.
It is intentionally conservative: warnings should be reviewed before delivery.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable


ALLOWED_COMPONENTS = {
    "Text",
    "Image",
    "Divider",
    "Progress",
    "Button",
    "Checkbox",
    "Row",
    "Column",
    "List",
    "Stack",
}

BANNED_KEYS = {
    "theme",
    "action",
    "onAppear",
    "onChange",
    "onSelect",
    "onReachStart",
    "onReachEnd",
}

BANNED_COMPONENTS = {
    "TextInput",
    "Toggle",
    "Radio",
    "CheckboxGroup",
    "Select",
    "NavContainer",
    "Tabs",
    "TabContent",
    "Web",
    "Grid",
    "If",
}

FONT_SIZES = {10, 12, 14, 16, 18, 20, 32, 40}
SPACING = {0, 2, 4, 6, 8, 10, 12, 14, 16}
ORDER = ["createSurface", "updateComponents", "updateDataModel"]
COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
INTERP_RE = re.compile(r"\$\{([^}]+)\}")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")

EVENT_CAPABILITIES = {
    "clickToCallPhone": {"phoneNumber"},
    "clickToDeeplink": {"bundleName", "abilityName", "uri"},
    "clickToIntent": {"intentName", "params"},
}


class Reporter:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def print(self) -> None:
        for message in self.errors:
            print(f"ERROR: {message}")
        for message in self.warnings:
            print(f"WARN: {message}")
        if not self.errors and not self.warnings:
            print("OK: no deterministic issues found")


def extract_blocks(raw: str) -> tuple[str, str]:
    genui = re.search(r"```genui\s*(.*?)```", raw, re.S | re.I)
    cardspec = re.search(r"```cardspec\s*(.*?)```", raw, re.S | re.I)
    if genui and cardspec:
        return genui.group(1).strip(), cardspec.group(1).strip()

    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    json_lines = [line for line in lines if line.startswith("{")]
    if len(json_lines) >= 4:
        return "\n".join(json_lines[:3]), "\n".join(json_lines[3:])
    raise ValueError("Input must contain genui and cardspec blocks, or three JSONL lines plus cardspec JSON.")


def load_jsonl(genui_text: str, reporter: Reporter) -> list[dict[str, Any]]:
    lines = [line.strip() for line in genui_text.splitlines() if line.strip()]
    if len(lines) != 3:
        reporter.error(f"genui must contain exactly 3 JSONL lines, found {len(lines)}.")
    result = []
    for index, line in enumerate(lines[:3], 1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            reporter.error(f"genui line {index} is invalid JSON: {exc}.")
            continue
        if not isinstance(value, dict):
            reporter.error(f"genui line {index} must be a JSON object.")
            continue
        result.append(value)
    return result


def load_cardspec(cardspec_text: str, reporter: Reporter) -> dict[str, Any]:
    try:
        value = json.loads(cardspec_text)
    except json.JSONDecodeError as exc:
        reporter.error(f"cardspec is invalid JSON: {exc}.")
        return {}
    if not isinstance(value, dict):
        reporter.error("cardspec must be a JSON object.")
        return {}
    return value


def walk(value: Any, path: str = "$") -> Iterable[tuple[str, Any]]:
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, f"{path}[{index}]")


def read_pointer(data: Any, pointer: str) -> tuple[bool, Any]:
    if not pointer.startswith("/"):
        return False, None
    current = data
    if pointer == "/":
        return True, current
    for part in pointer.strip("/").split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return False, None
    return True, current


def numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.fullmatch(r"(-?\d+(?:\.\d+)?)(?:vp|fp|px)?", value.strip())
        if match:
            return float(match.group(1))
    return None


def padding_tuple(value: Any) -> tuple[float, float, float, float]:
    if value is None:
        return 0, 0, 0, 0
    if (num := numeric(value)) is not None:
        return num, num, num, num
    if isinstance(value, dict):
        top = numeric(value.get("top")) or 0
        right = numeric(value.get("right")) or 0
        bottom = numeric(value.get("bottom")) or 0
        left = numeric(value.get("left")) or 0
        return top, right, bottom, left
    return 0, 0, 0, 0


def estimate_text_width(text: str, font_size: float) -> float:
    width = 0.0
    for char in text:
        if CJK_RE.match(char):
            width += font_size
        elif char.isspace():
            width += 0.35 * font_size
        elif char in ".,;:!?'\"°%/|":
            width += 0.4 * font_size
        else:
            width += 0.6 * font_size
    return width


def normalize_text(text: str) -> str:
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[：:，,。.!！?？|/\\-]", "", text)
    return text


def content_to_string(value: Any, data_model: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if set(value.keys()) == {"path"}:
            ok, result = read_pointer(data_model, value["path"])
            return "" if not ok or result is None else str(result)
        if value.get("call") == "formatString":
            template = value.get("args", {}).get("value")
            if isinstance(template, str):
                def repl(match: re.Match[str]) -> str:
                    pointer = match.group(1)
                    ok, result = read_pointer(data_model, pointer)
                    return "" if not ok or result is None else str(result)

                return INTERP_RE.sub(repl, template)
    return None


def collect_token_colors() -> set[str]:
    script = Path(__file__).resolve()
    color_files = [
        script.parent.parent / "reference" / "design" / "color-token-system.md",
        script.parent.parent / "reference" / "design" / "color-token-values.md",
    ]
    text = ""
    for color_file in color_files:
        if color_file.exists():
            text += "\n" + color_file.read_text(encoding="utf-8")
    return {color.upper() for color in re.findall(r"#[0-9a-fA-F]{6,8}", text)}


def collect_asset_sources() -> set[str]:
    script = Path(__file__).resolve()
    asset_file = script.parent.parent / "reference" / "design" / "asset-library.md"
    if not asset_file.exists():
        return set()
    text = asset_file.read_text(encoding="utf-8")
    return set(re.findall(r"`(resources/base/media/[^`]+\.svg)`", text, re.I))


def check_protocol(
    messages: list[dict[str, Any]],
    cardspec: dict[str, Any],
    reporter: Reporter,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    empty: dict[str, Any] = {}
    if len(messages) < 3:
        return empty, empty, empty
    for index, expected in enumerate(ORDER):
        keys = [key for key in messages[index].keys() if key != "version"]
        if messages[index].get("version") != "v0.9":
            reporter.error(f"line {index + 1} version must be v0.9.")
        if expected not in messages[index]:
            reporter.error(f"line {index + 1} must contain {expected}.")
        if len(keys) != 1:
            reporter.error(f"line {index + 1} must contain only version and {expected}.")

    create = messages[0].get("createSurface", {})
    update = messages[1].get("updateComponents", {})
    data = messages[2].get("updateDataModel", {})
    if not isinstance(create, dict) or not isinstance(update, dict) or not isinstance(data, dict):
        reporter.error("createSurface, updateComponents, and updateDataModel must be objects.")
        return empty, empty, empty

    if create.get("catalogId") != "ohos.a2ui.extended.catalog":
        reporter.error("createSurface.catalogId must be ohos.a2ui.extended.catalog.")
    if create.get("surfaceId") != update.get("surfaceId") or create.get("surfaceId") != data.get("surfaceId"):
        reporter.error("surfaceId must match across all genui messages.")

    size = cardspec.get("suggestSize")
    width, height = create.get("width"), create.get("height")
    if size == "2x2":
        if width != 140 or height != 140:
            reporter.error("2x2 cards must use createSurface width 140 and height 140.")
    elif size == "2x4":
        if width != 300 or height != 140:
            reporter.error("2x4 cards must use createSurface width 300 and height 140.")
    else:
        reporter.error('cardspec.suggestSize must be "2x2" or "2x4".')

    if any(key in cardspec for key in ("onClick", "events", "click", "actions")):
        reporter.error("CardSpec must not contain click behavior.")

    return create, update, data


def check_components(update: dict[str, Any], data_msg: dict[str, Any], cardspec: dict[str, Any], reporter: Reporter) -> None:
    components = update.get("components")
    if not isinstance(components, list):
        reporter.error("updateComponents.components must be a list.")
        return

    root_id = update.get("root")
    by_id: dict[str, dict[str, Any]] = {}
    for comp in components:
        if not isinstance(comp, dict):
            reporter.error("Every component must be an object.")
            continue
        cid = comp.get("id")
        if not isinstance(cid, str) or not cid:
            reporter.error("Every component must have a non-empty string id.")
            continue
        if cid in by_id:
            reporter.error(f"Duplicate component id: {cid}.")
        by_id[cid] = comp

    if root_id not in by_id:
        reporter.error("updateComponents.root must reference an existing component id.")
        return

    data_model = data_msg.get("value", {})
    token_colors = collect_token_colors()
    asset_sources = collect_asset_sources()

    for comp in components:
        cid = comp.get("id", "<unknown>")
        ctype = comp.get("component")
        if ctype in BANNED_COMPONENTS:
            reporter.error(f"{cid}: banned component {ctype}.")
        elif ctype not in ALLOWED_COMPONENTS:
            reporter.error(f"{cid}: unsupported component {ctype}.")

        for path, value in walk(comp):
            key = path.rsplit(".", 1)[-1].split("[", 1)[0]
            if key in BANNED_KEYS:
                reporter.error(f"{cid}: banned key {key}.")
            if key.startswith("on") and key != "onClick":
                reporter.error(f"{cid}: only onClick event is allowed, found {key}.")
            if isinstance(value, str):
                value_lower = value.lower()
                if value.startswith("http://") or value.startswith("https://"):
                    reporter.error(f"{cid}: network URL is not allowed at {path}.")
                if "data:image/svg" in value_lower:
                    reporter.error(f"{cid}: inline/base64 SVG is not allowed at {path}.")
                elif value_lower.endswith(".svg"):
                    if value.startswith("resources/base/media/") and value not in asset_sources:
                        reporter.error(f"{cid}: SVG path at {path} is not declared in asset-library.md.")
                    elif not value.startswith("resources/base/media/"):
                        reporter.warn(f"{cid}: SVG at {path} must be user-provided or declared in asset-library.md.")
                if key.endswith("Color") or key in {"color", "backgroundColor", "borderColor", "fontColor"}:
                    check_color(value, token_colors, f"{cid}:{path}", reporter)

        check_children(comp, by_id, reporter)
        check_events(comp, reporter)
        check_bindings(comp, data_model, reporter)
        check_style(comp, token_colors, reporter)
        check_text_fit(comp, data_model, reporter)

    check_root(by_id[root_id], cardspec, reporter)
    check_layout(by_id[root_id], by_id, reporter)
    check_duplicates(components, data_model, reporter)
    check_button_rows(components, by_id, reporter)


def check_color(value: str, token_colors: set[str], location: str, reporter: Reporter) -> None:
    if not COLOR_RE.fullmatch(value):
        reporter.error(f"{location}: color must be #RRGGBB or #AARRGGBB, found {value}.")
        return
    if token_colors and value.upper() not in token_colors:
        reporter.error(f"{location}: color {value} is not found in color-token-system.md.")


def check_children(comp: dict[str, Any], by_id: dict[str, dict[str, Any]], reporter: Reporter) -> None:
    cid = comp.get("id", "<unknown>")
    children = comp.get("children")
    if children is None:
        return
    if isinstance(children, list):
        for child in children:
            if not isinstance(child, str):
                reporter.error(f"{cid}: children must be flat component id strings.")
            elif child not in by_id:
                reporter.error(f"{cid}: child id {child} does not exist.")
    elif isinstance(children, dict):
        if set(children.keys()) != {"componentId", "path"}:
            reporter.error(f"{cid}: template children must contain only componentId and path.")
        if children.get("componentId") not in by_id:
            reporter.error(f"{cid}: template componentId does not exist.")
        if not isinstance(children.get("path"), str) or not children["path"].startswith("/"):
            reporter.error(f"{cid}: template path must be an absolute JSON Pointer.")
    else:
        reporter.error(f"{cid}: children must be a list or template object.")


def check_events(comp: dict[str, Any], reporter: Reporter) -> None:
    cid = comp.get("id", "<unknown>")
    handlers = comp.get("onClick")
    if handlers is None:
        return
    if not isinstance(handlers, list):
        reporter.error(f"{cid}: onClick must be an array.")
        return
    for handler in handlers:
        if not isinstance(handler, dict):
            reporter.error(f"{cid}: onClick handler must be an object.")
            continue
        call = handler.get("call")
        if call not in EVENT_CAPABILITIES:
            reporter.error(f"{cid}: unknown event capability {call}.")
            continue
        args = handler.get("args", {})
        if not isinstance(args, dict):
            reporter.error(f"{cid}: event args must be an object.")
            continue
        extra = set(args.keys()) - EVENT_CAPABILITIES[call]
        missing = EVENT_CAPABILITIES[call] - set(args.keys())
        if extra:
            reporter.error(f"{cid}: event {call} has unsupported args {sorted(extra)}.")
        if missing:
            reporter.error(f"{cid}: event {call} missing args {sorted(missing)}.")
        if call == "clickToCallPhone" and set(args.keys()) != {"phoneNumber"}:
            reporter.error(f"{cid}: clickToCallPhone args must contain only phoneNumber.")


def check_bindings(comp: dict[str, Any], data_model: Any, reporter: Reporter) -> None:
    cid = comp.get("id", "<unknown>")
    for path, value in walk(comp):
        if isinstance(value, dict) and set(value.keys()) == {"path"}:
            pointer = value["path"]
            if isinstance(pointer, str) and pointer.startswith("/"):
                ok, _ = read_pointer(data_model, pointer)
                if not ok:
                    reporter.error(f"{cid}: binding path {pointer} at {path} is missing in DataModel.")
        if isinstance(value, dict) and value.get("call") == "formatString":
            template = value.get("args", {}).get("value")
            if not isinstance(template, str):
                reporter.error(f"{cid}: formatString args.value must be a string.")
                continue
            for pointer in INTERP_RE.findall(template):
                if pointer.startswith("/"):
                    ok, _ = read_pointer(data_model, pointer)
                    if not ok:
                        reporter.error(f"{cid}: formatString path {pointer} is missing in DataModel.")


def check_style(comp: dict[str, Any], token_colors: set[str], reporter: Reporter) -> None:
    cid = comp.get("id", "<unknown>")
    styles = comp.get("styles", {})
    if not isinstance(styles, dict):
        reporter.error(f"{cid}: styles must be an object.")
        return

    font_size = numeric(styles.get("fontSize"))
    if font_size is not None and int(font_size) not in FONT_SIZES:
        reporter.error(f"{cid}: fontSize {font_size:g} is outside the approved scale.")

    overflow = styles.get("textOverflow")
    if overflow in {"ellipsis", "clip", "marquee"}:
        reporter.error(f"{cid}: textOverflow {overflow} is not allowed for generated protected text.")

    for key in ("padding", "margin"):
        value = styles.get(key)
        values = padding_tuple(value)
        for item in values:
            if item not in SPACING:
                reporter.warn(f"{cid}: {key} value {item:g} is outside the spacing scale.")

    for key in ("itemMargin", "space"):
        value = numeric(comp.get(key))
        if value is not None and value not in SPACING:
            reporter.warn(f"{cid}: {key} {value:g} is outside the spacing scale.")

    gradient = styles.get("linearGradient")
    if isinstance(gradient, dict):
        colors = gradient.get("colors", [])
        if not isinstance(colors, list) or not colors:
            reporter.error(f"{cid}: linearGradient.colors must be a non-empty list.")
        for stop in colors:
            if not (isinstance(stop, list) and len(stop) == 2 and isinstance(stop[0], str)):
                reporter.error(f"{cid}: each gradient stop must be [color, offset].")
            else:
                check_color(stop[0], token_colors, f"{cid}:linearGradient", reporter)

    if comp.get("component") == "Image":
        if "src" not in comp:
            reporter.error(f"{cid}: Image must have src.")
        if numeric(styles.get("width")) is None or numeric(styles.get("height")) is None:
            reporter.error(f"{cid}: Image must have explicit numeric width and height.")
        if styles.get("objectFit") != "contain":
            reporter.warn(f"{cid}: Image should use objectFit contain unless deliberately cropped.")


def check_text_fit(comp: dict[str, Any], data_model: Any, reporter: Reporter) -> None:
    cid = comp.get("id", "<unknown>")
    ctype = comp.get("component")
    styles = comp.get("styles", {})
    if not isinstance(styles, dict):
        return

    if ctype == "Text":
        text = content_to_string(comp.get("content"), data_model)
        if text is None:
            return
        font = numeric(styles.get("fontSize")) or 14
        width = numeric(styles.get("width"))
        max_lines = int(numeric(styles.get("maxLines")) or 1)
        if width is not None:
            estimate = estimate_text_width(text, font)
            if estimate > width * max_lines:
                reporter.error(f"{cid}: text {text!r} estimated width {estimate:.1f} exceeds {width:g} x {max_lines} lines.")

    if ctype == "Button":
        label = content_to_string(comp.get("label"), data_model)
        if label is None:
            return
        font = numeric(styles.get("fontSize")) or 14
        width = numeric(styles.get("width"))
        height = numeric(styles.get("height"))
        if height is not None and height < 24:
            reporter.error(f"{cid}: Button height must be at least 24.")
        if width is not None:
            estimate = estimate_text_width(label, font) + 16
            if estimate > width:
                reporter.error(f"{cid}: Button label {label!r} may not fit width {width:g}.")


def check_root(root: dict[str, Any], cardspec: dict[str, Any], reporter: Reporter) -> None:
    cid = root.get("id", "root")
    styles = root.get("styles", {})
    size = cardspec.get("suggestSize")
    width = numeric(styles.get("width"))
    height = numeric(styles.get("height"))
    radius = numeric(styles.get("borderRadius"))
    clip = styles.get("clip")

    expected = (140, 140, 18) if size == "2x2" else (300, 140, 22)
    if width != expected[0] or height != expected[1]:
        reporter.error(f"{cid}: root width/height must be {expected[0]} x {expected[1]}.")
    if radius != expected[2] or clip is not True:
        reporter.error(f"{cid}: root must use borderRadius {expected[2]} and clip true.")
    pad = padding_tuple(styles.get("padding"))
    if pad != (12, 12, 12, 12):
        reporter.warn(f"{cid}: root padding should be 12 on all sides for the default safe area.")


def check_layout(root: dict[str, Any], by_id: dict[str, dict[str, Any]], reporter: Reporter) -> None:
    for comp in by_id.values():
        ctype = comp.get("component")
        if ctype not in {"Row", "Column"}:
            continue
        cid = comp.get("id", "<unknown>")
        styles = comp.get("styles", {})
        children = comp.get("children")
        if not isinstance(children, list) or not all(isinstance(child, str) for child in children):
            continue

        width = numeric(styles.get("width"))
        height = numeric(styles.get("height"))
        pad_top, pad_right, pad_bottom, pad_left = padding_tuple(styles.get("padding"))
        gap = numeric(comp.get("itemMargin")) or 0
        child_components = [by_id[child] for child in children if child in by_id]

        if ctype == "Row" and width is not None:
            used = pad_left + pad_right + gap * max(0, len(child_components) - 1)
            unknown = False
            for child in child_components:
                child_width = numeric(child.get("styles", {}).get("width"))
                if child_width is None:
                    unknown = True
                else:
                    used += child_width
            if not unknown and used > width:
                reporter.error(f"{cid}: Row children use {used:g} width, exceeding {width:g}.")
            if height is not None:
                inner = height - pad_top - pad_bottom
                for child in child_components:
                    child_height = numeric(child.get("styles", {}).get("height"))
                    if child_height is not None and child_height > inner:
                        reporter.error(f"{cid}: child {child.get('id')} height {child_height:g} exceeds Row inner height {inner:g}.")

        if ctype == "Column" and height is not None:
            used = pad_top + pad_bottom + gap * max(0, len(child_components) - 1)
            unknown = False
            for child in child_components:
                child_height = numeric(child.get("styles", {}).get("height"))
                if child_height is None:
                    unknown = True
                else:
                    used += child_height
            if not unknown and used > height:
                reporter.error(f"{cid}: Column children use {used:g} height, exceeding {height:g}.")
            if width is not None:
                inner = width - pad_left - pad_right
                for child in child_components:
                    child_width = numeric(child.get("styles", {}).get("width"))
                    if child_width is not None and child_width > inner:
                        reporter.error(f"{cid}: child {child.get('id')} width {child_width:g} exceeds Column inner width {inner:g}.")

    if root.get("component") == "Column":
        check_bottom_anchor(root, by_id, reporter)


def check_bottom_anchor(root: dict[str, Any], by_id: dict[str, dict[str, Any]], reporter: Reporter) -> None:
    styles = root.get("styles", {})
    height = numeric(styles.get("height"))
    children = root.get("children")
    if height is None or not isinstance(children, list) or not children:
        return
    pad_top, _, pad_bottom, _ = padding_tuple(styles.get("padding"))
    gap = numeric(root.get("itemMargin")) or 0
    used = pad_top + pad_bottom + gap * max(0, len(children) - 1)
    unknown = False
    for child_id in children:
        child = by_id.get(child_id)
        child_height = numeric(child.get("styles", {}).get("height")) if child else None
        if child_height is None:
            unknown = True
        else:
            used += child_height
    if unknown:
        return
    bottom_gap = height - used + pad_bottom
    if bottom_gap > 16:
        reporter.error(f"root: last section bottom gap is {bottom_gap:g}, exceeding 16.")
    elif bottom_gap < 8:
        reporter.warn(f"root: last section bottom gap is {bottom_gap:g}; typical 2x2/2x4 bottom gap is 8-14.")


def check_duplicates(components: list[dict[str, Any]], data_model: Any, reporter: Reporter) -> None:
    seen: dict[str, str] = {}
    texts: list[tuple[str, str]] = []
    for comp in components:
        if comp.get("component") == "Text":
            text = content_to_string(comp.get("content"), data_model)
        elif comp.get("component") == "Button":
            text = content_to_string(comp.get("label"), data_model)
        else:
            continue
        if not text:
            continue
        norm = normalize_text(text)
        if len(norm) < 2:
            continue
        cid = comp.get("id", "<unknown>")
        texts.append((cid, norm))
        if norm in seen:
            reporter.error(f"{cid}: duplicate visible text {text!r}; first seen in {seen[norm]}.")
        else:
            seen[norm] = cid

    for index, (cid, text) in enumerate(texts):
        for other_id, other in texts[index + 1:]:
            if len(text) >= 3 and len(other) >= 3 and (text in other or other in text) and text != other:
                reporter.warn(f"{cid} and {other_id}: visible texts may be semantically duplicated ({text!r}, {other!r}).")


def contains_button(comp: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> bool:
    if comp.get("component") == "Button":
        return True
    children = comp.get("children")
    if isinstance(children, list):
        return any(child in by_id and contains_button(by_id[child], by_id) for child in children)
    return False


def contains_text_or_column(comp: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> bool:
    if comp.get("component") in {"Text", "Column"}:
        return True
    children = comp.get("children")
    if isinstance(children, list):
        return any(child in by_id and contains_text_or_column(by_id[child], by_id) for child in children)
    return False


def check_button_rows(components: list[dict[str, Any]], by_id: dict[str, dict[str, Any]], reporter: Reporter) -> None:
    for comp in components:
        if comp.get("component") != "Row":
            continue
        cid = comp.get("id", "<unknown>")
        children = comp.get("children")
        if not isinstance(children, list):
            continue
        child_components = [by_id[child] for child in children if isinstance(child, str) and child in by_id]
        direct_buttons = [child for child in child_components if child.get("component") == "Button"]
        if not direct_buttons:
            continue
        has_text_peer = any(child.get("component") != "Button" and contains_text_or_column(child, by_id) for child in child_components)
        if has_text_peer:
            for button in direct_buttons:
                styles = button.get("styles", {})
                margin = styles.get("margin", {})
                margin_top = numeric(margin.get("top")) if isinstance(margin, dict) else None
                parent_padding = padding_tuple(comp.get("styles", {}).get("padding", {}))
                if margin_top is None and parent_padding[0] == parent_padding[2]:
                    reporter.warn(f"{cid}: Button {button.get('id')} sits beside text without margin.top or asymmetric padding; baseline may render high.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Harmony A2UI Form card drafts.")
    parser.add_argument("path", nargs="?", help="Draft file. Reads stdin when omitted or '-'.")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
    args = parser.parse_args()

    raw = sys.stdin.read() if not args.path or args.path == "-" else Path(args.path).read_text(encoding="utf-8")
    reporter = Reporter()
    try:
        genui_text, cardspec_text = extract_blocks(raw)
    except ValueError as exc:
        reporter.error(str(exc))
        reporter.print()
        return 1

    messages = load_jsonl(genui_text, reporter)
    cardspec = load_cardspec(cardspec_text, reporter)
    if len(messages) >= 3:
        _, update, data = check_protocol(messages, cardspec, reporter)
        if update:
            check_components(update, data, cardspec, reporter)

    reporter.print()
    if reporter.errors or (args.strict and reporter.warnings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
