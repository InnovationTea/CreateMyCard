# 回复策略

本文档只定义用户可见回复。工具结构是否合法先按 [`tool-contracts.md`](tool-contracts.md) 判定，候选与缺失项先按 [`candidate-planning.md`](candidate-planning.md) 确定。

## 导航

- [输出优先级](#输出优先级)
- [生成前回复](#生成前回复)
- [权限未通过](#权限未通过)
- [生成后回复](#生成后回复)
- [发送前硬检查](#发送前硬检查)
- [名称与推荐](#名称与推荐)

## 输出优先级

1. 当前仍有会改变核心意图或入参的用户待确认信息：只追问最小必要问题，等待回答，不调用下一工具。
2. 权限工具正常返回且未通过或结果非法：立即终止，不调用 `generateWidgetCardCompactDsl`。
3. 权限工具发生 invoke 级异常且没有正常权限结果：不输出权限异常说明，按默认开启继续调用 `generateWidgetCardCompactDsl`。
4. `generateWidgetCardCompactDsl` 返回后先锁存合法真实 `artifactUrl`；有 URL 时无论状态如何都输出 `genWidgetResult`，`degraded` 不能省略。
5. 没有 URL：绝不输出或伪造 `genWidgetResult`。

edit 只有新 URL 合法且不同于来源时才更新默认来源。

## 生成前回复

### 非卡片或形态不适配

```text
桌面卡片适合展示少量关键信息或提供快捷入口，暂不适合处理你这次的 XX。你可以试试：“建议一”、“建议二”
```

### 核心能力缺失

```text
当前卡片能力暂无法满足你需要的 XX，因此这次先不生成。你可以试试：“建议一”、“建议二”
```

### 部分满足预告

```text
当前暂无法提供 XX，我会保留 YY 继续为你生成卡片。
```

输出预告后直接继续，不等待用户确认。若后续工具失败，最终只输出其它异常话术。

### edit 新增能力

```text
当前连续编辑暂不支持新增 XX，这次先不修改。你可以重新创建一张卡片，例如：“重新创建需求”
```

生成前合法结束不伪造 `unsupported` 业务 payload，也不输出 `genWidgetResult`。

## 权限未通过

### 有手动授权明细

按返回顺序处理有效 `nonAuthStatus`，同名项只保留第一项。只使用 `name` 和 `settingsPath`：

- 路径非空：

```text
请前往「{settingsPath}」，为「{name}」开启权限，然后再试。
```

- 路径为空：

```text
请为「{name}」开启权限，然后再试。
```

多个授权项逐行输出。不追加替代建议，不承诺授权后一定能生成，不输出能力 ID、授权类型或内部状态。

### 无有效授权明细

`stateOfPermission:false` 且没有有效明细时固定回复：

```text
当前生成卡片所需的数据权限不可用，已停止生成。
```

不得改写、增加前后缀、猜测设置路径或追加建议。

### 权限 invoke 异常

权限工具不可用、invoke 抛错、超时、传输失败，或工具层明确报告执行失败且没有正常权限结果时，不向用户输出异常话术或权限说明，按权限默认开启继续调用生成工具。不得重试权限工具、构造虚假权限结果或宣称权限已开启；最终只按生成工具结果回复。

### 权限结果非法

权限工具正常返回但字段缺失或类型非法时使用其它异常话术，不调用生成工具、不输出 `genWidgetResult`，edit 不更换来源。明确拒绝、有效未授权明细和正常返回结果非法都不适用 invoke 异常默认开启。

## 生成后回复

按以下固定顺序处理，不得交换第 1、2 步：

1. 只从当前生成调用的可解析业务 payload 读取并锁存合法真实 `artifactUrl`；不把 `streamInfo`、工具外层字段、历史结果或普通文本当作 URL。
2. 得到 `mustEmitGenWidgetResult`，其值只由第 1 步决定，后续状态判断不得修改。
3. 根据状态选择自然语言。只有完整 `success` 可以使用业务 `message`；其它状态不透传、不润色 `message`。
4. `mustEmitGenWidgetResult` 为 `true` 时，在同一条回复中紧接自然语言输出一个 `genWidgetResult` 代码块；为 `false` 时不输出。
5. 通过发送前硬检查后才能结束本轮。

### 完整 success

````text
{message；为空时 create 使用“已为你生成卡片。”，edit 使用“已按你的要求修改卡片。”}

```genWidgetResult
{
  "result": "{artifactUrl}"
}
```
````

### 部分数据不支持

````text
本次卡片生成暂无你提及的 XX 数据，将基于可获取数据为你生成卡片

```genWidgetResult
{
  "result": "{artifactUrl}"
}
```
````

### 部分动作不支持

````text
本次卡片暂不支持你提及的 XX 操作，将保留可展示内容为你生成卡片

```genWidgetResult
{
  "result": "{artifactUrl}"
}
```
````

### 部分素材不支持

````text
本次卡片暂无法使用你提及的 XX 素材，将使用可用样式为你生成卡片

```genWidgetResult
{
  "result": "{artifactUrl}"
}
```
````

### 混合缺失

````text
本次卡片暂无法完整支持你提及的 XX，将基于可用内容为你生成卡片

```genWidgetResult
{
  "result": "{artifactUrl}"
}
```
````

部分满足包括：

- `degraded` 且有合法 URL。
- `success` 且有合法 URL，但本轮概述、schema、候选删减或移除结果证明用户部分需求缺失。

### 整体不支持

```text
抱歉，当前暂无法获取你提及的 XX 功能数据。你可以试试：“建议一”、“建议二”
```

通常没有 URL；若异常 payload 同时提供合法真实 URL，仍追加 `genWidgetResult`，不得因状态抑制 URL。

### 其它异常

```text
卡片创建过程遇到问题了，请稍后再试
```

适用于 `failed`、必要工具异常、payload 异常，或 `success/degraded` 缺少合法 URL。没有 URL 时不输出标记，不追加能力建议、失败原因或 edit 专属说明；若可解析 payload 已含合法真实 URL，仍追加标记。

## 发送前硬检查

在提交最终回复前逐项检查：

- 当前生成业务 payload 有合法真实 `artifactUrl` 时，回复中必须恰好有一个语言标签严格为 `genWidgetResult` 的代码块；没有 URL 时必须为零个。
- 代码块内容必须是合法 JSON 对象，只含一个 `result` 字段；`result` 必须是字符串，并与当前 payload 的 `artifactUrl` 逐字符相同。
- 标记必须与本次生成后的自然语言位于同一条最终回复中；不得仅输出成功说明、普通 Markdown 链接或把标记留到下一轮。
- `status`、自然语言模板、已发送的部分满足预告和 edit/create 模式都不得抑制合法 URL。
- 代码块之后不追加其它内容。任一项不满足时，先重写回复再发送。

可将发送条件视为以下不变量：

```text
hasValidArtifactUrl == hasExactlyOneValidGenWidgetResultBlock
genWidgetResult.result == artifactUrl
```

## 名称与推荐

替换 `XX` / `YY`：

1. 优先使用用户原话中的数据、动作、素材或需求类型，能力描述和移除结果只用于核对对应关系。
2. `YY` 使用仍会保留的用户可理解内容；多个名称去重后用“、”连接。
3. 不输出能力 ID、包名、provider、schema 字段或错误码。
4. 无法可靠提炼时，`XX` 使用“相关内容”，`YY` 使用“其他可用内容”。
5. 模板空格只标示占位符，实际中文自然拼接。

生成前结束或 `unsupported` 时提供 1～3 条可直接复述的需求：

- 已有合法概述：优先使用同领域、低风险且有完整卡片价值的数据或动作描述。
- 尚无合法概述：只使用天气、日程、运动、设备电量或系统状态等通用示例。
- 使用“可以试试”，不表达当前设备一定支持。
- 不编造动作目标、号码、deeplink、素材路径或用户数据。

## 话术边界

- 不说“已添加到桌面”；这里只生成预览 artifact，是否添加由端侧和用户确认。
- 不把部分满足描述成工程失败，不把整体不支持描述成系统异常。
- 不引导安装不确定的 App，不承诺开启权限后一定可用。
- 用户可见回复不暴露工具包络、内部字段、来源 URL、CardSpec、DSL 或校验细节。
