"""动态列表 Plan 的触发边界、完整成员保护和单次复核回退。"""
import json

import pytest

from services.compact_list_review import review_list_plan, second_member_targets
from services.compact_plan import CompactPlanValidationResult


def field(index, name):
    return f"/data/records/{index}/{name}"


def fact(path, priority="must"):
    return {"dataId": path, "requirement": "展示对应字段", "priority": priority}


def sample(query):
    member = {name: {"type": "string"} for name in ("name", "state", "note")}
    task = {
        "userQuery": query, "size": "2x4",
        "dataModelSchema": {"data": {"records": [member, member], "date": {"type": "string"}}},
    }
    plan = {"info_required": [
        fact(field(0, "name")), fact(field(0, "state")),
        fact(field(0, "note"), "should"), fact("/data/date"),
    ]}
    return task, plan


@pytest.mark.parametrize("query", [
    "只看最新一条通话记录", "仅显示最近一次运动", "记录列表只取前1条", "显示第一通电话",
    "显示当前状态",
])
def test_single_and_non_list_queries_keep_the_original_plan(query):
    task, plan = sample(query)
    assert second_member_targets(plan, task) == ()


def test_use_only_second_members_available_core_fields():
    task, plan = sample("展示最近通话的号码、状态")
    assert second_member_targets(plan, task) == (field(1, "name"), field(1, "state"))
    records = task.get("dataModelSchema", {}).get("data", {}).get("records")
    assert records is not None
    records[1].pop("state")
    assert second_member_targets(plan, task) == (field(1, "name"),)
    records.pop()
    assert second_member_targets(plan, task) == ()


def test_already_selected_multiple_members_need_no_review():
    task, plan = sample("查看近期记录")
    facts = plan.get("info_required")
    assert facts is not None
    facts.append(fact(field(1, "name")))
    assert second_member_targets(plan, task) == ()


@pytest.mark.asyncio
@pytest.mark.parametrize("response", ["valid", "missing_member", "lost_date", "malformed"])
async def test_spare_plan_attempt_preserves_core_and_conversation(response):
    task, plan = sample("显示近期记录")
    original = CompactPlanValidationResult(plan)
    conversation = [{"role": "assistant", "content": "original submission"}]
    targets = second_member_targets(plan, task)
    calls = []

    async def generate(messages):
        calls.append(messages)
        if response == "malformed":
            return "invalid"
        facts = list(plan.get("info_required", []))
        if response == "lost_date":
            facts = [item for item in facts if item.get("dataId") != "/data/date"]
        if response != "missing_member":
            facts.extend(fact(path) for path in targets)
        return json.dumps({"name": "submit_card_plan", "arguments": {"info_required": facts}})

    result = await review_list_plan(
        original, conversation, task, targets, require_composition=False, generate=generate,
    )
    assert len(calls) == 1
    assert all(path in calls[0][-1].get("content", "") for path in targets)
    if response == "valid":
        assert result is not original
        assert "submit_card_plan" in conversation[-1].get("content", "")
    else:
        assert result is original
        assert conversation == [{"role": "assistant", "content": "original submission"}]
