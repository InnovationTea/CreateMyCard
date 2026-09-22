"""仅为单电量 Hero 复用已批准的电池设置入口，不改变展示字段。"""

from __future__ import annotations

from models.generation import TaskSpec

from .provider_bundle import provider_template_layout_kind
from .template_retrieval import TemplateSearchIntent, TemplateSearchResult

_BATTERY_CAPABILITY = "GetPhoneBatteryInfo"
_BATTERY_BUSINESS = "BatteryOverview"
_SETTINGS_EVENT = "event.open.settings.battery"
_HEALTH_EVENT = "event.open.settings.batteryHealth"
_SETTINGS_ARGS = {
    "intentName": "Settings",
    "bundleName": "com.huawei.hmos.settings",
    "abilityName": "com.huawei.hmos.settings.MainAbility",
    "uri": "battery",
}


def resolve_battery_settings_fallback(
    intent: TemplateSearchIntent,
    search_result: TemplateSearchResult,
    task_spec: TaskSpec,
) -> TemplateSearchIntent:
    """Full 优先；无 Full 且有 Hero 时才补选唯一、目标正确的设置候选。"""
    if not intent.allow_battery_settings_fallback or intent.action_ids:
        return intent
    if task_spec.size != "2x2" or search_result.card_size != task_spec.size:
        return intent
    if tuple(intent.required_output_fields_by_capability) != (_BATTERY_CAPABILITY,):
        return intent
    if len(search_result.business_candidates) != 1:
        return intent
    group = search_result.business_candidates[0]
    if group.capability_id != _BATTERY_CAPABILITY or group.business_id != _BATTERY_BUSINESS:
        return intent
    roles = {provider_template_layout_kind(candidate.template_id) for candidate in group.candidates}
    if "Full" in roles or "Hero" not in roles:
        return intent
    event_id = _SETTINGS_EVENT
    expected_args = _SETTINGS_ARGS
    events = [event for event in task_spec.eventCandidates if event.id == event_id]
    if not events:
        fields = intent.required_output_fields_by_capability.get(_BATTERY_CAPABILITY, ())
        if "/healthStatusDesc" not in fields:
            return intent
        event_id = _HEALTH_EVENT
        expected_args = {**_SETTINGS_ARGS, "uri": "smart_charge_battery_health"}
        events = [event for event in task_spec.eventCandidates if event.id == event_id]
    if len(events) != 1:
        return intent
    event = events[0]
    if event.call != "clickToDeeplink" or event.args != expected_args:
        return intent
    return intent.model_copy(update={"action_ids": (event_id,)})
