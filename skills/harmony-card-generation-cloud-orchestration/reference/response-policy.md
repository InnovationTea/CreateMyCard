# 回复策略

主 Agent 的回复以微服务返回为准。不要复述内部候选计划、schema、CardSpec、DSL 或校验细节。

## success

条件：微服务返回 `status: "success"` 且有 `artifactUrl`。

回复：

````text
{userMessage}

```genWidgetResult:"{artifactUrl}"```
````

如果 `userMessage` 为空，使用：“已为你生成卡片。”

## degraded

条件：微服务返回 `status: "degraded"` 且有 `artifactUrl`。

回复：

````text
{userMessage}

```genWidgetResult:"{artifactUrl}"```
````

规则：

- 保留降级原因，例如权限未开启、App 未安装、部分能力不可用。
- 不说“失败了”；强调已经生成可用版本。
- 不输出被移除能力的技术 ID，除非 `userMessage` 已经使用用户可理解表达。

## unsupported

条件：微服务返回 `status: "unsupported"`。

回复：

```text
{userMessage}

可以试试天气、日历、系统状态、应用使用时长或打开应用入口类卡片。
```

规则：

- 不输出 `genWidgetResult`。
- 不建议用户打开不存在的权限或安装不确定的 App，除非微服务 `userMessage` 明确给出。

## failed

条件：微服务返回 `status: "failed"` 或工具调用异常。

回复：

```text
{userMessage 或 “卡片生成服务暂时不可用，请稍后再试。”}
```

规则：

- 不输出 `genWidgetResult`。
- 不编造 artifact URL。
- 如果失败原因是工具缺失，明确说当前环境尚未接入云侧生成工具。

## 工具不可用

如果 `getWidgetCapabilityOverview`、`getDataCapabilitySchemas` 或 `generateWidgetCard` 在当前运行环境不可调用：

```text
当前环境还没有接入云侧卡片生成工具，暂时不能生成可添加的卡片。需要接入 getWidgetCapabilityOverview、getDataCapabilitySchemas 和 generateWidgetCard 后才能完成。
```

## 话术边界

- 可以轻量润色微服务话术，让它更自然。
- 不改变微服务的状态判断。
- 不承诺“开启权限后一定可用”，只说“可以再试”。
- 不解释 A2UI、CardSpec、OBS、IDS 等内部实现，除非用户明确追问技术细节。
