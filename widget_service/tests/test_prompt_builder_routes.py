# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.

import pytest

from config.config import get_settings
from models.generation import EventAction, TaskSpec
from services.prompt_builder import PromptBuilder


def test_single_business_dual_action_selects_v03(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        get_settings(),
        "CONFIG",
        {"fusion_ball_min_prd_version": "11.7.5.205"},
    )
    actions = [
        EventAction(call="clickToIntent", args={"intentName": "PowerSaving"}),
        EventAction(call="clickToIntent", args={"intentName": "NavigateHome"}),
    ]
    task_spec = TaskSpec(
        userQuery="查看电量，并提供省电和回家两个入口",
        size="2x2",
        eventCandidates=actions,
        dataModelSchema={
            "data": {
                "phoneBattery": {
                    "batterySOC": {"type": "integer"},
                    "chargingStatusDesc": {"type": "string"},
                }
            }
        },
    )

    prompt = PromptBuilder().build_design_compact(task_spec, "design rules")
    system_prompt = prompt[0]["content"]

    assert "示例三（2x2-V03）" in system_prompt
    assert "示例一（2x2-V01）" not in system_prompt
    assert "本次 TaskSpec 是 2x2 单业务且恰好提供两个动作" in system_prompt
    assert "所有保留数据合并成一行" in system_prompt
