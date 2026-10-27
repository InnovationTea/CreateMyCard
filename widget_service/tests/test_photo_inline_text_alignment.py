"""Q16/Q1紧邻辅助文本不应被误认为左右分栏，准入与前景保持不变。"""

import asyncio
import copy
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from photo_samples.common import expanded
from services import post_layout_theme as themes
from services.capability_registry import CapabilityRegistry
from services.protocol_registry import A2UIProtocolRegistry
from services.validator import ArtifactValidator
from test_photo_asset_delivery import artifact
from test_uniform_photo_eligibility import PATHS, choose, evidence, photo, rejection, sample

CASES = json.loads((Path(__file__).parent / "fixtures/photo_weather_q16_q1.json").read_text(
    encoding="utf-8",
))
WEATHER = {
    "photo-ux-mountain-sunset-lake-square",
    "photo-ux-pink-sunset-lake-square", "photo-ux-cumulus-blue-square",
}


def weather_case(case):
    fixture = CASES.get(case)
    assert fixture is not None
    rows = themes.decode(fixture.get("compact"))
    return expanded(rows, copy.deepcopy(fixture.get("task")))


@pytest.mark.parametrize("case", ["Q16", "Q1"])
def test_weather_inline_support_is_two_lines_and_globally_left(case):
    saved = weather_case(case)
    before = copy.deepcopy(saved)
    measured = evidence(saved)
    flow = measured.get("photoBodyTextFlow", {})
    assert flow.get("support", {}).get("leftAligned") is True
    assert flow.get("root", {}).get("leftAligned") is True
    assert flow.get("root", {}).get("lineCount") == 2
    for identity in WEATHER:
        assert rejection(saved, identity) is None
    assert "下方留空" in rejection(saved, "photo-ux-clouds-weather-square")
    assert saved == before


@pytest.mark.parametrize("case", ["Q16", "Q1"])
@pytest.mark.parametrize("selected", sorted(WEATHER))
def test_weather_subject_selection_and_final_obs_delivery_preserve_foreground(
    monkeypatch, case, selected,
):
    saved = weather_case(case)
    monkeypatch.setattr(themes.secrets, "choice", lambda items: selected)
    result, audit = choose(saved, monkeypatch)
    assert set(audit.get("candidates", [])) == WEATHER
    assert audit.get("themeId") == selected
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)
    original = artifact()
    original.genui = saved.source
    original.taskSpec = saved.task
    fixture = CASES.get(case)
    assert fixture is not None
    original.cardSpec = copy.deepcopy(fixture.get("cardSpec"))
    capabilities = CapabilityRegistry(version=original.meta.capabilityRegistryVersion)
    weather = capabilities.get_data_capability("ViewWeather")
    assert weather is not None
    original.effectiveCapabilities["data"] = [weather.model_dump()]
    original.effectiveCapabilities["event"] = saved.task.get("eventCandidates", [])
    monkeypatch.setattr(themes, "select_theme", AsyncMock(return_value=(result, audit)))
    delivered = asyncio.run(themes.theme_artifact(
        original, saved.task, None, ArtifactValidator({}),
        A2UIProtocolRegistry(original.meta.protocolProfileId).get_profile(),
        final_layout=saved.compact,
    ))
    assert not audit.get("finalValidationErrors"), audit.get("finalValidationErrors")
    assert themes.foreground_signature(delivered.genui) == themes.foreground_signature(saved.source)
    backgrounds = []
    for node in themes.components(themes.decode(delivered.genui)):
        if node.get("component") == "Image" and node.get("id", "").startswith(themes.PREFIX):
            backgrounds.append(node.get("src"))
    selected_photo = photo(selected)
    expected_source = selected_photo.get("remoteUrl") or selected_photo.get("src")
    assert backgrounds == [expected_source]


@pytest.mark.parametrize("change", [
    "width", "weight", "children", "center", "spaceBetween", "missing-source", "invalid-source",
])
def test_untrusted_or_distributed_items_do_not_receive_content_width_exemption(change):
    saved = weather_case("Q16")
    item = next(node for node in saved.nodes if node.get("id") == "support_item0")
    row = next(node for node in saved.nodes if node.get("id") == "support_row0")
    if change == "width":
        item.get("styles", {})["width"] += 1
    elif change == "weight":
        item.get("styles", {})["layoutWeight"] = 1
    elif change == "children":
        item.get("children", []).reverse()
    elif change in {"center", "spaceBetween"}:
        row.get("styles", {})["justifyContent"] = change
    elif change == "missing-source":
        saved.compact = None
    else:
        saved.compact = "not compact"
    assert rejection(saved, "photo-ux-wave-square")


@pytest.mark.parametrize("business,identity", [
    ("sleep", "photo-ux-sleep-square"), ("calendar", "photo-ux-meeting-room-square"),
    ("countdown", "photo-ux-hourglass-square"),
])
@pytest.mark.parametrize("lines", [2, 3])
def test_inline_provenance_works_across_businesses_but_keeps_three_line_limit(
    business, identity, lines,
):
    saved = sample(PATHS.get(business), lines, button=False)
    rows = themes.decode(saved.compact)
    rows[0][3].append("details")
    rows.append(["details", "SecondaryBody", {"items": [
        {"label": "甲", "value": "一"}, {"label": "乙", "value": "二"},
    ]}])
    saved = expanded(rows, saved.task)
    flow = evidence(saved).get("photoBodyTextFlow", {}).get("root", {})
    assert flow.get("lineCount") == lines + 1
    assert (rejection(saved, identity) is None) is (lines == 2)


def test_base_components_with_fixed_width_still_count_as_distributed_columns():
    saved = sample(PATHS.get("weather"), 1, button=False)
    rows = themes.decode(saved.compact)
    rows[0][3].append("details")
    rows.extend([
        ["details", "Row", {}, ["first", "second"]],
        ["first", "Text", {"width": 28, "content": "甲"}],
        ["second", "Text", {"content": "乙"}],
    ])
    assert rejection(expanded(rows, saved.task), "photo-ux-wave-square")
