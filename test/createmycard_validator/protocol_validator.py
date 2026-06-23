"""A2UI protocol rules."""

from __future__ import annotations

try:
    from .common import CANONICAL_MESSAGE_KEYS, MESSAGE_KEYS, Finding, ValidationContext, error, warning
except ImportError:
    from common import CANONICAL_MESSAGE_KEYS, MESSAGE_KEYS, Finding, ValidationContext, error, warning  # type: ignore


def validate(ctx: ValidationContext) -> list[Finding]:
    findings: list[Finding] = []
    if not ctx.messages:
        return findings

    create_count = 0
    has_components = False
    has_data = False

    for index, msg in enumerate(ctx.messages):
        if msg.get("version") != "v0.9":
            findings.append(error("RULE_PROTOCOL_001", f"message {index + 1}: version must be v0.9", 10))

        # ========== 新增 RULE_PROTOCOL_006: 检测 type 信封格式错误 ==========
        if "type" in msg and isinstance(msg["type"], str):
            msg_type = msg["type"]
            if msg_type in {"createSurface", "updateComponents", "updateDataModel", "deleteSurface"}:
                findings.append(error(
                    "RULE_PROTOCOL_006",
                    f"message {index + 1}: 使用了错误的 '{{\"type\": \"{msg_type}\", \"params\": ...}}' 信封格式，"
                    f"应直接使用 '{{\"{msg_type}\": ...}}' 格式",
                    15
                ))

        # ========== 新增 RULE_PROTOCOL_007: 检测 command 信封格式错误 ==========
        if "command" in msg and isinstance(msg["command"], str):
            cmd = msg["command"]
            if cmd in {"createSurface", "updateComponents", "updateDataModel", "deleteSurface"}:
                findings.append(error(
                    "RULE_PROTOCOL_007",
                    f"message {index + 1}: 使用了错误的 '{{\"command\": \"{cmd}\", \"params\": ...}}' 信封格式，"
                    f"应直接使用 '{{\"{cmd}\": ...}}' 格式",
                    15
                ))

        # ========== 新增 RULE_PROTOCOL_008: 检测字段名大小写错误 ==========
        for key in msg:
            correct = CANONICAL_MESSAGE_KEYS.get(key.lower())
            if correct and correct != key:
                findings.append(error(
                    "RULE_PROTOCOL_008",
                    f"message {index + 1}: 消息体字段名 '{key}' 大小写错误，应使用驼峰命名 '{correct}'",
                    15
                ))

        bodies = [key for key in MESSAGE_KEYS if key in msg]
        if len(bodies) != 1:
            findings.append(error("RULE_PROTOCOL_010", f"message {index + 1}: envelope must contain exactly one message body", 10))
            continue

        kind = bodies[0]

        # ========== 新增 RULE_PROTOCOL_009: 检测缺少 surfaceId ==========
        body = msg.get(kind, {})
        if isinstance(body, dict) and "surfaceId" not in body:
            findings.append(error(
                "RULE_PROTOCOL_009",
                f"message {index + 1} ({kind}): 缺少 surfaceId 字段",
                10
            ))

        if kind == "createSurface":
            create_count += 1
            if index != 0:
                findings.append(error("RULE_PROTOCOL_002", "first message must be createSurface", 10))
        if kind == "updateComponents":
            has_components = True
        if kind == "updateDataModel":
            has_data = True

    if create_count == 0:
        findings.append(error("RULE_PROTOCOL_002", "missing createSurface as first message", 10))
    if create_count > 1:
        findings.append(error("RULE_PROTOCOL_003", "createSurface appears more than once", 10))
    if not has_components:
        findings.append(error("RULE_PROTOCOL_004", "missing updateComponents", 10))
    if not has_data:
        if ctx.bindings:
            findings.append(error("RULE_PROTOCOL_005", "dynamic DSL missing updateDataModel", 10))
        else:
            findings.append(warning("RULE_PROTOCOL_005", "static widget without updateDataModel"))

    return findings
