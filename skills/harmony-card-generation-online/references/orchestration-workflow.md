# 云侧编排工作流

本文档只定义 create/edit 的状态流转和工具顺序。候选构造见 [`candidate-planning.md`](candidate-planning.md)，接口与解析见 [`tool-contracts.md`](tool-contracts.md)，用户输出见 [`response-policy.md`](response-policy.md)。

## 对话上下文与编辑链

主 Agent 不创建独立状态或快照，只从当前对话上下文中的真实工具调用参数及其合法业务结果追溯编辑链：

- `success` / `degraded` 的真实 `artifactUrl` 标识一个有效结果；edit 调用中的 `sourceArtifactUrl` 将它与来源结果关联。
- `candidateDataBindings` 只取自编辑链中实际调用 `generateWidgetCardCompactDsl` 时显式提交的完整数组；某轮省略该字段时，沿 `sourceArtifactUrl` 向前查找最近一次显式提交。
- 后续有效业务结果中的 `effectiveCapabilities.data` 和可可靠对应的移除结果用于排除未生效的数据能力。
- 调用失败、结果非法、没有新 URL 或 edit 返回来源 URL 时不形成新的有效结果，不改变后续追溯起点。
- 用户对话只用于理解目标卡片和修改意图；普通回复、`genWidgetResult` 文本、示例和来源 artifact 不用于恢复内部字段。

无法从当前对话上下文建立“调用参数 → 业务结果 → artifactUrl → 下一轮 sourceArtifactUrl”的可靠对应关系时，停止需要该信息的 edit，不猜测或补造。

## 十三步流程

1. **确认触发上下文**：明确创建/编辑桌面卡片，或处于卡片创建、模板、端侧显式标记上下文时进入流程；普通非卡片对话不召回。
2. **执行形态门禁**：非卡片任务、长报告、完整页面或复杂表单直接结束并引导；是否做成卡片仍有歧义时只追问一个最小必要问题。
3. **判断模式与目标**：创建请求走 create；包含修改、删除、替换、改颜色、改尺寸或继续优化等语义走 edit。edit 未指定目标时使用最近有效结果；明确目标无法对应时才追问。
4. **分流 edit**：
   - 纯视觉、布局、文案或尺寸：不重新获取概述/schema，只准备来源 URL 和本轮明确修改字段。
   - 删除数据能力或修改已有数据参数：恢复编辑后的完整数据候选，再重新获取概述/schema。
   - 新增数据能力、修改事件或素材候选：停止编辑并引导重新创建。
5. **执行调用前确认**：检查目标对象、地点、时间范围、动作目标及能力必填参数。用户可回答且会改变核心结果时先追问并等待。
6. **可选过程回复**：需要说明进度时只说“我先检查当前设备支持情况，然后为你生成可用的卡片。”，不承诺具体能力。
7. **获取能力概述**：create 和数据类 edit 调 `getWidgetCapabilityOverview`；其它 edit 跳过。解析失败按其它异常结束。
8. **第一次能力满足度门禁**：按候选规划选择数据、事件和素材；核心无法满足且不能形成保持原意图的静态/入口卡时结束并引导；仅次要内容缺失时先预告再继续。
9. **加载数据 schema**：只为本轮已选且实际可用的数据能力调用 `getDataCapabilitySchemas`。移除 `missingCapabilityIds` 后重新执行能力满足度门禁；最后一个核心能力被移除时不生成。
10. **构造生成参数**：按运行时 schema 生成 create 完整候选计划，或 edit 的明确替换字段；同时确定去重后的最终数据能力 ID 集合。
11. **执行权限门禁**：数据集合非空时调用 `RequestDataPermission` 并等待；只有契约明确通过才进入下一步。集合为空时跳过。权限检查后不得改变数据集合，否则重新检查。
12. **生成或编辑**：前置门禁通过后调用 `generateWidgetCardCompactDsl`；不补做微服务负责的继承、协议选择、校验、重试或上传。
13. **原子交付并识别新链路节点**：解析当前生成调用的业务 payload 后，先锁存合法真实 `artifactUrl` 是否存在，再判断状态和自然语言；锁存为有 URL 时，必须在同一条最终回复中追加且只追加一个 `genWidgetResult` 代码块，并在发送前核对块内 `result` 与该 URL 完全一致。不得只回复业务 `message`、等待确认或留到下一轮补发。edit 只有在返回不同于来源的新 URL 时，才把本次真实调用及其业务结果作为后续可追溯节点；其它结果继续使用上一版有效结果。

## 调用轨迹

| 场景 | 调用轨迹 |
| --- | --- |
| 动态 create | overview → schema → permission → generate |
| 静态/入口 create | overview → generate |
| 纯视觉、布局、文案、尺寸 edit，来源含动态数据 | permission → generate |
| 纯视觉、布局、文案、尺寸 edit，来源无动态数据 | generate |
| 删除数据或修改参数 edit | overview → schema → permission（非空时）→ generate |
| 非卡片、追问、edit 新增能力 | 零调用 |

所有箭头都以当前步骤结果合法且门禁通过为前提；任一步失败立即终止，不继续调用后续工具。

生成工具已经返回后，不再调用其它工具补做交付。当前回复只有通过 [`response-policy.md`](response-policy.md) 的 URL/标记发送前检查后才能结束。

## 职责边界

- 主 Agent 只做模式识别、候选规划、门禁、工具调用和回复组织。
- 微服务负责最终 CardSpec、DSL、artifact、校验和降级。
- 端侧负责权限工具执行、artifact 下载、渲染、确认添加和运行时刷新。
- 主 Agent 不下载或解析来源 artifact，不直接生成或修复产物，不把点击事件写入 CardSpec，不用离线资料补足在线结果。
