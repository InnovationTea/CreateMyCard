"""原卡主题冗余重传的边界与真实编辑入口回归。"""

import pytest

from core.errors import GenerationStatus
from services.edit_request_normalizer import normalize_source_theme_echo
from services.widget_generation_service import WidgetGenerationService
from test_semantic_widget_edit import _request
from test_semantic_widget_edit import edit_run as _edit_run
from test_semantic_widget_edit import source as _source

source = _source
theme_edit_run = _edit_run

THEME = "photo-ux-texture-purple-diagonal-square"


def _declare_theme(artifact):
    artifact.taskSpec["assetCandidates"] = [
        {"id": THEME, "src": "resources/existing.jpg"},
    ]
    artifact.effectiveCapabilities["asset"] = [THEME]


@pytest.mark.parametrize("supplied", [
    ["first", "second", THEME],
    [THEME, "first", "second"],
])
def test_known_theme_echo_preserves_original_candidates(theme_edit_run, supplied):
    artifact = theme_edit_run.source
    artifact.generationPlan.candidateAssetIds = ["first", "second"]
    _declare_theme(artifact)
    request = _request(candidateAssetIds=supplied)
    result = normalize_source_theme_echo(request, artifact)
    assert result.candidateAssetIds == ["first", "second"]
    assert request.candidateAssetIds == supplied
    assert artifact.effectiveCapabilities.get("asset") == [THEME]


@pytest.mark.parametrize("supplied", [
    [], [THEME], ["second", "first", THEME],
    ["first", "second", "unknown"], ["first", "second", THEME, THEME],
])
def test_real_candidate_changes_are_not_normalized(theme_edit_run, supplied):
    artifact = theme_edit_run.source
    artifact.generationPlan.candidateAssetIds = ["first", "second"]
    _declare_theme(artifact)
    request = _request(candidateAssetIds=supplied)
    assert normalize_source_theme_echo(request, artifact) is request


@pytest.mark.parametrize("missing", ["effective", "declaration", "address"])
def test_theme_requires_source_evidence(theme_edit_run, missing):
    artifact = theme_edit_run.source
    _declare_theme(artifact)
    if missing == "effective":
        artifact.effectiveCapabilities["asset"] = []
    elif missing == "declaration":
        artifact.taskSpec["assetCandidates"] = []
    else:
        artifact.taskSpec["assetCandidates"] = [{"id": THEME, "src": ""}]
    request = _request(candidateAssetIds=[THEME])
    assert normalize_source_theme_echo(request, artifact) is request


@pytest.mark.asyncio
async def test_echo_reaches_edit_and_retains_source_theme(theme_edit_run):
    _declare_theme(theme_edit_run.source)
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(
        _request(candidateAssetIds=[THEME]),
    )
    assert response.status == GenerationStatus.SUCCESS
    assert len(theme_edit_run.saved) == 1
    saved = theme_edit_run.saved[0]
    assert saved.generationPlan.candidateAssetIds == []
    assert THEME in saved.effectiveCapabilities.get("asset", [])


@pytest.mark.asyncio
async def test_new_theme_without_source_evidence_is_rejected(theme_edit_run):
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(
        _request(candidateAssetIds=[THEME]),
    )
    assert response.status == GenerationStatus.UNSUPPORTED
    assert not theme_edit_run.calls
    assert not theme_edit_run.saved
