# 干净 dev 合入说明

本次重新合入不沿用旧模板 PR 的整体 squash。旧分支同时修改了 API、配置、模型客户端、协议注册、批量服务、
日志、Docker、根文档、Skill、测试报告和多个通用转换器，无法证明每项都属于模板主路径。

新的变更分类只有两类：

1. `cloud/services/template_generation/`：模板功能的全部代码、资源、测试和文档。
2. `cloud/services/widget_generation_service.py`：一个模板接口 import，以及 Compact、Terse 两个主入口各一段
   简单的 `try/except` 模板尝试和旧链路回退。

明确不纳入本次 PR：

- 批量生成和批量结果存储。
- DeepSeek 调用预算数据库。
- WebSocket 鉴权和路由重构。
- Docker、依赖清单和环境样例调整。
- A2UI/Terse/Compact 通用转换器替换。
- API response 的模板诊断字段。
- 根能力注册表、协议 profile 和 Validator 规则改版。
- 与模板无关的 Skill、测试报告和工具页面。

旧大分支保留作历史对照，不作为新 PR 的提交基础。
