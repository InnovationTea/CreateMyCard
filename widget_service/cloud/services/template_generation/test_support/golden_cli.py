# -*- coding: utf-8 -*-
"""统一金样工作流入口：一条命令完成检查与固化。

覆盖两层金样：Layer A（每模板确定性快照）与 Layer B（taskspec 级
录制/回放真实生成链路）。``--declared`` 同时作用于两层；模板 ID 与
用例 ID（Qxxx）天然不重叠，可混用。

检查（PR 验证，一条命令；与 pytest 金样门禁同一套比较逻辑）::

    python3 -m services.template_generation.test_support.golden_cli check
    python3 -m services.template_generation.test_support.golden_cli check --diff \\
        --declared ScheduleOverviewEventCountDetailsFull@1,Q035

固化（复核差异之后）::

    python3 -m services.template_generation.test_support.golden_cli bless \\
        --declared <模板ID与/或用例ID逗号分隔>
    # 回放未命中（语料/提示词变化）时带语料目录自动重录：
    python3 -m services.template_generation.test_support.golden_cli bless \\
        --declared Q016 --corpus-dir <widget_batch_cases 目录>

退出码：0 = 干净，或全部差异已申报（待固化）；1 = 存在未申报漂移、
回放未命中，或 bless 被拒绝。引擎级大改可整体用 --declare-all。
bless 在存在任何未申报差异时拒绝执行，避免把未复核的变化一并固化。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from services.template_generation.test_support import golden as golden_layer
from services.template_generation.test_support import golden_scenarios
from services.template_generation.test_support import golden_taskspecs

_RECORD_HINT = (
    "  record: python3 -m services.template_generation.test_support."
    "golden_taskspecs record --corpus-dir <widget_batch_cases 目录> --cases {ids}"
)

_TOP_DESCRIPTION = """\
Golden-master UI-consistency regression for the widget card generation service.

Three snapshot layers live under
services/template_generation/tests/goldens/ (relative to cloud/):
  [template]   Layer A - one canonical A2UI snapshot per template, built from
               the deterministic preview dataset (no LLM). Catches cardtpl,
               theme, and compiler changes.
  [taskspec]   Layer B - one record/replay per eval case (Qxxx) through the
               real service chain (WS envelope -> request -> capability
               registry -> preflight -> engine -> validation -> artifact),
               with recorded LLM responses injected as the transport.
               Catches retrieval/planner/prompt/validation drift. A changed
               prompt is reported as "replay missed" instead of silently
               comparing stale data.
  [scenario]   Layer C - composed-scenario snapshots registered inside the
               pytest files (deterministic builders, no LLM): layout+action
               compositions, parametrized geometry/palette variants, and
               stub-model pipeline renders that Layers A/B do not produce.
               Replaces inline deep assertions with reviewed snapshot diffs.

The loop: edit code -> `check` -> if the drift is EXPECTED, review
`check --diff` and promote it with `bless --declared <ids>`; if UNEXPECTED,
fix the code and re-check. A change is only done when `check` exits 0.
"""

_TOP_EPILOG = """\
report states (per layer, Jest-style):
  PASS    generated output equals the blessed golden.
  REVIEW  declared change awaiting `bless` (check still exits 0).
  STALE   prompt changed, so the recording cannot verify the run; the
          non-LLM output still matches. Re-record via bless --corpus-dir.
  FAIL    undeclared divergence - investigate the diff, then fix the code
          or bless the intended change.

exit codes:  0 = clean, or every divergence is declared;
             1 = undeclared drift, replay misses, or bless refused.

typical sessions (run from the cloud/ directory):
  # PR gate - is any generated UI different?
  python3 -m services.template_generation.test_support.golden_cli check

  # full inventory of every golden testcase (grouped, with documented skips):
  python3 -m services.template_generation.test_support.golden_cli report
  python3 -m services.template_generation.test_support.golden_cli report --health

  # push the pipeline_combo matrix onto the eval-device combo gallery:
  python3 -m services.template_generation.test_support.golden_cli combo-gallery

  # an intended single-template UI edit:
  python3 -m ...golden_cli check --diff --declared WeatherOverviewFull@1
  python3 -m ...golden_cli bless --declared WeatherOverviewFull@1

  # upstream merge / engine-wide change - review everything, then promote:
  python3 -m ...golden_cli check --declare-all --diff > review.txt
  python3 -m ...golden_cli bless --declare-all

  # prompts changed (replay missed) - re-record from the eval corpus
  # (makes ~2 real DeepSeek calls per case):
  python3 -m ...golden_cli bless --declared Q035,Q059 --corpus-dir \\
      ../genui_evaluation/entry/src/main/resources/rawfile/widget_batch_cases

  # new eval case: record it and the check covers it from then on
  python3 -m ...golden_taskspecs record --corpus-dir <widget_batch_cases> \\
      --cases Q089
  # retired case: delete tests/goldens/taskspecs/<case>/ by hand

One --declared list gates all layers: template ids (Xxx@1), case ids
(Qxxx), and scenario ids (<module>__<name>) never collide. The pytest CI
gates run the same comparisons (tests/test_template_goldens.py,
tests/test_taskspec_goldens.py, tests/test_scenario_goldens.py).
Per-layer CLIs: test_support.golden (Layer A run/accept/diff) and
test_support.golden_taskspecs (Layer B record/run/accept).
"""

_CHECK_DESCRIPTION = """\
Rebuild all golden layers from current code and compare with the blessed
set. This is the one-command test; it uses the same comparison logic as the
pytest golden gates and never calls the LLM (Layer B replays recordings,
so a changed prompt shows up as "replay missed" instead of a live call).
Exit 0 requires: no undeclared divergence and no replay-missed (stale) case.
"""

_CHECK_EPILOG = """\
examples:
  check                                   # plain PR gate
  check --diff                            # + unified diffs of every change
  check --diff --declared WeatherOverviewFull@1,Q035
                                          # mark intended changes; drift
                                          # becomes REVIEW, exit stays 0
  check --declare-all --diff > review.txt # engine-wide change: use the
                                          # output as the review checklist
"""

_BLESS_DESCRIPTION = """\
Promote reviewed divergence into the golden set (Layer A rewrites the
snapshot; Layer B re-blesses from replay, or re-records when the prompt
changed; Layer C rewrites the scenario snapshots). Refuses while ANY
undeclared drift exists in any layer, and re-checks after writing - review
`check --diff` first, then bless exactly what you reviewed. Replay misses
are only re-recorded when --corpus-dir is given; re-recording makes ~2
real DeepSeek calls per case and each record is replay-verified before it
is kept.
"""

_BLESS_EPILOG = """\
examples:
  bless --declared WeatherOverviewFull@1          # after reviewing one diff
  bless --declared Q035,Q059 --corpus-dir <widget_batch_cases>
                                                  # prompt changed: re-record
  bless --declare-all                             # engine-wide promotion
                                                  (bless BOTH layers)
"""


@dataclass(frozen=True)
class _LayerState:
    """一层的生成/固化文本与比对结论。"""

    title: str
    comparison: golden_layer.GoldenComparison
    generated: dict[str, golden_layer.TemplateGolden] = field(default_factory=dict)
    blessed: dict[str, str] = field(default_factory=dict)
    replay_missed: tuple[str, ...] = ()
    skipped: bool = False

    @property
    def has_undeclared(self) -> bool:
        return not self.skipped and self.comparison.has_undeclared_divergence

    @property
    def has_divergence(self) -> bool:
        return not self.skipped and (
            self.comparison.has_divergence or bool(self.replay_missed)
        )


def _split_ids(raw: str) -> frozenset[str]:
    return frozenset(item.strip() for item in raw.split(",") if item.strip())


def _template_layer(
    declared: frozenset[str], declare_all: bool
) -> _LayerState:
    generated = golden_layer.build_snapshots()
    blessed = golden_layer.load_blessed()
    comparison = golden_layer.compare(
        generated, blessed, declared=declared, declare_all=declare_all
    )
    return _LayerState(
        title="Template golden comparison:",
        comparison=comparison,
        generated=generated,
        blessed=blessed,
    )


def _taskspec_layer(
    declared: frozenset[str], declare_all: bool
) -> _LayerState:
    case_ids = golden_taskspecs.blessed_case_ids()
    if not case_ids:
        return _LayerState(
            title="Taskspec golden comparison:",
            comparison=golden_layer.compare({}, {}),
            skipped=True,
        )
    generated: dict[str, golden_layer.TemplateGolden] = {}
    blessed: dict[str, str] = {}
    missed: list[str] = []
    for case_id in case_ids:
        text, is_missed = asyncio.run(golden_taskspecs.replay_case_text(case_id))
        generated[case_id] = golden_layer.TemplateGolden(
            template_id=case_id, meta={}, text=text
        )
        blessed[case_id] = (
            golden_taskspecs.GOLDEN_ROOT / case_id / "golden.json"
        ).read_text(encoding="utf-8")
        if is_missed:
            missed.append(case_id)
    comparison = golden_layer.compare(
        generated, blessed, declared=declared, declare_all=declare_all
    )
    return _LayerState(
        title="Taskspec golden comparison:",
        comparison=comparison,
        generated=generated,
        blessed=blessed,
        replay_missed=tuple(missed),
    )


def _print_layer(layer: _LayerState, *, diff: bool) -> None:
    if layer.skipped:
        print(f"{layer.title}\n  skipped (no blessed cases).")
        return
    print(golden_layer.render_report(layer.comparison, title=layer.title))
    for case_id in layer.replay_missed:
        print(f"  replay missed: {case_id}")
        print(_RECORD_HINT.format(ids=case_id))
    if diff:
        for item_id in layer.comparison.changed_ids:
            text = golden_layer.render_diff(item_id, layer.generated, layer.blessed)
            if text:
                print(text)


def _scenario_layer(
    declared: frozenset[str], declare_all: bool
) -> _LayerState:
    generated = golden_scenarios.build_snapshots()
    if not generated:
        return _LayerState(
            title="Scenario golden comparison:",
            comparison=golden_layer.compare({}, {}),
            skipped=True,
        )
    blessed = golden_scenarios.load_blessed()
    comparison = golden_layer.compare(
        generated, blessed, declared=declared, declare_all=declare_all
    )
    return _LayerState(
        title="Scenario golden comparison:",
        comparison=comparison,
        generated=generated,
        blessed=blessed,
    )


def _check_layers(declared: frozenset[str], declare_all: bool) -> list[_LayerState]:
    layers = [_template_layer(declared, declare_all)]
    taskspec = _taskspec_layer(declared, declare_all)
    layers.append(taskspec)
    layers.append(_scenario_layer(declared, declare_all))
    return layers


def _cmd_check(args: argparse.Namespace) -> int:
    declared = _split_ids(args.declared)
    layers = _check_layers(declared, args.declare_all)
    if args.diff:
        for layer in layers:
            _print_layer(layer, diff=True)
    report = golden_layer.render_check_report(
        [
            golden_layer.CheckLayer(
                label="Templates",
                comparison=layers[0].comparison,
            ),
            golden_layer.CheckLayer(
                label="Taskspecs",
                comparison=layers[1].comparison,
                extra_failed=layers[1].replay_missed,
            ),
            golden_layer.CheckLayer(
                label="Scenarios",
                comparison=layers[2].comparison,
            ),
        ]
    )
    print(report.text)
    return 1 if (report.has_undeclared or report.has_stale) else 0


def _cmd_bless(args: argparse.Namespace) -> int:
    declared = _split_ids(args.declared)
    if not declared and not args.declare_all:
        print(
            "bless requires --declared <ids> (or --declare-all); "
            "review 'check --diff' output first.",
            file=sys.stderr,
        )
        return 1
    layers = _check_layers(declared, args.declare_all)
    blocked = [
        layer
        for layer in layers
        if layer.has_undeclared
        or (layer.replay_missed and args.corpus_dir is None)
    ]
    if blocked:
        print("bless refused: undeclared drift exists. Review with 'check --diff':")
        for layer in blocked:
            kind = layer.title.split()[0].lower()
            for item_id in layer.comparison.undeclared_changes:
                print(f"  {kind}: {item_id}")
            for item_id in layer.comparison.undeclared_additions:
                print(f"  {kind} added:    {item_id}")
            for item_id in layer.comparison.undeclared_removals:
                print(f"  {kind} removed:  {item_id}")
            for item_id in layer.replay_missed:
                print(f"  replay missed: {item_id}")
        return 1

    # Layer A：重写 declared 命中的模板；unchanged 重写内容不变；removed 由 prune 清理。
    template_layer = layers[0]
    golden_layer.bless(template_layer.generated)
    for item_id in sorted(
        set(template_layer.comparison.declared_changes)
        | set(template_layer.comparison.declared_additions)
    ):
        print(f"{item_id} OK (template golden blessed)")

    # Layer C：与 Layer A 同语义——按当前生成重写全部场景快照并 prune。
    scenario_layer = layers[2]
    if not scenario_layer.skipped:
        golden_scenarios.bless(scenario_layer.generated)
        for item_id in sorted(
            set(scenario_layer.comparison.declared_changes)
            | set(scenario_layer.comparison.declared_additions)
        ):
            print(f"{item_id} OK (scenario golden blessed)")

    # Layer B：declared 命中的用例从回放重新固化；未命中可带语料目录自动重录。
    if not layers[1].skipped:
        taskspec_layer = layers[1]
        replay_targets = sorted(
            set(taskspec_layer.comparison.declared_changes)
            | set(taskspec_layer.comparison.declared_additions)
        )
        accepted, _missed = golden_taskspecs.re_bless_cases(replay_targets)
        for case_id in accepted:
            print(f"{case_id} OK (taskspec golden re-blessed from replay)")
        record_targets = sorted(taskspec_layer.replay_missed)
        for case_id in record_targets:
            if args.corpus_dir is None:
                continue
            count, status, error = golden_taskspecs.record_case(
                Path(args.corpus_dir), case_id
            )
            if error is None:
                print(
                    f"{case_id} OK (re-recorded, status={status}, {count} llm call(s))"
                )
            else:
                print(f"{case_id} FAILED (re-record): {error}", file=sys.stderr)
        unhandled_misses = [
            case_id
            for case_id in taskspec_layer.replay_missed
            if args.corpus_dir is None
        ]
        if unhandled_misses:
            print(
                "Replay misses need re-recording; pass --corpus-dir:",
                file=sys.stderr,
            )
            print(_RECORD_HINT.format(ids=",".join(unhandled_misses)), file=sys.stderr)
            return 1

    layers_after = _check_layers(declared, args.declare_all)
    if any(layer.has_divergence for layer in layers_after):
        print("bless finished but divergence remains:")
        for layer in layers_after:
            _print_layer(layer, diff=False)
        return 1
    print("OK: golden set updated; check is green.")
    return 0


_REPORT_DESCRIPTION = """\
Full inventory of every golden testcase across all three layers, grouped the
way the workflow is organized (Layer A by size/layout, Layer B by final
status, Layer C by pipeline-stage hierarchy). Fast: reads blessed goldens and
registered builders, never re-renders. Use --health to also run the full
comparison and append the live per-layer verdict.
"""

_REPORT_EPILOG = """\
examples:
  report                # full inventory (a few seconds)
  report --health       # inventory + live per-layer PASS/FAIL verdict
  report --json         # machine-readable inventory
"""


def _report_layer_a() -> dict:
    manifest_path = golden_layer.MANIFEST_PATH
    if not manifest_path.is_file():
        return {"present": False}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    templates = manifest.get("templates", [])
    by_size = Counter(item.get("size", "?") for item in templates)
    by_layout = Counter(item.get("layoutKind", "?") for item in templates)
    grouped: dict[str, list[str]] = {}
    for item in sorted(templates, key=lambda entry: entry["templateId"]):
        grouped.setdefault(f'{item.get("size")}·{item.get("layoutKind")}', []).append(
            item["templateId"]
        )
    return {
        "present": True,
        "goldenVersion": manifest.get("goldenVersion"),
        "total": len(templates),
        "bySize": dict(sorted(by_size.items())),
        "byLayout": dict(sorted(by_layout.items())),
        "groups": grouped,
    }


def _report_layer_b() -> dict:
    statuses: dict[str, list[str]] = {}
    case_ids = golden_taskspecs.blessed_case_ids()
    for case_id in case_ids:
        golden = json.loads(
            (golden_taskspecs.GOLDEN_ROOT / case_id / "golden.json").read_text(
                encoding="utf-8"
            )
        )
        status = golden.get("status", "?")
        if status == "failed" and golden.get("errorCode"):
            status = f"failed:{golden['errorCode']}"
        statuses.setdefault(status, []).append(case_id)
    return {
        "total": len(case_ids),
        "byStatus": {key: sorted(values) for key, values in sorted(statuses.items())},
    }


def _report_layer_c() -> dict:
    registered = golden_scenarios.discover_scenarios()
    blessed = golden_scenarios.load_blessed()
    groups: dict[str, dict] = {}
    for scenario_id in sorted(registered):
        group = golden_scenarios.scenario_group(scenario_id)
        entry = groups.setdefault(group, {"scenarios": [], "combinationKeys": 0})
        entry["scenarios"].append(scenario_id)
        path = golden_scenarios.scenario_golden_path(scenario_id)
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            combinations = payload.get("combinations")
            if isinstance(combinations, dict):
                entry["combinationKeys"] += len(combinations)
            excluded = payload.get("excludedCombinations")
            if isinstance(excluded, dict):
                entry["excludedKeys"] = entry.get("excludedKeys", 0) + len(excluded)
    orphans = sorted(set(blessed) - set(registered))
    unblessed = sorted(set(registered) - set(blessed))
    skipped = []
    try:
        from services.template_generation.tests.test_template_pipeline_matrix import (
            _SKIPPED_TEMPLATES,
        )

        skipped = sorted(_SKIPPED_TEMPLATES)
    except Exception:
        skipped = []
    return {
        "total": len(registered),
        "groups": {name: groups[name] for name in sorted(groups)},
        "unblessed": unblessed,
        "orphanGoldens": orphans,
        "documentedSkips": skipped,
    }


def _render_coverage_table(
    entries: list[dict], summary: dict, show_all: bool
) -> list[str]:
    """Jest 覆盖率风格的对齐表格：每模板一行、最差在前、末行为全量汇总。"""

    def sort_key(entry: dict):
        opt = len(entry["optionalFields"])
        gaps = opt - len(entry["absenceTestedFields"])
        bucket = 2 if opt == 0 else (0 if gaps else 1)
        pct = entry["absencePct"] if entry["absencePct"] is not None else 0.0
        return (bucket, pct, entry["templateId"])

    optional_rows = [e for e in entries if e["optionalFields"]]
    gap_rows = [e for e in optional_rows if e["absencePct"] < 100]
    complete_rows = [e for e in optional_rows if e["absencePct"] >= 100]
    vacant_rows = [e for e in entries if not e["optionalFields"]]
    visible = (
        sorted(optional_rows, key=sort_key)
        if show_all
        else sorted(gap_rows, key=sort_key)
    )

    def note_for(entry: dict) -> str:
        if entry["templateId"] in summary["structuralSkips"]:
            return "structural: " + entry.get("skipReason", "")[:56]
        if entry["size"] == "2x4":
            return "2x4: Search rejects at entry (Layer A only)"
        gaps = len(entry["optionalFields"]) - len(entry["absenceTestedFields"])
        if gaps:
            untested = [
                name
                for name in entry["optionalFields"]
                if name not in entry["absenceTestedFields"]
            ]
            return f"untested fields: {', '.join(untested)}"
        return ""

    name_w = max(
        [len("Template")]
        + [len(e["templateId"]) for e in visible]
        + [len("All templates")]
    )
    name_w = min(name_w, 52)
    header = (
        f"{'Template':<{name_w}} | Size | Opt | %Absence | "
        f"{'Subsets':>9} | Props | Notes"
    )
    line = "-" * len(header)
    rows = [line, header, line]

    def fmt_row(name, size, opt, pct, rendered, refused, total, props_text, note):
        pct_text = f"{pct:>6.1f}%" if pct is not None else "     –"
        subsets_text = (
            f"{rendered}/{refused}/{total:>3}" if total else "  – /  – /  –"
        )
        return (
            f"{name:<{name_w}} | {size:<4} | {opt:>3} | {pct_text} | "
            f"{subsets_text:>9} | {props_text:>5} | {note}"
        )

    variant_ids = set()
    rows.append(
        fmt_row(
            "All templates",
            "—",
            summary["optionalFieldsTotal"],
            summary["absencePct"],
            sum(e.get("subsetsRendered", 0) for e in optional_rows),
            sum(e.get("subsetsRefused", 0) for e in optional_rows),
            sum(e.get("subsetsTotal", 0) for e in optional_rows),
            "—",
            f"{summary['exhaustiveSubsetTemplates']}/{summary['optionalFieldTemplates']}"
            " templates exhaustive",
        )
    )
    for entry in visible:
        props_count = len(entry["props"])
        variant = entry.get("propsVariantCovered", False)
        if variant:
            variant_ids.add(entry["templateId"])
        rows.append(
            fmt_row(
                entry["templateId"],
                entry["size"],
                len(entry["optionalFields"]),
                entry["absencePct"],
                entry.get("subsetsRendered", 0),
                entry.get("subsetsRefused", 0),
                entry.get("subsetsTotal", 0),
                f"{props_count}{' +var' if variant else ''}",
                note_for(entry),
            )
        )
    rows.append(line)
    if variant_ids:
        rows.append(
            "Props +var = explicit param-variant coverage: "
            + ", ".join(sorted(variant_ids))
        )
    if not show_all:
        hidden = len(complete_rows) + len(vacant_rows)
        rows.append(
            f"({hidden} templates fully covered or without optional fields — "
            "hidden; --coverage shows all)"
        )
    return rows


def _template_pipeline_outcomes(wire_id: str) -> dict:
    """pipeline_combo 金样 → 每组合的 PASS/REFUSED 结果行（数据驱动 HTML/CLI 共用）。

    覆盖 normal（常规渲染）与 fusion（融球模式）两个家族；行内 ``variant``
    字段取 "normal" | "fusion"。``present``/``fusionPresent`` 分别表示两份
    家族金样是否存在。
    """
    slug = wire_id.split("@")[0].lower()
    skip_reason = ""
    try:
        from services.template_generation.tests.test_template_pipeline_matrix import (
            _SKIPPED_TEMPLATES,
        )

        skip_reason = _SKIPPED_TEMPLATES.get(wire_id, "")
    except Exception:
        pass
    rows: list[dict] = []
    presents: dict[str, bool] = {}
    for variant, scenario_id in (
        ("normal", f"pipeline_combo__{slug}"),
        ("fusion", f"pipeline_combo_fusion__{slug}"),
    ):
        family_path = golden_scenarios.scenario_golden_path(scenario_id)
        presents[variant] = family_path.is_file()
        if not family_path.is_file():
            continue
        payload = json.loads(family_path.read_text(encoding="utf-8"))
        for source, outcome in (
            (payload.get("combinations", {}), "PASS"),
            (payload.get("excludedCombinations", {}), "REFUSED"),
        ):
            for key, value in source.items():
                reason = "" if outcome == "PASS" else str(value)
                rows.append(
                    {
                        "key": key,
                        "outcome": outcome,
                        "reason": reason,
                        "raw": value,
                        "variant": variant,
                    }
                )
    rows.sort(
        key=lambda row: (
            row["variant"],
            len(row["key"].split("__")[-1].split("+")),
            row["key"],
        )
    )
    return {
        "present": presents["normal"],
        "fusionPresent": presents["fusion"],
        "skipReason": skip_reason,
        "rows": rows,
    }


def _template_layer_b_matches(capability_id: str) -> list[dict]:
    """按候选能力匹配 Layer B 语料用例（含每用例提供的候选绑定数据）。"""
    matches = []
    for case_dir in sorted(golden_taskspecs.GOLDEN_ROOT.iterdir()):
        input_path = case_dir / "input.json"
        golden_path = case_dir / "golden.json"
        if not input_path.is_file() or not golden_path.is_file():
            continue
        input_text = input_path.read_text(encoding="utf-8")
        if capability_id and capability_id not in input_text:
            continue
        payload = json.loads(input_text)
        golden = json.loads(golden_path.read_text(encoding="utf-8"))
        arguments = payload.get("arguments", payload.get("content", {}))
        bindings = [
            {
                "capabilityId": binding.get("capabilityId", ""),
                "writeResultTo": binding.get("writeResultTo", ""),
                "outputFields": list(binding.get("candidateOutputFields", [])),
            }
            for binding in payload.get("candidateDataBindings", [])
        ]
        matches.append(
            {
                "case": case_dir.name,
                "status": golden.get("status", "?"),
                "errorCode": golden.get("errorCode", ""),
                "query": str(
                    arguments.get("userQuery", payload.get("userQuery", ""))
                ),
                "size": payload.get("size")
                or payload.get("content", {}).get("size", "?"),
                "bindings": bindings,
            }
        )
    return matches


def _template_reference_groups(base: str) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for path in sorted(golden_scenarios.SCENARIOS_DIR.rglob("*.json")):
        if path.parent.relative_to(golden_scenarios.SCENARIOS_DIR).as_posix().startswith(
            "1_pipeline/matrix/pipeline_combo"
        ):
            continue
        if base in path.read_text(encoding="utf-8"):
            group = golden_scenarios.scenario_group(path.stem)
            groups.setdefault(group, []).append(path.stem)
    return groups


_HTML_CSS = """
  :root { --ok:#16a34a; --warn:#d97706; --bad:#dc2626; --line:#d4d4d8; }
  * { box-sizing: border-box; }
  body { font: 14px/1.45 -apple-system, "Segoe UI", "PingFang SC", sans-serif;
         margin: 24px; color: #18181b; }
  h1 { font-size: 20px; } h2 { font-size: 16px; margin: 28px 0 8px; }
  .cards { display: flex; gap: 12px; flex-wrap: wrap; margin: 16px 0; }
  .card { border: 1px solid var(--line); border-radius: 8px; padding: 10px 16px; min-width: 130px; }
  .card .n { font-size: 24px; font-weight: 700; }
  .card .l { color: #71717a; font-size: 12px; }
  .bar { height: 8px; background: #e4e4e7; border-radius: 4px; overflow: hidden; margin-top: 6px; }
  .bar i { display: block; height: 100%; background: var(--ok); }
  .controls { margin: 12px 0; display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
  input[type=text], select { padding: 6px 10px; border: 1px solid var(--line); border-radius: 6px; }
  label { color: #3f3f46; }
  table { border-collapse: collapse; width: 100%; margin: 8px 0; }
  th, td { border: 1px solid var(--line); padding: 4px 8px; text-align: left; vertical-align: top; }
  th { background: #fafafa; position: sticky; top: 0; }
  tr[data-gap="1"] td { background: #fef2f2; }
  .pct { font-weight: 700; }
  .pct.full { color: var(--ok); } .pct.zero { color: var(--bad); }
  .badge { display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: 12px; font-weight: 600; }
  .pass { background: #dcfce7; color: var(--ok); }
  .refused, .fail { background: #fee2e2; color: var(--bad); }
  code { background: #f4f4f5; padding: 0 4px; border-radius: 4px; }
  details { border: 1px solid var(--line); border-radius: 8px; margin: 8px 0; }
  summary { cursor: pointer; padding: 8px 12px; font-weight: 600; }
  .body { padding: 4px 16px 12px; }
  h4 { margin: 14px 0 4px; font-size: 13px; color: #52525b; }
  ul.combos { list-style: none; padding-left: 0; columns: 2; }
  ul.combos li { padding: 1px 0; }
  .muted { color: #71717a; }
  .lb-controls { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin: 6px 0; }
  .lb-controls select, .lb-controls input { padding: 4px 8px; border: 1px solid var(--line); border-radius: 6px; }
"""

_HTML_JS = """
  function applyFilter() {
    var q = document.getElementById('q').value.toLowerCase();
    var size = document.getElementById('size').value;
    var layout = document.getElementById('layout').value;
    var gaps = document.getElementById('gaps').checked;
    var shown = 0;
    document.querySelectorAll('tr.tpl').forEach(function (row) {
      var ok = true;
      if (q && row.getAttribute('data-name').indexOf(q) === -1) ok = false;
      if (size !== 'all' && row.getAttribute('data-size') !== size) ok = false;
      if (layout !== 'all' && row.getAttribute('data-layout') !== layout) ok = false;
      if (gaps && row.getAttribute('data-gap') !== '1') ok = false;
      row.style.display = ok ? '' : 'none';
      if (ok) shown += 1;
      var det = document.getElementById('d-' + row.getAttribute('data-id'));
      if (det) det.style.display = ok ? '' : 'none';
    });
    document.getElementById('count').textContent = shown + ' / ' + rows_total + ' templates';
  }
  function lbApply(wrap) {
    var filters = Array.prototype.slice.call(wrap.querySelectorAll('.lb-filter'));
    var rows = wrap.querySelectorAll('table.lb tbody tr');
    var shown = 0;
    rows.forEach(function (row) {
      var ok = true;
      filters.forEach(function (f) {
        var dim = f.getAttribute('data-dim');
        var val = (f.value || '').toLowerCase();
        if (!val || val === 'all') return;
        var rowValue = (row.getAttribute('data-' + dim) || '').toLowerCase();
        if (dim === 'text') {
          ok = row.textContent.toLowerCase().indexOf(val) !== -1;
        } else if (rowValue.indexOf(val) === -1) {
          ok = false;
        }
      });
      row.style.display = ok ? '' : 'none';
      if (ok) shown += 1;
    });
    var count = wrap.querySelector('.lb-count');
    if (count) count.textContent = shown + ' / ' + rows.length + ' cases';
  }
  function filterLb(el) { lbApply(el.closest('.lb-wrap')); }
  var rows_total = document.querySelectorAll('tr.tpl').length;
  document.addEventListener('click', function (ev) {
    var link = ev.target.closest ? ev.target.closest('a[href^="#d-"]') : null;
    if (!link) return;
    var target = document.querySelector(link.getAttribute('href'));
    if (target) { target.open = true; }
  });
  document.addEventListener('DOMContentLoaded', function () {
    applyFilter();
    document.querySelectorAll('.lb-wrap').forEach(lbApply);
  });
"""


def _write_coverage_html(path: Path, coverage: dict, inventory: dict) -> None:
    """把全部模板的 data-field/props 覆盖与逐组合结果写成单个自包含 HTML 报告。"""
    import html as html_escape

    from services.template_generation.engine.cardplan.provider_bundle import (
        provider_template_layout_kind,
    )
    from services.template_generation.engine.cardplan.registry import CardPlanRegistry
    from services.template_generation.tests.test_template_pipeline_matrix import (
        _CONTEXT_FIELD_TYPES_BY_CAPABILITY,
        _SKIPPED_TEMPLATES,
        _data_roots,
        _sample_value,
    )

    esc = html_escape.escape
    registry = CardPlanRegistry(disabled_provider_ids=(), disabled_template_ids=())
    by_id = {entry["templateId"]: entry for entry in coverage["templates"]}
    summary = coverage["summary"]

    selected_by_case: dict[str, dict] = {}
    try:
        from services.template_generation.test_support.golden_taskspecs import (
            capture_selected_templates,
            blessed_case_ids,
        )

        print("HTML: replaying all Layer B cases to capture selected templates…")
        for case_id in blessed_case_ids():
            selected_by_case[case_id] = capture_selected_templates(case_id)
    except Exception as exc:
        print(f"HTML: selected-template capture skipped ({exc})")

    cards = "".join(
        f'<div class="card"><div class="n">{value}</div><div class="l">{label}</div></div>'
        for value, label in (
            (summary["totalTemplates"], "templates"),
            (f"{summary['absencePct']}%", "optional-field absence coverage"),
            (f"{summary['exhaustiveSubsetTemplates']}/{summary['optionalFieldTemplates']}", "templates with exhaustive 2^k subsets"),
            (f"{summary['absenceTestedFields']}/{summary['optionalFieldsTotal']}", "optional fields absence-tested"),
            (f"{summary['requiredFieldsTotal']}", "required fields (always covered)"),
            (len(summary["structuralSkips"]), "structural skips"),
        )
    )

    parts = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        "<title>Golden template coverage report</title>",
        f"<style>{_HTML_CSS}</style>",
        "</head><body>",
        "<h1>Golden template coverage report</h1>",
        f'<div class="muted">Layer A {inventory["layerA_templates"].get("total", 0)} · '
        f'Layer B {inventory["layerB_taskspecs"]["total"]} · '
        f'Layer C {inventory["layerC_scenarios"]["total"]} golden testcases — '
        "generated by golden_cli report --html</div>",
        f'<div class="cards">{cards}</div>',
        "<h2>Per-template coverage</h2>",
        '<div class="controls">',
        '<input type="text" id="q" placeholder="filter by template name…" oninput="applyFilter()">',
        '<select id="size" onchange="applyFilter()">'
        "<option value='all'>all sizes</option><option value='2x2'>2x2</option>"
        "<option value='2x4'>2x4</option></select>",
        '<select id="layout" onchange="applyFilter()">'
        "<option value='all'>all layouts</option>"
        + "".join(
            f"<option value='{esc(kind)}'>{esc(kind)}</option>"
            for kind in sorted({entry["layoutKind"] for entry in coverage["templates"]})
        )
        + "</select>",
        '<label><input type="checkbox" id="gaps" onchange="applyFilter()"> only templates with gaps</label>',
        '<span id="count" class="muted"></span>',
        "</div>",
        "<table><thead><tr><th>Template</th><th>Size</th><th>Layout</th><th>Req</th>"
        "<th>Opt</th><th>%Absence</th><th>Subsets (pass/refused/Σ)</th>"
        "<th>Props</th><th>Notes</th></tr></thead><tbody>",
    ]
    details = []
    for wire_id in sorted(by_id):
        entry = by_id[wire_id]
        definition = registry.require_template(wire_id)
        capability_id = definition.capability_id or ""
        optional = list(entry["optionalFields"])
        gaps = [f for f in optional if f not in entry["absenceTestedFields"]]
        pct = entry["absencePct"] if entry["absencePct"] is not None else 100.0
        pct_cls = "full" if pct >= 100 else ("zero" if pct == 0 else "")
        skip_reason = entry.get("skipReason", "") or _SKIPPED_TEMPLATES.get(wire_id, "")
        notes = skip_reason or (
            "untested: " + ", ".join(gaps) if gaps else ""
        )
        slug = wire_id.split("@")[0].lower()
        parts.append(
            f'<tr class="tpl" data-id="{esc(slug)}" data-name="{esc(wire_id.lower())}" '
            f'data-size="{entry["size"]}" data-layout="{esc(entry["layoutKind"])}" '
            f'data-gap="{1 if gaps or skip_reason else 0}">'
            f'<td><a href="#d-{esc(slug)}"><b>{esc(wire_id)}</b></a></td>'
            f'<td>{entry["size"]}</td><td>{esc(entry["layoutKind"])}</td>'
            f'<td>{len(entry["requiredFields"])}</td><td>{len(optional)}</td>'
            f'<td><span class="pct {pct_cls}">{pct}%</span></td>'
            f'<td>{entry.get("subsetsRendered", 0)}/{entry.get("subsetsRefused", 0)}/'
            f'{entry.get("subsetsTotal", 0)}</td>'
            f'<td>{len(entry["props"])}{" +var" if entry.get("propsVariantCovered") else ""}</td>'
            f'<td>{esc(notes)}</td></tr>'
        )

        outcomes = _template_pipeline_outcomes(wire_id)
        rows_html = []
        for row in outcomes.get("rows", []):
            cls = "pass" if row["outcome"] == "PASS" else "refused"
            reason = f" — {esc(row['reason'][:140])}" if row["reason"] else ""
            variant_note = (
                "" if row.get("variant", "normal") == "normal" else " ·融球"
            )
            rows_html.append(
                f'<li class="{cls}"><span class="badge {cls}">'
                f'{row["outcome"]}{variant_note}</span> '
                f"<code>{esc(row['key'])}</code>{reason}</li>"
            )
        if not outcomes["present"]:
            rows_html.append(
                f'<li class="refused"><span class="badge refused">NO FAMILY</span> '
                f"{esc(outcomes.get('skipReason', ''))}</li>"
            )
        elif not outcomes.get("fusionPresent", False):
            rows_html.append(
                '<li class="refused"><span class="badge refused">NO FUSION '
                "FAMILY</span> 融球模式家族金样缺失</li>"
            )
        layer_b = _template_layer_b_matches(capability_id)
        layer_b_rows = "".join(
            f'<tr data-size="{esc(item["size"])}" data-status="{esc(item["status"])}">'
            f'<td>{esc(item["case"])}</td><td>{esc(item["size"])}</td>'
            f'<td><span class="badge {"pass" if item["status"] == "success" else "fail"}">'
            f'{esc(item["status"])}</span></td>'
            f'<td>{esc(item["errorCode"])}</td><td>{esc(item["query"])}</td>'
            "<td>"
            + "<br>".join(
                f'{esc(b["capabilityId"])} → {esc(b["writeResultTo"])} '
                f'[{esc(", ".join(b["outputFields"]))}]'
                for b in item["bindings"]
            )
            + "</td></tr>"
            for item in layer_b
        )
        data_model = []
        for root_index, domain in enumerate(_data_roots(definition)):
            bound_paths = {
                binding.path
                for binding in definition.bindings.values()
                if binding.root_index == root_index
            }
            leaves = [
                f"{esc(binding.path)} ({binding.data_type}, "
                f"{esc(repr(_sample_value(capability_id, binding)))})"
                for binding in definition.bindings.values()
                if binding.root_index == root_index
            ]
            leaves += [
                f"{esc(path)} ({data_type}, context)"
                for path, data_type in _CONTEXT_FIELD_TYPES_BY_CAPABILITY.get(
                    capability_id, {}
                ).items()
                if root_index == 0 and path not in bound_paths
            ]
            data_model.append(f"<b>{esc(domain)}</b>: " + ", ".join(leaves))
        skip_note = (
            f'<p class="muted">Structural skip: {esc(skip_reason)}</p>'
            if skip_reason
            else ""
        )
        field_rows = "".join(
            f'<tr><td>required</td><td><code>{esc(path)}</code></td>'
            f'<td><span class="badge pass">always present</span></td></tr>'
            for path in entry["requiredFields"]
        ) + "".join(
            f'<tr><td>optional</td><td><code>{esc(path)}</code></td><td>'
            + (
                '<span class="badge pass">absence-tested</span>'
                if path in entry["absenceTestedFields"]
                else '<span class="badge fail">NOT tested</span>'
            )
            + "</td></tr>"
            for path in entry["optionalFields"]
        )
        details.append(
            f'<details id="d-{esc(slug)}"><summary>'
            f'<span class="pct {pct_cls}">{pct}%</span> <b>{esc(wire_id)}</b> · '
            f'{entry["size"]}·{esc(entry["layoutKind"])} — req {len(entry["requiredFields"])} / '
            f'opt {len(optional)} / props {len(entry["props"])}'
            f'{(" — " + esc(notes)) if notes else ""}</summary><div class="body">'
            f"{skip_note}<h4>Data fields</h4><table>{field_rows}</table>"
            "<h4>TaskSpec mock data model (pipeline matrix `all`)</h4><p>"
            + "</p><p>".join(data_model)
            + f"</p><h4>Pipeline matrix outcomes ({len(outcomes.get('rows', []))})</h4>"
            + ("<ul class='combos'>" + "".join(rows_html) + "</ul>"
               if rows_html else "<p class='muted'>no combinations</p>")
            + f"<h4>Layer B corpus cases (capability {esc(capability_id)}): "
            f"{len(layer_b)} matched, "
            f"{sum(1 for i in layer_b if i['status'] == 'success')} pass</h4>"
            + ((
                "<div class='lb-wrap'><div class='lb-controls'>"
                "<select class='lb-filter' data-dim='size' onchange='filterLb(this)'>"
                "<option value='all'>all sizes</option><option value='2x2'>asks 2x2</option>"
                "<option value='2x4'>asks 2x4</option></select>"
                "<select class='lb-filter' data-dim='status' onchange='filterLb(this)'>"
                "<option value='all'>all statuses</option><option value='success'>success</option>"
                "<option value='failed'>failed</option></select>"
                "<input class='lb-filter' data-dim='text' type='text' "
                "placeholder='filter case / error / query…' oninput='filterLb(this)'>"
                "<span class='lb-count muted'></span></div>"
                f"<table class='lb'><thead><tr><th>Case</th><th>TaskSpec size</th><th>Status</th>"
                f"<th>Error</th><th>Query</th><th>Provided data (candidate bindings)</th></tr></thead>"
                f"<tbody>{layer_b_rows}</tbody></table></div>"
            ) if layer_b_rows else "<p class='muted'>none</p>")
            + "</div></details>"
        )
    parts.append("</tbody></table>")

    ts = inventory["taskspecCoverage"]
    ts_summary = ts["summary"]
    cap_options = "".join(
        f"<option value='{esc(cap)}'>{esc(cap)}</option>"
        for cap in ts_summary["capabilitiesCovered"]
    )
    def selected_cell(case_id: str) -> str:
        info = selected_by_case.get(case_id)
        if info is None:
            return '<span class="muted">n/a</span>'
        if not info["selected"]:
            reason = info.get("errorCode") or "generation failed before selection"
            return f'<span class="badge refused">none</span> <span class="muted">{esc(reason)}</span>'
        business = [
            template_id
            for template_id in info["selected"]
            if not template_id.endswith(("Layout@1", "PillAction@1", "IconAction@1"))
        ]
        layouts = [
            template_id
            for template_id in info["selected"]
            if template_id.endswith("Layout@1")
        ]
        cell = "<br>".join(
            f'<a href="#d-{esc(template_id.split("@")[0].lower())}">'
            f"<b>{esc(template_id)}</b></a>"
            for template_id in business
        )
        if layouts:
            cell += (
                '<span class="muted"><br>'
                + "<br>".join(esc(template_id) for template_id in layouts)
                + "</span>"
            )
        return cell

    ts_rows = "".join(
        f'<tr data-size="{esc(row["size"])}" data-status="{esc(row["status"])}" '
        f'data-cap="{esc(", ".join(row["capabilities"])).lower()}" '
        f'data-case="{esc(row["case"]).lower()}">'
        f'<td>{esc(row["case"])}</td><td>{esc(row["size"])}</td>'
        f"<td>{selected_cell(row['case'])}</td>"
        f'<td><span class="badge {"pass" if row["status"] == "success" else "fail"}">'
        f'{esc(row["status"])}</span></td><td>{esc(row["errorCode"])}</td>'
        f'<td>{esc(", ".join(row["capabilities"]))}</td>'
        f'<td>{"<br>".join(esc(line) for line in row["dataLines"])}</td>'
        f'<td>{esc(row["query"])}</td></tr>'
        for row in ts["rows"]
    )
    parts.append("<h2>TaskSpec coverage (Layer B corpus)</h2>")
    parts.append(
        '<div class="muted">Every Layer B taskspec: requested size, selected '
        "templates, provided data fields (candidate bindings), and the frozen "
        f"generation outcome. Capabilities covered: "
        f"{len(ts_summary['capabilitiesCovered'])} / "
        f"{len(ts_summary['capabilitiesInRegistry'])} · distinct data fields: "
        f"{ts_summary['distinctDataFields']} · asks 2x4 taskspecs fail on this "
        "route by design.</div>"
    )
    parts.append(
        "<div class='lb-wrap'><div class='lb-controls'>"
        "<select class='lb-filter' data-dim='size' onchange='filterLb(this)'>"
        "<option value='all'>all sizes</option><option value='2x2'>2x2</option>"
        "<option value='2x4'>2x4</option></select>"
        "<select class='lb-filter' data-dim='status' onchange='filterLb(this)'>"
        "<option value='all'>all statuses</option><option value='success'>success</option>"
        "<option value='failed'>failed</option></select>"
        f"<select class='lb-filter' data-dim='cap' onchange='filterLb(this)'>"
        f"<option value='all'>all capabilities</option>{cap_options}</select>"
        "<input class='lb-filter' data-dim='text' type='text' "
        "placeholder='filter case / template / error / query…' oninput='filterLb(this)'>"
        "<span class='lb-count muted'></span></div>"
        "<table class='lb'><thead><tr><th>Case</th><th>Size</th>"
        "<th>Selected templates</th><th>Status</th>"
        "<th>Error</th><th>Capabilities</th><th>Provided data (candidate bindings)</th>"
        "<th>Query</th></tr></thead><tbody>"
    )
    parts.append(ts_rows)
    parts.append("</tbody></table></div>")

    parts.append("<h2>Template detail</h2>")
    parts.extend(details)
    parts.append(f"<script>{_HTML_JS}</script></body></html>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts), encoding="utf-8")


def _taskspec_coverage() -> dict:
    """Layer B 全量 taskspec 清单：每个用例请求的尺寸、数据字段与生成结果。"""
    registry_caps: set[str] = set()
    try:
        from services.template_generation.engine.cardplan.registry import CardPlanRegistry

        registry = CardPlanRegistry(disabled_provider_ids=(), disabled_template_ids=())
        for wire_id in registry.provider_template_ids:
            capability_id = registry.require_template(wire_id).capability_id
            if capability_id:
                registry_caps.add(capability_id)
    except Exception:
        registry_caps = set()

    rows = []
    distinct_fields: set[str] = set()
    for case_dir in sorted(golden_taskspecs.GOLDEN_ROOT.iterdir()):
        input_path = case_dir / "input.json"
        golden_path = case_dir / "golden.json"
        if not input_path.is_file() or not golden_path.is_file():
            continue
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        golden = json.loads(golden_path.read_text(encoding="utf-8"))
        capabilities: list[str] = []
        data_lines = []
        field_count = 0
        for binding in payload.get("candidateDataBindings", []):
            outputs = list(binding.get("candidateOutputFields", []))
            field_count += len(outputs)
            capability = binding.get("capabilityId", "")
            root = binding.get("writeResultTo", "")
            capabilities.append(capability)
            for field in outputs:
                distinct_fields.add(f"{capability}{root}{field}")
            data_lines.append(
                f"{capability} → {root} [{', '.join(outputs)}]"
            )
        rows.append(
            {
                "case": case_dir.name,
                "size": payload.get("size")
                or payload.get("content", {}).get("size", "?"),
                "status": golden.get("status", "?"),
                "errorCode": golden.get("errorCode", ""),
                "query": str(
                    payload.get("arguments", payload.get("content", {})).get(
                        "userQuery", payload.get("userQuery", "")
                    )
                ),
                "capabilities": sorted(set(capabilities)),
                "dataLines": data_lines,
                "fieldCount": field_count,
            }
        )
    capabilities_covered = sorted(
        {cap for row in rows for cap in row["capabilities"] if cap}
    )
    by_status = Counter(row["status"] for row in rows)
    by_size = Counter(row["size"] for row in rows)
    return {
        "rows": rows,
        "summary": {
            "total": len(rows),
            "bySize": dict(sorted(by_size.items())),
            "byStatus": dict(sorted(by_status.items())),
            "capabilitiesCovered": capabilities_covered,
            "capabilitiesInRegistry": sorted(registry_caps),
            "capabilitiesNotCovered": sorted(registry_caps - set(capabilities_covered)),
            "distinctDataFields": len(distinct_fields),
        },
    }


def _cmd_report(args) -> int:
    inventory = {
        "layerA_templates": _report_layer_a(),
        "layerB_taskspecs": _report_layer_b(),
        "layerC_scenarios": _report_layer_c(),
        "coverage": _report_coverage(),
        "taskspecCoverage": _taskspec_coverage(),
    }
    if args.json:
        if args.health:
            layer_states = _check_layers(frozenset(), False)
            inventory["health"] = [
                {
                    "layer": label,
                    "skipped": state.skipped,
                    "comparison": {
                        "unchanged": len(state.comparison.unchanged),
                        "declaredChanges": len(state.comparison.declared_changes),
                        "undeclaredChanges": len(state.comparison.undeclared_changes),
                        "undeclaredAdditions": len(state.comparison.undeclared_additions),
                        "undeclaredRemovals": len(state.comparison.undeclared_removals),
                    },
                    "replayMissed": list(state.replay_missed),
                }
                for state, label in zip(
                    layer_states, ("Templates", "Taskspecs", "Scenarios")
                )
            ]
        print(json.dumps(inventory, ensure_ascii=False, indent=2))
        return 0

    print("Golden testcase report")
    print("=" * 72)
    layer_a = inventory["layerA_templates"]
    if not layer_a.get("present"):
        print("Layer A · templates  : MISSING (run `golden accept` to bootstrap)")
    else:
        print(
            f"Layer A · templates  : {layer_a['total']} goldens "
            f"({layer_a['goldenVersion']})"
        )
        print(
            "    by size  : "
            + " · ".join(f"{size} {n}" for size, n in layer_a["bySize"].items())
        )
        print(
            "    by layout: "
            + " · ".join(f"{kind} {n}" for kind, n in layer_a["byLayout"].items())
        )
        for group, ids in layer_a["groups"].items():
            print(f"    [{group}] ({len(ids)}): {', '.join(ids)}")
    layer_b = inventory["layerB_taskspecs"]
    print(f"Layer B · taskspecs  : {layer_b['total']} cases (real chain, recorded LLM)")
    for status, ids in layer_b["byStatus"].items():
        print(f"    {status} ({len(ids)}): {', '.join(ids)}")
    layer_c = inventory["layerC_scenarios"]
    print(
        f"Layer C · scenarios  : {layer_c['total']} goldens in "
        f"{len(layer_c['groups'])} groups (pipeline-stage hierarchy, see "
        "goldens/scenarios/README.md)"
    )
    for group, entry in layer_c["groups"].items():
        extras = ""
        if entry["combinationKeys"]:
            extras += f" · {entry['combinationKeys']} combination keys"
        if entry.get("excludedKeys"):
            extras += f" · {entry['excludedKeys']} frozen refusals"
        print(f"  {group} — {len(entry['scenarios'])} scenarios{extras}")
        print(f"      {', '.join(entry['scenarios'])}")
    if layer_c["documentedSkips"]:
        print(
            "    documented pipeline skips: "
            + ", ".join(layer_c["documentedSkips"])
        )
    if layer_c["unblessed"]:
        print(
            "    UNBLESSED builders (register but no golden file): "
            + ", ".join(layer_c["unblessed"])
        )
    if layer_c["orphanGoldens"]:
        print(
            "    ORPHAN golden files (on disk, not registered): "
            + ", ".join(layer_c["orphanGoldens"])
        )
    coverage = inventory["coverage"]
    summary = coverage["summary"]
    taskspecs = inventory["taskspecCoverage"]
    ts_summary = taskspecs["summary"]
    if args.html:
        html_path = Path(args.html)
        print("Building HTML coverage report (includes a full Layer B replay)…")
        _write_coverage_html(html_path, coverage, inventory)
        print(
            f"HTML coverage report written: {html_path} "
            f"({html_path.resolve()}) — open it in a browser; it covers all "
            f"{summary['totalTemplates']} templates."
        )
    print("Coverage · template data fields / props (Jest-style: worst first)")
    for line in _render_coverage_table(
        coverage["templates"], summary, show_all=args.coverage
    ):
        print(line)
    variant_note = (
        f"{summary['propsVariantCoveredTemplates']} templates with explicit "
        "param-variant coverage"
    )
    print(
        f"Coverage · props: declared on {summary['propsTemplates']} templates — "
        "default render (Layer A) + optional-absent (pipeline) covered for all; "
        f"{variant_note}. Required data fields: {summary['requiredFieldsTotal']} "
        "(present in every pipeline render). 2x4: canonical only (Search rejects "
        "2x4 at pipeline entry)."
    )
    print(
        f"Coverage · taskspecs   : {ts_summary['total']} "
        f"({' · '.join(f'{size} {n}' for size, n in ts_summary['bySize'].items())}) — "
        + " · ".join(f"{status} {n}" for status, n in ts_summary["byStatus"].items())
    )
    print(
        f"    capabilities covered: {len(ts_summary['capabilitiesCovered'])}/"
        f"{len(ts_summary['capabilitiesInRegistry'])} — "
        f"{', '.join(ts_summary['capabilitiesCovered'])}"
        + (
            f" | not covered: {', '.join(ts_summary['capabilitiesNotCovered'])}"
            if ts_summary["capabilitiesNotCovered"]
            else ""
        )
    )
    print(f"    distinct data fields provided: {ts_summary['distinctDataFields']}")
    if args.coverage:
        print("  per-taskspec:")
        for row in taskspecs["rows"]:
            error = f" · {row['errorCode']}" if row["errorCode"] else ""
            print(
                f"    {row['case']} [{row['size']}] {row['status']}{error} — "
                f"{row['fieldCount']} data fields ({', '.join(row['capabilities'])})"
                f"  「{row['query'][:40]}」"
            )
    total = (
        layer_a.get("total", 0) if layer_a.get("present") else 0
    ) + layer_b["total"] + layer_c["total"]
    print("=" * 72)
    print(f"Total golden testcases: {total}")
    exit_code = 0
    if args.fail_under is not None:
        pct = summary["absencePct"]
        passed = pct >= args.fail_under
        print(
            f"Coverage threshold: absence {pct}% (fail-under {args.fail_under}%) — "
            + ("OK" if passed else "FAILED")
        )
        if not passed:
            exit_code = 1
    if args.health:
        layer_states = _check_layers(frozenset(), False)
        report = golden_layer.render_check_report(
            [
                golden_layer.CheckLayer(
                    label=label,
                    comparison=state.comparison,
                    extra_failed=state.replay_missed,
                )
                for state, label in zip(
                    layer_states, ("Templates", "Taskspecs", "Scenarios")
                )
                if not state.skipped
            ]
        )
        print(report.text)
        if report.has_undeclared or report.has_stale:
            exit_code = 1
    return exit_code


def _report_coverage() -> dict:
    """按模板计算数据字段/props 覆盖：声明（registry）× 金样（Layer A + pipeline 矩阵）。"""
    from services.template_generation.engine.cardplan.provider_bundle import (
        provider_template_layout_kind,
    )
    from services.template_generation.engine.cardplan.registry import CardPlanRegistry

    registry = CardPlanRegistry(disabled_provider_ids=(), disabled_template_ids=())
    layer_a_ids = set()
    manifest_path = golden_layer.MANIFEST_PATH
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        layer_a_ids = {
            item["templateId"] for item in manifest.get("templates", [])
        }
    skipped: dict[str, str] = {}
    try:
        from services.template_generation.tests.test_template_pipeline_matrix import (
            _SKIPPED_TEMPLATES,
        )

        skipped = dict(_SKIPPED_TEMPLATES)
    except Exception:
        skipped = {}

    variant_slugs: set[str] = set()
    for path in golden_scenarios.SCENARIOS_DIR.rglob("*.json"):
        stem = path.stem
        if stem.startswith(("calendar_geometry__",)):
            variant_slugs.add(stem.split("__", 1)[1].replace("_", ""))
        elif stem == "templgen__battery_compact__no_icon":
            variant_slugs.add("batteryoverviewcompact")

    entries: list[dict] = []
    for wire_id in sorted(registry.provider_template_ids):
        definition = registry.require_template(wire_id)
        if definition.capability_id is None:
            continue
        layout_kind = provider_template_layout_kind(wire_id)
        variant = definition.variants[0]
        optional = sorted(variant.optional_bindings)
        required = sorted(variant.required_bindings)
        props = sorted(variant.parameters_schema)
        size = "2x4" if layout_kind in ("WideFull", "WideHalf", "WideHero") else "2x2"
        entry: dict = {
            "templateId": wire_id,
            "size": size,
            "layoutKind": layout_kind,
            "requiredFields": required,
            "optionalFields": optional,
            "props": props,
            "layerACanonical": wire_id in layer_a_ids,
        }
        slug = wire_id.split("@")[0].lower()
        family_id = f"pipeline_combo__{slug}"
        family_path = golden_scenarios.scenario_golden_path(family_id)
        if wire_id in skipped:
            entry.update(
                pipelineCovered=False,
                skipReason=skipped[wire_id],
                absenceTestedFields=[],
                subsetsRendered=0,
                subsetsRefused=0,
            )
        elif family_path.is_file():
            payload = json.loads(family_path.read_text(encoding="utf-8"))
            keys = list(payload.get("combinations", {}))
            refused = list(payload.get("excludedCombinations", {}))
            absence_tested = [
                name
                for name in optional
                if any(
                    key == "none"
                    or (key.startswith("absent_") and name in key.split("+"))
                    or name in key
                    for key in keys + refused
                )
            ]
            entry.update(
                pipelineCovered=True,
                subsetsRendered=len(keys),
                subsetsRefused=len(refused),
                absenceTestedFields=absence_tested,
            )
        else:
            entry.update(
                pipelineCovered=False,
                absenceTestedFields=[],
                subsetsRendered=0,
                subsetsRefused=0,
                skipReason=(
                    "2x4：Search 在管线入口拒绝 2x4，仅 Layer A canonical 渲染"
                    if size == "2x4"
                    else "no pipeline_combo family (unexpected)"
                ),
            )
        entry["propsVariantCovered"] = bool(props) and any(
            slug.replace("_", "").endswith(variant_slug)
            for variant_slug in variant_slugs
        )
        subsets_total = 2 ** len(optional)
        tested = len(entry["absenceTestedFields"])
        entry["subsetsTotal"] = subsets_total
        entry["absencePct"] = (
            round(100.0 * tested / len(optional), 1) if optional else None
        )
        entries.append(entry)

    matrix_entries = [e for e in entries if e["size"] == "2x2"]
    optional_templates = [e for e in entries if e["optionalFields"]]
    absence_tested = [
        e for e in optional_templates
        if e["optionalFields"] and len(e["absenceTestedFields"]) == len(e["optionalFields"])
    ]
    not_tested = [
        {
            "templateId": e["templateId"],
            "fields": [f for f in e["optionalFields"] if f not in e["absenceTestedFields"]],
            "reason": e.get("skipReason", "no matrix family"),
        }
        for e in optional_templates
        if len(e["absenceTestedFields"]) < len(e["optionalFields"])
    ]
    props_declared = [e for e in entries if e["props"]]
    props_variant = [e for e in props_declared if e["propsVariantCovered"]]
    fields_total = sum(len(e["optionalFields"]) for e in optional_templates)
    fields_tested = sum(len(e["absenceTestedFields"]) for e in optional_templates)
    return {
        "templates": entries,
        "summary": {
            "totalTemplates": len(entries),
            "pipelineCovered": sum(
                1 for e in matrix_entries if e.get("pipelineCovered")
            ),
            "structuralSkips": sorted(skipped),
            "optionalFieldTemplates": len(optional_templates),
            "exhaustiveSubsetTemplates": len(absence_tested),
            "optionalFieldsTotal": fields_total,
            "absenceTestedFields": fields_tested,
            "absencePct": (
                round(100.0 * fields_tested / fields_total, 1) if fields_total else 100.0
            ),
            "templatesWithGaps": sorted(
                e["templateId"]
                for e in optional_templates
                if len(e["absenceTestedFields"]) < len(e["optionalFields"])
            ),
            "fieldsNotAbsenceTested": not_tested,
            "requiredFieldsTotal": sum(len(e["requiredFields"]) for e in entries),
            "propsTemplates": len(props_declared),
            "propsVariantCoveredTemplates": len(props_variant),
            "propsVariantCoveredIds": [e["templateId"] for e in props_variant],
            "wideCanonicalOnly": sorted(
                e["templateId"] for e in entries if e["size"] == "2x4"
            ),
        },
    }


_TEMPLATE_DESCRIPTION = """\
Per-template drill-down: every golden taskspec that maps to one template, with
its data fields and the pass/fail outcome of each generation. Combines the
pipeline matrix (TaskSpec data-field subsets through the real pipeline with a
stub LLM), the Layer A canonical render, Layer B corpus cases matched at
capability level, and any other scenario families referencing the template.
"""

_TEMPLATE_EPILOG = """\
examples:
  template WeatherOverviewFull@1         # full outcome view for one template
  template WeatherOverviewFull           # @N suffix is resolved automatically
"""


def _resolve_template_id(raw: str) -> str:
    from services.template_generation.engine.cardplan.registry import CardPlanRegistry

    registry = CardPlanRegistry(disabled_provider_ids=(), disabled_template_ids=())
    if raw in registry.provider_template_ids:
        return raw
    matches = sorted(
        wire_id
        for wire_id in registry.provider_template_ids
        if wire_id.split("@")[0] == raw or wire_id.startswith(raw)
    )
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ValueError(f"unknown template id: {raw!r}")
    raise ValueError(f"ambiguous template id {raw!r}: {', '.join(matches)}")


def _cmd_template(args) -> int:
    from services.template_generation.engine.cardplan.provider_bundle import (
        provider_template_layout_kind,
    )
    from services.template_generation.engine.cardplan.registry import CardPlanRegistry

    try:
        wire_id = _resolve_template_id(args.template_id)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    registry = CardPlanRegistry(disabled_provider_ids=(), disabled_template_ids=())
    definition = registry.require_template(wire_id)
    variant = definition.variants[0]
    layout_kind = provider_template_layout_kind(wire_id)
    optional_names = sorted(variant.optional_bindings)

    def absent_fields(key: str) -> list[str]:
        if key == "all":
            return []
        if key == "none":
            return list(optional_names)
        return key[len("absent_"):].split("+") if key.startswith("absent_") else []

    print(f"Template report: {wire_id}")
    print("=" * 72)
    print(
        f"  size {('2x4' if layout_kind in ('WideFull', 'WideHalf', 'WideHero') else '2x2')}"
        f" · layout {layout_kind} · capability {definition.capability_id}"
        f" · business {definition.business_id}"
    )
    required_paths = [definition.bindings[name].path for name in variant.required_bindings]
    optional_paths = [definition.bindings[name].path for name in optional_names]
    print(f"  required data fields ({len(required_paths)}): {', '.join(required_paths) or '—'}")
    print(f"  optional data fields ({len(optional_paths)}): {', '.join(optional_paths) or '—'}")
    prop_names = sorted((variant.parameters_schema.get("properties") or {}).keys())
    print(f"  props ({len(prop_names)}): {', '.join(prop_names) or '—'}")
    try:
        from services.template_generation.tests.test_template_pipeline_matrix import (
            _CONTEXT_FIELD_TYPES_BY_CAPABILITY,
            _data_roots,
            _sample_value,
        )

        capability_id = definition.capability_id or ""
        print("  TaskSpec mock data model (pipeline matrix `all` combination):")
        for root_index, domain in enumerate(_data_roots(definition)):
            bound_paths = {
                binding.path
                for name, binding in definition.bindings.items()
                if binding.root_index == root_index
            }
            leaves = []
            for name, binding in definition.bindings.items():
                if binding.root_index != root_index:
                    continue
                sample = _sample_value(capability_id, binding)
                leaves.append(f"{binding.path} ({binding.data_type}, {sample!r})")
            for path, data_type in _CONTEXT_FIELD_TYPES_BY_CAPABILITY.get(
                capability_id, {}
            ).items():
                if root_index == 0 and path not in bound_paths:
                    leaves.append(f"{path} ({data_type}, context)")
            print(f"    {domain}:")
            for leaf in leaves:
                print(f"      {leaf}")
    except Exception:
        pass

    print("-" * 72)
    layer_a_path = golden_layer.TEMPLATES_DIR / f"{wire_id}.json"
    print(
        f"Layer A · canonical render (all fields): "
        + ("PASS (blessed)" if layer_a_path.is_file() else "MISSING")
    )

    print("-" * 72)
    slug = wire_id.split("@")[0].lower()

    def natural_key(key: str) -> tuple[int, str]:
        absent = absent_fields(key)
        return (len(absent), key)

    pipeline_pass = pipeline_refused = pipeline_total = 0
    for variant_label, family_id in (
        ("常规渲染", f"pipeline_combo__{slug}"),
        ("融球模式", f"pipeline_combo_fusion__{slug}"),
    ):
        family_path = golden_scenarios.scenario_golden_path(family_id)
        if not family_path.is_file():
            if variant_label == "常规渲染":
                skip_note = ""
                try:
                    from services.template_generation.tests.test_template_pipeline_matrix import (
                        _SKIPPED_TEMPLATES,
                    )

                    skip_note = (
                        f" — {_SKIPPED_TEMPLATES[wire_id]}"
                        if wire_id in _SKIPPED_TEMPLATES
                        else ""
                    )
                except Exception:
                    pass
                print(f"Pipeline matrix: NO FAMILY{skip_note}")
            else:
                print("Pipeline matrix (融球模式): NO FAMILY")
            continue
        payload = json.loads(family_path.read_text(encoding="utf-8"))
        combinations = payload.get("combinations", {})
        excluded = payload.get("excludedCombinations", {})
        variant_pass, variant_refused = len(combinations), len(excluded)
        variant_total = variant_pass + variant_refused
        pipeline_pass += variant_pass
        pipeline_refused += variant_refused
        pipeline_total += variant_total
        print(
            f"Pipeline matrix · {variant_label} (TaskSpec asks "
            f"{payload.get('size', '2x2')} — data-field subsets, stub LLM, "
            f"real pipeline): {variant_total} combinations"
        )
        for key in sorted(combinations, key=natural_key):
            absent = absent_fields(key)
            detail = "all fields present" if not absent else f"absent: {', '.join(absent)}"
            print(f"  PASS    {key:<28} {detail}")
        for key in sorted(excluded, key=natural_key):
            absent = absent_fields(key)
            detail = "all fields absent" if not absent else f"absent: {', '.join(absent)}"
            reason = str(excluded[key])
            reason = reason[: args.error_width] + "…" if len(reason) > args.error_width else reason
            print(f"  REFUSED {key:<28} {detail}")
            print(f"          └ {reason}")
        print(
            f"  → {variant_pass} pass · {variant_refused} refused · "
            f"{variant_total - variant_pass - variant_refused} untested"
        )

    print("-" * 72)
    capability = definition.capability_id or ""
    matched: list[dict] = []
    for case_dir in sorted(golden_taskspecs.GOLDEN_ROOT.iterdir()):
        input_path = case_dir / "input.json"
        golden_path = case_dir / "golden.json"
        if not input_path.is_file() or not golden_path.is_file():
            continue
        input_text = input_path.read_text(encoding="utf-8")
        if capability not in input_text:
            continue
        golden = json.loads(golden_path.read_text(encoding="utf-8"))
        payload = json.loads(input_text)
        arguments = payload.get("arguments", payload.get("content", {}))
        query = str(arguments.get("userQuery", payload.get("userQuery", "")))[:36]
        data_lines = []
        for binding in payload.get("candidateDataBindings", []):
            outputs = list(binding.get("candidateOutputFields", []))
            shown = outputs if args.data else outputs[:6]
            data_lines.append(
                f"{binding.get('capabilityId')} → {binding.get('writeResultTo')} "
                f"[{', '.join(shown)}{'…' if len(shown) < len(outputs) else ''}]"
            )
        matched.append(
            {
                "case": case_dir.name,
                "status": golden.get("status", "?"),
                "errorCode": golden.get("errorCode", ""),
                "query": query,
                "size": payload.get("size")
                or payload.get("content", {}).get("size", "?"),
                "dataLines": data_lines,
            }
        )
    passed = sum(1 for item in matched if item["status"] == "success")
    print(
        f"Layer B · corpus cases with candidate capability {capability}: "
        f"{len(matched)} (pass {passed} / fail {len(matched) - passed}) — "
        "capability-level match: exact template selection depends on each "
        "case's data"
    )
    for size in ("2x2", "2x4"):
        items = [item for item in matched if item["size"] == size]
        if items:
            size_pass = sum(1 for item in items if item["status"] == "success")
            print(
                f"    asks {size}: {len(items)} cases, pass {size_pass} / "
                f"fail {len(items) - size_pass}"
            )
    for item in matched:
        mark = "PASS" if item["status"] == "success" else "FAIL"
        error = f" · {item['errorCode']}" if item["errorCode"] else ""
        print(
            f"  {mark:<8}{item['case']:<7}[{item['size']}] "
            f"{item['status']}{error}  「{item['query']}」"
        )
        for line in item["dataLines"][: (None if args.data else 1)]:
            print(f"      data: {line}")
        hidden = len(item["dataLines"]) - (1 if item["dataLines"] else 0)
        if hidden > 0 and not args.data:
            print(f"      (+{hidden} more binding(s) — --data shows all)")

    print("-" * 72)
    base = wire_id.split("@")[0]
    referencing: dict[str, list[str]] = {}
    for path in sorted(golden_scenarios.SCENARIOS_DIR.rglob("*.json")):
        if path.parent.relative_to(golden_scenarios.SCENARIOS_DIR).as_posix().startswith(
            "1_pipeline/matrix/pipeline_combo"
        ):
            continue
        text = path.read_text(encoding="utf-8")
        if base in text:
            group = golden_scenarios.scenario_group(path.stem)
            referencing.setdefault(group, []).append(path.stem)
    total_refs = sum(len(ids) for ids in referencing.values())
    print(f"Other scenario families referencing this template: {total_refs}")
    for group, ids in sorted(referencing.items()):
        print(f"  {group} ({len(ids)}): {', '.join(ids)}")

    print("=" * 72)
    print(
        f"Verdict: pipeline {pipeline_pass}/{pipeline_total} pass "
        f"({pipeline_refused} refusals frozen by design) · Layer B {passed}/"
        f"{len(matched)} pass · Layer A "
        + ("PASS" if layer_a_path.is_file() else "MISSING")
    )
    return 0


_TASKSPEC_DESCRIPTION = """\
TaskSpec coverage report and per-case drill-down for Layer B corpus cases.

Without arguments: replays every recorded case (offline, no LLM), maps each
taskspec to the templates the engine actually selected, and prints the
coverage report. With a case id: prints the full drill-down for that one
taskspec — provided data bindings, generation outcome, selected templates,
and which pipeline-matrix combination each selection corresponds to.
"""

_TASKSPEC_EPILOG = """\
examples:
  taskspec                # coverage report for all 88 cases (replays each; ~1 min)
  taskspec Q035           # drill-down: one taskspec → selected templates → outcomes
  taskspec Q051 --error-width 400
"""

_COMBO_GALLERY_DESCRIPTION = """\
Export the pipeline_combo matrix goldens (Layer C scenario families) as the
on-device combo gallery dataset for ProviderScenarioGalleryPage (enter it
with dataset=pipelineCombo). Family goldens are copied verbatim into
<dataset-dir>/families/ and every combination becomes a tile: rendered
combos draw their real A2UI card, refused combos and structurally skipped
templates show their reason. The eval app (genui_evaluation) is a separate
repository from CreateMyCard, so the dataset directory must be given
explicitly as an absolute path.
"""

_COMBO_GALLERY_EPILOG = """\
examples:
  combo-gallery --dataset-dir /abs/path/genui_evaluation/entry/src/main/resources/rawfile/pipeline_combo_gallery
  combo-gallery --dataset-dir /tmp/dryrun/pipeline_combo_gallery   # dry run
"""


def _cmd_combo_gallery(args) -> int:
    from services.template_generation.test_support import combo_gallery

    try:
        result = combo_gallery.export_combo_gallery(Path(args.dataset_dir))
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    manifest = result["manifest"]
    counts = manifest["counts"]
    print(f"Combo gallery exported: {result['galleryDir']}")
    for provider in manifest["providers"]:
        by_status = Counter(case["status"] for case in provider["cases"])
        detail = " · ".join(
            f"{name} {by_status[name]}"
            for name in ("success", "refused", "skipped")
            if by_status.get(name)
        )
        print(
            f"  {provider['providerName']:<6} {provider['providerId']:<32} "
            f"{len(provider['cases']):>3} cases ({detail})"
        )
    print(
        f"total: {counts['families']} families · {counts['cases']} cases · "
        f"{counts['rendered']} rendered · "
        f"{counts['refused']} refused · {counts['skipped']} skipped"
    )
    for name, stats in counts.get("byVariant", {}).items():
        print(
            f"  variant {name}: {stats['families']} families · "
            f"{stats['rendered']} rendered · {stats['refused']} refused · "
            f"{stats['skipped']} skipped"
        )
    print(f"manifest: {result['manifestPath']}")
    return 0


def _taskspec_rows_with_selection() -> tuple[list[dict], list[str]]:
    from services.template_generation.test_support.golden_taskspecs import (
        capture_selected_templates,
    )

    rows = []
    selected_union: set[str] = set()
    for index, case_id in enumerate(golden_taskspecs.blessed_case_ids(), start=1):
        info = capture_selected_templates(case_id)
        payload = json.loads(
            (golden_taskspecs.GOLDEN_ROOT / case_id / "input.json").read_text(
                encoding="utf-8"
            )
        )
        size = payload.get("size") or payload.get("content", {}).get("size", "?")
        business = sorted(
            template_id
            for template_id in info["selected"]
            if not template_id.endswith(
                ("Layout@1", "PillAction@1", "IconAction@1")
            )
        )
        selected_union.update(business)
        data_lines = []
        field_count = 0
        for binding in payload.get("candidateDataBindings", []):
            outputs = list(binding.get("candidateOutputFields", []))
            field_count += len(outputs)
            data_lines.append(
                f"{binding.get('capabilityId')} → {binding.get('writeResultTo')} "
                f"[{', '.join(outputs)}]"
            )
        rows.append(
            {
                "case": case_id,
                "size": size,
                "status": info["status"],
                "errorCode": info["errorCode"],
                "business": business,
                "layouts": [
                    template_id
                    for template_id in info["selected"]
                    if template_id.endswith("Layout@1")
                ],
                "dataLines": data_lines,
                "fieldCount": field_count,
                "replayMissed": info["replayMissed"],
                "progress": f"{index}/{len(golden_taskspecs.blessed_case_ids())}",
            }
        )
    return rows, sorted(selected_union)


def _cmd_taskspec(args) -> int:
    from services.template_generation.engine.cardplan.provider_bundle import (
        provider_template_layout_kind,
    )
    from services.template_generation.engine.cardplan.registry import CardPlanRegistry
    from services.template_generation.test_support import golden_scenarios
    from services.template_generation.test_support.golden_taskspecs import (
        capture_selected_templates,
    )

    if not args.case_id:
        print("Replaying all Layer B cases to capture selected templates…")
        rows, selected_union = _taskspec_rows_with_selection()
        registry = CardPlanRegistry(disabled_provider_ids=(), disabled_template_ids=())
        business_templates = sorted(
            wire_id
            for wire_id in registry.provider_template_ids
            if not wire_id.endswith(("Layout@1", "PillAction@1", "IconAction@1"))
        )
        not_exercised = sorted(set(business_templates) - set(selected_union))
        print(
            f"TaskSpec coverage report — {len(rows)} cases\n"
            f"  selected-template coverage: {len(selected_union)}/{len(business_templates)} "
            "business templates exercised by Layer B\n"
            f"  not exercised: {', '.join(not_exercised) or '—'}\n"
        )
        for row in rows:
            mark = "PASS" if row["status"] == "success" else "FAIL"
            error = f" · {row['errorCode']}" if row["errorCode"] else ""
            business = ", ".join(row["business"]) or "(no business template — generation failed)"
            print(
                f"  {mark:<6}{row['case']:<7}[{row['size']}] {business}  "
                f"{row['fieldCount']} data fields{error}"
                + ("  REPLAY MISS" if row["replayMissed"] else "")
            )
        return 0

    case_id = args.case_id.strip().upper()
    input_path = golden_taskspecs.GOLDEN_ROOT / case_id / "input.json"
    golden_path = golden_taskspecs.GOLDEN_ROOT / case_id / "golden.json"
    if not input_path.is_file() or not golden_path.is_file():
        print(f"error: unknown taskspec case: {case_id!r}", file=sys.stderr)
        return 1
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    info = capture_selected_templates(case_id)

    print(f"TaskSpec report: {case_id}")
    print("=" * 72)
    print(
        f"  requested size {payload.get('size', '?')} · status "
        f"{golden.get('status', '?')}"
        + (f" · error {golden.get('errorCode', '')}" if golden.get("errorCode") else "")
        + (" · REPLAY MISS" if info["replayMissed"] else "")
    )
    print(f"  userQuery: {payload.get('userQuery', '')}")
    print("  provided data (candidate bindings):")
    for binding in payload.get("candidateDataBindings", []):
        outputs = list(binding.get("candidateOutputFields", []))
        print(
            f"    {binding.get('capabilityId')} → {binding.get('writeResultTo')} "
            f"[{len(outputs)} fields: {', '.join(outputs)}]"
        )
    events = payload.get("candidateEventCandidates", [])
    print(
        f"  candidate events: {len(events)} · candidate assets: "
        f"{len(payload.get('candidateAssetIds', []))}"
    )

    print("-" * 72)
    print(f"Selected templates ({len(info['selected'])}):")
    registry = CardPlanRegistry(disabled_provider_ids=(), disabled_template_ids=())
    provided: set[tuple[str, str]] = set()
    for binding in payload.get("candidateDataBindings", []):
        for field in binding.get("candidateOutputFields", []):
            provided.add((binding.get("capabilityId", ""), binding.get("writeResultTo", ""), field))
    for template_id in info["selected"]:
        kind_note = ""
        subset_note = ""
        if not template_id.endswith(("Layout@1", "PillAction@1", "IconAction@1")):
            definition = registry.require_template(template_id)
            kind = provider_template_layout_kind(template_id)
            roots = _data_roots_safe(definition)
            absent = []
            for name in definition.variants[0].optional_bindings:
                binding = definition.bindings[name]
                root = roots[binding.root_index] if binding.root_index < len(roots) else ""
                if (definition.capability_id or "", root, binding.path) not in provided:
                    absent.append(name)
            key = (
                "all" if not absent
                else "none" if len(absent) == len(definition.variants[0].optional_bindings)
                else "absent_" + "+".join(sorted(absent))
            )
            family_path = golden_scenarios.scenario_golden_path(
                f"pipeline_combo__{template_id.split('@')[0].lower()}"
            )
            if family_path.is_file():
                family = json.loads(family_path.read_text(encoding="utf-8"))
                if key in family.get("combinations", {}):
                    subset_note = f"pipeline golden: PASS ({key})"
                elif key in family.get("excludedCombinations", {}):
                    subset_note = f"pipeline golden: REFUSED ({key})"
                else:
                    subset_note = f"pipeline golden: combination {key} not frozen"
            else:
                subset_note = "no pipeline_combo family"
            kind_note = f" [{kind}]"
        print(f"  - {template_id}{kind_note}")
        if subset_note:
            print(f"      {subset_note}")
    print("=" * 72)
    print(
        "Tip: `golden_cli template <selected template id>` shows that template's "
        "full data-field/props coverage."
    )
    return 0


def _data_roots_safe(definition):
    try:
        from services.template_generation.tests.test_template_pipeline_matrix import (
            _data_roots,
        )

        return _data_roots(definition)
    except Exception:
        domain = (definition.data_domain or "/data").rstrip("/")
        return (domain,)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m services.template_generation.test_support.golden_cli",
        description=_TOP_DESCRIPTION,
        epilog=_TOP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check_parser = sub.add_parser(
        "check",
        help="compare both golden layers against current generation (the one-command test)",
        description=_CHECK_DESCRIPTION,
        epilog=_CHECK_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    check_parser.add_argument(
        "--declared",
        default="",
        metavar="ID,…",
        help="comma-separated template ids (Xxx@1) and/or case ids (Qxxx) whose "
        "UI change is expected; they become REVIEW instead of FAIL",
    )
    check_parser.add_argument(
        "--declare-all",
        action="store_true",
        help="treat every divergence as declared (engine-wide change review)",
    )
    check_parser.add_argument(
        "--diff",
        action="store_true",
        help="print unified diffs for every changed item (review before blessing)",
    )

    bless_parser = sub.add_parser(
        "bless", help="promote reviewed (declared) divergence into the golden set",
        description=_BLESS_DESCRIPTION,
        epilog=_BLESS_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    bless_parser.add_argument(
        "--declared",
        default="",
        metavar="ID,…",
        help="comma-separated template ids (Xxx@1) and/or case ids (Qxxx) being "
        "promoted; must cover every divergence or bless refuses",
    )
    bless_parser.add_argument(
        "--declare-all",
        action="store_true",
        help="promote every divergence in BOTH layers (engine-wide change review)",
    )
    bless_parser.add_argument(
        "--corpus-dir",
        default=None,
        metavar="DIR",
        help="widget_batch_cases corpus dir (genui_evaluation/entry/src/main/"
        "resources/rawfile/widget_batch_cases); enables re-recording "
        "replay-missed taskspec cases with real LLM calls",
    )

    report_parser = sub.add_parser(
        "report",
        help="full inventory report of every golden testcase across all layers",
        description=_REPORT_DESCRIPTION,
        epilog=_REPORT_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    report_parser.add_argument(
        "--health",
        action="store_true",
        help="also run the full comparison and append the live per-layer verdict "
        "(adds ~1 minute; without it the report is a fast pure inventory)",
    )
    report_parser.add_argument(
        "--coverage",
        action="store_true",
        help="show ALL template rows in the coverage table (default: only "
        "templates with coverage gaps)",
    )
    report_parser.add_argument(
        "--html",
        nargs="?",
        const="coverage/index.html",
        default=None,
        metavar="PATH",
        help="write a self-contained browsable HTML coverage report covering "
        "every template (default path: coverage/index.html)",
    )
    report_parser.add_argument(
        "--fail-under",
        default=None,
        type=float,
        metavar="PCT",
        help="exit 1 when optional-data-field absence coverage falls below PCT "
        "percent (coverage gate, Jest-style)",
    )
    report_parser.add_argument(
        "--json",
        action="store_true",
        help="print the inventory as JSON instead of text",
    )

    template_parser = sub.add_parser(
        "template",
        help="per-template drill-down: every taskspec mapping to one template with its pass/fail outcome",
        description=_TEMPLATE_DESCRIPTION,
        epilog=_TEMPLATE_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    template_parser.add_argument(
        "template_id",
        metavar="TEMPLATE_ID",
        help="template id (Xxx@1); the @N suffix may be omitted when unambiguous",
    )
    template_parser.add_argument(
        "--error-width",
        default=160,
        type=int,
        metavar="CHARS",
        help="truncate refusal/error text to this many characters (default 160)",
    )
    template_parser.add_argument(
        "--data",
        action="store_true",
        help="show every candidate binding's full output-field list for Layer B cases",
    )

    taskspec_parser = sub.add_parser(
        "taskspec",
        help="TaskSpec coverage report and per-case drill-down (with selected templates)",
        description=_TASKSPEC_DESCRIPTION,
        epilog=_TASKSPEC_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    taskspec_parser.add_argument(
        "case_id",
        nargs="?",
        default="",
        metavar="CASE_ID",
        help="Qxxx case id for the per-case drill-down; omit for the full "
        "taskspec coverage report (replays all cases)",
    )
    taskspec_parser.add_argument(
        "--error-width",
        default=160,
        type=int,
        metavar="CHARS",
        help="truncate refusal/error text to this many characters (default 160)",
    )

    combo_gallery_parser = sub.add_parser(
        "combo-gallery",
        help="export the pipeline_combo matrix goldens as the on-device combo gallery dataset",
        description=_COMBO_GALLERY_DESCRIPTION,
        epilog=_COMBO_GALLERY_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    combo_gallery_parser.add_argument(
        "--dataset-dir",
        required=True,
        metavar="PATH",
        help="absolute path to the eval app's gallery dataset directory "
        "(<rawfile>/pipeline_combo_gallery); genui_evaluation is a separate "
        "repository from CreateMyCard, so no default is assumed",
    )

    args = parser.parse_args(argv)
    if args.command == "check":
        return _cmd_check(args)
    if args.command == "report":
        return _cmd_report(args)
    if args.command == "template":
        return _cmd_template(args)
    if args.command == "taskspec":
        return _cmd_taskspec(args)
    if args.command == "combo-gallery":
        return _cmd_combo_gallery(args)
    return _cmd_bless(args)


if __name__ == "__main__":
    sys.exit(main())
