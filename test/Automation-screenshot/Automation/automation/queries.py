from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class QueryCase:
    qid: str
    query: str


def load_queries(path: Path) -> list[QueryCase]:
    cases: list[QueryCase] = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line_number, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                cases.append(QueryCase(qid=f"q{line_number}", query=line))
                continue
            qid = str(obj.get("qid") or obj.get("id") or f"q{line_number}")
            query = str(obj.get("query") or obj.get("text") or "")
            if not query:
                raise ValueError(f"Missing query at {path}:{line_number}")
            cases.append(QueryCase(qid=qid, query=query))
    return cases

