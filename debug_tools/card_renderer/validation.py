"""单轮线上校验回放入口；不得用缺失上下文拼造通过结果。"""

from __future__ import annotations

import json
from typing import Any

from debug_tools.card_renderer.validation_replay import (
    ReplayContext,
    prepare_replay,
    replay_validation,
)
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1, max_length=1_000_000)
    context: dict[str, Any] | None = None


def _input_notes(source: str) -> list[dict[str, Any]]:
    """原文 JSONL 提示不参与线上判定，保留线上确定性容错语义。"""
    notes: list[dict[str, Any]] = []
    for number, line in enumerate(source.splitlines(), 1):
        if not line.strip() or line.strip().startswith("```"):
            continue
        try:
            json.loads(line)
        except json.JSONDecodeError as exc:
            notes.append(
                {
                    "code": "DSL_INPUT_JSON_INVALID",
                    "severity": "warning",
                    "stage": "input",
                    "sourceKind": "original",
                    "sourceLine": number,
                    "sourceColumn": exc.colno,
                    "message": exc.msg,
                }
            )
    return notes


def inspect_dsl(request: ValidationRequest) -> dict[str, Any]:
    notes = _input_notes(request.source)
    try:
        context = ReplayContext.model_validate(request.context)
        prepared = prepare_replay(context)
    except (ValueError, OSError) as exc:
        # Pydantic ValidationError 也是 ValueError，保留明确的缺失位置。
        message = str(exc)
        if isinstance(exc, ValidationError) and request.context is None:
            message = "请提供原始产物与执行上下文，裸 DSL 无法复现线上完整校验。"
        result = {
            "status": "context_required",
            "valid": False,
            "complete": False,
            "diagnostics": [
                {
                    "stage": "context",
                    "sourceKind": "context",
                    "code": "REPLAY_CONTEXT_INVALID",
                    "message": message,
                }
            ],
            "stages": [{"name": "校验上下文", "status": "blocked"}],
            "warnings": [],
            "genui": None,
            "previewError": None,
            "size": None,
            "sources": {"original": request.source},
        }
    else:
        result = replay_validation(request.source, context, prepared)
    result["inputNotes"] = notes
    return result


def register_validation_routes(app: FastAPI) -> None:
    app.post("/debug/renderer/validate")(inspect_dsl)
