"""原色 SVG 在组件展开、标题转换和末尾主题中的染色回归。"""

import json
from pathlib import Path
from typing import Any

import pytest

from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.layout_theme_contract import layout_only_prompt, strip_source_colors
from services.post_layout_theme import apply_theme, foreground_signature, presets
from services.theme_style_roles import layout_phase, native_asset

REGISTRY = (
    Path(__file__).resolve().parents[1]
    / "cloud/data/capabilities/app-11.7.7.300_rom-7.0/asset_capabilities.json"
)
NATIVE_NAMES = (
    "icon_id", "ic_charge", "ic_weatherWarning", "ic_uv_color", "ic_warning_color",
    "ic_weather_color", "ic_hotspot", "ic_call_bule", "ic_call_yellow", "ic_ring_bule",
    "ic_ring_yellow", "ic_sportsHealth_bule", "ic_sportsHealth_yellow", "ic_sun",
    "ic_calender", "ic_sun_monochrome",
)


def _asset(name: str) -> dict[str, Any]:
    assets = json.loads(REGISTRY.read_text(encoding="utf-8"))
    for asset in assets:
        if asset.get("id") == f"asset.{name}":
            return asset
    raise AssertionError(f"正式素材不存在：{name}")


def _images(source: str) -> list[dict[str, Any]]:
    images: list[dict[str, Any]] = []
    for line in source.splitlines():
        message = json.loads(line)
        components = message.get("updateComponents", {}).get("components", [])
        for component in components:
            if component.get("component") == "Image":
                images.append(component)
    return images


def _source(kind: str, src: str) -> str:
    props: dict[str, Any] = {"icon": src, "fillColor": "#FFFF0000"}
    if kind == "SingleLineTitle":
        props["title"] = "测试标题"
    elif kind == "PillButton":
        props["label"] = "打开"
        props["onClick"] = [{"call": "clickToDeeplink", "args": {"uri": "test://open"}}]
    elif kind == "Image":
        props.pop("icon")
        props["src"] = src
        props["width"] = 20
        props["height"] = 20
    else:
        raise AssertionError(f"未登记测试组件：{kind}")
    rows = [["root", "Column", {}, ["visual"]], ["visual", kind, props]]
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def _card_button_source(src: str) -> str:
    rows = [
        ["root", "Column", {}, ["action"]],
        [
            "action",
            "CardButton",
            {
                "label": "打开",
                "icon": src,
                "onClick": [{"call": "clickToDeeplink", "args": {"uri": "test://open"}}],
            },
        ],
    ]
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


@pytest.mark.parametrize("name", NATIVE_NAMES)
def test_registered_native_description_matches_runtime(name: str) -> None:
    asset = _asset(name)
    description = asset.get("description")
    src = asset.get("src")
    assert isinstance(description, str)
    assert isinstance(src, str)
    assert "保留原色" in description
    with layout_phase(True, {"assetCandidates": [asset]}):
        assert native_asset(src)
    assert not native_asset(src)


@pytest.mark.parametrize("name", NATIVE_NAMES)
@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("kind", ["SingleLineTitle", "PillButton", "Image"])
def test_native_images_stay_unpainted_after_conversion_and_theme(
    name: str, size: str, kind: str,
) -> None:
    asset = _asset(name)
    src = asset.get("src")
    assert isinstance(src, str)
    task = {"size": size, "assetCandidates": [asset]}
    with layout_phase(True, task):
        converted = convert_compact_dsl_to_a2ui(
            _source(kind, src), size=size, skip_compact_dsl_validation=kind == "Image",
        )
    theme = next(item for item in presets(task) if item.get("id") == "gradient-blue")
    themed = apply_theme(converted, theme, task, {})
    for output in (converted, themed):
        images = _images(output)
        assert len(images) == 1
        image = images[0]
        assert image.get("src") == src
        assert "fillColor" not in image
        styles = image.get("styles")
        assert isinstance(styles, dict)
        assert "fillColor" not in styles


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("name", ["battery_leaf_fill", "ic_weather_monochrome"])
def test_tintable_title_retains_runtime_color(size: str, name: str) -> None:
    asset = _asset(name)
    src = asset.get("src")
    assert isinstance(src, str)
    task = {"size": size, "assetCandidates": [asset]}
    with layout_phase(True, task):
        assert not native_asset(src)
        converted = convert_compact_dsl_to_a2ui(_source("SingleLineTitle", src), size=size)
    images = _images(converted)
    assert len(images) == 1
    styles = images[0].get("styles")
    assert isinstance(styles, dict)
    assert styles.get("fillColor") == "@theme:graphicPrimary/1"


@pytest.mark.parametrize(
    "layout_enabled, expected",
    [(False, "#FF1F4799"), (True, "@theme:primary/1")],
)
def test_tintable_card_button_gets_default_icon_color(
    layout_enabled: bool, expected: str,
) -> None:
    asset = _asset("alarm_fill_1")
    src = asset.get("src")
    assert isinstance(src, str)
    task = {"size": "2x4", "assetCandidates": [asset]}
    with layout_phase(layout_enabled, task):
        converted = convert_compact_dsl_to_a2ui(_card_button_source(src), size="2x4")
    images = _images(converted)
    assert len(images) == 1
    styles = images[0].get("styles")
    assert isinstance(styles, dict)
    assert styles.get("fillColor") == expected


@pytest.mark.parametrize("layout_enabled", [False, True])
def test_card_button_png_keeps_original_color(layout_enabled: bool) -> None:
    asset = _asset("emoji_z")
    src = asset.get("src")
    assert isinstance(src, str)
    task = {"size": "2x4", "assetCandidates": [asset]}
    with layout_phase(layout_enabled, task):
        converted = convert_compact_dsl_to_a2ui(_card_button_source(src), size="2x4")
    images = _images(converted)
    assert len(images) == 1
    styles = images[0].get("styles")
    assert isinstance(styles, dict)
    assert "fillColor" not in styles


@pytest.mark.parametrize("name", ["ic_uv_color", "ic_warning_color"])
@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_nested_icons_keep_native_color_without_disabling_monochrome_tint(
    name: str, size: str,
) -> None:
    native = _asset(name)
    monochrome = _asset("battery_leaf_fill")
    native_src = native.get("src")
    monochrome_src = monochrome.get("src")
    assert isinstance(native_src, str)
    assert isinstance(monochrome_src, str)
    rows = [
        ["root", "Column", {}, ["ratios"]],
        ["ratios", "NumericRatioStack", {"items": [
            {"icon": native_src, "value": "20"},
            {"icon": monochrome_src, "value": "30"},
            {"icon": native_src, "value": "50"},
        ]}],
    ]
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    task = {"assetCandidates": [native, monochrome]}
    with layout_phase(True, task):
        converted = convert_compact_dsl_to_a2ui(source, size=size)
    images = _images(converted)
    assert len(images) == 3
    for image in images:
        styles = image.get("styles")
        assert isinstance(styles, dict)
        if image.get("src") == native_src:
            assert "fillColor" not in styles
        else:
            assert styles.get("fillColor") is not None


def _info_source(src: str, *, native: bool, size: str = "2x2") -> str:
    visual = {"type": "icon", "icon": src}
    if native:
        visual["color"] = "native"
    rows = [
        ["root", "Column", {"width": "matchParent", "height": "matchParent"}, ["info"]],
        ["info", "InfoBlock", {
            "primaryText": {"path": "/data/value"}, "secondaryText": "设备电量",
            "visual": visual, "variant": "slot" if size == "2x4" else "stacked",
            "fontColor": "#FF1F4799", "backgroundColor": "#CCFFFFFF",
        }],
        ["/data/value", "68%"],
    ]
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("normalize", [False, True])
@pytest.mark.parametrize("asset_kind", ["monochrome", "native", "bitmap"])
def test_info_icon_color_is_decided_by_asset_not_model(
    size: str, native: bool, normalize: bool, asset_kind: str,
) -> None:
    src = "resources/base/media/phone_fill.svg"
    description = "单色图标，可染色"
    if asset_kind == "native":
        description = "保留原色，禁止染色"
    elif asset_kind == "bitmap":
        src = "resources/base/media/photo.png"
        description = "设备图片"
    task = {
        "size": size, "appVersion": "11.9.9.342",
        "assetCandidates": [{"src": src, "description": description}],
    }
    source = _info_source(src, native=native, size=size)
    with layout_phase(True, task):
        prepared = strip_source_colors(source) if normalize else source
        converted = convert_compact_dsl_to_a2ui(prepared, size=size)
        reference = convert_compact_dsl_to_a2ui(
            _info_source(src, native=False, size=size), size=size,
        )
    assert foreground_signature(converted) == foreground_signature(reference)
    theme_cases = [("gradient-blue", "#FF1F4799")]
    if size == "2x2":
        theme_cases.append(("fusion-ball-schedule-blue", "#FFFFFFFF"))
    for theme_id, expected_color in theme_cases:
        theme = next(item for item in presets(task) if item.get("id") == theme_id)
        themed = apply_theme(converted, theme, task, {})
        images = _images(themed)
        assert len(images) == 1
        image = images[0]
        assert image.get("src") == src
        styles = image.get("styles")
        assert isinstance(styles, dict)
        if asset_kind == "monochrome":
            assert styles.get("fillColor") == expected_color
        else:
            assert "fillColor" not in styles


@pytest.mark.parametrize("native", [False, True])
def test_non_fusion_info_icon_keeps_explicit_native_contract(native: bool) -> None:
    source = _info_source("resources/base/media/phone_fill.svg", native=native)
    with layout_phase(False):
        converted = convert_compact_dsl_to_a2ui(source, size="2x2")
    images = _images(converted)
    assert len(images) == 1
    styles = images[0].get("styles")
    assert isinstance(styles, dict)
    assert ("fillColor" not in styles) is native


def test_native_color_cleanup_preserves_content_and_data() -> None:
    rows = [
        ["root", "Column", {}, ["info"]],
        ["info", "InfoBlock", {
            "primaryText": "native", "secondaryText": {"path": "/data/color"},
            "visual": {"type": "icon", "icon": "phone.svg", "color": "native"},
        }],
        ["/data/color", {"color": "native"}],
    ]
    source = "\n".join(json.dumps(row) for row in rows)
    normalized = [json.loads(line) for line in strip_source_colors(source).splitlines()]
    props = normalized[1][2]
    assert props.get("primaryText") == "native"
    assert props.get("secondaryText") == {"path": "/data/color"}
    assert props.get("visual") == {"type": "icon", "icon": "phone.svg"}
    assert normalized[2] == rows[2]
    prompt = layout_only_prompt([{"role": "system", "content": source}])
    content = prompt[0].get("content", "")
    example_props = json.loads(content.splitlines()[1])[2]
    assert example_props.get("visual") == {"type": "icon", "icon": "phone.svg"}
    assert "图标是否保留原色由素材声明决定" in content
