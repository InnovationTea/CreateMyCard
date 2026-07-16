# Datamodel-First 卡片校验器

`scripts` 目录用于校验 HarmonyOS A2UI Form 卡片产物（三行 `genui` JSONL + `cardspec` JSON）。

下文命令默认在 `skills/harmony-card-generation-offline/` 目录下运行；如果在仓库根目录运行，把 `python scripts/validate_card.py` 替换为 `python skills/harmony-card-generation-offline/scripts/validate_card.py`。

校验分两类：

- **静态校验**：按 `scripts/rules/` 中的静态配置和 schema 校验，默认模式。
- **动态 effective 校验**：在同一套静态规则基础上，把数据/事件/素材三类能力的白名单替换为本次 `cloud-new` 过滤后的 `effectiveCapabilities`。

两者共用协议、组件、CardSpec、表达式、模板/绑定路径、跨文件一致、颜色等规则；区别只在数据/事件/素材能力的来源不同。

## 一、静态校验

### 1. JSONL + CardSpec

```bash
python scripts/validate_card.py --dsl out.genui.jsonl --cardspec out.cardspec.json
```

也可以传入同时包含两个 fenced code block 的草稿：

```bash
python scripts/validate_card.py draft.md
```

草稿格式：

````md
```genui
{"version":"v0.9","createSurface":{}}
{"version":"v0.9","updateComponents":{}}
{"version":"v0.9","updateDataModel":{}}
```
```cardspec
{"title":"天气","description":"今日天气","suggestSize":"2x4","dataBindings":[]}
```
````

### 2. 只传 JSONL

```bash
python scripts/validate_card.py --dsl out.genui.jsonl
```

只检查 JSONL 语法、协议行顺序、组件结构、表达式、素材基础安全等；缺少 CardSpec 时跨文件一致性和数据能力 schema 推导会受限。

### 3. 只传 CardSpec

```bash
python scripts/validate_card.py --cardspec out.cardspec.json
```

只检查 CardSpec 必填字段、尺寸、`dataBindings` 基础形态和 `writeResultTo` 冲突。

## 二、动态 effective 校验

动态校验运行在 semantic 阶段。默认 `--stage all` 会覆盖它；如果指定 `--stage hard`，不会运行动态能力校验。

动态校验不复算候选过滤，不判断 removed 原因，只检查最终 DSL/CardSpec 是否使用了 `effectiveCapabilities` 之外的数据、事件、素材能力。

### 1. JSONL + CardSpec + effective

```bash
python scripts/validate_card.py \
  --dsl out.genui.jsonl \
  --cardspec out.cardspec.json \
  --effective effective.json
```

如果输入是完整 `WidgetArtifact` JSON（包含 `genui`、`cardSpec`、`taskSpec`、`effectiveCapabilities`）：

```bash
python scripts/validate_card.py --artifact artifact.json
```

这是推荐接入方式，因为数据、事件、素材三类能力都有足够上下文。

### 2. 只传 JSONL + effective

```bash
python scripts/validate_card.py \
  --dsl out.genui.jsonl \
  --effective effective.json
```

仍会跑与静态 JSONL 校验相同的协议、组件、表达式、素材基础安全规则，并额外检查：

- DSL 中 `onClick[].call + args` 是否来自 `effectiveCapabilities.event`。
- DSL 中 `Image.src` / `backgroundImage` 是否来自 `effectiveCapabilities.asset` 解析出的资源路径。

只传 JSONL 时缺少 `CardSpec.dataBindings[].writeResultTo`，无法完整判断 `/data/...` 路径是否落在有效数据能力写入路径下；若 DSL 引用了 `/data/...`，推荐使用 `JSONL + CardSpec` 模式。

### 3. 只传 CardSpec + effective

```bash
python scripts/validate_card.py \
  --cardspec out.cardspec.json \
  --effective effective.json
```

仍会跑与静态 CardSpec 校验相同的必填字段、尺寸、`dataBindings` 基础形态、`writeResultTo` 冲突规则，并额外检查：

- `cardSpec.dataBindings[].capabilityId` 是否存在于 `effectiveCapabilities.data`。

由于没有 DSL，这种模式不会检查事件 `onClick` 和素材 `Image.src` / `backgroundImage`。

## effective.json 格式

可以直接传 `effectiveCapabilities`：

```json
{
  "data": ["ViewWeather"],
  "event": [
    {
      "call": "clickToDeeplink",
      "args": {"uri": "weather://home"}
    }
  ],
  "asset": ["asset.calendar_fill"]
}
```

也可以包一层：

```json
{
  "effectiveCapabilities": {
    "data": ["ViewWeather"],
    "event": [],
    "asset": []
  }
}
```

素材可以传 id，也可以传带 src 的对象：

```json
{
  "asset": [
    {
      "id": "asset.calendar_fill",
      "src": "resources/base/media/calendar_fill.svg"
    }
  ]
}
```

如果 effective 中只有素材 id，校验器按以下顺序把 id 解析成 `src`：

1. `artifact.taskSpec.assetCandidates`
2. `--capabilities-dir/asset_capabilities.json`

示例：

```bash
python scripts/validate_card.py \
  --artifact artifact.json \
  --capabilities-dir cloud-new/cloud/data/capabilities/app-11.7.5.205_rom-36
```

动态模式下，数据绑定路径推导也会优先使用该目录中的 `data_capabilities.json`。这样 DSL 引用 `/data/...` 时，会按 `cloud-new` 当前版本的真实 `outputSchema` 判断，而不是使用 `scripts/rules/schemas/` 里的静态小样本。

如果没有传 `--capabilities-dir`，动态模式不会回退到静态小样本 schema；只要 DSL 引用路径落在本次 effective data binding 的 `writeResultTo` 下，就不会因为静态清单缺失而误报。

## 全局参数

- `--format text|json|model`：输出格式，默认 `text`。
- `--stage hard|semantic|quality|all`：校验阶段，默认 `all`。
- `--max-errors N`：最多输出多少条 error，默认 `50`。
- `--strict`：warning 也导致退出码为 `1`。
- `--stop-on-stage-error`：hard/semantic 出错后停止后续阶段。
- `--capabilities-dir`：`cloud-new` 能力目录，用于解析素材 id 和动态数据路径。
- `--enable-aesthetic`：显式开启美学质检模块（默认关闭，见下方“美学模块状态”）。

退出码：`0` 无 error；`1` 存在 error，或指定 `--strict` 且存在 warning。

## Python API

`cloud-new` 可以直接调用 API，不必起子进程跑 CLI。

动态校验完整 artifact：

```python
from pathlib import Path
import sys

sys.path.insert(0, "scripts")

from validators import ValidationOptions, validate_card

reporter = validate_card(
    artifact=artifact_dict,
    options=ValidationOptions(
        capabilities_dir=Path("cloud-new/cloud/data/capabilities/app-11.7.5.205_rom-36"),
    ),
)

if reporter.error_count:
    print(reporter.render_json())
```

动态校验 JSONL + CardSpec：

```python
reporter = validate_card(
    dsl_text=genui,
    cardspec=card_spec,
    effective_capabilities={
        "data": ["ViewWeather"],
        "event": [],
        "asset": [],
    },
)
```

静态校验：

```python
reporter = validate_card(
    dsl_text=genui,
    cardspec=card_spec,
)
```

## 动态校验边界

动态 effective 校验等价于“最终 DSL/CardSpec 是否使用了 effective 白名单之外的能力”。它不做：

- 不检查候选能力是否合理。
- 不复算 `DeviceCapabilityResolver`。
- 不判断 removed 是否完整、原因是否正确。
- 不判断 effective 本身是否过滤正确。

## 校验阶段与流水线

三阶段固定顺序，由 `--stage` 控制截止点：

| 阶段 | 触发条件 | 参与 validator |
| --- | --- | --- |
| `hard` | 协议/结构错误必须先修 | `ProtocolValidator`、`ComponentValidator`、`CardSpecValidator`、`ExpressionValidator`、`AssetValidator` |
| `semantic` | 结构 OK 后跑语义规则 | `BindingValidator`、`CrossValidator`、`EffectiveCapabilityValidator`（仅动态模式） |
| `quality` | 语义 OK 后跑质量规则 | `ColorValidator`；`QualityValidator` 仅在 `--enable-aesthetic` 时加入 |

默认 `--stage all` 即三阶段全跑；`--stop-on-stage-error` 会在 hard 出错后跳过 semantic、任一阶段累计出 error 后跳过 quality，用于交互式修复减少回合。若 JSONL 出现 `DSL_JSON_PARSE_FAILED`（属于 hard 阶段的致命错），流水线会整体停在解析层不再往后走。

## 目录结构

```text
scripts/
  validate_card.py                  # CLI 入口
  README.md
  rules/
    config/
      protocol.json                 # 协议、组件、CardSpec、模板 children、事件 handler 结构规则
      layout.json                   # 布局/字号/间距/美学阈值（当前仅美学模块读取）
      style.json                    # createSurface 允许样式、颜色字段清单等
      color.json                    # 颜色格式与 token 命名规则
      asset.json                    # 资源路径禁止模式与 allowlist
      expression.json               # 表达式长度、括号深度、禁用变量/操作符/关键字、允许函数
      diagnostics.zh-CN.json        # 错误码 → 中文默认 message/fixHint
    schemas/
      capability.calendar.schema.json  # 静态数据能力小样本
      capability.weather.schema.json
      event.click.schema.json       # 事件能力 schema（onClick 参数校验用）
  validators/
    __init__.py                     # 只导出 validate_card / ValidationOptions
    api.py                          # 顶层：串联 inputs → context → pipeline
    inputs.py                       # dsl/cardspec/artifact/effective 的解析与归一化
    effective_loader.py             # 动态模式：能力目录加载、asset/data 解析
    pipeline.py                     # validator 列表、stage 选择、短路
    rule_registry.py                # 集中加载 rules/ 下所有配置
    context.py                      # ValidationContext 数据模型
    source_parser.py                # JSONL/CardSpec/artifact 解析、表达式与模板上下文抽取
    diagnostics.py                  # Diagnostic + Reporter，负责聚合、限流、渲染
    base.py                         # BaseValidator + JSON Pointer / 表达式 / 数值工具函数
    protocol_validator.py           # hard 阶段
    component_validator.py          # hard 阶段
    cardspec_validator.py           # hard 阶段
    expression_validator.py         # hard 阶段
    asset_validator.py              # hard 阶段
    binding_validator.py            # semantic 阶段
    cross_validator.py              # semantic 阶段
    effective_capability_validator.py # semantic 阶段（动态模式）
    color_validator.py              # quality 阶段
    aesthetic/                      # 可选美学子系统（仅 --enable-aesthetic）
      __init__.py                   # 导出 QualityValidator
      validator.py                  # BaseValidator 包装（原 quality_validator.py）
      engine.py                     # 独立美学分析引擎（原 validate_aesthetic.py）
```

## 美学模块状态

美学质检（`validators/aesthetic/`）保留在源码中，但默认不参与流水线：

- 默认 `--stage all` 不再触发它，`validate_card` 不会因它产生 warning/error。
- 加 `--enable-aesthetic` 才在 quality 阶段独立跑并输出 `AESTHETIC_*` 诊断。
- `layout.json` 里的 `defaultPadding`/`allowedFontSizes`/`allowedSpacing`/`qualityWeights` 等阈值当前只被这个模块读取；美学模块还会尝试从 `layout.json` 读取 `contrast*` / `max*` 等键，若缺失回退到内置默认。静态色板 / 字号阈值与本地 2x2 模板对齐前，默认关闭以避免误报。
- 美学模块整体位于 `validators/aesthetic/`：`engine.py` 是纯分析引擎，`validator.py` 只是流水线包装；核心流水线不会在 `--enable-aesthetic` 关闭时 import 到 engine 的内部符号。

## Validator 与 rules 对应表

流水线里每个 validator 都通过 `RuleRegistry`（`rules/config/*.json` + `rules/schemas/*.json` + `reference/design/*.md` 若干条目）读取规则，validator 自身不硬编码具体阈值；下表列出实际的读取关系。

### hard 阶段

| Validator | 读取的规则来源 | 主要检查 |
| --- | --- | --- |
| `ProtocolValidator` | `protocol.json` → `version` / `messageOrder` / `messageRequiredFields` / `messageNonEmptyFields` / `catalogIds` / `structureFieldsNoExpression`；`style.json` → `createSurfaceAllowedStyles` | 三行 JSONL 顺序、`version` 固定、必填字段非空、`surfaceId` 三行一致、`catalogId` 合法、`updateDataModel.path` 是结构 Pointer、`createSurface.styles` 只允许外壳形状字段 |
| `ComponentValidator` | `protocol.json` → `commonTopLevelFields` / `componentCommonRequiredFields` / `componentNonEmptyRequiredFields` / `componentTopLevelFields` / `componentRequiredFields` / `forbiddenComponentFields` / `templateComponents` / `templateChildren.allowedKeys` / `templateChildren.requiredKeys` / `eventHandlerForbiddenFields` / `allowedComponents`（`RuleRegistry.allowed_components`） | 组件 id 唯一、`root` 存在、组件类型在白名单、顶层字段/必填字段满足配置、`onClick` 数量与禁用键、模板 children 结构 |
| `CardSpecValidator` | `protocol.json` → `sizes` 键作为允许 `suggestSize`、`cardSpec.topLevelFields` / `requiredFields` / `staticStringLimits` / `dataBindingRequiredFields` / `writeResultToPrefix` | CardSpec 顶层字段、必填、静态字符串上限、`suggestSize` 合法、`dataBindings` 每项必填、`writeResultTo` 前缀与重叠 |
| `ExpressionValidator` | `expression.json` → `maxLength` / `maxParenDepth` / `bannedVariables` / `bannedOperators` / `bannedKeywords` / `allowedFunctions` | 表达式是否完整包裹、长度、括号深度、禁用变量/操作符/关键字、只允许声明的内置函数；结构字段（id/component/EventHandler.call/as/模板 children.path）禁止表达式 |
| `AssetValidator` | `asset.json` → `forbiddenPatterns`；`RuleRegistry.asset_allowlist`（来自 `asset.json.allowlist` + `reference/design/asset-library.md` 的 `resources/base/media/*.svg`） | 禁止 http/https、data image、base64；静态模式下资源路径必须在 allowlist 内；动态模式跳过 allowlist，交给 `EffectiveCapabilityValidator` |

### semantic 阶段

| Validator | 读取的规则来源 | 主要检查 |
| --- | --- | --- |
| `BindingValidator` | `RuleRegistry.capabilities`（从 `rules/schemas/capability.*.schema.json` 加载的静态数据能力）；`rules/schemas/event.click.schema.json` → `functions`；动态模式改读 `context.effective_data_capabilities` | `dataBindings[].capabilityId` 与 `arguments` 是否匹配 capability schema；`writeResultTo` 是否与建议一致；模板 `children.path` 指向数组；表达式 JSON Pointer 能否从 `updateDataModel.value` 或 `writeResultTo + outputSchema` 推导；`onClick` 是否符合 `event.click.schema.json` 声明（含 `clickToIntent.intentName/params`） |
| `CrossValidator` | `protocol.json` → `sizes`；`RuleRegistry.capabilities`（静态能力 schema） | `CardSpec.suggestSize` 与 `createSurface.width/height` 对应实际尺寸预算；`writeResultTo` 根结构是否在 `updateDataModel.value` 初始化；capability 是否声明了 `outputSchema` |
| `EffectiveCapabilityValidator` | 仅动态模式：`context.effective_capabilities`（`data/event/asset`）+ `context.effective_asset_sources` + `context.effective_data_capabilities`；不读 `rules/` | `dataBindings[].capabilityId` 是否在 effective.data；DSL `/data/...` 是否在 effective 数据能力的 `writeResultTo` 覆盖之下；`onClick` 是否与 effective.event 中的 `{call,args}` 精确匹配；`Image.src` / `backgroundImage` 是否命中 effective.asset 解析出的 src |

### quality 阶段

| Validator | 读取的规则来源 | 主要检查 |
| --- | --- | --- |
| `ColorValidator` | `color.json` → `tokenNamePattern`；`style.json` → `colorStyleFields`；`RuleRegistry.allowed_color_hex`（来自 `color.json.tokens` + `sceneExtensions` + `reference/design/color-token-values.md` + `color-token-system.md` 里出现的所有 `#RRGGBB(AA)`） | 颜色字段格式（`#RRGGBB` / `#RRGGBBAA`）、禁止直接输出 token 名、`linearGradient` 结构；未回溯到 token/多彩色/场景拓展色的 hex 记 warning |
| `QualityValidator` | `layout.json` 中的美学阈值（对比度、字号/圆角/阴影层级上限等）；委托 `aesthetic/engine.py` | 仅在 `--enable-aesthetic` 时启用，产出 `AESTHETIC_*` 诊断和 0–100 质量分 |

### 规则文件到 validator 的反查表

- `rules/config/protocol.json` → `ProtocolValidator`、`ComponentValidator`、`CardSpecValidator`、`CrossValidator`。其中 `forbiddenComponents` 与 `structureFieldsNoExpression` 目前作为规则声明留存，validator 未直接读取（组件白名单 + 各 validator 里对结构字段的表达式禁令已覆盖等价约束）。
- `rules/config/expression.json` → `ExpressionValidator`。
- `rules/config/style.json` → `ProtocolValidator`（`createSurfaceAllowedStyles`）、`ColorValidator`（`colorStyleFields`）；其余字段目前给模型/文档使用，validator 未直接读。
- `rules/config/color.json` → `ColorValidator`（含 `RuleRegistry.allowed_color_hex` 汇总）；`forbidRawTokenNames`、`maxPrimaryColorFamilies` 目前仅作为规则声明留存。
- `rules/config/asset.json` → `AssetValidator`（含 `RuleRegistry.asset_allowlist` 汇总）。
- `rules/config/layout.json` → `QualityValidator` / `aesthetic/engine.py`（仅美学模块）。
- `rules/config/diagnostics.zh-CN.json` → `Reporter`：为 `add()` 未显式传 `message/fixHint` 的诊断提供默认中文文案。
- `rules/schemas/capability.*.schema.json` → `RuleRegistry.capabilities`，被 `BindingValidator`、`CrossValidator` 用作静态数据能力；动态模式下这些会被 `context.effective_data_capabilities` 覆盖。
- `rules/schemas/event.click.schema.json` → `BindingValidator._check_event_handlers`。
- `reference/design/asset-library.md`、`color-token-values.md`、`color-token-system.md` → `RuleRegistry` 在构造 `asset_allowlist` 和 `allowed_color_hex` 时会扫描其中的资源路径/hex 值，作为 rules 文件的补充白名单。
- 组件目录 / 表达式语法 / CardSpec JSON Schema 参考文档：真相源已迁移到 `protocol.json`、`expression.json`、`protocol.json.cardSpec`；供人阅读的说明由 `reference/protocol/*.md` 承担，`rules/` 下不再冗余保留。
