# 单批 Web 质量评分插件

## 用途与边界

对调试平台一次批跑的最终 GenUI 和对应 Web 画面生成问题单、分数及汇总。使用平台已有的表格、指标、
图片和问题明细组件，不注入独立 HTML，不调用模型，不修改 DSL。平台另提供只读批次对比。

评分只表示声明检查范围内的缺陷扣分，不是整体审美分、真机验收或训练数据通过证明。
Web 渲染不能证明拨号、Intent、权限或设备能力实际执行成功。

## 使用

1. 将本次改动完整放入同版本仓库，包括本插件、网页截图采集器、画廊插件和截图页面；不能只复制此目录。
2. 按调试平台原有方式安装依赖、构建前端并重启后端。Python 评分使用标准库，不增加生产依赖。
3. 从主导航或批跑中心进入“质量评分”，也可从后处理区域的“单批 Web 质量评分”入口进入。
   选择已完成批次，按全部、前 N 条、指定 ID 或逐项勾选样本，检查 query、size 与状态。
   点击“确认导入样本”，再点击“运行评分”。进入页面、选择批次或确认导入本身均不触发评分。
4. 宿主自动补齐 `browser-gallery` 依赖。首次执行会先网页渲染，再按样本评分，最后生成汇总。
5. 运行完成后自动进入原插件看板。列表显示分数上下界、问题组数和质量状态；详情展示截图、扣分与证据。
   看板区分来源样本总数和本次所选数量；再次运行保留所选 ID 并新建执行目录。

主入口为 `/debug/quality`，评估方案为 `/debug/quality/evaluation`，对比为
`/debug/quality/compare`。后两者只读，不启动评分。运行前更改选择会撤销确认，需要重新确认导入。

### 子集与对比

配置 `sampleIds` 和 `count` 互斥；不指定表示全部。`count` 按批次原顺序取前 N 条，宿主将其固化为
ID 列表。空集、未知 ID、重复 ID、无效数量或未完成批次均拒绝。仅所选样本进入评分、明细和汇总；
画廊依赖仍可能采集整批或复用历史结果，不因评分子集改变画廊契约。

对比默认读取两边最新终态评分快照，可填写 executionId 指定历史执行；无结果明确报错，不自动补跑。
按样本 ID 对齐，并核对 query、size、参数快照和检测版本；上下文不一致、缺失侧、待评均不伪造分差。
差值为右侧减左侧；问题分布为每卡每 code 去重数，确认与疑似分开统计。通过率仅指本次选择中
Web 范围无问题的比例，不是训练数据通过率。不同集合或口径不展示总体通过率差。

对应只读 API：`GET /debug/batch/quality/evaluation`；
`GET /debug/batch/quality/compare?leftRunId=…&rightRunId=…`，后者支持可选的
`leftExecutionId` / `rightExecutionId`。评分提交仍使用原 POST postprocess 接口，configs 中传选择。

已有历史画廊不会被依赖调度自动重跑。旧画廊没有检测证据时，先在“浏览器渲染画廊”点击“再次运行”，
待完成后再对评分插件点击“再次运行”。DSL、Query、尺寸或最终产物上下文变化时同样执行此顺序。
所有评分输出由宿主保存在新的后处理执行目录，不覆盖输入及历史评分。

环境仍使用原平台的 Node.js、playwright-core 与 Edge/Chrome。浏览器查找失败时可按原截图脚本设置
`WIDGET_DEBUG_GALLERY_BROWSER_EXECUTABLE`。此插件不需要模拟器、HDC 或模型 API。

## 检测与证据

| 检查 | 方法 | 结论 |
|---|---|---|
| 文字被裁剪或省略 | 浏览器 Range 文字边界、实际滚动尺寸、逐层裁剪边界、行数限制 | 可确认当前 Web 文字显示损失 |
| 内容越出画布 | 文字或图片边界与当前卡片画布比较，2 CSS px 测量容差 | 确认当前 Web 越界 |
| 文字重叠 | 独立文字片段矩形相交，排除父子嵌套与同组件 | 疑似问题；矩形相交不等于字形遮挡 |
| 图片加载失败 | 浏览器图片状态及渲染器的素材缺失占位 | 确认 Web 加载失败；不推断一定是 DSL 引用错误 |
| 解析诊断 | 复用当前网页解析器输出 | 待确认诊断，不套用旧协议强行淘汰 |
| Web 解析或渲染失败 | 截图页面中的逐卡解析／运行时错误 | 当前 Web 渲染淘汰，得分为 0 |

显式隐藏、透明、滚动区域和未渲染状态不被推断为布局错误。滚动区域计入排除数量，不能宣称已全覆盖。
没有可测文字或图片的画面保持待评，不因空问题单获得满分。
品牌色板、玻璃材质的合成对比度、整体疏密、完整 Query 语义、动作与数据绑定能力、端侧字形与交互不在
本版检测范围内。后续扩展检测项须提供证据并映射规则，不能用“没有问题记录”代表检查已完成。

采集与截图来自同一浏览器画面。证据绑定规范化换行后的 GenUI SHA-256、渲染上下文和 PNG SHA-256。
新画廊执行将截图留存在独立执行目录，评分再复制到自己的输出目录，避免后续画廊重跑替换历史配图。
这些哈希用于防止产物混配，不是外部受信验收签名。

## 评分

复用 consequence-comparison-v2 计算结构。本版未重新拟合或改变数值。
权重、严重程度系数、规则表及有序前缀统一维护在 [EVALUATION.md](EVALUATION.md) 的受控 JSON 块；
评分器读取同一参数，方案接口将其展开为 Markdown 表格。修改参数后重启服务并重新评分，历史结果
保留执行时快照。不要在此 README 再复制参数表，避免双份口径。
同根因或同类同组件问题去重，各分类风险累计最多为 1。

`得分 = 100 × (1 − Σ 分类权重 × min(1, 去重后的严重程度系数之和))`

上界仅扣确认问题，下界额外计入疑似问题；它们不是统计置信区间。确定的渲染硬失败得 0 分。
未映射规则、缺证据、输入变化或图片哈希不一致显示“待评”，不冒充 100 分。
本版确认的文字截断通常为可见性中等问题：单个独立问题组扣 15 分；重复记录不重复扣分。
拨号未提供号码的历史豁免保持不变，不代表真实拨号已验证。

同一批次的全部样本都进入汇总。未知不当作 0 或 100；均分只在已评分子集计算，并明确包含得 0 分的
Web 渲染淘汰样本。平台 `success` 表示评分程序执行成功，不等于卡片质量通过；质量结论在 `verdict`。

## 接口与文件

- `plugin.json`：v2 清单、截图依赖、输出类型和列表字段。
- `plugin.py`：只读当前产物与直接依赖证据、验证配对、逐卡评分和数据集汇总。
- `score_model.py`：既定模型；没有渲染、外部调用或数据集路径依赖。
- `EVALUATION.md`：唯一参数来源、计算流程、淘汰与待评、对比定义和边界。
- `../../batch_testing/quality.py`：只读方案渲染与历史批次对比，缺证据不补跑。
- `../../scripts/web_quality.mjs`：浏览器测量函数。
- `../../scripts/capture_batch_gallery.mjs`：在原截图流程中同步采集并输出证据。

不要求额外提交 baseline/candidate 文件。插件不读取旧修复轮次的历史问题单来给新图扣分。

## 验证命令

本地验证结果：34 项 Python 插件／画廊／宿主回归、14 项平台展示回归、76 项渲染器回归通过；
9 个真实浏览器测量场景和 3 张真实网页渲染测试卡通过。3 张卡经评分得到 100 / 85 / 0。
与原评分模块的 1,521 组规则组合结果一致；Ruff、前端类型检查和生产构建通过。
这些是代码与明确测试场景的验证结果，不是业务全量数据或真机验收结果。

在 `widget_service` 下：

```shell
python -m pytest tests/test_debug_quality_score.py tests/test_debug_batch_gallery.py tests/test_debug_batch_postprocess.py -q
python -m ruff check debug_tools/postprocess_plugins/quality-score debug_tools/postprocess_plugins/gallery/plugin.py tests/test_debug_quality_score.py
```

在 `widget_service/debug_tools` 下：

```shell
node scripts/web_quality.test.mjs
node scripts/quality_smoke.test.mjs
npm --workspace @widget-debug/platform run typecheck
```

浏览器自测使用明确的测试卡片，不调用生成模型。端到端自测复用真实截图页面、解析器、React 渲染器和
Playwright 截图入口，仅将批跑查询 API 替换为固定测试输入；测试截图保留在临时目录。

## 修改文件清单

### 评分工作流扩展（本次）

全部路径相对仓库根目录；前端构建结果同步到 `widget_service/debug_tools/dist/`。

| 文件 | 用途 |
|---|---|
| `docs/云侧方案设计.md` | 子集、参数唯一来源及只读比较契约 |
| `widget_service/debug_tools/batch_testing/api.py` | 方案/比较接口和批次名称 |
| `widget_service/debug_tools/batch_testing/postprocess.py` | 子集校验、选择快照、只执行所选样本 |
| `widget_service/debug_tools/batch_testing/quality.py` | 快照对齐、分差、问题分布与通过率 |
| `widget_service/debug_tools/postprocess_plugins/quality-score/plugin.json` | 子集配置 schema |
| `widget_service/debug_tools/postprocess_plugins/quality-score/plugin.py` | 子集汇总、参数哈希、信息记录不扣分 |
| `widget_service/debug_tools/postprocess_plugins/quality-score/score_model.py` | 从方案读取参数，纯计算模型保持原数值 |
| `widget_service/debug_tools/postprocess_plugins/quality-score/EVALUATION.md` | 方案与唯一参数块 |
| `widget_service/debug_tools/postprocess_plugins/quality-score/README.md` | 使用和交付说明 |
| `widget_service/debug_tools/platform/src/App.tsx` | 主导航及新路由 |
| `widget_service/debug_tools/platform/src/batchApi.ts` | 新 API 类型与客户端 |
| `widget_service/debug_tools/platform/src/routes/BatchTaskCenterRoute.tsx` | 批跑中心评分入口 |
| `widget_service/debug_tools/platform/src/routes/QualityRoute.tsx` | 批次/样本选择与确认 |
| `widget_service/debug_tools/platform/src/routes/QualityCompareRoute.tsx` | 只读比较页面 |
| `widget_service/debug_tools/platform/src/routes/QualityEvaluationRoute.tsx` | 安全的受限 Markdown 方案页面 |
| `widget_service/debug_tools/platform/src/routes/PostprocessDashboardRoute.tsx` | 复用原看板、保留子集重跑及工具链接 |
| `widget_service/debug_tools/platform/src/components/PostprocessPanel.tsx` | 引导评分到两步选择页 |
| `widget_service/debug_tools/platform/src/components/useQualityRun.ts` | 显式运行、防双击与完成跳转 |
| `widget_service/debug_tools/platform/src/styles.css` | 新页面布局样式 |
| `widget_service/debug_tools/platform/src/App.test.tsx` | 导航路由测试 |
| `widget_service/debug_tools/platform/src/routes/QualityRoute.test.tsx` | 默认不运行、选择确认与配置提交测试 |
| `widget_service/debug_tools/platform/src/routes/QualityCompareRoute.test.tsx` | 对比及不可比状态测试 |
| `widget_service/debug_tools/platform/src/routes/QualityEvaluationRoute.test.tsx` | 文档渲染与转义测试 |
| `widget_service/debug_tools/platform/src/routes/PostprocessDashboardRoute.test.tsx` | 子集重跑与失败状态回归 |
| `widget_service/debug_tools/platform/src/components/PostprocessPanel.test.tsx` | 评分入口与其他插件兼容测试 |
| `widget_service/tests/test_debug_quality_workflow.py` | 新增 18 项后端选择/比较/接口回归 |

合入 Fusion 后验证：Python 83 项通过、平台 Vitest 81 项通过、TypeScript 无报错、`npm run build` 成功、
Ruff 与差异空白检查通过。测试仅使用隔离测试输入，不调用模型、不修改生产 DSL。
测试有 Starlette/httpx 与 React Router 的兼容性提示，不影响当前测试和构建。

### 首版 Web 评分接入

以下路径相对仓库根目录。除新插件与测试外，仅调整网页截图证据传递，不改平台看板源码、
生成服务、云侧协议或原始 DSL 数据。

| 文件 | 用途 |
|---|---|
| `docs/云侧方案设计.md` | 登记单批 Web 评分边界与证据合同 |
| `widget_service/debug_tools/platform/src/routes/BatchGalleryCaptureRoute.tsx` | 将当前渲染输入和解析诊断交给截图采集器 |
| `widget_service/debug_tools/scripts/capture_batch_gallery.mjs` | 同步采集测量证据并绑定 DSL／PNG 哈希 |
| `widget_service/debug_tools/scripts/web_quality.mjs` | Web 几何、文字和素材检测 |
| `widget_service/debug_tools/postprocess_plugins/gallery/plugin.json` | 声明检测证据产物 |
| `widget_service/debug_tools/postprocess_plugins/gallery/plugin.py` | 保存证据和不可被后续运行替换的历史截图 |
| `widget_service/debug_tools/postprocess_plugins/quality-score/plugin.json` | 注册评分插件、依赖和可视化字段 |
| `widget_service/debug_tools/postprocess_plugins/quality-score/plugin.py` | 输入配对校验、单卡评分与整批汇总 |
| `widget_service/debug_tools/postprocess_plugins/quality-score/score_model.py` | 复用并等价格式化既定评分模型 |
| `widget_service/debug_tools/postprocess_plugins/quality-score/README.md` | 使用、原理、边界和验证说明 |
| `widget_service/debug_tools/scripts/web_quality.test.mjs` | 真实浏览器测量回归 |
| `widget_service/debug_tools/scripts/quality_smoke.test.mjs` | 实际网页渲染与截图入口联调 |
| `widget_service/tests/test_debug_quality_score.py` | 评分、证据失效、路径安全和宿主依赖调度回归 |
