from __future__ import annotations

import json
from typing import Any

from .card_sizes import CARD_SIZE_DIMENSIONS


LAYOUT_FALLBACK_PROMPTS = {
    "compact_component": """当前 JSX 已达到浏览器布局修复的切换条件，现在进入紧凑组件替换阶段。

请根据最后一次浏览器 findings 重新组织布局，并将放不下的文本类组件替换为语义兼容、占位更小的安全组件。

必须保留：
- 所有用户要求的业务事实；
- 所有已使用的 dataIds；
- 所有 actionId；
- 动态数据绑定关系。

允许：
- 更换更为尺寸更小的其他组件或文本组件；
- 当最后一次 findings 的 `browser-semantic-overlap` 涉及 `EmphasizedData` 时，先复核业务语义；若内容是可无损保留的短文本、状态或完整格式化字符串，优先尝试替换为 `EmphasisText`。有真实且必要的第二个文本字段时填写 `secondaryText`，否则省略。原 `value` 的完整可见内容与 `dataIds.value` 必须分别迁移到 `mainText` 与 `dataIds.mainText`；不得丢失、拆分或静态化动态值；
- 两条日程必须合并在一个 EventCard.items 中，由组件自适应分配条目间距，不得生成两个 EventCard；高度不足时在这个组件上改用 density="compact"，并完整保留每条事件的 title、time、location 和全部 dataIds；紧凑日程组优先放入 140vp 连续内容区，不放入 118vp 子槽；
- 合并语义相近的辅助字段；
- 更换 Layout Pattern 或 Sub Pattern；
- 2x2 可调整 Stack 的 direction、width、height、flex 和 gap；2x4 只通过 layout/variant 更换语义外壳和内容槽，禁止提交 Stack/Grid；多个紧凑占比使用 NumericRatioStack。

禁止：
- 删除信息或 Action；
- 把动态数据改成静态文本；
- 将纯数值单位、进度关系或按业务规则应使用 `EventCard` 的日程事件，仅为消除重叠而从 `EmphasizedData` 替换成 `EmphasisText`；
- 使用省略号、裁剪或 overflow 隐藏问题。

完成后调用 submit_card_jsx 提交完整 JSX。""",
    "drop_optional_component": """紧凑组件替换后仍未通过浏览器校验，现在允许删除一个最低优先级的业务显示组件。

删除顺序：
1. 与核心任务关系最弱的信息；
2. 辅助说明、更新时间、来源等次要信息；
3. 对主要任务影响最小的补充属性。

必须满足：
- 最多删除一个业务显示组件；
- 允许删除 Info Plan 中的非 Action 信息；删除后本次结果记为 partial；
- 不得删除任何 Action；
- 不得把被删除的动态数据改成无绑定的静态文本；
- 建议将省略事实在 Plan 中对应的 requirement 原文逐项写入 unmetRequirements，供产物说明使用；是否填写不影响 drop 阶段放行。

后续重试只能重新分配剩余内容的空间，不得再删除第二个业务显示组件。
完成后调用 submit_card_jsx 提交完整 JSX。""",
}


def build_layout_fallback_prompt(strategy: str) -> str:
    try:
        return LAYOUT_FALLBACK_PROMPTS[strategy]
    except KeyError as exc:
        raise ValueError(f"unsupported layout fallback strategy: {strategy!r}") from exc


def build_plan_prompt() -> str:
    return (
        "本轮不要生成 JSX，也不要选择布局，只调用 submit_card_plan 提交 Info Plan。"
        "按照已读取的 info_process 规则，将用户要求展示的内容拆成原子事实；"
        "每项填写 requirement，并在真实 dataId、actionId 或用户原文静态 text 中恰好选择一个目标。"
        "动态信息必须使用真实 dataId；多个对象的标题、时间、地点等属性必须逐项列出，不能用一句话代替。"
        "输入 actions 中用户要求的每个动作都必须作为 actionId 事实保留。"
        "不要加入仅供操作传参的字段、内部标识、背景数据或与 userQuery 无关的信息，也不要填写空字符串或 null。"
        "用户明确给出的值与样例不同时，可在对应 dataId 事实中填写 initialValue 和 valueSourceQuote；"
        "用户未给具体值时省略二者，不得把样例值改成静态 text。"
        "可在每个事实的 componentHints 中按优先级填写一至多个组件软候选。候选必须能通过可绑定 Prop 承载该事实；"
        "同一组件同时出现在多项事实中表示这些事实可由一个组件合并展示，不表示生成多个实例。"
        "componentHints 只辅助后续选组件，不冻结组件，也不包含 Stack、布局名称、Region、对齐或尺寸。"
        "当同一事件集合包含三条或更多日程且候选组件为 EventCard 时，info_required 最多选择两个完整事件对象，"
        "最终由同一个 EventCard.items 承载；每个选中事件应成组保留标题、时间和可用地点，"
        "不得选择第三个事件的部分字段，也不得规划第二个 EventCard。优先保留用户明确点名的事件，"
        "其余按时间先后选择。"
        "先判断事实是核心、补充说明还是同级属性，再依据 component_style 选择候选；"
        "不得为了紧凑把核心信息降级为无层级的属性列表。"
        "多日天气清单的同一天同时提供完整日期和星期时，只把星期列为必需事实；完整日期保留为可选输入，"
        "不要同时冻结两种重复的日期标识。"
        "提交前逐句核对 userQuery 的对象、数量、日期范围、信息和操作，确保无遗漏。"
        "整个工具参数尽量控制在 1024 tokens 内，并闭合为合法 JSON。"
    )


def build_plan_context(plan: dict[str, Any]) -> str:
    payload = json.dumps(plan, ensure_ascii=False, separators=(",", ":"))
    ownership: list[dict[str, Any]] = []
    for index, fact in enumerate(plan.get("info_required", []), start=1):
        if not isinstance(fact, dict):
            continue
        target = next(
            (
                (key, fact[key])
                for key in ("dataId", "actionId", "text")
                if key in fact and fact[key] not in (None, "")
            ),
            None,
        )
        if target is None:
            continue
        target_kind, target_value = target
        item = {
            "fact": index,
            "requirement": fact.get("requirement", ""),
            target_kind: target_value,
        }
        if fact.get("componentHints"):
            item["componentHints"] = fact["componentHints"]
        ownership.append(item)
    ownership_payload = json.dumps(ownership, ensure_ascii=False, separators=(",", ":"))
    return (
        "以下是已接受的 Info Plan。普通提交和紧凑组件兜底必须保留已选事实与绑定；"
        "只有 Runner 明确进入 drop_optional_component 阶段时才执行该阶段的专用省略规则。"
        "描述性文字不是必须逐字展示的正文。"
        "非 drop_optional_component 阶段不得通过修改 coverage 或 unmetRequirements 解除必需事实。"
        "initialValue 已作为对应 ID 的统一初始值。"
        "Info Plan 不冻结布局或具体组件；componentHints 只是软候选。"
        "每次 submit_card_jsx 都应根据当前完整内容重新选择 layoutPattern、subPattern/variant 和组件。"
        "2x4 的布局决定由 Runner 根据本轮 JSX 的 Card.layout/Region.variant 自动派生。修复时也可重新选择布局，"
        "但不得因此删除冻结事实或 Action。"
        "下方事实归属表只规定必须展示的原子事实及候选组件，不规定最终布局。"
        "生成 JSX 前，在内部为每项事实选择恰好一个可见 Prop 作为 owner；标题也是可见 owner。"
        "Info Plan 中以 text 声明的静态事实必须由不带同名 dataIds/dataValueMaps 的可见 Prop 承载；"
        "不得为了形式上补绑定而给静态文字分配无关 dataId。"
        "同时按已读取组件规则保留信息层级：普通多字段信息卡必须保留一个动态核心，静态类别标题不能替代核心；"
        "存在核心时不得把它降级到 TableText；多个补充字段按是否需要逐项标签选择一个 SecondaryBody 或一个 TableText，"
        "不得把三个及以上不同语义字段压入 EmphasisText.secondaryText；只有明确的列表、对比或等权查看意图才允许 TableText 成为唯一业务组件；"
        "同一语义分区内 EmphasisText 与 EmphasizedData 合计最多一个；2x4 语义 JSX 不允许用 Stack/Grid 包装内容。"
        "同一 dataId 不得为了凑足 SecondaryBody、TableText 等组件的最少条目数而再次展示；"
        "静态标题已经表达某项 text 事实时，也不要在正文重复。"
        "若正文 owner 展示地点名、设备名或事件名，静态标题必须使用不包含该值的类别概括；"
        "地点名、设备名、事件名等动态字段需要与静态标题后缀合并时，优先使用标题组件的 `*Template`，"
        "不要再增加一行正文重复该字段。若组件软候选与随后读取的 JSX 或布局规范冲突，以规范为准。\n"
        f"<required_fact_ownership>\n{ownership_payload}\n</required_fact_ownership>\n"
        f"<info_plan>\n{payload}\n</info_plan>"
    )


def build_system_prompt(
    component_name: str,
    card_size: str | None = None,
    *,
    validation_enabled: bool = True,
) -> str:
    if card_size in CARD_SIZE_DIMENSIONS:
        width, height = CARD_SIZE_DIMENSIONS[card_size]
        size_rule = (
            f'- 当前输入 size 为 "{card_size}"，根节点必须使用 '
            f'<Card size="{card_size}"> 并按 {width}x{height}vp 完成布局闭合。'
        )
    else:
        size_rule = (
            '- 根节点 Card.size 必须与输入顶层 size 完全一致：'
            '"2x2" 对应 150x150vp，"2x4" 对应 300x150vp。'
        )
    if card_size == "2x2":
        decision_rule = (
            '- submit_card_jsx.decision 只填写当前布局文档中的中文顶层名称，例如 '
            '{"layoutPattern":"标题单内容"}；2x2 不得填写 subPattern。'
        )
    elif card_size == "2x4":
        decision_rule = (
            '- 2x4 不填写 decision；程序根据 Card.layout 和每个 Region.variant 自动派生 '
            'layoutPattern 与 subPattern。模型只需保证语义 JSX 的布局标识与内容关系一致。'
        )
    else:
        decision_rule = (
            '- submit_card_jsx.decision.layoutPattern 必须使用当前尺寸布局文档中的中文名称；'
            '2x4 还必须按父区域填写 subPattern。'
        )
    validation_rule = (
        (
            "- JSX 提交后会立即经过语法、组件合同、资源、交互引用和静态布局校验；"
            "Runner 启用浏览器校验时，会追加真实渲染检查。"
            "若工具返回错误，必须按 findings 修复并重新提交。"
        )
        if validation_enabled
        else (
            "- 本次运行只接受第一次 JSX 提交，不会返回校验 findings 或安排修复轮次；"
            "请确保首次提交满足已读取合同。"
        )
    )
    lines = (
        "你是鸿蒙桌面卡片生成 Agent。你需要理解任务数据，选择必要信息和设计系统组件，"
        "最后生成符合当前组件合同的声明式 JSX。",
        "",
        "必须严格按以下顺序，每轮只调用一个工具：",
        "1. 读取 info_process：完成信息筛选与分组。",
        "2. 读取 component_style：了解可选组件及其绑定能力。",
        "3. 调用 submit_card_plan：只提交必要事实和组件软候选，不选择布局。",
        "4. 读取 jsx_contract：了解 JSX 与布局原语合同。",
        "5. 读取 layout_patterns：了解当前尺寸的布局与子布局规则。",
        (
            "6. 调用 submit_card_jsx：提交完整 JSX；程序从 Card.layout/Region.variant 自动派生 decision。"
            if card_size == "2x4" else
            "6. 调用 submit_card_jsx：同时提交本轮 decision 与完整 JSX。"
        ),
        "",
        (
            "调用 submit_card_jsx 时填写 jsx，不得重复填写 decision。"
            if card_size == "2x4" else
            "调用 submit_card_jsx 时先填写 decision，再填写 jsx。"
        )
        + "submit_card_jsx.jsx 只提交一个以 <Card> 为根的 JSX 表达式，"
        + "不要提交 function/import/export、Markdown 说明或代码围栏。"
        + "每次修复都可重新选择 layoutPattern 和 subPattern/variant；"
        +
        (
            "2x4 的 decision 随本轮语义 JSX 自动更新，不需要沿用上一版布局。"
            if card_size == "2x4" else
            "decision 只需与同一次提交的 JSX 一致，不需要沿用上一版布局。"
        ),
        "",
        "重要约束：",
        "- 只能使用 component_style 和 jsx_contract 中明确允许的组件与属性；"
        "组件用法以 component_style 为准，核心 JSX 与布局原语以 jsx_contract 为准。",
        (
            "- 2x4 使用 Card.layout + Region.slot/variant 提交布局，禁止在语义 JSX 中输出 Stack/Grid。"
            "程序从语义布局确定性派生中文 decision、统一展开外壳，再编译和浏览器校验。"
            "每个 Region 必须按 variant 直接放入规定数量的业务组件；需要核心与辅助上下分离时选择双内容 variant。"
            "多个紧凑占比使用 NumericRatioStack，并通过 direction 选择横排或纵排。"
            "修复仍提交语义 JSX，不编辑或复制程序展开后的 Stack/Grid 外壳。"
            "few-shot 同样使用语义提交，仅参考其信息组织与绑定，不照搬业务内容或布局组合。"
            if card_size == "2x4" else
            "- Card 与每个 Stack 必须显式填写 direction=\"column\" 或 direction=\"row\"；"
            "Stack/Grid 不得生成 basis 或 minWidth。固定槽使用 flex={0}，"
            "并按父容器 direction 显式填写主轴 width 或 height。"
        ),
        "- 任何 icon、src 或 checkIcon 只能逐字使用当前输入 `assetCandidates` 中已有的 `src`；"
        "根据候选的 description 选择语义匹配的资源，禁止编造、改写路径或补充目录前缀；"
        "候选列表为空时不得输出资源属性。",
        "- `userQuery` 是当前请求的意图和具体事实来源，`data[].value` 只是动态字段的预览样例。"
        "若 `userQuery` 明确给出了与某个单一数据字段同义的具体名称、地点、时间或状态，"
        "而其与样例值不同，可见 Prop 必须使用 `userQuery` 中的事实，同时仍绑定该字段的真实 `dataId`；"
        "不得为了跟随样例值而改写用户明确提供的事实。"
        "生成前必须在计划中按真实 dataId 明确 initialValue 和 valueSourceQuote；只在 JSX 中改字面量不会建立该字段的初始值。"
        "`userQuery` 未提供对应具体值时，才使用 `data[].value`。"
        "一个 Prop 绑定多个 `dataId` 时不得猜测如何把查询文本反向拆分到多个动态字段；不得虚构数据。"
        "交互信息只能通过输入 `actions` 中已有的 `actionId` 表达，不添加其他交互属性。",
        "- 每个原子业务事实在整张卡片中必须只有一个可见 owner，标题也计入可见 owner。"
        "某个 ID 已绑定到一个可见文本 Prop，或已作为 `dataIds` 数组成员组合进某个文本后，"
        "不得再将该 ID 绑定到其他可见文本重复展示；同一数值允许同时驱动进度图形和与该图形配套的唯一数值文本。"
        "不得用静态标题、标签或同义改写再次表达已经展示的动态事实，也不得为满足组件最少条目数复制事实；"
        "此时应改选条目数合同匹配的组件。提交前按事实语义检查 owner，但不得因去重删除未展示的必需信息。",
        "只有“正常、健康、已连接”等状态描述时应使用文本组件，不得编造进度值。",
        "- `actions` 是 userQuery 明确要求且已映射到输入的动作列表；每个动作都必须生成一个操作控件。"
        "2x4 输入只要 `actions` 非空，就不得选择不支持 Action 的“上下双区”，也不得以布局空间不足为由"
        "把动作写入 unmetRequirements。每个控件最多选择一个 `actionId`，"
        "同一 `actionId` 在一张卡片中最多使用一次。模型输入中的 `actions[].description` "
        "是映射后的推荐按钮术语，不是上游原始动作描述或业务数据；只能用于对应按钮内部的短文案。"
        "禁止将该术语或改写后的操作说明"
        "放入标题、正文、摘要、数据项或按钮外的任何可见内容。",
        validation_rule,
        "- 同一个 task action 只能实例化一个操作控件；"
        "不得同时用 PillButton、CircleButton 和 CardButton 表达同一操作。",
        size_rule,
        decision_rule,
        "- 必须处理信息层级、文字溢出和操作区占位；不得把可见业务内容生成成 `...` 截断效果。",
        "- submit_card_jsx.coverage 只逐项写明已满足的用户需求，不填写 dataIds/actionIds。"
        "无法满足的需求逐项写入 unmetRequirements，不得用笼统的“空间不足”或虚构内容掩盖缺失。",
        "",
    )
    return "\n".join(lines)


def build_user_prompt(task: dict[str, Any]) -> str:
    task_json = json.dumps(task, ensure_ascii=False, indent=2)
    return "请按规定工具工作流，为以下输入生成一张卡片：\n\n" + task_json
