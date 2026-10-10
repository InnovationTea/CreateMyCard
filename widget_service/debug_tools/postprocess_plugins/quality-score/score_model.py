"""共享后果评分模型；参数从随插件交付的方案读取，normalize/score 为纯计算。"""

import copy
import hashlib
import json
import math
from pathlib import Path

NAMES = {
    "function": "功能与需求",
    "visibility": "可见性与可读性",
    "layout": "布局合理性",
    "style": "细节规范",
}
_POLICY_START = "<!-- scoring-policy:start -->"
_POLICY_END = "<!-- scoring-policy:end -->"


def load_policy():
    """只读取固定方案文件；无效参数立即失败，不回退到另一套默认权重。"""
    document = Path(__file__).with_name("EVALUATION.md").read_text(encoding="utf-8")
    block = document.split(_POLICY_START, 1)[1].split(_POLICY_END, 1)[0].strip()
    if not block.startswith("```json\n") or not block.endswith("```"):
        raise ValueError("方案必须包含唯一 JSON 参数块")
    value = json.loads(block.removeprefix("```json\n").removesuffix("```"))
    weights = value.get("weights")
    degrees = value.get("degrees")
    if not isinstance(weights, dict) or set(weights) != set(NAMES):
        raise ValueError("方案必须声明四类权重")
    if not isinstance(degrees, dict) or set(degrees) != {"severe", "medium", "minor"}:
        raise ValueError("方案必须声明三档严重程度")
    for number in [*weights.values(), *degrees.values()]:
        if type(number) not in (int, float) or not math.isfinite(number):
            raise ValueError("参数必须为有限数值")
        if not 0 <= number <= 1:
            raise ValueError("参数必须在 0 到 1 之间")
    if not math.isclose(sum(weights.values()), 1):
        raise ValueError("四类权重之和必须为 1")
    rules = value.get("rules")
    if not isinstance(rules, dict):
        raise ValueError("方案规则表必须为对象")
    for code, rule in rules.items():
        if not isinstance(code, str) or not isinstance(rule, list) or len(rule) != 3:
            raise ValueError("方案规则格式无效")
        category, degree, confirmed = rule
        if category not in weights or degree not in degrees or type(confirmed) is not bool:
            raise ValueError(f"方案规则参数无效: {code}")
    prefixes = value.get("prefix_rules")
    if not isinstance(prefixes, list):
        raise ValueError("方案缺少前缀规则")
    for item in prefixes:
        if not isinstance(item, dict) or item.get("category") not in weights:
            raise ValueError("方案前缀分类无效")
        values = item.get("prefixes")
        if not isinstance(values, list) or not values:
            raise ValueError("方案前缀列表无效")
        if any(not isinstance(prefix, str) or not prefix for prefix in values):
            raise ValueError("方案前缀不得为空")
    return value


_POLICY = load_policy()
WEIGHTS = _POLICY.get("weights")
DEGREES = _POLICY.get("degrees")
RULES = _POLICY.get("rules")

def components(f):
    e = f.get("evidence") or {}
    if isinstance(e, list):
        return sorted({x["component"] for x in e if isinstance(x, dict) and x.get("component")})
    if not isinstance(e, dict):
        e = {}
    original = e.get("original", {})
    el = f.get("element") or {}
    return (
        f.get("components")
        or e.get("components")
        or original.get("components")
        or [e.get("component") or el.get("dsl_id") or el.get("json_pointer") or "card"]
    )


def normalize(f, origin):
    code = f.get("code") or f.get("rule_id") or "unknown"
    short = code.removeprefix("native.")
    evidence = f.get("evidence") or {}
    phone_number_note = short == "event.phone_target_unresolved" or (
        short == "review.confirmed_missing_recipient"
        and isinstance(evidence, dict)
        and evidence.get("requirement") == "phone_target"
    )
    info = f.get("level") == "info" or f.get("confidence") in (
        "native_root_model_replay_verified",
        "native_binding_transition_verified",
    )
    info = info or phone_number_note
    rule = RULES.get(short)
    gate = (
        f.get("level") == "reject"
        or f.get("severity") == "P0"
        or short in ("structure.invalid", "render.failed")
    )
    if not rule and gate:
        rule = ("function", "severe", True)
    if not rule and f.get("rule_id"):
        category = None
        for mapping in _POLICY.get("prefix_rules", []):
            if code.startswith(tuple(mapping.get("prefixes", []))):
                category = mapping.get("category")
                break
        if category:
            rule = (
                category,
                "minor" if f.get("severity") in ("P2", "P3") else "medium",
                f.get("evidence_type") == "程序已证实",
            )
    cat, degree, confirmed = rule or (None, "medium", False)
    if f.get("severity") == "P0":
        confirmed = f.get("evidence_type") == "程序已证实"
    # Geometry on off-screen list instances is not proof of visible missing content.
    if f.get("template_instances") and short in ("layout.zero_area", "layout.clipped_content"):
        confirmed = False
    if f.get("impact") in DEGREES:
        degree = f["impact"]
    targets = components(f)
    family = short
    if short in ("event.phone_target_unresolved", "review.confirmed_missing_recipient"):
        family, targets = "phone_target", ["card"]
    if short in (
        "text.capacity_exceeded",
        "text.clipped",
        "text.overflow",
        "layout.clipped_content",
        "layout.zero_area",
    ):
        family = "visible_content_loss"
    return dict(
        code=code,
        category=cat,
        degree=degree,
        factor=DEGREES[degree],
        confirmed=confirmed,
        info=info,
        gate=gate,
        components=targets,
        root=f.get("root_cause_id") or f.get("rootCauseId"),
        family=family,
        message=(
            "评分提示：拨号未提供号码，按当前口径不扣分；不代表真实拨号已验证。原记录："
            if phone_number_note
            else ""
        )
        + f.get("message", code),
        evidence=f.get("evidence", {}),
        original_priority=f.get("priority") or f.get("severity"),
        origin=origin,
    )


def score(findings, reject=False, only_visual=False):
    groups, unknown, notes = {}, [], []
    certain_gate, possible_gate = reject, reject
    for f in findings:
        if f["info"]:
            notes.append(f)
            continue
        if only_visual and f["category"] == "function":
            continue
        if f["gate"]:
            certain_gate |= f["confirmed"]
            possible_gate = True
        if f["category"] is None:
            unknown.append(f)
            continue
        group = f["root"] or f"{f['category']}:{f['family']}:{','.join(sorted(f['components']))}"
        groups.setdefault(group, []).append(f)
    counted = []
    for group, fs in groups.items():
        chosen = max(fs, key=lambda f: WEIGHTS[f["category"]] * f["factor"])
        confirmed = [f for f in fs if f["confirmed"]]
        certain = (
            max(confirmed, key=lambda f: WEIGHTS[f["category"]] * f["factor"])
            if confirmed
            else None
        )
        counted.append(
            dict(
                group=group,
                category=chosen["category"],
                possible_factor=chosen["factor"],
                confirmed_category=certain["category"] if certain else None,
                confirmed_factor=certain["factor"] if certain else 0,
                findings=fs,
            )
        )
    breakdown = []
    for cat, weight in WEIGHTS.items():
        certain = min(
            1, sum(g["confirmed_factor"] for g in counted if g["confirmed_category"] == cat)
        )
        possible = min(1, sum(g["possible_factor"] for g in counted if g["category"] == cat))
        breakdown.append(
            dict(
                category=cat,
                name=NAMES[cat],
                weight=weight,
                confirmed_deduction=round(100 * weight * certain, 2),
                possible_deduction=round(100 * weight * possible, 2),
            )
        )
    high = 0 if certain_gate else round(100 - sum(x["confirmed_deduction"] for x in breakdown), 2)
    low = 0 if possible_gate else round(100 - sum(x["possible_deduction"] for x in breakdown), 2)
    if unknown and not certain_gate:
        high = low = None
    return dict(
        score=high,
        range=[low, high] if high is not None else None,
        breakdown=breakdown,
        groups=counted,
        notes=notes,
        unmapped=unknown,
        hard_reject=certain_gate,
        confirmed_groups=sum(g["confirmed_factor"] > 0 for g in counted),
        pending_groups=sum(any(not f["confirmed"] for f in g["findings"]) for g in counted),
    )


def policy():
    """返回参数副本，调用者不得改变共享计算参数。"""
    return copy.deepcopy(_POLICY)


def policy_digest():
    serialized = json.dumps(_POLICY, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def evaluation_document():
    """把唯一参数块展开成 Markdown 表格；不维护第二份权重或规则文案。"""
    document = Path(__file__).with_name("EVALUATION.md").read_text(encoding="utf-8")
    before, remainder = document.split(_POLICY_START, 1)
    _, after = remainder.split(_POLICY_END, 1)
    rows = ["| 维度 | 权重 |", "| --- | ---: |"]
    for key, weight in WEIGHTS.items():
        rows.append(f"| {NAMES.get(key)}（{key}） | {weight} |")
    rows.extend(["", "| 严重程度 | 系数 |", "| --- | ---: |"])
    for key, factor in DEGREES.items():
        rows.append(f"| {key} | {factor} |")
    rows.extend(["", "| 规则 | 分类 | 严重程度 | 默认确认 |", "| --- | --- | --- | --- |"])
    for code, (category, degree, confirmed) in RULES.items():
        rows.append(f"| {code} | {NAMES.get(category)} | {degree} | {confirmed} |")
    rows.extend(["", "| 有序前缀（优先命中） | 分类 |", "| --- | --- |"])
    for item in _POLICY.get("prefix_rules", []):
        prefixes = "、".join(item.get("prefixes", []))
        rows.append(f"| {prefixes} | {NAMES.get(item.get('category'))} |")
    rows.append("\n前缀规则严重程度由记录推导；P2/P3 为 minor，其余为 medium，证据已证实才确认。")
    return before + "\n".join(rows) + after
