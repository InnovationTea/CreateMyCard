# Validator Rules

该目录是标准 A2UI 校验 API 的服务内静态规则快照，供
`cloud/services/card_validation/` 在运行时直接读取。

运行时不得依赖或执行 `skills/*/scripts`。更新在线校验逻辑时，应同步检查本目录、
`docs/云侧方案设计.md` 和相关测试，保证校验代码与部署规则一致。
