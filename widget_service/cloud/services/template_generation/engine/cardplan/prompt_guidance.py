"""按已选模板裁剪业务专属说明，保留完整条目及公共约束。"""

from __future__ import annotations

import re

_TEMPLATE_REFERENCE = re.compile(r"\b[A-Za-z][A-Za-z0-9-]*@[1-9][0-9]*\b")


def selected_template_guidance(
    content: str,
    business_template_ids: frozenset[str],
    selected_template_ids: frozenset[str],
) -> str:
    """仅移除明确引用其它业务模板的完整条目，不按字符截断或改写正文。"""
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in content.splitlines():
        boundary = line.startswith("- ") or line.startswith("#")
        if boundary and current:
            blocks.append(current)
            current = []
        current.append(line)
    if current:
        blocks.append(current)

    visible: list[str] = []
    for block in blocks:
        text = "\n".join(block)
        references = frozenset(_TEMPLATE_REFERENCE.findall(text))
        business_references = references.intersection(business_template_ids)
        unrelated = business_references.isdisjoint(selected_template_ids)
        if business_references and unrelated:
            continue
        visible.append(text)
    return "\n".join(visible).strip()
