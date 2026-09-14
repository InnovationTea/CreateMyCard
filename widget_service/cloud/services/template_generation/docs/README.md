# Template Generation 文档中心

本目录维护 `template_generation` 模块的实现说明。模块为
`generateWidgetCardCompactDsl` 和 `generateWidgetCardTerseDslNested2` 的 create 请求提供受控
Template source DSL，但不负责能力裁决、CardSpec/TaskSpec 构造、最终校验、artifact 保存或业务响应。

> 本目录统一使用协议名 `Tersel`。`Tersel-Nest2`、`TerseDSL-Nested-2`、`Nested-2` 和 `Terse`
> 只作为历史名称或现有 WebSocket operation 的组成部分保留。

## 文档层级

| 文档 | 用途 | 是否权威契约 |
| --- | --- | --- |
| [云侧方案设计](../../../../../docs/云侧方案设计.md) | 系统边界、对外接口、协议、校验和降级规则 | 是，唯一权威来源 |
| [template-generation-design.md](template-generation-design.md) | 本轮模板显示、作者语法、暂缓范围和验收要求 | 否，模块内方案 |
| [architecture.md](architecture.md) | 当前代码的路由、Template 生成流程和失败边界 | 否，实现说明 |
| [modules.md](modules.md) | 目录、类、函数和代码责任索引 | 否，实现说明 |
| [tersel-protocol.md](tersel-protocol.md) | Tersel 语法、DesignToken、内联样式和安全边界 | 否，模块内协议说明 |
| [compact-dsl-data-flow.md](compact-dsl-data-flow.md) | Compact 入口的数据流和回退策略 | 否，接口实现说明 |
| [tersel-data-flow.md](tersel-data-flow.md) | Tersel 入口的数据流和严格失败策略 | 否，接口实现说明 |
| [provider-template-contract.md](provider-template-contract.md) | Provider Bundle、CardTpl、Layout 与 Action 接入规则 | 否，模块内契约 |
| [template-search-planner-contract.md](template-search-planner-contract.md) | 第一层、Search、Planner、第二层及验证器的职责与输入输出 | 否，模块内契约 |
| [support-template-action-policy.md](support-template-action-policy.md) | Support 内嵌事件白名单、业务对象归属和确定性校验 | 否，模块内契约 |
| [provider-template-capability-checklist.md](provider-template-capability-checklist.md) | 业务模板、数据分层和运行状态清单 | 否，从 Provider 事实源派生 |
| [provider-template-preview-gallery.md](provider-template-preview-gallery.md) | 确定性 A2UI 预览数据集的生成与验证 | 否，开发辅助 |
| [provider-template-e2e-gallery.md](provider-template-e2e-gallery.md) | 经正式服务入口批跑 Provider 场景画廊 | 否，测试辅助 |
| [migration-notes.md](migration-notes.md) | 历史合入边界和决策背景 | 否，仅供追溯 |

Provider 的 `first-layer.md` 和 `second-layer.md` 是模型输入资源，不是开发者总体设计文档；
它们应与对应 `provider.json` 和 `.cardtpl` 一起修改。

## 生产入口

模块对生产调用方只暴露一个源 DSL 生成入口：

```python
await request_template_source_dsl(
    task_spec,
    card_spec,
    effective_bindings,
    processor_kind=processor_kind,
    protocol_profile=protocol_profile,
    model_runtime=model_runtime,
    model_request_context=model_request_context,
    enable_fusion_ball=enable_fusion_ball,
)
```

生产链由 `TemplateSourceGenerator` 读取已有 `TaskSpec.appVersion`，与
`CONFIG.fusion_ball_min_prd_version` 比较后，将结果作为内部 `enable_fusion_ball` 传给上述窄入口；配置或
版本缺失、非法、低于配置版本时均传 `False`。`TaskSpec.appVersion` 沿用公共 TaskSpec 构建链，不在模板
模块内重新从请求取值或维护第二份版本字段。本模块责任边界内的 `request_template_source_dsl` 仍要求显式
布尔值。
关闭时，融球 Theme 会在首层 Prompt 构造前从当前请求的 Registry 视图中移除，后续检索、二层组合和编译也
不能选择该类 Theme。

模板链路当前支持 `2x2` 单业务加零到两个显式 Action，以及双业务加零到两个显式 Action。
Search 仅按尺寸、场景和数据可用性筛选模板；Planner 结合布局、主题、业务和动作生成最多三个完整 Plan。
双业务可使用 `TwoSupportLayout`，各动作由所属业务的 Support 消费；双业务单动作还可使用
`HeroTitle + HeroContent + Action` 组合。所有组合必须完整覆盖用户显式字段，并合法消费每个已选动作。
其它多业务组合确定性判定模板不适用。`2x4` 在首层 Prompt 和模型调用前直接判定模板不适用。
Compact create 回退原 Compact 生成，Tersel 模板入口直接失败。完整边界见
[Search 与 Planner 契约](template-search-planner-contract.md)。

Support 内嵌事件还须通过模板声明的事件白名单及同业务数据对象校验；Planner 和编译器共同执行，
不由模型自由分配。具体规则统一维护于 [Support 事件归属契约](support-template-action-policy.md)。

入口返回当前公共 Processor 可直接消费的字符串。当前 Compact 与
Tersel 生产路线都使用 `DESIGN_COMPACT` Processor，因此模块最终返回 Design Compact DSL。
模块内部仍使用受限 Tersel 和 CardTpl 表达布局与模板，但这些不是对外产物。

## 边界速查

模块负责：

- 加载并校验 Template Controls、Provider Bundle、Theme、Layout 和 CardTpl。
- 从已裁决的 TaskSpec、CardSpec 和有效数据绑定中判断模板是否可完整覆盖需求。
- 第一层模型只标定用户显式字段、可为空的业务主焦点和显式 Action；Search 筛选数据可用模板，
  Planner 确定 Theme、Layout、业务顺序和 Action 消费位置，第二层模型只选择一个完整 Plan 并填充 Props。
- 确定性执行语法校验、数据准入、布局约束、Action 绑定和 CardTpl 展开。
- 生成标准 A2UI，并适配为当前 Processor 的源 DSL。

生产模块不负责（`test_support/` 中的开发测试工具不属于生产依赖图）：

- 不查询 IDS，不执行设备能力或权限裁决。
- 不生成 CardSpec、TaskSpec、artifact 或 `GenerateWidgetCardResponse`。
- 不调用 `ArtifactValidator`、`ArtifactStore` 或 `ResponsePlanner`。
- 生产路径不持有 `WidgetGenerationService` 实例，不反向调用原协议生成链。
- 不决定 Compact 和 Tersel 入口的回退、edit 和业务响应策略。

## 开发入口

修改前建议按以下顺序定位：

1. 路由差异：阅读 [architecture.md](architecture.md) 和对应接口数据流。
2. 函数职责：阅读 [modules.md](modules.md)。
3. Provider 或 CardTpl：阅读 [provider-template-contract.md](provider-template-contract.md)。
4. 新增或修改资源：同时检查 `provider.json`、分层规则、`.cardtpl` 和能力清单。
5. 回归：运行模块测试和预览数据集校验，具体命令见预览文档。

### Python 静态预检

无法获取流水线 CodeCheck 版本或规则包时，暂用开发依赖中固定版本的 Pylint 做本地预检。
规则统一维护于 `widget_service/pyproject.toml`，修改 Python 文件后与 Ruff、相关单测一起执行：

```bash
# 在 widget_service 目录执行；Python 环境需安装本项目 dev 依赖。
python -m ruff check cloud/services/template_generation/engine/cardplan/provider_bundle.py cloud/services/template_generation/tests/test_provider_elseif.py
PYTHONPATH=cloud python -m pylint --rcfile=pyproject.toml cloud/services/template_generation/engine/cardplan/provider_bundle.py cloud/services/template_generation/tests/test_provider_elseif.py
git diff --check
```

文件参数替换为本次实际修改的 Python 文件，不仅限于以上示例。当前基础规则覆盖语法错误、变量使用、
无返回值赋值、返回语句一致性、不可达语句、`finally` 返回、裸异常、重复异常/字典键和可变默认参数。
不使用 `--exit-zero` 吞掉检查失败；历史问题和新增问题必须分别记录。

Pylint `inconsistent-return-statements`（R1710）不等同于流水线的 H0301：它不能完整验证所有分支
的返回类型和二元组长度，也不会必然拒绝“条件表达式返回与二元组返回混用”。对
`_template_directive_components()`，保留带类型注解的统一返回变量，并以回归测试验证返回顺序、
二元组类型/长度、非法指令异常和单一返回出口；不能通过伪值、强制字符串化或屏蔽告警改变真实语义。

基础门禁暂不包含全量类型推断或风格规则。扩大至 Pylint `E/F` 与 `unbalanced-tuple-unpacking`
规则的试跑发现，本文件既有 Pydantic 字段被推断成 `FieldInfo`（E1101）和动态列表构造后的解包
（W0632）告警，需要另行核验或适配，不能把基础规则通过称作“全量 Pylint/CodeCheck 通过”。
后续可获取原流水线时，仍需用同版本、同规则集复扫。

## 目录概览

```text
template_generation/
├── facade.py                  生产窄入口
├── controls.py                模板细粒度开关
├── binding_dependencies.py    有效绑定隔离
├── model_client.py            共享模型运行时窄适配
├── source_adapter.py          A2UI 到公共 Processor 源格式的适配
├── profile.py                 模板内部 Tersel 协议资源入口
├── engine/
│   ├── pipeline.py            模板生成主编排
│   ├── advanced/              数据轮廓、首层选择和二层 Prompt
│   └── cardplan/              Provider Registry、Search、CardTpl 编译与展开
├── resources/source/          受信 Provider、Theme、Prompt 和 CardTpl 资源
├── tools/                     模块构建和模板画廊命令
├── test_support/              不进入生产依赖图的端到端画廊辅助工具
├── tests/                     模块回归测试
└── docs/                      实现文档
```
