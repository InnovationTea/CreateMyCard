"""手机＋耳机恢复必需信息，不改 W1 几何、动作与字符串电量合同。"""

import pytest

from models.generation import TaskSpec
from services.prompt_builder import PromptBuilder
from services.protocol_registry import DESIGN_COMPACT_PROFILE_ID, A2UIProtocolRegistry


def _task() -> TaskSpec:
    return TaskSpec(
        userQuery="查看手机剩余电量、耳机连接状态、耳机仓电量和左右耳机电量，点一下打开歌单。",
        size="2x4",
        dataModelSchema={"data": {
            "phoneBattery": {"batterySOCText": {
                "type": "string", "sampleValue": "68%", "description": "手机电量，已包含%",
            }},
            "earphone": {
                "isConnected": {"type": "boolean", "sampleValue": True},
                "batteryLevel": {"type": "integer", "sampleValue": 80},
                "leftBatteryLevel": {"type": "integer", "sampleValue": 76},
                "rightBatteryLevel": {"type": "integer", "sampleValue": 78},
            },
        }},
        eventCandidates=[{"call": "clickToDeeplink", "args": {
            "intentName": "Music", "bundleName": "", "abilityName": "",
            "uri": "hwmusic://com.huawei.hmsapp.music/showMusicList?code=a001&type=4",
        }}],
    )


@pytest.mark.parametrize("mode", ["create", "edit", "repair"])
def test_every_generation_mode_preserves_requested_earphone_information(mode: str) -> None:
    task = _task()
    builder = PromptBuilder()
    prompt = A2UIProtocolRegistry.read_design_prompt(DESIGN_COMPACT_PROFILE_ID)
    previous = '["root","Text",{"content":"旧卡片"}]'
    messages = builder.build_design_compact(
        task, prompt, previous_design_token=previous if mode == "edit" else None,
    )
    if mode == "repair":
        messages = builder.build_repair(
            messages, previous, [{"stage": "validation", "code": "TEST", "message": "测试"}],
            dsl_format=DESIGN_COMPACT_PROFILE_ID,
        )
    system = messages[0].get("content")
    assert isinstance(system, str)
    assert "W1-focus-aux" in system
    assert "136" in system and "130" in system and "59" in system
    assert "右上背板仍用最多两行显示耳机连接状态与耳机仓电量" in system
    assert "左耳、右耳电量各用一行 12/14fp" in system
    assert "音乐动作。动作直接绑定背板" in system
    assert "耳机仓/左右耳中最重要的一项电量信息" not in system
    assert "未要求的候选不强制显示" in system
    assert "不得把字符串绑定给 Progress" in system
    assert "也不得编造数值路径或总量" in system
    assert task.eventCandidates[0].args.get("uri", "").endswith("code=a001&type=4")
    assert builder._layout_scope(task) == "W1-focus-aux"
