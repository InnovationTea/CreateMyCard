# AI 卡片云侧项目协作说明

本文档面向参与本项目开发的工程师和 AI 编码助手。它只维护相对静态的项目背景、文件说明和协作规范；具体云侧方案、接口契约、状态码、产物结构、校验规则、降级策略、测试集和日志指标，统一以 `docs/云侧方案设计.md` 为准。

除必要专业名词术语外，文档编写、回复和面向用户的说明均使用中文。

## 文档定位

- `docs/云侧方案设计.md` 是方案设计的唯一权威来源。
- `AGENTS.md` 只记录项目背景、关键文件、优先级和 AI 编码助手执行规范。
- 不要在 `AGENTS.md` 中新增或复制接口字段、协议细节、状态码、CardSpec、TaskSpec、Artifact、校验项等方案内容。
- 方案变更应先同步 `docs/云侧方案设计.md`，再同步代码、Skill、测试和相关配置。

## 项目背景

本项目服务于小艺 App 的 AI 卡片生成功能。小艺 App 已具备对话式 Agent 能力，用户可以通过自然语言让 Agent 完成任务。本项目要在现有对话链路上扩展“创建桌面卡片”能力：用户输入需求描述后，云侧生成可在端侧预览和添加到桌面的 HarmonyOS A2UI Form 卡片。

本文档中提到的“App”“宿主 App”“小艺 App”均指小艺 App，除非上下文明确说明为天气、日历、运动健康等被调用的一方应用。

一期重点覆盖一方应用和系统能力，例如天气、日历、系统设置、运动健康等。三方 App 数据、跨端数据和复杂页面型需求不作为默认动态能力支持，必须在方案文档和能力注册表中明确声明后才能进入实现。

## 关键文件说明

- `docs/云侧方案设计.md`：云侧方案、系统边界、工具接口、协议约束、校验、降级、测试和日志规范。
- `skills/harmony-card-generation-online/`：按照目标链路设计的在线云侧编排 Skill，需随方案持续优化。
- `skills/harmony-card-generation-offline/`：离线直出 Skill，用于不走云侧微服务时由主 Agent 端到端生成、修复、评审或解释本地 `genui` 与 `cardspec` 产物；只能作为兜底、调试和历史视觉参考，不作为在线链路协议依据。
- `skills/harmony-card-template-generation/`：独立的模板驱动生成 Skill，由主 Agent 从固定布局和受控组件变体中选择一个模板并生成本地 `genui` 与 `cardspec`；不调用在线或离线生成 Skill。
- `skills/harmony-card-generation-offline/reference/capability/event-capability/click-event.md`：事件能力清单。
- `skills/harmony-card-generation-offline/reference/capability/data-capability/`：端侧数据能力清单，持续扩充中。
- `skills/harmony-card-generation-offline/reference/design/asset-library.md`：端侧素材库清单。

## 优先级

开发时按以下优先级处理冲突：

1. `docs/云侧方案设计.md`
2. 本文件 `AGENTS.md`
3. `skills/harmony-card-generation-online/` 下的在线云侧编排 Skill 实现与参考资料
4. `skills/harmony-card-template-generation/` 下的独立模板生成方案、正式模板和校验配置
5. `skills/harmony-card-generation-offline/` 下的离线 Skill、历史模板和样例 `.dat`

历史模板只能作为视觉参考，不能作为协议依据。模板中出现的旧尺寸、`theme`、emoji、网络图、未声明事件或不合规属性，不得复制到新实现。

当代码实现、Skill 文档、能力配置或其它项目文档与 `docs/云侧方案设计.md` 冲突时，应先经过用户确认，再同步修改相关文件。

## 开发协作规范

修改本项目代码或 Skill 前，应先阅读 `docs/云侧方案设计.md` 和本文件，确认改动属于主 Agent / Skill、微服务、A2UI 模型调用、端侧解析还是测试。

开发时应按方案文档划分职责，不要跨边界实现职责，除非用户明确要求调整方案。新增接口、能力、协议能力、校验项、降级策略或测试场景时，应同步更新方案文档、配置、schema、错误码和测试样例中受影响的部分。

遇到不支持场景时，优先按方案文档实现降级或不支持决策，不要绕过能力过滤，也不要伪造动态能力。

输出给用户的结果不要暴露内部字段名，例如 capability、provider、TaskSpec；日志、接口和排障文档中可以保留这些术语。

## 给 AI 编码助手的要求

1. 先阅读 `docs/云侧方案设计.md` 和本文件。
2. 先判断本次改动影响的系统边界，再开始修改。
3. 不要把方案细节重新写入 `AGENTS.md`。
4. 不要把历史模板当成协议依据。
5. 不要回滚用户已有改动；如冲突影响当前任务，先说明风险再处理。
6. 修改代码后按风险补充或运行对应测试。
7. 面向用户的总结使用中文，并说明已修改的文件和验证结果。
