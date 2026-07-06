from core.errors import ErrorCode, GenerationStatus
from models.capability import RemovedCapability
from models.service import ResponsePlan


class ResponsePlanner:
    """把内部生成结果转换成工具状态和用户可读话术。"""

    def plan(
        self,
        requested_count: int,
        effective_count: int,
        removed: list[RemovedCapability],
        has_artifact: bool,
    ) -> ResponsePlan:
        """规划生成接口响应状态。

        入参：
        - requested_count：用户候选数据能力数量。
        - effective_count：过滤后有效数据能力数量。
        - removed：被移除能力列表。
        - has_artifact：是否已生成 artifact。
        出参：结构化响应规划结果。
        """
        if not has_artifact:
            return ResponsePlan(
                status=GenerationStatus.UNSUPPORTED,
                message="当前设备上没有可用的数据能力或入口能力，暂时不能生成这类实时卡片。你可以试试天气、日历或系统状态类卡片。",
                errorCode=ErrorCode.NO_EFFECTIVE_CAPABILITY.value,
            )
        if requested_count > 0 and effective_count == requested_count and not removed:
            return ResponsePlan(
                status=GenerationStatus.SUCCESS,
                message="已为你生成可用的桌面卡片。",
            )
        if removed:
            reasons = "、".join(sorted({item.userReadableReason for item in removed}))
            return ResponsePlan(
                status=GenerationStatus.DEGRADED,
                message=f"{reasons}，已先为你生成可用版本。",
            )
        return ResponsePlan(
            status=GenerationStatus.SUCCESS,
            message="已为你生成可用的桌面卡片。",
        )
