# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.

from enum import Enum


class StatusCode(Enum):
    """StatusCode enum"""
    """根据 StatusCode 解析对应的异常类。

    StatusCode 命名遵循规范：{SCOPE}_{DETAIL}_{SUBJECT}_{FAILURE_TYPE}

    采用分层匹配策略确保异常类型的准确映射：

    1. **手动覆盖 (Manual Override)** - 优先级最高
       - 用于处理特殊情况或遗留兼容性
       - 通过 MANUAL_OVERRIDES 字典显式指定 StatusCode -> 异常类的映射
       - 例如：某些跨层级的复合错误可能需要特殊处理

    2. **范围规则匹配 (Range Rule Matching)** - 针对有作用域的状态码
       - 适用于带有 SCOPE 前缀的状态码（LLM_*、TOOL_*、FLOW_*）
       - 根据数值区间范围确定异常类型

    3. **关键词规则匹配 (Keyword Rule Matching)** - 针对无作用域或未覆盖的状态码
       - 通过 DETAIL、SUBJECT、FAILURE_TYPE 中的关键词进行智能匹配
       - 关键词分类示例：
         * VALIDATE/INVALID/PARAM/MISSING/FORMAT/SCHEMA
           → ValidationError（参数/数据验证失败）
         * CONFIG/INIT/CONNECT/SERVICE/PROVIDER/QUEUE
           → FrameworkError（框架级初始化/连接失败）
         * TIMEOUT/EXECUTE/EXECUTION/PROCESS/RUNTIME/STREAM/RESPONSE
           → ExecutionError（运行时执行失败）

    4. **兜底 (Absolute Fallback)** - 优先级最低
       - 当上述规则都未匹配时，默认返回 ExecutionError
       - 确保任何状态码都能映射到有效的异常类

    Note:
        - 建议新增 StatusCode 时遵循命名规范，以确保自动映射的准确性
        - 如果关键词规则与范围规则冲突，范围规则优先（对于有作用域的状态码）
        - 只有在特殊情况下才使用 MANUAL_OVERRIDES，优先依赖自动规则
    """

    SUCCESS = (0, "success")
    ERROR = (-1, "error")

    # =============================================================================================================
    # 101. LLM 调用 101000–101999
    # =============================================================================================================

    #   101000–101049  LLMTimeoutError        超时相关
    LLM_CALL_MODEL_TIMEOUT = (
        101000, "llm call model timeout ({timeout}s), reason: {error_msg}")

    #   101050–101099  LLMExecutionError      执行相关
    LLM_CALL_RESPONSE_EMPTY = (
        101050, "llm call response is empty, reason: {error_msg}")

    #   101100–101149  LLMDependencyError     依赖调用相关
    LLM_CALL_PROVIDER_CALL_FAILED = (
        101100, "llm call provider call failed, reason: {error_msg}")

    #   101150–101199  LLMDataError           数据处理相关
    LLM_VALIDATE_ASSERTION_RUNTIME_ERROR = (
        101150, "llm validate assertion runtime error, reason: {error_msg}")

    LLM_PARSE_FUNCTION_CALL_PROCESS_ERROR = (
        101151, "llm parse function call process error, reason: {error_msg}")

    #   101200–101249  LLMConfigurationError  配置相关
    LLM_VALIDATE_INPUT_PARAM_ERROR = (
        101200, "llm validate input parameter error, reason: {error_msg}")

    # =============================================================================================================
    # 102. Tool 工具相关 102000–102999
    # =============================================================================================================

    TOOL_NOT_FOUND = (
        102000, "tool not found, reason: {error_msg}")

    TOOL_ARGUMENTS_INVALID = (
        102050, "tool arguments parameter error, reason: {error_msg}")

    TOOL_VALIDATE_FILEPATH_INVALID = (
        102051, "tool validate filepath is invalid, reason: {error_msg}")

    TOOL_VALIDATE_FILENAME_INVALID = (
        102052, "tool validate filename is invalid, reason: {error_msg}")

    TOOL_VALIDATE_ACCESS_INVALID = (
        102100, "tool validate access is invalid, reason: {error_msg}")

    TOOL_EXECUTE_TIMEOUT = (
        102150, "tool execute timeout ({timeout}s), reason: {error_msg}")

    TOOL_EXECUTE_TASK_EXECUTION_ERROR = (
        102200, "tool execute task execution error, reason: {error_msg}")

    TOOL_GENERATE_CONTENT_PROCESS_ERROR = (
        102201, "tool generate content process error, reason: {error_msg}")

    TOOL_SEARCH_CONTENT_CALL_FAILED = (
        102250, "tool search content call failed, reason: {error_msg}")

    TOOL_DEPENDENCY_CALL_FAILED = (
        102251, "tool dependency call failed, reason: {error_msg}")

    TOOL_ACQUIRE_SANDBOX_INIT_FAILED = (
        102252, "tool acquire sandbox initialization failed, reason: {error_msg}")

    TOOL_CONVERT_CONTENT_PROCESS_ERROR = (
        102300, "tool convert content process error, reason: {error_msg}")

    TOOL_EXTRACT_DATA_PROCESS_ERROR = (
        102301, "tool extract data process error, reason: {error_msg}")

    TOOL_VALIDATE_DATA_INVALID = (
        102302, "tool validate data is invalid, reason: {error_msg}")

    TOOL_RUNTIME_CONFIG_ERROR = (
        102350, "tool runtime config error, reason: {error_msg}")

    TOOL_OPERATE_FILE_PROCESS_ERROR = (
        102450, "tool operate file process error, reason: {error_msg}")

    # =============================================================================================================
    # 103. Flow 流程相关 103000–103999
    # =============================================================================================================

    FLOW_EXECUTION_ERROR = (
        103000, "flow execution error, reason: {error_msg}")

    FLOW_CALL_NETWORK_CALL_FAILED = (
        103050, "flow call network call failed, reason: {error_msg}")

    FLOW_SEND_MESSAGE_CALL_FAILED = (
        103051, "flow send message call failed, reason: {error_msg}")

    FLOW_PARSE_JSON_PROCESS_ERROR = (
        103100, "flow parse json process error, reason: {error_msg}")

    FLOW_VALIDATE_INPUT_MESSAGE_ERROR = (
        103101, "flow validate input message error, reason: {error_msg}")

    FLOW_TIMEOUT_ERROR = (
        103150, "flow execution timeout, reason: {error_msg}"
    )

    FLOW_CONFIGURATION_ERROR = (
        103200, "flow configuration error, reason: {error_msg}"
    )

    def __init__(self, code: int, msg: str):
        """Validate and initialize enum member values.

        Args:
            code: integer status code
            msg: error message template (supports str.format placeholders)
        """
        if not isinstance(code, int):
            raise TypeError(f"StatusCode code must be int, got {type(code)!r} for {self.name}")
        if not isinstance(msg, str):
            raise TypeError(f"StatusCode errmsg must be str, got {type(msg)!r} for {self.name}")
        self._code = code
        self._msg = msg

    @property
    def code(self) -> int:
        """Return the integer error code."""
        return self._code

    @property
    def errmsg(self) -> str:
        """Return the error message template (unformatted)."""
        return self._msg