# 批跑后处理插件开发规范

插件位于 `debug_tools/postprocess_plugins/<pluginId>/`。每个目录包含 `plugin.json` 和 Python 入口；服务启动时
扫描清单，执行时才在独立子进程中加载脚本。插件只负责生产结构化数据和受限文件，调试平台依据清单自动
生成插件独立看板，不加载或执行插件提供的 HTML、JavaScript 或 React 代码。

## 本地环境与配置

所有插件都复用调试平台的 Python 3.12 运行环境，不需要单独创建插件虚拟环境。从仓库根目录安装
Python 依赖：

```powershell
uv sync
```

`example-metrics`、`complete-showcase` 和 `component-recall` 只需要上述 Python 环境。其它内置插件还需要
以下按功能安装的本地环境：

| 插件 | Python 外依赖 | 是否需要额外配置 |
| --- | --- | --- |
| `browser-capture` | Node.js、npm、`playwright-core`、Edge/Chrome/Chromium | 非标准安装路径的浏览器需配置环境变量 |
| `validation-failure-gallery` | Node.js、npm、`playwright-core`、Edge/Chrome/Chromium | 同上 |
| `device-capture` | DevEco JDK、SDK、HDC、Hvigor、ArkTS 渲染工程、HarmonyOS 设备或模拟器 | 必须配置 `debug_tool.yaml` |

### 浏览器截图插件

浏览器截图和校验失败画廊会由 Python 子进程调用 Node.js 截图脚本。仓库只声明 `playwright-core`，不会下载 Playwright
自带的浏览器；需要本机已安装 Edge、Chrome 或 Chromium。从仓库根目录执行：

```powershell
cd debug_tools
npm install
node -e "import('playwright-core').then(() => console.log('playwright-core OK'))"
cd ..
```

截图脚本会自动检查 Windows 的 Edge/Chrome 常见安装路径、macOS 的应用目录，以及 Linux 下常见的
Edge/Chrome/Chromium 路径。浏览器不在这些位置时，在启动调试平台的同一个终端中指定可执行文件：

```powershell
$env:WIDGET_DEBUG_GALLERY_BROWSER_EXECUTABLE = 'D:\Tools\Chrome\chrome.exe'
uv run debug_tools
```

该变量只对当前终端有效。设置后应保持平台进程从同一终端启动，以便 Node.js 子进程继承配置。

### 真机截图插件

`device-capture` 复用 `device_debug` 的 Render Session。先安装 DevEco Studio 及对应 SDK，再在
`debug_tools/debug_tool.yaml` 中配置本机工具链和模拟器目录：

```yaml
platform:
  environment:
    deveco_studio_home: D:/DevEco
    workspace_root: D:/Workspace
    sdk_home: ${environment.deveco_studio_home}/sdk
    hdc: ${environment.sdk_home}/default/openharmony/toolchains/hdc.exe
  device_capture:
    hdc: ${environment.hdc}
    deveco_sdk_home: ${environment.sdk_home}
    java_home: ${environment.java_home}
    hvigor: ${environment.hvigor}
    render_timeout_seconds: 30
    capture_attempts: 6
    auto_start_emulator: false
```

内置工程位于 `debug_tools/a2ui_render`，插件面板仅配置本次执行的 `targetId`。
截图前等待默认 1 秒，通过 `debug_tools/debug_tool.yaml` 中
`platform.device_capture.capture_delay_seconds` 设置 0～30 秒，0 表示关闭额外等待，修改后重启调试后端。
页面不提供时延配置，旧执行记录中的 `captureDelaySeconds` 仅兼容读取，不覆盖本机 YAML。
每个样本收到就绪终态、确认应用
前台后再等待，截图重试也执行该等待；取消时立即中断。实际时延保存至截图元数据和汇总事实。
只重生成画廊仍复用已有图片；调整时延后应再次运行真机截图，再次运行真机画廊。插件自动选择最新 HAP：
真机和未知目标要求 signed，模拟器可使用 unsigned。App 的 `A2UI_RUN` 终态决定成功、警告或失败，
卡片裁切严格使用 App 返回的 `cropPx`。

启动前可先验证工具和设备：

```powershell
& 'D:\DevEco\jbr\bin\java.exe' -version
& 'D:\DevEco\sdk\default\openharmony\toolchains\hdc.exe' list targets
```

真机需开启开发者模式和 USB 调试，并确认本机已获得设备授权。插件面板始终要求选择本次在线目标，
不会从配置文件读取或持久化设备序列号。

需要本地模拟器时，在插件面板点击“启动本地模拟器”。平台读取 `emulator`、
`emulator_instance_root` 和 `emulator_image_root`，等待所选实例的 HDC 端口上线并自动选中返回的
`targetId`；启动进程退出或等待超时会在面板显示明确错误。

## 业务插件依赖与离线画廊

- `data-analysis`：统一分析全部请求 Trace 与最终产物，输出逐请求、逐样本和数据集统计；口径见其 README。
- `browser-capture`、`device-capture`：只截图并保留证据，不生成 HTML；真机目标配置属于 `device-capture`。
- `browser-gallery`、`device-gallery`：直接依赖对应截图插件和 `data-analysis`，共用离线模板。
- `quality-score`：依赖 `browser-capture` 和 `data-analysis`；外部导入评分不启用这两项依赖。
- `component-recall`、`validation-failure-gallery`：依赖分析插件，本期保留其专属分析及中间产物截图。

重生成画廊复用成功、部分完成或跳过的前置结果；失败、中断或尚未执行的必要依赖自动递归补跑，共享依赖
只跑一次。依赖补跑沿用最近终态配置，本次依赖配置字段覆盖历史值并重新校验。显式目标提供新配置时整体
采用新配置，未提供时沿用历史配置，防止历史互斥选项混入。更新已成功的数据仍须显式重跑前置
插件，再重跑画廊；旧历史不修改。
两种画廊均支持筛选联动指标、排序、列数、放大和精简布局；只内嵌自身路线图片，离线打开无需服务。
内置插件可声明 `upstream_results` 关键字参数接收直接依赖规范化结果，checkpoint 按参数名称识别。
示例插件无需依赖分析插件。旧结果继续只读兼容，新截图和 HTML 位于各自历史执行目录。

## v2 清单

```json
{
  "apiVersion": "batch-postprocess-v2",
  "id": "my-plugin",
  "name": "我的插件",
  "version": "2.0.0",
  "entrypoint": "plugin.py",
  "dependence": ["prepare-data"],
  "timeoutSeconds": 300,
  "configSchema": {"type": "object", "properties": {}, "additionalProperties": false},
  "outputs": [
    {
      "key": "quality",
      "scope": "sample",
      "title": "质量明细",
      "dataType": "records",
      "renderer": "table",
      "required": true,
      "deferred": false
    }
  ],
  "presentation": {
    "defaultView": "table",
    "sampleFields": [
      {"key": "score", "label": "得分", "type": "number", "sortable": true}
    ]
  }
}
```

`outputs` 是产物白名单。数据类型限于 `metrics`、`records`、`matrix`、`image`、`json`、`text`、`code`、
`diff`、`issues`、`file`、`link`；`renderer` 只能选择该类型允许的受控渲染提示。图表是 `records` 或
`matrix` 的显示方式，不能携带表达式、模板或前端代码。`presentation.defaultView` 仅支持 `table/gallery`；
`sampleFields` 声明样本索引读取的 `facts` 字段。

`required: true, deferred: true` 表示产物可在样本或数据集基础阶段暂缺，但必须由 `finalize` 在最终校验前补齐。
清单存在 deferred 产物时入口必须实现 `finalize`。

`id` 只能包含字母、数字、点、下划线和短横线，最长 80 个字符。`dependence` 是按声明顺序排列的插件
名称列表；宿主会自动补齐依赖、拒绝不存在或形成循环的依赖，并行运行彼此没有依赖关系的插件。
首次运行与重跑的独立执行记录也可并行；同批次内写入相同插件或读写依赖结果存在冲突时按提交顺序等待，
只读取相同历史依赖的记录可并行。插件的
`upstreamResults` 只包含其直接依赖结果，不包含用户同次勾选的其它独立插件。`configSchema` 使用 JSON Schema
2020-12，前后端均会校验。`entrypoint: "builtin"` 只供内置插件使用。

普通“开始后处理”只运行尚无执行历史的插件。依赖插件已有历史时，宿主将其最新规范化结果放入
`upstreamResults`，不会重复执行。显式“再次运行”会同时恢复失败或中断的必要依赖；可复用的依赖分支保持
原结果，未执行的依赖自动补齐。下游等待本次依赖完成，依赖仍失败时不运行下游业务。

## 函数与上下文

入口必须实现样本函数，可选实现数据集函数和收尾函数；可使用同步函数或 `async def`：

```python
def process_sample(context: dict[str, object]) -> dict[str, object]: ...

def process_dataset(context: dict[str, object]) -> dict[str, object]: ...

def finalize(context: dict[str, object]) -> dict[str, object]: ...
```

样本上下文包含 `apiVersion`、`scope`、`runId`、`sample`、只读的 `runDir/sampleDir/finalAttemptDir`、唯一
可写的 `outputDir`、已校验 `config` 和 `upstreamResults`。数据集上下文另含 `run` 与本插件的
`sampleResults`。收尾上下文另含规范化的 `sampleResults`、`datasetResult`、`pluginOutputDir`、
`sampleOutputDirs` 和 `datasetOutputDir`。宿主按批跑样本顺序执行样本函数，再执行一次数据集函数，最后执行
一次收尾函数；每一步完成后都会增量更新看板。收尾函数返回 `sampleResults` 和可选 `datasetResult`，提供的
样本按 `sampleId` 替换，未提供的基础结果保持不变。

## v2 返回结果

```json
{
  "status": "success",
  "summary": "质量检查完成",
  "facts": {"score": 98.5, "labels": ["稳定", "完整"]},
  "artifacts": [
    {
      "key": "quality",
      "data": [{"item": "结构", "score": 100}]
    }
  ]
}
```

- `status` 只能为 `success`、`partial`、`failed` 或 `skipped`。
- `summary` 是一句纯文本摘要。
- `facts` 仅允许标量和字符串数组，用于索引、筛选与排序。
- `artifacts[].key` 必须存在于清单，作用域必须匹配；可内联 JSON，或以 `path` 引用当前
  `outputDir` 内真实存在的安全相对文件。必需产物在成功结果中不可缺失。
- 合法但暂无专用渲染器的数据会降级为只读 JSON；任何内容都不会作为 HTML 或脚本执行。
- `image/gallery` 的数据项可使用 `url` 展示图片，或使用 `dsl` 与可选 `size` 交由内置 CardRenderer 渲染；
  同时存在时优先展示图片并保留 DSL 作为回退。

宿主统一校验 Schema、序列化和路径边界。样本异常、超时或无效结果会转为该样本的 `failed`，不会终止
其它样本或依赖图中的其它插件。新执行将摘要、数据集结果、逐样本结果与 `dashboard.json` 分开保存，避免详情接口
内联大产物。旧 `batch-postprocess-v1` 文件仍能通过只读适配器展示，但所有新执行只写 v2。

完整最小实现见 `example-metrics/`；覆盖全部受控数据类型和渲染方式的实现见
`complete-showcase/`；带独立评测标注、聚合指标和逐样本解释的实现见 `component-recall/`。
