---
name: harmony-card-generation-online-directive
description: "仅用于为小艺/HarmonyOS 创建或连续编辑可添加到桌面的服务卡片。仅当当前请求或可追溯上下文明确要求桌面卡片、服务卡片、widget、小组件、添加到桌面、修改已有桌面卡片，并且全部所需内容仅属于天气、日程与时间、闹钟、电话、运动和健康、睡眠统计、设备状态、系统设置、位置、音乐控制、指定 App 使用时长、雨天打车、会议时使用；组合需求的每一项都必须在此范围内。不要用于普通对话，任何范围外或无法归类的内容，银行卡、会员卡、贺卡、名片、游戏卡牌、普通网页/UI 卡片等泛卡片语义；卡片意图、内容范围不明确时也不使用。"
metadata:
  tools:
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "getWidgetCapabilityOverview"
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "getDataCapabilitySchemas"
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "RequestDataPermission"
    - bundleName: "com.omega_w_0823.hmservice"
      toolName: "generateWidgetCardCompactDslWithDirective"
---

# Harmony 卡片云侧编排

## 目标与边界

只执行编排：识别 create/edit、判断需求适配、选择候选、执行生成前能力与权限门禁、调用工具并组织用户回复。不得自行生成、修改或校验卡片 DSL、CardSpec、artifact 或其它替代产物。

## 执行入口

每个任务开始时读取且只读取一次 [`references/runtime-guide.md`](references/runtime-guide.md)，create、edit、权限、异常和结果交付全部按该文件执行。正常运行路径不得继续加载其它 reference。

- 仅当用户明确要求联调、排障或回归核对时，额外读取 [`references/examples.md`](references/examples.md) 或 [`references/tools/`](references/tools/) 中与目标工具对应的一份静态快照。
- 示例和快照不能授权额外字段，也不能覆盖当前运行时工具 schema。

## 执行流程
主流程固定为：识别 create/edit → 检查用户必填信息 → 获取能力概述 → 选择候选并按需加载数据 schema → 检查最终数据权限 → 调用生成工具 → 按状态组织自然语言回复。

四个工具按以下顺序和职责使用：

1. `getWidgetCapabilityOverview`：create 和删除数据/修改数据参数的 edit 获取当前可用数据、事件和素材概述；纯视觉 edit 可跳过。
2. `getDataCapabilitySchemas`：存在数据候选时，只为已选且实际可用的数据能力加载完整 schema；没有数据候选时跳过。
3. `RequestDataPermission`：生成前检查最终、完整、去重后的数据能力集合；集合为空时跳过。纯视觉 edit 若来源含动态数据，仍须检查继承的数据权限。
4. `generateWidgetCardCompactDslWithDirective`：只有前置门禁通过，或权限工具发生允许放行的 invoke 级异常时才调用；主 Agent 不补做微服务负责的 DSL、CardSpec、校验、重试或上传。

```text
getWidgetCapabilityOverview → getDataCapabilitySchemas（有数据候选时）→ RequestDataPermission（数据集合非空时）→ generateWidgetCardCompactDslWithDirective
```

## 工具调用

依赖 frontmatter 声明的三个微服务工具和一个端工具。使用统一调用格式：

```text
invoke(functionName:"<toolName>", arguments:{bundleName:"com.omega_w_0823.hmservice", ...},"skillName":"harmony-card-generation-online-directive")
```

## 不可绕过的重要约束

1. 当前运行时 schema 是工具入参的唯一依据。
2. 主 Agent 不下载或解析来源 artifact，不自行生成最终 DSL、CardSpec 或替代 artifact。
3. 权限工具正常返回时，只有 `stateOfPermission:true`、`nonAuthStatus` 缺失或为空，且任一权限项都没有 `authorized:false` 才允许生成。任一授权不通过、存在未授权明细或正常返回结果非法时立即终止，不调用 `generateWidgetCardCompactDslWithDirective`。
4. `RequestDataPermission` 工具不可用、invoke 抛错、超时、传输失败或工具层明确执行失败，且没有正常权限结果时，按权限默认开启静默放行并继续调用生成工具；不重试、不伪造权限结果、不改变数据集合，也不向用户说明权限异常。
5. 除上述权限 invoke 级异常外，任一必要工具失败或结果非法都终止本轮，不模拟成功。
6. 生成工具返回后，先解析当前业务 payload 的状态并组织话术；合法真实 `artifactUrl` 只用于连续编辑链追溯。
7. 卡片结果由生成工具的 directive 指令帧提前下发。主 Agent 不得再次输出产物 URL、结果代码块或其它重复交付标记。
8. 用户可见回复不暴露能力 ID、schema、provider、TaskSpec、OBS、IDS、错误码、请求 ID、工具包络或内部草稿。
