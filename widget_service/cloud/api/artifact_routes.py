# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from config.config import get_settings

router = APIRouter()

_ARTIFACT_FILE_RE = re.compile(
    r"artifact_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}\.md"
)


@router.get("/artifacts/{file_name}", response_class=FileResponse)
@router.head(
    "/artifacts/{file_name}",
    response_class=FileResponse,
    include_in_schema=False,
)
async def download_artifact(file_name: str) -> FileResponse:
    """下载服务生成的具名 Markdown artifact。"""
    if _ARTIFACT_FILE_RE.fullmatch(file_name) is None:
        raise HTTPException(status_code=404, detail="artifact not found")

    artifact_path = Path(get_settings().WORKSPACE_ROOT) / "mock_obs" / file_name
    if not artifact_path.is_file():
        raise HTTPException(status_code=404, detail="artifact not found")

    return FileResponse(
        path=artifact_path,
        media_type="text/markdown; charset=utf-8",
        filename=file_name,
        content_disposition_type="attachment",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
