# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact DSL protocol prompt and validation in one isolated module."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, TypedDict, TypeGuard
from urllib.parse import urlparse

COMPACT_DSL_FORMAT = "compact-dsl"

COMPONENT_WHITELIST = (
    "Row",
    "Column",
    "List",
    "Stack",
    "Grid",
    "Text",
    "Image",
    "Divider",
    "Progress",
    "Button",
    "TextInput",
    "Radio",
    "Toggle",
    "Checkbox",
    "Select",
    "Web",
)

CONTAINER_COMPONENTS = {"Row", "Column", "List", "Stack", "Grid"}
ROOT_COMPONENTS = {"Column", "Stack"}
FORM_COMPONENTS = {"TextInput", "Radio", "Toggle", "Checkbox", "Select"}

REQUIRED_PROPS: dict[str, tuple[str, ...]] = {
    "Row": ("space",),
    "Column": ("space",),
    "List": ("space",),
    "Stack": (),
    "Grid": (),
    "Text": ("content",),
    "Image": ("src",),
    "Divider": (),
    "Progress": ("value", "total"),
    "Button": ("label", "enabled", "action"),
    "TextInput": ("text", "placeholder", "enabled", "maxLength", "type"),
    "Radio": ("value", "checked", "group", "indicatorType"),
    "Toggle": ("label", "isOn", "enabled"),
    "Checkbox": ("label", "group", "select"),
    "Select": ("options", "selected", "value"),
    "Web": ("url",),
}


class _PathBinding(TypedDict):
    path: str


def is_compact_dsl(protocol_profile: dict[str, Any]) -> bool:
    """Return whether a loaded profile uses tuple-based Compact DSL."""
    return protocol_profile.get("format") == COMPACT_DSL_FORMAT


def build_compact_dsl_system_prompt(protocol_profile: dict[str, Any]) -> str:
    """Build the compact, self-contained model contract for Compact DSL."""
    allowed = ", ".join(protocol_profile.get("componentWhitelist", COMPONENT_WHITELIST))
    return "\n".join(
        [
            "Generate HarmonyOS Compact DSL as raw NDJSON only.",
            "Do not output Markdown fences, prose, a JSON envelope, createSurface, "
            "updateComponents, or updateDataModel.",
            'A component line is ["<id>","<Type>",{<props>},["<childId>",...]]; '
            "the children array is required only for Row, Column, List, Stack, and Grid.",
            'A data line is ["/<json-pointer>",<value>]. Each physical line must be one '
            "complete compact JSON array.",
            'The first line must be ["root","Column"|"Stack",{...},children]. Root props '
            'must include "width":"matchParent".',
            "Declare parents before children. Every non-root component ID must first appear "
            "in an earlier parent's children array, and every child ID must be created later.",
            "Write component props directly in the props object; never use an A2UI styles wrapper.",
            'A string-valued prop may be a literal string or {"path":"/..."}. Every path '
            "binding must have a data line in the same output; initialize UI value bindings "
            "after the component line. TextInput.text must use a path binding.",
            "Use literal props for fixed text and path bindings for values that need DataModel "
            "binding or updates.",
            f"Allowed component types only: {allowed}.",
            "Required props: Row/Column/List space:number; Text content:string|path; "
            "Image src:string|path; Progress value:number,total:number; Button "
            "label:string|path,enabled:boolean,action:object.",
            "Required form props: TextInput text:path,placeholder:string,enabled:boolean,"
            "maxLength:integer,type:normal|email|password|number; Radio value:string,"
            "checked:boolean,group:string,indicatorType:tick|dot; Toggle label:string,"
            "isOn:boolean,enabled:boolean; Checkbox label:string,group:string,select:boolean; "
            "Select options:array,selected:integer,value:string; Web url:http/https string.",
            "Prefer the core display set Row, Column, List, Stack, Text, Image, Divider, "
            "Progress, and Button. Use TextInput, Radio, Toggle, Checkbox, or Select only when "
            "the user explicitly needs input or selection. Use Grid only for an explicit grid "
            "layout and Web only for an explicit embedded web page.",
            "Button.action must contain exactly one of functionCall or event. A non-image URL "
            "uses functionCall.call=openUrl with a real http/https args.url. Form controls must "
            "be followed by a Button.action.event that submits their values.",
            "For submit_form event.context use path for TextInput, getRadioValue(group) for "
            "Radio, getCheckboxGroupValues(group) for Checkbox, getToggleValue(componentID) "
            "for Toggle, and getSelectValue(componentID) for Select.",
            "Preserve facts, numbers, media paths, and URLs from taskSpec. Do not invent business "
            "data, URLs, icons, or decorative content.",
        ]
    )


@dataclass(frozen=True)
class CompactDSLValidationReport:
    errors: list[str]
    warnings: list[str]

    def passed(self, strict: bool = False) -> bool:
        return not self.errors and (not strict or not self.warnings)


@dataclass(frozen=True)
class _ComponentRecord:
    line: int
    component_id: str
    component_type: str
    props: dict[str, Any]
    children: list[str]


class _Reporter:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)


def validate_compact_dsl(
    genui_text: str,
    cardspec: dict[str, Any] | str,
    component_whitelist: list[str] | tuple[str, ...] | None = None,
    strict: bool = False,
) -> CompactDSLValidationReport:
    """Validate raw tuple-based GenUI NDJSON and its CardSpec boundary."""
    reporter = _Reporter()
    allowed = set(component_whitelist or COMPONENT_WHITELIST)
    _check_cardspec(cardspec, reporter)

    if "```" in genui_text:
        reporter.error("genui must be raw NDJSON without Markdown fences.")

    components: dict[str, _ComponentRecord] = {}
    component_order: list[_ComponentRecord] = []
    data_rows: dict[str, list[tuple[int, Any]]] = defaultdict(list)
    record_order: list[tuple[str, int, str]] = []

    for line_number, raw_line in enumerate(genui_text.splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            reporter.error(f"genui line {line_number} is invalid JSON: {exc}.")
            continue
        if not isinstance(value, list):
            reporter.error(f"genui line {line_number} must be a JSON array.")
            continue

        if value and isinstance(value[0], str) and value[0].startswith("/"):
            _read_data_line(value, line_number, data_rows, record_order, reporter)
            continue
        component = _read_component_line(value, line_number, allowed, reporter)
        if component is None:
            continue
        record_order.append(("component", line_number, component.component_id))
        if component.component_id in components:
            reporter.error(f"line {line_number}: duplicate component id {component.component_id}.")
            continue
        components[component.component_id] = component
        component_order.append(component)

    if not record_order:
        reporter.error("genui must contain at least one NDJSON line.")
    else:
        first_kind, first_line, first_key = record_order[0]
        if first_kind != "component" or first_key != "root":
            reporter.error(f'line {first_line}: first genui line must create component "root".')

    _check_component_tree(components, component_order, reporter)
    _check_bindings(component_order, data_rows, reporter)
    _check_form_submission(component_order, reporter)

    errors = reporter.errors + reporter.warnings if strict else reporter.errors
    return CompactDSLValidationReport(errors=errors, warnings=reporter.warnings)


def _read_data_line(
    value: list[Any],
    line_number: int,
    data_rows: dict[str, list[tuple[int, Any]]],
    record_order: list[tuple[str, int, str]],
    reporter: _Reporter,
) -> None:
    if len(value) != 2:
        reporter.error(f"line {line_number}: data line must contain exactly 2 items.")
        return
    path = value[0]
    if not isinstance(path, str) or not _is_json_pointer(path):
        reporter.error(f"line {line_number}: data path must be an absolute JSON Pointer.")
        return
    data_rows[path].append((line_number, value[1]))
    record_order.append(("data", line_number, path))


def _read_component_line(
    value: list[Any],
    line_number: int,
    allowed: set[str],
    reporter: _Reporter,
) -> _ComponentRecord | None:
    if len(value) not in {3, 4}:
        reporter.error(f"line {line_number}: component line must contain 3 or 4 items.")
        return None
    component_id, component_type, props = value[:3]
    if not isinstance(component_id, str) or not component_id or component_id.startswith("/"):
        reporter.error(f"line {line_number}: component id must be a non-empty non-path string.")
        return None
    if not isinstance(component_type, str):
        reporter.error(f"line {line_number}: component type must be a string.")
        return None
    if component_type not in allowed:
        reporter.error(f"{component_id}: unsupported component {component_type}.")
    if not isinstance(props, dict):
        reporter.error(f"{component_id}: props must be a JSON object.")
        return None
    if "styles" in props:
        reporter.error(f"{component_id}: props must not contain an A2UI styles wrapper.")

    children: list[str] = []
    if component_type in CONTAINER_COMPONENTS:
        if len(value) != 4:
            reporter.error(f"{component_id}: {component_type} requires a children array.")
        elif not isinstance(value[3], list) or not all(
            isinstance(child, str) and child for child in value[3]
        ):
            reporter.error(f"{component_id}: children must be an array of non-empty string IDs.")
        else:
            children = value[3]
            if len(children) != len(set(children)):
                reporter.error(f"{component_id}: children must not contain duplicate IDs.")
    elif len(value) == 4:
        reporter.error(f"{component_id}: {component_type} must not have a children array.")

    _check_required_props(component_id, component_type, props, reporter)
    _check_component_prop_types(component_id, component_type, props, reporter)
    return _ComponentRecord(line_number, component_id, component_type, props, children)


def _check_cardspec(cardspec: dict[str, Any] | str, reporter: _Reporter) -> None:
    if isinstance(cardspec, str):
        try:
            cardspec = json.loads(cardspec)
        except json.JSONDecodeError as exc:
            reporter.error(f"cardspec is invalid JSON: {exc}.")
            return
    if not isinstance(cardspec, dict):
        reporter.error("cardspec must be a JSON object.")
        return
    if cardspec.get("suggestSize") not in {"2x2", "2x4"}:
        reporter.error('cardspec.suggestSize must be "2x2" or "2x4".')
    if any(key in cardspec for key in ("onClick", "events", "click", "actions")):
        reporter.error("CardSpec must not contain click behavior.")


def _check_required_props(
    component_id: str,
    component_type: str,
    props: dict[str, Any],
    reporter: _Reporter,
) -> None:
    for key in REQUIRED_PROPS.get(component_type, ()):
        if key not in props:
            reporter.error(f"{component_id}: {component_type} requires prop {key}.")


def _check_component_prop_types(
    component_id: str,
    component_type: str,
    props: dict[str, Any],
    reporter: _Reporter,
) -> None:
    if component_type in {"Row", "Column", "List"} and "space" in props:
        if not _is_number(props["space"]) or props["space"] < 0:
            reporter.error(f"{component_id}: {component_type}.space must be a non-negative number.")
    elif component_type == "Text" and "content" in props:
        _require_string_source(component_id, "content", props["content"], reporter)
    elif component_type == "Image" and "src" in props:
        _require_string_source(component_id, "src", props["src"], reporter)
    elif component_type == "Progress":
        for key in ("value", "total"):
            if key in props and not _is_number(props[key]):
                reporter.error(f"{component_id}: Progress.{key} must be a number.")
        value = props.get("value")
        total = props.get("total")
        if _is_number(value) and not 0 <= value <= 100:
            reporter.error(f"{component_id}: Progress.value must be between 0 and 100.")
        if _is_number(total) and total <= 0:
            reporter.error(f"{component_id}: Progress.total must be greater than 0.")
        if _is_number(value) and _is_number(total) and value > total:
            reporter.error(f"{component_id}: Progress.value must not exceed total.")
    elif component_type == "Button":
        if "label" in props:
            _require_string_source(component_id, "label", props["label"], reporter)
        if "enabled" in props and not isinstance(props["enabled"], bool):
            reporter.error(f"{component_id}: Button.enabled must be a boolean.")
        if "action" in props:
            _check_button_action(component_id, props["action"], reporter)
    elif component_type == "TextInput":
        if "text" in props and not _is_path_binding(props["text"]):
            reporter.error(f"{component_id}: TextInput.text must be a path binding object.")
        _require_string_prop(component_id, "TextInput", "placeholder", props, reporter)
        _require_bool_prop(component_id, "TextInput", "enabled", props, reporter)
        max_length = props.get("maxLength")
        if "maxLength" in props and (
            not isinstance(max_length, int) or isinstance(max_length, bool) or max_length <= 0
        ):
            reporter.error(f"{component_id}: TextInput.maxLength must be a positive integer.")
        input_type = props.get("type")
        if "type" in props and input_type not in {"normal", "email", "password", "number"}:
            reporter.error(f"{component_id}: TextInput.type is unsupported.")
    elif component_type == "Radio":
        _require_string_prop(component_id, "Radio", "value", props, reporter)
        _require_string_prop(component_id, "Radio", "group", props, reporter)
        _require_bool_prop(component_id, "Radio", "checked", props, reporter)
        if "indicatorType" in props and props["indicatorType"] not in {"tick", "dot"}:
            reporter.error(f"{component_id}: Radio.indicatorType must be tick or dot.")
    elif component_type == "Toggle":
        _require_string_prop(component_id, "Toggle", "label", props, reporter)
        _require_bool_prop(component_id, "Toggle", "isOn", props, reporter)
        _require_bool_prop(component_id, "Toggle", "enabled", props, reporter)
    elif component_type == "Checkbox":
        _require_string_prop(component_id, "Checkbox", "label", props, reporter)
        _require_string_prop(component_id, "Checkbox", "group", props, reporter)
        _require_bool_prop(component_id, "Checkbox", "select", props, reporter)
    elif component_type == "Select":
        _check_select_props(component_id, props, reporter)
    elif component_type == "Web" and "url" in props:
        url = props["url"]
        if not isinstance(url, str) or not _is_http_url(url):
            reporter.error(f"{component_id}: Web.url must be a complete http/https URL.")


def _require_string_prop(
    component_id: str,
    component_type: str,
    prop_name: str,
    props: dict[str, Any],
    reporter: _Reporter,
) -> None:
    if prop_name in props and not isinstance(props[prop_name], str):
        reporter.error(f"{component_id}: {component_type}.{prop_name} must be a string.")


def _require_bool_prop(
    component_id: str,
    component_type: str,
    prop_name: str,
    props: dict[str, Any],
    reporter: _Reporter,
) -> None:
    if prop_name in props and not isinstance(props[prop_name], bool):
        reporter.error(f"{component_id}: {component_type}.{prop_name} must be a boolean.")


def _check_select_props(
    component_id: str,
    props: dict[str, Any],
    reporter: _Reporter,
) -> None:
    options = props.get("options")
    if "options" in props:
        if not isinstance(options, list) or not options:
            reporter.error(f"{component_id}: Select.options must be a non-empty array.")
        else:
            for index, option in enumerate(options):
                if not isinstance(option, dict) or not isinstance(option.get("value"), str):
                    reporter.error(
                        f"{component_id}: Select.options[{index}].value must be a string."
                    )
    selected = props.get("selected")
    if "selected" in props and (
        not isinstance(selected, int) or isinstance(selected, bool) or selected < 0
    ):
        reporter.error(f"{component_id}: Select.selected must be a non-negative integer.")
    elif (
        isinstance(options, list)
        and options
        and isinstance(selected, int)
        and selected >= len(options)
    ):
        reporter.error(f"{component_id}: Select.selected is outside the options array.")
    _require_string_prop(component_id, "Select", "value", props, reporter)


def _require_string_source(
    component_id: str,
    prop_name: str,
    value: Any,
    reporter: _Reporter,
) -> None:
    if not isinstance(value, str) and not _is_path_binding(value):
        reporter.error(
            f"{component_id}: {prop_name} must be a string literal or path binding object."
        )


def _check_button_action(component_id: str, action: Any, reporter: _Reporter) -> None:
    if not isinstance(action, dict):
        reporter.error(f"{component_id}: Button.action must be an object.")
        return
    action_kinds = set(action) & {"functionCall", "event"}
    if len(action_kinds) != 1 or set(action) != action_kinds:
        reporter.error(
            f"{component_id}: Button.action must contain exactly one of functionCall or event."
        )
        return
    if "functionCall" in action:
        function_call = action["functionCall"]
        if not isinstance(function_call, dict):
            reporter.error(f"{component_id}: Button.action.functionCall must be an object.")
            return
        if not _is_non_empty_string(function_call.get("call")) or not isinstance(
            function_call.get("args"), dict
        ):
            reporter.error(
                f"{component_id}: functionCall requires string call and object args."
            )
            return
        if function_call["call"] == "openUrl":
            url = function_call["args"].get("url")
            if not isinstance(url, str) or not _is_http_url(url):
                reporter.error(
                    f"{component_id}: openUrl args.url must be a complete http/https URL."
                )
    else:
        event = action["event"]
        if not isinstance(event, dict):
            reporter.error(f"{component_id}: Button.action.event must be an object.")
            return
        if not _is_non_empty_string(event.get("name")) or not isinstance(
            event.get("context"), dict
        ):
            reporter.error(f"{component_id}: event requires string name and object context.")


def _check_component_tree(
    components: dict[str, _ComponentRecord],
    component_order: list[_ComponentRecord],
    reporter: _Reporter,
) -> None:
    root = components.get("root")
    if root is None:
        reporter.error('genui must define component "root".')
        return
    if not component_order or component_order[0].component_id != "root":
        reporter.error('the first component line must define component "root".')
    if root.component_type not in ROOT_COMPONENTS:
        reporter.error("root component type must be Column or Stack.")
    if root.props.get("width") != "matchParent":
        reporter.error('root props.width must be "matchParent".')

    parents: dict[str, list[_ComponentRecord]] = defaultdict(list)
    for parent in component_order:
        for child_id in parent.children:
            parents[child_id].append(parent)
            child = components.get(child_id)
            if child is None:
                reporter.error(f"{parent.component_id}: child id {child_id} is never created.")
            elif child.line <= parent.line:
                reporter.error(
                    f"{parent.component_id}: child {child_id} must be created after its parent."
                )

    for component in component_order:
        if component.component_id == "root":
            if component.component_id in parents:
                reporter.error("root must not appear in another component's children.")
            continue
        declared_by = [
            parent
            for parent in parents.get(component.component_id, [])
            if parent.line < component.line
        ]
        if not declared_by:
            reporter.error(
                f"{component.component_id}: component must first appear in an earlier "
                "parent's children."
            )
        elif len(declared_by) > 1:
            reporter.error(
                f"{component.component_id}: component must have exactly one parent, found "
                f"{len(declared_by)}."
            )


def _check_bindings(
    component_order: list[_ComponentRecord],
    data_rows: dict[str, list[tuple[int, Any]]],
    reporter: _Reporter,
) -> None:
    for component in component_order:
        for location, path, initializes_value in _path_bindings(component.props):
            if not _is_json_pointer(path):
                reporter.error(
                    f"{component.component_id}: binding at props.{location} must use an absolute "
                    "JSON Pointer."
                )
                continue
            rows = data_rows.get(path, [])
            if not rows:
                reporter.error(
                    f"{component.component_id}: binding path {path} has no data line in this genui."
                )
                continue
            if initializes_value and not any(line > component.line for line, _ in rows):
                reporter.error(
                    f"{component.component_id}: binding path {path} must be initialized after "
                    "the component line."
                )

        _check_string_binding_value(component, "content", data_rows, reporter)
        _check_string_binding_value(component, "src", data_rows, reporter)
        _check_string_binding_value(component, "label", data_rows, reporter)
        _check_string_binding_value(component, "text", data_rows, reporter)


def _check_string_binding_value(
    component: _ComponentRecord,
    prop_name: str,
    data_rows: dict[str, list[tuple[int, Any]]],
    reporter: _Reporter,
) -> None:
    value = component.props.get(prop_name)
    if not _is_path_binding(value):
        return
    path = value["path"]
    later_values = [item for line, item in data_rows.get(path, []) if line > component.line]
    if later_values and not isinstance(later_values[0], str):
        reporter.error(
            f"{component.component_id}: {prop_name} binding {path} must initialize a string value."
        )


def _check_form_submission(
    component_order: list[_ComponentRecord], reporter: _Reporter
) -> None:
    controls = [item for item in component_order if item.component_type in FORM_COMPONENTS]
    if not controls:
        return
    event_buttons = [
        item
        for item in component_order
        if item.component_type == "Button"
        and isinstance(item.props.get("action"), dict)
        and "event" in item.props["action"]
        and isinstance(item.props["action"]["event"], dict)
        and item.props["action"]["event"].get("name") == "submit_form"
        and isinstance(item.props["action"]["event"].get("context"), dict)
    ]
    if not event_buttons:
        reporter.error("form controls require a Button.action.event named submit_form.")
        return
    last_control_line = max(item.line for item in controls)
    submission_buttons = [button for button in event_buttons if button.line > last_control_line]
    if not submission_buttons:
        reporter.error("Button.action.event must be created after the form controls it submits.")
        return

    contexts = [button.props["action"]["event"]["context"] for button in submission_buttons]
    context_values = [value for context in contexts for value in context.values()]
    _check_radio_groups(controls, reporter)
    for control in controls:
        if control.component_type == "TextInput":
            text_binding = control.props.get("text")
            path = text_binding.get("path") if isinstance(text_binding, dict) else None
            if path and not any(
                _is_path_binding(value) and value["path"] == path for value in context_values
            ):
                reporter.error(
                    f"{control.component_id}: submit_form context must include path {path}."
                )
        elif control.component_type == "Radio":
            _require_context_call(
                control,
                context_values,
                "getRadioValue",
                "group",
                control.props.get("group"),
                reporter,
            )
        elif control.component_type == "Checkbox":
            _require_context_call(
                control,
                context_values,
                "getCheckboxGroupValues",
                "group",
                control.props.get("group"),
                reporter,
            )
        elif control.component_type == "Toggle":
            _require_context_call(
                control,
                context_values,
                "getToggleValue",
                "componentID",
                control.component_id,
                reporter,
            )
        elif control.component_type == "Select":
            _require_context_call(
                control,
                context_values,
                "getSelectValue",
                "componentID",
                control.component_id,
                reporter,
            )


def _check_radio_groups(controls: list[_ComponentRecord], reporter: _Reporter) -> None:
    groups: dict[str, list[_ComponentRecord]] = defaultdict(list)
    for control in controls:
        if control.component_type == "Radio" and isinstance(control.props.get("group"), str):
            groups[control.props["group"]].append(control)
    for group, radios in groups.items():
        if len(radios) < 2:
            reporter.error(f"Radio group {group} must contain at least two Radio components.")
        if sum(item.props.get("checked") is True for item in radios) > 1:
            reporter.error(f"Radio group {group} must not have more than one checked component.")


def _require_context_call(
    control: _ComponentRecord,
    context_values: list[Any],
    call: str,
    arg_name: str,
    arg_value: Any,
    reporter: _Reporter,
) -> None:
    for value in context_values:
        if (
            isinstance(value, dict)
            and value.get("call") == call
            and isinstance(value.get("args"), dict)
            and value["args"].get(arg_name) == arg_value
        ):
            return
    reporter.error(
        f"{control.component_id}: submit_form context must include {call} "
        f"with {arg_name}={arg_value}."
    )


def _path_bindings(
    value: Any,
    path: tuple[str, ...] = (),
) -> list[tuple[str, str, bool]]:
    if _is_path_binding(value):
        location = ".".join(path)
        is_event_context = path[:3] == ("action", "event", "context")
        return [(location, value["path"], not is_event_context)]
    result: list[tuple[str, str, bool]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            result.extend(_path_bindings(child, (*path, key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            result.extend(_path_bindings(child, (*path, str(index))))
    return result


def _is_path_binding(value: Any) -> TypeGuard[_PathBinding]:
    return (
        isinstance(value, dict)
        and set(value) == {"path"}
        and isinstance(value["path"], str)
    )


def _is_json_pointer(value: str) -> bool:
    if not value.startswith("/"):
        return False
    if any("." in segment for segment in value[1:].split("/")):
        return False
    index = 0
    while index < len(value):
        if value[index] != "~":
            index += 1
            continue
        if index + 1 >= len(value) or value[index + 1] not in {"0", "1"}:
            return False
        index += 2
    return True


def _is_number(value: Any) -> TypeGuard[int | float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
