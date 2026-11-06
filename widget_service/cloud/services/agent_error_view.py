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


def _candidate_keyword_message(name: str) -> str | None:
    """仅给顶层错名提供条件性提示；关键词不授权改参或推断业务用途。"""
    lowered = name.lower()
    matched_categories = []
    destinations = []
    for keyword, destination in (
        ("data", "数据放入 candidateDataBindings"),
        ("event", "事件放入 candidateEventCandidates"),
        ("asset", "素材放入 candidateAssetIds"),
    ):
        if keyword in lowered:
            matched_categories.append(keyword)
            destinations.append(destination)
    has_data = "data" in lowered
    has_event = "event" in lowered
    has_asset = "asset" in lowered
    message: str | None = None
    if len(matched_categories) > 1:
        message = (
            f"字段 {name} 同时包含 {'、'.join(matched_categories)}，请核对用途："
            f"{'，'.join(destinations)}，不将混合内容直接改名。"
        )
    elif has_data:
        message = (
            f"不支持字段 {name}；若为数据候选，请改用 candidateDataBindings 对象数组，"
            "每项包含 capabilityId、arguments、writeResultTo 和非空 candidateOutputFields。"
            "核对本轮数据概述及完整定义，保留合法业务参数，无参时显式传 arguments: {}。"
        )
    elif has_event:
        message = (
            f"不支持字段 {name}；若为事件候选，请改用 candidateEventCandidates 对象数组，"
            "每项为 {capabilityId, action:{call,args}}。按本轮事件模板保留固定值，"
            "仅填写声明的动态参数并核对数据依赖。"
        )
    elif has_asset:
        message = (
            f"不支持字段 {name}；若为素材候选，请改用 candidateAssetIds 字符串数组，"
            "ID 须来自本轮素材概述，不传素材定义对象或地址。"
        )
    if message is not None:
        message += (
            "保留合法值、类型和顺序，已有目标字段先核对冲突；"
            "不得仅删除该字段或清空候选绕过校验，提交前仍须完成全部预检；"
            "数据绑定变化后复查权限，编辑不得增删原数据集合或替换事件、素材候选。"
        )
    return message


def candidate_migration_message(name: str) -> str | None:
    """仅解释登记的顶层错用字段，不将同名业务参数当作候选。"""
    messages = {
        "dataCapabilityInputs": (
            "将顶层 dataCapabilityInputs 重构为 candidateDataBindings 数组；"
            "若原值是按能力 ID 索引的参数对象，先核对每个 ID 来自本轮能力概述，"
            "将 ID 填入 capabilityId，对应参数对象原样迁移到 arguments，"
            "再依据本轮完整数据定义填写 writeResultTo 和非空 candidateOutputFields。"
            "缺少必要业务参数时先向用户澄清，不从样例猜填。"
        ),
        "action": (
            "生成接口不接受顶层 action；创建不传 sourceArtifactUrl，"
            "编辑须保留目标卡片有效的 sourceArtifactUrl，不能通过删除来源切换创建。"
            "移除 action 后保留其余合法业务参数。"
        ),
        "assetCandidateIds": (
            "将 assetCandidateIds 改为 candidateAssetIds；保留本轮已选合法素材 ID，"
            "值为字符串数组，不将素材改成定义对象。"
        ),
        "dataCapabilities": (
            "将 dataCapabilities 重构为 candidateDataBindings，每项包含 capabilityId、"
            "arguments、writeResultTo 和非空 candidateOutputFields。核对本轮数据概述的 ID，"
            "依据 getDataCapabilitySchemas 的 inputSchema 将 inputParams 或平铺业务参数"
            "放入 arguments；依据 defaultWriteResultTo 和 outputSchema 填写路径及展示字段。"
        ),
        "eventCapabilities": (
            "将 eventCapabilities 重构为 candidateEventCandidates，每项为 "
            "{capabilityId, action:{call,args}}。ID 取本轮事件概述；将 actionTemplate 的"
            "call、args 完整复制到 action，保留固定值，仅填写声明的动态参数并核对数据依赖。"
        ),
        "assetCandidates": (
            "将 assetCandidates 重构为 candidateAssetIds 字符串数组；"
            "对象含 assetId 或 id 时，核对本轮素材概述后提取已选 ID；"
            "不传整份素材定义或自行构造地址，不盲目合并冲突的 ID。"
        ),
    }
    aliases = {
        "events": "eventCapabilities",
        "assets": "assetCandidates",
        "dataCandidates": "dataCapabilities",
        "dataList": "dataCapabilities",
        "dataIds": "dataCapabilities",
        "dataBindings": "dataCapabilities",
        "candidateDataCapabilities": "dataCapabilities",
        "eventCandidates": "eventCapabilities",
        "candidateEvents": "eventCapabilities",
        "candidateAssets": "assetCandidates",
        "candidateAssetCandidates": "assetCandidates",
        "assetIds": "assetCandidates",
    }
    canonical = aliases.get(name, name)
    message = messages.get(canonical)
    if message is not None and canonical != name:
        message = message.replace(canonical, name, 1)
    if message is not None:
        message += (
            "保留原需求和同一候选的合法业务参数及类型（包括 0、false、空字符串），"
            "不得仅删除该字段、清空候选或省略原调用参数来绕过校验；"
            "已有正确候选时先核对冲突，不盲目覆盖。提交完整 invoke.arguments，"
            "复核必填项及下层参数；数据绑定变化后复查权限，编辑不得增删原数据集合。"
        )
    elif name not in {"dataCapabilityIds", "eventCapabilityIds"}:
        message = _candidate_keyword_message(name)
    return message


def candidate_field_migration(path: str) -> str | None:
    """仅匹配候选项本层的别名，不解释 arguments 内部的业务字段。"""
    parts = path.removeprefix("/").split("/")
    message: str | None = None
    if len(parts) == 3 and parts[1].isdigit():
        root, _index, name = parts
        if root == "candidateDataBindings":
            if name in {"id", "dataCapabilityId"}:
                message = (
                    f"将候选项的 {name} 移至 capabilityId，核对本轮数据概述；"
                    "保留该项的调用参数，补齐 writeResultTo，不仅修正 ID。"
                )
            elif name == "inputParams":
                message = (
                    "将 inputParams 中符合本轮 inputSchema 的参数放入同一候选项的 arguments；"
                    "保留真实类型及零值、false、空字符串，不删除参数、不省略 arguments 或改成 {}。"
                    "仅本轮 Schema 确认无参时用 {}；已有 arguments 时先核对冲突，"
                    "缺少必要业务值先澄清，绑定变化后复查权限。"
                )
        elif root == "candidateEventCandidates" and name == "eventCapabilityId":
            message = (
                "将 eventCapabilityId 移至候选项的 capabilityId，核对本轮事件概述；"
                "将 actionTemplate 的 call、args 放入 action，保留固定值与合法动态参数，"
                "已有目标字段时先核对冲突，不删除事件。"
            )
    return message


def _extra_field_message(path: str) -> str:
    parts = path.removeprefix("/").split("/")
    name = parts[-1].replace("~1", "/").replace("~0", "~")
    message = f"不支持字段 {name}，请移除该字段。"
    if len(parts) == 1 and name in {"arguments", "params", "content"}:
        message = f"不支持 {name} 包裹层，请将其中的业务字段直接放入 arguments 对象。"
    if len(parts) == 1:
        migration = candidate_migration_message(name)
        if migration is not None:
            message = migration
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
    migration = candidate_field_migration(path)
    if migration is not None:
        message = migration
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
    elif code == "REQUEST_DATA_FIELD_MISPLACED":
        instruction = issue.get("repairInstruction")
        if isinstance(instruction, str) and instruction:
            message = instruction.removeprefix("核对字段归属；")
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
