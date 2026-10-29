"""把内部完整诊断投影为主 Agent 所需的简版错误反馈。"""

from typing import Any

_ACTIONS = frozenset(
    {
        "FIX_AND_RETRY",
        "REFRESH_CAPABILITIES",
        "REMOVE_OPTIONAL_CANDIDATE",
        "STOP",
        "NOTIFY_USER",
    }
)
_METADATA_NAMES = {"/title": "标题", "/description": "说明"}
_SCHEMA_CODES = frozenset({"DATA_ARGUMENT_SCHEMA_INVALID", "EVENT_ARGUMENT_SCHEMA_INVALID"})
_TYPE_CODES = frozenset(
    {
        "REQUEST_DICT_TYPE",
        "REQUEST_MODEL_TYPE",
        "REQUEST_MODEL_ATTRIBUTES_TYPE",
        "REQUEST_LIST_TYPE",
        "REQUEST_STRING_TYPE",
        "REQUEST_INT_TYPE",
        "REQUEST_INT_PARSING",
        "REQUEST_FLOAT_TYPE",
        "REQUEST_FLOAT_PARSING",
        "REQUEST_BOOL_TYPE",
        "REQUEST_BOOL_PARSING",
    }
)


def _extra_field_message(path: str) -> str:
    parts = path.removeprefix("/").split("/")
    name = parts[-1].replace("~1", "/").replace("~0", "~")
    message = f"不支持字段 {name}，请移除该字段。"
    if len(parts) == 1 and name in {"arguments", "params", "content"}:
        message = f"不支持 {name} 包裹层，请将其中的业务字段直接放入 arguments 对象。"
    is_event_definition = False
    if parts[0] == "candidateEventCandidates":
        if len(parts) == 3:
            is_event_definition = True
        elif len(parts) == 4 and parts[2] == "action":
            is_event_definition = True
    if is_event_definition:
        if name == "id":
            message = "此处不支持 id，请核对本轮事件概述，将事件 ID 放到候选项的 capabilityId。"
        elif name == "actionTemplate":
            message = (
                "此处不支持 actionTemplate，请核对本轮模板，将 call、args 放入 action；"
                "已有 action 时先核对冲突。"
            )
        elif name == "dynamicArguments":
            message = "此处不支持 dynamicArguments 定义，请移除；执行值按本轮事件模板填写。"
    if parts[0] == "candidateDataBindings" and "/arguments/" in path:
        message = f"不支持参数 {name}，请移除多传项，按本轮 inputSchema 填写合法业务参数。"
    return message


def _compact_expected(value: Any) -> str:
    expected = value if isinstance(value, str) else ""
    prefixes = (("JSON 字符串；", "字符串"), ("JSON 对象；", "对象"), ("JSON 数组；", "数组"))
    for prefix, keyword in prefixes:
        if expected.startswith(prefix):
            remaining = expected.removeprefix(prefix)
            if keyword in remaining:
                expected = remaining
            break
    return expected.rstrip("。；")


def _constraint_message(issue: dict[str, Any], path: str, message: str) -> str | None:
    result: str | None = None
    code = issue.get("code")
    name = path.rsplit("/", 1)[-1]
    expected = _compact_expected(issue.get("expected"))
    if isinstance(code, str) and code in _TYPE_CODES and expected:
        result = f"{name} 类型不正确，应为{expected}。"
    elif code in ("REQUEST_LITERAL_ERROR", "REQUEST_ENUM") and expected:
        result = f"{name} 仅支持 {expected}，请按需求选择。"
    elif isinstance(code, str) and code in _SCHEMA_CODES:
        if message == "字段类型不符合 schema。":
            result = f"{name} 类型不正确，应为{expected}。"
        elif message == "字段取值不在 schema 允许范围内。":
            result = f"{name} 取值不合法；{expected}。"
        elif message == "固定事件参数与注册表动作模板不一致。":
            result = f"{name} 必须保留模板固定值；{expected}。"
    elif code == "OUTPUT_FIELD_PATH_INVALID":
        result = "展示字段路径无效，请从本轮 outputSchema 选择叶子路径，数组使用数字下标。"
    elif code == "EVENT_CALL_MISMATCH" and expected:
        result = f"call 与模板不一致，请原样使用 {expected}。"
    return result


def _combine_message(issue: dict[str, Any], message: str) -> str:
    expected = _compact_expected(issue.get("expected"))
    generic_expected = expected.startswith("当前工具 Schema")
    if expected and not generic_expected and expected not in message:
        message += f"要求：{expected}。"
    instruction = issue.get("repairInstruction")
    if isinstance(instruction, str) and instruction:
        instruction = instruction.removeprefix("按 expected 重构 JSON 类型；")
        instruction = instruction.replace("按 expected ", "按上述要求")
        instruction = instruction.replace("按 expected", "按上述要求")
        instruction = instruction.removeprefix("将参数调整到 expected 范围；")
        instruction = instruction.replace(
            "若这会改变用户核心要求", "若满足该范围会改变用户核心要求"
        )
        if not instruction.startswith("按上述要求修正") and instruction not in message:
            message += instruction
    return message


def _metadata_message(issue: dict[str, Any], path: str, message: str) -> str | None:
    result: str | None = None
    name = _METADATA_NAMES.get(path)
    if name is not None:
        if issue.get("actualType") == "missing" and message.startswith("新建卡片缺少必填字段"):
            result = f"缺少{name}，须填写非空字符串。"
        elif issue.get("code") == "REQUEST_STRING_TOO_SHORT":
            result = f"{name}不能为空，请填写非空字符串。"
        elif issue.get("actualType") == "null" and message.startswith(("编辑时", "新建卡片的")):
            result = f"{name}不能为 null，请填写非空字符串。"
            if message.startswith("编辑时"):
                result = f"{name}不能为 null；未修改则省略继承，修改时填写非空字符串。"
    elif path == "/sourceArtifactUrl" and message.startswith("编辑来源无效"):
        result = (
            "sourceArtifactUrl 无效，请使用目标卡片最近有效来源；无法恢复时停止，不能切换新建。"
        )
    return result


def _issue_view(issue: dict[str, Any]) -> dict[str, str]:
    path = issue.get("path")
    if not isinstance(path, str):
        path = "/"
    message = issue.get("message")
    if not isinstance(message, str) or not message:
        message = "此处参数不符合要求。"
    code = issue.get("code")
    metadata = _metadata_message(issue, path, message)
    if metadata is not None:
        message = metadata
    elif code == "REQUEST_EXTRA_FORBIDDEN":
        message = _extra_field_message(path)
    elif (
        isinstance(code, str) and code in _SCHEMA_CODES and message == "包含 schema 未声明的字段。"
    ):
        message = _extra_field_message(path)
    elif code == "UNKNOWN_CAPABILITY":
        message += "请重新获取能力概述，使用本轮返回的 ID。"
    elif code == "REQUEST_VALUE_ERROR" and path == "/dataCapabilityIds":
        message = "生成接口不接受 dataCapabilityIds，请使用完整 candidateDataBindings 对象数组。"
    elif code == "REQUEST_VALUE_ERROR" and path == "/eventCapabilityIds":
        message = (
            "生成接口不接受 eventCapabilityIds，请使用完整 candidateEventCandidates 对象数组。"
        )
    else:
        constraint = _constraint_message(issue, path, message)
        message = constraint if constraint is not None else _combine_message(issue, message)
    return {"path": path, "message": message}


def _issues_view(value: Any) -> list[dict[str, str]]:
    issues = []
    if isinstance(value, list):
        for issue in value:
            if isinstance(issue, dict):
                issues.append(_issue_view(issue))
    return issues


def agent_error_view(
    error: dict[str, Any],
    fallback_message: str,
    *,
    user_message: str | None = None,
) -> dict[str, Any]:
    """仅读取完整诊断；停止优先，缺少明确重试控制时沿用停止策略。"""
    raw_details = error.get("details")
    details = raw_details if isinstance(raw_details, dict) else {}
    raw_actions = details.get("requiredActions")
    actions = []
    if isinstance(raw_actions, list):
        for action in raw_actions:
            if not isinstance(action, str) or action not in _ACTIONS:
                actions = []
                break
            actions.append(action)
    if not actions:
        actions = ["STOP"]
    retryable = details.get("retryable") is True
    if "STOP" in actions or "NOTIFY_USER" in actions:
        retryable = False
    if not retryable:
        actions = ["NOTIFY_USER"] if "NOTIFY_USER" in actions else ["STOP"]
    message = error.get("message")
    if not isinstance(message, str) or not message:
        message = fallback_message
    message = message.partition("，停止本轮")[0]
    instruction = details.get("agentInstruction")
    if not isinstance(instruction, str) or not instruction:
        instruction = "停止本轮自动调用，并按实际失败原因回复。"
    instruction = instruction.partition("diagnostic 路径")[0]
    issues = _issues_view(details.get("issues"))
    if retryable:
        diagnostic = details.get("diagnostic")
        if isinstance(diagnostic, dict):
            issues.extend(_issues_view(diagnostic.get("issues")))
        missing_metadata_only = bool(issues)
        for issue in issues:
            if issue.get("path") not in _METADATA_NAMES:
                missing_metadata_only = False
                break
            if not issue.get("message", "").startswith("缺少"):
                missing_metadata_only = False
                break
        if missing_metadata_only:
            message = "新建卡片缺少必填字段。"
            instruction = "补齐以下字段后提交完整 arguments 重试，保留原需求。"
    else:
        instruction = "停止本轮自动调用，并按实际失败原因回复；保留原有效来源。"
    if user_message is not None:
        message = user_message
        instruction = "请向用户回复上述 message，停止本轮自动调用。"
    result: dict[str, Any] = {
        "message": message,
        "retryable": retryable,
        "requiredActions": actions,
        "agentInstruction": instruction,
        "issues": issues,
    }
    warnings = _issues_view(details.get("warnings"))
    if warnings:
        result["warnings"] = warnings
    return result
