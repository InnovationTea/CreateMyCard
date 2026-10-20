# 卡片质量评分插件

## 功能

支持 Web 批跑和外部 DSL＋截图＋Query 两种输入，共用评分模型。
输出逐卡问题单、扣分明细、分数上下界及批次汇总；支持整批比较和单条优化前后图片对比。
评分与 DSL 修复独立运行。

## 安装与入口

1. 使用包含本插件、画廊采集器及前端页面的完整工程。
2. 在 debug_tools 目录安装前端依赖并执行 `npm run build`，然后重启平台。
3. 外部图片检测需在运行后端的 Python 环境安装 OCR：

```shell
python -m pip install -r postprocess_plugins/quality-score/requirements-offline.txt
```

主入口：`/debug/quality`；导入页：`/debug/quality/import`；
评估方案：`/debug/quality/evaluation`；批次／单条对比：`/debug/quality/compare`。

Web 截图使用原平台的 Node.js、playwright-core 和 Edge/Chrome。
浏览器路径可通过 `WIDGET_DEBUG_GALLERY_BROWSER_EXECUTABLE` 配置。

## 选择样本并评分

1. 选择已完成批次，检查 Query、尺寸和状态。
2. 选择全部、前 N 条、指定 ID 或勾选样本，点击“确认导入样本”。
3. 点击“运行评分”。完成后进入插件看板。
4. 修改批次或样本范围后需重新确认；再次运行会保存新的执行记录。

Web 批次使用 `browser-capture` 检测结果，并依赖 `data-analysis`；外部批次直接检查上传文件。
进入页面、选择批次和导入文件均不会自动评分。

配置 `sampleIds` 与 `count` 互斥，默认全部；`count` 按批次原顺序取前 N 条。
空集、重复或未知 ID、无效数量及未完成批次会返回错误。
评分仅处理所选样本；截图依赖仍按原流程采集整批或复用已有结果。

## 导入已有卡片

- 单条：填写 ID、Query、尺寸，上传 DSL、PNG/JPEG 截图和可选 CardSpec。
- DSL 支持 JSONL、消息数组及 `{"genui": "...", "cardSpec": {}}` 组合对象；
  单独上传 CardSpec 时以单独文件为准。文本使用 UTF-8。
- 批量：选择目录，根部包含 `quality-import.json`，或旧交付包中的 `dataset-manifest.json`。
  旧清单的“批次／ID”转换为 `批次__ID`；相同 Query 的不同 DSL 分别保留。
- 图片来源选择 Web、模拟器／真机或未知，并上传对应 DSL 的截图。
- 每次 1–500 条、文件合计最多 40 MiB。单 DSL 最大 2 MiB，单图最大 8 MiB／1600 万像素，
  上传请求最大 64 MiB。较大批次需拆分清单。
- 清单附有 DSL／图片 SHA-256 时会校验内容；不一致则拒绝导入。

清单路径相对所选目录：

```json
{"samples":[{"id":"Q001","query":"显示天气","size":"2x2","dsl":"dsl/Q001.genui.jsonl","image":"images/Q001.png","cardspec":"dsl/Q001.cardspec.json"}]}
```

导入后保存为独立批次。返回评分页确认样本，再点击“运行评分”。

## 批次和单条对比

批次模式按样本 ID 对齐；单条模式分别选择左右批次、样本，允许 ID 不同。
默认读取最新已完成评分，也可填写执行 ID 比较历史版本。
点击“加载对比”后展示左右图片、分数上下界、问题差异及通过率差；点击图片可查看原图。

分差为右侧减左侧。计算分差要求 Query、尺寸、客户端版本、评分参数和检测范围一致。
外部检测还核对检测器版本、OCR 版本、图片来源及显式动作要求。
不满足条件时展示两侧结果和具体差异原因，分差留空。
总体通过率差还要求两边样本集合一致。

## 检测方法

| 来源 | 检查项 | 方法 |
|---|---|---|
| Web | 文字裁剪／省略、画布越界 | Range 文本边界、滚动尺寸和逐层裁剪边界，2 CSS px 容差 |
| Web | 疑似文字重叠 | 独立文字片段矩形相交，排除父子嵌套与同组件 |
| Web | 图片加载及解析问题 | 图片加载状态、素材占位及解析器诊断 |
| 外部 | 消息结构、组件引用及循环 | 复用随包提供的离线 v0.9 检查器 |
| 外部 | 占位文案、初始绑定及需求线索 | 检查 DSL、CardSpec 和已覆盖的 Query 短语 |
| 外部 | 疑似文本缺失 | 本地 OCR 与 DSL 中可解析文本匹配 |

Web 采集排除隐藏、透明和滚动区域；外部 OCR 对数字、短文本及复杂表达式记录未检查项。
待确认问题保留原始证据。真实点击、权限、动态更新、完整语义及整体审美需另行检查；
完整检测范围见 [评估方案](EVALUATION.md)。

Web 证据绑定 DSL、渲染上下文和截图哈希。外部截图由用户配对，哈希核对上传内容。
检测结果过期时，Web 批次先重新运行画廊再评分；外部批次重新导入。
缺少 OCR、协议暂不支持、检测失败或关联文件不匹配时显示“待评”并附原因。
每次执行独立保存截图和结果，历史版本保持原样。

## 计分与统计

权重、严重程度及规则表统一维护在 [EVALUATION.md](EVALUATION.md) 的 JSON 参数块。
评分器和方案页面读取同一参数；修改后重启服务并重新评分，历史结果保留原参数快照。

`得分 = 100 × (1 − Σ 分类权重 × min(1, 去重后的严重程度系数之和))`

同根因或同类同组件问题合并，各类别累计风险最大为 1。
上界仅扣确认问题，下界额外计入待确认问题；确认的结构或渲染硬错误得 0 分。
拨号未提供号码按当前规则不扣分。100 分表示当前检查项未产生扣分。

均分按已评分样本计算，包含硬错误淘汰样本；待评不记作 0 或 100。
无问题率为“评分完整、上下界均为 100 且无确认／待确认问题”的样本数除以所选总数。
问题频次按每卡每个规则 code 去重，确认与待确认分别统计。
插件运行状态记录在 `status`，卡片质量状态记录在 `verdict`。

## 接口

- `POST /debug/batch/quality/import`：单条或批量导入。
- `POST /debug/batch/runs/{run_id}/postprocess`：运行评分，configs 中传入样本选择。
- `GET /debug/batch/quality/evaluation`：方案文档及参数。
- `GET /debug/batch/quality/compare`：读取评分结果对比，必填 `leftRunId`、`rightRunId`；
  可选 `leftExecutionId`、`rightExecutionId`。单条模式同时传 `leftSampleId`、`rightSampleId`。

## 验证

在 widget_service 下运行：

```shell
python -m pytest tests/test_debug_quality_import.py tests/test_debug_quality_workflow.py tests/test_debug_quality_score.py tests/test_debug_batch_gallery.py tests/test_debug_batch_postprocess.py -q
```

在 debug_tools 下运行：

```shell
node scripts/web_quality.test.mjs
node scripts/quality_smoke.test.mjs
node scripts/quality_inputs.test.mjs
npm --workspace @widget-debug/platform run typecheck
npm run build
```

浏览器 UI 测试使用固定 API 输入；Python 回归覆盖真实导入接口、宿主执行及评分结果。
前端部署时同步整套 `dist/index.html` 和 `dist/assets/` 构建文件。

## 本次修改文件

下列路径除文档和测试外相对仓库根目录的 `debug_tools/`。评分参数保持不变。

| 文件 | 用途 |
|---|---|
| [`调试平台运行规范.md`](../../调试平台运行规范.md#质量评分与跨批次比较) | 双输入、证据关联和单条比较契约 |
| `batch_testing/quality_import.py` | 安全导入、清单哈希校验和独立运行目录 |
| `batch_testing/api.py` | 导入接口、单条对比参数 |
| `batch_testing/postprocess.py` | 导入来源跳过画廊，保留原排队和依赖行为 |
| `batch_testing/quality.py` | 单样本配对、截图链接、检测范围与分数上下界比较 |
| `platform/src/App.tsx` | 注册导入页 |
| `platform/src/batchApi.ts` | 导入及单条对比类型和请求 |
| `platform/src/routes/QualityRoute.tsx` | 双来源入口、导入来源说明 |
| `platform/src/routes/QualityImportRoute.tsx` | 单条上传、目录清单导入 |
| `platform/src/routes/QualityCompareRoute.tsx` | 单条选择、左右图片与分差；原批次视图保留 |
| `postprocess_plugins/quality-score/plugin.json` | 双输入名称与截图字段 |
| `postprocess_plugins/quality-score/plugin.py` | 两入口共用归一化、评分和产物 |
| `postprocess_plugins/quality-score/external.py` | 离线检测适配与证据绑定 |
| `postprocess_plugins/quality-score/offline_checks/core.py` | 复用消息解析、结构引用检查和 OCR |
| `postprocess_plugins/quality-score/offline_checks/content_checks.py` | 复用内容、绑定与需求线索检查 |
| `postprocess_plugins/quality-score/requirements-offline.txt` | 可选本地 OCR 依赖 |
| `postprocess_plugins/quality-score/EVALUATION.md` | 新输入的覆盖边界与对比口径；数值参数不变 |
| `postprocess_plugins/quality-score/README.md` | 使用、文件清单和验证方式 |
| `postprocess_plugins/quality-score/score_model.py` | 精简拨号信息项文案，扣分逻辑不变 |
| `platform/src/routes/QualityEvaluationRoute.tsx` | 精简当前方案与历史快照说明 |
| `platform/src/routes/QualityEvaluationRoute.test.tsx` | 当前方案与历史快照说明回归 |
| `widget_service/tests/test_debug_quality_score.py`（仓库根目录） | 摘要与质量状态一致性回归 |
| `platform/src/routes/QualityImportRoute.test.tsx` | 导入页面和清单回归 |
| `platform/src/routes/QualityCompareRoute.test.tsx` | 单条与整批切换回归 |
| `widget_service/tests/test_debug_quality_import.py`（仓库根目录） | 导入、安全边界、评分宿主、单条配对回归 |
| `scripts/quality_inputs.test.mjs` | 真实浏览器上传、无自动评分、图片加载和左右布局回归；API 使用测试夹具 |
| `scripts/quality_smoke.test.mjs` | 使用当前 A2UI 输入验证 Web 渲染与测量链路 |
| `dist/` | 从源码重新生成的前端构建产物 |
