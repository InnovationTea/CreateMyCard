"""质量评分方案和历史对比；只读取已落盘证据，绝不触发生成或评分。"""

from __future__ import annotations

import importlib.util
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from .postprocess import PostprocessManager

PASS_DEFINITION = (
    "Web 范围无问题率 = 有完整评分、上下界均为 100 且无确认或待确认问题的样本数"
    " / 本次所选样本总数；待评不计通过，不代表训练验收通过率。"
)


def _model():
    path = Path(__file__).resolve().parents[1] / "postprocess_plugins/quality-score/score_model.py"
    spec = importlib.util.spec_from_file_location("quality_evaluation_model", path)
    if spec is None or spec.loader is None:
        raise ValueError("评分模型不可用")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evaluation() -> dict[str, Any]:
    model = _model()
    return {
        "markdown": model.evaluation_document(),
        "policy": model.policy(),
        "policySha256": model.policy_digest(),
    }


def _artifact(result: dict[str, Any], key: str) -> Any:
    for item in result.get("artifacts", []):
        if item.get("key") == key:
            return item.get("data")
    return None


def _number(value: Any) -> float | None:
    if type(value) not in (int, float):
        return None
    if not math.isfinite(value) or not 0 <= value <= 100:
        return None
    return value


def _sample(result: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    facts = result.get("facts") or {}
    detail = _artifact(result, "detail") or {}
    evidence = detail.get("evidence") or {}
    context = evidence.get("renderContext") or {}
    query = context.get("query", meta.get("query"))
    size = context.get("size", meta.get("size"))
    score, low = _number(facts.get("score")), _number(facts.get("scoreLow"))
    if low is None or score is None or low > score:
        score = low = None
    issues: dict[str, str] = {}
    for item in _artifact(result, "issues") or []:
        code = item.get("规则")
        state = item.get("状态")
        if not code or state == "信息":
            continue
        if issues.get(code) != "确认":
            issues[code] = state or "待确认"
    passed = (
        score == low == 100
        and facts.get("verdict") == "范围内未扣分"
        and not issues
    )
    return {
        "score": score,
        "scoreLow": low,
        "verdict": facts.get("verdict") or "待评",
        "query": query,
        "size": size,
        "issues": dict.fromkeys(issues, 1),
        "confirmedIssues": dict.fromkeys([k for k, v in issues.items() if v == "确认"], 1),
        "pendingIssues": dict.fromkeys([k for k, v in issues.items() if v != "确认"], 1),
        "passed": passed,
        "policy": detail.get("policy"),
        "evidenceVersion": evidence.get("schemaVersion"),
    }


def _result_set(
    manager: PostprocessManager, run_id: str, execution_id: str | None
) -> dict[str, Any]:
    executions = manager.executions(run_id)
    selected = None
    for execution in executions:
        if execution_id and execution.get("executionId") != execution_id:
            continue
        if execution.get("status") not in {"completed", "partial", "failed"}:
            continue
        for stage in execution.get("plugins", []):
            if stage.get("id") == "quality-score":
                selected = execution.get("executionId")
                break
        if selected:
            break
    if not isinstance(selected, str):
        raise ValueError(f"批次 {run_id} 尚无已完成评分结果；请先显式运行评分")
    dashboard = manager.dashboard(run_id, selected, "quality-score")
    policy = _artifact(dashboard.get("datasetResult") or {}, "policy")
    samples: dict[str, dict[str, Any]] = {}
    for meta in dashboard.get("samples", []):
        sample_id = meta.get("sampleId")
        if not isinstance(sample_id, str) or sample_id in samples:
            raise ValueError("评分结果样本 ID 无效或重复")
        try:
            result = manager.sample_result(run_id, selected, "quality-score", sample_id)
        except (KeyError, OSError, ValueError) as exc:
            result = {"facts": {"verdict": f"待评：结果不可读（{type(exc).__name__}）"}}
        samples[sample_id] = _sample(result, meta)
    if not samples:
        raise ValueError(f"批次 {run_id} 的最新评分无样本结果，不能用旧结果或零分替代")
    scores = []
    passed = 0
    for sample in samples.values():
        value = sample.get("score")
        if value is not None:
            scores.append(value)
        passed += sample.get("passed") is True
    return {
        "runId": run_id,
        "executionId": selected,
        "total": len(samples),
        "scored": len(scores),
        "passCount": passed,
        "passRate": round(100 * passed / len(samples), 2),
        "meanScore": round(sum(scores) / len(scores), 2) if scores else None,
        "policy": policy,
        "samples": samples,
    }


def _diff(left: dict[str, int], right: dict[str, int]) -> list[dict[str, Any]]:
    rows = []
    for code in sorted(left.keys() | right.keys()):
        a, b = left.get(code, 0), right.get(code, 0)
        rows.append({"code": code, "left": a, "right": b, "delta": b - a})
    return rows


def _same_policy(a: Any, b: Any) -> bool:
    if not isinstance(a, dict) or not a or not isinstance(b, dict):
        return False
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def compare(
    manager: PostprocessManager,
    left_run_id: str,
    right_run_id: str,
    left_execution_id: str | None = None,
    right_execution_id: str | None = None,
) -> dict[str, Any]:
    left = _result_set(manager, left_run_id, left_execution_id)
    right = _result_set(manager, right_run_id, right_execution_id)
    left_samples, right_samples = left.get("samples", {}), right.get("samples", {})
    policy_matches = _same_policy(left.get("policy"), right.get("policy"))
    warnings = []
    if not policy_matches:
        warnings.append("两边评分参数快照不一致或缺失，不计算分数及通过率差；请同口径重评")
    same_selection = left_samples.keys() == right_samples.keys()
    if not same_selection:
        warnings.append("所选样本集合不同，仅对可对齐样本计算分差，不计算总体通过率差")
    rows = []
    all_aligned = True
    distributions = {key: [Counter(), Counter()] for key in (
        "issues", "confirmedIssues", "pendingIssues"
    )}
    for sample_id in sorted(left_samples.keys() | right_samples.keys()):
        a, b = left_samples.get(sample_id), right_samples.get(sample_id)
        alignment = "matched"
        delta = None
        if a is None:
            alignment = "right-only"
        elif b is None:
            alignment = "left-only"
        elif not a.get("query") or not a.get("size"):
            alignment = "context-missing"
        elif (a.get("query"), a.get("size")) != (b.get("query"), b.get("size")):
            alignment = "context-mismatch"
        elif not policy_matches or not _same_policy(a.get("policy"), b.get("policy")):
            alignment = "policy-mismatch"
        elif not _same_policy(a.get("policy"), left.get("policy")):
            alignment = "policy-mismatch"
        elif a.get("evidenceVersion") != b.get("evidenceVersion"):
            alignment = "evidence-mismatch"
        elif a.get("score") is None or b.get("score") is None:
            alignment = "pending-score"
        else:
            delta = round(b.get("score") - a.get("score"), 2)
        if alignment not in {"matched", "pending-score"}:
            all_aligned = False
        for key, counts in distributions.items():
            counts[0].update((a or {}).get(key, {}))
            counts[1].update((b or {}).get(key, {}))
        rows.append({
            "sampleId": sample_id, "alignment": alignment,
            "left": a, "right": b, "scoreDelta": delta,
            "issueDiff": _diff((a or {}).get("issues", {}), (b or {}).get("issues", {})),
        })
    comparable = policy_matches and same_selection and all_aligned
    if not all_aligned:
        warnings.append("部分样本的 ID、上下文、参数或检测版本无法对齐，相关分差留空")
    if left.get("scored") != left.get("total") or right.get("scored") != right.get("total"):
        warnings.append("存在待评样本；均分仅覆盖有分子集，缺证据不应解释为质量下降")
    public_left = {k: v for k, v in left.items() if k not in {"samples", "policy"}}
    public_right = {k: v for k, v in right.items() if k not in {"samples", "policy"}}
    return {
        "left": public_left, "right": public_right,
        "comparable": comparable, "warnings": warnings,
        "passRateDelta": round(100 * (
            right.get("passCount") / right.get("total")
            - left.get("passCount") / left.get("total")
        ), 2)
        if comparable else None,
        "rows": rows, "issueDistribution": _diff(*distributions.get("issues")),
        "confirmedIssueDistribution": _diff(*distributions.get("confirmedIssues")),
        "pendingIssueDistribution": _diff(*distributions.get("pendingIssues")),
        "passDefinition": PASS_DEFINITION,
    }
