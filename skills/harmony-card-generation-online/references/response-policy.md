# 回复策略

主 Agent 仍按微服务业务 payload 区分 `success`、`degraded`、`unsupported`、`failed`，但面向端侧的非完整满足或异常回复必须收敛为“部分数据不支持、整体不支持、其它异常”三类固定话术。不要复述内部候选计划、schema、CardSpec、DSL、来源 URL 或校验细节。

## 状态映射

| 对端结果 | 判定条件 | 是否输出 `genWidgetResult` |
| --- | --- | --- |
| 完整成功 | `success`，存在有效 `artifactUrl`，且没有已知的用户提及数据缺失 | 是，使用正常成功说明 |
| 部分数据不支持 | `degraded` 且存在有效 `artifactUrl`；或 `success` 且存在有效 `artifactUrl`，但 `unavailableCapabilities`、`missingCapabilityIds` 或 `removedCapabilities` 已表明用户提及的部分数据不可用 | 是，使用固定话术 |
| 整体不支持 | 业务 payload 为 `unsupported` | 否，使用固定话术 |
| 其它异常 | `failed`、必要工具不可用、调用异常、payload 无法解析、状态非法，或 `success` / `degraded` 缺少有效 `artifactUrl` | 否，使用固定话术 |

edit 模式的新 `artifactUrl` 还必须不同于 `sourceArtifactUrl`；缺失、无效或与来源相同时归为其它异常，不得回用来源 URL 伪装编辑成功。

## 通用规则

- 调用工具前的必要追问不属于上述结果。存在会改变用户核心意图、候选选择或必填业务入参的待确认信息时，直接提出最少必要问题并等待用户回答；此时不调用工具，也不输出固定结果话术或 `genWidgetResult`。
- 部分能力不可用但剩余数据仍可生成有价值的卡片时，不再询问是否继续，直接完成降级生成。用户已明确“必须包含缺失数据，否则不要生成”时保留该约束，由微服务作 `unsupported` 裁决。
- 三个工具返回的是包装结构：`streamInfo` 以及 `items`；如果运行环境返回原始插件包络，则先检查顶层 `errorCode/errorMessage/reply`。`errorCode` 非 `"0"` 时归为其它异常，为 `"0"` 时从 `reply.items` 继续解析。
- 业务结果必须先从当前工具对应的 `items[].data` 解析。`items[].status` 是工具层状态，不等同于 `generateWidgetCard` 业务 payload 的 `status`。
- `items[].data` 是 JSON 字符串时先解析为对象；解析失败、缺少 `data` 或 `items[].error` 表示失败时，归为其它异常。
- 只认可 `success`、`degraded`、`unsupported`、`failed` 四种业务状态；其它值归为其它异常。
- `success` 或 `degraded` 必须同时有有效 `artifactUrl` 才能输出 `genWidgetResult`。代码块内容必须是合法 JSON 对象：`{"result":"artifactUrl"}`；没有真实 URL 时绝不输出标记。
- 除完整成功外，不透传、不拼接、也不润色业务 payload 的 `message` 或旧字段 `userMessage`。工具或微服务提供的原因只可用于内部判定和提炼 `XX`。
- edit 模式完整成功或部分数据不支持后，将本轮新 URL 作为后续未指定目标编辑的默认来源；其它结果不更换默认来源。
- 用户可见回复不要暴露 capabilityId、provider、TaskSpec、OBS、IDS、errorCode、requestId、items 或原始 data 字符串。

## XX 提炼规则

固定话术中的 `XX` 是占位符，输出时必须替换：

1. 优先使用用户原话中的数据或功能名称，并用能力描述、`unavailableCapabilities`、`missingCapabilityIds` 和 `removedCapabilities` 仅作对应关系校验。
2. 多个名称去重后用“、”连接，例如“日程、设备电量”。
3. 不输出技术 ID、包名、provider、schema 字段名或错误码。
4. 无法可靠提炼时使用“相关”，不得猜测具体名称。
5. 部分数据不支持模板中 `XX` 两侧的空格只用于标示占位符，实际替换后不保留；例如输出“日程数据”，不要输出“日程 数据”。

## 完整 success

条件：`generateWidgetCard` 返回 `status: "success"`，存在有效 `artifactUrl`，且本轮没有已知的用户提及数据缺失。

回复：

````text
{message；为空时，create 模式使用“已为你生成卡片。”，edit 模式使用“已按你的要求修改卡片。”}

```genWidgetResult
{
  "result": "{artifactUrl}"
}
```
````

## 部分数据不支持

条件：

- `generateWidgetCard` 返回 `status: "degraded"` 且存在有效 `artifactUrl`；或
- 返回 `status: "success"` 且存在有效 `artifactUrl`，但 `unavailableCapabilities`、`missingCapabilityIds` 或 `removedCapabilities` 已表明用户提及的部分数据不可用，而剩余可获取数据仍生成了卡片。

固定回复：

````text
本次卡片生成暂无你提及的 XX 数据，该能力暂未开放，将基于可获取数据为你生成卡片

```genWidgetResult
{
  "result": "{artifactUrl}"
}
```
````

输出前按“XX 提炼规则”替换 `XX`。不要使用微服务 `message`，不要追加权限、安装、恢复时间、原卡片状态或其它说明。

## 整体不支持

条件：`generateWidgetCard` 返回 `status: "unsupported"`。

固定回复：

```text
抱歉，你提及的XX功能数据本期暂未开放，你可以尝试生成首页精选的天气、日程、运动、设备电量等同类应用卡片
```

输出前按“XX 提炼规则”替换 `XX`。不输出 `genWidgetResult`，不使用微服务 `message`，不追加其它替代建议或编辑专属说明。

## 其它异常

条件包括：

- `generateWidgetCard` 返回 `status: "failed"`。
- 任一必要工具不可用、调用异常、工具项报错或包装结构无法解析。
- 业务状态不在约定枚举中。
- `success` 或 `degraded` 缺少有效 `artifactUrl`。
- edit 模式的新 `artifactUrl` 无效或与 `sourceArtifactUrl` 相同。

固定回复：

```text
卡片创建过程遇到问题了，请稍后再试
```

不输出 `genWidgetResult`，不使用微服务 `message`，不暴露具体失败原因，也不追加“原卡片不受影响”“服务暂时不可用”等其它话术。

## 话术边界

- 不承诺“开启权限后一定可用”，不引导用户安装不确定的 App。
- 不说“已添加到桌面”；这里只生成预览 artifact，是否添加由端侧和用户确认。
- 不把部分数据不支持描述成工程失败，也不把整体不支持描述成系统异常。
- 三类固定话术不得改写同义句、增加前后缀或拼接微服务自定义文案。
