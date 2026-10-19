# 数据分析插件

`data-analysis` 是业务可视化插件的公共分析依赖，仅消费已落盘数据，不调用微服务、模型或渲染器。
入口使用后处理 v2 的 `process_sample` / `process_dataset`，没有必填配置。
本期新增六类统计；原组件真值召回及校验失败历史分析仍由各自插件维护。

## 输入与结果

逐样本读取全部 `attempt_*/trace/view.json` 和同次 `result.json`；最终产物读取宿主指定的
`finalAttemptDir/blocks.json`、`genui.jsonl`。不读取当前服务配置替代历史请求。

样本 `analysis` JSON 的版本为 `batch-analysis-v1`：

- `sampleId`、`warnings`：样本标识及读取诊断。
- `requests[]`：每个实际请求一条，保留 `source`、`uid`、`traceStatus`、业务 `status`、
  `pass1/pass2`、`weight`、`unknownReason/unknownMetrics` 和原 Trace 的 `warnings`。
- 请求的 `phasesMs`：plan/generate/repair；`elapsedMs/elapsedSource`：端到端及证据来源。
- 请求的 `counts`：interfaceRetries、repairs、modelRetries、planRetries、providerFallbacks。
- 请求的 `models[]`：每个模型物理调用一条，保留 spanId、phase、sourcePhase、status、ttftMs、tps
  和各缺失指标的 unknownMetrics。initial 映射为 generate，其它未识别阶段归入 unknown。
- `usage`：components/assets/events/data 各自是排序去重后的标识列表；不可分析时为 null，
  可解析但没有使用时为空数组，另有 `warnings`。

数据集 `statistics` JSON 及画廊按样本预聚合的统计使用相同结构：

- `sampleCount/requestCount/paddedCount/effectiveCount`：样本、实际请求、补齐和赋权记录数。
- pass1/pass2 为 `{hits, count, rate}`，rate 在 0–1 之间。
- 各耗时与次数为 `{sum, count, mean}`，支持画廊筛选后合并分子分母；无有效值时 mean=null。
- `models` 按 all/plan/generate/repair/unknown 分组，TTFT/TPS 使用相同的 sum/count/mean 结构。
- `usage` 每类含 count（可分析样本分母）、used（至少使用一项的样本数）、rate 和
  items（id、count、rate）。类别分母独立；同一样本同一标识只计一次。

`overview` 是独立看板的指标列表；结构化明细同时完整保留，便于后续新增可视化而不重复解析 Trace。

## 成功、耗时与次数

pass@1 / pass@2 按每次实际请求内部第 1 次／前 2 次接口生成尝试判断，只有 success 计成功，
degraded、failed、unsupported、cancelled 均不计成功。修复或模型传输重试不另计接口尝试。
缺少必要尝试证据时为 null；完整 Trace 已结束且仅一次失败时 pass@2=false。
已观测到前两次内成功可直接判 true，不要求后续证据完整。

pass 分母只包含可判定的实际请求，全部实际请求数另行展示。首次成功请求 weight=2，其余为 1；
同 Trace 的补齐只作为聚合权重，不复制文件或执行请求，不增加 pass 分母，不虚构新的重试。
耗时和次数按请求赋权，模型性能按每个物理调用及其所属请求权重聚合。使用率不受补齐或请求数影响。

阶段区间按 plan/dsl/repair 的 operation 识别，同请求同阶段区间取并集，避免重复累计。
generate 是 DSL 生成阶段；每个请求内先汇总，再计算数据集均值。端到端优先 request 根区间，
缺失时退回同次 result.elapsedMs，来源分别为 trace.request、result.elapsedMs 或 unknown。
不累计截图、后处理、批次等待或其它请求。

TTFT 读取 firstTokenLatencyMs；TPS 优先 tokensPerSecond，否则使用 completionTokens 除以
inferenceDurationMs。传输指标有 duration 与 TTFT 时可得到推理时长，不能直接使用包含排队的物理调用
span 时长。零 TTFT 是有效值；零推理时长不能用于除法，缺失指标不参与均值。

接口重试、模型失败重试、计划重试、提供方切换分别读取对应 retryCounts；质量修复读取 repair.attempt。
仅完整且精确的 Trace 可把未发生的阶段或次数判零，其它缺失为 null。

## 最终产物使用

组件读取展开前 Design Compact DSL，按正式高阶组件注册表识别；普通组件不混入。
素材从最终 A2UI 的 src 识别，注册 ID 与资源路径归一。事件优先匹配最终任务上下文的具体候选动作，
再匹配注册动作模板；固定参数必须一致，声明的动态参数位置允许实际值变化，空动作不能作为匹配模板。
数据能力读取最终 CardSpec 的 dataBindings。只提供候选而没有产物使用，不计入使用集合。

缺产物或解析错误保留原因，受影响类别不进分母；已知空集合计入分母。组件出现率与基于人工标注的
组件真值召回率是不同指标，不能互相替代。

## 历史与缺失

分析缺失允许产生 partial 结果并继续画廊；异常样本由宿主隔离。画廊只消费依赖结果，不能重读 Trace
自行推算缺失数据。重跑分析创建新历史；已有画廊不自动更新，须再次运行画廊生成新的快照。
