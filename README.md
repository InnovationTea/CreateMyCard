# CreateMyCard

CreateMyCard 是 HarmonyOS A2UI Form 服务卡片的 AI Skill 开发仓库。核心产物是一个可被 AI Agent 加载的 Skill——根据一句话自然语言描述，生成完整的卡片 DSL（genui JSONL）+ 数据契约（CardSpec JSON）。

## 目录结构

```
CreateMyCard/
├── skills/                         # 正式发布的 Skill
│   └── harmony-card-generation/    # 主 Skill
│       ├── SKILL.md                # Skill 定义（系统提示词）
│       ├── reference.md            # 参考文档索引
│       ├── reference/              # 14 份协议/组件/设计参考文档
│       ├── scripts/                # 内置校验脚本（DSL + CardSpec）
│       ├── agents/                 # Agent 接口定义（OpenAI 格式）
│       └── template/               # Skill 内置模板（经筛选发布）
│
├── template/                       # 备选模板池
│   ├── layout/                     # 通用布局模板（2x2 / 2x4）
│   └── scene/                      # 场景模板（care, marathon, meeting...）
│
├── test/                           # 测试与评估
│   ├── batch_generate.py           # 批量生成 CLI 入口
│   ├── queries.jsonl               # 测试查询集
│   ├── createmycard_generator/     # 生成 pipeline（API 调用、提示词组装、DSL 提取）
│   └── createmycard_validator/     # 规则校验引擎（7 个模块、~80 条规则、3 个 profile）
│
├── resources/                      # 公共资源（图片素材等）
└── scripts/                        # 项目级脚本
```

## 工作流

### 模板开发流程

1. **创建场景模板** — 在 `template/scene/<场景名>/` 下编写 `.dat`（DSL JSONL）文件和 `query.txt`（描述语句）
2. **批量测试** — 用 `test/batch_generate.py` 跑批量生成和校验，评估质量
3. **人工审核** — 查看生成结果和渲染截图（`.png`）
4. **发布到 Skill** — 将效果好的模板发布到 `skills/harmony-card-generation/template/`

### Skill 迭代流程

1. **修改 Skill 定义** — 编辑 `skills/harmony-card-generation/SKILL.md` 或 `reference/` 下的参考文档
2. **回归测试** — 用 `test/batch_generate.py --validate` 跑测试查询集，对比前后生成质量
3. **校验器调优** — 在 `test/createmycard_validator/rules/` 下调整规则权重和启用状态

## 批量测试

```bash
# 基本生成
python test/batch_generate.py --queries test/queries.jsonl --skill-dir skills/harmony-card-generation

# 生成 + 校验
python test/batch_generate.py --queries test/queries.jsonl --skill-dir skills/harmony-card-generation --validate

# 生成 + 校验 + 失败重试
python test/batch_generate.py --queries test/queries.jsonl --skill-dir skills/harmony-card-generation --validate --max-retry 2

# 输出每条查询的独立文件
python test/batch_generate.py --queries test/queries.jsonl --skill-dir skills/harmony-card-generation --write-items
```

### 独立校验

```bash
# 校验 DSL
python skills/harmony-card-generation/scripts/validate_genui_card.py path/to/card.dsl.jsonl

# 校验 CardSpec
python skills/harmony-card-generation/scripts/validate_cardspec.py path/to/card.cardspec.json

# 校验目录下所有文件
python -m test.createmycard_validator.validator path/to/output_dir/
```

## 卡片尺寸

| 尺寸 | 分辨率 | 说明 |
|------|--------|------|
| 2x2  | 160 × 160 vp | 默认尺寸，方形卡片 |
| 2x4  | 320 × 160 vp | 横版卡片 |

## 技术栈

- **Skill 定义**：Markdown（SKILL.md + 参考文档）
- **测试工具**：Python 3（批量生成 + 校验器）
- **LLM API**：Anthropic Messages API 兼容接口
- **卡片协议**：HarmonyOS A2UI Extended Catalog v0.9
