# AI 卡片端到端日志定位指南（初稿）

本文用于定位小艺 App 创建 AI 卡片过程中的问题，包括未进入卡片流程、未调用生成工具、
生成失败，以及云侧已生成但端侧未展示等情况。

排查以 `sessionId` 为主线：先查看用户实际遇到的现象，再沿调用链确认请求到达了哪里、
每一段返回了什么，找到最后一个正常节点与第一个异常节点。

本文的跨系统链路、平台用途和 DM 关键词来自当前联调经验；微服务日志名称已对照当前仓库核实。
平台入口、MCP 专用日志和部分端侧细节尚待补充，线上排查时需核对部署版本。

## 1. 链路与平台

请求调用顺序：

```text
小艺 App → DM → MCP → agentRuntime → 卡片微服务（当前项目）
```

从业务执行角度看，内部 AgentLoop 平台将微服务包装成工具，结合
`skills/harmony-card-generation-online/` 中的在线 Skill 完成卡片需求。
Skill 负责需求判断与工具编排；微服务负责能力裁决、卡片生成、校验和产物存储。
生成后的产物链接通过工具内部通道交付端侧，端侧下载并完成解析、预览和添加。

这里的请求调用顺序与产物交付是两个观察方向；指令返回经过的具体模块和日志位置需继续补齐。

| 入口或模块 | 主要查看内容 | 要回答的问题 |
| --- | --- | --- |
| 华山 ping 平台 | 通过 sessionId 查看用户 App 界面结果 | 用户看到的是未进入流程、生成异常，还是展示异常？ |
| DM | 意图识别、技能召回、决策、端工具执行与事件回报 | 请求是否命中目标意图，并进入正确执行流程？ |
| MCP | 工具请求接入、转发与返回，具体关键词待补充 | 上游请求是否成功传到 agentRuntime？ |
| AgentLoop / agentRuntime | Skill 执行、工具输入输出、指令记录 | 是否执行在线 Skill，在哪一步停止或失败？ |
| 卡片微服务 | 入口请求、能力过滤、生成结果、异常与耗时 | 是否收到请求，是否生成有效产物？ |
| App 端侧 | 创建流程、指令接收、产物下载与渲染 | 云侧结果是否真正展示给用户？ |

## 2. 开始定位前，先收齐上下文

至少记录以下信息，避免查错环境或混入其它轮次：

- 环境、问题发生时间及其时区。
- 完整 `sessionId`；能获取时同时记录 `interactionId`。
- 用户原始 query，以及本轮属于首次创建还是继续修改。
- App 版本、ROM 版本和设备型号。
- 华山 ping 中的实际界面结果，以及用户预期结果。

### 2.1 sessionId 与微服务轮次标识

`sessionId` 用于跨模块串联会话。微服务收到完整会话字段时，使用下面的形式生成 `requestId`：

```text
sessionId&interactionId
```

例如笔记中的 `44d6605265a5&2` 可以作为轮次检索串；实际排查应优先使用完整值。
当前实现只有 `sessionId` 时会使用 `sessionId`，因此不能要求所有请求都有 `&轮次` 后缀。

同一个会话可能包含多轮修改和多个工具调用。先用 `sessionId` 找全链路，
再结合轮次、时间和 `operation` 定位某一次调用，避免把上一轮成功当成本轮成功。

微服务入口还有 `user_trace_hash` 和 `device_trace_hash`，可辅助检索。
哈希不是 `sessionId`，按哈希命中的记录仍需回到会话与时间范围核对。

## 3. 推荐的定位顺序

1. 在华山 ping 中输入 `sessionId`，确认用户界面上的真实结果。
2. 查看微服务是否收到本轮生成请求，以及是否出现生成完成日志，快速确定大致范围。
3. 如果没有生成请求，回到 AgentLoop 检查 Skill 和工具轨迹，再向上排查 MCP、DM。
4. 如果请求已经进入微服务，沿入口、能力裁决、模型生成、校验和产物存储继续定位。
5. 如果微服务已生成产物，检查结果返回、指令下发、端侧接收、下载和渲染。

| 观察到的现象 | 优先检查 | 当前证据的边界 |
| --- | --- | --- |
| App 未进入卡片流程 | DM 意图、Skill 召回、端侧 `createNewFlow` | 仅凭界面不能确定是哪一个模块异常 |
| AgentLoop 中没有目标工具调用 | 在线 Skill 执行、能力判断、权限结果 | 可能是正常提前结束，需要看停止原因 |
| AgentLoop 已调用工具，微服务没有入口日志 | MCP / agentRuntime 转发、目标实例与日志范围 | 不能仅凭一次搜索无结果判定微服务未收到 |
| 有能力概述请求，没有生成请求 | AgentLoop 后续决策、权限检查、工具错误 | 能力概述成功不代表一定继续生成 |
| 有生成请求，没有有效产物 | 微服务异常、模型、校验、存储及最终返回 | 完成日志缺失本身不能说明具体失败原因 |
| 有成功日志，App 没有卡片 | 结果返回、指令、下载、解析、渲染 | 云侧生成成功不等于端侧展示成功 |

搜索无结果时，先核对环境、时间范围、实例、日志轮转以及日志是否完整，再判断链路是否中断。

## 4. DM：从意图识别排到端工具执行

查询时先按本次 `sessionId` 和发生时间限定范围。日志过多时，可临时排除
`MessagesLlmProcessor`；需要检查模型处理细节时再去掉排除条件。

### 4.1 NLU 是否识别出目标意图

检索：

```text
obtain intent
```

如果没有目标意图，继续查看 NLU 请求体：

```text
Unify nluReq:
```

- 请求中有 `availableSkill`：确认列表里是否包含目标技能，再检查 NLU 为什么没有选择目标意图。
  按当前联调分工，可联系 NLU：张俊，并提供请求体与意图结果。
- 请求中没有技能列表，或列表缺少目标技能：继续检查 SkillGate 的召回结果。

```text
print searchSkillInfo response
SkillInfoResponse skillInfos:
```

如果 SkillGate 未返回预期技能，按当前联调分工联系 SkillGate：陈淼。
需要同时带上版本信息、查询请求和返回列表，避免只提供“没有召回”的结论。

### 4.2 端工具是否被识别为支持

相关方法：

```text
com.huawei.dialog.external.skilltoolexecutor.ToolDiscoveryRegistry#isToolSupportedInDeviceToolCenter
```

检索：

```text
Device tools aliases support toolName:
doSkillGateClientToolAlias skillName:
SkillInfoResponse skillInfos:
update clientToolPrimary:
```

依次核对工具支持判断、技能与工具别名映射、技能列表，以及端工具动态更新结果。
出现日志关键词只说明执行到了该处，还要检查具体工具名和返回值。

### 4.3 DS 是否选择目标意图

NLU 已识别出目标意图后，继续检索：

```text
ds response
```

检查 DS 最终决策是否仍是目标意图，技能是否为 `huawei.device.tool.executor`。
如果 NLU 结果正确而 DS 决策不符，应继续定位决策阶段。

### 4.4 端工具执行参数是否正确

关注 `DeviceToolExecutorExecMethod`，并检索实际构造的参数：

```text
ToolExecuteInvokeClientTool buildPayload:
```

核对目标工具、调用参数、会话关联信息是否符合本次操作。
同时查看给端侧下发的指令：

```text
EventDirectiveManager directiv
```

### 4.5 是否收到端侧执行回报

检索：

```text
Access request body:
ToolExecute-InvokeRsp
```

当前联调经验是：正常情况下端侧约在 1 秒内上报 `ToolExecute-InvokeRsp`。
如果迟迟没有回报，重点排查指令送达、端工具执行、回报通道和超时。
这里的 1 秒是经验观察值，正式超时阈值待补充，不能仅凭超过 1 秒就判定执行失败。

## 5. MCP 与 AgentLoop：确认工具调用在哪里停止

在 AgentLoop 中找到同一会话，按执行顺序查看：

1. 是否加载了目标在线 Skill，以及实际版本。
2. 是否调用 `getWidgetCapabilityOverview`，输入与返回是否正常。
3. 需要数据 schema 时，是否调用 `getDataCapabilitySchemas`。
4. 使用数据能力时，是否调用 `RequestDataPermission`，以及权限结果如何影响后续执行。
5. 是否调用 `generateWidgetCardCompactDsl`，参数是否对应本轮 query。
6. 工具是否返回结构化结果，状态、产物链接和错误信息是什么。
7. 是否存在后续指令记录，以及它与端侧日志能否对应。

没有生成调用时，应先阅读 Agent 的停止原因。当前方案允许因需求不适合卡片、
核心能力不支持或权限门禁未通过而提前结束；这些情况需要与编排异常区分。
权限工具的 invoke 异常与正常返回的拒绝结果处理不同，具体以方案中的权限规则为准。

现有联调检索词：

```text
AIWidgetStart
directives
harmony-card-generation-online-directive
```

`harmony-card-generation-online-directive` 作为现有检索词保留，
其与仓库在线 Skill 名称的部署映射待补充。
`AIWidgetStart` 命中后还要查看指令内容和状态，不能仅凭名称判断生成成功。

MCP 的专用入口、转发、返回及异常关键词待补充。
当前可按 `sessionId` 对照 DM、MCP 和 agentRuntime 的时间线，
确认上一段的输出是否成为下一段的输入，并记录具体中断位置。

## 6. 微服务：从收到请求排到产物生成

常用日志文件：

```text
/opt/huawei/logs/genui-agent-service/debug/debug_python.log
/opt/huawei/logs/genui-agent-service/debug/debug.log
```

下列命令在日志所在的 Linux 环境执行。使用 `grep -F` 按字面值查找，
直接替代日常的 `cat 文件 | grep` 写法；下划线不需要转义。

### 6.1 设置本次检索变量

```bash
LOG_DIR='/opt/huawei/logs/genui-agent-service/debug'
PY_LOG="$LOG_DIR/debug_python.log"
APP_LOG="$LOG_DIR/debug.log"
SESSION_ID='替换为完整sessionId'
REQUEST_ID="${SESSION_ID}&2"  # 将 2 替换为实际 interactionId
```

先查会话，再缩小到具体轮次：

```bash
grep -nF -- "$SESSION_ID" "$PY_LOG"
grep -nF -- "$REQUEST_ID" "$PY_LOG" | grep -F -- 'request_body='
```

如果请求没有 `interactionId`，直接用 `SESSION_ID` 检索。
请求体可能较长，查看参数细节时应保留完整日志行。

### 6.2 确认能力概述请求和生成请求到达

```bash
grep -F -- "$SESSION_ID" "$PY_LOG" \
  | grep -F -- 'widget_operation_ws_raw_request_received operation=getWidgetCapabilityOverview'

grep -F -- "$REQUEST_ID" "$PY_LOG" \
  | grep -F -- 'widget_operation_ws_raw_request_received operation=generateWidgetCardCompactDsl'
```

入口日志在完整协议校验前打印，包含 `operation`、用户与设备哈希以及 `request_body`。
因此“有原始入口日志”只说明请求已经到达，还要确认后续参数解析和业务处理是否成功。

可继续检索这些已核实的节点：

```text
widget_operation_ws_payload_received
widget_operation_ws_message_received
widget_operation_ws_handler_completed
widget_operation_ws_invalid_arguments
widget_operation_ws_failed
```

### 6.3 检查应用依赖与能力过滤

```bash
grep -F -- "$SESSION_ID" "$PY_LOG" \
  | grep -F -- 'capability_package_dependency_checked result='
```

重点读取 `result` 中的字段：

| 字段 | 查看内容 |
| --- | --- |
| `idsQueryStatus` | 安装应用查询状态 |
| `filterPackages` / `checkedPackages` | 本次查询和检查覆盖了哪些包 |
| `matchedPackages` / `missingPackages` | 哪些依赖命中，哪些未命中 |
| `dataCapabilityPackageStatuses` | 数据能力对应的包依赖状态 |
| `removedCapabilities` | 因包未安装而移除的能力及原因 |

此处的 `removedCapabilities` 只覆盖该日志记录的包依赖移除原因；
最终还有哪些能力被移除，应结合生成汇总中的 `removed_capabilities` 判断。
查询状态异常时，也不要只看到 `missingPackages` 就断言用户未安装应用。

### 6.4 确认生成结果

保留原来“查看全部成功结果”的用法：

```bash
grep -F -- 'generate_widget_card_completed status=success artifact_url=' "$PY_LOG"
```

定位单次问题时，使用本轮标识并查看所有完成状态，避免漏掉降级结果：

```bash
grep -F -- "$REQUEST_ID" "$PY_LOG" | grep -F -- 'generate_widget_card_completed'
grep -F -- "$REQUEST_ID" "$PY_LOG" | grep -F -- 'widget_generation_summary'
```

| 结果状态 | 含义与后续动作 |
| --- | --- |
| `success` | 云侧生成成功，继续核对结果返回与端侧展示 |
| `degraded` | 已生成产物，但需求部分满足；核对移除项和用户回复 |
| `unsupported` | 当前请求不支持，查看具体原因 |
| `failed` | 生成失败，沿错误信息与失败阶段定位 |

并非所有失败路径都会打印 `generate_widget_card_completed`。
没有完成日志时，应结合最终工具响应、生成汇总和异常日志判断。
`widget_generation_summary` 可查看 `status`、`error_code`、`removed_capabilities`、
`latency_by_stage`、`retry_count` 和 `generation_mode` 等信息。

当前代码中，完成日志出现在产物存储之后，但这不证明工具响应、指令交付或端侧渲染已经成功。

### 6.5 查看失败节点

```bash
grep -F -- "$REQUEST_ID" "$PY_LOG" | grep -F \
  -e 'widget_operation_ws_invalid_arguments' \
  -e 'widget_operation_ws_failed' \
  -e 'a2ui_generation_failed' \
  -e 'strict_generation_validation_failed' \
  -e 'widget_generation_summary'
```

这些关键词用于快速找到线索，不是完整错误清单。
定位后应回看附近上下文与完整异常栈，避免后续行未带会话标识而被过滤掉。

### 6.6 按哈希辅助检索

```bash
TRACE_HASH='替换为日志中的完整哈希'
grep -F -- "$TRACE_HASH" "$PY_LOG" | grep -F -- 'request_body='
```

需要按用户哈希精确查入口时：

```bash
grep -F -- "user_trace_hash=$TRACE_HASH" "$PY_LOG" \
  | grep -F -- 'operation=generateWidgetCardCompactDsl'
```

### 6.7 查看 payload 与实时日志

```bash
grep -F -- "$REQUEST_ID" "$APP_LOG" | grep -F -- 'payload='

tail -F "$PY_LOG" | grep --line-buffered -F -- "$SESSION_ID"
tail -F "$APP_LOG" | grep --line-buffered -F -- "$SESSION_ID"
```

`tail -F` 适合跟随可能轮转的日志；`--line-buffered` 用于减少管道过滤造成的显示延迟。
`payload=` 是通用关键词，命中后需看完整日志所属模块，不能直接视为端侧已收到的指令。

需要减少周期性统计日志时：

```bash
grep -F -- "$SESSION_ID" "$PY_LOG" | grep -vF -- 'websocket_metrics'
```

原笔记中的 `not like bsocket_metri` 可对应排除这类统计日志。
日志平台中的包含、排除语法以实际平台为准，本文不假定其支持 SQL。

## 7. 云侧有产物，但 App 没有展示

按以下顺序核对证据：

1. 本轮完成日志是否有真实产物链接，最终工具响应是否也返回了该结果。
2. agentRuntime 中是否有对应的 `AIWidgetStart` / `directives` 记录，具体状态与内容是什么。
3. DM 是否存在对应的指令下发记录，端侧是否收到同一条指令。
4. 端侧是否进入预期创建流程，可先用 `createNewFlow` 检索相关上下文。
5. 端侧是否下载到产物，下载内容是否完整，解析和渲染是否报错。
6. 华山 ping 中的最终界面是否与上述执行结果一致。

上述顺序用于逐段核对交付证据；具体指令路由与日志归属仍需结合线上实现确认。
端侧下载和渲染的日志关键词待补充。

当前方案由工具内部交付产物链接，主 Agent 的自然语言回复不承担渲染触发职责。
因此不要用“回复里没有链接”判断交付失败，也不要仅凭“已为你创建卡片”的文案判断展示成功。

## 8. 中控配置与其它检索线索

当前笔记保留了以下中控检索项：

```text
hivoice.search.unified.config
taichu
```

可作为检查技能分发、召回配置的线索；配置入口、字段含义、灰度范围及生效方式待补充。
涉及技能未加载时，同时核对 App / ROM 版本和线上实际生效配置。

## 9. 问题记录模板

```text
【问题现象】
用户 query：
预期结果：
华山 ping 中的实际结果：

【定位信息】
环境 / 时间 / 时区：
sessionId：
interactionId / 微服务 requestId：
App / ROM 版本及设备型号：
首次创建 / 多轮修改：

【链路证据】
DM：目标意图、SkillGate 结果、DS 决策、工具参数与回报
MCP：请求接入、转发与返回
AgentLoop：在线 Skill、工具调用顺序、停止原因或最终结果
微服务：入口、能力过滤、生成状态、错误码与耗时
指令与端侧：下发、接收、下载、解析、渲染

【当前结论】
最后一个已确认正常的节点：
第一个出现异常或缺失证据的节点：
支持结论的日志时间与原文：
仍待确认的内容：
下一步处理人与动作：
```

## 10. 后续补充清单

- 华山 ping、AgentLoop 和各模块日志平台的入口及查询示例。
- 一条成功会话的完整样例，标注每段的时间、会话标识和预期结果。
- MCP 接入、转发、返回、超时的关键词和日志位置。
- agentRuntime 与 AgentLoop 的页面对应关系，以及在线 Skill 的部署名称和版本查看方法。
- 指令从微服务返回到端侧的实际路由，各阶段的成功与失败样例。
- `createNewFlow` 及端侧下载、解析、渲染、添加卡片的关键词。
- 中控配置含义、生效条件和端工具正式超时阈值。
- 各模块负责人、常见问题及已验证的处理办法。

## 参考依据

- [云侧方案设计](../../docs/云侧方案设计.md)：系统边界、在线流程、产物交付与日志规范。
- [微服务请求路由](../cloud/api/routes.py)：会话轮次标识、原始请求与处理阶段日志。
- [设备能力裁决](../cloud/services/device_capability_resolver.py)：应用依赖检查日志。
- [卡片生成服务](../cloud/services/widget_generation_service.py)：生成完成与汇总日志。
- [卡片指令构造](../cloud/services/widget_directive.py)：`AIWidgetStart` 和 `directives` 内容。
