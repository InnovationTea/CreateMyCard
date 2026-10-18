# Validator Rules

该目录是标准 A2UI 校验 API 的服务内静态规则快照，供
`cloud/services/card_validation/` 在运行时直接读取。

运行时不得依赖或执行 `skills/*/scripts`。更新在线校验逻辑时，应同步检查本目录、
`docs/云侧方案设计.md` 和相关测试，保证校验代码与部署规则一致。

当前快照同步自 `skills/harmony-card-generation-online/scripts/rules/`；微服务通过
`services.card_validation.validate_card` Python API 加载，不调用 Skill CLI。

同步范围不是只有新增的能力 Schema，而是在线校验器的完整运行时快照：

- `config/` 下 6 个规则文件：协议、组件样式、素材、表达式、布局和诊断文案。
- `schemas/` 下 7 个数据能力 Schema 和 1 个点击事件 Schema。
- 对应的 18 个 Python 校验模块位于 `cloud/services/card_validation/`。

Skill 中的 `validate_card.py` 是 CLI 包装层，不复制到微服务；它调用的校验逻辑已经
以内嵌 Python API 的方式同步到 `cloud/services/card_validation/`。
