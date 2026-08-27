"""Provider Template A2UI 画廊数据集测试。"""

from __future__ import annotations

import json
from collections import Counter

from services.template_generation.engine.cardplan.preview_dataset import (
    build_template_preview_cases,
    validate_preview_asset_paths,
    write_template_preview_dataset,
)


def test_template_preview_dataset_covers_all_business_templates(tmp_path):
    manifest = write_template_preview_dataset(tmp_path)
    cases = manifest["cases"]

    assert manifest["templateCount"] == 78
    assert manifest["countsByLayout"] == {
        "Compact": 32,
        "Hero": 7,
        "Full": 26,
        "WideHero": 2,
        "WideFull": 11,
    }
    assert manifest["countsBySize"] == {"2x2": 65, "2x4": 13}
    assert len(cases) == 78
    assert len({case["templateId"] for case in cases}) == 78
    assert all((tmp_path / case["file"]).is_file() for case in cases)


def test_template_preview_a2ui_has_surface_components_and_data():
    cases = build_template_preview_cases()

    for case in cases:
        assert len(case.messages) == 3
        assert "createSurface" in case.messages[0]
        assert "updateComponents" in case.messages[1]
        assert "updateDataModel" in case.messages[2]
        components = case.messages[1]["updateComponents"]["components"]
        root = next(component for component in components if component["id"] == "root")
        assert root["component"] == "Column"
        slot = next(component for component in components if component["id"] == "root_0")
        assert slot["styles"]["height"] == case.content_height_vp


def test_template_preview_assets_are_bundled_by_genui_evaluation():
    cases = build_template_preview_cases()
    paths = validate_preview_asset_paths(cases)
    names = {path.rsplit("/", 1)[-1] for path in paths}

    assert names == {
        "battery_leaf_fill.svg",
        "calendar_fill.svg",
        "clock_fill.svg",
        "externaldrive_fill.svg",
        "figure_run.svg",
        "flame_fill.svg",
        "heart_fill.svg",
        "icon_earphone.svg",
        "icon_tiktok.png",
        "icon_weather1.svg",
        "l_circle_fill.svg",
        "location_north_up_right_fill.svg",
        "moon_z_fill_1.svg",
        "r_circle_fill.svg",
    }


def test_template_preview_manifest_data_tiers_are_disjoint():
    cases = build_template_preview_cases()

    for case in cases:
        counts = Counter((*case.primary_data, *case.secondary_data, *case.optional_data))
        assert all(count == 1 for count in counts.values())
        assert case.primary_data
        assert json.dumps(case.messages, ensure_ascii=False)
