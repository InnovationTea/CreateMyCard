# CreateMyCard

CreateMyCard 是基于 LLM 的鸿蒙桌面卡片 A2UI DSL 批量生成、静态校验与自动修复工具链。

## 功能

- 根据自然语言 query 生成 A2UI JSONL DSL
- 支持生成后 7 维度静态校验
- 校验失败时可将错误反馈给模型并自动重试修复
- 支持 JSONL / CSV 输入
- 默认只输出汇总 `results.json`，可按需额外输出单条 `.json` / `.dat`

## 当前结构

```text
CreateMyCard-main/
├── batch_generate.py          # 薄 CLI 入口
├── createmycard_generator/            # 生成流程：配置、API、prompt、DSL 解析、输出、pipeline
├── createmycard_validator/            # 生产静态校验器：规则、profile、CLI、Python API
├── skills/                    # 生成 prompt 所需 skill 和 reference 文档
├── queries.jsonl              # 默认输入样例
├── test/                      # 后续测试目录
└── .env                       # 本地 API 配置（不提交）
```

## 配置

安装依赖：

```bash
pip install requests python-dotenv
```

在项目根目录创建 `.env`：

```env
ANTHROPIC_AUTH_TOKEN=你的API令牌
ANTHROPIC_BASE_URL=https://yunwu.ai
ANTHROPIC_MODEL=claude-opus-4-6
```

## 常用命令

### 只生成，不校验

```bash
python batch_generate.py -i queries.jsonl
```

### 生成 + 校验 + 自动修复重试

```bash
python batch_generate.py -i queries.jsonl --validate --max-retry 2
```

### 生成 + 校验，但不做修复重试

```bash
python batch_generate.py -i queries.jsonl --validate --max-retry 0
```

### 默认只输出汇总文件

```bash
python batch_generate.py -i queries.jsonl --validate
```

默认只更新 `output/results.json`，不会生成 `q1.json` / `q1.dat` 等单条文件。

### 额外输出单条文件

```bash
python batch_generate.py -i queries.jsonl --validate --write-items
```

使用 `--write-items` 时，会在汇总文件之外额外生成每条 query 的 `.json` 和 `.dat` 文件。

### 关闭关键词提取

关键词提取默认开启，如需关闭：

```bash
python batch_generate.py -i queries.jsonl --no-extract-keywords
```

### 配置检查，不调用 API

```bash
python batch_generate.py --dry-run --validate --max-retry 1 --no-extract-keywords
```

## CLI 参数

```text
-i, --input FILE             输入 queries JSONL 或 CSV 文件路径
-o, --output FILE            汇总 results JSON 文件路径
--item-output-dir DIR        单条 JSON/dat 输出目录
--skill-dir DIR              skill 目录路径
--model NAME                 覆盖模型名称
--base-url URL               覆盖 API base URL
--auth-token TOKEN           覆盖 API token
--temperature FLOAT          模型温度；默认不发送
--max-tokens N               每次请求最大 token 数，默认 32768
--timeout N                  API 请求超时秒数，默认 120
--delay FLOAT                query 间隔秒数，默认 1.0
--config FILE                API 配置文件路径
--validate                   启用静态校验
--write-items                额外输出每条 query 的独立 JSON/dat 文件
--single-file                兼容旧参数；当前默认只输出汇总 results.json
--extract-keywords           显式开启关键词提取（默认开启）
--no-extract-keywords        关闭关键词提取
--max-retry N                校验失败时最多修复重试 N 次，默认 1
--dry-run                    只检查配置和输入，不调用 API
```

## 输出

默认只输出：

```text
output/
└── results.json      # 汇总结果
```

如果使用 `--write-items`，则额外输出：

```text
output/
├── q1.json           # 单条完整结果
├── q1.dat            # 单条纯 JSONL DSL
└── ...
```

`results.json` 中每条记录包含：

- `id`
- `query`
- `keywords`
- `dsl`：解析后的 DSL 对象数组
- `metadata.validation`：校验结果
- `metadata.retry_count`
- `metadata.elapsed_ms`

## 静态校验器

校验器位于 `createmycard_validator/`。

单文件校验：

```bash
python createmycard_validator/validator.py output/q1.dat --profile train
```

目录校验：

```bash
python createmycard_validator/validator.py output --profile train --output output/validation_report.json
```

规则/profile 自检：

```bash
python createmycard_validator/validate_rules.py
```

列出规则：

```bash
python createmycard_validator/validator.py --list-rules
```

## 校验维度

| 模块 | 内容 |
|---|---|
| `json` | JSONL 格式、版本字段 |
| `protocol` | createSurface / updateComponents / updateDataModel 协议顺序和完整性 |
| `surface` | surfaceId 一致性和命名 |
| `tree` | root、children 引用、循环引用 |
| `component` | 组件字段规范 |
| `data` | DataModel 和数据绑定完整性 |
| `design` | padding、maxLines、点击区域、对齐等设计规则 |

## 开发验证

```bash
python -m compileall -q batch_generate.py createmycard_generator createmycard_validator
python createmycard_validator/validate_rules.py
python batch_generate.py --dry-run --validate --max-retry 1 --no-extract-keywords
```
