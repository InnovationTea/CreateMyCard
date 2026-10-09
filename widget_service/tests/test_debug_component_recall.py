from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest
from debug_tools.batch_testing.runner import BatchRunManager


def _load_plugin() -> ModuleType:
    path = (
        Path(__file__).parents[2]
        / "debug_tools"
        / "postprocess_plugins"
        / "component-recall"
        / "plugin.py"
    )
    spec = importlib.util.spec_from_file_location("component_recall_plugin", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _context(tmp_path: Path, final_attempt: Path | None) -> dict[str, object]:
    run_dir = tmp_path / "run"
    _write_json(
        run_dir / "dataset_evaluation" / "component-recall.json",
        {
            "schemaVersion": "component-recall-ground-truth-v1",
            "samples": {
                "Q001": {
                    "required": ["SingleLineTitle"],
                    "anyOf": [["InfoBlock", "TextBlock"]],
                }
            },
        },
    )
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return {
        "runDir": str(run_dir),
        "sample": {"id": "Q001"},
        "finalAttemptDir": str(final_attempt) if final_attempt else None,
        "outputDir": str(output_dir),
    }


def test_required_any_of_deduplication_and_extra_components(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plugin = _load_plugin()
    monkeypatch.setattr(
        plugin,
        "_registered_components",
        lambda: {"SingleLineTitle", "InfoBlock", "TextBlock", "EventCard"},
    )
    attempt = tmp_path / "attempt"
    dsl_path = attempt / "blocks" / "designcompactdsl.txt"
    dsl_path.parent.mkdir(parents=True)
    dsl_path.write_text(
        "\n".join(
            [
                '["a", "SingleLineTitle", {}]',
                '["b", "SingleLineTitle", {}]',
                '["c", "InfoBlock", {}]',
                '["d", "EventCard", {}]',
                '["row", {"title": "数据行"}]',
            ]
        ),
        encoding="utf-8",
    )

    result = plugin.process_sample(_context(tmp_path, attempt))

    assert result.get("status") == "success"
    facts = result.get("facts")
    assert facts.get("recallRate") == 100.0
    assert facts.get("actualCount") == 3
    assert facts.get("extraComponents") == ["EventCard"]
    assert facts.get("missingComponents") == []


def test_annotated_sample_without_final_dsl_scores_zero(tmp_path: Path) -> None:
    plugin = _load_plugin()

    result = plugin.process_sample(_context(tmp_path, None))

    assert result.get("status") == "failed"
    assert result.get("facts", {}).get("recallRate") == 0.0
    assert result.get("facts", {}).get("verdict") == "no-output"


def test_malformed_dsl_is_failed_and_scores_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plugin = _load_plugin()
    monkeypatch.setattr(plugin, "_registered_components", lambda: {"SingleLineTitle"})
    attempt = tmp_path / "attempt"
    dsl_path = attempt / "blocks" / "designcompactdsl.txt"
    dsl_path.parent.mkdir(parents=True)
    dsl_path.write_text("not-json\n", encoding="utf-8")

    result = plugin.process_sample(_context(tmp_path, attempt))

    assert result.get("status") == "failed"
    assert result.get("facts", {}).get("recallRate") == 0.0
    assert result.get("facts", {}).get("verdict") == "invalid-output"
    assert "不是合法 JSON" in result.get("facts", {}).get("parseError")


def test_dataset_uses_only_annotated_sample_macro_average() -> None:
    plugin = _load_plugin()
    comparison = {
        "key": "component-comparison",
        "data": [{"requirement": "SingleLineTitle", "status": "matched"}],
    }
    result = plugin.process_dataset(
        {
            "sampleResults": [
                {
                    "status": "success",
                    "facts": {"annotated": True, "recallRate": 100.0},
                    "artifacts": [comparison],
                },
                {
                    "status": "failed",
                    "facts": {"annotated": True, "recallRate": 0.0},
                    "artifacts": [
                        {
                            "key": "component-comparison",
                            "data": [{"requirement": "InfoBlock", "status": "missing"}],
                        }
                    ],
                },
                {
                    "status": "skipped",
                    "facts": {"annotated": False},
                    "artifacts": [],
                },
            ]
        }
    )

    facts = result.get("facts")
    assert facts.get("macroRecallRate") == 50.0
    assert facts.get("evaluatedSamples") == 2
    assert facts.get("totalSamples") == 3
    assert facts.get("fullRecall") == 1
    assert facts.get("missingSamples") == 1


def test_representative_annotation_snapshot_contains_expected_16_samples() -> None:
    path = (
        Path(__file__).parents[2]
        / "debug_tools"
        / "Datasets"
        / "request_dataset"
        / "evaluation"
        / "component-recall.json"
    )
    value = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "Q001",
        "Q003",
        "Q009",
        "Q011",
        "Q012",
        "Q015",
        "Q022",
        "Q034",
        "Q053",
        "Q054",
        "Q055",
        "Q061",
        "Q063",
        "Q064",
        "Q065",
        "Q081",
    }

    assert set(value.get("samples", {})) == expected


def test_evaluation_snapshot_writes_file_summary(tmp_path: Path) -> None:
    dataset_root = tmp_path / "dataset"
    output_dir = tmp_path / "run"
    _write_json(
        dataset_root / "evaluation" / "component-recall.json",
        {
            "schemaVersion": "component-recall-ground-truth-v1",
            "samples": {"Q001": {"required": ["SingleLineTitle"]}},
        },
    )

    BatchRunManager._snapshot_evaluation(dataset_root, output_dir)

    snapshot = json.loads(
        (output_dir / "dataset_evaluation" / "summary.json").read_text(encoding="utf-8")
    )
    assert snapshot.get("schemaVersion") == "batch-dataset-evaluation-snapshot-v1"
    files = snapshot.get("files")
    assert files[0].get("name") == "component-recall.json"
    assert files[0].get("annotatedSamples") == 1
    assert len(files[0].get("sha256")) == 64
