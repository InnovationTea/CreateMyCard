# Feature Profile 与生成契约

## 用户需求字段

- `serviceObject`：卡片服务的唯一对象，例如“上海天气”“下一场会议”“手机电池”。
- `primaryQuestion`：用户希望卡片一眼回答的唯一问题，例如“现在多少度”“会议几点开始”“是否需要省电”。
- `primaryVisual`：主问题适合的视觉语义，只选 `text/metric/progress/media/schedule/status` 之一。
- `contentItems`：需要展示的事实。每项包含稳定 `id`、内容角色和优先级。
- `actions`：用户可执行的相关动作；`2x2` 最多一个，`2x4` 最多两个。
- `dataNeeds`：需要动态刷新的已声明数据能力。
- `assetNeeds`：承担识别、状态、动作或主媒体职责的素材。
- `size`：只使用 `2x2` 或 `2x4`。
- `styleIntent`：只使用四套受控风格之一。

示例：“做一张上海天气卡，显示温度、天气和打开天气入口”。

```json
{
  "schemaVersion": "feature-profile-v1",
  "serviceObject": "上海天气",
  "primaryQuestion": "当前温度和天气如何",
  "size": "2x2",
  "primaryVisual": "status",
  "contentItems": [
    {"id": "temperature", "role": "primary", "priority": "mustKeep"},
    {"id": "weatherText", "role": "support", "priority": "mustKeep"},
    {"id": "openWeather", "role": "action", "priority": "mustKeep"}
  ],
  "actions": ["打开天气"],
  "dataNeeds": ["天气"],
  "assetNeeds": ["天气状态图标"],
  "styleIntent": "ambient-scene"
}
```

## 内容角色

- `object`：服务对象名称。
- `primary`：唯一主问题的主值、主标题或主状态。
- `support`：帮助判断的短信息，不重复 primary。
- `metric/status/badge`：并列小事实，不能形成第二主问题。
- `action`：合法事件对应的动作标签。
- `asset`：已声明的本地素材。

不可缺少且必须完整显示的内容标为 `mustKeep`；空间允许才保留的内容标为 `shouldKeep`。标题、时间、日期、状态、CTA、主指标、倒计时、价格、数量和用户明确要求的字段都是受保护文本。

## 尺寸与容量

- 未指定尺寸先尝试 `2x2`。
- 只有受保护文本、并列关系、关键媒体或动作热区无法在 136x136vp 内容区成立时才使用 `2x4`。
- `2x2` 最多三个顶层模块、一个动作和一个数据能力。
- `2x4` 最多四个顶层模块、两个相关动作和两个数据能力。
- 用户要求其它尺寸时改为最接近的支持尺寸，并在最终说明中指出调整。

## 内容映射

1. 每个 Feature Profile 内容项只能映射到一个模块槽位。
2. 所有 `mustKeep` 必须恰好映射一次。
3. 未映射的 `shouldKeep` 必须在 Design Plan `degradations` 中记录 ID 和原因。
4. 动态绑定必须来自已声明能力；静态示例不能冒充运行时事实。
5. 删除内容时同步删除对应事件、素材、DataModel 和无用数据绑定。

## 最终协议

- `genui` 恰好三行 JSONL，顺序固定。
- `version` 为 `v0.9`，`catalogId` 为 `ohos.a2ui.extended.catalog.form`。
- `createSurface.width/height` 和 root `styles.width/height` 为 `matchParent`。
- CardSpec 静态字段简短、用户可理解且不含表达式。
- 点击事件只写 DSL `onClick`。

最终只展示布局/风格说明、`genui` 和 `cardspec`，不展示内部设计对象。
