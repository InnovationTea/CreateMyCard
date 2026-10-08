# AI Widget Debug Tools

`debug_tools` 是本地浏览器测试工作台，包含四个业务模块和一个统一 React 壳：

- `end_to_end_debug/`：端到端 Main Agent 调试服务和 Agent 事件轨迹。
- `interface_debug/`：浏览器直连三个工具 WebSocket 接口的手工调试、final 解析和跨接口参数构建。
- `card_renderer/`：A2UI、Compact DSL、Design Compact 产物预览和 Artifact 检查器。
- `batch_testing/`：读取固定测试数据集、并发调用 Compact DSL 接口、保存结果、解析 Trace 并调度插件。
- `postprocess_plugins/`：后处理插件清单与实现；画廊、真机截图及其资源均按插件自包含组织。
- `platform/`：React/Vite 组合应用，负责路由、共享配置、左侧接口调用历史和模块间产物传递。

平台壳固定为 `100dvh`。`navigation-rail` 下半部的“接口调用历史”只记录三个微服务调用的 request、`final`/`final_error` 和状态；Agent 的普通事件仍只显示在端到端模块内部，不会把中间 WebSocket 帧混入共享历史。

## 本地启动

接口调试和卡片渲染可以完全在浏览器中运行；批量测试任务中心需要由统一 Python 入口提供本地文件 API、
持久化队列和可选的受管微服务。连接已部署后端时可先单独启动微服务（默认 base 为
`ws://127.0.0.1:8855/api/v1/ws/tools`）：

```powershell
cd widget_service
.venv\Scripts\python.exe cloud\start_websocket_server.py
```

如果当前环境可以使用 Node.js，可以启动前端开发服务器：

```powershell
cd widget_service\debug_tools
npm install
npm run dev
```

打开 <http://127.0.0.1:5173/debug/>，进入“连接配置”填写 `toolWsBaseUrl` 和其它固定参数。Vite 的 `/debug` 代理只服务同源 Agent/健康检查路径，不代理微服务 WebSocket；接口模块会按 `toolWsBaseUrl` 直接连接 8855。没有 Agent 后端时，“接口调试”和“卡片渲染”仍可用；“端到端调试”会显示 Agent 未连接。

### 统一 Python 启动入口

前端构建产物统一位于 `debug_tools/dist/`。构建完成后，从 `widget_service` 目录选择启动模式。

只启动静态前端，不加载 Main Agent 配置和模型客户端：

```powershell
uv run debug_tools --mode frontend --host 127.0.0.1 --port 8888
```

同时启动静态前端和 Main Agent 后端：

```powershell
uv run debug_tools --mode full --host 127.0.0.1 --port 8888
```

没有使用 `uv` 时，可将上述命令替换为
`python -m debug_tools --mode frontend|full --host 127.0.0.1 --port 8888`。

两种模式均打开 <http://127.0.0.1:8888/debug/>，并提供批量测试任务、队列和结果 API。单次接口调试仍由
浏览器直连微服务；只有选择“本地受管后端”的批量任务会由调试后端启动、探活和回收 8855（或任务指定
端口）的微服务子进程。`frontend` 模式下接口调试、批量测试和卡片渲染可用，
端到端页会显示 Agent 未连接；`full` 模式额外提供
`/debug/health`、`/debug/skills`、`/debug/artifact` 和 Main Agent WebSocket。旧的嵌套
`start_server.py` 与直接运行 `backend.server` 的入口已移除。

## 调试入口

| 用途 | 地址 |
| --- | --- |
| 工作台（Vite 开发） | `http://127.0.0.1:5173/debug/` |
| 工作台（统一 Python 入口） | `http://127.0.0.1:8888/debug/` |
| 健康检查（仅 `full`） | `http://127.0.0.1:8888/debug/health` |
| Main Agent WebSocket（仅 `full`） | `ws://127.0.0.1:8888/debug/e2e/ws`（`/debug/agent/ws` 为兼容别名） |
| 默认微服务 WebSocket base | `ws://127.0.0.1:8855/api/v1/ws/tools` |
| 单个微服务接口 | `{toolWsBaseUrl}/{operation}` |
| 批量测试页面 | `http://127.0.0.1:8888/debug/batch` |
| 批跑数据集 | `debug_tools/Datasets/<dataset>/*.json` |
| 批跑输出 | `debug_tools/batch_output/<runId>/` |

平台不会自动拉起或回收微服务。三个允许的 operation 为
`getWidgetCapabilityOverview`、`getDataCapabilitySchemas` 和
`generateWidgetCardCompactDsl`。浏览器直接连接 `toolWsBaseUrl`，接收帧直到
`final`/`final_error`，再关闭该连接；`/debug/tools/{operation}` 仅返回
`BROWSER_DIRECT_REQUIRED` 迁移提示，不是 BFF 代理。

### 批量测试

“批量测试”入口首先展示持久化任务中心。创建任务时从 `Datasets` 的直接子文件夹中选择一个数据集，
再选择其中任意有效 JSON 样本；目录不递归扫描。任务保存样本选择、可选公共请求字段覆盖和后端测试参数
快照。批跑并发、额外失败重试、调用超时和 Trace 根目录统一读取 `debug_agent.yaml` 的
`batch_testing`，不在创建任务页面重复配置。每次尝试使用
`batch-<8位运行标识>-<5位样本序号>-<3位重试序号>` UID，并覆盖请求中的
`content.uid` 和 `userAuth.user.userId`，不修改源数据文件。

任务创建成功后会自动生成首个执行并加入队列，无需再次点击启动。调度器空闲时自动执行；已有其它任务时
页面显示“排队中”。同一时刻只执行一个任务，任务内部仍可并发处理样本。再次执行同一任务会生成独立执行记录；其它执行请求
进入持久化队列。浏览器关闭不影响执行；调试后端重启时活动执行标记为中断，等待项保留并暂停，需在页面
显式恢复。批跑结果按轮次保存 `manifest.json`、`summary.json`、`summary.md` 和每个样本的请求、响应、
artifact blocks、`genui.jsonl`、Trace v2 与最终结果。每个 attempt 保存原始 Trace、导入摘要与归一化
`view.json`，附件按 SHA-256 去重到运行级 `trace_blobs/`。页面可恢复已完成轮次、预览成功 DSL，并用
节点树和时间瀑布查看单链路的输入、输出、诊断和原始记录。

正常完成的批跑不会自动执行后处理。进入批跑详情后，可选择一个或多个后处理插件并手工启动；没有依赖关系
的插件并行运行，清单 `dependence` 中声明的插件会被自动补齐并先执行。平台根据插件的 v2 产物声明自动生成独立看板，提供数据集汇总、分页样本索引和样本检查器。
“开始后处理”仅运行所选插件中尚无执行历史的插件；已执行依赖复用最新结果。已执行插件需要在结果区域
点击“再次运行”单独触发，新的结果会作为一条历史执行保留。
内置插件包括浏览器渲染画廊、真机截图画廊和组件召回分析，
统一通过插件清单发现，并由后处理接口配置、排队和执行，不提供按插件固定编写的专用启动接口。
浏览器画廊产物保存为
`batch_output/<runId>/gallery.html`。该插件将每个可渲染样本的 Web 预览
截图以内联 PNG 保存到单个 HTML，支持状态筛选和搜索；失败、不支持、取消或没有有效 GenUI 的样本也会
保留并显示原因。画廊失败不会改判批跑结果，可在任务中心重试或重新生成，完成后点击“打开画廊”
在新标签页查看。截图默认调用系统 Edge、Chrome 或 Chromium，也可通过
`WIDGET_DEBUG_GALLERY_BROWSER_EXECUTABLE` 指定浏览器可执行文件。
批跑详情默认折叠后处理配置；点击标题栏“后处理插件”后，模态面板在同一界面显示可选插件和已选插件的
最新结果，不会压缩样本结果与产物预览区域。插件重新执行后保留历史结果，可在独立看板中切换查看；任务
列表聚合展示当前运行中所有已执行插件。
任务详情和画廊使用相同的尺寸解析规则：优先读取最终 CardSpec 的 `suggestSize`，其次识别 query 中明确
写出的 `2x2`/`2x4`，再回退到样本 `size`；因此没有在 GenUI `createSurface` 中声明宽高的 `2x4` 卡片
也会以宽卡尺寸渲染。

真机截图不属于任务参数，也不会写入任务快照。批跑完成后，用户可单独选择真机截图画廊插件；服务端
此时检查 HDC、DevEco 工具链、已配置签名的 ArkTS 渲染工程和目标设备，通过后由独立后台队列串行执行，不阻塞后续
批跑，也不改变生成成功、降级或失败判定；个别样本失败会保留原因并允许重试。截图完成后会同时生成
`batch_output/<runId>/device_gallery.html`，与浏览器画廊互不读取、互不依赖。全屏截图仅保留用于排障。

自定义插件放在 `debug_tools/postprocess_plugins/<pluginId>/`，包含 `plugin.json` 和 Python 入口脚本。
清单使用 `batch-postprocess-v2`，通过 `dependence` 声明运行依赖，通过 JSON Schema 声明配置，并通过 `outputs/presentation` 声明产物和
受控展示提示；脚本实现
`process_sample(context)`，可选实现 `process_dataset(context)`。两者返回 JSON 对象，使用
`success/partial/failed/skipped` 状态以及 `summary/facts/artifacts` 声明式结果。
脚本在独立子进程中执行，原批跑目录按只读契约使用，新增文件只能写入上下文提供的 `outputDir`。
可复制 `postprocess_plugins/example-metrics/` 作为最小开发起点；需要查看全部受控展示组件、文件产物、
样本事实和配置声明时，参考 `postprocess_plugins/complete-showcase/`。
完整清单、上下文、函数签名、结果块和失败语义见 `postprocess_plugins/README.md`。

真机截图配置统一保存在
`debug_tools/end_to_end_debug/backend/debug_agent.yaml` 的 `device_capture` 节，只由调试平台读取，不进入
微服务配置、任务快照或浏览器响应：

```yaml
device_capture:
  hdc: hdc
  device_sn: null
  render_project: D:/WorkSpace/Fusion/auto/A2UI_Render_0716
  deveco_sdk_home: C:/Program Files/HuaWei/DevEco Studio/sdk
  java_home: C:/Program Files/HuaWei/DevEco Studio/jbr
  hvigor: C:/Program Files/HuaWei/DevEco Studio/tools/hvigor/bin/hvigorw.bat
  signed_hap_name: entry-default-signed.hap
  bundle_name: com.example.myapplication
  ability_name: EntryAbility
  module_name: entry
  rawfile_target: entry/src/main/resources/rawfile/test.json
  hap_output_dir: entry/build/default/outputs/default
  render_wait_seconds: 8
  command_timeout_seconds: 300
  crop_config: debug_tools/postprocess_plugins/device_capture/device_crop.json
  auto_start_emulator: true
  emulator: D:/DevEco Studio/tools/emulator/Emulator.exe
  emulator_name: Huawei_Phone
  emulator_instance_root: D:/Huawei/Emulator
  emulator_image_root: D:/Huawei/Sdk
  emulator_start_timeout_seconds: 120
  emulator_poll_seconds: 2
```

未指定设备 SN 时必须且只能连接一台 HDC 设备。渲染工程须能产出配置名称的已签名 HAP；默认裁切坐标来自
`postprocess_plugins/device_capture/device_crop.json`，可按测试设备分辨率提供同结构的本地配置覆盖。启用
`auto_start_emulator` 后，如果 HDC 当前没有设备，环境检查会启动指定的 DevEco 本地虚拟器并等待其上线；
已有设备时不会重复启动，多个设备时仍要求通过 `device_sn` 明确选择。后端关闭时只终止本模块启动的虚拟器。
虚拟器冷启动需要足够的物理内存和 Windows 提交内存，启动失败或超时会作为不可用原因展示在创建任务页。

已部署模式只连接配置的 `ws://`/`wss://` 地址。本地受管模式从 `debug_agent.yaml`、`.env` 和进程环境
读取默认配置，启动时自动选择回环空闲端口；页面只允许覆盖用于比较模型路由、采样、思考、重试和回退
策略的非敏感参数。API Key、Access Key 和 Secret 不下发浏览器或写入任务文件。平台只回收自己启动且
身份可验证的子进程。如需 Trace，应在 `debug_agent.yaml` 的 `batch_testing` 中启用记录并配置可由调试
平台读取的根目录。命令行 `--trace-root` 或 `WIDGET_SERVICE_GENERATION_TRACE_ROOT` 可显式覆盖该目录。只接受
`generation-trace-v2`；Trace 缺失、未完成、结构错误或附件校验失败只显示告警，不会把已经成功生成的
样本改判为失败。

### Agent dotted 协议

端到端页面使用 `protocolVersion: "1.0"`：

1. `conversation.open` → `conversation.ready`（获得 `conversationId`）。
2. `turn.start`（非空 `text`）→ `turn.status`、`assistant.message`、`tool.call`、`artifact_preview`、`turn.completed` 或 `error`；`waiting_tool` 和 `tool.trace` 仅作协议内部状态，不进入运行轨迹。
3. 浏览器收到 `tool.call` 后执行对应微服务，并回传带匹配 `turnId`、`callId`（建议同时带 `conversationId`）的 `tool.result`；后端返回 `tool.result.accepted`/`duplicate`/`rejected` 后继续 Agent。
4. `turn.cancel` 和 `conversation.reset` 分别取消当前回合和重建会话。旧 `message`/`configure`/`reset` 仅为兼容独立客户端保留。

工具桥和浏览器调用的默认超时均为 180 秒。断线、连接错误、非 JSON、服务端关闭和超时会结束当前调用并写入失败状态；中间 `start`/`partial`/`command` 帧不进入左栏共享历史。后端只校验调用关联 ID、operation、final 终态标记、结果 JSON 可序列化性和 4 MiB 大小上限，不持有微服务连接。

## 调试模型配置

端到端 Main Agent 与微服务使用相同的 provider 名称、主备切换、失败重试、并发和超时配置语义。
配置优先级为 `cloud/config/default_config.yaml` < `end_to_end_debug/backend/debug_agent.yaml` 的
`model` 节 < `widget_service/.env`；进程环境变量高于三个文件。修改后需重启调试后端。

实际模型传输只由 `WIDGET_SERVICE_OPENAI_MASTER_CLIENT` 选择，支持 `deepseek_official_http`、
`deepseek_platform` 和 `llmclient`。配置 API key 或 URL 本身不会隐式改变 provider。官方 HTTP 使用
`WIDGET_SERVICE_DEEPSEEK_OFFICIAL_HTTP_*`，平台 WebSocket 使用
`WIDGET_SERVICE_DEEPSEEK_PLATFORM_*`。API key 只从服务端读取，不会下发到浏览器或写入事件日志。

## 范围说明

Main Agent 后端只负责 Skill 导入、模型调用和浏览器工具等待桥；API key 只从服务端读取，不下发浏览器。浏览器配置保存在
`localStorage` 的版本化键 `ai-widget-debug-config:v1`，其中 `agentWsUrl` 与 `toolWsBaseUrl` 分开设置。
后端配置中的 `upstream_base_url` 仅为兼容旧测试/配置保留，浏览器直连路径不会让后端代理微服务。

卡片渲染保留现有 artifact 选择、编辑器和批跑复用流程，
底层统一使用从根目录 `render` 迁入的 Parser、UIGraph、组件注册表与 `renderTree`。根目录
`render` 保留为上游行为对照，不作为第二个调试平台入口。

本地素材由 `/resources/{path}` 和 `/background_assets/{path}` 提供，只允许读取固定资源根内的文件。
外部图片不经过服务端代理；卡片动作仅在浏览器中展示解析参数，不执行跳转。
