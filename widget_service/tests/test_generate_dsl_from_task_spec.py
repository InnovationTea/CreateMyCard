# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import json
import re

import pytest

from config.config import get_settings
from generate_dsl_from_task_spec import generate_dsl_from_task_spec


@pytest.mark.asyncio
@pytest.mark.parametrize("photos_enabled", [False, True])
async def test_generate_dsl_from_task_spec_reuses_compact_pipeline(monkeypatch, photos_enabled):
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_a2ui_model_mock", True)
    monkeypatch.setattr(settings, "enable_photo_background_theme", photos_enabled)
    task_spec = {
        "userQuery": "生成一张简洁的欢迎卡片",
        "size": "2x2",
        "eventCandidates": [],
        "dataModelSchema": {},
        "assetCandidates": [],
    }

    generated = await generate_dsl_from_task_spec(task_spec)

    assert generated.compact_dsl
    assert not re.search(r"#[0-9A-Fa-f]{6,8}", generated.compact_dsl)
    assert "@theme:" not in generated.dsl
    if photos_enabled:
        assert "bg_ux_texture_" in generated.dsl
        assert "#FF8FADCC" in generated.dsl
        assert "linearGradient" not in generated.dsl
    else:
        assert "linearGradient" in generated.dsl
    messages = [json.loads(line) for line in generated.dsl.splitlines()]
    assert len(messages) == 3
    assert "createSurface" in messages[0]
    assert "updateComponents" in messages[1]
    assert "updateDataModel" in messages[2]
