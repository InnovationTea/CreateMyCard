from __future__ import annotations

from collections import Counter
from typing import Any

from ..base import BaseValidator
from .common import add, component_pointer, iter_components, parents_by_id


class IconValidator(BaseValidator):
    stage = "quality"
    name = "icon"

    def validate(self, context: Any, rules: Any, reporter: Any) -> None:
        del rules
        parents = parents_by_id(context)
        sources: list[tuple[int, str, tuple[str, ...]]] = []
        for index, component in iter_components(context):
            if component.get("component") != "Image":
                continue
            src = component.get("src")
            is_static = isinstance(src, str) and src and not src.strip().startswith(("{{", "${"))
            if is_static:
                component_id = component.get("id")
                parent_ids = ()
                if isinstance(component_id, str):
                    parent_ids = tuple(sorted(parents.get(component_id, set())))
                sources.append((index, src, parent_ids))
        keys = ((src, parent_ids) for _, src, parent_ids in sources if parent_ids)
        for duplicate_key, count in Counter(keys).items():
            if count > 1:
                src, parent_ids = duplicate_key
                index = next(
                    item_index
                    for item_index, value, item_parents in sources
                    if value == src and item_parents == parent_ids
                )
                add(
                    reporter,
                    "ICON.DUPLICATE_SRC",
                    component_pointer(index, "src"),
                    "同一卡片不应重复使用相同装饰图标。",
                    src,
                    "避免重复装饰素材",
                )
