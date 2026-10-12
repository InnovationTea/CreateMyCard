# 端到端调试

`end_to_end_debug` 提供 Main Agent 的本地调试后端和可嵌入 React 会话界面，用于观察用户需求经过 Skill、
工具调用和结果回复的完整轨迹。它不代理三个微服务 WebSocket；浏览器收到工具调用后，仍直接连接平台
“连接配置”中的微服务地址，并把终态结果回传给 Agent。

## 启动

端到端调试只在统一入口的 `full` 模式下可用：

```powershell
uv run debug_tools --mode full --host 127.0.0.1 --port 8888
```

打开 <http://127.0.0.1:8888/debug/end-to-end>。页面同时显示以下状态时才能走完整链路：

- Agent 已连接；
- 当前微服务可用；
- 已加载期望的 Skill profile。

`frontend` 模式仍会渲染页面，但不会创建 Main Agent 会话。

## 目录

```text
end_to_end_debug/
├── backend/                 # FastAPI、会话管理、Agent 与工具等待桥
│   ├── debug_agent.yaml     # 调试平台稳定配置
│   ├── server.py            # full 模式应用入口
│   └── system_prompt.md     # 调试 Agent system prompt
└── frontend/                # 对话、运行轨迹和会话状态 React 组件
```

## 页面操作

1. 选择快捷需求或输入非空文本。
2. 发送后观察运行状态和右侧运行轨迹。
3. 工具调用出现时，浏览器使用当前微服务配置执行调用；成功或失败都会写回当前回合。
4. 回合完成后检查助手回复、工具终态和 artifact 预览事件。
5. 点击“新建会话”可清空当前上下文并创建新会话。

工具桥默认等待 180 秒。断线、非 JSON、连接关闭或超时会结束当前工具调用，并在运行轨迹中记录失败。

## 配置

Main Agent 的主要配置位于 `backend/debug_agent.yaml`：

- `default_profile` 和 `profiles`：默认 Skill 及页面展示信息；
- `ui.quick_prompts`：页面快捷需求；
- `model`：Main Agent 的模型路由、重试、并发和超时；
- `server`：调试后端固定参数；
- `defaults`：页面公共请求参数默认值；
- `batch_testing`、`device_capture`：由批量测试与后处理使用，分别见对应子包文档。

模型配置优先级为：

```text
cloud/config/default_config.yaml
< end_to_end_debug/backend/debug_agent.yaml
< widget_service/.env
< 进程环境变量
```

实际模型传输由 `WIDGET_SERVICE_OPENAI_MASTER_CLIENT` 选择。API Key 只从服务端环境读取，不返回浏览器，
也不写入事件轨迹。配置变更后需要重启调试后端。

## 会话协议

前端和后端使用 `protocolVersion: "1.0"` 的 dotted 事件：

1. `conversation.open` 创建会话，后端返回 `conversation.ready`。
2. `turn.start` 发起回合；后端按过程发送 `turn.status`、`assistant.message`、`tool.call` 和
   `artifact_preview`。
3. 浏览器执行 `tool.call` 后，以相同的 `turnId` 和 `callId` 回传 `tool.result`。
4. 后端以 `turn.completed` 或 `error` 结束回合。
5. `turn.cancel` 取消当前回合，`conversation.reset` 重建会话。

`waiting_tool` 和 `tool.trace` 属于内部状态，不展示为普通运行轨迹。后端只校验工具调用关联标识、接口名称、
终态标记、JSON 可序列化性和大小上限，不持有微服务连接。

## 前端包检查

```powershell
cd debug_tools
npm --workspace @widget-debug/end-to-end run typecheck
npm --workspace @widget-debug/end-to-end run test
```

统一入口、其它页面和常见故障见 [`../README.md`](../README.md)。
