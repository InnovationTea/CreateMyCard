"""防止调试工具测试重新进入微服务测试目录。"""

import ast
from pathlib import Path


def test_service_tests_do_not_import_debug_tools() -> None:
    service_tests = Path(__file__).resolve().parents[3] / "widget_service/tests"
    violations: list[str] = []
    for path in service_tests.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                modules = [node.module]
            for module in modules:
                if module == "debug_tools" or module.startswith("debug_tools."):
                    violations.append(f"{path.name}:{node.lineno}: {module}")
    assert not violations, "调试工具测试应归入 debug_tools/tests：" + "; ".join(violations)
