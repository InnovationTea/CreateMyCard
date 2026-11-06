"""仅补齐事件 URI 完整绑定表达式后的 JSON 引号，不推断动作或业务值。"""

import json
import re
from typing import Any

from app.logger import logger

# 先匹配完整的 URI 表达式，再跳过其它合法字符串，避免修改展示文案中的 JSON 示例。
# 此语法例外只接受单引号 URI 前缀加一个 /data 引用；不扩展为任意表达式修复。
_URI_OR_STRING = re.compile(
    r'"uri"\s*:\s*(?P<value>"\{\{\s*'
    r"'[A-Za-z][A-Za-z0-9+.-]*://[^'\"\\\r\n]*'\s*\+\s*"
    r'\$\{/data/[^{}\s"\\]+\}\s*\}\})(?=\s*[},])'
    r'|"(?:[^"\\]|\\.)*"'
)


def repair_event_uri_quotes(raw: str, decoder: json.JSONDecoder) -> str:
    """仅插入引号；用同位置 null 探针核实所有修改均落在事件 args.uri。"""
    pieces: list[str] = []
    probes: list[str] = []
    position = 0
    count = 0
    for match in _URI_OR_STRING.finditer(raw):
        if match.group("value") is None:
            continue
        end = match.end("value")
        pieces.append(raw[position:end] + '"')
        probes.append(raw[position:match.start("value")] + "null")
        position = end
        count += 1
    result = raw
    if count:
        pieces.append(raw[position:])
        probes.append(raw[position:])
        result = "".join(pieces)
        restored = decoder.decode(result)
        probe = decoder.decode("".join(probes))
        if _repaired_event_count(restored, probe) != count:
            raise ValueError("URI quote repair is outside event action args")
        logger.info(f"event_uri_json_quote_repaired count={count} model_called=false")
    return result


def _repaired_event_count(restored: Any, probe: Any) -> int:
    """探针只用于位置确认，不会进入正式请求或补造参数。"""
    if not isinstance(restored, dict) or not isinstance(probe, dict):
        return 0
    events = restored.get("candidateEventCandidates")
    probe_events = probe.get("candidateEventCandidates")
    if not isinstance(events, list) or not isinstance(probe_events, list):
        return 0
    count = 0
    for event, probe_event in zip(events, probe_events, strict=True):
        if not isinstance(event, dict) or not isinstance(probe_event, dict):
            continue
        for name in ("action", "actionTemplate"):
            action = event.get(name)
            probe_action = probe_event.get(name)
            if not isinstance(action, dict) or not isinstance(probe_action, dict):
                continue
            args = action.get("args")
            probe_args = probe_action.get("args")
            if not isinstance(args, dict) or not isinstance(probe_args, dict):
                continue
            if isinstance(args.get("uri"), str) and probe_args.get("uri") is None:
                count += 1
    return count
