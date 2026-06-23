# CreateMyCard A2UI DSL 静态校验器

`createmycard_validator` 是 CreateMyCard 项目的 DSL 静态校验核心，供命令行和 `batch_generate.py --validate` 复用。设计目标是模块化、低耦合，并方便新增匹配规则检测生成的 DSL。

## 核心流程

```text
DSL text
  -> common.collect_context() 生成 ValidationContext
  -> validator.validate() 按 profile 执行模块
  -> <module>_validator.validate(ctx) 产出 Finding
  -> engine.RuleBook.enrich() 从 rules/*.json 补齐 severity/deduct/dimension
  -> 汇总 score / dimension_summary / errors
```

## 校验维度

| 模块 | 内容 |
|---|---|
| `json` | JSONL 语法、单行对象合法性 |
| `protocol` | version、消息体字段、createSurface/updateComponents/updateDataModel 协议完整性 |
| `surface` | surfaceId 一致性和命名 |
| `tree` | root、children 引用、循环引用 |
| `component` | 组件字段和组件目录规范 |
| `data` | DataModel、绑定路径、List 重复模板数据源 |
| `design` | padding、maxLines、点击区域、对齐、字体和颜色样式 |

## 文件结构

```text
createmycard_validator/
├── validator.py            # Public API + CLI + 报告汇总
├── validate_rules.py        # 规则/profile/实现覆盖自校验
├── common.py                # Finding、ValidationContext、DSL 解析和通用查询 API
├── rule_check.py            # RuleCheckSpec 新规则扩展契约
├── engine.py                # RuleBook、profile、依赖跳过逻辑
├── registry.py              # 模块注册表
├── *_validator.py           # 各模块校验实现
├── profiles/                # dev / train / release
└── rules/                   # *_rules.json
```

## 新增规则推荐流程

### 1. 选择模块和 Rule ID

例如新增设计规则：

```text
RULE_DESIGN_009
```

### 2. 在规则 JSON 中增加元数据

编辑 `rules/design_rules.json`：

```json
{"id":"RULE_DESIGN_009","module":"design","dimension":"设计规范","severity":"WARNING","deduct":0,"enabled":true,"message":"示例设计规则"}
```

### 3. 在模块 validator 中新增 check 函数

示例：

```python
def check_demo_rule(ctx: ValidationContext) -> list[Finding]:
    findings = []
    for component in ctx.iter_components("Text"):
        ...
    return findings
```

### 4. 注册到 `RULE_CHECKS`

如果该模块已经使用 `RuleCheckSpec`：

```python
RULE_CHECKS = [
    RuleCheckSpec("RULE_DESIGN_009", "design", check_demo_rule),
]
```

旧模块仍可继续在 `validate(ctx)` 中直接返回 findings；`RULE_CHECKS` 是推荐的新扩展方式。

### 5. 运行自检和规则说明

```powershell
python createmycard_validator/validate_rules.py
python createmycard_validator/validator.py --explain-rule RULE_DESIGN_009
python createmycard_validator/validator.py sample.dat --profile train
```

## ValidationContext 可用 API

新增规则时优先使用这些辅助方法，避免重复遍历 raw DSL：

```python
ctx.iter_components()
ctx.iter_components("Text")
ctx.get_component("root")
ctx.iter_texts()
ctx.iter_buttons()
ctx.has_data_path("/items")
ctx.get_data_path("/items")
```

数据绑定使用 `DataBinding`：

```python
for binding in ctx.bindings:
    binding.component_id
    binding.path
    binding.scope_path
    binding.repeated
    binding.is_relative
```

List 重复模板内允许相对 path，例如 `name`；普通全局绑定仍应使用 JSON Pointer，例如 `/user/name`。

## CLI 用法

```powershell
# 校验单个文件
python createmycard_validator/validator.py output/q1.dat --profile train

# 校验目录
python createmycard_validator/validator.py output --profile train --output output/validation_report.json

# 只启用部分模块
python createmycard_validator/validator.py output/q1.dat --enable protocol tree

# 禁用模块或规则
python createmycard_validator/validator.py output/q1.dat --disable design
python createmycard_validator/validator.py output/q1.dat --disable-rule RULE_DESIGN_003

# 查看元信息
python createmycard_validator/validator.py --list-modules
python createmycard_validator/validator.py --list-rules
python createmycard_validator/validator.py --explain-rule RULE_PROTOCOL_004
```

## Profile

当前维护三个 profile：

```text
profiles/dev.json
profiles/train.json
profiles/release.json
```

默认 profile 在 `registry.py` 中定义为：

```python
DEFAULT_PROFILE = "train"
```

## 规则配置自检

```powershell
python createmycard_validator/validate_rules.py
```

自检会检查：

- 规则 JSON 是否合法
- rule id 是否重复
- 规则引用的 module 是否存在
- severity / deduct / enabled / message 字段是否合法
- profile 中启用/禁用模块和规则是否存在
- 已启用规则是否能检测到实现
- 实现中出现的 rule id 是否存在元数据
- 规则实现模块是否和元数据 module 一致

## Python API

```python
from createmycard_validator.validator import validate, validate_file, validate_directory

report = validate(dsl_text, profile="train")
file_report = validate_file("output/q1.dat", profile="train")
dir_report = validate_directory("output", profile="train")
```

返回值包含：

- `passed`
- `score`
- `dimension_scores`
- `dimension_summary`
- `errors`：包含 ERROR 和 WARNING finding
- `skipped_modules`
