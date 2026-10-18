# CreateMyCard

## 首次运行（把仓库交给别人时照这个走）

```powershell
# 1) Python 依赖（根目录，uv 会把 debug_tools 与微服务 widget_service 一起装上）
uv sync

# 2) 前端依赖（已提交的 debug_tools/dist 可直接用；改了前端源码才需要重新构建）
cd debug_tools; npm install; npm run build; cd ..

# 3) 起微服务（默认 127.0.0.1:8855）
uv run python widget_service/cloud/start_websocket_server.py

# 4) 起调试平台（http://127.0.0.1:8888/debug）
uv run python -m debug_tools --mode frontend
```

**配置是可选的**：`.env` 不入库（含密钥）。不配任何东西时 `enable_a2ui_model_mock=true`，
模型走本地 mock，**全链路（导入 → 批跑 → 产物 → 期望对比 → 画廊）都能跑通**，不需要 key。

要用真实模型再：

```powershell
copy widget_service\.env.example widget_service\.env
# 填 URL／KEY／模型名，并把 WIDGET_SERVICE_ENABLE_A2UI_MODEL_MOCK 改为 false
```

两个容易踩的点：

- 批量测试的「已部署后端」WebSocket Base URL 必须带路径：`ws://127.0.0.1:8855/api/v1/ws/tools`
- 批跑产物根目录 `workspace_root` 默认相对 cloud 包（`widget_service/cloud/workspace`），平台按同一位置取产物；
  要挪地方就改 `WIDGET_SERVICE_WORKSPACE_ROOT`，但两边必须一致，否则批跑会取不到 artifact

## 项目文档

- [云侧方案设计](docs/云侧方案设计.md)：项目方案与接口约定的权威来源。
- [校验、重试与兜底机制入门指南](docs/校验、重试与兜底机制入门指南.md)：面向新人的全链路校验、失败处理、重试次数、兜底与排障说明。
