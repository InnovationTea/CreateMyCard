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
| `browser-gallery` | Node.js、npm、`playwright-core`、Edge/Chrome/Chromium | 非标准安装路径的浏览器需配置环境变量 |
| `validation-failure-gallery` | Node.js、npm、`playwright-core`、Edge/Chrome/Chromium | 同上 |
| `device-gallery` | DevEco JDK、SDK、HDC、Hvigor、ArkTS 渲染工程、HarmonyOS 设备或模拟器 | 必须配置 `debug_agent.yaml` |

### 浏览器截图插件

这两个插件会由 Python 子进程调用 Node.js 截图脚本。仓库只声明 `playwright-core`，不会下载 Playwright
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

`device-gallery` 会复制一份 ArkTS 渲染工程，通过 Hvigor 构建 HAP，再使用 HDC 安装、启动、截图和
回收临时文件。先安装 DevEco Studio 及对应 HarmonyOS/OpenHarmony SDK，准备可由 Hvigor 构建的渲染工程，
然后修改 `debug_tools/end_to_end_debug/backend/debug_agent.yaml` 中的 `device_capture`：

```yaml
device_capture:
  hdc: D:/DevEco/sdk/default/openharmony/toolchains/hdc.exe
  device_sn: null
  render_project: D:/Workspace/A2UI_Render
  deveco_sdk_home: D:/DevEco/sdk
  java_home: D:/DevEco/jbr
  hvigor: D:/DevEco/tools/hvigor/bin/hvigorw.bat
  signed_hap_name: entry-default-signed.hap
  bundle_name: com.example.myapplication
  ability_name: EntryAbility
  module_name: entry
  rawfile_target: entry/src/main/resources/rawfile/test.json
  hap_output_dir: entry/build/default/outputs/default
  crop_config: debug_tools/postprocess_plugins/device_capture/device_crop.json
  auto_start_emulator: false
```

路径可以是绝对路径，也可以是相对仓库根目录的路径。`rawfile_target` 和 `hap_output_dir` 必须是渲染工程内
的相对路径。`signed_hap_name` 要与 Hvigor 实际生成的可安装 HAP 文件名一致；真机通常需要已签名产物。

使用已启动的真机或模拟器时，建议保持 `auto_start_emulator: false`。启用前先验证工具和设备：

```powershell
& 'D:\DevEco\jbr\bin\java.exe' -version
& 'D:\DevEco\sdk\default\openharmony\toolchains\hdc.exe' list targets
```

`device_sn` 留空时必须且只能有一台 HDC 设备在线；多设备时填写 `hdc list targets` 返回的目标标识。
真机需开启开发者模式和 USB 调试，并确认本机已获得设备授权。

需要由平台自动启动 DevEco 模拟器时，再设置 `auto_start_emulator: true`，并补充
`emulator`、`emulator_name`、`emulator_instance_root` 和 `emulator_image_root`。这些值必须指向本机已创建
的同一个 DevEco 模拟器实例。

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
名称列表；宿主会自动补齐依赖、拒绝不存在或形成循环的依赖，并行运行彼此没有依赖关系的插件。插件的
`upstreamResults` 只包含其直接依赖结果，不包含用户同次勾选的其它独立插件。`configSchema` 使用 JSON Schema
2020-12，前后端均会校验。`entrypoint: "builtin"` 只供内置插件使用。

普通“开始后处理”只运行尚无执行历史的插件。依赖插件已有历史时，宿主将其最新规范化结果放入
`upstreamResults`，不会重复执行；只有用户点击该插件的“再次运行”时才创建新的执行记录。

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
