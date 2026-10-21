"""云侧 Trace 计时调用规范回归。"""

import ast
from pathlib import Path


def test_changed_trace_steps_always_supply_measured_duration():
    root = Path(__file__).parents[1] / "cloud"
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id != "trace_step":
                continue
            assert any(keyword.arg == "duration_ms" for keyword in node.keywords), (
                path, node.lineno,
            )
