"""静态测试的显式公共标题夹具；不供生产或模型示例使用。"""

import copy


def titled_rows(rows, title="共同主题"):
    result = copy.deepcopy(rows)
    root = next(row for row in result if row[0] == "root")
    body = next(row for row in result if row[0] == "body")
    items = body[2].get("items")
    if body[1] == "TextList" and isinstance(items, list) and len(items) == 3:
        return result
    if "header" not in root[3]:
        root[3].insert(0, "header")
        result.insert(1, ["header", "SingleLineTitle", {"title": title}])
    return result


def titled_plan(plan, title="共同主题"):
    result = copy.deepcopy(plan)
    facts = result.get("info_required")
    groups = result.get("contentGroups")
    assert isinstance(facts, list) and isinstance(groups, list)
    for group in groups:
        if group.get("kind") != "shared":
            continue
        for index in group.get("factIndexes", []):
            if facts[index].get("displayRole") == "title":
                return result
    references = []
    for fact in facts:
        if fact.get("sourceTexts"):
            references = fact.get("sourceTexts")[:1]
            break
    index = len(facts)
    facts.append({
        "text": title, "requirement": "卡片共同主题", "priority": "must",
        "sourceTexts": references, "displayRole": "title", "componentHints": ["SingleLineTitle"],
    })
    groups.append({"id": "fixture_header", "kind": "shared", "identity": None,
                   "factIndexes": [index]})
    return result
