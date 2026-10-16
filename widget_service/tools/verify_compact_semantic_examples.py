"""验证既有案例迁移、导出统一渲染输入；不调用模型。"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

CLOUD = Path(__file__).resolve().parents[1] / "cloud"
sys.path.insert(0, str(CLOUD))

from services.compact_dsl_a2ui_converter import (  # noqa: E402
    ComponentRow,
    DataRow,
    parse_compact_dsl_rows,
)
from services.compact_prompt_loader import FRAGMENT  # noqa: E402
from services.compact_semantic_layout import GEOMETRY_PROPS  # noqa: E402
from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext  # noqa: E402


def blocks(body: str) -> dict[str, str]:
    return dict(re.findall(r"```(json|genui)\n([\s\S]*?)\n```", body))


def verify(old_source: str, new_source: str, output: Path) -> None:
    old_examples = dict(FRAGMENT.findall(old_source))
    output.mkdir(parents=True, exist_ok=False)
    (output / "md").mkdir()
    results = []
    for fragment, body in FRAGMENT.findall(new_source):
        if not fragment.startswith("example-"):
            continue
        original = old_examples.get(fragment)
        if original is None:
            raise ValueError("不得新增测试样本答案")
        old = blocks(original)
        current = blocks(body)
        if old.get("json") != current.get("json"):
            raise ValueError("示例输入发生变更 " + fragment)
        old_rows = parse_compact_dsl_rows(old["genui"], expand_layouts=False)
        new_rows = parse_compact_dsl_rows(current["genui"], expand_layouts=False)
        original_business = {}
        new_business = {}
        for rows, destination, excluded in (
            (old_rows, original_business, {"Row", "Column", "Stack"}),
            (new_rows, new_business, {"Layout", "Region", "Group"}),
        ):
            for row in rows:
                if not isinstance(row, ComponentRow) or row.component_type in excluded:
                    continue
                props = dict(row.props)
                for key in GEOMETRY_PROPS:
                    props.pop(key, None)
                destination[row.component_id] = (row.component_type, props)
        # V23 原有三项辅助文本默认双列会裁掉 mA；只改内部分列，不改事实或文字。
        if fragment == "example-v23":
            original_current = original_business.get("current")
            if original_current is not None:
                kind, props = original_current
                original_business["current"] = (kind, {**props, "columns": 1})
        if original_business != new_business:
            raise ValueError("业务组件、动作、样例值或语义发生变更 " + fragment)
        if [row for row in old_rows if isinstance(row, DataRow)] != [
            row for row in new_rows if isinstance(row, DataRow)
        ]:
            raise ValueError("数据行发生变更 " + fragment)
        task = json.loads(current["json"])
        task["appVersion"] = "12.0.0.1"
        processed = DesignCompactProcessor().process(
            current["genui"], DslProcessingContext(size="2x4", card_spec={}, task_spec=task,
                                                 protocol_profile={}, layout_scope="W-plan-guided"),
        )
        number = int(fragment.removeprefix("example-v"))
        artifact = "\n\n".join([
            "```request\n" + json.dumps(task, ensure_ascii=False) + "\n```",
            "```taskspec\n" + json.dumps(task, ensure_ascii=False) + "\n```",
            "```designcompactdsl\n" + current["genui"] + "\n```",
            "```genui\n" + processed.standard_dsl + "\n```",
        ])
        (output / "md" / f"q{number}_artifact.md").write_text(artifact, encoding="utf-8")
        meta = {"index": number, "title": fragment, "size": "2x4",
                "status": "success" if not processed.errors else "failed",
                "message": "；".join(error.message for error in processed.errors)}
        meta_file = output / f"q{number}_meta.json"
        meta_file.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        results.append(meta)
        print(fragment, meta["status"], meta["message"], flush=True)
    (output / "summary.json").write_text(json.dumps({"results": results}, ensure_ascii=False),
                                         encoding="utf-8")
    if any(result.get("status") != "success" for result in results):
        raise RuntimeError("示例未全部通过现有 Processor，保留结果供诊断")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--reference-ref", default="origin/main",
                        help="用于核对示例输入与业务事实的已同步上游引用")
    args = parser.parse_args()
    repository = CLOUD.parents[1]
    relative = args.source.resolve().relative_to(repository).as_posix()
    original_source = subprocess.check_output(
        ["git", "show", args.reference_ref + ":" + relative], cwd=repository,
    ).decode("utf-8")
    verify(original_source, args.source.read_text(encoding="utf-8"), args.output)
