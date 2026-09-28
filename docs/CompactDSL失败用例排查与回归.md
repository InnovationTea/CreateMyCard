# CompactDSL 失败用例排查与回归

基线：`Br_feature_fusion` / `da0295c`；样本为外部 `cardSpec0918` 的 88 条请求。
本次限定为 Compact 单步框架适配、校验冲突及原需求完整性恢复，不切换模板或 JSX，
不优化视觉设计、不修改原用例或最终模型产物。

## 失败原因与处理

| 用例 | 原因 | 本次处理 |
|---|---|---|
| Q008/Q026/Q056/Q062 | 原 SVG 在 `resources/base/media` 存在，但云侧漏登记，模型调用前即失败 | 按用户要求仅在本地补登记；素材配置、测试及版本路由均不进入本 PR |
| Q028 | V08 要求左对齐，通用单数字规则又强制居中安全盒 | 专用倒计时路由优先；非倒计时安全盒规则不变 |
| Q068/Q072/Q088 | 无动作倒计时要求三个直接 Text，通用稀疏 W9 又要求嵌套 content Column | 统一专用规则判定，保留顺序、单位、宽度、分布与高度检查；Q068 同时有日程内容过密 |
| Q053 | W1 两个大读数以及左侧 Text 过多 | 保留拦截，补充节点计数与普通字号摘要的修复反馈 |
| Q060 | 两个明确动作只输出一个；辅助槽混合两个对象的数据 | 明确先分配动作槽、再安排同对象状态，禁止删掉必需动作 |
| Q079 | 已带 `%` 的字符串误作数值；固定填槽提示还要求仅取一项耳机电量，导致左右耳遗漏 | 保留字符串完整绑定与 W1 几何；右上显示连接＋仓电量，左侧补回带左右耳标签的普通字号电量，歌单动作不变 |
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
- 用户确认第 2 点属于“恢复用户要求的信息完整性”。已移除手机＋耳机提示中的
  “只取最重要一项”，仍使用原 W1、136×126 左区、两个 130×59 右槽和原歌单点击目标。
  最新 Q079 产物实际包含手机电量、连接状态、仓电量、左耳电量、右耳电量的可见绑定；
  不是仅在数据行中保留字段。没有新增“全部候选必显”的通用门禁。
- 最新独立批次 `806_fix_r5` 用**原始输入**复测 Q008/Q026/Q056/Q062/Q079，**5/5 生成通过**；
  runner 每条只发一次请求，服务内部仍最多两次修复，不将请求次数解释为模型一次直出。
  原素材文件、原输入及旧能力快照均未修改；删除先前未执行的换图标迁移工具及对应测试。
  **其中四条图标请求依赖本地未提交的素材配置，不代表干净 PR 检出即可复现。** 本 PR
  不包含图标注册、能力快照、默认版本或版本路由的任何净改动。
- 设备 `3DK0224B01003123` 对该批次完成 **5/5 真机截图与裁图**，保存在独立目录
  `Fusion/autoNew/auto/output/806_fix_review_r5`。已逐张查看：Q079 左右耳读数及标签完整，
  连接、仓电量和歌单入口保留；Q008/Q026/Q056 实际使用原彩色温度计，Q062 按原规则
  未选用该可选图标。Q026 温度范围长行仍存在裁切，只记录，不借素材修复改变布局。
- **DSL 通过不等于全量视觉验收**：前一批 Q053 缺少左右读数的对象标签，Q060 充电器
  文本截断，Q072 三日天气长行温度裁切。这些未在本轮顺带优化，保留记录；不宣称 88 张
  卡片均已完整验收，PR 仍为草稿。
- 保留本地素材适配时，相关离线测试 **489 通过**；能力路由/素材服务测试
  **49 通过 / 1 跳过**。本地全量 **1273 通过 / 22 失败 / 16 跳过**；
  在独立干净基线、相同环境和未监听端口复测为 **1242 通过 / 24 失败 / 16 跳过**。
  本地失败集合没有新增项；基线中的两个格式化电量测试使用原始 Boolean 文案，已将
  测试夹具改成原规范要求的条件表达式。其余存量失败涉及旧能力预期、SVG 着色、模板
  环尺寸、模型配置等，不在本补丁中顺手修改，不能宣称全量测试全绿。
- 从暂存区导出不含任何本地图标适配的独立检出，验证 PR 实际交付内容：相关测试
  **484 通过**，全量 **1268 通过 / 22 失败 / 16 跳过**，与干净基线相比无新增失败；
  Ruff、构建同步检查和差异空白检查通过。原本地 10 个图标相关文件的 Git 内容摘要
  与已实跑版本逐个相同，另复验本地图标及信息完整性测试 **8 通过**。
- 第一笔改变 repair 文本，快照仅更新 repair 产物及 60 条 repair 消息。后续只修正
  运行时手机＋耳机 W1 提示，另补创建/编辑/修复三种模式的回归，不刷新快照掩盖差异。
  主提示源、全部 few-shot 和已有模型消息快照保持不变，构建源与产物一致。

## 复现命令

在 `widget_service` 目录，使用工程 Python 3.12 环境：

```powershell
python scripts/build_compact_prompts.py --check
python -m pytest tests/test_phone_earphone_information.py tests/test_compact_countdown_backboard.py tests/test_compact_dsl_validator.py tests/test_design_compact_few_shots.py tests/test_compact_prompt_bundle.py tests/test_design_compact_repair_prompt.py tests/test_deepseek_official_http_transport.py -q
```

确需变更提示词基线时，先审查源文件、构建产物，再显式刷新并检查 diff；不要用刷新快照掩盖意外变更：

```powershell
$env:PYTHONPATH = "cloud;."
python -m scripts.refresh_compact_prompt_baseline --reason "具体的已评审变更原因"
```

从 `Fusion/runCard` 使用独立批次复测原始用例，不修改候选图标 ID，不覆盖 `806` 结果。

## 提交文件清单

以下为本次提交的全部文件；本地输入、密钥、模型日志、DSL、截图、runCard 复测脚本和 workspace
产物不提交到仓库。

- `docs/云侧方案设计.md`：专用规则优先级、信息完整性及错误诊断边界；不改变素材版本策略。
- `docs/CompactDSL失败用例排查与回归.md`：原因、证据、未闭环项与复现说明。
- `widget_service/cloud/services/card_validation/compact_dsl_validator.py`：消除两处冲突，细化反馈。
- `widget_service/cloud/custom/deepseek_official_http_transport.py`：截断分类与安全元数据诊断。
- `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source/repair.md`：结构修复步骤。
- `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/generated/REPAIR_SYSTEM_PROMPT.md`：构建产物。
- `widget_service/scripts/refresh_compact_prompt_baseline.py`：显式更新提示词快照的工具。
- `widget_service/tests/fixtures/compact_prompt_migration_baseline.json`：有意变更的 repair 快照。
- `widget_service/tests/test_compact_countdown_backboard.py`：倒计时背板正反例。
- `widget_service/tests/test_deepseek_official_http_transport.py`：截断、空响应及日志防泄露测试。
- `widget_service/tests/test_design_compact_few_shots.py`：纯倒计时加动作回归及旧 Boolean 夹具修正。
- `widget_service/tests/test_design_compact_repair_prompt.py`：结构修复指令断言。
- `widget_service/tests/test_compact_prompt_bundle.py`：将迁移基线测试名称更新为已评审基线。
- `widget_service/cloud/services/prompt_builder.py`：修正手机＋耳机填槽提示，恢复左右耳电量。
- `widget_service/tests/test_phone_earphone_information.py`：创建/编辑/修复均保留全部所需信息的指令。

后续提交另删除 `widget_service/scripts/migrate_card_asset_candidates.py` 和
`widget_service/tests/test_migrate_card_asset_candidates.py`：均为上一笔新增且尚未使用的迁移方案，
不再需要换图标，可从 Git 历史恢复；不涉及删除用户原数据。
