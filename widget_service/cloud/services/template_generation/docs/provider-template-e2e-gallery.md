# Provider 模板端到端场景画廊

## 用途

该工具用于让开发者或 AI Agent 一次性生成全部业务 Provider 的 2×2 场景画廊，验证当前模板能否通过正式
`generate_widget_card_terse_dsl_nested2` 服务入口完成能力裁决、模板路由、A2UI 转换和最终校验。

它与 [Provider 原子模板预览](provider-template-preview-gallery.md) 的定位不同：原子预览不调用模型，适合逐个
检查 `.cardtpl`；本工具调用正式生成服务，适合检查真实组合是否可用。批跑时只在本地截获最终 Artifact，
不会把画廊测试产物上传到 OBS。

该能力位于 `template_generation/test_support/`，只通过 `WidgetGenerationService` 的公开入口发起测试请求，
不在 Template 模块内构造 TaskSpec、CardSpec 或最终 Artifact。批跑器调用
`generate_widget_card_terse_dsl_nested2` 时，通过仅供 Python 服务调用的关键字参数携带目标模板、目标 Action
和样例覆盖；该入口据此构造 `TemplateSourceGenerator`，它们不进入 `GenerateWidgetCardRequest`、工具请求
JSON 或公开 Schema。Search 通过后，二层候选才会收窄到目标模板，外部工具请求不能设置这些开发测试约束。

## 场景矩阵

每个业务按模板实例展开适用的 2×2 场景，而不是把同后缀模板的字段合并成一个用例：

| 场景 | 预期模板组合 |
| --- | --- |
| 单内容 + 2 个 Action | Compact + 2 × PillAction |
| 2 个内容 | 当前业务 Compact + 另一 Provider 的 Compact |
| 单内容 + 1 个 Action | Hero + PillAction |
| 单内容 | Full |

因此每个 Compact 分别生成“单内容 + 2 个 Action”和“2 个内容”两个用例，每个 Hero 生成一个
“单内容 + 1 个 Action”用例，每个 Full 生成一个“单内容”用例。业务缺少某个后缀时仍保留一张缺失占位卡。

模拟输入从当前 `provider.json` 读取 Provider、业务、能力写入根，以及目标模板自己的主数据和次要数据；
这些必选数据全部进入 `candidateOutputFields`。数据能力参数和 Action 内容来自当前能力注册表，用户 query
明确描述每一个按钮的操作语义。缺少对应后缀时仍保留请求文件，但结果直接记录为“缺失
Compact/Hero/Full 模板”，供端侧显示异常卡片。生成完成后还会检查 A2UI 的 Action 数量，不符合场景预期的
结果按失败记录。Provider 或单模板被当前管控配置禁用时，用例仍会出现在清单中，但直接标记为禁用，不调用
模型。

## 生成

在 `CreateMyCard` 根目录运行：

```bash
widget_service/.venv/bin/python \
  widget_service/scripts/generate_provider_template_gallery.py \
  --refresh-inputs --concurrency 2
```

常用参数：

- `--provider com.huawei.weather.cli`：只批跑一个 Provider，可重复指定。
- `--dry-run`：不调用模型，仅生成“待批跑/缺失”结果清单，适合先验证输入和端侧导入。
- `--strict`：存在真实生成失败时返回非零退出码；模板后缀缺失仍作为画廊检查结果保留。
- `--input-root`、`--output-root`：覆盖默认临时目录。

默认临时目录为：

```text
template_generation/test/provider_gallery_inputs/
template_generation/test/provider_gallery_output/
```

输入请求是与工具调用一致的 `content + deviceInfo + session + userAuth` 包络；每个请求按
`providers/<provider>/<business>/<template>/<scenario>.json` 存放。输出按同样的
Provider/业务/模板层级保存 A2UI 消息数组，根目录 `manifest.json` 记录目标模板、搭配模板以及 `success`、
`failed`、`missing` 和 `not_generated` 状态。

本地配置若仍为 `enable_a2ui_model_mock=true`，请先使用 `--dry-run`。真实批跑可在模型运行时已配置的环境中
通过 `WIDGET_SERVICE_ENABLE_A2UI_MODEL_MOCK=false` 启用；不要把凭据写入输入文件、命令行或仓库。

## 端侧导入

批跑结束后，在 `genui_evaluation` 根目录执行：

```bash
python3 scripts/sync_provider_scenario_gallery.py
```

导入脚本只复制状态为 `success` 的 A2UI 文件，同时完整保留失败和缺失记录。端侧首页进入
“Provider 场景画廊”后，可按 Provider 页签检查每个业务的全部模板实例和适用布局；没有 A2UI 的场景显示
错误卡片和具体原因。

## 验证

```bash
cd widget_service
.venv/bin/ruff check \
  cloud/services/template_generation/test_support/provider_gallery.py \
  cloud/services/template_generation/tests/test_provider_gallery_batch.py \
  scripts/generate_provider_template_gallery.py
PYTHONPATH=cloud .venv/bin/pytest -q \
  cloud/services/template_generation/tests/test_provider_gallery_batch.py
```
