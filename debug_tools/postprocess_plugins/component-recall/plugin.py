"""基于数据集显式标注的高阶组件召回分析。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from debug_tools.paths import CLOUD_ROOT

_ANNOTATION_VERSION = "component-recall-ground-truth-v1"
_ANNOTATION_FILE = "component-recall.json"


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON 根节点必须是对象: {path.name}")
    return value


def _annotations(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "dataset_evaluation" / _ANNOTATION_FILE
    value = _read_object(path)
    if value.get("schemaVersion") != _ANNOTATION_VERSION:
        raise ValueError("组件召回标注版本无效")
    samples = value.get("samples")
    if not isinstance(samples, dict):
        raise ValueError("组件召回标注缺少 samples")
    return samples


def _registered_components() -> set[str]:
    contract_path = (
        CLOUD_ROOT
        / "data"
        / "protocol_profiles"
        / "design-compact-dsl-fusion"
        / "runtime"
        / "visual-recipes-v1.json"
    )
    contract = _read_object(contract_path)
    components = contract.get("components")
    if not isinstance(components, dict):
        raise ValueError("高阶组件注册表无效")
    return {str(name) for name in components}


def _actual_components(path: Path) -> set[str]:
    registered = _registered_components()
    actual: set[str] = set()
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Design Compact DSL 第 {line_number} 行不是合法 JSON") from exc
        if not isinstance(value, list) or len(value) < 3:
            continue
        component = value[1]
        if isinstance(component, str) and component in registered:
            actual.add(component)
    return actual


def _string_list(value: object, name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"组件召回标注 {name} 必须是非空字符串数组")
    return list(dict.fromkeys(value))


def _expected_units(annotation: dict[str, Any]) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    required = annotation.get("required", [])
    if not isinstance(required, list):
        raise ValueError("组件召回标注 required 必须是数组")
    for component in _string_list(required, "required") if required else []:
        units.append({"kind": "required", "label": component, "options": [component]})
    any_of = annotation.get("anyOf", [])
    if not isinstance(any_of, list):
        raise ValueError("组件召回标注 anyOf 必须是数组")
    for index, group in enumerate(any_of, start=1):
        options = _string_list(group, f"anyOf[{index}]")
        units.append(
            {
                "kind": "anyOf",
                "label": " / ".join(options),
                "options": options,
            }
        )
    if not units:
        raise ValueError("组件召回标注至少包含一个召回单元")
    return units


def _sample_id(context: dict[str, Any]) -> str:
    sample = context.get("sample")
    if not isinstance(sample, dict):
        raise ValueError("样本上下文无效")
    return str(sample.get("id") or "")


def process_sample(context: dict[str, Any]) -> dict[str, Any]:
    run_dir = Path(str(context.get("runDir") or ""))
    sample_id = _sample_id(context)
    annotation = _annotations(run_dir).get(sample_id)
    if annotation is None:
        return {
            "status": "skipped",
            "summary": "该样本没有组件召回真值标注",
            "facts": {"annotated": False, "verdict": "unannotated"},
            "artifacts": [],
        }
    if not isinstance(annotation, dict):
        raise ValueError(f"样本 {sample_id} 的组件召回标注无效")
    units = _expected_units(annotation)
    final_attempt_value = context.get("finalAttemptDir")
    dsl_path = (
        Path(str(final_attempt_value)) / "blocks" / "designcompactdsl.txt"
        if final_attempt_value
        else None
    )
    has_output = dsl_path is not None and dsl_path.is_file()
    parse_error = ""
    actual: set[str] = set()
    if has_output and dsl_path is not None:
        try:
            actual = _actual_components(dsl_path)
        except ValueError as exc:
            parse_error = str(exc)
    comparison: list[dict[str, Any]] = []
    matched_components: set[str] = set()
    missing: list[str] = []
    for unit in units:
        options = list(unit["options"])
        matched = next((component for component in options if component in actual), "")
        if matched:
            matched_components.add(matched)
        else:
            missing.append(str(unit["label"]))
        comparison.append(
            {
                "requirement": unit["label"],
                "kind": unit["kind"],
                "options": options,
                "matched": matched,
                "status": "matched" if matched else "missing",
            }
        )
    hits = len(units) - len(missing)
    recall_rate = round(hits * 100.0 / len(units), 1)
    extras = sorted(actual - matched_components)
    output_dir = Path(str(context.get("outputDir") or ""))
    artifacts: list[dict[str, Any]] = [
        {"key": "component-comparison", "data": comparison},
        {
            "key": "actual-components",
            "data": [
                {
                    "component": component,
                    "classification": (
                        "matched" if component in matched_components else "extra"
                    ),
                }
                for component in sorted(actual)
            ],
        },
    ]
    if has_output and dsl_path is not None:
        target = output_dir / "designcompactdsl.txt"
        shutil.copy2(dsl_path, target)
        artifacts.append({"key": "source-dsl", "path": target.name, "language": "jsonl"})
    status = "success" if has_output and not parse_error else "failed"
    if parse_error:
        verdict = "invalid-output"
    elif not has_output:
        verdict = "no-output"
    else:
        verdict = "full" if recall_rate == 100.0 else "missing"
    return {
        "status": status,
        "summary": (
            f"召回 {hits}/{len(units)} 个组件单元"
            if has_output and not parse_error
            else parse_error or "没有最终 Design Compact DSL，召回率记为 0%"
        ),
        "facts": {
            "annotated": True,
            "recallRate": recall_rate,
            "verdict": verdict,
            "expectedUnits": len(units),
            "actualCount": len(actual),
            "actualComponents": sorted(actual),
            "missingComponents": missing,
            "extraComponents": extras,
            "parseError": parse_error,
        },
        "artifacts": artifacts,
    }


def _distribution(rates: list[float]) -> list[dict[str, Any]]:
    bins = [
        ("0–20%", 0.0, 20.0),
        ("20–40%", 20.0, 40.0),
        ("40–60%", 40.0, 60.0),
        ("60–80%", 60.0, 80.0),
        ("80–100%", 80.0, 100.1),
    ]
    result: list[dict[str, Any]] = []
    for label, lower, upper in bins:
        count = sum(1 for rate in rates if lower <= rate < upper)
        result.append({"range": label, "count": count})
    return result


def process_dataset(context: dict[str, Any]) -> dict[str, Any]:
    raw_results = context.get("sampleResults")
    sample_results = raw_results if isinstance(raw_results, list) else []
    annotated: list[dict[str, Any]] = []
    for item in sample_results:
        if not isinstance(item, dict):
            continue
        facts = item.get("facts")
        if isinstance(facts, dict) and facts.get("annotated") is True:
            annotated.append(item)
    rates: list[float] = []
    full = 0
    component_stats: dict[str, dict[str, int]] = {}
    for item in annotated:
        facts = item.get("facts")
        if not isinstance(facts, dict):
            continue
        rate_value = facts.get("recallRate")
        if isinstance(rate_value, (int, float)):
            rate = float(rate_value)
            rates.append(rate)
            if rate == 100.0:
                full += 1
        for artifact in list(item.get("artifacts") or []):
            if not isinstance(artifact, dict) or artifact.get("key") != "component-comparison":
                continue
            for row in list(artifact.get("data") or []):
                if not isinstance(row, dict):
                    continue
                label = str(row.get("requirement") or "")
                stats = component_stats.setdefault(label, {"expected": 0, "matched": 0})
                stats["expected"] += 1
                if row.get("status") == "matched":
                    stats["matched"] += 1
    total = len(sample_results)
    evaluated = len(annotated)
    macro = round(sum(rates) / len(rates), 1) if rates else 0.0
    missing = evaluated - full
    component_rows: list[dict[str, Any]] = []
    for component, stats in sorted(component_stats.items()):
        expected = stats["expected"]
        matched = stats["matched"]
        component_rows.append(
            {
                "component": component,
                "expected": expected,
                "matched": matched,
                "recallRate": round(matched * 100.0 / expected, 1) if expected else 0.0,
            }
        )
    processing_failed = any(item.get("status") == "failed" for item in annotated)
    return {
        "status": "partial" if processing_failed else "success",
        "summary": f"已评估 {evaluated}/{total} 个样本，宏平均召回率 {macro}%",
        "facts": {
            "macroRecallRate": macro,
            "evaluatedSamples": evaluated,
            "totalSamples": total,
            "fullRecall": full,
            "missingSamples": missing,
        },
        "artifacts": [
            {
                "key": "recall-overview",
                "data": [
                    {"label": "数据集整体召回率", "value": macro, "unit": "%"},
                    {"label": "已评估样本", "value": f"{evaluated}/{total}"},
                    {"label": "完全召回", "value": full},
                    {"label": "存在缺失", "value": missing},
                ],
            },
            {"key": "recall-distribution", "data": _distribution(rates)},
            {"key": "component-stats", "data": component_rows},
        ],
    }
