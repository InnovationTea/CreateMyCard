"""双按钮结构回归：不依赖命名、候选数量或字体运行时测量。"""

import json

import pytest

from services.card_validation import CompactDslValidationError, validate_compact_dsl


def _rows() -> list:
    return [
        ["root", "Column", {"padding": 12, "itemMargin": 8}, ["summary", "controls"]],
        ["summary", "Column", {"width": 126, "height": 40, "itemMargin": 2}, ["a", "b"]],
        ["a", "Text", {"content": "电量 80%", "fontSize": 14, "height": 20, "maxLines": 1}],
        ["b", "Text", {"content": "未充电", "fontSize": 12, "height": 18, "maxLines": 1}],
        ["controls", "Column", {"width": 126, "height": 78, "itemMargin": 6}, ["one", "two"]],
        ["one", "ActionUnit", {"state": "capsule", "label": "动作一", "onClick": []}],
        ["two", "ActionUnit", {"state": "capsule", "label": "动作二", "onClick": []}],
        ["/state/ready", True],
    ]


def _validate(rows: list, size: str = "2x2") -> None:
    events = [{"call": "testAction", "args": {"target": "one"}}]
    for row in rows:
        if len(row) > 2 and row[1] == "ActionUnit":
            row[2]["onClick"] = events
    task = {"size": size, "eventCandidates": events, "dataModelSchema": {}, "assetCandidates": []}
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    validate_compact_dsl(source, task_spec=task, card_spec={"suggestSize": size})


def test_accepts_s3_with_arbitrary_ids_and_one_event_candidate() -> None:
    _validate(_rows())


@pytest.mark.parametrize("font,gap", [(38, 8), (30, 4)])
def test_rejects_badcase_header_large_value_and_two_actions(font: int, gap: int) -> None:
    rows = _rows()
    rows[0][2]["itemMargin"] = gap
    rows[0][3].insert(0, "heading")
    rows.append(["heading", "CardHeader", {"title": "电量", "fontColor": "#FF000000"}])
    rows[1][2].pop("height")
    rows[1][2]["layoutWeight"] = 1
    rows[2][2].update(content="80", fontSize=font)
    rows[2][2].pop("height")
    rows[3][2].pop("height")
    with pytest.raises(CompactDslValidationError, match="S3_DUAL_ACTION_LAYOUT"):
        _validate(rows)


@pytest.mark.parametrize("change", ["font", "height", "gap", "icon", "lines", "order"])
def test_rejects_invalid_s3_slots(change: str) -> None:
    rows = _rows()
    if change == "font":
        rows[2][2]["fontSize"] = 24
    elif change == "height":
        rows[1][2].pop("height")
    elif change == "gap":
        rows[4][2]["itemMargin"] = 4
    elif change == "icon":
        rows[1][3].append("extra")
        rows.append(["extra", "Text", {"content": "额外信息"}])
    elif change == "lines":
        rows[2][2]["maxLines"] = 2
    else:
        rows[0][3].reverse()
    with pytest.raises(CompactDslValidationError, match="S3_DUAL_ACTION_LAYOUT"):
        _validate(rows)


def test_does_not_apply_to_wide_cards() -> None:
    rows = _rows()
    rows[1][2].pop("height")
    _validate(rows, "2x4")


def test_does_not_apply_to_one_capsule() -> None:
    rows = _rows()
    rows[4][3].remove("two")
    rows.pop(6)
    rows[1][2].pop("height")
    _validate(rows)
