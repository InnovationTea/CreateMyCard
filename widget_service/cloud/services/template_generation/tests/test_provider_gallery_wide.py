"""画廊尺寸、版本和端到端调用契约回归。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.template_generation.test_support.provider_gallery import (
    FUSION_PRD_VERSION,
    ProviderGalleryBatchRunner,
    write_gallery_input_dataset,
)
from services.template_generation.test_support.provider_gallery_wide import PLAIN_PRD_VERSION
from services.template_generation.tests.test_provider_gallery_batch import _GalleryService


def test_wide_inputs_cover_formal_templates_and_keep_square_ids(tmp_path: Path) -> None:
    square = write_gallery_input_dataset(tmp_path / "square")
    root = tmp_path / "mixed"
    mixed = write_gallery_input_dataset(
        root, card_sizes=("2x2", "2x4"), appearances=("fusion", "plain"),
    )
    square_ids: set[str] = set()
    for provider in square.providers:
        square_ids.update(case.caseId for case in provider.cases)
    mixed_square_ids: set[str] = set()
    wide_templates: set[str] = set()
    all_ids: list[str] = []
    paths: list[str] = []
    for provider in mixed.providers:
        for case in provider.cases:
            all_ids.append(case.caseId)
            paths.append(case.requestFile)
            if case.cardSize == "2x2" and case.appearanceId == "fusion":
                mixed_square_ids.add(case.caseId)
            if case.cardSize == "2x4":
                wide_templates.add(case.targetTemplateId)
            payload = json.loads((root / case.requestFile).read_text(encoding="utf-8"))
            content = payload.get("content")
            device = payload.get("deviceInfo")
            assert isinstance(content, dict)
            assert isinstance(device, dict)
            assert content.get("size") == case.cardSize
            assert device.get("prdVer") == case.prdVer
            assert case.providerId == provider.providerId
            if case.appearanceId == "plain":
                assert case.prdVer == PLAIN_PRD_VERSION
                assert not case.expectsFusionBall
    source = Path(__file__).parents[1] / "resources" / "source" / "providers"
    expected: set[str] = set()
    for path in source.glob("*/provider.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for template in payload.get("templates", []):
            template_id = template.get("templateId")
            assert isinstance(template_id, str)
            if template_id.endswith(("WideFull@1", "WideHero@1", "WideHalf@1")):
                expected.add(template_id)
    assert wide_templates == expected
    assert mixed_square_ids == square_ids
    assert len(all_ids) == len(set(all_ids)) == len(set(paths))
    assert mixed.cardSize == "mixed"


@pytest.mark.parametrize("appearance", ["fusion", "plain"])
@pytest.mark.asyncio
async def test_wide_runner_forwards_size_templates_and_version(
    tmp_path: Path, appearance: str,
) -> None:
    inputs = tmp_path / "inputs"
    manifest = write_gallery_input_dataset(
        inputs, card_sizes=("2x4",), appearances=(appearance,),
    )
    service = _GalleryService()
    summary = await ProviderGalleryBatchRunner(service).run(inputs, tmp_path / "output")
    expected_count = sum(len(provider.cases) for provider in manifest.providers)
    assert summary.total == summary.success == expected_count
    assert summary.failed == summary.missing == 0
    assert {request.size for request in service.requests} == {"2x4"}
    version = FUSION_PRD_VERSION if appearance == "fusion" else PLAIN_PRD_VERSION
    assert set(service.prd_versions) == {version}
    output = json.loads(summary.manifest_path.read_text(encoding="utf-8"))
    assert output.get("cardSize") == "2x4"
    for provider in output.get("providers", []):
        for case in provider.get("cases", []):
            assert case.get("cardSize") == "2x4"
            if case.get("expectedTemplateSuffix") == "WideHalf":
                assert case.get("partnerTemplateId")
                assert case.get("fusionBallRendered") is False


@pytest.mark.parametrize("sizes", [(), ("4x4",)])
def test_invalid_sizes_do_not_clear_previous_dataset(
    tmp_path: Path, sizes: tuple[str, ...],
) -> None:
    existing = tmp_path / "manifest.json"
    existing.write_text("previous", encoding="utf-8")
    with pytest.raises(ValueError, match="card_sizes"):
        write_gallery_input_dataset(tmp_path, card_sizes=sizes)
    assert existing.read_text(encoding="utf-8") == "previous"


@pytest.mark.parametrize("appearances", [(), ("unknown",)])
def test_invalid_appearances_rejected(tmp_path: Path, appearances: tuple[str, ...]) -> None:
    with pytest.raises(ValueError, match="appearances"):
        write_gallery_input_dataset(tmp_path, appearances=appearances)
