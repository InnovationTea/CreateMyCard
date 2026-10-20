import json

from tools.convert_compact_gallery import convert_requests


def _source(rows: list[list]) -> str:
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def _semantic_card() -> str:
    return _source([
        ["root", "Layout", {"layout": "W-split-panels"}, ["left", "right"]],
        ["left", "Region", {"variant": "center"}, ["left_content"]],
        ["left_content", "EmphasisText", {"mainText": "左侧", "fontSize": 18}],
        ["right", "Region", {"variant": "center"}, ["right_content"]],
        ["right_content", "EmphasisText", {"mainText": "右侧", "fontSize": 18}],
    ])


def test_gallery_converter_expands_semantic_layout_and_isolates_bad_variants() -> None:
    invalid = _source([
        ["root", "Layout", {"layout": "W-split-panels"}, ["left"]],
        ["left", "Region", {"variant": "center"}, ["left_content"]],
        ["left_content", "EmphasisText", {"mainText": "左侧", "fontSize": 18}],
    ])
    payload = {
        "requests": [
            {"key": "valid", "source": _semantic_card(), "size": "2x4", "preview": True},
            {"key": "invalid", "source": invalid, "size": "2x4", "preview": True},
        ],
    }

    converted = convert_requests(payload)
    results = converted.get("results")
    assert results is not None
    by_key = {item.get("key"): item for item in results}
    valid = by_key.get("valid")
    invalid_result = by_key.get("invalid")
    assert valid is not None
    assert invalid_result is not None
    assert "updateComponents" in valid.get("genui", "")
    assert "子组件数量应为" in invalid_result.get("error", "")
