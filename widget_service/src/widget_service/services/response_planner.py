from widget_service.core.errors import ErrorCode, GenerationStatus
from widget_service.models.capability import RemovedCapability


class ResponsePlanner:
    def plan(
        self,
        requested_count: int,
        effective_count: int,
        removed: list[RemovedCapability],
        has_artifact: bool,
    ) -> tuple[GenerationStatus, str, str]:
        if not has_artifact:
            return (
                GenerationStatus.UNSUPPORTED,
                "当前设备上没有可用的数据能力或入口能力，暂时不能生成这类实时卡片。你可以试试天气、日历或系统状态类卡片。",
                ErrorCode.NO_EFFECTIVE_CAPABILITY.value,
            )
        if requested_count > 0 and effective_count == requested_count and not removed:
            return GenerationStatus.SUCCESS, "已为你生成可用的桌面卡片。", ""
        if removed:
            reasons = "、".join(sorted({item.userReadableReason for item in removed}))
            return GenerationStatus.DEGRADED, f"{reasons}，已先为你生成可用版本。", ""
        return GenerationStatus.SUCCESS, "已为你生成可用的桌面卡片。", ""
