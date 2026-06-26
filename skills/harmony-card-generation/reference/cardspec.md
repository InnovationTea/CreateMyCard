# CardSpec 数据能力契约

## 职责边界

CardSpec 是卡片结果的一部分，与 DSL 一起描述同一张卡片。最终响应只有一个组合结果：`genui` 代码块中的 DSL JSONL + `cardspec` 代码块中的 JSON 对象。DSL 负责可渲染 Form 组件，CardSpec 负责推荐尺寸、端侧数据能力、刷新计划和持久化契约。DSL 按本 skill 的 Form 规则生成：

- `catalogId` 使用 `ohos.a2ui.extended.catalog`。
- 组件、样式、事件、DataModel 表达式遵循 `reference/protocol.md`、`reference/component-catalog.md` 和 `reference/data-binding.md`。
- 不要从示例产物复制组件结构或 catalog。

Agent 负责选择已声明能力、生成参数、设计 DataModel 初始结构、生成 DSL 和 CardSpec。端侧负责执行能力、处理权限、归一化结果、持久化配置，并在运行时发送 `updateDataModel`。

事件能力不属于 CardSpec。点击、拨号、打开应用或详情页只写入 DSL `onClick`，并按 `reference/event-capability/` 中的 manifest 校验。

## 输出形态

每次生成卡片都输出两个代码块：

- `genui`：A2UI JSONL 消息流。
- `cardspec`：供端侧执行数据能力、刷新和持久化的 JSON 对象。

两者共同构成最终卡片结果。静态卡片也必须有 CardSpec，只是没有 `dataBindings`。

静态卡片 CardSpec：

```json
{
  "suggestSize": "2x2"
}
```

动态卡片 CardSpec：

```json
{
  "suggestSize": "2x4",
  "dataBindings": [
    {
      "capabilityId": "calendar.events.search",
      "arguments": {
        "timeInterval": [1766448000000, 1766534399999]
      },
      "writeResultTo": "/data/calendar"
    }
  ],
  "refreshPlan": {
    "onInstall": ["today_events"],
    "onVisible": ["today_events"],
    "periodic": {
      "intervalSec": 1800,
      "bindings": ["today_events"]
    }
  }
}
```

## 字段规则

- `suggestSize` 必须与尺寸选择一致，只能是 `"2x2"` 或 `"2x4"`。
- 静态卡片必须输出 CardSpec，但不要虚构 `dataBindings` 或 `refreshPlan`。
- 动态卡片必须包含 `dataBindings`。
- 每个 `dataBindings[]` 表示一次端侧能力调用。
- `capabilityId` 必须来自 `reference/data-capability/` 中选定能力 manifest 的 `id`。
- `arguments` 只能使用该能力 `inputSchema.properties` 声明的字段；不要沿用旧示例参数或自行改名。
- `writeResultTo` 必须是 `/data` 下的 JSON Pointer，例如 `/data/weather`。
- 多个 binding 的 `writeResultTo` 不得相同、互为父子，或互相覆盖。
- 默认使用简洁形态：`capabilityId`、`arguments`、`writeResultTo`。只有端侧明确需要时才加入 `bindingId`、`capabilityVersion` 或 `refreshPlan`。
- 如果提供 `refreshPlan`，它只能引用已存在的 `bindingId`。

## 能力选择

按场景从 `reference/data-capability/` 读取对应能力文档，不要一次加载所有能力。新增数据能力应继续放入该目录，模型按用户语义和 manifest 的 `description`、`inputSchema`、`required`、`outputSchema` 选择能力。

- 当前已有天气能力：`reference/data-capability/weather.md`
- 当前已有日历能力：`reference/data-capability/calendar.md`

如果用户请求的动态能力没有在 `reference/data-capability/` 中声明，不要编造能力。改用静态降级方案，或说明需要端侧补充 capability manifest。

## DataModel 映射

端侧执行 `dataBindings` 后，将标准化结果整体写入 `writeResultTo`。UI 访问路径由 `writeResultTo + outputSchema 字段` 推导。

例如 `writeResultTo` 是 `/data/calendar`，日历能力输出有 `items`，则列表路径是：

```text
/data/calendar/items
```

例如 `writeResultTo` 是 `/data/status`，某个能力输出有 `current.valueText`，则当前主值路径是：

```text
/data/status/current/valueText
```

初始化 DataModel 要包含 UI 会访问的根结构，但不要写入用户真实隐私数据：

```json
{
  "data": {
    "calendar": {
      "items": []
    }
  },
  "state": {
    "loading": true
  }
}
```

固定对象或标量优先用原生 `{path}` 绑定：

```json
{
  "id": "current_value",
  "component": "Text",
  "content": {"path": "/data/status/current/valueText"}
}
```

数组字段使用模板循环，模板对象只有 `componentId` 和 `path`：

```json
{
  "id": "event_list",
  "component": "Column",
  "children": {
    "componentId": "event_template",
    "path": "/data/calendar/items"
  }
}
```

模板内通过相对路径访问当前项：

```json
{
  "id": "event_title",
  "component": "Text",
  "content": {"path": "title"}
}
```

如果模板项点击需要使用当前项字段作为事件参数，也使用同一相对路径：

```json
{
  "call": "clickToIntent",
  "args": {
    "intentName": "ViewCalendarEvent",
    "params": {
      "entityId": {"path": "entityId"}
    }
  }
}
```

## 检查清单

- DSL 与 CardSpec 的尺寸选择一致。
- DSL 与 CardSpec 是同一个卡片结果的两个代码块，尺寸和 DataModel 访问路径必须互相对齐。
- 所有 UI 访问字段都能从 `writeResultTo` 和能力 `outputSchema` 推导。
- 事件参数如果来自数据能力输出，也能从同一 DataModel 路径推导；事件能力本身不写入 CardSpec。
- `updateDataModel.value` 初始化了 `/data/...` 根结构和必要 `/state/...` 字段。
- 数组字段使用模板循环，不展开成固定重复组件。
- CardSpec 不包含 DSL catalog、组件规则或示例结构的替代定义。
- 不暴露意图框架原始返回结构，不写死用户真实隐私数据。
