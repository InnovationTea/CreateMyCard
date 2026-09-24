# 模板后处理与校验说明

本文按当前实现说明模板生成后的公共处理链，系统规则以
[云侧方案设计](../../../../../docs/云侧方案设计.md#校验与重试) 为准。
模板编译成功、最终校验无 error、画廊生成成功和端侧显示正确是不同的验证结果。

## 1. 来源标志与模板根的区别

| 调用方式 | Compact 校验 | 最终 A2UI 校验 |
| --- | --- | --- |
| 正式服务成功取得模板源 DSL | 服务设置 `skip_compact_dsl_validation=True`，跳过整个 `validate_compact_dsl()` | 开关启用时执行 Artifact 校验，按最终模板根选择质量规则 |
| 普通 Compact 生成、模板未命中后的原协议回退 | 不设置跳过标志，执行 Compact 校验 | 开关启用时执行 Artifact 校验 |
| 直接调用 `validate_compact_dsl()` | 不读取服务来源标志；有效模板根只豁免主文字检查 | 调用方另行执行 |
| 原子预览直接展开模板 | 不代表经过正式服务的完整处理链 | DSL-only 可验证结构等规则；完整校验还需真实 CardSpec 和有效能力 |

来源标志来自 `WidgetGenerationService.generate_source_dsl()` 成功调用模板生成器后的结果，
不是从组件 ID 推断。每次重新生成源 DSL 时重置；公共 repair 沿用本次来源标志。
最终质量豁免则每次重新检查 `root` 是否直接引用真实的 `template_root`，并要求当前组件列表没有重复 ID。
它不依赖融球、不接受名称前缀或嵌套标记，也不是不可伪造的来源证明。

## 2. 实际处理顺序

```text
模板检索、Planner、二层受信编译与内部修复
  → 模板 A2UI 回转 Design Compact DSL
  → 公共绑定路径修复和解析
  → 按来源决定是否执行 validate_compact_dsl
  → 标准 A2UI 转换
  → 展示单位确定性去重
  → 素材交付地址映射
  → ArtifactValidator（配置启用时）
  → 按路由决定失败或保存
```

模板来源跳过 Compact 后，仍执行公共解析、转换、单位去重和素材映射。最终 Artifact 校验仍检查
协议、组件、树引用、表达式、绑定、事件、素材、CardSpec 和有效能力，包括 emoji 与最小字号等硬规则。
不能因为一个阶段被跳过而推断其余阶段也被跳过。

有效模板根跳过整卡 `quality` 阶段（当前为对比度校验），范围包括并列背景、标题及动作；
也跳过 `DISPLAY_UNIT_MISSING`，
允许固定模板将数值和单位放在不同容器。`DISPLAY_UNIT_DUPLICATED` 继续检查。
质量跳过日志为 `quality_validation_skipped reason=template_root`，不代表实际检查通过。

运行时 `If/IF` 组件仍不支持。模板解析、Tersel 转换和模板归档会拒绝；公共 Compact 的
`childrenIf/childrenElse` 不构成普通 `children` 树边，孤立分支可能先因不可达而失败。
直接输入标准 A2UI 时，组件准入仍会拒绝未知 If；运行时 `Expr` 不受该组件禁用影响。

## 3. 当前检查范围的边界

- 模板来源不执行 Compact 的字号、布局路线、TaskSpec 数据边界、首帧及高度预算检查；最终
  Artifact 校验没有等价的整卡高度预算检查。固定布局必须通过模板设计及预览验证高度。
- 最终绑定规则可根据 CardSpec 输出结构接受路径，不能证明首帧已经初始化。缺少数据根时的
  `CROSS_DATA_PATH_UNCOVERED` 是 warning，不是 error。
- Compact 解析修复会保留首个同 ID 行，丢弃后续同 ID 行；转换后的重复 ID 检查不能追溯被去除的冲突。
  直接标准 A2UI 输入中的重复 ID 仍会报告。检查原始输入与检查最终产物不能互相替代。
- 有效模板子树的环形 Progress 及直接容器保留显式宽高和描边；其它 2×2 环按当前普通规则归一化，
  单业务为 48vp，命中双分区结构时为 44vp，描边为 6vp。两者均不再采用旧的 52vp 单业务期望。
- DSL-only 使用静态素材 allowlist；完整 Artifact 使用实际有效素材声明及对应版本能力目录。
  静态名单与能力目录不同步可能造成预览单独报错，应核对声明来源，不为模板关闭素材检查。

这些是当前运行范围，不是新增豁免，也不意味着所有模板已经通过视觉验收。

## 4. 错误、告警和修复

Compact 和 Tersel 模板入口都是严格路由。转换失败、最终处理结果存在 error 时返回
`VALIDATION_FAILED`，不保存；关闭 Artifact 校验开关只跳过该阶段，不跳过转换。
warning 不阻断，标题和描述过长的 `CARD_STATIC_FIELD_INVALID` 应保留在检查结果中。

公共 repair 需要同时开启 `enable_validation_failure_retry` 且存在原协议模型 Prompt。
Compact 路由允许原协议回退，具有该 Prompt；Tersel 模板路由设置 `need_fallback=false`，
不具备该 Prompt，因此不进入公共 repair。模板内部二层输出的修复独立执行，不受此说明替代。
公共 repair 只返回新的 Compact 源，不重跑首层标定、Search、Planner 或 CardTpl 展开。

## 5. 画廊样例注入

画廊输入必须先根据目标模板声明的字段构造投影，再对投影中存在的字段注入 `sampleValue`。
不得仅因模板名称以 Weather 开头，就向 `/current/condition` 注入样例。

天气 Support 按声明的 `/current/condition` 或 `/daily/N/condition` 写入“多云”；
`WeatherOverviewDaily2TravelSupport@1` 使用 `/data/weather/daily/2/condition`。
数据请求的 `forecastDays` 按声明的最大逐日索引加一计算，最少为 1；当前天气与双城市样例仍为 1，
后天天气为 3。单业务和组合画廊共用此规则，不修改全局默认参数。

注入器只遍历已经声明的对象和数组元素，不新增字段或扩展数组；非法路径仍抛出异常，不吞掉或回退到
当前天气。注入使用 schema 副本，不改原始 TaskSpec。原始场景失败后应修复输入生成器，再重新生成请求，
不能只修输出目录里的 JSON。

## 6. 回归与代码入口

模板目录测试应与当前来源路径相符：测试模板表达式时显式使用模板来源上下文；测试普通公共校验时
保留默认上下文。素材测试分别检查当前已注册的资源、跨业务语义和未注册资源，不把已删除素材当作
“已注册但语义不匹配”的样例。候选测试保留精确候选集合及顺序，不用包含判断掩盖变化。

在 `widget_service` 目录运行模板模块全量测试：

```bash
LOCAL_FLAG=true .venv312/bin/python -m pytest -q cloud/services/template_generation
```

`tests/test_provider_gallery_batch.py` 中的逐日天气回归分别覆盖无操作和单操作场景，使用真实
`TaskSpecBuilder` 投影与可信注入器，验证正确字段成功、旧当前天气路径被拒绝、原始 schema 不变。
全矩阵回归检查所有非缺失场景的覆盖路径均存在于投影中；这属于无模型检查，不能替代真实生成结果。

主要入口：

- `widget_generation_service.py`：来源标志、Artifact 校验开关、repair 门禁和严格失败。
- `generation_pipeline.py`：Compact 校验分支、转换与单位去重。
- `compact_dsl_a2ui_converter.py`：公共解析、重复 ID 处理、组件树及环形尺寸归一化。
- `card_validation/pipeline.py`、`context.py`：最终阶段调度与模板根识别。
- `card_validation/display_unit_validator.py`、`cross_validator.py`：单位和首帧数据根诊断。
- `test_support/provider_gallery.py`：场景投影、样例注入参数、正式入口批跑。

验证时分别记录生成失败、模板或能力缺失、Artifact error/warning 和端侧 `schemaWarning`。
完整操作见 [正式场景画廊](provider-template-e2e-gallery.md) 和
[原子模板预览](provider-template-preview-gallery.md)。
