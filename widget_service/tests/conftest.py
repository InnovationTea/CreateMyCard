"""Focused test doubles for stages outside a test's scope."""

import pytest


@pytest.fixture
def isolated_theme_stage(monkeypatch):
    """Plan/repair tests use partial artifacts and finite layout-model responses."""
    async def theme(artifact, *_args, **_kwargs):
        return artifact

    monkeypatch.setattr("services.post_layout_theme.theme_artifact", theme)
