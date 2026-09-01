# Provider 模板端到端场景画廊

## 用途

该工具用于让开发者或 AI Agent 一次性生成全部业务 Provider 的 2×2 场景画廊，验证当前模板能否通过正式
`generate_widget_card_terse_dsl_nested2` 服务入口完成能力裁决、模板路由、A2UI 转换和最终校验。每个场景
同时生成非融球和融球版本。请求中的 `deviceInfo.prdVer` 经公共构建链写入 `TaskSpec.appVersion`，模板生成器
再使用该已有字段完成请求级裁决。

它与 [Provider 原子模板预览](provider-template-preview-gallery.md) 的定位不同：原子预览不调用模型，适合逐个
检查 `.cardtpl`；本工具调用正式生成服务，适合检查真实组合是否可用。批跑时只在本地截获最终 Artifact，
不会把画廊测试产物上传到 OBS。

该能力位于 `template_generation/test_support/`，只通过 `WidgetGenerationService` 的公开入口发起测试请求，
不在 Template 模块内构造 TaskSpec、CardSpec 或最终 Artifact。批跑器调用
`generate_widget_card_terse_dsl_nested2` 时，通过仅供 Python 服务调用的关键字参数携带目标模板、目标 Action
和样例覆盖；该入口据此构造 `TemplateSourceGenerator`，它们不进入 `GenerateWidgetCardRequest`、工具请求
JSON 或公开 Schema。Search 通过后，二层候选才会收窄到目标模板，外部工具请求不能设置这些开发测试约束。
当前 `2x2` Search 显式拒绝多业务组合，因此该端到端画廊只生成单业务路线。Provider 中已有的 Support
模板与 `TwoSupportLayout` 仍作为底层保留能力和原子预览资源存在，但当前 Search 路线不可达。

## 场景矩阵

每个业务按模板实例展开适用的 2×2 场景，而不是把同后缀模板的字段合并成一个用例：

| 场景 | 预期模板组合 |
| --- | --- |
| 单内容 + 2 个 Action | Compact + 2 × PillAction |
| 单内容 + 1 个 Action | Hero + PillAction |
| 单内容 | Full |

因此每个 Compact 生成“单内容 + 2 个 Action”用例，每个 Hero 生成“单内容 + 1 个 Action”用例，每个
Full 生成“单内容”用例。业务缺少某个后缀时仍保留一张缺失占位卡。画廊不构造 Support 配对请求，避免把
当前 Search 明确拒绝的多业务组合记录为普通生成失败。

每个上述用例继续展开为两个相邻外观：

| 外观 | 路由请求版本来源 | 预期 |
| --- | --- | --- |
| 非融球 | 请求 `deviceInfo.prdVer = 11.7.5.205` | 低于配置最低版本，融球关闭 |
| 融球 | 请求 `deviceInfo.prdVer = 11.7.5.206` | 等于配置最低版本；单业务 Compact/Full/Hero 命中融球 Theme 时展开融球背景 |

画廊验证前需在服务 `CONFIG` 中配置 `fusion_ball_min_prd_version=11.7.5.206`。批跑结果会校验路由请求版本
门禁和最终 A2UI 是否按模板融球契约出现受控背景；Artifact TaskSpec 中的 `appVersion` 应与请求版本一致。
没有融球 Theme 的业务即使使用 11.7.5.206 也不应出现融球。两种外观保持相同 `providerId` 并相邻写入
manifest，端侧因此把它们放在对应 Provider 业务的同一个页签中，而不是拆成“融球/非融球”两个页签；
同一 Provider 中可通过符合条件的 Compact/Full/Hero 场景对照两种实际效果。

模拟输入从当前 `provider.json` 读取 Provider、业务、能力写入根，以及目标模板自己的主数据和次要数据；
这些必选数据全部进入 `candidateOutputFields`。数据能力参数和 Action 内容来自当前能力注册表，用户 query
明确描述每一个按钮的操作语义。缺少对应后缀时仍保留请求文件，但结果直接记录为“缺失
Compact/Hero/Full 模板”，供端侧显示异常卡片。生成完成后还会检查 A2UI 的 Action 数量，不符合场景
预期的结果按失败记录。Provider 或单模板被当前管控配置禁用时，用例仍会出现在清单中，但直接标记为禁用，
不调用模型。

## 生成

### 环境准备

复现时建议将两个工程放在同一个父目录下，端侧同步脚本会按该结构解析默认路径：

```text
GenerateUI/
├── CreateMyCard/
└── genui_evaluation/
```

服务要求 Python 3.12。在 `CreateMyCard` 根目录创建独立环境并安装依赖：

```bash
python3.12 -m venv widget_service/.venv312
widget_service/.venv312/bin/python -m pip install -r widget_service/requirements.txt
```

首次配置时，以 `widget_service/.env.example` 为模板创建 `widget_service/.env`，不要覆盖已经存在的本地
配置。真实批跑必须设置 `WIDGET_SERVICE_ENABLE_A2UI_MODEL_MOCK=false`，并按
[Widget Service README](../../../../README.md) 配置当前选择的模型后端。凭据必须通过本地环境或受控密钥
服务提供，不得写入输入文件、命令行、日志或仓库。

### 无模型预检

先在 `CreateMyCard` 根目录执行无模型预检，确认当前 Provider、模板控制配置、输入生成和结果清单均可用：

```bash
widget_service/.venv312/bin/python \
  widget_service/cloud/services/template_generation/tools/generate_provider_template_gallery.py \
  --refresh-inputs --dry-run --concurrency 2
```

以 2026-09-01 当前资源为基线，应生成 8 个 Provider、108 个用例；无模型 dry-run 中 18 个状态为
`missing`，90 个状态为 `not_generated`。Provider 或模板调整后数量可以变化，应以重新生成的
输入 manifest 为准，不能继续复用旧结果目录中的数量。

### 真实批跑

无模型预检通过后，确认本地真实模型配置可用，再执行：

```bash
WIDGET_SERVICE_ENABLE_A2UI_MODEL_MOCK=false \
widget_service/.venv312/bin/python \
  widget_service/cloud/services/template_generation/tools/generate_provider_template_gallery.py \
  --refresh-inputs --concurrency 2 --strict
```

`--strict` 会在存在真实生成失败时返回非零退出码；声明缺少对应模板的 `missing` 场景不计为生成失败。
批跑对 `A2UI_GENERATION_FAILED` 单用例默认最多尝试 2 次，用于吸收 HTTP 模型调用的偶发失败；检索、
版本、Action 数量和融球结果等确定性校验失败不重试。
命令结束后必须核对控制台的 `total/success/failed/missing/not_generated` 汇总，并确认输出 manifest 中
`failed` 和 `notGenerated` 均为 `0`，再进入端侧同步。

常用参数：

- `--provider com.huawei.weather.cli`：只批跑一个 Provider，可重复指定。
- `--dry-run`：不调用模型，仅生成“待批跑/缺失”结果清单，适合验证输入和端侧导入。
- `--strict`：存在真实生成失败时返回非零退出码；模板后缀缺失仍作为画廊检查结果保留。
- `--model-failure-attempts 1`：覆盖单用例模型失败最大尝试次数；默认值为 2，必须为正整数。
- Provider 画廊不提供融球命令行开关；每个输入场景固定构造 `11.7.5.205` 与 `11.7.5.206` 两个请求，
  公共构建链将各自的 `request.deviceInfo.prdVer` 写入 `TaskSpec.appVersion`，`TemplateSourceGenerator` 再结合
  `CONFIG.fusion_ball_min_prd_version` 完成融球裁决；配置或版本缺失、非法时两种请求都关闭融球。
- `--input-root`、`--output-root`：覆盖默认临时目录。

默认输入和输出目录为：

```text
widget_service/cloud/services/template_generation/test/provider_gallery_inputs/
widget_service/cloud/services/template_generation/test/provider_gallery_output/
```

输入请求是与工具调用一致的 `content + deviceInfo + session + userAuth` 包络；每个请求按
`providers/<provider>/<business>/<template>/<appearance>/<scenario>.json` 存放。输出按同样的
Provider/业务/模板层级保存 A2UI 消息数组，根目录 `manifest.json` 记录目标模板以及 `success`、`failed`、
`missing` 和 `not_generated` 状态。双版本输入使用
`provider-template-gallery-input/4`；端侧输出继续使用 `provider-template-gallery-output/2`，并在新的
请求版本字段 `prdVer` 之外保留兼容别名 `appVersion` 和空的 `partnerTemplateId`；旧的任务规格版本副本
字段不再输出，现有端侧导入器无需升级即可读取。

## 端侧导入

批跑结束后，从 `CreateMyCard` 切换到同级 `genui_evaluation` 根目录执行：

```bash
cd ../genui_evaluation
python3 scripts/sync_provider_scenario_gallery.py
```

导入脚本只复制状态为 `success` 的 A2UI 文件，同时完整保留失败和缺失记录。端侧首页进入
“Provider 场景画廊”后，可按 Provider 页签检查每个业务的全部模板实例和适用布局；没有 A2UI 的场景显示
错误卡片和具体原因。

同步脚本默认读取：

```text
../CreateMyCard/widget_service/cloud/services/template_generation/test/provider_gallery_output/
```

如果两个工程不是同级目录，使用 `--source` 和 `--target` 显式指定来源与目标。同步完成后，脚本打印的
用例数必须与云侧输出 manifest 的 `counts.total` 一致，A2UI 数必须与 `counts.success` 一致。

## 构建与安装

在 `genui_evaluation` 根目录使用本机 DevEco Studio 的 JBR、SDK 和 Hvigor 重新构建签名 HAP；以下是 macOS
默认安装路径，非默认安装位置需要替换为实际路径：

```bash
JAVA_HOME=/Applications/DevEco-Studio.app/Contents/jbr/Contents/Home \
DEVECO_SDK_HOME=/Applications/DevEco-Studio.app/Contents/sdk \
  /Applications/DevEco-Studio.app/Contents/tools/hvigor/bin/hvigorw \
  assembleHap --no-daemon
```

安装前必须先确认目标设备，只对明确的连接标识执行安装：

```bash
hdc list targets -v
hdc -t <connect-key> shell echo ok
hdc -t <connect-key> install -r \
  entry/build/default/outputs/default/entry-default-signed.hap
```

启动应用后，在首页进入“Provider 场景画廊”，按 Provider 页签检查成功场景；`missing`、`failed` 或
`not_generated` 场景会在相同卡片位置显示明确原因，不应被当成端侧渲染成功。

## 验证

```bash
cd widget_service
.venv312/bin/ruff check \
  cloud/services/template_generation/test_support/provider_gallery.py \
  cloud/services/template_generation/tests/test_provider_gallery_batch.py \
  cloud/services/template_generation/tools/generate_provider_template_gallery.py
PYTHONPATH=cloud .venv312/bin/pytest -q \
  cloud/services/template_generation/tests/test_provider_gallery_batch.py
```
