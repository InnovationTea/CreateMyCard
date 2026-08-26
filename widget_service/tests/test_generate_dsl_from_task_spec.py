# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import json

import pytest

from config.config import get_settings
from generate_dsl_from_task_spec import generate_dsl_from_task_spec


@pytest.mark.asyncio
async def test_generate_dsl_from_task_spec_reuses_compact_pipeline(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_a2ui_model_mock", True)
    task_spec = {
        "userQuery": "生成一张简洁的欢迎卡片",
        "size": "2x2",
        "eventCandidates": [],
        "dataModelSchema": {},
        "assetCandidates": [],
    }

    generated = await generate_dsl_from_task_spec(task_spec)

    assert generated.compact_dsl
    messages = [json.loads(line) for line in generated.dsl.splitlines()]
    assert len(messages) == 3
    assert "createSurface" in messages[0]
    assert "updateComponents" in messages[1]
    assert "updateDataModel" in messages[2]
