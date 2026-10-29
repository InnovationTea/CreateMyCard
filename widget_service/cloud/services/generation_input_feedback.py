"""Plan 阶段的必要动态输入缺口合同；不选择能力、不补绑定、不改变校验规则。"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from core.errors import ErrorCode
from models.preflight import AgentAction, PreflightIssue
from services.argument_json_recovery import DECODER
from services.compact_plan_output import normalize_plan_output

REPORT_MISSING_DATA = "report_missing_data"
MISSING_DATA_PLAN_INSTRUCTION = (
    "先判断用户需要的数据来源及更新行为。没有动态字段不等于缺少数据；用户提供的固定文字、"
    "已采用的静态事实及仅快捷动作需求按原合同提交正常计划。仅当用户明确需要读取或刷新真实"
    "动态数据、而当前 dataModelSchema 没有足够字段时，改为提交 report_missing_data。"
    "已有满足需求的字段时应正确引用 dataId，不以报告规避规划、布局或容量错误。"
    "每项 description 简述待核对的数据需求，sourceQuote 逐字引用本轮 userQuery 的连续原文；"
    "不提供能力ID、绑定路径、参数、样例读数或执行指令，不将动态需求改成静态文字。"
    "只提交一个调用对象，不与 submit_card_plan 混合，不输出DSL；收到缺口后由主Agent核对"
    "真实可用性及权限，报告自身不证明有可用能力。"
)


class MissingDataRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    description: str = Field(min_length=1, max_length=200)
    sourceQuote: str = Field(min_length=1, max_length=512)


class MissingDataReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    requirements: list[MissingDataRequirement] = Field(min_length=1, max_length=8)


class MissingDataReportValidationError(ValueError):
    """报告自身不合法，消费既有 Plan 提交预算，不授权上游补参。"""

    def __init__(self, message: str) -> None:
        self.errors = (message,)
        super().__init__(message)


class MissingDataInputError(ValueError):
    """合法缺口报告交回主 Agent；微服务不使用相同缺失输入内部重跑。"""

    error_code = ErrorCode.GENERATION_INPUT_INCOMPLETE
    code = ErrorCode.GENERATION_INPUT_INCOMPLETE

    def __init__(self, report: MissingDataReport) -> None:
        self.report = report
        super().__init__("生成所需的动态数据输入不完整。")

    def details(self) -> dict[str, Any]:
        issues = []
        for requirement in self.report.requirements:
            issues.append(PreflightIssue(
                code="REQUIRED_DATA_INPUT_MISSING", path="/candidateDataBindings",
                message=requirement.description,
                expected="必要动态数据具有本轮真实可用的绑定和完整展示字段",
                agentAction=AgentAction.FIX_AND_RETRY, retryable=True,
                repairInstruction=(
                    "仅用本轮可用能力补齐绑定、参数或展示字段，复查最终集合权限；不猜测能力或读数。"
                ),
                referenceSource="本轮能力概述、完整数据定义及用户有效需求",
            ).model_dump(mode="json"))
        return {
            "stage": "generationInput", "modelCalled": True, "retryable": True,
            "requiredActions": ["REFRESH_CAPABILITIES", "FIX_AND_RETRY"],
            "agentInstruction": (
                "核对本轮可用数据能力，补齐全部 issues 后提交完整 invoke.arguments 重试，"
                "沿用三次总调用预算。缺必要业务值先澄清，核心不支持时停止。"
            ),
            "issues": issues,
        }


def missing_data_tool() -> dict[str, Any]:
    return {
        "name": REPORT_MISSING_DATA,
        "description": "仅当用户明确需要动态数据而本轮输入不足时，交回主 Agent 核对补齐。",
        "parameters": MissingDataReport.model_json_schema(),
    }


def parse_missing_data_report(
    raw_output: str, user_query: str, *, allow_report: bool,
) -> MissingDataReport | None:
    result: MissingDataReport | None = None
    try:
        payload = DECODER.decode(normalize_plan_output(raw_output).text)
    except ValueError:
        payload = None  # 非本合同的输出仍由原 Plan 解析器诊断。
    if not isinstance(payload, dict) or payload.get("name") != REPORT_MISSING_DATA:
        return result
    if not allow_report:
        raise MissingDataReportValidationError("编辑不允许 report_missing_data 或扩大数据集合。")
    if set(payload) != {"name", "arguments"}:
        raise MissingDataReportValidationError("report_missing_data 仅允许 name、arguments。")
    try:
        report = MissingDataReport.model_validate(payload.get("arguments"), strict=True)
    except ValidationError as exc:
        raise MissingDataReportValidationError(
            "report_missing_data.arguments 必须含1至8项requirements；每项仅含非空"
            "description（最多200字）、sourceQuote（最多512字），不得提交能力、绑定或读数。"
        ) from exc
    for requirement in report.requirements:
        if requirement.sourceQuote not in user_query:
            raise MissingDataReportValidationError("sourceQuote 必须是本轮有效需求的连续原文。")
    result = report
    return result
