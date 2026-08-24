# 干净 dev 合入说明

本次重新合入不沿用旧模板 PR 的整体 squash。旧分支同时修改了 API、配置、模型客户端、协议注册、批量服务、
日志、Docker、根文档、Skill、测试报告和多个通用转换器，无法证明每项都属于模板主路径。

新的变更分类只有两类：

1. `cloud/services/template_generation/`：模板匹配、展开、A2UI 字符串接口、资源、测试和文档。
2. `cloud/services/widget_generation_service.py`：在 `_generate_widget_card_with_policy` 内负责模板路由、回退策略，并复用
   主生成链组装 TaskSpec、CardSpec、artifact 和 `GenerateWidgetCardResponse`。

本阶段在模板模块内部完成第二次资产升级：

- 12 个旧模板前缀拆分为 82 个“模板 ID 即 UI 形态”的 `.cardtpl` 定义；日期与日程归并后，
  Provider 业务索引为 11 个业务领域。
- 删除作者语法中的 `Variant`、`allowedParentComponents` 和 `limits`。
- `provider.json` 使用 `dataDomain`、`description`、`primaryData`、`secondaryData`、`optionalData`。
- 新增独立 Layout Provider，第二层根组件改为支持 `...children` 的布局模板。
- 第一层拒绝语义改为 Theme 有值、`component=[]`、`action=null`。

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
