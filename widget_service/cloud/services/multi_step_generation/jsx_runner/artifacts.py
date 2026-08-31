from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


PACKAGE_DIR = Path(__file__).resolve().parent
SKILL_DIR = PACKAGE_DIR.parent
DEFAULT_TEMPLATE = SKILL_DIR / "templates" / "template.html"
TEMPLATE_COMPONENTS_PATTERN = re.compile(
    r"const\s*\{(?P<body>.*?)\}\s*=\s*window\.ClawWidgetDesignSystem\s*;",
    flags=re.DOTALL,
)


def load_tasks(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("tasks", [payload])
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ValueError("输入必须是任务对象、任务对象数组或包含 tasks 数组的对象")
    return payload


def select_tasks(
    tasks: list[dict[str, Any]], *, task_id: str | None, index: int | None, run_all: bool
) -> list[dict[str, Any]]:
    if run_all:
        return tasks
    if task_id is not None:
        selected = [task for task in tasks if str(task.get("id")) == task_id]
        if not selected:
            raise ValueError(f"找不到 id={task_id} 的任务")
        return selected
    selected_index = 0 if index is None else index
    if selected_index < 0 or selected_index >= len(tasks):
        raise ValueError(f"任务下标越界：{selected_index}")
    return [tasks[selected_index]]


def build_component_name(task: dict[str, Any], fallback_index: int) -> str:
    raw = str(task.get("id", fallback_index)).strip() or str(fallback_index)
    safe = re.sub(r"[^A-Za-z0-9_$]+", "_", raw).strip("_") or str(fallback_index)
    return f"CardGenerated_{safe}"


def create_run_dir(output_root: Path, run_id: str | None = None) -> tuple[str, Path]:
    resolved_id = run_id or datetime.now(UTC).astimezone().strftime("%Y%m%d-%H%M%S")
    if resolved_id in {".", ".."} or not re.fullmatch(r"[A-Za-z0-9._-]+", resolved_id):
        raise ValueError("run_id may contain only letters, numbers, dot, underscore and hyphen")
    target = output_root.resolve() / resolved_id
    (target / "jsx").mkdir(parents=True, exist_ok=True)
    (target / "a2ui").mkdir(parents=True, exist_ok=True)
    (target / "context").mkdir(parents=True, exist_ok=True)
    return resolved_id, target


def preview_template_components(template_path: Path = DEFAULT_TEMPLATE) -> frozenset[str]:
    """Return the Design System components made available to generated JSX."""
    source = template_path.read_text(encoding="utf-8")
    match = TEMPLATE_COMPONENTS_PATTERN.search(source)
    if not match:
        raise ValueError("template.html must destructure window.ClawWidgetDesignSystem for generated JSX")
    names: set[str] = set()
    for entry in match.group("body").split(","):
        name = entry.strip()
        if not name:
            continue
        if not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", name):
            raise ValueError(f"template.html contains an unsupported component binding: {name!r}")
        names.add(name)
    return frozenset(names)


def _wrap_expression(generated_component_name: str, jsx: str) -> str:
    return f"function {generated_component_name}() {{\n  return (\n{jsx.strip()}\n  );\n}}\n"


def write_rejected_card(
    *,
    jsx: str,
    component_name: str,
    turn: int,
    task: dict[str, Any],
    run_dir: Path,
) -> dict[str, str]:
    """Persist a rejected JSX candidate beside successful JSX artifacts."""
    jsx_dir = run_dir / "jsx"
    jsx_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{component_name}.turn-{turn:02d}.rejected"
    source = _wrap_expression(component_name, jsx)
    jsx_path = jsx_dir / f"{stem}.jsx"
    jsx_path.write_text(source, encoding="utf-8")
    return {
        "jsx": jsx_path.relative_to(run_dir).as_posix(),
    }


def write_card(
    result: dict[str, Any],
    run_dir: Path,
    task: dict[str, Any] | None = None,
    compile_context: dict[str, Any] | None = None,
) -> dict[str, str]:
    name = result["component_name"]
    jsx_dir = run_dir / "jsx"
    jsx_path = jsx_dir / f"{name}.jsx"
    a2ui_path = run_dir / "a2ui" / f"{name}.a2ui.json"
    jsx_path.write_text(result["source"], encoding="utf-8")
    a2ui_path.write_text(json.dumps(result["a2ui"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    paths = {
        "jsx": jsx_path.relative_to(run_dir).as_posix(),
        "a2ui": a2ui_path.relative_to(run_dir).as_posix(),
    }
    if compile_context and (compile_context.get("data") or compile_context.get("actions")):
        context_path = run_dir / "context" / f"{name}.context.json"
        context_path.write_text(
            json.dumps(compile_context, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        paths["context"] = context_path.relative_to(run_dir).as_posix()
    return paths


def write_json(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
