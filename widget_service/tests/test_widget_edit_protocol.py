"""协议快照完整性、原样例拼装和隔离转换的离线验收。"""

import hashlib
import json
import re
from pathlib import Path

import pytest

from custom.a2ui_model_client import A2UIModelClient
from models.generation import TaskSpec
from services.generation_pipeline import DslProcessingContext
from services.single_step_processor import SingleStepFallbackProcessor
from services.single_step_prompt import SingleStepPromptBuilder
from services.widget_edit_protocol import converter
from services.widget_edit_protocol.prompt_builder import SYSTEM_PROMPT, PromptBuilder
from services.widget_edit_protocol.resources import MODEL_FORMAT, PROFILE_DIR


def _manifest():
    return json.loads((PROFILE_DIR / "provenance.json").read_text(encoding="utf-8"))


def test_profile_resources_and_model_format_use_functional_names():
    assert PROFILE_DIR.name == "widget-edit"
    assert MODEL_FORMAT == "widget-edit-compact"
    assert converter.__name__ == "services.widget_edit_protocol.converter"
    assert SingleStepFallbackProcessor.__name__ == "SingleStepFallbackProcessor"
    manifest = _manifest()
    assert manifest.get("upstreamCommit")
    assert "upstreamBranch" not in manifest
    for entry in manifest.get("files", []):
        destination = entry.get("destination")
        assert isinstance(destination, str)
        assert "/widget-edit/" in destination or "/widget_edit_protocol/" in destination


def test_conversion_error_uses_functional_code():
    context = DslProcessingContext(size="2x2", card_spec={}, task_spec={}, protocol_profile={})
    result = SingleStepFallbackProcessor().process("not compact DSL", context)
    assert len(result.issues) == 1
    assert result.issues[0].code == "SINGLE_STEP_COMPACT_CONVERSION_FAILED"


_FROZEN_FILES = []
for _entry in _manifest().get("files", []):
    if _entry.get("adaptation", "").startswith("None"):
        _FROZEN_FILES.append(_entry)


@pytest.mark.parametrize("entry", _FROZEN_FILES, ids=lambda entry: entry.get("source"))
def test_frozen_resource_and_converter_are_exact_upstream_blobs(entry):
    root = Path(__file__).resolve().parents[2]
    destination = entry.get("destination")
    assert isinstance(destination, str)
    # 比较Git文本blob，不把Windows checkout的CRLF当成上游内容变化。
    content = (root / destination).read_bytes().replace(b"\r\n", b"\n")
    header = f"blob {len(content)}\0".encode()
    assert hashlib.sha1(header + content).hexdigest() == entry.get("upstreamGitBlob")


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_create_uses_entire_original_assembly_without_extra_fusion_constraints(size):
    task = TaskSpec(userQuery="展示天气", size=size, appVersion="11.7.7.331", dataModelSchema={})
    expected = PromptBuilder().build_design_compact(task, SYSTEM_PROMPT)
    actual = SingleStepPromptBuilder.build(task, {"documents": {"wrong": "OTHER_PROMPT"}},
                                         fallback_context={"failedSourceDsl": "FAILED_LAYOUT",
                                                           "fontRequirements": [{"fontSize": 30}]})
    assert actual == expected
    assert "OTHER_PROMPT" not in json.dumps(actual)
    assert "FAILED_LAYOUT" not in json.dumps(actual)
    payload = json.loads(actual[1].get("content", ""))
    assert payload == task.model_dump(mode="json", exclude_none=True, exclude={"appVersion"})


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_conversion_uses_frozen_protocol_not_fusion_converter(monkeypatch, size):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("single-step must not call fusion converter or processor")

    monkeypatch.setattr(
        "services.compact_dsl_a2ui_converter.convert_compact_dsl_to_a2ui", forbidden,
    )
    monkeypatch.setattr("services.generation_pipeline.DesignCompactProcessor.process", forbidden)
    text = (PROFILE_DIR / f"FEWSHOT_{size}.md").read_text(encoding="utf-8")
    examples = re.findall(r"```genui\s*\n(.*?)\n```", text, re.DOTALL)
    assert examples
    source = examples[0]
    task = {"appVersion": "11.7.7.331"}
    context = DslProcessingContext(size=size, card_spec={}, task_spec=task, protocol_profile={})
    result = SingleStepFallbackProcessor().process(source, context)
    assert not result.errors
    assert result.standard_dsl == converter.convert_compact_dsl_to_a2ui(
        source, size=size, protocol_profile={"version": "v0.9", "appVersion": "11.7.7.331"},
    )
    assert len(result.standard_dsl.splitlines()) == 3


def test_output_keeps_original_compact_rows_until_fallback_processor(monkeypatch):
    source = '["root","Column",{},["text"]]\n["text","Text",{"content":"卡片"}]'

    def forbidden(*_args):
        raise AssertionError("standard normalization must not touch single-step compact source")

    monkeypatch.setattr(A2UIModelClient, "convert_dsl", forbidden)
    result = A2UIModelClient()._process_model_output(
        f"```genui\n{source}\n```",
        {"id": MODEL_FORMAT, "format": MODEL_FORMAT, "singleStepOutput": True},
    )
    assert result == source


def test_edit_uses_field_patch_without_original_creation_rules():
    task = TaskSpec(userQuery="标题改16号字", size="2x4", dataModelSchema={})
    prompt = SingleStepPromptBuilder.build(task, {}, previous_genui="EXPANDED_SOURCE")
    system = prompt[0].get("content", "")
    payload = json.loads(prompt[1].get("content", ""))
    original_create = PromptBuilder().build_design_compact(task, SYSTEM_PROMPT)[0].get("content")
    assert original_create not in system
    assert "EXPANDED_SOURCE" not in system
    assert payload.get("previousGenui") == "EXPANDED_SOURCE"
    assert "previousDesignToken" not in system
    assert "只输出一个JSON对象" in system
    assert "不按任何创建默认规格修正原卡" in system


def test_repair_uses_original_repair_template():
    task = TaskSpec(userQuery="标题改16号字", size="2x4", dataModelSchema={})
    prompt = SingleStepPromptBuilder.build(task, {})
    errors = [{"message": "invalid"}]
    actual = SingleStepPromptBuilder.build_repair(prompt, "invalid compact", errors)
    expected = PromptBuilder().build_repair(
        prompt, "invalid compact", errors, dsl_format="design-compact-dsl",
    )
    assert actual == expected


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_mock_returns_matching_original_compact_format(size):
    task = TaskSpec(userQuery="卡片", size=size, dataModelSchema={})
    prompt = SingleStepPromptBuilder.build(task, {})
    source = A2UIModelClient(use_mock=True)._load_mock_data(
        {"id": MODEL_FORMAT, "format": MODEL_FORMAT}, prompt,
    )
    assert source.startswith('["root","Column"')
    context = DslProcessingContext(size=size, card_spec={}, task_spec={}, protocol_profile={})
    result = SingleStepFallbackProcessor().process(source, context)
    assert not result.errors
    assert result.standard_dsl
