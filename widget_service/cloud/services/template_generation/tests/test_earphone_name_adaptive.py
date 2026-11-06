"""耳机名称在各角色、可选数据和标题分支中保留单行自适应契约。"""

from __future__ import annotations

import pytest

from services.template_generation.engine.cardplan.compiler import _instantiate_blueprint
from services.template_generation.engine.cardplan.preview_dataset import _template_parameters
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.tersel_converter import Nested2Node

_NAME_UPPER_SIZES = {
    "EarbudPairHero": 18,
    "Hero": 12,
    "EarbudsPhoneWideFull": 11,
    "EarbudsDynamicWideFull": 12,
    "NameAndConnectionSupport": 14,
    "NameAndChargeSupport": 14,
    "EarbudPairFull": 12,
    "CompleteWideFull": 12,
    "EarbudPairCompact": 12,
    "CompletePhoneWideFull": 11,
    "EarphoneHero": 14,
    "EarphoneCompact": 10,
    "MusicFull": 12,
    "ConnectionTextFull": 16,
    "EarbudPairRingFull": 16,
    "EarbudTripleHero": 18,
    "EarbudsChargingWideFull": 12,
    "EarphoneCasePercentTextFull": 16,
    "EarphonePercentTextFull": 16,
}


def _nodes(root: Nested2Node, kind: str) -> list[Nested2Node]:
    result = [root] if root.component_type == kind else []
    for child in root.children:
        result.extend(_nodes(child, kind))
    return result


def _expand(suffix: str, with_optional: bool, with_title: bool) -> Nested2Node:
    registry = get_cardplan_registry()
    definition = registry.require_template("BluetoothDeviceOverview" + suffix + "@1")
    variant = definition.variants[0]
    bindings = {}
    for name, binding in definition.bindings.items():
        if not with_optional and name in variant.optional_bindings and name != "name":
            continue
        bindings[name] = "${data.earphone." + binding.path.removeprefix("/") + "}"
    parameters = _template_parameters(definition)
    if with_title:
        parameters["title"] = "耳机状态"
    else:
        parameters.pop("title", None)
    if not with_optional:
        parameters.pop("earphoneIcon", None)
    return _instantiate_blueprint(
        variant.root, parameters, bindings,
        registry.theme_reference_values("2x2-two-support"),
    )


def test_all_registered_name_templates_are_covered() -> None:
    actual = set()
    for definition in get_cardplan_registry().templates.values():
        if definition.business_id != "BluetoothDeviceOverview":
            continue
        for binding in definition.bindings.values():
            if binding.path == "/earphoneName":
                actual.add(definition.wire_id)
    expected = {"BluetoothDeviceOverview" + suffix + "@1" for suffix in _NAME_UPPER_SIZES}
    assert actual == expected


@pytest.mark.parametrize("suffix", _NAME_UPPER_SIZES)
@pytest.mark.parametrize("with_optional", [False, True])
@pytest.mark.parametrize("with_title", [False, True])
def test_names_keep_original_upper_size_and_single_line(
    suffix: str, with_optional: bool, with_title: bool,
) -> None:
    root = _expand(suffix, with_optional, with_title)
    names = []
    for node in _nodes(root, "Text"):
        if "earphoneName}" in str(node.values[0]):
            names.append(node)
    assert len(names) == 1
    upper = _NAME_UPPER_SIZES.get(suffix)
    assert upper is not None
    if suffix == "EarbudPairFull" and not with_optional:
        upper = 18
    styles = names[0].values[-1]
    assert isinstance(styles, dict)
    assert styles.get("fontSize") == styles.get("maxFontSize") == upper
    assert styles.get("minFontSize") == 8
    assert styles.get("maxLines") == 1
    assert styles.get("textOverflow") == "ellipsis"
    assert styles.get("width") in ("matchParent", 112)


@pytest.mark.parametrize("with_title", [False, True])
def test_compact_name_and_connection_share_one_scaling_text(with_title: bool) -> None:
    root = _expand("EarbudPairCompact", True, with_title)
    header = root.children[0]
    assert header.component_type == "Text"
    expression = str(header.values[0])
    assert "/earphoneName}" in expression
    assert "/isConnected}" in expression
    assert "| 已连接" in expression
    assert "| 未连接" in expression
    assert ("耳机状态" if with_title else "蓝牙耳机") in expression
    styles = header.values[-1]
    assert isinstance(styles, dict)
    constraints = styles.get("constraintSize")
    assert isinstance(constraints, dict)
    assert "maxWidth" not in constraints


def test_compact_iconless_label_scales_with_name() -> None:
    root = _expand("EarphoneCompact", False, False)
    row = root.children[-1]
    assert row.component_type == "Row"
    assert len(row.children) == 1
    text = row.children[0]
    assert text.component_type == "Text"
    assert "耳机 " in str(text.values[0])
    assert "/earphoneName}" in str(text.values[0])


def test_pair_hero_preserves_height_shrink_from_main() -> None:
    root = _expand("EarbudPairHero", True, True)
    name = root.children[1]
    assert name.component_type == "Text"
    assert "earphoneName}" in str(name.values[0])
    styles = name.values[-1]
    assert isinstance(styles, dict)
    assert styles.get("height") == 30
    assert styles.get("flexShrink") == 1


@pytest.mark.parametrize("with_optional", [False, True])
def test_name_charge_support_keeps_only_outer_horizontal_inset(with_optional: bool) -> None:
    root = _expand("NameAndChargeSupport", with_optional, False)
    styles = root.values[0]
    assert isinstance(styles, dict)
    assert "padding" not in styles
    assert styles.get("justifyContent") == "start"
    assert styles.get("alignItems") == "center"
    for node in _nodes(root, "Row") + _nodes(root, "Column"):
        container_styles = node.values[0]
        assert isinstance(container_styles, dict)
        assert "padding" not in container_styles
