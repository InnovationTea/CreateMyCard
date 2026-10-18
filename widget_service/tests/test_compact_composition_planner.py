"""Compact 有限组合搜索的动作布局回归。"""

from services.compact_composition_planner import (
    composition_structure_blueprint,
    feasible_composition_candidates,
)


def test_anchor_candidate_uses_circle_button_from_plan_preference() -> None:
    plan = {
        "info_required": [
            {
                "requirement": "会议提醒",
                "dataId": "/data/calendar/reminder",
                "componentHints": ["EmphasisText"],
            },
            {
                "requirement": "更新时间",
                "dataId": "/data/meta/updatedAt",
                "componentHints": ["SecondaryBody"],
            },
            {
                "requirement": "打开免打扰设置",
                "actionId": "event.open.settings.dnd",
                "componentHints": ["CircleButton", "PillButton"],
            },
        ],
        "layoutHints": ["S-title-anchor", "S-title-content-action"],
    }
    task = {
        "size": "2x2",
        "dataModelSchema": {
            "data": {
                "calendar": {
                    "reminder": {
                        "type": "string",
                        "description": "会议提醒摘要",
                        "sampleValue": "会议提醒",
                    }
                },
                "meta": {
                    "updatedAt": {
                        "type": "string",
                        "description": "更新时间",
                        "sampleValue": "09:00",
                    }
                },
            }
        },
        "eventCandidates": [
            {
                "id": "event.open.settings.dnd",
                "description": "打开免打扰设置",
                "call": "clickToDeeplink",
                "args": {"uri": "intelligent_scene_entry"},
            }
        ],
    }

    result = feasible_composition_candidates("2x2", plan, task)

    assert result.get("status") == "reference_candidates"
    candidates = result.get("candidates")
    assert isinstance(candidates, list) and candidates
    candidate = candidates[0]
    assert candidate.get("layout") == "S-title-anchor"
    regions = candidate.get("regions")
    assert isinstance(regions, list)
    groups = []
    for region in regions:
        region_groups = region.get("groups")
        assert isinstance(region_groups, list)
        groups.extend(region_groups)
    action = next(group for group in groups if group.get("actionId"))
    assert action.get("component") == "CircleButton"
    assert action.get("accessibilityLabel") == "打开免打扰设置"
    assert action.get("requiresAccurateIcon") is True
    blueprint = composition_structure_blueprint("2x2", candidate)
    blueprint_action = next(
        item for item in blueprint if item.get("component") == "CircleButton"
    )
    assert blueprint_action.get("groupParameters") == {
        "accessibilityLabel": "打开免打扰设置",
        "requiresAccurateIcon": True,
    }
