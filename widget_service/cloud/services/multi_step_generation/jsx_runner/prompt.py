from __future__ import annotations

import json
from typing import Any

from .card_sizes import CARD_SIZE_DIMENSIONS
from .config import RESOURCE_STAGES


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
        f"{len(RESOURCE_STAGES) + 1}. 调用 submit_card_jsx 提交最终 JSX。",
        "",
        "submit_card_jsx.jsx 只提交一个以 <Card> 为根的 JSX 表达式，"
        "不要提交 function/import/export、Markdown 说明或代码围栏。",
        "",
        "重要约束：",
        "- 只能使用 component_style 和 jsx_contract 中明确允许的组件与属性；"
        "组件用法以 component_style 为准，核心 JSX 与布局原语以 jsx_contract 为准。",
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
        "不得再将该 ID 绑定到 Summary 或其他组件重复展示；"
        "提交前展平检查所有 `dataIds`，删除重复事实，但不得因去重删除未展示的必需信息。",
        "只有“正常、健康、已连接”等状态描述时应使用文本组件，不得编造进度值。",
        "- `actions` 是候选动作列表；每个控件最多选择一个 `actionId`，"
        "同一 `actionId` 在一张卡片中最多使用一次。",
        validation_rule,
        "- 同一个 task action 只能实例化一个操作控件；"
        "不得同时用 PillButton、CircleButton 和 CardButton 表达同一操作。",
        size_rule,
        "- 必须处理信息层级、文字溢出和操作区占位；不得把可见业务内容生成成 `...` 截断效果。",
        "- submit_card_jsx.coverage 只逐项写明已满足的用户需求，不填写 dataIds/actionIds。"
        "无法满足的需求逐项写入 unmetRequirements，不得用笼统的“空间不足”或虚构内容掩盖缺失。",
        "",
    )
    return "\n".join(lines)


def build_user_prompt(task: dict[str, Any]) -> str:
    task_json = json.dumps(task, ensure_ascii=False, indent=2)
    return "请按规定工具工作流，为以下输入生成一张卡片：\n\n" + task_json
