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
    "issues.path 用于定位错误，请修正下一次 invoke.arguments 的完整业务对象；"
    "不要手工构造 WebSocket content、顶层镜像、设备或会话包络。"
    "逐项处理全部 issues；先修外层容器和层级，再复核对应项全部必填及下层参数，"
    "返回列表不保证已列出被外层错误遮蔽的问题。"
    "保留原需求、创建／编辑模式、有效来源、用户尺寸要求及其它合法数据、事件和素材候选；"
    "不得只提交局部补丁、原样重试、猜值或清空候选以规避错误。"
    "绑定或数据集合变化后重新检查权限；缺必要业务值时先澄清，核心能力不支持时停止。"
    "修正后串行调用并等待最终结果，不超过本轮既有调用预算；"
    "相同错误重复且无新修正依据时停止。"
)


@dataclass(frozen=True)
class _Guidance:
    expected: str
    instruction: str
    reference: str = ""


_DATA_LIST = _Guidance(
    "JSON 对象数组，每项包含 capabilityId、arguments、writeResultTo，可选 candidateOutputFields",
    "按本轮已选数据构造对象数组，每项独立保留 ID、静态调用参数和写入路径；"
    "不能仅传 ID、定义对象或序列化字符串，不通过清空数据候选规避错误。",
    "getDataCapabilitySchemas.dataCapabilities[]",
)
_EVENT_LIST = _Guidance(
    "JSON 对象数组，每项为 {capabilityId, action:{call,args}}",
    "从本轮事件概述构造候选对象数组：capabilityId 使用该事件的 ID，"
    "action 仅取对应 actionTemplate 的 call、args，保留固定值及空字符串，"
    "只替换已声明的动态参数；不整体复制含 id、Schema 或 dynamicArguments 的定义对象。",
    "getWidgetCapabilityOverview.eventCapabilities[]",
)
_EVENT_ID = _Guidance(
    "本轮事件概述中的 ID 字符串，位于候选项的 capabilityId",
    "从本轮事件概述核对该动作的 ID 后填写 capabilityId；"
    "若 ID 误放在 id、action 或模板内部，只能核对后放回候选项外层，"
    "不得根据文案、URI 或相近名称猜 ID，也不把 ID 写进 call。",
    "getWidgetCapabilityOverview.eventCapabilities[].id",
)
_EVENT_ACTION = _Guidance(
    "JSON 对象 {call,args}，args 为 JSON 对象",
    "将本轮对应模板中 call、args 的完整值放入 action；仅保留这两个执行字段，"
    "保留固定值和空字符串，只填写声明的动态参数。"
    "不把整个事件定义放入 action，不提交 id、actionTemplate 或 dynamicArguments 定义；"
    "已有动作或 ID 发生冲突时先核对本轮概述，不覆盖实际参数。",
    "getWidgetCapabilityOverview.eventCapabilities[].actionTemplate/dynamicArguments",
)
_EVENT_ARGS = _Guidance(
    "本轮动作模板的完整 args 对象及其已声明动态参数",
    "按本轮该事件的 args 模板核对字段层级、类型、固定值及动态参数允许值；"
    "仅在 dynamicArguments 声明的相对路径填入有来源的值，不把动态参数定义作为执行参数。"
    "依赖数据的引用须有对应绑定，列表引用使用同一展示对象的明确数字下标，不保留 i 或猜第 0 项。",
    "getWidgetCapabilityOverview.eventCapabilities[].actionTemplate/dynamicArguments",
)
_DATA_ARGS = _Guidance(
    "符合本轮 inputSchema 的静态 JSON 参数对象；无参能力使用 {}",
    "按本轮该数据能力 inputSchema 构造静态参数对象，满足字段名、层级、类型、必填和取值范围；"
    "不要把对象序列化为字符串，不使用 DSL 绑定或表达式。"
    "值从用户要求或已核验来源取得，缺必要业务值时澄清，不填 null、空字符串或假值代替。",
    "getDataCapabilitySchemas.dataCapabilities[].inputSchema",
)
_DATA_FIELDS = {
    "capabilityId": _Guidance(
        "本轮可用数据能力 ID 字符串，位于候选项的 capabilityId",
        "从本轮可用数据概述核对该数据能力 ID，并填写到候选项外层 capabilityId；"
        "不把完整数据定义或仅含 ID 的数组当作数据绑定。",
        "getWidgetCapabilityOverview.dataCapabilities[].id",
    ),
    "arguments": _DATA_ARGS,
    "writeResultTo": _Guidance(
        "位于 /data/ 下且与其它绑定不相同、不互为父子的 JSON Pointer 字符串",
        "优先使用本轮数据定义的 defaultWriteResultTo；自定义路径需符合 JSON Pointer 转义，"
        "并检查与全部其它绑定不相同、不覆盖。编辑保留原能力及写入路径，不随意改根。",
        "getDataCapabilitySchemas.dataCapabilities[].defaultWriteResultTo",
    ),
    "candidateOutputFields": _Guidance(
        "可选字符串数组，每项为本轮 outputSchema 可推导的叶子 JSON Pointer",
        "从本轮 outputSchema 选择所需展示字段，保留同一对象和时间范围；"
        "数组用实际非负整数下标，不复制完整 Schema、样例读数或用静态值代替动态字段。"
        "仅修正非法路径，不为过检删掉用户必需的展示字段。",
        "getDataCapabilitySchemas.dataCapabilities[].outputSchema",
    ),
}
_TOP_FIELDS = {
    "candidateDataBindings": _DATA_LIST,
    "candidateEventCandidates": _EVENT_LIST,
    "sourceArtifactUrl": _Guidance(
        "同一目标卡片最近有效结果的非空完整来源地址",
        "编辑只使用本会话目标卡片最近有效结果的来源，不猜地址、传空值、删除来源或切换创建；"
        "无法可靠恢复有效来源时停止。",
    ),
    "size": _Guidance(
        "2x2 或 2x4",
        "仅填写 2x2 或 2x4，保留用户明确指定尺寸，不因参数错误擅自扩大尺寸。",
    ),
    "title": _Guidance(
        "新建为非空字符串；编辑未修改时可省略继承",
        "新建时填写符合有效需求的非空静态短标题，不从动态数据样例抄读数；"
        "编辑未改标题时省略继承，不用 null 或空字符串代替省略。",
    ),
    "description": _Guidance(
        "新建为非空字符串；编辑未修改时可省略继承",
        "新建时填写符合有效需求的非空静态短说明，不承诺未支持功能；"
        "编辑未改说明时省略继承，不用 null 或空字符串代替省略。",
    ),
    "userQuery": _Guidance(
        "包含本轮有效需求、全部明确约束及实际采用静态事实的非空字符串",
        "填写本轮有效需求及实际采用的完整静态事实；没有原始需求时先澄清，"
        "不把技术字段或示例当需求，不删除核心要求来规避错误。",
    ),
    "candidateAssetIds": _Guidance(
        "本轮素材概述中 ID 组成的字符串数组",
        "仅使用本轮素材概述中的 ID，不填写资源路径、完整定义或伪造 ID；"
        "无所需匹配素材时可为空，不能删除已有必要素材来规避其它参数错误。",
        "getWidgetCapabilityOverview.assetCandidates[].id",
    ),
    "options": _Guidance(
        "当前工具 Schema 明确开放的配置对象",
        "仅在当前运行时工具 Schema 开放时提交 options，按声明的布尔等类型填写；"
        "未开放则不提交，不借配置扩大降级、权限或重试范围。",
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
                "下一次 invoke.arguments 直接填写 userQuery 及本轮完整业务参数，"
                "不要再次包 arguments、params、content 或整个工具调用／传输包络；"
                "从本轮已有业务对象恢复合法值，不猜设备或会话字段。",
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
                "核对字段是否错名、错层级或误复制了定义元数据；按本轮定义放回正确业务位置并保留实际值。",
            ),
        )
    return _Guidance(
        "当前工具 Schema 在该位置声明的类型和约束",
        "按当前工具 Schema 核对该嵌套字段，不因它与顶层字段同名而搬动或删除业务值。",
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
                "原样使用本轮对应模板的 call，不填写事件 ID、URI、能力名或自定义调用类型。",
                _EVENT_ACTION.reference,
            )
        return _EVENT_ACTION
    return _EVENT_LIST


def _actual_type(error: dict[str, Any]) -> str:
    if error.get("type") == "missing":
        return "missing"
    value = error.get("input", _MISSING)
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
    if error_type == "missing":
        prefix = "在 invoke.arguments 对应位置补齐必填字段；"
    elif error_type == "extra_forbidden":
        prefix = "先核对该字段的归属，实际业务值应保留到正确位置，纯定义元数据才移除；"
    elif error_type in _TYPE_EXPECTATIONS:
        prefix = (
            "按 expected 重新构造正确 JSON 类型；对象和数组不序列化成字符串，"
            "不强制转成字符串或用空值过检；"
        )
    elif error_type in {"literal_error", "enum"}:
        prefix = "核对本轮定义的允许值，不自创枚举或更改用户明确目标；"
    message = str(error.get("msg", ""))
    location = tuple(error.get("loc", ()))
    edit_null = message.endswith("cannot be null in edit mode")
    if edit_null and location != ("sourceArtifactUrl",):
        prefix += "编辑未改该字段则省略继承，明确修改则提交完整合法值，不传 null；"
    return prefix + guide.instruction


def request_validation_feedback(exc: ValidationError, operation: str) -> dict[str, Any]:
    issues = []
    # 仅读取 input 的 JSON 类型；不回传值、原始异常消息或 ctx。
    for error in exc.errors(include_context=False, include_input=True):
        location = tuple(error.get("loc", ()))
        error_type = str(error.get("type", "validation_error"))
        guide = _guidance(location, operation)
        expected = guide.expected
        expected_type = _TYPE_EXPECTATIONS.get(error_type)
        if expected_type is not None:
            expected = f"{expected_type}；{expected}"
        retryable = _is_business_error(location, error_type)
        instruction = _repair_instruction(error, guide)
        if not retryable:
            instruction = (
                "请求上下文缺失或无法定位业务字段，请停止本轮调用并核对工具链路；"
                "不要手工填写 content、镜像字段、设备或会话包络，不编造用户身份。"
            )
        issues.append(
            PreflightIssue(
                code=f"REQUEST_{error_type.upper()}",
                path=_pointer(location),
                message=_message(error_type),
                expected=expected,
                actualType=_actual_type(error),
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
            _RETRY_INSTRUCTION
            if retryable
            else "包含不可自动修复的上下文问题，请停止本轮调用并保留原有效来源；"
            "不手工构造传输包络或编造技术字段。"
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
            "服务端请求未能解析为合法 JSON，尚无法定位具体业务字段。"
            "请停止本轮自动调用并核对工具调用链路的参数序列化；"
            "主 Agent 仅按当前工具定义构造业务 arguments 对象，不手工拼接传输帧或包络，"
            "不从此错误猜测缺失业务值，不原样重复调用。"
        ),
    }


def terminal_feedback(stage: str) -> dict[str, Any]:
    """没有明确改参依据的失败不授权自动重调或切换任务模式。"""
    return {
        "stage": stage,
        "retryable": False,
        "requiredActions": ["STOP"],
        "agentInstruction": (
            "本轮没有可执行的入参修正依据，请停止自动调用并按真实状态回复；"
            "保留原有效来源，不猜修法、不改为新建或静态请求，不把失败结果当作成功。"
        ),
    }
