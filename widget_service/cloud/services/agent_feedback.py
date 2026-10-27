"""面向主 Agent 的请求纠错与终态指引，不回传原始入参。"""

from typing import Any

from pydantic import ValidationError

from models.preflight import AgentAction, PreflightIssue

_GENERATION_OPERATIONS = (
    "generateWidgetCard", "generateWidgetCardCompactDsl", "generateWidgetCardTerseDslNested2",
)
_DATA_INSTRUCTION = (
    "从本轮数据定义构造对象数组，每项包含 capabilityId、arguments、writeResultTo，"
    "按需填写完整 candidateOutputFields；不能仅传能力 ID。"
)
_EVENT_INSTRUCTION = (
    "从本轮事件概述构造对象数组，每项包含 capabilityId 和完整 action；"
    "action 含 call、args，仅替换模板声明的动态参数，不能仅传事件 ID。"
)
_FIELD_INSTRUCTIONS = {
    "candidateDataBindings": _DATA_INSTRUCTION,
    "candidateEventCandidates": _EVENT_INSTRUCTION,
    "sourceArtifactUrl": (
        "仅使用本会话目标卡片最近有效结果的来源地址；无法恢复时停止，"
        "不得猜地址、删除来源字段或切换新建。"
    ),
    "size": "仅填写 2x2 或 2x4，保留用户明确指定的尺寸；不得擅自扩尺寸。",
    "title": "新建时填写符合有效需求的非空静态短标题，不从动态数据样例抄值。",
    "description": "新建时填写符合有效需求的非空静态短说明，不承诺未支持的功能。",
    "userQuery": "填写本轮有效需求及实际采用的静态展示事实，不删除核心要求来规避错误。",
    "arguments": "按本轮 Schema 构造 JSON 对象，不能传字符串、数组或 null，也不强制转换业务值。",
    "candidateAssetIds": "使用本轮素材概述中的 ID 字符串数组；没有所需匹配素材时为空数组。",
}


def _pointer(parts: tuple[Any, ...]) -> str:
    escaped = []
    for part in parts:
        escaped.append(str(part).replace("~", "~0").replace("/", "~1"))
    return "/" + "/".join(escaped)


def request_validation_feedback(exc: ValidationError, operation: str) -> dict[str, Any]:
    issues = []
    for error in exc.errors(include_context=False, include_input=False):
        location = tuple(error.get("loc", ()))
        error_type = str(error.get("type", "validation_error"))
        message = str(error.get("msg", "字段不符合请求约束。"))
        field_name = str(location[-1]) if location else ""
        instruction = _FIELD_INSTRUCTIONS.get(field_name)
        if field_name == "dataCapabilityIds" and operation in _GENERATION_OPERATIONS:
            instruction = "删除 dataCapabilityIds；" + _DATA_INSTRUCTION
        elif field_name == "eventCapabilityIds":
            instruction = "删除 eventCapabilityIds；" + _EVENT_INSTRUCTION
        elif field_name == "actionTemplate":
            instruction = (
                "将本轮对应事件 actionTemplate 的完整值放入 action，保留 call、args 及固定值；"
                "不提交 actionTemplate 字段名或 dynamicArguments 定义。"
                "已有 action 时先核对冲突，不覆盖实际动作参数。"
            )
        elif error_type == "extra_forbidden":
            message = "此位置包含未声明字段。"
            instruction = (
                "删除该未声明字段，仅使用当前工具 Schema 的字段；"
                "若它承载实际需求，按本轮定义构造合法候选，不得清空动态绑定冒充静态请求。"
            )
        if message.endswith("cannot be null in edit mode"):
            instruction = "编辑时未修改该字段则省略；明确修改时传入符合 Schema 的值，不传 null。"
        if instruction is None:
            instruction = (
                "按当前工具 Schema 修正该位置的必填项、结构、类型或枚举；"
                "需要能力参数时先读取本轮完整定义，不猜字段、不强制类型转换。"
            )
        transport_field = bool(location) and location[0] in {
            "uid", "device", "deviceInfo", "prdVer", "locale", "userAuth",
        }
        retryable = bool(location) and not transport_field
        if not retryable:
            instruction = (
                "请求上下文缺失或无法可靠定位字段，请停止本轮调用，"
                "不编造设备、用户或技术字段。"
            )
        issues.append(PreflightIssue(
            code=f"REQUEST_{error_type.upper()}", path=_pointer(location), message=message,
            expected="符合当前工具 Schema 及新建／编辑模式约束",
            agentAction=AgentAction.FIX_AND_RETRY if retryable else AgentAction.STOP,
            retryable=retryable, repairInstruction=instruction,
            referenceSource=f"{operation} 当前工具 Schema",
        ))
    retryable = bool(issues) and all(issue.retryable for issue in issues)
    return {
        "stage": "requestValidation", "modelCalled": False, "retryable": retryable,
        "requiredActions": ["FIX_AND_RETRY" if retryable else "STOP"],
        "agentInstruction": (
            "逐项按 issues.path 和 repairInstruction 修正全部问题后再调用；"
            "不得原样重试、猜值、删除核心需求、切换创建／编辑或超过既有调用预算。"
            "绑定或数据集合变化后重新检查权限；缺必要业务值时先澄清。"
            if retryable else "包含不可自动修复的上下文问题，请停止本轮调用并保留原有效来源。"
        ),
        "issues": [issue.model_dump(mode="json") for issue in issues],
    }


def terminal_feedback(stage: str) -> dict[str, Any]:
    """没有明确改参依据的失败不授权自动重调或切换任务模式。"""
    return {
        "stage": stage, "retryable": False, "requiredActions": ["STOP"],
        "agentInstruction": (
            "本轮没有可执行的入参修正依据，请停止自动调用并按真实状态回复；"
            "保留原有效来源，不猜修法、不改为新建或静态请求，不把失败结果当作成功。"
        ),
    }
