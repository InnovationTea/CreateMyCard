# 生成契约

## 内容角色

生成前把用户需求归入以下角色：

- `object`：唯一服务对象，例如城市、会议、设备或应用。
- `primary`：回答唯一主问题的主值、主标题或主状态。
- `support`：帮助判断的短信息，不重复 primary。
- `metric/tile/status/badge`：模板声明的并列小事实。
- `action`：最多一个主动作；`2x4` 模板明确声明时可有两个相关动作。
- `asset`：承担识别、状态、动作或主媒体职责的本地素材。

把不可缺少且必须完整显示的内容标为 `mustKeep`，把空间允许才保留的内容标为 `shouldKeep`。标题、时间、日期、状态、CTA、主指标、倒计时、价格、数量和用户明确要求的字段都是受保护文本。

## 尺寸选择

- 未指定尺寸先尝试 `2x2`。
- 只有受保护文本、并列关系、关键媒体或动作热区无法在 136x136vp 内容区成立时才使用 `2x4`。
- `2x2` 只承载一个核心数据能力；`2x4` 最多两个。
- 用户要求其它尺寸时，改为最接近的 `2x2` 或 `2x4`，并在说明中指出调整。

## 填充规则

1. 保留模板 surfaceId、root、组件 ID、region 层级和固定宽高。
2. 只修改内容、DataModel、允许的组件变体、合法素材、颜色和事件。
3. 所有动态路径都必须初始化，或能由 CardSpec 数据能力输出推导。
4. 删除可选槽位时清理组件、children 引用、DataModel 和冗余 binding。
5. 不把示例文案、示例参数或示例事件当成用户事实。

## 协议输出

- `genui` 恰好三行 JSONL，顺序固定。
- `version` 为 `v0.9`，`catalogId` 为 `ohos.a2ui.extended.catalog`。
- `createSurface.width/height` 和 root `styles.width/height` 为 `matchParent`。
- CardSpec 静态字段必须简短、用户可理解且不含表达式。
- 点击事件只写 DSL `onClick`。

最终先给一句布局和风格说明，再输出 `genui`、`cardspec` 两个代码块。说明不得暴露模板 ID、能力 ID、内部槽位名或校验过程。
