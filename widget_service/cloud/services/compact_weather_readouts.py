"""融合 Plan 中需要单独说明的两项天气读数。"""

import re


def selected_weather_readouts(card_spec: dict, plan: dict | None) -> dict[str, tuple[str, ...]]:
    """按实际挂载路径识别已选字段，不把同名字段或其它百分比视为天气指标。"""
    bindings = card_spec.get("dataBindings") or []
    roots = []
    for binding in bindings:
        if isinstance(binding, dict) and binding.get("capabilityId") == "ViewWeather":
            root = binding.get("writeResultTo")
            if isinstance(root, str) and root.startswith("/"):
                roots.append(root.rstrip("/") + "/")

    facts = (plan or {}).get("info_required")
    if not roots or not isinstance(facts, list):
        return {}
    labels = {}
    for fact in facts:
        path = fact.get("dataId") if isinstance(fact, dict) else None
        if not isinstance(path, str):
            continue
        for root in roots:
            if not path.startswith(root):
                continue
            relative = path.removeprefix(root)
            if relative == "current/windLevel":
                labels[path] = ("风力", "风级")
            elif re.fullmatch(r"daily/[0-9]+/rainProbabilityPercent", relative):
                labels[path] = ("降水概率", "降雨概率")
    return labels
