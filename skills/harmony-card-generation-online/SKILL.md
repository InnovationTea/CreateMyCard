---
name: harmony-card-generation-online
description: "用于为小艺/HarmonyOS 创建或连续编辑可添加到桌面的服务卡片。仅当用户明确要求桌面卡片、服务卡片、widget、小组件、添加到桌面或修改已有桌面卡片时使用。动态数据范围仅限：天气与未来预报、日历日程与会议、指定日期倒计时、指定 App 今日使用时长、蓝牙耳机连接与电量、手机电池与充电健康、睡眠与健康运动。点击动作范围仅限：拨号、清理运行内存，打开指定设置页，打开天气城市页、闹钟、音乐歌单、运动健康锻炼或睡眠页、日程详情或会议，导航确切位置，以及开启或关闭省电模式。卡片组合需求的每项动态数据和动作都必须在上述范围内。不要用于普通对话、卡片意图不明、其他任意非华为自带 App 数据或操作、银行卡、会员卡、名片、游戏卡牌、普通网页/UI 等泛卡片语义。"
metadata:
  tools:
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "getWidgetCapabilityOverview"
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "getDataCapabilitySchemas"
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "RequestDataPermission"
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "generateWidgetCardCompactDsl"
---

# Harmony 卡片云侧编排

## 目标与边界

只执行编排：识别 create/edit、判断需求适配、选择候选、执行生成前能力与权限门禁、调用工具并组织用户回复。不得自行生成、修改或校验卡片 DSL、CardSpec、artifact 或其它替代产物。

## 执行入口

每个任务开始时读取且只读取一次 [`references/runtime-guide.md`](references/runtime-guide.md)，create、edit、权限、异常和结果交付全部按该文件执行。正常运行路径不得继续加载其它 reference。

- 仅当用户明确要求联调、排障或回归核对时，额外读取 [`references/examples.md`](references/examples.md) 或 [`references/tools/`](references/tools/) 中与目标工具对应的一份静态快照。
- 示例和快照不能授权额外字段，也不能覆盖当前运行时工具 schema。

## 执行流程
主流程固定为：识别 create/edit → 检查用户必填信息 → 获取能力概述 → 选择候选并按需加载数据 schema → 检查最终数据权限 → 调用生成工具 → 按 URL 原子交付结果。识别为 create 后，必须以本轮工具结果完整执行四工具链；不得以历史对话、此前卡片、缓存、经验或“需求相似”为由跳过、替代或复用任一前置步骤。

四个工具按以下顺序和职责使用：

1. `getWidgetCapabilityOverview`：每个 create 必须调用，获取本轮当前可用数据、事件和素材概述；删除数据/修改数据参数的 edit 也调用，纯视觉 edit 可跳过。
2. `getDataCapabilitySchemas`：create 或数据类 edit 存在本轮数据候选时必须调用，只为已选且实际可用的数据能力加载完整 schema；只有本轮确无数据候选时才能不调用，不能因历史 schema 跳过。
3. `RequestDataPermission`：生成前检查本轮最终、完整、去重后的数据能力集合；集合非空时必须调用，只有集合为空时才能不调用。纯视觉 edit 若来源含动态数据，仍须检查继承的数据权限。
4. `generateWidgetCardCompactDsl`：只有前置门禁通过，或权限工具发生允许放行的 invoke 级异常时才调用；主 Agent 不补做微服务负责的 DSL、CardSpec、校验、重试或上传。

```text
getWidgetCapabilityOverview → getDataCapabilitySchemas（有数据候选时）→ RequestDataPermission（数据集合非空时）→ generateWidgetCardCompactDsl
```

## 工具调用

依赖 frontmatter 声明的三个微服务工具和一个端工具。使用统一调用格式：

```text
invoke(functionName:"<toolName>", arguments:{bundleName:"com.omega_w_0823.hmservice", ...},"skillName":"harmony-card-generation-online")
```

## 不可绕过的重要约束

1. 当前运行时 schema 是工具入参的唯一依据。
2. 主 Agent 不下载或解析来源 artifact，不自行生成最终 DSL、CardSpec 或替代 artifact。
3. 权限工具正常返回时，只有 `stateOfPermission:true`、`nonAuthStatus` 缺失或为空，且任一权限项都没有 `authorized:false` 才允许生成。任一授权不通过、存在未授权明细或正常返回结果非法时，必须立即终止，不调用 `generateWidgetCardCompactDsl`，并且只能按运行指南的预置权限话术回复用户。
4. 唯一的权限放行例外是本次 `RequestDataPermission` 工具调用失败，包括工具不可用、invoke 抛错或工具层明确执行失败；仅在此条件下按权限默认开启静默放行并继续调用生成工具。不重试、不伪造权限结果、不改变数据集合，也不向用户说明权限异常。
5. 除上述权限 invoke 级异常外，任一必要工具失败或结果非法都终止本轮，不模拟成功。
6. 生成工具返回后，先从当前可解析业务 payload 锁存合法真实 `artifactUrl`，再判断状态和话术。`streamInfo`、工具外层、历史回复或普通文本中的 URL 不算产物 URL。
7. 只要当前业务 payload 含合法真实 `artifactUrl`，同一条最终回复就必须且只能输出一个以下代码块；没有 URL 时不得输出，edit 返回来源 URL 时也按无有效新 URL 处理：

````text
```genWidgetResult
{
  "result": "{artifactUrl}"
}
```
````

8. `genWidgetResult` 必须位于自然语言之后，块内 JSON 只能包含字符串字段 `result`，其值与当前 `artifactUrl` 完全一致，代码块之后不得追加内容。
9. 用户可见回复不暴露能力 ID、schema、provider、TaskSpec、OBS、IDS、错误码、请求 ID、工具包络或内部草稿。
