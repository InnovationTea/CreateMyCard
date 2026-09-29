"""Q073 完整模板通过既有检索与编译链路覆盖全部输入字段。"""

import json
from pathlib import Path

from services.template_generation.tests.helpers.generate_q073_preview import generate


def test_q073_full_fields_and_embedded_daily_action(tmp_path):
    output = tmp_path / "preview.json"
    generate(Path(__file__).parent / "fixtures/q073.json", output)
    text = output.read_text(encoding="utf-8")
    messages = json.loads(text)
    update = messages[1].get("updateComponents")
    assert update is not None
    nodes = update.get("components")
    assert nodes is not None
    rings = [node for node in nodes if node.get("component") == "Progress"]
    assert len(rings) == 2
    assert "打开歌单" in text
    assert "播放每日30首" in text
    assert len([node for node in nodes if node.get("onClick")]) == 1
    assert "code=a001" in text
    for field in ("chargingStatusDesc", "leftChargingStatusDesc", "rightChargingStatusDesc"):
        assert field in text
    assert "示例数据" not in text
    images = [node for node in nodes if node.get("component") == "Image"]
    assert len(images) == 3
