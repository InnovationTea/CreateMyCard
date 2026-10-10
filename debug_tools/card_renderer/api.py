"""卡片预览使用的 Python Compact DSL 转换接口。"""

from __future__ import annotations

from typing import Literal

from debug_tools.paths import ensure_cloud_import_path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field


class ConvertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1, max_length=1_000_000)
    size: Literal["auto", "2x2", "2x4"] = "auto"


class ConvertResponse(BaseModel):
    genui: str
    size: Literal["2x2", "2x4"]


def register_renderer_conversion_routes(app: FastAPI) -> None:
    """复用云侧转换器，转换端点在 SPA fallback 之前注册。"""

    ensure_cloud_import_path()

    from services.compact_dsl_a2ui_converter import (
        CompactDslConversionError,
        ComponentRow,
        convert_compact_dsl_to_a2ui,
        parse_compact_dsl_rows,
    )

    @app.post("/debug/renderer/convert", response_model=ConvertResponse)
    def convert_for_preview(request: ConvertRequest) -> ConvertResponse:
        size: Literal["2x2", "2x4"] = "2x2"
        try:
            if request.size == "auto":
                for row in parse_compact_dsl_rows(request.source):
                    if not isinstance(row, ComponentRow):
                        continue
                    width = row.props.get("width")
                    if isinstance(width, (int, float)) and width >= 240:
                        size = "2x4"
                        break
            else:
                size = request.size
            genui = convert_compact_dsl_to_a2ui(request.source, size=size)
        except CompactDslConversionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return ConvertResponse(genui=genui, size=size)
