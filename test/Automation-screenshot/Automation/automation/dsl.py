from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .ui_tree import UiTree


DSL_KEYWORDS = ("createSurface", "updateComponents", "updateDataModel", "v0.9")
REQUIRED_DSL_KEYS = ("createSurface", "updateComponents", "updateDataModel")
GENUI_MARKER = "genui"
CARDSPEC_MARKER = "cardspec"
DSL_RECORD_START_RE = re.compile(
    r'\{\s*"version"\s*:\s*"v0\.9"\s*,\s*"(?P<op>createSurface|updateComponents|updateDataModel)"\s*:',
    re.S,
)


@dataclass(frozen=True)
class DslExtraction:
    qid: str
    records: list[dict]
    source_text: str

    @property
    def found(self) -> bool:
        return bool(self.records)


class DslExtractor:
    def __init__(self, keywords: tuple[str, ...] = DSL_KEYWORDS):
        self.keywords = keywords

    def extract_from_tree(self, qid: str, tree: UiTree) -> DslExtraction:
        best_source = ""
        best_records: list[dict] = []
        strategy1_complete: DslExtraction | None = None
        has_genui_scope = has_genui_marker(tree)

        for source in iter_single_dsl_nodes(tree, self.keywords):
            records = repair_and_extract(source)
            if is_complete_dsl(records) and strategy1_complete is None:
                strategy1_complete = DslExtraction(qid=qid, records=records, source_text=source)
            if len(records) > len(best_records):
                best_source, best_records = source, records

        if has_open_genui_without_cardspec(tree):
            return DslExtraction(qid=qid, records=[], source_text=best_source)

        for source in iter_genui_cardspec_blocks(tree):
            records = repair_and_extract(source)
            if is_complete_dsl(records):
                return DslExtraction(qid=qid, records=records, source_text=source)
            if len(records) > len(best_records):
                best_source, best_records = source, records

        for source in iter_nearby_dsl_sibling_blocks(tree, self.keywords):
            records = repair_and_extract(source)
            if is_complete_dsl(records):
                return DslExtraction(qid=qid, records=records, source_text=source)
            if len(records) > len(best_records):
                best_source, best_records = source, records

        if strategy1_complete is not None and not has_genui_scope:
            return strategy1_complete

        return DslExtraction(qid=qid, records=[], source_text=best_source)

    def save_jsonl(self, extraction: DslExtraction, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("[")
            for index, record in enumerate(extraction.records):
                if index > 0:
                    f.write(",\n")
                f.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            f.write("]\n")
        return path

    def _parse_records(self, text: str) -> list[dict]:
        parsed_source = parse_json_records(text)
        if parsed_source:
            return parsed_source

        records: list[dict] = []
        for line in text.splitlines():
            line = line.strip()
            if not any(keyword in line for keyword in self.keywords):
                continue
            records.extend(parse_json_records(line))
        if records:
            return records

        for candidate in iter_json_candidates(text):
            if any(keyword in candidate for keyword in self.keywords):
                records.extend(parse_json_records(candidate))
        return records


def parse_json_records(text: str) -> list[dict]:
    return repair_and_extract(text)


def repair_and_extract(text: str) -> list[dict]:
    text = strip_code_fence(text)
    records = parse_json_value(text)
    if records:
        return records

    records = []
    for segment in iter_dsl_record_segments(text):
        records.extend(parse_repaired_json_records(segment))
    return dedupe_records(records)


def iter_single_dsl_nodes(tree: UiTree, keywords: tuple[str, ...]):
    for node in tree.nodes:
        text = node.text.strip()
        if text and any(keyword in text for keyword in keywords):
            yield text


def iter_genui_cardspec_blocks(tree: UiTree):
    text_nodes = [(index, node.text.strip()) for index, node in enumerate(tree.nodes) if node.text.strip()]
    marker_indexes = [
        (position, text.lower())
        for position, (_, text) in enumerate(text_nodes)
        if text.lower() in {GENUI_MARKER, CARDSPEC_MARKER}
    ]

    for marker_position, marker in marker_indexes:
        if marker != GENUI_MARKER:
            continue
        end_position = next(
            (
                position
                for position, next_marker in marker_indexes
                if position > marker_position and next_marker == CARDSPEC_MARKER
            ),
            None,
        )
        if end_position is None or end_position <= marker_position + 1:
            continue
        yield "\n".join(text for _, text in text_nodes[marker_position + 1 : end_position])


def has_genui_marker(tree: UiTree) -> bool:
    return any(node.text.strip().lower() == GENUI_MARKER for node in tree.nodes)


def has_open_genui_without_cardspec(tree: UiTree) -> bool:
    texts = [node.text.strip().lower() for node in tree.nodes if node.text.strip()]
    for index, text in enumerate(texts):
        if text == GENUI_MARKER and CARDSPEC_MARKER not in texts[index + 1 :]:
            return True
    return False


def iter_nearby_dsl_sibling_blocks(tree: UiTree, keywords: tuple[str, ...], max_index_distance: int = 5):
    indexed_nodes = list(enumerate(tree.nodes))
    anchor_indexes = [
        index
        for index, node in indexed_nodes
        if node.text.strip() and any(keyword in node.text for keyword in keywords)
    ]
    yielded: set[tuple[int, int]] = set()

    for anchor_index in anchor_indexes:
        start = max(0, anchor_index - max_index_distance)
        end = min(len(tree.nodes), anchor_index + max_index_distance + 1)
        key = (start, end)
        if key in yielded:
            continue
        yielded.add(key)
        texts = [node.text.strip() for node in tree.nodes[start:end] if node.text.strip()]
        if texts:
            yield "\n".join(texts)


def is_complete_dsl(records: list[dict]) -> bool:
    return all(any(required_key in record for record in records) for required_key in REQUIRED_DSL_KEYS)


def parse_json_value(text: str) -> list[dict]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def parse_repaired_json_records(text: str) -> list[dict]:
    for candidate in iter_repair_candidates(text):
        for parser in (parse_json_value, parse_json_prefix_value):
            records = parser(candidate)
            if records:
                return records
    return []


def parse_json_prefix_value(text: str) -> list[dict]:
    try:
        value, _ = json.JSONDecoder().raw_decode(text)
    except json.JSONDecodeError:
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def iter_dsl_record_segments(text: str):
    matches = list(DSL_RECORD_START_RE.finditer(text))
    if matches:
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            yield trim_record_segment(text[match.start() : end])
        return

    yield from iter_json_candidates(text)


def trim_record_segment(text: str) -> str:
    segment = text.strip()
    start = segment.find("{")
    if start > 0:
        segment = segment[start:]
    return segment.strip().rstrip(",")


def iter_repair_candidates(text: str):
    candidate = trim_record_segment(strip_code_fence(text))
    if not candidate:
        return
    yield candidate

    balanced = balance_json_boundaries(candidate)
    if balanced != candidate:
        yield balanced


def balance_json_boundaries(text: str) -> str:
    stack: list[str] = []
    output: list[str] = []
    in_string = False
    escaped = False

    for char in text:
        output.append(char)
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            stack.append("}")
        elif char == "[":
            stack.append("]")
        elif char in "}]":
            if stack and char == stack[-1]:
                stack.pop()
            else:
                output.pop()

    if in_string:
        output.append('"')

    output.extend(reversed(stack))
    return "".join(output)


def dedupe_records(records: list[dict]) -> list[dict]:
    seen: set[str] = set()
    unique: list[dict] = []
    for record in records:
        fingerprint = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        unique.append(record)
    return unique


def strip_code_fence(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json|jsonl)?", "", cleaned, flags=re.I).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    return cleaned


def iter_json_candidates(text: str):
    start: int | None = None
    depth = 0
    in_string = False
    escaped = False

    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char in "{[":
            if depth == 0:
                start = index
            depth += 1
        elif char in "}]":
            if depth == 0:
                continue
            depth -= 1
            if depth == 0 and start is not None:
                yield text[start : index + 1]
                start = None

