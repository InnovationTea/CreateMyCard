"""Q059 完整组合链路及旧 CompactAction 样式回归。"""

import json
from pathlib import Path

import pytest

from services.template_generation.engine.cardplan.compiler import _instantiate_blueprint
from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.tests.helpers.generate_q059_preview import generate


@pytest.mark.asyncio
async def test_q059_composes_full_with_two_actions(tmp_path):
    output = tmp_path / "q059.json"
    await generate(Path(__file__).parent / "fixtures/q059.json", output)
    text = output.read_text(encoding="utf-8")
    messages = json.loads(text)
    update = messages[1].get("updateComponents")
    assert update is not None
    nodes = update.get("components")
    assert nodes is not None
    actions = [node for node in nodes if node.get("onClick")]
    assert len(actions) == 2
    assert "bluetooth_entry" in text and "code=a001" in text
    assert "示例数据" not in text
    assert "14:00" in text
    rings = [node for node in nodes if node.get("component") == "Progress"]
    assert len(rings) == 1
    assert rings[0].get("styles", {}).get("strokeWidth") == 6
    slots = [node for node in nodes if node.get("styles", {}).get("height") == 57]
    assert len(slots) == 2
    right = next(node for node in nodes if node.get("styles", {}).get("height") == 126)
    assert right.get("itemMargin") == 12
    for label in ("蓝牙设置", "每日推荐"):
        node = next(item for item in nodes if item.get("content") == label)
        assert node.get("styles", {}).get("fontSize") == 16


def test_compact_action_default_keeps_original_type_size():
    registry = CardPlanRegistry()
    variant = registry.require_variant("CompactAction@1", "default")
    theme = registry.require_theme("family-weather-care-blue")
    root = _instantiate_blueprint(
        variant.root,
        {"actionId": "test", "label": "测试", "icon": "test.svg"},
        {},
        theme.reference_values,
    )
    row = root.children[0]
    label = row.children[0]
    styles = next(value for value in label.values if isinstance(value, dict))
    assert styles.get("fontSize") == 14
    assert styles.get("height") == 19
