"""单批 Web 评分适配：只读输入、保留证据，不修复 DSL，不触发模型。"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path
from typing import Any

# 宿主按文件加载插件，工作目录是输出目录；不能依赖机器上的 PYTHONPATH。
_SPEC = importlib.util.spec_from_file_location(
    "quality_score_model", Path(__file__).with_name("score_model.py")
)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError("无法加载随插件交付的评分模型")
model = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(model)

BOUNDARY = (
    "仅评价当前 Web 预览的已声明检查：文字截断、画布越界、文字重叠候选、素材加载和解析诊断。"
    "不验证真实 Intent 执行、完整业务语义、端侧一致性、色板与整体审美。"
    "100 分不等于训练验收；分数上下界不是统计置信区间。"
)


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON 根节点必须为对象：{path.name}")
    return value


def _inside(root: Path, value: str) -> Path:
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("输入文件越过运行目录")
    return path


def _pending(reason: str) -> dict[str, Any]:
    return {
        "status": "partial",
        "summary": reason,
        "facts": {"score": None, "scoreLow": None, "verdict": "待评", "confirmed": 0, "pending": 0},
        "artifacts": [
            {"key": "score", "data": [{"label": "评分", "value": "待评"}]},
            {"key": "issues", "data": [{"状态": "证据不足", "原因": reason}]},
            {"key": "coverage", "data": BOUNDARY},
        ],
    }


def _evidence(context: dict[str, Any]) -> dict[str, Any] | None:
    for stage in context.get("upstreamResults", []):
        if stage.get("pluginId") != "browser-gallery":
            continue
        result = stage.get("result") or {}
        for artifact in result.get("artifacts", []):
            if artifact.get("key") == "web-quality-evidence":
                value = artifact.get("data")
                if isinstance(value, dict):
                    return value
    return None


def process_sample(context: dict[str, Any]) -> dict[str, Any]:
    """复用同一次网页渲染证据与既定模型；历史截图或缺证据不得给满分。"""
    sample = context.get("sample")
    if not isinstance(sample, dict):
        raise ValueError("缺少 sample")
    run_dir = Path(context.get("runDir", "")).resolve()
    final_dir = context.get("finalAttemptDir")
    if not final_dir:
        return _pending("没有最终产物；生成失败与质量淘汰应分别统计")
    source_dir = _inside(run_dir, final_dir)
    dsl_path = _inside(run_dir, str(source_dir / "genui.jsonl"))
    if not dsl_path.is_file():
        return _pending("最终产物没有 GenUI，无法对当前卡片评分")
    evidence = _evidence(context)
    if not evidence or evidence.get("schemaVersion") != "web-quality-v1":
        return _pending("缺少新版 Web 检测证据；先再次运行浏览器渲染画廊，再运行评分")
    source = dsl_path.read_text(encoding="utf-8")
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    if evidence.get("sourceSha256") != digest:
        return _pending("DSL 已变化或证据未绑定当前 DSL；请重新运行画廊")
    blocks_path = _inside(run_dir, str(source_dir / "blocks.json"))
    blocks = _read_object(blocks_path) if blocks_path.is_file() else None
    render_context = {"query": sample.get("query"), "size": sample.get("size"), "blocks": blocks}
    if evidence.get("renderContext") != render_context:
        return _pending("Query、尺寸或最终产物上下文已变化；请重新运行画廊")
    render_failed = evidence.get("renderFailed") is True
    if not render_failed and evidence.get("complete") is not True:
        return _pending("网页测量未完成，不能用空问题单评分")
    expected_coverage = {
        "text-clipping",
        "card-boundary",
        "text-overlap-candidates",
        "image-loading",
        "parser-warnings",
    }
    if not render_failed and not expected_coverage.issubset(evidence.get("coverage", [])):
        return _pending("检测证据未包含本版声明的检查范围")
    if not render_failed and "findings" not in evidence:
        return _pending("检测结果缺少 findings；未检测不等于没有问题")
    findings = evidence.get("findings", [])
    if not isinstance(findings, list) or any(not isinstance(x, dict) for x in findings):
        raise ValueError("检测证据 findings 格式错误")
    findings = list(findings)
    if render_failed:
        findings.append({"code": "render.failed", "message": "当前 DSL 的 Web 解析或渲染失败"})
    for warning in evidence.get("parseWarnings", []):
        findings.append({"code": "protocol.profile_diagnostics", "message": str(warning)})
    normalized = [model.normalize(f, "web-quality-v1") for f in findings]
    result = model.score(normalized)
    score = result.get("score")
    bounds = result.get("range")
    low = bounds[0] if bounds else None
    verdict = "范围内未扣分"
    if score is None:
        verdict = "待评"
    elif result.get("hard_reject"):
        verdict = "Web渲染淘汰"
    elif result.get("pending_groups"):
        verdict = "含待确认问题"
    elif result.get("confirmed_groups"):
        verdict = "存在确认问题"
    artifacts: list[dict[str, Any]] = []
    if not render_failed:
        image_value = evidence.get("imageRunPath")
        if not isinstance(image_value, str):
            return _pending("缺少本次截图路径")
        image_path = _inside(run_dir, image_value)
        if not image_path.is_file():
            return _pending("本次截图文件缺失")
        image_bytes = image_path.read_bytes()
        if hashlib.sha256(image_bytes).hexdigest() != evidence.get("imageSha256"):
            return _pending("截图哈希不匹配；不展示旧图或混用分数")
        output_dir = Path(context.get("outputDir", ""))
        target = output_dir / "card.png"
        shutil.copy2(image_path, target)
        artifacts.append({"key": "capture", "path": target.name, "alt": "本次 Web 渲染截图"})
    issue_rows = []
    for finding in normalized:
        issue_rows.append(
            {
                "规则": finding.get("code"),
                "分类": model.NAMES.get(finding.get("category"), "未映射"),
                "状态": (
                    "信息" if finding.get("info")
                    else "确认" if finding.get("confirmed") else "待确认"
                ),
                "组件": finding.get("components"),
                "原因": finding.get("message"),
                "证据": finding.get("evidence"),
            }
        )
    artifacts.extend(
        [
            {
                "key": "score",
                "data": [
                    {"label": "已确认扣分后", "value": score if score is not None else "待评"},
                    {"label": "含疑似问题下界", "value": low if low is not None else "待评"},
                    {"label": "质量状态", "value": verdict},
                ],
            },
            {"key": "deductions", "data": result.get("breakdown", [])},
            {"key": "issues", "data": issue_rows},
            {"key": "coverage", "data": BOUNDARY},
            {
                "key": "detail",
                "data": {
                    "scoring": result, "evidence": evidence, "policy": model.policy(),
                    "policySha256": model.policy_digest(),
                },
            },
        ]
    )
    return {
        "status": "partial" if score is None else "success",
        "summary": f"{verdict}；仅限 Web 检查范围，不代表训练验收",
        "facts": {
            "score": score,
            "scoreLow": low,
            "verdict": verdict,
            "confirmed": result.get("confirmed_groups"),
            "pending": result.get("pending_groups"),
        },
        "artifacts": artifacts,
    }


def process_dataset(context: dict[str, Any]) -> dict[str, Any]:
    """未知不记作零或满分；均分上下界按同一已评分子集汇总。"""
    rows, highs, lows = [], [], []
    rejected = 0
    results = context.get("sampleResults", [])
    config = context.get("config") or {}
    selected = config.get("sampleIds")
    if selected is not None:
        results = [item for item in results if item.get("sampleId") in selected]
    elif config.get("count") is not None:
        count = config.get("count")
        results = results[:count]
    for item in results:
        facts = item.get("facts", {})
        value, low = facts.get("score"), facts.get("scoreLow")
        rows.append({"样本": item.get("sampleId"), **facts})
        if isinstance(value, int | float) and isinstance(low, int | float):
            highs.append(value)
            lows.append(low)
        rejected += facts.get("verdict") == "Web渲染淘汰"
    total, scored = len(rows), len(highs)
    bins = []
    for lower in range(0, 100, 20):
        count = sum(lower <= x < lower + 20 for x in highs)
        if lower == 80:
            count += highs.count(100)
        bins.append({"分数段": f"{lower}–{lower + 20}", "卡片数": count})
    return {
        "status": "success" if scored == total else "partial",
        "summary": f"已评分 {scored}/{total}；待评 {total - scored}；Web 渲染淘汰 {rejected}",
        "facts": {
            "total": total,
            "scored": scored,
            "pending": total - scored,
            "rejected": rejected,
        },
        "artifacts": [
            {
                "key": "overview",
                "data": [
                    {"label": "总数", "value": total},
                    {"label": "已评分", "value": scored},
                    {"label": "待评（不入均分）", "value": total - scored},
                    {"label": "Web 渲染淘汰", "value": rejected},
                    {
                        "label": "平均分上界（含淘汰）",
                        "value": round(sum(highs) / scored, 2) if scored else "待评",
                    },
                    {
                        "label": "平均分下界（含淘汰）",
                        "value": round(sum(lows) / scored, 2) if scored else "待评",
                    },
                ],
            },
            {"key": "distribution", "data": bins},
            {"key": "scores", "data": rows},
            {"key": "policy", "data": model.policy()},
        ],
    }
