# Datamodel-First 卡片校验器

本目录提供 `harmony-card-generation-datamodel-first` 的本地校验程序，用于校验模型生成的 `genui` DSL JSONL 和 `cardspec` JSON。

校验器目标：

- 先保证 DSL / CardSpec 语法正确、协议闭环、可渲染。
- 再检查 DataModel 绑定、CardSpec data capability、事件参数、资源路径。
- 最后做基础布局、样式、颜色和质量评分，帮助模型修复到更稳定、更美观的卡片。

## 快速使用

在仓库根目录运行：

```bash
python skills/harmony-card-generation-datamodel-first/scripts/validate_card.py --dsl out.genui.jsonl --cardspec out.cardspec.json
```

只校验 DSL：

```bash
python skills/harmony-card-generation-datamodel-first/scripts/validate_card.py --dsl out.genui.jsonl
```

只校验 CardSpec：

```bash
python skills/harmony-card-generation-datamodel-first/scripts/validate_card.py --cardspec out.cardspec.json
```

校验包含两个 fenced code block 的完整草稿：

```bash
python skills/harmony-card-generation-datamodel-first/scripts/validate_card.py draft.md
```

输出给模型二次修复的短格式：

```bash
python skills/harmony-card-generation-datamodel-first/scripts/validate_card.py --dsl out.genui.jsonl --cardspec out.cardspec.json --format model
```

## CLI 参数

- `path`：可选，包含 `genui` / `cardspec` 代码块的草稿文件；省略或写 `-` 时读取 stdin。
- `--dsl`：genui JSONL 文件，或包含 fenced `genui` block 的文件。
- `--cardspec`：CardSpec JSON 文件，或包含 fenced `cardspec` block 的文件。
- `--stage hard|semantic|quality|all`：控制校验阶段，默认 `all`。
- `--format text|json|model`：输出格式，默认 `text`。
- `--max-errors N`：最多输出多少条 error，默认 `50`。
- `--strict`：warning 也导致退出码为 `1`。
- `--stop-on-stage-error`：恢复旧的阶段阻断行为；默认会继续收集可独立判断的后续阶段问题，减少多轮修复。

输入文件按 `utf-8-sig` 读取，兼容带 BOM 的 UTF-8 文件；stdin 开头的 BOM 也会自动去掉。

退出码：

- `0`：无 error。
- `1`：存在 error；或指定 `--strict` 且存在 warning。

## 目录结构

```text
scripts/
  validate_card.py
  README.md
  rules/
    form_catalog.json
    expression_grammar.ebnf
    config/
      protocol.json
      layout.json
      style.json
      color.json
      asset.json
      diagnostics.zh-CN.json
    schemas/
      cardspec.schema.json
      capability.calendar.schema.json
      capability.weather.schema.json
      event.click.schema.json
  validators/
    __init__.py
    asset_validator.py
    base.py
    binding_validator.py
    cardspec_validator.py
    color_validator.py
    component_validator.py
    context.py
    cross_validator.py
    diagnostics.py
    expression_validator.py
    protocol_validator.py
    quality_validator.py
    rule_registry.py
    source_parser.py
```

## 执行流程

`validate_card.py` 做三件事：

1. `RuleRegistry` 从 `scripts/rules/` 加载规则、配置和 capability schema。
2. `SourceParser` 解析 DSL / CardSpec，构造 `ValidationContext`。
3. 按阶段运行 `validators/` 中注册的 Validator。

阶段顺序：

```text
hard -> semantic -> quality
```

门禁规则：

- 默认尽量多报：`hard`、`semantic`、`quality` 会按顺序运行，便于模型一次看到结构、语义和质量问题。
- JSONL 行本身解析失败时，不继续运行依赖 DSL 结构的 Validator，避免错位索引造成误报。
- 指定 `--stop-on-stage-error` 时恢复旧行为：`hard` error 阻断 `semantic/quality`，`semantic` error 阻断 `quality`。
- `quality` 阶段会输出 `qualityScore` 和 `status`。

`status` 含义：

- `invalid`：存在 error。
- `valid_with_quality_risks`：无 error，但质量分低于 70。
- `valid`：无 error，质量分 70-89。
- `polished`：无 error，质量分不低于 90。

## Validator 职责

### `protocol_validator.py`

阶段：`hard`

检查：

- 三行 JSONL 顺序：`createSurface` -> `updateComponents` -> `updateDataModel`。
- `version`、`catalogId`、`surfaceId`。
- `createSurface`、`updateComponents`、`updateDataModel` 的必填字段是否存在且非空。
- `updateDataModel.path` 是否是结构 JSON Pointer。
- `createSurface.styles` 只允许 `borderRadius`、`clip`。

主要规则来源：

- `rules/config/protocol.json`
- `rules/config/style.json`

### `component_validator.py`

阶段：`hard`

检查：

- 组件类型是否允许。
- 组件 id 是否唯一。
- root 是否引用存在组件。
- 顶层字段是否符合组件目录。
- 公共必填顶层字段、组件特有必填顶层字段是否存在且非空。
- `children` 引用是否存在。
- 模板 `children` 对象是否只用于 `Row` / `Column` / `List`。

主要规则来源：

- `rules/form_catalog.json`
- `rules/config/protocol.json`

### `cardspec_validator.py`

阶段：`hard`

检查：

- CardSpec 必填字段：`title`、`description`、`suggestSize`。
- `title` / `description` 必须是静态字符串。
- `suggestSize` 只能是 `2x2` / `2x4`。
- `dataBindings[].capabilityId/arguments/writeResultTo` 基础形态。
- 多个 `writeResultTo` 不得互相覆盖。

### `expression_validator.py`

阶段：`hard`

检查：

- 动态值必须是完整 `{{ ... }}` 表达式。
- 不允许半嵌入表达式，例如 `"会议 {{ ${/time} }}"`。
- 不允许嵌套多组 `{{ ... }}`。
- 表达式内字符串必须使用单引号。
- 禁用 `$__widthBreakpoint`、`$__colorMode`、`$item`、`$index`。
- 禁用旧式 `{"path": ...}` 和 `formatString` 值绑定。
- `id`、`component`、EventHandler `call/as`、模板 `children.path` 等结构字段不允许表达式。

备注：

- 当前实现是轻量扫描校验，不依赖第三方 parser。
- `expression_grammar.ebnf` 保留为规范来源，后续可以接入正式 parser。

### `asset_validator.py`

阶段：`hard`

检查：

- `Image.src` 和 `styles.backgroundImage` 禁止网络 URL、`data:image`、base64。
- 静态资源路径必须在素材 allowlist 中。
- 表达式资源路径会尝试从 `updateDataModel.value` 静态解析；无法解析时给 warning。

主要规则来源：

- `rules/config/asset.json`
- `reference/design/asset-library.md`

`RuleRegistry` 会自动从 `asset-library.md` 提取 `resources/base/media/*.svg`。

### `binding_validator.py`

阶段：`semantic`

检查：

- `dataBindings[].capabilityId` 是否已声明。
- `arguments` 是否符合 capability `inputSchema.properties`。
- `arguments` 不能写 DSL 表达式或旧绑定对象。
- 模板 `children.path` 是否指向数组。
- 表达式中的绝对 JSON Pointer 是否能从 `updateDataModel.value` 或 `writeResultTo + outputSchema` 推导。
- 模板子树内的相对表达式是否合理。
- `onClick` 事件能力和参数是否符合 `event.click.schema.json`。

主要规则来源：

- `rules/schemas/capability.*.schema.json`
- `rules/schemas/event.click.schema.json`

### `cross_validator.py`

阶段：`semantic`

检查：

- DSL surface 尺寸是否与 CardSpec `suggestSize` 一致；`createSurface.width/height` 可写 `matchParent`，校验按 profile 基准尺寸解析。
- CardSpec `writeResultTo` 根路径是否在 `updateDataModel.value` 中初始化。

### `color_validator.py`

阶段：`quality`

检查：

- 颜色必须是最终 hex：`#RRGGBB` 或 `#AARRGGBB`。
- 不允许直接输出 token 名，例如 `brand`、`font_primary`、`multi_color_02`。
- 渐变结构必须包含 `direction` 和合法 stop。
- hex 未能回溯到 token、多彩色或场景拓展色时给 warning。

主要规则来源：

- `rules/config/color.json`
- `reference/design/color-token-values.md`
- `reference/design/color-token-system.md`

### `quality_validator.py`

阶段：`quality`

检查：

- root `width/height/borderRadius/clip/padding/background`；root `width/height` 可写 `matchParent`，内部组件使用 `matchParent` 会报错。
- Row 横向预算。
- Column 纵向预算。
- 字号阶梯。
- 间距阶梯。
- Button 最小尺寸。
- Image 必须有 `width`、`height`、`objectFit`。
- 环形 Progress 宽高相等。
- 静态文本宽度估算。
- 计算 `qualityScore`。

主要规则来源：

- `rules/config/layout.json`
- `rules/config/style.json`
- `rules/config/protocol.json`

## 规则文件维护

### 修改尺寸、圆角、catalogId

编辑：

```text
scripts/rules/config/protocol.json
```

常见字段：

- `version`
- `catalogIds`
- `messageOrder`
- `messageRequiredFields`
- `messageNonEmptyFields`
- `sizes`
- `allowedComponents`
- `forbiddenComponents`
- `commonTopLevelFields`
- `componentCommonRequiredFields`
- `componentNonEmptyRequiredFields`
- `componentTopLevelFields`
- `componentRequiredFields`

### 修改字号、间距、按钮最小尺寸

编辑：

```text
scripts/rules/config/layout.json
```

常见字段：

- `allowedFontSizes`
- `allowedSpacing`
- `minClickableSize`
- `defaultPadding`

### 修改样式字段或枚举

编辑：

```text
scripts/rules/config/style.json
```

常见字段：

- `commonStyleFields`
- `componentStyleFields`
- `enumValues`
- `imageRequiredStyles`

### 修改颜色来源

编辑：

```text
scripts/rules/config/color.json
```

如果只是新增官方 token hex，优先更新：

```text
reference/design/color-token-values.md
```

`RuleRegistry` 会从该文档自动收集 hex。

### 修改资源白名单

优先更新：

```text
reference/design/asset-library.md
```

校验器会自动提取文档中的：

```text
resources/base/media/*.svg
```

若需要临时追加，也可以编辑：

```text
scripts/rules/config/asset.json
```

### 新增数据能力

在 `scripts/rules/schemas/` 新增文件：

```text
capability.<name>.schema.json
```

文件形态：

```json
{
  "capabilityId": "example.capability",
  "preferredWriteResultTo": "/data/example",
  "inputSchema": {
    "type": "object",
    "properties": {}
  },
  "outputSchema": {
    "type": "object",
    "properties": {}
  }
}
```

新增后无需改 `RuleRegistry`，它会自动加载所有 `capability.*.schema.json`。

### 新增事件能力

编辑：

```text
scripts/rules/schemas/event.click.schema.json
```

当前事件校验集中在 `clickToCallPhone`、`clickToDeeplink`、`clickToIntent` 三类函数。若新增完全不同的事件函数，通常还需要扩展 `binding_validator.py` 中的事件参数检查。

### 修改诊断文案

编辑：

```text
scripts/rules/config/diagnostics.zh-CN.json
```

当 Validator 调用 `reporter.add()` 时，如果没有传入自定义 `message` 或 `fix_hint`，会从这里按错误码取默认文案。

## 新增 Validator

1. 在 `scripts/validators/` 下新增模块。
2. 继承 `BaseValidator`。
3. 设置 `stage` 和 `name`。
4. 实现 `validate(self, context, rules, reporter)`。
5. 在 `scripts/validate_card.py` 的 `VALIDATORS` 列表中注册。

示例：

```python
from validators.base import BaseValidator


class ExampleValidator(BaseValidator):
    stage = "quality"
    name = "example"

    def validate(self, context, rules, reporter):
        reporter.add(
            "warning",
            "EXAMPLE_WARNING",
            self.stage,
            "genui",
            message="示例 warning。",
            fix_hint="按需要修复。",
        )
```

## 诊断输出

内部诊断结构：

```json
{
  "severity": "error",
  "code": "EXPR_FULL_STRING_REQUIRED",
  "stage": "hard",
  "file_kind": "genui",
  "line": 2,
  "json_pointer": "/updateComponents/componentsById/title/content",
  "message": "动态值必须是完整 {{ ... }} 表达式，不能半嵌入普通字符串或嵌套表达式。",
  "actual": "会议 {{ ${/meeting/time} }}",
  "expected": "{{ '会议 ' + ${/meeting/time} }}",
  "fix_hint": "把静态文本也放进表达式内部，用 + 拼接。",
  "source": "config/diagnostics.zh-CN.json"
}
```

`--format text` 适合人工阅读。  
`--format json` 适合集成脚本。  
`--format model` 适合把错误直接喂回模型修复。

## 验证命令

编译检查：

```bash
python -m py_compile skills/harmony-card-generation-datamodel-first/scripts/validate_card.py skills/harmony-card-generation-datamodel-first/scripts/validators/*.py
```

校验单个模板：

```bash
python skills/harmony-card-generation-datamodel-first/scripts/validate_card.py \
  --dsl skills/harmony-card-generation-datamodel-first/assets/templates/2x2-countdown-panel/template.genui.jsonl \
  --cardspec skills/harmony-card-generation-datamodel-first/assets/templates/2x2-countdown-panel/cardspec.json \
  --format json
```

PowerShell 批量校验模板：

```powershell
$failed = 0
$templates = Get-ChildItem .\skills\harmony-card-generation-datamodel-first\assets\templates -Directory
foreach ($t in $templates) {
  $dsl = Join-Path $t.FullName 'template.genui.jsonl'
  $card = Join-Path $t.FullName 'cardspec.json'
  if ((Test-Path $dsl) -and (Test-Path $card)) {
    python .\skills\harmony-card-generation-datamodel-first\scripts\validate_card.py --dsl $dsl --cardspec $card --format json | Out-Null
    if ($LASTEXITCODE -ne 0) {
      Write-Host "FAILED $($t.Name)"
      $failed++
    }
  }
}
if ($failed -eq 0) { Write-Host 'all templates passed' } else { exit 1 }
```

## 当前边界

- 当前表达式检查是轻量扫描校验，不是完整 EBNF parser。
- `cardspec.schema.json` 目前主要作为结构契约文档保留，主要 hard 校验在 `cardspec_validator.py` 中完成。
- 布局检查是静态估算，不等同真实渲染截图验证。
- `qualityScore` 是工程质量门，不是绝对审美评分。
- 如果新增复杂能力，优先新增 schema/config；只有涉及跨节点推导、布局预算或新语义时，再新增 Validator。
