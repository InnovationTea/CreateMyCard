# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import importlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLOUD_ROOT = PROJECT_ROOT / "cloud"

if str(CLOUD_ROOT) not in sys.path:
    sys.path.insert(0, str(CLOUD_ROOT))

app = importlib.import_module("start_websocket_server").app
get_settings = importlib.import_module("config.config").get_settings


def test_download_artifact_returns_saved_markdown(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    artifact_dir = workspace / "mock_obs"
    artifact_dir.mkdir(parents=True)
    file_name = "artifact_12345678-1234-4abc-8def-1234567890ab.md"
    artifact_content = "```genui\n{}\n```\n"
    (artifact_dir / file_name).write_text(artifact_content, encoding="utf-8")
    monkeypatch.setattr(get_settings(), "WORKSPACE_ROOT", workspace)

    with TestClient(app) as client:
        response = client.get(f"/artifacts/{file_name}")
        head_response = client.head(f"/artifacts/{file_name}")

    assert response.status_code == 200
    assert response.text == artifact_content
    assert response.headers["content-type"].startswith("text/markdown")
    assert response.headers["content-disposition"] == (
        f'attachment; filename="{file_name}"'
    )
    assert response.headers["cache-control"] == "private, no-store"
    assert head_response.status_code == 200
    assert head_response.content == b""
    assert int(head_response.headers["content-length"]) == len(
        artifact_content.encode("utf-8")
    )


def test_download_artifact_rejects_unknown_or_invalid_names(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    artifact_dir = workspace / "mock_obs"
    artifact_dir.mkdir(parents=True)
    (workspace / "secret.md").write_text("secret", encoding="utf-8")
    monkeypatch.setattr(get_settings(), "WORKSPACE_ROOT", workspace)

    with TestClient(app) as client:
        missing = client.get(
            "/artifacts/artifact_12345678-1234-4abc-8def-1234567890ab.md"
        )
        invalid = client.get("/artifacts/secret.md")

    assert missing.status_code == 404
    assert invalid.status_code == 404
