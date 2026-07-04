from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from api.schemas import (
    CapabilityOverviewRequest,
    DataCapabilitySchemasRequest,
    GenerateWidgetCardRequest,
    ToolDispatchRequest,
)
from services.widget_generation_service import WidgetGenerationService

router = APIRouter(prefix="/api/v1")


def get_service() -> WidgetGenerationService:
    """创建卡片生成服务对象。

    入参：无。
    出参：WidgetGenerationService 实例。
    """
    return WidgetGenerationService()


@router.post("/widget/capability-overview")
async def get_widget_capability_overview(request: CapabilityOverviewRequest):
    """HTTP 获取能力概述。

    入参：
    - request：包含 locale、appVersion、romVersion 等版本上下文。
    出参：数据能力概述，以及全量事件能力和素材清单。
    """
    return get_service().get_widget_capability_overview(request)


@router.post("/widget/data-capability-schemas")
async def get_data_capability_schemas(request: DataCapabilitySchemasRequest):
    """HTTP 获取数据能力完整 schema。

    入参：
    - request：包含待查询的数据能力 ID 列表和版本上下文。
    出参：已注册能力的完整 schema，以及缺失能力 ID 列表。
    """
    return get_service().get_data_capability_schemas(request)


@router.post("/tools/{tool_name}")
async def dispatch_tool(tool_name: str, request: ToolDispatchRequest):
    """HTTP 工具分发入口。

    入参：
    - tool_name：工具能力名称。
    - request：工具参数包装对象。
    出参：对应工具能力的响应；生成能力会提示改走 WebSocket。
    """
    # 前两个工具能力保持 HTTP 调用；生成能力使用 WebSocket，便于后续返回进度或流式结果。
    service = get_service()
    if tool_name == "getWidgetCapabilityOverview":
        return service.get_widget_capability_overview(
            CapabilityOverviewRequest(**request.arguments)
        )
    if tool_name == "getDataCapabilitySchemas":
        return service.get_data_capability_schemas(
            DataCapabilitySchemasRequest(**request.arguments)
        )
    if tool_name == "generateWidgetCard":
        raise HTTPException(
            status_code=400,
            detail="generateWidgetCard uses WebSocket: /api/v1/ws/widget/generate",
        )
    raise HTTPException(status_code=404, detail=f"Unknown tool: {tool_name}")


@router.websocket("/ws/widget/generate")
async def generate_widget_card_ws(websocket: WebSocket):
    """WebSocket 卡片生成入口。

    入参：
    - websocket：客户端 WebSocket 连接。
    出参：无；服务端通过 WebSocket 返回生成结果或错误消息。
    """
    # 协议：客户端发送 requestId 和生成参数，
    # 服务端带同一 requestId 返回结果。
    await websocket.accept()
    await websocket.send_json(
        {
            "type": "ready",
            "tool": "generateWidgetCard",
            "message": "Send GenerateWidgetCardRequest JSON to start generation.",
        }
    )
    service = get_service()
    try:
        while True:
            payload = await websocket.receive_json()
            request_id = payload.get("requestId")
            arguments = payload.get("arguments", payload)
            try:
                result = service.generate_widget_card(GenerateWidgetCardRequest(**arguments))
                await websocket.send_json(
                    {
                        "type": "generateWidgetCardResult",
                        "requestId": request_id,
                        "data": result.model_dump(mode="json", exclude_none=True),
                    }
                )
            except ValidationError as exc:
                await websocket.send_json(
                    {
                        "type": "error",
                        "requestId": request_id,
                        "errorCode": "INVALID_ARGUMENTS",
                        "message": "Invalid generateWidgetCard arguments.",
                        "details": exc.errors(),
                    }
                )
            except Exception as exc:
                await websocket.send_json(
                    {
                        "type": "error",
                        "requestId": request_id,
                        "errorCode": "FAILED",
                        "message": str(exc),
                    }
                )
    except WebSocketDisconnect:
        return
