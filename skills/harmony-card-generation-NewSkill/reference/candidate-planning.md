# 候选规划

目标：把用户 query 转成微服务可裁决的候选计划。候选计划只表达“用户可能需要什么”，不表达最终设备一定支持什么。

## 场景判断

进入本 skill 的典型 query：

- “帮我做一张天气卡片”
- “生成一个通勤 widget，包含天气和日程”
- “做一个一键清理内存的桌面卡”
- “给我做一个看抖音使用时长和耗电的卡片”
- “创建一个会议提醒卡片，可以一键入会”

不进入或直接说明边界的 query：

- 纯聊天、百科、写作、代码任务。
- 要求完整 App 页面、复杂表单、长报告。
- 要求直接输出 DSL/CardSpec；本 skill 已改为云侧生成链路。

## 能力概述筛选 Prompt

拿到 `getWidgetCapabilityOverview` 后，在内部按以下标准筛选：

```text
从用户 query 中抽取：
1. 核心场景：天气、日历、系统设置、应用使用、运动健康、音乐、电话、会议、导航等。
2. 用户想看的动态数据：当前状态、列表、用量、耗电、时间范围、地点、应用。
3. 用户想执行的动作：打开应用、查看详情、拨号、清理内存、入会、导航、切换设置。
4. 视觉素材意图：天气图标、日历图标、应用图标、系统状态图标等。

只从 overview 返回的 dataCapabilities、eventCapabilities、assetCandidates 中选择候选。
能力 summary/tags 与核心场景或动作强相关才选择。
不能仅凭名称相似选择会改变用户意图的能力。
```

## 尺寸选择

- 默认 `2x2`：一个核心状态、一个动作、一个简单提醒。
- 选择 `2x4`：两个以上核心信息区、动态列表、天气+日程、主指标+上下文+动作都需要完整展示。
- 如果不确定，优先 `2x2`，让微服务在必要时降级或调整。

## 数据能力候选

生成 `candidateDataBindings` 时遵守：

- `capabilityId` 必须来自已加载 schema。
- `arguments` 只使用 `inputSchema.properties` 中声明的字段。
- 必填字段缺失且无法从用户 query、会话安全上下文或 schema 默认说明推导时，不要编造；移除该候选或把缺失值放入 `slots.missing` 供微服务判断。
- `writeResultTo` 优先使用 schema 返回的 `defaultWriteResultTo`；没有时使用 `/data/{semanticKey}`，且多个候选不能相同或互为父子。
- `required` 默认 `false`。只有用户核心诉求完全依赖该能力时才设为 `true`。
- 不把候选 binding 当最终 CardSpec；微服务会过滤和规范化。

常见 slot：

```json
{
  "districtName": "青浦区",
  "timeRange": "today",
  "appName": "抖音",
  "appBundleName": "com.ss.hm.ugc.aweme",
  "target": "home",
  "relationship": "母亲",
  "phoneNumber": ""
}
```

## 事件能力候选

- 只传 `candidateEventCapabilityIds`，不要在主 Agent 中生成最终 `onClick`。
- 打开应用、打开详情、拨号、入会、导航、清理内存、切换设置等都通过 overview 的事件能力 ID 选择。
- 如果用户没有明确动作，但场景有自然入口，可以选一个低风险入口候选，例如打开天气或日历详情。
- 涉及高风险或不可逆动作时，只选 overview 中明确支持且用户明确要求的能力。

## 素材候选

- 只传 `candidateAssetIds`，不要自造图片路径。
- 素材候选必须和场景、状态或动作有明确语义关系。
- 没有匹配素材时传空数组，由微服务决定是否用无素材设计。

## 降级

默认：

```json
{
  "allowDegradation": true,
  "returnMode": "obs_url"
}
```

除非用户明确要求“必须包含某能力，否则不要生成”，否则允许微服务降级。主 Agent 不自行决定最终降级形态。
