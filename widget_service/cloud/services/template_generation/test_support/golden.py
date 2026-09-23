# -*- coding: utf-8 -*-
"""模板金样（golden master）工具：Layer A 每模板快照的生成、分类比对与固化。

快照来自确定性 preview dataset（不经过 LLM），每个 provider 模板一份
canonical JSON。用于在模板/引擎改动后区分「预期 UI 变化」与「未预期 UI
漂移」。description 等提示词侧元数据不入快照——本层只盯 UI 内容；
Layer B（taskspec 级、固定首层 query 的产物快照）后续复用同一套
canonicalize/compare 机制。

用法（在 cloud/ 目录下）::

    python3 -m services.template_generation.test_support.golden run
    python3 -m services.template_generation.test_support.golden run --diff \\
        --declared ScheduleOverviewEventCountDetailsFull@1
    python3 -m services.template_generation.test_support.golden accept

``run`` 在存在未申报差异时退出码 1；``accept`` 将当前生成结果固化为金样
（首次引导与复核后更新共用）。
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from services.template_generation.engine.cardplan.preview_dataset import (
    build_template_preview_cases,
)

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "tests" / "goldens"
TEMPLATES_DIR = GOLDEN_DIR / "templates"
MANIFEST_PATH = GOLDEN_DIR / "manifest.json"

_DIFF_LINE_CAP = 200
_LIST_ID_CAP = 20


@dataclass(frozen=True)
class CheckLayer:
    """一层金样在 check 报告中的输入。"""

    label: str
    comparison: GoldenComparison
    extra_failed: tuple[str, ...] = ()


@dataclass(frozen=True)
class CheckReport:
    """Jest 风格的 check 汇总：正文 + 判定。"""

    text: str
    has_undeclared: bool
    has_stale: bool
    has_divergence: bool
    failed_ids: tuple[str, ...]
    review_ids: tuple[str, ...]


def render_check_report(layers: list[CheckLayer]) -> CheckReport:
    """渲染 Jest 风格的分层测试摘要。

    结果状态与 Jest 快照语义对应：
      PASS   生成结果与金样一致且回放可验证；
      STALE  内容仍一致但录制已失效（replay miss）——需重录才能继续验证；
      REVIEW 差异已申报（declared），等待 bless 固化；
      FAIL   未申报差异。
    """
    layer_lines: list[str] = []
    failed_lines: list[str] = []
    stale_lines: list[str] = []
    review_lines: list[str] = []
    total_passed = total_stale = total_review = total_failed = 0
    failed_ids: list[str] = []
    review_ids: list[str] = []
    for layer in layers:
        comparison = layer.comparison
        failed = (
            list(comparison.undeclared_changes)
            + list(comparison.undeclared_additions)
            + list(comparison.undeclared_removals)
        )
        # replay miss 且输出已分歧的用例已在 failed 里；输出仍一致的归入
        # STALE（内容没变但录制失效，需重录才能继续验证）。
        stale = [item_id for item_id in layer.extra_failed if item_id not in failed]
        review = (
            list(comparison.declared_changes)
            + list(comparison.declared_additions)
            + list(comparison.declared_removals)
        )
        passed = len(comparison.unchanged) - len(stale)
        total = passed + len(stale) + len(failed) + len(review)
        if failed:
            status = "FAIL"
        elif stale:
            status = "STALE"
        elif review:
            status = "REVIEW"
        else:
            status = "PASS"
        layer_lines.append(
            f"  {layer.label:<10} {status:<6} "
            f"passed {passed:>3} · stale {len(stale):>3} · "
            f"under review {len(review):>3} · failed {len(failed):>3} · "
            f"total {total:>3}"
        )
        kind = layer.label.rstrip("s").lower()
        for item_id in failed:
            failed_lines.append(f"  [{kind}] {item_id}")
        for item_id in stale:
            stale_lines.append(f"  [{kind}] {item_id}")
        for item_id in review:
            review_lines.append(f"  [{kind}] {item_id}")
        failed_ids.extend(f"{kind}:{item_id}" for item_id in failed)
        review_ids.extend(f"{kind}:{item_id}" for item_id in review)
        total_passed += passed
        total_stale += len(stale)
        total_review += len(review)
        total_failed += len(failed)

    lines = ["Golden check", *layer_lines, ""]
    if failed_lines:
        lines += [
            "Failed (undeclared - fix the code, or re-run check with --declared):",
            *failed_lines,
            "",
        ]
    if stale_lines:
        lines += [
            "Stale recordings (output unchanged but unverifiable - re-record):",
            *stale_lines,
            "",
        ]
    if review_lines:
        lines += [
            "Under review (declared - promote with: golden_cli bless --declared <ids>):",
            *review_lines,
            "",
        ]
    lines.append(
        f"Golden summary  passed {total_passed} · stale {total_stale} · "
        f"under review {total_review} · failed {total_failed}"
    )
    has_undeclared = total_failed > 0
    has_stale = total_stale > 0
    has_divergence = has_undeclared or has_stale or total_review > 0
    if has_undeclared:
        suffix = f", {total_stale} stale" if has_stale else ""
        verdict = f"Result: FAILED ({total_failed} undeclared{suffix})"
    elif has_stale:
        verdict = f"Result: STALE RECORDINGS ({total_stale} need re-record)"
    elif total_review:
        verdict = "Result: REVIEW PENDING (all changes declared - bless to promote)"
    else:
        verdict = "Result: PASSED"
    lines.append(verdict)
    return CheckReport(
        text="\n".join(lines),
        has_undeclared=has_undeclared,
        has_stale=has_stale,
        has_divergence=has_divergence,
        failed_ids=tuple(failed_ids),
        review_ids=tuple(review_ids),
    )


_PydanticDocsLineRe = re.compile(
    r"\n\s*For further information visit https://errors\.pydantic\.dev/\S+"
)


def _normalize_error_text(value: Any) -> Any:
    """递归剥离 ValidationError 文案里随 pydantic 版本变化的帮助链接。

    ``str(ValidationError)`` 以 ``For further information visit
    https://errors.pydantic.dev/<版本>/v/<错误码>`` 结尾，版本号跟随当前
    安装的 pydantic（依赖只声明 ``pydantic>=2.8.0``），属于环境差异而非
    业务契约；字段位置、错误类型与业务错误消息全部保留。
    """
    if isinstance(value, str):
        return _PydanticDocsLineRe.sub("", value)
    if isinstance(value, dict):
        return {key: _normalize_error_text(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(_normalize_error_text(item) for item in value)
    return value


def canonicalize(payload: Any) -> str:
    """Canonical JSON：对象键排序、数组顺序保持原样、缩进稳定。

    序列化前剥离错误文案中随依赖版本漂移的片段，使基线只固化业务契约。
    """
    return (
        json.dumps(_normalize_error_text(payload), ensure_ascii=False, sort_keys=True, indent=2)
        + "\n"
    )


@dataclass(frozen=True)
class TemplateGolden:
    """单个模板的快照：元数据 + canonical JSON 文本。"""

    template_id: str
    meta: dict[str, str]
    text: str


def build_snapshots() -> dict[str, TemplateGolden]:
    """把每个 preview case 编译成按模板 ID 索引的 canonical 快照。"""
    snapshots: dict[str, TemplateGolden] = {}
    for case in build_template_preview_cases():
        meta = {
            "businessId": case.business_id,
            "capabilityId": case.capability_id,
            "layoutKind": case.layout_kind,
            "providerId": case.provider_id,
            "size": case.size,
        }
        payload = {
            "templateId": case.template_id,
            "meta": meta,
            "messages": list(case.messages),
        }
        snapshots[case.template_id] = TemplateGolden(
            template_id=case.template_id,
            meta=meta,
            text=canonicalize(payload),
        )
    return snapshots


def load_blessed() -> dict[str, str]:
    """读取已固化金样；金样目录不存在时返回空表（全部视为待固化新增）。"""
    if not TEMPLATES_DIR.is_dir():
        return {}
    return {
        path.stem: path.read_text(encoding="utf-8")
        for path in sorted(TEMPLATES_DIR.glob("*.json"))
    }


@dataclass(frozen=True)
class GoldenComparison:
    """ blessed 与 generated 的分类比对结果。"""

    unchanged: tuple[str, ...]
    declared_changes: tuple[str, ...]
    undeclared_changes: tuple[str, ...]
    declared_additions: tuple[str, ...]
    undeclared_additions: tuple[str, ...]
    declared_removals: tuple[str, ...]
    undeclared_removals: tuple[str, ...]

    @property
    def changed_ids(self) -> tuple[str, ...]:
        return self.declared_changes + self.undeclared_changes

    @property
    def has_divergence(self) -> bool:
        return bool(
            self.declared_changes
            or self.undeclared_changes
            or self.declared_additions
            or self.undeclared_additions
            or self.declared_removals
            or self.undeclared_removals
        )

    @property
    def has_undeclared_divergence(self) -> bool:
        return bool(
            self.undeclared_changes
            or self.undeclared_additions
            or self.undeclared_removals
        )


def compare(
    generated: dict[str, TemplateGolden],
    blessed: dict[str, str],
    *,
    declared: frozenset[str] = frozenset(),
    declare_all: bool = False,
) -> GoldenComparison:
    """逐模板分类差异；新增/删除同样走 declared 过滤。"""

    def _split(ids: list[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
        hit = tuple(item for item in ids if declare_all or item in declared)
        miss = tuple(item for item in ids if not (declare_all or item in declared))
        return hit, miss

    unchanged: list[str] = []
    changed: list[str] = []
    added: list[str] = []
    for template_id in sorted(generated):
        blessed_text = blessed.get(template_id)
        if blessed_text is None:
            added.append(template_id)
        elif blessed_text == generated[template_id].text:
            unchanged.append(template_id)
        else:
            changed.append(template_id)
    removed = sorted(set(blessed) - set(generated))
    declared_changes, undeclared_changes = _split(changed)
    declared_additions, undeclared_additions = _split(added)
    declared_removals, undeclared_removals = _split(removed)
    return GoldenComparison(
        unchanged=tuple(unchanged),
        declared_changes=declared_changes,
        undeclared_changes=undeclared_changes,
        declared_additions=declared_additions,
        undeclared_additions=undeclared_additions,
        declared_removals=declared_removals,
        undeclared_removals=undeclared_removals,
    )


def render_report(comparison: GoldenComparison, title: str = "Template golden comparison:") -> str:
    def fmt(ids: tuple[str, ...]) -> str:
        if not ids:
            return "0"
        shown = ", ".join(ids[:_LIST_ID_CAP])
        if len(ids) > _LIST_ID_CAP:
            shown += f", ... +{len(ids) - _LIST_ID_CAP} more"
        return f"{len(ids)} ({shown})"

    lines = [
        title,
        f"  unchanged:            {len(comparison.unchanged)}",
        f"  changed (declared):   {fmt(comparison.declared_changes)}",
        f"  changed (UNDECLARED): {fmt(comparison.undeclared_changes)}",
        f"  added   (declared):   {fmt(comparison.declared_additions)}",
        f"  added   (UNDECLARED): {fmt(comparison.undeclared_additions)}",
        f"  removed (declared):   {fmt(comparison.declared_removals)}",
        f"  removed (UNDECLARED): {fmt(comparison.undeclared_removals)}",
    ]
    if comparison.has_undeclared_divergence:
        lines += [
            "UNDECLARED UI drift - investigate before blessing.",
            "  inspect:  python3 -m services.template_generation.test_support.golden run --diff",
            "  declare:  re-run with --declared <template_id,...>",
        ]
    elif comparison.has_divergence:
        lines += [
            "All divergence is declared. Bless it before committing:",
            "  python3 -m services.template_generation.test_support.golden accept",
        ]
    else:
        lines.append("OK: generated UI matches the blessed golden set.")
    return "\n".join(lines)


def render_diff(
    template_id: str,
    generated: dict[str, TemplateGolden],
    blessed: dict[str, str],
) -> str | None:
    snapshot = generated.get(template_id)
    blessed_text = blessed.get(template_id)
    if snapshot is None or blessed_text is None:
        return None
    diff = difflib.unified_diff(
        blessed_text.splitlines(),
        snapshot.text.splitlines(),
        fromfile=f"goldens/templates/{template_id}.json (blessed)",
        tofile=f"{template_id} (generated)",
        lineterm="",
    )
    return "\n".join(list(diff)[:_DIFF_LINE_CAP])


def bless(
    generated: dict[str, TemplateGolden],
    *,
    only: frozenset[str] | None = None,
) -> None:
    """固化当前生成结果：写每模板快照 + 索引 manifest，清理失效文件。

    ``only`` 限制实际写入的模板（未列入的已固化文件保持原样）；
    清理与 manifest 始终按完整 ``generated`` 集合计算。
    """
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    for path in TEMPLATES_DIR.glob("*.json"):
        if path.stem not in generated:
            path.unlink()
    for template_id, snapshot in sorted(generated.items()):
        if only is not None and template_id not in only:
            continue
        (TEMPLATES_DIR / f"{template_id}.json").write_text(
            snapshot.text, encoding="utf-8"
        )
    manifest = {
        "goldenVersion": "template-goldens/1",
        "templateCount": len(generated),
        "templates": [
            {"templateId": template_id, **generated[template_id].meta}
            for template_id in sorted(generated)
        ],
    }
    MANIFEST_PATH.write_text(canonicalize(manifest), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="golden",
        description="Template golden-master tool (Layer A, deterministic preview snapshots).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser(
        "run", help="regenerate snapshots and compare with the blessed set"
    )
    run_parser.add_argument(
        "--declared",
        default="",
        help="comma-separated template ids whose UI change is expected",
    )
    run_parser.add_argument(
        "--declare-all",
        action="store_true",
        help="treat every divergence as declared (engine-wide change review)",
    )
    run_parser.add_argument(
        "--diff", action="store_true", help="print unified diffs for changed templates"
    )

    sub.add_parser(
        "accept", help="bless the generated snapshots (bootstrap or post-review update)"
    )

    diff_parser = sub.add_parser("diff", help="print the unified diff for one template")
    diff_parser.add_argument("template_id")

    args = parser.parse_args(argv)

    generated = build_snapshots()
    blessed = load_blessed()

    if args.command == "accept":
        bless(generated)
        print(f"Blessed {len(generated)} template goldens under {TEMPLATES_DIR}")
        return 0

    if args.command == "diff":
        text = render_diff(args.template_id, generated, blessed)
        if text is None:
            print(
                f"No diff available for {args.template_id!r} (missing on one side).",
                file=sys.stderr,
            )
            return 1
        print(text)
        return 0

    declared = frozenset(
        item.strip() for item in args.declared.split(",") if item.strip()
    )
    comparison = compare(
        generated, blessed, declared=declared, declare_all=args.declare_all
    )
    print(render_report(comparison))
    if args.diff:
        for template_id in comparison.changed_ids:
            text = render_diff(template_id, generated, blessed)
            if text:
                print(text)
    return 0 if not comparison.has_undeclared_divergence else 1


if __name__ == "__main__":
    sys.exit(main())
