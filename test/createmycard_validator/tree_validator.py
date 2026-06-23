"""Component tree correctness rules."""

from __future__ import annotations

try:
    from .common import Finding, ValidationContext, component_id_map, error, referenced_ids, warning
except ImportError:
    from common import Finding, ValidationContext, component_id_map, error, referenced_ids, warning  # type: ignore


def validate(ctx: ValidationContext) -> list[Finding]:
    findings: list[Finding] = []
    ids: list[str] = []
    for component in ctx.components:
        cid = component.get("id")
        if isinstance(cid, str) and cid:
            ids.append(cid)

    if "root" not in ids:
        findings.append(error("RULE_TREE_001", "missing component id='root'", 10))
    if ids.count("root") > 1:
        findings.append(error("RULE_TREE_002", "root component appears more than once", 10))

    duplicates = sorted({cid for cid in ids if ids.count(cid) > 1})
    for cid in duplicates:
        findings.append(error("RULE_TREE_003", f"component id '{cid}' is duplicated", 10))

    index = component_id_map(ctx.components)
    for component in ctx.components:
        cid = component.get("id", "<unknown>")
        for ref in referenced_ids(component):
            if ref not in index:
                findings.append(error("RULE_TREE_004", f"component '{cid}' references missing child '{ref}'", 10))

    # Cycle detection and reachability.
    graph = {cid: referenced_ids(component) for cid, component in index.items()}
    visiting: set[str] = set()
    visited: set[str] = set()

    def dfs(cid: str, stack: list[str]) -> None:
        if cid in visiting:
            findings.append(error("RULE_TREE_005", "cycle reference detected: " + " -> ".join(stack + [cid]), 10))
            return
        if cid in visited:
            return
        visiting.add(cid)
        for ref in graph.get(cid, []):
            if ref in index:
                dfs(ref, stack + [cid])
        visiting.remove(cid)
        visited.add(cid)

    if "root" in index:
        dfs("root", [])
        for cid in sorted(set(index) - visited):
            findings.append(warning("RULE_TREE_006", f"component '{cid}' is not reachable from root"))

    return findings
