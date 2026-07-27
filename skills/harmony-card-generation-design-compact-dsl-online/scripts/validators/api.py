"""Public API for validate_card.

Only responsibility here is to wire input normalization → context building →
pipeline execution. Split into ``inputs.py``, ``effective_loader.py``,
``pipeline.py`` so this file stays small and easy to read.

Two entry points are exposed:

- ``validate_card`` — full-featured entry that accepts DSL + CardSpec + artifact
  + effectiveCapabilities and returns a ``Reporter``. Use this when you need
  structured diagnostics or CardSpec-aware checks.
- ``validate_dsl`` — quick entry that validates only the DSL and returns a
  model-friendly string via ``Reporter.render_model``. Missing CardSpec is
  silently tolerated: CardSpec-only errors are dropped so callers get a clean
  DSL-only report. This is the default posture for local tests and API calls
  from other agents/services.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .diagnostics import Reporter
from .effective_loader import attach_effective_capabilities
from .inputs import (
    artifact_cardspec_text,
    artifact_dsl,
    cardspec_text,
    effective_from_inputs,
    parse_jsonish,
    unwrap_artifact,
)
from .pipeline import PIPELINE_BLOCKING_CODES, run_pipeline
from .rule_registry import RuleRegistry
from .source_parser import SourceParser, extract_combined


@dataclass
class ValidationOptions:
    stage: str = "all"
    max_errors: int = 50
    stop_on_stage_error: bool = False
    skill_dir: Path | None = None
    capabilities_dir: Path | None = None


def validate_card(
    *,
    dsl_text: str = "",
    cardspec: dict[str, Any] | str | None = None,
    artifact: dict[str, Any] | str | None = None,
    effective_capabilities: dict[str, Any] | str | None = None,
    options: ValidationOptions | None = None,
) -> Reporter:
    opts = options or ValidationOptions()
    skill_dir = opts.skill_dir or Path(__file__).resolve().parents[2]
    rules = RuleRegistry(skill_dir)
    reporter = Reporter(rules.diagnostics, max_errors=opts.max_errors)

    artifact_value = unwrap_artifact(parse_jsonish(artifact))
    effective_value = effective_from_inputs(effective_capabilities, artifact_value)

    resolved_dsl = dsl_text or artifact_dsl(artifact_value)
    resolved_cardspec = cardspec_text(cardspec) or artifact_cardspec_text(artifact_value)
    if not resolved_dsl and not resolved_cardspec and isinstance(artifact, str):
        resolved_dsl, resolved_cardspec = extract_combined(artifact)

    context = SourceParser().parse(resolved_dsl, resolved_cardspec, reporter)
    attach_effective_capabilities(
        context,
        effective_value,
        artifact_value,
        opts.capabilities_dir,
    )
    if not reporter.has_code(*PIPELINE_BLOCKING_CODES):
        run_pipeline(
            context,
            rules,
            reporter,
            opts.stage,
            stop_on_stage_error=opts.stop_on_stage_error,
        )
    return reporter


def validate_dsl(
    dsl_text: str,
    *,
    effective_capabilities: dict[str, Any] | str | None = None,
    options: ValidationOptions | None = None,
) -> str:
    """Validate DSL only and return a model-friendly report string.

    - 只跑 DSL 相关的协议/组件/表达式/绑定/跨文件/颜色规则。
    - CardSpec 缺失是允许的：validator 层已经处理"未提供 CardSpec 时不校验
      CardSpec 必填字段"这条语义，这里再兜底一次，把只针对 cardspec 的诊断从
      结果中过滤掉，避免污染面向模型的输出。
    - 返回值就是 ``Reporter.render_model`` 的字符串；调用方可以直接把它转发给
      下游模型或写入日志。永远不会抛出诊断相关异常（校验器本身崩溃例外）。

    需要结构化数据或 CardSpec-aware 校验时，走 :func:`validate_card` 拿
    ``Reporter`` 对象。
    """
    reporter = validate_card(
        dsl_text=dsl_text,
        effective_capabilities=effective_capabilities,
        options=options,
    )
    # 只留下与 DSL 相关的诊断（file_kind != "cardspec"）。CardSpec 缺失或不完整
    # 时任何 file_kind="cardspec" 的诊断都不该出现在纯 DSL 报告里。
    reporter.diagnostics = [d for d in reporter.diagnostics if d.file_kind != "cardspec"]
    return reporter.render_model()
