# CompactDSL 失败用例排查与回归

基线：`Br_feature_fusion` / `da0295c`；样本为外部 `cardSpec0918` 的 88 条请求。
本次只修改 Compact 单步链路的校验冲突、修复反馈和 HTTP 错误诊断，不切换模板或 JSX。

## 失败原因与处理

| 用例 | 原因 | 本次处理 |
|---|---|---|
| Q008/Q026/Q056/Q062 | 输入引用未注册的 `asset.icon_weather_temperature1`，模型调用前即失败 | 保持线上白名单；提供需显式指定映射、只写独立副本的离线迁移工具 |
| Q028 | V08 要求左对齐，通用单数字规则又强制居中安全盒 | 专用倒计时路由优先；非倒计时安全盒规则不变 |
| Q068/Q072/Q088 | 无动作倒计时要求三个直接 Text，通用稀疏 W9 又要求嵌套 content Column | 统一专用规则判定，保留顺序、单位、宽度、分布与高度检查；Q068 同时有日程内容过密 |
| Q053 | W1 两个大读数以及左侧 Text 过多 | 保留拦截，补充节点计数与普通字号摘要的修复反馈 |
| Q060 | 两个明确动作只输出一个；辅助槽混合两个对象的数据 | 明确先分配动作槽、再安排同对象状态，禁止删掉必需动作 |
| Q079 | 已带 `%` 的字符串被当成数值、编造进度字段或放到不支持的大字号槽 | 反馈明确完整绑定、保留单位、不虚构数值路径；W1 不满足格式化大字条件时使用 ≤18fp |
| Q083 | “标签＋值＋单位”拆分后超过节点数，按钮背板额外放独立标题 | 反馈列出实际节点并说明合并方式；修复提示明确移动标题到 content、保留独立沉底按钮 |

此前追加 thinking 的探测失败不能算新的排版错误。本次以 Q053、8192 token 重现：
`finish_reason=length`，`completion_tokens=8192`，`reasoning_tokens=8192`，正文 0 字符。
因此该探测是输出预算全部用于推理而未生成正文；没有据此断言所有历史空响应都同因。
现在返回 `MODEL_OUTPUT_TRUNCATED` 并记录安全元数据，不记录正文、推理内容或密钥，
也不自动开启 thinking/增加预算/无限重试。普通实跑维持 thinking 关闭。

## 验证证据与边界

- 新增的两个正例在修复前分别命中矛盾校验，修复后通过；反例仍拒绝嵌套错误、错单位、
  错宽度、错误居中、额外信息行。有动作 W9 与普通稀疏 W9 的居中要求不变。
- 原成功的 76 个 Compact 产物按原 TaskSpec/CardSpec 只读回放：**76/76 通过**。
- 真实模型分阶段复测：第一阶段 5/8 通过；补充错误反馈后 Q060/Q079 通过；细化 repair
  提示后 Q083 通过。每次请求最多首次生成＋两次反馈修复，未手改产物；不能将多阶段
  累计拿到 8 个 DSL 解释为一次批次成功率 100%。所有结果与原 `806` 隔离。
- **DSL 通过不等于内容完整验收**：Q079 仍漏掉用户要求的左右耳电量，原因是运行时
  手机＋耳机专用提示强制“手机为焦点、耳机只取最重要一项”。该规则与需求完整性冲突，
  已请求产品确认后续修改口径，本补丁不擅自改变其固定填槽。Q053 真机结果左右两个读数
  缺少对应对象标签，亦不能作为合格金标。Q060 辅助槽充电器文本被截断；Q072 三日天气
  长行的温度被裁掉且下方信息靠近按钮。虽然这 8 条均完成真机渲染与裁图，不能宣称视觉
  验收全部通过。本 PR 保持草稿，后续还需修复字段完整性与动态文本压力约束。
- 4 个旧素材请求尚未修改或计入成功；必须由操作者明确批准迁移。目标温度计图标的选择
  不是线上自动别名，也不是恢复已下线能力。
- 相关离线测试 **488 通过**。全量测试：本分支 **1272 通过 / 22 失败 / 16 跳过**；
  在独立干净基线、相同环境和未监听端口复测为 **1242 通过 / 24 失败 / 16 跳过**。
  本分支失败集合没有新增项；基线中的两个格式化电量测试使用原始 Boolean 文案，已将
  测试夹具改成原规范要求的条件表达式。其余存量失败涉及旧能力预期、SVG 着色、模板
  环尺寸、模型配置等，不在本补丁中顺手修改，不能宣称全量测试全绿。
- 本次只改变 repair 提示文本；创建/编辑提示和全部 few-shot 的摘要不变。更新的快照
  是 repair 产物及 60 条 repair 消息；未删除摘要检查。生成物通过构建器更新。

## 复现命令

在 `widget_service` 目录，使用工程 Python 3.12 环境：

```powershell
python scripts/build_compact_prompts.py --check
python -m pytest tests/test_compact_countdown_backboard.py tests/test_compact_dsl_validator.py tests/test_design_compact_few_shots.py tests/test_compact_prompt_bundle.py tests/test_design_compact_repair_prompt.py tests/test_deepseek_official_http_transport.py tests/test_migrate_card_asset_candidates.py -q
```

确需变更提示词基线时，先审查源文件、构建产物，再显式刷新并检查 diff；不要用刷新快照掩盖意外变更：

```powershell
$env:PYTHONPATH = "cloud;."
python -m scripts.refresh_compact_prompt_baseline --reason "具体的已评审变更原因"
```

获得素材迁移确认后，可使用以下命令生成另一份批跑输入（路径由操作者提供）：

```powershell
python -m scripts.migrate_card_asset_candidates --input-dir <原用例目录> --output-dir <不存在的新目录> --registry cloud/data/capabilities/app-11.7.5.205_rom-6.0/asset_capabilities.json --asset-map asset.icon_weather_temperature1=asset.icon_weather_thermometer
```

工具同时更新请求顶层与 `content` 的候选数组，保留全部其它值和顺序，输出替换清单；
目标未注册、其它候选未知或输出目录已存在时拒绝。线上预检查、注册表快照均不修改。
然后从 `Fusion/runCard` 用独立批次复测，不覆盖原始输入和 `806` 结果。

## 提交文件清单

以下为本次提交的全部文件；本地输入、密钥、模型日志、DSL、截图、runCard 复测脚本和 workspace
产物不提交到仓库。

- `docs/云侧方案设计.md`：补充专用规则优先级、反馈与离线迁移边界。
- `docs/CompactDSL失败用例排查与回归.md`：原因、证据、未闭环项与复现说明。
- `widget_service/cloud/services/card_validation/compact_dsl_validator.py`：消除两处冲突，细化反馈。
- `widget_service/cloud/custom/deepseek_official_http_transport.py`：截断分类与安全元数据诊断。
- `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/repair.md`：结构修复步骤。
- `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/generated/REPAIR_SYSTEM_PROMPT.md`：构建产物。
- `widget_service/scripts/migrate_card_asset_candidates.py`：显式离线迁移工具。
- `widget_service/scripts/refresh_compact_prompt_baseline.py`：显式更新提示词快照的工具。
- `widget_service/tests/fixtures/compact_prompt_migration_baseline.json`：有意变更的 repair 快照。
- `widget_service/tests/test_compact_countdown_backboard.py`：倒计时背板正反例。
- `widget_service/tests/test_deepseek_official_http_transport.py`：截断、空响应及日志防泄露测试。
- `widget_service/tests/test_migrate_card_asset_candidates.py`：副本迁移、白名单和不覆盖测试。
- `widget_service/tests/test_design_compact_few_shots.py`：纯倒计时加动作回归及旧 Boolean 夹具修正。
- `widget_service/tests/test_design_compact_repair_prompt.py`：结构修复指令断言。
- `widget_service/tests/test_compact_prompt_bundle.py`：将迁移基线测试名称更新为已评审基线。
