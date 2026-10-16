# -*- coding: utf-8 -*-
"""queryfunc_screen 核心工具 —— DSL 加载 / 结构检查 / 功能检查(基于 query) / OCR / 截图查找。

完全独立, 不依赖 step1_screen.py, 可在任何机器复用。
所有路径由调用方传入, 本模块不硬编码任何数据集路径。

DSL 声明层需求检查:
  ① event 意图: query 的 matched_actions 物化出的 intentName ↔ DSL onClick 的 intentName
  ② data 写入: query 的 data_capability_ids ↔ DSL updateDataModel.value.data 的域名
  OCR 仅覆盖能可靠解析的文本；复杂表达式、列表上下文与数字另记缺口。
"""

import glob
import json
import os
import re
from pathlib import Path

# ============================================================
# 能力 -> 数据域名候选(任一候选域名命中 DSL data 即视为该能力已写入)
# ============================================================
CAP_DOMAIN = {
    # 6.0 数据能力
    "ViewWeather": ("weather",),
    "GetCalendarEvents": ("calendar",),
    "GetHealthAndSportSummary": ("healthSport", "health", "sport"),
    "GetPhoneBatteryInfo": ("battery", "phoneBattery"),
    "GetEarphoneInfo": ("earphone",),
    "GetCountdownDays": ("countdown",),
    "GetAppUsageDuration": ("appUsageStats",),
    # 7.0 数据能力(含 rom7 短域名)
    "GetMemoData": ("memo", "memoData", "notes"),
    "GetPhoneCallRecords": ("phoneCallRecords", "callRecords", "phoneCall", "call", "calls"),
    "GetCurrentTime": ("currentTime", "time", "clock"),
    "GetAppPowerConsumptionRanking": (
        "appPowerConsumptionRanking",
        "powerConsumptionRanking",
        "powerConsumption",
        "power",
    ),
    "GetDailyMostUsage": ("dailyMostUsage", "mostUsedApps", "appUsage", "usage"),
}


def extend_cap_domain(extra):
    """合并额外的能力域名映射(数据集自定义)。"""
    for k, v in extra.items():
        cur = CAP_DOMAIN.get(k, ())
        CAP_DOMAIN[k] = tuple(cur) + tuple(v) if isinstance(v, list | tuple) else tuple(cur)


# ============================================================
# matched_actions 短语 -> 期望 intent(用于 req_source=matched_actions)
# 从 natural-queries.json 的 matched_actions 文本匹配短语提取需求意图。
# 空元组 () 表示纯查询展示, 不要求交互 intent。
# ============================================================
MA_INTENT = {
    "拨打电话": ("CallPhone",),
    "跳转去导航": ("StartNavigate",),
    "跳转到备忘录": ("ViewNote",),
    "跳转到相机界面": ("OpenCamera",),
    "跳转到每日30首和收藏页面": ("Music",),
    "跳转音乐首页": ("Music",),
    "跳转日程": ("ViewCalendarEvent",),
    "跳转到电池设置页面": ("Settings",),
    "跳转闹钟": ("Clock",),
    "跳具体的tab页（跳转世界时钟、秒表、计时器）": ("Clock",),
    "跳转锻炼时长页": ("Health",),
    "跳转睡眠页": ("Health",),
    "跳转运动健康首页": ("Health",),
    "模式切换（免打扰、睡眠、学习）": ("Settings", "SetSettingSwitch"),
    "开启专注免打扰开关": ("Settings", "SetSettingSwitch"),
    "一键开启省电模式": ("Settings", "SetSettingSwitch"),
    "welink一键入会": ("EnterMeeting",),
    "跳到设置健康使用设备页面": ("Settings",),
    # 纯查询展示, 不要求 intent
    "查询天气状况": (),
    "查询日程": (),
}


def action_phrases(ma_text):
    if isinstance(ma_text, list):
        if not all(isinstance(x, str) for x in ma_text):
            raise ValueError("matched_actions 必须为字符串或字符串列表")
        return [x.strip() for x in ma_text if x.strip()]
    if not isinstance(ma_text, str):
        raise ValueError("matched_actions 必须为字符串或字符串列表")
    return [p.strip() for p in re.split(r"[；;\n]", ma_text) if p.strip()]


def matched_action_requirements(ma_text):
    """从 matched_actions 文本解析需求 intent 集合 + 是否有交互需求。
    返回 (req_intents:set, has_interact:bool)。"""
    req, has_interact = set(), False
    for phrase in action_phrases(ma_text):
        for key, ints in MA_INTENT.items():
            if key in phrase:
                req |= set(ints)
                if ints:
                    has_interact = True
    return req, has_interact


# ============================================================
# DSL 加载(兼容单行 JSON 数组 + 多行 JSONL)
# ============================================================
def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("JSON 对象存在重复键")
            result[key] = value
        return result

    def invalid(_):
        raise ValueError("JSON 包含非有限数值")

    return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid)


def parse_actions(txt, nested=False):
    txt = txt.lstrip("\ufeff")
    try:
        data = strict_json(txt)
    except json.JSONDecodeError:
        return [strict_json(line) for line in txt.splitlines() if line.strip()]
    if isinstance(data, dict) and "genui" in data:
        if nested:
            raise ValueError("不支持多层 genui 包装")
        if "cardSpec" in data and not isinstance(data["cardSpec"], dict):
            raise ValueError("cardSpec 必须是对象")
        value = data["genui"]
        if isinstance(value, str):
            return parse_actions(value, True)
        if isinstance(value, list):
            return value
        raise ValueError("genui 必须是消息文本或数组")
    return data if isinstance(data, list) else [data]


def load_actions(path):
    """Read JSON array / JSONL / genui+cardSpec bundle without changing bytes."""
    return parse_actions(Path(path).read_text(encoding="utf-8-sig"))


def get_components(actions):
    for a in actions:
        if isinstance(a, dict) and "updateComponents" in a:
            return a["updateComponents"].get("components", [])
    return []


def get_data_model(actions):
    for a in actions:
        if isinstance(a, dict) and "updateDataModel" in a:
            return a["updateDataModel"]
    return None


def flatten_values(o, out):
    if isinstance(o, dict):
        for v in o.values():
            flatten_values(v, out)
    elif isinstance(o, list):
        for v in o:
            flatten_values(v, out)
    elif isinstance(o, str | int | float):
        out.append(str(o))


def extract_domain(dm):
    """从 updateDataModel 提取数据域名集合(value.data 的键)。"""
    if not dm:
        return set()
    val = dm.get("value", {})
    data = val.get("data", {}) if isinstance(val, dict) else {}
    return set(data.keys()) if isinstance(data, dict) else set()


def intent_names(comps):
    """从组件 onClick 提取 intentName 集合。"""
    names = set()
    for c in comps:
        clicks = c.get("onClick") or []
        if isinstance(clicks, dict):
            clicks = [clicks]
        if not isinstance(clicks, list):
            continue
        for oc in clicks:
            if not isinstance(oc, dict) or not isinstance(oc.get("args", {}), dict):
                continue
            nm = oc.get("args", {}).get("intentName")
            if isinstance(nm, str) and nm:
                names.add(nm)
    return names


# ============================================================
# 结构检查(List children 兼容 dict 绑定 / list 引用)
# ============================================================
_FILL = ("matchParent", "fillParent", "matchparent", "fillparent")


def _edit_dist1(a, b):
    """编辑距离 <=1 (用于近拼写笔误识别)。"""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b, strict=False)) <= 1
    short, long = (a, b) if len(a) < len(b) else (b, a)
    for i in range(len(long)):
        if short == long[:i] + long[i + 1 :]:
            return True
    return False


def check_structure(actions):
    """结构检测。返回 (ok, issues, comps, soft)。
    List/Loop 组件 children 是 dict 绑定{componentId,path,itemVar}时, 只校验 componentId 存在;
    children 是 list 时, 校验每个引用 id 存在。"""
    issues, soft = [], []
    if not isinstance(actions, list) or not actions:
        return False, ["DSL为空"], [], []
    acts, comps, updates = set(), [], []
    for r in actions:
        if not isinstance(r, dict):
            issues.append("消息非对象")
            continue
        for op in ("createSurface", "updateComponents", "updateDataModel"):
            if op in r and not isinstance(r[op], dict):
                issues.append(op + " 非对象")
        if r.get("version") != "v0.9":
            soft.append(f"待复核协议版本={r.get('version')}")
        for k in r:
            if k == "updateComponents":
                if not isinstance(r[k], dict):
                    issues.append("updateComponents 非对象")
                    continue
                updates.append(r[k])
                comps = r[k].get("components", [])
            acts.add(k)
    for need in ("createSurface", "updateComponents", "updateDataModel"):
        if need not in acts:
            issues.append(f"缺{need}")
    if len(updates) != 1 or len(actions) != 3:
        soft.append("待复核多消息/增量更新格式，未执行完整状态归并")
    if not isinstance(comps, list) or not comps or not all(isinstance(c, dict) for c in comps):
        return False, issues + ["组件列表为空或类型错误"], [], soft
    if any(not isinstance(c.get("id"), str) or not c["id"] for c in comps):
        return False, issues + ["组件 ID 缺失或不是字符串"], [], soft
    ids = {c.get("id") for c in comps}
    if len(ids) != len(comps):
        issues.append("组件 ID 重复")
    graph = {}
    for c in comps:
        ch = c.get("children")
        if isinstance(ch, dict):
            # List/Loop 绑定: {componentId, path, itemVar}; 只校验 componentId 指向的模板组件存在
            tmpl = ch.get("componentId")
            if not isinstance(tmpl, str):
                soft.append("待复核列表模板绑定格式")
                continue
            if tmpl and tmpl not in ids:
                near = [i for i in ids if _edit_dist1(tmpl, i)]
                if near:
                    soft.append(f"List模板引用笔误:{c.get('id')}->'{tmpl}'(应为{near[0]})")
                else:
                    issues.append(f"List模板悬空:{c.get('id')}->{tmpl}")
            graph[c["id"]] = [tmpl] if tmpl in ids else []
            continue
        if isinstance(ch, list):
            for child in ch:
                if not isinstance(child, str):
                    soft.append("待复核非字符串子节点引用")
                    continue
                if child not in ids:
                    near = [i for i in ids if _edit_dist1(child, i)]
                    if near:
                        soft.append(f"引用拼写笔误:{c.get('id')}->'{child}'(应为{near[0]})")
                    else:
                        issues.append(f"悬空引用:{c.get('id')}->{child}")
            graph[c["id"]] = [x for x in ch if isinstance(x, str) and x in ids]
        elif ch is not None:
            soft.append("待复核 children 字段类型")
    if len(updates) == 1:
        root = updates[0].get("root", "root")
        if not isinstance(root, str) or root not in ids:
            issues.append("根组件引用不存在")
    # Iterative DFS avoids recursion limits on malformed deep graphs.
    state = {}
    for start in graph:
        if state.get(start):
            continue
        stack = [(start, False)]
        while stack:
            node, leaving = stack.pop()
            if leaving:
                state[node] = 2
                continue
            if state.get(node) == 1:
                issues.append("组件引用形成循环")
                stack.clear()
                break
            if state.get(node) == 2:
                continue
            state[node] = 1
            stack.append((node, True))
            stack.extend((child, False) for child in graph.get(node, []))
    return (not issues), issues, comps, soft


# ============================================================
# 功能检查(query-based) —— 不看 cardspec 主题词, 看 query 真实需求
# ============================================================
def check_function_intent(actions, comps, req_intents, data_caps, domains_map=None):
    """对照物化的 intentName 列表 + 数据能力列表判功能缺失。
    actions:     DSL 三条消息(用于提取 data model)
    comps:       组件列表(用于提取 onClick intent)
    req_intents: list of (intentName, evidence) —— 来自 all-cards.jsonl 的 actions[].args.intentName
    data_caps:   list of capability id —— 来自 query 的 data_capability_ids
    返回 (issues, missing_intents, missing_data_caps)。"""
    issues = []
    intents = intent_names(comps)
    domains = extract_domain(get_data_model(actions))
    # ① 缺意图
    missing_intents = [(it, ev) for it, ev in req_intents if it and it not in intents]
    if missing_intents:
        issues.append("缺意图:" + "; ".join(f"{it}({ev})" for it, ev in missing_intents))
    # ② 缺数据域(任一候选域名命中即 OK)
    missing_data_caps = []
    for c in data_caps:
        cand = (domains_map or CAP_DOMAIN).get(c, ())
        if cand and not (set(cand) & domains):
            missing_data_caps.append(c)
    if missing_data_caps:
        issues.append(
            "缺数据域:" + ",".join(missing_data_caps) + f"(实际:{sorted(domains) or '空'})"
        )
    return issues, missing_intents, missing_data_caps


def check_function_ma(actions, comps, matched_actions_text, data_caps, domains_map=None):
    """对照 matched_actions 文本(短语表) + 数据能力列表判功能缺失。
    actions:              DSL 三条消息(用于提取 data model)
    comps:                组件列表(用于提取 onClick intent)
    matched_actions_text: query 的 matched_actions 字段文本
    返回 (issues, missing_intents, missing_data_caps)。"""
    issues = []
    req, has_interact = matched_action_requirements(matched_actions_text)
    intents = intent_names(comps)
    domains = extract_domain(get_data_model(actions))
    if has_interact:
        missing = req - intents
        if missing:
            issues.append(
                f"matched需求需{('/'.join(sorted(missing)))}但DSL无对应intent"
                f"(实际:{sorted(intents) or '空'})"
            )
            missing_intents = [(it, "") for it in sorted(missing)]
        else:
            missing_intents = []
    else:
        missing_intents = []
    missing_data_caps = []
    for c in data_caps:
        cand = (domains_map or CAP_DOMAIN).get(c, ())
        if cand and not (set(cand) & domains):
            missing_data_caps.append(c)
    if missing_data_caps:
        issues.append(
            "缺数据域:" + ",".join(missing_data_caps) + f"(实际:{sorted(domains) or '空'})"
        )
    return issues, missing_intents, missing_data_caps


# ============================================================
# 文本语义检查
# ============================================================
_SAFE_TEXT = re.compile(r"[^\u4e00-\u9fffA-Za-z0-9\s，。、：；！？·（）()【】《》" "''—…/+%.℃°-]")


def check_text_semantics(comps):
    """检测 DSL 静态文本是否含异常乱码字符。"""
    issues = []
    for c in comps:
        if c.get("component") != "Text":
            continue
        content = str(c.get("content") or "").strip()
        if not content or "{{" in content:
            continue
        bad = _SAFE_TEXT.findall(content)
        if bad:
            issues.append(f"文案含异常字符: {content!r} -> {''.join(set(bad))}")
    return issues


# ============================================================
# OCR 文字完整性
# ============================================================
_ocr = None


class OCREngine:
    def __init__(self):
        from rapidocr_onnxruntime import RapidOCR

        self.ocr = RapidOCR()

    def recognize(self, img):
        res, _ = self.ocr(img)
        if not res:
            return []
        return [t for (_b, t, _s) in res]


def get_ocr():
    global _ocr
    if _ocr is None:
        _ocr = OCREngine()
    return _ocr


def normalize(s):
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", s)


TEMPLATE_RE = re.compile(r"\$\{([^}]+)\}")


def resolve_template(content, dm_value):
    """把 Text 模板(如 '{{ ${/data/weather/current/condition} }}') 解析为期望展示文本。"""
    expects = []
    # Only evaluate a complete, single direct path. Never execute expressions.
    match = re.fullmatch(r"\{\{\s*\$\{(/data/[A-Za-z0-9_/.]+)\}\s*\}\}", content)
    if match:
        val = extract_path(dm_value, match.group(1).lstrip("/"))
        if isinstance(val, str | int | float) and not isinstance(val, bool):
            expects.append(str(val))
    if "{{" not in content:
        expects.append(content.strip())
    return expects


def extract_path(dm_value, path):
    cur = dm_value
    for tok in path.split("/"):
        if not tok:
            continue
        if isinstance(cur, dict) and tok in cur:
            cur = cur[tok]
        elif isinstance(cur, list) and tok.isdigit() and int(tok) < len(cur):
            cur = cur[int(tok)]
        else:
            return None
    return cur


def declared_display_texts(actions):
    """DSL 明确声明要展示的文本 = 静态Text文案 + 模板解析出的数据值。"""
    comps = get_components(actions)
    dm = get_data_model(actions)
    expects = []
    for c in comps:
        if c.get("component") != "Text":
            continue
        content = c.get("content")
        if not content:
            continue
        expects += resolve_template(str(content), (dm or {}).get("value", {}) if dm else {})
    return [e for e in expects if e]


def ocr_expectations(actions):
    texts, unmeasured = [], []
    dm = get_data_model(actions)
    value = dm.get("value", {}) if isinstance(dm, dict) else {}
    for comp in get_components(actions):
        if comp.get("component") != "Text":
            continue
        content = comp.get("content")
        if content is None or content == "":
            continue
        resolved = resolve_template(str(content), value)
        if not resolved:
            unmeasured.append(comp.get("id"))
        for text in resolved:
            norm = normalize(text)
            if len(norm) >= 2 and re.search(r"[\u4e00-\u9fff]", norm):
                texts.append(text)
            else:
                unmeasured.append(comp.get("id"))
    return texts, sorted(set(unmeasured))


def check_ocr(img_path, actions):
    """Reuse OCR matching as a clue, never as sole evidence for rejection."""
    issues = []
    if not img_path or not os.path.exists(img_path):
        return ["[未检查·截图缺失]"]
    expects, unmeasured = ocr_expectations(actions)
    if not expects:
        return ["[未检查·无可可靠匹配的文本]"]
    try:
        text = get_ocr().recognize(img_path)
    except Exception as e:
        return [f"[检测失败·OCR]{type(e).__name__}"]
    text_n = " ".join(normalize(t) for t in text)
    for exp in expects:
        if not exp:
            continue
        e_n = normalize(exp)
        if len(e_n) < 2:
            continue
        is_strong = any("\u4e00" <= ch <= "\u9fff" for ch in e_n)
        if not is_strong:
            continue  # 纯数字/时间/温度格式多变, 跳过避免误报
        if e_n in text_n:
            continue
        chars = [ch for ch in e_n if "\u4e00" <= ch <= "\u9fff"]
        if not chars:
            continue
        found = sum(1 for ch in chars if ch in text_n)
        ratio = found / len(chars)
        if ratio >= 0.6:
            issues.append(
                f"[可微调·文字截断] '{exp}'在截图OCR部分命中({int(ratio * 100)}%), 疑似被裁"
            )
        elif ratio >= 0.3:
            issues.append(f"[待复核·文字缺失] '{exp}'在截图OCR仅命中{int(ratio * 100)}%")
        else:
            issues.append(
                f"[待复核·关键内容缺失] '{exp}'在截图OCR基本未找到；不能仅据此认定渲染失败"
            )
    if unmeasured:
        issues.append("[未检查·部分文本]数字、短文本、列表上下文或复杂表达式需后续原生测量")
    return issues


# ============================================================
# 截图查找(多目录 + 模板, 支持 glob 通配)
# ============================================================
def make_sshot_finder(dirs, template):
    """返回 find(cid) -> 截图路径 or None。
    template 支持 {cid} 占位 + glob 通配符(如 {cid}-*.jpeg)。"""

    def find(cid):
        hits = set()
        for d in dirs:
            pattern = template.format(cid=cid)
            # 若 template 含通配符, 用 glob 搜; 否则直接拼路径
            if any(ch in pattern for ch in "*?["):
                hits.update(
                    str(Path(p).resolve())
                    for p in glob.glob(os.path.join(d, pattern))
                    if Path(p).is_file()
                )
            else:
                p = os.path.join(d, pattern)
                if os.path.exists(p):
                    hits.add(str(Path(p).resolve()))
        if len(hits) > 1:
            raise ValueError("文件匹配不唯一，请缩小目录或文件名模式")
        return next(iter(hits), None)

    return find
