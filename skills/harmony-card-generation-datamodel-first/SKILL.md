---
name: harmony-card-generation-datamodel-first
description: "生成、修复、评审或解释 HarmonyOS A2UI Form 服务卡片的表达式版本。用于需要同时产出三行 genui JSONL 与 cardspec JSON，并只按完整 {{ ... }} 表达式读取 DataModel、支持列表循环项表达式、2x2/2x4 尺寸、Form 组件字段、事件能力和 CardSpec 数据契约校验同一张卡片的任务。"
---

# Harmony 卡片生成（表达式版）

产出同一张 Form 卡片：三行 `genui` JSONL 加一个 `cardspec` JSON。输出前按 `core-rules.md` 检查协议、绑定、布局、内容、颜色、事件和 CardSpec。

## 执行顺序

1. 先读 `reference/core-rules.md`，把 P0/L0/L1/L2 当硬门槛。
2. 只进入一个模式：新卡片、修复/评审、能力边界。新卡片再读 `reference/generation-workflow.md`；修复/评审按 `reference/core-rules.md` 的人工阻断补充复核。
3. 新卡片先收敛到一个服务对象或主问题，再按角色槽位分配内容：`object`、`primary`、`support`、`metric/tile/status/badge`、`action`、`asset`。不要把所有事实硬压成固定支撑条数。
4. 未指定尺寸先尝试 `2x2`；只有受保护文本、热区、并列关系、关键媒体或布局预算具体失败时才升级 `2x4`。
5. 从零生成完成内容分级后，只要候选尺寸可能由模板承载，且入选内容能收敛为一个服务对象/主问题与 `object`、`primary`、`support`、`metric/tile/status/badge`、`action`、`asset` 角色槽位，先读 `reference/template-routing.md` 和 `assets/templates/index.json` 做候选判断；最多选一个模板。模板只提供骨架和预算，内容、DataModel、素材、颜色、事件必须重做。
6. 需要专项，或对组件字段、绑定、布局、颜色、事件不确定时，按 `reference.md` 定向补读最小必要文件；没有读到权威文件前不要凭样例或记忆补字段。先解决协议、绑定、尺寸和布局，再处理事件、CardSpec、颜色、素材、主显示组突出度、支撑组归拢和表面层级。
7. 写 DSL 前先算 surface/root、内容区、padding/margin/itemMargin、热区、受保护文本、并排宽高和颜色来源。
8. 输出前确认协议、绑定、布局、颜色、事件、尺寸、模板槽位、信息职责、事实等价类和 CardSpec 对齐；若确认项依赖未读专项，先补读再输出。只有用户要求校验既有文件或调试脚本时才运行 `scripts/validate_card.py`。

模式 1/2 的最终回答只给最终 DSL/CardSpec，不输出解释、校验日志、命令、比较过程或中间文件。

## 输出形态

只输出两个代码块，顺序固定：

```genui
{"version":"v0.9","createSurface":{...}}
{"version":"v0.9","updateComponents":{"surfaceId":"...","root":"...","components":[...]}}
{"version":"v0.9","updateDataModel":{...}}
```

```cardspec
{
  "suggestSize": "2x2"
}
```

静态卡片也输出 `cardspec`，但不要虚构 `dataBindings`。动态卡片的 `cardspec.dataBindings` 必须来自已声明 data capability，且 UI 路径能由 `writeResultTo + outputSchema` 推导。

## 一致性约定

- 新卡片默认使用 `2x2 = 140 x 140`，root `padding: 12`、`borderRadius: 18`、`clip: true`；`2x4 = 300 x 140`，root `padding: 12`、`borderRadius: 22`、`clip: true`。
- 新卡片默认省略 `createSurface.styles`；表面背景、内容布局、安全区和 root 形状都写在 `root.styles` 或 root 下的真实背景组件。只有宿主明确要求外层形状/裁切时，`createSurface.styles` 才可出现且仅限 `borderRadius`、`clip`。
- 绑定方式固定为：静态值或完整 `{{ ... }}` 表达式。动态展示值、样式动态值和事件参数都用表达式读取 DataModel；不使用 `{"path":"/..."}` 或 `formatString` 作为值绑定。`updateDataModel.path`、CardSpec `writeResultTo`、模板 `children.path` 是协议结构 JSON Pointer，不属于值绑定；列表模板项内用表达式读取当前项字段。
- 非模板生成时使用稳定语义 ID：`surface_card`、`root`、`header_row`、`title_text`、`primary_value`、`primary_caption`、`support_row`、`action_button` 等；模板生成时保留模板 ID 体系，但删除不用的可选槽位并同步清理引用。
- 不使用网络图、内联/base64 SVG、emoji、占位媒体、未声明资源路径、未声明 SVG、未声明事件能力、`Button.action`、非 `onClick` 事件或 Form 子集外组件；允许 `reference/design/asset-library.md` 声明的本地 SVG。
- 可点击 UI 必须有真实 `onClick` EventHandler；如果动作能力不明，删除点击行为，把动作区降级为非误导支撑信息。
- 颜色规则读 `reference/design/color-token-system.md`；需要具体 hex 时再读 `reference/design/color-token-values.md`。DSL 输出 hex，不输出 token 名。
- 布局失败时按固定顺序降级：缩短弱文本 -> 删除可选角色槽位或 `shouldKeep` 字段 -> 降低到批准字号阶梯 -> 拆行/改 Column -> 放弃模板 -> 升级 `2x4` -> 能力边界说明。

## 专项参考

默认只读 `reference/core-rules.md`；新卡片再读 `reference/generation-workflow.md`。路由不清楚、修复已有 DSL、需要模板、动态数据、事件、颜色、素材，或主显示组不突出、支撑组散落、表面层级缺失时，再按 `reference.md` 读取对应专项文件；进入专项文件后先看顶部决策、阻断或使用规则，不一次性泛读无关参考。

新卡片中只要入选内容存在可由素材承担的识别、状态、动作、主媒体或视觉锚点职责，先读 `reference/design/asset-library.md` 再决定是否使用 `Image`；用户未提供素材不等于素材不可用。决定省略素材前，必须确认素材库无明确匹配、加入素材会破坏 L1 布局预算，或用户明确要求不用图片/图标。

运行本 skill 时不读取本 skill 包外的 UX 文档、旧样例、截图、网页或链接；需要的生成流程、布局字号、配色和验收规则已经折叠进 `reference/` 内部文件。

## 降级原则

当需求信息不足、组件字段不确定、布局预算复杂、动作/素材/颜色来源不完整，或出现渲染失败迹象时，优先降低自由度：标准短需求先用 `reference/template-routing.md` 的模板 manifest 槽位模式；若不用模板，则少组件、少层级、少颜色、少动态路径、少 Stack。若协议或布局预算无法证明成立，删除可选槽位、改用 `2x4`，或进入能力边界说明。
