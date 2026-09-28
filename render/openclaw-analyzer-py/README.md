# OpenClaw 日志分析器 (Python)

纯 Python 实现，**无需安装第三方依赖**，功能与 C++ 版一致。

## 使用

```powershell
cd c:\analyse_log\openclaw-analyzer-py

# 控制台报告
python -m openclaw_analyzer ..\1d99e2db-408f-43a8-b156-78184ee51d07.jsonl.reset.2026-05-21T13-22-57.351Z

# HTML 可视化报告（默认 report.html）
python -m openclaw_analyzer session.jsonl --html

# 指定 HTML 路径，仅生成 HTML
python -m openclaw_analyzer session.jsonl --html analysis.html --no-console

# 导出 JSON
python -m openclaw_analyzer session.jsonl --json report.json

# 本地 Web 界面（上传 JSONL、双屏对比、Query PK）
python -m openclaw_analyzer.web --port 8765
# 浏览器打开 http://127.0.0.1:8765/
```

## 功能

- 识别真实用户 Query（过滤 session 启动消息）
- 追踪 LLM 推理、工具调用、工具返回、最终回复
- 显示各阶段时延（推理耗时 / 等待+执行 / 距 Query / 工具报告耗时）
- **HTML 可视化报告**：时延分布条、步骤卡片、Query 导航
- **Web 界面**：上传 JSONL、在线预览报告、下载 HTML、双屏对比、Query 步骤 PK

## 项目结构

```
openclaw-analyzer-py/
├── openclaw_analyzer/
│   ├── __init__.py
│   ├── __main__.py       # 命令行入口
│   ├── log_parser.py    # JSONL 解析
│   ├── query_analyzer.py
│   ├── html_report.py   # HTML 可视化报告
│   ├── web_server.py    # 本地 Web 服务
│   └── time_utils.py
├── web/                 # Web 前端静态文件
│   ├── index.html
│   ├── app.js
│   └── styles.css
└── README.md
```
