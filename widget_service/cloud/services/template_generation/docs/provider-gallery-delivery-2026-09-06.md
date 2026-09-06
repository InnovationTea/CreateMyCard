# 2026-09-06 Provider 画廊生成与端侧交付

## 双业务素材修复（已同步工程，未重新安装）

### 原因与处理

- 对照 `cloud/data/capabilities/app-11.7.5.205_rom-6.0/asset_capabilities.json` 的 72 项注册资源：
  步数、睡眠和训练缺少各自候选，双业务合并后的天气水滴被误填到这些槽位；原有 `asset` 类型只产生
  空语义标签，编译器无法按业务区分。天气候选还混入温度计，违背天气状态图标的含义。
- 在模板条目补充 `assetParameterSemanticTags`，覆盖全部 10 个 Support 素材槽位；
  同一请求的第二层候选投影和编译校验均按槽位过滤。耳机进一步限定为本体，排除充电盒。
- 画廊为步数/跑步选择 `figure_run.svg`，睡眠选择 `moon_z_fill_1.svg`，心率选择
  `heart_fill.svg`，耳机选择 `icon_earphone.svg`。无图标的文字模板不增设槽位。
- 按用户补充，天气温度模板使用天气状态图标，禁止温度计。当前注册清单没有多云、阴天、雪天图标；
  画廊保持既有“多云”样例并省略图标，不改成晴天迁就太阳资源，也不借用搭档素材。
  生产语义标签只约束素材类别，天气具体状态仍按二层规则匹配；状态未知或无对应素材时省略。
- 不修改上游素材清单、数据契约、HTTP 补丁或用户既有页面/HAR。按仓库协作约定保留原工作区改动，
  继续在本记录中的隔离工作树开发。

### 本轮修改文件

以下路径相对 `template_generation/`，不包含前两轮已记录的无关变更：

| 文件 | 用途 |
| --- | --- |
| `engine/cardplan/provider_bundle.py` | 加载并校验素材槽位语义配置，保留旧 Bundle 默认行为 |
| `engine/cardplan/prompt.py` | 从注册描述推导天气状态、睡眠、耳机本体和应用图标语义 |
| `engine/cardplan/compiler.py` | 所有声明的 asset Prop 都参与校验/纠正；天气 Support 使用已有颜色策略 |
| `resources/source/providers/health-sport/provider.json` | 五个健康运动 Support 素材槽位配置 |
| `resources/source/providers/weather/provider.json` | 两个天气 Support 状态图标约束 |
| `resources/source/providers/earphone/provider.json` | 耳机本体素材约束 |
| `resources/source/providers/app-usage/provider.json` | 应用品牌图标约束，不伪造应用身份 |
| `resources/source/providers/system-memory/provider.json` | 内存素材约束，不借用无关业务图标 |
| `resources/source/providers/health-sport/layer-docs/second-layer.md` | 双业务素材独立选取规则 |
| `resources/source/providers/weather/layer-docs/second-layer.md` | 温度模板仍选天气状态，未知/缺失时省略 |
| `test_support/provider_gallery.py` | 补齐业务图标候选并固定多云测试前提 |
| `tests/test_provider_asset_semantics.py` | 25 项资源、槽位隔离、配置非法值、旧协议兼容和画廊回归 |
| `tests/test_template_generation.py` | 原有天气颜色测试同时覆盖天气 Support 标记 |
| `docs/provider-template-contract.md` | 配置、二层候选与编译器的语义约束契约 |
| `docs/provider-template-e2e-gallery.md` | 画廊素材映射及缺失状态说明 |
| `docs/provider-gallery-delivery-2026-09-06.md` | 本轮证据和交付边界 |

端侧通过既有同步脚本更新 `entry/src/main/resources/rawfile/provider_scenario_gallery/manifest.json`
和 75 份生成 A2UI，未手改生成内容或修改同步脚本。

### 实际验证

- 专项素材 + 画廊测试：40 通过；端侧同步测试：12 通过。
- 完整回归：626 通过、2 个既有失败，无本次改动新增失败：
  `test_charging_summary_guards_every_optional_status[names2]` 仍是充电摘要仅健康状态存在时 Text 数量
  2/3 不一致；`test_form_validator_allows_empty_stack_children_but_rejects_empty_column_children`
  仍是已知空 Stack 断言。没有顺带修改这两处行为。
- 本轮 6 个 Python 修改文件 Ruff、Bundle `--check`、差异空白检查通过。
- 真实 HTTP 模型全量批跑：115 场景、101 成功、14 既有能力缺失、0 失败；不是 dry-run 或 Mock。
- 101 份 A2UI 均为三消息 JSON，Image 资源全部属于指定清单；39 个可用双业务场景逐一检查两个槽位，
  共 78 个槽位、24 个正确业务图标，无天气温度计、太阳代替多云或跨业务误用。
- 同步前确认端侧原 75 份 A2UI 与上次云侧基线一致，无期间人工修改；先备份再同步。
  显示仍为 85 场景、75 成功、10 缺失，双业务保持 15 组每组一张（13 可用、2 缺失），完整自动化
  0/1/2 操作场景保留。同步后 75 份文件逐字节匹配新云侧产物并通过 JSON 检查。
- 本轮只同步端侧工程，没有重新构建或安装 HAP，也没有进行实机显示验证。设备上的安装版本仍为下节版本。

### 产物与日志

- 新输出：`test/provider_gallery_output_assets_20260906/`；此前
  `test/provider_gallery_output_verified/` 保留未覆盖。
- 同步前资源备份：`test/provider_gallery_delivery_20260906/device-gallery-before-assets.tgz`。
- 完整回归日志：`/tmp/provider-gallery-asset-regression-final-20260906.log`。
- 真实批跑日志：`/tmp/provider-gallery-assets-http-20260906.log`。

## 显示去重更新（当前安装版本）

- 按用户确认，视觉画廊每组仅保留双操作版本，不再重复展示 0/1/2 操作三个相同布局。
- 修改端侧 `scripts/sync_provider_scenario_gallery.py`：按模板对和外观筛选显示子集，重新计算显示计数；
  保留入选场景真实失败/缺失状态，不以其他操作版本替换，不修改完整自动化输入输出。
- 新增端侧 `scripts/test_sync_provider_scenario_gallery.py`：覆盖去重、稳定顺序、源数据不变、状态保留、
  缺少代表版本、重复组、文件缺失及来源/目标目录重叠保护。
- 同步更新本记录和 `docs/provider-template-e2e-gallery.md`。端侧清单及资源由同步脚本重新生成，
  未手工修改 A2UI；页面和 HAR 未改动。
- 显示画廊现有 85 个场景，75 份成功 A2UI、10 个缺失占位；双业务段落 15 组，每组一张，
  其中 13 可用、2 缺失。完整自动化仍为 115 个场景、101 份 A2UI，Support 的 45 个操作场景保留。
- 本轮未重新调用模型。12 项同步测试、22 项画廊/Planner 测试通过；两份修改 Python 文件 Ruff 通过，
  两仓相关差异空白检查通过。未重复执行上次已记录的全量回归。
- 75 份入选 A2UI 均与云侧源文件逐字节一致，并通过三消息 JSON 检查；15 组不存在重复。
  签名 HAP 内恰有 76 份画廊 JSON，与端侧资源一致。
- `assembleHap` 成功，设备 `3AX0224A14000098` 覆盖安装成功。
- 安装后启动返回 `10106102`（设备锁屏，开发模式下无法自动解锁），因此未复核去重后的实机页面；
  未尝试绕过锁屏。解锁后进入“Provider 场景画廊 → 双业务段落”即可查看每组一张的显示子集。
- 当前 HAP SHA256：`d6853b62b69ec84c811920e643ea5d184fe54f5dc14de4351001dd4c1cfe9cdb`。
- 去重前 101 份端侧资源备份：
  `template_generation/test/provider_gallery_delivery_20260906/device-gallery-before-dedup.tgz`。
  自动化源文件未删除；端侧移除的 26 份重复视觉资源也可从该备份恢复。
- 当前构建日志：`/tmp/provider-gallery-dedup-hap-build-20260906.log`。

以下记录为同日首次完整交付过程，展示数量与 HAP 摘要以本节更新为准。

## 范围与结果

- 以 `55545322` 的 Support 扩充为基线，隔离工作树分支为 `codex/provider-gallery-two-support-20260906`。
- 真实 HTTP 模型：`deepseek-v4-flash`；模拟模型及备用模型关闭。HTTP 配置、传输复用本机已有实现，
  未将 HTTP 补丁或凭据写入本次业务代码变更。
- 请求版本统一 `11.7.5.206`；10 个分组，115 个场景，101 成功、14 缺失、0 失败、0 未生成。
- 新增“双业务段落”：15 种 Support 各配一个数据根独立的搭档，展开 0/1/2 个段落操作，
  共 45 个场景；39 成功，6 因应用使用时长/系统内存的数据能力未注册而缺失。非全排列覆盖。
- 保留原有“跨业务组合”天气标题 + 日程内容场景。TwoSupport 使用专用非融球主题。

## 修改文件

以下路径均相对 `template_generation/`：

| 文件 | 用途 |
| --- | --- |
| `test_support/provider_gallery.py` | 添加 Support 覆盖集、独立页签、0/1/2 动作及非融球结果断言 |
| `tests/test_provider_gallery_batch.py` | 验证全部 Support 覆盖、双数据根、动作数量、缺失跳过和输出文件 |
| `engine/cardplan/compiler.py` | 将通用电量 Support 纳入非状态专属变体，避免被旧充电状态检查误拒绝 |
| `resources/source/providers/health-sport/templates/heart-rate-overview.cardtpl` | 移除单子节点 Row，使心率值与下行单位为相邻 Text；保留 56vp 居中样式及顶间距 |
| `tests/test_template_generation.py` | 增加电量 Support 状态覆盖与心率值/单位相邻结构回归 |
| `docs/provider-template-e2e-gallery.md` | 更新双业务段落矩阵、版本、数量及端侧入口说明 |
| `docs/provider-gallery-delivery-2026-09-06.md` | 本次生成、测试、同步和安装证据 |

端侧仅同步 `entry/src/main/resources/rawfile/provider_scenario_gallery/manifest.json` 和 101 份生成的 A2UI；
没有改写用户现有页面、HAR 或其他画廊资源。旧场景目录已打包备份，可恢复。

## 验证

- 画廊与 Planner：22 项单元测试通过。
- 首次完整回归：597 通过、2 失败，失败为既有充电摘要 `health` 单独存在时的文本节点数量断言，
  以及已知空 Stack 必填子节点断言；本次未修改这两处行为。
- 修复后回归：599 通过、上述 2 项明确排除；不是全量无失败声明。
- 修改的 4 个 Python 文件 Ruff 通过，`git diff --check` 通过，`build_cardplan_bundle.py --check` 通过。
- 首轮真实批跑 97 成功、4 失败；分别定位到通用电量 Support 状态检查（3 个）与心率单位邻接（1 个）。
  修复后完整重跑，101 个可用场景全部通过服务最终校验、动作计数与融球断言。
- 同步后，101 份 A2UI 与云侧产物逐字节一致，均为三条 JSON 消息；39 个 TwoSupport 均有两个等权内容槽。
- `hvigorw assembleHap --no-daemon` 构建成功（仍有现有 ArkTS 告警）；签名 HAP 内 102 份 JSON 与同步源一致。
- `hdc -t 3AX0224A14000098 install -r` 返回安装成功，`aa start` 返回启动成功。
- 实机已进入“Provider 场景画廊 → 双业务段落”，页面汇总为“成功 39，异常 6”；6 个异常与输入清单
  中未注册能力的缺失场景一致。实际可见电量 68%、未充电、青浦区 29°、天气描述和日程信息。
- 39 个可用双段落场景均有 `Surface 2001 / schemaWarning`，内容为表达式引用格式告警；页面仍展示
  动态值，未记录页面 `failed` 异常。此项为端侧兼容性待核验，不宣称无告警渲染，也未顺带修改用户 HAR。
  未点击业务动作触发外部应用，仅验证生成的绑定与显示。

## 产物位置

隔离工作树：`/Users/yansf/workspace/GenerateUI/.codex-worktrees/provider-gallery-two-support-20260906`。

- 输入：`template_generation/test/provider_gallery_inputs/`
- 最终输出：`template_generation/test/provider_gallery_output_verified/`
- 旧端侧资源备份：`template_generation/test/provider_gallery_delivery_20260906/device-gallery-before-sync.tgz`
- 实机截图：`template_generation/test/provider_gallery_delivery_20260906/two-support-device.png`
- 端侧工程：`/Users/yansf/workspace/GenerateUI/genui_evaluation`
- HAP：`entry/build/default/outputs/default/entry-default-signed.hap`
- HAP SHA256：`ae929994d06960bffeb86bf6dfcdefd186ddd006ac30721e1ce4d91511e28d81`

本地生成、测试、构建日志分别保存在 `/tmp/provider-gallery-http-verified-20260906.log`、
`/tmp/provider-gallery-regression-final-20260906.log`、`/tmp/provider-gallery-hap-build-20260906.log`。
端侧页面日志为 `/tmp/provider-gallery-device-20260906.log`。
