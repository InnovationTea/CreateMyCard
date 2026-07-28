# 回复策略

同时处理生成前决策、数据权限结果和 `generateWidgetCard` 业务结果。生成前可以追问、说明调整、结束并引导，或在权限明确拒绝时终止；调用生成接口后仍按 `success`、`degraded`、`unsupported`、`failed` 映射。不要复述内部候选计划、schema、CardSpec、DSL、来源 URL 或校验细节。

## 生成前决策

| 决策 | 判定 | 工具行为 | `genWidgetResult` |
| --- | --- | --- | --- |
| 继续生成 | 核心内容可满足，或静态入口/动作本身就是核心目标 | 继续当前流程 | 仅生成成功后输出 |
| 调整后生成 | 核心内容可满足，仅次要数据、动作或非核心素材不可用 | 先告知调整，再自动继续 | 仅生成成功后输出 |
| 追问 | 是否做成卡片仍有歧义，或缺少会改变核心意图的用户可回答信息 | 不调用下一工具，等待回答 | 否 |
| 结束并引导 | 需求不适合桌面卡片，或没有任何核心能力且无法形成满足原意图的静态/入口卡 | 停止后续工具 | 否 |

生成前结束不伪造 `unsupported` 业务 payload。工具失败或 payload 非法归为其它异常，不根据未知能力推荐场景。

## 生成结果映射

先判断 URL，再判断状态话术：`generateWidgetCard` 业务 payload 只要含有合法真实 `artifactUrl`，就必须输出 `genWidgetResult`，`degraded` 也不例外；业务状态不能抑制 URL 标记。没有 URL 时绝不输出。

| 对端结果 | 判定条件 | 是否输出 `genWidgetResult` |
| --- | --- | --- |
| 完整成功 | `success`，存在有效 `artifactUrl`，且没有已知的用户需求缺失 | 是，使用正常成功说明 |
| 部分满足 | `degraded` 且存在有效 `artifactUrl`；或 `success` 且存在有效 URL，但本轮已知部分用户需求缺失 | 是，按数据、动作、素材或混合缺失使用受控话术 |
| 整体不支持 | 业务 payload 为 `unsupported` | 无 URL 时否；若 payload 同时返回合法 URL，仍必须输出 |
| 需要手动授权 | `RequestDataPermission` 返回非空 `result.nonAuthStatus`，或任一权限项 `authorized: false` | 否，立即终止并按授权项引导用户手动授权 |
| 权限不可用 | `RequestDataPermission` 返回 Boolean `result.stateOfPermission: false`，且 `nonAuthStatus` 缺失或为空 | 否，立即终止并使用通用权限话术 |
| 其它异常 | `failed`、必要工具不可用、调用异常、payload 无法解析、状态非法，或 `success` / `degraded` 缺少有效 `artifactUrl` | 无 URL 时否；若可解析 payload 含合法 URL，仍必须输出 |

edit 模式的新 `artifactUrl` 还必须不同于 `sourceArtifactUrl`；缺失、无效或与来源相同时归为其它异常，不得回用来源 URL 伪装编辑成功。

## 通用规则

- 调用工具前存在会改变核心意图、候选选择或必填业务入参的待确认信息时，只提出最小必要问题并等待用户回答；此时不调用工具，也不输出结果话术或 `genWidgetResult`。
- 非空数据能力集合必须先调用 `RequestDataPermission`；在得到明确权限结果前不得调用 `generateWidgetCard`。数据集合为空时跳过权限工具。
- 当前工具快照中只将 Boolean `result.stateOfPermission: true`、`result.nonAuthStatus` 缺失或为空数组，且返回中的权限项均未出现 Boolean `false` 视为通过。权限结果实行一票否决：`stateOfPermission` 或任一权限项 `authorized` 为 `false` 时立即结束任务并拒绝继续生成，不调用生成工具；有明细时进入手动授权引导，无明细时视为权限不可用。字段缺失、类型非法、调用失败或工具不可用均归为其它异常，不调用生成工具。
- 核心内容可满足而仅次要内容不可用时，不询问是否继续；先输出部分满足预告，再自动完成生成。
- 用户明确“必须包含，否则不要生成”的能力已知不可用时，结束并引导，不生成部分满足版本。
- 三个微服务工具返回的是包装结构：`streamInfo` 以及 `items`；如果运行环境返回原始插件包络，则先检查顶层 `errorCode/errorMessage/reply`。`errorCode` 非 `"0"` 时归为其它异常，为 `"0"` 时从 `reply.items` 继续解析。`RequestDataPermission` 按其当前运行时输出 schema 单独解析，不套用生成业务状态。
- 三个微服务工具的业务结果必须先从当前工具对应的 `items[].data` 解析。`items[].status` 是工具层状态，不等同于 `generateWidgetCard` 业务 payload 的 `status`；`RequestDataPermission` 按其独立输出 schema 解析。
- `items[].data` 是 JSON 字符串时先解析为对象；解析失败、缺少 `data` 或 `items[].error` 表示失败时，归为其它异常。
- 只认可 `success`、`degraded`、`unsupported`、`failed` 四种业务状态；其它值归为其它异常。
- 合法真实 `artifactUrl` 是输出 `genWidgetResult` 的充分条件：只要 URL 存在就必须输出，`degraded` 也不得省略。代码块内容必须是合法 JSON 对象：`{"result":"artifactUrl"}`；没有真实 URL 时绝不输出标记。
- 除完整成功外，不透传、不拼接、也不润色业务 payload 的 `message` 或旧字段 `userMessage`。工具或微服务提供的原因只可用于内部判定和提炼 `XX`。
- edit 模式完整成功或部分满足后，将本轮新 URL 作为后续未指定目标编辑的默认来源；其它结果不更换默认来源。
- 用户可见回复不要暴露 capabilityId、provider、TaskSpec、OBS、IDS、errorCode、requestId、items 或原始 data 字符串。

## 名称提炼

模板中的 `XX` 和 `YY` 必须替换：

1. `XX` 优先使用用户原话中的数据、动作、素材或需求类型，并用能力描述、`unavailableCapabilities`、`missingCapabilityIds` 和 `removedCapabilities` 仅作对应关系校验。
2. `YY` 使用仍会保留的用户可理解内容；多个名称去重后用“、”连接。
3. 不输出技术 ID、包名、provider、schema 字段名或错误码。
4. 无法可靠提炼时，`XX` 使用“相关内容”，`YY` 使用“其他可用内容”。
5. 模板中的空格用于标示占位符，实际回复按中文自然拼接，例如输出“日程数据”，不要输出“日程 数据”。

## 权限未通过

### 需要手动授权

条件：`RequestDataPermission` 返回非空 `result.nonAuthStatus`，或任一权限项 `authorized` 为 Boolean `false`。数组项必须是对象，`name` 必须是非空字符串，`settingsPath` 缺失时按空字符串处理；其它类型错误按工具结果非法处理。

处理规则：

- 立即终止本轮，不调用 `generateWidgetCard`，不输出 `genWidgetResult`；edit 模式不更换当前默认来源 URL。
- 只使用 `name` 和 `settingsPath`，不暴露 `capabilityId`、`authType`、`authorized` 或其它内部字段。
- 按返回顺序输出授权项，同名项只保留第一项。
- `settingsPath` 为非空字符串：

```text
请前往「{settingsPath}」，为「{name}」开启权限，然后再试。
```

- `settingsPath` 缺失或为空：

```text
请为「{name}」开启权限，然后再试。
```

多个授权项逐行输出对应指引，不追加替代建议，也不承诺授权后一定能够生成。

### 无授权明细

条件：`RequestDataPermission` 返回 Boolean `result.stateOfPermission: false`，且 `nonAuthStatus` 缺失或为空数组。

固定回复：

```text
当前生成卡片所需的数据权限不可用，已停止生成。
```

立即终止本轮，不调用 `generateWidgetCard`，不输出 `genWidgetResult`，不追加猜测的开启权限路径、替代建议或内部权限字段。edit 模式不更换当前默认来源 URL。

## 推荐生成规则

生成前结束或微服务返回 `unsupported` 时提供 1 至 3 条可直接复述的需求：

- 已取得合法能力概述时，优先从本轮 `dataCapabilities` 和可安全理解的 `eventCapabilities` 描述中选择同领域、低风险、有完整卡片价值的场景。
- 尚未取得能力概述时，只使用天气、日程、运动、设备电量或系统状态等一期通用示例。
- 使用“可以试试”，不写“当前设备支持”“一定可以生成”。
- 不编造事件目标、号码、deeplink、intent、素材路径或用户数据。
- 每条建议使用引号包裹完整需求，用户下一轮可直接选择或复述。

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

输出预告后直接继续流程，不等待用户回复。若后续工具失败，最终只输出其它异常话术。

### edit 新增能力

```text
当前连续编辑暂不支持新增 XX，这次先不修改。你可以重新创建一张卡片，例如：“重新创建需求”
```

纯视觉、布局、文案、尺寸、删除数据能力或修改已有数据参数不使用该模板，仍按 edit 契约处理。

## 生成后回复

### 完整 success

````text
{message；为空时，create 使用“已为你生成卡片。”，edit 使用“已按你的要求修改卡片。”}

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

### 整体不支持

```text
抱歉，当前暂无法获取你提及的 XX 功能数据。你可以试试：“建议一”、“建议二”
```

不得输出 `genWidgetResult`，不得使用微服务 `message`。优先使用本轮能力概述构造建议；没有可用概述时使用通用示例。

### 其它异常

```text
卡片创建过程遇到问题了，请稍后再试
```

不得输出 `genWidgetResult`，不得使用微服务 `message`，不得追加能力建议、失败原因或编辑专属说明。

## 话术边界

- 不承诺“开启权限后一定可用”，不引导用户安装不确定的 App。
- 不说“已添加到桌面”；这里只生成预览 artifact，是否添加由端侧和用户确认。
- 不把部分满足描述成工程失败，也不把整体不支持描述成系统异常。
- 没有授权明细时，通用权限不可用话术不得改写同义句、增加前后缀、追加建议或拼接工具自定义文案。
- 存在授权明细时，只按 `name` 与 `settingsPath` 模板逐项引导，不补充工具未返回的路径，不输出其它授权字段。
- 其它受控核心句只替换占位符、填充建议，并按规定追加 `genWidgetResult`。
