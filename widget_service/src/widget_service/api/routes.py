from fastapi import APIRouter, HTTPException

from widget_service.api.schemas import (
    CapabilityOverviewRequest,
    DataCapabilitySchemasRequest,
    GenerateWidgetCardRequest,
    ToolDispatchRequest,
)
from widget_service.services.widget_generation_service import WidgetGenerationService

router = APIRouter(prefix="/api/v1")


def get_service() -> WidgetGenerationService:
    return WidgetGenerationService()


@router.post("/widget/capability-overview")
async def get_widget_capability_overview(request: CapabilityOverviewRequest):
    return get_service().get_widget_capability_overview(request)


@router.post("/widget/data-capability-schemas")
async def get_data_capability_schemas(request: DataCapabilitySchemasRequest):
    return get_service().get_data_capability_schemas(request)


@router.post("/widget/generate")
async def generate_widget_card(request: GenerateWidgetCardRequest):
    return get_service().generate_widget_card(request)


@router.post("/tools/{tool_name}")
async def dispatch_tool(tool_name: str, request: ToolDispatchRequest):
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
        return service.generate_widget_card(GenerateWidgetCardRequest(**request.arguments))
    raise HTTPException(status_code=404, detail=f"Unknown tool: {tool_name}")
