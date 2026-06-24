# CLAUDE.md

这是一个 HarmonyOS A2UI Form 服务卡片的 AI Skill 开发仓库。

## 项目定位

本仓库开发和维护一个 AI Skill：输入一句话，输出完整的 HarmonyOS 桌面卡片（genui DSL JSONL + CardSpec JSON）。仓库同时包含模板库和自动化测试/校验工具链。

## 关键目录

- `skills/harmony-card-generation/` — **核心 Skill 源码**，包括 SKILL.md（系统提示词）、14 份参考文档（reference/）、2 个校验脚本（scripts/）
- `template/` — **备选模板池**，layout/ 是通用布局，scene/ 是场景化卡片。这里是草稿区，效果好的模板会发布到 `skills/.../template/`
- `test/` — **测试工具链**，batch_generate.py 是批量生成 CLI，createmycard_generator/ 是生成 pipeline，createmycard_validator/ 是规则校验引擎

## Skill 结构（skills/harmony-card-generation/）

- `SKILL.md` — Skill 入口，定义了完整的工作流（13 步）、场景分类、参考路由决策树、40+ 条不可违反的规则
- `reference.md` — 参考文档导航索引，按任务和触发条件路由到具体文档
- `reference/protocol.md` — Form 协议硬约束（最高优先级）
- `reference/component-catalog.md` — 10 个允许的组件及其属性/样式枚举
- `reference/card-composition-rules.md` — 可泛化的构图规则（311 行，最核心的布局参考）
- `reference/data-binding.md` — DataModel、表达式、模板循环
- `reference/cardspec.md` — CardSpec 数据契约（dataBindings, refreshPlan）
- `reference/data-capability/` — 天气、日历等端侧数据能力契约
- `reference/design-review.md` — 视觉/交互评审标准
- `reference/review-validation.md` — 最终验收入口

## 模板文件格式

- `.dat` 文件 — JSON 文本，包含 A2UI JSONL DSL 消息（createSurface, updateComponents, updateDataModel）
- `.png` 文件 — 对应卡片的渲染截图
- `query.txt` — 生成该卡片时使用的描述语句

## 校验器（test/createmycard_validator/）

模块化、基于规则的 DSL 静态分析引擎：
- 7 个校验模块：json → protocol → surface/tree → component/data/design
- 上游模块失败时下游模块跳过（依赖链）
- 3 个 profile：dev（宽松）、train（默认、完整依赖链）、release（严格）
- 规则定义在 `rules/` 目录的 JSON 文件中，可调整权重和启用状态

## 常用命令

```bash
# 批量生成 + 校验
python test/batch_generate.py -i test/queries.jsonl --skill-dir skills/harmony-card-generation --validate

# 独立校验 DSL
python skills/harmony-card-generation/scripts/validate_genui_card.py <file.dsl.jsonl>

# 独立校验 CardSpec
python skills/harmony-card-generation/scripts/validate_cardspec.py <file.cardspec.json>
```

## 编辑注意事项

- 修改 `SKILL.md` 或 `reference/` 后应跑 `batch_generate.py --validate` 回归测试
- 模板的 `.dat` 文件是 JSON 格式但使用 .dat 扩展名，不要当二进制处理
- 卡片只支持 10 个组件：Text, Image, Divider, Progress, Button, Checkbox, Row, Column, List, Stack
- 卡片协议版本固定为 `v0.9`，catalogId 固定为 `ohos.a2ui.extended.catalog`
- LLM 默认使用 `claude-opus-4-6`，API base URL 配置在环境变量或 test/createmycard_generator/config.py
