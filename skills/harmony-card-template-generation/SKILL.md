---
name: harmony-card-template-generation
description: "使用固定布局模板和受控组件变体生成 HarmonyOS A2UI Form 服务卡片。用于用户显式调用本 Skill，并要求主 Agent 根据自然语言需求、目标尺寸或视觉风格，从模板库中选择一个 2x2/2x4 布局，最终生成三行 genui JSONL 与 cardspec JSON；支持已声明的数据能力、点击事件和本地素材，但不调用 harmony-card-generation-online 或 harmony-card-generation-offline。"
---

# Harmony 卡片模板生成

根据用户需求选择一个正式模板，在模板声明的区域、槽位和组件变体内生成最终 DSL 与 CardSpec。不要调用或读取其它卡片生成 Skill。

## 执行顺序

1. 读取 `references/generation-contract.md`，把用户需求收敛为一个服务对象和一个主问题，并提取 `primary`、`support`、`metric/tile/status/badge`、`action`、`asset`、尺寸和风格。
2. 读取 `references/routing-and-style.md` 与 `assets/templates/index.json`。先做硬过滤，再按索引顺序选择第一个完全满足约束的模板；一次只能选择一个模板。
3. 只读取选中模板的 `manifest.json`、`template.genui.jsonl` 和 `cardspec.json`。模板的 region 外框、层级、固定宽高和 root shell 不得改变。
4. 需要动态数据时读取 `references/capability/cardspec.md` 和 `references/capability/data-capability/index.md`，再只读取命中的 1-2 个能力文件。`2x2` 最多一个数据能力，`2x4` 最多两个。
5. 需要点击时读取 `references/capability/event-capability/click-event.md`；无法匹配声明目标时删除点击，不编造 `call` 或参数。事件只写 DSL `onClick`，不写 CardSpec。
6. 需要图片或图标时读取 `references/design/asset-library.md`；只用已声明的本地资源。需要具体颜色时读取 `references/design/color-token-system.md` 和 `color-token-values.md`。
7. 仅在 manifest 的 `componentVariants` 中选择变体。删除可选槽位时，同步删除组件、children 引用、DataModel 字段和无用数据绑定；不得跨模板拼装 region。
8. 写完后运行 `python scripts/validate_card.py <draft> --template-id <id> --strict`。只允许按诊断修复一次；仍失败时说明当前模板无法安全承载，不输出无效 DSL。
9. 最终先给一句面向用户的布局/风格说明，再输出 `genui` 和 `cardspec` 两个代码块；不要暴露模板 ID、能力 ID、校验日志或中间计划。

## 模板选择硬门槛

- 用户需求能收敛为一个服务对象和一个主问题。
- 用户指定尺寸与模板尺寸一致；未指定时先尝试 `2x2`，受保护文本、并列关系、关键媒体或热区明确放不下时再使用 `2x4`。
- 必选内容能映射到 manifest 槽位，受保护文本不依赖省略号或裁切。
- 动作数、数据能力数、素材需求和组件类型均在 manifest 上限内。
- 所需 region 变体在 manifest 中声明；不允许为迁就内容改变固定几何。

若无模板匹配，按顺序删除 `shouldKeep` 内容、尝试 `2x4`、使用同尺寸安全通用模板。仍不成立时说明需要简化需求，不退回自由生成。

## 不可妥协项

- `genui` 恰好三行：`createSurface`、`updateComponents`、`updateDataModel`。
- `version` 使用 `v0.9`，`catalogId` 使用 `ohos.a2ui.extended.catalog`。
- `createSurface.width/height` 与 root `styles.width/height` 使用 `matchParent`；内部 region 使用 manifest 数值预算。
- CardSpec 只承载静态短 `title`、静态短 `description`、`suggestSize` 和已声明的 `dataBindings`。
- 不使用网络图、内联/base64 SVG、emoji、未声明素材、未声明事件、`theme`、`Button.action` 或 Form 子集外组件；允许素材库声明的本地 SVG/PNG。
- 不修改模板 ID 体系，不新增第二主问题，不把多个事实重复写进不同槽位。

## 专项参考

- 模板字段和维护规则：`references/template-contract.md`
- 协议消息与组件：`references/protocol/protocol.md`、`references/protocol/component-catalog.md`
- 表达式与 DataModel：`references/protocol/data-binding.md`
- 布局、构图和色彩：`references/design/layout-system.md`、`design-heuristics.md`、`color-token-system.md`
- 方案维护说明：`方案设计.md`，只在维护本 Skill 时读取，不在普通生成任务中加载。

## 输出形态

先用一句话说明采用的布局类型、视觉风格及必要降级，然后输出：

```genui
{"version":"v0.9","createSurface":{...}}
{"version":"v0.9","updateComponents":{...}}
{"version":"v0.9","updateDataModel":{...}}
```

```cardspec
{"title":"状态卡片","description":"状态概览","suggestSize":"2x2"}
```
