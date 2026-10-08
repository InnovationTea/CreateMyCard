"""Deterministic, size-scoped retrieval of generation and repair examples.

The catalog is deliberately local: no embedding request, network call, or
model-authored query is needed between the accepted Plan and JSX generation.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import PROMPT_SOURCE_DIR


_CASE_HEADING = re.compile(r"^## 示例[^\n]*$", re.MULTILINE)
_REPAIR_HEADING = re.compile(
    r"^## 修复 (?P<key>[\w-]+) \| (?P<scope>component|sublayout|parent-layout)"
    r" \| (?P<issue>overlap|overflow|structure)[^\n]*$", re.MULTILINE,
)
_INPUT = re.compile(r"### 输入\s*```json\s*(\{.*?\})\s*```", re.DOTALL)
_JSX = re.compile(r"<Card\b.*?</Card>", re.DOTALL)
_LAYOUT = re.compile(r'\blayout="([^"]+)"')
_VARIANT = re.compile(r'\bvariant="([^"]+)"')
_COMPONENT = re.compile(r"<([A-Z][A-Za-z0-9]*)\b")
_FRONTMATTER = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)


@dataclass(frozen=True, slots=True)
class Example:
    key: str
    source: Path
    text: str
    layout: str
    variants: frozenset[str]
    components: frozenset[str]
    data_count: int
    action_count: int
    scope: str = ""
    issue: str = ""


def _sections(path: Path, pattern: re.Pattern[str]) -> list[tuple[re.Match[str], str]]:
    source = path.read_text(encoding="utf-8")
    source = _FRONTMATTER.sub("", source, count=1)
    matches = list(pattern.finditer(source))
    return [
        (match, source[match.start():matches[index + 1].start() if index + 1 < len(matches) else len(source)].strip())
        for index, match in enumerate(matches)
    ]


def _profile(text: str) -> tuple[str, frozenset[str], frozenset[str]]:
    # For repair examples, use the corrected card (the last JSX expression).
    jsx_matches = _JSX.findall(text)
    jsx = jsx_matches[-1] if jsx_matches else ""
    layout_match = _LAYOUT.search(jsx)
    return (
        layout_match.group(1) if layout_match else "",
        frozenset(_VARIANT.findall(jsx)),
        frozenset(_COMPONENT.findall(jsx)) - {"Card", "Region"},
    )


def generation_examples(card_size: str) -> tuple[Example, ...]:
    if card_size not in {"2x2", "2x4"}:
        return ()
    paths = (
        PROMPT_SOURCE_DIR / "fewshots" / f"fewshots_{card_size}.md",
        PROMPT_SOURCE_DIR / "fewshots" / f"library_{card_size}.md",
        *((PROMPT_SOURCE_DIR / "fewshots" / "library_dense_2x2.md",) if card_size == "2x2" else ()),
        *((PROMPT_SOURCE_DIR / "fewshots" / "library_dense_2x4.md",) if card_size == "2x4" else ()),
    )
    examples: list[Example] = []
    for path in paths:
        for index, (_, section) in enumerate(_sections(path, _CASE_HEADING), start=1):
            input_match = _INPUT.search(section)
            if input_match is None:
                raise ValueError(f"few-shot has no input JSON: {path} section {index}")
            payload = json.loads(input_match.group(1))
            layout, variants, components = _profile(section)
            if not layout:
                raise ValueError(f"few-shot has no complete Card JSX: {path} section {index}")
            # The accepted Plan is already present at retrieval time. Repeating
            # its sample tool call costs tokens and can bias the current Plan.
            text = re.sub(r"\n### 计划\s*```js.*?```", "", section, flags=re.DOTALL)
            examples.append(Example(
                key=f"{path.stem}-{index}", source=path, text=text,
                layout=layout, variants=variants, components=components,
                data_count=len({item["id"] for item in payload.get("data", [])}),
                action_count=len({item["id"] for item in payload.get("actions", [])}),
            ))
    return tuple(examples)


def repair_examples(card_size: str) -> tuple[Example, ...]:
    if card_size not in {"2x2", "2x4"}:
        return ()
    path = PROMPT_SOURCE_DIR / "repair" / f"repair_examples_{card_size}.md"
    examples = []
    for match, section in _sections(path, _REPAIR_HEADING):
        layout, variants, components = _profile(section)
        # Count distinct IDs in the corrected expression, not literal values.
        corrected = _JSX.findall(section)[-1]
        binding_chunks = [
            *re.findall(r"dataIds=\{\{(.*?)\}\}", corrected, re.DOTALL),
            *re.findall(r'"dataIds"\s*:\s*\{(.*?)\}', corrected, re.DOTALL),
        ]
        data_ids = {
            value for chunk in binding_chunks
            for value in re.findall(r'"([\w.-]+)"', chunk)
            if "." in value
        }
        action_ids = set(re.findall(r'actionId="([^"]+)"', corrected))
        examples.append(Example(
            key=match.group("key"), source=path, text=section,
            layout=layout, variants=variants, components=components,
            data_count=len(data_ids), action_count=len(action_ids),
            scope=match.group("scope"), issue=match.group("issue"),
        ))
    return tuple(examples)


def select_generation_examples(
    plan: dict[str, Any], *, card_size: str, limit: int = 4,
) -> tuple[Example, ...]:
    """Rank by capacity first, then component and layout similarity."""
    limit = max(0, min(6, limit))
    facts = plan.get("info_required", [])
    data_count = len({fact["dataId"] for fact in facts if "dataId" in fact})
    action_count = len({fact["actionId"] for fact in facts if "actionId" in fact})
    hints = {hint for fact in facts for hint in fact.get("componentHints", [])}
    layouts = plan.get("layoutHints", [])

    def score(example: Example) -> tuple[int, int, int, int, str]:
        layout_rank = layouts.index(example.layout) if example.layout in layouts else 2
        return (
            abs(example.action_count - action_count),
            abs(example.data_count - data_count),
            layout_rank,
            -len(example.components & hints),
            example.key,
        )

    # An example with fewer Actions may teach the model to drop a required
    # button. Never retrieve it merely to increase layout diversity.
    tolerance = 2 if card_size == "2x2" else 3
    exact_action_examples = [
        item for item in generation_examples(card_size)
        if item.action_count == action_count
        and abs(item.data_count - data_count) <= tolerance
    ]
    if not exact_action_examples:
        return ()
    ranked = sorted(exact_action_examples, key=score)
    chosen: list[Example] = []
    by_layout: dict[str, int] = {}
    for example in ranked:
        if len(chosen) >= limit:
            break
        # Avoid a near-duplicate wall of examples for one parent layout.
        if by_layout.get(example.layout, 0) >= 2:
            continue
        chosen.append(example)
        by_layout[example.layout] = by_layout.get(example.layout, 0) + 1
    for example in ranked:
        if len(chosen) >= limit:
            break
        if example not in chosen:
            chosen.append(example)
    return tuple(chosen)


def select_repair_example(
    result: dict[str, Any], *, plan: dict[str, Any],
    submitted_jsx: str, used_keys: set[str], card_size: str,
) -> Example | None:
    """Return one geometry-relevant example, never a binding/prop repair."""
    findings = [
        item for item in result.get("findings", [])
        if isinstance(item, dict) and item.get("severity") == "error"
    ]
    codes = " ".join(str(item.get("code", "")) for item in findings)
    phase = str(result.get("phase", ""))
    if phase not in {"browser_layout", "layout_budget", "layout_structure"} and not any(
        token in codes for token in ("browser-", "layout-budget", "layout-structure")
    ):
        return None
    scope = str(result.get("repairScope") or "component")
    if result.get("fallbackStage") == "compact_component":
        scope = "parent-layout"
    if scope not in {"component", "sublayout", "parent-layout"}:
        scope = "component"
    issue = "overlap" if "overlap" in codes else "structure" if "structure" in codes else "overflow"
    facts = plan.get("info_required", [])
    data_count = len({fact["dataId"] for fact in facts if "dataId" in fact})
    action_count = len({fact["actionId"] for fact in facts if "actionId" in fact})
    current_layout = (_LAYOUT.search(submitted_jsx) or [None, ""])[1]
    candidates = [item for item in repair_examples(card_size) if item.scope == scope and item.key not in used_keys]
    if not candidates:
        return None
    return min(candidates, key=lambda item: (
        item.issue != issue,
        abs(item.action_count - action_count),
        abs(item.data_count - data_count),
        item.layout != current_layout if scope != "parent-layout" else item.layout == current_layout,
        item.key,
    ))
