"""显式刷新经过评审的提示词快照；先 build，再运行本脚本并审查哈希差异。"""

import argparse
import hashlib
import json
import re
from pathlib import Path

from scripts.build_compact_prompts import DEFAULT_BUNDLE, FRAGMENT, compile_bundle

from config.config import get_settings
from models.generation import TaskSpec
from services.prompt_builder import PromptBuilder
from services.protocol_registry import DESIGN_COMPACT_PROFILE_ID, A2UIProtocolRegistry

BASELINE = (
    Path(__file__).resolve().parents[1] / "tests/fixtures/compact_prompt_migration_baseline.json"
)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def refresh(reason: str) -> None:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    baseline["revisionReason"] = reason
    baseline["products"] = {
        name: _digest(content) for name, content in compile_bundle().items()
    }
    records = baseline.get("messages")
    assert isinstance(records, list)
    settings = get_settings()
    previous_config = settings.CONFIG
    try:
        settings.CONFIG = {"fusion_ball_min_prd_version": "11.7.7.300"}
        prompt = A2UIProtocolRegistry.read_design_prompt(DESIGN_COMPACT_PROFILE_ID)
        builder = PromptBuilder()
        for record in records:
            identifier = record.get("id")
            assert isinstance(identifier, str)
            size, example = identifier.split("-")
            source = DEFAULT_BUNDLE / "prompt_source/fewshots" / f"{size}.md"
            fragments = dict(FRAGMENT.findall(source.read_text(encoding="utf-8")))
            content = fragments.get(f"example-{example.lower()}")
            assert isinstance(content, str)
            task_match = re.search(r"```json\s*\n(.*?)\n```", content, re.S)
            dsl_match = re.search(r"```genui\s*\n(.*?)\n```", content, re.S)
            assert task_match is not None and dsl_match is not None
            task = TaskSpec(**json.loads(task_match.group(1)), appVersion=record.get("appVersion"))
            dsl = dsl_match.group(1)
            mode = record.get("mode")
            messages = builder.build_design_compact(task, prompt)
            if mode == "edit":
                messages = builder.build_design_compact(task, prompt, previous_design_token=dsl)
            elif mode == "repair":
                errors = [{"stage": "conversion", "code": "TEST", "message": "引用缺失"}]
                messages = builder.build_repair(
                    messages, dsl, errors, dsl_format=DESIGN_COMPACT_PROFILE_ID,
                )
            else:
                assert mode == "create"
            record["sha256"] = _digest(json.dumps(messages, ensure_ascii=False))
    finally:
        settings.CONFIG = previous_config
    BASELINE.write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reason", required=True, help="记录本次有意改变提示词的原因")
    refresh(parser.parse_args().reason)
