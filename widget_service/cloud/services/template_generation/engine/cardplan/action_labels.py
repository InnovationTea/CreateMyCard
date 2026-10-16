"""动作文案的候选投影和局部生成边界，不授予新的事件执行权限。"""

from __future__ import annotations

import json
import unicodedata
from typing import Any

from services.template_generation.engine.tersel_converter import TerselConversionError

from .models import ActionBinding

LABEL_ACTION_TEMPLATES = frozenset({
    "PillAction@1", "CompactAction@1", "CompactSubtitleAction@1", "PlaylistCompactAction@1",
})
_SWITCH_LABELS = {
    "event.setMobileData": ("开启移动数据", "关闭移动数据"),
    "event.setNearLinkMode": ("开启星闪", "关闭星闪"),
    "event.setBluetoothMode": ("开启蓝牙", "关闭蓝牙"),
    "event.setWifiMode": ("开启Wi-Fi", "关闭Wi-Fi"),
    "event.setLocationSwitch": ("开启定位", "关闭定位"),
    "event.setScreenUseTimeManageSwitch": ("开启屏幕时长管控", "关闭屏幕时长管控"),
    "event.setMicPermissionSwitch": ("开启麦克风权限", "关闭麦克风权限"),
}
_SOUND_LABELS = {"Vibrate": "设为振动", "Sound": "设为响铃", "Silent": "设为静音"}
_CAMERA_LABELS = {
    "Photo": "拍照模式",
    "Video": "录像模式",
    "PORTRAIT": "人像模式",
    "CINEMA": "电影模式",
    "NIGHT": "夜景模式",
    "SUPER_MACRO": "微距模式",
    "LIGHT_PAINTING": "流光快门",
    "TIME_LAPSE": "延时摄影",
    "SLOW_MO": "慢动作",
    "STITCHING": "全景模式",
    "PRO": "专业模式",
}


def parameter_action_label(event_id: str, args: Any) -> str | None:
    """按原始动作参数命名；缺失或未知参数交给既有文案兜底，不推测方向。"""
    label: str | None = None
    params = args.get("params") if isinstance(args, dict) else None
    if isinstance(params, dict):
        switch_labels = _SWITCH_LABELS.get(event_id)
        if switch_labels is not None:
            switch_flag = params.get("switchFlag")
            if type(switch_flag) is int and switch_flag in (0, 1):
                label = switch_labels[switch_flag]
        elif event_id == "event.setSoundMode":
            option = params.get("optionValue")
            if isinstance(option, str):
                label = _SOUND_LABELS.get(option)
        elif event_id == "event.openCamera":
            mode = params.get("mode")
            if isinstance(mode, str):
                label = _CAMERA_LABELS.get(mode)
    return label


def action_label_candidate(action: ActionBinding, *, id_key: str = "actionId") -> dict[str, Any]:
    """只向缺少文案的候选补充命名所需的事件语义。"""
    candidate: dict[str, Any] = {id_key: action.action_id, "label": action.display_label}
    if action.display_subtitle:
        candidate["subtitle"] = action.display_subtitle
    if action.display_label is None:
        candidate["labelPolicy"] = "generate-from-request"
        candidate["description"] = action.description
        candidate["readOnlyAction"] = {"call": action.call, "args": action.args}
    return candidate


def action_label_request(user_query: str, actions: tuple[ActionBinding, ...]) -> tuple[str, ...]:
    """仅在存在待生成文案时，把用户需求提供给第二层命名流程。"""
    lines: tuple[str, ...] = ()
    if any(action.display_label is None for action in actions):
        lines = ("actionLabelRequest=" + json.dumps(user_query, ensure_ascii=False),)
    return lines


def validate_action_label(binding: ActionBinding, label: Any) -> str:
    """已知文案精确匹配；生成文案仅通过局部纯文本检查，语义仍由模型负责。"""
    if not isinstance(label, str):
        raise TerselConversionError("Action label must be a string.")
    if binding.display_label is not None:
        if label != binding.display_label:
            raise TerselConversionError("Action label/actionId pair is not approved.")
    else:
        if not label or label != label.strip() or len(label) > 20:
            raise TerselConversionError("Generated Action label must contain 1-20 characters.")
        has_control = any(unicodedata.category(char).startswith("C") for char in label)
        if has_control or len(label.splitlines()) != 1:
            raise TerselConversionError("Generated Action label must be single-line plain text.")
        if any(marker in label for marker in ("${", "{{", "}}", "://", "www.", "<", ">")):
            raise TerselConversionError(
                "Generated Action label cannot contain expressions or links."
            )
        if label in {"打开详情", "查看详情", "详情", "打开", "查看"}:
            raise TerselConversionError("Generated Action label must name the actual action.")
    return label
