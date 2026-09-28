"""Q068/Q072/Q088：倒计时专用背板与通用 W9 规则不能互相否定。"""

import json

import pytest

from services.card_validation import CompactDslValidationError, validate_compact_dsl


def _fixture(*, action: bool = False) -> tuple[list, dict]:
    click = {"call": "openAlarm", "args": {}}
    task = {
        "size": "2x4",
        "userQuery": "显示出发倒计时和任务状态" + ("，点击打开闹钟" if action else ""),
        "dataModelSchema": {"data": {
            "countdown": {"countdownDays": {
                "type": "integer", "description": "倒计时天数，不含天", "sampleValue": 30,
            }},
            "other": {"status": {"type": "string", "sampleValue": "进行中"}},
        }},
        "eventCandidates": [click] if action else [],
        "assetCandidates": [],
    }
    rows = [
        ["root", "Row", {"width": "matchParent", "height": "matchParent",
                         "padding": 8, "itemMargin": 8}, ["countdown", "other"]],
        ["countdown", "Column", {"width": 138, "height": 134, "padding": 12,
                                 "justifyContent": "spaceBetween", "alignItems": "center"},
         ["title", "value", "unit"]],
        ["title", "Text", {"content": "出发", "width": 114, "fontSize": 12,
                           "fontWeight": 400, "textAlign": "center", "maxLines": 1}],
        ["value", "Text", {"content": {"path": "/data/countdown/countdownDays"},
                           "width": 114, "fontSize": 30, "fontWeight": 700,
                           "textAlign": "center", "maxLines": 1}],
        ["unit", "Text", {"content": "天", "width": 114, "fontSize": 12,
                          "textAlign": "center", "maxLines": 1}],
        ["other", "Column", {"width": 138, "height": 134, "padding": 12}, ["other_content"]],
        ["other_content", "Column", {"width": 114, "layoutWeight": 1,
                                     "justifyContent": "center"}, ["status"]],
        ["status", "Text", {"content": {"path": "/data/other/status"}, "fontSize": 18,
                            "width": 114, "maxLines": 1}],
        ["/data/countdown/countdownDays", 30],
        ["/data/other/status", "进行中"],
    ]
    if action:
        rows[1][3] = ["content", "action"]
        rows.extend([
            ["content", "Column", {"width": 114, "layoutWeight": 1,
                                   "justifyContent": "center"}, ["title", "value", "unit"]],
            ["action", "Button", {"label": "打开闹钟", "width": 114,
                                  "height": 36, "onClick": [click]}],
        ])
    return rows, task


def _validate(rows: list, task: dict) -> None:
    validate_compact_dsl(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows),
        task_spec=task,
        card_spec={"suggestSize": "2x4"},
    )


def test_accepts_actionless_countdown_direct_three_texts() -> None:
    _validate(*_fixture())


@pytest.mark.parametrize("mutation,message", [
    ("nested", "directly contain exactly three Text"),
    ("alignment", "balanced vertical spacing"),
    ("width", "width 114"),
    ("unit", "unit `天`"),
    ("extra", "directly contain exactly three Text"),
])
def test_actionless_countdown_keeps_specialized_guards(mutation: str, message: str) -> None:
    rows, task = _fixture()
    if mutation == "nested":
        rows[1][3] = ["content"]
        rows.append(["content", "Column", {"width": 114, "layoutWeight": 1,
                                           "justifyContent": "center"}, ["title", "value", "unit"]])
    elif mutation == "alignment":
        rows[1][2]["justifyContent"] = "start"
    elif mutation == "width":
        rows[3][2]["width"] = 90
    elif mutation == "unit":
        rows[4][2]["content"] = "小时"
    else:
        rows[1][3].append("extra")
        rows.append(["extra", "Text", {"content": "附加说明", "fontSize": 12}])
    with pytest.raises(CompactDslValidationError, match=message):
        _validate(rows, task)


def test_countdown_with_action_keeps_centered_content_contract() -> None:
    rows, task = _fixture(action=True)
    _validate(rows, task)
    content = next(row for row in rows if row[0] == "content")
    content[2]["justifyContent"] = "start"
    with pytest.raises(CompactDslValidationError, match="W9 sparse backboard"):
        _validate(rows, task)
