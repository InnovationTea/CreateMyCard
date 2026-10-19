"""原色 SVG 在组件展开、标题转换和末尾主题中的染色回归。"""

import json
from pathlib import Path
from typing import Any

import pytest

from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.post_layout_theme import apply_theme, presets
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
def test_tintable_title_retains_runtime_color(size: str) -> None:
    asset = _asset("battery_leaf_fill")
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
