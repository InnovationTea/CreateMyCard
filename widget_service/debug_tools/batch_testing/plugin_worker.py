"""在独立 Python 进程中加载并调用批跑后处理插件。"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import inspect
import json
from pathlib import Path
from typing import Any


def _load_module(entrypoint: Path) -> Any:
    spec = importlib.util.spec_from_file_location("batch_postprocess_plugin", entrypoint)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载插件入口")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _invoke(entrypoint: Path, hook: str, context: dict[str, Any]) -> dict[str, Any]:
    module = _load_module(entrypoint)
    function = getattr(module, hook, None)
    if function is None:
        if hook == "process_dataset":
            if context.get("apiVersion") == "batch-postprocess-v2":
                return {
                    "status": "skipped",
                    "summary": "插件未实现数据集汇总",
                    "facts": {},
                    "artifacts": [],
                }
            return {"status": "skipped", "summary": "插件未实现数据集汇总", "blocks": []}
        raise RuntimeError(f"插件未实现必选函数: {hook}")
    value = function(context)
    if inspect.isawaitable(value):
        value = await value
    if not isinstance(value, dict):
        raise TypeError(f"{hook} 必须返回 JSON 对象")
    json.dumps(value, ensure_ascii=False)
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entrypoint", required=True)
    parser.add_argument("--hook", choices=("process_sample", "process_dataset"), required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--result", required=True)
    arguments = parser.parse_args()
    context_path = Path(arguments.context).resolve()
    result_path = Path(arguments.result).resolve()
    context = json.loads(context_path.read_text(encoding="utf-8"))
    if not isinstance(context, dict):
        raise TypeError("插件上下文必须是 JSON 对象")
    result = asyncio.run(_invoke(Path(arguments.entrypoint).resolve(), arguments.hook, context))
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
