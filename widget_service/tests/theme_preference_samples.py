"""测试显式提供模型语义结果；不在Mock中重新实现中文关键词识别。"""

import json


def preference(attribute, value, evidence, operation="prefer"):
    return {"property": attribute, "operator": operation, "value": value, "evidence": evidence}


def reply(items, theme_id="gradient-blue"):
    return json.dumps({"themeId": theme_id, "preferences": items}, ensure_ascii=False)
