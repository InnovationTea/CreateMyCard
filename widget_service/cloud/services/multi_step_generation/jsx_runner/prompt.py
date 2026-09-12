from __future__ import annotations

import json
from typing import Any

from .card_sizes import CARD_SIZE_DIMENSIONS
from .config import RESOURCE_STAGES


LAYOUT_FALLBACK_PROMPTS = {
    "compact_component": """当前 JSX 已连续三次未通过浏览器布局校验，现在进入紧凑组件替换阶段。

请根据最后一次浏览器 findings 重新组织布局，并将放不下的文本类组件替换为语义兼容、占位更小的安全组件。

必须保留：
- 所有用户要求的业务事实；
- 所有已使用的 dataIds；
- 所有 actionId；
- 动态数据绑定关系。

允许：
- 更换更为尺寸更小的其他组件或文本组件；
- 当最后一次 findings 的 `browser-semantic-overlap` 涉及 `EmphasizedData` 时，先复核业务语义；若内容是可无损保留的短文本、状态或完整格式化字符串，并且能从现有需求提供真实的 `secondaryText`，优先尝试替换为 `EmphasisText`。原 `value` 的完整可见内容与 `dataIds.value` 必须分别迁移到 `mainText` 与 `dataIds.mainText`；不得丢失、拆分或静态化动态值；
- 两条及以上 EventCard 高度不足时，优先保留每条事件的 title、time、location 和全部 dataIds，并改用 density="compact"；多条紧凑日程优先放入 140vp 连续内容区，不放入 118vp 子槽，也不得改用无法承载这些动态字段的静态标签；
- 合并语义相近的辅助字段；
- 更换 Layout Pattern 或 Sub Pattern；
- 重新分配 Stack 的显式 direction、width、height、flex 和 gap。

禁止：
- 删除信息或 Action；
- 把动态数据改成静态文本；
- 将纯数值单位、进度关系或按业务规则应使用 `EventCard` 的日程事件，仅为消除重叠而从 `EmphasizedData` 替换成 `EmphasisText`；
- 使用省略号、裁剪或 overflow 隐藏问题。

完成后调用 submit_card_jsx 提交完整 JSX。""",
    "drop_optional_component": """紧凑组件替换后仍未通过浏览器校验，现在进入信息组件合并或删除阶段。

首先固定当前 JSX 中的全部 Action 组件及其 actionId，并为它们保留合法布局槽位。任何情况下都不得删除、替换、遗漏或修改 Action 组件及其 actionId。

按以下顺序处理：
1. 优先把语义相近的信息合并到更少的 JSX 业务显示组件中；合并后必须保留原有信息、dataIds 和动态绑定，且组件真实尺寸必须适合目标槽位。
2. 合并后仍无法通过时，才允许删除一个最低优先级的信息类业务显示组件；不得删除 Action 组件。

删除顺序：
1. 与 userQuery 无直接关系的信息；
2. 辅助说明、更新时间、来源等次要信息；
3. 对主要任务影响最小的补充属性。

必须满足：
- 最多删除一个业务显示组件；
- 两次兜底提交共用进入本阶段时的固定基线，不能第一轮删一个、第二轮再删一个；合并或拆分组件时须保留原有 dataIds 和静态业务文本；
- 不得删除标题所表达的核心对象；
- 不得删除用户明确点名的信息；
- 必须保留全部 Action 组件及其原始 actionId；
- 不得把被删除数据改成无绑定的静态文本；
- 只有实际删除信息类组件时，才将省略的需求写入 unmetRequirements；仅合并组件时不得虚构未满足需求。

完成后调用 submit_card_jsx 提交完整 JSX。""",
}


def build_layout_fallback_prompt(strategy: str) -> str:
    try:
        return LAYOUT_FALLBACK_PROMPTS[strategy]
    except KeyError as exc:
        raise ValueError(f"unsupported layout fallback strategy: {strategy!r}") from exc


def build_plan_prompt() -> str:
    return (
        "本轮不要生成 JSX，只调用 submit_card_plan。按照已读取的 info_process 规则，"
        "在 info_required 中简要列出卡片必须展示的信息及其真实 dataId、actionId，避免后续遗漏；"
        "输入 actions 中的每个动作都来自 userQuery 明确要求，必须在方案中分配合法按钮槽位；"
        "2x4 任务只要 actions 非空，layout_optionA 和 layout_optionB 都禁止选择“上下双区”；"
        "不要加入与用户意图无关的信息。每个布局 option 按 content、layoutPattern、subPattern 的顺序输出："
        "先在 content 中按父区域列出最终业务组件，明确每区是单内容还是双内容、是否有标题和按钮，"
        "并参照 layouts 文档简要写明各内容区的水平、垂直对齐方式和弹性策略，尤其不要遗漏"
        "所选子布局规定的底端对齐；"
        "再依据已读取的 layouts 文档充分权衡组件数量、内容块关系、对齐方式和弹性空间，"
        "填写与上述结论一致的 layoutPattern 和 subPattern；将首选方案写入 layout_optionA；"
        "只有存在同样可行的替代布局时才填写 layout_optionB。"
        "info_required、layout_optionA、layout_optionB 各自控制在 512 tokens 内，只写结论；"
        "整个工具参数必须在 2048 tokens 内闭合为完整 JSON。"
    )


def build_plan_context(plan: dict[str, Any]) -> str:
    payload = json.dumps(plan, ensure_ascii=False, separators=(",", ":"))
    return (
        "以下是生成前计划。最终 JSX 必须保留 info_required 和采用方案 content 中的业务组件清单及数量，"
        "并参考 content 中按区域记录的对齐与弹性策略，使 submit_card_jsx.decision "
        "与采用方案的 layoutPattern/subPattern 一致；如果最终组件数量变化，必须重新选择匹配的 "
        "subPattern，不得只保留旧名称。若计划与已读取规范冲突，以规范为准。\n"
        f"<plan>\n{payload}\n</plan>"
    )


def build_system_prompt(
    component_name: str,
    card_size: str | None = None,
    *,
    validation_enabled: bool = True,
) -> str:
    order = "\n".join(
        f"{index}. {stage.key}：{stage.label}"
        for index, stage in enumerate(RESOURCE_STAGES, start=1)
    )
    if card_size in CARD_SIZE_DIMENSIONS:
        width, height = CARD_SIZE_DIMENSIONS[card_size]
        size_rule = (
            f'- 当前输入 size 为 "{card_size}"，根节点必须使用 '
            f'<Card size="{card_size}"> 并按 {width}x{height}vp 完成布局闭合。'
        )
    else:
        size_rule = (
            '- 根节点 Card.size 必须与输入顶层 size 完全一致：'
            '"2x2" 对应 160x160vp，"2x4" 对应 320x160vp。'
        )
    if card_size == "2x2":
        decision_rule = (
            '- submit_card_jsx.decision 只填写当前布局文档中的中文顶层名称，例如 '
            '{"layoutPattern":"标题单内容"}；2x2 不得填写 subPattern。'
        )
    elif card_size == "2x4":
        decision_rule = (
            '- submit_card_jsx.decision 必须同时填写中文顶层 layoutPattern 和 subPattern。'
            '选择“左右双区”时，subPattern 必须包含 left 和 right；'
            '每侧根据该区域最终的内容组件数、标题和 Action 独立选择子布局。'
            '没有 Action 的区域不得选择名称包含“按钮”的子布局。'
            '选择“左内容右侧双槽”时，subPattern 必须包含 content；'
            '“上下双区”和“四槽宫格”没有命名子布局，subPattern 填写空对象 {}。'
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
        "必须严格按顺序、每轮只调用一次 read_generation_resource 读取下一份资源：",
        order,
        f"{len(RESOURCE_STAGES) + 1}. 调用 submit_card_plan 提交必要信息和布局方案。",
        f"{len(RESOURCE_STAGES) + 2}. 调用 submit_card_jsx 提交最终 JSX。",
        "",
        "调用 submit_card_jsx 时先填写 decision，再填写 jsx。"
        "submit_card_jsx.jsx 只提交一个以 <Card> 为根的 JSX 表达式，"
        "不要提交 function/import/export、Markdown 说明或代码围栏。",
        "",
        "重要约束：",
        "- 只能使用 component_style 和 jsx_contract 中明确允许的组件与属性；"
        "组件用法以 component_style 为准，核心 JSX 与布局原语以 jsx_contract 为准。",
        "- Card 与每个 Stack 必须显式填写 direction=\"column\" 或 direction=\"row\"；"
        "Stack/Grid 不得生成 basis 或 minWidth。固定槽使用 flex={0}，"
        "并按父容器 direction 显式填写主轴 width 或 height。",
        "- 任何 icon、src 或 checkIcon 只能逐字使用当前输入 `assetCandidates` 中已有的 `src`；"
        "根据候选的 description 选择语义匹配的资源，禁止编造、改写路径或补充目录前缀；"
        "候选列表为空时不得输出资源属性。",
        "- `userQuery` 是当前请求的意图和具体事实来源，`data[].value` 只是动态字段的预览样例。"
        "若 `userQuery` 明确给出了与某个单一数据字段同义的具体名称、地点、时间或状态，"
        "而其与样例值不同，可见 Prop 必须使用 `userQuery` 中的事实，同时仍绑定该字段的真实 `dataId`；"
        "不得为了跟随样例值而改写用户明确提供的事实。"
        "`userQuery` 未提供对应具体值时，才使用 `data[].value`。"
        "一个 Prop 绑定多个 `dataId` 时不得猜测如何把查询文本反向拆分到多个动态字段；不得虚构数据。"
        "交互信息只能通过输入 `actions` 中已有的 `actionId` 表达，不添加其他交互属性。",
        "- 同一个输入数据 ID 在整张卡片中原则上只展示一次。"
        "某个 ID 已绑定到一个可见 Prop，或已作为 `dataIds` 数组成员组合进某个文本后，"
        "不得再将该 ID 绑定到其他组件重复展示；"
        "提交前展平检查所有 `dataIds`，删除重复事实，但不得因去重删除未展示的必需信息。",
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
