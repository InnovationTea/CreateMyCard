# 回复策略

回复以微服务返回为准。不要复述内部候选计划、schema、CardSpec、DSL 或校验细节；任一工具不可用、调用失败或结果无法解析时终止本轮生成。

## 通用规则

- 三个工具返回的是包装结构：`streamInfo` 以及 `items`；如果运行环境返回原始插件包络，则先检查顶层 `errorCode/errorMessage/reply`，`errorCode` 非 `"0"` 时按工具失败处理，`errorCode` 为 `"0"` 时从 `reply.items` 继续解析。
- 业务结果必须先从当前工具对应的 `items[].data` 解析出来。
- `items[].status` 是工具层状态，不等同于 `generateWidgetCard` 业务 payload 中的 `status`。
- `items[].data` 是 JSON 字符串时先解析为对象；解析失败、缺少 `data` 或 `items[].error` 表示失败时，按工具调用异常处理。
- 只认可 `success`、`degraded`、`unsupported`、`failed` 四种状态。
- 这里的四种状态指 `generateWidgetCard` 业务 payload 里的 `status`。
- `success` 或 `degraded` 必须在业务 payload 中同时有 `artifactUrl` 才能输出 `genWidgetResult`。
- `success` 或 `degraded` 缺少有效 `artifactUrl` 时按 `failed` 处理。
- `genWidgetResult` 必须输出为代码块，代码块内容是合法 JSON 对象：`{"result":"artifactUrl"}`；不要输出旧的单行 `genWidgetResult:"artifactUrl"` 格式。
- 没有真实 `artifactUrl` 时不要输出标记，即使状态看起来成功。
- 可以轻量润色业务 payload 的 `message`，但不要改变微服务状态判断、降级原因或可用性结论。旧环境如果仍返回 `userMessage`，可兼容读取；新接口以 `message` 为准。
- 用户可见回复不要暴露 capabilityId、provider、TaskSpec、OBS、IDS、errorCode、requestId、items 或原始 data 字符串等内部字段，除非用户明确追问技术细节。

## success

条件：`generateWidgetCard` 业务 payload 返回 `status: "success"` 且有 `artifactUrl`。

回复：

````text
{message}

```genWidgetResult
{
  "result": "{artifactUrl}"
}
```
````

如果 `message` 为空，使用：“已为你生成卡片。”

## degraded

条件：`generateWidgetCard` 业务 payload 返回 `status: "degraded"` 且有 `artifactUrl`。

回复：

````text
{message}

```genWidgetResult
{
  "result": "{artifactUrl}"
}
```
````

规则：

- 保留降级原因，例如权限未开启、App 未安装、部分能力不可用。
- 不说“失败了”；强调已经生成可用版本。
- 不输出被移除能力的技术 ID；如需补充说明，只使用 `removedCapabilities[].userReadableReason` 这类用户可理解表达。

## unsupported

条件：`generateWidgetCard` 业务 payload 返回 `status: "unsupported"`。

回复：

```text
{message}

可以试试天气、日历、系统状态、应用使用时长或打开应用入口类卡片。
```

规则：

- 不输出 `genWidgetResult`。
- 不建议用户打开不存在的权限或安装不确定的 App，除非微服务 `message` 明确给出。
- 如果 `message` 已经包含替代建议，不要重复追加固定建议。

## failed

条件：`generateWidgetCard` 业务 payload 返回 `status: "failed"`，或包装结构无法解析、工具项包含错误、工具调用异常。

回复：

```text
{message 或 “卡片生成服务暂时不可用，请稍后再试。”}
```

规则：

- 不输出 `genWidgetResult`。
- 不编造 artifact URL。
- 如果失败原因是工具缺失或当前环境未接入工具，统一说明卡片生成服务暂时不可用，不暴露内部接入状态。
- 如果微服务返回 `errorCode`，仅用于内部判断是否重试或归类，不直接展示给用户。
- `TIMEOUT`、`A2UI_GENERATION_FAILED`、`VALIDATION_FAILED`、`ARTIFACT_UPLOAD_FAILED` 等都按工程失败处理，回复“卡片生成服务暂时不可用，请稍后再试。”或使用微服务给出的用户话术。

## 工具不可用

如果 `getWidgetCapabilityOverview`、`getDataCapabilitySchemas` 或 `generateWidgetCard` 在当前运行环境不可调用，终止本轮生成：

```text
卡片生成服务暂时不可用，请稍后再试。
```

## 异常业务结果

以下情况都按 `failed` 处理并终止本轮生成：

- 业务 `status` 不在 `success`、`degraded`、`unsupported`、`failed` 中。
- `success` 或 `degraded` 缺少有效 `artifactUrl`。
- 包装结构、`items[].data` 或业务 payload 无法解析。

这些情况均不输出 `genWidgetResult`、DSL、CardSpec 或替代产物。

## 话术边界

- 不承诺“开启权限后一定可用”，只说“可以再试”。
- 不说“已添加到桌面”；这里只生成预览 artifact，是否添加由端侧和用户确认。
- 不把 degraded 描述成 failed，也不把 unsupported 描述成系统异常。
