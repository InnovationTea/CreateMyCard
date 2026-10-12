"""PNG 后处理仅移除位图染色，不改变 SVG、绑定、数据和异常语义。"""

import json

import pytest

from services.template_generation.postprocessing import remove_png_fill_colors


@pytest.mark.parametrize("source", ["icons/a.png", "icons/A.PNG?version=2#icon"])
def test_png_colors_removed_from_flat_and_nested_nodes(source: str) -> None:
    bitmap = {
        "component": "Image", "src": source, "fillColor": "#123456",
        "styles": {"fillColor": "#123456", "width": 20},
    }
    messages = [
        {"updateComponents": {"components": [
            bitmap, {"component": "Column", "children": [bitmap]},
        ]}},
        {"updateDataModel": {"value": bitmap}},
    ]
    raw = "\n".join(json.dumps(message) for message in messages)
    output = remove_png_fill_colors(raw)
    actual = [json.loads(line) for line in output.splitlines()]
    expected_bitmap = {"component": "Image", "src": source, "styles": {"width": 20}}
    assert actual == [
        {"updateComponents": {"components": [
            expected_bitmap, {"component": "Column", "children": [expected_bitmap]},
        ]}},
        {"updateDataModel": {"value": bitmap}},
    ]
    assert remove_png_fill_colors(output) == output


@pytest.mark.parametrize("source", ["icons/a.svg", "{{ /data/icon }}", {"path": "/data/icon"}])
def test_non_png_output_is_unchanged(source: object) -> None:
    raw = json.dumps({"updateComponents": {"components": [{
        "component": "Image", "src": source, "styles": {"fillColor": "#123456"},
    }]}})
    assert remove_png_fill_colors(raw) == raw


def test_invalid_json_still_raises() -> None:
    with pytest.raises(json.JSONDecodeError):
        remove_png_fill_colors("{")
