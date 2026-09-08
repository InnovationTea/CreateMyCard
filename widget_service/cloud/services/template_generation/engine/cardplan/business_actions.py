"""Support 内嵌事件的共享白名单与数据对象归属校验。"""

from __future__ import annotations

from typing import Any

from services.template_generation.engine.a2ui_expression import (
    A2UIExpressionError,
    normalize_tersel_expression,
)

from .models import ActionBinding, TemplateDefinition

_CALENDAR_ARGUMENTS = {
    "event.viewCalendarEvent": ("entityId", "params"),
    "event.enter.meeting": ("oneClickServiceLink", "uri"),
}


def supports_business_action(
    definition: TemplateDefinition,
    action: ActionBinding,
    card_size: str,
) -> bool:
    """只检查可信事件与模板的关联；事件 call/args 的注册校验仍由原入口负责。"""
    if action.event_id not in definition.supported_event_ids:
        return False
    accepts_action = False
    for variant in definition.variants:
        if variant.supported_card_sizes and card_size not in variant.supported_card_sizes:
            continue
        properties = variant.parameters_schema.get("properties", {})
        if "actionId" in properties:
            accepts_action = True
            break
    return accepts_action and _matches_business_data(definition, action)


def _matches_business_data(definition: TemplateDefinition, action: ActionBinding) -> bool:
    if action.event_id == "event.open.weather":
        if definition.data_domain is None:
            return False
        expected = definition.data_domain + "/location/cityCode"
        return _argument_references(action.args.get("uri")) == (expected,)
    calendar_argument = _CALENDAR_ARGUMENTS.get(action.event_id)
    if calendar_argument is None:
        return True
    if definition.data_domain is None:
        return False
    field, argument = calendar_argument
    event_paths: set[str] = set()
    for binding in definition.bindings.values():
        parts = binding.path.split("/")
        if len(parts) >= 4 and parts[1] == "events" and parts[2].isdigit():
            event_paths.add(f"{definition.data_domain}/events/{parts[2]}/{field}")
    if len(event_paths) != 1:
        return False
    value = action.args.get(argument)
    if argument == "params":
        value = value.get("entityId") if isinstance(value, dict) else None
    return set(_argument_references(value)) == event_paths


def _argument_references(value: Any) -> tuple[str, ...]:
    references: tuple[str, ...] = ()
    if isinstance(value, dict):
        path = value.get("path")
        if set(value) == {"path"} and isinstance(path, str):
            references = (path,)
    elif isinstance(value, str):
        body = value.strip()
        if body.startswith("{{") and body.endswith("}}"):
            body = body.removeprefix("{{").removesuffix("}}").strip()
        try:
            references = normalize_tersel_expression(body).references
        except A2UIExpressionError:
            # 非法表达式不能用于证明业务对象归属，失效关闭。
            references = ()
    return tuple(dict.fromkeys(references))
