# 阿里云百炼可选模型通道 Implementation Plan

**Goal:** 基于PR539新增可选aliyun_bailian通道，使用独立配置，不改变现有通道、默认选项或Prompt合同。

**Architecture:** 将现有DeepSeek非流式HTTP传输的等价逻辑提取为共享OpenAI兼容传输，保留原DeepSeek薄适配；百炼使用独立适配、配置与provider名称，复用现有执行限流、超时、重试、Trace和Plan→DSL→Repair流程。

**Tech Stack:** Python、httpx、Pydantic Settings、pytest、Ruff、GitHub CLI、官方build_gallery.mjs。

## 1. 配置与测试先行

- 先更新云侧方案的模型通道说明。
- 新增测试：provider主备选择、独立密钥与模型、base URL补全、当前thinking参数、错误映射、超时、资源关闭。
- 无密钥时不得调用网络或借用DeepSeek密钥；不在URL、日志、Trace、示例配置或PR中保留实际密钥。
- 提取共享HTTP实现时保持DeepSeek旧错误码、请求体与返回值；运行原HTTP、路由、Trace测试回归。

## 2. 实现与真实单例

- 更新config.py、default_config.yaml、.env.example、model_transport.py、model_runtime.py。
- 新建共享HTTP传输与百炼适配，原DeepSeek适配仅做等价配置映射。
- 使用用户提供的百炼部署地址与模型deepseek-v4.1-flash；密钥仅隐藏输入到进程环境。
- Q053单例：最多5次修复、runtime prompt context=false，校验通过并生成官方Gallery后才提交PR。
- 配置提供者时Runner不得继续强制覆盖成DeepSeek官方；通过受控实验入口传入，不改业务合同。

## 3. 提交PR

- PR基线为PR539头分支，仅提交接入代码、配置、测试和文档；不夹带提示词优化。
- 无上游写权限则推送个人fork的新分支，以PR539头分支为base创建堆叠PR。
- 提交前执行Ruff、相关pytest、git diff --check和敏感内容检查，核对暂存文件清单。

## 4. PR提交后执行原定双版本比较

- 版本A：PR539 + 本PR的阿里云通道；版本B：相同PR539与通道 + 已保存的修复优化。
- 相同cardSpec24的32条原始任务、相同百炼模型、采样参数和最多5次修复，串行各运行一批。
- few-shot开启、runtime prompt context关闭，不修改输入、不按输出修改Prompt、不拼接好结果。
- 两版采用同样的上游Drop策略；分别记录严格成功、降级、首次成功、累计耗时与实际信息覆盖。
- 使用build_gallery.mjs统一渲染，检查典型卡片的可读性、分区、截断、对齐与剩余失败；输出比较报告。

## 接入验收

- 2026-10-15：Q053真实单例成功，1次Plan、1次初始DSL、4次质量修复，累计57.185秒；
  最终产物包含Compact DSL和A2UI，官方build_gallery.mjs成功渲染1/1。
- 使用aliyun_bailian/deepseek-v4.1-flash，关闭thinking；密钥隐藏输入到进程环境，不写入仓库或配置文件。
- 原版测试test_debug_agent_prefers_official_http_when_api_key_is_configured在PR539上同样失败
  （期望high、实现disable），不属于本次接入回归；该断言未修改。
