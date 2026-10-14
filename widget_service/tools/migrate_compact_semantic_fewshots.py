"""迁移已有 2×4 Few-shot 的布局表达；输入和业务组件 Props 不增删。"""

import argparse
import json
import re
import sys
from copy import deepcopy
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


class Migration:
    def __init__(self, source: str) -> None:
        self.rows = parse_compact_dsl_rows(source, expand_layouts=False)
        self.by_id = {}
        for row in self.rows:
            if isinstance(row, ComponentRow):
                self.by_id[row.component_id] = row
        self.result: list[list] = []
        self.used: set[str] = set()

    def node(self, identifier: str) -> ComponentRow:
        row = self.by_id.get(identifier)
        if row is None:
            raise ValueError("不存在组件 " + identifier)
        return row

    def unwrap(self, identifier: str) -> str:
        row = self.node(identifier)
        while row.component_type in {"Row", "Column", "Stack"} and len(row.children) == 1:
            identifier = row.children[0]
            row = self.node(identifier)
        return identifier

    def content(self, identifier: str) -> str:
        identifier = self.unwrap(identifier)
        row = self.node(identifier)
        if identifier in self.used:
            raise ValueError("迁移会重复引用业务组件 " + identifier)
        self.used.add(identifier)
        if row.component_type in {"Row", "Column", "Stack"}:
            if len(row.children) != 2:
                raise ValueError(f"{identifier} 不属于已登记的两项组合")
            children = [self.content(child) for child in row.children]
            variant = "peer-pair" if row.component_type == "Row" else "hero-support"
            if self.node(children[0]).component_type == "SecondaryBody":
                variant = "label-value"
            self.result.append([identifier, "Group", {"variant": variant}, children])
        else:
            props = deepcopy(row.props)
            for key in GEOMETRY_PROPS:
                props.pop(key, None)
            self.result.append([identifier, row.component_type, props])
        return identifier

    def region(self, identifier: str) -> str:
        outer = identifier
        identifier = self.unwrap(identifier)
        row = self.node(identifier)
        children = list(row.children)
        if not children or self.node(children[0]).component_type != "SingleLineTitle":
            child = self.content(identifier)
            self.result.append([outer, "Region", {"variant": "center"}, [child]])
            return outer
        title = self.content(children.pop(0))
        action = None
        if children and self.node(children[-1]).component_type == "PillButton":
            action = self.content(children.pop())
        if len(children) != 1:
            raise ValueError("子布局不属于单内容、主次内容或紧密主辅 " + identifier)
        body_id = self.unwrap(children[0])
        body = self.node(body_id)
        content_children = [title]
        if body.component_type == "Column" and len(body.children) == 2:
            content_children.extend(self.content(child) for child in body.children)
            variant = "title-hero-support-action" if action else "title-primary-details"
        else:
            content_children.append(self.content(body_id))
            variant = "title-content-action" if action else "title-content"
        if action:
            content_children.append(action)
        self.result.append([outer, "Region", {"variant": variant}, content_children])
        return outer

    def convert(self, layout: str, description: str) -> str:
        original_root = self.node("root")
        root_id = self.unwrap("root")
        root = self.node(root_id)
        props = {"layout": layout}
        for node in (original_root, root):
            for key in ("linearGradient", "backgroundColor", "backgroundImage"):
                if key in node.props:
                    props[key] = deepcopy(node.props[key])
        if layout == "W-top-bottom":
            children = list(root.children)
            title = []
            if self.node(children[0]).component_type == "SingleLineTitle":
                title.append(self.content(children.pop(0)))
            if len(children) == 1:
                children = list(self.node(self.unwrap(children[0])).children)
            if len(children) != 2:
                raise ValueError("上下结构不明")
            props["variant"] = "bottom-details" if "底部结论" in description else "continuous"
            children = title + [self.content(child) for child in children]
        elif layout == "W-split-panels":
            children = [self.region(child) for child in root.children]
        elif layout == "W-content-side-slots":
            content, slots = root.children
            slots_node = self.node(self.unwrap(slots))
            if len(slots_node.children) != 2:
                raise ValueError("双槽结构不明")
            children = [self.region(content)]
            children.extend(self.content(child) for child in slots_node.children)
        else:
            children = []
            for identifier in root.children:
                children.extend(self.content(child) for child in self.node(identifier).children)
        self.result.insert(0, ["root", "Layout", props, children])
        for row in self.rows:
            if isinstance(row, DataRow):
                self.result.append([row.path, deepcopy(row.value)])
        return "\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":"))
                         for row in self.result)


def migrate(source: str) -> str:
    def replace_fragment(match: re.Match) -> str:
        fragment, body = match.group(1), match.group(2)
        if not fragment.startswith("example-"):
            return match.group(0)
        block = re.search(r"```genui\n([\s\S]*?)\n```", body)
        if block is None:
            raise ValueError("示例缺少唯一 DSL")
        layout_match = re.search(r"W-[a-z-]+", body)
        if layout_match is None:
            raise ValueError("示例未标注父布局")
        converted = Migration(block.group(1)).convert(layout_match.group(), body)
        body = body[:block.start(1)] + converted + body[block.end(1):]
        return f"<!-- prompt:{fragment} -->\n{body}<!-- /prompt:{fragment} -->\n"
    return FRAGMENT.sub(replace_fragment, source)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(migrate(args.source.read_text(encoding="utf-8")), encoding="utf-8")
