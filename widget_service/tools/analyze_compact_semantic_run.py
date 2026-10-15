"""按真实服务状态统计实验；预览规范化不覆盖原始产物或失败状态。"""

import argparse
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud"))

from services.compact_dsl_a2ui_converter import (  # noqa: E402
    CompactDslConversionError,
    ComponentRow,
    parse_compact_dsl_rows,
    serialize_compact_dsl_source,
)


def block(artifact: str, label: str) -> str | None:
    matched = re.search(r"^```" + label + r"\s*\n(.*?)\n```", artifact, re.M | re.S)
    return matched.group(1) if matched else None


def trace_artifacts(run: Path, meta: dict) -> dict[str, Path]:
    relative = meta.get("traceDirectory")
    if not isinstance(relative, str):
        return {}
    directory = (run / relative).resolve()
    trace = directory / "trace.jsonl"
    if not trace.is_file():
        return {}
    paths = {}
    for line in trace.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        for key, reference in record.get("artifacts", {}).items():
            relative_file = reference.get("path")
            if not isinstance(relative_file, str):
                continue
            path = (directory / relative_file).resolve()
            if path.is_relative_to(directory) and path.is_file():
                paths[key] = path
    return paths


def read_reference(paths: dict[str, Path], key: str) -> str | None:
    path = paths.get(key)
    return path.read_text(encoding="utf-8") if path is not None else None


def analyze(run: Path) -> dict:
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    results = summary.get("results", [])
    preview = run / "preview"
    layouts = Counter()
    statuses = Counter()
    preview_repairs = []
    failures = []
    canonical_dir = run / "canonical-designcompactdsl"
    canonical_dir.mkdir(exist_ok=True)
    for meta in results:
        index = meta.get("index")
        if not isinstance(index, int):
            raise ValueError("Missing result index")
        filename = f"q{index}_artifact.md"
        original_file = run / "md" / filename
        artifact = original_file.read_text(encoding="utf-8") if original_file.is_file() else ""
        refs = trace_artifacts(run, meta)
        for label, ref in (("request", "raw_request"), ("taskspec", "task_spec")):
            value = read_reference(refs, ref)
            if block(artifact, label) is None and value is not None:
                artifact += f"\n```{label}\n{value}\n```\n"
        source = block(artifact, "designcompactdsl")
        if source is None:
            source = read_reference(refs, "dsl_processing_input")
        parent = None
        canonical = None
        if source is not None:
            try:
                canonical = serialize_compact_dsl_source(source)
                rows = parse_compact_dsl_rows(canonical, expand_layouts=False)
                for row in rows:
                    if isinstance(row, ComponentRow) and row.component_id == "root":
                        parent = row.props.get("layout") if row.component_type == "Layout" else None
            except CompactDslConversionError as exc:
                meta["previewSourceError"] = str(exc)
        layouts[parent or "legacy-or-unparseable"] += 1
        statuses[meta.get("status", "unknown")] += 1
        meta["semanticLayout"] = parent
        if canonical is not None:
            (canonical_dir / f"q{index}.jsonl").write_text(canonical, encoding="utf-8")
            replacement = f"```designcompactdsl\n{canonical}\n```"
            if block(artifact, "designcompactdsl") is None:
                artifact += "\n" + replacement + "\n"
            else:
                artifact = re.sub(r"^```designcompactdsl\s*\n.*?\n```",
                                  lambda _, value=replacement: value, artifact, flags=re.M | re.S)
            meta["previewSourceCanonicalized"] = canonical.strip() != source.strip()
            if meta["previewSourceCanonicalized"]:
                preview_repairs.append(index)
        elif source is not None and block(artifact, "designcompactdsl") is None:
            artifact += f"\n```designcompactdsl\n{source}\n```\n"
        (preview / "md").mkdir(parents=True, exist_ok=True)
        (preview / "md" / filename).write_text(artifact, encoding="utf-8")
        (preview / f"q{index}_meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        if meta.get("status") not in {"success", "degraded"}:
            issues = read_reference(refs, "dsl_processing_issues")
            failures.append({"case": index, "issues": json.loads(issues) if issues else []})
    durations = [meta.get("totalElapsed_ms", 0) / 1000 for meta in results]
    passed = [meta for meta in results if meta.get("status") in {"success", "degraded"}]
    first = sum(meta.get("qualityRepairAttempts") == 0 for meta in passed)
    metrics = {
        "tasks": len(results), "serviceStatus": dict(statuses),
        "validatedOutputCount": len(passed), "firstPassCount": first,
        "meanWholeTaskSeconds": round(statistics.mean(durations), 2),
        "medianWholeTaskSeconds": round(statistics.median(durations), 2),
        "batchWholeSeconds": round(summary.get("totalElapsed_ms", 0) / 1000, 2),
        "totalRepairAttempts": sum(meta.get("qualityRepairAttempts", 0) for meta in results),
        "layouts": dict(layouts), "previewSyntaxNormalizedCases": preview_repairs,
        "note": "预览仅规范化源JSON；服务状态来自原始请求，不改变通过/失败判定。",
        "failedCases": failures,
    }
    (run / "semantic-metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    (preview / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    args = parser.parse_args()
    metrics = analyze(args.run)
    print(json.dumps({key: value for key, value in metrics.items() if key != "failedCases"},
                     ensure_ascii=False, indent=2))
