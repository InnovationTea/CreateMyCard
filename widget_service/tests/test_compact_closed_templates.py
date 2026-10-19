"""布局和组合模板须在代码块内闭合引用，不依赖模型补写悬空节点。"""

import json
import re
from collections import Counter
from pathlib import Path

import pytest

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


def _template_rows(source):
    """只在测试中移除属性占位，检查结构；不改变 Runtime 的严格 JSON 解析。"""
    rows = []
    for line in source.splitlines():
        if not line.strip():
            continue
        normalized = line.replace("{...}", "{}").replace(",...}", "}")
        rows.append(json.loads(normalized))
    return rows


@pytest.mark.parametrize("filename,source", _templates())
def test_template_references_are_closed(filename, source):
    components = {}
    for row in _template_rows(source):
        assert isinstance(row, list)
        assert len(row) in (3, 4), filename
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
def test_template_business_props_are_placeholders(filename, source):
    for line, row in zip(source.strip().splitlines(), _template_rows(source), strict=True):
        if row[1] in ("Layout", "Region", "Group"):
            assert "..." not in line, filename
            assert set(row[2]) <= {"layout", "variant", "orientation"}, filename
        else:
            assert "..." in line, filename
            assert set(row[2]) <= {"variant", "direction"}, filename


def test_template_explanations_and_core_reference_contract():
    assert len(_templates()) == 33
    for filename in FILES:
        text = (SOURCE / filename).read_text(encoding="utf-8")
        assert "不能输出省略号" in text
    core = (SOURCE / "core.md").read_text(encoding="utf-8")
    assert "children 中每个 ID 必须与本次输出某一组件行的第一项逐字一致" in core
    assert "组件 ID 引用不同于显示值的数据路径绑定" in core
