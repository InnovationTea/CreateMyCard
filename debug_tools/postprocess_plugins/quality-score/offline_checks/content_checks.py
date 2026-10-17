"""Content checks shared by initial screening and full quality audit.

Rules produce evidence, not a universal natural-language correctness claim.
"""

import re

PLACEHOLDER = re.compile(r"待接入|待补充|能力待|尚未实现|功能未实现|TODO|TBD", re.I)
PATH = re.compile(r"\$\{(/[^{}]+)\}")


def strings(value, pointer=""):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from strings(
                child, pointer + "/" + str(key).replace("~", "~0").replace("/", "~1")
            )
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from strings(child, pointer + "/" + str(index))
    elif isinstance(value, str):
        yield pointer, value


def at(value, path):
    for part in path.strip("/").split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict):
            if part not in value:
                raise KeyError(path)
            value = value.get(part)
        elif isinstance(value, list) and part.isdigit():
            value = value[int(part)]
        else:
            raise KeyError(path)
    return value


def content_findings(actions, spec, query="", provenance=None):
    findings = []

    def add(code, level, message, evidence):
        findings.append(dict(code=code, level=level, message=message, evidence=evidence))

    comps, models = [], []
    for action in actions:
        if not isinstance(action, dict):
            continue
        update = action.get("updateComponents")
        if isinstance(update, dict):
            comps.extend(update.get("components", []))
        data = action.get("updateDataModel")
        if isinstance(data, dict):
            models.append(data)
    model = (
        models[0].get("value", {})
        if len(models) == 1 and models[0].get("path", "/") == "/"
        else None
    )
    displayed = [
        (c.get("id"), c.get("content", c.get("label", "")))
        for c in comps
        if c.get("component") in ("Text", "Button")
    ]
    unfinished = [
        dict(component=cid, text=text)
        for cid, text in displayed
        if isinstance(text, str) and "{{" not in text and PLACEHOLDER.search(text)
    ]
    if unfinished:
        # A declared integration placeholder is different from an empty/loading runtime state.
        add(
            "content.integration_placeholder",
            "reject"
            if not spec.get("dataBindings") and not (model or {}).get("data")
            else "review",
            "可见内容包含尚未完成的能力接入占位；需回到生成端处理",
            unfinished,
        )
    ambiguous = [
        dict(component=cid, text=text)
        for cid, text in displayed
        if text in ("待确认", "暂无数据", "加载中")
    ]
    if ambiguous:
        add(
            "content.state_needs_context",
            "review",
            "需核对这是否是需求明确要求的空态/加载态",
            ambiguous,
        )
    development = [
        dict(component=cid, text=text)
        for cid, text in displayed
        if isinstance(text, str)
        and re.fullmatch(r".{0,12}入口未声明|保留一个主(?:入口|动作)", text)
    ]
    if development:
        add(
            "content.development_note",
            "repair_required",
            "可见文案仍是生成或实现阶段说明，不是业务内容；需先核对真实缺项再修复",
            development,
        )
    static_pending = [
        dict(component=cid, text=text)
        for cid, text in displayed
        if isinstance(text, str) and "{{" not in text and "待同步" in text
    ]
    if static_pending:
        add(
            "content.static_pending_state",
            "review",
            "待同步状态写死在组件中；须确认空态需求及状态变化逻辑",
            static_pending,
        )
    preview_states = []
    if model is not None:
        for cid, text in displayed:
            if not isinstance(text, str):
                continue
            for path in PATH.findall(text):
                try:
                    value = at(model, path)
                except (KeyError, IndexError, TypeError):
                    continue
                if isinstance(value, str) and value in (
                    "待同步",
                    "待确认",
                    "数据待更新",
                    "尚未同步",
                ):
                    preview_states.append(dict(component=cid, path=path, value=value))
    if preview_states:
        add(
            "content.preview_state_needs_context",
            "review",
            "动态预览字段仍为待同步等占位；需证明是合法空态样本，不能仅因字段有绑定就放行",
            preview_states,
        )
    static_examples = [
        dict(component=cid, text=text)
        for cid, text in displayed
        if isinstance(text, str)
        and "{{" not in text
        and re.search(r"示例|测试数据|example", text, re.I)
    ]
    if static_examples:
        add(
            "content.static_example",
            "review",
            "可见组件写死示例文案，需核对是否为合法演示需求",
            static_examples,
        )
    if model is None:
        add("binding.incremental_model", "pending", "当前检查未合并多次/非根 DataModel 更新", {})
    else:
        for comp in comps:
            for pointer, text in strings(comp):
                for path in PATH.findall(text):
                    try:
                        at(model, path)
                    except (KeyError, IndexError, TypeError):
                        add(
                            "binding.unresolved_path",
                            "repair_required",
                            "DSL 引用在初始数据模型中不存在，需核对空数组/缺字段处理",
                            dict(component=comp.get("id"), pointer=pointer, path=path),
                        )
    for comp in comps:
        if (
            comp.get("component") == "Button"
            and not comp.get("onClick")
            and (comp.get("styles") or {}).get("enabled") is not False
        ):
            add(
                "event.button_without_action",
                "review",
                "按钮未声明 onClick；核对父级事件及禁用状态",
                dict(component=comp.get("id")),
            )
        for handler in comp.get("onClick", []) if isinstance(comp.get("onClick", []), list) else []:
            args = handler.get("args", {}) if isinstance(handler, dict) else {}
            params = args.get("params", {}) if isinstance(args, dict) else {}
            is_phone = isinstance(args, dict) and args.get("intentName") == "CallPhone"
            if is_phone and isinstance(params, dict) and params.get("phoneNumber") == "":
                add(
                    "event.phone_target_unresolved",
                    "review",
                    "拨号号码为空；需确认需求是打开拨号界面还是拨给指定对象，"
                    "不能默认已实现回拨/联系人拨号",
                    dict(component=comp.get("id")),
                )
    if provenance and provenance.get("degradations"):
        add(
            "semantic.upstream_degradation",
            "review",
            "上游已声明降级；需逐项核对 Query 是否仍被完整满足",
            provenance.get("degradations"),
        )
    # ponytail: 只覆盖明确短语线索；完整语义判断需另接可信评估器。
    requirements = [
        ("charging_case", r"充电盒.{0,8}电量|耳机和充电盒", r"case|box|充电盒", "充电盒电量"),
        (
            "location",
            r"显示当前位置|看看当前位置|查看当前位置",
            r"latitude|longitude|currentLocation|当前位置",
            "当前位置",
        ),
        ("feels_like", r"体感温度", r"feelsLike|apparentTemp|体感", "体感温度"),
        ("weather", r"显示.{0,8}天气|看看.{0,8}天气|当地天气", r"/weather[/}]|天气", "天气"),
    ]
    visible = " ".join(t for _, t in displayed if isinstance(t, str))
    for requirement, trigger, output, label in requirements:
        checked_query = query
        if requirement == "location":
            # “显示当前位置今天到未来三天的天气”只要求本地天气，不要求独立位置面板。
            checked_query = re.sub(
                r"显示当前位置(?:今天到未来三天|今天|未来三天|的)?的?天气", "显示当地天气", query
            )
        if re.search(trigger, checked_query) and not re.search(output, visible, re.I):
            add(
                "semantic.required_display_unproven",
                "review",
                "未找到明确要求的“" + label + "”展示证据",
                dict(requirement=requirement, query=query),
            )
    action_texts = []
    for comp in comps:
        for _, text in strings(comp.get("onClick", [])):
            action_texts.append(text)
    actions_text = " ".join(action_texts)
    event_rules = [
        ("直接入会|一键入会", "EnterMeeting", "入会"),
        ("点开日程|查看日程详情", "ViewCalendarEvent", "日程详情"),
        ("跳转.{0,4}闹钟|打开闹钟", "Clock", "闹钟"),
        ("打开相机|直达.{0,4}拍摄", "OpenCamera", "相机"),
    ]
    for trigger, intent, label in event_rules:
        if re.search(trigger, query) and intent not in actions_text:
            add(
                "semantic.required_action_unproven",
                "review",
                "未找到 Query 要求的“" + label + "”动作声明",
                dict(expected_intent=intent),
            )
    return findings
