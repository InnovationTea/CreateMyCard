"""布局和组合模板须在代码块内闭合引用，不依赖模型补写悬空节点。"""

import json
import re
from collections import Counter
from pathlib import Path

import pytest

from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source"
)
FILES = ("layouts/2x2.md", "layouts/2x4.md", "combinations/2x2.md")
BLOCK = re.compile(r"```genui\s*\n(.*?)```", re.DOTALL)


def _templates():
    templates = []
    for filename in FILES:
        text = (SOURCE / filename).read_text(encoding="utf-8")
        for index, match in enumerate(BLOCK.finditer(text), 1):
            templates.append(pytest.param(filename, match.group(1), id=f"{filename}-{index}"))
    return templates


@pytest.mark.parametrize("filename,source", _templates())
def test_template_references_are_closed(filename, source):
    components = {}
    for line in source.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        assert isinstance(row, list)
        if len(row) == 2:
            continue
        identifier = row[0]
        assert identifier not in components, f"Duplicate component: {identifier}"
        assert isinstance(row[2], dict)
        components[identifier] = row
    assert components
    first = next(iter(components))
    incoming = Counter()
    for row in components.values():
        children = row[3] if len(row) == 4 else []
        for child in children:
            assert child in components, f"{row[0]} references missing component {child}"
            incoming[child] += 1
    for identifier in components:
        expected = 0 if identifier == first else 1
        assert incoming.get(identifier, 0) == expected
    reached = set()
    pending = [first]
    while pending:
        identifier = pending.pop()
        assert identifier not in reached, f"Cycle or repeated child: {identifier}"
        reached.add(identifier)
        row = components.get(identifier)
        assert row is not None
        pending.extend(row[3] if len(row) == 4 else [])
    assert reached == set(components)


@pytest.mark.parametrize("filename,source", _templates())
def test_template_business_props_convert(filename, source):
    size = "2x4" if "2x4" in filename else "2x2"
    first_line = next(line for line in source.splitlines() if line.strip())
    first = json.loads(first_line)
    if first[0] != "root":
        if size == "2x4":
            prefix = [
                ["root", "Layout", {"layout": "W-content-side-slots"},
                 [first[0], "fixture_upper", "fixture_lower"]],
                ["fixture_upper", "InfoBlock", {
                    "variant": "slot", "primaryText": "信息甲", "secondaryText": "对象甲",
                    "backgroundColor": "#99FFFFFF",
                }],
                ["fixture_lower", "InfoBlock", {
                    "variant": "slot", "primaryText": "信息乙", "secondaryText": "对象乙",
                    "backgroundColor": "#99FFFFFF",
                }],
            ]
        else:
            prefix = [
                ["root", "Layout", {"layout": "S-title-content"}, ["fixture_title", first[0]]],
                ["fixture_title", "SingleLineTitle", {"title": "状态", "fontSize": 12}],
            ]
        source = "\n".join(json.dumps(row, ensure_ascii=False) for row in prefix) + "\n" + source
    result = convert_compact_dsl_to_a2ui(
        source, size=size, protocol_profile={"version": "v0.9", "appVersion": "99.0"},
    )
    messages = [json.loads(line) for line in result.splitlines()]
    assert len(messages) == 3
