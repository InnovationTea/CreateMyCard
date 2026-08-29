# -*- coding: utf-8 -*-
"""场景金样（Layer C）工具：把测试文件中的确定性渲染场景固化为可复核快照。

一个场景 = 测试模块里注册的确定性构建函数（固定输入 + 真实引擎调用，
不经过 LLM），产出 canonical JSON 快照。用于把「内联深断言」迁移到
record/bless 工作流：引擎改动后差异以 diff 呈现，复核后 bless 固化；
组合了布局+动作+融合球的产物是 Layer A（模板孤立预览）与 Layer B
（录制语料链路）都不覆盖的盲区。

用法（在 cloud/ 目录下）::

    python3 -m services.template_generation.test_support.golden_cli check
    python3 -m services.template_generation.test_support.golden_cli bless \\
        --declared <场景ID>            # 场景 ID 形如 <模块>__<场景名>

测试侧：构建函数用 ``@scenario("<id>")`` 注册；测试函数调用
``assert_golden_scenario("<id>")`` 断言与金样一致（缺失即未引导，漂移即
带 diff 失败并提示申报/固化）。
"""

from __future__ import annotations

import difflib
import importlib
import json
import pkgutil
from pathlib import Path
from typing import Any, Callable

from services.template_generation.test_support.golden import (
    TemplateGolden,
    canonicalize,
    compare,
)

TESTS_PACKAGE = "services.template_generation.tests"
GOLDEN_DIR = Path(__file__).resolve().parents[1] / "tests" / "goldens"
SCENARIOS_DIR = GOLDEN_DIR / "scenarios"

_DIFF_LINE_CAP = 200

_REGISTRY: dict[str, Callable[[], Any]] = {}


def scenario(scenario_id: str) -> Callable[[Callable[[], Any]], Callable[[], Any]]:
    """注册确定性场景构建函数；跨文件的 ID 冲突视为编码错误。

    pytest 顶层导入与包内点号导入会把同一测试模块加载成两个模块对象，
    同源构建函数的重复注册按幂等处理（以先注册者为准）。
    """

    def register(fn: Callable[[], Any]) -> Callable[[], Any]:
        existing = _REGISTRY.get(scenario_id)
        if existing is not None:
            existing_code = getattr(existing, "__code__", None)
            same_source = (
                existing_code is not None
                and existing_code.co_filename == fn.__code__.co_filename
                and existing_code.co_firstlineno == fn.__code__.co_firstlineno
            )
            if not same_source:
                raise ValueError(f"duplicate golden scenario id: {scenario_id}")
            return fn
        _REGISTRY[scenario_id] = fn
        return fn

    return register


def discover_scenarios() -> dict[str, Callable[[], Any]]:
    """导入 tests 包的全部 test_*.py 模块，收集已注册场景（幂等）。"""
    package = importlib.import_module(TESTS_PACKAGE)
    for module_info in pkgutil.iter_modules(package.__path__):
        if not module_info.name.startswith("test_"):
            continue
        importlib.import_module(f"{TESTS_PACKAGE}.{module_info.name}")
    return dict(sorted(_REGISTRY.items()))


def build_snapshots() -> dict[str, TemplateGolden]:
    """把每个注册场景跑一遍，产出按场景 ID 索引的 canonical 快照。"""
    snapshots: dict[str, TemplateGolden] = {}
    for scenario_id, builder in discover_scenarios().items():
        snapshots[scenario_id] = TemplateGolden(
            template_id=scenario_id,
            meta={},
            text=canonicalize(builder()),
        )
    return snapshots


_SCENARIO_STAGE_MAP: dict[str, str] = {
    # —— 管线阶段（first layer：检索与计划）——
    "retrieval": "1_pipeline/retrieval/retrieval",
    "plan_planner": "1_pipeline/retrieval/plan_planner",
    "plan_data": "1_pipeline/retrieval/plan_data",
    "retired_app_usage": "1_pipeline/retrieval/retired_app_usage",
    # —— 管线阶段（second layer：展开与组合）——
    "provider_elseif": "1_pipeline/composition/directives/provider_elseif",
    "provider_presence": "1_pipeline/composition/directives/provider_presence",
    "runtime_if": "1_pipeline/composition/directives/runtime_if",
    "pill_action": "1_pipeline/composition/actions/pill_action",
    "support_action": "1_pipeline/composition/actions/support_action",
    "non_fusion": "1_pipeline/composition/markers/non_fusion",
    "provider_marker": "1_pipeline/composition/markers/provider_marker",
    "tersel_protocol": "1_pipeline/composition/conversion/tersel_protocol",
    "a2ui_expression": "1_pipeline/composition/conversion/a2ui_expression",
    "provider_expr": "1_pipeline/composition/conversion/provider_expr",
    "style_enum": "1_pipeline/composition/conversion/style_enum",
    "text_heights": "1_pipeline/composition/conversion/text_heights",
    "image_color": "1_pipeline/composition/policies/image_color",
    "ux_title": "1_pipeline/composition/policies/ux_title",
    "battery_palette": "1_pipeline/composition/policies/battery_palette",
    "templgen": "1_pipeline/composition/templgen",
    # —— 管线阶段（契约与目录）——
    "internal_contracts": "1_pipeline/contracts/internal_contracts",
    "provider_asset": "1_pipeline/contracts/provider_asset",
    # —— 管线阶段（端到端矩阵；normal = 常规渲染，fusion_ball = 融球模式）——
    "pipeline_combo": "1_pipeline/matrix/pipeline_combo/normal",
    "pipeline_combo_fusion": "1_pipeline/matrix/pipeline_combo/fusion_ball",
    # —— 业务域垂直套件 ——
    "battery_action": "2_domain/battery/battery_action",
    "battery_caseext": "2_domain/battery/battery_caseext",
    "calendar_geometry": "2_domain/calendar/calendar_geometry",
    "calendar_fullext": "2_domain/calendar/calendar_fullext",
    "calendar_reqcase": "2_domain/calendar/calendar_reqcase",
    "earbud": "2_domain/earphone/earbud",
    "earbud_triple": "2_domain/earphone/earbud_triple",
    "earphone": "2_domain/earphone/earphone",
    "bluetooth_hero": "2_domain/earphone/bluetooth_hero",
    "support_refresh": "2_domain/support/support_refresh",
    "travel_weather": "2_domain/travel/travel_weather",
    "weather_hero": "2_domain/weather/weather_hero",
    # —— 工具数据集产物 ——
    "gallery_input": "3_tooling/gallery_input",
    "template_examples": "3_tooling/template_examples",
    "preview_dataset": "3_tooling/preview_dataset",
}


def scenario_group(scenario_id: str) -> str:
    """场景分组目录（相对 goldens/scenarios/）：按模板生成管线阶段组织。

    未在 ``_SCENARIO_STAGE_MAP`` 登记的新前缀落入 ``unsorted/``，登记一行即归位。
    """
    prefix = scenario_id.split("__", 1)[0]
    return _SCENARIO_STAGE_MAP.get(prefix, "unsorted")


# 端到端矩阵分组的金样文件名去掉场景 ID 前缀（目录本身已表达
# normal/fusion_ball 变体语义：normal/x.json ↔ pipeline_combo__x）。
_PREFIX_STRIPPED_GROUPS = frozenset(
    {
        "1_pipeline/matrix/pipeline_combo/normal",
        "1_pipeline/matrix/pipeline_combo/fusion_ball",
    }
)
_PREFIX_BY_GROUP = {group: prefix for prefix, group in _SCENARIO_STAGE_MAP.items()}


def scenario_file_stem(scenario_id: str) -> str:
    """场景 ID → 金样文件名（不含扩展名）；矩阵分组去掉 ID 前缀。"""
    group = scenario_group(scenario_id)
    if group in _PREFIX_STRIPPED_GROUPS:
        return scenario_id.split("__", 1)[1]
    return scenario_id


def scenario_id_for_path(path: Path) -> str:
    """金样文件路径 → 场景 ID（load_blessed/bless 清理的反向映射）。"""
    stem = path.stem
    group = path.parent.relative_to(SCENARIOS_DIR).as_posix()
    if group in _PREFIX_STRIPPED_GROUPS:
        return f"{_PREFIX_BY_GROUP[group]}__{stem}"
    return stem


def scenario_golden_path(scenario_id: str) -> Path:
    return (
        SCENARIOS_DIR
        / scenario_group(scenario_id)
        / f"{scenario_file_stem(scenario_id)}.json"
    )


def load_blessed() -> dict[str, str]:
    """读取已固化场景金样（递归各分组子目录）；目录不存在时返回空表。"""
    if not SCENARIOS_DIR.is_dir():
        return {}
    return {
        scenario_id_for_path(path): path.read_text(encoding="utf-8")
        for path in sorted(SCENARIOS_DIR.rglob("*.json"))
    }


def bless(generated: dict[str, TemplateGolden]) -> None:
    """固化当前场景快照：按分组写子目录文件并清理失效文件（与 Layer A 同语义）。"""
    SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
    for path in SCENARIOS_DIR.rglob("*.json"):
        if scenario_id_for_path(path) not in generated:
            path.unlink()
    for scenario_id, snapshot in sorted(generated.items()):
        target = scenario_golden_path(scenario_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(snapshot.text, encoding="utf-8")
    for directory in sorted(
        (path for path in SCENARIOS_DIR.rglob("*") if path.is_dir()),
        reverse=True,
    ):
        try:
            directory.rmdir()
        except OSError:
            pass  # 目录仍持有本批有效金样，保留。


def assert_golden_scenario(scenario_id: str) -> None:
    """测试断言入口：场景输出必须与已固化金样一致。

    缺失金样 = 未引导（提示 bless --declared）；不一致 = 带 unified diff
    失败（预期变化则申报后 bless）。
    """
    builder = _REGISTRY.get(scenario_id)
    if builder is None:
        raise AssertionError(f"unknown golden scenario id: {scenario_id!r}")
    snapshot = TemplateGolden(
        template_id=scenario_id, meta={}, text=canonicalize(builder())
    )
    path = scenario_golden_path(scenario_id)
    if not path.is_file():
        raise AssertionError(
            f"golden scenario {scenario_id!r} has no blessed snapshot. "
            "Bootstrap or bless after review:\n"
            "  python3 -m services.template_generation.test_support.golden_cli "
            f"bless --declared {scenario_id}"
        )
    blessed_text = path.read_text(encoding="utf-8")
    comparison = compare({scenario_id: snapshot}, {scenario_id: blessed_text})
    if comparison.has_divergence:
        diff = difflib.unified_diff(
            blessed_text.splitlines(),
            snapshot.text.splitlines(),
            fromfile=(
                f"goldens/scenarios/{scenario_group(scenario_id)}/"
                f"{scenario_file_stem(scenario_id)}.json (blessed)"
            ),
            tofile=f"{scenario_id} (generated)",
            lineterm="",
        )
        raise AssertionError(
            f"golden scenario {scenario_id!r} drifted from the blessed snapshot "
            "(intended change? re-run with the id declared, then bless):\n\n"
            + "\n".join(list(diff)[:_DIFF_LINE_CAP])
        )


def a2ui_messages(result: Any) -> dict[str, Any]:
    """把 generate_template_a2ui 的结果整理成可冻结的 canonical 载荷。"""
    return {
        "a2ui": [
            json.loads(line)
            for line in result.a2ui.splitlines()
            if line.strip()
        ],
        "templateIds": list(result.template_ids),
    }
