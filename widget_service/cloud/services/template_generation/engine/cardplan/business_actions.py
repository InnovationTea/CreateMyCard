"""业务模板内嵌事件的共享白名单与数据对象归属校验。"""

from __future__ import annotations

from typing import Any

from services.template_generation.engine.a2ui_expression import (
    A2UIExpressionError,
    normalize_tersel_expression,
)

from .models import ActionBinding, TemplateDefinition
from .provider_bundle import provider_template_layout_kind

_CALENDAR_ARGUMENTS = {
    "event.viewCalendarEvent": ("entityId", "params"),
    "event.enter.meeting": ("oneClickServiceLink", "uri"),
}
_WIDE_STANDARD_ACTION_TEMPLATE_IDS = frozenset(
    {"ScheduleOverviewEventCountTwoEventsFull@1"}
)


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
        standard_template_in_wide_layout = (
            card_size == "2x4"
            and definition.wire_id in _WIDE_STANDARD_ACTION_TEMPLATE_IDS
            and provider_template_layout_kind(definition.wire_id) == "Full"
        )
        if (
            variant.supported_card_sizes
            and card_size not in variant.supported_card_sizes
            and not standard_template_in_wide_layout
        ):
            continue
        properties = variant.parameters_schema.get("properties", {})
        if "actionId" in properties:
            accepts_action = True
            break
    return accepts_action and matches_business_data(definition, action)


def matches_business_data(
    definition: TemplateDefinition,
    action: ActionBinding,
    *,
    allow_static_target: bool = False,
) -> bool:
    """验证事件引用的数据对象；调用方必须先完成业务事件白名单检查。"""
    if allow_static_target and _has_static_target(action):
        return True
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
    event_paths: dict[int, str] = {}
    for binding in definition.bindings.values():
        parts = binding.path.split("/")
        if len(parts) >= 4 and parts[1] == "events" and parts[2].isdigit():
            event_index = int(parts[2])
            event_paths[event_index] = (
                f"{definition.data_domain}/events/{event_index}/{field}"
            )
    if not event_paths:
        return False
    value = action.args.get(argument)
    if argument == "params":
        value = value.get("entityId") if isinstance(value, dict) else None
    references = set(_argument_references(value))
    if definition.wire_id in _WIDE_STANDARD_ACTION_TEMPLATE_IDS:
        primary_event_path = event_paths[min(event_paths)]
        return references == {primary_event_path}
    return len(event_paths) == 1 and references == set(event_paths.values())


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


def _has_static_target(action: ActionBinding) -> bool:
    """根按钮可打开已批准的固定入口；动态对象仍须匹配模板绑定。"""
    value: Any = action.args.get("uri")
    calendar = _CALENDAR_ARGUMENTS.get(action.event_id)
    if calendar is not None and calendar[1] == "params":
        params = action.args.get("params")
        value = params.get("entityId") if isinstance(params, dict) else None
    if not isinstance(value, str) or not value.strip():
        return False
    return "{{" not in value and "${" not in value
