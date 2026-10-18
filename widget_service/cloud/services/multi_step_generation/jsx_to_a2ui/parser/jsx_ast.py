from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class JSXElement:
    tag: str
    props: dict[str, Any] = field(default_factory=dict)
    children: list["JSXElement | str"] = field(default_factory=list)
    offset: int = 0

    def child_elements(self) -> list["JSXElement"]:
        return [child for child in self.children if isinstance(child, JSXElement)]
