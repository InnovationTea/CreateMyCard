"""从主 Agent 调工具的视角解释请求错误；不回传原始参数或传输包络。"""

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from models.preflight import AgentAction, PreflightIssue

_GENERATION_OPERATIONS = (
    "generateWidgetCard",
    "generateWidgetCardCompactDsl",
    "generateWidgetCardTerseDslNested2",
)
_MISSING = object()
_TRANSPORT_FIELDS = frozenset(
    {
        "uid",
        "device",
        "deviceInfo",
        "prdVer",
        "locale",
        "userAuth",
        "session",
        "utterance",
        "content",
    }
)
_RETRY_INSTRUCTION = (
    "修正全部 issues 后提交完整 invoke.arguments 重试；保留原需求，沿用既有调用预算。"
)


@dataclass(frozen=True)
class _Guidance:
    expected: str
    instruction: str
    reference: str = ""


_DATA_LIST = _Guidance(
    "JSON 对象数组，每项包含 capabilityId、arguments、writeResultTo，可选 candidateOutputFields",
    "按本轮数据定义构造完整绑定，不只传 ID；arguments 为静态对象，无参用 {}。",
    "getDataCapabilitySchemas.dataCapabilities[]",
)
_EVENT_LIST = _Guidance(
    "JSON 对象数组，每项为 {capabilityId, action:{call,args}}",
    "从本轮事件概述取 ID，action 仅复制 actionTemplate 的 call、args；只填写声明的动态参数。",
    "getWidgetCapabilityOverview.eventCapabilities[]",
)
_EVENT_ID = _Guidance(
    "本轮事件概述中的 ID 字符串，位于候选项的 capabilityId",
    "核对本轮事件概述，将对应 ID 填在候选项外层 capabilityId，不猜 ID。",
    "getWidgetCapabilityOverview.eventCapabilities[].id",
)
_EVENT_ACTION = _Guidance(
    "JSON 对象 {call,args}，args 为 JSON 对象",
    "将本轮 actionTemplate 的 call、args 完整值放入 action，保留固定值及空字符串；"
    "不把整个事件定义放入 action。",
    "getWidgetCapabilityOverview.eventCapabilities[].actionTemplate/dynamicArguments",
)
_EVENT_ARGS = _Guidance(
    "本轮动作模板的完整 args 对象及其已声明动态参数",
    "按本轮模板填写声明的动态参数，保留固定值；数据引用须匹配绑定及实际展示对象的数字下标。",
    "getWidgetCapabilityOverview.eventCapabilities[].actionTemplate/dynamicArguments",
)
_DATA_ARGS = _Guidance(
    "符合本轮 inputSchema 的静态 JSON 参数对象；无参能力使用 {}",
    "按本轮 inputSchema 填写静态参数；缺必要业务值先澄清，不猜值。",
    "getDataCapabilitySchemas.dataCapabilities[].inputSchema",
)
_DATA_FIELDS = {
    "capabilityId": _Guidance(
        "本轮可用数据能力 ID 字符串，位于候选项的 capabilityId",
        "核对本轮数据概述，将对应 ID 填在候选项外层 capabilityId。",
        "getWidgetCapabilityOverview.dataCapabilities[].id",
    ),
    "arguments": _DATA_ARGS,
    "writeResultTo": _Guidance(
        "位于 /data/ 下且与其它绑定不相同、不互为父子的 JSON Pointer 字符串",
        "优先使用 defaultWriteResultTo，检查全部绑定的路径冲突；编辑保留原写入根。",
        "getDataCapabilitySchemas.dataCapabilities[].defaultWriteResultTo",
    ),
    "candidateOutputFields": _Guidance(
        "可选字符串数组，每项为本轮 outputSchema 可推导的叶子 JSON Pointer",
        "从本轮 outputSchema 选择所需叶子路径，数组用数字下标；保留必需字段及对应时间范围。",
        "getDataCapabilitySchemas.dataCapabilities[].outputSchema",
    ),
}
_TOP_FIELDS = {
    "candidateDataBindings": _DATA_LIST,
    "candidateEventCandidates": _EVENT_LIST,
    "sourceArtifactUrl": _Guidance(
        "同一目标卡片最近有效结果的非空完整来源地址",
        "使用目标卡片最近有效来源，不猜地址或切换创建；来源不可恢复时停止。",
    ),
    "size": _Guidance(
        "2x2 或 2x4",
        "按用户要求填写允许尺寸。",
    ),
    "title": _Guidance(
        "新建为非空字符串；编辑未修改时可省略继承",
        "新建填写短标题；编辑未修改则省略继承。",
    ),
    "description": _Guidance(
        "新建为非空字符串；编辑未修改时可省略继承",
        "新建填写简短说明；编辑未修改则省略继承。",
    ),
    "userQuery": _Guidance(
        "包含本轮有效需求、全部明确约束及实际采用静态事实的非空字符串",
        "填写本轮有效需求和采用的静态事实，保留核心要求；无原始需求时先澄清。",
    ),
    "candidateAssetIds": _Guidance(
        "本轮素材概述中 ID 组成的字符串数组",
        "从本轮素材概述选择 ID，无匹配项可为空。",
        "getWidgetCapabilityOverview.assetCandidates[].id",
    ),
    "options": _Guidance(
        "当前工具 Schema 明确开放的配置对象",
        "按当前工具 Schema 填写；未开放则省略。",
    ),
}
_TYPE_EXPECTATIONS = {
    "dict_type": "JSON 对象",
    "model_type": "JSON 对象",
    "model_attributes_type": "JSON 对象",
    "list_type": "JSON 数组",
    "string_type": "JSON 字符串",
    "int_type": "JSON 整数",
    "int_parsing": "JSON 整数",
    "float_type": "JSON 数字",
    "float_parsing": "JSON 数字",
    "bool_type": "JSON 布尔值 true 或 false",
    "bool_parsing": "JSON 布尔值 true 或 false",
}


def _pointer(parts: tuple[Any, ...]) -> str:
    escaped = []
    for part in parts:
        escaped.append(str(part).replace("~", "~0").replace("/", "~1"))
    return "/" + "/".join(escaped)


def _guidance(location: tuple[Any, ...], operation: str) -> _Guidance:
    if not location:
        return _Guidance("当前工具的业务对象", "无法定位业务字段，请停止并核对工具调用链路。")
    root = str(location[0])
    if root == "candidateDataBindings":
        if len(location) == 2 and isinstance(location[1], int):
            return _Guidance(
                "包含 ID、调用参数和写入路径的单个 JSON 对象",
                _DATA_LIST.instruction,
                _DATA_LIST.reference,
            )
        if len(location) >= 3 and isinstance(location[1], int):
            name = str(location[2])
            if name == "arguments":
                return _DATA_ARGS
            if name == "candidateOutputFields" and len(location) > 3:
                guide = _DATA_FIELDS.get(name)
                if guide is not None:
                    return _Guidance(
                        "outputSchema 可推导的单个叶子 JSON Pointer 字符串",
                        guide.instruction,
                        guide.reference,
                    )
            return _DATA_FIELDS.get(name, _DATA_LIST)
        return _DATA_LIST
    if root == "candidateEventCandidates":
        return _event_guidance(location)
    if root == "candidateAssetIds" and len(location) > 1:
        guide = _TOP_FIELDS.get(root)
        if guide is not None:
            return _Guidance("本轮素材概述中的单个 ID 字符串", guide.instruction, guide.reference)
    if len(location) == 1:
        if root in {"arguments", "params", "content"}:
            return _Guidance(
                "invoke.arguments 直接包含当前工具声明的业务字段",
                "直接提交完整业务参数，不要再次包 arguments、params、content 或整个调用对象。",
            )
        if root == "dataCapabilityIds" and operation in _GENERATION_OPERATIONS:
            return _Guidance(
                _DATA_LIST.expected,
                "将查询和权限使用的 dataCapabilityIds 改为完整 candidateDataBindings；"
                + _DATA_LIST.instruction,
                _DATA_LIST.reference,
            )
        if root == "eventCapabilityIds":
            return _Guidance(
                _EVENT_LIST.expected,
                "将 eventCapabilityIds 改为完整 candidateEventCandidates；"
                + _EVENT_LIST.instruction,
                _EVENT_LIST.reference,
            )
        return _TOP_FIELDS.get(
            root,
            _Guidance(
                "当前工具 Schema 在该位置声明的字段",
                "核对字段名和层级，将业务值放回正确位置，移除误传定义元数据。",
            ),
        )
    return _Guidance(
        "当前工具 Schema 在该位置声明的类型和约束",
        "按该嵌套位置的 Schema 修正，不套用同名顶层字段规则。",
    )


def _event_guidance(location: tuple[Any, ...]) -> _Guidance:
    if len(location) == 2 and isinstance(location[1], int):
        return _Guidance(
            "单个 JSON 对象 {capabilityId, action:{call,args}}",
            _EVENT_LIST.instruction,
            _EVENT_LIST.reference,
        )
    if len(location) < 3 or not isinstance(location[1], int):
        return _EVENT_LIST
    name = str(location[2])
    if name in {"capabilityId", "id"}:
        return _EVENT_ID
    if name in {"actionTemplate", "dynamicArguments"}:
        return _EVENT_ACTION
    if name == "action":
        if len(location) >= 4 and location[3] == "args":
            return _EVENT_ARGS
        if len(location) == 4 and location[3] == "call":
            return _Guidance(
                "本轮对应 actionTemplate.call 的原始字符串值",
                "原样使用本轮对应模板的 call。",
                _EVENT_ACTION.reference,
            )
        return _EVENT_ACTION
    return _EVENT_LIST


def _actual_type(
    error: dict[str, Any], arguments: dict[str, Any] | None = None,
) -> str:
    if error.get("type") == "missing":
        return "missing"
    value = error.get("input", _MISSING)
    if arguments is not None:
        value = _request_value(arguments, tuple(error.get("loc", ())))
        if value is _MISSING:
            return "missing"
    elif error.get("type") == "value_error" and value is None:
        # 自定义跨字段校验可能没有 input；不能把 Pydantic 合成的 None 当作用户显式 null。
        value = _MISSING
    result = "unknown"
    if value is _MISSING:
        return result
    if value is None:
        result = "null"
    elif isinstance(value, bool):
        result = "boolean"
    elif isinstance(value, str):
        result = "string"
    elif isinstance(value, dict):
        result = "object"
    elif isinstance(value, list):
        result = "array"
    elif isinstance(value, int):
        result = "integer"
    elif isinstance(value, float):
        result = "number"
    return result


def _request_value(arguments: dict[str, Any], location: tuple[Any, ...]) -> Any:
    value: Any = arguments
    for part in location:
        if isinstance(value, dict):
            value = value.get(part, _MISSING)
        elif isinstance(value, list) and isinstance(part, int):
            value = value[part] if 0 <= part < len(value) else _MISSING
        else:
            value = _MISSING
        if value is _MISSING:
            break
    return value


def _request_message(error: dict[str, Any], actual_type: str) -> str:
    """只解释已登记的服务端约束，不回显自定义异常文本或用户值。"""
    location = tuple(error.get("loc", ()))
    message = str(error.get("msg", ""))
    if location in {("title",), ("description",)}:
        name = str(location[0])
        if message == f"Value error, {name} is required in create mode":
            if actual_type == "missing":
                return f"新建卡片缺少必填字段 {name}。"
            if actual_type == "null":
                return f"新建卡片的 {name} 不能为 null。"
            return f"新建卡片必须提供有效的非空 {name} 字符串。"
    if location == ("sourceArtifactUrl",):
        if message == "Value error, sourceArtifactUrl must be a non-empty string":
            return "编辑来源无效：sourceArtifactUrl 必须是目标卡片的非空有效来源地址。"
    if message.endswith("cannot be null in edit mode"):
        return "编辑时该字段不能为 null。"
    return _message(str(error.get("type", "validation_error")))


def _message(error_type: str) -> str:
    messages = {
        "missing": "缺少必填字段。",
        "extra_forbidden": "此位置包含未声明字段。",
        "literal_error": "取值不在当前工具允许的枚举范围内。",
        "enum": "取值不在当前工具允许的枚举范围内。",
        "string_too_short": "字符串长度不足。",
        "string_too_long": "字符串长度超出限制。",
        "too_short": "容器中的元素数量不足。",
        "too_long": "容器中的元素数量超出限制。",
        "json_invalid": "JSON 语法不合法。",
    }
    if error_type in _TYPE_EXPECTATIONS:
        return "字段的 JSON 类型不符合要求。"
    return messages.get(error_type, "字段不符合当前工具或创建／编辑模式约束。")


def _repair_instruction(error: dict[str, Any], guide: _Guidance) -> str:
    error_type = str(error.get("type", "validation_error"))
    prefix = ""
    if error_type == "extra_forbidden":
        prefix = "核对字段归属；"
    elif error_type in _TYPE_EXPECTATIONS:
        prefix = "按 expected 重构 JSON 类型；"
    message = str(error.get("msg", ""))
    location = tuple(error.get("loc", ()))
    edit_null = message.endswith("cannot be null in edit mode")
    if edit_null and location != ("sourceArtifactUrl",):
        return "未修改则省略继承；修改时提交完整合法值，不传 null。"
    return prefix + guide.instruction


def _mode_guidance(
    guide: _Guidance, location: tuple[Any, ...], arguments: dict[str, Any] | None,
) -> _Guidance:
    result = guide
    if arguments is not None and location in {("title",), ("description",)}:
        if "sourceArtifactUrl" in arguments:
            result = _Guidance("非空字符串；未修改可省略继承", "修改时填写合法值，否则省略继承。")
        else:
            instruction = (
                "按有效需求填写短标题。" if location == ("title",) else "按有效需求填写简短说明。"
            )
            result = _Guidance("非空字符串", instruction)
    return result


def _request_retry_instruction(issues: list[PreflightIssue]) -> str:
    instruction = _RETRY_INSTRUCTION
    has_binding_issue = False
    has_structure_issue = False
    for issue in issues:
        if issue.path == "/dataCapabilityIds" or issue.path.startswith("/candidateDataBindings"):
            has_binding_issue = True
        if issue.code in {
            "REQUEST_DICT_TYPE", "REQUEST_MODEL_TYPE", "REQUEST_MODEL_ATTRIBUTES_TYPE",
            "REQUEST_LIST_TYPE",
        }:
            has_structure_issue = True
        if issue.path in {"/arguments", "/params", "/content"}:
            has_structure_issue = True
        parts = issue.path.split("/")
        if len(parts) == 4 and parts[1] == "candidateEventCandidates":
            if parts[3] in {"action", "actionTemplate"}:
                has_structure_issue = True
    if has_structure_issue:
        instruction += "先修外层结构再复核下层字段；未列出的问题不代表已通过后续检查。"
    if has_binding_issue:
        instruction += "数据绑定变化后复查权限。"
    return instruction


def request_validation_feedback(
    exc: ValidationError, operation: str, *, arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    issues = []
    # 仅读取 input 的 JSON 类型；不回传值、原始异常消息或 ctx。
    for error in exc.errors(include_context=False, include_input=True):
        location = tuple(error.get("loc", ()))
        error_type = str(error.get("type", "validation_error"))
        guide = _guidance(location, operation)
        guide = _mode_guidance(guide, location, arguments)
        expected = guide.expected
        expected_type = _TYPE_EXPECTATIONS.get(error_type)
        if expected_type is not None:
            expected = f"{expected_type}；{expected}"
        retryable = _is_business_error(location, error_type)
        actual_type = _actual_type(error, arguments)
        instruction = _repair_instruction(error, guide)
        if not retryable:
            instruction = (
                "核对工具链路的上下文传递，不要手工填写身份或设备字段。"
            )
        issues.append(
            PreflightIssue(
                code=f"REQUEST_{error_type.upper()}",
                path=_pointer(location),
                message=_request_message(error, actual_type),
                expected=expected,
                actualType=actual_type,
                agentAction=AgentAction.FIX_AND_RETRY if retryable else AgentAction.STOP,
                retryable=retryable,
                repairInstruction=instruction,
                referenceSource=guide.reference or f"{operation} 当前工具 Schema",
            )
        )
    retryable = bool(issues) and all(issue.retryable for issue in issues)
    return {
        "stage": "requestValidation",
        "modelCalled": False,
        "retryable": retryable,
        "requiredActions": ["FIX_AND_RETRY" if retryable else "STOP"],
        "agentInstruction": (
            _request_retry_instruction(issues)
            if retryable
            else "停止本轮调用并核对工具上下文，不编造身份或设备字段。"
        ),
        "issues": [issue.model_dump(mode="json") for issue in issues],
    }


def _is_business_error(location: tuple[Any, ...], error_type: str) -> bool:
    if not location:
        return False
    # 业务对象误套包络是可修正的 extra；真正缺失／非法的传输上下文仍停止。
    wrapper_extra = error_type == "extra_forbidden" and len(location) == 1
    if wrapper_extra and location[0] in {"content", "session", "utterance"}:
        return True
    return location[0] not in _TRANSPORT_FIELDS


def request_envelope_feedback() -> dict[str, Any]:
    """传输请求无法解析时，不把修补传输帧的任务交给主 Agent。"""
    return {
        "stage": "requestEnvelope",
        "modelCalled": False,
        "retryable": False,
        "requiredActions": ["STOP"],
        "agentInstruction": (
            "请求 JSON 无法解析，停止本轮调用并核对序列化链路；"
            "仅按工具定义提交 arguments 对象，不手工拼接传输包络。"
        ),
    }


def terminal_feedback(stage: str) -> dict[str, Any]:
    """没有明确改参依据的失败不授权自动重调或切换任务模式。"""
    return {
        "stage": stage,
        "retryable": False,
        "requiredActions": ["STOP"],
        "agentInstruction": (
            "停止本轮自动调用，按实际失败原因回复；保留原有效来源。"
        ),
    }
