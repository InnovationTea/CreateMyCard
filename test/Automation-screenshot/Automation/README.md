# 小艺 DSL 自动化

本目录包含 Python 主流程，用于执行：

`query -> DSL 提取 -> ArkTS rawfile 复制 -> 构建安装启动 -> 截图`

当前实现以 Python 为主，保持流程简单、模块化、可维护。

## 目录结构

- `main.py`：命令行入口。
- `automation/hdc.py`：HDC 命令封装。
- `automation/ui_tree.py`：UI 树解析、控件定位和打分。
- `automation/xiaoyi.py`：等待小艺就绪、发送 query、等待回复、提取 DSL。
- `automation/dsl.py`：DSL 关键词搜索、JSON 修复和保存。
- `automation/arkts.py`：复制 DSL 到 ArkTS rawfile，构建、安装、启动 ArkTS，并截图。
- `automation/pipeline.py`：单条和批量流程编排。

## 命令

直接运行一条 query：

```powershell
python Automation\main.py one --qid q_manual --query "你的 query"
```

从 `queries.jsonl` 按 id 运行一条 query：

```powershell
python Automation\main.py one-from-file --qid q1
```

批量模式：

```powershell
python Automation\main.py batch
```

批量模式会先发送所有 query 并收集 DSL 文件；全部 DSL 收集完成后，再逐条渲染并保存截图。

指定单台设备运行：

```powershell
python Automation\main.py batch --sn "你的设备SN"
```

多设备并行模式会自动发现所有 HDC 设备，每台设备都会完整执行一遍 `queries.jsonl`：

```powershell
python Automation\main.py parallel --devices auto
```

也可以手动指定设备列表：

```powershell
python Automation\main.py parallel --devices "SN1,SN2" --max-workers 2
```

DevEco SDK 和 JDK 路径可以通过 `Automation/automation/config.py` 顶部的本机配置区维护，也可以通过参数或环境变量覆盖：

```powershell
python Automation\main.py --deveco-sdk-home "D:\DevEco Studio\sdk" --java-home "D:\DevEco Studio\jbr" --render-wait 10 batch
```

也可以把公共参数放在子命令后面：

```powershell
python Automation\main.py batch --deveco-sdk-home "D:\DevEco Studio\sdk" --java-home "D:\DevEco Studio\jbr" --render-wait 10
```

注意：`--deveco-sdk-home` 和 `--java-home` 只是运行参数，不是单独的“设置环境”命令；每次运行仍然需要带 `one`、`one-from-file` 或 `batch` 子命令。

Python runner 会直接执行 ArkTS 流程：`hvigor clean`、`hvigor assembleHap`、打印 HAP 输出目录、创建设备临时目录、`hdc file send`、`bm install -p`、清理临时目录、force-stop、启动 Ability。`JAVA_HOME\bin` 会被放到 `PATH` 最前面，确保签名工具使用 DevEco JDK。`--build-timeout` 控制本地构建和安装超时，`--render-wait` 控制应用启动后等待多久再截图。

## 输出

- DSL 文件：`dsl/{qid}.jsonl`
- ArkTS rawfile 目标：`ArkTs/entry/src/main/resources/rawfile/sample.jsonl`

`sample` 当前按 JSON 数组文件校验并复制到 ArkTS rawfile 目录。
- 截图文件：`output/{qid}.jpeg`

指定 `--sn` 或使用 `parallel` 时，输出会按设备隔离：

- DSL 文件：`dsl/{safe_sn}/{safe_sn}_{qid}.jsonl`
- ArkTS 工作副本：`Automation/.work/devices/{safe_sn}/ArkTs`
- 截图文件：`output/{safe_sn}/{safe_sn}_{qid}.jpeg`
