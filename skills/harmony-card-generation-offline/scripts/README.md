# Datamodel-First 卡片校验器

`scripts` 目录用于校验 HarmonyOS A2UI Form 卡片产物。

下文命令默认在 `skills/harmony-card-generation-offline/` 目录下运行；如果在仓库根目录运行，将 `python scripts/validate_card.py` 替换为 `python skills/harmony-card-generation-offline/scripts/validate_card.py`。

校验分两类：

- 静态校验：按 `scripts/rules/` 中的静态能力清单和协议规则校验。
- 动态 effective 校验：按本次 `cloud-new` 过滤后的 `effectiveCapabilities` 校验能力使用。

两者的校验范围应保持一致：协议、组件、CardSpec、表达式、绑定、布局、颜色、质量等规则都相同；区别只在数据/事件/素材能力校验的来源不同。

## 一、静态校验

静态校验是默认模式，不需要传 `--effective`。

### 1. JSONL + CardSpec

分别传入 genui JSONL 和 CardSpec：

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

### 2. JSONL

只校验 genui JSONL：

```bash
python scripts/validate_card.py --dsl out.genui.jsonl
```

适合只检查 JSONL 语法、协议行顺序、组件结构、表达式、素材基础安全规则等。缺少 CardSpec 时，跨文件一致性和数据能力 schema 推导会受限。

### 3. CardSpec

只校验 CardSpec：

```bash
python scripts/validate_card.py --cardspec out.cardspec.json
```

适合只检查 CardSpec 必填字段、尺寸、`dataBindings` 基础形态和 `writeResultTo` 冲突。

## 二、动态 effective 校验

动态校验是在同一套静态规则基础上，把能力相关校验切换为本次过滤后的 effective 白名单。

动态校验不复算候选过滤，不判断 removed 原因，只检查最终 DSL/CardSpec 是否使用了 `effectiveCapabilities` 之外的数据、事件、素材能力。

动态 effective 校验运行在 semantic 阶段。默认 `--stage all` 会覆盖它；如果指定 `--stage hard`，不会运行动态能力校验。

### 1. JSONL + CardSpec

分别传入 JSONL、CardSpec 和 effective 能力：

```bash
python scripts/validate_card.py \
  --dsl out.genui.jsonl \
  --cardspec out.cardspec.json \
  --effective effective.json
```

如果输入是完整 `WidgetArtifact` JSON，且包含 `genui`、`cardSpec`、`taskSpec`、`effectiveCapabilities`：

```bash
python scripts/validate_card.py --artifact artifact.json
```

这是推荐接入方式，因为数据、事件、素材三类能力都有足够上下文。

### 2. JSONL

只传 JSONL 和 effective 能力：

```bash
python scripts/validate_card.py \
  --dsl out.genui.jsonl \
  --effective effective.json
```

这种模式仍会运行与静态 JSONL 校验相同的协议、组件、表达式、素材基础安全等规则，并额外使用 effective 白名单检查：

- DSL 中 `onClick[].call + args` 是否来自 `effectiveCapabilities.event`。
- DSL 中 `Image.src` / `backgroundImage` 是否来自 `effectiveCapabilities.asset` 解析出的资源路径。

注意：只传 JSONL 时缺少 `CardSpec.dataBindings[].writeResultTo`，因此无法完整判断 `/data/...` 路径是否落在有效数据能力写入路径下。若 DSL 引用了 `/data/...`，建议使用 `JSONL + CardSpec` 模式。

### 3. CardSpec

只传 CardSpec 和 effective 能力：

```bash
python scripts/validate_card.py \
  --cardspec out.cardspec.json \
  --effective effective.json
```

这种模式仍会运行与静态 CardSpec 校验相同的 CardSpec 必填字段、尺寸、`dataBindings` 基础形态、`writeResultTo` 冲突等规则，并额外检查：

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
      "args": {
        "uri": "weather://home"
      }
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

如果 effective 中只有素材 id，需要让校验器能把 id 解析成 `src`。解析优先级：

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
- `--capabilities-dir`：`cloud-new` 能力目录，用于解析素材 id。

退出码：

- `0`：无 error。
- `1`：存在 error；或指定 `--strict` 且存在 warning。

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

动态 effective 校验等价于检查“最终 DSL/CardSpec 有没有使用 effective 白名单之外的能力”。

它不做：

- 不检查候选能力是否合理。
- 不复算 `DeviceCapabilityResolver`。
- 不判断 removed 是否完整。
- 不判断 removed 原因是否正确。
- 不判断 effective 本身是否过滤正确。

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
    api.py
    asset_validator.py
    base.py
    binding_validator.py
    cardspec_validator.py
    color_validator.py
    component_validator.py
    context.py
    cross_validator.py
    diagnostics.py
    effective_capability_validator.py
    expression_validator.py
    protocol_validator.py
    quality_validator.py
    rule_registry.py
    source_parser.py
```

## Validator 职责

- `protocol_validator.py`：校验三行 JSONL 顺序、version、surfaceId、消息必填字段等。
- `component_validator.py`：校验组件类型、id、root、children、组件字段白名单等。
- `cardspec_validator.py`：校验 CardSpec 必填字段、尺寸、`dataBindings` 基础形态和 `writeResultTo` 冲突。
- `expression_validator.py`：校验表达式形态、禁用字段、结构字段表达式等。
- `asset_validator.py`：校验素材路径基础安全规则；动态模式下跳过静态 allowlist，由 effective 校验器接管。
- `binding_validator.py`：校验 DataModel 路径、模板路径、事件参数等；动态模式下跳过静态能力清单检查。
- `effective_capability_validator.py`：校验最终 DSL/CardSpec 是否只使用本次过滤后的数据、事件、素材能力。
- `cross_validator.py`：校验 DSL 和 CardSpec 的尺寸、数据契约交叉一致性。
- `color_validator.py`：校验颜色格式和 token。
- `quality_validator.py`：校验布局、样式、文本适配、质量分等。
