"""宽卡辅助文本按完整标签和值自适应排版；不删除标签或改写数据。"""

import json

import pytest

from services.card_validation import validate_compact_dsl


@pytest.mark.parametrize("label", [None, "记录时间"])
@pytest.mark.parametrize("max_lines", [1, 2])
def test_wide_supporting_text_adapts_complete_label_and_value_before_budget(
    label: str | None, max_lines: int,
) -> None:
    item = {"value": {"path": "/data/recordedAt"}, "maxLines": max_lines}
    if label:
        item["label"] = label
    rows = [
        ["root", "Layout", {"layout": "W-content-side-slots"}, ["body", "a", "b"]],
        ["body", "Region", {"variant": "title-hero-support"}, ["title", "main", "detail"]],
        ["title", "SingleLineTitle", {"title": "设备状态", "fontSize": 12}],
        ["main", "EmphasisText", {"mainText": "在线", "fontSize": 18}],
        ["detail", "SecondaryBody", {"items": [item], "fontSize": 12 if max_lines == 2 else 14}],
        ["a", "InfoBlock", {"variant": "slot", "primaryText": "就绪", "secondaryText": "设备状态",
                            "backgroundColor": "#99FFFFFF"}],
        ["b", "InfoBlock", {"variant": "slot", "primaryText": "关闭", "secondaryText": "免打扰",
                            "backgroundColor": "#99FFFFFF"}],
        ["/data/recordedAt", "2027-04-12 18:30"],
    ]
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    task = {"size": "2x4", "dataModelSchema": {"data": {"recordedAt": {
        "type": "string", "description": "记录时间", "sampleValue": "2027-04-12 18:30",
    }}}}
    validate_compact_dsl(source, task_spec=task, card_spec={})


def test_small_card_publishing_does_not_enable_extra_regular_label_pressure() -> None:
    rows = [
        ["root", "Column", {"width": 132, "height": 126}, ["detail"]],
        ["detail", "SecondaryBody", {"role": "supporting", "fontSize": 14, "items": [{
            "label": "记录时间", "value": {"path": "/data/recordedAt"},
        }]}],
        ["/data/recordedAt", "2027-04-12 18:30"],
    ]
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    task = {"size": "2x2", "dataModelSchema": {"data": {"recordedAt": {
        "type": "string", "description": "记录时间", "sampleValue": "2027-04-12 18:30",
    }}}}
    validate_compact_dsl(source, task_spec=task, card_spec={})
