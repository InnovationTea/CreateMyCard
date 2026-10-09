# AI Widget 调试工作台

`debug_tools` 是 AI 卡片云侧链路的本地浏览器工作台。日常使用从这里完成端到端会话、微服务接口调用、
卡片预览和数据集批跑；协议、存储格式和插件开发等实现细节分别维护在各子包 README 中。


## 环境准备

- Python 3.12。
- 推荐安装 `uv`；也可以使用已安装依赖的 Python 虚拟环境。
- 仓库已包含 `debug_tools/dist/`，直接使用 Python 入口时不要求安装 Node.js。
- 只有修改前端源码时才需要 Node.js 和 npm。

以下命令均从仓库根目录开始执行。

```powershell
uv sync
```

没有使用 `uv` 时，可按 [`widget_service/README.md`](../widget_service/README.md#run) 创建 Python 3.12
虚拟环境并安装依赖，同时确保仓库根目录和 `widget_service/cloud` 均在 Python 导入路径中。

## 启动工作台

完整模式提供全部页面，并启用端到端调试所需的 Main Agent 后端：

```powershell
uv run debug_tools
```

打开 <http://127.0.0.1:8888/debug/>。

没有使用 `uv` 时，将命令替换为：

```powershell
python -m debug_tools
```

### 启动本地微服务

“接口调试”和“端到端调试”默认连接
`ws://127.0.0.1:8855/api/v1/ws/tools`。在另一个终端启动服务：

```powershell
cd widget_service
uv run cloud/start_websocket_server.py
```

也可以在“连接配置”中填写已经部署的 `ws://` 或 `wss://` 地址。工作台不会为单次接口调试自动启动或代理
微服务；批量测试选择“本地受管后端”时，才会由调试后端按任务配置启动和回收本地服务。

## 第一次使用

### 0. 配置本地环境

调试平台和微服务采用的配置优先级为：
`widget_service/.env` > `debug_tools/end_to_end_debug/backend/debug_agent.yaml` > `default_config.yaml`。

在启动微服务时，会按照优先级从低到高导入配置文件，并覆盖已有字段。如果微服务的执行过程不符合预期，请按照配置优先级进行检查。

在蓝区进行测试时，需要配置如下字段使用 DeepSeek 模型：

```dotenv
WIDGET_SERVICE_OPENAI_MASTER_CLIENT=deepseek_official_http
WIDGET_SERVICE_DEEPSEEK_OFFICIAL_HTTP_API_KEY=<your-api-key>
```

在绿区进行测试时，将`iac3.0`中的`spec_records.yaml`复制到`default_config.yaml`并连接VPN即可使用绿区模型。


### 1. 检查连接配置

进入“连接配置”：

1. 选择“已部署微服务”或“本地受管微服务”。
2. 使用已部署模式时，确认“微服务 WebSocket Base”可访问。
3. 按测试场景检查 App、ROM、设备和地区等公共参数。
4. 点击“保存配置”，确认页面顶部状态变为“可用”。

配置保存在当前浏览器，不会写入任务源码。

![连接配置](docs/images/settings.jpg)

### 2. 主要功能

#### 端到端调试

适合验证“用户需求 → Main Agent → 微服务工具 → 生成结果”的完整链路。
![端到端调试](docs/images/main-agent.jpg)


#### 接口调试

适合逐个检查三个正式工具接口。先选择顶部 Tab，填写业务参数，再点击“发送请求”；会话标识、交互标识和
设备时间由页面自动补齐。响应区可以在“最终结果”“原始 final”和“构建 JSON”之间切换，成功调用会进入
左侧历史，并可继续作为后续请求或卡片渲染的输入。

![接口调试页面](docs/images/interface.jpg)


#### 卡片渲染

适合检查已有 A2UI、Compact DSL、Design Compact DSL 或 artifact：

1. 将内容粘贴到左侧编辑器，或从左侧接口调用历史选择生成结果。
2. 点击“渲染”，必要时手工切换 `2×2` 或 `2×4` 画布。
3. 在中间预览布局、缩放和数据绑定效果。
4. 在右侧 Artifact 检查器确认解析出的产物信息。

![卡片渲染页面](docs/images/render.jpg)

#### 批量测试

适合对固定数据集做回归、链路分析和后处理：

1. 在“批量测试”中点击“创建任务”。
2. 选择 `Datasets` 下的一个数据集、样本和后端模式。
3. 创建后首轮执行会自动入队；任务中心展示排队、运行和完成进度。
4. 进入任务详情查看逐样本响应、卡片预览和 Trace。
5. 批跑完成后，按需选择后处理插件并点击“开始后处理”。

![创建批量测试任务](docs/images/create-task.jpg)

任务可以重复执行，每次都会生成独立结果；关闭浏览器不会停止后台任务。数据集格式、队列、输出目录、
Trace 和本地受管服务说明见 [`batch_testing/README.md`](batch_testing/README.md)，插件开发说明见
[`postprocess_plugins/README.md`](postprocess_plugins/README.md)。

![任务列表](docs/images/task_board.jpg)
![任务详情](docs/images/task_result.jpg)
![Trace](docs/images/trace.jpg)
![后处理](docs/images/post-processing.jpg)

## 常见问题

### 页面提示前端未构建

修改前端或 `dist/` 缺失时重新构建：

```powershell
cd debug_tools
npm install
npm run build
```

然后重启 Python 入口并刷新浏览器。

## 子包文档

| 子包 | 文档内容 |
| --- | --- |
| [`platform/`](platform/README.md) | React 壳、路由、共享配置、调用历史和开发构建 |
| [`end_to_end_debug/`](end_to_end_debug/README.md) | Main Agent 后端、会话协议、模型与 Skill 配置 |
| [`interface_debug/`](interface_debug/README.md) | 三个工具接口、请求构建与 final 解析 |
| [`card_renderer/`](card_renderer/README.md) | 支持的 DSL、渲染运行时、资源和导出组件 |
| [`batch_testing/`](batch_testing/README.md) | 数据集、任务队列、运行结果、Trace 与受管服务 |
| [`postprocess_plugins/`](postprocess_plugins/README.md) | 插件清单、依赖、上下文、输出和开发规范 |

完整架构边界与验收项见 [`调试平台技术方案.md`](调试平台技术方案.md)。
