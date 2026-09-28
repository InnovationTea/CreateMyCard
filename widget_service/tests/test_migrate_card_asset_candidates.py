"""素材迁移只接受显式且已注册的替换，不删除未知候选或覆盖原输入。"""

import json

import pytest
from scripts.migrate_card_asset_candidates import migrate


def _fixture(tmp_path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    candidates = {"candidateAssetIds": ["asset.old", "asset.other"],
                  "userQuery": "保留原需求", "size": "2x4", "candidateDataBindings": []}
    payload = {**candidates, "content": candidates}
    source = inputs / "Q008.json"
    source.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    registry = tmp_path / "asset_capabilities.json"
    registry.write_text('[{"id":"asset.new"},{"id":"asset.other"}]', encoding="utf-8")
    return inputs, source, registry, payload


def test_migrate_both_envelopes_without_modifying_source(tmp_path) -> None:
    inputs, source, registry, payload = _fixture(tmp_path)
    original = source.read_bytes()
    output = tmp_path / "migrated"
    changes = migrate(inputs, output, registry, {"asset.old": "asset.new"})
    assert source.read_bytes() == original
    actual = json.loads((output / source.name).read_text(encoding="utf-8"))
    for container in (actual, actual.get("content")):
        assert container.get("candidateAssetIds") == ["asset.new", "asset.other"]
        container["candidateAssetIds"] = ["asset.old", "asset.other"]
    assert actual == payload
    assert len(changes) == 2
    report = json.loads((output / "asset_migration_report.json").read_text(encoding="utf-8"))
    assert report.get("changes") == changes


@pytest.mark.parametrize("mapping", [
    {}, {"asset.old": "asset.missing"}, {"asset.unrelated": "asset.new"},
])
def test_invalid_migration_writes_nothing(tmp_path, mapping) -> None:
    inputs, _, registry, _ = _fixture(tmp_path)
    output = tmp_path / "migrated"
    with pytest.raises(ValueError):
        migrate(inputs, output, registry, mapping)
    assert not output.exists()


@pytest.mark.parametrize("target", ["same", "nested", "existing"])
def test_output_cannot_overwrite_or_nest_input(tmp_path, target: str) -> None:
    inputs, source, registry, _ = _fixture(tmp_path)
    original = source.read_bytes()
    output = inputs
    if target == "nested":
        output = inputs / "child"
    elif target == "existing":
        output = tmp_path / "existing"
        output.mkdir()
    with pytest.raises(ValueError, match="输出目录"):
        migrate(inputs, output, registry, {"asset.old": "asset.new"})
    assert source.read_bytes() == original
