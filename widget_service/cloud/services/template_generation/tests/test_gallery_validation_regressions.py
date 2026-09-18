"""画廊格式化读数与逐日天气输入回归。"""

import json
import re
from pathlib import Path

import pytest

from services.template_generation.engine.cardplan.preview_dataset import (
    build_template_preview_cases,
)
from services.template_generation.test_support.provider_gallery import (
    write_gallery_input_dataset,
)


@pytest.fixture(scope="module")
def preview_cases():
    return build_template_preview_cases()


@pytest.mark.parametrize("template_id", [
    "BluetoothDeviceOverviewEarphoneCaseCompact@1",
    "BluetoothDeviceOverviewEarphoneCompact@1",
    "WorkoutOverviewFull@1",
    "WorkoutOverviewHero@1",
    "WorkoutOverviewCompact@1",
])
def test_formatted_gallery_values_use_18fp(preview_cases, template_id: str) -> None:
    case = next(case for case in preview_cases if case.template_id == template_id)
    update = case.messages[1].get("updateComponents")
    assert isinstance(update, dict)
    components = update.get("components")
    assert isinstance(components, list)
    sizes = []
    for component in components:
        if component.get("component") != "Text":
            continue
        styles = component.get("styles")
        assert isinstance(styles, dict)
        font_size = styles.get("fontSize")
        assert isinstance(font_size, (int, float))
        sizes.append(font_size)
    assert max(sizes) == 18


def test_weather_gallery_overrides_only_declared_fields(tmp_path: Path) -> None:
    manifest = write_gallery_input_dataset(tmp_path)
    daily_two_checked = False
    for provider in manifest.providers:
        for case in provider.cases:
            if case.missingReason:
                continue
            payload = json.loads((tmp_path / case.requestFile).read_text(encoding="utf-8"))
            content = payload.get("content")
            assert isinstance(content, dict)
            bindings = content.get("candidateDataBindings")
            assert isinstance(bindings, list)
            gallery_test = payload.get("galleryTest")
            assert isinstance(gallery_test, dict)
            overrides = gallery_test.get("sampleOverrides")
            assert isinstance(overrides, dict)
            for binding in bindings:
                if binding.get("capabilityId") != "ViewWeather":
                    continue
                fields = binding.get("candidateOutputFields")
                domain = binding.get("writeResultTo")
                arguments = binding.get("arguments")
                assert isinstance(fields, list)
                assert isinstance(domain, str)
                assert isinstance(arguments, dict)
                required_days = 1
                for field in fields:
                    daily_field = re.fullmatch(r"/daily/(\d+)/.+", field)
                    if daily_field is not None:
                        required_days = max(required_days, int(daily_field.group(1)) + 1)
                assert arguments.get("forecastDays") == required_days
                for path in overrides:
                    if path.startswith(domain + "/"):
                        assert path.removeprefix(domain) in fields
                if case.targetTemplateId == "WeatherOverviewDaily2TravelSupport@1":
                    assert overrides.get("/data/weather/daily/2/condition") == "多云"
                    assert "/data/weather/current/condition" not in overrides
                    assert arguments.get("forecastDays") == 3
                    daily_two_checked = True
    assert daily_two_checked
